"""When each lit cell became persistently lit, and how much of a unit is newly lit.

Works on cells, not units: the input is the monthly radiance of every cell
of the status domain (``ntl.stack.TileStack.usable``).

Method, in two steps, with thresholds picked for this project ([P], not from
a document, not yet reviewed by ``/method-critique``):

1. **One value per cell and calendar year**: the median of the year's usable
   monthly values (good quality, enough observations), if the year has at
   least ``MIN_MONTHS_PER_YEAR`` of them. A cell is *lit in a year* when
   that value is at least ``conventions.LIT_MIN_RADIANCE``.
2. **First-light year**: the earliest year from which the cell is lit in
   every later year that has a value, with at least ``MIN_LIT_YEARS`` lit
   years from then on (so that being lit in the final year alone does not
   count). A cell that is lit like this from its first year with a value
   was already lit when the record began: its first-light year is that
   year, and it is flagged ``from_start``.

What it does and does not describe:

- Only cells of the status domain are looked at, and that domain needs a
  mean of ``LIT_MIN_RADIANCE`` over the whole record. A cell that lit up
  in the last few years can fail that mean and be absent, so recent first
  light is undercounted, the more so the later it happened.
- "Lit" is a threshold on a yearly median. A cell hovering near the
  threshold can get a late first-light year from one dim year.
- A cell with no first-light year was lit on average but is not lit at
  the end of the record, or is too thinly observed to say.
"""

from __future__ import annotations

import warnings
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: Usable monthly values a cell needs in a calendar year for a yearly value. [P]
MIN_MONTHS_PER_YEAR = 3
#: Lit years, from the first-light year on, needed to call a cell persistently lit. [P]
MIN_LIT_YEARS = 2
#: Value stored for "no first-light year".
NO_YEAR = 0


def yearly_cell_medians(values: ArrayLike, years: ArrayLike, min_months: int = MIN_MONTHS_PER_YEAR) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
    """Median usable radiance of each cell in each calendar year.

    Parameters
    ----------
    values : array_like of float, shape ``(T, N)``
        Usable monthly radiance, nW cm-2 sr-1; NaN where not usable.
    years : array_like of int, shape ``(T,)``
        Calendar year of each row.
    min_months : int
        Usable months a cell needs in a year.

    Returns
    -------
    ndarray of int64, shape ``(Y,)``
        The distinct years, ascending.
    ndarray of float32, shape ``(Y, N)``
        Yearly medians; NaN where the cell has too few usable months.

    Raises
    ------
    ValueError
        If the shapes disagree.
    TypeError
        If ``years`` is not an integer array.
    """
    values = np.asarray(values)
    years = np.asarray(years)
    if years.dtype.kind not in "iu":
        raise TypeError(f"years must be integers, got dtype {years.dtype}")
    if values.ndim != 2 or years.shape != (values.shape[0],):
        raise ValueError(f"values has shape {values.shape}, years {years.shape}")
    distinct = np.unique(years).astype(np.int64)
    out = np.full((distinct.size, values.shape[1]), np.nan, dtype=np.float32)
    for i, year in enumerate(distinct):
        block = values[years == year]
        enough = np.isfinite(block).sum(axis=0) >= min_months
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # a cell with no usable month in a year is expected
            median = np.nanmedian(block, axis=0)
        out[i] = np.where(enough, median, np.nan)
    return distinct, out


class FirstLight(NamedTuple):
    """Result of :func:`first_light`. One value per cell.

    Attributes
    ----------
    year : ndarray of int64, shape ``(N,)``
        First-light year; ``NO_YEAR`` (0) where the cell has none.
    from_start : ndarray of bool, shape ``(N,)``
        True where the first-light year is the cell's first year with a
        value: the cell was already lit when its record began.
    """

    year: NDArray[np.int64]
    from_start: NDArray[np.bool_]


def first_light(
    yearly: ArrayLike,
    years: ArrayLike,
    lit_min: float = c.LIT_MIN_RADIANCE,
    min_lit_years: int = MIN_LIT_YEARS,
) -> FirstLight:
    """First year from which each cell stays lit.

    Parameters
    ----------
    yearly : array_like of float, shape ``(Y, N)``
        Yearly radiance per cell (:func:`yearly_cell_medians`); NaN where
        the year has no value.
    years : array_like of int, shape ``(Y,)``
        The calendar years, ascending.
    lit_min : float
        A cell is lit in a year when its value is at least this,
        nW cm-2 sr-1.
    min_lit_years : int
        Lit years needed from the first-light year on.

    Returns
    -------
    FirstLight

    Raises
    ------
    ValueError
        If the shapes disagree, there is no year, or the years are not
        ascending.
    TypeError
        If ``years`` is not an integer array.
    """
    yearly = np.asarray(yearly, dtype=np.float64)
    years = np.asarray(years)
    if years.dtype.kind not in "iu":
        raise TypeError(f"years must be integers, got dtype {years.dtype}")
    if yearly.ndim != 2 or years.shape != (yearly.shape[0],):
        raise ValueError(f"yearly has shape {yearly.shape}, years {years.shape}")
    if years.size == 0:
        raise ValueError("no year to look at")
    if np.any(np.diff(years) <= 0):
        raise ValueError("years must be ascending")
    has = np.isfinite(yearly)
    with np.errstate(invalid="ignore"):
        lit = has & (yearly >= lit_min)
    # stays[y]: in every year from y on, the cell is lit or has no value
    stays = np.logical_and.accumulate((lit | ~has)[::-1], axis=0)[::-1]
    lit_ahead = np.cumsum(lit[::-1], axis=0)[::-1]  # lit years from y on
    qualifies = lit & stays & (lit_ahead >= min_lit_years)
    any_year = qualifies.any(axis=0)
    first = np.argmax(qualifies, axis=0)
    first_valued = np.argmax(has, axis=0)
    year = np.where(any_year, years[first], NO_YEAR).astype(np.int64)
    return FirstLight(year=year, from_start=any_year & (first == first_valued))


class UnitNewLight(NamedTuple):
    """Per-unit counts from the cells' first-light years. One value per unit.

    Attributes
    ----------
    cells : ndarray of int64, shape ``(U,)``
        Cells of the unit.
    dated : ndarray of int64, shape ``(U,)``
        Cells with a first-light year.
    new : ndarray of int64, shape ``(U,)``
        Of those, cells whose first-light year is after ``since`` and that
        were not lit from the start of their record.
    median_year : ndarray of float64, shape ``(U,)``
        Median first-light year of the ``new`` cells; NaN if none.
    """

    cells: NDArray[np.int64]
    dated: NDArray[np.int64]
    new: NDArray[np.int64]
    median_year: NDArray[np.float64]


def unit_new_light(result: FirstLight, unit_position: ArrayLike, units: int, since: int) -> UnitNewLight:
    """Count each unit's newly lit cells.

    Parameters
    ----------
    result : FirstLight
        From :func:`first_light`.
    unit_position : array_like of int, shape ``(N,)``
        Position of each cell's unit, 0 to ``units - 1``; -1 for a cell in
        no unit of this level.
    units : int
        Number of units.
    since : int
        A cell is "new" when its first-light year is later than this.

    Returns
    -------
    UnitNewLight

    Raises
    ------
    ValueError
        If ``unit_position`` does not have one entry per cell, or names a
        unit at or beyond ``units``.
    """
    position = np.asarray(unit_position, dtype=np.int64)
    if position.shape != result.year.shape:
        raise ValueError(f"unit_position has shape {position.shape}, the cells {result.year.shape}")
    if position.size and position.max() >= units:
        raise ValueError(f"a cell is in unit {int(position.max())}, but there are only {units} units")
    inside = position >= 0
    dated = inside & (result.year != NO_YEAR)
    new = dated & ~result.from_start & (result.year > since)

    def count(mask: NDArray[np.bool_]) -> NDArray[np.int64]:
        return np.bincount(position[mask], minlength=units).astype(np.int64)

    median = np.full(units, np.nan)
    order = np.argsort(position[new], kind="stable")
    sorted_units, sorted_years = position[new][order], result.year[new][order]
    edges = np.searchsorted(sorted_units, np.arange(units + 1))
    for u in np.unique(sorted_units):
        median[u] = np.median(sorted_years[edges[u]:edges[u + 1]])
    return UnitNewLight(cells=count(inside), dated=count(dated), new=count(new), median_year=median)


# ---------------------------------------------------------------------------
# Then and now: the replacement for "newly lit" (method critique, 2026-11-23)
# ---------------------------------------------------------------------------
# The first-light year above measures crossing a line of 2 nW cm-2 sr-1: in
# the Java tile 97% of the cells it called new read between 1 and 2 the year
# before, a third to over half were restarts after a dim year, and the share
# moved from 55% to 71% when the line moved from 2 to 3. It is kept for
# reference and no longer exported. What is exported instead compares the
# first years of the record with the last, with a real gap between "dark"
# and "lit".

#: Calendar years at each end of the record that are compared. [P]
END_YEARS = 3
#: Yearly values a cell needs within an end period. [P]
MIN_END_YEARS = 2
#: A cell is dark in a period when its typical yearly value is under this,
#: nW cm-2 sr-1: the product stores radiance under 0.5 as zero.
DARK_MAX = 0.5
#: Classes of :func:`then_and_now`.
TN_UNKNOWN, TN_LIT_BOTH, TN_BRIGHTENED, TN_EMERGED, TN_FADED, TN_DIM_BOTH = 0, 1, 2, 3, 4, 5


def then_and_now(
    yearly: ArrayLike,
    years: ArrayLike,
    end_years: int = END_YEARS,
    min_end_years: int = MIN_END_YEARS,
    dark_max: float = DARK_MAX,
    lit_min: float = c.LIT_MIN_RADIANCE,
) -> NDArray[np.uint8]:
    """Class of each cell by its light at the start and at the end of the record.

    Parameters
    ----------
    yearly : array_like of float, shape ``(Y, N)``
        Yearly radiance per cell (:func:`yearly_cell_medians`), nW cm-2
        sr-1; NaN where the year has no value.
    years : array_like of int, shape ``(Y,)``
        The calendar years, ascending.
    end_years : int
        Years in each end period: the first and the last ``end_years``.
    min_end_years : int
        Yearly values a cell needs in each period.
    dark_max, lit_min : float
        "Then" and "now" are the medians of the cell's yearly values in
        the two periods. Dark is under ``dark_max``; lit is at least
        ``lit_min``; in between is dim.

    Returns
    -------
    ndarray of uint8, shape ``(N,)``
        ``TN_UNKNOWN`` (0) too few yearly values in either period;
        ``TN_LIT_BOTH`` (1) lit then and now;
        ``TN_BRIGHTENED`` (2) dim then, lit now;
        ``TN_EMERGED`` (3) dark then, lit now: light where there was none;
        ``TN_FADED`` (4) lit then, not lit now;
        ``TN_DIM_BOTH`` (5) everything else (not lit now and not lit then).

    Raises
    ------
    ValueError
        If the shapes disagree, the years are not ascending, or the record
        is shorter than two end periods.

    Notes
    -----
    Only cells of the status domain are looked at, which needs a mean of
    ``lit_min`` over the whole record: a cell that emerged in the last few
    years can fail that and be absent, so emergence is undercounted.
    """
    yearly = np.asarray(yearly, dtype=np.float64)
    years = np.asarray(years)
    if yearly.ndim != 2 or years.shape != (yearly.shape[0],):
        raise ValueError(f"yearly has shape {yearly.shape}, years {years.shape}")
    if np.any(np.diff(years) <= 0):
        raise ValueError("years must be ascending")
    if years.size < 2 * end_years:
        raise ValueError(f"the record has {years.size} years, fewer than two periods of {end_years}")

    def typical(block: NDArray[np.float64]) -> NDArray[np.float64]:
        enough = np.isfinite(block).sum(axis=0) >= min_end_years
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.where(enough, np.nanmedian(block, axis=0), np.nan)

    then, now = typical(yearly[:end_years]), typical(yearly[-end_years:])
    known = np.isfinite(then) & np.isfinite(now)
    with np.errstate(invalid="ignore"):
        lit_now, lit_then, dark_then = now >= lit_min, then >= lit_min, then < dark_max
    out = np.full(yearly.shape[1], TN_DIM_BOTH, dtype=np.uint8)
    out[lit_now & lit_then] = TN_LIT_BOTH
    out[lit_now & ~lit_then] = TN_BRIGHTENED
    out[lit_now & dark_then] = TN_EMERGED
    out[~lit_now & lit_then] = TN_FADED
    out[~known] = TN_UNKNOWN
    return out


def unit_class_counts(classes: ArrayLike, unit_position: ArrayLike, units: int) -> NDArray[np.int64]:
    """Cells of each unit in each class of :func:`then_and_now`.

    Parameters
    ----------
    classes : array_like of int, shape ``(N,)``
    unit_position : array_like of int, shape ``(N,)``
        Position of each cell's unit, 0 to ``units - 1``; -1 for none.
    units : int

    Returns
    -------
    ndarray of int64, shape ``(units, 6)``
        Column ``k`` counts the unit's cells of class ``k``.
    """
    classes = np.asarray(classes, dtype=np.int64)
    position = np.asarray(unit_position, dtype=np.int64)
    if position.shape != classes.shape:
        raise ValueError(f"unit_position has shape {position.shape}, the cells {classes.shape}")
    if position.size and position.max() >= units:
        raise ValueError(f"a cell is in unit {int(position.max())}, but there are only {units} units")
    inside = position >= 0
    flat = np.bincount(position[inside] * 6 + classes[inside], minlength=units * 6)
    return flat.reshape(units, 6).astype(np.int64)
