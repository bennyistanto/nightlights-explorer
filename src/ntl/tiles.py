"""The Black Marble 10-degree tile grid: which tile holds a point or a box.

The grid is a plain geographic one. Tile ``h00v00`` has its upper-left
corner at 180 W, 90 N; ``h`` counts east, ``v`` counts south (Black Marble
User Guide, Collection 2.0, tile grid section). All functions are pure.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple

from ntl.conventions import N_TILES_H, N_TILES_V, TILE_SIZE_DEG

_TILE_ID = re.compile(r"^h(\d{2})v(\d{2})$")


class Tile(NamedTuple):
    """A tile index pair.

    Attributes
    ----------
    h : int
        Column, 0 at 180 W, increasing east. 0 to 35.
    v : int
        Row, 0 at 90 N, increasing south. 0 to 17.
    """

    h: int
    v: int

    @property
    def id(self) -> str:
        """Tile name as it appears in file names, for example ``"h29v09"``."""
        return f"h{self.h:02d}v{self.v:02d}"


def parse_tile(text: str) -> Tile:
    """Turn ``"h29v09"`` into ``Tile(29, 9)``.

    Raises
    ------
    ValueError
        If the text is not of the form ``hHHvVV`` or lies off the grid.
    """
    match = _TILE_ID.match(text.strip().lower())
    if match is None:
        raise ValueError(f"not a tile id (expected hHHvVV): {text!r}")
    tile = Tile(int(match.group(1)), int(match.group(2)))
    if not (0 <= tile.h < N_TILES_H and 0 <= tile.v < N_TILES_V):
        raise ValueError(f"tile off the grid: {text!r}")
    return tile


def tile_of(lon: float, lat: float) -> Tile:
    """Tile containing a point.

    Parameters
    ----------
    lon, lat : float
        Degrees east and north, WGS84. ``-180 <= lon <= 180``,
        ``-90 <= lat <= 90``.

    Returns
    -------
    Tile

    Notes
    -----
    A point exactly on a shared edge belongs to the tile to its east and
    south, except on the grid's own east and south limits (lon 180, lat
    -90), which belong to the last column and row.
    """
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise ValueError(f"point off the globe: lon={lon}, lat={lat}")
    h = min(int(math.floor((lon + 180.0) / TILE_SIZE_DEG)), N_TILES_H - 1)
    v = min(int(math.floor((90.0 - lat) / TILE_SIZE_DEG)), N_TILES_V - 1)
    return Tile(h, v)


def tile_bounds(tile: Tile) -> tuple[float, float, float, float]:
    """Outer edges of a tile as (west, south, east, north) in degrees."""
    west = -180.0 + tile.h * TILE_SIZE_DEG
    north = 90.0 - tile.v * TILE_SIZE_DEG
    return (west, north - TILE_SIZE_DEG, west + TILE_SIZE_DEG, north)


def tiles_for_bbox(west: float, south: float, east: float, north: float) -> list[Tile]:
    """Every tile a bounding box overlaps with non-zero area.

    Parameters
    ----------
    west, south, east, north : float
        Degrees. Requires ``west < east`` and ``south < north``. A box that
        crosses the antimeridian must be passed as two boxes.

    Returns
    -------
    list of Tile
        Sorted by ``v`` then ``h`` (north to south, west to east).

    Notes
    -----
    A box whose east or south edge lies exactly on a tile edge does not pull
    in the neighbouring tile: that overlap has zero area.
    """
    if not (west < east and south < north):
        raise ValueError("need west < east and south < north; split boxes that cross the antimeridian")
    if west < -180.0 or east > 180.0 or south < -90.0 or north > 90.0:
        raise ValueError("bounding box off the globe")
    h_min = int(math.floor((west + 180.0) / TILE_SIZE_DEG))
    h_max = int(math.ceil((east + 180.0) / TILE_SIZE_DEG)) - 1
    v_min = int(math.floor((90.0 - north) / TILE_SIZE_DEG))
    v_max = int(math.ceil((90.0 - south) / TILE_SIZE_DEG)) - 1
    return [Tile(h, v) for v in range(v_min, v_max + 1) for h in range(h_min, h_max + 1)]
