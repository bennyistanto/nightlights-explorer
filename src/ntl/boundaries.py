"""Small display outlines for the three admin levels.

The sub-district boundary file is detailed (about 380 MB). The browser needs
outlines a few MB in size. This module simplifies the sub-district polygons
once and builds the district and province outlines by merging them, so that:

- a border shared by two levels lies on the same line at each level;
- every outline carries the same ``siak`` code the statistics use, because
  the codes go through ``ntl.zonal.resolve_levels`` exactly as the cells do.

**Display only.** No statistic is computed from these geometries: cells are
assigned to units from the detailed polygons (``ntl.stack``).

Simplification uses ``shapely.coverage_simplify`` (Visvalingam-Whyatt),
which moves a shared edge once for both neighbours and so leaves no gap or
overlap, provided the input is a valid coverage: polygons that do not
overlap and whose shared edges have identical vertices. The tolerance is
"roughly equal to the square root of the area of triangles that will be
removed" (shapely documentation), not a distance from the original line.
If the input is not a valid coverage the function still returns a result,
which "may result in invalid topology"; the report records whether the
input was valid, and the output is made valid polygon by polygon.

Because outlines are simplified and cells are assigned from the detailed
polygons, a lit cell near a border can be drawn inside the neighbouring
unit's outline. Measured on the national file (2026-11-23): 1.70% of lit
cells at sub-district level, 0.37% at district level, 0.03% at province
level; the furthest about 0.6 km.

The simplification follows the approach of ``drywet-explorer``'s
``pipeline/step0_boundaries.py`` (the same owner's project).

Output: one GeoJSON file per level, each feature with ``code`` and ``name``,
read back by ``ntl.export``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ntl import conventions as c
from ntl import zonal

log = logging.getLogger("ntl.boundaries")

#: Code and name field of each level in the sub-district boundary file.
LEVEL_FIELDS = {"province": ("a1siak", "a1name"), "district": ("a2siak", "a2name"), "subdistrict": ("a3siak", "a3name")}


def simplify_coverage(geometries: Sequence[Any], tolerance: float) -> tuple[np.ndarray, str]:
    """Simplify polygons that tile an area, keeping shared edges shared.

    Parameters
    ----------
    geometries : sequence of shapely geometries
        Polygons or multipolygons, in degrees.
    tolerance : float
        Simplification tolerance, degrees.

    Returns
    -------
    ndarray of shapely geometries
        One per input, made valid. A small polygon can come back empty.
    str
        ``"coverage"`` if the input was a valid coverage;
        ``"coverage_invalid_input"`` if the polygons overlap or their
        edges do not match (neighbours may then show slivers or overlaps).

    Raises
    ------
    ValueError
        If the tolerance is not a positive number, or a geometry is missing.
    TypeError
        If a geometry is not a polygon or multipolygon (from shapely).
    """
    import shapely

    if not (np.isfinite(tolerance) and tolerance > 0):
        raise ValueError(f"tolerance must be a positive number of degrees, got {tolerance}")
    array = np.asarray(geometries, dtype=object)
    if any(g is None for g in array):
        raise ValueError("a feature has no geometry")
    how = "coverage" if shapely.coverage_is_valid(array) else "coverage_invalid_input"
    if how != "coverage":
        log.warning("the polygons are not a valid coverage (overlaps or unmatched edges); simplified anyway")
    return shapely.make_valid(shapely.coverage_simplify(array, tolerance)), how


def most_common_name(names: Iterable[Any]) -> str | None:
    """The name most features of a unit carry; None if none carries one."""
    counts = Counter(str(n).strip() for n in names if isinstance(n, str) and n.strip())
    return counts.most_common(1)[0][0] if counts else None


def merge_level(
    geometries: Sequence[Any],
    codes: Sequence[int],
    names: Sequence[Any],
) -> list[tuple[int, str | None, Any]]:
    """Merge features into one outline per unit code.

    Parameters
    ----------
    geometries : sequence of shapely geometries
        One per feature (already simplified).
    codes : sequence of int
        Unit code of each feature at the level wanted; 0 means the feature
        belongs to no unit of this level and is left out.
    names : sequence
        Name of each feature at this level; missing values allowed.

    Returns
    -------
    list of (code, name, geometry)
        Ascending by code. Units whose merged geometry is empty are left out.
    """
    import shapely

    codes = zonal.integer_codes(codes, "outline codes")
    geometries = np.asarray(geometries, dtype=object)
    names = np.asarray(names, dtype=object)
    if not (codes.shape == geometries.shape == names.shape):
        raise ValueError("geometries, codes and names must have the same length")
    out = []
    for code in np.unique(codes[codes != c.NO_UNIT]):
        members = codes == code
        merged = shapely.union_all(geometries[members])
        if merged.is_empty:
            log.warning("unit %d: nothing left after simplification, no outline", code)
            continue
        out.append((int(code), most_common_name(names[members]), merged))
    return out


def feature_collection(units: Sequence[tuple[int, str | None, Any]], decimals: int = c.OUTLINE_DECIMALS) -> dict[str, Any]:
    """GeoJSON for merged units, coordinates rounded.

    Rounding can close a ring onto itself; geometries are made valid again
    after rounding and the polygonal part kept.
    """
    import shapely

    features = []
    for code, name, geometry in units:
        rounded = shapely.make_valid(shapely.set_precision(geometry, 10.0 ** -decimals))
        if rounded.geom_type == "GeometryCollection":
            parts = [g for g in rounded.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            rounded = shapely.union_all(parts) if parts else shapely.Polygon()
        if rounded.is_empty or rounded.geom_type not in ("Polygon", "MultiPolygon"):
            log.warning("unit %d: nothing left after rounding, no outline", code)
            continue
        features.append({"type": "Feature", "properties": {"code": code, "name": name},
                         "geometry": json.loads(shapely.to_geojson(rounded))})
    return {"type": "FeatureCollection", "features": features}


def build_outlines(path: str | Path, tolerance: float = c.OUTLINE_TOLERANCE_DEG) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Outlines of every unit at the three levels, from the sub-district file.

    Parameters
    ----------
    path : str or Path
        Polygon file with the fields of :data:`LEVEL_FIELDS`, geographic
        coordinates. Read whole: several GB of memory for the national file.
    tolerance : float
        Simplification tolerance, degrees.

    Returns
    -------
    dict of str to dict
        A GeoJSON feature collection per level.
    dict
        What was done: source, features, vertices before and after, method.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file cannot be read as polygons, a field is absent, a code
        is missing, the coordinates are not geographic, or the codes do
        not nest (``zonal.resolve_levels``).
    """
    import geopandas as gpd
    import shapely

    if not Path(path).is_file():
        raise FileNotFoundError(f"{path}: no such boundary file")
    try:
        frame = gpd.read_file(path)
    except Exception as exc:  # the reader raises its own error types for a file that is not vector data
        raise ValueError(f"{path}: cannot be read as a polygon file ({exc})") from exc
    if frame.crs is None:
        log.warning("%s has no coordinate system; taken to be geographic", path)
    if frame.crs is not None and not frame.crs.is_geographic:
        raise ValueError(f"{path}: coordinates are not geographic ({frame.crs})")
    for code_field, name_field in LEVEL_FIELDS.values():
        for field in (code_field, name_field):
            if field not in frame.columns:
                raise ValueError(f"{path}: no field {field}")
        if frame[code_field].isna().any():
            raise ValueError(f"{path}: field {code_field} has missing values")
    codes = zonal.resolve_levels(*(frame[LEVEL_FIELDS[level][0]].to_numpy() for level in c.ADMIN_LEVELS))
    before = int(shapely.get_num_coordinates(frame.geometry.values).sum())
    simple, how = simplify_coverage(frame.geometry.values, tolerance)
    emptied = int(shapely.is_empty(simple).sum())
    log.info("%d features, %d vertices to %d (%s), %d emptied", len(frame), before,
             int(shapely.get_num_coordinates(simple).sum()), how, emptied)
    collections, levels = {}, {}
    for level in c.ADMIN_LEVELS:
        units = merge_level(simple, codes[level], frame[LEVEL_FIELDS[level][1]].to_numpy())
        collections[level] = feature_collection(units)
        levels[level] = dict(units=len(units), outlines=len(collections[level]["features"]),
                             unnamed=sum(1 for _, name, _ in units if name is None))
        log.info("%s: %d outlines, %d without a name", level, levels[level]["outlines"], levels[level]["unnamed"])
    source = Path(path)
    report = dict(
        created=dt.datetime.now().isoformat(timespec="seconds"), script="ntl.boundaries",
        source=dict(file=source.name, bytes=source.stat().st_size,
                    modified=dt.datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds")),
        use="display only; no statistic reads these outlines",
        tolerance_deg=tolerance, decimals=c.OUTLINE_DECIMALS, method=how, features=len(frame),
        features_emptied=emptied, vertices_in=before, levels=levels,
    )
    return collections, report


def write_outlines(collections: dict[str, dict[str, Any]], report: dict[str, Any], folder: str | Path) -> dict[str, Path]:
    """Write ``<level>.geojson`` per level and ``outlines_report.json`` to a folder."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for level, collection in collections.items():
        paths[level] = folder / f"{level}.geojson"
        paths[level].write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        report["levels"][level]["bytes"] = paths[level].stat().st_size
    (folder / "outlines_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.boundaries",
        description="Simplified display outlines of provinces, districts and sub-districts from the sub-district boundary file.",
        epilog=r"example:" "\n" r"  python -m ntl.boundaries --boundaries E:\temp\idn-bnd\idn_bnd_adm3.shp --out E:\temp\ntl\cache\outlines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--boundaries", required=True, type=Path, help="sub-district polygon file with a1siak..a3siak and a1name..a3name")
    parser.add_argument("--out", required=True, type=Path, help="folder for <level>.geojson and outlines_report.json")
    parser.add_argument("--tolerance", type=float, default=c.OUTLINE_TOLERANCE_DEG,
                        help=f"simplification tolerance in degrees (default {c.OUTLINE_TOLERANCE_DEG})")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 if the file cannot be used."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        collections, report = build_outlines(args.boundaries, args.tolerance)
        written = write_outlines(collections, report, args.out)
    except ImportError as exc:
        log.error("%s: outlines need geopandas and shapely 2.1 or later (the \"outlines\" extra)", exc)
        return 1
    except (OSError, ValueError, TypeError) as exc:
        log.error("%s", exc)
        return 1
    for level, path in written.items():
        log.info("%s: %s, %.2f MB", level, path, path.stat().st_size / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
