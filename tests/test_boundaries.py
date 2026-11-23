"""Display outlines: shared edges stay shared, levels merge by code, names survive."""

import json

import numpy as np
import pytest

shapely = pytest.importorskip("shapely")
from shapely.geometry import Polygon, box, shape  # noqa: E402

from ntl import boundaries  # noqa: E402


def wiggly_pair():
    """Two polygons sharing a wiggly edge near x = 1; together they fill the box (0, 0) to (2, 1).

    The wiggle is a row of triangles of area 2e-7 (base 0.002, height
    0.0002): its square root, 0.00045, is under the tolerance of 0.003.
    """
    ys = np.arange(0.0, 1.0001, 0.001)
    xs = 1.0 + 0.0002 * (np.arange(ys.size) % 2)
    xs[[0, -1]] = 1.0
    edge = list(zip(xs.tolist(), ys.tolist()))
    west = Polygon([(0, 0), *edge, (0, 1)])
    east = Polygon([(2, 0), (2, 1), *reversed(edge)])
    return west, east


def test_a_shared_edge_is_simplified_once_for_both_neighbours():
    west, east = wiggly_pair()
    simple, how = boundaries.simplify_coverage([west, east], 0.003)
    assert how == "coverage"
    assert shapely.get_num_coordinates(simple).sum() < 0.1 * shapely.get_num_coordinates([west, east]).sum()
    # No gap and no overlap: the two still fill the box exactly.
    assert simple[0].intersection(simple[1]).area == pytest.approx(0.0, abs=1e-12)
    assert simple[0].union(simple[1]).area == pytest.approx(2.0, abs=1e-9)


def test_overlapping_polygons_are_reported_as_not_a_coverage():
    simple, how = boundaries.simplify_coverage([box(0, 0, 1, 1), box(0.5, 0, 1.5, 1)], 0.003)
    assert how == "coverage_invalid_input" and len(simple) == 2


def test_levels_merge_by_code_and_leave_out_code_zero():
    parts = [box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1), box(3, 0, 4, 1)]
    units = boundaries.merge_level(parts, [5208, 5208, 5271, 0], ["Lombok Utara", "Lombok Utara", "Mataram", None])
    assert [(code, name) for code, name, _ in units] == [(5208, "Lombok Utara"), (5271, "Mataram")]
    assert units[0][2].equals(box(0, 0, 2, 1))          # two features, one outline
    with pytest.raises(TypeError, match="integers"):
        boundaries.merge_level(parts, [5208.0, 5208.0, 5271.0, 0.0], [None] * 4)
    with pytest.raises(ValueError, match="same length"):
        boundaries.merge_level(parts, [5208, 5271], [None, None])


def test_the_name_most_features_carry_wins_and_blanks_do_not_count():
    assert boundaries.most_common_name(["Pati", "Pati", "PATI", None, float("nan"), "  "]) == "Pati"
    assert boundaries.most_common_name([None, float("nan"), ""]) is None


def test_features_are_rounded_and_stay_valid():
    units = [(52, "A", Polygon([(116.123456, -8.5), (116.2, -8.5), (116.2, -8.4), (116.123456, -8.4)])),
             (53, None, box(0, 0, 0.00001, 0.00001))]        # smaller than the rounding grid
    collection = boundaries.feature_collection(units, decimals=4)
    assert [f["properties"] for f in collection["features"]] == [{"code": 52, "name": "A"}]
    geometry = shape(collection["features"][0]["geometry"])
    assert geometry.is_valid
    xs = np.array(geometry.exterior.coords)[:, 0]
    np.testing.assert_allclose(xs, np.round(xs, 4), atol=1e-12)
    json.dumps(collection)                                    # plain JSON all the way down


def test_outlines_of_three_levels_from_a_file(tmp_path):
    gpd = pytest.importorskip("geopandas")
    west, east = wiggly_pair()
    frame = gpd.GeoDataFrame(
        dict(a1siak=[52, 52, 52], a2siak=[5208, 5208, 5271], a3siak=[520801, 0, 527101],
             a1name=["NTB", "NTB", "NTB"], a2name=["Lombok Utara", "Lombok Utara", "Mataram"], a3name=["Tanjung", None, "Ampenan"]),
        geometry=[west, east, box(2, 0, 3, 1)], crs="EPSG:4326")
    path = tmp_path / "units.geojson"
    frame.to_file(path, driver="GeoJSON")
    collections, report = boundaries.build_outlines(path)
    codes = {level: [f["properties"]["code"] for f in collections[level]["features"]] for level in collections}
    assert codes == {"province": [52], "district": [5208, 5271], "subdistrict": [520801, 527101]}
    # The feature with no sub-district code is still inside its district's outline.
    district = shape(collections["district"]["features"][0]["geometry"])
    assert district.area == pytest.approx(2.0, abs=1e-6)
    assert report["method"] == "coverage" and report["features"] == 3
    paths = boundaries.write_outlines(collections, report, tmp_path / "out")
    assert json.loads(paths["district"].read_text(encoding="utf-8"))["features"][1]["properties"]["name"] == "Mataram"
    assert json.loads((tmp_path / "out" / "outlines_report.json").read_text(encoding="utf-8"))["levels"]["province"]["bytes"] > 0
    with pytest.raises(ValueError, match="no field a3name"):
        frame.drop(columns="a3name").to_file(tmp_path / "bad.geojson", driver="GeoJSON")
        boundaries.build_outlines(tmp_path / "bad.geojson")


def test_bad_tolerances_and_missing_geometries_are_refused():
    for tolerance in (-1.0, 0.0, float("nan")):
        with pytest.raises(ValueError, match="tolerance"):
            boundaries.simplify_coverage([box(0, 0, 1, 1)], tolerance)
    with pytest.raises(ValueError, match="no geometry"):
        boundaries.simplify_coverage([box(0, 0, 1, 1), None], 0.003)


def test_command_line_writes_three_levels_and_ends_cleanly_on_bad_input(tmp_path):
    gpd = pytest.importorskip("geopandas")
    west, east = wiggly_pair()
    frame = gpd.GeoDataFrame(
        dict(a1siak=[52, 52], a2siak=[5208, 5271], a3siak=[520801, 527101],
             a1name=["NTB", "NTB"], a2name=["Lombok Utara", "Mataram"], a3name=["Tanjung", "Ampenan"]),
        geometry=[west, east], crs="EPSG:4326")
    source = tmp_path / "units.geojson"
    frame.to_file(source, driver="GeoJSON")
    out = tmp_path / "outlines"
    assert boundaries.main(["--boundaries", str(source), "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["district.geojson", "outlines_report.json", "province.geojson", "subdistrict.geojson"]
    report = json.loads((out / "outlines_report.json").read_text(encoding="utf-8"))
    assert report["tolerance_deg"] == 0.003 and report["source"]["file"] == "units.geojson"
    # Inputs that cannot be used end with status 1, not a traceback.
    assert boundaries.main(["--boundaries", str(tmp_path / "absent.shp"), "--out", str(out)]) == 1
    (tmp_path / "text.shp").write_text("not a shapefile", encoding="utf-8")
    assert boundaries.main(["--boundaries", str(tmp_path / "text.shp"), "--out", str(out)]) == 1
    assert boundaries.main(["--boundaries", str(source), "--out", str(out), "--tolerance", "-1"]) == 1
    assert boundaries.main(["--boundaries", str(source), "--out", str(source)]) == 1    # a file is not a folder
    projected = frame.to_crs("EPSG:3857")
    projected.to_file(tmp_path / "metres.geojson", driver="GeoJSON")
    assert boundaries.main(["--boundaries", str(tmp_path / "metres.geojson"), "--out", str(out)]) == 1
