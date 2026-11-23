"""Read layers from Black Marble HDF-EOS5 files.

The one place that touches ``h5py``. It does three things and no science:

1. finds a layer in the fixed grid group;
2. turns the stored numbers into physical ones: **fill is masked first**,
   then scale and offset are applied, so a fill value is never averaged,
   scaled or compared;
3. says where the cells are, from the tile bounds in the file attributes.

Flag layers are returned exactly as stored (:func:`read_raw`); measurement
layers come back as float with NaN for fill (:func:`read_scaled`).

Notes
-----
Facts below were read from real Collection 2 files on 2026-11-22
(``conventions`` tag [F]):

- VNP46A2 names the additive term ``offset``; VNP46A1 names it
  ``add_offset``. Both are handled.
- The ``lat`` and ``lon`` arrays in the file hold each cell's north-west
  **corner**, not its centre (``lat[0]`` is exactly the tile's north edge).
  This module derives positions from the tile bounds and never from those
  arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

from ntl import conventions as c

#: A window is (row slice, column slice) into a tile.
Window = tuple[slice, slice]


@dataclass(frozen=True)
class Grid:
    """Georeferencing of a block of cells on the 15 arc-second grid.

    Attributes
    ----------
    west, north : float
        Outer edge of the block's north-west cell, degrees.
    cell : float
        Cell size in degrees (both axes).
    shape : (int, int)
        Rows, columns.
    """

    west: float
    north: float
    cell: float
    shape: tuple[int, int]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Outer edges as (west, south, east, north)."""
        rows, cols = self.shape
        return (self.west, self.north - rows * self.cell, self.west + cols * self.cell, self.north)

    def centres(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Cell-centre longitudes (per column) and latitudes (per row)."""
        rows, cols = self.shape
        lon = self.west + (np.arange(cols) + 0.5) * self.cell
        lat = self.north - (np.arange(rows) + 0.5) * self.cell
        return lon, lat

    def window(self, west: float, south: float, east: float, north: float) -> Window:
        """Smallest window whose cells cover a bounding box, clipped to the grid.

        Parameters
        ----------
        west, south, east, north : float
            Degrees. Requires ``west < east`` and ``south < north``.

        Returns
        -------
        (slice, slice)
            Rows, then columns. A cell is included if any part of it lies
            inside the box.

        Raises
        ------
        ValueError
            If the box is inverted or empty, or misses the grid entirely.
        """
        if not (west < east and south < north):
            raise ValueError(f"need west < east and south < north, got {(west, south, east, north)}")
        rows, cols = self.shape
        eps = c.WINDOW_EDGE_TOLERANCE
        c0 = max(0, int(np.floor((west - self.west) / self.cell + eps)))
        c1 = min(cols, int(np.ceil((east - self.west) / self.cell - eps)))
        r0 = max(0, int(np.floor((self.north - north) / self.cell + eps)))
        r1 = min(rows, int(np.ceil((self.north - south) / self.cell - eps)))
        if c0 >= c1 or r0 >= r1:
            raise ValueError(f"box {(west, south, east, north)} does not overlap grid {self.bounds}")
        return (slice(r0, r1), slice(c0, c1))

    def subgrid(self, window: Window) -> "Grid":
        """Grid of a window cut from this one."""
        rs, cs = window
        r0, r1, _ = rs.indices(self.shape[0])
        c0, c1, _ = cs.indices(self.shape[1])
        return Grid(self.west + c0 * self.cell, self.north - r0 * self.cell, self.cell, (r1 - r0, c1 - c0))


def _first(value: object) -> float:
    """Scalar from an HDF5 attribute, as the decimal its writer meant.

    Attributes are often one-element arrays. VNP46A1 stores scale and offset
    as float32: widened directly, 0.01 becomes 0.009999999776, and a stored
    angle of 4000 would scale to 39.99999911 instead of 40.0. NumPy prints a
    float32 as the shortest decimal that round-trips, which is the intended
    value, so float32 attributes are read through that text form.
    """
    scalar = np.ravel(np.asarray(value))[0]
    if isinstance(scalar, np.float32):
        return float(str(scalar))
    return float(scalar)


def _group(handle: h5py.File) -> h5py.Group:
    """The grid group, or a ``KeyError`` that says what the file is not."""
    group = handle.get(c.GRID_GROUP)
    if group is None:
        raise KeyError(f"not a Black Marble grid file: group {c.GRID_GROUP!r} is absent")
    return group


def _layer(handle: h5py.File, name: str) -> h5py.Dataset:
    """One layer, or a ``KeyError`` listing the layers that do exist."""
    group = _group(handle)
    if name not in group:
        raise KeyError(f"layer {name!r} not in file; available: {sorted(group.keys())}")
    return group[name]


def _two_dimensional(group: h5py.Group) -> dict[str, h5py.Dataset]:
    return {name: ds for name, ds in group.items() if isinstance(ds, h5py.Dataset) and ds.ndim == 2}


def list_layers(path: str | Path) -> list[str]:
    """Names of the two-dimensional layers in a file.

    Parameters
    ----------
    path : str or Path
        A VNP46 ``.h5`` file.

    Returns
    -------
    list of str
        Sorted. The one-dimensional ``lat`` and ``lon`` arrays are left out.

    Raises
    ------
    KeyError
        If the file has no Black Marble grid group.
    """
    with h5py.File(path, "r") as handle:
        return sorted(_two_dimensional(_group(handle)))


def read_grid(path: str | Path) -> Grid:
    """Georeferencing of a tile, from its bounding attributes.

    Parameters
    ----------
    path : str or Path
        A VNP46 ``.h5`` file.

    Returns
    -------
    Grid
        West and north edges, cell size and shape of the whole tile.

    Raises
    ------
    KeyError
        If the file has no Black Marble grid group or no gridded layer.
    ValueError
        If the bounds and the layer shape disagree with a 15 arc-second
        grid. That would mean a product this reader was not written for.
    """
    with h5py.File(path, "r") as handle:
        west = _first(handle.attrs["WestBoundingCoord"])
        east = _first(handle.attrs["EastBoundingCoord"])
        north = _first(handle.attrs["NorthBoundingCoord"])
        south = _first(handle.attrs["SouthBoundingCoord"])
        layers = _two_dimensional(_group(handle))
        if not layers:
            raise KeyError(f"{path}: no two-dimensional layer in {c.GRID_GROUP!r}")
        shape = next(iter(layers.values())).shape
    cell_x, cell_y = (east - west) / shape[1], (north - south) / shape[0]
    if not (np.isclose(cell_x, c.CELL_SIZE_DEG) and np.isclose(cell_y, c.CELL_SIZE_DEG)):
        raise ValueError(f"{path}: cell size {cell_x} x {cell_y} degrees, expected {c.CELL_SIZE_DEG}")
    return Grid(west, north, c.CELL_SIZE_DEG, (int(shape[0]), int(shape[1])))


def read_raw(path: str | Path, name: str, window: Window | None = None) -> NDArray:
    """A layer exactly as stored: for flags and bit masks.

    Parameters
    ----------
    path : str or Path
        A VNP46 ``.h5`` file.
    name : str
        Layer name as in the file.
    window : (slice, slice), optional
        Rows and columns to read. Default: the whole tile.

    Returns
    -------
    ndarray
        In the stored data type, fill values included: no masking and no
        scaling. Decode with ``ntl.qa``.

    Raises
    ------
    KeyError
        If the group or the layer is absent.
    """
    with h5py.File(path, "r") as handle:
        dataset = _layer(handle, name)
        return dataset[window] if window is not None else dataset[...]


def read_scaled(path: str | Path, name: str, window: Window | None = None) -> NDArray[np.float64]:
    """A measurement layer in physical units, NaN where there is no value.

    Parameters
    ----------
    path : str or Path
        A VNP46 ``.h5`` file.
    name : str
        Layer name as in the file (hyphens, not Earth Engine underscores).
    window : (slice, slice), optional
        Rows and columns to read. Default: the whole tile.

    Returns
    -------
    ndarray of float64
        ``stored * scale_factor + offset``, with NaN wherever the stored
        value equals the layer's ``_FillValue`` or one of its
        ``conventions.EXTRA_FILLS``. Units are the layer's own (radiance:
        nW cm-2 sr-1; angles: degrees; ``UTC_Time``: decimal hours; moon
        illumination: percent; brightness temperature: kelvin).

    Raises
    ------
    KeyError
        If the group or the layer is absent.
    ValueError
        If an integer layer has no ``_FillValue`` attribute, or one that
        does not fit the layer's data type. Scaling it unmasked could turn
        a fill into a plausible number.

    Notes
    -----
    The fill is compared in the stored data type before any conversion.
    Radiance is float32 with fill -999.9, which is not exactly representable:
    comparing after a cast to float64 against the literal would miss it.
    A float layer without ``_FillValue`` falls back to
    ``conventions.RADIANCE_FILL``; no Collection 2 layer read so far (33
    layers, 64 files) lacks the attribute.

    Scale and offset are taken as the decimals the file intends (see
    ``_first``), so a stored 4000 with scale 0.01 is 40.0. The product is
    still binary floating point: compare against round thresholds with a
    tolerance, or in stored units.

    This masks what the file declares, not what is physically doubtful. In
    VNP46A1, measured on tile h29v09: radiance is present under cloud (only
    the cloud bits say whether a cell was clear), and the brightness
    temperature layers hold clamp-like values over cold cloud
    (``BrightnessTemperature_M12`` stored 0, which scales to 203.0 K, and
    ``BrightnessTemperature_M13`` stored 65160, which scales to 365.9 K)
    that come back here as ordinary numbers.
    """
    with h5py.File(path, "r") as handle:
        dataset = _layer(handle, name)
        stored = dataset[window] if window is not None else dataset[...]
        attrs = dict(dataset.attrs)

    is_integer = stored.dtype.kind in "iu"
    if "_FillValue" in attrs:
        declared = np.ravel(np.asarray(attrs["_FillValue"]))[0]
        if is_integer and not (np.iinfo(stored.dtype).min <= declared <= np.iinfo(stored.dtype).max):
            raise ValueError(f"{name}: _FillValue {declared} does not fit {stored.dtype}")
        missing = stored == declared.astype(stored.dtype)
    elif is_integer:
        raise ValueError(f"{name}: integer layer without _FillValue; refusing to scale it unmasked")
    else:
        missing = stored == np.asarray(c.RADIANCE_FILL, dtype=stored.dtype)
    for extra in c.EXTRA_FILLS.get(name, ()):
        missing |= stored == extra

    scale = _first(attrs["scale_factor"]) if "scale_factor" in attrs else 1.0
    offset = next((_first(attrs[key]) for key in c.OFFSET_ATTRS if key in attrs), 0.0)
    values = stored.astype(np.float64) * scale + offset
    values[missing] = np.nan
    return values
