"""DMSP-OLS yearly composites, 1992 to 2013: from EOG's archives to arrays over Indonesia.

The explorer's record starts in 2012, where VIIRS starts. DMSP-OLS adds
twenty earlier years, as one global grid per satellite and year. This
module only brings those grids into reach: it crops them to a box and keeps
the three layers apart. Making satellites agree with each other and with
VIIRS is a model on top of this (``temp/dmsp-fusion-plan.md``), not part of it.

Product: EOG's Version 4 DMSP-OLS Nighttime Lights Time Series, one archive
per satellite-year (F10 1992 to F18 2013, 34 of them), each with three
grids of 30 arc-seconds, read from the files on 2026-11-24:

- ``stable_lights.avg_vis``: the cleaned yearly lights as a digital number
  from 0 to 63. Not radiance: the sensor has no on-board calibration, and
  the brightest city cores sit at 63 whatever they do.
- ``avg_vis``: the raw yearly average, with fires and background noise kept.
- ``cf_cvg``: how many cloud-free observations went into the year.

EOG also publishes the stable lights after its own intercalibration (files
named ``intercal``, floating point); :func:`read_box` reads those as well.
Both come from https://eogdata.mines.edu/products/dmsp/ (in November 2026
the downloads asked for a sign-in, and the files were fetched by hand).

None of the grids carries a fill value: 0 is "no stable light", and a cell
with no cloud-free observation is 0 as well, so dark and unseen can only be
told apart with ``cf_cvg``.

A known slip in EOG's headers. Three intercalibrated files (F16 2009,
F18 2010, F18 2011) give their north-west corner as 180 W, 75 N, half a cell
from the other 31. Measured on 2026-11-24 over Indonesia: in all 34
satellite-years the cells above zero are exactly the cells above zero in the
archive of the same satellite-year when read by position, and fewer agree
when either is moved by one cell. So the data sit on the usual cells and only
the header differs. :func:`read_window` reads such a file by position and
logs a warning; any other origin is refused.

The global grid has 43,201 columns and 16,801 rows. Cell CENTRES sit on
multiples of 1/120 degree, from 180 W to 180 E and from 75 N to 65 S, so
each cell covers exactly two by two cells of the 15 arc-second VIIRS grid.

Nothing here is specific to Indonesia except the default box.
"""

from __future__ import annotations

import argparse
import gzip
import logging
import re
import shutil
import sys
import tarfile
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Final, NamedTuple

import numpy as np
from numpy.typing import NDArray

from ntl import conventions as c
from ntl.read import Grid

log = logging.getLogger("ntl.dmsp")

#: Cell size of the DMSP grids, degrees (30 arc-seconds).
DMSP_CELL: Final[float] = 1.0 / 120.0
#: Outer edges of the global grid's north-west cell: half a cell beyond 180 W and 75 N.
DMSP_WEST: Final[float] = -180.0 - DMSP_CELL / 2.0
DMSP_NORTH: Final[float] = 75.0 + DMSP_CELL / 2.0
#: Rows and columns of the global grid.
DMSP_SHAPE: Final[tuple[int, int]] = (16801, 43201)
#: Top of the digital number scale.
DMSP_MAX: Final[int] = 63
#: Digital number from which a cell of the archived stable lights is taken as saturated. Picked: the
#: scale ends at 63 and the brightest city cores sit within a few numbers of it.
SATURATED_DN: Final[int] = 60
#: The north-west corner three of EOG's intercalibrated files state by mistake (see the module docstring).
HEADER_SLIP: Final[tuple[float, float]] = (-180.0, 75.0)
#: How far a header may sit from the expected corner, degrees (a thousandth of a cell and more).
ORIGIN_TOLERANCE: Final[float] = 1e-6
#: Slack, in cells, when a box edge falls on a cell edge, so that a grid's own bounds give the grid back.
EDGE_TOLERANCE: Final[float] = 1e-7
#: Bytes copied at a time when a layer is unpacked.
COPY_CHUNK: Final[int] = 16 * 1024 * 1024
#: The three layers of an archive, by the text that marks their file names.
LAYERS: Final[dict[str, str]] = {"stable": ".stable_lights.avg_vis.tif", "average": ".avg_vis.tif", "observations": ".cf_cvg.tif"}
#: The box cropped by default: the project's box for Indonesia (west, south, east, north).
INDONESIA_BOX: Final[tuple[float, float, float, float]] = c.INDONESIA_BBOX

_NAME = re.compile(r"^(F\d{2})(\d{4})\b")


class Crop(NamedTuple):
    """One satellite-year over a box.

    Attributes
    ----------
    satellite : str
        For example ``"F12"``.
    year : int
    grid : Grid
        Georeferencing of the arrays (cell 1/120 degree).
    stable, average : ndarray of uint8, shape ``grid.shape``
        Digital number 0 to 63, as stored. 0 is "no light"; there is no fill.
    observations : ndarray of uint8, shape ``grid.shape``
        Cloud-free observations behind the year, as stored. 0 means the cell
        was never seen, and its light of 0 is then unseen, not dark.
    """

    satellite: str
    year: int
    grid: Grid
    stable: NDArray[np.uint8]
    average: NDArray[np.uint8]
    observations: NDArray[np.uint8]


def satellite_year(name: str) -> tuple[str, int]:
    """Satellite and year from a file name such as ``F101992.v4.tar``.

    Parameters
    ----------
    name : str
        A file name or path.

    Returns
    -------
    (str, int)
        For example ``("F10", 1992)``.

    Raises
    ------
    ValueError
        If the name does not start with a satellite and a year.
    """
    found = _NAME.match(Path(name).name)
    if not found:
        raise ValueError(f"{name}: not a DMSP satellite-year file name (expected FssYYYY...)")
    return found.group(1), int(found.group(2))


def box_window(box: tuple[float, float, float, float]) -> tuple[slice, slice, Grid]:
    """Rows and columns of the global grid that cover a box, and their georeferencing.

    Parameters
    ----------
    box : (west, south, east, north)
        Degrees.

    Returns
    -------
    (slice, slice, Grid)
        A cell is included if any part of it lies inside the box.

    Raises
    ------
    ValueError
        If the box is not ordered or lies outside the grid.
    """
    west, south, east, north = box
    if not (west < east and south < north):
        raise ValueError(f"box {box} is not west, south, east, north")
    # the slack keeps a box that ends on a cell edge from gaining a row or column through rounding
    col0 = int(np.floor((west - DMSP_WEST) / DMSP_CELL + EDGE_TOLERANCE))
    col1 = int(np.ceil((east - DMSP_WEST) / DMSP_CELL - EDGE_TOLERANCE))
    row0 = int(np.floor((DMSP_NORTH - north) / DMSP_CELL + EDGE_TOLERANCE))
    row1 = int(np.ceil((DMSP_NORTH - south) / DMSP_CELL - EDGE_TOLERANCE))
    if col0 < 0 or row0 < 0 or col1 > DMSP_SHAPE[1] or row1 > DMSP_SHAPE[0]:
        raise ValueError(f"box {box} is not inside the DMSP grid (180 W to 180 E, 65 S to 75 N)")
    grid = Grid(west=DMSP_WEST + col0 * DMSP_CELL, north=DMSP_NORTH - row0 * DMSP_CELL, cell=DMSP_CELL, shape=(row1 - row0, col1 - col0))
    return slice(row0, row1), slice(col0, col1), grid


def grid_offsets(grid: Grid) -> tuple[int, int]:
    """Row and column of a grid's north-west cell on the global DMSP grid.

    Raises
    ------
    ValueError
        If the grid is not made of whole cells of the global grid.
    """
    col = (grid.west - DMSP_WEST) / DMSP_CELL
    row = (DMSP_NORTH - grid.north) / DMSP_CELL
    rows, cols = grid.shape
    if abs(grid.cell - DMSP_CELL) > 1e-12 or abs(col - round(col)) > 1e-4 or abs(row - round(row)) > 1e-4:
        raise ValueError(f"grid at {grid.west}, {grid.north} with cell {grid.cell} is not on the global DMSP grid")
    row, col = round(row), round(col)
    if row < 0 or col < 0 or row + rows > DMSP_SHAPE[0] or col + cols > DMSP_SHAPE[1]:
        raise ValueError(f"grid at {grid.west}, {grid.north} of {grid.shape} cells reaches outside the global DMSP grid")
    return row, col


def read_window(path: str | Path, grid: Grid) -> NDArray:
    """The cells of one global DMSP file that a grid covers, values as stored.

    Parameters
    ----------
    path : str or Path
        A global GeoTIFF: a layer of an archive, or one of EOG's
        intercalibrated files. Only read.
    grid : Grid
        A window of the global grid (from :func:`box_window` or a crop).

    Returns
    -------
    ndarray, shape ``grid.shape``
        Digital numbers, unscaled, in the file's own dtype (``uint8`` in the
        archives, ``float32`` in the intercalibrated files). No fill value.

    Raises
    ------
    ValueError
        If the file does not have the global grid's shape, cell and corner.
        The one corner accepted besides the true one is :data:`HEADER_SLIP`,
        read by position with a warning (see the module docstring).
    """
    import rasterio  # an optional dependency, as for ntl.zonal
    from rasterio.windows import Window

    row, col = grid_offsets(grid)
    rows, cols = grid.shape
    with rasterio.open(path) as source:
        if (source.height, source.width) != DMSP_SHAPE:
            raise ValueError(f"{path}: {source.height} by {source.width} cells, expected the global DMSP grid {DMSP_SHAPE}")
        header = source.transform
        if abs(header.a - DMSP_CELL) > 1e-8 or abs(header.e + DMSP_CELL) > 1e-8:
            raise ValueError(f"{path}: cell of {header.a} by {-header.e} degrees, expected the global DMSP grid's {DMSP_CELL}")
        if abs(header.c - DMSP_WEST) > ORIGIN_TOLERANCE or abs(header.f - DMSP_NORTH) > ORIGIN_TOLERANCE:
            if abs(header.c - HEADER_SLIP[0]) > ORIGIN_TOLERANCE or abs(header.f - HEADER_SLIP[1]) > ORIGIN_TOLERANCE:
                raise ValueError(f"{path}: corner at {header.c}, {header.f}, expected the global DMSP grid's {DMSP_WEST}, {DMSP_NORTH}")
            log.warning("%s: header corner %s, %s is EOG's known half-cell slip; read by position", Path(path).name, header.c, header.f)
        return source.read(1, window=Window(col, row, cols, rows))


def read_box(path: str | Path, box: tuple[float, float, float, float] = INDONESIA_BOX) -> tuple[NDArray, Grid]:
    """One global DMSP grid over a box, values as stored.

    Parameters
    ----------
    path : str or Path
    box : (west, south, east, north)

    Returns
    -------
    (ndarray, Grid)
        As :func:`read_window`, with the georeferencing of the cells read.

    Raises
    ------
    ValueError
        As :func:`box_window` and :func:`read_window`.
    """
    grid = box_window(box)[2]
    return read_window(path, grid), grid


def crop_archive(archive: str | Path, out: str | Path, scratch: str | Path, box: tuple[float, float, float, float] = INDONESIA_BOX) -> Path:
    """Crop the three layers of one EOG archive to a box and save them as one ``.npz``.

    Each layer is unpacked to ``scratch`` in turn (a global grid is about
    0.7 GB unpacked), read over the box and removed. The archive itself is
    only read. Members are picked by name and written under names chosen
    here, so nothing in the archive decides where a file lands.

    Parameters
    ----------
    archive : str or Path
        ``FssYYYY.v4.tar`` as EOG publishes it.
    out, scratch : str or Path
        Where the ``.npz`` goes, and a folder for the unpacked grids; both
        are created. Keep them off synced folders.
    box : (west, south, east, north)

    Returns
    -------
    Path
        ``<out>/<FssYYYY>.npz`` with ``stable``, ``average``,
        ``observations`` and the grid's ``west``, ``north``, ``cell``. It
        appears under its name only when complete.

    Raises
    ------
    ValueError
        If a layer is missing from the archive.
    """
    archive, out, scratch = Path(archive), Path(out), Path(scratch)
    satellite, year = satellite_year(archive.name)
    out.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, NDArray] = {}
    grid = None
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith(".tif.gz")]
        for layer, marker in LAYERS.items():
            # ".avg_vis.tif" also ends the stable lights' name: the stable layer must not be taken for the raw one
            wanted = [m for m in members if m.name.endswith(marker + ".gz") and (layer != "average" or "stable_lights" not in m.name)]
            if len(wanted) != 1:
                raise ValueError(f"{archive.name}: expected one {layer} layer, found {[m.name for m in wanted]}")
            unpacked = scratch / f"{satellite}{year}.{layer}.tif"
            try:
                with tar.extractfile(wanted[0]) as packed, gzip.open(packed) as plain, open(unpacked, "wb") as target:
                    shutil.copyfileobj(plain, target, length=COPY_CHUNK)
                arrays[layer], grid = read_box(unpacked, box)
            finally:
                unpacked.unlink(missing_ok=True)
    target = out / f"{satellite}{year}.npz"
    # ".part.npz", not ".npz.part": numpy would add ".npz" to a name that does not end with it
    temporary = out / f"{satellite}{year}.part.npz"
    try:
        np.savez_compressed(temporary, satellite=satellite, year=year, west=grid.west, north=grid.north, cell=grid.cell, **arrays)
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    log.info("%s%d: %s cells over the box, stable lights up to %s, at %d or more %d", satellite, year, arrays["stable"].shape, arrays["stable"].max(),
             SATURATED_DN, int((arrays["stable"] >= SATURATED_DN).sum()))
    return target


def load_crop(path: str | Path) -> Crop:
    """Read a file written by :func:`crop_archive`.

    Parameters
    ----------
    path : str or Path

    Returns
    -------
    Crop
        The three layers in the dtype they were archived in.
    """
    with np.load(path, allow_pickle=False) as z:
        stable = z["stable"]
        grid = Grid(west=float(z["west"]), north=float(z["north"]), cell=float(z["cell"]), shape=stable.shape)
        return Crop(satellite=str(z["satellite"]), year=int(z["year"]), grid=grid, stable=stable, average=z["average"], observations=z["observations"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.dmsp",
        description="Crop EOG's DMSP-OLS Version 4 yearly archives to a box and keep the three layers of each satellite-year.",
        epilog="example:\n" r"  python -m ntl.dmsp --archives \\server\share\DMSP --out E:\temp\ntl\dmsp --scratch E:\temp\ntl\scratch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--archives", required=True, type=Path, help="folder of FssYYYY.v4.tar files; only read")
    parser.add_argument("--out", required=True, type=Path, help="folder for one .npz per satellite-year")
    parser.add_argument("--scratch", required=True, type=Path,
                        help="folder for the grids while they are unpacked, one at a time (about 0.7 GB); not to be shared by two runs")
    parser.add_argument("--box", nargs=4, type=float, default=list(INDONESIA_BOX), metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                        help="box to crop, degrees (default: the project's box for Indonesia)")
    parser.add_argument("--force", action="store_true", help="crop again a satellite-year that is already there")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 if every archive was cropped, 1 if any failed."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        import rasterio  # noqa: F401  (asked for here so that a missing package is known before anything is unpacked)
    except ImportError:
        log.error("cropping needs rasterio (the 'zonal' extra)")
        return 1
    if not args.archives.is_dir():
        log.error("%s is not a folder that can be reached", args.archives)
        return 1
    archives = sorted(args.archives.glob("F*.tar"))
    if not archives:
        log.error("no F*.tar archive in %s", args.archives)
        return 1
    box = tuple(args.box)
    try:
        wanted = box_window(box)[2]
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    done, skipped, failed = [], [], []
    for archive in archives:
        try:
            satellite, year = satellite_year(archive.name)
            existing = args.out / f"{satellite}{year}.npz"
            if existing.is_file() and not args.force:
                if load_crop(existing).grid == wanted:
                    skipped.append(archive.name)
                    continue
                log.info("%s%d: cropped before to another box, cropped again", satellite, year)
            crop_archive(archive, args.out, args.scratch, box)
            done.append(archive.name)
        except (OSError, ValueError, tarfile.TarError, EOFError, zlib.error, zipfile.BadZipFile) as exc:
            log.error("%s: %s", archive.name, exc)
            failed.append(archive.name)
    log.info("%d cropped, %d already there, %d failed%s", len(done), len(skipped), len(failed), ": " + ", ".join(failed) if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
