"""A yearly DMSP-OLS record per admin unit, 1992 to 2013, with a band that says how far two satellites disagree.

Method, as settled after the critiques and reviews of 2026-11-24. The
evidence is in ``temp/dmsp-critique.md`` and ``temp/review-dmsp.md``, which are
working notes and not part of the repository; every figure used is repeated
here with its date.

Level. The level across years is EOG's own intercalibration (Elvidge et al.
2009, https://doi.org/10.3390/en20300595: second order, reference F12 1999,
fitted over Sicily on the assumption that its lighting was largely stable).
Nothing is refitted here. The overlaps between satellites cannot fix a trend: every one
of them is two satellites in the SAME year, so they say nothing about how
readings moved from one year to the next. Any trend error from the Sicily
assumption is in every year and no band below can show it.

Two satellites in a year. The value is their mean, unless one of them
plainly misses the unit's dim light (see recall below) while the other does
not; then the better one stands alone.

The band is a statement of DISAGREEMENT BETWEEN SATELLITES, not a confidence
interval. Per unit, the spread is the root mean square, over the years with
two satellites, of half the log difference of the two readings (root mean
square, so that one bad year counts; a year where one satellite sees the unit
and the other sees nothing counts as :data:`ONE_SIDED_HALF`). The half width
in log is ``sqrt((k * spread)**2 + year**2)`` with ``k`` = 1 for a mean of two
and :data:`BAND_FACTOR` for one satellite, and ``year`` the part common to all
units in a year (:data:`YEAR_SPREAD`). Measured over Indonesia, provinces,
leaving a year out, for light: with ``k`` = 1 a single-satellite band held the
other satellite's reading 35% of the time, with ``k`` = 2 about 68%. The year term
is an upper estimate (0.051 for light, 0.081 for lit area, standard deviation
over 1995 to 2011 of the part common to all provinces), since it also takes
in real change. A value of zero carries no band: it is "not detected".

Quantities per unit and year: ``light`` (sum of corrected digital numbers;
not radiance), ``lit`` (cells above zero, a count of 30 arc-second cells, not
an area in km2; no floor), ``bright`` (cells above :data:`BRIGHT_DN`) and
``outside`` (light over cells not touched by a flare outline). No floor is
put on ``lit`` because newly lit rural cells sit just above the detection
edge: of cells dark in the mid 1990s and lit in 2008 and 2009, 8% exceed a
corrected value of 8.

Recall. A satellite-year can lose dim cells that the years around it see.
For each satellite-year the steady dim cells are those lit in at least
:data:`STEADY_SHARE` of the other satellite-years within
:data:`RECALL_WINDOW` years, with a median corrected value below
:data:`DIM_DN`; recall is the share of a unit's steady dim cells that this
satellite-year sees. Over Indonesia it is below 0.7 in 32 of 38 provinces in
1992, 14 in 1993, 12 in 2009 and 11 in 2013, and in three or fewer in every
other year once the weaker of two satellites has been set aside (F12 1999
alone is below 0.7 in 18). It measures that dim light went missing, not why:
in 1997 in central and south Kalimantan the raw light is higher than usual,
which may be fire and haze rather than a detection edge (not checked).

Flags, none of which changes a value: ``drops`` (lit area well below the
years before and after: it drops and returns), ``low_recall``, ``thin`` (few
cloud-free observations in the unit), ``undetected`` (no light at all),
``saturated`` (share of light from cells at the top of the scale) and the
second segment: for 2010 to 2013 EOG's Version 4 series holds a yearly
composite of F18 alone (other satellites flew, but none has a composite), so
nothing ties those years to the ones before, and the step from 2009 to 2010
is not known.

Gas flares. ``outside`` leaves out cells touched by the outlines NOAA drew
for the DMSP years (for Elvidge et al. 2009; one shapefile per country, dated
2009). The outlines are broad and take in towns, and flare glow reaches
beyond them, so ``outside`` is neither "settlement light" nor free of flares.
Which mask is used decides the result where flares are large (one province
of Indonesia reads 0.69, 1.17 or 0.71 of its 1996 light in 2007 with no mask,
these outlines, or a tight mask). So ``outside`` is marked usable only for
units where the outlines never hold more than :data:`FLARE_SHARE_MAX` of the
light.

What this record cannot support: a growth figure from two single years, any
change across 2009 to 2010, a trend for a saturated unit, or the words
"electrification" and "settlement light". It has not been compared with any
record on the ground.

Nothing here is specific to Indonesia.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, NamedTuple

import numpy as np
from numpy.typing import NDArray

from ntl import conventions as c
from ntl import dmsp
from ntl.read import Grid

log = logging.getLogger("ntl.longrecord")

#: Corrected digital number above which a cell counts as brightly lit. Picked; pairs of satellites
#: agree better on this count than on all lit cells (median province disagreement 0.040 against 0.067).
BRIGHT_DN: Final[float] = 8.0
#: A satellite-year, or a unit within one, with a median of fewer cloud-free observations than this is
#: thin. Picked: the two satellite-years below it (F10 1992 at 11, F12 1994 at 10) are far from the rest (22 to 50).
THIN_OBSERVATIONS: Final[float] = 15.0
#: Fewest years with two satellites a unit needs for a spread of its own. Picked.
MIN_PAIR_YEARS: Final[int] = 4
#: Half log difference counted for a year in which one satellite sees a unit and the other sees nothing. Picked.
ONE_SIDED_HALF: Final[float] = 1.0
#: Multiple of the spread used for a year that rests on one satellite. Measured (module docstring).
BAND_FACTOR: Final[float] = 2.0
#: Part of the error common to all units in a year, in log, by quantity. Measured for light and lit area
#: (module docstring); the other two take the figure of the quantity they resemble, which is assumed.
YEAR_SPREAD: Final[dict[str, float]] = {"light": 0.05, "outside": 0.05, "lit": 0.08, "bright": 0.08}
#: First year of the second segment: F18, which never shares a year with another satellite.
UNTIED_FROM: Final[int] = 2010
#: Years on each side that count as "around" a satellite-year, for recall and for drops. Picked.
RECALL_WINDOW: Final[int] = 3
#: Share of the satellite-years around in which a cell must be lit to be steady. Picked.
STEADY_SHARE: Final[float] = 0.6
#: Median corrected digital number below which a steady cell is dim. Picked, as BRIGHT_DN.
DIM_DN: Final[float] = 8.0
#: Fewest steady dim cells a unit needs for a recall. Picked.
RECALL_MIN_CELLS: Final[int] = 50
#: Recall below which a unit-year is flagged, and below which a satellite may be set aside. Picked;
#: of 91 province-years reading more than 0.15 log below the years around, it catches 39.
LOW_RECALL: Final[float] = 0.7
#: How much better the other satellite's recall must be for it to stand alone. Picked.
RECALL_GAP: Final[float] = 0.15
#: A unit-year is a drop when its lit area is below this share of the years before and of the years after. Picked.
DROP_RATIO: Final[float] = 0.75
#: Fewest years needed on each side, within RECALL_WINDOW, for a drop to be judged. Picked.
DROP_MIN_YEARS: Final[int] = 2
#: Fewest lit cells (median of each side) for a drop to be judged. Picked.
DROP_MIN_CELLS: Final[float] = 20.0
#: Largest share of a unit's light inside the flare outlines, in any year, for ``outside`` to be usable. Picked.
FLARE_SHARE_MAX: Final[float] = 0.10
#: The quantities kept per unit.
QUANTITIES: Final[tuple[str, ...]] = ("light", "lit", "bright", "outside")

Key = tuple[str, int]


class Reading(NamedTuple):
    """One satellite-year summed over units.

    Attributes
    ----------
    light, outside : ndarray of float64, shape (units,)
        Sum of corrected digital numbers over all cells, and over cells not
        touched by a flare outline (equal where no outlines were given).
    lit, bright : ndarray of float64, shape (units,)
        Count of cells above zero, and above :data:`BRIGHT_DN`.
    saturated : ndarray of float64, shape (units,)
        Share of ``light`` from cells at or above ``dmsp.SATURATED_DN`` in the
        archived file; NaN where the unit has no light.
    observations : ndarray of float64, shape (units,)
        Median cloud-free observations over the unit's cells; NaN for a unit
        with no cell.
    recall : ndarray of float64, shape (units,)
        Share of the unit's steady dim cells seen; NaN where it has fewer
        than :data:`RECALL_MIN_CELLS` or no steady cells were given.
    seen : float
        Median cloud-free observations over all cells inside any unit.
    """

    light: NDArray[np.float64]
    lit: NDArray[np.float64]
    bright: NDArray[np.float64]
    outside: NDArray[np.float64]
    saturated: NDArray[np.float64]
    observations: NDArray[np.float64]
    recall: NDArray[np.float64]
    seen: float


class Series(NamedTuple):
    """The yearly record of one quantity.

    Attributes
    ----------
    value, low, high : ndarray of float64, shape (years, units)
        The value and the disagreement band. ``low`` and ``high`` are NaN
        where the value is zero and where the unit has no spread.
    pair_low, pair_high : ndarray of float64, shape (years, units)
        The two readings of a year with two satellites; NaN in other years.
    spread : ndarray of float64, shape (units,)
        Root mean square of half the log difference between two satellites,
        natural log.
    own_spread : ndarray of bool, shape (units,)
        False where the unit had fewer than :data:`MIN_PAIR_YEARS` years to
        judge from and the median over the other units stands in.
    """

    value: NDArray[np.float64]
    low: NDArray[np.float64]
    high: NDArray[np.float64]
    pair_low: NDArray[np.float64]
    pair_high: NDArray[np.float64]
    spread: NDArray[np.float64]
    own_spread: NDArray[np.bool_]


class LongRecord(NamedTuple):
    """The yearly record of every quantity with its flags.

    Attributes
    ----------
    years : ndarray of int64, shape (years,)
        Only years with a reading; a year without one is absent, not NaN.
    series : dict of str to Series
        By quantity (:data:`QUANTITIES`).
    used : ndarray of int8, shape (years, units)
        Satellites behind the value: 2 for a mean of two, 1 for one.
    sources : list of list of str
        Per year, the satellites kept, for example ``["F14", "F15"]``. Where
        ``used`` is 1 in a year with two, ``chosen`` says which.
    chosen : ndarray of int8, shape (years, units)
        -1 where both or the only satellite stand; otherwise the position in
        ``sources`` of the one kept for its better recall.
    recall, observations, saturated : ndarray of float64, shape (years, units)
        The lowest recall and observation count, and the highest saturated
        share, among the satellites behind the value.
    drops, low_recall, thin, undetected : ndarray of bool, shape (years, units)
        The flags of the module docstring.
    flare_share : ndarray of float64, shape (years, units)
        Share of ``light`` inside the flare outlines; NaN where no light.
    outside_usable : ndarray of bool, shape (units,)
        True where ``flare_share`` never exceeds :data:`FLARE_SHARE_MAX`.
    segment : ndarray of int8, shape (years,)
        0 before :data:`UNTIED_FROM`, 1 from it.
    dropped : list of str
        Satellite-years left out for thin observation.
    satellites : dict of str to dict
        Per satellite-year read, left out or not: ``light`` and ``lit``
        summed over all units, so that each satellite can be drawn as its
        own line.
    seen : dict of str to float
        Median cloud-free observations of every satellite-year read.
    """

    years: NDArray[np.int64]
    series: dict[str, Series]
    used: NDArray[np.int8]
    sources: list[list[str]]
    chosen: NDArray[np.int8]
    recall: NDArray[np.float64]
    observations: NDArray[np.float64]
    saturated: NDArray[np.float64]
    drops: NDArray[np.bool_]
    low_recall: NDArray[np.bool_]
    thin: NDArray[np.bool_]
    undetected: NDArray[np.bool_]
    flare_share: NDArray[np.float64]
    outside_usable: NDArray[np.bool_]
    segment: NDArray[np.int8]
    dropped: list[str]
    satellites: dict[str, dict[str, float]]
    seen: dict[str, float]


def _unit_median(values: NDArray, index: NDArray[np.intp], units: int) -> NDArray[np.float64]:
    """Median of ``values`` per unit position in ``index``; NaN for a unit with no value."""
    order = np.lexsort((values, index))
    ordered, sorted_index = values[order].astype(np.float64), index[order]
    first = np.searchsorted(sorted_index, np.arange(units), side="left")
    last = np.searchsorted(sorted_index, np.arange(units), side="right")
    count = last - first
    out = np.full(units, np.nan)
    has = count > 0
    lower = first[has] + (count[has] - 1) // 2
    upper = first[has] + count[has] // 2
    out[has] = (ordered[lower] + ordered[upper]) / 2.0
    return out


def unit_reading(corrected: NDArray, uncorrected: NDArray, observations: NDArray, units: NDArray, codes: NDArray,
                 flares: NDArray[np.bool_] | None = None, steady: NDArray[np.bool_] | None = None) -> Reading:
    """Sum one satellite-year over units.

    Parameters
    ----------
    corrected : ndarray of float
        EOG's intercalibrated stable lights (digital number). 0 is "no
        light"; the files carry no fill value, so a cell never seen is 0 too.
    uncorrected : ndarray, same shape
        The stable lights as archived, used only to find saturated cells
        (the corrected files are capped below the top of the scale).
    observations : ndarray, same shape
        Cloud-free observations per cell.
    units : ndarray of int, same shape
        Unit code per cell, ``conventions.NO_UNIT`` outside every unit.
    codes : ndarray of int
        The unit codes to report, strictly ascending.
    flares : ndarray of bool, same shape, optional
        True where a cell is touched by a flare outline.
    steady : ndarray of bool, same shape, optional
        True for this satellite-year's steady dim cells (:func:`steady_dim_cells`).

    Returns
    -------
    Reading

    Raises
    ------
    ValueError
        If the arrays differ in shape, ``codes`` is not strictly ascending,
        or ``corrected`` holds a NaN inside a unit.
    """
    shapes = [a.shape for a in (corrected, uncorrected, observations, units)]
    if len(set(shapes)) != 1:
        raise ValueError(f"shapes differ: {shapes}")
    for name, extra in (("flare cells", flares), ("steady cells", steady)):
        if extra is not None and extra.shape != units.shape:
            raise ValueError(f"{name} {extra.shape} do not match the grid {units.shape}")
    codes = np.asarray(codes)
    if codes.size > 1 and np.any(np.diff(codes) <= 0):
        raise ValueError("unit codes must be strictly ascending")
    inside = np.isin(units, codes)
    index = np.searchsorted(codes, units[inside])
    value = corrected[inside].astype(np.float64)
    if np.isnan(value).any():
        raise ValueError("the corrected layer holds NaN inside a unit; EOG's files have no fill value")

    def total(weights: NDArray) -> NDArray[np.float64]:
        return np.bincount(index, weights=weights, minlength=codes.size).astype(np.float64)

    light = total(value)
    top = total(np.where(uncorrected[inside] >= dmsp.SATURATED_DN, value, 0.0))
    with np.errstate(invalid="ignore", divide="ignore"):
        saturated = np.where(light > 0, top / light, np.nan)
    outside = light if flares is None else total(np.where(flares[inside], 0.0, value))
    recall = np.full(codes.size, np.nan)
    if steady is not None:
        cells = total(steady[inside])
        with np.errstate(invalid="ignore", divide="ignore"):
            recall = np.where(cells >= RECALL_MIN_CELLS, total(steady[inside] & (value > 0)) / cells, np.nan)
    seen_cells = observations[inside]
    return Reading(light=light, lit=total(value > 0), bright=total(value > BRIGHT_DN), outside=outside, saturated=saturated,
                   observations=_unit_median(seen_cells, index, codes.size), recall=recall,
                   seen=float(np.median(seen_cells)) if seen_cells.size else float("nan"))


def steady_dim_cells(corrected: Mapping[Key, NDArray]) -> dict[Key, NDArray[np.bool_]]:
    """For each satellite-year, the cells the years around it agree are dimly but steadily lit.

    Parameters
    ----------
    corrected : mapping of (satellite, year) to ndarray
        Corrected digital numbers of the same cells in every satellite-year.

    Returns
    -------
    dict of (satellite, year) to ndarray of bool
        True where the cell is lit in at least :data:`STEADY_SHARE` of the
        OTHER satellite-years within :data:`RECALL_WINDOW` years and its
        median value among them is below :data:`DIM_DN`. All False for a
        satellite-year with fewer than two others around it. The
        satellite-year itself never enters its own reference; at the ends of
        the record the reference is one-sided.
    """
    keys = sorted(corrected)
    years = np.array([k[1] for k in keys])
    lit = {k: corrected[k] > 0 for k in keys}
    out: dict[Key, NDArray[np.bool_]] = {}
    for i, key in enumerate(keys):
        others = [keys[j] for j in np.flatnonzero((np.abs(years - years[i]) <= RECALL_WINDOW) & (np.arange(len(keys)) != i))]
        dim = np.zeros(corrected[key].shape, dtype=bool)
        if len(others) >= 2:
            steady = np.mean([lit[o] for o in others], axis=0) >= STEADY_SHARE
            median = np.median(np.array([corrected[o][steady] for o in others]), axis=0)
            dim[steady] = median < DIM_DN
        out[key] = dim
    return out


def pair_spread(pairs: Sequence[tuple[NDArray, NDArray]], units: int) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Per unit, how far two satellites of the same year are apart, over all such years.

    Parameters
    ----------
    pairs : sequence of (ndarray, ndarray), each of shape (units,)
        The two readings of each year with two satellites.
    units : int

    Returns
    -------
    (ndarray of float64, ndarray of bool)
        The root mean square of half the log difference, and whether it is
        the unit's own. A year where both read zero says nothing and is left
        out; a year where one reads zero counts as :data:`ONE_SIDED_HALF`. A
        unit with fewer than :data:`MIN_PAIR_YEARS` years takes the median of
        the units that have them (NaN if none has).
    """
    if not pairs:
        return np.full(units, np.nan), np.zeros(units, dtype=bool)
    halves = []
    for a, b in pairs:
        with np.errstate(invalid="ignore", divide="ignore"):
            half = np.abs(np.log(a / b)) / 2.0
        half = np.where((a > 0) != (b > 0), ONE_SIDED_HALF, half)
        halves.append(np.where((a > 0) | (b > 0), half, np.nan))
    stack = np.array(halves)
    valid = np.isfinite(stack)
    with np.errstate(invalid="ignore", divide="ignore"):
        rms = np.sqrt(np.where(valid, stack**2, 0.0).sum(axis=0) / valid.sum(axis=0))
    own = valid.sum(axis=0) >= MIN_PAIR_YEARS
    return np.where(own, rms, np.median(rms[own]) if own.any() else np.nan), own


def band(value: NDArray, spread: NDArray, used: NDArray, year_spread: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Lower and upper edge of the disagreement band.

    Parameters
    ----------
    value : ndarray, shape (years, units)
    spread : ndarray, shape (units,)
        From :func:`pair_spread`.
    used : ndarray of int, shape (years, units)
        Satellites behind each value, 1 or 2.
    year_spread : float
        The part common to all units in a year, natural log.

    Returns
    -------
    (ndarray, ndarray)
        ``value * exp(-w)`` and ``value * exp(+w)`` with
        ``w = sqrt((k * spread)**2 + year_spread**2)``, ``k`` 1 where two
        satellites were used and :data:`BAND_FACTOR` where one. NaN where the
        value is zero (not detected is not "zero for certain") or NaN.
    """
    width = np.sqrt((np.where(used == 1, BAND_FACTOR, 1.0) * spread) ** 2 + year_spread**2)
    known = np.asarray(value) > 0
    return np.where(known, value * np.exp(-width), np.nan), np.where(known, value * np.exp(width), np.nan)


def choose(first: NDArray, second: NDArray) -> NDArray[np.int8]:
    """Which of two satellites to set aside for missing a unit's dim light.

    Parameters
    ----------
    first, second : ndarray, shape (units,)
        Recall of the two satellites; NaN where it could not be judged.

    Returns
    -------
    ndarray of int8, shape (units,)
        -1 to keep both; 0 or 1 for the one that stands alone: its recall is
        at least :data:`RECALL_GAP` above the other's, and the other's is
        below :data:`LOW_RECALL`. A NaN on either side keeps both.
    """
    out = np.full(np.shape(first), -1, dtype=np.int8)
    with np.errstate(invalid="ignore"):
        out[(second < LOW_RECALL) & (first >= second + RECALL_GAP)] = 0
        out[(first < LOW_RECALL) & (second >= first + RECALL_GAP)] = 1
    return out


def lit_drops(lit: NDArray, years: NDArray) -> NDArray[np.bool_]:
    """Unit-years whose lit area drops well below the years before AND after, and so returns.

    Parameters
    ----------
    lit : ndarray, shape (years, units)
        Lit cells per year and unit.
    years : ndarray of int, shape (years,)

    Returns
    -------
    ndarray of bool, shape (years, units)
        True where the lit area is below :data:`DROP_RATIO` times both the
        median of the years before and the median of the years after, each
        taken within :data:`RECALL_WINDOW` years, each from at least
        :data:`DROP_MIN_YEARS` years and at least :data:`DROP_MIN_CELLS`
        cells. A fall that lasts, or a rise, is not a drop. The first and
        last :data:`DROP_MIN_YEARS` years of a record are never judged. The
        flag says the lit area dropped and came back, not why.
    """
    lit = np.asarray(lit, dtype=np.float64)
    drops = np.zeros(lit.shape, dtype=bool)
    for i, year in enumerate(years):
        before = (years < year) & (years >= year - RECALL_WINDOW)
        after = (years > year) & (years <= year + RECALL_WINDOW)
        if before.sum() < DROP_MIN_YEARS or after.sum() < DROP_MIN_YEARS:
            continue
        usual = np.minimum(np.median(lit[before], axis=0), np.median(lit[after], axis=0))
        with np.errstate(invalid="ignore"):
            drops[i] = (usual >= DROP_MIN_CELLS) & (lit[i] < DROP_RATIO * usual)
    return drops


def assemble(readings: Mapping[Key, Reading]) -> LongRecord:
    """Turn satellite-year readings into the yearly record with its band and flags.

    Parameters
    ----------
    readings : mapping of (satellite, year) to Reading
        All of the same units, in the same order.

    Returns
    -------
    LongRecord

    Notes
    -----
    A satellite-year whose ``seen`` is below :data:`THIN_OBSERVATIONS` is left
    out where a satellite that is not thin covers the same year, and kept
    where it is the only one (its unit-years then carry the ``thin`` flag as
    far as their own observation counts say so).

    Raises
    ------
    ValueError
        If there are no readings, they differ in length, or a year is left
        with more than two satellites.
    """
    if not readings:
        raise ValueError("no readings")
    sizes = {r.light.size for r in readings.values()}
    if len(sizes) != 1:
        raise ValueError(f"readings cover different numbers of units: {sorted(sizes)}")
    units = sizes.pop()
    thin = {k for k, r in readings.items() if r.seen < THIN_OBSERVATIONS}
    dropped = sorted(k for k in thin if any(o[1] == k[1] and o not in thin for o in readings))
    kept: dict[int, list[Key]] = {}
    for key in sorted(readings):
        if key not in dropped:
            kept.setdefault(key[1], []).append(key)
    if max(len(v) for v in kept.values()) > 2:
        raise ValueError("a year has more than two satellites; the record is defined for one or two")
    years = np.array(sorted(kept), dtype=np.int64)
    shape = (years.size, units)

    used = np.ones(shape, dtype=np.int8)
    chosen = np.full(shape, -1, dtype=np.int8)
    for i, year in enumerate(years):
        if len(kept[year]) == 2:
            a, b = (readings[k] for k in kept[year])
            chosen[i] = choose(a.recall, b.recall)
            used[i] = np.where(chosen[i] < 0, 2, 1)

    def over_used(name: str, join) -> NDArray[np.float64]:
        """One per-unit attribute over the satellites behind each value; ``join`` takes the worse of two."""
        out = np.full(shape, np.nan)
        for i, year in enumerate(years):
            rows = [getattr(readings[k], name) for k in kept[year]]
            if len(rows) == 1:
                out[i] = rows[0]
                continue
            a, b = rows
            with np.errstate(invalid="ignore"):
                joined = np.where(np.isnan(a), b, np.where(np.isnan(b), a, join(a, b)))
            out[i] = np.where(chosen[i] == 0, a, np.where(chosen[i] == 1, b, joined))
        return out

    series: dict[str, Series] = {}
    for quantity in QUANTITIES:
        value = np.full(shape, np.nan)
        pair_low, pair_high = value.copy(), value.copy()
        pairs = []
        for i, year in enumerate(years):
            rows = [getattr(readings[k], quantity) for k in kept[year]]
            if len(rows) == 1:
                value[i] = rows[0]
                continue
            a, b = rows
            pairs.append((a, b))
            pair_low[i], pair_high[i] = np.minimum(a, b), np.maximum(a, b)
            value[i] = np.where(chosen[i] == 0, a, np.where(chosen[i] == 1, b, (a + b) / 2.0))
        spread, own = pair_spread(pairs, units)
        low, high = band(value, spread, used, YEAR_SPREAD[quantity])
        series[quantity] = Series(value=value, low=low, high=high, pair_low=pair_low, pair_high=pair_high, spread=spread, own_spread=own)

    recall = over_used("recall", np.minimum)
    observations = over_used("observations", np.minimum)
    saturated = over_used("saturated", np.maximum)
    light, outside = series["light"].value, series["outside"].value
    with np.errstate(invalid="ignore", divide="ignore"):
        flare_share = np.where(light > 0, 1.0 - outside / light, np.nan)
        low_recall = recall < LOW_RECALL
        thin_units = observations < THIN_OBSERVATIONS
    share_max = np.where(np.isnan(flare_share).all(axis=0), 0.0, np.nanmax(np.where(np.isnan(flare_share), 0.0, flare_share), axis=0))
    return LongRecord(
        years=years, series=series, used=used, sources=[[k[0] for k in kept[y]] for y in years], chosen=chosen,
        recall=recall, observations=observations, saturated=saturated,
        drops=lit_drops(series["lit"].value, years), low_recall=low_recall, thin=thin_units, undetected=light == 0,
        flare_share=flare_share, outside_usable=share_max <= FLARE_SHARE_MAX, segment=(years >= UNTIED_FROM).astype(np.int8),
        dropped=[f"{s}{y}" for s, y in dropped],
        satellites={f"{s}{y}": {"light": float(r.light.sum()), "lit": float(r.lit.sum())} for (s, y), r in sorted(readings.items())},
        seen={f"{s}{y}": r.seen for (s, y), r in sorted(readings.items())},
    )


def flare_cells(outlines: str | Path, grid: Grid) -> NDArray[np.bool_]:
    """Cells of a grid touched by flare outlines.

    Parameters
    ----------
    outlines : str or Path
        A vector file of polygons, for example ``Flares_Indonesia_1.shp``,
        which NOAA published per country for the DMSP years (the Internet
        Archive keeps
        ``ngdc.noaa.gov/eog/interest/gas_flares_countries_shapefiles.html``;
        gone from NOAA's address in November 2026).
        Only read.
    grid : Grid

    Returns
    -------
    ndarray of bool, shape ``grid.shape``
        True where any part of an outline touches the cell. This differs on
        purpose from the cell-centre rule used for admin units
        (``ntl.zonal``): a mask should err towards taking a cell out.
    """
    import geopandas as gpd  # an optional dependency, as for ntl.zonal

    return flare_cells_from(gpd.read_file(outlines).to_crs(4326).geometry, grid)


def flare_cells_from(shapes, grid: Grid) -> NDArray[np.bool_]:
    """As :func:`flare_cells`, from polygons already read (any iterable of shapely geometries in degrees)."""
    from rasterio import features  # an optional dependency, as for ntl.zonal
    from rasterio.transform import from_origin

    transform = from_origin(grid.west, grid.north, grid.cell, grid.cell)
    return features.rasterize(((g, 1) for g in shapes), out_shape=grid.shape, transform=transform, all_touched=True, dtype="uint8").astype(bool)


def build(crops: str | Path, eog: str | Path, units: Mapping[str, NDArray], flares: NDArray[np.bool_] | None = None) -> dict[str, tuple[NDArray, LongRecord]]:
    """Read every satellite-year once and assemble the record of each admin level.

    Parameters
    ----------
    crops : str or Path
        Folder of ``FssYYYY.npz`` written by ``python -m ntl.dmsp``. Their
        grid decides which cells of EOG's files are read.
    eog : str or Path
        Folder of EOG's intercalibrated stable lights (global GeoTIFFs named
        ``FssYYYY...intercal.stable_lights.avg_vis.tif``). Only read.
    units : mapping of str to ndarray of int
        Per admin level, the unit code per cell of the cropped grid.
    flares : ndarray of bool, optional
        Cells touched by a flare outline (:func:`flare_cells`).

    Returns
    -------
    dict of str to (ndarray, LongRecord)
        Per level, the sorted unit codes and the record.

    Raises
    ------
    ValueError
        If the two folders do not hold the same satellite-years, a
        satellite-year has two files, a corrected file is not floating
        point, two corrected layers are identical (a wrong file under a right
        name), the crops are not all on one grid, or a unit map does not
        match that grid.
    """
    crops, eog = Path(crops), Path(eog)
    corrected_files: dict[Key, Path] = {}
    for path in sorted(eog.glob("F*intercal.stable_lights.avg_vis.tif")):
        key = dmsp.satellite_year(path.name)
        if key in corrected_files:
            raise ValueError(f"two intercalibrated files for {key[0]}{key[1]}: {corrected_files[key].name} and {path.name}")
        corrected_files[key] = path
    archived = {dmsp.satellite_year(p.name): p for p in sorted(crops.glob("F??????.npz"))}
    if not corrected_files or not archived:
        raise ValueError(f"no satellite-years found: {len(archived)} crops in {crops}, {len(corrected_files)} intercalibrated files in {eog}")
    if set(corrected_files) != set(archived):
        raise ValueError(f"satellite-years differ between {crops} and {eog}: {sorted(set(corrected_files) ^ set(archived))}")

    grid = dmsp.load_crop(next(iter(archived.values()))).grid
    for level, codes_map in units.items():
        if codes_map.shape != grid.shape:
            raise ValueError(f"unit map '{level}' has {codes_map.shape} cells, the crops have {grid.shape}")
    if flares is not None and flares.shape != grid.shape:
        raise ValueError(f"flare cells {flares.shape} do not match the crops' grid {grid.shape}")
    inside = np.zeros(grid.shape, dtype=bool)
    for codes_map in units.values():
        inside |= codes_map != c.NO_UNIT

    # only cells inside some unit are held, for every satellite-year at once: the steady cells need them all
    corrected, uncorrected, observations, digests = {}, {}, {}, {}
    for key in sorted(corrected_files):
        crop = dmsp.load_crop(archived[key])
        if crop.grid != grid:
            raise ValueError(f"{archived[key].name} is on another grid than the first crop; crop them all to one box")
        layer = dmsp.read_window(corrected_files[key], grid)
        if not np.issubdtype(layer.dtype, np.floating):
            raise ValueError(f"{corrected_files[key].name} is {layer.dtype}, not floating point: not an intercalibrated file")
        corrected[key], uncorrected[key], observations[key] = layer[inside], crop.stable[inside], crop.observations[inside]
        digest = hashlib.sha256(corrected[key].tobytes()).hexdigest()
        if digest in digests:
            raise ValueError(f"{corrected_files[key].name} holds the same values as {corrected_files[digests[digest]].name}: one of them is the wrong file")
        digests[digest] = key
    steady = steady_dim_cells(corrected)
    flare_inside = None if flares is None else flares[inside]

    out: dict[str, tuple[NDArray, LongRecord]] = {}
    for level, codes_map in units.items():
        level_units = codes_map[inside]
        codes = np.unique(level_units[level_units != c.NO_UNIT])
        readings = {key: unit_reading(corrected[key], uncorrected[key], observations[key], level_units, codes, flare_inside, steady[key]) for key in corrected}
        out[level] = (codes, assemble(readings))
        log.info("%s: %d units, %d years, satellite-years left out %s", level, codes.size, out[level][1].years.size, out[level][1].dropped or "none")
    return out


def save(record: LongRecord, codes: NDArray, path: str | Path, sources: Mapping[str, str] | None = None) -> Path:
    """Write one admin level's record to a ``.npz``; it appears under its name only when complete.

    Arrays written (``Y`` years, ``U`` units): ``codes`` (U), ``years`` (Y),
    ``segment`` (Y), ``used``, ``chosen``, ``recall``, ``observations``,
    ``saturated``, ``flare_share``, ``drops``, ``low_recall``, ``thin``,
    ``undetected`` (all Y by U), ``outside_usable`` (U), and per quantity
    ``<q>_value``, ``<q>_low``, ``<q>_high``, ``<q>_pair_low``,
    ``<q>_pair_high`` (Y by U), ``<q>_spread``, ``<q>_own_spread`` (U).
    ``light`` and ``outside`` are sums of corrected digital numbers, ``lit``
    and ``bright`` counts of 30 arc-second cells; spreads are natural logs.
    ``meta`` is a JSON string: the satellites per year, those left out, the
    observation count and national sums of each, every threshold of this module, and
    ``sources`` as given (file and folder names).

    Parameters
    ----------
    record : LongRecord
    codes : ndarray of int, shape (units,)
    path : str or Path
    sources : mapping of str to str, optional
        Where the inputs came from, written into ``meta``.

    Returns
    -------
    Path
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, NDArray] = {"codes": np.asarray(codes), "years": record.years, "segment": record.segment, "used": record.used, "chosen": record.chosen,
                                  "recall": record.recall.astype(np.float32), "observations": record.observations.astype(np.float32),
                                  "saturated": record.saturated.astype(np.float32), "flare_share": record.flare_share.astype(np.float32),
                                  "drops": record.drops, "low_recall": record.low_recall, "thin": record.thin, "undetected": record.undetected,
                                  "outside_usable": record.outside_usable}
    for quantity, one in record.series.items():
        for field in Series._fields:
            arrays[f"{quantity}_{field}"] = getattr(one, field)
    thresholds = {name: value for name, value in globals().items() if name.isupper() and isinstance(value, (int, float, dict, tuple))}
    thresholds["SATURATED_DN"] = dmsp.SATURATED_DN
    meta = {"sources_by_year": {int(y): s for y, s in zip(record.years, record.sources)}, "dropped": record.dropped, "satellites": record.satellites,
            "seen": {k: (None if np.isnan(v) else v) for k, v in record.seen.items()}, "thresholds": thresholds, "sources": dict(sources or {}),
            "band": "disagreement between satellites, not a confidence interval; see the module docstring of ntl.longrecord"}
    # ".part.npz", not ".npz.part": numpy would add ".npz" to a name that does not end with it
    temporary = path.with_name(path.stem + ".part.npz")
    try:
        np.savez_compressed(temporary, meta=json.dumps(meta, allow_nan=False), **arrays)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return path


def load(path: str | Path) -> tuple[NDArray, LongRecord, dict]:
    """Read a file written by :func:`save`.

    Returns
    -------
    (ndarray, LongRecord, dict)
        The unit codes, the record, and ``meta``.
    """
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta"]))
        series = {q: Series(**{f: z[f"{q}_{f}"] for f in Series._fields}) for q in QUANTITIES}
        years = z["years"]
        record = LongRecord(
            years=years, series=series, used=z["used"], sources=[meta["sources_by_year"][str(int(y))] for y in years], chosen=z["chosen"],
            recall=z["recall"].astype(np.float64), observations=z["observations"].astype(np.float64), saturated=z["saturated"].astype(np.float64),
            drops=z["drops"], low_recall=z["low_recall"], thin=z["thin"], undetected=z["undetected"], flare_share=z["flare_share"].astype(np.float64),
            outside_usable=z["outside_usable"], segment=z["segment"], dropped=list(meta["dropped"]), satellites=dict(meta.get("satellites", {})),
            seen={k: (float("nan") if v is None else v) for k, v in meta["seen"].items()},
        )
        return z["codes"], record, meta


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.longrecord",
        description="Yearly DMSP-OLS light per admin unit, 1992 to 2013, from EOG's intercalibrated files, with a disagreement band and flags.",
        epilog="example:\n"
        r"  python -m ntl.longrecord --crops E:\temp\ntl\dmsp --eog E:\temp\ntl\eog --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp" "\n"
        r"      --flares E:\temp\ntl\flares\Flares_Indonesia_1.shp --out E:\temp\ntl\longrecord",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--crops", required=True, type=Path, help="folder of FssYYYY.npz from python -m ntl.dmsp; their box is the box used")
    parser.add_argument("--eog", required=True, type=Path, help="folder of EOG's intercalibrated stable lights; only read")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--boundaries", type=Path, help="admin boundary file, as for python -m ntl.stack; the unit maps are made on the crops' grid")
    where.add_argument("--units", type=Path, help=".npz of unit codes per cell of the crops' grid, one array per admin level (made before with --keep-units)")
    parser.add_argument("--keep-units", type=Path, help="with --boundaries: also write the unit maps to this .npz, to pass as --units next time")
    parser.add_argument("--levels", nargs="+", default=["province", "district"], choices=list(c.ADMIN_LEVELS), help="admin levels (default: province district)")
    parser.add_argument("--flares", type=Path, help="flare outlines (polygons, for example Flares_Indonesia_1.shp from NOAA); without it 'outside' equals 'light'")
    parser.add_argument("--out", required=True, type=Path, help="folder for one dmsp_<level>.npz per level")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 on a problem with the inputs."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        first = sorted(args.crops.glob("F??????.npz"))
        if not first:
            raise ValueError(f"no FssYYYY.npz in {args.crops}")
        grid = dmsp.load_crop(first[0]).grid
        if args.units:
            with np.load(args.units, allow_pickle=False) as maps:
                units = {level: maps[level] for level in args.levels}
        else:
            from ntl import stack

            maps = stack.unit_maps_from_file(args.boundaries, grid)
            units = {level: maps[level] for level in args.levels}
            if args.keep_units:
                args.keep_units.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(args.keep_units, **maps)
        flares = flare_cells(args.flares, grid) if args.flares else None
        sources = {"crops": str(args.crops), "eog": str(args.eog), "units": str(args.units or args.boundaries), "flares": str(args.flares or ""),
                   "box": json.dumps(list(grid.bounds))}
        for level, (codes, record) in build(args.crops, args.eog, units, flares).items():
            log.info("%s: written %s", level, save(record, codes, args.out / f"dmsp_{level}.npz", sources))
    except ImportError as exc:
        log.error("%s: the long record needs rasterio, and geopandas for --boundaries and --flares (the 'zonal' extra)", exc)
        return 1
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
