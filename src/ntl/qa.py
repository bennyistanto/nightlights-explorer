"""Decode Black Marble quality layers into plain masks.

Pure functions on arrays: no file access. Tables are in ``conventions`` and
come from the Black Marble User Guide, Collection 2.0 (Table 6 for
``QF_Cloud_Mask``, Table 9 for ``Mandatory_Quality_Flag``). The files repeat
them in a ``Description`` attribute (VNP46A2) or ``flag_meanings`` (VNP46A1,
cloud mask only), and those texts agree with the guide.

Three states are kept apart everywhere, because the monitor depends on it:

- **observed, usable**: a retrieval the caller's rule accepts;
- **observed, rejected**: a retrieval exists but the rule refuses it;
- **not observed**: no retrieval (fill). This is never "dark".

All functions take the layers **as stored** (``ntl.read.read_raw``), never
after scaling: a flag layer turned to float with NaN for fill would make
"not observed" look observed, so non-integer input is refused.
"""

from __future__ import annotations

from collections.abc import Collection

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: Codes returned by :func:`observation_state` (defined in ``conventions``).
NOT_OBSERVED: int = c.STATE_NOT_OBSERVED
REJECTED: int = c.STATE_REJECTED
USABLE: int = c.STATE_USABLE


def _unsigned(values: ArrayLike, what: str) -> NDArray[np.unsignedinteger]:
    """The input as an array, refused unless its dtype is unsigned integer."""
    array = np.asarray(values)
    if array.dtype.kind != "u":
        raise TypeError(f"{what} must be unsigned integer as stored in the file, got {array.dtype}")
    return array


def bit_field(packed: ArrayLike, field: tuple[int, int]) -> NDArray[np.uint8]:
    """Extract one bit field from ``QF_Cloud_Mask``.

    Parameters
    ----------
    packed : array_like of uint16, any shape
        Raw ``QF_Cloud_Mask`` values, fill 65535 included. A scalar works.
    field : (shift, width)
        One of the ``CM_*`` pairs in ``conventions``.

    Returns
    -------
    ndarray of uint8, same shape
        The field's value, 0 to ``2**width - 1``. Cells where the cloud mask
        is fill get ``conventions.DECODED_FILL`` (255): every bit of the fill
        value is set, so decoding it would read as "confident cloudy, shadow,
        cirrus, snow" and so on, which is false.

    Raises
    ------
    TypeError
        If the input is not an unsigned integer array.

    Notes
    -----
    User Guide Table 6. Bit 0 is the least significant; with the opposite
    order every cell of a real tile, sea included, decodes as land.
    """
    packed = _unsigned(packed, "QF_Cloud_Mask")
    shift, width = field
    decoded = ((packed >> shift) & ((1 << width) - 1)).astype(np.uint8)
    return np.where(packed == c.CLOUD_MASK_FILL, np.uint8(c.DECODED_FILL), decoded)


def cloud_confidence(packed: ArrayLike) -> NDArray[np.uint8]:
    """Cloud detection class from ``QF_Cloud_Mask`` bits 6 to 7.

    Parameters
    ----------
    packed : array_like of uint16
        Raw cloud mask.

    Returns
    -------
    ndarray of uint8
        0 confident clear, 1 probably clear, 2 probably cloudy, 3 confident
        cloudy, 255 where the mask is fill.
    """
    return bit_field(packed, c.CM_CLOUD_CONFIDENCE)


def land_water(packed: ArrayLike) -> NDArray[np.uint8]:
    """Background class from ``QF_Cloud_Mask`` bits 1 to 3.

    Parameters
    ----------
    packed : array_like of uint16
        Raw cloud mask.

    Returns
    -------
    ndarray of uint8
        0 land and desert, 1 land no desert, 2 inland water, 3 sea water,
        5 coastal, 255 where the mask is fill.
    """
    return bit_field(packed, c.CM_LAND_WATER)


def is_land(packed: ArrayLike, include_coastal: bool = True) -> NDArray[np.bool_]:
    """True on land cells according to one night's cloud mask.

    Parameters
    ----------
    packed : array_like of uint16
        Raw cloud mask.
    include_coastal : bool
        Whether the mixed "coastal" class counts as land. The choice must be
        stated with any statistic that uses it.

    Returns
    -------
    ndarray of bool
        False on inland water, sea water and where the mask is fill.

    Notes
    -----
    This is one night's classification, not a fixed land mask. Measured on
    tile h29v09 over 32 nights, 3.1% of cells change class from night to
    night, mostly along coasts. Build a stable land mask from the most
    frequent class over many nights, or from a static source.
    """
    lw = land_water(packed)
    land = (lw == c.LW_LAND_DESERT) | (lw == c.LW_LAND_NO_DESERT)
    return land | (lw == c.LW_COASTAL) if include_coastal else land


def composite_observed(quality: ArrayLike, good_only: bool = False) -> NDArray[np.bool_]:
    """True where a VNP46A3 or VNP46A4 composite cell rests on observations.

    Parameters
    ----------
    quality : array_like of uint8
        A ``*_Quality`` layer as stored.
    good_only : bool
        If True, accept only quality 0 (more than 3 observations). Default
        accepts 0 and 1 (at least one observation).

    Returns
    -------
    ndarray of bool
        False where the cell is gap filled (2) or fill (255).

    Raises
    ------
    TypeError
        If the input is not unsigned integer.

    Notes
    -----
    User Guide Table 12. A gap-filled cell carries a radiance taken from
    history, with zero observations in the period (checked on VNP46A3
    A2018213 h29v09: quality 2 always has ``_Num`` 0 and no ``_Std``). It
    cannot show a change, so it is "not observed" for status purposes.
    """
    quality = _unsigned(quality, "composite quality")
    if good_only:
        return quality == c.CQ_GOOD
    return (quality == c.CQ_GOOD) | (quality == c.CQ_POOR)


def observed(quality: ArrayLike) -> NDArray[np.bool_]:
    """True where VNP46A2 holds a retrieval (flag is not 255).

    Parameters
    ----------
    quality : array_like of uint8
        ``Mandatory_Quality_Flag`` as stored.

    Returns
    -------
    ndarray of bool

    Raises
    ------
    TypeError
        If the input is not unsigned integer (for example a float array
        with NaN for fill, where NaN would count as observed).

    Notes
    -----
    Measured on 32 files (tile h29v09, 2018-07-25 to 08-25): flag 255 and
    the radiance fill are exactly the same 94,113,110 cells.
    """
    return _unsigned(quality, "Mandatory_Quality_Flag") != c.MQF_FILL


def usable(quality: ArrayLike, allowed: Collection[int] = c.MQF_STRICT) -> NDArray[np.bool_]:
    """True where the quality flag is one of ``allowed``.

    Parameters
    ----------
    quality : array_like of uint8
        ``Mandatory_Quality_Flag`` as stored.
    allowed : collection of int
        Accepted flag values. Default: 0 only (high quality). Passing
        ``{0, 1}`` admits outliers and possible cloud contamination, which
        the user guide classes as poor quality; say so wherever the result
        is shown.

    Returns
    -------
    ndarray of bool

    Raises
    ------
    TypeError
        If the input is not unsigned integer.
    ValueError
        If ``allowed`` contains the fill value: a missing retrieval can
        never be usable.
    """
    if c.MQF_FILL in allowed:
        raise ValueError("the fill value 255 cannot be an allowed quality flag")
    return np.isin(_unsigned(quality, "Mandatory_Quality_Flag"), list(allowed))


def observation_state(quality: ArrayLike, allowed: Collection[int] = c.MQF_STRICT) -> NDArray[np.uint8]:
    """Three-way state per cell: not observed, rejected, usable.

    Parameters
    ----------
    quality : array_like of uint8
        ``Mandatory_Quality_Flag`` as stored.
    allowed : collection of int
        As for :func:`usable`.

    Returns
    -------
    ndarray of uint8
        ``NOT_OBSERVED`` (0), ``REJECTED`` (1) or ``USABLE`` (2).
    """
    state = np.full(np.shape(quality), NOT_OBSERVED, dtype=np.uint8)
    state[observed(quality)] = REJECTED
    state[usable(quality, allowed)] = USABLE
    return state
