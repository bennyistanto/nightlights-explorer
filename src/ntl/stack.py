"""From a tile's monthly files to arrays the statistics can use.

A :class:`TileStack` holds, for one tile and one view-angle class, every
month of the record for the cells that matter: the cells in the status
domain ("lit" land cells inside an admin unit). Building one reads each
monthly file twice: once to fix the land mask and find the domain, once to
collect the values of the domain's cells. Nothing here computes a statistic.

Product: NASA Black Marble monthly composites, VNP46A3, Collection 2
(``conventions.MONTHLY_PRODUCT``), the snow-free composite layers of one
view-angle class. The domain rule and its reasons are in
``temp/status-design.md``; the product facts are in the project skill
(``.claude/skills/ntl/SKILL.md``).

Why only the domain's cells: a whole tile for 179 months is about 8 GB per
array, and the domain is small. Measured on the eleven Indonesian tiles
(2026-11-22): from 11 cells (h27v09) to 117,400 (h29v09) of the 5.76
million in a tile.

What "lit" means here is a picked rule (:func:`lit_domain`): a land cell
with at least 12 good-quality months whose mean over them is at least 2 nW
cm-2 sr-1. A stack can also be built with the cells that stand above their
surroundings in half of those months (consistent light sources,
``ntl.sources``); that is for the map's layer of faint sources, not for
the statuses. By default the mean is taken over the whole record,
which is look-ahead for a monitor: pass ``until`` to fix the domain and the
usual radiance from the months before a date. It matters: tile h29v09 from
months before 2018 has 68,529 domain cells against 117,400 from the whole
record. The stack records which it was built with.

Units are identified by ``siak`` codes at three levels, province, district
and sub-district; a code of 0 at one level means the cell is held by the
level above (``ntl.zonal``).
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import composite, qa, sources, zonal
from ntl import conventions as c
from ntl.download import parse_granule_name
from ntl.read import Grid, read_grid, read_raw, read_scaled
from ntl.tiles import parse_tile, tile_bounds

log = logging.getLogger("ntl.stack")


@dataclass(frozen=True, eq=False)
class TileStack:
    """Monthly values of one view class for the status-domain cells of a tile.

    ``T`` months by ``N`` cells. Months are consecutive calendar months; a
    month with no file inside the record is present as a row of "no value".
    Two stacks are never compared with ``==`` (the fields are arrays).

    Attributes
    ----------
    tile : str
        Tile id, or several joined by ``+`` after :func:`concat`.
    view : str
        ``"AllAngle"``, ``"NearNadir"`` or ``"OffNadir"``.
    months : tuple of datetime.date
        First day of each month, length ``T``. For the statistics use
        :attr:`calendar_month` and :attr:`year`, which are integers.
    lon, lat : ndarray of float64, shape ``(N,)``
        Cell-centre coordinates, degrees.
    province, district, subdistrict : ndarray of int64, shape ``(N,)``
        ``siak`` code of each cell at each level (adm1, adm2, adm3); 0 where
        the cell is held by the level above. ``province`` is never 0 inside
        the domain.
    usual : ndarray of float64, shape ``(N,)``
        Mean AllAngle radiance over the cell's good-quality months used to
        define the domain, nW cm-2 sr-1. Always from AllAngle, whatever
        ``view`` is.
    value : ndarray of float32, shape ``(T, N)``
        Composite radiance of ``view``, nW cm-2 sr-1; NaN where the file
        has fill or the month has no file. Gap-filled months hold a number
        here: use :meth:`usable` or ``quality`` before any arithmetic.
    nights : ndarray of uint16, shape ``(T, N)``
        Observations behind each value; 0 where none (fill already mapped).
    quality : ndarray of uint8, shape ``(T, N)``
        Composite quality as stored: 0 good, 1 poor, 2 gap filled, 255 fill.
    until : datetime.date or None
        The domain and ``usual`` use months before this date; None means
        the whole record (look-ahead).
    lit_min : float
        Domain rule: minimum mean radiance.
    min_good_months : int
        Domain rule: minimum good months.
    source_contrast : float or None
        Domain rule: cells that are consistent light sources at this margin
        over their background, nW cm-2 sr-1, are in the domain whatever
        their mean (``ntl.sources``); None if sources were not added. A
        cell with ``usual`` under ``lit_min`` is in the domain as a source.
    """

    tile: str
    view: str
    months: tuple[dt.date, ...]
    lon: NDArray[np.float64]
    lat: NDArray[np.float64]
    province: NDArray[np.int64]
    district: NDArray[np.int64]
    subdistrict: NDArray[np.int64]
    usual: NDArray[np.float64]
    value: NDArray[np.float32]
    nights: NDArray[np.uint16]
    quality: NDArray[np.uint8]
    until: dt.date | None = None
    lit_min: float = c.LIT_MIN_RADIANCE
    min_good_months: int = c.LIT_MIN_GOOD_MONTHS
    source_contrast: float | None = None

    @property
    def calendar_month(self) -> NDArray[np.int64]:
        """Calendar month (1 to 12) of each row, as ``ntl.status`` and ``ntl.monitor`` expect."""
        return np.array([m.month for m in self.months], dtype=np.int64)

    @property
    def year(self) -> NDArray[np.int64]:
        """Calendar year of each row."""
        return np.array([m.year for m in self.months], dtype=np.int64)

    def units(self, level: str) -> NDArray[np.int64]:
        """Unit code of each cell at one level.

        Parameters
        ----------
        level : str
            ``"province"``, ``"district"`` or ``"subdistrict"``.

        Returns
        -------
        ndarray of int64, shape ``(N,)``

        Raises
        ------
        ValueError
            If the level is unknown.
        """
        if level not in c.ADMIN_LEVELS:
            raise ValueError(f"unknown level {level!r}; expected one of {c.ADMIN_LEVELS}")
        return getattr(self, level)

    def observed(self) -> NDArray[np.bool_]:
        """Where a value rests on at least one observation.

        Returns
        -------
        ndarray of bool, shape ``(T, N)``
            True for quality 0 or 1 with a finite value. False for
            gap-filled months, which hold a number but no observation.
        """
        return qa.composite_observed(self.quality) & np.isfinite(self.value)

    def usable(self, min_nights: int = c.MIN_NIGHTS) -> NDArray[np.float64]:
        """Monthly values fit for the status: good quality and enough nights.

        Parameters
        ----------
        min_nights : int
            Nights a value must rest on.

        Returns
        -------
        ndarray of float64, shape ``(T, N)``
            The value where quality is 0 and ``nights >= min_nights``, NaN
            elsewhere. "Not usable" is never zero. In the files read so far
            quality 0 always has 4 or more nights, so the default adds
            nothing to the quality test; a higher value does.
        """
        good = qa.composite_observed(self.quality, good_only=True) & (self.nights >= min_nights)
        return np.where(good & np.isfinite(self.value), self.value.astype(np.float64), np.nan)

    def seasonal(self, min_nights: int = c.MIN_NIGHTS) -> composite.Seasonal:
        """Three-month composite of every cell.

        Parameters
        ----------
        min_nights : int
            Nights a pooled value must rest on.

        Returns
        -------
        composite.Seasonal
            As ``composite.three_month`` on the observed months, with the
            value set to NaN where the window holds fewer than
            ``min_nights``. The first and last rows are NaN.
        """
        pooled = composite.three_month(self.value, self.nights, self.observed())
        value = np.where(pooled.nights >= min_nights, pooled.value, np.nan)
        return composite.Seasonal(value=value, nights=pooled.nights, centre_share=pooled.centre_share)


def month_range(first: dt.date, last: dt.date) -> tuple[dt.date, ...]:
    """First days of every calendar month from ``first`` to ``last``, inclusive.

    Parameters
    ----------
    first, last : datetime.date
        Both the first day of a month.

    Returns
    -------
    tuple of datetime.date

    Raises
    ------
    ValueError
        If either date is not the first of a month, or ``last`` precedes ``first``.
    """
    if first.day != 1 or last.day != 1:
        raise ValueError("month_range takes first-of-month dates")
    if last < first:
        raise ValueError("last month is before the first")
    out, year, month = [], first.year, first.month
    while (year, month) <= (last.year, last.month):
        out.append(dt.date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(out)


def monthly_files(root: str | Path, tile: str) -> dict[dt.date, Path]:
    """The monthly composite files on disk for a tile, one per month.

    Parameters
    ----------
    root : str or Path
        Data root (the ``--root`` of ``ntl.download``).
    tile : str
        Tile id, for example ``"h29v09"``.

    Returns
    -------
    dict of datetime.date to Path
        Keyed by the month's first day, ascending. Where a month has more
        than one production on disk, the latest production stamp is kept.

    Raises
    ------
    ValueError
        If the tile id is malformed.
    FileNotFoundError
        If no file is found.
    """
    parse_tile(tile)
    product = c.MONTHLY_PRODUCT
    found: dict[dt.date, Path] = {}
    for path in sorted(Path(root).glob(f"{c.BLACK_MARBLE_DIR}/{product}/*/*/{product}.*.{tile}.*.h5")):
        parsed = parse_granule_name(path.name)
        if parsed is None or parsed[0] != product:
            continue
        if parsed[1].day != 1:
            log.warning("%s: a monthly file not dated the first of a month; ignored", path.name)
            continue
        found[parsed[1]] = path  # names sort by production stamp, so the last one wins
    if not found:
        raise FileNotFoundError(f"no {product} file for tile {tile} under {root}")
    return dict(sorted(found.items()))


def unit_maps_from_shapes(
    shapes: Iterable[tuple[Any, int, int, int]],
    grid: Grid,
) -> dict[str, NDArray[np.int64]]:
    """One unit map per admin level from sub-district polygons.

    Parameters
    ----------
    shapes : iterable of (geometry, province, district, subdistrict)
        Each polygon with its three ``siak`` codes as stored (integers); 0
        where the polygon has no code at that level.
    grid : Grid
        The tile's grid.

    Returns
    -------
    dict of str to ndarray of int64
        ``"province"``, ``"district"``, ``"subdistrict"``, each of
        ``grid.shape``: the codes of the polygon containing each cell's
        centre, resolved so that 0 defers to the level above
        (``zonal.resolve_levels``).

    Raises
    ------
    TypeError
        If a code is not an integer (floats are refused, not truncated).
    ValueError
        As ``zonal.resolve_levels``.

    Notes
    -----
    The polygons are burned once and every level is looked up from the
    same polygon, so a cell cannot take its sub-district from one polygon
    and its district from another where polygons overlap. A polygon with no
    code at any level still occupies its cells, which then belong to no unit.
    """
    rows = list(shapes)
    levels = zonal.resolve_levels(
        zonal.integer_codes(np.array([row[1] for row in rows]), "province codes"),
        zonal.integer_codes(np.array([row[2] for row in rows]), "district codes"),
        zonal.integer_codes(np.array([row[3] for row in rows]), "sub-district codes"),
    ) if rows else {level: np.zeros(0, dtype=np.int64) for level in c.ADMIN_LEVELS}
    position = zonal.burn_index((row[0] for row in rows), grid)
    return {level: np.concatenate([[c.NO_UNIT], levels[level]])[position] for level in c.ADMIN_LEVELS}


def unit_maps_from_file(path: str | Path, grid: Grid) -> dict[str, NDArray[np.int64]]:
    """Unit maps for a grid from the sub-district boundary file.

    Parameters
    ----------
    path : str or Path
        A polygon file readable by geopandas with integer fields
        ``a1siak``, ``a2siak``, ``a3siak``, in geographic coordinates.
    grid : Grid
        The tile's grid. Only polygons intersecting its bounds are read.

    Returns
    -------
    dict of str to ndarray of int64
        As :func:`unit_maps_from_shapes`.

    Raises
    ------
    ValueError
        If the file's coordinate system is not geographic, or a code field
        is absent or holds a missing value.
    TypeError, ValueError
        As :func:`unit_maps_from_shapes`.

    Notes
    -----
    Reading the detailed national polygons for one tile can take several GB
    of memory.
    """
    import geopandas as gpd

    frame = gpd.read_file(path, bbox=grid.bounds)
    if frame.crs is not None and not frame.crs.is_geographic:
        raise ValueError(f"{path}: coordinates are not geographic ({frame.crs})")
    fields = ("a1siak", "a2siak", "a3siak")
    for name in fields:
        if name not in frame.columns:
            raise ValueError(f"{path}: no field {name}")
        if frame[name].isna().any():
            raise ValueError(f"{path}: field {name} has missing values")
    return unit_maps_from_shapes(zip(frame.geometry, *(frame[name].to_numpy() for name in fields)), grid)


def lit_domain(
    land: ArrayLike,
    in_province: ArrayLike,
    good_months: ArrayLike,
    mean_radiance: ArrayLike,
    lit_min: float = c.LIT_MIN_RADIANCE,
    min_good_months: int = c.LIT_MIN_GOOD_MONTHS,
    source: ArrayLike | None = None,
) -> NDArray[np.bool_]:
    """The status domain: lit land cells inside a province.

    Parameters
    ----------
    land : array_like of bool
        Fixed land class, coast excluded (``composite.is_fixed_land``).
    in_province : array_like of bool
        True where the cell lies in a province.
    good_months : array_like of int
        Good-quality AllAngle months of each cell in the defining period.
    mean_radiance : array_like of float
        Mean radiance over those months, nW cm-2 sr-1.
    lit_min, min_good_months : float, int
        The picked rule (``conventions``).
    source : array_like of bool, optional
        True where the cell is a consistent light source
        (``sources.consistent_sources``). Such a cell is lit whatever its mean.

    Returns
    -------
    ndarray of bool
        True where all hold: land, in a province, at least
        ``min_good_months`` good months, and either a mean of at least
        ``lit_min`` or, if ``source`` is given, a consistent source.
    """
    lit = np.asarray(mean_radiance, dtype=np.float64) >= lit_min
    if source is not None:
        lit = lit | np.asarray(source, dtype=bool)
    return np.asarray(land, dtype=bool) & np.asarray(in_province, dtype=bool) & (np.asarray(good_months) >= min_good_months) & lit


def build_stack(
    root: str | Path,
    tile: str,
    unit_maps: Mapping[str, NDArray[np.int64]],
    view: str = c.DEFAULT_VIEW,
    lit_min: float = c.LIT_MIN_RADIANCE,
    min_good_months: int = c.LIT_MIN_GOOD_MONTHS,
    until: dt.date | None = None,
    source_contrast: float | None = None,
) -> TileStack:
    """Read a tile's monthly files into a :class:`TileStack`.

    Parameters
    ----------
    root : str or Path
        Data root holding the files fetched by ``ntl.download``.
    tile : str
        Tile id.
    unit_maps : mapping of str to ndarray of int
        ``"province"``, ``"district"``, ``"subdistrict"`` maps for this
        tile's grid (:func:`unit_maps_from_file`).
    view : str
        View-angle class to collect. The domain is always defined on
        AllAngle so that every class is collected on the same cells.
    lit_min, min_good_months : float, int
        The domain rule (:func:`lit_domain`).
    until : datetime.date, optional
        Use only months strictly before this date for the land mask, the
        domain and ``usual``. Default: the whole record. Values of every
        month are collected either way.
    source_contrast : float, optional
        Add to the domain the cells that are consistent light sources at
        this margin over their background, nW cm-2 sr-1 (``ntl.sources``,
        from the same months as the rest of the domain). Default None:
        the mean rule alone, which is the domain of the statuses.

    Returns
    -------
    TileStack
        Possibly with zero cells, if the tile has no cell in the domain.

    Raises
    ------
    ValueError
        If the view is unknown, a unit map is not an integer array of the
        tile grid's shape, the first file is not on the tile's grid, or
        ``until`` leaves no month.
    FileNotFoundError
        If the tile has no monthly file.
    KeyError
        If a file lacks a layer; the message names the file.

    Notes
    -----
    A month with no file between the first and last file gets NaN values, 0
    nights and quality 255, and is logged. A gap at either end is not
    represented: the record simply starts or ends at the first or last
    file. The first month of the record (January 2012, which starts on the
    19th) and the latest month may cover part of a month: the caller
    decides whether to use them.
    """
    if view not in c.COMPOSITE_VIEWS:
        raise ValueError(f"unknown view {view!r}; expected one of {c.COMPOSITE_VIEWS}")
    files = monthly_files(root, tile)
    months = month_range(min(files), max(files))
    absent = [m for m in months if m not in files]
    if absent:
        log.warning("tile %s: %d month(s) without a file, first %s", tile, len(absent), absent[0])

    grid = read_grid(files[months[0]])
    expected = tile_bounds(parse_tile(tile))
    if not np.allclose(grid.bounds, expected):
        raise ValueError(f"files of tile {tile} have bounds {grid.bounds}, expected {expected}")
    maps = {}
    for level in c.ADMIN_LEVELS:
        array = np.asarray(unit_maps[level])
        if array.shape != grid.shape:
            raise ValueError(f"{level} map has shape {array.shape}, tile grid {grid.shape}")
        maps[level] = zonal.integer_codes(array, f"{level} map")

    domain_months = [m for m in months if m in files and (until is None or m < until)]
    if not domain_months:
        raise ValueError(f"no month before {until} to define the domain")

    def layer(path: Path, name: str, scaled: bool) -> NDArray:
        try:
            return read_scaled(path, name) if scaled else read_raw(path, name)
        except KeyError as exc:
            raise KeyError(f"{path.name}: {exc.args[0]}") from None

    all_angle = c.COMPOSITE_LAYER.format(view=c.DEFAULT_VIEW, suffix="")
    votes = composite.new_class_votes(grid.shape)
    total = np.zeros(grid.shape)
    n_good = np.zeros(grid.shape, dtype=np.uint16)
    n_source = np.zeros(grid.shape, dtype=np.uint16)
    background = sources.background_filter(grid.shape, sources.source_kernel()) if source_contrast is not None else None
    for month in domain_months:
        path = files[month]
        composite.add_class_votes(votes, layer(path, c.COMPOSITE_LAND_WATER, False))
        good = qa.composite_observed(layer(path, all_angle + c.COMPOSITE_QUALITY, False), good_only=True)
        radiance = layer(path, all_angle, True)
        good &= np.isfinite(radiance)
        total[good] += radiance[good]
        n_good += good
        if background is not None:
            n_source += sources.is_source(radiance, good, background(radiance, good), source_contrast)
    land = composite.is_fixed_land(composite.modal_class(votes))
    del votes
    mean = np.where(n_good > 0, total / np.maximum(n_good, 1), 0.0)
    in_province = maps["province"] > c.NO_UNIT
    source = sources.consistent_sources(n_source, n_good) if source_contrast is not None else None
    rows, cols = np.nonzero(lit_domain(land, in_province, n_good, mean, lit_min, min_good_months, source))
    n = rows.size
    log.info("tile %s: %d cells in the domain, %d of them as a light source under %.1f nW (land in a province: %d)", tile, n,
             int((mean[rows, cols] < lit_min).sum()), lit_min, int((land & in_province).sum()))

    name = c.COMPOSITE_LAYER.format(view=view, suffix="")
    value = np.full((len(months), n), np.nan, dtype=np.float32)
    nights = np.zeros((len(months), n), dtype=np.uint16)
    quality = np.full((len(months), n), c.CQ_FILL, dtype=np.uint8)
    for t, month in enumerate(months):
        if month not in files:
            continue
        path = files[month]
        value[t] = layer(path, name, True)[rows, cols]
        counts = layer(path, name + c.COMPOSITE_NUM, False)[rows, cols]
        nights[t] = np.where(counts == c.COMPOSITE_NUM_FILL, 0, counts)
        quality[t] = layer(path, name + c.COMPOSITE_QUALITY, False)[rows, cols]

    lon_all, lat_all = grid.centres()
    return TileStack(
        tile=tile,
        view=view,
        months=months,
        lon=lon_all[cols],
        lat=lat_all[rows],
        province=maps["province"][rows, cols],
        district=maps["district"][rows, cols],
        subdistrict=maps["subdistrict"][rows, cols],
        usual=mean[rows, cols],
        value=value,
        nights=nights,
        quality=quality,
        until=until,
        lit_min=float(lit_min),
        min_good_months=int(min_good_months),
        source_contrast=None if source_contrast is None else float(source_contrast),
    )


def concat(stacks: Iterable[TileStack]) -> TileStack:
    """Join stacks of neighbouring tiles into one, cell by cell.

    Units that cross a tile edge then sum over all their cells, because the
    statistics group cells by unit code and do not care which tile a cell
    came from (14 provinces, 28 districts and 23 sub-districts cross a tile
    edge in the national join).

    Parameters
    ----------
    stacks : iterable of TileStack
        Stacks of different tiles, built the same way.

    Returns
    -------
    TileStack
        ``tile`` holds the ids joined by ``+``.

    Raises
    ------
    ValueError
        If no stack is given; if the stacks differ in view, months, or the
        way the domain was built; or if a cell appears twice.
    """
    stacks = list(stacks)
    if not stacks:
        raise ValueError("no stack to join")
    first = stacks[0]
    for other in stacks[1:]:
        if other.view != first.view:
            raise ValueError(f"stacks of {first.tile} and {other.tile} differ in view")
        if other.months != first.months:
            raise ValueError(
                f"stacks of {first.tile} ({first.months[0]} to {first.months[-1]}, {len(first.months)} months) and "
                f"{other.tile} ({other.months[0]} to {other.months[-1]}, {len(other.months)} months) differ in months"
            )
        if ((other.until, other.lit_min, other.min_good_months, other.source_contrast)
                != (first.until, first.lit_min, first.min_good_months, first.source_contrast)):
            raise ValueError(f"stacks of {first.tile} and {other.tile} were built with different domain rules")

    def join(name: str, axis: int = 0) -> NDArray:
        return np.concatenate([getattr(s, name) for s in stacks], axis=axis)

    lon, lat = join("lon"), join("lat")
    if lon.size and np.unique(np.column_stack([lon, lat]), axis=0).shape[0] != lon.size:
        raise ValueError("the same cell appears in more than one stack")
    return TileStack(
        tile="+".join(s.tile for s in stacks),
        view=first.view,
        months=first.months,
        lon=lon,
        lat=lat,
        province=join("province"),
        district=join("district"),
        subdistrict=join("subdistrict"),
        usual=join("usual"),
        value=join("value", 1),
        nights=join("nights", 1),
        quality=join("quality", 1),
        until=first.until,
        lit_min=first.lit_min,
        min_good_months=first.min_good_months,
        source_contrast=first.source_contrast,
    )


def _npz_path(path: str | Path) -> Path:
    """The path with a ``.npz`` suffix, which numpy would otherwise append on its own."""
    path = Path(path)
    return path if path.suffix == ".npz" else path.with_name(path.name + ".npz")


def save(stack: TileStack, path: str | Path) -> Path:
    """Write a stack to a compressed ``.npz`` cache.

    Parameters
    ----------
    stack : TileStack
    path : str or Path
        Target; ``.npz`` is added if missing.

    Returns
    -------
    Path
        The file written. It appears under its name only when complete (a
        temporary file is renamed), and records the cache version and how
        the domain was built. A cache is rebuildable from the source files.
    """
    target = _npz_path(path)
    temporary = target.with_name(target.stem + ".part.npz")
    try:
        np.savez_compressed(
            temporary,
            version=c.STACK_CACHE_VERSION,
            tile=stack.tile,
            view=stack.view,
            months=np.array([m.isoformat() for m in stack.months]),
            until="" if stack.until is None else stack.until.isoformat(),
            lit_min=stack.lit_min,
            min_good_months=stack.min_good_months,
            source_contrast=np.nan if stack.source_contrast is None else stack.source_contrast,
            lon=stack.lon, lat=stack.lat,
            province=stack.province, district=stack.district, subdistrict=stack.subdistrict,
            usual=stack.usual, value=stack.value, nights=stack.nights, quality=stack.quality,
        )
        os.replace(temporary, target)
    except BaseException:
        # A failed write must leave neither a half file nor a stray one;
        # an earlier complete cache under the target name is untouched.
        temporary.unlink(missing_ok=True)
        raise
    return target


def load(path: str | Path) -> TileStack:
    """Read a stack written by :func:`save`.

    Parameters
    ----------
    path : str or Path
        The cache; ``.npz`` is added if missing.

    Returns
    -------
    TileStack

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not a stack cache this version can read; the message
        says to rebuild it.

    Notes
    -----
    Caches of version 1 (written before 2026-11-22 without a version) named
    adm2 "regency" and adm3 "district". They are read with those fields
    mapped to ``district`` and ``subdistrict``; their domain rule is taken
    to be the whole record with the default thresholds, which is how every
    version 1 cache was built. Caches of version 1 and 2 were built before
    light sources were added to the domain: ``source_contrast`` is None.
    """
    target = _npz_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"{target}: no such stack cache")
    try:
        archive = np.load(target, allow_pickle=False)
    except (zipfile.BadZipFile, EOFError, ValueError) as exc:
        # A truncated or half-synced file, or one that is not an archive.
        raise ValueError(f"{target}: not a readable stack cache ({exc}); rebuild it") from exc
    if not hasattr(archive, "files"):
        raise ValueError(f"{target}: not a stack cache (a single array, not an archive); rebuild it")
    with archive as z:
        keys = set(z.files)
        version = int(z["version"]) if "version" in keys else 1
        if version == 1:
            wanted = {"tile", "view", "months", "lon", "lat", "province", "regency", "district", "usual", "value", "nights", "quality"}
            names = {"district": "regency", "subdistrict": "district"}
        elif version in (2, c.STACK_CACHE_VERSION):
            wanted = {"tile", "view", "months", "until", "lit_min", "min_good_months", "lon", "lat", "province",
                      "district", "subdistrict", "usual", "value", "nights", "quality"}
            if version == c.STACK_CACHE_VERSION:
                wanted |= {"source_contrast"}
            names = {"district": "district", "subdistrict": "subdistrict"}
        else:
            raise ValueError(f"{target}: cache version {version} is not readable by this code; rebuild it")
        missing = sorted(wanted - keys)
        if missing:
            raise ValueError(f"{target}: not a complete stack cache (missing {missing}); rebuild it")
        until = None if version == 1 or not str(z["until"]) else dt.date.fromisoformat(str(z["until"]))
        return TileStack(
            tile=str(z["tile"]),
            view=str(z["view"]),
            months=tuple(dt.date.fromisoformat(str(m)) for m in z["months"]),
            lon=z["lon"], lat=z["lat"],
            province=z["province"], district=z[names["district"]], subdistrict=z[names["subdistrict"]],
            usual=z["usual"], value=z["value"], nights=z["nights"], quality=z["quality"],
            until=until,
            lit_min=c.LIT_MIN_RADIANCE if version == 1 else float(z["lit_min"]),
            min_good_months=c.LIT_MIN_GOOD_MONTHS if version == 1 else int(z["min_good_months"]),
            source_contrast=float(z["source_contrast"]) if version == c.STACK_CACHE_VERSION and np.isfinite(float(z["source_contrast"])) else None,
        )


def cache_path(folder: str | Path, tile: str, view: str = c.DEFAULT_VIEW) -> Path:
    """Where the cache of one tile and view lives inside a cache folder."""
    return Path(folder) / f"stack_{tile}_{view}.npz"


def load_folder(folder: str | Path, view: str = c.DEFAULT_VIEW) -> TileStack:
    """Every cached tile of one view in a folder, joined into one stack.

    Parameters
    ----------
    folder : str or Path
        A folder of caches named by :func:`cache_path`.
    view : str
        View-angle class.

    Returns
    -------
    TileStack
        The tiles that have at least one cell, joined by :func:`concat`.

    Raises
    ------
    FileNotFoundError
        If the folder holds no cache of that view.
    ValueError
        As :func:`load` and :func:`concat`.
    """
    paths = sorted(Path(folder).glob(f"stack_*_{view}.npz"))
    if not paths:
        raise FileNotFoundError(f"{folder}: no stack cache for view {view}")
    stacks = [load(path) for path in paths]
    for stack in stacks:
        log.info("tile %s: %d cells, %d months", stack.tile, stack.value.shape[1], len(stack.months))
    return concat([stack for stack in stacks if stack.value.shape[1] > 0])


_EXAMPLES = r"""examples:
  python -m ntl.stack --root E:\temp\ntl --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp --out E:\temp\ntl\cache --tiles h29v09 h30v09
  python -m ntl.stack --root E:\temp\ntl --boundaries adm3.shp --out E:\temp\ntl\cache_2018 --tiles h29v09 --until 2018-01-01
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.stack",
        description="Read each tile's monthly Black Marble files into a cache of the lit cells inside an admin unit.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", required=True, type=Path, help="data root holding the files fetched by ntl.download")
    parser.add_argument("--boundaries", required=True, type=Path,
                        help="sub-district polygon file with integer fields a1siak, a2siak, a3siak")
    parser.add_argument("--out", required=True, type=Path, help="cache folder; keep it outside any synced folder")
    parser.add_argument("--tiles", required=True, nargs="+", metavar="hHHvVV", help="tile ids, e.g. h29v09 h30v09")
    parser.add_argument("--view", default=c.DEFAULT_VIEW, choices=c.COMPOSITE_VIEWS, help=f"view-angle class (default {c.DEFAULT_VIEW})")
    parser.add_argument("--until", type=dt.date.fromisoformat,
                        help="fix the lit domain from months before this date, YYYY-MM-DD (default: whole record, which is look-ahead)")
    parser.add_argument("--sources", action="store_true",
                        help="also keep the consistent light sources of ntl.sources under the mean rule: for the map's faint layer "
                             "(python -m ntl.export --faint), not for the statuses; write these stacks to their own folder")
    parser.add_argument("--force", action="store_true", help="rebuild a tile whose cache already exists")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point: build and cache the stack of each tile.

    Returns
    -------
    int
        0 if every tile asked for has a cache at the end; 1 if any failed;
        2 for a usage problem.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        tiles = [parse_tile(t).id for t in args.tiles]
    except ValueError as exc:
        parser.error(str(exc))  # exits with status 2
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for tile in tiles:
        target = cache_path(args.out, tile, args.view)
        if target.is_file() and not args.force:
            log.info("tile %s: cache exists, skipped (%s)", tile, target)
            continue
        try:
            files = monthly_files(args.root, tile)
            grid = read_grid(next(iter(files.values())))
            stack = build_stack(args.root, tile, unit_maps_from_file(args.boundaries, grid), view=args.view, until=args.until,
                                source_contrast=c.SOURCE_MIN_CONTRAST if args.sources else None)
        except (FileNotFoundError, KeyError, ValueError, TypeError) as exc:
            log.error("tile %s: %s", tile, exc)
            failed += 1
            continue
        try:
            save(stack, target)
        except OSError as exc:
            log.error("tile %s: cannot write %s (%s)", tile, target, exc)
            failed += 1
            continue
        log.info("tile %s: %d cells, %d months, domain from %s, wrote %s", tile, stack.value.shape[1], len(stack.months),
                 "the whole record" if stack.until is None else f"months before {stack.until}", target)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
