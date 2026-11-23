"""From grid cells to admin units: which unit a cell belongs to, and sums
over units that say how much of the unit was actually seen.

Levels and names (owner, 2026-11-22): province (adm1, ``a1siak``),
district (adm2, ``a2siak``), sub-district (adm3, ``a3siak``). The codes
nest by prefix (``conventions.ADMIN_DIVISOR``). Code 0 means "no unit at
this level". Codes are integers: a float or a negative code is refused
rather than rounded.

A cell belongs to the unit whose polygon contains the cell's centre
(checked against a point-in-polygon test on 35,000 cells of tile h29v09,
no mismatch).

A code of 0 at one level means the area is held by the level above (owner,
2026-11-22): a feature with ``a3siak`` 0 and a district code lies in that
district and in no sub-district. :func:`resolve_levels` applies the rule.
State of the adm3 file after the owner's corrections of 2026-11-22 (20:11),
re-measured by the method review: 7,278 features with a sub-district, 15
held by a district, 10 by a province, 1 with no code at all; 38 province
codes; :func:`province_conflicts` finds nothing. Before the corrections
three province-held features carried a wrong province code (history in
``temp/boundary-issues.md``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl.read import Grid


def integer_codes(codes: ArrayLike, what: str = "unit codes") -> NDArray[np.int64]:
    """Codes as int64, refused unless they are non-negative integers.

    Parameters
    ----------
    codes : array_like
        Unit codes.
    what : str
        Name used in the error message.

    Returns
    -------
    ndarray of int64

    Raises
    ------
    TypeError
        If the dtype is not integer (floats are never truncated).
    ValueError
        If a code is negative.
    """
    array = np.asarray(codes)
    if array.dtype.kind not in "iu":
        raise TypeError(f"{what} must be integers, got {array.dtype}")
    array = array.astype(np.int64)
    if array.size and array.min() < 0:
        raise ValueError(f"{what} must not be negative")
    return array


def to_level(subdistrict_codes: ArrayLike, level: str) -> NDArray[np.int64]:
    """Code of the province, district or sub-district a sub-district code belongs to.

    Parameters
    ----------
    subdistrict_codes : array_like of int
        ``a3siak`` codes, for example 520801. 0 means no unit.
    level : str
        ``"province"``, ``"district"`` or ``"subdistrict"``.

    Returns
    -------
    ndarray of int64
        ``a1siak`` (52), ``a2siak`` (5208) or the code itself. 0 stays 0.

    Raises
    ------
    ValueError
        If the level is unknown or a code is negative.
    TypeError
        If the codes are not integers.
    """
    if level not in c.ADMIN_DIVISOR:
        raise ValueError(f"unknown level {level!r}; expected one of {c.ADMIN_LEVELS}")
    return integer_codes(subdistrict_codes, "sub-district codes") // c.ADMIN_DIVISOR[level]


def resolve_levels(province: ArrayLike, district: ArrayLike, subdistrict: ArrayLike) -> dict[str, NDArray[np.int64]]:
    """Code of each feature at each admin level, where 0 defers to the level above.

    Parameters
    ----------
    province, district, subdistrict : array_like of int, same length
        ``a1siak``, ``a2siak`` and ``a3siak`` of each feature of the
        sub-district boundary file. 0 means the feature has no code at that
        level.

    Returns
    -------
    dict of str to ndarray of int64
        Keys ``"province"``, ``"district"``, ``"subdistrict"``. For each
        feature: the sub-district code as stored; the district code from the
        sub-district code's leading digits, or the stored district code
        where the sub-district code is 0; the province code from the
        district code's leading digits, or the stored province code where
        both are 0.

    Raises
    ------
    ValueError
        If the lengths differ, a code is negative, or a stored district or
        province code contradicts the leading digits of a finer code that
        is present (for example sub-district 520801 with district 5207).
    TypeError
        If the codes are not integers.

    Notes
    -----
    A feature with sub-district 0 and district 1218 lies in district 1218
    and in no sub-district: its cells count toward the district and the
    province. Finer codes take precedence because they nest by prefix on
    every coded feature of the file; the stored province code is used only
    where nothing finer exists, so check those with
    :func:`province_conflicts`.
    """
    a1 = integer_codes(province, "province codes")
    a2 = integer_codes(district, "district codes")
    a3 = integer_codes(subdistrict, "sub-district codes")
    if not (a1.shape == a2.shape == a3.shape and a1.ndim == 1):
        raise ValueError("province, district and sub-district codes must be one-dimensional and of equal length")
    step_down = c.ADMIN_DIVISOR["district"]
    step_up = c.ADMIN_DIVISOR["province"] // c.ADMIN_DIVISOR["district"]
    from_subdistrict = a3 // step_down
    bad = (a3 > 0) & (a2 > 0) & (from_subdistrict != a2)
    if bad.any():
        i = int(np.nonzero(bad)[0][0])
        raise ValueError(f"feature {i}: sub-district {a3[i]} does not start with its district {a2[i]}")
    district_out = np.where(a3 > 0, from_subdistrict, a2)
    from_district = district_out // step_up
    bad = (district_out > 0) & (a1 > 0) & (from_district != a1)
    if bad.any():
        i = int(np.nonzero(bad)[0][0])
        raise ValueError(f"feature {i}: district {district_out[i]} does not start with its province {a1[i]}")
    province_out = np.where(district_out > 0, from_district, a1)
    return {"province": province_out, "district": district_out, "subdistrict": a3}


def province_conflicts(
    province: ArrayLike,
    names: Iterable[Any],
    code_of_name: dict[str, int],
    report_unknown_names: bool = False,
) -> list[tuple[int, int, int | None]]:
    """Features whose province code disagrees with their own province name.

    Parameters
    ----------
    province : array_like of int
        Province code of each feature (as resolved or as stored).
    names : iterable
        Province name of each feature; anything that is not a string (a
        missing name) is taken as no name. Same length as ``province``.
    code_of_name : dict of str to int
        Province name to code, from the province-level boundary file.
    report_unknown_names : bool
        Also return features whose code is a known province but whose name
        is not in ``code_of_name``, so cannot be checked. In the files of
        2026-11-22 that is the 44 features named "DKI Jakarta", which the
        province file spells "Daerah Khusus Ibukota Jakarta".

    Returns
    -------
    list of (index, code, expected)
        One entry per feature whose code is not 0 and either is not a known
        province code, or differs from the code of its name, or (if asked)
        has a name that cannot be looked up. ``expected`` is the code of
        the name, or None where the name is missing or unknown.

    Raises
    ------
    ValueError
        If ``names`` and ``province`` differ in length, or a code is negative.
    TypeError
        If the codes are not integers.
    """
    codes = integer_codes(province, "province codes")
    known = set(code_of_name.values())
    out: list[tuple[int, int, int | None]] = []
    for i, (code, name) in enumerate(zip(codes.tolist(), names, strict=True)):
        if code == c.NO_UNIT:
            continue
        named = isinstance(name, str)
        expected = code_of_name.get(name) if named else None
        if code not in known or (expected is not None and expected != code):
            out.append((i, code, expected))
        elif report_unknown_names and named and expected is None:
            out.append((i, code, None))
    return out


def burn_index(geometries: Iterable[Any], grid: Grid) -> NDArray[np.int64]:
    """Position of the polygon that contains each cell's centre.

    Parameters
    ----------
    geometries : iterable of geometry
        Polygons in geographic coordinates (degrees, the grid's datum).
    grid : Grid
        Target grid.

    Returns
    -------
    ndarray of int64, shape ``grid.shape``
        1-based position in ``geometries`` of the polygon containing the
        cell's centre; 0 where none does. Where polygons overlap, the later
        one wins.

    Notes
    -----
    Uses ``rasterio.features.rasterize`` with ``all_touched=False``, which
    is the cell-centre rule; a centre exactly on a polygon edge follows
    GDAL's convention. Empty or missing geometries are skipped by the
    rasteriser with a warning. Burn once and look codes up by position
    (:func:`burn_units`, ``ntl.stack``): a cell then takes every level's
    code from the same polygon.
    """
    from rasterio import features
    from rasterio.transform import from_origin

    shapes = [(geometry, i + 1) for i, geometry in enumerate(geometries)]
    if not shapes:
        return np.zeros(grid.shape, dtype=np.int64)
    burned = features.rasterize(
        shapes,
        out_shape=grid.shape,
        transform=from_origin(grid.west, grid.north, grid.cell, grid.cell),
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    return burned.astype(np.int64)


def burn_units(shapes: Iterable[tuple[Any, int]], grid: Grid) -> NDArray[np.int64]:
    """Unit code of every cell of a grid, by the cell-centre rule.

    Parameters
    ----------
    shapes : iterable of (geometry, code)
        Polygons with their integer unit code. Several polygons may share a
        code and then form one unit. Features with code 0 are skipped.
    grid : Grid
        Target grid (``ntl.read.read_grid`` of any file of the tile).

    Returns
    -------
    ndarray of int64, shape ``grid.shape``
        The code of the polygon containing each cell's centre, 0 where none
        does. Where polygons overlap, the later one in ``shapes`` wins.

    Raises
    ------
    TypeError
        If a code is not an integer (5208.7 is refused, not truncated).
    ValueError
        If a code is negative.

    Notes
    -----
    Polygons are burned by position (:func:`burn_index`) and mapped back to
    codes, so codes of any size are safe.
    """
    kept = []
    for geometry, code in shapes:
        if isinstance(code, (bool, float, np.floating)) or not isinstance(code, (int, np.integer)):
            raise TypeError(f"unit code must be an integer, got {code!r}")
        if code < 0:
            raise ValueError(f"unit code must not be negative, got {code}")
        if code != c.NO_UNIT:
            kept.append((geometry, int(code)))
    codes = np.array([c.NO_UNIT] + [code for _, code in kept], dtype=np.int64)
    return codes[burn_index((geometry for geometry, _ in kept), grid)]


class UnitSums(NamedTuple):
    """Result of :func:`unit_sums`. Arrays are aligned with ``codes``.

    Attributes
    ----------
    codes : ndarray of int64
        Unit codes present in the input, ascending, without 0.
    total : ndarray of float64
        Sum of ``values`` over the unit's cells that were used.
    cells : ndarray of int64
        Number of cells used.
    coverage : ndarray of float64
        Share of the unit's weight carried by the cells used, 0 to 1. With
        weights equal to each cell's usual light this says how much of the
        unit's light was seen: a sum from a tenth of a town is not the town.
        0 for a unit whose weights are all zero.
    """

    codes: NDArray[np.int64]
    total: NDArray[np.float64]
    cells: NDArray[np.int64]
    coverage: NDArray[np.float64]


def unit_sums(values: ArrayLike, unit_codes: ArrayLike, weights: ArrayLike | None = None) -> UnitSums:
    """Sum cell values per unit, using only cells that have a value.

    Parameters
    ----------
    values : array_like of float
        One value per cell. NaN or infinite means "not usable" (not
        observed, too few nights): such cells are left out, never counted as
        zero.
    unit_codes : array_like of int, same shape
        Unit code per cell; 0 for cells in no unit, which are ignored.
    weights : array_like of float, same shape, optional
        Non-negative weight per cell for ``coverage``. Default: every cell
        weighs 1, so coverage is the share of cells used. Weights of cells
        outside every unit are not looked at.

    Returns
    -------
    UnitSums

    Raises
    ------
    ValueError
        If shapes differ, a code is negative, or a weight inside a unit is
        negative or not finite.
    TypeError
        If the unit codes are not integers.

    Notes
    -----
    Sums of two quantities are comparable only over the same cells. To
    compare a month with its reference, set to NaN in both every cell that
    lacks either, then call this once for each. No area weighting: a cell
    counts the same at any latitude.
    """
    shape = np.shape(values)
    if np.shape(unit_codes) != shape:
        raise ValueError(f"shapes differ: {shape} values, {np.shape(unit_codes)} unit codes")
    if weights is not None and np.shape(weights) != shape:
        raise ValueError(f"shapes differ: {shape} values, {np.shape(weights)} weights")
    values = np.asarray(values, dtype=np.float64).ravel()
    unit_codes = integer_codes(unit_codes).ravel()
    in_unit = unit_codes != c.NO_UNIT
    if weights is None:
        cell_weights = np.ones(int(in_unit.sum()))
    else:
        cell_weights = np.asarray(weights, dtype=np.float64).ravel()[in_unit]
        if not np.all(np.isfinite(cell_weights) & (cell_weights >= 0)):
            raise ValueError("weights must be finite and not negative inside units")

    codes, index = np.unique(unit_codes[in_unit], return_inverse=True)
    used = np.isfinite(values[in_unit])
    n = codes.size
    total = np.bincount(index, weights=np.where(used, values[in_unit], 0.0), minlength=n).astype(np.float64)
    cells = np.bincount(index, weights=used.astype(np.float64), minlength=n).astype(np.int64)
    weight_all = np.bincount(index, weights=cell_weights, minlength=n)
    weight_used = np.bincount(index, weights=np.where(used, cell_weights, 0.0), minlength=n)
    coverage = np.where(weight_all > 0, weight_used / np.where(weight_all > 0, weight_all, 1.0), 0.0)
    return UnitSums(codes=codes, total=total, cells=cells, coverage=coverage.astype(np.float64))
