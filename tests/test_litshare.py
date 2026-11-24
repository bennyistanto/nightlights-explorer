"""People by the light where they live: every figure worked by hand on a few cells."""

import datetime as dt
import json

import h5py
import numpy as np
import pytest

from ntl import conventions as c
from ntl import litshare
from ntl.litshare import DARK, FAINT, LIT, UNSEEN
from ntl.tiles import Tile

CELL = c.CELL_SIZE_DEG
SIDE = c.CELLS_PER_TILE
TILE = "h29v09"  # 110 E to 120 E, 0 to 10 S


def test_light_state_has_four_states_and_never_calls_unseen_dark():
    yearly = np.array([[np.nan, 0.0, 0.49, 0.5, 1.99, 2.0, 30.0]])
    assert litshare.light_state(yearly, 0.5, 2.0).tolist() == [[UNSEEN, DARK, DARK, FAINT, FAINT, LIT, LIT]]
    with pytest.raises(ValueError):
        litshare.light_state(yearly, 3.0, 2.0)


def test_positions_marks_unlisted_codes_as_zero():
    units = np.array([11, 13, 52])
    assert litshare.positions(np.array([52, 11, 12, 0, 99, 13]), units).tolist() == [3, 1, 0, 0, 0, 2]
    assert litshare.positions(np.array([[5]]), np.array([], dtype=np.int64)).tolist() == [[0]]
    with pytest.raises(ValueError):
        litshare.positions(np.array([1]), np.array([3, 3]))


def test_sum_by_unit_counts_and_weights_and_skips_no_unit():
    position = np.array([1, 1, 2, 0, 2])
    assert litshare.sum_by_unit(position, 3).tolist() == [2.0, 2.0, 0.0]
    assert litshare.sum_by_unit(position, 3, np.array([1.5, 2.5, 4.0, 100.0, 1.0])).tolist() == [4.0, 5.0, 0.0]


def test_subunits_with_counts_each_child_once_and_needs_enough_cells():
    chosen = np.array([True, True, True, False, True, True])
    position = np.array([1, 1, 1, 1, 2, 0])
    child = np.array([101, 101, 102, 103, 0, 201])  # 103 is not chosen; the cell of unit 2 is held by the unit itself
    assert litshare.subunits_with(chosen, position, child, 2).tolist() == [2, 0]
    assert litshare.subunits_with(chosen, position, child, 2, min_cells=2).tolist() == [1, 0]   # only 101 has two cells
    assert litshare.subunits_with(np.zeros(6, dtype=bool), position, child, 2).tolist() == [0, 0]


def test_lattice_index_nests_five_pixels_per_cell_from_an_offset_edge():
    # the first pixel is the fourth fifth of lattice column 66000 (95 E), as in the WorldPop files
    edge = -180.0 + 66000 * CELL + 3 * CELL / 5
    assert litshare.lattice_index(edge, CELL / 5, 8, -180.0).tolist() == [66000, 66000, 66001, 66001, 66001, 66001, 66001, 66002]
    north = 90.0 - 20000 * CELL - 4 * CELL / 5
    assert litshare.lattice_index(north, CELL / 5, 3, 90.0, descending=True).tolist() == [20000, 20001, 20001]


def test_lattice_index_refuses_rasters_that_do_not_nest():
    with pytest.raises(ValueError, match="whole fraction"):
        litshare.lattice_index(95.0, CELL / 4.5, 10, -180.0)
    with pytest.raises(ValueError, match="lattice"):
        litshare.lattice_index(95.0 + 0.3 * CELL / 5, CELL / 5, 10, -180.0)
    with pytest.raises(ValueError, match="whole fraction"):
        litshare.lattice_index(95.0, 1.0, 10, -180.0)          # a pixel of a degree: no cell nests in it
    with pytest.raises(ValueError, match="positive"):
        litshare.lattice_index(95.0, -CELL / 5, 10, -180.0)


def test_block_sum_adds_pixels_into_cells_and_drops_nodata():
    block = np.array([[1.0, 2.0, 4.0], [8.0, -99999.0, 16.0], [np.nan, 32.0, 64.0]])
    sums, rows, cols = litshare.block_sum(block, np.array([7, 7, 8]), np.array([3, 4, 4]), -99999.0)
    assert rows.tolist() == [7, 8] and cols.tolist() == [3, 4]
    assert sums.tolist() == [[9.0, 22.0], [0.0, 96.0]]
    with pytest.raises(ValueError):
        litshare.block_sum(block, np.array([7, 8, 7]), np.array([3, 4, 4]), None)


def test_tile_cells_uses_the_global_lattice():
    tile = Tile(29, 9)
    rows = np.array([9 * SIDE, 9 * SIDE - 1, 10 * SIDE - 1, 9 * SIDE])
    cols = np.array([29 * SIDE, 29 * SIDE, 30 * SIDE - 1, 30 * SIDE])
    assert litshare.tile_cells(tile, rows, cols).tolist() == [True, False, True, False]


def test_level_table_by_hand():
    # two years, five cells: unit 11 holds cells 0 to 2, unit 12 cell 3, cell 4 is in no unit
    state = np.array([[LIT, DARK, UNSEEN, FAINT, LIT], [LIT, LIT, FAINT, UNSEEN, LIT]], dtype=np.uint8)
    people = np.array([10.0, 20.0, 40.0, 80.0, 1000.0])
    units = np.array([11, 11, 11, 12, 0])
    sub = np.array([1101, 1102, 1102, 1201, 0])
    table = litshare.level_table(state, people, units, sub, min_subunit_cells=1)
    assert table.codes.tolist() == [11, 12] and table.people.tolist() == [[70.0, 80.0], [70.0, 80.0]]
    assert table.cells[LIT].tolist() == [[1, 0], [2, 0]]
    assert table.cells[DARK].tolist() == [[1, 0], [0, 0]]
    assert table.cells[UNSEEN].tolist() == [[1, 0], [0, 1]]
    assert table.people_by_state[LIT].tolist() == [[10.0, 0.0], [30.0, 0.0]]
    assert table.people_by_state[FAINT].tolist() == [[0.0, 80.0], [40.0, 0.0]]
    # every person is in exactly one state in every year
    assert table.people_by_state.sum(axis=0).tolist() == [[70.0, 80.0], [70.0, 80.0]]
    assert table.subunits.tolist() == [2, 1] and table.subunits_lit.tolist() == [[1, 0], [2, 0]]
    assert litshare.level_table(state, people, units, sub, min_subunit_cells=2).subunits_lit.tolist() == [[0, 0], [0, 0]]
    # people that differ by year: each year's states are weighed by that year's people
    yearly = litshare.level_table(state, np.stack([people, 2 * people]), units)
    assert yearly.people.tolist() == [[70.0, 80.0], [140.0, 160.0]] and yearly.people_by_state[LIT].tolist() == [[10.0, 0.0], [60.0, 0.0]]
    with pytest.raises(ValueError):
        litshare.level_table(state, people[:3], units)
    alone = litshare.level_table(state, people, units)
    assert alone.subunits is None and alone.subunits_lit is None


def test_population_year_for_uses_own_year_and_carries_the_first_back():
    assert litshare.population_year_for([2012, 2014, 2015, 2020, 2026], [2015, 2016, 2020, 2026]) == {2012: 2015, 2014: 2015, 2015: 2015, 2020: 2020, 2026: 2026}
    # a gap or a year past the last raster takes the latest earlier one: nothing is extrapolated
    assert litshare.population_year_for([2018, 2030], [2015, 2016, 2020]) == {2018: 2016, 2030: 2020}
    assert litshare.population_year_for([2012, 2026], [2015, 2020], fixed=2020) == {2012: 2020, 2026: 2020}
    with pytest.raises(ValueError, match="2019"):
        litshare.population_year_for([2012], [2015, 2020], fixed=2019)
    with pytest.raises(ValueError):
        litshare.population_year_for([2012], [])


def test_national_shares_are_of_each_years_own_people():
    state = np.array([[LIT, DARK, UNSEEN], [LIT, LIT, FAINT]], dtype=np.uint8)
    people = np.array([[10.0, 30.0, 60.0], [20.0, 20.0, 160.0]])
    assert litshare.national_shares(state, people, [2015, 2016]) == [
        {"year": 2015, "people": 100, "unseen": 60.0, "dark": 30.0, "faint": 0.0, "lit": 10.0},
        {"year": 2016, "people": 200, "unseen": 0.0, "dark": 0.0, "faint": 80.0, "lit": 20.0}]


# ---- the whole path: monthly files, population rasters and unit maps, to the site files
#
# Four populated cells in the north-west corner of the tile, all in province 52:
#   A (0,0) 25 people   5.0 in every month                          -> lit, lit
#   B (0,1) 50 people   2015: 0, 0, 0, 0.8 (median 0)  2016: 1.0    -> dark, faint
#   C (0,2) 100 people  2015: 3.0   2016: gap filled every month    -> lit, unseen
#   D (0,3) no people                                               -> not in the support
#   E (1,0) 200 people  2015: good in 2 months only   2016: 0.4, 0.4, 0.8, 0.8 -> unseen, faint
MONTHS = [dt.date(year, month, 1) for year in (2015, 2016) for month in (5, 6, 7, 8)]


def write_month(root, month):
    i, first = MONTHS.index(month) % 4, month.year == 2015
    value = np.full((SIDE, SIDE), -999.9, dtype=np.float32)
    quality = np.full((SIDE, SIDE), c.CQ_FILL, dtype=np.uint8)
    value[0, :4] = [5.0, ((0.0, 0.0, 0.0, 0.8)[i] if first else 1.0), 3.0, 9.0]
    value[1, 0] = 7.0 if first else (0.4, 0.4, 0.8, 0.8)[i]
    quality[0, :4] = c.CQ_GOOD
    quality[1, 0] = c.CQ_GOOD if (not first or i < 2) else c.CQ_POOR
    if not first:
        quality[0, 2] = c.CQ_GAP_FILLED  # a number, but not an observation
    folder = root / c.BLACK_MARBLE_DIR / c.MONTHLY_PRODUCT / f"{month.year}" / f"{month:%j}"
    folder.mkdir(parents=True, exist_ok=True)
    with h5py.File(folder / f"{c.MONTHLY_PRODUCT}.A{month.year}{month:%j}.{TILE}.002.2025001000000.h5", "w") as f:
        g = f.create_group(c.GRID_GROUP)
        base = c.COMPOSITE_LAYER.format(view="AllAngle", suffix="")
        d = g.create_dataset(base, data=value, compression="gzip", compression_opts=1)
        d.attrs["_FillValue"] = np.array([np.float32(-999.9)])
        d = g.create_dataset(base + c.COMPOSITE_QUALITY, data=quality, compression="gzip", compression_opts=1)
        d.attrs["_FillValue"] = np.array([c.CQ_FILL], dtype=np.uint8)


def write_population(folder, year, factor, extra=0.0):
    """A 2 by 4 cell raster, five pixels a side: cells A, B, C, E hold 25, 50, 100, 200 people times ``factor``.

    ``extra`` people are put in cell D, which is otherwise empty.
    """
    import rasterio
    from rasterio.transform import from_origin

    people = np.zeros((10, 20), dtype=np.float32)
    people[:5, 0:5], people[:5, 5:10], people[:5, 10:15] = 1.0, 2.0, 4.0
    people[5:, 0:5] = 8.0
    people *= factor
    people[1, 16] = extra
    people[0, 19] = -99999.0                         # no data adds nothing
    folder.mkdir(exist_ok=True)
    with rasterio.open(folder / f"x_pop_{year}_y.tif", "w", driver="GTiff", height=10, width=20, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(110.0, 0.0, CELL / 5, CELL / 5), nodata=-99999.0) as dst:
        dst.write(people, 1)


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    pytest.importorskip("rasterio")
    root = tmp_path_factory.mktemp("ntl")
    for month in MONTHS:
        write_month(root, month)
    write_population(root / "pop", 2016, 1.0)
    write_population(root / "pop", 2020, 3.0)
    boundaries = root / "b.shp"
    boundaries.write_bytes(b"x")
    return root, root / "pop", boundaries


def fake_maps(path, grid):
    assert grid.shape == (2, 4) and grid.west == pytest.approx(110.0) and grid.north == pytest.approx(0.0)
    return {"province": np.array([[52, 52, 52, 52], [52, 0, 0, 0]]),
            "district": np.array([[5208, 5208, 5208, 5208], [5271, 0, 0, 0]]),
            "subdistrict": np.array([[520801, 520801, 520802, 520802], [527101, 0, 0, 0]])}


def test_build_end_to_end(inputs, tmp_path, monkeypatch):
    root, population, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    meta = litshare.build(root, population, boundaries, tmp_path / "out", work=tmp_path / "work", min_subunit_cells=1)
    assert meta["years"] == [2015, 2016] and meta["cells"] == 4 and meta["tiles"] == [TILE]
    # 2015 has no raster of its own: the first one, 2016, is carried back and said so
    assert meta["population"]["used"] == {"2015": 2016, "2016": 2016} and meta["population"]["carried_back"] == [2015]
    assert meta["population"]["years"] == [2016, 2020] and meta["population"]["fixed_year"] is None
    assert meta["national"] == [{"year": 2015, "people": 375, "unseen": 53.33, "dark": 13.33, "faint": 0.0, "lit": 33.33},
                                {"year": 2016, "people": 375, "unseen": 26.67, "dark": 0.0, "faint": 66.67, "lit": 6.67}]
    assert json.loads((tmp_path / "out" / "meta.json").read_bytes()) == meta and b"\r" not in (tmp_path / "out" / "meta.json").read_bytes()
    province = json.loads((tmp_path / "out" / "province.json").read_text())
    assert province["codes"] == [52] and province["people"] == [[375], [375]]
    assert province["people_unseen"] == [[200], [100]] and province["people_dark"] == [[50], [0]]
    assert province["people_faint"] == [[0], [250]] and province["people_lit"] == [[125], [25]]
    assert province["cells_lit"] == [[2], [1]] and province["cells_unseen"] == [[1], [1]]
    assert province["subunits"] == [3] and province["subunits_lit"] == [[2], [1]]
    district = json.loads((tmp_path / "out" / "district.json").read_text())
    assert district["codes"] == [5208, 5271] and district["people"] == [[175, 200], [175, 200]]
    assert district["people_lit"] == [[125, 0], [25, 0]] and district["people_faint"] == [[0, 0], [50, 200]]
    sub = json.loads((tmp_path / "out" / "subdistrict.json").read_text())
    assert sub["codes"] == [520801, 520802, 527101] and sub["cells_lit"] == [[1, 1, 0], [1, 0, 0]]
    assert sub["people"] == [[75, 100, 200], [75, 100, 200]]
    assert "people_lit" not in sub and "subunits_lit" not in sub   # no people share where both sides are modelled

    # a second run reads the three caches and writes the same bytes
    before = {name: (tmp_path / "out" / name).read_bytes() for name in ("province.json", "district.json", "subdistrict.json", "meta.json")}
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", lambda path, grid: pytest.fail("the unit map cache was not used"))
    monkeypatch.setattr(litshare, "tile_states", lambda *a, **k: pytest.fail("the state cache was not used"))
    monkeypatch.setattr(litshare, "read_population", lambda *a, **k: pytest.fail("the population cache was not used"))
    litshare.build(root, population, boundaries, tmp_path / "out", work=tmp_path / "work", min_subunit_cells=1)
    assert {name: (tmp_path / "out" / name).read_bytes() for name in before} == before


def test_each_year_uses_its_own_population(inputs, tmp_path, monkeypatch):
    root, _, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    write_population(tmp_path / "pop", 2015, 2.0)
    write_population(tmp_path / "pop", 2016, 1.0, extra=40.0)   # cell D gains people in 2016: it joins the support for both years
    meta = litshare.build(root, tmp_path / "pop", boundaries, tmp_path / "out")
    assert meta["population"]["used"] == {"2015": 2015, "2016": 2016} and meta["population"]["carried_back"] == [] and meta["cells"] == 5
    province = json.loads((tmp_path / "out" / "province.json").read_text())
    assert province["people"] == [[750], [415]]
    assert province["people_lit"] == [[250], [65]]              # 2015: A and C, doubled; 2016: A, and D at 9.0
    assert province["people_dark"] == [[100], [0]] and province["people_unseen"] == [[400], [100]]
    assert province["cells_lit"] == [[3], [2]]                  # D is lit in 2015 too, with nobody in it that year
    assert province["subunits_lit"] == [[0], [0]]               # the default asks for five lit cells


def test_one_population_year_for_every_year(inputs, tmp_path, monkeypatch):
    root, population, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    meta = litshare.build(root, population, boundaries, tmp_path, population_year=2020)
    assert meta["population"]["used"] == {"2015": 2020, "2016": 2020} and meta["population"]["fixed_year"] == 2020
    province = json.loads((tmp_path / "province.json").read_text())
    assert province["people"] == [[1125], [1125]] and province["people_lit"] == [[375], [75]]


def test_problems_with_the_inputs_are_named(inputs, tmp_path, monkeypatch):
    root, population, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    with pytest.raises(ValueError, match="no monthly file"):
        litshare.build(tmp_path, population, boundaries, tmp_path / "out")
    with pytest.raises(ValueError, match="2031"):
        litshare.build(root, population, boundaries, tmp_path / "out", population_year=2031)
    assert not (tmp_path / "out").exists()                      # nothing is created before the inputs are read
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", lambda path, grid: {level: np.zeros(grid.shape, dtype=np.int64) for level in c.ADMIN_LEVELS})
    with pytest.raises(ValueError, match="no populated cell lies in a province"):
        litshare.build(root, population, boundaries, tmp_path / "out")
    with pytest.raises(FileNotFoundError):
        litshare.build(root, tmp_path, boundaries, tmp_path / "out")


def test_a_damaged_or_outdated_cache_is_rebuilt(inputs, tmp_path, monkeypatch, caplog):
    root, population, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    work = tmp_path / "work"
    litshare.build(root, population, boundaries, tmp_path / "out", work=work)
    good = (tmp_path / "out" / "province.json").read_bytes()
    (work / f"states_{TILE}_AllAngle.npz").write_bytes(b"not a zip file")
    (work / "population_cells.npz").write_bytes(b"")
    boundaries.with_suffix(".dbf").write_bytes(b"codes corrected")   # the codes live beside the .shp: the unit maps must be burned again
    burned = []
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", lambda path, grid: burned.append(1) or fake_maps(path, grid))
    with caplog.at_level("WARNING", logger="ntl.litshare"):
        litshare.build(root, population, boundaries, tmp_path / "out", work=work)
    assert (tmp_path / "out" / "province.json").read_bytes() == good and burned == [1]
    assert caplog.text.count("unreadable cache ignored") == 2
    boundaries.with_suffix(".dbf").unlink()


def test_main_reports_a_problem_without_a_traceback(inputs, tmp_path, monkeypatch, caplog):
    root, population, boundaries = inputs
    monkeypatch.setattr(litshare.stack, "unit_maps_from_file", fake_maps)
    arguments = ["--root", str(root), "--population", str(population), "--boundaries", str(boundaries), "--out", str(tmp_path / "out")]
    assert litshare.main(arguments + ["--min-subunit-cells", "1"]) == 0
    assert json.loads((tmp_path / "out" / "province.json").read_text())["subunits_lit"] == [[2], [1]]
    assert litshare.main(arguments + ["--population-year", "2031"]) == 1 and "2031" in caplog.text
    with pytest.raises(SystemExit) as usage:
        litshare.main(["--root", str(root)])
    assert usage.value.code == 2
