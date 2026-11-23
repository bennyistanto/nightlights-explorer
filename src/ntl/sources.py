"""Where the light sources are: cells that stand above their surroundings, month after month.

The lit domain of the status (``ntl.stack.lit_domain``) is a plain
threshold on a cell's mean radiance. That misses dim, isolated lights.
This module finds them: a cell is a *source* in a month if its radiance
exceeds a distance-weighted mean of its neighbours by a set margin, and a
*consistent source* if that holds in a set share of its good-quality
months. Consistent sources under the threshold are exported as a layer of
"faint sources" for the map (``ntl.export``); the statuses do not use them.

The idea is the background filter described in a tutorial the owner
supplied (``temp/fb/Model Tutorial - PDF.pdf``, pages 7 to 12, read
2026-11-23; no code was taken from it and none came with it): estimate the
background with a weighted mean of the neighbours, subtract it and a
threshold, keep what is left, then keep cells that are lit consistently
over time. What is this project's own [P]:

- The weights, ``1 / (1 + d / SOURCE_SCALE_KM) ** 3`` out to
  ``SOURCE_RADIUS_KM`` with the centre cell left out, are the tutorial's
  shape with its pixel distances turned into kilometres (it works on cells
  of about 304 m; ours are 15 arc-seconds, about 463 m).
- Neighbours without a good-quality value are left out of the mean, and a
  cell with too little weight around it gets no background.
- The margin ``SOURCE_MIN_CONTRAST`` (0.5 nW cm-2 sr-1) and the share
  ``SOURCE_MIN_SHARE`` (half of the good months) were chosen on tile
  h28v09 (``temp/status-design.md``, "Source filter test"): over open sea
  0.003% of cells pass both. The tutorial's margin of 0.1 belongs to other
  images; this product sets composite radiance under 0.5 to zero.

What the filter is not: a measure of light. It finds peaks, not extents.
On tile h28v09 the cells it does not mark hold 49% of the light of the
threshold domain, most of them next to a marked cell, so it cannot replace
the threshold. Nor are its extra cells fit for the statuses: their median
is about 1.4 nW cm-2 sr-1, they read exactly zero in 7.8% of their good
months (1.8% for threshold cells at 2 to 3), and adding them nationally
shifted the pooled thresholds of every unit (second method critique,
2026-11-23). ``stack.build_stack(source_contrast=...)`` can still add them
to a stack; that is how the faint layer is made. Whether a faint source is
a settlement, a flare, a mine or a plantation has not been checked.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c

#: Smallest summed weight of good neighbours for a background to be given
#: (the weights of a full neighbourhood sum to 1). [P]
MIN_NEIGHBOUR_WEIGHT = 0.05


def source_kernel(radius_km: float = c.SOURCE_RADIUS_KM, scale_km: float = c.SOURCE_SCALE_KM, cell_km: float = c.CELL_KM) -> NDArray[np.float64]:
    """Weights of the neighbours of a cell, by distance.

    Parameters
    ----------
    radius_km : float
        Neighbours farther than this get no weight.
    scale_km : float
        Distance at which the weight has fallen to an eighth of its value at zero.
    cell_km : float
        Side of a cell, km.

    Returns
    -------
    ndarray of float64, shape ``(2R + 1, 2R + 1)``
        ``1 / (1 + d / scale_km) ** 3`` for a neighbour at distance ``d``
        km up to the radius, zero beyond and zero at the centre, scaled to
        sum to 1. ``R`` is the radius in whole cells.

    Raises
    ------
    ValueError
        If a length is not positive or the radius is under one cell.
    """
    if min(radius_km, scale_km, cell_km) <= 0:
        raise ValueError(f"lengths must be positive, got radius {radius_km}, scale {scale_km}, cell {cell_km}")
    reach = int(round(radius_km / cell_km))
    if reach < 1:
        raise ValueError(f"a radius of {radius_km} km is under one cell of {cell_km} km")
    rows, cols = np.mgrid[-reach:reach + 1, -reach:reach + 1]
    distance = np.hypot(rows, cols) * cell_km
    kernel = np.where(distance <= radius_km, 1.0 / (1.0 + distance / scale_km) ** 3, 0.0)
    kernel[reach, reach] = 0.0
    return kernel / kernel.sum()


def background_filter(shape: tuple[int, int], kernel: ArrayLike) -> Callable[[ArrayLike, ArrayLike], NDArray[np.float64]]:
    """A function giving the local background of grids of one shape.

    The kernel's transform is worked out once, so that a month costs two
    transforms of the grid and two back.

    Parameters
    ----------
    shape : tuple of int
        Rows and columns of the grids to come.
    kernel : array_like of float, shape ``(2R + 1, 2R + 1)``
        From :func:`source_kernel`; must be symmetric about its centre.

    Returns
    -------
    callable
        ``background(radiance, good)``: for each cell the weighted mean of
        the radiance of its good neighbours, in the unit of ``radiance``;
        NaN where the good neighbours carry less than
        ``MIN_NEIGHBOUR_WEIGHT``. ``radiance`` may hold anything where
        ``good`` is False. Beyond the edge of the grid there are no
        neighbours.

    Raises
    ------
    ValueError
        If the kernel is not square with an odd side, or a grid passed
        later has another shape.
    """
    kernel = np.asarray(kernel, dtype=np.float64)
    if kernel.ndim != 2 or kernel.shape[0] != kernel.shape[1] or kernel.shape[0] % 2 == 0:
        raise ValueError(f"kernel must be square with an odd side, got {kernel.shape}")
    reach = kernel.shape[0] // 2
    padded = (shape[0] + 2 * reach, shape[1] + 2 * reach)
    transform = np.fft.rfft2(kernel, padded)

    def spread(grid: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.fft.irfft2(np.fft.rfft2(grid, padded) * transform, padded)[reach:reach + shape[0], reach:reach + shape[1]]

    def background(radiance: ArrayLike, good: ArrayLike) -> NDArray[np.float64]:
        good = np.asarray(good, dtype=bool)
        if good.shape != tuple(shape):
            raise ValueError(f"grid has shape {good.shape}, the filter was made for {tuple(shape)}")
        value = np.where(good, np.asarray(radiance, dtype=np.float64), 0.0)
        weight = spread(good.astype(np.float64))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(weight > MIN_NEIGHBOUR_WEIGHT, spread(value) / weight, np.nan)

    return background


def is_source(radiance: ArrayLike, good: ArrayLike, background: ArrayLike, min_contrast: float = c.SOURCE_MIN_CONTRAST) -> NDArray[np.bool_]:
    """Cells that stand above their surroundings this month.

    Parameters
    ----------
    radiance : array_like of float
        nW cm-2 sr-1.
    good : array_like of bool
        True where the radiance is a good-quality value.
    background : array_like of float
        From :func:`background_filter`, same unit; NaN where there is none.
    min_contrast : float
        Margin over the background, same unit.

    Returns
    -------
    ndarray of bool
        True where the cell is good and its radiance exceeds its
        background by more than ``min_contrast``. A cell without a
        background is not a source.
    """
    with np.errstate(invalid="ignore"):
        return np.asarray(good, dtype=bool) & (np.asarray(radiance, dtype=np.float64) - np.asarray(background, dtype=np.float64) > min_contrast)


def consistent_sources(source_months: ArrayLike, good_months: ArrayLike, min_share: float = c.SOURCE_MIN_SHARE) -> NDArray[np.bool_]:
    """Cells that were a source in enough of their good months.

    Parameters
    ----------
    source_months, good_months : array_like of int
        Months as a source, and good-quality months, of each cell.
    min_share : float
        Share of the good months, above 0 and at most 1.

    Returns
    -------
    ndarray of bool
        True where the cell has a good month and was a source in at least
        ``min_share`` of them.

    Raises
    ------
    ValueError
        If the share is outside (0, 1].
    """
    if not 0 < min_share <= 1:
        raise ValueError(f"min_share must be above 0 and at most 1, got {min_share}")
    source_months = np.asarray(source_months, dtype=np.float64)
    good_months = np.asarray(good_months, dtype=np.float64)
    return (good_months > 0) & (source_months >= min_share * good_months)
