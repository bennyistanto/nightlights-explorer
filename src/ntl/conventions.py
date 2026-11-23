"""Single source for product facts, grid constants and picked defaults.

Every value carries a source tag in its comment:

- ``[UG]``  Black Marble User Guide, Collection 2.0 (October 2024).
- ``[L]``   LAADS DAAC: the page named in the comment, or a live archive
            listing fetched on the date given.
- ``[F]``   Read from real Collection 2 files (VNP46A1 and VNP46A2, tile
            h29v09, 2018-07-25 to 08-25, 32 files each) on 2026-11-22.
- ``[P]``   Proposed or picked for this project. Not a product fact.
- ``[B]``   Chosen from the status backtest on tiles h28v09, h29v09 and
            h30v09 (``temp/status-design.md``; outputs in the session
            scratchpad of 2026-11-22, not kept in the repo).
- ``[O]``   The owner's decision, recorded in ``HANDOFF.md``.

If a value here disagrees with a file on disk, the file wins: fix the value
and its source note together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# --------------------------------------------------------------------------
# LAADS archive
# --------------------------------------------------------------------------

#: Root of the LAADS HTTPS archive. Appending ``.json`` or ``.csv`` to any
#: directory URL returns its listing. [L] "Data Download Scripts" page,
#: read 2026-11-22.
LAADS_ARCHIVE_URL: Final[str] = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData"

#: ArchiveSet of Black Marble Collection 2. [L] archive path and live
#: listing, 2026-11-22.
BLACK_MARBLE_ARCHIVE_SET: Final[int] = 5200

#: Environment variable holding the Earthdata bearer token. [P]
TOKEN_ENV_VAR: Final[str] = "EARTHDATA_TOKEN"

#: First eight bytes of every HDF5 file (HDF5 file format specification,
#: "Format Signature"). A sign-in page served in place of a granule fails
#: this test.
HDF5_SIGNATURE: Final[bytes] = b"\x89HDF\r\n\x1a\n"


@dataclass(frozen=True)
class Product:
    """One Black Marble product as it sits in the LAADS archive.

    Attributes
    ----------
    short_name : str
        Archive folder and file-name prefix, for example ``"VNP46A2"``.
    cadence : str
        ``"daily"``, ``"monthly"`` or ``"yearly"``. Decides which
        day-of-year folders exist: every day, the first day of each month,
        or day 001 only. [L] live listings of ``5200/VNP46A1/2018``,
        ``5200/VNP46A3/2018`` and ``5200/VNP46A4/2018``, 2026-11-22.
    description : str
        One line for help text and logs.
    """

    short_name: str
    cadence: str
    description: str


#: Suomi NPP Black Marble products. [UG] for the descriptions.
PRODUCTS: Final[dict[str, Product]] = {
    "VNP46A1": Product("VNP46A1", "daily", "daily at-sensor TOA radiance with angles, moon and ancillary bands"),
    "VNP46A2": Product("VNP46A2", "daily", "daily moonlight- and atmosphere-corrected radiance"),
    "VNP46A3": Product("VNP46A3", "monthly", "monthly composite by view-angle class and snow status"),
    "VNP46A4": Product("VNP46A4", "yearly", "yearly composite by view-angle class and snow status"),
}

# --------------------------------------------------------------------------
# Tile grid
# --------------------------------------------------------------------------

#: Tile edge in degrees. [F] bounding attributes: 110 to 120 E, 0 to 10 S.
TILE_SIZE_DEG: Final[float] = 10.0
#: Tiles across (h00 to h35) and down (v00 to v17): 360 and 180 degrees in
#: 10-degree steps (derived), as drawn in [UG] Figure 2.
N_TILES_H: Final[int] = 36
N_TILES_V: Final[int] = 18
#: Cells per tile edge. [F] StructMetadata ``XDim=2400``, ``YDim=2400``.
CELLS_PER_TILE: Final[int] = 2400

#: Working bounding box for Indonesia as (west, south, east, north) in
#: degrees. [P] Picked to enclose the country with a margin; it is not a
#: legal boundary. Touches tiles h27 to h32, v08 to v10.
INDONESIA_BBOX: Final[tuple[float, float, float, float]] = (94.5, -11.5, 141.5, 6.5)

# --------------------------------------------------------------------------
# Downloader defaults. All [P]: picked, not taken from a document.
# --------------------------------------------------------------------------

#: Parallel transfers. LAADS publishes no figure on the page read; it does
#: warn that scripts sending many bad requests may be blocked. Kept low.
DEFAULT_WORKERS: Final[int] = 4
MAX_WORKERS: Final[int] = 8
#: Attempts per request before a file is reported as failed.
MAX_ATTEMPTS: Final[int] = 6
#: Backoff: ``min(cap, base * 2**(attempt-1))`` seconds, then jittered.
BACKOFF_BASE_S: Final[float] = 2.0
BACKOFF_CAP_S: Final[float] = 120.0
#: Seconds allowed to connect, and between received chunks. Picked from the
#: one measured transfer (25.8 MB in about 6 s, 2026-11-22): a connection
#: that takes over 20 s, or a stream silent for a minute, is treated as
#: stalled and retried rather than waited on.
CONNECT_TIMEOUT_S: Final[float] = 20.0
READ_TIMEOUT_S: Final[float] = 60.0
#: Stream chunk size in bytes.
CHUNK_BYTES: Final[int] = 1 << 20

#: HTTP statuses worth another attempt. 401 is on the list because LAADS
#: documents intermittent 401 responses that succeed when repeated
#: ([L] "Data Download Scripts": "A recursive wget does not retry HTTP 401
#: responses ... Run the same command again to pick up the gaps").
#: 404 is on the list from experience: on 2026-11-22, 2 of 179 files that
#: the listing showed as "Online" answered 404 and downloaded normally two
#: minutes later. Only listed files are ever requested, and a listing's own
#: 404 (folder absent) is handled before this set is consulted.
RETRY_STATUSES: Final[frozenset[int]] = frozenset({401, 404, 408, 425, 429, 500, 502, 503, 504})

#: Sent with every request. Names the tool only: no personal details.
USER_AGENT: Final[str] = "ntl-downloader/0.1"

# --------------------------------------------------------------------------
# Inside a Black Marble file
# --------------------------------------------------------------------------
# The files carry their own flag tables: VNP46A2 in ``Description``
# attributes, VNP46A1 in ``flag_meanings`` (cloud mask only; ``QF_DNB`` and
# the ``QF_VIIRS_M*`` layers carry no table). Where present they agree with
# [UG] Tables 6 and 9.

#: HDF5 group holding every gridded layer. [UG] and [F]
GRID_GROUP: Final[str] = "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields"

#: Cell size in degrees: 15 arc-seconds. [F] ``DataResolution``
CELL_SIZE_DEG: Final[float] = TILE_SIZE_DEG / CELLS_PER_TILE

#: Attribute names that hold the additive offset. VNP46A2 writes ``offset``,
#: VNP46A1 writes ``add_offset``. [F]
OFFSET_ATTRS: Final[tuple[str, ...]] = ("add_offset", "offset")

#: Fill of float radiance layers, used only if a layer has no ``_FillValue``
#: attribute. Stored as float32, so compare in float32. [UG] and [F]
RADIANCE_FILL: Final[float] = -999.9

#: Stored values that mean "no value" although they are not the layer's
#: ``_FillValue`` and lie inside its declared valid range. [F] measured:
#: ``DNB_Lunar_Irradiance`` holds 65526 on 160 cells across 3 of 32 files,
#: exactly where the VNP46A2 cloud mask is fill; the largest real stored
#: value is 1260. Scaled, 65526 would read as 6552.6 nW cm-2.
EXTRA_FILLS: Final[dict[str, tuple[int, ...]]] = {
    "DNB_Lunar_Irradiance": (65526,),
}

#: Tolerance, in cells, when turning a box edge into a row or column index,
#: so an edge lying on a cell edge does not pull in the neighbour through
#: floating-point rounding. [P] picked; a cell is 15 arc-seconds, and
#: 1e-9 of one is far below any real coordinate's precision.
WINDOW_EDGE_TOLERANCE: Final[float] = 1e-9

#: Main layers by product. Names carry a hyphen in the file; Earth Engine
#: renames them with underscores. [UG] and [F]
A2_NTL: Final[str] = "DNB_BRDF-Corrected_NTL"
A2_NTL_GAP_FILLED: Final[str] = "Gap_Filled_DNB_BRDF-Corrected_NTL"
A2_QUALITY: Final[str] = "Mandatory_Quality_Flag"
A1_RADIANCE: Final[str] = "DNB_At_Sensor_Radiance"
A1_UTC_TIME: Final[str] = "UTC_Time"
CLOUD_MASK: Final[str] = "QF_Cloud_Mask"

# ---- Mandatory_Quality_Flag, VNP46A2. [UG] Table 9 and [F] ----------------
MQF_HIGH_QUALITY: Final[int] = 0
MQF_POOR_OUTLIER: Final[int] = 1  # outlier, potential cloud contamination
MQF_POOR_HIGH_SOLAR_ZENITH: Final[int] = 2  # solar zenith 102 to 108 degrees
MQF_POOR_LUNAR_ECLIPSE: Final[int] = 3
MQF_POOR_AURORA: Final[int] = 4
MQF_POOR_GLINT: Final[int] = 5
MQF_FILL: Final[int] = 255  # no retrieval

#: Flag values accepted for status and outage work. [P] Strict by choice:
#: the user guide calls 1 to 5 poor quality.
MQF_STRICT: Final[frozenset[int]] = frozenset({MQF_HIGH_QUALITY})

# ---- QF_Cloud_Mask, uint16. [UG] Table 6 and [F] --------------------------
CLOUD_MASK_FILL: Final[int] = 65535
#: (shift, width) of each bit field.
CM_DAY_NIGHT: Final[tuple[int, int]] = (0, 1)  # 0 night, 1 day
CM_LAND_WATER: Final[tuple[int, int]] = (1, 3)
CM_MASK_QUALITY: Final[tuple[int, int]] = (4, 2)  # 0 poor, 1 low, 2 medium, 3 high
CM_CLOUD_CONFIDENCE: Final[tuple[int, int]] = (6, 2)
CM_SHADOW: Final[tuple[int, int]] = (8, 1)
CM_CIRRUS: Final[tuple[int, int]] = (9, 1)
CM_SNOW_ICE: Final[tuple[int, int]] = (10, 1)
CM_VI_USED: Final[tuple[int, int]] = (11, 1)
CM_AURORA: Final[tuple[int, int]] = (12, 1)
CM_LUNAR_ECLIPSE: Final[tuple[int, int]] = (13, 1)

#: Cloud confidence classes, bits 6 to 7.
CLOUD_CONFIDENT_CLEAR: Final[int] = 0
CLOUD_PROBABLY_CLEAR: Final[int] = 1
CLOUD_PROBABLY_CLOUDY: Final[int] = 2
CLOUD_CONFIDENT_CLOUDY: Final[int] = 3

#: Land and water classes, bits 1 to 3. Values 4, 6 and 7 are not defined
#: in the table and do not occur in the files read. [F] The class of a cell
#: is not constant: 3.1% of the tile's cells take more than one class over
#: 32 nights, mostly coast flickering between land or sea and coastal.
LW_LAND_DESERT: Final[int] = 0
LW_LAND_NO_DESERT: Final[int] = 1
LW_INLAND_WATER: Final[int] = 2
LW_SEA_WATER: Final[int] = 3
LW_COASTAL: Final[int] = 5

#: Value written by ``ntl.qa`` decoders where the cloud mask itself is fill.
DECODED_FILL: Final[int] = 255

# ---- VNP46A3 and VNP46A4 composites. [UG] 5.3, Tables 11 to 13 -------------
# Checked against one real file, VNP46A3 A2018213 h29v09, on 2026-11-22: the
# quality table is in each ``_Quality`` layer's ``Description``; quality 0
# always has 4 or more observations, 1 to 3 observations is always quality
# 1, and quality 2 has none.

#: View-angle classes. NearNadir is view zenith 0 to 20 degrees, OffNadir
#: 40 to 60 degrees (layer ``long_name`` in the file).
COMPOSITE_VIEWS: Final[tuple[str, ...]] = ("AllAngle", "NearNadir", "OffNadir")
#: Layer name pattern. ``suffix`` is "" for radiance, or one of the three
#: below. Indonesia uses the snow-free layers only: in the file read, 97% of
#: the snow-covered composite is gap filled.
COMPOSITE_LAYER: Final[str] = "{view}_Composite_Snow_Free{suffix}"
COMPOSITE_NUM: Final[str] = "_Num"  # observations used, uint16
#: Fill of the ``_Num`` layers. [F] Set it to 0 nights before any sum.
COMPOSITE_NUM_FILL: Final[int] = 65535
COMPOSITE_QUALITY: Final[str] = "_Quality"  # uint8, table below
COMPOSITE_STD: Final[str] = "_Std"  # standard deviation, nW cm-2 sr-1
#: Land and water classes, same codes as ``LW_*``, fill 255. [F] It is NOT
#: the same every month: it is fill exactly where the AllAngle quality is
#: fill (312 to 4.97 million cells of tile h29v09, by month), and 0.6 to
#: 1.5% of cells change class at least once. Use one fixed mask per tile
#: (``ntl.composite.modal_class``).
COMPOSITE_LAND_WATER: Final[str] = "Land_Water_Mask"
LAND_WATER_FILL: Final[int] = 255

CQ_GOOD: Final[int] = 0  # more than 3 observations
#: 1 to 3 observations. [F] Some cells with 4 or more observations are also
#: marked poor, a rule the user guide table does not state. In the first
#: file read they were all over sea, inland water and coast, with a mean
#: radiance of at most 1.0 and a standard deviation above the mean; over the
#: whole record of tile h29v09 it happens on land too (783 cell-months in
#: the status domain). So "poor" cannot be read as "under 4 nights".
CQ_POOR: Final[int] = 1
#: Gap filled from historical data. **The radiance layer holds a number
#: here although nothing was observed** (``_Num`` is 0, ``_Std`` is fill).
CQ_GAP_FILLED: Final[int] = 2
CQ_FILL: Final[int] = 255

#: Observation state codes returned by ``ntl.qa.observation_state``. [P]
STATE_NOT_OBSERVED: Final[int] = 0  # no retrieval: never "dark"
STATE_REJECTED: Final[int] = 1  # a retrieval the caller's rule refuses
STATE_USABLE: Final[int] = 2

# ---- Downloader layout and behaviour. All [P] ------------------------------
#: Folder under the data root that mirrors the LAADS archive.
BLACK_MARBLE_DIR: Final[str] = "blackmarble"
#: Manifest file name inside that folder.
MANIFEST_NAME: Final[str] = "manifest.jsonl"
#: Log a progress line every this many finished files.
PROGRESS_EVERY: Final[int] = 25
#: Stop the batch after this many files in a row fail for a reason that
#: points at the token (401, 403, or a page served in place of the file).
#: LAADS warns that scripts sending many bad requests may be blocked.
AUTH_FAILURES_BEFORE_STOP: Final[int] = 3

# --------------------------------------------------------------------------
# Status statistic. Design adopted by the owner on 2026-11-22 after a
# backtest on tiles h28v09, h29v09 and h30v09 (temp/status-design.md).
# Tags here: [B] chosen from that backtest; [P] picked without a test;
# [O] the owner's decision.
# --------------------------------------------------------------------------

#: Admin levels, coarse to fine, in the owner's terms (2026-11-22):
#: province is adm1 (``a1siak``), district is adm2 (``a2siak``, kabupaten
#: or kota), sub-district is adm3 (``a3siak``, kecamatan). Code written
#: before that date, and every note in ``temp/`` older than it, said
#: "regency" for adm2 and "district" for adm3.
#: The divisor turns a sub-district code into the code of each level. [F]
#: checked on every coded feature of the adm3 boundary file (7,278 after the
#: owner's corrections): ``a3siak // 100 == a2siak`` and
#: ``a3siak // 10000 == a1siak`` with no exception. [O] siak codes are the keys.
ADMIN_LEVELS: Final[tuple[str, ...]] = ("province", "district", "subdistrict")
ADMIN_DIVISOR: Final[dict[str, int]] = {"province": 10_000, "district": 100, "subdistrict": 1}
#: The level above each level; a province has none.
ADMIN_PARENT: Final[dict[str, str | None]] = {"province": None, "district": "province", "subdistrict": "district"}
#: Code of cells that belong to no unit.
NO_UNIT: Final[int] = 0
#: Finest level at which a sub-district's area can be reported
#: (``ntl.monitor.reporting_level``).
REPORT_NONE: Final[int] = 0
REPORT_PROVINCE: Final[int] = 1
REPORT_DISTRICT: Final[int] = 2
REPORT_SUBDISTRICT: Final[int] = 3

#: Thresholds that define which cells and units enter the status. All [P]:
#: picked for the method tests of 2026-11-22 and carried through the
#: backtest; none was varied systematically.
#: Long-term mean radiance for a cell to be in the status domain,
#: nW cm-2 sr-1. Floor flicker ends near here in the western tiles (2 to 3%
#: of cells above it are zero in over a tenth of months; 24% in h30v09).
LIT_MIN_RADIANCE: Final[float] = 2.0
#: Good months a cell needs before its long-term mean is trusted.
LIT_MIN_GOOD_MONTHS: Final[int] = 12
#: Nights behind a monthly or three-month value for it to be usable.
MIN_NIGHTS: Final[int] = 4
#: Domain cells a unit needs to be monitorable at its own level, and to
#: vote when its parent asks whether its children agree. [P] Units below it
#: still get a status but report through their parent. Measured nationally:
#: 1,690 of 4,479 sub-districts are under 20 cells, and they supply nearly
#: all "seen and dark" windows (6,209 of 6,518).
MIN_UNIT_CELLS: Final[int] = 20

#: Months of a unit's own past used to fit its expected value. [B] of 4, 6
#: and 10 years, 6 gave the least noise for h29v09 sub-districts (0.115,
#: 0.107, 0.110) and 10 brought bias back (+0.03). Figures for 3, 5 and 8
#: years were reported by the critique but their output was not kept.
STATUS_LOOKBACK_MONTHS: Final[int] = 72
#: Observed windows needed in the lookback, and in the target's calendar
#: month, before an expected value is given. [P]
STATUS_MIN_FIT_WINDOWS: Final[int] = 24
STATUS_MIN_SAME_MONTH: Final[int] = 2
#: Huber tuning constant, in units of the residual scale. [P] the
#: conventional value; not varied in the backtest.
HUBER_TUNING: Final[float] = 1.345
#: Reweighting passes of the robust fit. [P] This is a truncation, not
#: convergence: the standards review measured predictions at 20 passes
#: within 2e-4 (99th percentile) of 200 passes on real unit-windows, and at
#: most 1.1e-2 away. Changing it changes results at that level.
HUBER_PASSES: Final[int] = 20
#: A unit has a value only if its usable cells carry this share of its
#: usual light. [P] inherited from the prototype; windows under 0.8 coverage
#: were measured 1.1 to 1.3 times noisier (monthly) and 1.4 to 1.6 times
#: (three-month) in h29v09.
STATUS_MIN_COVERAGE: Final[float] = 0.5
#: Earlier anomalies a unit needs before its own noise is estimated. [P]
STATUS_MIN_PAST_ANOMALIES: Final[int] = 24
#: Standardised anomalies a pool needs before a tail factor is read from
#: it: at least TAIL_POOL_MIN, and at least TAIL_POOL_BEYOND values expected
#: beyond the quantile (so 1,000 values for a 1% rate, 300 for 5%). [B] 300
#: is the value the backtest used. [P] the "ten beyond" rule was added after
#: the national run of 2026-11-22: the first province factor at 1%, read
#: from 452 values (4 or 5 beyond the quantile), was -1.99 where later years
#: gave -2.75 to -3.01, and produced an 11.9% alarm rate in that year.
TAIL_POOL_MIN: Final[int] = 300
TAIL_POOL_BEYOND: Final[int] = 10
#: Months a held window is kept out of later fits, so a lasting drop is not
#: learned as the new normal. [P] 24 tested against no hold only. Used by
#: ``status.anomalies_held``.
STATUS_HOLD_MONTHS: Final[int] = 24
#: Two tiers of false-alarm rate per unit-window. [O] Applied by
#: ``monitor.run_level``.
WATCH_RATE: Final[float] = 0.05
ALARM_RATE: Final[float] = 0.01
#: A unit is monitorable at a level only if the smallest drop it would
#: detect with DETECTION_POWER at the alarm rate is at most this. [B] at
#: 0.30 only 21%, 14% and 3% of lit sub-districts qualified in the three tiles;
#: 0.50 admits units that see only a halving.
MAX_DETECTABLE_DROP: Final[float] = 0.40
#: Probability of catching the smallest detectable drop. [P]
DETECTION_POWER: Final[float] = 0.80
#: 1.4826 x median absolute deviation estimates a standard deviation for
#: normally distributed data (1 / 0.6745, the 75th normal percentile). A
#: mathematical constant, not a choice.
MAD_TO_SD: Final[float] = 1.4826

#: Classes of "nights behind a unit's value" for the nights factor: lower
#: edges of the second and later classes. [P] as used in the backtest:
#: monthly 4-7, 8-11, 12-15, 16+; three-month under 12, 12-23, 24-39, 40+.
NIGHT_CLASS_EDGES_MONTHLY: Final[tuple[int, ...]] = (8, 12, 16)
NIGHT_CLASS_EDGES_SEASONAL: Final[tuple[int, ...]] = (12, 24, 40)

#: Status of a unit in a window, returned by ``ntl.monitor``. [P] Only
#: dimming is classified; a unit brighter than expected is "normal".
STATUS_NOT_OBSERVED: Final[int] = 0  # too little of the unit was seen: never "dark"
STATUS_NO_REFERENCE: Final[int] = 1  # seen, but its past is too thin for an expected value
STATUS_NO_THRESHOLD: Final[int] = 2  # an anomaly exists, but no scale or factor yet
STATUS_NORMAL: Final[int] = 3
STATUS_WATCH: Final[int] = 4  # below the WATCH_RATE threshold
STATUS_ALARM: Final[int] = 5  # below the ALARM_RATE threshold
#: Low against its own past but not against the rest of its parent: the
#: whole area moved (haze, a shared year-to-year swing). ``run_level`` only
#: labels it; ``monitor.confirm_by_children`` is what can raise the parent.
STATUS_REGIONAL: Final[int] = 6
#: Enough of the unit was seen and every usable cell read zero. An
#: observation, not a gap. What tier it deserves is not yet designed.
STATUS_DARK: Final[int] = 7

#: A parent is raised to REGIONAL when MORE than this share of its voting
#: children read low against their own past, given at least
#: CHILD_AGREEMENT_MIN voting children. A child votes if it was judged or
#: seen dark and has MIN_UNIT_CELLS cells. [P] The share was picked to sit
#: near the alarm rate; the base rates behind it are in
#: ``temp/status-design.md`` ("After the second reviews") and must be
#: re-read there, because the first figures recorded here (1.35%) belonged
#: to a threshold of 0.67 and to a count that let tiny dark units vote.
CHILD_AGREEMENT_SHARE: Final[float] = 2.0 / 3.0
CHILD_AGREEMENT_MIN: Final[int] = 3

#: Version of the ``.npz`` written by ``ntl.stack.save``. 1 had no version
#: key and named adm2 "regency" and adm3 "district"; 2 uses the level names
#: above and records how the domain was built; 3 also records whether
#: consistent light sources were added to the domain (``ntl.sources``).
STACK_CACHE_VERSION: Final[int] = 3
#: Side of a 15 arc-second cell along a meridian, km (mean Earth radius 6371.0088 km).
CELL_KM: Final[float] = CELL_SIZE_DEG * 3.141592653589793 * 6371.0088 / 180.0
#: Light sources (``ntl.sources``): neighbours count out to this distance, km,
#: with a weight falling to an eighth at the scale; a cell is a source in a
#: month when it exceeds its background by the contrast, nW cm-2 sr-1, and is
#: a consistent source when that holds in this share of its good months.
#: [P] Chosen on tile h28v09, 2026-11-23. Consistent sources under the mean
#: rule are shown on the map as faint sources; they are NOT in the status
#: domain: a national run with them added lost 281 of 759 alarm readings of
#: the run without them, 67 in units that gained no cell (second method
#: critique, 2026-11-23).
SOURCE_RADIUS_KM: Final[float] = 6.1
SOURCE_SCALE_KM: Final[float] = 0.61
SOURCE_MIN_CONTRAST: Final[float] = 0.5
SOURCE_MIN_SHARE: Final[float] = 0.5
#: Product and default view-angle class of the monthly status.
MONTHLY_PRODUCT: Final[str] = "VNP46A3"
DEFAULT_VIEW: Final[str] = "AllAngle"

# ---------------------------------------------------------------------------
# What ships to the browser (``ntl.boundaries``, ``ntl.export``)
# ---------------------------------------------------------------------------
#: Tolerance for simplifying display outlines, degrees. [P] The value
#: ``drywet-explorer`` uses for all three levels. It is the square root of
#: the area of the triangles removed (``shapely.coverage_simplify``): a
#: bend goes when its triangle is under about 9e-6 square degrees, which
#: for a compact bend is about 0.003 degree (330 m at the equator, under
#: one 15 arc-second cell of about 460 m) and for a long narrow one can be
#: longer. Display only: no statistic reads outlines.
OUTLINE_TOLERANCE_DEG: Final[float] = 0.003
#: Decimals kept in outline coordinates (0.0001 degree is about 11 m).
OUTLINE_DECIMALS: Final[int] = 4
#: Budget for everything under the site's data folder, bytes. [P]
SITE_BUDGET_BYTES: Final[int] = 300 * 1024 * 1024
#: Columns of a status bundle, in file order: name, numpy dtype, scale,
#: missing code. A stored integer is ``round(value * scale)``; the missing
#: code marks "no value" (None: the column has no missing value). Values
#: beyond the dtype's range are clipped and counted in the export report.
#: ``flags`` packs three booleans: bit 0 held, bit 1 joint, bit 2 monitorable.
#: ``run`` is ``ntl.persistence.low_runs``: low (watch or alarm) windows so
#: far in the episode the window belongs to, 0 where it does not read low;
#: ``span`` is the calendar windows the same episode covers so far.
BUNDLE_COLUMNS: Final[tuple[tuple[str, str, float, int | None], ...]] = (
    ("state", "u1", 1, None),              # STATUS_* codes
    ("index", "<i2", 1000, -32768),        # ln(light / usual light)
    ("anomaly", "<i2", 1000, -32768),      # ln(observed / expected)
    ("relative", "<i2", 1000, -32768),     # anomaly minus that of the rest of the parent
    ("scale", "<u2", 10000, 65535),        # the unit's own noise, log units
    ("relative_scale", "<u2", 10000, 65535),
    ("coverage", "u1", 200, 255),          # share of usual light seen, 0 to 1
    ("nights", "u1", 2, 255),              # mean nights behind the value
    ("detectable", "u1", 200, 255),        # smallest detectable drop, 0 to 1
    ("flags", "u1", 1, None),
    ("run", "u1", 1, None),                # persistence.low_runs: months; clipped at 255
    ("span", "u1", 1, None),               # persistence.run_spans: calendar months of the same episode
    ("unseen", "u1", 1, None),             # persistence.unseen_runs: months in a row not observed
)
#: Readable names of the status codes, for the site's metadata.
STATUS_NAMES: Final[dict[int, str]] = {
    STATUS_NOT_OBSERVED: "not observed",
    STATUS_NO_REFERENCE: "no reference",
    STATUS_NO_THRESHOLD: "no threshold",
    STATUS_NORMAL: "normal",
    STATUS_WATCH: "watch",
    STATUS_ALARM: "alarm",
    STATUS_REGIONAL: "regional",
    STATUS_DARK: "dark",
}
