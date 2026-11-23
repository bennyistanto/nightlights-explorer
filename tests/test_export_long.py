"""Export on a ten-year record: the figures that a short fixture cannot pin down.

A growing unit, a steady one, uneven observation counts, and a final month in
which nothing was seen. Each assert here was chosen because the code change it
guards against (a dropped factor, the wrong slice, an unsorted array, a write
in place) left every other test passing.
"""

import datetime as dt
import gzip
import json
import logging
import os

import numpy as np
import pytest

from ntl import cellmaps, export, monitor, persistence, trend
from ntl import conventions as c
from ntl.stack import TileStack

YEARS = 10
T = YEARS * 12
CELL = c.CELL_SIZE_DEG
GROWTH = 0.05   # a year, unit 520801


def long_stack():
    """Eight cells in two sub-districts of one district, 2014-01 to 2023-12.

    Sub-district 520801 (cells 0 to 3) grows 5% a year from about 10; 520802
    (cells 4 to 7) is steady at about 8. Observation counts differ by cell.
    The last month has no usable value anywhere.
    """
    months = tuple(dt.date(2014 + i // 12, i % 12 + 1, 1) for i in range(T))
    rng = np.random.default_rng(21)
    t = np.arange(T) / 12.0
    growing = 10.0 * (1 + GROWTH) ** t[:, None] * np.exp(rng.normal(0, 0.02, (T, 4)))
    steady = 8.0 * np.exp(rng.normal(0, 0.02, (T, 4)))
    value = np.concatenate([growing, steady], axis=1).astype(np.float32)
    nights = np.tile(np.array([4, 6, 9, 10, 12, 15, 20, 25], dtype=np.uint16), (T, 1))
    quality = np.zeros((T, 8), dtype=np.uint8)
    value[-1], nights[-1], quality[-1] = np.nan, 0, 255          # the final month: nothing seen
    # cell centres far from the equator in this grid's terms (9.9 S), and deliberately not in grid order
    lon = 116.0 + (np.array([5, 2, 7, 0, 3, 6, 1, 4]) + 0.5) * CELL
    lat = -9.9 - (np.array([0, 1, 0, 1, 0, 1, 0, 1]) + 0.5) * CELL
    subdistrict = np.repeat([520801, 520802], 4)
    return TileStack(
        tile="h29v09", view="AllAngle", months=months, lon=lon, lat=lat,
        province=np.full(8, 52), district=np.full(8, 5208), subdistrict=subdistrict,
        usual=np.nanmean(value, axis=0).astype(np.float64), value=value, nights=nights, quality=quality)


@pytest.fixture(scope="module")
def stack():
    return long_stack()


@pytest.fixture(scope="module")
def run(stack, tmp_path_factory):
    path = monitor.save_levels(monitor.run_levels(stack), stack, tmp_path_factory.mktemp("run") / "run.npz")
    return monitor.load_levels(path)


@pytest.fixture(scope="module")
def site(stack, run, tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    export.export_site(stack, run, out)
    return out


def read(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_the_last_observed_month_is_the_one_before_the_empty_one(site, run):
    assert (run.levels["province"].state[-1] == c.STATUS_NOT_OBSERVED).all()
    meta = read(site, "meta.json")
    assert meta["latest"]["window"] == T - 2 and meta["latest"]["month"] == "2023-11"


def test_trend_is_in_percent_a_year_with_its_bounds_the_right_way_round(site):
    units = read(site, "units_subdistrict.json")
    assert units["trend"][0] == pytest.approx(100 * GROWTH, abs=0.3)          # not 0.05, not log(1.05)
    assert units["trend"][1] == pytest.approx(0.0, abs=0.3)
    for k in range(2):
        assert units["trend_low"][k] < units["trend"][k] < units["trend_high"][k]
    assert units["trend_years"] == [YEARS, YEARS]
    # every cell is lit from the first year, so the like-for-like trend is the same series
    assert units["trend_core"] == units["trend"] and units["core_cells"] == [4, 4]


def test_figures_over_the_record_stop_at_the_latest_observed_month(site, run):
    units = read(site, "units_subdistrict.json")
    state = run.levels["subdistrict"].state
    # With the empty final month included these would be 1, and one judged month fewer would not show.
    assert units["longest_unseen"] == [0, 0]
    assert persistence.unseen_runs(state).max(axis=0).tolist() == [1, 1]
    files = read(site, "meta.json")["variables"]["cell_maps"]["files"]
    assert files["2023"]["months"] == 11 and sum(f["months"] for f in files.values()) == T - 1


def test_judged_months_are_counted_up_to_the_latest_observed_month(stack, run, tmp_path):
    # Two units cannot fill the pooled thresholds, so nothing is judged in this run. Give sub-districts a
    # judged history by hand, including a reading in the final month that the provinces did not see.
    levels = dict(run.levels)
    state = levels["subdistrict"].state.copy()
    state[state == c.STATUS_NO_THRESHOLD] = c.STATUS_NORMAL
    state[-1] = c.STATUS_NORMAL
    levels["subdistrict"] = levels["subdistrict"]._replace(state=state)
    export.export_site(stack, monitor.Run(months=run.months, levels=levels, info=run.info), tmp_path)
    units = read(tmp_path, "units_subdistrict.json")
    upto = (state[:-1] == c.STATUS_NORMAL).sum(axis=0).tolist()
    assert units["judged_windows"] == upto and min(upto) > 50
    assert (state == c.STATUS_NORMAL).sum(axis=0).tolist() == [n + 1 for n in upto]     # the whole record would count one more


def test_cell_maps_are_in_cell_order_with_their_own_observation_counts(site, stack):
    meta = read(site, "meta.json")
    cm = meta["variables"]["cell_maps"]
    assert cm["change"]["lag_months"] == cellmaps.YEAR_LAG == 12
    order = np.argsort(export.cell_index(stack.lon, stack.lat))
    entry = cm["files"]["2020"]
    got = np.frombuffer(gzip.decompress((site / entry["file"]).read_bytes()), dtype=np.uint8).reshape(entry["months"], 8)
    _, _, seen = cellmaps.unpack(got)
    # nights are 4, 6, 9 (class 2) and 10 and more (class 3) by cell: unsorted, this row would read differently
    want = cellmaps.observation_class(stack.nights[entry["first_window"]][order])
    assert seen[0].tolist() == want.tolist() and sorted(set(want.tolist())) == [2, 3]
    assert seen[0].tolist() != cellmaps.observation_class(stack.nights[entry["first_window"]]).tolist()


def test_lit_area_uses_the_latitude(site, stack):
    units = read(site, "units_subdistrict.json")
    side = CELL * export.KM_PER_DEGREE
    want = [float((side * side * np.cos(np.radians(stack.lat[stack.subdistrict == code]))).sum()) for code in (520801, 520802)]
    assert units["lit_km2"] == [pytest.approx(v, abs=0.005) for v in want]
    assert 4 * side * side - want[0] > 0.01                      # without the cosine the figure would be off by more than the tolerance


def test_cells_are_classed_then_and_now(site):
    units = read(site, "units_subdistrict.json")
    # every cell is lit in 2014 to 2016 and in 2021 to 2023
    assert units["then_now"] == [[0, 4, 0, 0, 0, 0], [0, 4, 0, 0, 0, 0]]
    meta = read(site, "meta.json")["variables"]["then_now"]
    assert meta["then"] == [2014, 2016] and meta["now"] == [2021, 2023]


# ---- writing ---------------------------------------------------------------------


def test_a_failed_write_leaves_the_old_file_and_no_temporary_one(tmp_path):
    target = tmp_path / "meta.json"
    target.write_text("old", encoding="utf-8")

    def half(temporary):
        temporary.write_text("new but incom", encoding="utf-8")
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        export._replace_with(target, half)
    assert target.read_text(encoding="utf-8") == "old" and [p.name for p in tmp_path.iterdir()] == ["meta.json"]


def test_a_held_file_is_retried_then_reported(tmp_path, monkeypatch, caplog):
    target = tmp_path / "files.js"
    target.write_text("old", encoding="utf-8")
    real, calls, naps = os.replace, [], []
    monkeypatch.setattr(export.time, "sleep", naps.append)

    def held_twice(source, destination):
        calls.append(1)
        if len(calls) <= 2:
            raise PermissionError("in use")
        real(source, destination)

    monkeypatch.setattr(export.os, "replace", held_twice)
    with caplog.at_level(logging.WARNING, logger="ntl.export"):
        export._replace_with(target, lambda temporary: temporary.write_text("new", encoding="utf-8"))
    assert target.read_text(encoding="utf-8") == "new" and len(calls) == 3 and len(naps) == 2
    assert caplog.text.count("held open") == 1                   # said once, not on every try

    def always(source, destination):
        raise PermissionError("in use")

    monkeypatch.setattr(export.os, "replace", always)
    with pytest.raises(PermissionError, match="still held open"):
        export._replace_with(target, lambda temporary: temporary.write_text("newer", encoding="utf-8"))
    assert target.read_text(encoding="utf-8") == "new" and [p.name for p in tmp_path.iterdir()] == ["files.js"]


def test_over_budget_leaves_no_files_js_not_even_a_stale_one(stack, run, tmp_path):
    (tmp_path / "files.js").write_text("// from an earlier export", encoding="utf-8")
    with pytest.raises(ValueError, match="files.js was not written"):
        export.export_site(stack, run, tmp_path, budget=1000)
    assert not (tmp_path / "files.js").exists() and (tmp_path / "meta.json").exists()


def test_the_outline_step_is_recorded_as_it_ran(stack, run, tmp_path):
    from ntl import stack as st

    cache, outlines = tmp_path / "cache", tmp_path / "outlines"
    cache.mkdir()
    outlines.mkdir()
    st.save(stack, st.cache_path(cache, "h29v09"))
    run_file = monitor.save_levels(run.levels, stack, tmp_path / "run.npz")
    square = {"type": "Polygon", "coordinates": [[[116, -10], [117, -10], [117, -9], [116, -9], [116, -10]]]}
    for level, code in (("province", 52), ("district", 5208), ("subdistrict", 520801)):
        collection = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"code": code, "name": "A"}, "geometry": square}]}
        (outlines / f"{level}.geojson").write_text(json.dumps(collection), encoding="utf-8")
    (outlines / "outlines_report.json").write_text(json.dumps({"tolerance_deg": 0.5, "method": "coverage", "features": 1}), encoding="utf-8")
    assert export.main(["--cache", str(cache), "--run", str(run_file), "--outlines", str(outlines), "--out", str(tmp_path / "site")]) == 0
    meta = read(tmp_path / "site", "meta.json")
    assert meta["source"]["inputs"]["outlines"] == {"tolerance_deg": 0.5, "method": "coverage", "features": 1}
    assert meta["level_detail"]["subdistrict"]["without_outline"] == 1      # 520802 has no outline in this folder
    assert read(tmp_path / "site", "units_subdistrict.json")["name"] == ["A", None]


# ---- trend details a short record cannot show ---------------------------------------


def test_a_yearly_value_is_a_median_not_a_mean():
    years = np.repeat([2020], 12)
    values = np.array([1.0] * 11 + [1000.0])
    assert trend.yearly_medians(values, years)[1][0] == 1.0


def test_eight_years_give_a_trend_and_seven_do_not():
    x = np.arange(8.0)
    assert np.isfinite(trend.theil_sen(x, 0.1 * x).slope) and np.isnan(trend.theil_sen(x[:7], 0.1 * x[:7]).slope)
    assert trend.MIN_YEARS == 8


def test_the_rate_is_the_exact_yearly_growth():
    years = np.repeat(np.arange(2012, 2027), 12)
    index = np.log(1.05) * (years - 2012)[:, None].astype(float)        # exactly 5% a year, no noise
    result = trend.unit_trends(index, years)
    assert result.rate[0] == pytest.approx(0.05, abs=1e-9)              # log(1.05) = 0.0488 would fail


def test_the_interval_takes_the_ranks_of_the_stated_formula():
    rng = np.random.default_rng(3)
    x = np.arange(15.0)
    y = 0.02 * x + rng.normal(0, 0.1, 15)
    slopes = np.sort([(y[j] - y[i]) / (x[j] - x[i]) for i in range(15) for j in range(i + 1, 15)])
    half = 1.6448536269514722 * np.sqrt(15 * 14 * 35 / 18.0)            # z for 90%, independent points
    lower, upper = int(np.floor((105 - half) / 2)), int(np.ceil((105 + half) / 2)) + 1
    result = trend.theil_sen(x, y, serial=0.0)
    assert result.low == slopes[lower - 1] and result.high == slopes[upper - 1]
    assert result.high > slopes[upper - 2]                             # one rank lower would be a different slope


# ---- bad input is refused by name ------------------------------------------------------


def test_new_modules_refuse_what_they_cannot_read():
    from ntl import firstlight

    with pytest.raises(TypeError, match="integer"):
        persistence.low_runs(np.array([3.0, 4.0]))
    with pytest.raises(ValueError, match="not a conventions.STATUS"):
        persistence.low_runs(np.array([3, 9]))
    assert persistence.low_runs(np.zeros((0, 3), dtype=int)).shape == (0, 3)
    with pytest.raises(TypeError, match="integers"):
        firstlight.first_light(np.ones((2, 1)), np.array([2012.5, 2013.5]))
    with pytest.raises(ValueError, match="no year"):
        firstlight.first_light(np.ones((0, 1)), np.array([], dtype=int))
    result = firstlight.FirstLight(year=np.array([2012, 2015]), from_start=np.array([True, False]))
    with pytest.raises(ValueError, match="only 1 units"):
        firstlight.unit_new_light(result, np.array([0, 1]), units=1, since=2013)
    with pytest.raises(ValueError, match="shape"):
        firstlight.unit_new_light(result, np.array([0]), units=1, since=2013)
    # a cell whose year equals `since` is not new: only later years are
    same = firstlight.FirstLight(year=np.array([2013, 2014]), from_start=np.array([False, False]))
    assert firstlight.unit_new_light(same, np.array([0, 0]), units=1, since=2013).new.tolist() == [1]
    with pytest.raises(ValueError, match="row per month"):
        trend.yearly_medians(3.0, np.array([2020]))
