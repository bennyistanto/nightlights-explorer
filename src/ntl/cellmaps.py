"""Monthly classes for every lit cell: what the map draws pixel by pixel.

Three things are said about each cell of the status domain in each month,
each as a small class so that all three fit one byte:

- **radiance**: how bright the cell was (3 bits);
- **change**: its radiance against the same calendar month a year earlier
  (3 bits);
- **observations**: how many observations stand behind the monthly value
  (2 bits).

These are descriptions of single cells, not statistics of units, and no
status is judged from them. A cell is 15 arc-seconds, but the sensor's
footprint is wider (about 750 m at nadir, per the product's documentation
as recorded in the project skill), so one cell's value is not independent
of its neighbours': read patterns, not single pixels.

Classes and breaks are picked for display ([P]). Radiance and change use
only *usable* values (good quality with enough observations,
``TileStack.usable``); the observation class counts every observation the
product reports, usable or not, so that it shows why a value is missing.

Change against a year earlier is the simplest comparison that removes the
time of year. It does not remove growth: where lights grow by several
percent a year, "brighter than a year ago" is the normal state.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: Radiance classes: code 0 = no usable value, 1 = no detectable light (the
#: product stores radiance under 0.5 as zero), then one class per interval
#: of these breaks, nW cm-2 sr-1. [P]
RADIANCE_BREAKS: Final[tuple[float, ...]] = (2.0, 5.0, 10.0, 20.0, 40.0)
#: Change classes: code 0 = no comparison (either month has no usable
#: value), then one class per interval of these ratios (this month over the
#: same month a year earlier). [P] The middle class is "about the same".
CHANGE_BREAKS: Final[tuple[float, ...]] = (0.5, 0.7, 0.85, 1.15, 1.4, 2.0)
#: Observation classes: code 0 = none, then one class per interval. [P]
#: The first break is ``conventions.MIN_NIGHTS``, so classes 2 and 3 are the
#: ones that can carry a usable value.
OBSERVATION_BREAKS: Final[tuple[int, ...]] = (c.MIN_NIGHTS, 10)
#: Bit layout of the packed byte.
RADIANCE_SHIFT, CHANGE_SHIFT, OBSERVATION_SHIFT = 0, 3, 6
RADIANCE_MASK, CHANGE_MASK, OBSERVATION_MASK = 0b111, 0b111, 0b11
#: Months between the two values compared by :func:`change_class`.
YEAR_LAG: Final[int] = 12


def radiance_class(values: ArrayLike) -> NDArray[np.uint8]:
    """Class of each usable radiance value.

    Parameters
    ----------
    values : array_like of float
        Usable radiance, nW cm-2 sr-1; NaN where not usable.

    Returns
    -------
    ndarray of uint8, same shape
        0 where NaN; 1 where the value is 0 or below (no detectable light;
        the product stores no negative radiance); 2 for a value above 0 and
        under the first break; then 3 to 7, one per
        further interval, a value equal to a break going to the higher class.
    """
    values = np.asarray(values, dtype=np.float64)
    out = (np.digitize(values, RADIANCE_BREAKS) + 2).astype(np.uint8)
    with np.errstate(invalid="ignore"):
        out[values <= 0] = 1
    out[~np.isfinite(values)] = 0
    return out


def change_class(values: ArrayLike, lag: int = YEAR_LAG) -> NDArray[np.uint8]:
    """Class of each value against the value ``lag`` rows earlier.

    Parameters
    ----------
    values : array_like of float, shape ``(T, ...)``
        Usable radiance in time order, consecutive months; NaN where not
        usable.
    lag : int
        Rows between the two values: 12 for "the same month a year earlier".

    Returns
    -------
    ndarray of uint8, same shape
        0 where either value is missing (always in the first ``lag``
        rows). Otherwise 1 to 7 by the ratio now over then: 1 under 0.5,
        4 from 0.85 to under 1.15 (about the same), 7 at 2.0 or more. Both
        zero is "about the same" (4); light where there was none is 7; no
        light where there was some is 1.

    Raises
    ------
    ValueError
        If ``lag`` is not positive.
    """
    if lag < 1:
        raise ValueError(f"lag must be at least 1, got {lag}")
    values = np.asarray(values, dtype=np.float64)
    out = np.zeros(values.shape, dtype=np.uint8)
    if values.shape[0] <= lag:
        return out
    now, then = values[lag:], values[:-lag]
    both = np.isfinite(now) & np.isfinite(then)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(then > 0, now / then, np.where(now > 0, np.inf, 1.0))
    classes = (np.digitize(ratio, CHANGE_BREAKS) + 1).astype(np.uint8)
    out[lag:] = np.where(both, classes, 0)
    return out


def observation_class(counts: ArrayLike) -> NDArray[np.uint8]:
    """Class of each count of observations.

    Parameters
    ----------
    counts : array_like of int
        Observations behind a monthly value; 0 where none.

    Returns
    -------
    ndarray of uint8, same shape
        0 for none, 1 for 1 to 3, 2 for 4 to 9, 3 for 10 or more.
    """
    counts = np.asarray(counts)
    out = (np.digitize(counts, OBSERVATION_BREAKS) + 1).astype(np.uint8)
    out[counts <= 0] = 0
    return out


def pack(values: ArrayLike, counts: ArrayLike, lag: int = YEAR_LAG) -> NDArray[np.uint8]:
    """The three classes of every cell-month in one byte.

    Parameters
    ----------
    values : array_like of float, shape ``(T, N)``
        Usable radiance, consecutive months; NaN where not usable.
    counts : array_like of int, shape ``(T, N)``
        Observations behind each monthly value.
    lag : int
        As :func:`change_class`.

    Returns
    -------
    ndarray of uint8, shape ``(T, N)``
        Bits 0 to 2 the radiance class, bits 3 to 5 the change class, bits
        6 and 7 the observation class.

    Raises
    ------
    ValueError
        If the two shapes differ.
    """
    values = np.asarray(values)
    counts = np.asarray(counts)
    if values.shape != counts.shape:
        raise ValueError(f"values has shape {values.shape}, counts {counts.shape}")
    return (radiance_class(values) << RADIANCE_SHIFT | change_class(values, lag) << CHANGE_SHIFT
            | observation_class(counts) << OBSERVATION_SHIFT).astype(np.uint8)


def unpack(packed: ArrayLike) -> tuple[NDArray[np.uint8], NDArray[np.uint8], NDArray[np.uint8]]:
    """The three classes from the packed byte: what the page does, in Python.

    Parameters
    ----------
    packed : array_like of uint8
        From :func:`pack`.

    Returns
    -------
    tuple of three ndarrays of uint8, each of the input's shape
        Radiance class, change class, observation class.
    """
    packed = np.asarray(packed, dtype=np.uint8)
    return ((packed >> RADIANCE_SHIFT) & RADIANCE_MASK, (packed >> CHANGE_SHIFT) & CHANGE_MASK,
            (packed >> OBSERVATION_SHIFT) & OBSERVATION_MASK)
