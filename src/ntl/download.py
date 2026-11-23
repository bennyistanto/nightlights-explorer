"""Download Black Marble granules from the LAADS archive.

For a product, a period and a region this module asks LAADS which files
exist, then fetches them in parallel with retry, resume and verification.
It is written against the interface LAADS documents, read 2026-11-22:

- "Data Download Scripts": any archive directory URL plus ``.json`` returns
  its listing; files are fetched with ``Authorization: Bearer <token>``;
  HTTP 401 can be transient and should be repeated; scripts that send many
  bad requests may be blocked.
- "Download Files Using EDL Tokens": paths are
  ``archive/allData/ARCHIVE_SET/PRODUCT/YEAR/DAY_OF_YEAR/FILENAME``; the
  client must follow redirects and keep session cookies; tokens expire.

Guarantees
----------
- A file appears under its final name only when complete: bytes go to
  ``<name>.part`` and are renamed after the checks pass.
- A finished file has the size the listing gave and starts with the HDF5
  signature. A sign-in page saved as ``.h5`` cannot pass.
- Every file present under its final name has one row in ``manifest.jsonl``
  (URL, bytes, SHA-256, time). A rerun skips complete files and writes any
  row that an interrupted run left out.
- A tile absent from the archive on a date is reported as ``missing``; a
  transfer that fails after all attempts is reported as ``failed``. Neither
  is silent, and the exit code is non-zero if anything failed.
- The batch stops early when several files in a row fail in a way that
  points at the token, instead of sending a bad request for every file.
- The token is read from the environment or an env file. It is sent only to
  the LAADS archive host, and is never logged, written to the manifest, or
  placed in a URL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import httpx

from ntl import conventions as c
from ntl.tiles import Tile, parse_tile, tiles_for_bbox

log = logging.getLogger("ntl.download")

_EXAMPLES = r"""
examples:
  List what would be fetched. Listings are public, so no token is needed:
    python -m ntl.download --product VNP46A2 --start 2018-08-01 --end 2018-08-10
        --tiles h29v09 --root E:\temp\ntl --dry-run

  A month of daily files for a box (west south east north, degrees), six at once:
    python -m ntl.download --product VNP46A1 --start 2018-08-01 --end 2018-08-31
        --bbox 115.5 -9.2 117.0 -8.0 --root E:\temp\ntl --workers 6

  Monthly composites for all of Indonesia, 2012 to 2024:
    python -m ntl.download --product VNP46A3 --start 2012-01-01 --end 2024-12-31
        --indonesia --root E:\temp\ntl

dates are the UTC dates in the file names. For a daily file, date D is the
night that begins on the evening of local date D in Indonesia. A monthly or
yearly composite is fetched when its period overlaps --start to --end.
"""

# VNP46A2.A2018217.h29v09.002.2025002133145.h5
#   product . A + year + day-of-year . tile . collection . production stamp
_GRANULE_NAME = re.compile(
    r"^(?P<product>[A-Z0-9]+)\.A(?P<year>\d{4})(?P<doy>\d{3})\."
    r"h(?P<h>\d{2})v(?P<v>\d{2})\.(?P<collection>\d{3})\.(?P<produced>\d+)\.h5$"
)
_CONTENT_RANGE = re.compile(r"^bytes (\d+)-")

Sleep = Callable[[float], None]


@dataclass(frozen=True)
class Granule:
    """One file in the archive.

    Attributes
    ----------
    product : str
        Short name, for example ``"VNP46A2"``.
    date : datetime.date
        Date in the file name (``AYYYYDDD``). For daily products this is the
        UTC date of the granule, which is not the local calendar night; for
        monthly and yearly products it is the first day of the period.
    tile : Tile
        Grid tile.
    name : str
        File name as listed.
    url : str
        Full HTTPS address on the LAADS archive host.
    size : int
        Bytes, as the listing reports. Used to verify the transfer.
    """

    product: str
    date: dt.date
    tile: Tile
    name: str
    url: str
    size: int

    def relative_path(self) -> Path:
        """Path under the data root. Mirrors the archive: product, year, day of year."""
        return Path(c.BLACK_MARBLE_DIR, self.product, f"{self.date.year}", f"{self.date:%j}", self.name)


@dataclass(frozen=True)
class Outcome:
    """Result for one requested (date, tile) or one granule.

    Attributes
    ----------
    status : str
        ``"downloaded"``, ``"skipped"`` (already complete), ``"missing"``
        (not in the archive) or ``"failed"`` (gave up; see ``detail``).
    product, date, tile, name : str, date, str, str
        What was asked for. ``name`` is empty when no file was found.
    detail : str
        Reason for a failure. Never contains the token.
    """

    status: str
    product: str
    date: dt.date
    tile: str
    name: str = ""
    detail: str = ""


class DownloadError(RuntimeError):
    """A request or a verification failed and should not be retried."""


class AuthError(DownloadError):
    """A failure that points at the token: 401, 403, or a page in place of a file."""


class _Incomplete(Exception):
    """A transfer ended short or out of step. Worth another attempt."""


def parse_granule_name(name: str) -> tuple[str, dt.date, Tile] | None:
    """Split a granule file name into product, date and tile.

    Parameters
    ----------
    name : str
        A file name such as ``VNP46A2.A2018217.h29v09.002.2025002133145.h5``.

    Returns
    -------
    (str, datetime.date, Tile) or None
        ``None`` for anything that is not a tiled ``.h5`` granule, so a
        listing may contain other entries without harm.
    """
    match = _GRANULE_NAME.match(name)
    if match is None:
        return None
    date = dt.date(int(match["year"]), 1, 1) + dt.timedelta(days=int(match["doy"]) - 1)
    return match["product"], date, Tile(int(match["h"]), int(match["v"]))


def period_dates(cadence: str, start: dt.date, end: dt.date) -> list[dt.date]:
    """Archive folder dates for a period.

    Parameters
    ----------
    cadence : str
        ``"daily"``, ``"monthly"`` or ``"yearly"``.
    start, end : datetime.date
        Inclusive.

    Returns
    -------
    list of datetime.date
        Daily: every date. Monthly: the first day of every month that
        overlaps the period. Yearly: 1 January of every year that overlaps
        it. A composite is filed in the archive under the day of year of its
        first day (live listings, 2026-11-22), so these are folder dates.

    Raises
    ------
    ValueError
        If ``end`` is before ``start`` or the cadence is unknown.

    Notes
    -----
    Selection is by overlap: 2018-08-05 to 2018-08-25 selects the August
    2018 monthly composite and the 2018 yearly one, although neither starts
    inside the period.
    """
    if end < start:
        raise ValueError("--end is before --start")
    if cadence == "daily":
        return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    if cadence == "monthly":
        out, year, month = [], start.year, start.month
        while (year, month) <= (end.year, end.month):
            out.append(dt.date(year, month, 1))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return out
    if cadence == "yearly":
        return [dt.date(y, 1, 1) for y in range(start.year, end.year + 1)]
    raise ValueError(f"unknown cadence: {cadence!r}")


def directory_url(product: str, date: dt.date) -> str:
    """Archive folder for one product and folder date (no trailing slash)."""
    return f"{c.LAADS_ARCHIVE_URL}/{c.BLACK_MARBLE_ARCHIVE_SET}/{product}/{date.year}/{date:%j}"


def listing_url(product: str, date: dt.date) -> str:
    """Address of the JSON listing of that folder."""
    return directory_url(product, date) + ".json"


def backoff_seconds(attempt: int, rng: Callable[[], float] = random.random) -> float:
    """Wait before the next attempt: capped exponential with jitter.

    Parameters
    ----------
    attempt : int
        Attempt just failed, counting from 1.
    rng : callable
        Returns a number in [0, 1). Injected for tests.

    Returns
    -------
    float
        Seconds, between half of and the whole of
        ``min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2**(attempt - 1))``. Jitter
        keeps parallel workers from all returning at the same instant.
    """
    ceiling = min(c.BACKOFF_CAP_S, c.BACKOFF_BASE_S * 2 ** (attempt - 1))
    return ceiling * (0.5 + 0.5 * rng())


def read_token(env_file: Path | None = None) -> str:
    """Find the bearer token without ever printing it.

    Parameters
    ----------
    env_file : Path, optional
        A text file with a line ``EARTHDATA_TOKEN=value``. ``#`` comment
        lines, blank lines, a leading ``export``, quotes around the value
        and a UTF-8 byte-order mark (as Notepad and PowerShell write) are
        accepted. The environment variable wins over the file.

    Returns
    -------
    str
        The token.

    Raises
    ------
    DownloadError
        If no token is found, the file cannot be decoded, or the value
        contains spaces. Messages name the variable or file, never a value.
    """
    token = os.environ.get(c.TOKEN_ENV_VAR, "").strip()
    if not token and env_file is not None and env_file.is_file():
        try:
            text = env_file.read_text(encoding="utf-8-sig")
        except UnicodeError:
            raise DownloadError(f"{env_file}: not UTF-8 text; save it as UTF-8") from None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export ") :]
            name, sep, value = line.partition("=")
            if sep and name.strip() == c.TOKEN_ENV_VAR:
                token = value.strip().strip("'\"")
    if not token:
        raise DownloadError(
            f"no token: set {c.TOKEN_ENV_VAR} in the environment or in an env file (--env-file)"
        )
    if any(ch.isspace() for ch in token):
        raise DownloadError(f"{c.TOKEN_ENV_VAR} contains spaces: keep only the token on that line, no comment")
    return token


def make_client(token: str | None = None, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Build the shared HTTP client.

    One client serves all worker threads. It follows redirects and keeps
    cookies, as LAADS requires for token downloads. ``httpx`` drops the
    ``Authorization`` header when a redirect leaves the original host, and
    every URL this module requests is built from ``LAADS_ARCHIVE_URL``, so
    the token goes to the archive host only.

    Parameters
    ----------
    token : str, optional
        Bearer token. Omit for listings, which are public.
    transport : httpx.BaseTransport, optional
        For tests: a mock transport in place of the network.

    Returns
    -------
    httpx.Client
        Close it when done (use as a context manager).
    """
    headers = {"User-Agent": c.USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(c.READ_TIMEOUT_S, connect=c.CONNECT_TIMEOUT_S),
        transport=transport,
    )


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds asked for by a numeric ``Retry-After`` header, capped at ``BACKOFF_CAP_S``."""
    value = response.headers.get("Retry-After", "")
    return min(float(value), c.BACKOFF_CAP_S) if value.isdigit() else None


def with_retry(
    action: Callable[[], httpx.Response | None],
    what: str,
    sleep: Sleep | None = None,
) -> httpx.Response | None:
    """Run ``action`` until it succeeds, cannot succeed, or attempts run out.

    Parameters
    ----------
    action : callable
        Performs one attempt. Returns a response, or ``None`` when it has
        handled the body itself (streaming). May raise
        ``httpx.HTTPStatusError`` for a bad status and any other
        ``httpx.HTTPError`` for network and protocol faults.
    what : str
        Short label for log lines. Must not contain the token.
    sleep : callable, optional
        Waits the given seconds. Default ``time.sleep``; injected in tests.

    Returns
    -------
    httpx.Response or None
        Whatever ``action`` returned on its successful attempt.

    Raises
    ------
    AuthError
        HTTP 403, or HTTP 401 on every attempt.
    DownloadError
        Any other status that will not improve (for example 404), a
        protocol fault such as a redirect loop, or ``MAX_ATTEMPTS`` spent.
    """
    sleep = sleep or time.sleep
    last, last_status = "no attempt made", 0
    for attempt in range(1, c.MAX_ATTEMPTS + 1):
        wait: float | None = None
        try:
            return action()
        except httpx.HTTPStatusError as exc:
            last_status = exc.response.status_code
            last = f"HTTP {last_status}"
            if last_status not in c.RETRY_STATUSES:
                raise (AuthError if last_status == 403 else DownloadError)(f"{what}: {last}") from None
            wait = _retry_after(exc.response)
        except (httpx.TransportError, _Incomplete) as exc:
            last, last_status = f"{type(exc).__name__}: {exc}", 0
        except httpx.HTTPError as exc:
            # Redirect loops, undecodable bodies: repeating will not help.
            raise DownloadError(f"{what}: {type(exc).__name__}") from None
        if attempt < c.MAX_ATTEMPTS:
            delay = wait if wait is not None else backoff_seconds(attempt)
            log.warning("%s: %s; attempt %d of %d, waiting %.0f s", what, last, attempt, c.MAX_ATTEMPTS, delay)
            sleep(delay)
    error = AuthError if last_status == 401 else DownloadError
    raise error(f"{what}: gave up after {c.MAX_ATTEMPTS} attempts ({last})")


def list_granules(
    client: httpx.Client,
    product: str,
    date: dt.date,
    sleep: Sleep | None = None,
) -> list[Granule]:
    """All tiled granules LAADS holds for one product and folder date.

    Parameters
    ----------
    client : httpx.Client
        No token needed.
    product : str
        Short name.
    date : datetime.date
        Folder date (see :func:`period_dates`).
    sleep : callable, optional
        Passed to :func:`with_retry`.

    Returns
    -------
    list of Granule
        Empty when the folder does not exist (HTTP 404): the archive has
        nothing for that date. Download addresses are built from the
        archive root and the file name, not taken from the listing.

    Raises
    ------
    DownloadError
        If the listing cannot be fetched or is not a LAADS JSON listing.
    """
    folder = directory_url(product, date)

    def attempt() -> httpx.Response:
        response = client.get(folder + ".json")
        if response.status_code != 404:
            response.raise_for_status()
        return response

    response = with_retry(attempt, f"listing {product} {date}", sleep)
    assert response is not None
    if response.status_code == 404:
        return []
    try:
        entries = response.json()["content"]
        granules = []
        for entry in entries:
            parsed = parse_granule_name(str(entry["name"]))
            if parsed is None or parsed[0] != product:
                continue
            granules.append(Granule(product, parsed[1], parsed[2], entry["name"], f"{folder}/{entry['name']}", int(entry["size"])))
    except (ValueError, KeyError, TypeError):
        # LAADS answers some faults with an HTML page and status 200.
        raise DownloadError(f"listing {product} {date}: reply is not a LAADS JSON listing") from None
    return granules


def find_granules(
    client: httpx.Client,
    product: str,
    dates: Iterable[dt.date],
    tiles: Sequence[Tile],
    workers: int = c.DEFAULT_WORKERS,
    sleep: Sleep | None = None,
) -> tuple[list[Granule], list[Outcome]]:
    """Resolve a request into granules to fetch and gaps to report.

    Parameters
    ----------
    client : httpx.Client
        No token needed.
    product : str
        Short name.
    dates : iterable of datetime.date
        Folder dates.
    tiles : sequence of Tile
        Tiles wanted.
    workers : int
        Listings fetched at once.
    sleep : callable, optional
        Passed to :func:`with_retry`.

    Returns
    -------
    granules : list of Granule
        One per (date, tile) found, sorted by date then tile. If the archive
        holds more than one production of the same tile and date, the latest
        production stamp is kept.
    gaps : list of Outcome
        ``missing`` for each (date, tile) the archive does not hold, and
        ``failed`` for each date whose listing could not be read.
    """
    wanted = set(tiles)
    granules: list[Granule] = []
    gaps: list[Outcome] = []

    def one(date: dt.date) -> tuple[dt.date, list[Granule] | DownloadError]:
        try:
            return date, list_granules(client, product, date, sleep)
        except DownloadError as exc:
            return date, exc

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for date, result in pool.map(one, list(dates)):
            if isinstance(result, DownloadError):
                gaps.extend(Outcome("failed", product, date, t.id, detail=str(result)) for t in sorted(wanted))
                continue
            latest: dict[Tile, Granule] = {}
            for granule in result:
                # Names sort by production stamp within a tile and date.
                if granule.tile in wanted and (granule.tile not in latest or granule.name > latest[granule.tile].name):
                    latest[granule.tile] = granule
            granules.extend(latest[t] for t in sorted(latest))
            gaps.extend(Outcome("missing", product, date, t.id) for t in sorted(wanted - latest.keys()))
    return granules, gaps


def _sha256(path: Path) -> str:
    """SHA-256 of a file as lowercase hex, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(c.CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Manifest:
    """Append-only record of finished files, one JSON object per line.

    Thread-safe. Holds file facts only: no header, token or cookie is ever
    passed to it.

    Parameters
    ----------
    path : Path
        The ``.jsonl`` file. Created on first write. Existing rows are read
        once so that a file already recorded is not recorded twice.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._names: set[str] = set()
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    self._names.add(json.loads(line)["name"])
                except (ValueError, KeyError, TypeError):
                    log.warning("manifest %s: unreadable row ignored", path)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._names

    def add(self, granule: Granule, sha256: str) -> None:
        """Record one finished granule with its checksum and the time now (UTC)."""
        row = {
            "name": granule.name,
            "product": granule.product,
            "date": granule.date.isoformat(),
            "tile": granule.tile.id,
            "url": granule.url,
            "bytes": granule.size,
            "sha256": sha256,
            "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            self._names.add(granule.name)


class AuthGuard:
    """Stops a batch when failures in a row point at the token.

    Thread-safe. ``AUTH_FAILURES_BEFORE_STOP`` consecutive :class:`AuthError`
    results trip it; any success resets the count.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run = 0
        self.tripped = threading.Event()

    def record(self, auth_failure: bool) -> None:
        """Count one finished transfer."""
        with self._lock:
            self._run = self._run + 1 if auth_failure else 0
            if self._run >= c.AUTH_FAILURES_BEFORE_STOP and not self.tripped.is_set():
                self.tripped.set()
                log.error("stopping: %d files in a row were refused. The token may have expired (they last 60 days)", self._run)


def is_complete(granule: Granule, root: Path) -> bool:
    """True if the final file exists with the size the listing gave."""
    final = root / granule.relative_path()
    return final.is_file() and final.stat().st_size == granule.size


def _fetch_once(client: httpx.Client, granule: Granule, part: Path) -> None:
    """One attempt to bring ``part`` up to the listed size, then check it.

    Raises ``_Incomplete`` for anything another attempt may cure,
    ``AuthError`` when a page arrives in place of the file,
    ``DownloadError`` for a size that can never match, and httpx errors.
    A good partial file is never overwritten by a reply that is not HDF5.
    """
    signature = c.HDF5_SIGNATURE
    have = part.stat().st_size if part.exists() else 0
    if have > granule.size:  # a stale or foreign partial: start over
        part.unlink()
        have = 0
    if have < granule.size:
        headers = {"Range": f"bytes={have}-"} if have else {}
        with client.stream("GET", granule.url, headers=headers) as response:
            if response.status_code == 416:
                # The server holds fewer bytes than the partial claims.
                part.unlink(missing_ok=True)
                raise _Incomplete("range refused; restarting from zero")
            response.raise_for_status()
            resumed = response.status_code == 206
            if resumed:
                match = _CONTENT_RANGE.match(response.headers.get("Content-Range", ""))
                if match is None or int(match.group(1)) != have:
                    part.unlink(missing_ok=True)
                    raise _Incomplete("server sent a different range; restarting from zero")
            handle = None
            try:
                for chunk in response.iter_bytes(c.CHUNK_BYTES):
                    if handle is None:
                        # A full reply must start like an HDF5 file before
                        # it may replace anything on disk.
                        if not resumed and len(chunk) >= len(signature) and not chunk.startswith(signature):
                            raise AuthError(f"{granule.name}: reply is not an HDF5 file (check the token)")
                        handle = part.open("ab" if resumed else "wb")
                    handle.write(chunk)
            finally:
                if handle is not None:
                    handle.close()
    got = part.stat().st_size if part.exists() else 0
    if got < len(signature):
        raise _Incomplete(f"{got} bytes received")
    with part.open("rb") as handle:
        if handle.read(len(signature)) != signature:
            part.unlink()
            raise AuthError(f"{granule.name}: reply is not an HDF5 file (check the token)")
    if got < granule.size:
        raise _Incomplete(f"{got} of {granule.size} bytes")
    if got > granule.size:
        part.unlink()
        raise DownloadError(f"{granule.name}: {got} bytes received, listing says {granule.size}")


def download_granule(
    client: httpx.Client,
    granule: Granule,
    root: Path,
    manifest: Manifest,
    sleep: Sleep | None = None,
    guard: AuthGuard | None = None,
) -> Outcome:
    """Fetch one granule to ``root``, resuming and verifying.

    Skips a file already complete (recording it if the manifest lacks it);
    otherwise streams to ``<name>.part``, continuing from bytes already
    there, checks size and HDF5 signature, renames, and records.

    Parameters
    ----------
    client : httpx.Client
        Carries the token.
    granule : Granule
        What to fetch.
    root : Path
        Data root. The file lands at ``root / granule.relative_path()``.
    manifest : Manifest
        Receives one row for the finished file.
    sleep : callable, optional
        Passed to :func:`with_retry`.
    guard : AuthGuard, optional
        Shared across a batch. When tripped, the transfer is not attempted.

    Returns
    -------
    Outcome
        ``downloaded``, ``skipped`` or ``failed``. Never raises for a
        transfer or disk problem: one bad file must not stop the batch.
    """
    final = root / granule.relative_path()
    part = final.with_name(final.name + ".part")
    result = dict(product=granule.product, date=granule.date, tile=granule.tile.id, name=granule.name)
    auth_failure = False
    try:
        if is_complete(granule, root):
            if granule.name not in manifest:
                manifest.add(granule, _sha256(final))
            return Outcome("skipped", **result)
        if guard is not None and guard.tripped.is_set():
            return Outcome("failed", detail="not attempted: batch stopped after repeated refusals", **result)
        final.parent.mkdir(parents=True, exist_ok=True)
        with_retry(lambda: _fetch_once(client, granule, part), granule.name, sleep)
        digest = _sha256(part)
        # Record first, then rename: a crash between the two leaves a row
        # for a file still named .part, which the next run completes.
        if granule.name not in manifest:
            manifest.add(granule, digest)
        os.replace(part, final)
    except (DownloadError, OSError, httpx.HTTPError) as exc:
        auth_failure = isinstance(exc, AuthError)
        detail = str(exc) if isinstance(exc, (DownloadError, OSError)) else type(exc).__name__
        log.error("failed: %s", detail)
        return Outcome("failed", detail=detail, **result)
    finally:
        if guard is not None:
            guard.record(auth_failure)
    log.info("downloaded %s (%.1f MB)", granule.name, granule.size / 1e6)
    return Outcome("downloaded", **result)


def download_all(
    client: httpx.Client,
    granules: Sequence[Granule],
    root: Path,
    workers: int = c.DEFAULT_WORKERS,
    sleep: Sleep | None = None,
) -> list[Outcome]:
    """Fetch many granules in parallel.

    Parameters
    ----------
    client : httpx.Client
        Carries the token; shared by all workers.
    granules : sequence of Granule
        What to fetch.
    root : Path
        Data root.
    workers : int
        Transfers at once.
    sleep : callable, optional
        Passed to :func:`with_retry`.

    Returns
    -------
    list of Outcome
        One per granule, in order of completion.

    Notes
    -----
    Ctrl-C cancels everything not yet started and re-raises; transfers in
    flight finish their current attempt. Partial files stay for the next run.
    """
    manifest = Manifest(root / c.BLACK_MARBLE_DIR / c.MANIFEST_NAME)
    guard = AuthGuard()
    outcomes: list[Outcome] = []
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [pool.submit(download_granule, client, g, root, manifest, sleep, guard) for g in granules]
        for done, future in enumerate(as_completed(futures), start=1):
            outcomes.append(future.result())
            if done % c.PROGRESS_EVERY == 0 or done == len(futures):
                log.info("progress: %d of %d", done, len(futures))
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return outcomes


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ntl.download",
        description="Download NASA Black Marble granules from LAADS for a region and period, "
        "in parallel, with retry, resume and verification.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    products = "; ".join(f"{p.short_name}: {p.description}" for p in c.PRODUCTS.values())
    parser.add_argument("--product", required=True, choices=sorted(c.PRODUCTS), help=products)
    parser.add_argument("--start", required=True, type=dt.date.fromisoformat, help="first date, YYYY-MM-DD, e.g. 2018-08-01")
    parser.add_argument("--end", required=True, type=dt.date.fromisoformat, help="last date, YYYY-MM-DD, inclusive")
    region = parser.add_mutually_exclusive_group(required=True)
    region.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                        help="bounding box in degrees, e.g. 115.5 -9.2 117.0 -8.0; every tile it touches is fetched whole")
    region.add_argument("--tiles", nargs="+", metavar="hHHvVV", help="tile ids, e.g. h29v09 h30v09")
    region.add_argument("--indonesia", action="store_true", help=f"the project box {c.INDONESIA_BBOX} (18 tiles)")
    parser.add_argument("--root", required=True, type=Path, help=r"data root, e.g. E:\temp\ntl; keep it outside any synced folder")
    parser.add_argument("--workers", type=int, default=c.DEFAULT_WORKERS, help=f"parallel transfers, 1 to {c.MAX_WORKERS} (default {c.DEFAULT_WORKERS})")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help=f"text file with a line {c.TOKEN_ENV_VAR}=... (default ./.env)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop; needs no token")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point.

    Returns
    -------
    int
        0 if every file asked for is on disk or listed (dry run); 1 if
        anything failed or nothing at all was found; 2 for a usage problem.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # The HTTP libraries log every request, and at DEBUG the response
    # headers with session cookies. Keep them out of the log at any level.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    product = c.PRODUCTS[args.product]
    try:
        if not 1 <= args.workers <= c.MAX_WORKERS:
            raise ValueError(f"--workers must be between 1 and {c.MAX_WORKERS}")
        tiles = [parse_tile(t) for t in args.tiles] if args.tiles else tiles_for_bbox(*(args.bbox or c.INDONESIA_BBOX))
        dates = period_dates(product.cadence, args.start, args.end)
    except ValueError as exc:
        parser.error(str(exc))  # exits with status 2
    log.info("%s (%s): %d date(s) x %d tile(s): %s", product.short_name, product.cadence, len(dates), len(tiles), " ".join(t.id for t in tiles))

    # Listings are public, so the plan is built without the token.
    with make_client() as anonymous:
        granules, gaps = find_granules(anonymous, product.short_name, dates, tiles, args.workers)
    log.info("found %d file(s), %.2f GB; %d gap(s)", len(granules), sum(g.size for g in granules) / 1e9, len(gaps))
    for gap in gaps:
        log.warning("%s: %s %s %s %s", gap.status, gap.product, gap.date, gap.tile, gap.detail)
    if not granules:
        log.error("nothing found for this request: check the product, period and tiles")
        return 1

    if args.dry_run:
        for granule in granules:
            print(f"{granule.size:>12}  {granule.name}")
        return 1 if any(g.status == "failed" for g in gaps) else 0

    # A rerun with everything in place needs no token.
    token = None
    if not all(is_complete(g, args.root) for g in granules):
        try:
            token = read_token(args.env_file)
        except DownloadError as exc:
            log.error("%s", exc)
            return 2
    with make_client(token) as client:
        outcomes = download_all(client, granules, args.root, args.workers)

    counts: dict[str, int] = {}
    for outcome in [*outcomes, *gaps]:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
    log.info("done: %s", ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
