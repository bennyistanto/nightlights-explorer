"""Light sources: the neighbour weights, the local background, a source month, a consistent source, the domain."""

import numpy as np
import pytest

from ntl import conventions as c
from ntl import sources, stack

nan = np.nan


def test_kernel_weights_by_hand():
    # cells of 1 km, a radius of 2 km, a scale of 1 km: weight 1 / (1 + d)^3
    kernel = sources.source_kernel(radius_km=2.0, scale_km=1.0, cell_km=1.0)
    assert kernel.shape == (5, 5) and kernel[2, 2] == 0.0
    raw = {1.0: 1 / 8, np.sqrt(2): 1 / (1 + np.sqrt(2)) ** 3, 2.0: 1 / 27}
    total = 4 * raw[1.0] + 4 * raw[np.sqrt(2)] + 4 * raw[2.0]            # the corners and knight moves lie beyond 2 km
    np.testing.assert_allclose(kernel[2, 3], raw[1.0] / total)
    np.testing.assert_allclose(kernel[1, 1], raw[np.sqrt(2)] / total)
    np.testing.assert_allclose(kernel[2, 4], raw[2.0] / total)
    assert kernel[0, 0] == 0.0 and kernel[0, 1] == 0.0
    np.testing.assert_allclose(kernel.sum(), 1.0)
    np.testing.assert_allclose(kernel, kernel[::-1, ::-1])
    with pytest.raises(ValueError, match="under one cell"):
        sources.source_kernel(radius_km=0.2, scale_km=1.0, cell_km=1.0)
    with pytest.raises(ValueError, match="positive"):
        sources.source_kernel(radius_km=2.0, scale_km=0.0, cell_km=1.0)


def test_background_is_the_weighted_mean_of_good_neighbours():
    kernel = sources.source_kernel(radius_km=1.0, scale_km=1.0, cell_km=1.0)      # the four nearest neighbours, a quarter each
    np.testing.assert_allclose(kernel[[0, 1, 1, 2], [1, 0, 2, 1]], 0.25)
    radiance = np.array([[1.0, 2.0, 3.0],
                         [4.0, 50.0, 6.0],
                         [7.0, 8.0, 9.0]])
    good = np.ones((3, 3), dtype=bool)
    background = sources.background_filter((3, 3), kernel)
    got = background(radiance, good)
    np.testing.assert_allclose(got[1, 1], (2 + 4 + 6 + 8) / 4)            # the centre does not count towards its own background
    np.testing.assert_allclose(got[0, 0], (2 + 4) / 2)                    # a corner has two neighbours: their mean, not a half of it
    good[0, 1] = False
    radiance[0, 1] = -999.0                                               # whatever sits in a cell that is not good is ignored
    got = background(radiance, good)
    np.testing.assert_allclose(got[1, 1], (4 + 6 + 8) / 3)
    np.testing.assert_allclose(got[0, 0], 4.0)
    alone = np.zeros((3, 3), dtype=bool)
    alone[1, 1] = True
    assert np.isnan(background(radiance, alone)[1, 1])                    # no good neighbour: no background
    with pytest.raises(ValueError, match="shape"):
        background(np.zeros((4, 4)), np.ones((4, 4), dtype=bool))
    with pytest.raises(ValueError, match="odd side"):
        sources.background_filter((3, 3), np.ones((2, 2)))


def test_a_source_exceeds_its_background_by_the_margin():
    radiance = np.array([3.0, 2.4, 2.6, 9.0, 9.0])
    background = np.array([2.0, 2.0, 2.0, nan, 2.0])
    good = np.array([True, True, True, True, False])
    # 1.0 over, 0.4 over, 0.6 over, no background, not good
    assert sources.is_source(radiance, good, background, 0.5).tolist() == [True, False, True, False, False]
    assert sources.is_source(radiance, good, background, 1.0).tolist() == [False] * 5       # the margin must be exceeded, not met


def test_consistent_sources_need_a_share_of_the_good_months():
    got = sources.consistent_sources([6, 5, 0, 0, 12], [12, 12, 12, 0, 12], 0.5)
    assert got.tolist() == [True, False, False, False, True]              # half is enough; a cell with no good month is never one
    with pytest.raises(ValueError, match="min_share"):
        sources.consistent_sources([1], [2], 0.0)


def test_the_domain_takes_a_dim_cell_that_is_a_source():
    land = np.array([True, True, True, True, False])
    in_province = np.array([True, True, True, False, True])
    good = np.array([20, 20, 5, 20, 20])
    mean = np.array([3.0, 1.2, 1.2, 1.2, 1.2])
    source = np.array([False, True, True, True, True])
    assert stack.lit_domain(land, in_province, good, mean).tolist() == [True, False, False, False, False]
    # a source under 2 nW comes in, but not with too few good months, outside a province, or off the land
    assert stack.lit_domain(land, in_province, good, mean, source=source).tolist() == [True, True, False, False, False]


def test_the_default_filter_reaches_13_cells_and_a_bright_cell_among_dark_ones_is_a_source():
    kernel = sources.source_kernel()
    assert kernel.shape == (27, 27) and c.CELL_KM == pytest.approx(0.4633, abs=1e-4)
    radiance = np.zeros((40, 40))
    radiance[20, 20] = 1.5                                                # a dim, isolated light
    radiance[5:9, 5:9] = 30.0                                             # a bright block: its inner cells have bright neighbours
    good = np.ones((40, 40), dtype=bool)
    background = sources.background_filter((40, 40), kernel)(radiance, good)
    source = sources.is_source(radiance, good, background)
    assert source[20, 20] and not source[20, 21] and not source[30, 30]
    assert source[5, 5]                                                   # the corner of the block stands above its surroundings
    assert background[6, 6] > background[5, 5] > 1.0                      # and the inside of the block has the higher background


def test_a_stack_remembers_whether_sources_were_added(tmp_path):
    import datetime as dt

    def make(contrast):
        return stack.TileStack(tile="h29v09", view="AllAngle", months=(dt.date(2020, 1, 1),), lon=np.array([110.1, 110.2]), lat=np.array([-1.0, -1.0]),
                               province=np.array([52, 52]), district=np.array([5201, 5201]), subdistrict=np.array([520101, 520101]),
                               usual=np.array([3.0, 1.2]), value=np.ones((1, 2), dtype=np.float32), nights=np.ones((1, 2), dtype=np.uint16),
                               quality=np.zeros((1, 2), dtype=np.uint8), source_contrast=contrast)

    for contrast in (0.5, None):
        again = stack.load(stack.save(make(contrast), tmp_path / f"s{contrast}.npz"))
        assert again.source_contrast == contrast
    # the statuses use the mean rule: a stack is built without sources unless asked
    import inspect
    assert inspect.signature(stack.build_stack).parameters["source_contrast"].default is None
    # stacks built by different rules do not join
    other = stack.TileStack(**{**make(None).__dict__, "tile": "h30v09", "lon": np.array([120.1, 120.2])})
    assert stack.concat([make(None), other]).source_contrast is None
    with pytest.raises(ValueError, match="different domain rules"):
        stack.concat([make(0.5), other])
