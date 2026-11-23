"""Reader behaviour on a small synthetic file, then on real files if present.

The synthetic file copies the layout seen in real Collection 2 files: the
grid group, one-element array attributes, ``offset`` in A2 style and
``add_offset`` in A1 style.
"""

import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from ntl import conventions as c
from ntl import qa
from ntl.read import Grid, list_layers, read_grid, read_raw, read_scaled

FILL32 = np.float32(-999.9)


@pytest.fixture
def tile(tmp_path):
    """A 4 x 4 'tile' spanning 110E to 110.0167E, 0 to 0.0167S."""
    path = tmp_path / "VNP46A2.A2018217.h29v09.002.0.h5"
    side = 4
    with h5py.File(path, "w") as f:
        f.attrs["WestBoundingCoord"] = 110.0
        f.attrs["EastBoundingCoord"] = 110.0 + side * c.CELL_SIZE_DEG
        f.attrs["NorthBoundingCoord"] = 0.0
        f.attrs["SouthBoundingCoord"] = -side * c.CELL_SIZE_DEG
        g = f.create_group(c.GRID_GROUP)

        ntl = np.arange(16, dtype=np.float32).reshape(4, 4)
        ntl[0, 0] = FILL32
        d = g.create_dataset(c.A2_NTL, data=ntl)
        d.attrs["_FillValue"] = np.array([FILL32])
        d.attrs["scale_factor"] = np.array([1.0], dtype=np.float32)
        d.attrs["offset"] = np.array([0.0], dtype=np.float32)

        # A1-style packed layer: degrees = stored * 0.01, fill -32768.
        zen = np.array([[0, 100, 6340, -32768]] * 4, dtype=np.int16)
        d = g.create_dataset("Sensor_Zenith", data=zen)
        d.attrs["_FillValue"] = np.array([-32768], dtype=np.int16)
        d.attrs["scale_factor"] = np.array([0.01], dtype=np.float32)
        d.attrs["add_offset"] = np.array([0.0], dtype=np.float32)

        # Offset under each of the two attribute names, same numbers.
        bt = np.array([[0, 1000, 65535, 4]] * 4, dtype=np.uint16)
        for name, key in (("BT_add_offset", "add_offset"), ("BT_offset", "offset")):
            d = g.create_dataset(name, data=bt)
            d.attrs["_FillValue"] = np.array([65535], dtype=np.uint16)
            d.attrs["scale_factor"] = np.array([0.0025], dtype=np.float32)
            d.attrs[key] = np.array([203.0], dtype=np.float32)

        flag = np.array([[0, 1, 5, 255]] * 4, dtype=np.uint8)
        d = g.create_dataset(c.A2_QUALITY, data=flag)
        d.attrs["_FillValue"] = np.array([255], dtype=np.uint8)

        g.create_dataset("lat", data=np.zeros(4))  # 1-D: must not be listed
    return path


def test_list_layers_only_two_dimensional(tile):
    assert "lat" not in list_layers(tile)
    assert c.A2_NTL in list_layers(tile)


def test_float32_fill_becomes_nan(tile):
    values = read_scaled(tile, c.A2_NTL)
    assert np.isnan(values[0, 0])
    assert np.isnan(values).sum() == 1
    assert values[0, 1] == 1.0 and values[3, 3] == 15.0
    # No trace of the fill survives as a number.
    assert np.nanmin(values) >= 0.0


def test_packed_layer_is_masked_before_scaling(tile):
    values = read_scaled(tile, "Sensor_Zenith")
    np.testing.assert_allclose(values[0, :3], [0.0, 1.0, 63.4], rtol=0, atol=1e-5)
    assert np.isnan(values[0, 3])  # would be -327.68 if scaled first


def test_both_offset_spellings(tile):
    for name in ("BT_add_offset", "BT_offset"):
        values = read_scaled(tile, name)
        # 1000 * 0.0025 + 203 = 205.5 K
        np.testing.assert_allclose(values[0, [0, 1, 3]], [203.0, 205.5, 203.01], atol=1e-4)
        assert np.isnan(values[0, 2])


def test_read_raw_leaves_flags_untouched(tile):
    raw = read_raw(tile, c.A2_QUALITY)
    assert raw.dtype == np.uint8 and raw[0].tolist() == [0, 1, 5, 255]


def test_window_read_matches_full_read(tile):
    window = (slice(1, 3), slice(2, 4))
    np.testing.assert_array_equal(read_scaled(tile, c.A2_NTL, window), read_scaled(tile, c.A2_NTL)[window])


def test_missing_layer_names_what_exists(tile):
    with pytest.raises(KeyError, match="available"):
        read_scaled(tile, "DNB_BRDF_Corrected_NTL")  # Earth Engine spelling


def test_grid_from_file_and_centres(tile):
    grid = read_grid(tile)
    assert grid.shape == (4, 4) and grid.west == 110.0 and grid.north == 0.0
    lon, lat = grid.centres()
    # First centre is half a cell in from the corner, not on it.
    assert lon[0] == pytest.approx(110.0 + c.CELL_SIZE_DEG / 2)
    assert lat[0] == pytest.approx(-c.CELL_SIZE_DEG / 2)


def test_grid_window_and_subgrid():
    grid = Grid(110.0, 0.0, 0.1, (100, 100))  # 110E to 120E, 0 to 10S
    window = grid.window(116.0, -9.0, 117.0, -8.0)
    assert window == (slice(80, 90), slice(60, 70))
    assert grid.subgrid(window).bounds == pytest.approx((116.0, -9.0, 117.0, -8.0))
    # A box sticking out is clipped; one that misses is an error.
    assert grid.window(119.95, -0.05, 125.0, 5.0) == (slice(0, 1), slice(99, 100))
    with pytest.raises(ValueError):
        grid.window(130.0, -5.0, 131.0, -4.0)


def test_float32_scale_gives_the_documented_decimal(tile):
    with h5py.File(tile, "a") as f:
        d = f[c.GRID_GROUP].create_dataset("Edge", data=np.array([[4000, 18000]], dtype=np.int16))
        d.attrs["_FillValue"] = np.array([-32768], dtype=np.int16)
        d.attrs["scale_factor"] = np.array([0.01], dtype=np.float32)
    # Widening float32 0.01 directly would give 39.99999911 and 179.99999598.
    assert read_scaled(tile, "Edge").tolist() == [[40.0, 180.0]]


def test_undeclared_second_fill_is_masked(tile):
    with h5py.File(tile, "a") as f:
        d = f[c.GRID_GROUP].create_dataset("DNB_Lunar_Irradiance", data=np.array([[1260, 65526, 65535]], dtype=np.uint16))
        d.attrs["_FillValue"] = np.array([65535], dtype=np.uint16)
        d.attrs["scale_factor"] = np.array([0.1])
    values = read_scaled(tile, "DNB_Lunar_Irradiance")
    assert values[0, 0] == pytest.approx(126.0) and np.isnan(values[0, 1:]).all()


def test_integer_layer_without_fill_is_refused(tile):
    with h5py.File(tile, "a") as f:
        g = f[c.GRID_GROUP]
        g.create_dataset("NoFill", data=np.array([[1, -32768]], dtype=np.int16))
        d = g.create_dataset("BadFill", data=np.array([[1, 255]], dtype=np.uint8))
        d.attrs["_FillValue"] = np.array([65535], dtype=np.uint16)
    with pytest.raises(ValueError, match="without _FillValue"):
        read_scaled(tile, "NoFill")
    with pytest.raises(ValueError, match="does not fit"):
        read_scaled(tile, "BadFill")


def test_not_a_black_marble_file(tmp_path):
    other = tmp_path / "other.h5"
    with h5py.File(other, "w") as f:
        f.create_dataset("x", data=np.zeros((2, 2)))
    for function in (list_layers, read_grid):
        with pytest.raises(KeyError):
            function(other)


def test_inverted_or_empty_box_is_refused():
    grid = Grid(110.0, 0.0, 0.1, (100, 100))
    for box in ((117.0, -9.0, 116.0, -8.0), (116.0, -8.0, 116.0, -8.0)):
        with pytest.raises(ValueError, match="west < east"):
            grid.window(*box)


# ---- real files -----------------------------------------------------------

DATA_ROOT = Path(os.environ.get("NTL_DATA_ROOT", r"E:\temp\ntl"))
A2 = sorted(DATA_ROOT.glob("blackmarble/VNP46A2/2018/220/*.h29v09.*.h5"))
A1 = sorted(DATA_ROOT.glob("blackmarble/VNP46A1/2018/220/*.h29v09.*.h5"))
needs_data = pytest.mark.skipif(not (A2 and A1), reason="Lombok window not on disk")


@needs_data
def test_real_a2_tile_georeferencing_and_states():
    grid = read_grid(A2[0])
    assert grid.shape == (2400, 2400)
    assert grid.bounds == pytest.approx((110.0, -10.0, 120.0, 0.0))

    ntl = read_scaled(A2[0], c.A2_NTL)
    flag = read_raw(A2[0], c.A2_QUALITY)
    # Fill in the radiance and "not observed" in the flag are the same cells.
    np.testing.assert_array_equal(np.isnan(ntl), ~qa.observed(flag))
    # Every retrieval is a physical radiance.
    assert np.nanmin(ntl) >= 0.0
    assert set(np.unique(flag).tolist()) <= {0, 1, 2, 3, 4, 5, 255}


@needs_data
def test_real_a1_overpass_time_over_lombok():
    grid = read_grid(A1[0])
    window = grid.window(115.8, -9.0, 116.8, -8.1)
    hours = read_scaled(A1[0], c.A1_UTC_TIME, window)
    # File dated 8 August 2018: Lombok seen at about 17.56 UTC (measured).
    assert 16.5 < np.nanmedian(hours) < 18.6
    zenith = read_scaled(A1[0], "Sensor_Zenith", window)
    assert 0.0 <= np.nanmin(zenith) and np.nanmax(zenith) <= 90.0


A3 = sorted(DATA_ROOT.glob("blackmarble/VNP46A3/2018/213/*.h29v09.*.h5"))


@pytest.mark.skipif(not A3, reason="monthly composite not on disk")
def test_real_a3_quality_follows_observation_count():
    for view in c.COMPOSITE_VIEWS:
        base = c.COMPOSITE_LAYER.format(view=view, suffix="")
        quality = read_raw(A3[-1], base + c.COMPOSITE_QUALITY)
        count = read_raw(A3[-1], base + c.COMPOSITE_NUM)
        land = read_raw(A3[-1], c.COMPOSITE_LAND_WATER) == c.LW_LAND_NO_DESERT
        assert count[quality == c.CQ_GOOD].min() >= 4
        # One to three observations is always poor.
        assert (quality[(count >= 1) & (count <= 3)] == c.CQ_POOR).all()
        # On land, poor means exactly that. Over water and coast the file
        # also marks some cells with 4 or more observations as poor (dim,
        # variable light), a rule the user guide table does not state.
        assert count[(quality == c.CQ_POOR) & land].max() <= 3
        assert count[quality == c.CQ_POOR].min() >= 1
        # Gap filled: a radiance value with nothing observed behind it.
        gap = quality == c.CQ_GAP_FILLED
        if gap.any():
            assert count[gap].max() == 0
            assert not np.isnan(read_scaled(A3[-1], base)[gap]).any()
            assert np.isnan(read_scaled(A3[-1], base + c.COMPOSITE_STD)[gap]).all()
        assert not qa.composite_observed(quality)[gap].any()


# The Lombok window only (days 206 to 237 of 2018, 25 July to 25 August): the count below was measured on those
# 32 files, and other windows of the same tile and year are on disk too (Palu, from day 255).
ALL_A2 = sorted(p for p in DATA_ROOT.glob("blackmarble/VNP46A2/2018/*/*.h29v09.*.h5") if 206 <= int(p.parent.name) <= 237)


@pytest.mark.skipif(len(ALL_A2) < 32, reason="Lombok window not on disk")
def test_real_lunar_irradiance_has_no_sentinel_left():
    # Stored 65526 (6552.6 after scaling) sits on 160 cells of three files,
    # inside the declared valid range. The largest real value is 126.0.
    worst = max(np.nanmax(read_scaled(path, "DNB_Lunar_Irradiance")) for path in ALL_A2)
    assert worst <= 200.0
    sentinel = sum(int((read_raw(path, "DNB_Lunar_Irradiance") == 65526).sum()) for path in ALL_A2)
    assert sentinel == 160
