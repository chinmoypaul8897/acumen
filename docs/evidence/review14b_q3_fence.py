"""REVIEW_14B probe 1 -- the fenced corporate-action pull, driven on a SCRATCH copy.

The re-review's independent attack on REVIEW_14 **B1/B2** (REVIEW_13B Q3) and on the FIX-2
session's neighbours **B408** (the `refresh_calendar` try/except) and **B409** (the top-up's
`--store`). Nothing here touches the real `data_root`/`cache_root` except to READ the slices it
copies: CLAUDE.md's newest rule -- *a review or any session may NEVER run a mutating CLI against
the real data_root/cache_root; mutations run against a SCRATCH copy only* -- is the rule this
very incident bought, and this script is what obeying it looks like.

WHAT IS MEASURED, in one process:

1. the scratch world is a COPY, not a junction or a symlink (asserted, not assumed);
2. `morning_refresh(..., allow_network=True)` runs with the network stubbed to RAISE and every
   outbound URL recorded -- the corporate-action endpoint must never be among them;
3. the fence is a DOWNGRADE, not a refusal: a **40-day-old** cached window is served, the step
   is ok, and its detail says the events were read rather than pulled;
4. `<cache_root>/ca/` is neither created nor modified -- the directory REVIEW_14 B1 measured a
   real morning accreting a file into every day;
5. both scratch roots are fingerprinted (path, size, mtime_ns, sha256) before and after, and
   every file that moved is named, so the no-write claim is measured over EVERY affected root
   rather than asserted by a test's own name (CLAUDE.md's second new rule);
6. B408: an unreadable published master leaves a REPORT, not a traceback, and the steps that
   need a calendar say NOT RUN by name;
7. B409: the top-up is handed `--store <the store it was given>`, proved by capturing the argv
   the shipped `refresh_daily_store` builds AND by driving the real `daily_backfill.main` on a
   scratch store to see where it writes.

ASCII-only, like every other source file in this repo (chunk-0 B7).

Usage:  python docs/evidence/review14b_q3_fence.py [scratch_root]
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt            # noqa: E402
from acumen import calendar as cal           # noqa: E402
from acumen import corp_actions as ca        # noqa: E402
from acumen import live_refresh as refresh   # noqa: E402
from acumen import nse_http                  # noqa: E402
from acumen.config import load_config        # noqa: E402
from acumen.daily_store import DailyStore    # noqa: E402

DAY = date(2026, 6, 10)
SYMBOLS = ("HDFCBANK", "ICICIBANK")
REPORT: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    REPORT.append(line)


def fingerprint(root: Path) -> dict[str, tuple[int, int, str]]:
    """path -> (size, mtime_ns, sha256). Every file under the root, no exceptions."""
    out: dict[str, tuple[int, int, str]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns, digest)
    return out


def diff(before: dict, after: dict) -> list[str]:
    moved = []
    for rel in sorted(set(before) | set(after)):
        if rel not in before:
            moved.append(f"CREATED {rel}")
        elif rel not in after:
            moved.append(f"REMOVED {rel}")
        elif before[rel] != after[rel]:
            moved.append(f"CHANGED {rel}  {before[rel]} -> {after[rel]}")
    return moved


def build_scratch(root: Path) -> Path:
    """Copy the slices of BOTH roots a pre-open reads. shutil.copy* only -- never a link."""
    config = load_config(include_env=False)
    real_data, real_cache = config.path("data_root"), config.path("cache_root")
    data, cache = root / "data", root / "cache"

    (data / "daily_store").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "daily_store" / "ledger.parquet",
                    data / "daily_store" / "ledger.parquet")
    for year in (2025, 2026):
        source = real_data / "daily_store" / "daily" / str(year)
        if source.is_dir():
            shutil.copytree(source, data / "daily_store" / "daily" / str(year),
                            dirs_exist_ok=True)
    shutil.copytree(real_data / "nse", data / "nse")
    (data / "universe_backfill").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "universe_backfill" / "ledger.json",
                    data / "universe_backfill" / "ledger.json")

    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    pin = real_cache / "instrument_master" / config.instrument_master
    shutil.copyfile(pin, cache / "instrument_master" / config.instrument_master)

    payload = json.loads(
        (REPO / "tests" / "fixtures" / "holidays_2026.json").read_text(encoding="utf-8")
    )
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY
    )
    return root


def plant_a_forty_day_old_ca_cache(cache_root: Path) -> Path:
    """The window `morning_refresh` will ask for, cached 40 days ago, holding a REAL event.

    Deliberately NOT the fix session's own fixture: an empty payload cannot show whether the
    cache was read or merely tolerated. This one carries a bonus whose ex-date sits inside the
    window, so a served cache is visible in the step's own arithmetic.
    """
    window_start = DAY - timedelta(days=refresh.DEFAULT_LOOKBACK_DAYS)
    name = f"nse_ca_{window_start.isoformat()}_{DAY.isoformat()}.json"
    path = ca.cache_path(cache_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [{
        "symbol": "HDFCBANK", "series": "EQ", "subject": "BONUS 1:1",
        "exDate": (DAY - timedelta(days=3)).strftime("%d-%b-%Y"),
        "recDate": "", "comp": "HDFC Bank",
    }]
    nse_http.write_cache(
        path, body, url=ca.nse_url(window_start, DAY),
        fetched_on=DAY - timedelta(days=40),
    )
    return path


class Blocked(RuntimeError):
    """Every outbound call this probe stubs raises this, and every one is recorded."""


def stub_the_network(attempts: list[str]):
    """Record and refuse at every layer the pre-open could reach out through."""
    originals = {
        "fetch_json": nse_http.fetch_json,
        "fetch_binary": nse_http.fetch_binary,
        "cached_json_fetch": nse_http.cached_json_fetch,
        "socket": socket.socket.connect,
    }

    def refuse_json(url, *args, **kwargs):
        attempts.append(url)
        raise Blocked(f"probe: the network is stubbed ({url})")

    def refuse_socket(self, address, *args, **kwargs):
        attempts.append(f"SOCKET {address}")
        raise Blocked(f"probe: the socket layer is stubbed ({address})")

    nse_http.fetch_json = refuse_json
    nse_http.fetch_binary = refuse_json
    nse_http.cached_json_fetch = refuse_json
    socket.socket.connect = refuse_socket
    return originals


def restore_the_network(originals: dict) -> None:
    nse_http.fetch_json = originals["fetch_json"]
    nse_http.fetch_binary = originals["fetch_binary"]
    nse_http.cached_json_fetch = originals["cached_json_fetch"]
    socket.socket.connect = originals["socket"]


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(tempfile.mkdtemp(prefix="review14b-"))
    root.mkdir(parents=True, exist_ok=True)
    say("REVIEW_14B PROBE 1 -- the fenced CA pull, on a scratch copy of BOTH roots")
    say("=" * 78)
    say(f"scratch root: {root}")

    build_scratch(root)
    data_root, cache_root = root / "data", root / "cache"

    # 1. THE COPY IS A COPY.
    links = [p for p in root.rglob("*") if p.is_symlink()]
    say("")
    say("1. THE SCRATCH WORLD")
    say(f"   symlinks/junctions found : {len(links)}  (CLAUDE.md: a COPY, never a link)")
    real_data = load_config(include_env=False).path("data_root")
    say(f"   real data_root           : {real_data}")
    say(f"   scratch data_root        : {data_root}")
    say(f"   disjoint trees           : "
        f"{not str(data_root).lower().startswith(str(real_data).lower())}")

    planted = plant_a_forty_day_old_ca_cache(cache_root)
    envelope = json.loads(planted.read_text(encoding="utf-8"))
    say(f"   planted CA day-cache     : {planted.relative_to(root).as_posix()}")
    say(f"   its fetched_on           : {envelope.get('fetched_on')}  "
        f"(= {DAY.isoformat()} minus 40 days)")

    # 2. THE FENCE'S OWN JUDGMENT, on the roots the job runs under.
    say("")
    say("2. THE FENCE, ASKED THE WAY morning_refresh ASKS IT")
    resolved, network, reason = bt.fence_ca_cache(
        cache_dir=cache_root, allow_network=True,
        data_root=data_root, cache_root=cache_root,
    )
    say(f"   resolved      : {resolved}")
    say(f"   may_network   : {network}   <- False is the downgrade")
    say(f"   reason        : {reason}")

    outside = Path(tempfile.mkdtemp(prefix="review14b-outside-"))
    _r, out_net, out_reason = bt.fence_ca_cache(
        cache_dir=outside, allow_network=True, data_root=data_root, cache_root=cache_root,
    )
    say(f"   control (a cache OUTSIDE both roots): may_network={out_net}  {out_reason}")

    # 3. DRIVE THE REAL morning_refresh WITH THE NETWORK STUBBED TO RAISE.
    say("")
    say("3. morning_refresh(allow_network=True) -- the shipped pre-open, network stubbed")
    before_data, before_cache = fingerprint(data_root), fingerprint(cache_root)
    attempts: list[str] = []
    originals = stub_the_network(attempts)
    try:
        calendar, universe, report = refresh.morning_refresh(
            today=DAY,
            store=DailyStore.at(data_root / "daily_store"),
            cache_dir=cache_root,
            allow_network=True,
            symbols=SYMBOLS,
            recording_root=root / "recordings",
        )
    finally:
        restore_the_network(originals)
    after_data, after_cache = fingerprint(data_root), fingerprint(cache_root)

    steps = {step.name: step for step in report.steps}
    for name, step in steps.items():
        say(f"   [{'ok' if step.ok else 'FAIL'}] {name}")
        say(f"        {step.detail[:300]}")

    ca_step = steps["corporate actions"]
    say("")
    say(f"   CA step ok            : {ca_step.ok}")
    say(f"   CA step fenced        : {ca_step.figures.get('fenced')}")
    say(f"   CA events_total       : {ca_step.figures.get('events_total')}"
        "   <- the 40-day cache was READ, not refused")
    say(f"   CA events_for_universe: {ca_step.figures.get('events_for_universe')}")

    # 4. THE URL WAS NEVER ATTEMPTED.
    ca_url = ca.nse_url(DAY - timedelta(days=refresh.DEFAULT_LOOKBACK_DAYS), DAY)
    say("")
    say("4. WHAT THE PRE-OPEN REACHED FOR")
    say(f"   the CA endpoint            : {ca_url}")
    say(f"   attempted?                 : {ca_url in attempts}")
    say(f"   outbound attempts recorded : {len(attempts)}")
    for url in dict.fromkeys(attempts):
        say(f"        {url[:150]}")

    # 5. WHAT MOVED UNDER EITHER SCRATCH ROOT.
    say("")
    say("5. EVERY FILE THAT MOVED, under BOTH scratch roots")
    moved_data = diff(before_data, after_data)
    moved_cache = diff(before_cache, after_cache)
    say(f"   data_root  : {len(moved_data)} file(s) moved of {len(after_data)}")
    for line in moved_data:
        say(f"        {line[:200]}")
    say(f"   cache_root : {len(moved_cache)} file(s) moved of {len(after_cache)}")
    for line in moved_cache:
        say(f"        {line[:200]}")
    ca_dir_files = sorted(
        p.relative_to(cache_root).as_posix() for p in (cache_root / "ca").rglob("*")
        if p.is_file()
    )
    say(f"   <cache_root>/ca contents   : {ca_dir_files}  (the planted file, unmoved)")
    say(f"   <cache_root>/ca touched?   : "
        f"{any(line.split()[1].startswith('ca/') for line in moved_cache)}")

    # 6. B408 -- an unreadable calendar leaves a REPORT.
    say("")
    say("6. B408 -- the calendar step that used to have no guard")
    empty = Path(tempfile.mkdtemp(prefix="review14b-nocal-"))
    calendar2, universe2, report2 = refresh.morning_refresh(
        today=DAY, store=DailyStore.at(empty / "daily_store"),
        cache_dir=empty / "no-cache-here", allow_network=False, symbols=("AAA",),
        daily_runner=lambda argv: 0, recording_root=empty / "rec",
    )
    say(f"   returned calendar          : {calendar2}")
    say(f"   report.ok                  : {report2.ok}")
    say(f"   steps reported             : {len(report2.steps)}  (none silently dropped)")
    for step in report2.steps:
        mark = "ok" if step.ok else "FAIL"
        say(f"        [{mark}] {step.name:<28} {step.detail[:110]}")

    # 7. B409 -- the top-up writes where it was pointed, proved by driving the real backfill.
    say("")
    say("7. B409 -- WHICH store the bhavcopy top-up tops up")
    seen: list[list[str]] = []
    step = refresh.refresh_daily_store(
        store=DailyStore.at(root / "b409-store"),
        calendar=cal.TradingCalendar.from_holidays([date(2026, 1, 26)], covered_years=[2026]),
        today=date(2026, 8, 7), runner=lambda argv: (seen.append(list(argv)), 0)[1],
    )
    say(f"   argv handed to the backfill: {seen[0]}")
    say(f"   step.figures['store']      : {step.figures.get('store')}")

    from acumen import backfill_daily

    real_before = fingerprint(real_data / "daily_store")
    attempts2: list[str] = []
    originals = stub_the_network(attempts2)
    try:
        code = backfill_daily.main([
            "--from", "2026-08-03", "--to", "2026-08-05",
            "--store", str(root / "b409-store"), "--allow-network",
        ])
    except SystemExit as exc:      # pragma: no cover -- argparse only
        code = int(exc.code or 0)
    except Exception as exc:
        code = f"raised {type(exc).__name__}: {exc}"
    finally:
        restore_the_network(originals)
    real_after = fingerprint(real_data / "daily_store")
    say(f"   the REAL backfill, --store <scratch>, network stubbed -> exit {code}")
    say(f"   files it wrote under the SCRATCH store : "
        f"{len([p for p in (root / 'b409-store').rglob('*') if p.is_file()])}")
    say(f"   files it moved under the REAL daily_store : {len(diff(real_before, real_after))}"
        "   <- must be 0")

    say("")
    say("=" * 78)
    say("END OF PROBE 1")
    (Path(__file__).with_suffix(".out.txt")).write_text(
        "\n".join(REPORT) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
