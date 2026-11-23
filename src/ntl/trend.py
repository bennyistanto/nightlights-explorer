"""Long-run change in a unit's light: a robust slope with its uncertainty.

The series is the unit's log index (``ntl.monitor.LevelSeries.index``):
the natural logarithm of the light of the unit's lit cells over their usual
light, on the cells seen that month. A slope of that series is a rate of
change in percent per year.

Method, in two steps:

1. **One value per calendar year**: the median of the year's monthly values,
   if the year has enough of them. A median damps the time of year (it
   does not remove it: a year's value uses whichever months were observed)
   and is not moved by one hazy or half-seen month.
2. **Theil-Sen slope** over those yearly values: the median of the slopes
   between every pair of years (Theil 1950; Sen 1968). A confidence
   interval comes from the same pairwise slopes, using the variance of
   Kendall's S statistic (Sen 1968; the form in Gilbert 1987, "Statistical
   Methods for Environmental Pollution Monitoring", section 16.5, as
   quoted by EnvStats ``kendallTrendTest`` and PNNL's Visual Sample Plan
   help; the originals were not opened, [U]). Yearly values of a unit are
   correlated from one year to the next: the residuals of the national
   run have a lag-1 autocorrelation of about 0.55 after small-sample bias
   correction (method critique, 2026-11-23). The variance of S is
   therefore multiplied by ``(1 + r) / (1 - r)`` with that pooled ``r``
   (``SERIAL_CORRELATION``), the usual first-order correction for an
   AR(1) series. It is one pooled value, not each unit's own, so the
   interval is still approximate, and with the ranks rounded outward it
   errs on the wide side: on simulated trendless series of 14 years with
   that correlation about 3% are called a trend at the 90% level, against
   about a third with the classical interval (the module's tests). No
   correction for ties.

What it does and does not describe:

- Only cells that are lit on average over the record are in the index
  (``ntl.stack.lit_domain``). Light that appears in cells outside that
  domain is not counted, so growth by spreading is understated.
- The index is like-for-like within a month, not across sensors: the whole
  record is VIIRS, one product collection.
- A slope over the whole record says nothing about when the change
  happened.

The thresholds are picked ([P]) and not yet reviewed by ``/method-critique``.
"""

from __future__ import annotations

import warnings
from statistics import NormalDist
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

#: Monthly values a calendar year needs for a yearly value. [P]
MIN_MONTHS_PER_YEAR = 6
#: Yearly values a unit needs for a slope. [P]
MIN_YEARS = 8
#: Confidence level of the interval. [P]
CONFIDENCE = 0.90
#: Lag-1 autocorrelation of yearly residuals assumed when widening the
#: interval. [B] pooled over the national run (critique of 2026-11-23:
#: median 0.53 to 0.60 by level after bias correction).
SERIAL_CORRELATION = 0.55


def yearly_medians(values: ArrayLike, years: ArrayLike, min_months: int = MIN_MONTHS_PER_YEAR) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Median of each calendar year's monthly values.

    Parameters
    ----------
    values : array_like of float, shape ``(T,)`` or ``(T, U)``
        Monthly values; NaN where there is none.
    years : array_like of int, shape ``(T,)``
        Calendar year of each row.
    min_months : int
        Finite values a year needs; with fewer its median is NaN.

    Returns
    -------
    ndarray of int64, shape ``(Y,)``
        The distinct years, ascending.
    ndarray of float64, shape ``(Y,)`` or ``(Y, U)``
        Yearly medians; NaN where the year has too few values.

    Raises
    ------
    ValueError
        If the shapes disagree.
    TypeError
        If ``years`` is not an integer array.
    """
    values = np.asarray(values, dtype=np.float64)
    years = np.asarray(years)
    if years.dtype.kind not in "iu":
        raise TypeError(f"years must be integers, got dtype {years.dtype}")
    if values.ndim == 0:
        raise ValueError("values must have a row per month")
    if years.ndim != 1 or values.shape[0] != years.shape[0]:
        raise ValueError(f"values has {values.shape[0]} rows, years has shape {years.shape}")
    distinct = np.unique(years).astype(np.int64)
    out = np.full((distinct.size, *values.shape[1:]), np.nan)
    for i, year in enumerate(distinct):
        block = values[years == year]
        enough = np.isfinite(block).sum(axis=0) >= min_months
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # a year with no value at all is expected
            median = np.nanmedian(np.where(np.isfinite(block), block, np.nan), axis=0) if block.size else np.nan
        out[i] = np.where(enough, median, np.nan)
    return distinct, out


class Slope(NamedTuple):
    """A Theil-Sen slope with its interval.

    Attributes
    ----------
    slope : float
        Median pairwise slope, in units of ``y`` per unit of ``x``; NaN if
        there are too few points.
    low, high : float
        Bounds of the confidence interval; NaN where ``slope`` is.
    points : int
        Finite points used.
    """

    slope: float
    low: float
    high: float
    points: int


def theil_sen(
    x: ArrayLike,
    y: ArrayLike,
    min_points: int = MIN_YEARS,
    confidence: float = CONFIDENCE,
    serial: float = SERIAL_CORRELATION,
) -> Slope:
    """Theil-Sen slope of ``y`` on ``x`` with a confidence interval.

    Parameters
    ----------
    x, y : array_like of float, shape ``(n,)``
        Points; a pair with a NaN in either is left out. ``x`` values must
        be distinct among the points used.
    min_points : int
        Points needed; with fewer the result is NaN.
    confidence : float
        Two-sided level of the interval, strictly between 0 and 1.
    serial : float
        Lag-1 autocorrelation of the residuals, from 0 up to but not
        including 1. The variance of S is multiplied by
        ``(1 + serial) / (1 - serial)``; 0 gives the classical interval
        for independent points.

    Returns
    -------
    Slope

    Raises
    ------
    ValueError
        If the shapes differ, ``confidence`` or ``serial`` is out of range,
        or two used points share an ``x``.

    Notes
    -----
    With ``N = n(n-1)/2`` pairwise slopes sorted ascending and
    ``C = z * sqrt(n(n-1)(2n+5)/18)``, the interval runs from the slope of
    rank ``(N - C)/2`` to the one of rank ``(N + C)/2 + 1`` (ranks from 1,
    rounded outward, the lower down and the upper up, then kept inside the
    list; Gilbert interpolates instead). The normal approximation behind
    ``C`` is usually recommended from about 10 points; with the 8 or 9 that
    ``MIN_YEARS`` allows the interval is rougher still, and with very few
    points both ranks fall on the ends of the list, so the "interval" is
    just the smallest and largest pairwise slope. No correction for ties in
    ``y`` or for serial correlation.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError(f"x and y must be one-dimensional and of equal length, got {x.shape} and {y.shape}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be strictly between 0 and 1, got {confidence}")
    if not 0.0 <= serial < 1.0:
        raise ValueError(f"serial must be at least 0 and under 1, got {serial}")
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    n = int(x.size)
    if n < max(min_points, 2):
        return Slope(np.nan, np.nan, np.nan, n)
    i, j = np.triu_indices(n, k=1)
    dx = x[j] - x[i]
    if np.any(dx == 0):
        raise ValueError("two points share the same x")
    slopes = np.sort((y[j] - y[i]) / dx)
    total = slopes.size
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    half = z * np.sqrt(n * (n - 1) * (2 * n + 5) / 18.0 * (1.0 + serial) / (1.0 - serial))
    lower_rank = int(np.floor((total - half) / 2.0))          # 1-based rank, rounded down
    upper_rank = int(np.ceil((total + half) / 2.0)) + 1        # 1-based rank, rounded up
    low = slopes[min(max(lower_rank, 1), total) - 1]
    high = slopes[min(max(upper_rank, 1), total) - 1]
    return Slope(float(np.median(slopes)), float(low), float(high), n)


class UnitTrends(NamedTuple):
    """Trend of every unit. One value per unit; rates are fractions per year.

    Attributes
    ----------
    rate, low, high : ndarray of float64, shape ``(U,)``
        ``exp(slope) - 1`` of the log index per year, and the same for the
        interval's bounds: 0.03 is 3% a year. NaN where the unit has too
        few yearly values.
    years : ndarray of int64, shape ``(U,)``
        Yearly values used.
    first_year, last_year : int
        Calendar years the slopes can draw on; both 0 for an empty record.
    """

    rate: NDArray[np.float64]
    low: NDArray[np.float64]
    high: NDArray[np.float64]
    years: NDArray[np.int64]
    first_year: int
    last_year: int


def unit_trends(
    index: ArrayLike,
    years: ArrayLike,
    min_months: int = MIN_MONTHS_PER_YEAR,
    min_years: int = MIN_YEARS,
    confidence: float = CONFIDENCE,
    serial: float = SERIAL_CORRELATION,
) -> UnitTrends:
    """Rate of change of each unit's light over the record.

    Parameters
    ----------
    index : array_like of float, shape ``(T, U)``
        Log index per window and unit (``LevelSeries.index``); NaN where
        the unit has no value.
    years : array_like of int, shape ``(T,)``
        Calendar year of each window.
    min_months, min_years, confidence
        As :func:`yearly_medians` and :func:`theil_sen`.

    Returns
    -------
    UnitTrends

    Raises
    ------
    ValueError
        If ``index`` is not two-dimensional or does not match ``years``.
    TypeError
        If ``years`` is not an integer array.
    """
    index = np.asarray(index, dtype=np.float64)
    if index.ndim != 2:
        raise ValueError(f"index must have shape (T, U), got {index.shape}")
    distinct, medians = yearly_medians(index, years, min_months)
    units = index.shape[1]
    rate, low, high = (np.full(units, np.nan) for _ in range(3))
    used = np.zeros(units, dtype=np.int64)
    x = distinct.astype(np.float64)
    for u in range(units):
        result = theil_sen(x, medians[:, u], min_years, confidence, serial)
        used[u] = result.points
        if np.isfinite(result.slope):
            rate[u], low[u], high[u] = np.expm1([result.slope, result.low, result.high])
    return UnitTrends(rate=rate, low=low, high=high, years=used,
                      first_year=int(distinct[0]) if distinct.size else 0, last_year=int(distinct[-1]) if distinct.size else 0)
