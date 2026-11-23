"""Which dark places lit up: every cell of a box, night by night, around a dated event.

``ntl.events`` follows the lit cells of the status domain. This module asks
the opposite question, for one case study so far (the return from Eid
al-Fitr 2019 across Java): take every land cell, lit or not, and compare
its light in a few groups of nights with its light on reference nights.
A road that carries traffic is dark on an ordinary night and is not in the
lit domain, so it can only be seen this way.

Product: NASA Black Marble daily, VNP46A2, Collection 2, layer
``DNB_BRDF-Corrected_NTL`` (nW cm-2 sr-1), high-quality retrievals only,
read through ``ntl.events.read_window``; the land and water classes come
from the monthly VNP46A3 files.

Method ([P]: picked for this project, not from a document):

1. **Window means**: a cell's mean over the nights of a window on which it
   was seen, if there are at least ``MIN_WINDOW_NIGHTS`` of them.
2. **Change**: the window mean minus the mean over the reference nights,
   classed for the map (``CHANGE_BREAKS``). Sea cells are left out.
3. **The line**: cells that are dim on the reference nights (under
   ``DIM_MAX``) and brighter by ``RISE`` or more in ONE window. Choosing
   cells by their rise guarantees a rise in that window, so those nights
   are in sample; every other night is not.
4. **Night by night**: the mean excess of the line's cells over their
   reference, minus the same for dim cells that did not change in the
   picking window (the background), which removes what the whole sky did.
5. **Same view**: the satellite sees a place from the same angle every 16
   nights (``events.VIEW_REPEAT_NIGHTS``), and the line's excess over the
   reference follows the view angle (second method critique, 2026-11-23:
   r = +0.89 over eleven nights of late June 2019). So the comparison that
   can carry a claim is a night against the night 16 before or after it,
   over the cells seen on both, net of the background.

What this cannot say: what the light is. Vehicles, lamps at rest areas and
toll gates, and the edges of towns all qualify, and dim cells that flicker
lie along main roads on ordinary nights too (the same critique: 28 to 50%
of cells picked on five ordinary windows lie within 1 km of a main road).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import sys
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import composite, events, export, stack
from ntl import conventions as c
from ntl.read import read_grid, read_raw

log = logging.getLogger("ntl.lightup")

#: Nights a cell needs in a window for a mean. [P]
MIN_WINDOW_NIGHTS: Final[int] = 2
#: Edges of the change classes drawn on the map, nW cm-2 sr-1. [P]
CHANGE_BREAKS: Final[tuple[float, ...]] = (-1.5, -0.5, 0.5, 1.5, 3.0)
#: Class of a cell without a mean in the window; the classes of CHANGE_BREAKS follow from 1.
CHANGE_UNSEEN: Final[int] = 0
#: A cell changed if any window differs from the reference by this, nW cm-2 sr-1. [P]
CHANGE_MIN: Final[float] = 0.5
#: The line: a reference mean under DIM_MAX and a rise of RISE or more, nW cm-2 sr-1. [P]
DIM_MAX: Final[float] = 3.0
RISE: Final[float] = 1.5
#: The background: dim cells within this of their reference in the picking window. [P]
STEADY_WITHIN: Final[float] = 0.3
#: Share of the line's cells, and number of background cells, a night needs for a figure. [P]
MIN_LINE_SHARE: Final[float] = 0.3
MIN_BACKGROUND_CELLS: Final[int] = 1000
#: Cells seen on both nights that a same-view comparison needs. [P]
MIN_PAIR_CELLS: Final[int] = 200
#: OpenStreetMap road classes fetched for the overlay: in Indonesia motorways are the toll roads.
ROAD_CLASSES: Final[dict[str, str]] = {"motorway": "toll roads (highway=motorway)", "trunk": "national main roads (highway=trunk)"}
OVERPASS_URL: Final[str] = "https://overpass-api.de/api/interpreter"
#: Road lines are simplified by this, degrees (about 110 m), and rounded to 4 decimals.
ROAD_TOLERANCE_DEG: Final[float] = 0.001


@dataclass(frozen=True)
class LightUp:
    """One study: the event whose nights are read, the box, the windows.

    Attributes
    ----------
    event : str
        Key of the event in ``events.EVENTS``: gives the first and last
        night and the quality flags; the files go to its folder.
    boxes : tuple of (tile, (west, south, east, north))
        The parts of the box by tile, west to east; neighbouring tiles of
        one row, so that they join side by side.
    reference : (date, date)
        First and last reference night.
    windows : tuple of (key, label, first, last)
        Groups of nights drawn on the map.
    pick : str
        Key of the window the line is picked in.
    pick_lon : (float, float)
        The line is picked between these longitudes, degrees. [P]
    pairs : tuple of (date, date)
        Nights compared at the same view: each first night against the
        second, 16 nights away.
    held_out : (tuple of date, date)
        Cells picked on the first nights alone, read on the second night.
    placebo : tuple of (date, date)
        Windows with no holiday, picked the same way: how many cells qualify.
    """

    event: str
    boxes: tuple[tuple[str, tuple[float, float, float, float]], ...]
    reference: tuple[dt.date, dt.date]
    windows: tuple[tuple[str, str, dt.date, dt.date], ...]
    pick: str
    pick_lon: tuple[float, float]
    pairs: tuple[tuple[dt.date, dt.date], ...] = ()
    held_out: tuple[tuple[dt.date, ...], dt.date] | None = None
    placebo: tuple[tuple[dt.date, dt.date], ...] = ()


#: Java, from the west tip of Banten to Banyuwangi, around Eid al-Fitr 2019 (5 and 6 June; 7 June was
#: collective leave: joint ministerial decree on holidays for 2019, setkab.go.id). The line is picked
#: between 107.3 and 110.6 E, the stretch from the edge of Jakarta to Semarang where the rise on the return
#: is a line and not a patch: a limit chosen after looking at the map. [P]
STUDIES: Final[dict[str, LightUp]] = {
    "mudik2019": LightUp(
        event="mudik2019",
        boxes=(("h28v09", (105.0, -8.9, 110.0, -5.8)), ("h29v09", (110.0, -8.9, 114.7, -5.8))),
        reference=(dt.date(2019, 5, 15), dt.date(2019, 5, 27)),
        windows=(("before_0528_0531", "Leaving", dt.date(2019, 5, 28), dt.date(2019, 5, 31)),
                 ("eid_0605_0607", "Eid and the day after", dt.date(2019, 6, 5), dt.date(2019, 6, 7)),
                 ("return_0608_0611", "Returning", dt.date(2019, 6, 8), dt.date(2019, 6, 11)),
                 ("after_0615_0625", "Later in June", dt.date(2019, 6, 15), dt.date(2019, 6, 25))),
        pick="return_0608_0611", pick_lon=(107.3, 110.6),
        pairs=((dt.date(2019, 6, 9), dt.date(2019, 5, 24)), (dt.date(2019, 6, 9), dt.date(2019, 6, 25)), (dt.date(2019, 6, 10), dt.date(2019, 5, 25)),
               (dt.date(2019, 5, 29), dt.date(2019, 6, 14)), (dt.date(2019, 5, 30), dt.date(2019, 6, 15)), (dt.date(2019, 5, 31), dt.date(2019, 6, 16))),
        held_out=((dt.date(2019, 6, 10), dt.date(2019, 6, 11)), dt.date(2019, 6, 9)),
        placebo=((dt.date(2019, 6, 15), dt.date(2019, 6, 18)), (dt.date(2019, 6, 20), dt.date(2019, 6, 23)), (dt.date(2019, 6, 22), dt.date(2019, 6, 25))),
    ),
}


def window_mean(cube: ArrayLike, first: int, last: int, min_nights: int = MIN_WINDOW_NIGHTS) -> NDArray[np.float64]:
    """Each cell's mean radiance over the nights of a window on which it was seen.

    Parameters
    ----------
    cube : array_like of float, shape ``(D, ...)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    first, last : int
        First and last night of the window, inclusive.
    min_nights : int
        Nights a cell must be seen.

    Returns
    -------
    ndarray of float64, shape ``cube.shape[1:]``
        NaN where the cell was seen on fewer nights.

    Raises
    ------
    ValueError
        If the window is empty or outside the cube.
    """
    cube = np.asarray(cube)
    if not 0 <= first <= last < cube.shape[0]:
        raise ValueError(f"window {first} to {last} is not inside the {cube.shape[0]} nights")
    part = cube[first:last + 1].astype(np.float64)
    seen = np.isfinite(part)
    count = seen.sum(axis=0)
    return np.where(count >= min_nights, np.where(seen, part, 0.0).sum(axis=0) / np.maximum(count, 1), np.nan)


def change_class(difference: ArrayLike, breaks: Sequence[float] = CHANGE_BREAKS) -> NDArray[np.uint8]:
    """Class of a change for the map: 0 where there is none to give, then 1 upward by the breaks."""
    difference = np.asarray(difference, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        return np.where(np.isfinite(difference), np.digitize(difference, breaks) + 1, CHANGE_UNSEEN).astype(np.uint8)


def pick_line(reference: ArrayLike, window: ArrayLike, allowed: ArrayLike | None = None, dim_max: float = DIM_MAX, rise: float = RISE,
              steady_within: float = STEADY_WITHIN) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """The cells that lit up in a window, and the dim cells that did not move.

    Parameters
    ----------
    reference, window : array_like of float
        Mean radiance on the reference nights and in the picking window,
        nW cm-2 sr-1; NaN where there is none.
    allowed : array_like of bool, optional
        Where a cell may be picked at all (land, a range of longitudes).
    dim_max, rise, steady_within : float
        A cell is dim under ``dim_max``; it lit up if the window exceeds
        the reference by ``rise`` or more, and is background if the two
        differ by ``steady_within`` or less.

    Returns
    -------
    tuple of two ndarrays of bool
        The line, and the background. A cell without both means is in neither.
    """
    reference = np.asarray(reference, dtype=np.float64)
    difference = np.asarray(window, dtype=np.float64) - reference
    with np.errstate(invalid="ignore"):
        dim = np.isfinite(difference) & (reference < dim_max)
        if allowed is not None:
            dim &= np.asarray(allowed, dtype=bool)
        return dim & (difference >= rise), dim & (np.abs(difference) <= steady_within)


def nightly_excess(cube: ArrayLike, reference: ArrayLike, cells: ArrayLike, min_cells: int = 1) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Mean excess of a group of cells over their reference, night by night.

    Parameters
    ----------
    cube : array_like of float, shape ``(D, ...)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    reference : array_like of float, shape ``cube.shape[1:]``
    cells : array_like of bool, shape ``cube.shape[1:]``
    min_cells : int
        Cells that must be seen for a night to get a figure.

    Returns
    -------
    ndarray of float64, shape ``(D,)``
        Mean of radiance minus reference over the cells seen; NaN with too few.
    ndarray of int64, shape ``(D,)``
        Cells seen each night.
    """
    cells = np.asarray(cells, dtype=bool)
    block = np.asarray(cube)[:, cells].astype(np.float64) - np.asarray(reference, dtype=np.float64)[cells][None, :]
    seen = np.isfinite(block)
    count = seen.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count >= max(min_cells, 1), np.where(seen, block, 0.0).sum(axis=1) / np.maximum(count, 1), np.nan), count.astype(np.int64)


def same_view_net(cube: ArrayLike, line: ArrayLike, background: ArrayLike, night: int, partner: int, min_cells: int = MIN_PAIR_CELLS) -> dict[str, Any]:
    """A night against another seen from the same angle: the line's change, net of the background's.

    Parameters
    ----------
    cube : array_like of float, shape ``(D, ...)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    line, background : array_like of bool, shape ``cube.shape[1:]``
    night, partner : int
        The two nights; the result is ``night`` minus ``partner``.
    min_cells : int
        Cells of each group that must be seen on both nights.

    Returns
    -------
    dict
        ``cells`` and ``background_cells`` seen on both nights; ``line``
        and ``background``, each group's mean difference in nW cm-2 sr-1;
        ``net``, the first minus the second. The three figures are None
        when either group has too few cells.
    """
    cube = np.asarray(cube)
    difference = cube[night].astype(np.float64) - cube[partner].astype(np.float64)
    both = np.isfinite(difference)
    on_line, on_background = both & np.asarray(line, dtype=bool), both & np.asarray(background, dtype=bool)
    result: dict[str, Any] = dict(cells=int(on_line.sum()), background_cells=int(on_background.sum()), line=None, background=None, net=None)
    if result["cells"] >= min_cells and result["background_cells"] >= min_cells:
        a, b = float(difference[on_line].mean()), float(difference[on_background].mean())
        result.update(line=round(a, 3), background=round(b, 3), net=round(a - b, 3))
    return result


def read_box(root: str | Path, study: LightUp) -> tuple[NDArray[np.float32], NDArray[np.float64], NDArray[np.float64]]:
    """Usable radiance of every cell of the study's box, night by night, joined across its tiles.

    Returns
    -------
    tuple
        As ``events.read_window``: the cube ``(D, rows, columns)``, and the
        longitude and latitude of each cell centre.

    Raises
    ------
    ValueError
        If the parts do not share their rows or are not in order west to east.
    FileNotFoundError
        If a tile has no daily file in the event's window.
    """
    base = events.EVENTS[study.event]
    parts = [events.read_window(root, dataclasses.replace(base, tile=tile, bbox=box)) for tile, box in study.boxes]
    for (_, _, lat_a), (_, _, lat_b) in zip(parts[:-1], parts[1:]):
        if lat_a.shape[0] != lat_b.shape[0] or not np.allclose(lat_a[:, 0], lat_b[:, 0]):
            raise ValueError(f"{study.event}: the tiles of the box do not share their rows")
    for (_, lon_a, _), (_, lon_b, _) in zip(parts[:-1], parts[1:]):
        if not lon_a[0, -1] < lon_b[0, 0]:
            raise ValueError(f"{study.event}: the parts of the box are not in order west to east")
    return (np.concatenate([p[0] for p in parts], axis=2), np.concatenate([p[1] for p in parts], axis=1), np.concatenate([p[2] for p in parts], axis=1))


def land_mask(root: str | Path, study: LightUp) -> NDArray[np.bool_]:
    """True for the land cells of the box, coast included.

    The commonest land and water class of each cell over the monthly files
    of the event's year (``composite.modal_class``), as ``ntl.stack`` does
    over the whole record. Same shape and order as :func:`read_box`.

    Raises
    ------
    FileNotFoundError
        If a tile has no monthly file in that year.
    """
    year = events.EVENTS[study.event].first.year
    parts = []
    for tile, box in study.boxes:
        files = [p for m, p in sorted(stack.monthly_files(root, tile).items()) if m.year == year]
        if not files:
            raise FileNotFoundError(f"no monthly file of {tile} in {year} under {root}: the land mask needs them")
        window = read_grid(files[0]).window(*box)
        votes = None
        for path in files:
            classes = read_raw(path, c.COMPOSITE_LAND_WATER, window)
            if votes is None:
                votes = composite.new_class_votes(classes.shape)
            composite.add_class_votes(votes, classes)
        parts.append(composite.is_fixed_land(composite.modal_class(votes), include_coastal=True))
    return np.concatenate(parts, axis=1)


def road_lines(answer: dict[str, Any], tolerance: float = ROAD_TOLERANCE_DEG) -> dict[str, list[list[list[float]]]]:
    """Road lines by class from an Overpass answer, simplified and rounded for the map.

    Parameters
    ----------
    answer : dict
        The JSON of an Overpass query written with ``out geom``.
    tolerance : float
        Simplification, degrees.

    Returns
    -------
    dict
        Per class of ``ROAD_CLASSES``, a list of lines, each a list of
        ``[lon, lat]`` rounded to 4 decimals.
    """
    from shapely.geometry import LineString  # an optional dependency, as for ntl.boundaries

    lines: dict[str, list[list[list[float]]]] = {kind: [] for kind in ROAD_CLASSES}
    for way in answer.get("elements", []):
        kind = way.get("tags", {}).get("highway")
        geometry = way.get("geometry", [])
        if way.get("type") != "way" or kind not in lines or len(geometry) < 2:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in geometry]).simplify(tolerance)
        lines[kind].append([[round(x, 4), round(y, 4)] for x, y in line.coords])
    return lines


def fetch_roads(study: LightUp, raw: str | Path) -> dict[str, Any]:
    """The toll roads and national main roads of the box from OpenStreetMap, kept beside the other source data.

    The answer of the public Overpass API is written to ``raw`` once and
    read from there afterwards. The data are under the Open Database
    Licence (credit "OpenStreetMap contributors"), and are the roads as
    mapped on the day of the fetch, NOT as they stood at the event.

    Raises
    ------
    OSError
        If the file is absent and the service cannot be reached.
    """
    raw = Path(raw)
    if not raw.is_file():
        west = min(box[0] for _, box in study.boxes)
        south = min(box[1] for _, box in study.boxes)
        east = max(box[2] for _, box in study.boxes)
        north = max(box[3] for _, box in study.boxes)
        query = f'[out:json][timeout:180];way["highway"~"^({"|".join(ROAD_CLASSES)})$"]({south},{west},{north},{east});out tags geom;'
        request = urllib.request.Request(OVERPASS_URL, data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": "night-lights-research-script/0.1"})
        raw.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(request, timeout=300) as response:
            raw.write_bytes(response.read())
        log.info("roads: fetched %.1f MB from OpenStreetMap to %s", raw.stat().st_size / 1e6, raw)
    answer = json.loads(raw.read_text(encoding="utf-8"))
    return dict(source="OpenStreetMap contributors, through the Overpass API; Open Database Licence",
                fetched=str(answer.get("osm3s", {}).get("timestamp_osm_base", "")), classes=dict(ROAD_CLASSES),
                note="roads as mapped on the day of the fetch, not as they stood at the event", **road_lines(answer))


def export_lightup(study: LightUp, root: str | Path, out: str | Path, roads: str | Path | None = None) -> dict[str, Any]:
    """Write the study's files into the event's folder of the site data.

    ``road_lon.f32.gz`` and ``road_lat.f32.gz``: centres of the land cells
    that changed by ``CHANGE_MIN`` in some window. ``road_class.u8.gz``:
    one byte per window and cell, :func:`change_class`. ``road.json``: the
    windows, the line, the nightly excess, the same-view comparisons, the
    held-out check and the placebo counts. ``roads.json`` (with ``roads``):
    the OpenStreetMap lines for the overlay.

    Parameters
    ----------
    study : LightUp
    root : str or Path
        Data root holding the daily and monthly files.
    out : str or Path
        The site's data folder.
    roads : str or Path, optional
        Where the raw OpenStreetMap answer is kept (fetched if absent).

    Returns
    -------
    dict
        What was written to ``road.json``.
    """
    base = events.EVENTS[study.event]
    folder = Path(out) / "events" / study.event
    cube, lon, lat = read_box(root, study)
    land = land_mask(root, study)
    index = lambda day: (day - base.first).days
    reference = window_mean(cube, index(study.reference[0]), index(study.reference[1]))
    means = {key: window_mean(cube, index(first), index(last)) for key, _, first, last in study.windows}
    differences = np.stack([means[key] - reference for key, _, _, _ in study.windows])
    with np.errstate(invalid="ignore"):
        changed = np.isfinite(reference) & land & (np.nanmax(np.abs(np.where(np.isfinite(differences), differences, 0.0)), axis=0) >= CHANGE_MIN)
    sizes = {
        "road_lon.f32.gz": export.gz_write(folder / "road_lon.f32.gz", lon[changed].astype("<f4").tobytes()),
        "road_lat.f32.gz": export.gz_write(folder / "road_lat.f32.gz", lat[changed].astype("<f4").tobytes()),
        "road_class.u8.gz": export.gz_write(folder / "road_class.u8.gz", np.ascontiguousarray(change_class(differences[:, changed])).tobytes()),
    }
    allowed = land & (lon >= study.pick_lon[0]) & (lon <= study.pick_lon[1])
    line, background = pick_line(reference, means[study.pick], allowed)
    pick_first, pick_last = next((first, last) for key, _, first, last in study.windows if key == study.pick)
    line_excess, line_seen = nightly_excess(cube, reference, line, min_cells=int(np.ceil(MIN_LINE_SHARE * max(int(line.sum()), 1))))
    back_excess, _ = nightly_excess(cube, reference, background, min_cells=MIN_BACKGROUND_CELLS)
    value = lambda v: None if not np.isfinite(v) else round(float(v), 3)
    nights = [dict(date=(base.first + dt.timedelta(days=k)).isoformat(), seen=round(float(line_seen[k] / max(int(line.sum()), 1)), 3),
                   excess=value(line_excess[k]) if np.isfinite(back_excess[k]) else None, background_excess=value(back_excess[k]) if np.isfinite(line_excess[k]) else None,
                   picked=pick_first <= base.first + dt.timedelta(days=k) <= pick_last) for k in range(cube.shape[0])]
    road: dict[str, Any] = dict(
        script="ntl.lightup", event=study.event, breaks=list(CHANGE_BREAKS), cells=int(changed.sum()), box_cells=int(reference.size), land_cells=int(land.sum()),
        reference=[d.isoformat() for d in study.reference],
        windows=[dict(key=key, label=label, first=first.isoformat(), last=last.isoformat(), seen=round(float(np.isfinite(means[key][land]).mean()), 3))
                 for key, label, first, last in study.windows],
        line=dict(cells=int(line.sum()), background_cells=int(background.sum()), picked_in=study.pick, longitudes=list(study.pick_lon),
                  rule=f"land cells under {DIM_MAX} nW on the reference nights and {RISE} nW or more brighter in the picking window",
                  reference_mean=value(np.nanmean(reference[line])) if line.any() else None),
        nights=nights,
        same_view=[dict(night=a.isoformat(), partner=b.isoformat(), **same_view_net(cube, line, background, index(a), index(b))) for a, b in study.pairs],
        placebo=[],
    )
    for first, last in study.placebo:
        other, _ = pick_line(reference, window_mean(cube, index(first), index(last)), allowed)
        road["placebo"].append(dict(first=first.isoformat(), last=last.isoformat(), cells=int(other.sum())))
    if study.held_out is not None:
        picked_on, night = study.held_out
        held, steady = pick_line(reference, window_mean(cube, index(min(picked_on)), index(max(picked_on))), allowed)
        excess, seen = nightly_excess(cube, reference, held)
        back, _ = nightly_excess(cube, reference, steady, min_cells=MIN_BACKGROUND_CELLS)
        k = index(night)
        road["held_out"] = dict(picked_on=[d.isoformat() for d in picked_on], night=night.isoformat(), cells=int(held.sum()), seen=int(seen[k]),
                                net=value(excess[k] - back[k]))
    sizes["road.json"] = export._write_json(folder / "road.json", road)
    if roads is not None:
        sizes["roads.json"] = export._write_json(folder / "roads.json", fetch_roads(study, roads))
    log.info("%s: %d cells changed of %d land cells; the line has %d cells; %.2f MB in %s", study.event, int(changed.sum()), int(land.sum()),
             int(line.sum()), sum(sizes.values()) / 1e6, folder)
    return road


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.lightup",
        description="Every land cell of a box, lit or not, in groups of nights around an event: which dark places lit up.",
        epilog="example:\n" r"  python -m ntl.lightup --study mudik2019 --root E:\temp\ntl --out site\data --roads E:\temp\ntl\osm\java_roads_overpass.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--study", required=True, choices=sorted(STUDIES), help="which study")
    parser.add_argument("--root", required=True, type=Path, help="data root holding the daily VNP46A2 files of every tile of the box, and its monthly files")
    parser.add_argument("--out", required=True, type=Path, help=r"the site's data folder, e.g. site\data")
    parser.add_argument("--roads", type=Path, help="file for the raw OpenStreetMap roads of the box: read if it exists, fetched from the Overpass API if not (optional)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 if an input cannot be used."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        export_lightup(STUDIES[args.study], args.root, args.out, roads=args.roads)
    except (OSError, ValueError, KeyError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
