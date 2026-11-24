"""DMSP F18 beside VIIRS on one grid, for the two years both have: what each sees of the same cells.

The long view does not join the two sensors (``ntl.longview``). This module
makes the comparison behind that decision repeatable, and gives the page two
things to show:

- by class of VIIRS radiance, how many cells F18 calls lit and how bright it
  reads them;
- per admin unit, the share of F18's light that lies in cells where VIIRS
  reads next to nothing.

Yearly VIIRS. For each 15 arc-second cell of Black Marble's monthly product
(VNP46A3, the all-angle composite), the median of the year's months of good
quality (``ntl.qa.composite_observed`` with ``good_only``). Every cell is
kept, not only the lit cells of the dashboard. A DMSP cell is exactly two by
two of those cells, and takes the mean of the ones that have a value; cells
are placed by their coordinates, so a DMSP cell that straddles two tiles is
handled. Measured over Indonesia on 2026-11-24: the median, the mean and the
mean without the quality screen pair equally well with F18 (correlation with
the digital number 0.946, 0.942, 0.937 for 2013), and counts of lit months
pair clearly worse.

Reading the second quantity. Black Marble sets very low radiance to zero, so
"under :data:`DARK_NW`" means below what that product keeps, not no light.
Over Indonesia a third of the cells F18 calls lit are of this kind, and 86% of
their light lies within three DMSP cells of a VIIRS cell of 0.5 nW: most of it
is the wider footprint of DMSP around lights VIIRS does see. It is larger
where towns are small and far apart. It is not a ratio between the sensors,
and none is computed here: that depends on which VIIRS product is used.

Nothing here is specific to Indonesia.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from ntl import conventions as c
from ntl import dmsp, qa, stack
from ntl.read import Grid, read_grid, read_raw, read_scaled

log = logging.getLogger("ntl.sensors")

#: Yearly VIIRS radiance below which a cell counts as dark in VIIRS, nW cm-2 sr-1. Picked: half of
#: the lowest class in which F18 calls most cells lit (57% at 0.25 to 0.5 nW, 4% below).
DARK_NW: Final[float] = 0.25
#: Edges of the classes of yearly VIIRS radiance, nW cm-2 sr-1; the last class is open. Picked: doubling steps.
CLASS_EDGES: Final[tuple[float, ...]] = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
#: Fewest F18-lit cells a unit needs for its share to be given. Picked, as the 20-cell minimum of the statuses.
MIN_LIT_CELLS: Final[int] = 20


def add_to_grid(total: NDArray[np.float64], count: NDArray, values: NDArray, source: Grid, target: Grid) -> None:
    """Add a finer grid's values into the cells of a coarser grid that contain them, in place.

    Parameters
    ----------
    total : ndarray of float64, shape ``target.shape``
        Running sum; updated in place.
    count : ndarray of int, shape ``target.shape``
        How many fine cells with a value went into each cell; updated in place.
    values : ndarray, shape ``source.shape``
        NaN where there is no value; such cells add nothing.
    source, target : Grid
        Each fine cell goes to the coarse cell that holds its centre. Fine
        cells outside the coarse grid are left out.
    """
    lon, lat = source.centres()
    col = np.floor((lon - target.west) / target.cell + 1e-9).astype(np.int64)
    row = np.floor((target.north - lat) / target.cell + 1e-9).astype(np.int64)
    keep_col, keep_row = (col >= 0) & (col < target.shape[1]), (row >= 0) & (row < target.shape[0])
    block = np.asarray(values)[np.ix_(keep_row, keep_col)]
    rows, cols = np.meshgrid(row[keep_row], col[keep_col], indexing="ij")
    has = np.isfinite(block)
    np.add.at(total, (rows[has], cols[has]), block[has])
    np.add.at(count, (rows[has], cols[has]), 1)


def yearly_viirs(root: str | Path, year: int, grid: Grid) -> tuple[NDArray[np.float32], NDArray[np.uint8]]:
    """Yearly Black Marble radiance on a DMSP grid.

    Parameters
    ----------
    root : str or Path
        Data root holding the monthly files fetched by ``ntl.download``.
    year : int
    grid : Grid
        The DMSP grid of the crops (``ntl.dmsp``).

    Returns
    -------
    (ndarray of float32, ndarray of uint8), each of shape ``grid.shape``
        Radiance in nW cm-2 sr-1: the mean, over the fine cells that have
        one, of each fine cell's median over its months of good quality;
        NaN where no fine cell has a value. And the number of fine cells
        (0 to 4) behind it.

    Raises
    ------
    FileNotFoundError
        If the year has no monthly file.
    """
    product = "VNP46A3"
    tiles = sorted({path.name.split(".")[2] for path in Path(root).glob(f"{c.BLACK_MARBLE_DIR}/{product}/{year}/*/{product}.*.h5")})
    if not tiles:
        raise FileNotFoundError(f"no {product} file for {year} under {root}")
    layer = c.COMPOSITE_LAYER.format(view=c.DEFAULT_VIEW, suffix="")
    total = np.zeros(grid.shape)
    count = np.zeros(grid.shape, dtype=np.uint8)
    for tile in tiles:
        files = {month: path for month, path in stack.monthly_files(root, tile).items() if month.year == year}
        if not files:
            continue
        tile_grid = read_grid(next(iter(files.values())))
        months = np.full((len(files),) + tile_grid.shape, np.nan, dtype=np.float32)
        for i, month in enumerate(sorted(files)):
            good = qa.composite_observed(read_raw(files[month], layer + c.COMPOSITE_QUALITY), good_only=True)
            radiance = read_scaled(files[month], layer)
            months[i] = np.where(good & np.isfinite(radiance), radiance, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # a cell with no good month has no median: NaN is the answer
            median = np.nanmedian(months, axis=0)
        add_to_grid(total, count, median, tile_grid, grid)
        log.info("%d %s: %d months", year, tile, len(files))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan).astype(np.float32), count


def by_class(dn: NDArray, light: NDArray, inside: NDArray[np.bool_], edges: Sequence[float] = CLASS_EDGES) -> list[dict[str, Any]]:
    """What the DMSP satellite sees in each class of VIIRS radiance.

    Parameters
    ----------
    dn : ndarray
        Corrected DMSP digital number per cell; 0 is not lit.
    light : ndarray, same shape
        Yearly VIIRS radiance, nW cm-2 sr-1; NaN where there is none.
    inside : ndarray of bool, same shape
        Cells to count (those inside an admin unit).
    edges : sequence of float
        Lower edges of the classes, ascending; the last class is open.

    Returns
    -------
    list of dict
        Per class: ``low``, ``high`` (None for the open class), ``cells``,
        ``lit_share`` (share the DMSP satellite calls lit; None with no
        cell) and ``median_dn`` of those lit cells (None with none).
    """
    out = []
    has = inside & np.isfinite(light)
    for k, low in enumerate(edges):
        high = edges[k + 1] if k + 1 < len(edges) else None
        chosen = has & (light >= low) & ((light < high) if high is not None else True)
        cells = int(chosen.sum())
        lit = dn[chosen] > 0
        out.append({"low": low, "high": high, "cells": cells, "lit_share": round(float(lit.mean()), 4) if cells else None,
                    "median_dn": round(float(np.median(dn[chosen][lit])), 2) if lit.any() else None})
    return out


def unseen_share(dn: NDArray, light: NDArray, units: NDArray, codes: NDArray, dark: float = DARK_NW) -> NDArray[np.float64]:
    """Per unit, the share of the DMSP satellite's light in cells where VIIRS reads under ``dark``.

    Parameters
    ----------
    dn, light : ndarray
        As :func:`by_class`.
    units : ndarray of int, same shape
        Unit code per cell, ``conventions.NO_UNIT`` outside.
    codes : ndarray of int
        Unit codes to report, strictly ascending.
    dark : float
        nW cm-2 sr-1.

    Returns
    -------
    ndarray of float64, shape (units,)
        Between 0 and 1. Only cells with a VIIRS value are counted. NaN for
        a unit with fewer than :data:`MIN_LIT_CELLS` such cells lit in DMSP.
    """
    counted = np.isin(units, codes) & np.isfinite(light) & (dn > 0)
    index = np.searchsorted(codes, units[counted])
    value = dn[counted].astype(np.float64)
    lit = np.bincount(index, minlength=len(codes))
    total = np.bincount(index, weights=value, minlength=len(codes))
    unseen = np.bincount(index, weights=np.where(light[counted] < dark, value, 0.0), minlength=len(codes))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(lit >= MIN_LIT_CELLS, unseen / total, np.nan)


def compare(root: str | Path, crops: str | Path, eog: str | Path, units: Mapping[str, NDArray], years: Sequence[int], satellite: str = "F18",
            cache: str | Path | None = None) -> dict[str, Any]:
    """The comparison for the site, for each year both sensors cover.

    Parameters
    ----------
    root, crops, eog : str or Path
        The Black Marble data root, the DMSP crops and EOG's intercalibrated files.
    units : mapping of str to ndarray of int
        Per admin level, unit code per cell of the crops' grid.
    years : sequence of int
    satellite : str
        The DMSP satellite of those years.
    cache : str or Path, optional
        Folder for the yearly VIIRS grids (``viirs_dmsp_<year>.npz``); read
        from there when present, since a year takes minutes to build.

    Returns
    -------
    dict
        ``years``; ``dark_nw``; ``classes`` (year to :func:`by_class`, over
        cells inside a unit of the first level given); and per level
        ``codes`` and ``unseen`` (year to a list per unit, None for NaN).

    Raises
    ------
    FileNotFoundError
        If a crop or an intercalibrated file of ``satellite`` is missing for a year.
    ValueError
        If a unit map does not match the crops' grid.
    """
    crops, eog = Path(crops), Path(eog)
    out: dict[str, Any] = {"years": [int(y) for y in years], "satellite": satellite, "dark_nw": DARK_NW, "classes": {}, "levels": {}}
    grid = None
    for year in years:
        crop_file = crops / f"{satellite}{year}.npz"
        corrected = sorted(eog.glob(f"{satellite}{year}*intercal.stable_lights.avg_vis.tif"))
        if not crop_file.is_file() or len(corrected) != 1:
            raise FileNotFoundError(f"need one crop and one intercalibrated file for {satellite}{year}; found {crop_file.is_file()} and {len(corrected)}")
        grid = dmsp.load_crop(crop_file).grid
        for level, codes_map in units.items():
            if codes_map.shape != grid.shape:
                raise ValueError(f"unit map '{level}' has {codes_map.shape} cells, the crops have {grid.shape}")
        dn = dmsp.read_window(corrected[0], grid)
        stored = Path(cache) / f"viirs_dmsp_{year}.npz" if cache else None
        if stored is not None and stored.is_file():
            with np.load(stored, allow_pickle=False) as z:
                light = z["light"]
        else:
            light, cells = yearly_viirs(root, year, grid)
            if stored is not None:
                stored.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(stored, light=light, cells=cells)
        first = next(iter(units.values()))
        out["classes"][str(year)] = by_class(dn, light, first != c.NO_UNIT)
        for level, codes_map in units.items():
            codes = np.unique(codes_map[codes_map != c.NO_UNIT])
            entry = out["levels"].setdefault(level, {"codes": [int(code) for code in codes], "unseen": {}})
            entry["unseen"][str(year)] = [None if not np.isfinite(v) else round(float(v), 3) for v in unseen_share(dn, light, codes_map, codes)]
        log.info("%d: %d cells with a VIIRS value inside a unit", year, int((np.isfinite(light) & (first != c.NO_UNIT)).sum()))
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.sensors",
        description="Compare the DMSP satellite F18 with yearly VIIRS on the DMSP grid, for the years both cover.",
        epilog="example:\n" r"  python -m ntl.sensors --root E:\temp\ntl --crops E:\temp\ntl\dmsp --eog E:\temp\ntl\eog --units E:\temp\ntl\dmsp_work\dmsp_units.npz" "\n"
        r"      --cache E:\temp\ntl\dmsp_work --out E:\temp\ntl\longrecord\sensors.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", required=True, type=Path, help="data root of ntl.download (the monthly Black Marble files); only read")
    parser.add_argument("--crops", required=True, type=Path, help="folder of FssYYYY.npz from python -m ntl.dmsp")
    parser.add_argument("--eog", required=True, type=Path, help="folder of EOG's intercalibrated stable lights; only read")
    parser.add_argument("--units", required=True, type=Path, help=".npz of unit codes per cell of the crops' grid (python -m ntl.longrecord --keep-units)")
    parser.add_argument("--levels", nargs="+", default=["province", "district"], help="admin levels (default: province district)")
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2013], help="years both sensors cover (default: 2012 2013)")
    parser.add_argument("--cache", type=Path, help="folder to keep the yearly VIIRS grids in, and to read them from")
    parser.add_argument("--out", required=True, type=Path, help="the JSON file to write (read by python -m ntl.longview --sensors)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 on a problem with the inputs."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        with np.load(args.units, allow_pickle=False) as maps:
            units = {level: maps[level] for level in args.levels}
        result = compare(args.root, args.crops, args.eog, units, args.years, cache=args.cache)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.out.with_suffix(".json.part")
        temporary.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        temporary.replace(args.out)
        log.info("written %s", args.out)
    except ImportError as exc:
        log.error("%s: the comparison needs h5py and rasterio", exc)
        return 1
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
