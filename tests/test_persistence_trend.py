"""Persistence (low runs and episodes) and trend (yearly medians, Theil-Sen)."""

import math

import numpy as np
import pytest

from ntl import conventions as c
from ntl import cellmaps, firstlight, persistence, trend

X, R, T_, N, W, A, G, D = (c.STATUS_NOT_OBSERVED, c.STATUS_NO_REFERENCE, c.STATUS_NO_THRESHOLD, c.STATUS_NORMAL,
                           c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL, c.STATUS_DARK)


# ---- persistence ---------------------------------------------------------------


def test_low_runs_and_spans_by_hand():
    #        0  1  2  3  4  5  6  7  8  9  10 11 12 13 14
    state = [N, W, A, X, G, A, N, W, D, W, R, T_, W, G, W]
    #  W, A, (unseen), (regional: neither ends nor adds), A; ended by N; W alone ended by D;
    #  W, two silent windows, W (bridged), regional, W
    assert persistence.low_runs(state).tolist() == [0, 1, 2, 0, 0, 3, 0, 1, 0, 1, 0, 0, 2, 0, 3]
    assert persistence.run_spans(state).tolist() == [0, 1, 2, 0, 0, 5, 0, 1, 0, 1, 0, 0, 4, 0, 6]


def test_three_silent_windows_in_a_row_end_an_episode():
    assert persistence.low_runs([W, X, X, W]).tolist() == [1, 0, 0, 2]           # two: bridged
    assert persistence.low_runs([W, X, R, T_, W]).tolist() == [1, 0, 0, 0, 1]    # three: a new episode
    assert persistence.low_runs([W, X, X, G, X, X, W]).tolist() == [1, 0, 0, 0, 0, 0, 2]   # a regional window breaks the silent streak
    assert persistence.MAX_SILENT == 3


def test_low_runs_use_the_past_only():
    rng = np.random.default_rng(4)
    state = rng.integers(0, 8, size=(60, 9))
    full = persistence.low_runs(state)
    for cut in (1, 17, 59):
        np.testing.assert_array_equal(persistence.low_runs(state[:cut]), full[:cut])
    with pytest.raises(ValueError, match="shape"):
        persistence.low_runs(np.zeros((2, 2, 2), dtype=int))


def test_episodes_by_hand():
    state = np.array([
        [N, W, A, X, G, N, W, D, W, R, T_, W],     # unit 0: three episodes, the last still open
        [N, G, G, N, N, N, N, N, N, N, N, N],      # unit 1: regional only, so none
        [A, A, X, X, X, X, X, X, X, X, X, X],      # unit 2: one, closed by the long silence after it
    ]).T
    e = persistence.episodes(state)
    assert e.unit.tolist() == [0, 0, 0, 2]
    assert e.start.tolist() == [1, 6, 8, 0] and e.end.tolist() == [2, 6, 11, 1]
    assert e.length.tolist() == [2, 1, 2, 2]          # low windows only
    assert e.span.tolist() == [2, 1, 4, 2]            # calendar windows, silent ones included
    assert e.open.tolist() == [False, False, True, False]
    assert e.worst.tolist() == [A, W, W, A]
    s = persistence.summarise(state)
    assert s.count.tolist() == [3, 0, 1] and s.longest.tolist() == [2, 0, 2] and s.longest_span.tolist() == [4, 0, 2]
    assert s.low_windows.tolist() == [5, 0, 2] and s.regional_windows.tolist() == [1, 2, 0]
    assert s.judged_windows.tolist() == [8, 12, 2]
    # The run length and span of an episode's last low window are the episode's own.
    assert persistence.low_runs(state)[e.end, e.unit].tolist() == e.length.tolist()
    assert persistence.run_spans(state)[e.end, e.unit].tolist() == e.span.tolist()


def test_episodes_agree_with_the_running_counts_on_random_series():
    rng = np.random.default_rng(9)
    state = rng.choice([X, R, N, W, A, G, D], size=(200, 30), p=[0.3, 0.05, 0.35, 0.1, 0.05, 0.1, 0.05])
    e = persistence.episodes(state)
    runs, spans = persistence.low_runs(state), persistence.run_spans(state)
    assert (runs[e.end, e.unit] == e.length).all() and (spans[e.end, e.unit] == e.span).all()
    assert e.length.sum() == np.isin(state, persistence.LOW_STATES).sum()      # every low window is in exactly one episode


def test_no_episode_at_all():
    e = persistence.episodes(np.full((5, 2), N))
    assert e.unit.size == 0 and e.span.size == 0
    assert persistence.summarise(np.full((5, 2), N)).longest.tolist() == [0, 0]
    with pytest.raises(ValueError, match="shape"):
        persistence.episodes([N, W])


# ---- trend ---------------------------------------------------------------------


def test_yearly_medians_need_enough_months():
    years = np.repeat([2012, 2013, 2014], 12)
    values = np.concatenate([np.arange(12.0), np.full(12, 5.0), np.full(12, np.nan)])
    values[12:19] = np.nan                 # 2013 keeps 5 values: one short of the 6 needed
    got_years, medians = trend.yearly_medians(values, years)
    assert got_years.tolist() == [2012, 2013, 2014]
    assert medians[0] == 5.5 and np.isnan(medians[1]) and np.isnan(medians[2])
    assert trend.yearly_medians(values, years, min_months=5)[1][1] == 5.0
    with pytest.raises(TypeError, match="integers"):
        trend.yearly_medians(values, years.astype(float))
    with pytest.raises(ValueError, match="rows"):
        trend.yearly_medians(values[:-1], years)


def test_theil_sen_by_hand():
    # Four points: pairwise slopes are 1, 1, 2, 1, 2.5, 4. Their median is 1.5.
    x = [0.0, 1.0, 2.0, 3.0]
    y = [0.0, 1.0, 2.0, 6.0]
    result = trend.theil_sen(x, y, min_points=4)
    assert result.slope == pytest.approx(1.5) and result.points == 4
    assert result.low <= result.slope <= result.high
    # One wild point does not move it much; a least-squares fit would be pulled far.
    assert trend.theil_sen(range(9), [0, 1, 2, 3, 400, 5, 6, 7, 8], min_points=4).slope == pytest.approx(1.0)


def test_theil_sen_interval_covers_a_known_slope_and_excludes_zero():
    rng = np.random.default_rng(11)
    x = np.arange(15.0)
    hits = 0
    for _ in range(400):
        result = trend.theil_sen(x, 0.05 * x + rng.normal(0, 0.1, x.size), serial=0.0)
        hits += result.low <= 0.05 <= result.high
    assert 0.86 <= hits / 400 <= 0.97          # the classical 90% interval on independent noise
    clear = trend.theil_sen(x, 0.05 * x + rng.normal(0, 0.02, x.size))
    assert clear.low > 0
    flat = trend.theil_sen(x, rng.normal(0, 0.1, x.size))
    assert flat.low < 0 < flat.high


def test_the_interval_is_widened_for_correlated_years():
    rng = np.random.default_rng(12)
    x = np.arange(14.0)
    r = trend.SERIAL_CORRELATION
    plain = wide = 0
    for _ in range(600):
        noise = np.empty(x.size)
        noise[0] = rng.normal(0, 1 / np.sqrt(1 - r * r))
        for k in range(1, x.size):
            noise[k] = r * noise[k - 1] + rng.normal()          # no trend at all, correlated from year to year
        a, b = trend.theil_sen(x, noise, serial=0.0), trend.theil_sen(x, noise)
        plain += not (a.low <= 0 <= a.high)
        wide += not (b.low <= 0 <= b.high)
        assert b.low <= a.low and b.high >= a.high and b.slope == a.slope
    # The classical interval calls a trend far too often on such series (about a third of the time here).
    # The widened one errs on the wide side: at most its nominal 10%, in fact about 3% with 14 years.
    assert plain / 600 > 0.25 and wide / 600 <= 0.12
    with pytest.raises(ValueError, match="serial"):
        trend.theil_sen(x, x, serial=1.0)


def test_theil_sen_refuses_what_it_cannot_use():
    assert math.isnan(trend.theil_sen([0, 1, 2], [0, 1, 2]).slope)                 # under the 8 points needed
    assert trend.theil_sen([0, 1, 2, np.nan], [0, 1, np.nan, 3], min_points=2).points == 2
    with pytest.raises(ValueError, match="same x"):
        trend.theil_sen([0, 0, 1], [0, 1, 2], min_points=2)
    with pytest.raises(ValueError, match="confidence"):
        trend.theil_sen([0, 1, 2], [0, 1, 2], min_points=2, confidence=1.0)
    with pytest.raises(ValueError, match="equal length"):
        trend.theil_sen([0, 1], [0, 1, 2])


def test_unit_trends_recover_growth_and_ignore_the_time_of_year():
    years = np.repeat(np.arange(2012, 2027), 12)
    month = np.tile(np.arange(12), 15)
    t = np.arange(years.size) / 12.0
    rng = np.random.default_rng(2)
    season = 0.2 * np.sin(2 * np.pi * month / 12)
    growing = np.log(1.05) * t + season + rng.normal(0, 0.03, t.size)        # 5% a year
    steady = season + rng.normal(0, 0.03, t.size)
    thin = growing.copy()
    thin[years > 2016] = np.nan                                               # five years only
    result = trend.unit_trends(np.column_stack([growing, steady, thin]), years)
    assert result.rate[0] == pytest.approx(0.05, abs=0.004) and result.low[0] > 0
    assert abs(result.rate[1]) < 0.004 and result.low[1] < 0 < result.high[1]
    assert np.isnan(result.rate[2]) and result.years.tolist() == [15, 15, 5]
    assert (result.first_year, result.last_year) == (2012, 2026)
    with pytest.raises(ValueError, match="shape"):
        trend.unit_trends(growing, years)


# ---- unseen runs ---------------------------------------------------------------


def test_unseen_runs_by_hand():
    state = [N, X, X, W, X, R, X, X, X]
    assert persistence.unseen_runs(state).tolist() == [0, 1, 2, 0, 1, 0, 1, 2, 3]
    grid = np.array([[X, N], [X, X], [N, X]])
    assert persistence.unseen_runs(grid).tolist() == [[1, 0], [2, 1], [0, 2]]


# ---- first light ---------------------------------------------------------------


def test_yearly_cell_medians_need_three_usable_months():
    years = np.repeat([2012, 2013], 12)
    values = np.full((24, 2), np.nan)
    values[:5, 0] = [1, 2, 3, 4, 100]         # 2012, cell 0: median 3
    values[12:14, 0] = 9.0                    # 2013, cell 0: two months only
    values[12:, 1] = 7.0                      # 2013, cell 1: every month
    got_years, yearly = firstlight.yearly_cell_medians(values, years)
    assert got_years.tolist() == [2012, 2013]
    assert yearly[0, 0] == 3.0 and np.isnan(yearly[1, 0]) and np.isnan(yearly[0, 1]) and yearly[1, 1] == 7.0
    with pytest.raises(ValueError, match="shape"):
        firstlight.yearly_cell_medians(values[:, 0], years)


def test_first_light_by_hand():
    years = np.arange(2012, 2020)
    nan = np.nan
    yearly = np.array([
        # 2012 13   14   15   16   17   18   19
        [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],   # 0 lit throughout: from the start
        [0.5, 0.5, 0.5, 3.0, 4.0, 5.0, 6.0, 7.0],   # 1 lights up in 2015
        [0.5, 3.0, 0.5, 0.5, 3.0, nan, 4.0, 5.0],   # 2 a false start in 2013, then 2016 (a year without a value does not break it)
        [5.0, 5.0, 5.0, 5.0, 0.5, 0.5, 0.5, 0.5],   # 3 lit, then dark at the end: no year
        [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5.0],   # 4 lit in the final year only: not persistent yet
        [nan, nan, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0],   # 5 first seen in 2014 and lit ever since: from the start of its record
        [nan, nan, nan, nan, nan, nan, nan, nan],   # 6 never a value
        [1.9, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],   # 7 exactly at the threshold from 2013
    ]).T
    result = firstlight.first_light(yearly, years)
    assert result.year.tolist() == [2012, 2015, 2016, 0, 0, 2014, 0, 2013]
    assert result.from_start.tolist() == [True, False, False, False, False, True, False, False]
    with pytest.raises(ValueError, match="ascending"):
        firstlight.first_light(yearly, years[::-1])
    with pytest.raises(ValueError, match="shape"):
        firstlight.first_light(yearly[:, 0], years)


def test_unit_new_light_counts_cells_lit_after_the_start():
    result = firstlight.FirstLight(year=np.array([2012, 2015, 2016, 0, 2014, 2019, 2013]),
                                   from_start=np.array([True, False, False, False, True, False, False]))
    position = np.array([0, 0, 0, 0, 1, 1, -1])      # the last cell is in no unit of this level
    got = firstlight.unit_new_light(result, position, units=3, since=2013)
    assert got.cells.tolist() == [4, 2, 0] and got.dated.tolist() == [3, 2, 0]
    assert got.new.tolist() == [2, 1, 0]             # 2014 in unit 1 was lit from the start of its record: not new
    assert got.median_year[0] == 2015.5 and got.median_year[1] == 2019 and np.isnan(got.median_year[2])


# ---- per-cell monthly classes ---------------------------------------------------


def test_radiance_and_observation_classes_by_hand():
    values = [np.nan, 0.0, 0.4, 2.0, 4.99, 5.0, 19.0, 39.9, 40.0, 300.0]
    assert cellmaps.radiance_class(values).tolist() == [0, 1, 2, 3, 3, 4, 5, 6, 7, 7]
    assert cellmaps.observation_class([0, 1, 3, 4, 9, 10, 31]).tolist() == [0, 1, 1, 2, 2, 3, 3]


def test_change_class_compares_with_the_same_month_a_year_earlier():
    then = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 0.0, 0.0, 10.0, np.nan, 10.0])
    now = np.array([4.9, 5.0, 8.4, 8.5, 11.4, 14.0, 20.0, 0.0, 3.0, 0.0, 5.0, np.nan])
    values = np.full((13, then.size), np.nan)
    values[0], values[12] = then, now
    got = cellmaps.change_class(values)
    assert not got[:12].any()                                        # nothing to compare with in the first year
    #                            <.5 .5-.7 .7-.85 same same 1.4-2 >=2 both0 new gone  no  no
    assert got[12].tolist() == [1,  2,    3,     4,   4,   6,    7,  4,    7,  1,    0,  0]
    assert cellmaps.change_class(values[:12]).shape == (12, then.size)
    with pytest.raises(ValueError, match="lag"):
        cellmaps.change_class(values, lag=0)


def test_pack_round_trips_the_three_classes():
    rng = np.random.default_rng(6)
    values = rng.gamma(2.0, 6.0, (30, 40))
    values[rng.random(values.shape) < 0.3] = np.nan
    values[rng.random(values.shape) < 0.05] = 0.0
    counts = rng.integers(0, 20, values.shape)
    packed = cellmaps.pack(values, counts)
    assert packed.dtype == np.uint8
    radiance, change, seen = cellmaps.unpack(packed)
    np.testing.assert_array_equal(radiance, cellmaps.radiance_class(values))
    np.testing.assert_array_equal(change, cellmaps.change_class(values))
    np.testing.assert_array_equal(seen, cellmaps.observation_class(counts))
    with pytest.raises(ValueError, match="shape"):
        cellmaps.pack(values, counts[:-1])


# ---- then and now --------------------------------------------------------------


def test_then_and_now_by_hand():
    years = np.arange(2012, 2020)
    nan = np.nan
    yearly = np.array([
        # then: 2012 13   14  | 15   16  | now: 17   18   19
        [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],   # 0 lit then and now
        [1.0, 1.2, 1.5, 3.0, 4.0, 5.0, 6.0, 7.0],   # 1 dim then, lit now: brightened
        [0.0, 0.0, 0.4, 3.0, 4.0, 5.0, 6.0, 7.0],   # 2 dark then, lit now: emerged
        [5.0, 5.0, 5.0, 5.0, 1.0, 1.0, 0.0, 1.0],   # 3 lit then, not now: faded
        [1.0, 1.0, 1.0, 9.0, 9.0, 1.0, 1.0, 1.0],   # 4 not lit at either end (the middle does not count)
        [nan, nan, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],   # 5 one early value only: unknown
        [0.0, nan, 0.0, 3.0, 3.0, nan, 3.0, 3.0],   # 6 two values in each period are enough: emerged
        [0.5, 0.5, 0.5, 2.0, 2.0, 2.0, 2.0, 2.0],   # 7 exactly at both lines: 0.5 is dim, 2.0 is lit
    ]).T
    got = firstlight.then_and_now(yearly, years)
    assert got.tolist() == [1, 2, 3, 4, 5, 0, 3, 2]
    with pytest.raises(ValueError, match="fewer than two periods"):
        firstlight.then_and_now(yearly[:5], years[:5])
    counts = firstlight.unit_class_counts(got, np.array([0, 0, 0, 1, 1, 1, -1, 0]), units=2)
    assert counts.tolist() == [[0, 1, 2, 1, 0, 0], [1, 0, 0, 0, 1, 1]]
