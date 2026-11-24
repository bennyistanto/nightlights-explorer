"""The long view for the site: DMSP 1992 to 2013 and VIIRS from 2012, side by side and NOT joined.

Two sensors, three segments, one time axis:

- DMSP-OLS 1992 to 2009 (satellites F10 to F16), from ``ntl.longrecord``:
  light as a sum of corrected digital numbers, lit cells, a band of
  disagreement between satellites, and flags.
- DMSP-OLS F18, 2010 to 2013: the same quantities, but a segment of its own,
  because for those years EOG's series has a yearly composite of F18 alone.
- VIIRS (Black Marble) from 2012: the unit's light RELATIVE TO ITS OWN USUAL
  LEVEL, one value per calendar year. It is the median over the year's months
  of the monthly index the dashboard's statuses use
  (``ntl.monitor.LevelSeries.index``: light of the unit's lit cells over
  their usual light, on the cells seen that month), turned from a log into a
  ratio. 1.0 is the unit's usual light over the VIIRS record.

Why they are not joined. Measured over Indonesia on 2026-11-24 for the two
years both sensors cover: a conversion of VIIRS radiance to a DMSP-like
number (blur, a sigmoid of log radiance and a floor) fitted on one year
predicts the other within 3% for the country, but misses provinces by 22% to
25% (9 or 10 of 38 within 10%); the country figure is a balance of opposite
regional errors (0.92, 1.09 and 1.16 for the three regions it was fitted on),
moves from 1.14 to 0.92 with a floor between 0.10 and 0.25 nW, and compresses
growth (radiance doubling becomes 1.6 times). A
third of the cells F18 calls lit have less than 0.25 nW of VIIRS light under
them: mostly the wider footprint of DMSP around lights VIIRS does see (86% of
it within 3 DMSP cells of a VIIRS cell of 0.5 nW), with a little light below
the VIIRS product's own floor. So the two are different instruments and the
page shows each in its own unit. No ratio between them is exported: it depends on
which VIIRS product is used.

Nothing here is specific to Indonesia.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ntl import longrecord, monitor, trend

log = logging.getLogger("ntl.longview")

#: Bits of the per unit-year flag written for the page.
FLAG_DROP: Final[int] = 1          # lit area drops and returns
FLAG_LOW_RECALL: Final[int] = 2    # the satellite missed much of the unit's steady dim light
FLAG_THIN: Final[int] = 4          # few cloud-free observations
FLAG_UNDETECTED: Final[int] = 8    # no light at all: not detected, which is not "dark for certain"
FLAG_ONE_OF_TWO: Final[int] = 16   # two satellites have a composite; one was set aside for missing dim light
#: Share of light at the top of the DMSP scale from which a unit-year counts as saturated on the page. Picked.
SATURATED_SHARE: Final[float] = 0.5
FLAG_SATURATED: Final[int] = 32
#: The DMSP quantities written, with the decimals kept.
DMSP_QUANTITIES: Final[dict[str, int]] = {"light": 0, "lit": 1}


def viirs_yearly(index: ArrayLike, years: ArrayLike, min_months: int = trend.MIN_MONTHS_PER_YEAR) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.int64]]:
    """One VIIRS value per calendar year and unit, relative to the unit's usual light.

    Parameters
    ----------
    index : array_like of float, shape (months, units)
        Monthly log index; NaN where the unit has no value that month.
    years : array_like of int, shape (months,)
        Calendar year of each row.
    min_months : int
        Months with a value a year needs; with fewer its value is NaN.

    Returns
    -------
    (ndarray of int64, ndarray of float64, ndarray of int64)
        The years; ``exp`` of the median of each year's monthly values,
        shape (years, units), 1.0 being the unit's usual light; and the
        months with a value behind each, same shape.
    """
    index = np.asarray(index, dtype=np.float64)
    years = np.asarray(years)
    listed, medians = trend.yearly_medians(index, years, min_months)
    counts = np.array([np.isfinite(index[years == year]).sum(axis=0) for year in listed], dtype=np.int64)
    return listed, np.exp(medians), counts


def flag_bits(record: longrecord.LongRecord) -> NDArray[np.uint8]:
    """The flags of a record packed into one small integer per year and unit (the ``FLAG_`` constants)."""
    with np.errstate(invalid="ignore"):
        saturated = record.saturated >= SATURATED_SHARE
    bits = (record.drops * FLAG_DROP + record.low_recall * FLAG_LOW_RECALL + record.thin * FLAG_THIN + record.undetected * FLAG_UNDETECTED
            + (record.chosen >= 0) * FLAG_ONE_OF_TWO + saturated * FLAG_SATURATED)
    return bits.astype(np.uint8)


def _rows(values: NDArray, decimals: int) -> list[list[float | None]]:
    """A (years, units) array as lists per UNIT, NaN as null."""
    return [[None if not np.isfinite(v) else round(float(v), decimals) for v in column] for column in np.asarray(values, dtype=np.float64).T]


def payload(codes: NDArray, record: longrecord.LongRecord, viirs_codes: NDArray, viirs_years: NDArray, viirs_ratio: NDArray, viirs_months: NDArray) -> dict[str, Any]:
    """Everything the page needs for one admin level, as plain lists.

    Parameters
    ----------
    codes : ndarray of int, shape (units,)
        Unit codes of the DMSP record; the payload follows their order.
    record : longrecord.LongRecord
    viirs_codes : ndarray of int
        Unit codes of the VIIRS run; a DMSP unit absent from it gets nulls.
    viirs_years, viirs_ratio, viirs_months
        From :func:`viirs_yearly`.

    Returns
    -------
    dict
        ``codes``; ``dmsp`` with ``years``, ``segment`` (0 or 1 per year),
        ``sources`` (satellites per year), per quantity ``value``, ``low``,
        ``high`` and the two readings of a year with two satellites
        (``pair_low``, ``pair_high``), each a list per unit of a list per
        year, and ``spread`` per unit (natural log; null where the unit had
        too few years with two satellites and only borrows the others'
        median, so that the page says "cannot be judged" and does not show a
        borrowed figure as the unit's own); ``flags`` (bits) and ``recall``
        per unit and year; per unit ``flare_share`` (the share of its light,
        summed over all years, that lies inside the flare outlines; null
        with no light);
        ``satellites`` (national light and
        lit cells of every satellite-year); and ``viirs`` with ``years``,
        ``ratio`` and ``months`` per unit.
    """
    dmsp: dict[str, Any] = {"years": [int(y) for y in record.years], "segment": [int(s) for s in record.segment], "sources": record.sources,
                            "flags": [[int(v) for v in column] for column in flag_bits(record).T],
                            "recall": _rows(record.recall, 2), "satellites": record.satellites}
    # over the whole record, weighted by light: the largest share of any single year would let one year with a
    # handful of lit cells put a nearly dark unit at 100%
    light, outside = np.nansum(record.series["light"].value, axis=0), np.nansum(record.series["outside"].value, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(light > 0, 1.0 - outside / light, np.nan)
    dmsp["flare_share"] = [None if not np.isfinite(v) else round(float(v), 3) for v in share]
    for quantity, decimals in DMSP_QUANTITIES.items():
        series = record.series[quantity]
        dmsp[quantity] = {field: _rows(getattr(series, field), decimals) for field in ("value", "low", "high", "pair_low", "pair_high")}
        dmsp[quantity]["spread"] = [None if not (np.isfinite(v) and own) else round(float(v), 4) for v, own in zip(series.spread, series.own_spread)]
    position = {int(code): i for i, code in enumerate(viirs_codes)}
    ratio = np.full((viirs_years.size, len(codes)), np.nan)
    months = np.zeros((viirs_years.size, len(codes)), dtype=np.int64)
    for j, code in enumerate(codes):
        if int(code) in position:
            ratio[:, j], months[:, j] = viirs_ratio[:, position[int(code)]], viirs_months[:, position[int(code)]]
    return {"codes": [int(code) for code in codes], "dmsp": dmsp,
            "viirs": {"years": [int(y) for y in viirs_years], "ratio": _rows(ratio, 4), "months": [[int(v) for v in column] for column in months.T]}}


def sensors_block(comparison: dict[str, Any], level: str, codes: Sequence[int]) -> dict[str, Any]:
    """The part of a ``python -m ntl.sensors`` result that one admin level's page needs.

    Parameters
    ----------
    comparison : dict
        As returned by ``ntl.sensors.compare``.
    level : str
    codes : sequence of int
        Unit codes of the DMSP record; ``unseen`` follows their order, with
        None for a unit the comparison does not know.

    Returns
    -------
    dict
        ``years``, ``satellite``, ``dark_nw``, ``classes`` (year to a list of
        classes of VIIRS radiance) and ``unseen`` (year to a list per unit).

    Raises
    ------
    KeyError
        If the comparison was not made for this level.
    """
    mine = comparison["levels"][level]
    position = {int(code): i for i, code in enumerate(mine["codes"])}
    unseen = {year: [values[position[int(code)]] if int(code) in position else None for code in codes] for year, values in mine["unseen"].items()}
    return {"years": comparison["years"], "satellite": comparison["satellite"], "dark_nw": comparison["dark_nw"], "classes": comparison["classes"], "unseen": unseen}


def export(records: str | Path, run_file: str | Path, out: str | Path, levels: Sequence[str] = ("province", "district"),
           sensors: str | Path | None = None) -> dict[str, int]:
    """Write ``long_<level>.json`` for the site.

    Parameters
    ----------
    records : str or Path
        Folder of ``dmsp_<level>.npz`` from ``python -m ntl.longrecord``.
    run_file : str or Path
        The monthly run the dashboard's statuses come from (``ntl.monitor``).
    out : str or Path
        Folder for the JSON files; created.
    levels : sequence of str
    sensors : str or Path, optional
        The JSON written by ``python -m ntl.sensors``: F18 beside VIIRS for
        the years both cover. Without it the files carry no ``sensors`` part.

    Returns
    -------
    dict of str to int
        Bytes written per file.

    Raises
    ------
    KeyError
        If the run has no such level.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    run = monitor.load_levels(run_file)
    comparison = json.loads(Path(sensors).read_text(encoding="utf-8")) if sensors else None
    years = np.array([month.year for month in run.months])
    sizes = {}
    for level in levels:
        codes, record, meta = longrecord.load(Path(records) / f"dmsp_{level}.npz")
        status = run.levels[level]
        body = payload(codes, record, status.codes, *viirs_yearly(status.series.index, years))
        if comparison is not None:
            body["sensors"] = sensors_block(comparison, level, body["codes"])
        body["meta"] = {"dmsp_thresholds": meta["thresholds"], "dmsp_dropped": meta["dropped"], "viirs_view": run.info.get("view"),
                        "viirs_months": [run.months[0].isoformat(), run.months[-1].isoformat()], "viirs_min_months": trend.MIN_MONTHS_PER_YEAR}
        target = out / f"long_{level}.json"
        temporary = target.with_suffix(".json.part")
        temporary.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        temporary.replace(target)
        sizes[target.name] = target.stat().st_size
        log.info("%s: %d units, %d bytes", target.name, len(codes), sizes[target.name])
    return sizes


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.longview",
        description="Write the long view for the site: the yearly DMSP record and yearly VIIRS, per admin unit, not joined.",
        epilog="example:\n" r"  python -m ntl.longview --records E:\temp\ntl\longrecord --run E:\temp\ntl\cache\run_monthly.npz --out site\data\long",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--records", required=True, type=Path, help="folder of dmsp_<level>.npz from python -m ntl.longrecord")
    parser.add_argument("--run", required=True, type=Path, help="the monthly run of ntl.monitor that the dashboard uses")
    parser.add_argument("--out", required=True, type=Path, help="folder for long_<level>.json")
    parser.add_argument("--levels", nargs="+", default=["province", "district"], help="admin levels (default: province district)")
    parser.add_argument("--sensors", type=Path, help="the JSON of python -m ntl.sensors, to add F18 beside VIIRS for the years both cover")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns 0 on success, 1 on a problem with the inputs."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        export(args.records, args.run, args.out, args.levels, args.sensors)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
