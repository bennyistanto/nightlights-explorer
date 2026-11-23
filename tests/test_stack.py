"""Tile reader on synthetic monthly files built to a known answer.

The files are full tile size (2400 x 2400) because the reader checks that a
file sits on its tile's grid, but only a 2 x 4 patch in the north-west
corner carries data; everything else is fill.
"""

import dataclasses
import datetime as dt

import h5py
import numpy as np
import pytest
from shapely.geometry import box

from ntl import conventions as c
from ntl import stack as st
from ntl.read import Grid

SIDE = c.CELLS_PER_TILE
CELL = c.CELL_SIZE_DEG
TILE = "h29v09"  # 110 E to 120 E, 0 to 10 S
GRID = Grid(110.0, 0.0, CELL, (SIDE, SIDE))
MONTHS = [dt.date(2018, m, 1) for m in (1, 2, 3, 5, 6)]  # April has no file
ARRAYS = ("lon", "lat", "province", "district", "subdistrict", "usual", "value", "nights", "quality")

# The patch, row 0 then row 1, columns 0 to 3:
#   A (0,0) lit land in sub-district 520801      -> in the domain
#   B (0,1) dim land (1.0), same sub-district    -> not lit
#   C (0,2) bright but sea                        -> not land
#   D (0,3) bright land outside every polygon     -> no unit
#   E (1,0) bright land, good in only 2 months    -> too few good months
#   F (1,1) lit land held by district 5208 only   -> in the domain, sub-district 0
#   G (1,2) lit land, gap filled in March         -> in the domain
#   H (1,3) coastal and bright                    -> not land
RADIANCE = np.array([[5.0, 1.0, 9.0, 9.0], [9.0, 4.0, 6.0, 9.0]], dtype=np.float32)
CLASSES = np.array([[1, 1, 3, 1], [1, 1, 1, 5]], dtype=np.uint8)


def write_month(root, month, production="2025001000000"):
    folder = root / c.BLACK_MARBLE_DIR / c.MONTHLY_PRODUCT / f"{month.year}" / f"{month:%j}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{c.MONTHLY_PRODUCT}.A{month.year}{month:%j}.{TILE}.002.{production}.h5"
    value = np.full((SIDE, SIDE), -999.9, dtype=np.float32)
    nights = np.full((SIDE, SIDE), c.COMPOSITE_NUM_FILL, dtype=np.uint16)
    quality = np.full((SIDE, SIDE), c.CQ_FILL, dtype=np.uint8)
    classes = np.full((SIDE, SIDE), c.LAND_WATER_FILL, dtype=np.uint8)
    value[:2, :4] = RADIANCE * (1.0 + 0.1 * MONTHS.index(month))  # grows 10% of the base each file
    nights[:2, :4] = 10
    quality[:2, :4] = c.CQ_GOOD
    classes[:2, :4] = CLASSES
    if MONTHS.index(month) >= 2:  # cell E is poor from the third file on
        quality[1, 0], nights[1, 0] = c.CQ_POOR, 2
    if month.month == 3:  # cell G is gap filled in March: a number, no nights
        quality[1, 2], nights[1, 2] = c.CQ_GAP_FILLED, 0
    with h5py.File(path, "w") as f:
        f.attrs["WestBoundingCoord"], f.attrs["EastBoundingCoord"] = 110.0, 120.0
        f.attrs["NorthBoundingCoord"], f.attrs["SouthBoundingCoord"] = 0.0, -10.0
        g = f.create_group(c.GRID_GROUP)
        base = c.COMPOSITE_LAYER.format(view="AllAngle", suffix="")
        kw = dict(compression="gzip", compression_opts=1)
        d = g.create_dataset(base, data=value, **kw)
        d.attrs["_FillValue"] = np.array([np.float32(-999.9)])
        d = g.create_dataset(base + c.COMPOSITE_NUM, data=nights, **kw)
        d.attrs["_FillValue"] = np.array([c.COMPOSITE_NUM_FILL], dtype=np.uint16)
        d = g.create_dataset(base + c.COMPOSITE_QUALITY, data=quality, **kw)
        d.attrs["_FillValue"] = np.array([c.CQ_FILL], dtype=np.uint8)
        d = g.create_dataset(c.COMPOSITE_LAND_WATER, data=classes, **kw)
        d.attrs["_FillValue"] = np.array([c.LAND_WATER_FILL], dtype=np.uint8)
    return path


def cell_box(row, col_from, col_to):
    """Polygon covering whole cells of one row, columns col_from to col_to inclusive."""
    return box(110.0 + col_from * CELL, -(row + 1) * CELL, 110.0 + (col_to + 1) * CELL, -row * CELL)


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("ntl")
    for month in MONTHS:
        write_month(root, month)
    return root


@pytest.fixture(scope="module")
def unit_maps():
    shapes = [
        (cell_box(0, 0, 2), 52, 5208, 520801),   # A, B, C: a coded sub-district
        (cell_box(1, 0, 0), 52, 5208, 520801),   # E: second part of the same sub-district
        (cell_box(1, 1, 1), 52, 5208, 0),        # F: held by the district
        (cell_box(1, 2, 3), 52, 5271, 527101),   # G, H: another sub-district
    ]
    return st.unit_maps_from_shapes(shapes, GRID)


@pytest.fixture(scope="module")
def built(data_root, unit_maps):
    return st.build_stack(data_root, TILE, unit_maps, min_good_months=3)


def test_month_range():
    assert st.month_range(dt.date(2018, 11, 1), dt.date(2019, 2, 1)) == (
        dt.date(2018, 11, 1), dt.date(2018, 12, 1), dt.date(2019, 1, 1), dt.date(2019, 2, 1))
    with pytest.raises(ValueError):
        st.month_range(dt.date(2018, 11, 5), dt.date(2019, 2, 1))
    with pytest.raises(ValueError):
        st.month_range(dt.date(2019, 2, 1), dt.date(2018, 11, 1))


def test_unit_maps_follow_the_zero_rule(unit_maps):
    assert unit_maps["subdistrict"][:2, :4].tolist() == [[520801, 520801, 520801, 0], [520801, 0, 527101, 527101]]
    assert unit_maps["district"][:2, :4].tolist() == [[5208, 5208, 5208, 0], [5208, 5208, 5271, 5271]]
    assert unit_maps["province"][:2, :4].tolist() == [[52, 52, 52, 0], [52, 52, 52, 52]]


def test_every_level_comes_from_the_same_polygon():
    # Two polygons overlap on cell (0, 0). The later one wins, at every level:
    # the cell must not take its sub-district from one and its district from the other.
    small = Grid(110.0, 0.0, 1.0, (1, 2))
    both_cells = box(110.0, -1.0, 112.0, 0.0)
    west_cell = box(110.0, -1.0, 111.0, 0.0)
    maps = st.unit_maps_from_shapes([(both_cells, 52, 5208, 520801), (west_cell, 53, 5301, 0)], small)
    assert maps["province"].tolist() == [[53, 52]]
    assert maps["district"].tolist() == [[5301, 5208]]
    assert maps["subdistrict"].tolist() == [[0, 520801]]
    # A polygon with no code at all still takes its cells, which then have no unit.
    maps = st.unit_maps_from_shapes([(both_cells, 52, 5208, 520801), (west_cell, 0, 0, 0)], small)
    assert maps["province"].tolist() == [[0, 52]]
    assert st.unit_maps_from_shapes([], small)["province"].tolist() == [[0, 0]]


def test_float_codes_are_refused_not_truncated():
    small = Grid(110.0, 0.0, 1.0, (1, 1))
    with pytest.raises(TypeError, match="integers"):
        st.unit_maps_from_shapes([(box(110.0, -1.0, 111.0, 0.0), 52.0, 5208.0, 520801.0)], small)


def test_monthly_files_keep_the_latest_production(data_root, tmp_path):
    files = st.monthly_files(data_root, TILE)
    assert list(files) == MONTHS
    newer = write_month(data_root, MONTHS[0], production="2026001000000")
    try:
        assert st.monthly_files(data_root, TILE)[MONTHS[0]] == newer
    finally:
        newer.unlink()
    with pytest.raises(FileNotFoundError):
        st.monthly_files(tmp_path, TILE)
    with pytest.raises(ValueError):
        st.monthly_files(data_root, "h99v09")


def test_domain_is_lit_land_in_a_unit(built):
    # A, F and G only: B is dim, C sea, D in no unit, E has 2 good months, H coastal.
    assert built.value.shape == (6, 3)  # January to June, April included as an empty row
    assert built.subdistrict.tolist() == [520801, 0, 527101]
    assert built.district.tolist() == [5208, 5208, 5271]
    assert built.units("district") is built.district
    with pytest.raises(ValueError, match="unknown level"):
        built.units("regency")
    assert built.province.tolist() == [52, 52, 52]
    # Cell centres, half a cell in from the corner.
    assert built.lon[0] == pytest.approx(110.0 + CELL / 2) and built.lat[0] == pytest.approx(-CELL / 2)
    assert built.lat[1] == pytest.approx(-1.5 * CELL) and built.lon[2] == pytest.approx(110.0 + 2.5 * CELL)


def test_usual_is_the_mean_of_good_months(built):
    # A: 5.0 x (1.0 + 1.1 + 1.2 + 1.3 + 1.4) / 5 = 6.0.  F: 4.0 x 1.2 = 4.8.
    # G is gap filled in March (factor 1.2), so its mean is 6.0 x (1.0 + 1.1 + 1.3 + 1.4) / 4 = 7.2.
    np.testing.assert_allclose(built.usual, [6.0, 4.8, 7.2], rtol=1e-6)


def test_missing_month_is_a_row_of_no_value(built):
    april = built.months.index(dt.date(2018, 4, 1))
    assert np.isnan(built.value[april]).all()
    assert (built.nights[april] == 0).all() and (built.quality[april] == c.CQ_FILL).all()
    assert built.calendar_month.tolist() == [1, 2, 3, 4, 5, 6]
    assert built.year.tolist() == [2018] * 6 and built.year.dtype == np.int64


def test_gap_filled_month_has_a_number_but_is_not_usable(built):
    march = built.months.index(dt.date(2018, 3, 1))
    g = 2
    assert built.value[march, g] == pytest.approx(6.0 * 1.2)   # the file holds a number
    assert built.quality[march, g] == c.CQ_GAP_FILLED and built.nights[march, g] == 0
    assert not built.observed()[march, g]
    assert np.isnan(built.usable()[march, g])
    assert built.usable()[march, 0] == pytest.approx(5.0 * 1.2)
    # More nights demanded than the files hold: nothing is usable.
    assert np.isnan(built.usable(min_nights=11)).all()


def test_seasonal_pools_observed_months_only(built):
    pooled = built.seasonal()
    feb = built.months.index(dt.date(2018, 2, 1))
    # Cell G, window January to March: March is gap filled, so (6.0 + 6.6) / 2 on 20 nights.
    assert pooled.value[feb, 2] == pytest.approx(6.3)
    assert pooled.nights[feb, 2] == 20 and pooled.centre_share[feb, 2] == pytest.approx(0.5)
    assert np.isnan(pooled.value[0]).all()  # first window is incomplete


def test_until_fixes_the_domain_from_the_past(data_root, unit_maps):
    early = st.build_stack(data_root, TILE, unit_maps, min_good_months=2, until=dt.date(2018, 3, 1))
    # January and February only: E is still good in both, so it joins A, F and G.
    assert early.subdistrict.tolist() == [520801, 520801, 0, 527101]
    assert early.until == dt.date(2018, 3, 1) and early.min_good_months == 2
    # Usual from those two months: A = 5.0 x (1.0 + 1.1) / 2.
    assert early.usual[0] == pytest.approx(5.25)
    assert early.value.shape[0] == 6  # every month is still collected
    with pytest.raises(ValueError, match="no month before"):
        st.build_stack(data_root, TILE, unit_maps, until=dt.date(2017, 1, 1))


def test_bad_requests_are_refused(data_root, unit_maps):
    with pytest.raises(ValueError, match="unknown view"):
        st.build_stack(data_root, TILE, unit_maps, view="Nadir")
    small = {level: np.zeros((4, 4), dtype=np.int64) for level in c.ADMIN_LEVELS}
    with pytest.raises(ValueError, match="map has shape"):
        st.build_stack(data_root, TILE, small)
    floats = {level: array.astype(np.float64) for level, array in unit_maps.items()}
    with pytest.raises(TypeError, match="integers"):
        st.build_stack(data_root, TILE, floats)


def test_a_failed_save_keeps_the_old_cache_and_leaves_no_stray_file(built, tmp_path, monkeypatch):
    target = st.save(built, tmp_path / "stack")
    before = target.read_bytes()
    real = np.savez_compressed

    def half_written(file, **arrays):
        real(file, **arrays)               # the temporary file exists...
        raise OSError("disk full")         # ...and then the write fails

    monkeypatch.setattr(np, "savez_compressed", half_written)
    with pytest.raises(OSError, match="disk full"):
        st.save(dataclasses.replace(built, tile="h30v09"), target)
    # Written straight to the target, the old cache would now be the new tile.
    assert [p.name for p in tmp_path.iterdir()] == ["stack.npz"]
    assert target.read_bytes() == before


def test_a_damaged_cache_says_rebuild(built, tmp_path):
    whole = st.save(built, tmp_path / "whole").read_bytes()
    cut = tmp_path / "cut.npz"
    cut.write_bytes(whole[: len(whole) // 2])          # a half-synced copy
    text = tmp_path / "text.npz"
    text.write_bytes(b"this is not an archive")
    single = tmp_path / "single.npz"
    with open(single, "wb") as handle:
        np.save(handle, np.arange(3))                  # one array, not an archive
    for path in (cut, text, single):
        with pytest.raises(ValueError, match="rebuild it"):
            st.load(path)


def test_a_boundary_file_without_a_code_field_is_named(tmp_path):
    gpd = pytest.importorskip("geopandas")
    path = tmp_path / "units.geojson"
    frame = gpd.GeoDataFrame({"a1siak": [52], "a3siak": [520801]}, geometry=[box(116.0, -8.5, 116.1, -8.4)], crs="EPSG:4326")
    frame.to_file(path, driver="GeoJSON")
    with pytest.raises(ValueError, match="no field a2siak"):
        st.unit_maps_from_file(path, GRID)


def test_save_and_load(built, tmp_path):
    # The suffix is added when missing, and no partial file is left behind.
    written = st.save(built, tmp_path / "stack")
    assert written == tmp_path / "stack.npz" and [p.name for p in tmp_path.iterdir()] == ["stack.npz"]
    again = st.load(tmp_path / "stack")
    assert again.tile == built.tile and again.months == built.months and again.view == built.view
    assert (again.until, again.lit_min, again.min_good_months) == (None, c.LIT_MIN_RADIANCE, 3)
    for name in ARRAYS:
        np.testing.assert_array_equal(getattr(again, name), getattr(built, name))
    dated = dataclasses.replace(built, until=dt.date(2018, 3, 1))
    assert st.load(st.save(dated, tmp_path / "dated.npz")).until == dt.date(2018, 3, 1)


def test_concat_joins_cells_and_refuses_mismatches(built):
    # A neighbour: the same cells moved ten degrees east, in another district.
    east = dataclasses.replace(built, tile="h30v09", lon=built.lon + 10.0, district=built.district + 100)
    both = st.concat([built, east])
    assert both.value.shape == (6, 6) and both.tile == f"{TILE}+h30v09"
    assert both.district.tolist() == [5208, 5208, 5271, 5308, 5308, 5371]
    with pytest.raises(ValueError, match="no stack"):
        st.concat([])
    with pytest.raises(ValueError, match="same cell"):
        st.concat([built, built])
    with pytest.raises(ValueError, match="differ in months"):
        st.concat([built, dataclasses.replace(east, months=built.months[:-1])])
    with pytest.raises(ValueError, match="domain rules"):
        st.concat([built, dataclasses.replace(east, until=dt.date(2018, 3, 1))])


def test_old_cache_is_read_with_its_levels_renamed(built, tmp_path):
    # Version 1 caches named adm2 "regency" and adm3 "district" and carried no version.
    path = tmp_path / "old.npz"
    np.savez_compressed(
        path, tile=built.tile, view=built.view, months=np.array([m.isoformat() for m in built.months]),
        lon=built.lon, lat=built.lat, province=built.province, regency=built.district, district=built.subdistrict,
        usual=built.usual, value=built.value, nights=built.nights, quality=built.quality)
    old = st.load(path)
    assert old.district.tolist() == [5208, 5208, 5271]
    assert old.subdistrict.tolist() == [520801, 0, 527101]
    assert old.until is None


def test_a_file_that_is_not_a_stack_cache_is_refused(tmp_path):
    np.savez_compressed(tmp_path / "other.npz", version=c.STACK_CACHE_VERSION, tile="h29v09")
    with pytest.raises(ValueError, match="rebuild"):
        st.load(tmp_path / "other.npz")
    np.savez_compressed(tmp_path / "future.npz", version=c.STACK_CACHE_VERSION + 1)
    with pytest.raises(ValueError, match="version"):
        st.load(tmp_path / "future.npz")
    with pytest.raises(FileNotFoundError):
        st.load(tmp_path / "absent.npz")


# ---- the command line ----------------------------------------------------------


def test_command_line_builds_skips_and_reports_failures(data_root, tmp_path, caplog):
    gpd = pytest.importorskip("geopandas")
    shapes = [(cell_box(0, 0, 2), 52, 5208, 520801), (cell_box(1, 1, 1), 52, 5208, 0), (cell_box(1, 2, 3), 52, 5271, 527101)]
    frame = gpd.GeoDataFrame(
        dict(a1siak=[s[1] for s in shapes], a2siak=[s[2] for s in shapes], a3siak=[s[3] for s in shapes]),
        geometry=[s[0] for s in shapes], crs="EPSG:4326")
    boundaries = tmp_path / "units.geojson"
    frame.to_file(boundaries, driver="GeoJSON")
    cache = tmp_path / "cache"
    common = ["--root", str(data_root), "--boundaries", str(boundaries), "--out", str(cache)]
    assert st.main([*common, "--tiles", TILE, "--until", "2018-06-01"]) == 0
    written = st.load(st.cache_path(cache, TILE))
    assert written.until == dt.date(2018, 6, 1) and len(written.months) == 6
    # Five months cannot give the default twelve good months: the tile has no cell, and says so.
    assert written.value.shape[1] == 0
    with pytest.raises(ValueError, match="no stack"):
        st.load_folder(cache)
    # A second call leaves the cache alone unless forced.
    before = st.cache_path(cache, TILE).stat().st_mtime_ns
    with caplog.at_level("INFO", logger="ntl.stack"):
        assert st.main([*common, "--tiles", TILE]) == 0
    assert "skipped" in caplog.text and st.cache_path(cache, TILE).stat().st_mtime_ns == before
    # A tile with no file fails without stopping the others; a bad tile id is a usage error.
    assert st.main([*common, "--tiles", "h30v09", TILE]) == 1
    with pytest.raises(SystemExit) as stop:
        st.main([*common, "--tiles", "nowhere"])
    assert stop.value.code == 2
    with pytest.raises(FileNotFoundError, match="no stack cache"):
        st.load_folder(tmp_path / "empty")
