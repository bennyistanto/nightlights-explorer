"""Export: encodings round-trip, bundles hold the right units, files are all named."""

import datetime as dt
import gzip
import json

import numpy as np
import pytest

from ntl import conventions as c
from ntl import export, monitor
from ntl.stack import TileStack

T = 30
CELL = c.CELL_SIZE_DEG


def tiny_stack():
    """Six cells in two provinces; one cell is held by its district (sub-district 0).

    cell:         0       1       2       3       4       5
    sub-district: 520801  520801  520802  0       530101  530101
    district:     5208    5208    5208    5208    5301    5301
    """
    months = tuple(dt.date(2020 + i // 12, i % 12 + 1, 1) for i in range(T))
    subdistrict = np.array([520801, 520801, 520802, 0, 530101, 530101])
    district = np.array([5208, 5208, 5208, 5208, 5301, 5301])
    rng = np.random.default_rng(3)
    usual = np.array([5.0, 10.0, 20.0, 4.0, 30.0, 6.5])
    value = (usual * np.exp(rng.normal(0, 0.05, (T, 6)))).astype(np.float32)
    # Cell centres on the global grid, deliberately not in grid order.
    lon = 116.0 + (np.array([3, 1, 2, 0, 5, 4]) + 0.5) * CELL
    lat = -8.0 - (np.array([0, 0, 1, 1, 0, 1]) + 0.5) * CELL
    return TileStack(
        tile="h29v09", view="AllAngle", months=months, lon=lon, lat=lat,
        province=district // 100, district=district, subdistrict=subdistrict, usual=usual,
        value=value, nights=np.full((T, 6), 10, dtype=np.uint16), quality=np.zeros((T, 6), dtype=np.uint8))


@pytest.fixture(scope="module")
def stack():
    return tiny_stack()


@pytest.fixture(scope="module")
def run(stack, tmp_path_factory):
    levels = monitor.run_levels(stack)
    path = monitor.save_levels(levels, stack, tmp_path_factory.mktemp("run") / "run.npz")
    return monitor.load_levels(path)


@pytest.fixture(scope="module")
def site(stack, run, tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    square = {"type": "Polygon", "coordinates": [[[116, -9], [117, -9], [117, -8], [116, -8], [116, -9]]]}

    def collection(units):
        return {"type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {"code": k, "name": n}, "geometry": square} for k, n in units]}

    outlines = {
        "province": collection([(52, "Nusa Tenggara Barat"), (53, "Nusa Tenggara Timur")]),
        "district": collection([(5208, "Lombok Utara"), (5301, "Kupang")]),
        "subdistrict": collection([(520801, "Tanjung"), (520802, "Gangga"), (530101, None), (530199, "No lit cell")]),
    }
    report = export.export_site(stack, run, out, outlines)
    return out, report


def gunzip(path):
    return gzip.decompress(path.read_bytes())


# ---- encodings ---------------------------------------------------------------


def test_encode_rounds_marks_missing_and_counts_what_it_clips():
    stored, clipped = export.encode([0.0, -0.6931, np.nan, 40.0, -40.0], "<i2", 1000, -32768)
    assert stored.tolist() == [0, -693, -32768, 32767, -32767]   # the missing code is never a clipped value
    assert clipped == 2
    stored, clipped = export.encode([0.0, 1.0, np.nan, 2.0], "u1", 200, 255)
    assert stored.tolist() == [0, 200, 255, 254] and clipped == 1
    with pytest.raises(ValueError, match="not finite"):
        export.encode([1.0, np.nan], "u1", 1, None)


def test_cell_index_is_row_major_from_the_north_west_and_refuses_off_grid_points():
    # The cell whose corner is 180 W, 90 N is 0; one cell east is 1; one cell south is one row on.
    assert export.cell_index([-180 + CELL / 2], [90 - CELL / 2]).tolist() == [0]
    assert export.cell_index([-180 + 1.5 * CELL], [90 - CELL / 2]).tolist() == [1]
    assert export.cell_index([-180 + CELL / 2], [90 - 1.5 * CELL]).tolist() == [export.GLOBAL_COLUMNS]
    assert export.GLOBAL_COLUMNS == 86400
    with pytest.raises(ValueError, match="not cell centres"):
        export.cell_index([116.0], [-8.0])   # a cell corner


def test_bundle_ranges_follow_the_province_prefix():
    assert export.bundle_ranges(np.array([52, 53]), "province") == {"all": (0, 2)}
    assert export.bundle_ranges(np.array([5208, 5271, 5301]), "district") == {"52": (0, 2), "53": (2, 1)}
    assert export.bundle_ranges(np.array([520801, 520802, 530101]), "subdistrict") == {"52": (0, 2), "53": (2, 1)}
    with pytest.raises(ValueError, match="ascending"):
        export.bundle_ranges(np.array([5301, 5208]), "district")


# ---- the run file --------------------------------------------------------------


def test_a_saved_run_reads_back_unchanged(stack, run):
    again = monitor.run_levels(stack)
    assert run.months == stack.months and list(run.levels) == list(c.ADMIN_LEVELS)
    assert run.info["until"] is None and run.info["view"] == "AllAngle" and run.info["seasonal"] is False
    for level in c.ADMIN_LEVELS:
        for name in ("codes", "state", "anomaly", "scale", "held", "joint", "monitorable", "watch"):
            np.testing.assert_array_equal(getattr(run.levels[level], name), getattr(again[level], name))
        np.testing.assert_array_equal(run.levels[level].series.index, again[level].series.index)
        np.testing.assert_array_equal(run.levels[level].series.cells, again[level].series.cells)
    assert run.levels["subdistrict"].codes.tolist() == [520801, 520802, 530101]


def test_a_file_that_is_not_a_run_is_refused(tmp_path):
    np.savez_compressed(tmp_path / "other.npz", months=np.array(["2020-01-01"]))
    with pytest.raises(ValueError, match="not a run file"):
        monitor.load_levels(tmp_path / "other.npz")
    with pytest.raises(FileNotFoundError):
        monitor.load_levels(tmp_path / "absent.npz")


# ---- the site folder -----------------------------------------------------------


def test_every_bundle_decodes_to_the_run_within_its_precision(site, run):
    out, _ = site
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    for level in c.ADMIN_LEVELS:
        result = run.levels[level]
        columns = export.bundle_columns(result)
        seen = 0
        for bundle in meta["level_detail"][level]["bundles"].values():
            got = export.unpack_bundle(gunzip(out / bundle["file"]), T, bundle["count"])
            units = slice(bundle["first"], bundle["first"] + bundle["count"])
            seen += bundle["count"]
            for name, _, scale, missing in c.BUNDLE_COLUMNS:
                want = np.asarray(columns[name])[:, units]
                if missing is None:
                    np.testing.assert_array_equal(got[name], want)
                else:
                    assert np.array_equal(np.isnan(got[name]), ~np.isfinite(want))
                    np.testing.assert_allclose(got[name], want, atol=0.5 / scale + 1e-12, equal_nan=True)
        assert seen == result.codes.size


def test_flags_carry_the_three_booleans(site, run):
    out, _ = site
    result = run.levels["subdistrict"]
    got = export.unpack_bundle(gunzip(out / "subdistrict" / "52.bin.gz"), T, 2)["flags"]
    np.testing.assert_array_equal(got & export.FLAG_HELD > 0, result.held[:, :2])
    np.testing.assert_array_equal(got & export.FLAG_JOINT > 0, result.joint[:, :2])
    np.testing.assert_array_equal(got & export.FLAG_MONITORABLE > 0, result.monitorable[:, :2])


def test_a_bundle_of_the_wrong_length_is_refused(site):
    out, _ = site
    with pytest.raises(ValueError, match="expected"):
        export.unpack_bundle(gunzip(out / "subdistrict" / "52.bin.gz"), T, 3)


def test_cells_are_sorted_and_point_at_their_units(site, stack):
    out, _ = site
    index = np.frombuffer(gunzip(out / "cells.u32.gz"), dtype="<u4")
    assert (np.diff(index.astype(np.int64)) > 0).all()
    order = np.argsort(export.cell_index(stack.lon, stack.lat))
    usual = np.frombuffer(gunzip(out / "cell_usual.u16.gz"), dtype="<u2")
    np.testing.assert_allclose(usual / export.USUAL_SCALE, stack.usual[order], atol=0.05 + 1e-9)
    units = json.loads((out / "units_subdistrict.json").read_text(encoding="utf-8"))
    position = np.frombuffer(gunzip(out / "cell_subdistrict.u16.gz"), dtype="<u2")
    codes = np.array([0] + units["code"])[position]              # 0 = held by the district
    np.testing.assert_array_equal(codes, stack.subdistrict[order])
    assert (position == 0).sum() == 1
    # Light of a unit is the sum of its cells' usual radiance.
    assert units["light"] == [15.0, 20.0, 36.5] and units["cells"] == [2, 1, 2]


def test_units_carry_names_and_the_reporting_level(site, run):
    out, _ = site
    units = json.loads((out / "units_subdistrict.json").read_text(encoding="utf-8"))
    assert units["name"] == ["Tanjung", "Gangga", None]
    # Nothing is monitorable in so short a record: no unit can be reported.
    assert not run.levels["subdistrict"].monitorable.any()
    assert units["reporting"] == [c.REPORT_NONE] * 3
    assert json.loads((out / "units_district.json").read_text(encoding="utf-8"))["name"] == ["Lombok Utara", "Kupang"]
    assert "reporting" not in json.loads((out / "units_province.json").read_text(encoding="utf-8"))


def test_meta_says_what_the_run_rests_on(site):
    out, _ = site
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["months"][0] == "2020-01" and meta["windows"] == T
    assert meta["source"]["domain"]["look_ahead"] is True and meta["source"]["retrospective"] is False
    assert meta["source"]["children_rule_applied"] is False
    assert meta["status"][str(c.STATUS_REGIONAL)] == "regional"
    assert [col["name"] for col in meta["encoding"]["columns"]] == [name for name, *_ in c.BUNDLE_COLUMNS]
    assert meta["level_detail"]["province"]["tiers"] is False and meta["level_detail"]["district"]["tiers"] is True
    # Factors by window: none exists in so short a record, and none is written as NaN.
    assert meta["level_detail"]["district"]["factors"]["alarm"] == [None] * T
    assert meta["level_detail"]["subdistrict"]["without_outline"] == 0
    assert meta["latest"] == {"window": T - 1, "month": "2022-06", "rule": meta["latest"]["rule"], "used_for": meta["latest"]["used_for"]}


def test_every_file_is_listed_and_named_by_a_literal(site):
    out, report = site
    on_disk = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert on_disk == set(report["files"]) | {"export_report.json"}
    assert report["total_bytes"] == sum(report["files"].values()) <= report["budget_bytes"]
    assert report["files_listed"] == len(report["files"])
    assert {name: (out / name).stat().st_size for name in report["files"]} == report["files"]
    js = (out / "files.js").read_text(encoding="utf-8")
    for name in report["files"]:
        if name != "files.js":
            assert f'FileAttachment("{name}")' in js
    # Sub-district outlines are split by province, and keep units that have no lit cell.
    east = json.loads((out / "outlines" / "subdistrict" / "53.geojson").read_text(encoding="utf-8"))
    assert [f["properties"]["code"] for f in east["features"]] == [530101, 530199]


def test_the_export_is_the_same_bytes_whenever_it_runs(stack, run, tmp_path, monkeypatch):
    import time

    first = export.export_site(stack, run, tmp_path / "a")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 86400.0)      # a day later
    export.export_site(stack, run, tmp_path / "b")
    for name in first["files"]:                                      # every file but the report
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
    # The gzip header carries no time (bytes 4 to 7) and no file name (flag byte 3).
    header = (tmp_path / "a" / "cells.u32.gz").read_bytes()[:8]
    assert header[3] == 0 and header[4:8] == b"\x00\x00\x00\x00"
    assert "created" not in json.loads((tmp_path / "a" / "meta.json").read_text(encoding="utf-8"))


def test_the_latest_window_skips_an_unobserved_end_and_sets_the_reporting_month(stack, run, tmp_path):
    assert export.latest_window(run) == T - 1
    # The same run with a last window in which nothing was seen.
    levels = {}
    for level, result in run.levels.items():
        state = result.state.copy()
        state[-1] = c.STATUS_NOT_OBSERVED
        monitorable = result.monitorable.copy()
        monitorable[-1] = True                      # what the empty window would wrongly claim
        levels[level] = result._replace(state=state, monitorable=monitorable)
    ended = monitor.Run(months=run.months, levels=levels, info=run.info)
    assert export.latest_window(ended) == T - 2
    export.export_site(stack, ended, tmp_path)
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["latest"]["window"] == T - 2 and meta["latest"]["month"] == "2022-05"
    units = json.loads((tmp_path / "units_subdistrict.json").read_text(encoding="utf-8"))
    assert units["reporting"] == [c.REPORT_NONE] * 3   # from the window before the empty one


def test_a_missing_code_inside_the_range_is_refused():
    with pytest.raises(ValueError, match="missing code"):
        export.encode([0.007, np.nan], "u1", 1000, 7)


def test_outlines_are_read_with_their_report_and_checked(tmp_path):
    square = {"type": "Polygon", "coordinates": [[[116, -9], [117, -9], [117, -8], [116, -8], [116, -9]]]}
    good = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"code": 52, "name": "A"}, "geometry": square}]}
    for level in c.ADMIN_LEVELS:
        (tmp_path / f"{level}.geojson").write_text(json.dumps(good), encoding="utf-8")
    (tmp_path / "outlines_report.json").write_text(json.dumps({"tolerance_deg": 0.5, "method": "coverage"}), encoding="utf-8")
    collections, report = export.read_outlines(tmp_path)
    assert list(collections) == list(c.ADMIN_LEVELS) and report["tolerance_deg"] == 0.5
    bad = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "A"}, "geometry": square}]}
    (tmp_path / "district.geojson").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="district.geojson"):
        export.read_outlines(tmp_path)
    (tmp_path / "district.geojson").unlink()
    with pytest.raises(FileNotFoundError, match="ntl.boundaries"):
        export.read_outlines(tmp_path)


def test_units_of_the_run_must_be_the_units_of_the_cells(stack, run, tmp_path):
    import dataclasses

    moved = dataclasses.replace(stack, subdistrict=np.where(stack.subdistrict == 520802, 520803, stack.subdistrict))
    with pytest.raises(ValueError, match="not the units of the stack"):
        export.export_site(moved, run, tmp_path)


def test_a_damaged_run_file_says_run_again(run, stack, tmp_path):
    whole = monitor.save_levels(run.levels, stack, tmp_path / "whole.npz").read_bytes()
    assert [p.name for p in tmp_path.iterdir()] == ["whole.npz"]      # the temporary name is gone
    (tmp_path / "cut.npz").write_bytes(whole[: len(whole) // 2])
    (tmp_path / "text.npz").write_bytes(b"not an archive")
    with open(tmp_path / "single.npz", "wb") as handle:
        np.save(handle, np.arange(3))
    np.savez_compressed(tmp_path / "partial.npz", version=monitor.RUN_FILE_VERSION, levels=np.array(["province"]))
    for name in ("cut.npz", "text.npz", "single.npz", "partial.npz"):
        with pytest.raises(ValueError, match="run the monitor again"):
            monitor.load_levels(tmp_path / name)


def test_mismatched_inputs_and_a_small_budget_are_refused(stack, run, tmp_path):
    shorter = monitor.Run(months=run.months[:-1], levels=run.levels, info=run.info)
    with pytest.raises(ValueError, match="different months"):
        export.export_site(stack, shorter, tmp_path)
    with pytest.raises(ValueError, match="over the budget"):
        export.export_site(stack, run, tmp_path, budget=100)


# ---- the command lines ---------------------------------------------------------


def test_monitor_and_export_run_from_a_cache_folder(stack, tmp_path):
    from ntl import stack as st

    cache = tmp_path / "cache"
    cache.mkdir()
    st.save(stack, st.cache_path(cache, "h29v09"))
    run_file = tmp_path / "run.npz"
    assert monitor.main(["--cache", str(cache), "--out", str(run_file)]) == 0
    # The output folder is made before the run, so a long run is not lost at the end.
    assert monitor.main(["--cache", str(cache), "--out", str(tmp_path / "new" / "deep" / "run.npz")]) == 0
    assert (tmp_path / "new" / "deep" / "run.npz").is_file()
    assert monitor.main(["--cache", str(cache), "--out", str(cache)]) == 1          # a folder is not a file
    assert export.main(["--cache", str(cache), "--run", str(run_file), "--out", str(tmp_path / "site")]) == 0
    meta = json.loads((tmp_path / "site" / "meta.json").read_text(encoding="utf-8"))
    assert meta["outlines"] is None and meta["source"]["cells"] == 6
    assert not (tmp_path / "site" / "outlines").exists()
    # Inputs that cannot be used end with status 1, not a traceback.
    assert monitor.main(["--cache", str(tmp_path / "nothing"), "--out", str(run_file)]) == 1
    assert export.main(["--cache", str(cache), "--run", str(tmp_path / "absent.npz"), "--out", str(tmp_path / "site")]) == 1
    assert export.main(["--cache", str(cache), "--run", str(run_file), "--outlines", str(tmp_path / "nothing"), "--out", str(tmp_path / "site")]) == 1
    assert export.main(["--cache", str(cache), "--run", str(run_file), "--out", str(run_file)]) == 1   # a file is not a folder
    assert meta["source"]["inputs"]["run_file"] == "run.npz"


# ---- the other variables -------------------------------------------------------


def test_the_run_columns_and_the_unit_counts_come_from_persistence(stack, run, tmp_path):
    from ntl import persistence

    # Give the run some low readings: a watch, an unseen month, an alarm, then normal, a regional month and a watch.
    levels = dict(run.levels)
    state = levels["subdistrict"].state.copy()
    state[-6:, 0] = [c.STATUS_WATCH, c.STATUS_NOT_OBSERVED, c.STATUS_ALARM, c.STATUS_NORMAL, c.STATUS_REGIONAL, c.STATUS_WATCH]
    levels["subdistrict"] = levels["subdistrict"]._replace(state=state)
    export.export_site(stack, monitor.Run(months=run.months, levels=levels, info=run.info), tmp_path)
    got = export.unpack_bundle(gunzip(tmp_path / "subdistrict" / "52.bin.gz"), T, 2)
    assert got["run"][-6:, 0].tolist() == [1, 0, 2, 0, 0, 1]
    assert got["span"][-6:, 0].tolist() == [1, 0, 3, 0, 0, 1]
    assert got["unseen"][-6:, 0].tolist() == [0, 1, 0, 0, 0, 0]
    np.testing.assert_array_equal(got["run"], persistence.low_runs(state[:, :2]))
    units = json.loads((tmp_path / "units_subdistrict.json").read_text(encoding="utf-8"))
    assert units["episodes"][0] == 2 and units["longest_run"][0] == 2 and units["longest_span"][0] == 3
    assert units["low_windows"][0] == 3 and units["regional_windows"][0] == 1
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["variables"]["persistence"]["low"] == ["watch", "alarm"] and meta["variables"]["persistence"]["max_silent"] == 3
    assert [col["name"] for col in meta["encoding"]["columns"]][-3:] == ["run", "span", "unseen"]


def test_trend_is_null_on_a_short_record(site):
    from ntl import trend

    out, _ = site
    units = json.loads((out / "units_district.json").read_text(encoding="utf-8"))
    # Thirty months give three yearly values (the third from six months): far under the eight a slope needs.
    assert units["trend"] == [None, None] and units["trend_years"] == [3, 3]
    assert units["trend_core"] == [None, None] and units["core_cells"] == [4, 2]   # every cell is lit from the first year
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["variables"]["trend"]["min_years"] == trend.MIN_YEARS and meta["variables"]["trend"]["years"] == [2020, 2022]
    assert meta["variables"]["trend"]["serial_correlation"] == trend.SERIAL_CORRELATION
    assert meta["variables"]["trend"]["median_by_level"]["district"] == {"all": None, "units": 0}


def test_cell_area_then_and_now_and_lit_area_are_exported(site, stack):
    out, _ = site
    # A 15 arc-second cell at the equator is about 0.2146 km2, and smaller by cos(latitude) elsewhere.
    assert export.cell_area_km2([0.0])[0] == pytest.approx(0.21466, abs=1e-4)
    assert export.cell_area_km2([60.0])[0] == pytest.approx(0.21466 / 2, abs=1e-4)
    units = json.loads((out / "units_subdistrict.json").read_text(encoding="utf-8"))
    order = np.argsort(export.cell_index(stack.lon, stack.lat))
    area = export.cell_area_km2(stack.lat[order])
    assert units["lit_km2"][0] == pytest.approx(area[stack.subdistrict[order] == 520801].sum(), abs=0.006)
    assert units["longest_unseen"] == [0, 0, 0]
    # The fixture has three years: too few for a first and a last period of three.
    assert not (out / "cell_first.u8.gz").exists()


def test_cells_are_exported_month_by_month_in_yearly_files(site, stack):
    from ntl import cellmaps

    out, report = site
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    files = meta["variables"]["cell_maps"]["files"]
    assert list(files) == ["2020", "2021", "2022"] and files["2022"] == {"file": "cells/2022.u8.gz", "first_window": 24, "months": 6}
    order = np.argsort(export.cell_index(stack.lon, stack.lat))
    want = cellmaps.pack(stack.usable()[:, order], stack.nights[:, order])
    got = np.concatenate([np.frombuffer(gunzip(out / files[year]["file"]), dtype=np.uint8).reshape(files[year]["months"], 6) for year in files])
    np.testing.assert_array_equal(got, want)
    radiance, change, seen = cellmaps.unpack(got)
    assert (seen == 3).all() and not change[:12].any() and change[12:].all()   # ten observations every month; a year earlier exists from month 13
    assert "cells/2021.u8.gz" in report["files"]
