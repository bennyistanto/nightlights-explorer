"""Status of every unit of one admin level, window by window.

This module ties ``ntl.status`` together for all units of a level, adding
the parts of the adopted design (``temp/status-design.md``) that need more
than one unit at a time:

- the statistic relative to the rest of the parent unit (part 3);
- the nights factor on each unit's scale (part 4);
- thresholds pooled over the level, re-read each January from earlier
  years only (part 5);
- the two tiers and "regional dimming" (part 6);
- the fallback level for reporting (part 7);
- the hold after an alarm (part 8).

Everything for window ``t`` uses windows before ``t``, with one stated
exception: the cell weights and the domain come from the caller
(``ntl.stack``), who decides whether they are fixed from the past.

Choices made here that the design left open, all marked as such:

- **Hold trigger**: a window is held when its own-history anomaly is below
  the alarm threshold of the first pass. The backtest triggered at four
  fit-scales instead.
- **Two passes**: scales, nights factors and thresholds are estimated on a
  first pass without the hold, then the anomalies are recomputed with it.
  The thresholds are not re-estimated after the hold, and the final scale
  leaves out the windows on hold. The targets (5% and 1%) are therefore
  met on the first pass only: the final scale is smaller, so the rates
  after the hold run above target. The measured rates of each national run
  are in ``temp/status-design.md``.
- **"Seen and dark"** is returned as its own status and given no tier. For
  the rest of a parent it is not kept: a rest that is seen and dark has no
  log index, so the unit is judged on its own history alone that window.
- **Nights** of a unit-window is the mean number of nights over its usable
  cells.
- The parent-relative statistic gets no nights factor and no hold.
- **Too few cells**: a unit under ``MIN_UNIT_CELLS`` domain cells still gets
  a status but is never monitorable at its own level and does not vote in
  :func:`children_agreement`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import NormalDist
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl import status, zonal
from ntl.stack import TileStack, load_folder

log = logging.getLogger("ntl.monitor")

#: Differences of sums leave rounding dust where a unit is alone in its
#: parent; anything under this share of the parent's weight counts as none.
_ROUNDING_DUST = 1e-9
#: A child code divided by this is its parent's code, at both steps
#: (sub-district to district, district to province).
_CHILD_TO_PARENT = c.ADMIN_DIVISOR["district"]


class LevelSeries(NamedTuple):
    """Per-unit series built from cells. ``T`` windows by ``U`` units.

    Attributes
    ----------
    codes : ndarray of int64, shape ``(U,)``
        Unit codes, ascending, without 0.
    index : ndarray of float64, shape ``(T, U)``
        Log index as ``status.log_index``; NaN where the unit has no value.
    coverage : ndarray of float64, shape ``(T, U)``
        Share of the unit's usual light carried by the usable cells.
    dark : ndarray of bool, shape ``(T, U)``
        Seen (coverage at or above the minimum) with every usable cell at zero.
    nights : ndarray of float64, shape ``(T, U)``
        Mean nights over the unit's usable cells that have a nights count;
        NaN where none.
    rest : ndarray of float64, shape ``(T, U)``
        Log index of the rest of the unit's parent (the parent without this
        unit), or all NaN if no parent codes were given. NaN where the rest
        has no usable cell, too little coverage, is seen and dark, the unit
        is alone, or the unit's parent code is 0.
    cells : ndarray of int64, shape ``(U,)``
        Domain cells of each unit (those with a usable weight).
    """

    codes: NDArray[np.int64]
    index: NDArray[np.float64]
    coverage: NDArray[np.float64]
    dark: NDArray[np.bool_]
    nights: NDArray[np.float64]
    rest: NDArray[np.float64]
    cells: NDArray[np.int64]


def level_series(
    values: ArrayLike,
    nights: ArrayLike,
    usual: ArrayLike,
    unit_codes: ArrayLike,
    parent_codes: ArrayLike | None = None,
    min_coverage: float = c.STATUS_MIN_COVERAGE,
) -> LevelSeries:
    """Sum cells into units for every window, and into "the rest of the parent".

    Parameters
    ----------
    values : array_like of float, shape ``(T, N)``
        Usable radiance per window and cell, NaN where not usable
        (``TileStack.usable()`` or a thresholded three-month composite).
    nights : array_like, shape ``(T, N)``
        Nights behind each value.
    usual : array_like of float, shape ``(N,)``
        Each cell's usual radiance; non-finite or negative means the cell
        is left out.
    unit_codes : array_like of int, shape ``(N,)``
        Unit code per cell at this level; 0 for cells held by a level above.
    parent_codes : array_like of int, shape ``(N,)``, optional
        Code of each cell's unit one level up. Cells of one unit must share
        one parent. Units whose parent code is 0 get no rest.
    min_coverage : float
        As ``status.log_index``.

    Returns
    -------
    LevelSeries

    Raises
    ------
    ValueError
        If shapes disagree, a code is negative, or a unit's cells have more
        than one parent.
    TypeError
        If unit or parent codes are not integers (floats are refused).

    Notes
    -----
    Gives the same index, coverage and dark flag as calling
    ``status.log_index`` window by window (tested), but groups the cells
    once. One difference: ``codes`` lists every unit with a domain cell,
    while ``status.log_index`` lists the units present in that one call.
    The rest of a parent is formed by subtracting the unit's sums
    from the parent's, so it uses exactly the same cells and weights.
    """
    values = np.asarray(values, dtype=np.float64)
    nights = np.asarray(nights, dtype=np.float64)
    usual = np.asarray(usual, dtype=np.float64)
    unit_codes = zonal.integer_codes(unit_codes, "unit codes")
    if values.ndim != 2 or nights.shape != values.shape:
        raise ValueError("values and nights must both be (windows, cells)")
    if usual.shape != (values.shape[1],) or unit_codes.shape != usual.shape:
        raise ValueError("usual and unit_codes must have one entry per cell")

    keep = (unit_codes > c.NO_UNIT) & np.isfinite(usual) & (usual >= 0)
    codes, group = np.unique(unit_codes[keep], return_inverse=True)
    n_units = codes.size
    weight = usual[keep]
    weight_all = np.bincount(group, weights=weight, minlength=n_units)
    v = values[:, keep]
    nt = nights[:, keep]
    T = values.shape[0]

    total = np.zeros((T, n_units))
    weight_used = np.zeros((T, n_units))
    night_sum = np.zeros((T, n_units))
    cell_count = np.zeros((T, n_units))
    for t in range(T):
        used = np.isfinite(v[t])
        total[t] = np.bincount(group, weights=np.where(used, v[t], 0.0), minlength=n_units)
        weight_used[t] = np.bincount(group, weights=np.where(used, weight, 0.0), minlength=n_units)
        counted = used & np.isfinite(nt[t])  # a value without a nights count stays out of the mean
        night_sum[t] = np.bincount(group, weights=np.where(counted, nt[t], 0.0), minlength=n_units)
        cell_count[t] = np.bincount(group, weights=counted.astype(np.float64), minlength=n_units)

    def to_index(total_, used_, all_):
        coverage = np.where(all_ > 0, used_ / np.where(all_ > 0, all_, 1.0), 0.0)
        enough = (coverage >= min_coverage) & (used_ > 0)
        lit = enough & (total_ > 0)
        out = np.full(total_.shape, np.nan)
        out[lit] = np.log(total_[lit] / used_[lit])
        return out, coverage, enough & (total_ <= 0)

    index, coverage, dark = to_index(total, weight_used, weight_all[None, :])
    mean_nights = np.where(cell_count > 0, night_sum / np.maximum(cell_count, 1), np.nan)

    rest = np.full((T, n_units), np.nan)
    if parent_codes is not None:
        parent_codes = zonal.integer_codes(parent_codes, "parent codes")
        if parent_codes.shape != unit_codes.shape:
            raise ValueError("parent_codes must have one entry per cell")
        parents_of_cells = parent_codes[keep]
        parent_of_unit = np.zeros(n_units, dtype=np.int64)
        parent_of_unit[group] = parents_of_cells
        if not np.array_equal(parent_of_unit[group], parents_of_cells):
            raise ValueError("cells of one unit have different parents")
        _, parent_group = np.unique(parent_of_unit, return_inverse=True)
        n_parents = int(parent_group.max()) + 1 if n_units else 0

        def per_parent(per_unit):
            if per_unit.ndim == 1:
                return np.bincount(parent_group, weights=per_unit, minlength=n_parents)[parent_group]
            return np.stack([np.bincount(parent_group, weights=row, minlength=n_parents)[parent_group] for row in per_unit])

        rest_total = per_parent(total) - total
        rest_used = per_parent(weight_used) - weight_used
        rest_all = (per_parent(weight_all) - weight_all)[None, :]
        # Differences of sums can leave rounding dust where the unit is alone.
        tiny = _ROUNDING_DUST * np.maximum(per_parent(weight_all), 1.0)[None, :]
        rest_used = np.where(rest_used > tiny, rest_used, 0.0)
        rest_total = np.where(rest_used > 0, np.maximum(rest_total, 0.0), 0.0)
        rest_all = np.where(rest_all > tiny, rest_all, 0.0)
        # The rest's own "seen and dark" flag is dropped: see the module docstring.
        rest, _, _ = to_index(rest_total, rest_used, np.broadcast_to(rest_all, rest_used.shape))
        rest[:, parent_of_unit == c.NO_UNIT] = np.nan  # no parent, so no "rest of the parent"

    cells = np.bincount(group, minlength=n_units).astype(np.int64)
    return LevelSeries(codes=codes, index=index, coverage=coverage, dark=dark, nights=mean_nights, rest=rest, cells=cells)


def night_class(nights: ArrayLike, edges: tuple[int, ...]) -> NDArray[np.int64]:
    """Class of each nights value: 0 below the first edge, then 1, 2, ...; -1 for NaN."""
    nights = np.asarray(nights, dtype=np.float64)
    out = np.searchsorted(np.asarray(edges, dtype=np.float64), nights, side="right").astype(np.int64)
    out[~np.isfinite(nights)] = -1
    return out


def _pools(years: NDArray, whole_record: bool) -> list[tuple[NDArray[np.bool_], NDArray[np.bool_]]]:
    """Pairs (windows that supply the pool, windows that receive the result)."""
    if whole_record:
        everything = np.ones(years.shape, dtype=bool)
        return [(everything, everything)]
    return [(years < year, years == year) for year in np.unique(years)]


def yearly_class_factors(
    standardised: ArrayLike,
    classes: ArrayLike,
    years: ArrayLike,
    n_classes: int,
    min_pool: int = c.TAIL_POOL_MIN,
    whole_record: bool = False,
) -> NDArray[np.float64]:
    """How much noisier each nights class is, re-read each January from earlier years.

    Parameters
    ----------
    standardised : array_like of float, shape ``(T, U)``
        Anomalies divided by their unit's own scale.
    classes : array_like of int, shape ``(T, U)``
        Nights class of each unit-window (:func:`night_class`).
    years : array_like of int, shape ``(T,)``
        Calendar year of each window.
    n_classes : int
        Number of classes.
    min_pool : int
        Values a class needs, in the earlier years, before it gets its own
        factor.
    whole_record : bool
        Read one set of factors from every window and apply it to every
        window. Look-ahead: for describing history, not for monitoring.

    Returns
    -------
    ndarray of float64, shape ``(T, n_classes)``
        For each window, the robust scale of the standardised anomalies of
        each class in the years before the window's year, divided by the
        robust scale of all classes together over the same years. 1.0 where
        a class has too few values. A window's scale is multiplied by the
        factor of its class.
    """
    standardised = np.asarray(standardised, dtype=np.float64)
    classes = np.asarray(classes)
    years = np.asarray(years)
    out = np.ones((standardised.shape[0], n_classes))
    for source, target in _pools(years, whole_record):
        pool = standardised[source]
        ok = np.isfinite(pool)
        if ok.sum() < min_pool:
            continue
        overall = status.robust_scale(pool[ok])
        if not overall > 0:
            continue
        for k in range(n_classes):
            members = pool[ok & (classes[source] == k)]
            if members.size >= min_pool:
                scale = status.robust_scale(members)
                if scale > 0:
                    out[target, k] = scale / overall
    return out


def yearly_tail_factor(
    standardised: ArrayLike,
    years: ArrayLike,
    rate: float,
    min_pool: int = c.TAIL_POOL_MIN,
    whole_record: bool = False,
) -> NDArray[np.float64]:
    """The pooled tail factor for each window, read from earlier years only.

    Parameters
    ----------
    standardised : array_like of float, shape ``(T, U)``
        Anomalies divided by their (nights-adjusted) scale, all units of a level.
    years : array_like of int, shape ``(T,)``
        Calendar year of each window.
    rate : float
        False-alarm rate.
    min_pool : int
        As ``status.tail_factor``.
    whole_record : bool
        Read one factor from every window and apply it to every window.
        Look-ahead: for describing history, not for monitoring.

    Returns
    -------
    ndarray of float64, shape ``(T,)``
        ``status.tail_factor`` of the values in years before the window's
        year; NaN while that pool cannot give one (``status.PoolError``:
        too small for the rate, or not centred). The factor changes once a
        year, each January.

    Raises
    ------
    ValueError
        If ``rate`` is not a valid rate (from ``status.tail_factor``).
    """
    standardised = np.asarray(standardised, dtype=np.float64)
    years = np.asarray(years)
    out = np.full(standardised.shape[0], np.nan)
    for source, target in _pools(years, whole_record):
        try:
            out[target] = status.tail_factor(standardised[source], rate, min_pool)
        except status.PoolError:
            continue
    return out


class LevelStatus(NamedTuple):
    """Result of :func:`run_level`. ``T`` windows by ``U`` units.

    Attributes
    ----------
    codes : ndarray of int64, shape ``(U,)``
    state : ndarray of uint8, shape ``(T, U)``
        ``conventions.STATUS_*``.
    anomaly : ndarray of float64, shape ``(T, U)``
        Own-history anomaly with the hold applied; ``exp`` of it is
        observed over expected light.
    relative : ndarray of float64, shape ``(T, U)``
        Anomaly minus that of the rest of the parent; NaN where there is none.
    scale, relative_scale : ndarray of float64, shape ``(T, U)``
        The unit's own noise at each window (nights factor included in
        ``scale``), from earlier windows only.
    watch, alarm : ndarray of float64, shape ``(T,)``
        Pooled factors for the own-history statistic at the two rates.
    relative_watch, relative_alarm : ndarray of float64, shape ``(T,)``
        The same for the parent-relative statistic.
    held : ndarray of bool, shape ``(T, U)``
        Windows put on hold.
    detectable : ndarray of float64, shape ``(T, U)``
        Smallest drop, as a fraction of expected light (0 to 1), that the
        unit would catch at the alarm rate with probability
        ``DETECTION_POWER``, at each window; NaN without an alarm factor.
    monitorable : ndarray of bool, shape ``(T, U)``
        ``detectable`` at most ``MAX_DETECTABLE_DROP`` and the unit has at
        least ``MIN_UNIT_CELLS`` domain cells.
    joint : ndarray of bool, shape ``(T, U)``
        True where the parent-relative test was applied to the status (a
        relative anomaly, its scale and its thresholds all exist, and the
        run has tiers). Where False, a WATCH or ALARM rests on the unit's
        own history alone. Always False with ``tiers=False``, where the
        relative test is not used.
    series : LevelSeries
        The inputs (index, coverage, dark, nights, rest, cells).
    """

    codes: NDArray[np.int64]
    state: NDArray[np.uint8]
    anomaly: NDArray[np.float64]
    relative: NDArray[np.float64]
    scale: NDArray[np.float64]
    relative_scale: NDArray[np.float64]
    watch: NDArray[np.float64]
    alarm: NDArray[np.float64]
    relative_watch: NDArray[np.float64]
    relative_alarm: NDArray[np.float64]
    held: NDArray[np.bool_]
    detectable: NDArray[np.float64]
    monitorable: NDArray[np.bool_]
    joint: NDArray[np.bool_]
    series: LevelSeries


def run_level(
    series: LevelSeries,
    months: ArrayLike,
    years: ArrayLike,
    night_edges: tuple[int, ...] = c.NIGHT_CLASS_EDGES_MONTHLY,
    gap: int = 0,
    watch_rate: float = c.WATCH_RATE,
    alarm_rate: float = c.ALARM_RATE,
    retrospective: bool = False,
    tiers: bool = True,
) -> LevelStatus:
    """Status of every unit of a level in every window.

    Parameters
    ----------
    series : LevelSeries
        From :func:`level_series`. If its ``rest`` is all NaN (no parent,
        as for provinces) the status rests on the unit's own history alone.
    months, years : array_like of int, shape ``(T,)``
        Calendar month (1 to 12) and year of each window; consecutive
        months (``TileStack.calendar_month`` and ``TileStack.year``). Dates
        are refused.
    night_edges : tuple of int
        Class edges for the nights factor
        (``NIGHT_CLASS_EDGES_MONTHLY`` or ``_SEASONAL``).
    gap : int
        0 for the monthly view, 2 for the three-month view.
    watch_rate, alarm_rate : float
        The two tiers; ``0 < alarm_rate < watch_rate < 0.5``.
    retrospective : bool
        If True, each unit's scale, the nights factors and the pooled
        factors are read from the whole record and applied to every window,
        so that early windows, which a monitor could not have judged, get a
        status too. This is hindsight: use it to describe history, never to
        claim what a monitor would have reported at the time. Each expected
        value is still fitted to earlier windows only, but which of them
        are on hold is decided with the whole-record thresholds, so an
        anomaly can change when later data change.
    tiers : bool
        If False, no unit is given WATCH or ALARM: one that reads low
        against its own past (at the watch rate) is REGIONAL. For the
        province level (owner, 2026-11-22): a province has no parent to be
        compared with, so haze and shared year-to-year movement cannot be
        told from a real change, and its alarm rate measured well above
        the 1% target (``temp/status-design.md``). Until an external haze layer exists a province reports
        "dimmer than its own past explains", never an alarm. Only the
        watch factor is then needed for a status; the alarm factor, which
        needs a larger pool, still sets the hold and ``detectable`` once
        it exists.

    Returns
    -------
    LevelStatus

    Raises
    ------
    ValueError
        If months, years or ``series.cells`` have the wrong shape, a month
        is outside 1 to 12, or the rates are not ordered
        ``0 < alarm_rate < watch_rate < 0.5``.
    TypeError
        If months or years are not integers.

    Notes
    -----
    A unit is in ALARM when its anomaly is below the alarm threshold and,
    where the parent-relative test can be applied, that is below its own
    alarm threshold too; WATCH likewise at the watch rate. Low against its
    own past but not against the rest of its parent is REGIONAL. Where the
    parent-relative test cannot be applied (no rest of the parent that
    window, or its scale or thresholds not yet known) the own-history test
    decides alone: ``joint`` is False there. In the national run of
    2026-11-22 about 40% of ALARMs were of that kind, so an ALARM is not
    always a joint finding.
    """
    index = series.index
    T, U = index.shape
    months = status._calendar_months(months, (T,))
    years = np.asarray(years)
    if years.shape != (T,):
        raise ValueError(f"years has shape {years.shape}, expected {(T,)}")
    if years.dtype.kind not in "iu":
        raise TypeError(f"years must be calendar years as integers, got dtype {years.dtype}")
    if not 0.0 < alarm_rate < watch_rate < 0.5:
        raise ValueError(f"rates must satisfy 0 < alarm_rate < watch_rate < 0.5, got {alarm_rate} and {watch_rate}")
    if np.shape(series.cells) != (U,):
        raise ValueError(f"series.cells has shape {np.shape(series.cells)}, expected {(U,)}")

    # First pass: anomalies without the hold, to learn scales and factors.
    first = np.full((T, U), np.nan)
    for u in range(U):
        if np.isfinite(index[:, u]).any():
            first[:, u] = status.anomalies(index[:, u], months, gap=gap)

    def unit_scales(anomalies_, skip=None):
        """Scale of every unit at every window: running, or one whole-record value."""
        out = np.full((T, U), np.nan)
        for u_ in range(U):
            column = anomalies_[:, u_]
            skipped = None if skip is None else skip[:, u_]
            if retrospective:
                use = np.isfinite(column) if skipped is None else np.isfinite(column) & ~skipped
                if use.sum() >= c.STATUS_MIN_PAST_ANOMALIES:
                    out[:, u_] = status.robust_scale(column[use])
            else:
                out[:, u_] = status.running_scale(column, skip=skipped)
        return out

    base_scale = unit_scales(first)
    classes = night_class(series.nights, night_edges)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(base_scale > 0, first / base_scale, np.nan)
    factors = yearly_class_factors(raw, classes, years, len(night_edges) + 1, whole_record=retrospective)
    class_factor = np.where(classes >= 0, np.take_along_axis(factors, np.maximum(classes, 0), axis=1), 1.0)
    first_scale = base_scale * class_factor
    with np.errstate(divide="ignore", invalid="ignore"):
        standardised = np.where(first_scale > 0, first / first_scale, np.nan)
    watch = yearly_tail_factor(standardised, years, watch_rate, whole_record=retrospective)
    alarm = yearly_tail_factor(standardised, years, alarm_rate, whole_record=retrospective)

    # Second pass: the same anomalies with the hold after an alarm.
    anomaly = np.full((T, U), np.nan)
    held = np.zeros((T, U), dtype=bool)
    for u in range(U):
        if not np.isfinite(index[:, u]).any():
            continue
        result = status.anomalies_held(index[:, u], months, alarm * first_scale[:, u], gap=gap)
        anomaly[:, u], held[:, u] = result.anomaly, result.held
    scale = unit_scales(anomaly, skip=held) * class_factor

    # Relative to the rest of the parent.
    relative = np.full((T, U), np.nan)
    relative_scale = np.full((T, U), np.nan)
    relative_watch = np.full(T, np.nan)
    relative_alarm = np.full(T, np.nan)
    if np.isfinite(series.rest).any():
        for u in range(U):
            if np.isfinite(series.rest[:, u]).any():
                relative[:, u] = anomaly[:, u] - status.anomalies(series.rest[:, u], months, gap=gap)
        relative_scale = unit_scales(relative)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_std = np.where(relative_scale > 0, relative / relative_scale, np.nan)
        relative_watch = yearly_tail_factor(rel_std, years, watch_rate, whole_record=retrospective)
        relative_alarm = yearly_tail_factor(rel_std, years, alarm_rate, whole_record=retrospective)

    # Classify.
    # With tiers both factors are needed; without, the watch factor alone.
    factors_known = np.isfinite(watch) & (np.isfinite(alarm) | (not tiers))
    has_threshold = np.isfinite(anomaly) & (scale > 0) & factors_known[:, None]
    with np.errstate(invalid="ignore"):
        own_alarm = has_threshold & (anomaly < alarm[:, None] * scale)
        own_watch = has_threshold & (anomaly < watch[:, None] * scale)
        has_rel = (
            np.isfinite(relative) & (relative_scale > 0)
            & np.isfinite(relative_alarm)[:, None] & np.isfinite(relative_watch)[:, None]
        )
        rel_alarm = has_rel & (relative < relative_alarm[:, None] * relative_scale)
        rel_watch = has_rel & (relative < relative_watch[:, None] * relative_scale)

    state = np.full((T, U), c.STATUS_NOT_OBSERVED, dtype=np.uint8)
    state[np.isfinite(index)] = c.STATUS_NO_REFERENCE
    state[np.isfinite(anomaly)] = c.STATUS_NO_THRESHOLD
    state[has_threshold] = c.STATUS_NORMAL
    if tiers:
        state[own_watch & has_rel & ~rel_watch] = c.STATUS_REGIONAL
        state[own_watch & (rel_watch | ~has_rel)] = c.STATUS_WATCH
        state[own_alarm & (rel_alarm | ~has_rel)] = c.STATUS_ALARM
    else:
        state[own_watch] = c.STATUS_REGIONAL
    state[series.dark] = c.STATUS_DARK

    z_power = NormalDist().inv_cdf(c.DETECTION_POWER)
    with np.errstate(invalid="ignore"):
        detectable = 1.0 - np.exp(-(-alarm[:, None] + z_power) * scale)
    detectable = np.where((scale > 0) & np.isfinite(alarm)[:, None], detectable, np.nan)
    big_enough = (series.cells >= c.MIN_UNIT_CELLS)[None, :]
    monitorable = np.isfinite(detectable) & (detectable <= c.MAX_DETECTABLE_DROP) & big_enough

    return LevelStatus(
        codes=series.codes, state=state, anomaly=anomaly, relative=relative, scale=scale,
        relative_scale=relative_scale, watch=watch, alarm=alarm, relative_watch=relative_watch,
        relative_alarm=relative_alarm, held=held, detectable=detectable, monitorable=monitorable,
        # The relative test exists but is not used when there are no tiers.
        joint=has_rel & tiers, series=series,
    )


def _unit_flags(codes: ArrayLike, flags: ArrayLike, what: str) -> tuple[NDArray[np.int64], NDArray[np.bool_]]:
    """Codes and one flag per code, checked: integers, no duplicate, same length."""
    codes = zonal.integer_codes(codes, f"{what} codes")
    flags = np.asarray(flags)
    if codes.ndim != 1 or flags.shape != codes.shape:
        raise ValueError(f"{what}: need one flag per code, got {flags.shape} flags for {codes.shape} codes")
    if flags.dtype != np.bool_:
        raise TypeError(f"{what}: flags must be boolean, got dtype {flags.dtype}")
    if np.unique(codes).size != codes.size:
        raise ValueError(f"{what}: a code appears more than once")
    return codes, flags


def reporting_level(
    subdistrict_codes: ArrayLike,
    subdistrict_ok: ArrayLike,
    district_codes: ArrayLike,
    district_ok: ArrayLike,
    province_codes: ArrayLike,
    province_ok: ArrayLike,
) -> NDArray[np.int64]:
    """The finest level at which each sub-district's area can be reported.

    Parameters
    ----------
    subdistrict_codes, district_codes, province_codes : array_like of int
        Unit codes of each level (``LevelStatus.codes``), none repeated.
    subdistrict_ok, district_ok, province_ok : array_like of bool, same lengths
        Whether each unit is monitorable (for one window, or over the record).

    Returns
    -------
    ndarray of int64, one per sub-district
        ``REPORT_SUBDISTRICT`` (3) if the sub-district is monitorable
        itself, else ``REPORT_DISTRICT`` (2) if its district is, else
        ``REPORT_PROVINCE`` (1) if its province is, else ``REPORT_NONE``
        (0): cannot be monitored. The parent is found from the leading
        digits of the code.

    Raises
    ------
    ValueError
        If codes and flags differ in length, or a code is repeated or negative.
    TypeError
        If codes are not integers or flags are not boolean.

    Notes
    -----
    A parent is not always quieter than its children (measured in tile
    h30v09), so each level is tested on its own merits, never assumed.
    A province-level "ok" comes from ``detectable``, which needs the alarm
    factor even though provinces carry no alarm.
    """
    codes, ok = _unit_flags(subdistrict_codes, subdistrict_ok, "sub-district")
    d_codes, d_ok = _unit_flags(district_codes, district_ok, "district")
    p_codes, p_ok = _unit_flags(province_codes, province_ok, "province")
    in_district = np.isin(codes // c.ADMIN_DIVISOR["district"], d_codes[d_ok])
    in_province = np.isin(codes // c.ADMIN_DIVISOR["province"], p_codes[p_ok])
    out = np.full(codes.size, c.REPORT_NONE, dtype=np.int64)
    out[in_province] = c.REPORT_PROVINCE
    out[in_district] = c.REPORT_DISTRICT
    out[ok] = c.REPORT_SUBDISTRICT
    return out


#: States in which a unit was judged, and those in which it reads low
#: against its own past (whatever the rest of its parent does).
_JUDGED = (c.STATUS_NORMAL, c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL, c.STATUS_DARK)
_LOW = (c.STATUS_WATCH, c.STATUS_ALARM, c.STATUS_REGIONAL, c.STATUS_DARK)


class Agreement(NamedTuple):
    """Result of :func:`children_agreement`, aligned with the parent codes.

    Attributes
    ----------
    judged : ndarray of int64, shape ``(T, P)``
        Voting children of each parent that were judged in each window.
    low : ndarray of int64, shape ``(T, P)``
        Of those, the children reading low against their own past.
    share : ndarray of float64, shape ``(T, P)``
        ``low / judged``; NaN where no child was judged.
    """

    judged: NDArray[np.int64]
    low: NDArray[np.int64]
    share: NDArray[np.float64]


def children_agreement(
    child_state: ArrayLike,
    child_codes: ArrayLike,
    parent_codes: ArrayLike,
    child_cells: ArrayLike | None = None,
    min_cells: int = c.MIN_UNIT_CELLS,
) -> Agreement:
    """How many of a parent's children read low together, window by window.

    Parameters
    ----------
    child_state : array_like of uint8, shape ``(T, U)``
        ``LevelStatus.state`` of the child level.
    child_codes : array_like of int, shape ``(U,)``
        Codes of the children. A child's parent is its code without the
        last two digits, at both steps of the hierarchy.
    parent_codes : array_like of int, shape ``(P,)``
        Codes of the parents to report on, none repeated.
    child_cells : array_like of int, shape ``(U,)``, optional
        Domain cells of each child (``LevelSeries.cells``). Children under
        ``min_cells`` do not vote. If omitted, every child votes.
    min_cells : int
        Cells a child needs to vote.

    Returns
    -------
    Agreement

    Raises
    ------
    ValueError
        If the shapes disagree, or a parent code is repeated or negative.
    TypeError
        If codes are not integers.

    Notes
    -----
    A child "reads low" when it is WATCH, ALARM, REGIONAL or DARK: low
    against its own past, whether or not the rest of its parent fell too.
    The parent-relative test deliberately sets aside a child whose siblings
    fell with it (that removes haze and shared swings), so an event that
    hits a whole parent disappears from the children one by one. This count
    brings it back at the parent: many children low together is evidence
    about the parent that no single child carries.

    Why small children do not vote: a unit of a few cells reads "seen and
    dark" whenever those cells sit at zero, which says little about its
    parent. In the national run of 2026-11-22, units under 20 cells
    supplied 6,209 of the 6,518 dark windows.
    """
    child_state = np.asarray(child_state)
    child_codes = zonal.integer_codes(child_codes, "child codes")
    parent_codes = zonal.integer_codes(parent_codes, "parent codes")
    if child_state.ndim != 2 or child_codes.shape != (child_state.shape[1],):
        raise ValueError("child_state must be (windows, children) with one code per child")
    if parent_codes.ndim != 1 or np.unique(parent_codes).size != parent_codes.size:
        raise ValueError("parent codes must be a list without repeats")
    votes = np.ones(child_codes.size, dtype=bool)
    if child_cells is not None:
        child_cells = np.asarray(child_cells)
        if child_cells.shape != child_codes.shape:
            raise ValueError("child_cells must have one entry per child")
        votes = child_cells >= min_cells

    position = {int(code): i for i, code in enumerate(parent_codes.tolist())}
    column = np.array([position.get(int(p), -1) for p in (child_codes // _CHILD_TO_PARENT).tolist()], dtype=np.int64)
    T = child_state.shape[0]
    judged = np.zeros((T, parent_codes.size), dtype=np.int64)
    low = np.zeros((T, parent_codes.size), dtype=np.int64)
    is_judged = np.isin(child_state, _JUDGED)
    is_low = np.isin(child_state, _LOW)
    for u in np.nonzero((column >= 0) & votes)[0]:
        judged[:, column[u]] += is_judged[:, u]
        low[:, column[u]] += is_low[:, u]
    share = np.where(judged > 0, low / np.maximum(judged, 1), np.nan)
    return Agreement(judged=judged, low=low, share=share)


def confirm_by_children(
    parent_state: ArrayLike,
    agreement: Agreement,
    min_share: float = c.CHILD_AGREEMENT_SHARE,
    min_children: int = c.CHILD_AGREEMENT_MIN,
) -> NDArray[np.uint8]:
    """Raise a parent to REGIONAL when enough of its children read low together.

    Parameters
    ----------
    parent_state : array_like of uint8, shape ``(T, P)``
        ``LevelStatus.state`` of the parent level.
    agreement : Agreement
        From :func:`children_agreement` for the same parents.
    min_share : float
        The share of the judged children reading low must be MORE than
        this: with the default, 2 of 3 is not enough and 3 of 4 is.
    min_children : int
        Judged children a parent needs for the rule to apply.

    Returns
    -------
    ndarray of uint8, shape ``(T, P)``
        The parent states, with NORMAL, NO_THRESHOLD and NO_REFERENCE
        replaced by REGIONAL where the children agree. WATCH, ALARM, DARK
        and NOT_OBSERVED are left as they are: a parent that was not seen
        is never given a status from its children.

    Raises
    ------
    ValueError
        If the agreement is not aligned with the parent states.

    Notes
    -----
    REGIONAL then means "dimmer across the unit than its own past
    explains, cause not identified". In Sumatra and Kalimantan from August
    to October that cause is often haze; an external aerosol or fire layer
    is needed to tell.
    """
    state = np.array(parent_state, dtype=np.uint8, copy=True)
    if agreement.judged.shape != state.shape:
        raise ValueError(f"agreement has shape {agreement.judged.shape}, parent states {state.shape}")
    with np.errstate(invalid="ignore"):
        agree = (agreement.judged >= min_children) & (agreement.share > min_share)
    upgradable = np.isin(state, (c.STATUS_NORMAL, c.STATUS_NO_THRESHOLD, c.STATUS_NO_REFERENCE))
    state[agree & upgradable] = c.STATUS_REGIONAL
    return state


# ---- every level of a stack, and its file ----------------------------------

#: Fields of a saved run, per level: the result arrays, then the inputs.
_STATUS_FIELDS = ("codes", "state", "anomaly", "relative", "scale", "relative_scale", "watch", "alarm",
                  "relative_watch", "relative_alarm", "held", "detectable", "monitorable", "joint")
_SERIES_FIELDS = ("index", "coverage", "dark", "nights", "rest", "cells")
#: Version of the run file written by :func:`save_levels`.
RUN_FILE_VERSION = 1


def run_levels(
    stack: TileStack,
    seasonal: bool = False,
    retrospective: bool = False,
) -> dict[str, LevelStatus]:
    """Status of every unit at the three levels, from one (joined) stack.

    Parameters
    ----------
    stack : TileStack
        Usually every tile joined (``ntl.stack.load_folder``), so that the
        pooled factors are read over the whole country.
    seasonal : bool
        False: the monthly view. True: the three-month view
        (``TileStack.seasonal``), with a gap of 2 windows and the seasonal
        nights classes. A three-month window is centred on its month.
    retrospective : bool
        As :func:`run_level`: hindsight, not what a monitor would have said.

    Returns
    -------
    dict of str to LevelStatus
        One entry per level of ``ADMIN_LEVELS``. Provinces are run without
        tiers (owner, 2026-11-22): they report REGIONAL, never WATCH or
        ALARM. The children-agreement rule is not applied here.

    Notes
    -----
    The sub-district level of the national stack takes about 11 minutes.
    """
    if seasonal:
        pooled = stack.seasonal()
        values, nights = pooled.value, pooled.nights
        edges, gap = c.NIGHT_CLASS_EDGES_SEASONAL, 2
    else:
        values, nights = stack.usable(), stack.nights
        edges, gap = c.NIGHT_CLASS_EDGES_MONTHLY, 0
    out = {}
    for level in c.ADMIN_LEVELS:
        parent = c.ADMIN_PARENT[level]
        series = level_series(values, nights, stack.usual, stack.units(level),
                              parent_codes=None if parent is None else stack.units(parent))
        out[level] = run_level(series, stack.calendar_month, stack.year, night_edges=edges, gap=gap,
                               retrospective=retrospective, tiers=parent is not None)
        log.info("%s: %d units, %d monitorable in the last window", level, out[level].codes.size,
                 int(out[level].monitorable[-1].sum()))
    return out


def save_levels(
    levels: Mapping[str, LevelStatus],
    stack: TileStack,
    path: str | Path,
    seasonal: bool = False,
    retrospective: bool = False,
) -> Path:
    """Write a run of :func:`run_levels` to one ``.npz`` file.

    Parameters
    ----------
    levels : mapping of str to LevelStatus
        From :func:`run_levels`.
    stack : TileStack
        The stack it was run on; its months, view and domain rule are
        recorded so that a reader knows what the run rests on.
    path : str or Path
        Target file (``.npz``). Written under a temporary name and renamed.
    seasonal, retrospective : bool
        As passed to :func:`run_levels`; recorded.

    Returns
    -------
    Path
        The file written.
    """
    target = Path(path)
    temporary = target.with_name(target.stem + ".part.npz")
    arrays: dict[str, object] = dict(
        version=RUN_FILE_VERSION,
        months=np.array([m.isoformat() for m in stack.months]),
        tiles=stack.tile, view=stack.view, seasonal=seasonal, retrospective=retrospective,
        until="" if stack.until is None else stack.until.isoformat(),
        lit_min=stack.lit_min, min_good_months=stack.min_good_months,
        source_contrast=np.nan if stack.source_contrast is None else stack.source_contrast,
        levels=np.array(list(levels)),
    )
    for level, result in levels.items():
        for name in _STATUS_FIELDS:
            arrays[f"{level}_{name}"] = getattr(result, name)
        for name in _SERIES_FIELDS:
            arrays[f"{level}_{name}"] = getattr(result.series, name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


class Run(NamedTuple):
    """A saved run, as read by :func:`load_levels`.

    Attributes
    ----------
    months : tuple of datetime.date
        First day of each window's month, length ``T``. In the three-month
        view the window is CENTRED on that month (the month before, the
        month and the month after: ``composite.three_month``), so the
        status of a month needs the following month's file.
    levels : dict of str to LevelStatus
    info : dict
        ``tiles``, ``view``, ``seasonal``, ``retrospective``, ``until``
        (ISO date or None), ``lit_min``, ``min_good_months``.
    """

    months: tuple[dt.date, ...]
    levels: dict[str, LevelStatus]
    info: dict[str, object]


def load_levels(path: str | Path) -> Run:
    """Read a file written by :func:`save_levels`.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If it is damaged, incomplete, or not a run file of a version this
        code reads. The message says to run the monitor again.
    """
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"{target}: no such run file")
    try:
        archive = np.load(target, allow_pickle=False)
    except (zipfile.BadZipFile, EOFError, ValueError) as exc:
        raise ValueError(f"{target}: not a readable run file ({exc}); run the monitor again") from exc
    if not hasattr(archive, "files"):
        raise ValueError(f"{target}: not a run file (a single array, not an archive); run the monitor again")
    with archive as z:
        if "version" not in z.files or "levels" not in z.files:
            raise ValueError(f"{target}: not a run file written by ntl.monitor; run the monitor again")
        if int(z["version"]) != RUN_FILE_VERSION:
            raise ValueError(f"{target}: run file version {int(z['version'])} is not readable by this code; run the monitor again")
        wanted = {"months", "tiles", "view", "seasonal", "retrospective", "until", "lit_min", "min_good_months"}
        for level in (str(name) for name in z["levels"]):
            wanted |= {f"{level}_{name}" for name in (*_STATUS_FIELDS, *_SERIES_FIELDS)}
        missing = sorted(wanted - set(z.files))
        if missing:
            raise ValueError(f"{target}: incomplete run file (missing {missing[:4]}); run the monitor again")
        levels = {}
        for level in (str(name) for name in z["levels"]):
            series = LevelSeries(codes=z[f"{level}_codes"], **{name: z[f"{level}_{name}"] for name in _SERIES_FIELDS})
            levels[level] = LevelStatus(**{name: z[f"{level}_{name}"] for name in _STATUS_FIELDS}, series=series)
        info = dict(
            tiles=str(z["tiles"]), view=str(z["view"]), seasonal=bool(z["seasonal"]),
            retrospective=bool(z["retrospective"]), until=str(z["until"]) or None,
            lit_min=float(z["lit_min"]), min_good_months=int(z["min_good_months"]),
            # absent from run files written before light sources were added to the domain (2026-11-23)
            source_contrast=float(z["source_contrast"]) if "source_contrast" in z.files and np.isfinite(float(z["source_contrast"])) else None,
        )
        months = tuple(dt.date.fromisoformat(str(m)) for m in z["months"])
    return Run(months=months, levels=levels, info=info)


_EXAMPLES = r"""example:
  python -m ntl.monitor --cache E:\temp\ntl\cache --out E:\temp\ntl\cache\run_monthly.npz
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.monitor",
        description="Status of every province, district and sub-district, month by month, "
        "from the stack caches written by ntl.stack.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cache", required=True, type=Path, help="folder of stack caches (python -m ntl.stack)")
    parser.add_argument("--out", required=True, type=Path, help="run file to write (.npz)")
    parser.add_argument("--view", default=c.DEFAULT_VIEW, choices=c.COMPOSITE_VIEWS, help=f"view-angle class (default {c.DEFAULT_VIEW})")
    parser.add_argument("--seasonal", action="store_true", help="three-month windows instead of months")
    parser.add_argument("--retrospective", action="store_true",
                        help="hindsight: thresholds from the whole record. For describing history, not what a monitor would have reported")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point: run every level and save the result.

    Returns
    -------
    int
        0 on success; 1 if the caches cannot be read; 2 for a usage problem.
    """
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        # Before the run, which takes minutes: a result that cannot be written is a result lost.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.is_dir():
            raise ValueError(f"{args.out} is a folder; --out must name a file")
        stack = load_folder(args.cache, args.view)
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    log.info("%d cells, %d months, domain from %s", stack.value.shape[1], len(stack.months),
             "the whole record (look-ahead)" if stack.until is None else f"months before {stack.until}")
    levels = run_levels(stack, seasonal=args.seasonal, retrospective=args.retrospective)
    try:
        written = save_levels(levels, stack, args.out, seasonal=args.seasonal, retrospective=args.retrospective)
    except OSError as exc:
        log.error("cannot write %s: %s", args.out, exc)
        return 1
    log.info("wrote %s", written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
