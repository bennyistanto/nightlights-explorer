"""The yearly DMSP record: sums per unit, recall of dim cells, two satellites into one year, the band and the flags."""

import json

import numpy as np
import pytest

from ntl import longrecord as lr


def _reading(light, recall=None, seen=30.0, lit=None, outside=None, observations=None, saturated=None):
    """A Reading from a few numbers; what is not given follows from ``light``."""
    light = np.asarray(light, dtype=float)
    n = light.size
    return lr.Reading(light=light, lit=light.copy() if lit is None else np.asarray(lit, dtype=float), bright=light / 2,
                      outside=light.copy() if outside is None else np.asarray(outside, dtype=float),
                      saturated=np.zeros(n) if saturated is None else np.asarray(saturated, dtype=float),
                      observations=np.full(n, seen) if observations is None else np.asarray(observations, dtype=float),
                      recall=np.full(n, np.nan) if recall is None else np.asarray(recall, dtype=float), seen=seen)


def test_a_satellite_year_is_summed_per_unit_with_saturation_read_from_the_archived_file():
    units = np.array([[1, 1, 2], [1, 2, 0]])
    corrected = np.array([[10.0, 0.0, 9.0], [50.0, 3.0, 99.0]])
    uncorrected = np.array([[12, 0, 8], [63, 2, 63]], dtype=np.uint8)
    seen = np.array([[20, 30, 40], [10, 50, 0]], dtype=np.uint8)
    reading = lr.unit_reading(corrected, uncorrected, seen, units, np.array([1, 2]))
    assert reading.light.tolist() == [60.0, 12.0]            # the cell outside every unit is not counted
    assert reading.lit.tolist() == [2.0, 2.0]                # no floor: the cell at 3 counts
    assert reading.bright.tolist() == [2.0, 1.0]             # above 8 only
    np.testing.assert_allclose(reading.saturated, [50 / 60, 0.0])
    assert reading.observations.tolist() == [20.0, 45.0]     # per unit: median of 20, 30, 10 and of 40, 50
    assert reading.seen == 30.0                              # over the five cells inside a unit
    assert reading.outside.tolist() == reading.light.tolist() and np.isnan(reading.recall).all()   # no outlines, no steady cells
    flares = np.array([[False, False, True], [True, False, True]])
    assert lr.unit_reading(corrected, uncorrected, seen, units, np.array([1, 2]), flares).outside.tolist() == [10.0, 3.0]
    with pytest.raises(ValueError, match="flare cells"):
        lr.unit_reading(corrected, uncorrected, seen, units, np.array([1, 2]), flares[:1])
    with pytest.raises(ValueError, match="shapes differ"):
        lr.unit_reading(corrected, uncorrected[:1], seen, units, np.array([1, 2]))
    with pytest.raises(ValueError, match="strictly ascending"):
        lr.unit_reading(corrected, uncorrected, seen, units, np.array([2, 1]))
    broken = corrected.copy()
    broken[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        lr.unit_reading(broken, uncorrected, seen, units, np.array([1, 2]))


def test_the_edges_of_bright_and_saturated_and_a_unit_with_no_cell():
    units = np.array([1, 1, 1, 1])
    corrected = np.array([8.0, 8.5, 20.0, 30.0])
    uncorrected = np.array([8, 9, 59, 60], dtype=np.uint8)
    reading = lr.unit_reading(corrected, uncorrected, np.ones(4, dtype=np.uint8), units, np.array([1, 7]))
    assert reading.bright.tolist() == [3.0, 0.0]             # 8 itself is not bright; above 8 is
    np.testing.assert_allclose(reading.saturated[0], 30.0 / 66.5)   # 60 counts as saturated, 59 does not
    assert reading.light[1] == 0.0 and np.isnan(reading.saturated[1]) and np.isnan(reading.observations[1])   # code 7 has no cell


def test_recall_is_the_share_of_steady_dim_cells_a_satellite_year_sees(monkeypatch):
    monkeypatch.setattr(lr, "RECALL_MIN_CELLS", 2)
    # five cells: 0 dim and steady, 1 dim and steady, 2 bright and steady, 3 lit in too few of the others, 4 never lit
    usual = np.array([5.0, 6.0, 40.0, 0.0, 0.0])
    corrected = {("F14", 2000 + i): usual.copy() for i in range(4)}
    corrected[("F14", 2001)] = np.array([5.0, 6.0, 40.0, 4.0, 0.0])      # cell 3 lit in one of the others only
    corrected[("F15", 2002)] = np.array([5.0, 0.0, 40.0, 0.0, 0.0])      # this satellite-year misses cell 1
    steady = lr.steady_dim_cells(corrected)
    assert steady[("F15", 2002)].tolist() == [True, True, False, False, False]
    units = np.ones(5, dtype=int)
    zeros = np.zeros(5, dtype=np.uint8)
    reading = lr.unit_reading(corrected[("F15", 2002)], zeros, zeros, units, np.array([1]), steady=steady[("F15", 2002)])
    assert reading.recall.tolist() == [0.5]
    # a satellite-year is never its own reference: with F15 2002 as one of five others, cell 1 is still steady for F14 2000
    assert steady[("F14", 2000)].tolist() == [True, True, False, False, False]
    assert not lr.steady_dim_cells({("F14", 2000): usual, ("F14", 2001): usual})[("F14", 2000)].any()   # one other is not enough


def test_the_spread_is_a_root_mean_square_and_counts_a_one_sided_year():
    ones = np.ones(1)
    # half log differences 0, 0, 0, 0.4: the root mean square is 0.2, where a mean would give 0.1 and a median 0
    pairs = [(ones, ones)] * 3 + [(ones, ones * np.exp(0.8))]
    spread, own = lr.pair_spread(pairs, 1)
    np.testing.assert_allclose(spread, [0.2])
    assert own.tolist() == [True]
    # one satellite sees nothing in one of four years: that year counts as ONE_SIDED_HALF, it is not left out
    spread, own = lr.pair_spread([(ones, ones)] * 3 + [(ones, np.zeros(1))], 1)
    np.testing.assert_allclose(spread, [lr.ONE_SIDED_HALF / 2.0])
    # a year where both see nothing says nothing: three years are left, one short of a spread of its own
    both = [(np.array([1.0, 0.0]), np.array([np.exp(0.2), 0.0]))] + [(np.array([1.0, 3.0]), np.array([np.exp(0.2), 3.0]))] * 3
    spread, own = lr.pair_spread(both, 2)
    assert own.tolist() == [True, False]
    np.testing.assert_allclose(spread, [0.1, 0.1])            # the second unit borrows the median of the others
    assert np.isnan(lr.pair_spread([], 2)[0]).all()


def test_the_band_is_wider_for_one_satellite_and_absent_for_a_zero():
    value = np.array([[100.0, 0.0], [100.0, 50.0]])
    used = np.array([[2, 2], [1, 1]])
    low, high = lr.band(value, np.array([0.1, 0.1]), used, year_spread=0.05)
    np.testing.assert_allclose(high[0, 0], 100 * np.exp(np.hypot(0.1, 0.05)))
    np.testing.assert_allclose(high[1, 0], 100 * np.exp(np.hypot(lr.BAND_FACTOR * 0.1, 0.05)))
    np.testing.assert_allclose(low[1, 0] * high[1, 0], 100.0**2)                # symmetric in log
    assert np.isnan(low[0, 1]) and np.isnan(high[0, 1])                         # not detected is not zero for certain


def test_a_satellite_that_misses_dim_light_is_set_aside_only_when_the_other_is_clearly_better():
    first = np.array([0.50, 0.50, 0.90, 0.72, np.nan, 0.60])
    second = np.array([0.90, 0.60, 0.50, 0.90, 0.90, 0.75])
    #                 other  gap    first  first  cannot  gap of exactly
    #                 better small  better fine   judge   0.15: set aside
    assert lr.choose(first, second).tolist() == [1, -1, 0, -1, -1, 1]


def test_a_drop_in_lit_area_that_comes_back_is_flagged_and_a_lasting_fall_or_a_rise_is_not():
    years = np.arange(2000, 2012)
    back = np.full(12, 100.0)
    back[[6, 7]] = 50.0                                       # two low years, then as before
    lasting = np.where(years >= 2006, 50.0, 100.0)            # falls and stays down
    rise = np.where(years >= 2006, 200.0, 100.0)
    small = np.full(12, 10.0)
    small[6] = 2.0                                            # too few cells to judge
    edge = np.full(12, 100.0)
    edge[[1, 10]] = 10.0                                      # only one year before 2001, only one after 2010
    drops = lr.lit_drops(np.column_stack([back, lasting, rise, small, edge]), years)
    assert years[drops[:, 0]].tolist() == [2006, 2007]
    assert not drops[:, 1:].any()
    exactly = np.full(12, 100.0)
    exactly[6] = 75.0                                         # at the ratio itself: not below it
    assert not lr.lit_drops(exactly[:, None], years).any()


def test_two_satellites_become_one_year_and_the_better_one_stands_alone_where_the_other_misses():
    readings = {}
    for i in range(4):
        readings[("F14", 2000 + i)] = _reading([100.0, 40.0], recall=[0.9, 0.9])
        readings[("F15", 2000 + i)] = _reading([100.0 * np.exp(0.2), 40.0], recall=[0.9, 0.9])
    readings[("F15", 2003)] = _reading([60.0, 40.0], recall=[0.5, 0.9])          # F15 misses unit 0's dim light in 2003
    readings[("F16", 2004)] = _reading([200.0, 0.0], recall=[0.9, 0.9])
    record = lr.assemble(readings)
    light = record.series["light"]
    assert record.years.tolist() == [2000, 2001, 2002, 2003, 2004]
    assert record.sources[0] == ["F14", "F15"] and record.sources[4] == ["F16"]
    np.testing.assert_allclose(light.value[0], [(100 + 100 * np.exp(0.2)) / 2, 40.0])
    np.testing.assert_allclose(light.pair_low[0], [100.0, 40.0])                 # the two readings are kept beside the band
    assert record.used[3].tolist() == [1, 2] and record.chosen[3].tolist() == [0, -1]
    assert light.value[3, 0] == 100.0 and record.recall[3, 0] == 0.9             # F14 alone, with its own recall
    np.testing.assert_allclose(light.pair_low[3, 0], 60.0)                       # the reading set aside is still there to see
    assert record.used[4].tolist() == [1, 1] and np.isnan(light.pair_low[4]).all()
    assert record.undetected[4].tolist() == [False, True] and np.isnan(light.low[4, 1])
    assert light.low[4, 0] < 200.0 < light.high[4, 0]
    assert record.segment.tolist() == [0, 0, 0, 0, 0]
    with pytest.raises(ValueError, match="no readings"):
        lr.assemble({})
    with pytest.raises(ValueError, match="different numbers of units"):
        lr.assemble({("F14", 2000): _reading([1.0]), ("F15", 2000): _reading([1.0, 2.0])})
    with pytest.raises(ValueError, match="more than two"):
        lr.assemble({(s, 2000): _reading([1.0]) for s in ("F12", "F14", "F15")})


def test_a_thin_satellite_year_is_left_out_where_another_covers_the_year_and_kept_where_alone():
    readings = {("F10", 1992): _reading([5.0], seen=11.0, observations=[11.0]), ("F10", 1994): _reading([10.0]),
                ("F12", 1994): _reading([30.0], seen=10.0), ("F18", 2010): _reading([12.0], recall=[0.5], saturated=[0.6])}
    record = lr.assemble(readings)
    assert record.dropped == ["F121994"] and record.years.tolist() == [1992, 1994, 2010]
    assert record.series["light"].value[:, 0].tolist() == [5.0, 10.0, 12.0]
    assert record.thin[:, 0].tolist() == [True, False, False]                   # 1992 kept, being alone, and flagged
    assert record.low_recall[:, 0].tolist() == [False, False, True]
    assert record.segment.tolist() == [0, 0, 1]                                 # F18 is its own segment
    assert record.saturated[2, 0] == 0.6 and record.seen["F121994"] == 10.0
    assert record.satellites["F121994"] == {"light": 30.0, "lit": 30.0}                 # a satellite-year left out is still listed
    assert np.isnan(record.series["light"].low).all()                           # no year with two satellites: no band can be given


def test_light_outside_the_flare_outlines_is_usable_only_where_the_outlines_hold_little():
    readings = {("F14", 2000): _reading([100.0, 100.0, 0.0], outside=[95.0, 60.0, 0.0]),
                ("F14", 2001): _reading([100.0, 100.0, 0.0], outside=[91.0, 99.0, 0.0])}
    record = lr.assemble(readings)
    np.testing.assert_allclose(record.flare_share[0, :2], [0.05, 0.40])
    assert record.outside_usable.tolist() == [True, False, True]                # 9% at most; 40% in one year; no light at all


def test_the_record_survives_a_round_trip_and_its_meta_is_plain_json(tmp_path):
    readings = {("F14", 2000 + i): _reading([100.0, 40.0], recall=[0.9, np.nan]) for i in range(4)}
    readings |= {("F15", 2000 + i): _reading([110.0, 40.0], recall=[0.9, np.nan]) for i in range(4)}
    readings[("F18", 2010)] = _reading([0.0, 5.0], seen=float("nan"))
    record = lr.assemble(readings)
    written = lr.save(record, np.array([11, 12]), tmp_path / "out" / "dmsp_province.npz", {"eog": "somewhere"})
    assert [p.name for p in written.parent.iterdir()] == ["dmsp_province.npz"]  # no part file left behind
    codes, back, meta = lr.load(written)
    assert codes.tolist() == [11, 12] and back.sources == record.sources and back.dropped == record.dropped and back.satellites == record.satellites
    for quantity in lr.QUANTITIES:
        for field in lr.Series._fields:
            np.testing.assert_array_equal(getattr(back.series[quantity], field), getattr(record.series[quantity], field))
    np.testing.assert_array_equal(back.undetected, record.undetected)
    assert np.isnan(back.seen["F182010"])
    with np.load(written) as z:
        text = str(z["meta"])
    assert "NaN" not in text and json.loads(text)["thresholds"]["BAND_FACTOR"] == lr.BAND_FACTOR
    assert meta["sources"] == {"eog": "somewhere"} and "not a confidence interval" in meta["band"]


def test_flare_outlines_take_every_cell_they_touch():
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")
    from shapely.geometry import box

    from ntl.read import Grid

    grid = Grid(west=100.0, north=4.0, cell=1.0, shape=(4, 4))
    # a square from 100.9 to 102.1 E and 1.9 to 3.1 N: it covers one cell whole and only clips the eight around it
    path_shape = box(100.9, 1.9, 102.1, 3.1)
    frame = gpd.GeoDataFrame({"ID": [1]}, geometry=[path_shape], crs=4326)
    cells = lr.flare_cells_from(frame.geometry, grid)
    assert cells.astype(int).tolist() == [[1, 1, 1, 0], [1, 1, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0]]
