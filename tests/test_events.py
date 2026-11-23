"""Daily case studies: reference, nightly classes, unit figures, files on disk."""

import dataclasses
import datetime as dt
import gzip
import json

import h5py
import numpy as np
import pytest

from ntl import conventions as c
from ntl import events
from ntl.stack import TileStack

nan = np.nan
HQ, POOR, FILL = c.MQF_HIGH_QUALITY, c.MQF_POOR_OUTLIER, c.MQF_FILL


def test_reference_is_the_median_of_usable_reference_nights():
    #              cell 0  1    2    3
    value = np.array([[10., 4.0, 7.0, 0.0],
                      [12., 5.0, nan, 0.0],
                      [20., 9.0, 9.0, 0.0],     # not a reference night
                      [14., 6.0, 8.0, 0.0]])
    quality = np.array([[HQ, HQ, HQ, HQ], [HQ, POOR, FILL, HQ], [HQ, HQ, HQ, HQ], [HQ, FILL, HQ, HQ]], dtype=np.uint8)
    usable = events.usable_values(value, quality)
    assert np.isnan(usable[1, 1]) and np.isnan(usable[1, 2]) and usable[3, 0] == 14.0
    reference = events.cell_reference(usable, [True, True, False, True], min_nights=2)
    # cell 0: median of 10, 12, 14; cell 1: one usable night only; cell 2: two (7, 8); cell 3: a median of zero is no reference
    assert reference[0] == 12.0 and np.isnan(reference[1]) and reference[2] == 7.5 and np.isnan(reference[3])
    with pytest.raises(ValueError, match="no reference night"):
        events.cell_reference(usable, [False] * 4)
    with pytest.raises(ValueError, match="shape"):
        events.cell_reference(usable, [True, False])


def test_ratio_and_staleness_classes_by_hand():
    reference = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, nan])
    value = np.array([[4.9, 5.0, 7.9, 8.0, 12.5, 3.0, 5.0]])
    quality = np.array([[HQ, HQ, HQ, HQ, HQ, POOR, HQ]], dtype=np.uint8)
    assert events.ratio_class(value, quality, reference).tolist() == [[3, 4, 4, 5, 6, 2, 0]]
    gone = np.array([[nan] * 7])
    assert events.ratio_class(gone, np.full((1, 7), FILL, dtype=np.uint8), reference).tolist() == [[1, 1, 1, 1, 1, 1, 0]]
    assert events.stale_class(np.array([0, 1, 2, 3, 5, 6, 40, 255], dtype=np.uint8)).tolist() == [0, 1, 1, 2, 2, 3, 3, 3]


def test_unit_nights_by_hand():
    reference = np.array([10.0, 30.0, 20.0, 20.0, nan])
    codes = np.array([5208, 5208, 5271, 5271, 5271])
    usable = np.array([
        [10.0, 30.0, 20.0, 20.0, 99.0],     # as the reference
        [4.0, 12.0, nan, 30.0, 99.0],       # 5208 at 40%, both cells down; 5271 half seen, brighter
        [nan, 30.0, nan, nan, 99.0],        # 5208: its bright cell only; 5271 not seen
        [2.0, nan, 20.0, 20.0, nan],        # 5208: its dim cell only, a quarter of its light: uncertain
    ])
    got = events.unit_nights(usable, reference, codes)
    assert got.codes.tolist() == [5208, 5271] and got.cells.tolist() == [2, 2]      # the cell without a reference is left out
    np.testing.assert_allclose(got.ratio[:, 0], [1.0, 0.4, 1.0, 0.2])
    np.testing.assert_allclose(got.coverage[:, 0], [1.0, 1.0, 0.75, 0.25])
    np.testing.assert_allclose(got.down[:, 0], [0.0, 1.0, 0.0, 1.0])
    np.testing.assert_allclose(got.ratio[:, 1], [1.0, 1.5, nan, 1.0])
    np.testing.assert_allclose(got.coverage[:, 1], [1.0, 0.5, 0.0, 1.0])
    assert got.state[:, 0].tolist() == [events.SAME, events.DOWN, events.SAME, events.UNCERTAIN]
    assert got.state[:, 1].tolist() == [events.SAME, events.UP, events.UNCERTAIN, events.SAME]


# ---- from files to the site folder ---------------------------------------------------

SIDE, CELL = c.CELLS_PER_TILE, c.CELL_SIZE_DEG
EVENT = events.Event(key="test", title="A test", tile="h29v09", bbox=(110.0, -1.0, 111.0, 0.0),
                     first=dt.date(2018, 8, 1), last=dt.date(2018, 8, 5), reference_last=dt.date(2018, 8, 2),
                     marks=((dt.date(2018, 8, 3), "shock"),), focus=(5208,), control=(52,), epicentre=(110.0, 0.0), min_reference_nights=2,
                     after=(dt.date(2018, 8, 3), dt.date(2018, 8, 5)), story=(dt.date(2018, 8, 2), dt.date(2018, 8, 3), dt.date(2018, 8, 5)))
# three lit cells in the tile's first row, columns 0, 1 and 2; values by night (no file on 4 August)
NIGHTS = {1: [10.0, 20.0, 5.0], 2: [12.0, 20.0, 5.0], 3: [2.0, 20.0, 5.0], 5: [11.0, 4.0, -999.9]}


def write_night(root, day):
    date = dt.date(2018, 8, day)
    folder = root / c.BLACK_MARBLE_DIR / events.DAILY_PRODUCT / "2018" / f"{date:%j}"
    folder.mkdir(parents=True, exist_ok=True)
    value = np.full((SIDE, SIDE), -999.9, dtype=np.float32)
    quality = np.full((SIDE, SIDE), FILL, dtype=np.uint8)
    stale = np.full((SIDE, SIDE), 255, dtype=np.uint8)
    value[0, :3] = NIGHTS[day]
    quality[0, :3] = [HQ, HQ, FILL if NIGHTS[day][2] < 0 else HQ]
    stale[0, :3] = [0, 0, 2]
    with h5py.File(folder / f"{events.DAILY_PRODUCT}.A2018{date:%j}.h29v09.002.2025001000000.h5", "w") as f:
        f.attrs["WestBoundingCoord"], f.attrs["EastBoundingCoord"] = 110.0, 120.0
        f.attrs["NorthBoundingCoord"], f.attrs["SouthBoundingCoord"] = 0.0, -10.0
        g = f.create_group(c.GRID_GROUP)
        kw = dict(compression="gzip", compression_opts=1)
        g.create_dataset(c.A2_NTL, data=value, **kw).attrs["_FillValue"] = np.array([np.float32(-999.9)])
        g.create_dataset(c.A2_QUALITY, data=quality, **kw).attrs["_FillValue"] = np.array([FILL], dtype=np.uint8)
        g.create_dataset(events.A2_LATEST, data=stale, **kw).attrs["_FillValue"] = np.array([255], dtype=np.uint8)


def test_an_event_goes_from_daily_files_to_the_site_folder(tmp_path):
    for day in NIGHTS:
        write_night(tmp_path, day)
    months = (dt.date(2018, 8, 1),)
    lon = 110.0 + (np.array([2, 0, 1]) + 0.5) * CELL          # deliberately not in grid order
    domain = TileStack(tile="h29v09", view="AllAngle", months=months, lon=lon, lat=np.full(3, -0.5 * CELL),
                       province=np.full(3, 52), district=np.array([5271, 5208, 5208]), subdistrict=np.array([527101, 520801, 0]),
                       usual=np.ones(3), value=np.ones((1, 3), dtype=np.float32), nights=np.ones((1, 3), dtype=np.uint16),
                       quality=np.zeros((1, 3), dtype=np.uint8))
    stack = events.build_event_stack(tmp_path, EVENT, domain)
    assert stack.dates == tuple(dt.date(2018, 8, d) for d in range(1, 6)) and stack.value.shape == (5, 3)
    np.testing.assert_allclose(stack.value[0], [5.0, 10.0, 20.0])          # each cell reads its own column of the file
    assert np.isnan(stack.value[3]).all() and (stack.quality[3] == FILL).all()   # 4 August: no file
    meta = events.export_event(EVENT, stack, tmp_path / "site")
    folder = tmp_path / "site" / "events" / "test"
    assert meta["cells"] == {"total": 3, "with_reference": 3, "focus": 2, "control": 3} and meta["reference"]["nights"] == 2
    # the control here is the whole province: its median ratio each night, NaN on the night without a file
    assert meta["story"]["control"]["median"] == [pytest.approx(1.0, abs=0.1), pytest.approx(1.0, abs=0.1), 1.0, None, pytest.approx(0.6, abs=0.01)]
    # the factor used is its summed light over its summed reference (references 11, 20 and 5)
    assert meta["story"]["control"]["light"] == [pytest.approx(35 / 36, abs=1e-3), pytest.approx(37 / 36, abs=1e-3), pytest.approx(27 / 36, abs=1e-3), None, pytest.approx(15 / 31, abs=1e-3)]
    assert meta["story"]["focus"]["light_adjusted"][2] is None          # two focus cells: under MIN_BAND_CELLS, no figure
    assert meta["reference"]["first"] == "2018-08-01" and meta["reference"]["last"] == "2018-08-02" and "flag 0" in meta["reference"]["rule"]
    assert meta["story"]["same_geometry"]["lag"] == 16 and meta["story"]["same_geometry"]["focus"]["ratio"] == [None] * 5      # five nights: no pair
    info = np.frombuffer(gzip.decompress((folder / "cell_info.u8.gz").read_bytes()), dtype=np.uint8).reshape(3, 2)
    assert info[:, 0].tolist() == [1, 1, 2] and info[:, 1].tolist() == [0, 1, 1]          # two focus cells, one control-only cell; a quarter, three quarters and one and a quarter km from the epicentre
    adjusted = np.frombuffer(gzip.decompress((folder / "adjusted.u8.gz").read_bytes()), dtype=np.uint8).reshape(5, 3)
    # no control on the night without a file; on 3 August the control (which holds the dimmed cell) reads 0.75, so the steady cells read 1.33
    assert adjusted[3].tolist() == [7, 7, 7] and adjusted[2].tolist() == [3, 6, 6]
    packed = np.frombuffer(gzip.decompress((folder / "nights.u8.gz").read_bytes()), dtype=np.uint8).reshape(5, 3)
    # cells in grid order have references 11, 20 and 5
    assert (packed & 7).tolist() == [[5, 5, 5], [5, 5, 5], [3, 5, 5], [1, 1, 1], [5, 3, 1]]
    assert (packed >> 3).tolist()[0] == [0, 0, 1] and (packed >> 3).tolist()[3] == [3, 3, 3]
    units = json.loads((folder / "units.json").read_text(encoding="utf-8"))
    d = units["district"]
    assert d["code"] == [5208, 5271] and d["cells"] == [2, 1]
    assert d["ratio"][0] == [pytest.approx(30 / 31, abs=1e-3), pytest.approx(32 / 31, abs=1e-3), pytest.approx(22 / 31, abs=1e-3), None, pytest.approx(15 / 31, abs=1e-3)]
    assert d["state"][0] == [events.SAME, events.SAME, events.DOWN, events.UNCERTAIN, events.DOWN]
    assert d["state"][1] == [events.SAME, events.SAME, events.SAME, events.UNCERTAIN, events.UNCERTAIN]
    assert units["subdistrict"]["code"] == [520801, 527101]                # the cell held by its district is in no sub-district
    js = (folder / "files.js").read_text(encoding="utf-8")
    assert all(f'FileAttachment("{name}")' in js for name in ("cells.u32.gz", "nights.u8.gz", "units.json", "meta.json"))
    with pytest.raises(FileNotFoundError, match="no daily file"):
        events.build_event_stack(tmp_path, dataclasses.replace(EVENT, first=dt.date(2019, 1, 1), last=dt.date(2019, 1, 2), reference_last=dt.date(2019, 1, 1),
                                                               marks=(), story=(), after=None), domain)
    # a focus with no referenced cell is refused by name, not by a traceback from a quantile
    with pytest.raises(ValueError, match="no focus cell has a reference"):
        events.export_event(dataclasses.replace(EVENT, key="nofocus", focus=(9999,)), stack, tmp_path / "site")


def test_a_damaged_night_is_left_as_not_seen(tmp_path):
    for day in NIGHTS:
        write_night(tmp_path, day)
    bad = next((tmp_path / c.BLACK_MARBLE_DIR / events.DAILY_PRODUCT / "2018" / "214").glob("*.h5"))      # 2 August
    bad.write_bytes(b"not an hdf5 file")
    lon = 110.0 + (np.array([0, 1, 2]) + 0.5) * CELL
    domain = TileStack(tile="h29v09", view="AllAngle", months=(dt.date(2018, 8, 1),), lon=lon, lat=np.full(3, -0.5 * CELL),
                       province=np.full(3, 52), district=np.array([5208, 5208, 5271]), subdistrict=np.zeros(3, dtype=np.int64),
                       usual=np.ones(3), value=np.ones((1, 3), dtype=np.float32), nights=np.ones((1, 3), dtype=np.uint16),
                       quality=np.zeros((1, 3), dtype=np.uint8))
    stack = events.build_event_stack(tmp_path, EVENT, domain)
    assert np.isnan(stack.value[1]).all() and (stack.quality[1] == FILL).all() and stack.value[0].tolist() == [10.0, 20.0, 5.0]
    cube, _, _ = events.read_window(tmp_path, EVENT)
    assert np.isnan(cube[1]).all() and cube[0, 0, :3].tolist() == [10.0, 20.0, 5.0]


def test_light_ratio_and_same_geometry_by_hand():
    reference = np.array([10.0, 30.0, nan, 20.0])
    usable = np.array([[10.0, 30.0, 5.0, 20.0],
                       [5.0, nan, 5.0, 10.0],        # the bright cell is not seen: 15 over 30, not over 60
                       [nan, nan, 5.0, nan]])
    ratio, seen = events.light_ratio(usable, reference, [True, True, True, True], min_cells=1)
    np.testing.assert_allclose(ratio, [1.0, 0.5, nan])            # the cell without a reference never counts
    assert seen.tolist() == [3, 2, 0]
    assert np.isnan(events.light_ratio(usable, reference, [True, True, True, True], min_cells=3)[0][1])
    # nights two apart: only cells seen on both count
    nights = np.array([[10.0, 4.0, nan], [1.0, 1.0, 1.0], [5.0, nan, 9.0], [2.0, 3.0, nan]])
    ratio, shared = events.same_geometry(nights, [True, True, True], lag=2, min_cells=1)
    np.testing.assert_allclose(ratio, [nan, nan, 0.5, 2.5])       # night 2: cell 0 only, 5 over 10; night 3: cells 0 and 1, 5 over 2
    assert shared.tolist() == [0, 0, 1, 2]
    assert np.isnan(events.same_geometry(nights, [True, True, True], lag=2, min_cells=2)[0][2])
    with pytest.raises(ValueError, match="lag"):
        events.same_geometry(nights, [True, True, True], lag=0)


def test_an_event_refuses_dates_outside_its_window_and_the_table_is_consistent():
    with pytest.raises(ValueError, match="marks"):
        dataclasses.replace(EVENT, marks=((dt.date(2018, 9, 1), "late"),))
    with pytest.raises(ValueError, match="story"):
        dataclasses.replace(EVENT, story=(dt.date(2018, 7, 1),))
    with pytest.raises(ValueError, match="after last"):
        dataclasses.replace(EVENT, first=dt.date(2018, 8, 6))
    for event in events.EVENTS.values():          # building the table already ran the checks; these are the ones it cannot make
        assert not set(event.focus) & set(event.control_districts), event.key
        assert event.focus and (event.control or event.control_districts), event.key


def test_control_factor_needs_enough_of_the_control_seen():
    ratio = np.array([[1.0, 1.2, 0.8, 0.5, nan],
                      [0.5, nan, nan, 0.5, nan],
                      [0.7, 0.9, 0.8, 2.0, nan]])
    control = np.array([True, True, True, False, True])       # the last control cell never has a value: it has no reference
    factor, seen = events.control_factor(ratio, control, min_seen=0.5)
    np.testing.assert_allclose(seen, [1.0, 1 / 3, 1.0])
    np.testing.assert_allclose(factor, [1.0, nan, 0.8])
    with pytest.raises(ValueError, match="no control cell"):
        events.control_factor(ratio, np.array([False, False, False, False, True]))


def test_dark_and_lit_by_hand_and_distance():
    before = np.array([[0.0, 0.2, 5.0, 4.0, 0.0, nan]] * 3)
    after = np.array([[3.0, 0.1, 0.0, 4.0, 3.0, 3.0]] * 3)
    after[:2, 4] = nan                                          # seen on one night only afterwards: not judged
    dark_before, lit_up, lit_before, went_dark = events.dark_and_lit(before, after)
    assert dark_before.tolist() == [True, True, False, False, False, False]
    assert lit_up.tolist() == [True, False, False, False, False, False]
    assert lit_before.tolist() == [False, False, True, True, False, False]
    assert went_dark.tolist() == [False, False, True, False, False, False]
    # one degree of latitude is about 111.2 km; a degree of longitude at 60 degrees is half that
    np.testing.assert_allclose(events.distance_km([10.0, 11.0], [61.0, 60.0], (10.0, 60.0)), [111.195, 55.597], atol=0.01)


def test_an_event_can_name_its_reference_nights_and_admit_poor_quality(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "MIN_BAND_CELLS", 1)       # the fixture has two focus cells
    for day in NIGHTS:
        write_night(tmp_path, day)
    lon = 110.0 + (np.array([0, 1, 2]) + 0.5) * CELL
    domain = TileStack(tile="h29v09", view="AllAngle", months=(dt.date(2018, 8, 1),), lon=lon, lat=np.full(3, -0.5 * CELL),
                       province=np.full(3, 52), district=np.array([5208, 5208, 3510]), subdistrict=np.zeros(3, dtype=np.int64),
                       usual=np.ones(3), value=np.ones((1, 3), dtype=np.float32), nights=np.ones((1, 3), dtype=np.uint16),
                       quality=np.zeros((1, 3), dtype=np.uint8))
    # the reference is the LAST night, as for an event whose earlier nights are under cloud; district 3510 is the control
    late = dataclasses.replace(EVENT, key="late", reference_nights=(dt.date(2018, 8, 5),), min_reference_nights=1, control=(), control_districts=(3510,),
                               story=(dt.date(2018, 8, 3),))
    stack = events.build_event_stack(tmp_path, late, domain)
    meta = events.export_event(late, stack, tmp_path / "site")
    assert meta["reference"]["dates"] == ["2018-08-05"] and meta["cells"]["with_reference"] == 2     # the third cell has no retrieval that night
    assert meta["cells"]["control"] == 0 and "control" not in meta["story"]                           # so the control has no reference: no adjusted figures
    assert meta["story"]["focus"]["light"][2] == pytest.approx((2.0 + 20.0) / (11.0 + 4.0), abs=1e-3)  # 3 August over the reference of 5 August
    assert meta["story"]["brightest"]["cells"][0]["radiance"] == 20.0
    # flag 1 is refused by default and admitted on request
    value, quality = np.array([[5.0, 5.0]]), np.array([[HQ, POOR]], dtype=np.uint8)
    assert np.isnan(events.usable_values(value, quality)[0, 1]) and events.usable_values(value, quality, (HQ, POOR))[0, 1] == 5.0
    assert events.ratio_class(value, quality, np.array([5.0, 5.0]), (HQ, POOR)).tolist() == [[5, 5]]


def test_recovery_nights_by_hand():
    adjusted = np.array([
        # cell: 0     1     2     3     4     5
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],        # before the event
        [0.2, 0.3, 0.9, nan, 0.4, nan],        # first night after
        [0.5, nan, 0.9, nan, nan, nan],
        [0.85, nan, 0.2, 0.1, nan, nan],
        [0.3, 0.7, 0.9, 0.79, nan, nan],
        [0.9, 0.8, 0.9, nan, nan, nan],
    ])
    got = events.recovery_nights(adjusted, start=1)
    # 0: hit, seen back two nights later; 1: hit, back on the fourth night after (cloud in between: an upper bound);
    # 2: not hit on its first seen night (a later dip does not count); 3: first seen two nights later and hit, never seen back;
    # 4: hit and never seen again; 5: never seen
    assert got.tolist() == [2, 4, events.NOT_HIT, events.NEVER_BACK, events.NEVER_BACK, events.NOT_JUDGED]
    with pytest.raises(ValueError, match="not one of its nights"):
        events.recovery_nights(adjusted, start=6)


def test_matched_reference_by_hand():
    #                  cell 0   1
    usable = np.array([[10.0, 8.0],      # reference night, seen from 5 degrees
                       [20.0, nan],      # reference night, 60 degrees
                       [12.0, 6.0],      # reference night, 12 degrees
                       [6.0, 4.0],       # the event night, 8 degrees
                       [18.0, 9.0]])     # a later night, 62 degrees
    zenith = np.array([[5.0, 5.0], [60.0, 60.0], [12.0, 12.0], [8.0, 8.0], [62.0, 62.0]])
    nights = [True, True, True, False, False]
    reference, used = events.matched_reference(usable, zenith, nights, tolerance=10.0)
    # the event night is like the nights at 5 and 12 degrees: medians 11 and 7; the later night is like the 60 degree night only
    np.testing.assert_allclose(reference[3], [11.0, 7.0])
    np.testing.assert_allclose(reference[4], [20.0, nan])
    assert used[3].tolist() == [2, 2] and used[4].tolist() == [1, 0]
    # a reference night is never its own reference: night 0 is judged against night 2 only, night 1 has no other night like it
    np.testing.assert_allclose(reference[0], [12.0, 6.0])
    assert np.isnan(reference[1]).all()
    light, cells = events.nightly_light(usable, reference, [True, True], min_cells=1)
    np.testing.assert_allclose(light, [18 / 18, nan, 18 / 18, 10 / 18, 18 / 20])
    assert cells.tolist() == [2, 0, 2, 2, 1]
    assert np.isnan(events.matched_reference(usable, zenith, nights, tolerance=10.0, min_nights=2)[0][4]).all()
    with pytest.raises(ValueError, match="no reference night"):
        events.matched_reference(usable, zenith, [False] * 5)
    with pytest.raises(ValueError, match="shapes"):
        events.matched_reference(usable, zenith[:3], nights)


def test_view_zenith_reads_its_own_night_or_one_a_cycle_away(tmp_path):
    def write_angles(date, hundredths):
        folder = tmp_path / c.BLACK_MARBLE_DIR / events.ANGLE_PRODUCT / f"{date:%Y}" / f"{date:%j}"
        folder.mkdir(parents=True, exist_ok=True)
        data = np.full((SIDE, SIDE), events.A1_ANGLE_FILL, dtype=np.int16)
        data[0, :2] = hundredths
        with h5py.File(folder / f"{events.ANGLE_PRODUCT}.A{date:%Y%j}.h29v09.002.2025001000000.h5", "w") as f:
            f.attrs["WestBoundingCoord"], f.attrs["EastBoundingCoord"] = 110.0, 120.0
            f.attrs["NorthBoundingCoord"], f.attrs["SouthBoundingCoord"] = 0.0, -10.0
            f.create_group(c.GRID_GROUP).create_dataset(events.A1_SENSOR_ZENITH, data=data, compression="gzip", compression_opts=1)

    write_angles(dt.date(2018, 8, 2), [-4150, 1200])            # the layer is signed by the side of the swath
    write_angles(dt.date(2018, 7, 16), [3000, 3100])            # sixteen nights before 1 August
    lon = 110.0 + (np.array([0, 1, 2]) + 0.5) * CELL
    zenith, cycles = events.view_zenith(tmp_path, EVENT, lon, np.full(3, -0.5 * CELL))
    np.testing.assert_allclose(zenith[1], [41.5, 12.0, nan])    # 2 August from its own file; the third cell holds fill
    np.testing.assert_allclose(zenith[0], [30.0, 31.0, nan])    # 1 August from the file one cycle earlier
    assert cycles.tolist() == [-1, 0, -32768, -32768, -32768] and np.isnan(zenith[2:]).all()
    with pytest.raises(FileNotFoundError):
        events.view_zenith(tmp_path / "nowhere", EVENT, lon, np.full(3, -0.5 * CELL))
