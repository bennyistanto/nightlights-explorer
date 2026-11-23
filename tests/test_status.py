"""Status statistic, on cases built so the right answer is known.

Several tests here were rewritten after the standards review of 2026-11-22
showed that their first versions would have passed with the feature they
name removed. Each now states what would make it fail.
"""

import math

import numpy as np
import pytest

from ntl import conventions as c
from ntl import status

# ---- log index -------------------------------------------------------------

USUAL = np.array([10.0, 10.0, 80.0])
ONE_UNIT = np.array([5, 5, 5])


def test_log_index_compares_like_with_like():
    # All seen, exactly as usual: ratio 1, log 0.
    full = status.log_index(np.array([10.0, 10.0, 80.0]), ONE_UNIT, USUAL)
    assert full.value[0] == pytest.approx(0.0) and full.coverage[0] == 1.0 and not full.dark[0]
    # Only the bright cell seen, at its usual level: still 0, not "bright".
    centre = status.log_index(np.array([np.nan, np.nan, 80.0]), ONE_UNIT, USUAL)
    assert centre.value[0] == pytest.approx(0.0) and centre.coverage[0] == pytest.approx(0.8)
    # Everything seen at half its usual level: ln 0.5.
    half = status.log_index(USUAL / 2, ONE_UNIT, USUAL)
    assert half.value[0] == pytest.approx(math.log(0.5))


def test_no_status_under_half_coverage_and_never_dark_when_unseen():
    # The two dim cells carry 20% of the unit's light.
    out = status.log_index(np.array([10.0, 10.0, np.nan]), ONE_UNIT, USUAL)
    assert np.isnan(out.value[0]) and out.coverage[0] == pytest.approx(0.2) and not out.dark[0]
    unseen = status.log_index(np.full(3, np.nan), ONE_UNIT, USUAL)
    assert np.isnan(unseen.value[0]) and unseen.coverage[0] == 0.0 and not unseen.dark[0]


def test_seen_and_dark_is_its_own_state():
    # Every cell observed and reading zero: no logarithm, but not "unseen".
    out = status.log_index(np.zeros(3), ONE_UNIT, USUAL)
    assert np.isnan(out.value[0]) and out.coverage[0] == 1.0 and out.dark[0]
    # At exactly the minimum coverage the unit still counts as seen.
    edge = status.log_index(np.array([np.nan, np.nan, 0.0]), ONE_UNIT, np.array([25.0, 25.0, 50.0]))
    assert edge.coverage[0] == 0.5 and edge.dark[0]


def test_cells_without_a_usual_value_do_not_break_the_tile():
    # A sea cell (no unit) and a land cell with no long-term mean.
    values = np.array([np.nan, 7.0, 20.0, 40.0])
    codes = np.array([0, 9, 9, 9])
    usual = np.array([np.nan, np.nan, 20.0, 80.0])
    out = status.log_index(values, codes, usual)
    # The unusable land cell is left out: (20 + 40) / (20 + 80), coverage 1.
    assert out.codes.tolist() == [9]
    assert out.value[0] == pytest.approx(math.log(0.6)) and out.coverage[0] == 1.0


def test_log_index_keeps_units_apart():
    values = np.array([5.0, 5.0, 30.0, np.nan])
    codes = np.array([1, 1, 2, 2])
    usual = np.array([10.0, 10.0, 10.0, 90.0])
    out = status.log_index(values, codes, usual)
    assert out.codes.tolist() == [1, 2]
    assert out.value[0] == pytest.approx(math.log(0.5))
    assert np.isnan(out.value[1]) and out.coverage[1] == pytest.approx(0.1)


# ---- scale -----------------------------------------------------------------


def test_robust_scale_ignores_an_outlier():
    sample = np.array([-2.0, -1.0, 0.0, 1.0, 2.0, 100.0, np.nan])
    # Median of the six finite values is 0.5; absolute deviations are
    # 2.5, 1.5, 0.5, 0.5, 1.5, 99.5, whose median is 1.5.
    assert status.robust_scale(sample) == pytest.approx(c.MAD_TO_SD * 1.5)
    assert math.isnan(status.robust_scale(np.array([np.nan])))
    assert status.robust_scale(np.array([3.0])) == 0.0


# ---- the fit ---------------------------------------------------------------


def seasonal_series(n=96, slope=0.006, season=0.05):
    """ln light growing 0.6% a month with a yearly cycle, no noise."""
    t = np.arange(n)
    months = (t % 12) + 1
    return t, months, 1.0 + slope * t + season * np.sin(2 * np.pi * months / 12)


def ols_predict(t, months, y, t_new, m_new):
    """Plain least squares on the same model, to show what robustness buys."""
    levels = np.unique(months)
    design = np.column_stack([t.astype(float)] + [(months == m).astype(float) for m in levels])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(np.concatenate([[t_new], (levels == m_new).astype(float)]) @ beta)


def test_fit_recovers_trend_and_season_exactly():
    t, months, y = seasonal_series()
    past = t < 84
    assert status.huber_predict(t[past], months[past], y[past], 90.0, int(months[90])) == pytest.approx(y[90], abs=1e-9)


def test_fit_is_not_dragged_by_a_bad_month_where_least_squares_is():
    t, months, y = seasonal_series()
    truth = y[90]
    y = y.copy()
    y[78] -= 1.0  # same calendar month as the target, near the end of the fit
    past = t < 84
    plain = ols_predict(t[past], months[past], y[past], 90.0, int(months[90]))
    robust = status.huber_predict(t[past], months[past], y[past], 90.0, int(months[90]))
    assert abs(plain - truth) > 0.1          # least squares is pulled far
    assert abs(robust - truth) < 1e-6        # the robust fit is not
    # And with a single pass the function IS least squares: the passes matter.
    one_pass = status.huber_predict(t[past], months[past], y[past], 90.0, int(months[90]), passes=1)
    assert one_pass == pytest.approx(plain, abs=1e-9)


def test_fit_refuses_what_it_cannot_determine():
    # The target's calendar month was never seen.
    with pytest.raises(status.FitError, match="calendar month"):
        status.huber_predict(np.arange(6.0), np.array([1, 2, 3, 1, 2, 3]), np.zeros(6), 7.0, 9)
    # One window per calendar month: slope and levels cannot be told apart.
    t = np.arange(12.0)
    with pytest.raises(status.FitError, match="different times"):
        status.huber_predict(t, (t % 12 + 1).astype(int), 0.1 * t, 12.0, 1)


def test_fit_refuses_bad_arguments():
    t, months, y = seasonal_series(n=30)
    bad = y.copy()
    bad[3] = np.nan
    with pytest.raises(ValueError, match="finite"):
        status.huber_predict(t, months, bad, 30.0, 7)
    with pytest.raises(ValueError, match="passes"):
        status.huber_predict(t, months, y, 30.0, 7, passes=0)
    with pytest.raises(ValueError, match="tuning"):
        status.huber_predict(t, months, y, 30.0, 7, tuning=0.0)
    with pytest.raises(ValueError, match="equal length"):
        status.huber_predict(t, months[:-1], y, 30.0, 7)


def test_fit_agrees_with_a_library_huber_regression():
    sm = pytest.importorskip("statsmodels.api")
    t, months, y = seasonal_series(n=72)
    rng = np.random.default_rng(5)
    y = y + rng.standard_t(4, y.size) * 0.05  # heavy-tailed noise
    levels = np.unique(months)
    design = np.column_stack([t.astype(float)] + [(months == m).astype(float) for m in levels])
    fit = sm.RLM(y, design, M=sm.robust.norms.HuberT(t=c.HUBER_TUNING)).fit(maxiter=500, tol=1e-12)
    for t_new in (72.0, 75.0, 80.0):
        m_new = int(t_new) % 12 + 1
        library = float(np.concatenate([[t_new], (levels == m_new).astype(float)]) @ fit.params)
        ours = status.huber_predict(t, months, y, t_new, m_new, passes=200)
        assert ours == pytest.approx(library, abs=1e-5)
        # The default 20 passes are a truncation, close but not identical.
        assert status.huber_predict(t, months, y, t_new, m_new) == pytest.approx(library, abs=5e-3)


def test_constant_series_predicts_the_constant():
    t = np.arange(36.0)
    assert status.huber_predict(t, (t % 12 + 1).astype(int), np.full(36, 2.5), 36.0, 1) == pytest.approx(2.5)


# ---- anomalies -------------------------------------------------------------


def test_anomalies_are_zero_for_a_normal_growing_unit_and_show_a_drop():
    t, months, y = seasonal_series()
    y = y.copy()
    y[90] += math.log(0.7)  # 30% of the light gone in one window
    z = status.anomalies(y, months)
    assert np.isnan(z[:24]).all() and np.isfinite(z[24:]).all()  # 24 past windows needed
    assert np.abs(z[24:90]).max() < 1e-6  # growth and season are in the expectation
    assert math.exp(z[90]) == pytest.approx(0.7, abs=1e-3)


def test_anomalies_use_the_past_only():
    t, months, y = seasonal_series()
    rng = np.random.default_rng(7)
    y = y + rng.normal(0, 0.03, y.size)
    before = status.anomalies(y, months)
    changed = y.copy()
    changed[60:] += 5.0  # change window 60 and everything after it
    after = status.anomalies(changed, months)
    np.testing.assert_array_equal(after[:60], before[:60])


def test_lookback_is_exactly_the_previous_windows():
    t, months, y = seasonal_series(n=120)
    rng = np.random.default_rng(3)
    y = y + rng.normal(0, 0.03, y.size)
    base = status.anomalies(y, months)[100]
    # Window 100 with lookback 72 uses windows 28 to 99.
    outside = y.copy()
    outside[27] += 3.0
    assert status.anomalies(outside, months)[100] == base
    inside = y.copy()
    inside[28] += 0.05
    assert status.anomalies(inside, months)[100] != base


def test_gap_decides_which_windows_enter_the_fit():
    t, months, y = seasonal_series()
    rng = np.random.default_rng(11)
    y = y + rng.normal(0, 0.03, y.size)
    nudged = y.copy()
    nudged[88:90] -= 0.02  # small enough that the robust fit keeps them
    # With a gap of 2 the two windows before the target are not in its fit.
    assert status.anomalies(nudged, months, gap=2)[90] == status.anomalies(y, months, gap=2)[90]
    # Without the gap they are, and the result moves.
    assert status.anomalies(nudged, months)[90] != status.anomalies(y, months)[90]


def test_calendar_month_must_have_been_seen_twice():
    t, months, y = seasonal_series()
    y = y.copy()
    # Leave calendar month 7 with a single earlier window (t = 78) before t = 90.
    y[(months == 7) & (t < 78)] = np.nan
    assert (np.isfinite(y[18:90])).sum() >= 24
    assert np.isnan(status.anomalies(y, months)[90])
    assert np.isfinite(status.anomalies(y, months, min_same_month=1)[90])


def test_missing_windows_get_no_anomaly():
    t, months, y = seasonal_series()
    y = y.copy()
    y[50] = np.nan
    assert np.isnan(status.anomalies(y, months)[50])


def test_undetermined_fit_gives_no_anomaly_not_a_number_from_nowhere():
    # Thirteen windows, each calendar month seen once before the last.
    t = np.arange(13)
    z = status.anomalies(0.1 * t, (t % 12) + 1, min_windows=2, min_same_month=1)
    assert np.isnan(z).all()


def test_anomalies_refuse_bad_arguments():
    t, months, y = seasonal_series(n=40)
    with pytest.raises(ValueError, match="gap"):
        status.anomalies(y, months, gap=-1)  # would put a window in its own reference
    with pytest.raises(ValueError, match="exclude"):
        status.anomalies(y, months, exclude=np.zeros(39, dtype=bool))
    with pytest.raises(ValueError, match="months"):
        status.anomalies(y, months[:-1])
    with pytest.raises(ValueError, match="one-dimensional"):
        status.anomalies(np.zeros((4, 4)), np.ones((4, 4), dtype=int))
    with pytest.raises(ValueError, match="at least 1"):
        status.anomalies(y, months, min_same_month=0)


def test_excluded_windows_keep_a_lasting_drop_visible():
    t, months, y = seasonal_series(n=120)
    y = y.copy()
    y[84:] += math.log(0.7)  # a 30% step that stays
    learned = status.anomalies(y, months)
    held = np.zeros(120, dtype=bool)
    held[84:108] = True
    kept = status.anomalies(y, months, exclude=held)
    assert math.exp(kept[96]) == pytest.approx(0.7, abs=1e-3)
    assert math.exp(kept[107]) == pytest.approx(0.7, abs=1e-3)
    # Without the bar the reference has started to learn the new level.
    assert math.exp(learned[107]) > math.exp(kept[107]) + 0.02


def test_hold_starts_at_the_threshold_and_ends_after_the_period():
    t, months, y = seasonal_series(n=150)
    y = y.copy()
    y[84:] += math.log(0.7)  # a 30% step that stays
    threshold = np.full(150, -0.2)  # anything more than 18% below expected is held
    result = status.anomalies_held(y, months, threshold, hold_months=24)
    plain = status.anomalies(y, months)
    # Before the step nothing is held and the two agree exactly.
    assert not result.held[:84].any()
    np.testing.assert_array_equal(result.anomaly[:84], plain[:84])
    # The step is held from its first window, and stays fully visible for the hold period.
    assert result.held[84]
    for later in (90, 100, 108):
        assert math.exp(result.anomaly[later]) == pytest.approx(0.7, abs=2e-3)
    # Past-only: what happens from window 120 on cannot change window 100.
    y2 = y.copy()
    y2[120:] += 1.0
    np.testing.assert_array_equal(status.anomalies_held(y2, months, threshold).anomaly[:120], result.anomaly[:120])


def test_held_windows_return_to_the_fit_after_the_hold():
    t, months, y = seasonal_series(n=96)
    y = y.copy()
    y[60] += math.log(0.5)  # one bad window
    threshold = np.full(96, -0.2)
    short = status.anomalies_held(y, months, threshold, hold_months=6)
    assert short.held[60] and short.held.sum() == 1
    # A fit that bars window 60 for good, for comparison.
    barred = np.zeros(96, dtype=bool)
    barred[60] = True
    never = status.anomalies(y, months, exclude=barred)
    # Up to window 66 the held window is out of every fit: identical to barring it.
    np.testing.assert_allclose(short.anomaly[61:67], never[61:67], atol=1e-12)
    # No threshold, no hold.
    assert not status.anomalies_held(y, months, np.full(96, np.nan)).held.any()
    with pytest.raises(ValueError, match="hold_months"):
        status.anomalies_held(y, months, threshold, hold_months=0)
    with pytest.raises(ValueError, match="shape"):
        status.anomalies_held(y, months, threshold[:-1])


def test_running_scale_uses_earlier_windows_only():
    z = np.array([np.nan, 0.1, -0.1, 0.2, -0.2, 5.0, 0.0])
    s = status.running_scale(z, min_past=4)
    assert np.isnan(s[:5]).all()                    # fewer than four earlier anomalies
    assert s[5] == pytest.approx(status.robust_scale(z[1:5]))  # the 5.0 at window 5 is not in its own scale
    assert s[6] == pytest.approx(status.robust_scale(z[1:6]))
    skipped = status.running_scale(z, skip=np.array([0, 0, 0, 0, 0, 1, 0], dtype=bool), min_past=4)
    assert skipped[6] == pytest.approx(status.robust_scale(z[1:5]))  # the held window is left out


# ---- thresholds ------------------------------------------------------------


def test_tail_factor_by_hand():
    pool = np.arange(-1000.0, 1000.0) / 100.0  # 2,000 values, -10.00 to 9.99
    # 1% quantile, linear rule: position 0.01 * 1999 = 19.99, between the
    # values -9.81 and -9.80: -9.81 + 0.99 * 0.01 = -9.8001.
    assert status.tail_factor(pool, 0.01) == pytest.approx(-9.8001)
    assert status.tail_factor(pool, 0.01) < status.tail_factor(pool, 0.05) < 0


def test_tail_factor_refuses_thin_or_uncentred_pools():
    # At 5% the floor of 300 values decides (10 / 0.05 = 200 is less).
    with pytest.raises(status.PoolError, match="minimum"):
        status.tail_factor(np.linspace(-3, 3, c.TAIL_POOL_MIN - 1), 0.05)
    assert status.tail_factor(np.linspace(-3, 3, c.TAIL_POOL_MIN), 0.05) < 0
    # At 1% the quantile must rest on 10 values: 10 / 0.01 = 1,000 are needed.
    with pytest.raises(status.PoolError, match="minimum of 1000"):
        status.tail_factor(np.linspace(-3, 3, 999), 0.01)
    assert status.tail_factor(np.linspace(-3, 3, 1000), 0.01) < 0
    assert status.tail_factor(np.linspace(-3, 3, 400), 0.01, min_beyond=4) < 0
    with pytest.raises(status.PoolError, match="not negative"):
        status.tail_factor(np.linspace(1, 5, 1000), 0.01)
    # A bad rate is the caller's mistake, not a pool that will grow: a plain ValueError.
    with pytest.raises(ValueError, match="between") as caught:
        status.tail_factor(np.linspace(-3, 3, 1000), 0.6)
    assert not isinstance(caught.value, status.PoolError)
    # Infinities from a zero scale are ignored, not counted.
    with pytest.raises(status.PoolError, match="minimum"):
        status.tail_factor(np.full(1000, -np.inf), 0.01)


def test_detectable_drop_by_hand():
    # scale 0.10, factor -2.6, 80% power: normal point 0.8416
    # 1 - exp(-(2.6 + 0.8416) * 0.10) = 1 - exp(-0.34416) = 0.2912
    assert status.detectable_drop(0.10, -2.6) == pytest.approx(0.2912, abs=1e-4)
    # With a pooled point of 1.0: 1 - exp(-0.36) = 0.3023
    assert status.detectable_drop(0.10, -2.6, upper_point=1.0) == pytest.approx(0.3023, abs=1e-4)
    assert status.detectable_drop(0.20, -2.6) > status.detectable_drop(0.10, -2.6)


def test_detectable_drop_refuses_nonsense():
    with pytest.raises(ValueError, match="negative"):
        status.detectable_drop(0.1, 2.6)
    for power in (0.0, 1.0):
        with pytest.raises(ValueError, match="power"):
            status.detectable_drop(0.1, -2.6, power=power)
    for scale in (0.0, -1.0, float("nan"), float("inf")):
        assert math.isnan(status.detectable_drop(scale, -2.6))


def test_monitorable_needs_history_a_real_scale_and_a_useful_sensitivity():
    assert status.is_monitorable(0.10, -2.6, past_anomalies=40)          # sees a 29% drop
    assert status.is_monitorable(0.10, -2.6, past_anomalies=24)          # exactly enough history
    assert not status.is_monitorable(0.10, -2.6, past_anomalies=23)
    assert not status.is_monitorable(0.25, -2.6, past_anomalies=40)      # would need a 58% drop
    for scale in (0.0, float("nan")):                                    # no history worth the name
        assert not status.is_monitorable(scale, -2.6, past_anomalies=40)
    # The cap is inclusive.
    drop = status.detectable_drop(0.10, -2.6)
    assert status.is_monitorable(0.10, -2.6, 40, max_drop=drop)
    assert not status.is_monitorable(0.10, -2.6, 40, max_drop=drop - 1e-12)
