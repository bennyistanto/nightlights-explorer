"""Which dark places lit up: window means, change classes, the line, nightly excess, the same-view comparison, road lines."""

import datetime as dt

import numpy as np
import pytest

from ntl import events, lightup

nan = np.nan


def test_window_mean_needs_enough_nights():
    #                 cell 0    1    2
    cube = np.array([[1.0, nan, 4.0],
                     [3.0, nan, nan],
                     [5.0, 2.0, nan],
                     [9.0, 9.0, 9.0]])        # outside the window
    np.testing.assert_allclose(lightup.window_mean(cube, 0, 2), [3.0, nan, nan])       # cell 1 and 2 were seen on one night only
    np.testing.assert_allclose(lightup.window_mean(cube, 0, 2, min_nights=1), [3.0, 2.0, 4.0])
    with pytest.raises(ValueError, match="window"):
        lightup.window_mean(cube, 2, 4)
    with pytest.raises(ValueError, match="window"):
        lightup.window_mean(cube, 2, 1)


def test_change_classes_by_hand():
    got = lightup.change_class([-2.0, -1.5, -0.6, 0.0, 0.5, 1.4, 1.5, 3.0, nan])
    # down 1.5 or more is class 1 (the break itself belongs to the class above it), ..., no mean is class 0
    assert got.tolist() == [1, 2, 2, 3, 4, 4, 5, 6, lightup.CHANGE_UNSEEN]


def test_the_line_is_dim_cells_that_rose_and_the_background_dim_cells_that_did_not():
    reference = np.array([1.0, 1.0, 1.0, 5.0, 1.0, nan, 1.0])
    window = np.array([2.5, 2.4, 1.2, 9.0, nan, 4.0, 2.6])
    allowed = np.array([True, True, True, True, True, True, False])
    line, background = lightup.pick_line(reference, window, allowed)
    # cell 0 rose by 1.5; cell 1 by 1.4; cell 2 held; cell 3 is not dim; cells 4 and 5 lack a mean; cell 6 is not allowed
    assert line.tolist() == [True, False, False, False, False, False, False]
    assert background.tolist() == [False, False, True, False, False, False, False]
    assert lightup.pick_line(reference, window)[0].tolist() == [True, False, False, False, False, False, True]


def test_nightly_excess_and_the_same_view_comparison_by_hand():
    reference = np.array([1.0, 2.0, 1.0, 1.0])
    cube = np.array([[1.0, 2.0, 1.0, 1.0],
                     [4.0, nan, 1.5, 0.5],
                     [nan, nan, 1.0, nan]])
    line = np.array([True, True, False, False])
    excess, seen = lightup.nightly_excess(cube, reference, line)
    np.testing.assert_allclose(excess, [0.0, 3.0, nan])            # night 1: only cell 0 is seen, 4 over its reference of 1
    assert seen.tolist() == [2, 1, 0]
    assert np.isnan(lightup.nightly_excess(cube, reference, line, min_cells=2)[0][1])
    background = np.array([False, False, True, True])
    got = lightup.same_view_net(cube, line, background, night=1, partner=0, min_cells=1)
    # the line: cell 0 only, +3; the background: +0.5 and -0.5, so 0; net +3
    assert got == {"cells": 1, "background_cells": 2, "line": 3.0, "background": 0.0, "net": 3.0}
    assert lightup.same_view_net(cube, line, background, night=1, partner=0, min_cells=2)["net"] is None


def test_road_lines_keep_the_two_classes_and_simplify():
    answer = {"elements": [
        {"type": "way", "tags": {"highway": "motorway"}, "geometry": [{"lon": 107.0, "lat": -6.5}, {"lon": 107.5, "lat": -6.50001}, {"lon": 108.0, "lat": -6.5}]},
        {"type": "way", "tags": {"highway": "trunk"}, "geometry": [{"lon": 109.12345678, "lat": -6.87654321}, {"lon": 109.2, "lat": -6.9}]},
        {"type": "way", "tags": {"highway": "residential"}, "geometry": [{"lon": 1.0, "lat": 1.0}, {"lon": 2.0, "lat": 2.0}]},
        {"type": "way", "tags": {"highway": "motorway"}, "geometry": [{"lon": 1.0, "lat": 1.0}]},        # one point is no line
        {"type": "node", "tags": {"highway": "motorway"}},
    ]}
    lines = lightup.road_lines(answer)
    assert lines["motorway"] == [[[107.0, -6.5], [108.0, -6.5]]]            # the middle point was within the tolerance of the straight line
    assert lines["trunk"] == [[[109.1235, -6.8765], [109.2, -6.9]]]
    assert set(lines) == set(lightup.ROAD_CLASSES)


def test_every_study_fits_its_event():
    for key, study in lightup.STUDIES.items():
        event = events.EVENTS[study.event]
        days = [study.reference[0], study.reference[1], *[d for _, _, a, b in study.windows for d in (a, b)], *[d for pair in study.pairs for d in pair],
                *[d for pair in study.placebo for d in pair]]
        if study.held_out is not None:
            days += [*study.held_out[0], study.held_out[1]]
        assert all(event.first <= d <= event.last for d in days), key
        assert study.pick in {w[0] for w in study.windows}, key
        assert all(abs((a - b).days) == events.VIEW_REPEAT_NIGHTS for a, b in study.pairs), key       # same-view pairs are one cycle apart
        assert all(isinstance(d, dt.date) for d in days)
