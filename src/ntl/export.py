"""Pack a monitor run into the files the dashboard loads.

No statistic is computed here: the statuses and series are values of
``ntl.monitor``, re-packed. Three things are derived from them, because the
page needs them and they are sums or look-ups: each unit's ``light`` (the
sum of its cells' usual radiance), the latest window with observations
(:func:`latest_window`), and the reporting level in that window
(``monitor.reporting_level``). Four further things are computed by their
own modules and packed here: how long a unit has been reading low and how
long it has gone unobserved (``ntl.persistence``), the rate of change of
its light over the record (``ntl.trend``), each cell's light at the start
and at the end of the record (``ntl.firstlight``), and each cell's monthly
classes (``ntl.cellmaps``). What is written under the output folder
(``site/data`` by convention; the layout follows ``drywet-explorer``, the
same owner's project, whose ``gz_write`` helper and ``files.js`` idea are
reused here):

``meta.json``
    Months, levels, status codes, thresholds, encodings, the pooled factors
    by month, which units each bundle holds, and what the run rests on.
``units_<level>.json``
    One record per unit, columnar: ``code``, ``name``, ``cells`` (lit cells),
    ``light`` (sum of the cells' usual radiance, nW cm-2 sr-1) and, for
    sub-districts, ``reporting`` (finest level at which the unit's area can
    be reported in the latest window with observations, ``REPORT_*``; the
    window is named in ``meta.json`` as ``latest``). Also, from the windows
    up to that one: ``trend``, ``trend_low``, ``trend_high`` (percent per
    year, null where there are too few years; ``ntl.trend``),
    ``trend_years``; ``trend_core`` with its bounds and ``core_cells``
    (the same trend over only the cells lit from the first year of the
    record, the like-for-like set); ``episodes``, ``longest_run``,
    ``longest_span``, ``low_windows``, ``regional_windows``,
    ``judged_windows``, ``longest_unseen`` (``ntl.persistence``);
    ``lit_km2`` (area of the lit cells, :func:`cell_area_km2`); and
    ``then_now`` (cells per class of ``firstlight.then_and_now``).
``<level>/<bundle>.bin.gz``
    The status of a group of units. Provinces are one bundle, ``all``;
    districts and sub-districts are bundled by province code, so the
    browser loads only the province the reader opens. Layout: the columns
    of ``conventions.BUNDLE_COLUMNS`` one after another, each
    ``[window, unit]`` in row order, little-endian. Units are in ascending
    code order, which is their order in ``units_<level>.json``.
``cells.u32.gz``, ``cell_usual.u16.gz``, ``cell_<level>.u16.gz``, ``cell_then_now.u8.gz``
    The lit cells: position on the global 15 arc-second grid
    (``row * 86400 + column``, row 0 at 90 N, column 0 at 180 W), usual
    radiance times 10, the position plus 1 of the cell's unit in
    ``units_<level>.json`` (0: none), and the cell's class by its light in
    the first and last three years of the record
    (``ntl.firstlight.then_and_now``).
``cells/<year>.u8.gz``
    One byte per lit cell and month of the year, ``[month, cell]`` in the
    order of ``cells.u32.gz``: the cell's radiance class, its change from
    the same month a year earlier and its observation class
    (``ntl.cellmaps``; the bits and breaks are in ``meta.json``). One file
    per calendar year, so the browser loads only the year on screen.
``outlines/province.geojson``, ``outlines/district.geojson``, ``outlines/subdistrict/<province>.geojson``
    Display outlines from ``ntl.boundaries``, if given.
``files.js``
    Generated: one literal ``FileAttachment`` per file. Observable Framework
    publishes only files named by a string literal.
``export_report.json``
    Size of every file, the total against the budget, and how many values
    were clipped to fit their encoding.

Binary files are gzip-compressed with a zero timestamp, and ``meta.json``
carries no clock time, so a rerun on the same inputs gives the same bytes
for every file except ``export_report.json``, which records when it ran.
Every file is written under a temporary name and renamed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl import cellmaps, firstlight, monitor, persistence, trend
from ntl.files import replace_with as _replace_with
from ntl.stack import TileStack, load_folder

log = logging.getLogger("ntl.export")

#: Columns of the global 15 arc-second grid.
GLOBAL_COLUMNS = round(360.0 / c.CELL_SIZE_DEG)
#: Flag bits of the ``flags`` column.
FLAG_HELD, FLAG_JOINT, FLAG_MONITORABLE = 1, 2, 4
#: Usual radiance is stored as tenths of nW cm-2 sr-1 in 16 bits.
USUAL_SCALE = 10
#: Length of one degree of a great circle on a sphere of the Earth's mean radius (6371.0088 km), km.
KM_PER_DEGREE = np.pi * 6371.0088 / 180.0
#: First-light years are stored as the year minus this, in 8 bits; 0 means none.
FIRST_LIGHT_BASE = 2000


def cell_area_km2(lat: ArrayLike) -> NDArray[np.float64]:
    """Area of a 15 arc-second cell centred at each latitude, km2, on a sphere.

    ``(cell in degrees x km per degree)^2 x cos(latitude)``: about 0.215 km2
    at the equator. A spherical approximation, good to a fraction of a
    percent at Indonesia's latitudes.
    """
    lat = np.asarray(lat, dtype=np.float64)
    side = c.CELL_SIZE_DEG * KM_PER_DEGREE
    return side * side * np.cos(np.radians(np.asarray(lat, dtype=np.float64)))


def gz_write(path: Path, data: bytes) -> int:
    """Write bytes gzip-compressed, atomically, with nothing in the header that changes between runs.

    Parameters
    ----------
    path : Path
        Target file; its folder is created.
    data : bytes
        Uncompressed content.

    Returns
    -------
    int
        Size of the file written, bytes.
    """
    def write(temporary: Path) -> None:
        # filename="" and mtime=0: the header carries neither a name nor a time.
        with open(temporary, "wb") as handle, gzip.GzipFile(filename="", fileobj=handle, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(data)

    return _replace_with(path, write)


def encode(values: ArrayLike, dtype: str, scale: float, missing: int | None) -> tuple[NDArray, int]:
    """Scale and round values into an integer type.

    Parameters
    ----------
    values : array_like
        Numbers; NaN means "no value".
    dtype : str
        Numpy integer dtype, for example ``"<i2"``.
    scale : float
        A stored integer is ``round(value * scale)``.
    missing : int or None
        Code stored for NaN. None: the column must have no NaN.

    Returns
    -------
    ndarray
        The stored integers.
    int
        How many values lay beyond the type's range and were clipped to
        the nearest storable value (never onto the missing code).

    Raises
    ------
    ValueError
        If a value is NaN and the column has no missing code, or the
        missing code is not the lowest or highest value of the type (a
        code inside the range could not be told from a value).
    """
    values = np.asarray(values, dtype=np.float64)
    kind = np.dtype(dtype)
    low, high = np.iinfo(kind).min, np.iinfo(kind).max
    if missing is not None:  # keep the missing code out of the storable range
        if missing not in (low, high):
            raise ValueError(f"missing code {missing} must be {low} or {high} for {kind.name}")
        low, high = (low + 1, high) if missing == low else (low, high - 1)
    absent = ~np.isfinite(values)
    if missing is None and absent.any():
        raise ValueError("a column without a missing code holds values that are not finite")
    scaled = np.round(np.where(absent, 0.0, values) * scale)
    clipped = int(((scaled < low) | (scaled > high)).sum())
    out = np.clip(scaled, low, high).astype(kind)
    if missing is not None:
        out[absent] = missing
    return out, clipped


def bundle_columns(result: monitor.LevelStatus) -> dict[str, NDArray]:
    """The arrays of a level in the order and meaning of ``BUNDLE_COLUMNS``."""
    flags = (result.held.astype(np.uint8) * FLAG_HELD | result.joint.astype(np.uint8) * FLAG_JOINT
             | result.monitorable.astype(np.uint8) * FLAG_MONITORABLE)
    return dict(
        state=result.state, index=result.series.index, anomaly=result.anomaly, relative=result.relative,
        scale=result.scale, relative_scale=result.relative_scale, coverage=result.series.coverage,
        nights=result.series.nights, detectable=result.detectable, flags=flags,
        run=persistence.low_runs(result.state), span=persistence.run_spans(result.state),
        unseen=persistence.unseen_runs(result.state),
    )


def pack_bundle(columns: Mapping[str, NDArray], units: NDArray[np.intp]) -> tuple[bytes, dict[str, int]]:
    """Bytes of one bundle: the chosen units of every column, one column after another.

    Returns
    -------
    bytes
        Uncompressed.
    dict of str to int
        Values clipped, per column (columns with none are left out).
    """
    parts, clipped = [], {}
    for name, dtype, scale, missing in c.BUNDLE_COLUMNS:
        stored, n = encode(columns[name][:, units], dtype, scale, missing)
        parts.append(np.ascontiguousarray(stored).tobytes())
        if n:
            clipped[name] = n
    return b"".join(parts), clipped


def unpack_bundle(data: bytes, windows: int, units: int) -> dict[str, NDArray[np.float64]]:
    """Read a bundle back to numbers: the inverse of :func:`pack_bundle`.

    What the browser does, in Python, so that the round trip can be tested.
    Missing codes come back as NaN; ``state`` and ``flags`` as integers.

    Raises
    ------
    ValueError
        If the length does not match ``windows`` by ``units``.
    """
    width = sum(np.dtype(dtype).itemsize for _, dtype, _, _ in c.BUNDLE_COLUMNS)
    if len(data) != width * windows * units:
        raise ValueError(f"bundle has {len(data)} bytes, expected {width * windows * units} for {windows} windows by {units} units")
    out, at = {}, 0
    for name, dtype, scale, missing in c.BUNDLE_COLUMNS:
        size = np.dtype(dtype).itemsize * windows * units
        stored = np.frombuffer(data, dtype=dtype, count=windows * units, offset=at).reshape(windows, units)
        at += size
        if missing is None:
            out[name] = stored.copy()
        else:
            out[name] = np.where(stored == missing, np.nan, stored.astype(np.float64) / scale)
    return out


def cell_index(lon: ArrayLike, lat: ArrayLike) -> NDArray[np.uint32]:
    """Position of cell centres on the global 15 arc-second grid.

    Parameters
    ----------
    lon, lat : array_like of float
        Cell-centre coordinates, degrees.

    Returns
    -------
    ndarray of uint32
        ``row * 86400 + column``; row 0 is the northernmost (90 N), column
        0 the westernmost (180 W). The centre is recovered as
        ``lon = -180 + (column + 0.5) / 240``, ``lat = 90 - (row + 0.5) / 240``.

    Raises
    ------
    ValueError
        If a point is not a cell centre of that grid (to 1e-6 degree).
    """
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    column = np.floor((lon + 180.0) / c.CELL_SIZE_DEG).astype(np.int64)
    row = np.floor((90.0 - lat) / c.CELL_SIZE_DEG).astype(np.int64)
    back_lon = -180.0 + (column + 0.5) * c.CELL_SIZE_DEG
    back_lat = 90.0 - (row + 0.5) * c.CELL_SIZE_DEG
    if lon.size and (np.abs(back_lon - lon).max() > 1e-6 or np.abs(back_lat - lat).max() > 1e-6):
        raise ValueError("coordinates are not cell centres of the global 15 arc-second grid")
    return (row * GLOBAL_COLUMNS + column).astype(np.uint32)


def bundle_ranges(codes: NDArray[np.int64], level: str) -> dict[str, tuple[int, int]]:
    """Which units each bundle of a level holds: ``{bundle: (first position, count)}``.

    Provinces form one bundle, ``"all"``. Finer levels are bundled by
    province code; codes ascend and nest by prefix, so each bundle is a
    contiguous run of the unit list.
    """
    if level == "province":
        return {"all": (0, int(codes.size))}
    province = codes // (c.ADMIN_DIVISOR["province"] // c.ADMIN_DIVISOR[level])
    if np.any(np.diff(province) < 0):
        raise ValueError(f"{level} codes are not in ascending order")
    out = {}
    for code in np.unique(province):
        members = np.nonzero(province == code)[0]
        out[str(int(code))] = (int(members[0]), int(members.size))
    return out


def _nullable(values: NDArray[np.float64], decimals: int) -> list[float | None]:
    """A float array as a JSON list, NaN as null."""
    return [None if not np.isfinite(v) else round(float(v), decimals) for v in values]


def _write_text(path: Path, text: str) -> int:
    return _replace_with(path, lambda temporary: temporary.write_text(text, encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> int:
    return _write_text(path, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def latest_window(run: monitor.Run) -> int:
    """The last window in which at least half of the provinces were observed.

    The record can end with a month whose files exist but hold no usable
    value yet (2026-11 in the run of 2026-11-23: every unit "not
    observed"). The page opens on this window, and the reporting level is
    taken from it.

    Returns
    -------
    int
        Position of the window; the last one if no window qualifies.
    """
    state = np.asarray(run.levels["province"].state)
    observed = (state != c.STATUS_NOT_OBSERVED).sum(axis=1) * 2 >= state.shape[1]
    hits = np.nonzero(observed)[0]
    return int(hits[-1]) if hits.size else state.shape[0] - 1


def read_outlines(folder: str | Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The feature collections written by ``ntl.boundaries``, and its report.

    Returns
    -------
    dict of str to dict
        A GeoJSON feature collection per level.
    dict
        ``outlines_report.json`` as written beside them (tolerance, method,
        source file); empty if that file is absent.

    Raises
    ------
    FileNotFoundError
        If a level's file is absent.
    ValueError
        If a file is not a feature collection whose features carry
        ``code`` and ``name``.
    """
    out = {}
    for level in c.ADMIN_LEVELS:
        path = Path(folder) / f"{level}.geojson"
        if not path.is_file():
            raise FileNotFoundError(f"{path}: no outlines for this level; run python -m ntl.boundaries")
        try:
            collection = json.loads(path.read_text(encoding="utf-8"))
            for feature in collection["features"]:
                int(feature["properties"]["code"])
                feature["properties"]["name"]
                feature["geometry"]["coordinates"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}: not outlines written by ntl.boundaries ({type(exc).__name__}: {exc})") from exc
        out[level] = collection
    report_path = Path(folder) / "outlines_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return out, report


def _files_js(names: Sequence[str]) -> str:
    """The generated module naming every file by a string literal."""
    lines = [
        "// GENERATED by ntl.export. Do not edit: run the export again.",
        "// Observable Framework publishes only files named by a string literal in a FileAttachment call.",
        'import {FileAttachment} from "observablehq:stdlib";',
        "",
        "export const files = {",
    ]
    lines += [f"  {json.dumps(name)}: FileAttachment({json.dumps(name)})," for name in names]
    lines += ["};", ""]
    return "\n".join(lines)


def export_site(
    stack: TileStack,
    run: monitor.Run,
    out: str | Path,
    outlines: Mapping[str, Mapping[str, Any]] | None = None,
    budget: int = c.SITE_BUDGET_BYTES,
    provenance: Mapping[str, Any] | None = None,
    faint: TileStack | None = None,
) -> dict[str, Any]:
    """Write every file the dashboard loads.

    Parameters
    ----------
    stack : TileStack
        The joined stack the run was made on: cells, their units and their
        usual radiance.
    run : monitor.Run
        The saved run (``monitor.load_levels``).
    out : str or Path
        Output folder. Existing files of the same names are replaced; other
        files are left alone.
    outlines : mapping of str to GeoJSON feature collection, optional
        From :func:`read_outlines`. Without it no outline is written and
        units have no names.
    budget : int
        Size limit for the folder, bytes.
    provenance : mapping, optional
        What the inputs were (run file, cache folder, outline report), put
        into ``meta.json`` under ``source.inputs`` as given. It must hold
        nothing that changes between runs on the same inputs.
    faint : TileStack, optional
        A joined stack built WITH consistent light sources
        (``python -m ntl.stack --sources``). Its cells that are not in
        ``stack`` are written as the map's layer of faint sources:
        ``faint_cells.u32.gz`` (positions, ascending, as ``cells.u32.gz``),
        ``faint_usual.u16.gz`` (mean radiance times ``USUAL_SCALE``) and
        ``faint_province.u16.gz`` (position + 1 in the province list, 0 for
        a province with no lit cell). No status uses them.

    Returns
    -------
    dict
        The export report, as written to ``export_report.json``.

    Raises
    ------
    ValueError
        If the run and the stack disagree on months or units, a level has
        more units than 16 bits can number, ``faint`` was not built with
        light sources, or the output exceeds the budget
        (then ``files.js`` is not written, so the folder cannot be built
        into a site by accident).
    """
    out = Path(out)
    if tuple(run.months) != tuple(stack.months):
        raise ValueError("the run and the stack cover different months")
    sizes: dict[str, int] = {}
    clipped: dict[str, int] = {}
    windows = len(run.months)
    latest = latest_window(run)

    # ---- cells: position, usual radiance, unit at each level
    index = cell_index(stack.lon, stack.lat)
    order = np.argsort(index, kind="stable")
    index = index[order]
    sizes["cells.u32.gz"] = gz_write(out / "cells.u32.gz", index.astype("<u4").tobytes())
    usual, n = encode(stack.usual[order], "<u2", USUAL_SCALE, None)
    if n:
        clipped["cell_usual"] = n
    sizes["cell_usual.u16.gz"] = gz_write(out / "cell_usual.u16.gz", usual.tobytes())

    # ---- cells month by month: radiance, change from a year earlier, observations (one byte each)
    log.info("cells: monthly classes and the comparison of the two ends of the record (about a minute nationally)")
    usable = stack.usable()[: latest + 1][:, order]
    packed = cellmaps.pack(usable, np.asarray(stack.nights)[: latest + 1][:, order])
    span_years = np.array([m.year for m in run.months[: latest + 1]], dtype=np.int64)
    cell_files = {}
    for year in np.unique(span_years):
        rows = np.nonzero(span_years == year)[0]
        name = f"cells/{int(year)}.u8.gz"
        sizes[name] = gz_write(out / "cells" / f"{int(year)}.u8.gz", np.ascontiguousarray(packed[rows]).tobytes())
        cell_files[str(int(year))] = dict(file=name, first_window=int(rows[0]), months=int(rows.size))
    del packed

    # ---- first light, cell by cell (windows up to the latest one with observations)
    cell_years, yearly = firstlight.yearly_cell_medians(usable, span_years)
    del usable
    lit_from = firstlight.first_light(yearly, cell_years)
    # The first-light year is no longer exported (method critique, 2026-11-23): it measured crossing a
    # line, not new light. It still picks the like-for-like cells for the second trend: lit from the first year.
    core = lit_from.from_start & (lit_from.year == int(cell_years[0]))
    # A record shorter than two end periods cannot be compared: every cell is then "unknown".
    then_now = (firstlight.then_and_now(yearly, cell_years) if cell_years.size >= 2 * firstlight.END_YEARS
                else np.full(yearly.shape[1], firstlight.TN_UNKNOWN, dtype=np.uint8))
    sizes["cell_then_now.u8.gz"] = gz_write(out / "cell_then_now.u8.gz", then_now.tobytes())
    area = cell_area_km2(stack.lat[order])
    core_values = stack.usable()[: latest + 1][:, order][:, core]
    core_nights = np.asarray(stack.nights)[: latest + 1][:, order][:, core]
    trend_medians = {}

    # ---- units, bundles and outlines, level by level
    levels_meta: dict[str, Any] = {}
    names: dict[str, dict[int, str | None]] = {}
    for level in c.ADMIN_LEVELS:
        result = run.levels[level]
        codes = np.asarray(result.codes, dtype=np.int64)
        cell_codes = stack.units(level)[order]
        if not np.array_equal(np.unique(cell_codes[cell_codes != c.NO_UNIT]), codes):
            raise ValueError(f"{level}: the units of the run are not the units of the stack's cells")
        if codes.size >= 65535:
            raise ValueError(f"{level}: {codes.size} units do not fit a 16-bit position")
        position = np.where(cell_codes == c.NO_UNIT, 0, np.searchsorted(codes, cell_codes) + 1)
        name = f"cell_{level}.u16.gz"
        sizes[name] = gz_write(out / name, position.astype("<u2").tobytes())

        names[level] = {}
        if outlines is not None:
            names[level] = {int(f["properties"]["code"]): f["properties"]["name"] for f in outlines[level]["features"]}
        light = np.bincount(position, weights=stack.usual[order], minlength=codes.size + 1)[1:]
        units: dict[str, Any] = dict(
            code=codes.tolist(),
            name=[names[level].get(int(code)) for code in codes],
            cells=np.asarray(result.series.cells).astype(int).tolist(),
            light=[round(float(v), 1) for v in light],
        )
        # Trend and episode counts use the windows up to the latest one with observations.
        years = np.array([m.year for m in run.months[: latest + 1]], dtype=np.int64)
        slopes = trend.unit_trends(np.asarray(result.series.index)[: latest + 1], years)
        counts = persistence.summarise(np.asarray(result.state)[: latest + 1])
        units.update(
            trend=_nullable(100.0 * slopes.rate, 2), trend_low=_nullable(100.0 * slopes.low, 2),
            trend_high=_nullable(100.0 * slopes.high, 2), trend_years=slopes.years.astype(int).tolist(),
            episodes=counts.count.astype(int).tolist(), longest_run=counts.longest.astype(int).tolist(),
            low_windows=counts.low_windows.astype(int).tolist(), judged_windows=counts.judged_windows.astype(int).tolist(),
            longest_unseen=persistence.unseen_runs(np.asarray(result.state)[: latest + 1]).max(axis=0).astype(int).tolist(),
            lit_km2=[round(float(v), 2) for v in np.bincount(position, weights=area, minlength=codes.size + 1)[1:]],
        )
        counts_tn = firstlight.unit_class_counts(then_now, position.astype(np.int64) - 1, int(codes.size))
        units.update(then_now=counts_tn.astype(int).tolist(), longest_span=counts.longest_span.astype(int).tolist(),
                     regional_windows=counts.regional_windows.astype(int).tolist())
        # the same trend over the like-for-like cells only: units that have none get no value
        core_series = monitor.level_series(core_values, core_nights, stack.usual[order][core], cell_codes[core])
        core_slopes = trend.unit_trends(core_series.index, years)
        at = np.searchsorted(codes, core_series.codes)

        def spread(values: NDArray[np.float64]) -> list[float | None]:
            """Percent values of the units that have core cells, placed among all units of the level."""
            full = np.full(codes.size, np.nan)
            full[at] = 100.0 * values
            return _nullable(full, 2)

        units.update(trend_core=spread(core_slopes.rate), trend_core_low=spread(core_slopes.low), trend_core_high=spread(core_slopes.high),
                     core_cells=np.bincount(position[core], minlength=codes.size + 1)[1:].astype(int).tolist())
        big = np.asarray(result.series.cells) >= c.MIN_UNIT_CELLS
        trend_medians[level] = dict(
            all=None if not np.isfinite(slopes.rate[big]).any() else round(float(np.nanmedian(100.0 * slopes.rate[big])), 2),
            units=int(np.isfinite(slopes.rate[big]).sum()))
        if level == "subdistrict":
            # From the latest window with observations: in a window nobody was
            # seen in, the scale has no nights factor and the answer differs.
            finest = monitor.reporting_level(
                codes, result.monitorable[latest],
                run.levels["district"].codes, run.levels["district"].monitorable[latest],
                run.levels["province"].codes, run.levels["province"].monitorable[latest])
            units["reporting"] = finest.astype(int).tolist()
        sizes[f"units_{level}.json"] = _write_json(out / f"units_{level}.json", units)

        columns = bundle_columns(result)
        ranges = bundle_ranges(codes, level)
        for bundle, (first, count) in ranges.items():
            data, lost = pack_bundle(columns, np.arange(first, first + count))
            for column, n in lost.items():
                clipped[f"{level}.{column}"] = clipped.get(f"{level}.{column}", 0) + n
            name = f"{level}/{bundle}.bin.gz"
            sizes[name] = gz_write(out / level / f"{bundle}.bin.gz", data)
        levels_meta[level] = dict(
            units=int(codes.size), parent=c.ADMIN_PARENT[level], tiers=c.ADMIN_PARENT[level] is not None,
            bundles={bundle: dict(first=first, count=count, file=f"{level}/{bundle}.bin.gz") for bundle, (first, count) in ranges.items()},
            factors=dict(watch=_nullable(result.watch, 4), alarm=_nullable(result.alarm, 4),
                         relative_watch=_nullable(result.relative_watch, 4), relative_alarm=_nullable(result.relative_alarm, 4)),
            without_outline=0 if outlines is None else int(sum(1 for code in codes if int(code) not in names[level])),
        )
        log.info("%s: %d units in %d bundle(s)", level, codes.size, len(ranges))

    # ---- outlines: provinces and districts whole, sub-districts by province
    if outlines is not None:
        for level in ("province", "district"):
            sizes[f"outlines/{level}.geojson"] = _write_json(out / "outlines" / f"{level}.geojson", outlines[level])
        step = c.ADMIN_DIVISOR["province"]
        by_province: dict[int, list[Any]] = {}
        for feature in outlines["subdistrict"]["features"]:
            by_province.setdefault(int(feature["properties"]["code"]) // step, []).append(feature)
        for province, features in sorted(by_province.items()):
            name = f"outlines/subdistrict/{province}.geojson"
            sizes[name] = _write_json(out / "outlines" / "subdistrict" / f"{province}.geojson",
                                      {"type": "FeatureCollection", "features": features})

    # ---- metadata
    meta = dict(
        title="Nightlights Explorer", subtitle="Indonesia after dark, by province, district and sub-district",
        script="ntl.export",
        months=[m.isoformat()[:7] for m in run.months], windows=windows,
        window="three months centred on the month named" if run.info["seasonal"] else "one calendar month",
        latest=dict(window=latest, month=run.months[latest].isoformat()[:7],
                    rule="the last window in which at least half of the provinces were observed",
                    used_for="the month the page opens on, and the reporting level in units_subdistrict.json"),
        levels=list(c.ADMIN_LEVELS), level_detail=levels_meta,
        status={str(code): name for code, name in c.STATUS_NAMES.items()},
        reporting={str(c.REPORT_NONE): "cannot be monitored", str(c.REPORT_PROVINCE): "province",
                   str(c.REPORT_DISTRICT): "district", str(c.REPORT_SUBDISTRICT): "sub-district"},
        encoding=dict(
            endian="little", layout="columns one after another, each [window, unit] in row order",
            columns=[dict(name=name, dtype=np.dtype(dtype).name, scale=scale, missing=missing)
                     for name, dtype, scale, missing in c.BUNDLE_COLUMNS],
            flags=dict(held=FLAG_HELD, joint=FLAG_JOINT, monitorable=FLAG_MONITORABLE),
            units="index, anomaly, relative and the scales are natural logarithms: exp(anomaly) is observed over expected light",
            cells=dict(index="row * columns + column on the global grid; row 0 at 90 N, column 0 at 180 W",
                       columns=GLOBAL_COLUMNS, cell_degrees=c.CELL_SIZE_DEG, usual_scale=USUAL_SCALE,
                       unit="position + 1 in units_<level>.json; 0 means none"),
        ),
        thresholds=dict(
            note="ntl.conventions at export time; the run file does not record the values it was made with",
            watch_rate=c.WATCH_RATE, alarm_rate=c.ALARM_RATE, hold_months=c.STATUS_HOLD_MONTHS,
            lookback_months=c.STATUS_LOOKBACK_MONTHS, min_coverage=c.STATUS_MIN_COVERAGE, min_nights=c.MIN_NIGHTS,
            min_unit_cells=c.MIN_UNIT_CELLS, max_detectable_drop=c.MAX_DETECTABLE_DROP, detection_power=c.DETECTION_POWER,
            threshold="a unit reads low when anomaly < factor * scale, with the factor of its window",
        ),
        source=dict(
            product=c.MONTHLY_PRODUCT, collection="Black Marble Collection 2", archive_set=c.BLACK_MARBLE_ARCHIVE_SET,
            view=run.info["view"], tiles=str(run.info["tiles"]).split("+"), cells=int(stack.lon.size),
            domain=dict(lit_min=run.info["lit_min"], min_good_months=run.info["min_good_months"], until=run.info["until"],
                        look_ahead=run.info["until"] is None,
                        # cells in the domain as a consistent light source, not by their mean (ntl.sources)
                        source_contrast=run.info.get("source_contrast"), source_share=c.SOURCE_MIN_SHARE, source_radius_km=c.SOURCE_RADIUS_KM,
                        source_cells=int((stack.usual < run.info["lit_min"]).sum()) if run.info.get("source_contrast") is not None else 0),
            retrospective=bool(run.info["retrospective"]),
            # monitor.run_levels does not apply the children-agreement rule, and nothing here does.
            children_rule_applied=False,
            inputs=dict(provenance or {}),
        ),
        outlines=None if outlines is None else dict(use="display only; no statistic reads them"),
        variables=dict(
            trend=dict(
                unit="percent per year", module="ntl.trend", confidence=trend.CONFIDENCE,
                min_months_per_year=trend.MIN_MONTHS_PER_YEAR, min_years=trend.MIN_YEARS,
                years=[run.months[0].year, run.months[latest].year],
                method="Theil-Sen slope of the yearly medians of the log index",
                serial_correlation=trend.SERIAL_CORRELATION, median_by_level=trend_medians, min_cells=c.MIN_UNIT_CELLS,
                core="trend_core is the same slope over only the cells lit from the first year of the record",
                caveats="the cells counted are those lit on average over the whole record, a set that favours places that grew; "
                        "the interval is widened for year-to-year correlation with one pooled value, so it is approximate",
            ),
            then_now=dict(
                module="ntl.firstlight", file="cell_then_now.u8.gz",
                classes=["unknown", "lit then and now", "brightened", "emerged", "faded", "dim then and now"],
                then=[int(cell_years[0]), int(cell_years[firstlight.END_YEARS - 1])],
                now=[int(cell_years[-firstlight.END_YEARS]), int(cell_years[-1])],
                dark_max=firstlight.DARK_MAX, lit_min=c.LIT_MIN_RADIANCE, min_end_years=firstlight.MIN_END_YEARS,
                min_months_per_year=firstlight.MIN_MONTHS_PER_YEAR,
                rule="then and now are the medians of the cell's yearly values in the first and last three years; "
                     "dark is under dark_max, lit is at least lit_min, dim is in between",
                caveat="only cells lit on average over the whole record are looked at, so emergence is undercounted",
            ),
            cell_maps=dict(
                module="ntl.cellmaps", files=cell_files, layout="[month of the year, cell], one byte each, cells in the order of cells.u32.gz",
                radiance=dict(shift=cellmaps.RADIANCE_SHIFT, mask=cellmaps.RADIANCE_MASK, breaks=list(cellmaps.RADIANCE_BREAKS),
                              unit="nW cm-2 sr-1", codes="0 no usable value, 1 no detectable light, 2 under the first break, then one per interval"),
                change=dict(shift=cellmaps.CHANGE_SHIFT, mask=cellmaps.CHANGE_MASK, breaks=list(cellmaps.CHANGE_BREAKS), lag_months=cellmaps.YEAR_LAG,
                            codes="0 no comparison, then one per interval of the ratio now over the same month a year earlier"),
                observations=dict(shift=cellmaps.OBSERVATION_SHIFT, mask=cellmaps.OBSERVATION_MASK, breaks=list(cellmaps.OBSERVATION_BREAKS),
                                  codes="0 none, then one per interval; a usable value needs the second class or higher and good quality"),
                caveat="single cells, not unit statistics; the sensor footprint is wider than a cell, so neighbours are not independent",
            ),
            area=dict(unit="km2", rule="15 arc-second cells on a sphere: (cell x km per degree)^2 x cos(latitude)"),
            persistence=dict(
                module="ntl.persistence", unit="months",
                low=[c.STATUS_NAMES[s] for s in persistence.LOW_STATES],
                ends=[c.STATUS_NAMES[s] for s in persistence.ENDING_STATES], max_silent=persistence.MAX_SILENT,
                min_cells=c.MIN_UNIT_CELLS,
                rule="an episode is a stretch of watch or alarm windows; it ends at the first normal or seen-no-light window, "
                     "or after max_silent windows in a row that say nothing; regional dimming neither ends it nor adds to it",
                caveat="about the unit's figure, not about each place inside the unit",
            ),
        ),
    )
    # ---- faint sources: on the map only (ntl.sources); no figure above uses them
    if faint is not None:
        if faint.source_contrast is None:
            raise ValueError("the faint stack was built without light sources; build it with python -m ntl.stack --sources")
        faint_index = cell_index(faint.lon, faint.lat)
        extra = ~np.isin(faint_index, index)
        keep = np.argsort(faint_index[extra], kind="stable")
        provinces = np.asarray(run.levels["province"].codes, dtype=np.int64)
        codes = faint.province[extra][keep]
        at = np.searchsorted(provinces, codes)
        position = np.where((at < provinces.size) & (provinces[np.minimum(at, provinces.size - 1)] == codes), at + 1, 0)
        faint_usual, _ = encode(faint.usual[extra][keep], "<u2", USUAL_SCALE, None)
        sizes["faint_cells.u32.gz"] = gz_write(out / "faint_cells.u32.gz", faint_index[extra][keep].astype("<u4").tobytes())
        sizes["faint_usual.u16.gz"] = gz_write(out / "faint_usual.u16.gz", faint_usual.tobytes())
        sizes["faint_province.u16.gz"] = gz_write(out / "faint_province.u16.gz", position.astype("<u2").tobytes())
        meta["variables"]["faint"] = dict(
            module="ntl.sources", cells=int(extra.sum()), contrast=faint.source_contrast, share=c.SOURCE_MIN_SHARE, radius_km=c.SOURCE_RADIUS_KM,
            median_usual=round(float(np.median(faint.usual[extra])), 2) if extra.any() else None,
            rule="not lit by the mean rule, but brighter than a distance-weighted mean of the cells within radius_km by more than contrast "
                 "in at least share of its good months",
            caveat="near the product's floor; in no status; not checked to be settlements")
    sizes["meta.json"] = _write_json(out / "meta.json", meta)
    for column, n in clipped.items():
        log.warning("%s: %d value(s) clipped to fit the encoding", column, n)

    # The budget is checked before files.js exists: without it the site cannot be built.
    listing = _files_js(sorted([*sizes, "files.js"]))
    total = sum(sizes.values()) + len(listing.encode("utf-8"))
    if total > budget:
        (out / "files.js").unlink(missing_ok=True)
        raise ValueError(f"the export is {total} bytes, over the budget of {budget}; files.js was not written")
    sizes["files.js"] = _write_text(out / "files.js", listing)

    report = dict(created=dt.datetime.now().isoformat(timespec="seconds"), script="ntl.export",
                  total_bytes=sum(sizes.values()), budget_bytes=budget, files_listed=len(sizes),
                  note="files lists everything written except this report", clipped=clipped, files=sizes)
    _write_text(out / "export_report.json", json.dumps(report, indent=1))
    log.info("%d files, %.2f MiB of a %.0f MiB budget in %s", len(sizes), report["total_bytes"] / 2**20, budget / 2**20, out)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.export",
        description="Pack a monitor run into the files the dashboard loads.",
        epilog="example:\n"
        r"  python -m ntl.export --cache E:\temp\ntl\cache --run E:\temp\ntl\cache\run_monthly.npz "
        r"--outlines E:\temp\ntl\cache\outlines --out site\data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cache", required=True, type=Path, help="folder of stack caches the run was made on")
    parser.add_argument("--run", required=True, type=Path, help="run file written by python -m ntl.monitor")
    parser.add_argument("--outlines", type=Path, help="folder written by python -m ntl.boundaries (optional)")
    parser.add_argument("--faint", type=Path,
                        help="folder of stack caches built with python -m ntl.stack --sources: their extra cells become the map's "
                             "layer of faint sources (optional)")
    parser.add_argument("--out", required=True, type=Path, help=r"output folder, e.g. site\data")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 if an input cannot be used."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.out.is_file():
            raise ValueError(f"{args.out} is a file; --out must name a folder")
        run = monitor.load_levels(args.run)
        stack = load_folder(args.cache, str(run.info["view"]))
        outlines, outline_report = (None, {}) if args.outlines is None else read_outlines(args.outlines)
        run_stat = args.run.stat()
        provenance = dict(
            run_file=args.run.name, run_bytes=run_stat.st_size,
            run_written=dt.datetime.fromtimestamp(run_stat.st_mtime).isoformat(timespec="seconds"),
            stack_cache_version="see each cache; version 1 caches carry no domain record",
            outlines={k: outline_report[k] for k in ("source", "tolerance_deg", "decimals", "method", "features") if k in outline_report},
        )
        faint = None if args.faint is None else load_folder(args.faint, str(run.info["view"]))
        export_site(stack, run, args.out, outlines, provenance=provenance, faint=faint)
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
