"""F18 beside VIIRS: fine cells onto the coarse grid, classes of radiance, and the light VIIRS does not see."""

import numpy as np

from ntl import sensors
from ntl.read import Grid


def test_fine_cells_go_to_the_coarse_cell_that_holds_their_centre_across_two_tiles():
    # a coarse grid of 2 by 3 cells of one degree whose edges fall on half degrees, as DMSP against VIIRS:
    # 9.5 to 12.5 E, 0.5 to 2.5 N
    target = Grid(west=9.5, north=2.5, cell=1.0, shape=(2, 3))
    total, count = np.zeros(target.shape), np.zeros(target.shape, dtype=np.uint8)
    # two fine "tiles" of half-degree cells that meet at 11 E: the middle coarse column straddles them
    west = Grid(west=10.0, north=2.0, cell=0.5, shape=(2, 2))        # 10 to 11 E, 1 to 2 N
    east = Grid(west=11.0, north=2.0, cell=0.5, shape=(2, 2))        # 11 to 12 E, 1 to 2 N
    sensors.add_to_grid(total, count, np.array([[1.0, 2.0], [3.0, np.nan]]), west, target)
    sensors.add_to_grid(total, count, np.array([[10.0, 20.0], [30.0, 40.0]]), east, target)
    # row 0 of the coarse grid is 1.5 to 2.5 N: it holds the fine row at 1.75 N; row 1 holds the one at 1.25 N
    assert count.tolist() == [[1, 2, 1], [1, 1, 1]]                  # the NaN cell adds nothing
    assert total.tolist() == [[1.0, 12.0, 20.0], [3.0, 30.0, 40.0]]  # the middle column sums both tiles
    # a fine grid wholly outside the coarse one changes nothing
    before = total.copy()
    sensors.add_to_grid(total, count, np.ones((2, 2)), Grid(west=40.0, north=2.0, cell=0.5, shape=(2, 2)), target)
    assert (total == before).all()


def test_classes_of_radiance_report_how_much_the_dmsp_satellite_calls_lit():
    light = np.array([0.0, 0.1, 0.3, 0.3, 5.0, 100.0, np.nan, 0.3])
    dn = np.array([0.0, 6.0, 0.0, 8.0, 30.0, 60.0, 50.0, 9.0])
    inside = np.array([True, True, True, True, True, True, True, False])
    rows = sensors.by_class(dn, light, inside, edges=(0.0, 0.25, 4.0))
    assert [r["cells"] for r in rows] == [2, 2, 2]                   # the NaN cell and the one outside are not counted
    assert [r["lit_share"] for r in rows] == [0.5, 0.5, 1.0]
    assert [r["median_dn"] for r in rows] == [6.0, 8.0, 45.0]
    assert rows[-1]["high"] is None and rows[0]["high"] == 0.25
    empty = sensors.by_class(dn, light, inside, edges=(0.0, 200.0))
    assert empty[1] == {"low": 200.0, "high": None, "cells": 0, "lit_share": None, "median_dn": None}


def test_the_share_of_dmsp_light_with_no_viirs_light_under_it_needs_enough_lit_cells(monkeypatch):
    monkeypatch.setattr(sensors, "MIN_LIT_CELLS", 3)
    units = np.array([1, 1, 1, 1, 2, 2, 2, 2, 0])
    dn = np.array([10.0, 30.0, 0.0, 20.0, 5.0, 5.0, 0.0, 0.0, 99.0])
    light = np.array([0.1, 2.0, 0.0, np.nan, 0.0, 0.0, 0.0, 9.0, 0.0])
    share = sensors.unseen_share(dn, light, units, np.array([1, 2]))
    # unit 1: two lit cells have a VIIRS value (the third lit cell has none): too few to say
    assert np.isnan(share).all()
    dn[2] = 20.0                                                     # a third counted lit cell, dark in VIIRS
    share = sensors.unseen_share(dn, light, units, np.array([1, 2]))
    np.testing.assert_allclose(share[0], 30.0 / 60.0)                # 10 + 20 of 60 lie under 0.25 nW
    assert np.isnan(share[1])                                        # unit 2 still has two lit cells only
