"""Monitor: units from cells, the rest of the parent, yearly factors, tiers, hold, fallback."""

import datetime as dt
import math

import numpy as np
import pytest

from ntl import conventions as c
from ntl import monitor, status

# ---- cells to units ---------------------------------------------------------


def small_case():
    """Two windows, six cells, three sub-districts in two districts.

    cells:        0     1     2     3     4     5
    sub-district: 101   101   102   102   201   201
    district:     1     1     1     1     2     2
    usual:        10    30    20    20    50    50
    """
    usual = np.array([10.0, 30.0, 20.0, 20.0, 50.0, 50.0])
    subdistrict = np.array([101, 101, 102, 102, 201, 201])
    district = subdistrict // 100
    values = np.array([
        [10.0, 30.0, 10.0, 10.0, 50.0, 50.0],     # window 0: sub-district 102 at half
        [np.nan, 30.0, 0.0, 0.0, np.nan, np.nan],  # window 1: 101 partly seen, 102 dark, 201 unseen
    ])
    nights = np.array([[4, 8, 10, 10, 6, 6], [0, 8, 5, 5, 0, 0]], dtype=float)
    return values, nights, usual, subdistrict, district


def test_level_series_by_hand():
    values, nights, usual, subdistrict, district = small_case()
    s = monitor.level_series(values, nights, usual, subdistrict, parent_codes=district)
    assert s.codes.tolist() == [101, 102, 201]
    assert s.cells.tolist() == [2, 2, 2]
    # Window 0: 101 as usual (0), 102 at half (ln 0.5), 201 as usual.
    np.testing.assert_allclose(s.index[0], [0.0, math.log(0.5), 0.0], atol=1e-12)
    assert s.coverage[0].tolist() == [1.0, 1.0, 1.0]
    assert s.nights[0].tolist() == [6.0, 10.0, 6.0]
    # Window 1: 101 sees its 30 of 40 (coverage 0.75) at the usual level; 102 is seen and dark; 201 unseen.
    assert s.index[1, 0] == pytest.approx(0.0) and s.coverage[1, 0] == 0.75
    assert np.isnan(s.index[1, 1]) and s.dark[1, 1] and not s.dark[1, 0]
    assert np.isnan(s.index[1, 2]) and not s.dark[1, 2] and s.coverage[1, 2] == 0.0
    assert np.isnan(s.nights[1, 2])


def test_rest_of_parent_by_hand():
    values, nights, usual, subdistrict, district = small_case()
    s = monitor.level_series(values, nights, usual, subdistrict, parent_codes=district)
    # Window 0, district 1 holds sub-districts 101 (sum 40 of usual 40) and 102 (20 of 40).
    # Rest of 101 is 102: ln(20/40). Rest of 102 is 101: ln(40/40) = 0.
    assert s.rest[0, 0] == pytest.approx(math.log(0.5))
    assert s.rest[0, 1] == pytest.approx(0.0)
    # Sub-district 201 is alone in its district: no rest, in every window.
    assert np.isnan(s.rest[:, 2]).all()
    # Window 1: the rest of 102 is 101, seen at 30 of its 40 (coverage 0.75), at the usual level.
    assert s.rest[1, 1] == pytest.approx(0.0)
    # The rest of 101 is 102, which is seen and dark: no logarithm.
    assert np.isnan(s.rest[1, 0])


def test_rest_needs_enough_coverage_of_its_own():
    # District 1: sub-district 101 (cells of 10 and 10) and 102 (cells of 10 and 30).
    usual = np.array([10.0, 10.0, 10.0, 30.0])
    subdistrict = np.array([101, 101, 102, 102])
    values = np.array([[10.0, 10.0, 10.0, np.nan]])  # 102 sees 10 of its 40: coverage 0.25
    s = monitor.level_series(values, np.full((1, 4), 9.0), usual, subdistrict, parent_codes=subdistrict // 100)
    assert s.index[0, 0] == pytest.approx(0.0) and np.isnan(s.index[0, 1])
    assert np.isnan(s.rest[0, 0])                 # the rest of 101 is 102, too little of it seen
    assert s.rest[0, 1] == pytest.approx(0.0)     # the rest of 102 is 101, fully seen
    # With a lower bar the same rest is accepted.
    low = monitor.level_series(values, np.full((1, 4), 9.0), usual, subdistrict, subdistrict // 100, min_coverage=0.2)
    assert low.rest[0, 0] == pytest.approx(0.0)


def test_a_unit_without_a_parent_gets_no_rest():
    # Cells of unit 7 and unit 8 both carry parent code 0: they must not be
    # treated as siblings inside a parent called "0".
    usual = np.array([10.0, 10.0, 10.0, 10.0])
    units = np.array([7, 8, 301, 302])
    parents = np.array([0, 0, 3, 3])
    s = monitor.level_series(np.full((2, 4), 10.0), np.full((2, 4), 9.0), usual, units, parent_codes=parents)
    assert np.isnan(s.rest[:, :2]).all()
    assert np.isfinite(s.rest[:, 2:]).all()


def test_nights_average_only_the_cells_that_have_a_count():
    usual = np.array([10.0, 10.0, 10.0])
    values = np.array([[10.0, 10.0, 10.0], [10.0, 10.0, 10.0]])
    nights = np.array([[6.0, np.nan, 12.0], [np.nan, np.nan, np.nan]])
    s = monitor.level_series(values, nights, usual, np.array([5, 5, 5]))
    assert s.nights[0, 0] == 9.0          # (6 + 12) / 2, the cell without a count left out
    assert np.isnan(s.nights[1, 0])       # no count at all is "unknown", never 0
    assert np.isfinite(s.index).all()     # the values themselves are still used


def test_level_series_matches_log_index_window_by_window():
    rng = np.random.default_rng(1)
    usual = rng.uniform(1, 30, 200)
    usual[5] = np.nan  # a cell with no usual value
    codes = rng.integers(0, 9, 200) * 100 + 5200  # includes code 5200 ... and some cells set to 0 below
    codes[:10] = 0
    values = rng.uniform(0, 30, (6, 200))
    values[rng.random((6, 200)) < 0.4] = np.nan
    values[2, codes == 5300] = 0.0  # one unit seen and dark in one window
    s = monitor.level_series(values, np.ones((6, 200)), usual, codes)
    for t in range(6):
        ref = status.log_index(values[t], codes, usual)
        assert s.codes.tolist() == ref.codes.tolist()
        np.testing.assert_allclose(s.index[t], ref.value, atol=1e-12, equal_nan=True)
        np.testing.assert_allclose(s.coverage[t], ref.coverage, atol=1e-12)
        assert s.dark[t].tolist() == ref.dark.tolist()


def test_level_series_refuses_bad_codes():
    values, nights, usual, subdistrict, district = small_case()
    wrong = district.copy()
    wrong[1] = 9
    with pytest.raises(ValueError, match="different parents"):
        monitor.level_series(values, nights, usual, subdistrict, parent_codes=wrong)
    # Float codes are refused, not truncated, for units and for parents.
    with pytest.raises(TypeError, match="integers"):
        monitor.level_series(values, nights, usual, subdistrict.astype(float))
    with pytest.raises(TypeError, match="integers"):
        monitor.level_series(values, nights, usual, subdistrict, parent_codes=district.astype(float))
    with pytest.raises(ValueError, match="negative"):
        monitor.level_series(values, nights, usual, -subdistrict)
    with pytest.raises(ValueError, match="one entry per cell"):
        monitor.level_series(values, nights, usual, subdistrict, parent_codes=district[:-1])


# ---- yearly factors ---------------------------------------------------------


def test_night_class():
    assert monitor.night_class(np.array([4, 7.9, 8, 11, 12, 15, 16, 30, np.nan]), c.NIGHT_CLASS_EDGES_MONTHLY).tolist() == [
        0, 0, 1, 1, 2, 2, 3, 3, -1]


def test_yearly_tail_factor_reads_earlier_years_only():
    rng = np.random.default_rng(2)
    years = np.repeat(np.arange(2012, 2018), 12)
    std = rng.normal(0, 1, (72, 40))
    k = monitor.yearly_tail_factor(std, years, 0.05)
    assert np.isnan(k[years == 2012]).all()               # nothing earlier
    assert np.isfinite(k[years == 2013]).all()            # 480 values from 2012
    assert k[years == 2014][0] == pytest.approx(np.quantile(std[years < 2014], 0.05))
    # Changing 2016 and later must not move the factor of 2015 or 2016.
    changed = std.copy()
    changed[years >= 2016] -= 5.0
    k2 = monitor.yearly_tail_factor(changed, years, 0.05)
    np.testing.assert_array_equal(k2[years <= 2016], k[years <= 2016])
    assert k2[years == 2017][0] < k[years == 2017][0]


def test_yearly_tail_factor_waits_for_a_pool_the_rate_can_rest_on():
    rng = np.random.default_rng(2)
    years = np.repeat(np.arange(2012, 2018), 12)
    std = rng.normal(0, 1, (72, 40))
    k = monitor.yearly_tail_factor(std, years, 0.01)
    # 1% needs 1,000 earlier values: 480 after one year, 960 after two, 1,440 after three.
    assert np.isnan(k[years <= 2014]).all() and np.isfinite(k[years >= 2015]).all()
    # A rate that makes no sense is the caller's mistake and is not swallowed as "pool too small".
    with pytest.raises(ValueError, match="between"):
        monitor.yearly_tail_factor(std, years, 0.7)


def test_class_factors_measure_the_noisier_class():
    rng = np.random.default_rng(3)
    years = np.repeat(np.arange(2012, 2016), 12)
    classes = np.tile(np.array([0, 1]), (48, 400))        # half the units in each class
    std = rng.normal(0, 1, (48, 800)) * np.where(classes == 0, 1.5, 0.75)
    f = monitor.yearly_class_factors(std, classes, years, 2)
    assert f[years == 2012].tolist() == [[1.0, 1.0]] * 12  # nothing earlier
    later = f[years == 2015][0]
    assert later[0] > 1.2 and later[1] < 0.85 and later[0] / later[1] == pytest.approx(2.0, rel=0.1)


# ---- tiers ------------------------------------------------------------------

T, U = 120, 40
MONTHS = (np.arange(T) % 12) + 1
YEARS = 2012 + np.arange(T) // 12
SMALL_UNIT = 7  # a quiet unit with too few cells to be monitorable


def staged_series():
    """Forty units over ten years with independent noise, and five staged events."""
    rng = np.random.default_rng(42)
    t = np.arange(T)
    base = 1.0 + 0.005 * t[:, None] + 0.05 * np.sin(2 * np.pi * MONTHS / 12)[:, None]
    index = base + rng.normal(0, 0.05, (T, U))
    rest = base + rng.normal(0, 0.03, (T, U))
    dark = np.zeros((T, U), dtype=bool)
    drop = math.log(0.5)
    index[110, 0] += drop                      # unit 0: drops alone
    index[110, 1] += drop; rest[110, 1] += drop  # unit 1: drops with the rest of its parent
    index[100, 2] = np.nan; dark[100, 2] = True  # unit 2: seen and dark
    index[105, 3] = np.nan                     # unit 3: not observed
    index[100:, 4] += drop                     # unit 4: a drop that stays
    rest[:, 5] = np.nan                        # unit 5: no parent to compare with
    index[110, 5] += drop
    cells = np.full(U, 50)
    cells[SMALL_UNIT] = c.MIN_UNIT_CELLS - 1
    return monitor.LevelSeries(
        codes=np.arange(1, U + 1) + 5200, index=index, coverage=np.where(np.isfinite(index) | dark, 1.0, 0.0),
        dark=dark, nights=np.full((T, U), 12.0), rest=rest, cells=cells)


@pytest.fixture(scope="module")
def run():
    return monitor.run_level(staged_series(), MONTHS, YEARS)


JUDGED = [c.STATUS_NORMAL, c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL]


def test_states_before_any_history(run):
    assert (run.state[:24] == c.STATUS_NO_REFERENCE).all()        # no expected value yet
    assert (run.state[24:48] == c.STATUS_NO_THRESHOLD).all()      # anomalies, but no scale yet
    # Scales exist from 2016. The 5% factor needs 300 earlier values (one year
    # of 40 units gives 480); the 1% factor needs 1,000 (three years).
    assert np.isnan(run.watch[YEARS < 2017]).all() and np.isfinite(run.watch[YEARS >= 2017]).all()
    assert np.isnan(run.alarm[YEARS < 2019]).all() and np.isfinite(run.alarm[YEARS >= 2019]).all()
    # With tiers, no status until both factors exist.
    assert (run.state[YEARS < 2019][24:] == c.STATUS_NO_THRESHOLD).all()
    assert np.isin(run.state[YEARS == 2019], JUDGED).all()


def test_a_unit_that_drops_alone_is_an_alarm(run):
    assert run.state[110, 0] == c.STATUS_ALARM and run.joint[110, 0]
    assert math.exp(run.anomaly[110, 0]) == pytest.approx(0.5, abs=0.06)
    assert run.held[110, 0]


def test_a_drop_shared_with_the_parent_is_regional(run):
    assert run.state[110, 1] == c.STATUS_REGIONAL
    assert abs(run.relative[110, 1]) < 0.2


def test_dark_and_unobserved_are_kept_apart(run):
    assert run.state[100, 2] == c.STATUS_DARK
    assert run.state[105, 3] == c.STATUS_NOT_OBSERVED


def test_without_a_parent_the_own_history_decides_and_says_so(run):
    assert np.isnan(run.relative[:, 5]).all()
    assert run.state[110, 5] == c.STATUS_ALARM
    # The flag tells this alarm (own history only) from the joint one of unit 0.
    assert not run.joint[:, 5].any()
    assert run.joint[YEARS >= 2019][:, 6:].all()


def test_a_lasting_drop_stays_in_alarm_under_the_hold(run):
    assert run.state[100, 4] == c.STATUS_ALARM and run.held[100, 4]
    # Six, eleven and eighteen months on, the reference has not learned the new level.
    for t in (106, 111, 118):
        assert run.state[t, 4] == c.STATUS_ALARM and run.held[t, 4]
        assert math.exp(run.anomaly[t, 4]) == pytest.approx(0.5, abs=0.08)
    # Without the hold the same window reads much closer to normal: the
    # reference has started to follow the drop. This is what the hold is for.
    plain = status.anomalies(run.series.index[:, 4], MONTHS)
    assert plain[118] > run.anomaly[118, 4] + 0.1


def test_windows_on_hold_do_not_widen_the_scale(run):
    # Unit 4 sits at half from window 100. Its scale afterwards is still the
    # scale of its quiet past (noise 0.05), not that of a series with a step in it.
    assert run.held[100:, 4].all()
    assert run.scale[119, 4] == pytest.approx(run.scale[99, 4], rel=0.15)
    assert run.scale[119, 4] < 0.08


def test_quiet_units_rarely_alarm(run):
    quiet = run.state[:, 6:]                         # units with no staged event
    judged = np.isin(quiet, JUDGED)
    assert judged.sum() > 400
    alarm_rate = (quiet == c.STATUS_ALARM).sum() / judged.sum()
    watch_rate = np.isin(quiet, [c.STATUS_WATCH, c.STATUS_ALARM]).sum() / judged.sum()
    # Both tests must agree, so the joint rates sit well under 1% and 5%.
    assert alarm_rate < 0.01 and watch_rate < 0.05


def test_own_history_test_alone_flags_near_its_target_rates(run):
    # The single test, before the parent is asked, must flag roughly 5% and 1%
    # of quiet windows: not far more, and not almost never.
    late = YEARS >= 2019
    anomaly, scale = run.anomaly[late][:, 6:], run.scale[late][:, 6:]
    watch = (anomaly < run.watch[late][:, None] * scale).mean()
    alarm = (anomaly < run.alarm[late][:, None] * scale).mean()
    assert 0.025 < watch < 0.09
    assert 0.002 < alarm < 0.03


def test_detectable_drop_matches_the_single_unit_formula(run):
    t, u = 115, 10
    expected = status.detectable_drop(run.scale[t, u], run.alarm[t])
    assert run.detectable[t, u] == pytest.approx(expected)
    assert expected <= c.MAX_DETECTABLE_DROP and run.monitorable[t, u]
    # Before the alarm factor exists nothing is detectable, so nothing is monitorable.
    assert np.isnan(run.detectable[YEARS < 2019]).all() and not run.monitorable[YEARS < 2019].any()


def test_a_noisy_unit_is_not_monitorable():
    series = staged_series()
    rng = np.random.default_rng(5)
    noisy = series.index.copy()
    noisy[:, 10] += rng.normal(0, 0.4, T)  # far above what a 40% drop would stand out from
    result = monitor.run_level(series._replace(index=noisy), MONTHS, YEARS)
    assert result.detectable[115, 10] > c.MAX_DETECTABLE_DROP and not result.monitorable[115, 10]
    assert result.monitorable[115, 11]


def test_a_unit_with_too_few_cells_is_never_monitorable(run):
    t = 115
    # Quiet enough by its noise, but under the minimum number of cells.
    assert run.detectable[t, SMALL_UNIT] <= c.MAX_DETECTABLE_DROP
    assert not run.monitorable[:, SMALL_UNIT].any()
    assert np.isin(run.state[t, SMALL_UNIT], JUDGED)  # it still gets a status


def test_nothing_before_a_window_depends_on_what_comes_after(run):
    series = staged_series()
    changed = series.index.copy()
    changed[108:] -= 0.7          # from January 2021 on, everything collapses
    later = monitor.run_level(series._replace(index=changed), MONTHS, YEARS)
    before = slice(0, 108)
    np.testing.assert_array_equal(later.state[before], run.state[before])
    np.testing.assert_array_equal(later.anomaly[before], run.anomaly[before])
    np.testing.assert_array_equal(later.scale[before], run.scale[before])
    np.testing.assert_array_equal(later.alarm[before], run.alarm[before])
    assert (later.state[108] != run.state[108]).any()


def test_the_gap_keeps_the_two_windows_before_out_of_the_fit():
    # An anomaly needs no pooled factor, so three units are enough (and fast).
    full = staged_series()
    keep = [9, 10, 11]
    series = monitor.LevelSeries(
        codes=full.codes[keep], index=full.index[:, keep], coverage=full.coverage[:, keep], dark=full.dark[:, keep],
        nights=full.nights[:, keep], rest=full.rest[:, keep], cells=full.cells[keep])
    u, t = 1, 110
    changed = series.index.copy()
    changed[t - 2:t, u] += 0.3
    for gap, same in ((2, True), (0, False)):
        a = monitor.run_level(series, MONTHS, YEARS, gap=gap).anomaly[t, u]
        b = monitor.run_level(series._replace(index=changed), MONTHS, YEARS, gap=gap).anomaly[t, u]
        assert bool(a == b) is same


def test_fewer_nights_get_a_wider_scale():
    rng = np.random.default_rng(8)
    t = np.arange(T)
    base = 1.0 + 0.005 * t[:, None]
    few = rng.random((T, U)) < 0.5                                   # half the windows rest on few nights
    index = base + rng.normal(0, 0.05, (T, U)) * np.where(few, 2.0, 1.0)  # and are twice as noisy
    series = monitor.LevelSeries(
        codes=np.arange(1, U + 1), index=index, coverage=np.ones((T, U)), dark=np.zeros((T, U), dtype=bool),
        nights=np.where(few, 5.0, 20.0), rest=np.full((T, U), np.nan), cells=np.full(U, 50))
    result = monitor.run_level(series, MONTHS, YEARS)
    late = slice(100, 120)
    ratio = np.nanmedian(result.scale[late][few[late]]) / np.nanmedian(result.scale[late][~few[late]])
    assert ratio == pytest.approx(2.0, rel=0.25)
    # With one class for every window the factor is 1 and the scale ignores the nights.
    flat = monitor.run_level(series._replace(nights=np.full((T, U), 20.0)), MONTHS, YEARS)
    flat_ratio = np.nanmedian(flat.scale[late][few[late]]) / np.nanmedian(flat.scale[late][~few[late]])
    assert flat_ratio == pytest.approx(1.0, abs=0.05)


def test_retrospective_judges_the_early_windows_with_hindsight(run):
    hind = monitor.run_level(run.series, MONTHS, YEARS, retrospective=True)
    # A monitor has no threshold early on; hindsight has one from the first anomaly on.
    early = slice(24, 48)
    assert (run.state[early] == c.STATUS_NO_THRESHOLD).all()
    assert np.isin(hind.state[early, 6:], JUDGED).all()
    assert len(set(np.round(hind.alarm, 12).tolist())) == 1          # one factor for the whole record
    assert np.nanstd(hind.scale[30:, 10]) == pytest.approx(0.0, abs=1e-12)  # one scale per unit
    # The expected values are the same wherever neither run put a window on
    # hold; hindsight has thresholds earlier, so it can hold earlier windows.
    no_hold = ~hind.held[:100].any(axis=0) & ~run.held[:100].any(axis=0)
    assert no_hold.sum() >= 10
    np.testing.assert_allclose(hind.anomaly[:100, no_hold], run.anomaly[:100, no_hold], atol=1e-9, equal_nan=True)
    assert hind.held[:60].any() and not run.held[:60].any()
    assert hind.state[110, 0] == c.STATUS_ALARM and hind.state[110, 1] == c.STATUS_REGIONAL


def test_without_tiers_a_low_unit_is_regional_never_an_alarm(run):
    plain = monitor.run_level(run.series, MONTHS, YEARS, tiers=False)
    assert not np.isin(plain.state, [c.STATUS_WATCH, c.STATUS_ALARM]).any()
    # Once both factors exist, every unit-window that was WATCH, ALARM or
    # REGIONAL with tiers is REGIONAL without them, and no other.
    both = YEARS >= 2019
    low_with_tiers = np.isin(run.state, [c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL])
    np.testing.assert_array_equal((plain.state == c.STATUS_REGIONAL)[both], low_with_tiers[both])
    assert plain.state[110, 0] == c.STATUS_REGIONAL   # the unit that dropped alone
    assert plain.state[100, 2] == c.STATUS_DARK       # dark is still its own state
    # Without tiers the watch factor is enough: 2017 and 2018 are judged,
    # where the run with tiers was still waiting for the alarm factor.
    waiting = (YEARS >= 2017) & (YEARS < 2019)
    assert (run.state[waiting] == c.STATUS_NO_THRESHOLD).all()
    assert np.isin(plain.state[waiting], [c.STATUS_NORMAL, c.STATUS_REGIONAL]).all()
    assert (plain.state[waiting] == c.STATUS_REGIONAL).any()
    # The parent comparison is not used without tiers, so nothing is "joint".
    assert run.joint.any() and not plain.joint.any()
    # Nothing else about the result changes.
    np.testing.assert_array_equal(plain.anomaly, run.anomaly)
    np.testing.assert_array_equal(plain.held, run.held)


def test_run_level_refuses_dates_and_disordered_rates():
    series = staged_series()
    dates = np.array([dt.date(2012 + i // 12, i % 12 + 1, 1) for i in range(T)])
    with pytest.raises(TypeError, match="calendar months"):
        monitor.run_level(series, dates, YEARS)
    with pytest.raises(ValueError, match="1 to 12"):
        monitor.run_level(series, np.arange(T), YEARS)
    with pytest.raises(ValueError, match="shape"):
        monitor.run_level(series, MONTHS[:-1], YEARS)
    with pytest.raises(TypeError, match="calendar years"):
        monitor.run_level(series, MONTHS, YEARS.astype(float))
    with pytest.raises(ValueError, match="shape"):
        monitor.run_level(series, MONTHS, YEARS[:-1])
    with pytest.raises(ValueError, match="series.cells"):
        monitor.run_level(series._replace(cells=series.cells[:-1]), MONTHS, YEARS)
    for watch, alarm in ((0.01, 0.05), (0.05, 0.05), (0.6, 0.01), (0.05, 0.0)):
        with pytest.raises(ValueError, match="alarm_rate < watch_rate"):
            monitor.run_level(series, MONTHS, YEARS, watch_rate=watch, alarm_rate=alarm)


# ---- children agreeing ------------------------------------------------------

N, W, A, R, D, X, NT = (c.STATUS_NORMAL, c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL, c.STATUS_DARK,
                        c.STATUS_NOT_OBSERVED, c.STATUS_NO_THRESHOLD)


def test_children_agreement_by_hand():
    # Five sub-districts: four in district 5208, one in 5271. Two windows.
    codes = np.array([520801, 520802, 520803, 520804, 527101])
    state = np.array([
        [N, R, R, X, N],   # 5208: three judged, two low (regional counts as low); 5271: one judged, none low
        [D, W, A, N, X],   # 5208: four judged, three low (dark counts); 5271: none judged
    ], dtype=np.uint8)
    out = monitor.children_agreement(state, codes, np.array([5208, 5271, 9999]))
    assert out.judged.tolist() == [[3, 1, 0], [4, 0, 0]]
    assert out.low.tolist() == [[2, 0, 0], [3, 0, 0]]
    assert out.share[0, 0] == pytest.approx(2 / 3) and out.share[1, 0] == 0.75
    assert out.share[0, 1] == 0.0 and np.isnan(out.share[1, 1]) and np.isnan(out.share[:, 2]).all()
    # The same step one level up: districts in provinces.
    up = monitor.children_agreement(np.array([[R, N, W]], dtype=np.uint8), np.array([5208, 5271, 5301]), np.array([52, 53]))
    assert up.judged.tolist() == [[2, 1]] and up.low.tolist() == [[1, 1]]


def test_children_with_too_few_cells_do_not_vote():
    codes = np.array([520801, 520802, 520803, 520804])
    state = np.array([[D, D, N, N]], dtype=np.uint8)
    cells = np.array([3, c.MIN_UNIT_CELLS - 1, c.MIN_UNIT_CELLS, 400])
    everyone = monitor.children_agreement(state, codes, np.array([5208]))
    assert (everyone.judged[0, 0], everyone.low[0, 0]) == (4, 2)
    # The two dark children are tiny: with the cell rule they say nothing about the district.
    eligible = monitor.children_agreement(state, codes, np.array([5208]), child_cells=cells)
    assert (eligible.judged[0, 0], eligible.low[0, 0]) == (2, 0)
    lower_bar = monitor.children_agreement(state, codes, np.array([5208]), child_cells=cells, min_cells=3)
    assert lower_bar.judged[0, 0] == 4


def test_children_agreement_refuses_bad_input():
    state = np.array([[N, N]], dtype=np.uint8)
    codes = np.array([520801, 520802])
    with pytest.raises(ValueError, match="one code per child"):
        monitor.children_agreement(state, codes[:1], np.array([5208]))
    with pytest.raises(ValueError, match="without repeats"):
        monitor.children_agreement(state, codes, np.array([5208, 5208]))
    with pytest.raises(TypeError, match="integers"):
        monitor.children_agreement(state, codes.astype(float), np.array([5208]))
    with pytest.raises(ValueError, match="one entry per child"):
        monitor.children_agreement(state, codes, np.array([5208]), child_cells=np.array([30]))


def test_parent_is_raised_only_when_enough_children_agree():
    parent = np.array([[N, N, X, NT, W, N]], dtype=np.uint8)
    agreement = monitor.Agreement(
        judged=np.array([[4, 4, 4, 4, 4, 2]]),
        low=np.array([[3, 1, 4, 3, 4, 2]]),
        share=np.array([[0.75, 0.25, 1.0, 0.75, 1.0, 1.0]]),
    )
    out = monitor.confirm_by_children(parent, agreement, min_share=0.5, min_children=3)
    # 0: raised. 1: too few low. 2: the parent itself was not seen, so nothing is claimed.
    # 3: no threshold of its own, raised by its children. 4: already WATCH, kept. 5: only two children judged.
    assert out.tolist() == [[R, N, X, R, W, N]]
    assert parent.tolist() == [[N, N, X, NT, W, N]]  # the input is not changed
    with pytest.raises(ValueError, match="shape"):
        monitor.confirm_by_children(parent[:, :3], agreement)


def test_the_default_rule_is_more_than_two_thirds():
    # Three parents, all NORMAL: 2 of 3 low, 4 of 6 low, 3 of 4 low; and one with no judged child.
    codes = np.array([110101, 110102, 110103,
                      120101, 120102, 120103, 120104, 120105, 120106,
                      130101, 130102, 130103, 130104,
                      140101])
    state = np.array([[R, R, N,  R, R, R, R, N, N,  R, R, R, N,  X]], dtype=np.uint8)
    parents = np.array([1101, 1201, 1301, 1401])
    agreement = monitor.children_agreement(state, codes, parents)
    assert agreement.low.tolist() == [[2, 4, 3, 0]] and agreement.judged.tolist() == [[3, 6, 4, 0]]
    out = monitor.confirm_by_children(np.full((1, 4), N, dtype=np.uint8), agreement)
    # Exactly two thirds is not "more than two thirds", however it is counted.
    assert out.tolist() == [[N, N, R, N]]


# ---- fallback ---------------------------------------------------------------


def test_reporting_level_falls_back_by_code_prefix():
    subdistricts = np.array([520801, 520802, 520901, 530101, 610101])
    subdistrict_ok = np.array([True, False, False, False, False])
    districts = np.array([5208, 5209, 5301, 6101])
    district_ok = np.array([True, False, False, False])
    provinces = np.array([52, 53, 61])
    province_ok = np.array([True, False, False])
    level = monitor.reporting_level(subdistricts, subdistrict_ok, districts, district_ok, provinces, province_ok)
    # 520801 itself; 520802 through district 5208; 520901 through province 52;
    # 530101 and 610101 through nothing.
    assert level.tolist() == [c.REPORT_SUBDISTRICT, c.REPORT_DISTRICT, c.REPORT_PROVINCE, c.REPORT_NONE, c.REPORT_NONE]
    assert level.tolist() == [3, 2, 1, 0, 0]


def test_reporting_level_refuses_misaligned_or_ambiguous_input():
    subdistricts, ok = np.array([520801, 520802]), np.array([True, False])
    districts, d_ok = np.array([5208]), np.array([True])
    provinces, p_ok = np.array([52]), np.array([True])
    with pytest.raises(ValueError, match="one flag per code"):
        monitor.reporting_level(subdistricts, ok[:1], districts, d_ok, provinces, p_ok)
    with pytest.raises(ValueError, match="more than once"):
        monitor.reporting_level(subdistricts, ok, np.array([5208, 5208]), np.array([True, False]), provinces, p_ok)
    with pytest.raises(TypeError, match="boolean"):
        monitor.reporting_level(subdistricts, np.array([1, 0]), districts, d_ok, provinces, p_ok)
    with pytest.raises(TypeError, match="integers"):
        monitor.reporting_level(subdistricts.astype(float), ok, districts, d_ok, provinces, p_ok)
