"""Downloader behaviour against a mock transport. No network, no token."""

import datetime as dt
import json

import httpx
import pytest

from ntl import conventions as c
from ntl import download as d
from ntl.tiles import Tile

FAKE_TOKEN = "not-a-real-token-0123456789"
NAME = "VNP46A2.A2018217.h29v09.002.2025002133145.h5"
BODY = c.HDF5_SIGNATURE + b"x" * 5000
DATE = dt.date(2018, 8, 5)  # day of year 217


def no_sleep(_seconds):
    return None


def granule(size=len(BODY)):
    return d.Granule("VNP46A2", DATE, Tile(29, 9), NAME, f"https://example.test/{NAME}", size)


def client_for(handler):
    return d.make_client(FAKE_TOKEN, transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(d.time, "sleep", no_sleep)


# ---- pure helpers ---------------------------------------------------------


def test_parse_granule_name():
    assert d.parse_granule_name(NAME) == ("VNP46A2", DATE, Tile(29, 9))
    assert d.parse_granule_name("index.html") is None
    assert d.parse_granule_name("VNP46A2.A2018217.h29v09.002.2025002133145.h5.xml") is None


def test_period_dates_daily_is_inclusive():
    days = d.period_dates("daily", dt.date(2018, 7, 30), dt.date(2018, 8, 2))
    assert [x.day for x in days] == [30, 31, 1, 2]


def test_period_dates_monthly_selects_by_overlap():
    months = d.period_dates("monthly", dt.date(2018, 11, 15), dt.date(2019, 2, 1))
    assert months == [dt.date(2018, 11, 1), dt.date(2018, 12, 1), dt.date(2019, 1, 1), dt.date(2019, 2, 1)]
    # A period inside one month still selects that month's composite.
    assert d.period_dates("monthly", dt.date(2018, 8, 5), dt.date(2018, 8, 25)) == [dt.date(2018, 8, 1)]


def test_period_dates_yearly_selects_by_overlap():
    assert d.period_dates("yearly", dt.date(2012, 1, 19), dt.date(2014, 6, 1)) == [
        dt.date(2012, 1, 1), dt.date(2013, 1, 1), dt.date(2014, 1, 1)]
    assert d.period_dates("yearly", dt.date(2012, 3, 1), dt.date(2012, 12, 31)) == [dt.date(2012, 1, 1)]


def test_period_dates_refuses_reversed_period():
    with pytest.raises(ValueError):
        d.period_dates("daily", dt.date(2018, 8, 2), dt.date(2018, 8, 1))


def test_listing_url_uses_day_of_year():
    assert d.listing_url("VNP46A2", DATE).endswith("/5200/VNP46A2/2018/217.json")


def test_backoff_is_capped_and_grows():
    assert d.backoff_seconds(1, rng=lambda: 1.0) == c.BACKOFF_BASE_S
    assert d.backoff_seconds(3, rng=lambda: 1.0) == c.BACKOFF_BASE_S * 4
    assert d.backoff_seconds(50, rng=lambda: 1.0) == c.BACKOFF_CAP_S
    assert d.backoff_seconds(1, rng=lambda: 0.0) == c.BACKOFF_BASE_S / 2


def test_read_token_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)
    env = tmp_path / ".env"
    env.write_text(f'# comment\nOTHER=1\n{c.TOKEN_ENV_VAR}="{FAKE_TOKEN}"\n', encoding="utf-8")
    assert d.read_token(env) == FAKE_TOKEN
    monkeypatch.setenv(c.TOKEN_ENV_VAR, "from-environment")
    assert d.read_token(env) == "from-environment"


def test_read_token_missing_names_variable_only(tmp_path, monkeypatch):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)
    with pytest.raises(d.DownloadError, match=c.TOKEN_ENV_VAR):
        d.read_token(tmp_path / "absent.env")


# ---- listing --------------------------------------------------------------


def listing(names):
    return {"content": [{"name": n, "size": 100 + i, "downloadsLink": f"https://example.test/{n}"} for i, n in enumerate(names)]}


def test_find_granules_filters_tiles_keeps_latest_and_reports_gaps():
    older = "VNP46A2.A2018217.h29v09.002.2024001000000.h5"
    names = [older, NAME, "VNP46A2.A2018217.h00v02.002.2025002133145.h5", "217"]

    def handler(request):
        if request.url.path.endswith("/217.json"):
            return httpx.Response(200, json=listing(names))
        return httpx.Response(404)

    with client_for(handler) as client:
        granules, gaps = d.find_granules(
            client, "VNP46A2", [DATE, DATE + dt.timedelta(days=1)], [Tile(29, 9), Tile(30, 9)])
    assert [g.name for g in granules] == [NAME]
    assert sorted((g.status, g.date.day, g.tile) for g in gaps) == [
        ("missing", 5, "h30v09"), ("missing", 6, "h29v09"), ("missing", 6, "h30v09")]


def test_html_in_place_of_listing_is_a_failure_not_a_gap():
    def handler(request):
        return httpx.Response(200, text="<html>Sign in</html>")

    with client_for(handler) as client:
        granules, gaps = d.find_granules(client, "VNP46A2", [DATE], [Tile(29, 9)])
    assert granules == [] and [g.status for g in gaps] == ["failed"]


# ---- download -------------------------------------------------------------


def test_download_writes_file_and_manifest_without_token(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, content=BODY)

    manifest = d.Manifest(tmp_path / "manifest.jsonl")
    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, manifest)
    final = tmp_path / granule().relative_path()
    assert outcome.status == "downloaded"
    assert final.read_bytes() == BODY
    assert not final.with_name(final.name + ".part").exists()
    assert seen == [f"Bearer {FAKE_TOKEN}"]
    row = json.loads(manifest.path.read_text(encoding="utf-8"))
    assert row["bytes"] == len(BODY) and len(row["sha256"]) == 64
    assert FAKE_TOKEN not in manifest.path.read_text(encoding="utf-8")


def test_complete_file_is_skipped_without_a_request(tmp_path):
    final = tmp_path / granule().relative_path()
    final.parent.mkdir(parents=True)
    final.write_bytes(BODY)

    def handler(request):
        raise AssertionError("no request expected")

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"))
    assert outcome.status == "skipped"


def test_transient_401_and_503_are_retried(tmp_path):
    replies = iter([httpx.Response(401), httpx.Response(503), httpx.Response(200, content=BODY)])
    calls = []

    def handler(request):
        calls.append(1)
        return next(replies)

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "downloaded" and len(calls) == 3


def test_410_is_not_retried(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(410)

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "failed" and "410" in outcome.detail and len(calls) == 1


def test_404_on_a_listed_file_is_retried(tmp_path):
    # Seen live: a listed, "Online" file answered 404, then downloaded.
    replies = iter([httpx.Response(404), httpx.Response(200, content=BODY)])
    with client_for(lambda request: next(replies)) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "downloaded"


def test_persistent_404_is_reported_after_all_attempts(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "failed" and "404" in outcome.detail and len(calls) == c.MAX_ATTEMPTS


def test_sign_in_page_is_rejected_and_removed(tmp_path):
    def handler(request):
        return httpx.Response(200, content=b"<html>Earthdata Login</html>")

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    final = tmp_path / granule().relative_path()
    assert outcome.status == "failed" and "not an HDF5 file" in outcome.detail
    assert not final.exists() and not final.with_name(final.name + ".part").exists()
    assert FAKE_TOKEN not in outcome.detail


def test_partial_file_is_resumed_with_a_range_request(tmp_path):
    final = tmp_path / granule().relative_path()
    final.parent.mkdir(parents=True)
    part = final.with_name(final.name + ".part")
    part.write_bytes(BODY[:1000])
    ranges = []

    def handler(request):
        ranges.append(request.headers.get("Range"))
        return httpx.Response(206, content=BODY[1000:], headers={"Content-Range": f"bytes 1000-{len(BODY) - 1}/{len(BODY)}"})

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "downloaded" and ranges == ["bytes=1000-"]
    assert final.read_bytes() == BODY


def test_short_transfer_is_retried_then_reported(tmp_path):
    def handler(request):
        # Always one byte short of the listed size, ignoring any range.
        return httpx.Response(200, content=BODY[:-1])

    with client_for(handler) as client:
        outcome = d.download_granule(client, granule(), tmp_path, d.Manifest(tmp_path / "m.jsonl"), sleep=no_sleep)
    assert outcome.status == "failed" and "gave up" in outcome.detail
    assert not (tmp_path / granule().relative_path()).exists()


def test_dry_run_needs_no_token(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)

    def handler(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=listing([NAME]))

    real = d.make_client
    monkeypatch.setattr(d, "make_client", lambda token=None: real(token, transport=httpx.MockTransport(handler)))
    code = d.main(["--product", "VNP46A2", "--start", "2018-08-05", "--end", "2018-08-05",
                   "--tiles", "h29v09", "--root", str(tmp_path), "--dry-run"])
    assert code == 0 and NAME in capsys.readouterr().out


# ---- behaviour added after the 2026-11-22 standards review ----------------


def run_one(tmp_path, handler, size=len(BODY)):
    manifest = d.Manifest(tmp_path / "m.jsonl")
    with client_for(handler) as client:
        return d.download_granule(client, granule(size), tmp_path, manifest, sleep=no_sleep), manifest


def part_path(tmp_path):
    final = tmp_path / granule().relative_path()
    return final.with_name(final.name + ".part")


def test_env_file_with_byte_order_mark(tmp_path, monkeypatch):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)
    env = tmp_path / ".env"
    env.write_bytes(b"\xef\xbb\xbf" + f"{c.TOKEN_ENV_VAR}={FAKE_TOKEN}\r\n".encode())
    assert d.read_token(env) == FAKE_TOKEN


def test_env_file_problems_are_reported_without_the_value(tmp_path, monkeypatch):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)
    utf16 = tmp_path / "utf16.env"
    utf16.write_text(f"{c.TOKEN_ENV_VAR}={FAKE_TOKEN}\n", encoding="utf-16")
    with pytest.raises(d.DownloadError, match="UTF-8"):
        d.read_token(utf16)
    commented = tmp_path / "commented.env"
    commented.write_text(f"{c.TOKEN_ENV_VAR}={FAKE_TOKEN} # my token\n", encoding="utf-8")
    with pytest.raises(d.DownloadError) as caught:
        d.read_token(commented)
    assert FAKE_TOKEN not in str(caught.value)


def test_download_address_is_built_from_the_archive_root_not_the_listing():
    def handler(request):
        return httpx.Response(200, json={"content": [
            {"name": NAME, "size": 10, "downloadsLink": f"https://elsewhere.example/{NAME}"}]})

    with client_for(handler) as client:
        found = d.list_granules(client, "VNP46A2", DATE)
    assert found[0].url == f"{c.LAADS_ARCHIVE_URL}/5200/VNP46A2/2018/217/{NAME}"


def test_listing_entry_without_size_is_a_failure():
    def handler(request):
        return httpx.Response(200, json={"content": [{"name": NAME}]})

    with client_for(handler) as client, pytest.raises(d.DownloadError):
        d.list_granules(client, "VNP46A2", DATE)


def test_range_refused_restarts_from_zero(tmp_path):
    part = part_path(tmp_path)
    part.parent.mkdir(parents=True)
    part.write_bytes(BODY[:1000])
    seen = []

    def handler(request):
        seen.append(request.headers.get("Range"))
        return httpx.Response(416) if "Range" in request.headers else httpx.Response(200, content=BODY)

    outcome, _ = run_one(tmp_path, handler)
    assert outcome.status == "downloaded" and seen == ["bytes=1000-", None]


def test_wrong_content_range_is_not_appended(tmp_path):
    part = part_path(tmp_path)
    part.parent.mkdir(parents=True)
    part.write_bytes(BODY[:1000])

    def handler(request):
        if "Range" in request.headers:  # claims 206 but sends from byte 0
            return httpx.Response(206, content=BODY, headers={"Content-Range": f"bytes 0-{len(BODY) - 1}/{len(BODY)}"})
        return httpx.Response(200, content=BODY)

    outcome, _ = run_one(tmp_path, handler)
    assert outcome.status == "downloaded"
    assert (tmp_path / granule().relative_path()).read_bytes() == BODY


def test_page_in_reply_to_a_resume_keeps_the_good_partial(tmp_path):
    part = part_path(tmp_path)
    part.parent.mkdir(parents=True)
    part.write_bytes(BODY[:1000])

    def handler(request):
        return httpx.Response(200, content=b"<html>Earthdata Login</html>")

    outcome, _ = run_one(tmp_path, handler)
    assert outcome.status == "failed" and part.read_bytes() == BODY[:1000]


def test_transfer_cut_inside_the_signature_is_retried_not_blamed_on_the_token(tmp_path):
    replies = iter([httpx.Response(200, content=BODY[:3]), httpx.Response(200, content=BODY)])
    outcome, _ = run_one(tmp_path, lambda request: next(replies))
    assert outcome.status == "downloaded"


def test_retry_after_is_capped(tmp_path):
    waits = []
    replies = iter([httpx.Response(503, headers={"Retry-After": "86400"}), httpx.Response(200, content=BODY)])
    manifest = d.Manifest(tmp_path / "m.jsonl")
    with client_for(lambda request: next(replies)) as client:
        d.download_granule(client, granule(), tmp_path, manifest, sleep=waits.append)
    assert waits == [c.BACKOFF_CAP_S]


def test_redirect_loop_fails_one_file_without_raising(tmp_path):
    def handler(request):
        return httpx.Response(302, headers={"Location": str(request.url)})

    outcome, _ = run_one(tmp_path, handler)
    assert outcome.status == "failed" and "TooManyRedirects" in outcome.detail


def test_skipped_file_gets_its_missing_manifest_row(tmp_path):
    final = tmp_path / granule().relative_path()
    final.parent.mkdir(parents=True)
    final.write_bytes(BODY)

    def handler(request):
        raise AssertionError("no request expected")

    outcome, manifest = run_one(tmp_path, handler)
    assert outcome.status == "skipped" and NAME in manifest
    run_one(tmp_path, handler)  # a second run adds nothing
    assert len(manifest.path.read_text(encoding="utf-8").splitlines()) == 1


def test_batch_stops_after_repeated_refusals(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(403)

    granules = [
        d.Granule("VNP46A2", DATE + dt.timedelta(days=i), Tile(29, 9),
                  f"VNP46A2.A2018{217 + i}.h29v09.002.1.h5", f"https://example.test/{i}", len(BODY))
        for i in range(10)
    ]
    with client_for(handler) as client:
        outcomes = d.download_all(client, granules, tmp_path, workers=1, sleep=no_sleep)
    assert all(o.status == "failed" for o in outcomes)
    assert len(calls) == c.AUTH_FAILURES_BEFORE_STOP
    assert sum("not attempted" in o.detail for o in outcomes) == 10 - c.AUTH_FAILURES_BEFORE_STOP


def test_token_never_reaches_the_log(tmp_path, caplog):
    replies = iter([httpx.Response(401), httpx.Response(200, content=b"<html>login</html>")])
    with caplog.at_level("DEBUG"):
        run_one(tmp_path, lambda request: next(replies))
    assert caplog.records and FAKE_TOKEN not in caplog.text and "Bearer" not in caplog.text


@pytest.mark.parametrize("extra", [
    ["--start", "2018-08-06", "--end", "2018-08-05", "--tiles", "h29v09"],
    ["--start", "2018-08-05", "--end", "2018-08-05", "--tiles", "h99v09"],
    ["--start", "2018-08-05", "--end", "2018-08-05", "--bbox", "120", "-9", "110", "-8"],
    ["--start", "2018-08-05", "--end", "2018-08-05", "--tiles", "h29v09", "--workers", "99"],
])
def test_bad_arguments_exit_with_usage_error(tmp_path, extra):
    with pytest.raises(SystemExit) as caught:
        d.main(["--product", "VNP46A2", "--root", str(tmp_path), "--dry-run", *extra])
    assert caught.value.code == 2


def test_rerun_with_everything_in_place_needs_no_token(monkeypatch, tmp_path):
    monkeypatch.delenv(c.TOKEN_ENV_VAR, raising=False)
    final = tmp_path / d.Granule("VNP46A2", DATE, Tile(29, 9), NAME, "", 0).relative_path()
    final.parent.mkdir(parents=True)
    final.write_bytes(BODY)

    def handler(request):
        assert request.url.path.endswith(".json")
        return httpx.Response(200, json={"content": [{"name": NAME, "size": len(BODY)}]})

    real = d.make_client
    monkeypatch.setattr(d, "make_client", lambda token=None: real(token, transport=httpx.MockTransport(handler)))
    code = d.main(["--product", "VNP46A2", "--start", "2018-08-05", "--end", "2018-08-05",
                   "--tiles", "h29v09", "--root", str(tmp_path), "--env-file", str(tmp_path / "none.env")])
    assert code == 0
