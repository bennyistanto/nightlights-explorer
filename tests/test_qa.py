"""Quality decoding on values worked by hand from User Guide Tables 6 and 9."""

import numpy as np
import pytest

from ntl import conventions as c
from ntl import qa

# One cloud-mask value built bit by bit:
#   bit 0      night            0          ->   0
#   bits 1-3   land no desert   001        ->   1 << 1 = 2
#   bits 4-5   mask quality     11 (high)  ->   3 << 4 = 48
#   bits 6-7   confident cloudy 11         ->   3 << 6 = 192
#   bit 8      shadow           1          ->   256
# Sum: 498.
CLOUDY_LAND = 498
# Night, sea water (011 -> 6), quality medium (10 -> 32), confident clear: 38.
CLEAR_SEA = 38
# Night, coastal (101 -> 10), quality high (48), probably clear (01 -> 64),
# snow/ice bit 10 (1024), lunar eclipse bit 13 (8192): 9338.
COASTAL_ECLIPSE = 9338

PACKED = np.array([[CLOUDY_LAND, CLEAR_SEA], [COASTAL_ECLIPSE, c.CLOUD_MASK_FILL]], dtype=np.uint16)


def test_cloud_confidence():
    assert qa.cloud_confidence(PACKED).tolist() == [[3, 0], [1, 255]]


def test_land_water_and_is_land():
    assert qa.land_water(PACKED).tolist() == [[1, 3], [5, 255]]
    assert qa.is_land(PACKED).tolist() == [[True, False], [True, False]]
    assert qa.is_land(PACKED, include_coastal=False).tolist() == [[True, False], [False, False]]


def test_single_bit_fields():
    assert qa.bit_field(PACKED, c.CM_SHADOW).tolist() == [[1, 0], [0, 255]]
    assert qa.bit_field(PACKED, c.CM_SNOW_ICE).tolist() == [[0, 0], [1, 255]]
    assert qa.bit_field(PACKED, c.CM_LUNAR_ECLIPSE).tolist() == [[0, 0], [1, 255]]
    assert qa.bit_field(PACKED, c.CM_MASK_QUALITY).tolist() == [[3, 2], [3, 255]]
    assert qa.bit_field(PACKED, c.CM_DAY_NIGHT).tolist() == [[0, 0], [0, 255]]


def test_fill_is_never_decoded_as_cloud():
    # 65535 has every bit set; decoded naively it reads "confident cloudy".
    only_fill = np.array([c.CLOUD_MASK_FILL], dtype=np.uint16)
    assert qa.cloud_confidence(only_fill).tolist() == [c.DECODED_FILL]


def test_signed_input_is_refused():
    with pytest.raises(TypeError):
        qa.cloud_confidence(np.array([498], dtype=np.int16))


FLAGS = np.array([0, 1, 2, 3, 4, 5, 255], dtype=np.uint8)


def test_observed_is_everything_but_fill():
    assert qa.observed(FLAGS).tolist() == [True] * 6 + [False]


def test_usable_strict_by_default():
    assert qa.usable(FLAGS).tolist() == [True] + [False] * 6
    assert qa.usable(FLAGS, {0, 1}).tolist() == [True, True] + [False] * 5


def test_fill_can_never_be_allowed():
    with pytest.raises(ValueError):
        qa.usable(FLAGS, {0, 255})


def test_observation_state_keeps_three_states_apart():
    state = qa.observation_state(FLAGS)
    assert state.tolist() == [qa.USABLE] + [qa.REJECTED] * 5 + [qa.NOT_OBSERVED]
    assert state.dtype == np.uint8


def test_flag_layers_must_be_as_stored():
    # A flag read through read_scaled has NaN for fill; NaN != 255 would
    # make "not observed" look observed.
    as_float = np.array([0.0, np.nan, 255.0])
    for function in (qa.observed, qa.usable, qa.observation_state):
        with pytest.raises(TypeError):
            function(as_float)
    # Signed storage would hold 255 as -1.
    with pytest.raises(TypeError):
        qa.observed(np.array([0, -1], dtype=np.int8))


def test_scalar_cloud_mask_decodes():
    assert int(qa.cloud_confidence(np.uint16(CLOUDY_LAND))) == 3
    assert int(qa.cloud_confidence(np.uint16(c.CLOUD_MASK_FILL))) == c.DECODED_FILL


def test_gap_filled_composite_is_not_observed():
    quality = np.array([0, 1, 2, 255], dtype=np.uint8)
    assert qa.composite_observed(quality).tolist() == [True, True, False, False]
    assert qa.composite_observed(quality, good_only=True).tolist() == [True, False, False, False]
    with pytest.raises(TypeError):
        qa.composite_observed(quality.astype(float))


def test_composite_layer_names():
    name = c.COMPOSITE_LAYER.format(view="NearNadir", suffix=c.COMPOSITE_QUALITY)
    assert name == "NearNadir_Composite_Snow_Free_Quality"


def test_vi_used_bit():
    # Bit 11 is 2048.
    assert qa.bit_field(np.array([2048, 0], dtype=np.uint16), c.CM_VI_USED).tolist() == [1, 0]
