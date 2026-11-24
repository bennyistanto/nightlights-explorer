"""The long view: yearly VIIRS relative to usual, flags as bits, and the payload the page reads."""

import json

import numpy as np

from ntl import longrecord as lr
from ntl import longview as lv


def _reading(light, **over):
    light = np.asarray(light, dtype=float)
    n = light.size
    fields = dict(light=light, lit=light.copy(), bright=light / 2, outside=light.copy(), saturated=np.zeros(n), observations=np.full(n, 30.0),
                  recall=np.full(n, np.nan), seen=30.0)
    fields.update({k: np.asarray(v, dtype=float) if k != "seen" else v for k, v in over.items()})
    return lr.Reading(**fields)


def test_a_year_of_viirs_is_the_median_month_as_a_ratio_to_usual_and_needs_enough_months():
    years = np.repeat([2012, 2013], 12)
    index = np.full((24, 2), np.log(1.2))
    index[12:, 0] = np.log(0.8)
    index[:7, 1] = np.nan                                     # five months left in 2012 for the second unit: too few
    listed, ratio, months = lv.viirs_yearly(index, years)
    assert listed.tolist() == [2012, 2013]
    np.testing.assert_allclose(ratio[:, 0], [1.2, 0.8])       # 1.0 would be the unit's usual light
    assert np.isnan(ratio[0, 1]) and months[0].tolist() == [12, 5]
    np.testing.assert_allclose(ratio[1, 1], 1.2)


def test_flags_are_packed_as_bits_and_the_payload_follows_the_dmsp_units():
    readings = {("F14", 2000 + i): _reading([100.0, 40.0], recall=[0.9, 0.9]) for i in range(4)}
    readings |= {("F15", 2000 + i): _reading([110.0, 40.0], recall=[0.9, 0.9]) for i in range(4)}
    readings[("F15", 2003)] = _reading([60.0, 40.0], recall=[0.5, 0.9])          # set aside for unit 0
    readings[("F18", 2010)] = _reading([0.0, 50.0], recall=[np.nan, 0.6], saturated=[np.nan, 0.7], observations=[9.0, 30.0])
    record = lr.assemble(readings)
    bits = lv.flag_bits(record)
    assert bits[3].tolist() == [lv.FLAG_ONE_OF_TWO, 0]
    assert bits[4].tolist() == [lv.FLAG_UNDETECTED | lv.FLAG_THIN, lv.FLAG_LOW_RECALL | lv.FLAG_SATURATED]
    # VIIRS knows unit 12 only; the payload keeps the order of the DMSP units and gives nulls to the other
    body = lv.payload(np.array([11, 12]), record, np.array([12]), np.array([2012, 2013]), np.array([[1.1], [np.nan]]), np.array([[12], [3]]))
    assert body["codes"] == [11, 12] and body["dmsp"]["years"] == [2000, 2001, 2002, 2003, 2010] and body["dmsp"]["segment"] == [0, 0, 0, 0, 1]
    assert body["dmsp"]["light"]["value"][0] == [105.0, 105.0, 105.0, 100.0, 0.0]         # a list per unit, a value per year
    assert body["dmsp"]["light"]["low"][0][4] is None                                    # no band on "not detected"
    assert body["dmsp"]["light"]["pair_low"][0][3] == 60.0 and body["dmsp"]["light"]["pair_low"][0][4] is None
    assert "outside" not in body["dmsp"] and body["dmsp"]["sources"][0] == ["F14", "F15"]
    assert body["dmsp"]["recall"][0][3] == 0.9 and body["dmsp"]["recall"][0][4] is None and body["dmsp"]["recall"][1][4] == 0.6
    assert body["dmsp"]["flare_share"] == [0.0, 0.0] and "outside_usable" not in body["dmsp"]
    flared = lr.assemble({("F14", 2000): _reading([100.0, 1.0], outside=[80.0, 0.0]), ("F14", 2001): _reading([300.0, 0.0], outside=[120.0, 0.0])})
    shares = lv.payload(np.array([11, 12]), flared, np.array([12]), np.array([2012]), np.array([[1.0]]), np.array([[12]]))["dmsp"]["flare_share"]
    assert shares == [0.5, 1.0]                # 200 of 400 over both years, not the 60% of the worse year; the second unit's one lit year decides it
    assert body["dmsp"]["satellites"]["F152003"] == {"light": 100.0, "lit": 100.0} and len(body["dmsp"]["light"]["spread"]) == 2
    np.testing.assert_allclose(body["dmsp"]["light"]["spread"][0], record.series["light"].spread[0], atol=1e-4)     # the unit's own
    borrowed = lr.assemble({("F14", 2000): _reading([1.0, 2.0]), ("F15", 2000): _reading([2.0, 2.0])})               # one shared year: no unit has its own
    assert lv.payload(np.array([11, 12]), borrowed, np.array([12]), np.array([2012]), np.array([[1.0]]), np.array([[12]]))["dmsp"]["light"]["spread"] == [None, None]
    assert body["viirs"]["ratio"] == [[None, None], [1.1, None]] and body["viirs"]["months"] == [[0, 0], [12, 3]]
    json.dumps(body, allow_nan=False)                                                    # nothing in it that JSON cannot carry


def test_the_sensor_comparison_is_cut_to_one_level_and_follows_the_dmsp_units():
    comparison = {"years": [2012], "satellite": "F18", "dark_nw": 0.25, "classes": {"2012": [{"low": 0.0, "high": None, "cells": 3, "lit_share": 0.5, "median_dn": 6.0}]},
                  "levels": {"province": {"codes": [12, 11], "unseen": {"2012": [0.4, None]}}}}
    block = lv.sensors_block(comparison, "province", [11, 12, 13])
    assert block["unseen"] == {"2012": [None, 0.4, None]}            # by code, not by position; a unit it does not know gets null
    assert block["classes"] == comparison["classes"] and block["dark_nw"] == 0.25
