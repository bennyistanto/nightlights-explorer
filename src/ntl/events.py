"""Daily case studies: night-by-night light around a dated event.

The monthly monitor cannot see an event that lasts days (Lombok, August
2018: every district read normal). This module works on the daily product
instead, for one event at a time, over the lit cells of the status domain
inside the event's box.

Product: NASA Black Marble daily, VNP46A2, Collection 2, layer
``DNB_BRDF-Corrected_NTL`` (lunar and atmosphere corrected radiance, nW cm-2
sr-1) with ``Mandatory_Quality_Flag``; only high-quality retrievals (flag 0)
are used unless the event admits more (``Event.quality``: Nyepi 2026 admits
flag 1, because on that night most of Bali carries it). ``Latest_High_Quality_Retrieval`` (days since the last such
retrieval) is carried along to show how stale a cell is; the gap-filled
layer is not used for any figure.

**Which night a file is.** A file dated D holds the overpass of about 01:30
local time on D + 1, that is the night that begins on the evening of local
date D (measured from ``UTC_Time`` in VNP46A1 over Lombok; README,
"Downloading"). A shock in the evening of D is first seen in the file dated
D; a shock in the morning of D likewise.

Method ([P]: picked for this project, not from a document, not reviewed):

1. **Reference**: for each cell, the median of its usable values in
   the event's reference nights, if it has enough of them
   (``Event.min_reference_nights``). A cell without a reference is left
   out of every figure. For Lombok the reference is the eleven nights
   before the mainshock night: the four nights before the first shock
   gave a reference to only 1,016 of 2,746 cells, eleven give 6,980 of
   7,303 in the wider box (2026-11-23).
1b. **Control**: nightly radiance moves up and down over a whole region for
   reasons that are not on the ground (sky, view angle, the moonlight
   correction). The event names a control area that the event did not
   touch (Bali for Lombok). Each night's shared movement is the control's
   summed light over its summed reference (:func:`light_ratio`, the same
   statistic as every unit figure), used only when enough of its cells
   were seen, and an *adjusted* ratio is a ratio divided by it. A night
   without a usable control has no adjusted figure. A control seen at a
   different view angle does not remove the angle (below).
1c. **Same geometry**: the satellite's view zenith repeats every 16 nights
   (``VIEW_REPEAT_NIGHTS``), and a city's light changes with it by tens of
   percent. :func:`same_geometry` compares each night with the night 16
   before over the cells seen on both.
1d. **Matched reference**: with the view zenith of every night (read from
   VNP46A1, :func:`view_zenith`), a cell's reference for a night is the
   median of its reference nights seen from within ``ZENITH_TOLERANCE``
   degrees of that night's zenith (:func:`matched_reference`), never the
   night itself. It answers "how bright is this cell when seen like this"
   and so takes the view angle out without a control. It needs a
   reference night at a similar angle, so fewer cells get a figure.
2. **Each night, each cell**: the ratio of its value to its reference,
   classed. A cell with no high-quality value that night says nothing.
3. **Each night, each unit**: over its cells seen that night, the summed
   light over the summed reference (like for like), the share of the unit's
   reference light that was seen (coverage), and the share of seen cells
   under half their reference. Below ``MIN_COVERAGE`` the night is
   UNCERTAIN, never "dark" and never "normal".

What this cannot say: why a cell is dim. A cell's value moves from night to
night with view angle, thin cloud the flag missed, and moonlight correction;
a short reference makes that worse. The figures say how the light compared
with the nights just before, not that power was out. Electricity figures
quoted for an event are leads from news reports and are not used here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import conventions as c
from ntl import export, qa
from ntl.download import parse_granule_name
from ntl.read import read_grid, read_raw, read_scaled
from ntl.stack import TileStack, cache_path, load
from ntl.tiles import parse_tile

log = logging.getLogger("ntl.events")

#: Daily product used for events.
DAILY_PRODUCT: Final[str] = "VNP46A2"
#: Layer of days since the last high-quality retrieval.
A2_LATEST: Final[str] = "Latest_High_Quality_Retrieval"
#: High-quality reference nights a cell needs, unless the event says otherwise. [P]
MIN_REFERENCE_NIGHTS: Final[int] = 3
#: Share of a unit's reference light that must be seen for a night to be read. [P]
MIN_COVERAGE: Final[float] = 0.5
#: A cell under this share of its reference counts as "down" that night. [P]
DOWN_RATIO: Final[float] = 0.5
#: Ratio classes of a cell-night: code 0 no reference, 1 no retrieval, 2 poor
#: quality, then one class per interval of these ratios (value over reference). [P]
RATIO_BREAKS: Final[tuple[float, ...]] = (0.5, 0.8, 1.25)
#: Staleness classes from days since the last high-quality retrieval: 0 for
#: the same night, then one per interval; the last also holds "never". [P]
STALE_BREAKS: Final[tuple[int, ...]] = (1, 3, 6)
#: Nights after which the satellite sees a place from the same angle again. Measured on the 32
#: VNP46A1 files of h29v09 (25 July to 25 August 2018, ``Sensor_Zenith`` over Mataram): nights 16
#: apart differ by a median 0.14 and at most 2.2 degrees; nights 11 apart by a median 6.6 and up
#: to 12.6 (``temp/view-repeat-draft.py``, 2026-11-23). Across years: 14 nights of March 2026 over Denpasar
#: against September 2018, 171 and 172 cycles earlier, differ by a median 0.2 and at most 0.5 degrees
#: (``temp/view-repeat-years-draft.py``). Checked on tile h29v09 only.
VIEW_REPEAT_NIGHTS: Final[int] = 16
#: Daily product that carries the view angles, and its view zenith layer (int16, hundredths of a degree,
#: fill -32768; signed by the side of the swath, so the absolute value is used: read from a file, 2026-11-23).
ANGLE_PRODUCT: Final[str] = "VNP46A1"
A1_SENSOR_ZENITH: Final[str] = "Sensor_Zenith"
A1_ANGLE_SCALE: Final[float] = 0.01
A1_ANGLE_FILL: Final[int] = -32768
#: Two nights count as seen alike when their view zeniths differ by at most this, degrees. [P]
ZENITH_TOLERANCE: Final[float] = 10.0
#: Unit-night states.
UNCERTAIN, DOWN, SAME, UP = 0, 1, 2, 3
#: A unit-night is DOWN under this ratio and UP above the second. [P]
UNIT_DOWN, UNIT_UP = 0.8, 1.25


@dataclass(frozen=True)
class Event:
    """One case study: where, when, what to compare with, and the shocks to mark.

    Attributes
    ----------
    key : str
        Folder name of the event's files.
    title : str
    tile : str
        Tile holding the box.
    bbox : tuple of float
        West, south, east, north, degrees: wide enough to hold the control.
    first, last : datetime.date
        First and last FILE date (night) of the window, inclusive.
    reference_last : datetime.date
        Last file date of the reference nights; they start at ``first``.
    marks : tuple of (datetime.date, str)
        File date of the first night after each shock, and a label.
    focus : tuple of int
        District codes of the affected area.
    control : tuple of int
        Province codes of the control area.
    epicentre : tuple of float
        Longitude and latitude of the main shock, degrees.
    min_reference_nights : int
        High-quality reference nights a cell needs. [P]
    after : tuple of datetime.date
        First and last file date of the "after" nights used to ask whether
        a cell went dark or a dark cell lit up.
    story : tuple of datetime.date
        Three nights the page sets side by side: before, during, after.
    reference_nights : tuple of datetime.date
        The reference nights, named one by one. If empty, they are every
        night from ``first`` to ``reference_last``. Needed where the
        nights before the event are under cloud (Nyepi falls in the wet
        season) and the clear nights come after it.
    quality : tuple of int
        ``Mandatory_Quality_Flag`` values accepted. Default: 0 only. Adding
        1 admits retrievals the product calls poor quality ("outlier,
        potential cloud contamination"): on a night when a whole island
        dims, most of its cells are flagged that way. Say so wherever the
        result is shown.
    control_districts : tuple of int
        District codes added to the control area.
    """

    key: str
    title: str
    tile: str
    bbox: tuple[float, float, float, float]
    first: dt.date
    last: dt.date
    reference_last: dt.date
    marks: tuple[tuple[dt.date, str], ...]
    focus: tuple[int, ...] = ()
    control: tuple[int, ...] = ()
    epicentre: tuple[float, float] = (0.0, 0.0)
    min_reference_nights: int = MIN_REFERENCE_NIGHTS
    after: tuple[dt.date, dt.date] | None = None
    story: tuple[dt.date, ...] = ()
    reference_nights: tuple[dt.date, ...] = ()
    quality: tuple[int, ...] = (c.MQF_HIGH_QUALITY,)
    control_districts: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        # Refuse an event whose dates do not fit its own window: ValueError naming the field at fault.
        if self.first > self.last:
            raise ValueError(f"{self.key}: first {self.first} is after last {self.last}")
        if not self.quality:
            raise ValueError(f"{self.key}: quality names no flag")
        west, south, east, north = self.bbox
        if not (west < east and south < north):
            raise ValueError(f"{self.key}: bbox {self.bbox} is not west, south, east, north")
        named = {"marks": [d for d, _ in self.marks], "story": list(self.story), "reference_nights": list(self.reference_nights),
                 "after": list(self.after or ()), "reference_last": [] if self.reference_nights else [self.reference_last]}
        for field, days in named.items():
            for day in days:
                if not self.first <= day <= self.last:
                    raise ValueError(f"{self.key}: {field} has {day}, outside {self.first} to {self.last}")


#: Times and magnitudes are from the USGS catalogue (``temp/events-shortlist.md``); the mainshock's
#: epicentre is USGS event us1000g3ub, 116.4375 E, 8.2581 S, 34 km deep (FDSN event service, 2026-11-23).
EVENTS: Final[dict[str, Event]] = {
    "lombok2018": Event(
        key="lombok2018", title="Lombok earthquakes, July and August 2018", tile="h29v09",
        bbox=(114.4, -9.1, 117.2, -8.0), first=dt.date(2018, 7, 25), last=dt.date(2018, 8, 25),
        reference_last=dt.date(2018, 8, 4),
        marks=(
            (dt.date(2018, 7, 29), "M 6.4, 29 July 06:47 local"),
            (dt.date(2018, 8, 5), "M 6.9, 5 August 19:46 local"),
            (dt.date(2018, 8, 19), "M 6.9, 19 August 22:56 local"),
        ),
        focus=(5201, 5202, 5203, 5208, 5271), control=(51,), epicentre=(116.4375, -8.2581),
        after=(dt.date(2018, 8, 7), dt.date(2018, 8, 18)),
        story=(dt.date(2018, 8, 14), dt.date(2018, 8, 19), dt.date(2018, 8, 20)),
    ),
    # Palu: USGS event us1000h3p4, M 7.5, 28 September 2018 10:02 UTC (18:02 local), 119.8462 E, 0.2559 S, 20 km deep
    # (FDSN event service, queried 2026-11-23). One tile only (h29v09): Palu city, Sigi and the parts of Donggala
    # south of the equator and west of 120 E. Controls in the same tile, far from the shaking: Balikpapan,
    # Samarinda and Makassar.
    "palu2018": Event(
        key="palu2018", title="Palu earthquake and tsunami, 28 September 2018", tile="h29v09",
        bbox=(116.5, -5.5, 120.0, 0.0), first=dt.date(2018, 9, 12), last=dt.date(2018, 10, 31),
        reference_last=dt.date(2018, 9, 27),
        marks=((dt.date(2018, 9, 28), "M 7.5, 28 September 18:02 local"),),
        focus=(7271, 7210, 7203), control=(), control_districts=(6471, 6472, 7371), epicentre=(119.8462, -0.2559), min_reference_nights=2,
        after=(dt.date(2018, 10, 15), dt.date(2018, 10, 31)),
        story=(dt.date(2018, 9, 27), dt.date(2018, 9, 28), dt.date(2018, 10, 28)),
    ),
    # Mudik 2019: Eid al-Fitr fell on Wednesday 5 June 2019 (government announcement of 3 June 2019,
    # setkab.go.id, "Pemerintah Tetapkan 1 Syawal 1440 Hijriah Jatuh pada Hari Rabu, 5 Juni 2019").
    # The "focus" is where people leave (Jakarta and the cities around it); the "control" is where many of
    # them go (districts of eastern West Java and western Central Java in the same tile; my choice, not a
    # survey). Here the control is not an untouched neighbour but the other end of the journey. Measured
    # 2026-11-23: the two do NOT share a sky or a view angle closely enough for the division to mean much
    # (``temp/status-design.md``, "Fourth case study"), so the page does not use the adjusted figures.
    # The reference nights are 15 to 27 May: inside Ramadan, before the travel peak. Ramadan has its own
    # night-time habits, so the reference is "late Ramadan", not an ordinary month.
    "mudik2019": Event(
        key="mudik2019", title="Mudik, Eid al-Fitr 2019", tile="h28v09",
        bbox=(106.3, -8.0, 110.0, -5.8), first=dt.date(2019, 5, 15), last=dt.date(2019, 6, 25),
        reference_last=dt.date(2019, 5, 27),
        marks=((dt.date(2019, 6, 5), "Eid al-Fitr, 5 June"),),
        focus=(3171, 3172, 3173, 3174, 3175, 3275, 3276, 3671, 3674),
        control=(), control_districts=(3205, 3206, 3207, 3208, 3210, 3301, 3302, 3303, 3304, 3305, 3306, 3307, 3326, 3327, 3328, 3329),
        epicentre=(106.8272, -6.1754), min_reference_nights=3,
        story=(dt.date(2019, 5, 22), dt.date(2019, 6, 5), dt.date(2019, 6, 19)),
    ),
    # Nyepi 2026: 19 March (Wikipedia's table of dates, temp/events-shortlist.md). The nights before it are
    # under cloud, so the reference is the two clear nights ten days later; retrievals flagged poor quality
    # are admitted, because on Nyepi night 56% of Bali's cells carry that flag and only 5% the high one.
    # Nyepi 2024 and 2025 cannot be done: no retrieval over Bali on either night (temp/nyepi-seen.log).
    "nyepi2026": Event(
        key="nyepi2026", title="Nyepi, 19 March 2026", tile="h29v09",
        bbox=(114.0, -9.0, 116.8, -8.0), first=dt.date(2026, 3, 6), last=dt.date(2026, 3, 31),
        reference_last=dt.date(2026, 3, 30), reference_nights=(dt.date(2026, 3, 29), dt.date(2026, 3, 30)),
        marks=((dt.date(2026, 3, 19), "Nyepi night"),),
        focus=(5101, 5102, 5103, 5104, 5105, 5106, 5107, 5108, 5171), control=(52,), control_districts=(3510,),
        epicentre=(115.2167, -8.65), min_reference_nights=1, quality=(c.MQF_HIGH_QUALITY, c.MQF_POOR_OUTLIER),
        story=(dt.date(2026, 3, 19), dt.date(2026, 3, 20), dt.date(2026, 3, 29)),
    ),
}

#: Share of the control's referenced cells that must be seen for its median to be used. [P]
MIN_CONTROL_SEEN: Final[float] = 0.3
#: Distance bands from the epicentre, km. [P]
DISTANCE_BANDS: Final[tuple[tuple[int, int], ...]] = ((0, 15), (15, 30), (30, 45), (45, 70))
#: Cells seen that a band or the focus needs for a median to be given. [P]
MIN_BAND_CELLS: Final[int] = 5
#: Length of one degree of a great circle, km (as ``ntl.export``).
KM_PER_DEGREE: Final[float] = export.KM_PER_DEGREE


def distance_km(lon: ArrayLike, lat: ArrayLike, point: tuple[float, float]) -> NDArray[np.float64]:
    """Distance of each cell from a point, km, on a flat map scaled by the cosine of the point's latitude.

    Good to well under a kilometre over the tens of kilometres used here.
    """
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    return KM_PER_DEGREE * np.hypot((lon - point[0]) * np.cos(np.radians(point[1])), lat - point[1])


def light_ratio(usable: ArrayLike, reference: ArrayLike, mask: ArrayLike, min_cells: int = MIN_BAND_CELLS) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Each night's light of a group of cells against their reference, like for like.

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    reference : array_like of float, shape ``(N,)``
        Each cell's reference radiance; NaN for a cell without one (never counted).
    mask : array_like of bool, shape ``(N,)``
        The group.
    min_cells : int
        Cells that must be seen for a night to get a figure.

    Returns
    -------
    ndarray of float64, shape ``(D,)``
        Summed radiance of the cells seen over the summed reference of the
        same cells; NaN on a night with too few cells or a zero reference sum.
    ndarray of int64, shape ``(D,)``
        Cells seen each night.
    """
    usable = np.asarray(usable, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool) & np.isfinite(reference)
    block = usable[:, mask]
    seen = np.isfinite(block)
    count = seen.sum(axis=1)
    ref_seen = np.where(seen, reference[mask][None, :], 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where((count >= min_cells) & (ref_seen > 0), np.where(seen, block, 0.0).sum(axis=1) / ref_seen, np.nan)
    return ratio, count.astype(np.int64)


def same_geometry(usable: ArrayLike, mask: ArrayLike, lag: int = VIEW_REPEAT_NIGHTS, min_cells: int = MIN_BAND_CELLS) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Each night's light against the night ``lag`` nights before, over the cells seen on both.

    With ``lag`` the view-angle repeat, both nights are seen from the same
    angle, so the ratio is free of it. It is not free of anything else that
    differs between two single nights (thin cloud, the moonlight correction).

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    mask : array_like of bool, shape ``(N,)``
    lag : int
        Nights between the two; at least 1.
    min_cells : int
        Cells that must be seen on both nights.

    Returns
    -------
    ndarray of float64, shape ``(D,)``
        Summed radiance on the night over the summed radiance ``lag`` nights
        before, same cells; NaN for the first ``lag`` nights, with too few
        shared cells, or when the earlier sum is zero.
    ndarray of int64, shape ``(D,)``
        Cells seen on both nights.

    Raises
    ------
    ValueError
        If ``lag`` is under 1.
    """
    if lag < 1:
        raise ValueError(f"lag must be at least 1, got {lag}")
    block = np.asarray(usable, dtype=np.float64)[:, np.asarray(mask, dtype=bool)]
    ratio = np.full(block.shape[0], np.nan)
    count = np.zeros(block.shape[0], dtype=np.int64)
    for k in range(lag, block.shape[0]):
        both = np.isfinite(block[k]) & np.isfinite(block[k - lag])
        count[k] = int(both.sum())
        earlier = float(block[k - lag][both].sum())
        if count[k] >= min_cells and earlier > 0:
            ratio[k] = float(block[k][both].sum()) / earlier
    return ratio, count


def matched_reference(usable: ArrayLike, zenith: ArrayLike, reference_nights: ArrayLike, tolerance: float = ZENITH_TOLERANCE,
                      min_nights: int = 1) -> tuple[NDArray[np.float32], NDArray[np.uint8]]:
    """A reference for every night and cell from the reference nights seen from a similar angle.

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    zenith : array_like of float, shape ``(D, N)``
        View zenith of each night at each cell, degrees; NaN where unknown.
    reference_nights : array_like of bool, shape ``(D,)``
    tolerance : float
        Largest difference in view zenith, degrees, for a reference night to count.
    min_nights : int
        Reference nights a cell needs at a similar angle.

    Returns
    -------
    ndarray of float32, shape ``(D, N)``
        For night ``k`` and each cell, the median of the cell's usable
        values on the reference nights other than ``k`` whose zenith is
        within ``tolerance`` of the zenith on ``k``; NaN with too few such
        nights, an unknown zenith, or a median of zero.
    ndarray of uint8, shape ``(D, N)``
        How many reference nights went into each.

    Raises
    ------
    ValueError
        If the shapes do not agree, no night is a reference night, or the tolerance is negative.
    """
    usable = np.asarray(usable, dtype=np.float64)
    zenith = np.asarray(zenith, dtype=np.float64)
    reference_nights = np.asarray(reference_nights, dtype=bool)
    if usable.ndim != 2 or zenith.shape != usable.shape or reference_nights.shape != (usable.shape[0],):
        raise ValueError(f"shapes do not agree: usable {usable.shape}, zenith {zenith.shape}, reference nights {reference_nights.shape}")
    if not reference_nights.any():
        raise ValueError("no reference night")
    if tolerance < 0:
        raise ValueError(f"tolerance must not be negative, got {tolerance}")
    reference = np.full(usable.shape, np.nan, dtype=np.float32)
    used = np.zeros(usable.shape, dtype=np.uint8)
    for k in range(usable.shape[0]):
        others = reference_nights.copy()
        others[k] = False                      # a night is never its own reference
        if not others.any():
            continue
        block = usable[others]
        with np.errstate(invalid="ignore"):
            alike = np.isfinite(block) & (np.abs(zenith[others] - zenith[k][None, :]) <= tolerance)
        count = alike.sum(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            median = np.nanmedian(np.where(alike, block, np.nan), axis=0)
        with np.errstate(invalid="ignore"):
            reference[k] = np.where((count >= min_nights) & (median > 0), median, np.nan)
        used[k] = np.minimum(count, 255)
    return reference, used


def nightly_light(usable: ArrayLike, reference: ArrayLike, mask: ArrayLike, min_cells: int = MIN_BAND_CELLS) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """As :func:`light_ratio`, with a reference that differs by night.

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
        Radiance, nW cm-2 sr-1; NaN where not seen.
    reference : array_like of float, shape ``(D, N)``
        From :func:`matched_reference`; NaN where a cell has none that night.
    mask : array_like of bool, shape ``(N,)``
    min_cells : int
        Cells that must be seen and have a reference for a night to get a figure.

    Returns
    -------
    ndarray of float64, shape ``(D,)``
        Summed radiance over the summed reference, over the cells with both; NaN with too few.
    ndarray of int64, shape ``(D,)``
        Cells counted each night.
    """
    mask = np.asarray(mask, dtype=bool)
    block = np.asarray(usable, dtype=np.float64)[:, mask]
    ref = np.asarray(reference, dtype=np.float64)[:, mask]
    both = np.isfinite(block) & np.isfinite(ref)
    count = both.sum(axis=1)
    ref_sum = np.where(both, ref, 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where((count >= min_cells) & (ref_sum > 0), np.where(both, block, 0.0).sum(axis=1) / ref_sum, np.nan)
    return ratio, count.astype(np.int64)


def control_factor(ratio: ArrayLike, control: ArrayLike, min_seen: float = MIN_CONTROL_SEEN) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """What the control area did each night: the median ratio of its cells.

    Kept for the record in ``meta.json``; the adjusted figures use the
    control's summed light (:func:`light_ratio`) since the 2026-11-23 review.

    Parameters
    ----------
    ratio : array_like of float, shape ``(D, N)``
        Each cell's usable radiance over its reference; NaN where not seen
        or without a reference.
    control : array_like of bool, shape ``(N,)``
        True for the control's cells.
    min_seen : float
        Share of the control's referenced cells that must be seen.

    Returns
    -------
    ndarray of float64, shape ``(D,)``
        The control's median ratio; NaN on nights when too few of its cells
        were seen.
    ndarray of float64, shape ``(D,)``
        The share of the control's referenced cells seen each night.

    Raises
    ------
    ValueError
        If no control cell has a reference.
    """
    ratio = np.asarray(ratio, dtype=np.float64)
    control = np.asarray(control, dtype=bool)
    block = ratio[:, control]
    has_reference = np.isfinite(block).any(axis=0)
    if not has_reference.any():
        raise ValueError("no control cell has a reference")
    block = block[:, has_reference]
    seen = np.isfinite(block).mean(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(block, axis=1)
    return np.where(seen >= min_seen, median, np.nan), seen


#: A cell counts as back when its control-adjusted ratio reaches this. [P]
RECOVERED_RATIO: Final[float] = 0.8
#: Codes of :func:`recovery_nights` for cells without a count.
NEVER_BACK, NOT_HIT, NOT_JUDGED = 253, 254, 255


def recovery_nights(adjusted: ArrayLike, start: int, back: float = RECOVERED_RATIO, hit: float = DOWN_RATIO) -> NDArray[np.uint8]:
    """Nights from an event until each cell that dimmed was first seen back.

    Parameters
    ----------
    adjusted : array_like of float, shape ``(D, N)``
        Each cell's control-adjusted ratio; NaN where the cell was not
        seen, has no reference, or the night has no usable control.
    start : int
        Position of the first night after the event.
    back : float
        A cell is back on the first night its ratio is at least this.
    hit : float
        A cell counts as hit if its first seen night from ``start`` on is
        under this.

    Returns
    -------
    ndarray of uint8, shape ``(N,)``
        For a cell that was hit: the number of nights from ``start`` to the
        first night it was seen back (0 would mean the first night itself,
        which cannot happen for a hit cell). ``NEVER_BACK`` (253) if it was
        never seen back by the last night; ``NOT_HIT`` (254) if its first
        seen night was not under ``hit``; ``NOT_JUDGED`` (255) if it was
        never seen from ``start`` on.

    Notes
    -----
    The count is an upper bound on how long the cell was dim: on a night
    under cloud, or without a control, the cell says nothing, so it may
    have been back earlier than the night it was first SEEN back.
    """
    adjusted = np.asarray(adjusted, dtype=np.float64)
    if adjusted.ndim != 2 or not 0 <= start < adjusted.shape[0]:
        raise ValueError(f"adjusted has shape {adjusted.shape}; start {start} is not one of its nights")
    after = adjusted[start:]
    seen = np.isfinite(after)
    out = np.full(adjusted.shape[1], NOT_JUDGED, dtype=np.uint8)
    any_seen = seen.any(axis=0)
    first = np.argmax(seen, axis=0)
    first_value = after[first, np.arange(after.shape[1])]
    with np.errstate(invalid="ignore"):
        was_hit = any_seen & (first_value < hit)
        is_back = seen & (after >= back)
    out[any_seen & ~was_hit] = NOT_HIT
    back_night = np.where(is_back.any(axis=0), np.argmax(is_back, axis=0), -1)
    out[was_hit] = np.where(back_night[was_hit] >= 0, np.minimum(back_night[was_hit], 252), NEVER_BACK).astype(np.uint8)
    return out


def dark_and_lit(before: ArrayLike, after: ArrayLike, min_nights: int = 3, dark_max: float = 0.5, lit_min: float = c.LIT_MIN_RADIANCE) -> tuple[NDArray[np.bool_], NDArray[np.bool_], NDArray[np.bool_], NDArray[np.bool_]]:
    """Which cells were dark or lit before, and which of those changed sides after.

    Parameters
    ----------
    before, after : array_like of float, shape ``(nights, ...)``
        High-quality radiance on the nights before and after; NaN where not seen.
    min_nights : int
        Nights a cell needs in each period.
    dark_max, lit_min : float
        A cell is dark when its median is under ``dark_max`` and lit when
        it is at least ``lit_min``. [P]

    Returns
    -------
    tuple of four ndarrays of bool
        Dark before; of those, lit after (light where there was none); lit
        before; of those, dark after (went dark).
    """
    before = np.asarray(before, dtype=np.float64)
    after = np.asarray(after, dtype=np.float64)
    judged = (np.isfinite(before).sum(axis=0) >= min_nights) & (np.isfinite(after).sum(axis=0) >= min_nights)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        was, now = np.nanmedian(before, axis=0), np.nanmedian(after, axis=0)
    with np.errstate(invalid="ignore"):
        dark_before, lit_before = judged & (was < dark_max), judged & (was >= lit_min)
        return dark_before, dark_before & (now >= lit_min), lit_before, lit_before & (now < dark_max)


def daily_files(root: str | Path, tile: str, product: str = DAILY_PRODUCT) -> dict[dt.date, Path]:
    """The daily files on disk for a tile, keyed by file date; the latest production of a date wins.

    Raises
    ------
    FileNotFoundError
        If none is found.
    """
    parse_tile(tile)
    found: dict[dt.date, Path] = {}
    for path in sorted(Path(root).glob(f"{c.BLACK_MARBLE_DIR}/{product}/*/*/{product}.*.{tile}.*.h5")):
        parsed = parse_granule_name(path.name)
        if parsed is not None and parsed[0] == product:
            found[parsed[1]] = path
    if not found:
        raise FileNotFoundError(f"no {product} file for tile {tile} under {root}")
    return found


class EventStack(NamedTuple):
    """Nightly values of the lit cells inside an event's box. ``D`` nights by ``N`` cells.

    Attributes
    ----------
    dates : tuple of datetime.date
        File date of each night, consecutive; a night with no file is a row
        of "no retrieval".
    lon, lat : ndarray of float64, shape ``(N,)``
        Cell centres.
    district, subdistrict : ndarray of int64, shape ``(N,)``
        Unit codes of each cell (0: held by the level above).
    value : ndarray of float32, shape ``(D, N)``
        Radiance, nW cm-2 sr-1; NaN where the file has fill or there is no file.
    quality : ndarray of uint8, shape ``(D, N)``
        ``Mandatory_Quality_Flag`` as stored; 255 where no retrieval.
    stale : ndarray of uint8, shape ``(D, N)``
        Days since the last high-quality retrieval as stored; 255 where none.
    """

    dates: tuple[dt.date, ...]
    lon: NDArray[np.float64]
    lat: NDArray[np.float64]
    district: NDArray[np.int64]
    subdistrict: NDArray[np.int64]
    value: NDArray[np.float32]
    quality: NDArray[np.uint8]
    stale: NDArray[np.uint8]


def build_event_stack(root: str | Path, event: Event, domain: TileStack) -> EventStack:
    """Read an event's nights for the status-domain cells inside its box.

    Parameters
    ----------
    root : str or Path
        Data root holding the daily files.
    event : Event
    domain : TileStack
        The monthly stack of the event's tile: it supplies which cells are
        lit and which unit each belongs to.

    Returns
    -------
    EventStack

    Raises
    ------
    FileNotFoundError
        If the tile has no daily file, or none inside the event's window.
    ValueError
        If no domain cell lies inside the box.
    """
    west, south, east, north = event.bbox
    inside = (domain.lon >= west) & (domain.lon < east) & (domain.lat > south) & (domain.lat <= north)
    if not inside.any():
        raise ValueError(f"no lit cell of {domain.tile} inside {event.bbox}")
    lon, lat = domain.lon[inside], domain.lat[inside]
    files = daily_files(root, event.tile)
    days = (event.last - event.first).days + 1
    dates = tuple(event.first + dt.timedelta(days=k) for k in range(days))
    present = [d for d in dates if d in files]
    if not present:
        raise FileNotFoundError(f"no daily file of {event.tile} between {event.first} and {event.last} under {root}")
    grid = read_grid(files[present[0]])
    window = grid.window(west, south, east, north)
    sub = grid.subgrid(window)
    left, _, _, top = sub.bounds
    cols = np.floor((lon - left) / c.CELL_SIZE_DEG).astype(np.int64)
    rows = np.floor((top - lat) / c.CELL_SIZE_DEG).astype(np.int64)
    value = np.full((days, lon.size), np.nan, dtype=np.float32)
    quality = np.full((days, lon.size), c.MQF_FILL, dtype=np.uint8)
    stale = np.full((days, lon.size), 255, dtype=np.uint8)
    for k, date in enumerate(dates):
        if date not in files:
            log.warning("%s: no file for %s", event.key, date)
            continue
        try:
            night = (read_scaled(files[date], c.A2_NTL, window)[rows, cols], read_raw(files[date], c.A2_QUALITY, window)[rows, cols],
                     read_raw(files[date], A2_LATEST, window)[rows, cols])
        except (OSError, KeyError) as exc:
            log.warning("%s: %s cannot be read (%s); the night is left as not seen", event.key, files[date], exc)
            continue
        value[k], quality[k], stale[k] = night
    return EventStack(dates=dates, lon=lon, lat=lat, district=domain.district[inside], subdistrict=domain.subdistrict[inside],
                      value=value, quality=quality, stale=stale)


def view_zenith(root: str | Path, event: Event, lon: ArrayLike, lat: ArrayLike, repeat: int = VIEW_REPEAT_NIGHTS) -> tuple[NDArray[np.float32], NDArray[np.int16]]:
    """View zenith of every night of an event at the given cells, from the VNP46A1 files on disk.

    A night without its own file takes the zenith of the nearest night a
    whole number of repeat cycles away (``VIEW_REPEAT_NIGHTS``), on the
    measured ground that the angle repeats then.

    Parameters
    ----------
    root : str or Path
        Data root holding ``VNP46A1`` files of the event's tile.
    event : Event
    lon, lat : array_like of float, shape ``(N,)``
        Cell centres, degrees, inside the event's box.
    repeat : int
        Nights after which the view repeats.

    Returns
    -------
    ndarray of float32, shape ``(D, N)``
        Absolute view zenith, degrees; NaN where no file serves the night or the layer holds fill.
    ndarray of int16, shape ``(D,)``
        Cycles between each night and the file it was read from: 0 its own
        file, negative an earlier one; -32768 where none serves.

    Raises
    ------
    FileNotFoundError
        If the tile has no VNP46A1 file.
    """
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    files = daily_files(root, event.tile, product=ANGLE_PRODUCT)
    days = (event.last - event.first).days + 1
    zenith = np.full((days, lon.size), np.nan, dtype=np.float32)
    cycles = np.full(days, -32768, dtype=np.int16)
    grid = read_grid(next(iter(files.values())))
    window = grid.window(*event.bbox)
    left, _, _, top = grid.subgrid(window).bounds
    cols = np.floor((lon - left) / c.CELL_SIZE_DEG).astype(np.int64)
    rows = np.floor((top - lat) / c.CELL_SIZE_DEG).astype(np.int64)
    read: dict[dt.date, NDArray[np.float32] | None] = {}
    for k in range(days):
        date = event.first + dt.timedelta(days=k)
        served = sorted((d for d in files if (d - date).days % repeat == 0), key=lambda d: abs((d - date).days))
        for source in served:
            if source not in read:
                try:
                    raw = read_raw(files[source], A1_SENSOR_ZENITH, window)[rows, cols]
                    read[source] = np.where(raw == A1_ANGLE_FILL, np.nan, np.abs(raw.astype(np.float32)) * A1_ANGLE_SCALE).astype(np.float32)
                except (OSError, KeyError) as exc:
                    log.warning("%s: %s cannot be read (%s)", event.key, files[source], exc)
                    read[source] = None
            if read[source] is not None:
                zenith[k] = read[source]
                cycles[k] = (source - date).days // repeat
                break
    return zenith, cycles


def read_window(root: str | Path, event: Event) -> tuple[NDArray[np.float32], NDArray[np.float64], NDArray[np.float64]]:
    """Usable radiance of EVERY cell of the event's box, lit or not, night by night.

    Returns
    -------
    ndarray of float32, shape ``(D, rows, columns)``
        nW cm-2 sr-1; NaN where the quality flag is not one the event admits
        (``Event.quality``), where there is no file, or where the file cannot be read.
    ndarray of float64, shape ``(rows, columns)``
        Longitude of each cell centre.
    ndarray of float64, shape ``(rows, columns)``
        Latitude of each cell centre.
    """
    files = daily_files(root, event.tile)
    days = (event.last - event.first).days + 1
    dates = [event.first + dt.timedelta(days=k) for k in range(days)]
    present = [d for d in dates if d in files]
    if not present:
        raise FileNotFoundError(f"no daily file of {event.tile} between {event.first} and {event.last} under {root}")
    grid = read_grid(files[present[0]])
    window = grid.window(*event.bbox)
    sub = grid.subgrid(window)
    cube = np.full((days, *sub.shape), np.nan, dtype=np.float32)
    for k, date in enumerate(dates):
        if date in files:
            try:
                good = np.isin(read_raw(files[date], c.A2_QUALITY, window), event.quality)
                cube[k] = np.where(good, read_scaled(files[date], c.A2_NTL, window), np.nan)
            except (OSError, KeyError) as exc:
                log.warning("%s: %s cannot be read (%s); the night is left as not seen", event.key, files[date], exc)
    lons, lats = sub.centres()
    lon, lat = np.meshgrid(lons, lats)
    return cube, lon, lat


def usable_values(value: ArrayLike, quality: ArrayLike, allowed: Sequence[int] = (c.MQF_HIGH_QUALITY,)) -> NDArray[np.float64]:
    """Radiance where the retrieval carries an accepted quality flag (high quality only by default), NaN elsewhere."""
    value = np.asarray(value, dtype=np.float64)
    return np.where(qa.usable(np.asarray(quality), frozenset(allowed)) & np.isfinite(value), value, np.nan)


def cell_reference(usable: ArrayLike, nights: ArrayLike, min_nights: int = MIN_REFERENCE_NIGHTS) -> NDArray[np.float64]:
    """Each cell's reference radiance: the median of its usable reference nights.

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
        From :func:`usable_values`.
    nights : array_like of bool, shape ``(D,)``
        True for the reference nights.
    min_nights : int
        Usable reference nights a cell needs.

    Returns
    -------
    ndarray of float64, shape ``(N,)``
        nW cm-2 sr-1; NaN where the cell has too few usable reference
        nights, or its median is not above zero (a ratio to zero means
        nothing).

    Raises
    ------
    ValueError
        If the shapes disagree or no night is a reference night.
    """
    usable = np.asarray(usable, dtype=np.float64)
    nights = np.asarray(nights, dtype=bool)
    if usable.ndim != 2 or nights.shape != (usable.shape[0],):
        raise ValueError(f"usable has shape {usable.shape}, nights {nights.shape}")
    if not nights.any():
        raise ValueError("no reference night")
    block = usable[nights]
    enough = np.isfinite(block).sum(axis=0) >= min_nights
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(block, axis=0)
    return np.where(enough & (median > 0), median, np.nan)


def ratio_class(value: ArrayLike, quality: ArrayLike, reference: ArrayLike, allowed: Sequence[int] = (c.MQF_HIGH_QUALITY,)) -> NDArray[np.uint8]:
    """Class of each cell-night by its radiance over the cell's reference.

    Returns
    -------
    ndarray of uint8, shape ``(D, N)``
        0 the cell has no reference; 1 no retrieval that night; 2 a
        retrieval of poor quality (not used); 3 under 0.5 of the
        reference; 4 from 0.5 to under 0.8; 5 from 0.8 to under 1.25; 6
        at 1.25 or more.
    """
    quality = np.asarray(quality)
    reference = np.asarray(reference, dtype=np.float64)
    usable = usable_values(value, quality, allowed)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (np.digitize(usable / reference[None, :], RATIO_BREAKS) + 3).astype(np.uint8)
    out[~np.isfinite(usable)] = 2
    out[~qa.observed(quality)] = 1
    out[:, ~np.isfinite(reference)] = 0
    return out


def stale_class(stale: ArrayLike) -> NDArray[np.uint8]:
    """Class of each cell-night by days since its last high-quality retrieval: 0 the same night, 1 for 1 to 2, 2 for 3 to 5, 3 for 6 or more or never."""
    stale = np.asarray(stale)
    return np.where(stale == 255, len(STALE_BREAKS), np.digitize(stale, STALE_BREAKS)).astype(np.uint8)


class UnitNights(NamedTuple):
    """Nightly figures per unit. ``D`` nights by ``U`` units.

    Attributes
    ----------
    codes : ndarray of int64, shape ``(U,)``
    cells : ndarray of int64, shape ``(U,)``
        Cells of the unit that have a reference.
    ratio : ndarray of float64, shape ``(D, U)``
        Summed light over summed reference, on the cells seen that night;
        NaN where none was seen.
    coverage : ndarray of float64, shape ``(D, U)``
        Share of the unit's reference light in cells seen that night.
    down : ndarray of float64, shape ``(D, U)``
        Share of the seen cells under ``DOWN_RATIO`` of their reference;
        NaN where none was seen.
    state : ndarray of uint8, shape ``(D, U)``
        ``UNCERTAIN`` where coverage is under ``MIN_COVERAGE``; otherwise
        ``DOWN``, ``SAME`` or ``UP`` by ``ratio``.
    """

    codes: NDArray[np.int64]
    cells: NDArray[np.int64]
    ratio: NDArray[np.float64]
    coverage: NDArray[np.float64]
    down: NDArray[np.float64]
    state: NDArray[np.uint8]


def unit_nights(usable: ArrayLike, reference: ArrayLike, unit_codes: ArrayLike) -> UnitNights:
    """Sum cells into units for every night.

    Parameters
    ----------
    usable : array_like of float, shape ``(D, N)``
    reference : array_like of float, shape ``(N,)``
    unit_codes : array_like of int, shape ``(N,)``
        Unit of each cell; 0 for none. Cells without a reference are left out.

    Returns
    -------
    UnitNights
    """
    usable = np.asarray(usable, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    codes_all = np.asarray(unit_codes, dtype=np.int64)
    keep = np.isfinite(reference) & (codes_all != c.NO_UNIT)
    codes, position = np.unique(codes_all[keep], return_inverse=True)
    ref, values = reference[keep], usable[:, keep]
    seen = np.isfinite(values)
    units, nights = codes.size, usable.shape[0]

    def total(weights: NDArray[np.float64]) -> NDArray[np.float64]:
        out = np.zeros((nights, units))
        for k in range(nights):
            out[k] = np.bincount(position, weights=weights[k], minlength=units)
        return out

    ref_all = np.bincount(position, weights=ref, minlength=units)
    ref_seen = total(np.where(seen, ref[None, :], 0.0))
    light = total(np.where(seen, values, 0.0))
    count = total(seen.astype(np.float64))
    with np.errstate(invalid="ignore"):
        low = total((seen & (values < DOWN_RATIO * ref[None, :])).astype(np.float64))
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(ref_seen > 0, light / ref_seen, np.nan)
        coverage = ref_seen / ref_all[None, :]
        down = np.where(count > 0, low / count, np.nan)
    state = np.full((nights, units), SAME, dtype=np.uint8)
    with np.errstate(invalid="ignore"):
        state[ratio < UNIT_DOWN] = DOWN
        state[ratio >= UNIT_UP] = UP
    state[~(coverage >= MIN_COVERAGE)] = UNCERTAIN
    return UnitNights(codes=codes, cells=np.bincount(position, minlength=units).astype(np.int64), ratio=ratio,
                      coverage=coverage, down=down, state=state)


def export_event(event: Event, stack: EventStack, out: str | Path, window: tuple[NDArray, NDArray, NDArray] | None = None,
                 zenith: tuple[NDArray[np.float32], NDArray[np.int16]] | None = None) -> dict[str, object]:
    """Write an event's files under ``<out>/events/<key>/``.

    ``meta.json``: dates, marks, classes, the reference and control rules,
    and the figures of the story (what the control did each night, the
    focus area raw and adjusted, medians by distance band, cells that went
    dark, dark cells that lit up). ``cells.u32.gz``: cell positions on the
    global grid, ascending. ``cell_info.u8.gz``: two bytes per cell, its
    group (0 other, 1 focus, 2 control) and its distance from the epicentre
    in km (254 for more). ``nights.u8.gz``: one byte per night and cell,
    bits 0 to 2 the ratio class, bits 3 and 4 the staleness class.
    ``adjusted.u8.gz``: one byte per night and cell, the class of the
    control-adjusted ratio, or 7 on a night with no usable control.
    ``recovery.u8.gz``: one byte per cell, :func:`recovery_nights` counted
    from the first night after the last marked event.
    ``units.json``: per level, the nightly ratio, adjusted ratio, coverage,
    down share and state of each unit. ``files.js`` names them all.

    Parameters
    ----------
    event : Event
    stack : EventStack
        From :func:`build_event_stack`.
    out : str or Path
        The site's data folder.
    window : tuple, optional
        From :func:`read_window`: every cell of the box, for the count of
        dark cells that lit up. Without it that figure is left out.
    zenith : tuple, optional
        From :func:`view_zenith` for ``stack.lon`` and ``stack.lat``: adds
        ``story.matched``, the focus and the control against references
        from nights seen from a similar angle. Without it that is left out.

    Returns
    -------
    dict
        The metadata written.
    """
    folder = Path(out) / "events" / event.key
    order = np.argsort(export.cell_index(stack.lon, stack.lat), kind="stable")
    index = export.cell_index(stack.lon, stack.lat)[order]
    lon, lat, district = stack.lon[order], stack.lat[order], stack.district[order]
    usable = usable_values(stack.value, stack.quality, event.quality)[:, order]
    dates = stack.dates
    reference_nights = np.array([(d in event.reference_nights) if event.reference_nights else (d <= event.reference_last) for d in dates])
    reference = cell_reference(usable, reference_nights, event.min_reference_nights)
    has_reference = np.isfinite(reference)
    ratio = usable / reference[None, :]
    focus = np.isin(district, event.focus) & has_reference
    control = (np.isin(district // (c.ADMIN_DIVISOR["province"] // c.ADMIN_DIVISOR["district"]), event.control)
               | np.isin(district, event.control_districts)) & has_reference
    if event.focus and not focus.any():
        raise ValueError(f"{event.key}: no focus cell has a reference (districts {event.focus}, {int(reference_nights.sum())} reference nights)")
    classes = ratio_class(stack.value[:, order], stack.quality[:, order], reference, event.quality)
    packed = (classes | (stale_class(stack.stale[:, order]) << 3)).astype(np.uint8)
    sizes = {
        "cells.u32.gz": export.gz_write(folder / "cells.u32.gz", index.astype("<u4").tobytes()),
        "nights.u8.gz": export.gz_write(folder / "nights.u8.gz", np.ascontiguousarray(packed).tobytes()),
    }

    # ---- the control, and everything measured against it
    story: dict[str, object] = {}
    adjusted = np.full(ratio.shape, np.nan)
    if control.any():
        median_factor, seen = control_factor(ratio, control)
        # the control's summed light over its summed reference: the same statistic as the focus it divides
        factor, _ = light_ratio(usable, reference, control, min_cells=1)
        factor = np.where((seen >= MIN_CONTROL_SEEN) & (factor > 0), factor, np.nan)
        with np.errstate(invalid="ignore"):
            adjusted = ratio / factor[:, None]
        with np.errstate(invalid="ignore"):
            adjusted_class = (np.digitize(adjusted, RATIO_BREAKS) + 3).astype(np.uint8)
        adjusted_class = np.where(classes < 3, classes, adjusted_class)       # no reference, no retrieval, poor quality stay as they are
        adjusted_class[~np.isfinite(factor)] = 7
        sizes["adjusted.u8.gz"] = export.gz_write(folder / "adjusted.u8.gz", np.ascontiguousarray(adjusted_class).tobytes())
        story["control"] = dict(provinces=list(event.control), districts=list(event.control_districts), cells=int(control.sum()), min_seen=MIN_CONTROL_SEEN,
                                rule="summed light of the control's cells seen over their summed reference; used when min_seen of its cells were seen",
                                light=export._nullable(factor, 3), median=export._nullable(median_factor, 3), seen=[round(float(v), 3) for v in seen])

    def nightly(values: NDArray[np.float64], mask: NDArray[np.bool_]) -> dict[str, object]:
        block = values[:, mask]
        count = np.isfinite(block).sum(axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            median = np.where(count >= MIN_BAND_CELLS, np.nanmedian(block, axis=1), np.nan)
        return dict(cells=int(mask.sum()), median=export._nullable(median, 3), seen=count.astype(int).tolist())

    def lights(mask: NDArray[np.bool_]) -> dict[str, object]:
        total, _ = light_ratio(usable, reference, mask)
        return dict(light=export._nullable(total, 3), light_adjusted=export._nullable(total / factor if control.any() else total * np.nan, 3))

    km = distance_km(lon, lat, event.epicentre) if event.focus else np.zeros(lon.size)
    group = np.where(focus, 1, np.where(control, 2, 0)).astype(np.uint8)
    info = np.stack([group, np.clip(np.round(km), 0, 254).astype(np.uint8)], axis=1)
    sizes["cell_info.u8.gz"] = export.gz_write(folder / "cell_info.u8.gz", info.tobytes())
    if event.focus:
        story["focus"] = dict(districts=list(event.focus), raw=nightly(ratio, focus), adjusted=nightly(adjusted, focus))
        bands = []
        for near, far in DISTANCE_BANDS:
            mask = focus & (km >= near) & (km < far)
            bands.append(dict(km=[near, far], adjusted=nightly(adjusted, mask), raw=nightly(ratio, mask), **lights(mask)))
        story["bands"] = bands
        # the same question by how bright a cell usually is: the unit's light summed over the cells seen, over their reference
        edges = [0.0, *np.nanquantile(reference[focus], [0.5, 0.9, 0.99]).tolist(), np.inf]
        names = ["dimmer half", "50th to 90th percentile", "90th to 99th", "brightest 1%"]
        by_brightness = []
        for name, low, high in zip(names, edges[:-1], edges[1:]):
            mask = focus & (reference >= low) & (reference < high)
            block, ref_block = usable[:, mask], reference[mask]
            seen_block = np.isfinite(block)
            ref_seen = np.where(seen_block, ref_block[None, :], 0.0).sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                share = np.where(seen_block.sum(axis=1) >= MIN_BAND_CELLS, np.nansum(block, axis=1) / ref_seen, np.nan)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mean_nw = np.where(seen_block.sum(axis=1) >= MIN_BAND_CELLS, np.nanmean(block, axis=1), np.nan)
            by_brightness.append(dict(name=name, nw=[round(low, 1), None if not np.isfinite(high) else round(high, 1)], cells=int(mask.sum()),
                                      mean_nw=export._nullable(mean_nw, 2), reference_mean_nw=None if ref_block.size == 0 else round(float(ref_block.mean()), 2),
                                      light=export._nullable(share, 3), light_adjusted=export._nullable(share / factor if control.any() else share * np.nan, 3),
                                      seen=seen_block.sum(axis=1).astype(int).tolist()))
        story["brightness"] = by_brightness
        block = usable[:, focus]
        seen_block = np.isfinite(block)
        ref_seen = np.where(seen_block, reference[focus][None, :], 0.0).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            total = np.where(seen_block.sum(axis=1) >= MIN_BAND_CELLS, np.nansum(block, axis=1) / ref_seen, np.nan)
        story["focus"]["light"] = export._nullable(total, 3)
        story["focus"]["light_adjusted"] = export._nullable(total / factor if control.any() else total * np.nan, 3)
        same, shared = same_geometry(usable, focus)
        story["same_geometry"] = dict(
            lag=VIEW_REPEAT_NIGHTS, note="light on the night over light 16 nights before, cells seen on both: the same view angle",
            focus=dict(ratio=export._nullable(same, 3), cells=shared.tolist()))
        if control.any():
            same_control, shared_control = same_geometry(usable, control)
            story["same_geometry"]["control"] = dict(ratio=export._nullable(same_control, 3), cells=shared_control.tolist())
        if zenith is not None:
            angle, cycles = zenith[0][:, order], zenith[1]
            matched, _ = matched_reference(usable, angle, reference_nights)
            focus_light, focus_cells = nightly_light(usable, matched, focus)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                focus_zenith = np.nanmedian(angle[:, focus], axis=1)
            story["matched"] = dict(
                tolerance=ZENITH_TOLERANCE, min_nights=1,
                rule="a cell's reference for a night is the median of its reference nights (never the night itself) whose view zenith is within the tolerance of that night's",
                zenith=export._nullable(focus_zenith, 1), cycles_carried=[None if v == -32768 else int(v) for v in cycles],
                focus=dict(light=export._nullable(focus_light, 3), cells=focus_cells.tolist()))
            if control.any():
                control_light, control_cells = nightly_light(usable, matched, control)
                story["matched"]["control"] = dict(light=export._nullable(control_light, 3), cells=control_cells.tolist())
        if len(event.story) >= 1 and event.story[0] in dates:
            k = dates.index(event.story[0])
            brightest = np.argsort(-np.where(focus & np.isfinite(usable[k]), usable[k], -1.0))[:12]
            story["brightest"] = dict(night=event.story[0].isoformat(), cells=[
                dict(lon=round(float(lon[i]), 4), lat=round(float(lat[i]), 4), radiance=round(float(usable[k, i]), 1),
                     reference=round(float(reference[i]), 1), district=int(district[i])) for i in brightest if np.isfinite(usable[k, i])])
    if control.any() and event.focus and event.marks:
        # nights until each cell that dimmed was seen back, counted from the first night after the (last marked) event
        start = dates.index(event.marks[-1][0])
        back = recovery_nights(adjusted, start)
        sizes["recovery.u8.gz"] = export.gz_write(folder / "recovery.u8.gz", back.tobytes())
        hit = focus & (back <= NEVER_BACK)
        counted = back[hit & (back < NEVER_BACK)].astype(int)
        story["recovery"] = dict(
            start=dates[start].isoformat(), back_ratio=RECOVERED_RATIO, hit_ratio=DOWN_RATIO, last_night=len(dates) - 1 - start,
            judged=int((focus & (back != NOT_JUDGED)).sum()), hit=int(hit.sum()), never_back=int((focus & (back == NEVER_BACK)).sum()),
            not_hit=int((focus & (back == NOT_HIT)).sum()),
            back_within={str(n): int((counted <= n).sum()) for n in (3, 7, 14, 21, 30)},
            median_nights=None if counted.size == 0 else float(np.median(counted)),
            codes=dict(never_back=NEVER_BACK, not_hit=NOT_HIT, not_judged=NOT_JUDGED),
            note="nights are upper bounds and counts seen back are lower bounds: a cell under cloud, or on a night without a control, says nothing")
    if event.after is not None:
        before = usable[reference_nights]
        after_nights = np.array([event.after[0] <= d <= event.after[1] for d in dates])
        _, _, lit_before, went_dark = dark_and_lit(before, usable[after_nights])
        rings = [(0, 20), (20, 40), (40, 70)]
        story["went_dark"] = dict(
            after=[d.isoformat() for d in event.after],
            rings=[dict(km=list(r), lit_before=int((lit_before & focus & (km >= r[0]) & (km < r[1])).sum()),
                        went_dark=int((went_dark & focus & (km >= r[0]) & (km < r[1])).sum())) for r in rings],
            control=dict(lit_before=int((lit_before & control).sum()), went_dark=int((went_dark & control).sum())))
        if window is not None:
            cube, wlon, wlat = window
            dark_before, lit_up, _, _ = dark_and_lit(cube[reference_nights], cube[after_nights])
            wkm = distance_km(wlon, wlat, event.epicentre)
            west_of_focus = wlon < min(lon[focus]) - 0.1 if focus.any() else np.zeros(wlon.shape, dtype=bool)
            story["new_light"] = dict(
                note="every cell of the box, lit or not, land or sea",
                near=dict(km=[0, 40], dark_before=int((dark_before & (wkm < 40)).sum()), lit_after=int((lit_up & (wkm < 40)).sum())),
                control_side=dict(dark_before=int((dark_before & west_of_focus).sum()), lit_after=int((lit_up & west_of_focus).sum())))

    units = {}
    for level, codes in (("district", district), ("subdistrict", stack.subdistrict[order])):
        result = unit_nights(usable, reference, codes)
        adjusted_unit = result.ratio / factor[:, None] if control.any() else np.full(result.ratio.shape, np.nan)
        units[level] = dict(
            code=result.codes.tolist(), cells=result.cells.tolist(),
            ratio=[export._nullable(row, 3) for row in result.ratio.T], adjusted=[export._nullable(row, 3) for row in adjusted_unit.T],
            coverage=[export._nullable(row, 3) for row in result.coverage.T],
            down=[export._nullable(row, 3) for row in result.down.T], state=result.state.T.astype(int).tolist(),
        )
    sizes["units.json"] = export._write_json(folder / "units.json", units)
    seen_by_night = np.isfinite(usable[:, has_reference]).mean(axis=1)
    meta = dict(
        key=event.key, title=event.title, script="ntl.events", product=DAILY_PRODUCT, layer=c.A2_NTL, tile=event.tile, bbox=list(event.bbox),
        epicentre=list(event.epicentre), dates=[d.isoformat() for d in dates],
        marks=[dict(date=d.isoformat(), label=label) for d, label in event.marks], story_nights=[d.isoformat() for d in event.story],
        night="a file dated D is the night that begins on the evening of local date D (overpass about 01:30 on D + 1)",
        quality=dict(flags=list(event.quality), note="0 is high quality; 1 is what the product calls poor quality (outlier, potential cloud contamination)"),
        reference=dict(first=min(d for d, r in zip(dates, reference_nights) if r).isoformat(),
                       last=max(d for d, r in zip(dates, reference_nights) if r).isoformat(), nights=int(reference_nights.sum()),
                       dates=[d.isoformat() for d, r in zip(dates, reference_nights) if r],
                       min_nights=event.min_reference_nights,
                       rule=f"median of the cell's values with quality flag {' or '.join(str(q) for q in event.quality)} in the reference nights"),
        cells=dict(total=int(index.size), with_reference=int(has_reference.sum()), focus=int(focus.sum()), control=int(control.sum())),
        seen_share_by_night=[round(float(v), 3) for v in seen_by_night], story=story,
        encoding=dict(nights="one byte per night and cell, [night, cell]; bits 0-2 ratio class, bits 3-4 staleness class",
                      adjusted="one byte per night and cell: the ratio class of the control-adjusted ratio; 7 on a night with no usable control",
                      cell_info="two bytes per cell: group (0 other, 1 focus, 2 control), km from the epicentre (254 for more)",
                      ratio_classes=["no reference", "no retrieval", "poor quality", "under 50% of reference", "50 to 80%", "80 to 125%", "125% or more"],
                      ratio_breaks=list(RATIO_BREAKS), stale_classes=["same night", "1 to 2 days", "3 to 5 days", "6 or more days, or never"],
                      stale_breaks=list(STALE_BREAKS)),
        unit=dict(states=["uncertain", "down", "same", "up"], min_coverage=MIN_COVERAGE, down_ratio=UNIT_DOWN, up_ratio=UNIT_UP, cell_down_ratio=DOWN_RATIO,
                  axes="ratio, adjusted, coverage, down and state are [unit][night]"),
        caveat="figures compare each night with the reference nights and with the control; they do not say why a cell is dim. "
               "A place's light changes with the view angle, which repeats every 16 nights: only story.same_geometry is free of it",
    )
    sizes["meta.json"] = export._write_json(folder / "meta.json", meta)
    lines = ["// GENERATED by ntl.events. Do not edit: run the event export again.", 'import {FileAttachment} from "observablehq:stdlib";', "",
             "export const files = {"]
    lines += [f"  {json.dumps(name)}: FileAttachment({json.dumps(name)})," for name in sorted(sizes)]
    lines += ["};", ""]
    export._write_text(folder / "files.js", "\n".join(lines))
    log.info("%s: %d cells (%d with a reference; focus %d, control %d), %d nights, %.2f MB in %s", event.key, index.size,
             meta["cells"]["with_reference"], int(focus.sum()), int(control.sum()), len(dates), sum(sizes.values()) / 1e6, folder)
    return meta


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.events",
        description="Night-by-night light around a dated event, from the daily Black Marble files, for the dashboard's case studies.",
        epilog=r"example:" "\n" r"  python -m ntl.events --event lombok2018 --root E:\temp\ntl --cache E:\temp\ntl\cache --out site\data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--event", required=True, choices=sorted(EVENTS), help="which case study")
    parser.add_argument("--root", required=True, type=Path, help="data root holding the daily files (python -m ntl.download --product VNP46A2)")
    parser.add_argument("--cache", required=True, type=Path, help="folder of monthly stack caches: they say which cells are lit")
    parser.add_argument("--out", required=True, type=Path, help=r"the site's data folder, e.g. site\data")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 if an input cannot be used."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    event = EVENTS[args.event]
    try:
        domain = load(cache_path(args.cache, event.tile))
        stack = build_event_stack(args.root, event, domain)
        try:
            zenith = view_zenith(args.root, event, stack.lon, stack.lat)
        except FileNotFoundError as exc:
            log.warning("%s: no view angles, so no matched reference (%s)", event.key, exc)
            zenith = None
        export_event(event, stack, args.out, window=read_window(args.root, event), zenith=zenith)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
