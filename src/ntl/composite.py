"""Building blocks on the monthly composites (VNP46A3): a fixed land mask
and a three-month seasonal composite.

Pure functions on arrays; reading files is ``ntl.read``'s job.

Why these exist (measured on all 179 months, 2026-11-22; tables in
``temp/national-tiles.md`` and ``temp/view-class-critique.md``):

- The ``Land_Water_Mask`` inside each monthly file is fill exactly where
  the month's AllAngle quality is fill (it does carry a class on gap-filled
  cells). A per-file mask therefore shrinks in cloudy months and flatters
  them. A tile needs one mask, built from every month.
- Averaged over the years, 0 to 9 calendar months a year have under half
  of the lit cells usable in a single month, depending on the tile (ten
  tiles; the eleventh has too few lit cells to say). Pooling three months
  brings that to none in any of the ten, again as an average over years:
  the lowest are 51% (h31v09, February) and 53% (h28v09, January), and
  single windows still fall under half (8 of 175 in h29v09, 19 in h31v09).
- The pooled value is a season, not a month: in tile h29v09 only 24 to 30%
  of a November to February window's nights come from its centre month. So
  results must carry the three month names, never one.

Memory: these functions work on whatever they are given. A whole tile for
all months is 179 x 2400 x 2400 values, about 8 GB per float64 array, and
:func:`three_month` allocates several. Pass the cells of interest (lit
cells, a window) or a few months at a time.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: Land and water classes that can occur in a mask, in voting order. The
#: order also settles ties (picked; 35 to 96 cells per tile tie).
_CLASSES: tuple[int, ...] = (
    c.LW_LAND_DESERT,
    c.LW_LAND_NO_DESERT,
    c.LW_INLAND_WATER,
    c.LW_SEA_WATER,
    c.LW_COASTAL,
)


def new_class_votes(shape: tuple[int, ...]) -> NDArray[np.uint16]:
    """Empty vote counter for :func:`add_class_votes`.

    Parameters
    ----------
    shape : tuple of int
        Shape of one mask, for example ``(2400, 2400)``.

    Returns
    -------
    ndarray of uint16, shape ``(5,) + shape``
        One layer per class (land and desert, land no desert, inland water,
        sea water, coastal), all zero.
    """
    return np.zeros((len(_CLASSES), *shape), dtype=np.uint16)


def add_class_votes(votes: NDArray[np.uint16], mask: ArrayLike) -> None:
    """Count one month's ``Land_Water_Mask`` into the votes, in place.

    Parameters
    ----------
    votes : ndarray of uint16
        From :func:`new_class_votes`.
    mask : array_like of uint8
        One month's mask as stored. Fill (255) and undefined values vote for
        nothing.

    Raises
    ------
    ValueError
        If the mask does not have the shape of one layer of ``votes``.
    """
    mask = np.asarray(mask)
    if votes.ndim < 1 or votes.shape[0] != len(_CLASSES) or mask.shape != votes.shape[1:]:
        raise ValueError(f"mask of shape {mask.shape} does not fit votes of shape {votes.shape}")
    for i, cls in enumerate(_CLASSES):
        votes[i] += mask == cls


def modal_class(votes: NDArray[np.uint16]) -> NDArray[np.uint8]:
    """Most frequent land and water class of each cell over all months.

    Parameters
    ----------
    votes : ndarray of uint16
        Filled by :func:`add_class_votes`.

    Returns
    -------
    ndarray of uint8
        Class code per cell (0, 1, 2, 3 or 5), or
        ``conventions.LAND_WATER_FILL`` (255) where no month ever classified
        the cell. On a tie the class earlier in the order land and desert,
        land no desert, inland water, sea water, coastal wins.

    Raises
    ------
    ValueError
        If ``votes`` does not have one layer per class.

    Notes
    -----
    The two land classes are counted separately, so a cell that is land in
    most months but split between them could lose to a single water class.
    Class 0 (land and desert) is absent or negligible in the Indonesian
    tiles read, so this has not mattered.
    """
    if votes.ndim < 1 or votes.shape[0] != len(_CLASSES):
        raise ValueError(f"votes must have {len(_CLASSES)} layers, got shape {votes.shape}")
    modal = np.asarray(_CLASSES, dtype=np.uint8)[votes.argmax(axis=0)]
    modal[votes.sum(axis=0) == 0] = c.LAND_WATER_FILL
    return modal


def is_fixed_land(modal: ArrayLike, include_coastal: bool = False) -> NDArray[np.bool_]:
    """True where the fixed class is land.

    Named apart from ``qa.is_land``, which reads one night's cloud mask and
    includes the coast by default; this one reads the fixed mask and leaves
    the coast out by default.

    Parameters
    ----------
    modal : array_like of uint8
        From :func:`modal_class`.
    include_coastal : bool
        Whether mixed coastal cells count. Default False: status excludes
        the coast, where the product's own quality rule differs.

    Returns
    -------
    ndarray of bool
    """
    modal = np.asarray(modal)
    land = (modal == c.LW_LAND_DESERT) | (modal == c.LW_LAND_NO_DESERT)
    return land | (modal == c.LW_COASTAL) if include_coastal else land


class Seasonal(NamedTuple):
    """Result of :func:`three_month`.

    Attributes
    ----------
    value : ndarray of float64
        Night-weighted mean radiance over the window, nW cm-2 sr-1. NaN
        where the window holds no observed night, and on the first and last
        time step, whose windows are incomplete.
    nights : ndarray of float64
        Nights behind each value (sum over the window). 0 where NaN.
    centre_share : ndarray of float64
        Share of those nights that fall in the centre month, 0 to 1. NaN
        where ``nights`` is 0. A low share means the value describes the
        neighbouring months more than the centre one.
    """

    value: NDArray[np.float64]
    nights: NDArray[np.float64]
    centre_share: NDArray[np.float64]


def three_month(values: ArrayLike, nights: ArrayLike, observed: ArrayLike) -> Seasonal:
    """Pool each month with its two neighbours, weighting by nights.

    For time step ``t`` the result is
    ``sum(value * nights) / sum(nights)`` over ``t-1, t, t+1``, using only
    months that were observed.

    Parameters
    ----------
    values : array_like of float, shape ``(T, ...)``
        Monthly composite radiance, consecutive calendar months along axis
        0. Units nW cm-2 sr-1. Entries where ``observed`` is False are
        ignored whatever they hold.
    nights : array_like, shape ``(T, ...)``
        Observations behind each monthly value (the ``_Num`` layer, with
        its fill already set to 0).
    observed : array_like of bool, shape ``(T, ...)``
        True where the monthly value rests on observations: use
        ``qa.composite_observed`` on the ``_Quality`` layer. Gap-filled
        months must be False: they carry a number but no night.

    Returns
    -------
    Seasonal

    Raises
    ------
    ValueError
        If the three inputs differ in shape or there are fewer than three
        time steps.

    Notes
    -----
    The caller is responsible for the months being consecutive: a missing
    month must be present as a row with ``observed`` False. The inputs are
    trusted as described: a ``_Num`` fill (65535) or a radiance fill left in
    a cell marked observed would be averaged in. Set the fill of ``_Num``
    to 0 (``conventions.COMPOSITE_NUM_FILL``) and read radiance with
    ``read_scaled`` first.

    Weighting by nights makes the value the mean over the nights that were
    seen, as if they had been composited together. It does not repeat the
    product's outlier removal across the three months.
    """
    values = np.asarray(values, dtype=np.float64)
    nights = np.asarray(nights, dtype=np.float64)
    observed = np.asarray(observed, dtype=bool)
    if not (values.shape == nights.shape == observed.shape):
        raise ValueError(f"shapes differ: {values.shape}, {nights.shape}, {observed.shape}")
    if values.shape[0] < 3:
        raise ValueError("need at least three consecutive months")

    use = observed & np.isfinite(values) & (nights > 0)
    w = np.where(use, nights, 0.0)
    wv = np.where(use, values * nights, 0.0)

    total = np.zeros_like(w)
    weighted = np.zeros_like(w)
    total[1:-1] = w[:-2] + w[1:-1] + w[2:]
    weighted[1:-1] = wv[:-2] + wv[1:-1] + wv[2:]

    has = total > 0
    safe = np.where(has, total, 1.0)
    return Seasonal(
        value=np.where(has, weighted / safe, np.nan),
        nights=total,
        centre_share=np.where(has, w / safe, np.nan),
    )
