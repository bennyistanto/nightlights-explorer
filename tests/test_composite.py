"""Fixed land mask and three-month composite, on values worked by hand."""

import os
from pathlib import Path

import numpy as np
import pytest

from ntl import composite
from ntl import conventions as c
from ntl import qa
from ntl.read import read_grid, read_raw, read_scaled


def test_modal_class_ignores_fill_and_breaks_ties_in_table_order():
    votes = composite.new_class_votes((4,))
    # cell 0: land twice, sea once -> land (1)
    # cell 1: sea once, coastal twice -> coastal (5)
    # cell 2: never classified -> 255
    # cell 3: land once, sea once -> tie, land comes first in the table
    for mask in ([1, 3, 255, 1], [1, 5, 255, 3], [3, 5, 255, 255]):
        composite.add_class_votes(votes, np.array(mask, dtype=np.uint8))
    assert composite.modal_class(votes).tolist() == [1, 5, c.LAND_WATER_FILL, 1]


def test_votes_and_masks_must_fit():
    votes = composite.new_class_votes((2, 3))
    with pytest.raises(ValueError, match="does not fit"):
        composite.add_class_votes(votes, np.zeros((3, 2), dtype=np.uint8))
    with pytest.raises(ValueError, match="does not fit"):
        composite.add_class_votes(votes, np.zeros((1,), dtype=np.uint8))  # would broadcast silently
    with pytest.raises(ValueError, match="layers"):
        composite.modal_class(np.zeros((4, 2, 3), dtype=np.uint16))


def test_fixed_land_excludes_coast_by_default():
    modal = np.array([0, 1, 2, 3, 5, 255], dtype=np.uint8)
    assert composite.is_fixed_land(modal).tolist() == [True, True, False, False, False, False]
    assert composite.is_fixed_land(modal, include_coastal=True).tolist() == [True, True, False, False, True, False]


def test_three_month_on_a_grid_keeps_cells_apart():
    # Two cells, three months, shape (3, 1, 2). Cell A: values 1, 2, 3 on 2, 2, 4 nights.
    # Cell B: only the centre month observed.
    values = np.array([[[1.0, 9.0]], [[2.0, 5.0]], [[3.0, 9.0]]])
    nights = np.array([[[2, 0]], [[2, 6]], [[4, 0]]], dtype=np.uint16)
    observed = np.array([[[True, False]], [[True, True]], [[True, False]]])
    out = composite.three_month(values, nights, observed)
    # A: (1*2 + 2*2 + 3*4) / 8 = 18/8 = 2.25, centre share 2/8. B: 5.0, share 1.
    assert out.value[1].tolist() == [[2.25, 5.0]]
    assert out.nights[1].tolist() == [[8.0, 6.0]]
    assert out.centre_share[1].tolist() == [[0.25, 1.0]]


def test_three_month_by_hand():
    # One cell, four months. Month 2 is gap filled: it holds 6.0 but was not observed.
    values = np.array([2.0, 4.0, 6.0, 8.0])
    nights = np.array([1, 3, 0, 4])
    observed = np.array([True, True, False, True])
    out = composite.three_month(values, nights, observed)
    # t=1: months 0,1,2 -> (2*1 + 4*3) / (1 + 3) = 14/4 = 3.5; 3 of 4 nights are the centre's
    # t=2: months 1,2,3 -> (4*3 + 8*4) / (3 + 4) = 44/7; none of the 7 nights is the centre's
    assert np.isnan(out.value[0]) and np.isnan(out.value[3])  # incomplete windows
    assert out.value[1] == pytest.approx(3.5) and out.value[2] == pytest.approx(44 / 7)
    assert out.nights.tolist() == [0, 4, 7, 0]
    assert out.centre_share[1] == pytest.approx(0.75) and out.centre_share[2] == 0.0


def test_gap_filled_value_never_enters_even_with_nights_claimed():
    values = np.array([1.0, 100.0, 1.0])
    nights = np.array([2, 5, 2])
    observed = np.array([True, False, True])  # the 100 is not an observation
    out = composite.three_month(values, nights, observed)
    assert out.value[1] == pytest.approx(1.0) and out.nights[1] == 4


def test_window_with_nothing_observed_is_nan_not_zero():
    out = composite.three_month(np.zeros((3, 2)), np.zeros((3, 2)), np.zeros((3, 2), dtype=bool))
    assert np.isnan(out.value).all() and np.isnan(out.centre_share).all() and (out.nights == 0).all()


def test_nan_value_marked_observed_is_dropped():
    out = composite.three_month(np.array([np.nan, 3.0, 5.0]), np.array([4, 2, 2]), np.array([True, True, True]))
    assert out.value[1] == pytest.approx(4.0) and out.nights[1] == 4


def test_three_month_shape_checks():
    with pytest.raises(ValueError, match="shapes differ"):
        composite.three_month(np.zeros(3), np.zeros(4), np.zeros(3, dtype=bool))
    with pytest.raises(ValueError, match="three consecutive"):
        composite.three_month(np.zeros(2), np.zeros(2), np.zeros(2, dtype=bool))


DATA_ROOT = Path(os.environ.get("NTL_DATA_ROOT", r"E:\temp\ntl"))
MONTHS = [sorted(DATA_ROOT.glob(f"blackmarble/VNP46A3/2018/{doy}/*.h29v09.*.h5")) for doy in ("182", "213", "244")]


@pytest.mark.skipif(not all(MONTHS), reason="July to September 2018 monthly files for h29v09 not on disk")
def test_three_month_on_real_files_over_lombok():
    files = [m[-1] for m in MONTHS]
    window = read_grid(files[0]).window(115.8, -9.0, 116.8, -8.1)
    base = c.COMPOSITE_LAYER.format(view="AllAngle", suffix="")
    values = np.stack([read_scaled(f, base, window) for f in files])
    nights = np.stack([read_raw(f, base + c.COMPOSITE_NUM, window) for f in files]).astype(float)
    quality = np.stack([read_raw(f, base + c.COMPOSITE_QUALITY, window) for f in files])
    nights[nights == c.COMPOSITE_NUM_FILL] = 0
    observed = qa.composite_observed(quality)
    out = composite.three_month(values, nights, observed)

    seen = out.nights[1] > 0
    assert seen.mean() > 0.9  # dry season: nearly everything is seen
    # Nights add up over the observed months only.
    np.testing.assert_array_equal(out.nights[1], np.where(observed, nights, 0).sum(axis=0))
    # A weighted mean lies between the smallest and largest observed month.
    low = np.where(observed, values, np.inf).min(axis=0)
    high = np.where(observed, values, -np.inf).max(axis=0)
    assert np.all(out.value[1][seen] >= low[seen] - 1e-9) and np.all(out.value[1][seen] <= high[seen] + 1e-9)
    assert np.nanmin(out.centre_share[1]) >= 0 and np.nanmax(out.centre_share[1]) <= 1
