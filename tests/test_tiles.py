"""Tile grid arithmetic, checked against values worked by hand."""

import pytest

from ntl.conventions import INDONESIA_BBOX
from ntl.tiles import Tile, parse_tile, tile_bounds, tile_of, tiles_for_bbox


def test_tile_of_known_places():
    # Mataram, Lombok: about 116.1 E, 8.6 S.
    # h = floor((116.1 + 180) / 10) = 29, v = floor((90 + 8.6) / 10) = 9.
    assert tile_of(116.1, -8.6) == Tile(29, 9)
    # Banda Aceh, about 95.3 E, 5.5 N: h = 27, v = floor(84.5 / 10) = 8.
    assert tile_of(95.3, 5.5) == Tile(27, 8)


def test_tile_of_grid_corners():
    assert tile_of(-180.0, 90.0) == Tile(0, 0)
    # The east and south limits belong to the last column and row.
    assert tile_of(180.0, -90.0) == Tile(35, 17)


def test_shared_edge_goes_east_and_south():
    assert tile_of(120.0, 0.0) == Tile(30, 9)


def test_tile_bounds_round_trip():
    assert tile_bounds(Tile(29, 9)) == (110.0, -10.0, 120.0, 0.0)


def test_indonesia_box_is_eighteen_tiles():
    tiles = tiles_for_bbox(*INDONESIA_BBOX)
    assert len(tiles) == 18
    assert {t.h for t in tiles} == {27, 28, 29, 30, 31, 32}
    assert {t.v for t in tiles} == {8, 9, 10}
    assert tiles[0] == Tile(27, 8) and tiles[-1] == Tile(32, 10)


def test_box_ending_on_a_tile_edge_stays_inside():
    assert tiles_for_bbox(110.0, -10.0, 120.0, 0.0) == [Tile(29, 9)]


def test_bad_boxes_are_refused():
    with pytest.raises(ValueError):
        tiles_for_bbox(120.0, -10.0, 110.0, 0.0)
    with pytest.raises(ValueError):
        tiles_for_bbox(170.0, -10.0, 190.0, 0.0)


def test_parse_tile():
    assert parse_tile("h29v09") == Tile(29, 9)
    assert parse_tile(" H29V09 ").id == "h29v09"
    for bad in ("h29", "29v09", "h36v09", "h29v18"):
        with pytest.raises(ValueError):
            parse_tile(bad)
