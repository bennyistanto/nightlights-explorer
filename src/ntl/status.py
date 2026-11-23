"""Is a unit dimmer or brighter than its own past says it should be?

The status statistic adopted on 2026-11-22 (``temp/status-design.md``),
written as pure functions on arrays. One unit, one view (monthly or
three-month) at a time; assembling units and files is the caller's job.

The chain:

1. :func:`log_index` : a unit's light in a window, on a log scale, over the
   cells that were usable, relative to what those same cells usually emit.
2. :func:`anomalies` : that value minus what a robust regression on time
   and calendar month, fitted on the unit's own previous years only,
   predicts for the window. Growth and season are in the prediction, so a
   normal window reads near zero.
3. :func:`robust_scale` and :func:`tail_factor` : the unit's own typical
   wobble, and how many wobbles a chosen false-alarm rate corresponds to.
4. :func:`detectable_drop` : the smallest drop a unit would catch, which
   decides whether it can be monitored at its level at all.

This module holds the single-unit pieces of the design: the index (part
1), the reference (part 2), the scale (part 4), the pooled factor (part
5), the smallest detectable drop (part 7) and the hold (part 8). The
pieces that need many units at once, namely the statistic relative to the
rest of the parent, the nights factor, the tiers and the fallback, are in
``ntl.monitor``.

What the statistic cannot do, measured in the backtest: it does not remove
movement shared by a whole region in a year, and a monthly value sees only
large changes: in the national run of 2026-11-22 the median smallest
detectable drop at the 1% rate was 31% for provinces, 34% for districts
and 38% for sub-districts.

Look-ahead: :func:`anomalies` uses only windows before ``t`` for window
``t``. The other functions use whatever they are given: the usual radiance
passed to :func:`log_index`, and the samples passed to :func:`robust_scale`
and :func:`tail_factor`, are the caller's to restrict to the past.
"""

from __future__ import annotations

from statistics import NormalDist
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl.zonal import unit_sums


class FitError(ValueError):
    """The past windows cannot determine a trend and a level for the target."""


class PoolError(ValueError):
    """A pool of standardised anomalies cannot give a tail factor yet."""


def _calendar_months(months: ArrayLike, shape: tuple[int, ...]) -> NDArray[np.int64]:
    """Calendar months as integers 1 to 12, refused otherwise (dates are a common mistake)."""
    array = np.asarray(months)
    if array.shape != shape:
        raise ValueError(f"months has shape {array.shape}, expected {shape}")
    if array.dtype.kind not in "iu":
        raise TypeError(f"months must be calendar months as integers 1 to 12, got dtype {array.dtype}")
    if array.size and (array.min() < 1 or array.max() > 12):
        raise ValueError("months must be calendar months, 1 to 12")
    return array.astype(np.int64)


def _median_abs(values: NDArray[np.float64]) -> float:
    """Median of the absolute values, by partial sort (same result as ``np.median``)."""
    a = np.abs(values)
    n = a.size
    half = n // 2
    if n % 2:
        return float(np.partition(a, half)[half])
    part = np.partition(a, [half - 1, half])
    return float(0.5 * (part[half - 1] + part[half]))


class UnitIndex(NamedTuple):
    """Result of :func:`log_index`. Arrays are aligned with ``codes``.

    Attributes
    ----------
    codes : ndarray of int64
        Unit codes, ascending, without 0.
    value : ndarray of float64
        ``ln(observed light / usual light of the same cells)``. NaN where
        the unit has no value this window: either too little of it was seen
        (``coverage`` under the minimum) or it was seen and emitted nothing
        (``dark`` is True).
    coverage : ndarray of float64
        Share of the unit's usual light carried by the usable cells, 0 to 1.
    dark : ndarray of bool
        True where enough of the unit was seen and every usable cell read
        zero. This is an observation, the opposite of "not observed": a
        logarithm cannot hold it, so it is flagged here and the caller must
        report it as its own state. Measured: 1,525 of 193,469
        sub-district windows in tile h29v09, mostly units with few lit cells.
    """

    codes: NDArray[np.int64]
    value: NDArray[np.float64]
    coverage: NDArray[np.float64]
    dark: NDArray[np.bool_]


def log_index(
    values: ArrayLike,
    unit_codes: ArrayLike,
    usual: ArrayLike,
    min_coverage: float = c.STATUS_MIN_COVERAGE,
) -> UnitIndex:
    """A unit's light in one window, on a log scale, like for like.

    Parameters
    ----------
    values : array_like of float
        Radiance per cell this window, nW cm-2 sr-1. NaN where the cell is
        not usable (not observed, too few nights): such cells are left out
        of both sums, never counted as dark.
    unit_codes : array_like of int, same shape
        Unit code per cell, 0 for no unit.
    usual : array_like of float, same shape
        Each cell's usual radiance (its long-term mean). It weights the
        coverage and forms the denominator. A cell whose usual radiance is
        NaN, infinite or negative is treated as not usable and weighs
        nothing.
    min_coverage : float
        Share of the unit's usual light that the usable cells must carry.

    Returns
    -------
    UnitIndex

    Raises
    ------
    ValueError
        If the shapes differ or a unit code is negative.
    TypeError
        If the unit codes are not integers.

    Notes
    -----
    Dividing by the usual light of the same cells makes windows comparable
    when different cells are visible: a month that sees only the bright
    centre of a town is not read as a bright month.
    """
    values = np.asarray(values, dtype=np.float64)
    usual = np.asarray(usual, dtype=np.float64)
    known = np.isfinite(usual) & (usual >= 0)
    weight = np.where(known, usual, 0.0)
    values = np.where(known, values, np.nan)
    seen = unit_sums(values, unit_codes, weights=weight)
    expected = unit_sums(np.where(np.isfinite(values), weight, np.nan), unit_codes, weights=weight)
    enough = (seen.coverage >= min_coverage) & (expected.total > 0)
    lit = enough & (seen.total > 0)
    value = np.full(seen.codes.size, np.nan)
    value[lit] = np.log(seen.total[lit] / expected.total[lit])
    return UnitIndex(codes=seen.codes, value=value, coverage=seen.coverage, dark=enough & (seen.total <= 0))


def robust_scale(values: ArrayLike) -> float:
    """Typical size of the deviations in a sample: 1.4826 x MAD.

    Parameters
    ----------
    values : array_like of float
        NaN and infinite entries are ignored.

    Returns
    -------
    float
        Median absolute deviation from the median, scaled to estimate a
        standard deviation for normal data. NaN for an empty sample; 0.0 for
        a single value or a constant sample, which callers must not read as
        "no noise" (:func:`is_monitorable` refuses a scale of zero).
    """
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    return float(c.MAD_TO_SD * np.median(np.abs(v - np.median(v))))


def huber_predict(
    time: ArrayLike,
    month: ArrayLike,
    y: ArrayLike,
    time_new: float,
    month_new: int,
    tuning: float = c.HUBER_TUNING,
    passes: int = c.HUBER_PASSES,
) -> float:
    """Fit ``y ~ slope * time + level(calendar month)`` robustly and predict.

    Parameters
    ----------
    time : array_like of float
        Time of each past window, in any unit with equal steps (months).
    month : array_like of int
        Calendar month (1 to 12) of each past window.
    y : array_like of float
        The unit's log index in those windows. Finite values only.
    time_new, month_new : float, int
        The window to predict. ``month_new`` must occur in ``month``.
    tuning : float
        Residuals beyond ``tuning`` scales are down-weighted (Huber). Positive.
    passes : int
        Reweighting passes, at least 1. A fixed number, not a convergence
        test: see ``conventions.HUBER_PASSES``.

    Returns
    -------
    float
        Predicted ``y`` at the new window.

    Raises
    ------
    ValueError
        If the inputs differ in length, ``y`` holds a non-finite value,
        ``tuning`` is not positive or ``passes`` is under 1.
    FitError
        If ``month_new`` has no past window, or no calendar month holds two
        windows at different times: the slope cannot then be told apart
        from the month levels.

    Notes
    -----
    Iteratively reweighted least squares. One slope over the fit period
    carries the growth; one level per calendar month carries the season.
    With one level per month the weighted fit has a closed form: within
    each calendar month take the weighted means of time and of ``y``; the
    slope is ``sum(w dt dy) / sum(w dt^2)`` over the deviations from those
    means; the prediction is the target month's mean ``y`` plus the slope
    times the distance from that month's mean time.

    Weights are 1 inside ``tuning`` residual scales and
    ``tuning * scale / |residual|`` outside. The scale is re-estimated each
    pass as 1.4826 x the median absolute residual (about zero, the usual
    convention; with it this fit agreed with a library Huber regression to
    1e-6 in the method review). A past outage or a single bad month
    therefore pulls the prediction little.
    """
    time = np.asarray(time, dtype=np.float64)
    month = np.asarray(month)
    y = np.asarray(y, dtype=np.float64)
    if not (time.shape == month.shape == y.shape and time.ndim == 1):
        raise ValueError("time, month and y must be one-dimensional and of equal length")
    if not np.all(np.isfinite(y)):
        raise ValueError("y must be finite: drop missing windows before fitting")
    if not tuning > 0:
        raise ValueError("tuning must be positive")
    if passes < 1:
        raise ValueError("passes must be at least 1")
    months, group = np.unique(month, return_inverse=True)
    target = np.nonzero(months == month_new)[0]
    if target.size == 0:
        raise FitError(f"calendar month {month_new} has no past window in the fit")

    weights = np.ones(y.size)
    for _ in range(passes):
        weight_sum = np.bincount(group, weights=weights)
        mean_time = np.bincount(group, weights=weights * time) / weight_sum
        mean_y = np.bincount(group, weights=weights * y) / weight_sum
        dt = time - mean_time[group]
        dy = y - mean_y[group]
        spread = float(np.sum(weights * dt * dt))
        if not spread > 0:
            raise FitError("no calendar month holds two windows at different times")
        slope = float(np.sum(weights * dt * dy)) / spread
        residual = dy - slope * dt
        scale = c.MAD_TO_SD * _median_abs(residual)
        if not scale > 0:
            break
        ratio = np.abs(residual) / (tuning * scale)
        weights = 1.0 / np.maximum(ratio, 1.0)
    j = int(target[0])
    return float(mean_y[j] + slope * (time_new - mean_time[j]))


def anomalies(
    index: ArrayLike,
    months: ArrayLike,
    lookback: int = c.STATUS_LOOKBACK_MONTHS,
    min_windows: int = c.STATUS_MIN_FIT_WINDOWS,
    min_same_month: int = c.STATUS_MIN_SAME_MONTH,
    exclude: ArrayLike | None = None,
    gap: int = 0,
) -> NDArray[np.float64]:
    """Observed minus expected, window by window, from the past only.

    Parameters
    ----------
    index : array_like of float, shape ``(T,)``
        One unit's log index for consecutive calendar months (from
        :func:`log_index`), NaN where it has none.
    months : array_like of int, shape ``(T,)``
        Calendar month (1 to 12) of each window.
    lookback : int
        Windows before ``t`` that may enter the fit: ``t - lookback`` to
        ``t - 1 - gap``. At least 1.
    min_windows, min_same_month : int
        Observed windows needed in that span, and among them in the target's
        calendar month. ``min_same_month`` at least 1.
    exclude : array_like of bool, shape ``(T,)``, optional
        Windows barred from every fit in this call. They still receive an
        anomaly themselves. This is a fixed bar: it cannot express the
        design's hold, which readmits a window after 24 months.
    gap : int
        Windows immediately before ``t`` left out of its fit, 0 or more.
        Use 2 for the three-month view, whose two preceding windows share
        months with the target; the fit then spans 70 windows, not 72.

    Returns
    -------
    ndarray of float64, shape ``(T,)``
        ``index[t] - prediction``; NaN where the window has no value, the
        past is too thin, or the past cannot determine a trend. ``exp`` of
        it is the ratio of observed to expected light.

    Raises
    ------
    ValueError
        If ``index`` is not one-dimensional, ``months`` or ``exclude`` has a
        different shape, ``gap`` is negative (a negative gap would let a
        window into its own reference), ``lookback`` is under 1 or
        ``min_same_month`` is under 1.
    """
    index = np.asarray(index, dtype=np.float64)
    if index.ndim != 1:
        raise ValueError("index must be one-dimensional: one unit at a time")
    months = _calendar_months(months, index.shape)
    if not isinstance(gap, (int, np.integer)) or gap < 0:
        raise ValueError("gap must be a whole number, not negative")
    if lookback < 1 or min_same_month < 1:
        raise ValueError("lookback and min_same_month must be at least 1")
    if exclude is None:
        barred = np.zeros(index.size, dtype=bool)
    else:
        barred = np.asarray(exclude, dtype=bool)
        if barred.shape != index.shape:
            raise ValueError(f"exclude has shape {barred.shape}, index {index.shape}")

    out = np.full(index.size, np.nan)
    for t in range(index.size):
        out[t] = _anomaly_at(index, months, t, barred, lookback, min_windows, min_same_month, gap)
    return out


def _anomaly_at(
    index: NDArray[np.float64],
    months: NDArray,
    t: int,
    barred: NDArray[np.bool_],
    lookback: int,
    min_windows: int,
    min_same_month: int,
    gap: int,
) -> float:
    """Anomaly of window ``t`` from windows ``t - lookback`` to ``t - 1 - gap`` not barred; NaN if none."""
    if not np.isfinite(index[t]):
        return float("nan")
    past = np.arange(max(0, t - lookback), max(0, t - gap))
    past = past[np.isfinite(index[past]) & ~barred[past]]
    if past.size < min_windows or (months[past] == months[t]).sum() < min_same_month:
        return float("nan")
    try:
        return float(index[t] - huber_predict(past.astype(np.float64), months[past], index[past], float(t), int(months[t])))
    except FitError:
        return float("nan")


class Held(NamedTuple):
    """Result of :func:`anomalies_held`.

    Attributes
    ----------
    anomaly : ndarray of float64, shape ``(T,)``
        As :func:`anomalies`, but each fit leaves out the windows on hold.
    held : ndarray of bool, shape ``(T,)``
        True where the window fell below its threshold and was put on hold.
    """

    anomaly: NDArray[np.float64]
    held: NDArray[np.bool_]


def anomalies_held(
    index: ArrayLike,
    months: ArrayLike,
    threshold: ArrayLike,
    hold_months: int = c.STATUS_HOLD_MONTHS,
    lookback: int = c.STATUS_LOOKBACK_MONTHS,
    min_windows: int = c.STATUS_MIN_FIT_WINDOWS,
    min_same_month: int = c.STATUS_MIN_SAME_MONTH,
    gap: int = 0,
) -> Held:
    """Anomalies with the hold: a window that drops below its threshold is
    kept out of later fits for a while, so a lasting drop stays visible.

    Parameters
    ----------
    index, months : array_like, shape ``(T,)``
        As :func:`anomalies`.
    threshold : array_like of float, shape ``(T,)``
        The anomaly below which window ``t`` is put on hold (a negative
        number: the unit's factor times its scale at ``t``). NaN means no
        threshold yet, and the window is never held.
    hold_months : int
        A held window is barred from the fit of every later window up to
        and including ``t + hold_months``; after that it is readmitted. At
        least 1.
    lookback, min_windows, min_same_month, gap
        As :func:`anomalies`.

    Returns
    -------
    Held

    Raises
    ------
    ValueError
        As :func:`anomalies`, or if ``threshold`` has a different shape or
        ``hold_months`` is under 1.

    Notes
    -----
    Sequential and past-only: whether window ``t`` is held depends on its
    own anomaly and threshold, and affects later windows only. A window
    held at ``t`` is barred from the fits of windows ``t + 1`` to
    ``t + hold_months`` and is back in the fit of ``t + hold_months + 1``
    (checked by the method review on real series).

    How much it helps depends on how many windows of a lasting drop fall
    below the threshold, because only those are held. Measured with a 30%
    step injected into real district series (adm2), the alarm threshold as
    trigger, share of the step still visible (median):

    =========================  ====  ====  ====
    months after the step        11    17    23
    =========================  ====  ====  ====
    three-month view, hold      96%   83%   35%
    three-month view, no hold   70%   27%    8%
    monthly view, hold          70%   30%   13%
    monthly view, no hold       57%   18%    5%
    =========================  ====  ====  ====

    In the monthly view fewer than half of the first step windows cross
    the alarm threshold, so few are held. Where 12 or more windows were
    held the step stayed at 98% or more for 24 months. A lower trigger
    would hold more; that is a design choice not made here. After the hold
    expires the reference adopts the new level and reads about 14% above
    the old expectation at 36 months.
    """
    index = np.asarray(index, dtype=np.float64)
    threshold = np.asarray(threshold, dtype=np.float64)
    if index.ndim != 1:
        raise ValueError("index must be one-dimensional: one unit at a time")
    months = _calendar_months(months, index.shape)
    if threshold.shape != index.shape:
        raise ValueError("threshold must have the shape of index")
    if not isinstance(gap, (int, np.integer)) or gap < 0:
        raise ValueError("gap must be a whole number, not negative")
    if lookback < 1 or min_same_month < 1 or hold_months < 1:
        raise ValueError("lookback, min_same_month and hold_months must be at least 1")
    anomaly = np.full(index.size, np.nan)
    held = np.zeros(index.size, dtype=bool)
    release = np.full(index.size, -1)  # last window whose fit a held window is barred from
    for t in range(index.size):
        barred = held & (release >= t)
        anomaly[t] = _anomaly_at(index, months, t, barred, lookback, min_windows, min_same_month, gap)
        if np.isfinite(anomaly[t]) and np.isfinite(threshold[t]) and anomaly[t] < threshold[t]:
            held[t] = True
            release[t] = t + hold_months
    return Held(anomaly=anomaly, held=held)


def running_scale(anomaly: ArrayLike, skip: ArrayLike | None = None, min_past: int = c.STATUS_MIN_PAST_ANOMALIES) -> NDArray[np.float64]:
    """A unit's own scale at each window, from its earlier anomalies only.

    Parameters
    ----------
    anomaly : array_like of float, shape ``(T,)``
        One unit's anomalies, NaN where none.
    skip : array_like of bool, shape ``(T,)``, optional
        Windows left out of the scale (those on hold).
    min_past : int
        Earlier anomalies needed.

    Returns
    -------
    ndarray of float64, shape ``(T,)``
        ``robust_scale`` of the anomalies before ``t``; NaN until
        ``min_past`` of them exist. The anomaly at ``t`` itself never
        enters its own scale.

    Raises
    ------
    ValueError
        If ``anomaly`` is not one-dimensional or ``skip`` has another shape.
    """
    anomaly = np.asarray(anomaly, dtype=np.float64)
    if anomaly.ndim != 1:
        raise ValueError("anomaly must be one-dimensional: one unit at a time")
    use = np.isfinite(anomaly)
    if skip is not None:
        skip = np.asarray(skip, dtype=bool)
        if skip.shape != anomaly.shape:
            raise ValueError(f"skip has shape {skip.shape}, anomaly {anomaly.shape}")
        use &= ~skip
    out = np.full(anomaly.size, np.nan)
    for t in range(anomaly.size):
        earlier = anomaly[:t][use[:t]]
        if earlier.size >= min_past:
            out[t] = robust_scale(earlier)
    return out


def tail_factor(
    standardised: ArrayLike,
    rate: float,
    min_pool: int = c.TAIL_POOL_MIN,
    min_beyond: int = c.TAIL_POOL_BEYOND,
) -> float:
    """How many wobbles below normal a false-alarm rate corresponds to.

    Parameters
    ----------
    standardised : array_like of float
        Past anomalies divided by their unit's own scale, pooled over many
        units of one admin level. NaN and infinite entries are ignored (a
        unit with a scale of zero produces infinities; leave such units out).
    rate : float
        Target share of unit-windows flagged with no event, for example
        ``conventions.ALARM_RATE``.
    min_pool : int
        Values the pool must hold.
    min_beyond : int
        Values the pool must be expected to hold beyond the quantile: the
        pool needs ``min_beyond / rate`` values (1,000 for a 1% rate with
        the default of 10). A quantile resting on four or five values is
        too unstable to use as a threshold.

    Returns
    -------
    float
        The ``rate`` quantile of the pool: a negative number. A unit is
        flagged when its anomaly is below this times its own scale.

    Raises
    ------
    ValueError
        If the rate is not strictly between 0 and 0.5.
    PoolError
        (a ``ValueError``) If the pool is smaller than ``min_pool`` or than
        ``min_beyond / rate``, or the quantile is not negative (the pool is
        not centred near zero, so it is not a pool of anomalies).

    Notes
    -----
    The pooled quantile is used instead of a normal one because the
    anomalies have heavier tails. In the backtest the own-history monthly
    factor at 1% ran from -2.3 to -2.9 by tile and level, where a normal
    distribution gives -2.33, and a normal factor realised about 1.6% false
    alarms at a 1% target. With a pool of a few hundred the 1% quantile
    rests on a handful of values and is itself uncertain.
    """
    if not 0.0 < rate < 0.5:
        raise ValueError("rate must be between 0 and 0.5")
    pool = np.asarray(standardised, dtype=np.float64)
    pool = pool[np.isfinite(pool)]
    needed = max(min_pool, int(np.ceil(min_beyond / rate)))
    if pool.size < needed:
        raise PoolError(f"pool of {pool.size} values is under the minimum of {needed} for a rate of {rate}")
    factor = float(np.quantile(pool, rate))
    if not factor < 0:
        raise PoolError(f"the {rate} quantile of the pool is {factor}, not negative")
    return factor


def detectable_drop(
    scale: float,
    factor: float,
    power: float = c.DETECTION_POWER,
    upper_point: float | None = None,
) -> float:
    """Smallest one-window drop a unit would catch with the given power.

    Parameters
    ----------
    scale : float
        The unit's own scale (:func:`robust_scale` of its past anomalies).
    factor : float
        Its threshold in scales (:func:`tail_factor`). Must be negative.
    power : float
        Probability of catching the drop, strictly between 0 and 1.
    upper_point : float, optional
        The ``power`` quantile of the pooled standardised anomalies. Default:
        the normal one (0.8416 for 80%). The backtest that produced the
        counts in ``temp/status-design.md`` used the pooled point, which ran
        from 0.82 to 1.02; with the normal point slightly more units
        qualify (h29v09 sub-districts: 911 against 888).

    Returns
    -------
    float
        Share of light, 0 to 1: ``1 - exp(-(|factor| + upper_point) * scale)``.
        A unit with 0.38 catches a 38% drop with the stated power; smaller
        drops less often. NaN if ``scale`` is not a positive finite number.

    Raises
    ------
    ValueError
        If ``factor`` is not negative or ``power`` is not between 0 and 1.
    """
    if not factor < 0:
        raise ValueError("factor must be negative")
    if not 0.0 < power < 1.0:
        raise ValueError("power must be between 0 and 1")
    if not (np.isfinite(scale) and scale > 0):
        return float("nan")
    point = NormalDist().inv_cdf(power) if upper_point is None else float(upper_point)
    return float(1.0 - np.exp(-(-factor + point) * scale))


def is_monitorable(
    scale: float,
    factor: float,
    past_anomalies: int,
    max_drop: float = c.MAX_DETECTABLE_DROP,
    min_past: int = c.STATUS_MIN_PAST_ANOMALIES,
    power: float = c.DETECTION_POWER,
    upper_point: float | None = None,
) -> bool:
    """Whether a unit can carry a status at its own admin level.

    Parameters
    ----------
    scale : float
        The unit's own scale. A scale that is zero, negative or not finite
        gives False: it means too little or degenerate history, not a
        perfectly steady unit.
    factor : float
        Threshold in scales at the alarm rate; negative.
    past_anomalies : int
        Earlier anomalies behind ``scale``.
    max_drop, min_past, power, upper_point
        As in :func:`detectable_drop` and ``conventions``.

    Returns
    -------
    bool
        True when the unit has at least ``min_past`` earlier anomalies and
        its :func:`detectable_drop` is at most ``max_drop`` (inclusive).
        Otherwise the caller tests the parent unit the same way, and failing
        that marks the unit as not monitorable. A parent is not always
        quieter than its children (measured in tile h30v09).

    Raises
    ------
    ValueError
        As :func:`detectable_drop`.
    """
    drop = detectable_drop(scale, factor, power=power, upper_point=upper_point)
    return bool(past_anomalies >= min_past and np.isfinite(drop) and drop <= max_drop)
