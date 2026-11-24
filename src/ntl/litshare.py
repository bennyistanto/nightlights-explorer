"""Year by year: the people of a unit by the light recorded where they live.

A yearly table per admin unit, meant as supporting information beside an
official figure such as the share of households with electricity. It is not
that figure. The satellite records mostly outdoor light above a floor, in
the small hours (nominally 01:30 local time; the time at a cell moves from
night to night, project skill section 1.1 and 1.3): a household with a
connection and no outdoor lighting is dark here, and a lit cell says nothing
about who in it is connected.

Method, with rules picked for this project ([P]) after the critique of
2026-11-24 (``temp/litshare-critique.md``), which showed that a first
version restricted to the status domain could never exceed the share of
people living in that fixed set of cells:

1. **Support**: every 15 arc-second cell that lies in a province and holds
   people in at least one year of a gridded population. Land class is not
   asked for: coastal-class cells hold towns, and leaving them out biased
   the first version against island provinces. "Holds people" is any value
   above zero: of the cells of the 2020 raster used so far, 433,948 hold
   under one person (167,630 people in all; method review, 2026-11-24).
   They weigh little in the people columns and as much as any other cell
   in the cell counts. Cells without people (a lit road, a plant) are not
   in the support and so in no count.
2. **One value per cell and calendar year**, from that year alone: the
   median of the year's usable monthly composites (VNP46A3, one view class,
   quality 0), needing ``firstlight.MIN_MONTHS_PER_YEAR`` of them
   (``firstlight.yearly_cell_medians``). Quality 0 means more than 3
   observations (user guide Table 12), so no separate count of nights is
   read. No value from another year is used: nothing is fixed with hindsight.
3. **Four states per cell and year**: *unseen* (too few usable months);
   *dark* (median under ``firstlight.DARK_MAX``, the 0.5 nW below which the
   product stores zero, user guide 2.3: nothing was recorded in at least
   half of the usable months; with an even number of months the median is
   the mean of the two middle ones, so a cell can be dark with one of them
   at 0 and the other under 1.0, which is 1.1 to 1.4% of seen cell-years
   on the two tiles the method review counted); *faint* (from there to under
   ``conventions.LIT_MIN_RADIANCE``); *lit* (at or above it).
4. **Per unit and year**: cells and people in each state, and for provinces
   and districts how many sub-districts hold at least ``MIN_SUBUNIT_CELLS``
   lit cells.
5. **People** of each year come from that year's own population raster
   (owner's decision, 2026-11-24). A year before the first raster uses the
   first one, carried back and marked in ``meta.json``; nothing is
   extrapolated. The yearly grids of the source used so far differ by a
   near-uniform rescaling (measured in the critique: growth of 10.1 to
   10.3% in every class of cell, 2015 to 2026), so shares barely depend on
   this choice; ``population_year`` fixes one year for every year, to
   measure by how much. Measured on the run of 2026-11-24 against 2020
   fixed: a share of seen people moves by at most 0.33 points for a
   province and 1.0 for a district (``docs/method.md`` 5.4).

Inputs: the monthly files under a data root (VNP46A3, Black Marble
Collection 2, ArchiveSet 5200), a folder of yearly population rasters
whose pixels nest in the 15 arc-second lattice, and the sub-district
polygon file. Outputs, in the folder asked for: ``province.json``,
``district.json`` and ``subdistrict.json`` (keys ``years``, ``codes``,
``people``, ``cells_<state>``, and for the first two ``people_<state>``,
``subunits``, ``subunits_lit``; every yearly column is ``[year][unit]``),
and ``meta.json`` (rule, inputs, which population year stands for each
year, national shares, what was left out). Reading rasters and boundaries
needs ``rasterio`` and ``geopandas`` (the package's ``zonal`` extra).

What it does and does not describe:

- The share of people in dark cells errs one way: the sensor's footprint
  (about 742 m against a 15 arc-second cell, skill section 1.1) and glow
  spread light over neighbours, so a dark cell gave less than the floor
  even with its neighbours' spill, while a faint or lit cell may owe its
  light to the place next door. Dark is "under the floor", not "no light
  at all": light dimmer than 0.5 nW is not told apart from none.
- The 2 nW line between faint and lit is picked, and the cells that were
  already lit nearly doubled their light (a balanced panel of 239,839
  status-domain cells has 1.94 times its 2015 light in 2026, critique
  finding 4; the populated cells outside that domain were not measured),
  so people move from faint to lit without
  anything changing on the ground that this module can name. Read faint
  and lit together against dark; do not read a rise in lit as people
  gaining light.
- Unseen is not at random: it falls on the same provinces again and again.
  Shares are meant to be taken over the people in seen cells, with the
  unseen share shown beside them.
- The population grid used so far (WorldPop R2025A v1, constrained) places
  census counts of about district level on mapped buildings with a model
  that has night-time lights among its covariates (release statement and
  covariate sheet cited in the critique, finding 5). A province or district
  total is census-based (scaled to a national projection, and modelled
  between and after the census years); where inside the unit the people sit is modelled,
  and not independently of light. A sub-district share is modelled on both
  sides, which is why the site file carries no people by state at that level.
- The cell-centre rule gives a border cell's people to one unit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import re
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl import files, firstlight, qa, stack
from ntl.read import Grid, read_raw, read_scaled
from ntl.tiles import Tile, parse_tile, tiles_for_bbox

log = logging.getLogger("ntl.litshare")

#: States of a cell in a year. Unseen is 0 so that an untouched array says "nothing known".
UNSEEN, DARK, FAINT, LIT = 0, 1, 2, 3
#: Names of the states in the site files, in the order of their codes.
STATE_NAMES = ("unseen", "dark", "faint", "lit")
#: Lit cells a sub-district needs to count as "holding light" in a year. [P] One cell
#: decided 686 of 4,402 sub-districts in the first version and the count churned by
#: as much as its trend (critique finding 10).
MIN_SUBUNIT_CELLS = 5
#: A population file names its year like this: ``idn_pop_2020_CN_100m_R2025A_v1.tif``.
POPULATION_NAME = re.compile(r"_pop_(\d{4})_")
#: Rows of a population raster read at a time. Picked: one row of the 512-pixel blocks of the
#: rasters used so far, which keeps a strip of a 55,238-pixel-wide raster near 0.5 GB while it is summed.
STRIP_ROWS = 512
#: How far a population pixel edge may sit from the 15 arc-second lattice, in pixels, before the
#: file is refused. Picked: the rasters used so far are off by 0.00003 pixel, a misaligned one by 0.1 or more.
LATTICE_TOLERANCE = 0.01
#: How far a raster's pixel width and height may differ, degrees, before it is refused as not square. Picked.
SQUARE_TOLERANCE = 1e-12
#: Version of the caches in the work folder; raise it when a rule or a layout changes.
CACHE_VERSION = 2
#: Version of the site files' layout. 3: people are ``[year][unit]``, each year's own population.
PAYLOAD_VERSION = 3


def light_state(yearly: ArrayLike, dark_max: float = firstlight.DARK_MAX, lit_min: float = c.LIT_MIN_RADIANCE) -> NDArray[np.uint8]:
    """State of each cell in each year.

    Parameters
    ----------
    yearly : array_like of float
        Yearly radiance of each cell, nW cm-2 sr-1; NaN where the year has
        too few usable months (``firstlight.yearly_cell_medians``).
    dark_max : float
        Under this value a cell is dark: the product's floor.
    lit_min : float
        At or above this value a cell is lit.

    Returns
    -------
    ndarray of uint8, shape of ``yearly``
        ``UNSEEN`` (NaN), ``DARK``, ``FAINT`` or ``LIT``.

    Raises
    ------
    ValueError
        If ``dark_max`` is above ``lit_min``.
    """
    if dark_max > lit_min:
        raise ValueError(f"dark_max {dark_max} is above lit_min {lit_min}")
    yearly = np.asarray(yearly, dtype=np.float64)
    out = np.full(yearly.shape, UNSEEN, dtype=np.uint8)
    seen = np.isfinite(yearly)
    out[seen] = FAINT
    out[seen & (yearly < dark_max)] = DARK
    out[seen & (yearly >= lit_min)] = LIT
    return out


def positions(codes: ArrayLike, units: ArrayLike) -> NDArray[np.int64]:
    """Position of each code in a sorted unit list, plus one; 0 where it is not listed.

    Parameters
    ----------
    codes : array_like of int
        Unit code of each cell (any shape); ``conventions.NO_UNIT`` allowed.
    units : array_like of int, shape ``(U,)``
        Distinct unit codes, ascending.

    Returns
    -------
    ndarray of int64, shape of ``codes``
        1 to ``U``, or 0 for a code that is not in ``units``.

    Raises
    ------
    ValueError
        If ``units`` is not strictly ascending.
    """
    codes = np.asarray(codes)
    units = np.asarray(units, dtype=np.int64)
    if np.any(np.diff(units) <= 0):
        raise ValueError("units must be distinct and ascending")
    if units.size == 0:
        return np.zeros(codes.shape, dtype=np.int64)
    at = np.minimum(np.searchsorted(units, codes), units.size - 1)
    return np.where(units[at] == codes, at + 1, 0).astype(np.int64)


def sum_by_unit(position: ArrayLike, units: int, weights: ArrayLike | None = None) -> NDArray[np.float64]:
    """Sum of a weight (or a count) over the cells of each unit.

    Parameters
    ----------
    position : array_like of int, shape ``(N,)``
        As :func:`positions`: 1 to ``units``, 0 for no unit.
    units : int
        Number of units.
    weights : array_like of float, shape ``(N,)``, optional
        Default: each cell counts 1.

    Returns
    -------
    ndarray of float64, shape ``(units,)``
        Cells at position 0 are left out.
    """
    position = np.asarray(position).ravel()
    weights = None if weights is None else np.asarray(weights, dtype=np.float64).ravel()
    return np.bincount(position, weights=weights, minlength=units + 1)[1:units + 1].astype(np.float64)


def subunits_with(chosen: ArrayLike, position: ArrayLike, child: ArrayLike, units: int, min_cells: int = 1) -> NDArray[np.int64]:
    """How many distinct child units of each unit hold enough chosen cells.

    Parameters
    ----------
    chosen : array_like of bool, shape ``(N,)``
        The cells that count (for example the lit cells of one year).
    position : array_like of int, shape ``(N,)``
        Parent unit of each cell, as :func:`positions`.
    child : array_like of int, shape ``(N,)``
        Child unit code of each cell; ``conventions.NO_UNIT`` where the
        cell is held by the parent itself, which counts for no child.
    units : int
        Number of parent units.
    min_cells : int
        Chosen cells a child needs to be counted.

    Returns
    -------
    ndarray of int64, shape ``(units,)``
    """
    keep = np.asarray(chosen, dtype=bool) & (np.asarray(position) > 0) & (np.asarray(child) != c.NO_UNIT)
    if not keep.any():
        return np.zeros(units, dtype=np.int64)
    pairs, counts = np.unique(np.stack([np.asarray(position)[keep], np.asarray(child)[keep]]), axis=1, return_counts=True)
    return np.bincount(pairs[0][counts >= min_cells], minlength=units + 1)[1:units + 1].astype(np.int64)


def lattice_index(edge: float, step: float, count: int, origin: float, descending: bool = False) -> NDArray[np.int64]:
    """Index on the 15 arc-second lattice of each pixel of a finer raster axis.

    Parameters
    ----------
    edge : float
        Outer edge of the axis' first pixel, degrees (west for columns,
        north for rows).
    step : float
        Pixel size, degrees, positive.
    count : int
        Pixels along the axis.
    origin : float
        Where lattice index 0 starts: -180 for columns, 90 for rows.
    descending : bool
        True for rows (latitude falls as the index rises).

    Returns
    -------
    ndarray of int64, shape ``(count,)``
        Lattice index of the cell holding each pixel's centre.

    Raises
    ------
    ValueError
        If the pixels do not nest in the lattice: the pixel size is not a
        whole fraction of 15 arc-seconds, or an edge is off the sub-lattice
        by more than ``LATTICE_TOLERANCE`` pixels. A raster that does not
        nest would need resampling, which this module does not do.
    """
    if not step > 0:
        raise ValueError(f"pixel size must be positive, got {step}")
    per_cell = c.CELL_SIZE_DEG / step
    if round(per_cell) < 1 or abs(per_cell - round(per_cell)) > LATTICE_TOLERANCE:
        raise ValueError(f"pixel size {step} is not a whole fraction of the 15 arc-second cell ({per_cell:.4f} pixels per cell)")
    nominal = c.CELL_SIZE_DEG / round(per_cell)  # the pixel size the lattice implies; the stored one can be off by a hair
    last = edge - count * step if descending else edge + count * step
    for at in (edge, last):  # both ends, so that a pixel size off by a hair cannot drift across the raster
        at = ((origin - at) if descending else (at - origin)) / nominal
        if abs(at - round(at)) > LATTICE_TOLERANCE:
            raise ValueError(f"pixel edges do not fall on the 15 arc-second lattice (off by {at - round(at):.4f} pixel)")
    centre = (edge - (np.arange(count) + 0.5) * step) if descending else (edge + (np.arange(count) + 0.5) * step)
    return np.floor(((origin - centre) if descending else (centre - origin)) / c.CELL_SIZE_DEG).astype(np.int64)


def block_sum(block: ArrayLike, row_index: ArrayLike, col_index: ArrayLike, nodata: float | None) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """Sum the pixels of a block into the lattice cells they fall in.

    Parameters
    ----------
    block : array_like of float, shape ``(R, C)``
        People per pixel.
    row_index, col_index : array_like of int, shapes ``(R,)`` and ``(C,)``
        Lattice row and column of each pixel row and column, non-decreasing.
    nodata : float or None
        Stored value for "no data". Such pixels, and non-finite ones, add
        nothing: a cell with no valid pixel sums to 0, which here means "no
        people counted", the same as the source's sea and uninhabited land.

    Returns
    -------
    ndarray of float64, shape ``(r, c)``
        Sums, one per distinct lattice row and column.
    ndarray of int64, shape ``(r,)``
    ndarray of int64, shape ``(c,)``
        The distinct lattice rows and columns, in order.

    Raises
    ------
    ValueError
        If an index is not non-decreasing or its length does not match.
    """
    block = np.asarray(block, dtype=np.float64)
    row_index = np.asarray(row_index, dtype=np.int64)
    col_index = np.asarray(col_index, dtype=np.int64)
    if block.shape != (row_index.size, col_index.size):
        raise ValueError(f"block has shape {block.shape}, indices {(row_index.size, col_index.size)}")
    if np.any(np.diff(row_index) < 0) or np.any(np.diff(col_index) < 0):
        raise ValueError("lattice indices must not decrease along an axis")
    valid = np.isfinite(block)
    if nodata is not None:
        valid &= block != nodata
    clean = np.where(valid, block, 0.0)
    row_start = np.concatenate([[0], np.nonzero(np.diff(row_index))[0] + 1])
    col_start = np.concatenate([[0], np.nonzero(np.diff(col_index))[0] + 1])
    sums = np.add.reduceat(np.add.reduceat(clean, row_start, axis=0), col_start, axis=1)
    return sums, row_index[row_start], col_index[col_start]


def _lattice_axes(src: Any, path: str | Path) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Lattice row of every raster row and lattice column of every raster column."""
    if src.crs is None or not src.crs.is_geographic:
        raise ValueError(f"{path}: coordinates are not geographic ({src.crs})")
    t = src.transform
    if t.b != 0 or t.d != 0 or t.e >= 0 or abs(t.a + t.e) > SQUARE_TOLERANCE:
        raise ValueError(f"{path}: expected a north-up raster with square pixels, got transform {tuple(t)[:6]}")
    rows = lattice_index(t.f, t.a, src.height, 90.0, descending=True)
    cols = lattice_index(t.c, t.a, src.width, -180.0)
    return rows, cols


def population_grid(path: str | Path) -> Grid:
    """The block of the 15 arc-second lattice that a population raster covers.

    Raises
    ------
    ValueError
        If the raster is not in geographic coordinates, is rotated, or does
        not nest in the lattice (:func:`lattice_index`).
    """
    import rasterio

    with rasterio.open(path) as src:
        rows, cols = _lattice_axes(src, path)
    shape = (int(rows[-1] - rows[0] + 1), int(cols[-1] - cols[0] + 1))
    return Grid(west=-180.0 + cols[0] * c.CELL_SIZE_DEG, north=90.0 - rows[0] * c.CELL_SIZE_DEG, cell=c.CELL_SIZE_DEG, shape=shape)


def grid_origin(grid: Grid) -> tuple[int, int]:
    """Global lattice row and column of a grid's north-west cell."""
    return round((90.0 - grid.north) / c.CELL_SIZE_DEG), round((grid.west + 180.0) / c.CELL_SIZE_DEG)


def read_population(path: str | Path, grid: Grid) -> NDArray[np.float32]:
    """People per 15 arc-second cell from one population raster.

    Parameters
    ----------
    path : str or Path
        A single-band raster of people per pixel in geographic coordinates
        whose pixels nest in the 15 arc-second lattice.
    grid : Grid
        Target block of the lattice (:func:`population_grid` of the file).

    Returns
    -------
    ndarray of float32, shape ``grid.shape``
        People per cell; 0 where the raster has no data.

    Raises
    ------
    ValueError
        As :func:`population_grid`, or if the raster falls outside ``grid``.
    """
    import rasterio
    from rasterio.windows import Window

    out = np.zeros(grid.shape, dtype=np.float64)
    row0, col0 = grid_origin(grid)
    with rasterio.open(path) as src:
        rows, cols = _lattice_axes(src, path)
        if rows[0] < row0 or cols[0] < col0 or rows[-1] >= row0 + grid.shape[0] or cols[-1] >= col0 + grid.shape[1]:
            raise ValueError(f"{path}: covers a different block of the lattice than the grid asked for")
        for start in range(0, src.height, STRIP_ROWS):
            stop = min(src.height, start + STRIP_ROWS)
            block = src.read(1, window=Window(0, start, src.width, stop - start))
            sums, r, k = block_sum(block, rows[start:stop], cols, src.nodata)
            # A lattice row can straddle two strips, so add; within one strip r and k are distinct.
            out[np.ix_(r - row0, k - col0)] += sums
    return out.astype(np.float32)


def population_files(folder: str | Path) -> dict[int, Path]:
    """Population rasters of a folder by year.

    Raises
    ------
    FileNotFoundError
        If the folder holds no ``.tif`` whose name carries ``_pop_<year>_``.
    ValueError
        If two files name the same year.
    """
    found: dict[int, Path] = {}
    for path in sorted(Path(folder).glob("*.tif")):
        match = POPULATION_NAME.search(path.name)
        if not match:
            continue
        year = int(match.group(1))
        if year in found:
            raise ValueError(f"{folder}: two population files for {year} ({found[year].name}, {path.name})")
        found[year] = path
    if not found:
        raise FileNotFoundError(f"{folder}: no population raster named like idn_pop_<year>_...tif")
    return found


def tile_cells(tile: Tile, rows: ArrayLike, cols: ArrayLike) -> NDArray[np.bool_]:
    """Which cells, given by global lattice row and column, fall in a tile."""
    rows, cols = np.asarray(rows), np.asarray(cols)
    r0, k0 = tile.v * c.CELLS_PER_TILE, tile.h * c.CELLS_PER_TILE
    return (rows >= r0) & (rows < r0 + c.CELLS_PER_TILE) & (cols >= k0) & (cols < k0 + c.CELLS_PER_TILE)


def tile_states(
    files: Mapping[dt.date, Path],
    rows: ArrayLike,
    cols: ArrayLike,
    years: Sequence[int],
    view: str = c.DEFAULT_VIEW,
    dark_max: float = firstlight.DARK_MAX,
    lit_min: float = c.LIT_MIN_RADIANCE,
    min_months: int = firstlight.MIN_MONTHS_PER_YEAR,
) -> NDArray[np.uint8]:
    """State of chosen cells of one tile in each year, from its monthly files.

    Parameters
    ----------
    files : mapping of datetime.date to Path
        The tile's monthly composites by month (``stack.monthly_files``).
    rows, cols : array_like of int, shape ``(n,)``
        Row and column of each cell **inside the tile** (0 to 2399).
    years : sequence of int
        Calendar years wanted. A year with no file is all ``UNSEEN``.
    view : str
        View-angle class.
    dark_max, lit_min : float
        As :func:`light_state`.
    min_months : int
        Usable months a cell needs in a year.

    Returns
    -------
    ndarray of uint8, shape ``(len(years), n)``

    Raises
    ------
    ValueError
        If the view is unknown.
        Also if a file lacks a layer; the message names the file.

    Notes
    -----
    A month is usable where the composite quality is 0 and the value is
    finite. Gap-filled months (quality 2) hold a number and are not used:
    they are history, not an observation of that month (skill 1.2). Only
    the block of the tile that spans the chosen cells is read.
    """
    if view not in c.COMPOSITE_VIEWS:
        raise ValueError(f"unknown view {view!r}; expected one of {c.COMPOSITE_VIEWS}")
    rows, cols = np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64)
    out = np.full((len(years), rows.size), UNSEEN, dtype=np.uint8)
    if rows.size == 0:
        return out
    window = (slice(int(rows.min()), int(rows.max()) + 1), slice(int(cols.min()), int(cols.max()) + 1))
    r, k = rows - window[0].start, cols - window[1].start
    name = c.COMPOSITE_LAYER.format(view=view, suffix="")
    for y, year in enumerate(years):
        months = [month for month in sorted(files) if month.year == year]
        if not months:
            continue
        block = np.full((len(months), rows.size), np.nan, dtype=np.float32)
        for m, month in enumerate(months):
            path = files[month]
            try:
                value = read_scaled(path, name, window)[r, k]
                good = qa.composite_observed(read_raw(path, name + c.COMPOSITE_QUALITY, window)[r, k], good_only=True)
            except KeyError as exc:
                raise ValueError(f"{path.name}: {exc.args[0]}") from None
            usable = good & np.isfinite(value)
            block[m, usable] = value[usable]
        _, yearly = firstlight.yearly_cell_medians(block, np.full(len(months), year, dtype=np.int64), min_months)
        out[y] = light_state(yearly[0], dark_max, lit_min)
    return out


def population_year_for(years: Sequence[int], available: Sequence[int], fixed: int | None = None) -> dict[int, int]:
    """Which population year stands for each year of the record.

    Parameters
    ----------
    years : sequence of int
        Calendar years of the light record.
    available : sequence of int
        Years that have a population raster.
    fixed : int, optional
        Use this one population year for every year. Default: each year's
        own raster.

    Returns
    -------
    dict of int to int
        For each record year, the population year used: its own if there is
        a raster; otherwise the latest earlier one; and for years before the
        first raster, the first raster (the earliest grid carried back,
        which the site marks). Nothing is extrapolated.

    Raises
    ------
    ValueError
        If there is no raster at all, or ``fixed`` is not among them.
    """
    available = sorted(int(a) for a in available)
    if not available:
        raise ValueError("no population year available")
    if fixed is not None:
        if fixed not in available:
            raise ValueError(f"no population raster for {fixed} (found {available})")
        return {int(year): int(fixed) for year in years}
    return {int(year): max((a for a in available if a <= year), default=available[0]) for year in years}


class Population(NamedTuple):
    """People per populated cell, for every population year. ``N`` cells.

    Attributes
    ----------
    grid : Grid
        The block of the 15 arc-second lattice the rasters cover.
    index : ndarray of int64, shape ``(N,)``
        Position of each cell in ``grid``, ``row * columns + column``,
        ascending: the cells that hold people in at least one year.
    people : dict of int to ndarray of float32, shape ``(N,)``
        People per cell by population year; 0 where the cell holds none
        that year.
    in_raster : dict of int to float
        All people in each year's raster, inside a province or not.
    description, licence_tag : str or None
        The first raster's own ``Description`` and copyright tags.
    pixel_arcsec : float
        Pixel size of the rasters, arc-seconds.
    """

    grid: Grid
    index: NDArray[np.int64]
    people: dict[int, NDArray[np.float32]]
    in_raster: dict[int, float]
    description: str | None
    licence_tag: str | None
    pixel_arcsec: float


def _file_stamp(path: Path) -> list[str | int]:
    """Name, size and modification time (nanoseconds) of a file: enough to notice it was replaced."""
    info = path.stat()
    return [path.name, info.st_size, info.st_mtime_ns]


def _load_cache(cache: Path | None, stamp: list) -> dict[str, NDArray] | None:
    """Arrays of a cache file whose stamp matches, or None.

    A missing, unreadable, damaged or outdated cache is never an error: it is
    logged when it had to be discarded, and the caller computes afresh.
    """
    if cache is None or not cache.is_file():
        return None
    try:
        with np.load(cache, allow_pickle=False) as stored:
            if json.loads(str(stored["stamp"])) != stamp:
                log.info("%s: made from other inputs or rules, rebuilding", cache.name)
                return None
            return {name: stored[name] for name in stored.files if name != "stamp"}
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
        log.warning("%s: unreadable cache ignored (%s: %s)", cache, type(exc).__name__, exc)
        return None


def _save_cache(cache: Path | None, stamp: list, arrays: Mapping[str, NDArray]) -> None:
    if cache is not None:
        files.save_npz(cache, {"stamp": np.array(json.dumps(stamp)), **arrays})


def load_population(rasters: Mapping[int, Path], work: Path | None = None) -> Population:
    """Read every population raster onto the 15 arc-second lattice.

    Parameters
    ----------
    rasters : mapping of int to Path
        Raster by year (:func:`population_files`). All must cover the same
        block of the lattice as the earliest one.
    work : Path, optional
        Folder for a cache of the result, keyed by the rasters' names,
        sizes and modification times.

    Returns
    -------
    Population

    Raises
    ------
    ValueError
        As :func:`read_population`.
    """
    import rasterio

    years = sorted(rasters)
    first = rasters[years[0]]
    grid = population_grid(first)
    with rasterio.open(first) as src:
        tags, pixel = src.tags(), float(src.transform.a)
    stamp = [CACHE_VERSION, [[year, *_file_stamp(rasters[year])] for year in years]]
    cache = None if work is None else work / "population_cells.npz"
    stored = _load_cache(cache, stamp)
    if stored is not None:
        log.info("population: %d cells of %d years read from %s", stored["index"].size, len(years), cache)
        people = {year: stored[f"people_{year}"] for year in years}
        in_raster = {year: float(total) for year, total in zip(years, stored["in_raster"])}
        index = stored["index"]
    else:
        sparse, in_raster = {}, {}
        for year in years:
            cells = read_population(rasters[year], grid).ravel()
            at = np.flatnonzero(cells > 0)
            sparse[year] = (at, cells[at])
            in_raster[year] = float(cells.sum(dtype=np.float64))
            log.info("population %d: %.0f people in %d cells (%s)", year, in_raster[year], at.size, rasters[year].name)
        index = np.unique(np.concatenate([at for at, _ in sparse.values()])).astype(np.int64)
        people = {}
        for year, (at, values) in sparse.items():
            people[year] = np.zeros(index.size, dtype=np.float32)
            people[year][np.searchsorted(index, at)] = values
        _save_cache(cache, stamp, {"index": index, "in_raster": np.array([in_raster[year] for year in years]),
                                   **{f"people_{year}": people[year] for year in years}})
    return Population(grid=grid, index=index, people=people, in_raster=in_raster, description=tags.get("Description"),
                      licence_tag=tags.get("TIFFTAG_COPYRIGHT"), pixel_arcsec=round(3600 * pixel, 3))


def unit_maps(boundaries: str | Path, grid: Grid, work: Path | None = None) -> dict[str, NDArray[np.int32]]:
    """Unit codes of every cell of a grid at the three levels, cached in ``work``.

    The cache is keyed by the grid and by the name, size and modification
    time of the boundary file and of the files beside it that carry its
    codes and geometry index (``.dbf``, ``.shx``, ``.prj`` for a shapefile):
    a corrected code changes the ``.dbf`` and not the ``.shp``.
    """
    source = Path(boundaries)
    parts = [source] + [part for part in (source.with_suffix(suffix) for suffix in (".dbf", ".shx", ".prj")) if part != source and part.is_file()]
    stamp = [CACHE_VERSION, [_file_stamp(part) for part in parts], grid.west, grid.north, *grid.shape]
    cache = None if work is None else work / "unit_maps_population_grid.npz"
    stored = _load_cache(cache, stamp)
    if stored is not None:
        log.info("unit maps: read from %s", cache)
        return {level: stored[level] for level in c.ADMIN_LEVELS}
    log.info("unit maps: burning %s onto %d x %d cells (minutes, several GB)", source.name, *grid.shape)
    burned = stack.unit_maps_from_file(source, grid)
    maps = {level: burned.pop(level).astype(np.int32) for level in c.ADMIN_LEVELS}  # one level at a time: the int64 maps are 0.36 GB each
    _save_cache(cache, stamp, maps)
    return maps


class LevelTable(NamedTuple):
    """Yearly figures of one admin level. ``Y`` years by ``U`` units.

    Attributes
    ----------
    codes : ndarray of int64, shape ``(U,)``
        Unit codes, ascending: the units with at least one populated cell.
    people : ndarray of float64, shape ``(Y, U)``
        People of each unit in the population year used for each year.
    cells : ndarray of int64, shape ``(4, Y, U)``
        Populated cells in each state, by state code.
    people_by_state : ndarray of float64, shape ``(4, Y, U)``
        People in the cells of each state. Sums to ``people``.
    subunits : ndarray of int64, shape ``(U,)`` or None
        Sub-districts of each unit that hold a populated cell; None at
        sub-district level.
    subunits_lit : ndarray of int64, shape ``(Y, U)`` or None
        Of those, the ones with at least ``min_subunit_cells`` lit cells
        that year.
    """

    codes: NDArray[np.int64]
    people: NDArray[np.float64]
    cells: NDArray[np.int64]
    people_by_state: NDArray[np.float64]
    subunits: NDArray[np.int64] | None
    subunits_lit: NDArray[np.int64] | None


def level_table(state: ArrayLike, people: ArrayLike, unit_codes: ArrayLike, subdistrict: ArrayLike | None = None,
                min_subunit_cells: int = MIN_SUBUNIT_CELLS) -> LevelTable:
    """Cells and people by state, per unit and year.

    Parameters
    ----------
    state : array_like of uint8, shape ``(Y, N)``
        :func:`light_state` of every populated cell.
    people : array_like of float, shape ``(Y, N)`` or ``(N,)``
        People of each cell in each year; one row is used for every year.
    unit_codes : array_like of int, shape ``(N,)``
        Unit of each cell at this level; ``conventions.NO_UNIT`` cells are
        left out.
    subdistrict : array_like of int, shape ``(N,)``, optional
        Sub-district code of each cell, to count sub-districts per unit.
        Leave out at sub-district level.
    min_subunit_cells : int
        Lit cells a sub-district needs to be counted as holding light.

    Returns
    -------
    LevelTable

    Raises
    ------
    ValueError
        If ``people`` does not match ``state``.
    """
    state = np.asarray(state)
    people = np.asarray(people, dtype=np.float64)
    if people.ndim == 1:
        people = np.broadcast_to(people, state.shape)
    if people.shape != state.shape:
        raise ValueError(f"people has shape {people.shape}, state {state.shape}")
    unit_codes = np.asarray(unit_codes, dtype=np.int64)
    codes = np.unique(unit_codes[unit_codes != c.NO_UNIT])
    position = positions(unit_codes, codes)
    years, units = state.shape[0], codes.size
    cells = np.zeros((len(STATE_NAMES), years, units), dtype=np.int64)
    by_state = np.zeros((len(STATE_NAMES), years, units))
    total = np.zeros((years, units))
    counted = subdistrict is not None
    subunits_lit = np.zeros((years, units), dtype=np.int64) if counted else None
    for y in range(years):
        total[y] = sum_by_unit(position, units, people[y])
        for which in (UNSEEN, DARK, FAINT, LIT):
            chosen = state[y] == which
            cells[which, y] = sum_by_unit(position[chosen], units)
            by_state[which, y] = sum_by_unit(position[chosen], units, people[y][chosen])
        if counted:
            subunits_lit[y] = subunits_with(state[y] == LIT, position, subdistrict, units, min_subunit_cells)
    subunits = subunits_with(np.ones(position.shape, dtype=bool), position, subdistrict, units) if counted else None
    return LevelTable(codes=codes, people=total, cells=cells, people_by_state=by_state, subunits=subunits, subunits_lit=subunits_lit)


def level_payload(table: LevelTable, years: Sequence[int], with_people_by_state: bool = True) -> dict[str, Any]:
    """The JSON body of one level: every yearly column as ``[year][unit]`` lists.

    Parameters
    ----------
    table : LevelTable
    years : sequence of int
        The years of the table's rows.
    with_people_by_state : bool
        False for the sub-district file: there both the people and where
        they sit inside the unit are modelled, so a share would be a model
        against a model. The unit's people are still given.

    Returns
    -------
    dict
        ``years``, ``codes``, ``people``, ``cells_<state>``, and where asked
        ``people_<state>``, ``subunits``, ``subunits_lit``. People are
        rounded to whole numbers, each figure on its own, so a unit's people
        by state can differ from its ``people`` by a person or two.
    """
    whole = lambda values: np.rint(values).astype(np.int64).tolist()  # noqa: E731
    body: dict[str, Any] = {"years": [int(y) for y in years], "codes": table.codes.tolist(), "people": whole(table.people)}
    for which, name in enumerate(STATE_NAMES):
        body[f"cells_{name}"] = table.cells[which].tolist()
        if with_people_by_state:
            body[f"people_{name}"] = whole(table.people_by_state[which])
    if table.subunits_lit is not None:
        body["subunits"] = table.subunits.tolist()
        body["subunits_lit"] = table.subunits_lit.tolist()
    return body


def national_shares(state: ArrayLike, people: ArrayLike, years: Sequence[int]) -> list[dict[str, float]]:
    """Share of all counted people in each state, per year, in percent.

    Parameters
    ----------
    state : array_like of uint8, shape ``(Y, N)``
    people : array_like of float, shape ``(Y, N)``
    years : sequence of int, length ``Y``

    Returns
    -------
    list of dict
        One per year: ``year``, ``people``, and a percentage of that year's
        people for each name of ``STATE_NAMES`` (two decimals). These are
        shares of everyone, unseen included.
    """
    state, people = np.asarray(state), np.asarray(people, dtype=np.float64)
    out = []
    for y, year in enumerate(years):
        total = float(people[y].sum())
        row: dict[str, float] = {"year": int(year), "people": round(total)}
        for which, name in enumerate(STATE_NAMES):
            row[name] = round(100 * float(people[y][state[y] == which].sum()) / total, 2) if total else 0.0
        out.append(row)
    return out


class Support(NamedTuple):
    """The populated cells of the provinces. ``N`` cells.

    Attributes
    ----------
    rows, cols : ndarray of int64, shape ``(N,)``
        Row and column of each cell on the global 15 arc-second lattice
        (row 0 at 90 N, column 0 at 180 W).
    codes : dict of str to ndarray of int64, shape ``(N,)``
        Unit code of each cell at each admin level.
    people : dict of int to ndarray of float32, shape ``(N,)``
        People per cell by population year.
    """

    rows: NDArray[np.int64]
    cols: NDArray[np.int64]
    codes: dict[str, NDArray[np.int64]]
    people: dict[int, NDArray[np.float32]]


def support_cells(population: Population, maps: Mapping[str, NDArray]) -> Support:
    """Cells that lie in a province and hold people in at least one population year.

    Raises
    ------
    ValueError
        If no populated cell lies in a province (the boundary file and the
        population rasters do not overlap).
    """
    grid_rows, grid_cols = np.divmod(population.index, population.grid.shape[1])
    inside = maps["province"][grid_rows, grid_cols] != c.NO_UNIT
    if not inside.any():
        raise ValueError("no populated cell lies in a province: do the boundary file and the population rasters cover the same area?")
    grid_rows, grid_cols = grid_rows[inside], grid_cols[inside]
    row0, col0 = grid_origin(population.grid)
    return Support(rows=grid_rows + row0, cols=grid_cols + col0,
                   codes={level: maps[level][grid_rows, grid_cols].astype(np.int64) for level in c.ADMIN_LEVELS},
                   people={year: values[inside] for year, values in population.people.items()})


def _digest(*arrays: NDArray) -> str:
    """SHA-256 of the bytes of some arrays, to name a set of cells in a cache stamp."""
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def all_states(
    root: str | Path,
    support: Support,
    tiles: Sequence[Tile],
    view: str,
    dark_max: float,
    lit_min: float,
    work: Path | None,
) -> tuple[list[int], NDArray[np.uint8], dict[str, Any]]:
    """State of every support cell in every year, tile by tile, with a cache per tile.

    Returns
    -------
    list of int
        The calendar years that have a monthly file in any tile.
    ndarray of uint8, shape ``(Y, N)``
    dict
        What was read and what was left out: ``tiles`` read,
        ``tiles_without_files`` (their cells are unseen in every year),
        ``cells_outside_tiles``, and the first and last ``months``.

    Raises
    ------
    ValueError
        If no tile with populated cells has a monthly file.

    Notes
    -----
    A tile's cache is reused when its cells (by a digest of their rows and
    columns), its files (names, which carry the production time, and
    sizes), the years, the view and the rule are all unchanged. ``years``
    is the union over tiles, so a new year rebuilds every tile.
    """
    min_months = firstlight.MIN_MONTHS_PER_YEAR
    tiles = list(dict.fromkeys(tiles))
    members = {tile: np.nonzero(tile_cells(tile, support.rows, support.cols))[0] for tile in tiles}
    latest = max(support.people)
    found: dict[Tile, dict[dt.date, Path]] = {}
    without_files = []
    for tile in tiles:
        at = members[tile]
        if at.size == 0:
            continue
        try:
            found[tile] = stack.monthly_files(root, tile.id)
        except FileNotFoundError:
            people = float(support.people[latest][at].sum())
            without_files.append({"tile": tile.id, "cells": int(at.size), "people": round(people), "people_year": latest})
            log.warning("tile %s: no monthly file; its %d populated cells (%.0f people in %d) are unseen in every year", tile.id, at.size, people, latest)
    if not found:
        raise ValueError(f"no monthly file under {root} for any tile with populated cells")
    covered = np.zeros(support.rows.size, dtype=bool)
    for at in members.values():
        covered[at] = True
    outside = int((~covered).sum())
    if outside:
        log.warning("%d populated cells lie in none of the tiles asked for; unseen in every year", outside)

    years = sorted({month.year for months in found.values() for month in months})
    state = np.full((len(years), support.rows.size), UNSEEN, dtype=np.uint8)
    for tile, months in found.items():
        at = members[tile]
        r, k = support.rows[at] - tile.v * c.CELLS_PER_TILE, support.cols[at] - tile.h * c.CELLS_PER_TILE
        stamp = [CACHE_VERSION, tile.id, view, years, float(dark_max), float(lit_min), min_months, _digest(r, k),
                 sorted(f"{path.name}:{path.stat().st_size}" for path in months.values())]
        cache = None if work is None else work / f"states_{tile.id}_{view}.npz"
        stored = _load_cache(cache, stamp)
        if stored is not None:
            log.info("tile %s: states of %d cells read from %s", tile.id, at.size, cache)
            state[:, at] = stored["state"]
            continue
        log.info("tile %s: reading %d monthly files for %d populated cells", tile.id, len(months), at.size)
        state[:, at] = tile_states(months, r, k, years, view, dark_max, lit_min, min_months)
        _save_cache(cache, stamp, {"state": state[:, at]})
    read = {"tiles": [tile.id for tile in found], "tiles_without_files": without_files, "cells_outside_tiles": outside,
            "months": [min(min(months) for months in found.values()).isoformat(), max(max(months) for months in found.values()).isoformat()]}
    return years, state, read


def build(
    root: str | Path,
    population: str | Path,
    boundaries: str | Path,
    out: str | Path,
    work: str | Path | None = None,
    population_year: int | None = None,
    tiles: Sequence[str] | None = None,
    view: str = c.DEFAULT_VIEW,
    dark_max: float = firstlight.DARK_MAX,
    lit_min: float = c.LIT_MIN_RADIANCE,
    min_subunit_cells: int = MIN_SUBUNIT_CELLS,
) -> dict[str, Any]:
    """Compute the yearly tables and write ``<level>.json`` and ``meta.json`` for the site.

    Parameters
    ----------
    root : str or Path
        Data root holding the monthly files fetched by ``ntl.download``.
    population : str or Path
        Folder of yearly population rasters (:func:`population_files`).
    boundaries : str or Path
        Sub-district polygon file with integer fields ``a1siak``,
        ``a2siak``, ``a3siak``.
    out : str or Path
        Folder for the JSON files; created once the inputs have been read.
    work : str or Path, optional
        Folder for caches: the population cells, the unit maps of their
        grid and each tile's states. Keep it outside any synced folder.
    population_year : int, optional
        Use this one population year for every year of the record.
        Default: each year's own raster (:func:`population_year_for`).
    tiles : sequence of str, optional
        Tile ids. Default: every tile the population grid touches.
    view : str
        View-angle class of the composites.
    dark_max, lit_min : float
        As :func:`light_state`, nW cm-2 sr-1.
    min_subunit_cells : int
        As :func:`level_table`.

    Returns
    -------
    dict
        The content of ``meta.json``: rule, inputs, which population year
        stands for each year, and what was left out.

    Raises
    ------
    FileNotFoundError
        If the population folder holds no raster.
    ValueError
        If a raster does not nest in the 15 arc-second lattice, the
        population year asked for has no raster, no populated cell lies in
        a province, or no tile with populated cells has a monthly file.
    """
    out = Path(out)
    work = None if work is None else Path(work)
    rasters = population_files(population)
    if population_year is not None and population_year not in rasters:
        raise ValueError(f"{population}: no population raster for {population_year} (found {sorted(rasters)})")
    people_cells = load_population(rasters, work)
    support = support_cells(people_cells, unit_maps(boundaries, people_cells.grid, work))
    wanted = [parse_tile(tile) for tile in tiles] if tiles else tiles_for_bbox(*people_cells.grid.bounds)
    years, state, read = all_states(root, support, wanted, view, dark_max, lit_min, work)

    used = population_year_for(years, sorted(rasters), population_year)
    people = np.stack([support.people[used[year]] for year in years]).astype(np.float64)
    national = national_shares(state, people, years)
    for row in national:
        log.info("%d (people of %d): unseen %.2f%%, dark %.2f%%, faint %.2f%%, lit %.2f%%", row["year"], used[row["year"]], *(row[name] for name in STATE_NAMES))

    bodies = {}
    for level in c.ADMIN_LEVELS:
        table = level_table(state, people, support.codes[level], None if level == "subdistrict" else support.codes["subdistrict"], min_subunit_cells)
        bodies[level] = level_payload(table, years, with_people_by_state=level != "subdistrict")
    sizes = {}
    for level, body in bodies.items():
        sizes[f"{level}.json"] = files.write_json(out / f"{level}.json", body)
        log.info("%s.json: %d units, %d bytes", level, len(body["codes"]), sizes[f"{level}.json"])
    meta = {
        "script": "python -m ntl.litshare",
        "version": PAYLOAD_VERSION,
        "rule": {"dark_max": float(dark_max), "lit_min": float(lit_min), "min_months_per_year": firstlight.MIN_MONTHS_PER_YEAR,
                 "yearly_value": "median of the year's usable monthly values (quality 0)", "min_subunit_cells": int(min_subunit_cells),
                 "support": "cells in a province that hold people in at least one population year, any land or water class"},
        "product": c.MONTHLY_PRODUCT, "view": view, "years": years, "cells": int(support.rows.size), **read,
        "population": {"years": sorted(rasters), "used": {str(year): used[year] for year in years},
                       "carried_back": [year for year in years if used[year] > year], "carried_forward": [year for year in years if used[year] < year],
                       "fixed_year": population_year, "files": {str(year): rasters[year].name for year in sorted(set(used.values()))},
                       "description": people_cells.description, "licence_tag": people_cells.licence_tag, "pixel_arcsec": people_cells.pixel_arcsec,
                       "people_in_raster": {str(year): round(people_cells.in_raster[year]) for year in sorted(set(used.values()))},
                       "grid": {"west": people_cells.grid.west, "north": people_cells.grid.north, "shape": list(people_cells.grid.shape)}},
        "national": national, "files": sizes,
    }
    files.write_json(out / "meta.json", meta, indent=1)  # last: its presence says the level files beside it are complete
    return meta


_EXAMPLE = "example:\n  python -m ntl.litshare --root <data root> --population <folder of rasters> --boundaries <adm3 file> --work <cache folder> --out site/data/yearly\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.litshare",
        description="Yearly cells and people by the light recorded where they live (dark, faint, lit, unseen), per admin unit, for the site.",
        epilog=_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", required=True, type=Path, help="data root holding the monthly files fetched by ntl.download")
    parser.add_argument("--population", required=True, type=Path, help="folder of yearly population rasters named ..._pop_<year>_....tif")
    parser.add_argument("--boundaries", required=True, type=Path, help="sub-district polygon file with integer fields a1siak, a2siak, a3siak")
    parser.add_argument("--out", required=True, type=Path, help="folder for <level>.json and meta.json")
    parser.add_argument("--work", type=Path, help="folder for the caches (population cells, unit maps, tile states); outside any synced folder")
    parser.add_argument("--population-year", type=int,
                        help="use this one population year for every year of the record (default: each year's own raster; "
                             "years before the first raster use the first)")
    parser.add_argument("--tiles", nargs="+", metavar="hHHvVV", help="tile ids (default: every tile the population grid touches)")
    parser.add_argument("--view", default=c.DEFAULT_VIEW, choices=c.COMPOSITE_VIEWS, help=f"view-angle class (default {c.DEFAULT_VIEW})")
    parser.add_argument("--dark-max", type=float, default=firstlight.DARK_MAX, help="a yearly median under this is 'dark', nW cm-2 sr-1")
    parser.add_argument("--lit-min", type=float, default=c.LIT_MIN_RADIANCE, help="a yearly median at or above this is 'lit', nW cm-2 sr-1")
    parser.add_argument("--min-subunit-cells", type=int, default=MIN_SUBUNIT_CELLS, help="lit cells a sub-district needs to count as holding light")
    parser.add_argument("--verbose", action="store_true", help="on a problem with the inputs, log the traceback as well")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point.

    Returns
    -------
    int
        0 on success, 1 on a problem with the inputs. A usage problem ends
        in argparse's own exit with status 2.
    """
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        build(args.root, args.population, args.boundaries, args.out, args.work, args.population_year, args.tiles, args.view,
              args.dark_max, args.lit_min, args.min_subunit_cells)
    except ImportError as exc:
        log.error("%s (this step needs rasterio and geopandas: install the package's 'zonal' extra)", exc)
        return 1
    except (OSError, ValueError) as exc:
        log.error("%s", exc, exc_info=args.verbose)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
