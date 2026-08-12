"""Chunk 13 FIX-2 evidence: the LIVE path, started on TODAY and run end to end.

REVIEW_13's verdict named the coverage gap that let a green suite pass over a live half that had
never run:

    "no test, evidence document or artefact anywhere in the repo ever successfully constructs
     build_live_screener(mode='live'). The two places that call it both assert a refusal."

and **B6** named why it could not have:

    "build_live_screener calls bt.build_runner(symbols, day, day, ...), which derives its
     calendar from the DAILY STORE over [day-30, day]. A derived calendar refuses any range
     holding a date it has never attempted. On a live morning that date is TODAY, and today's
     bhavcopy cannot exist during today."

    python docs/evidence/chunk13_fix2_live_morning.py

This document is that artefact. It runs, in order:

**PART 1 -- the refusal, still correct.** The store-derived calendar is asked for TODAY and
refuses, in its own words. That refusal is Q-3 safeguard 1 and it must not weaken by one date;
what changed is that a live morning no longer asks it a question only the published master can
answer.

**PART 2 -- a live morning STARTS on a today-dated run.** ``--mode live --day <today>
--preflight-only`` reaches its preflight instead of exiting 1. It is a real invocation of the
shipped CLI.

**PART 3 -- a whole live morning, end to end, on a REPLAYED TODAY.** ``--mode live`` over a real
symbol-day: seventeen boundary sweeps and the close-out poll, through ``run_day()``, with the
oracle-free battery per sweep, the pinned POC, the settled-universe filter, the disclosed line
on every alert, and the recording and dashboards written.

**READ-ONLY over the stores.** Everything a live morning needs that the real cache does not have
-- THE DAY'S OWN instrument master (Q-29) and the published holiday master (B6) -- is placed in
a SCRATCH ``cache_root`` under a temporary directory, by COPY and never by link (CLAUDE.md's
data-store safety). ``data_root`` is opened read-only; the recordings are written outside it.
Two things are replaced in PART 3 and both are named rather than hidden: the BAR SOURCE is the
minute lake instead of the broker (a session may not be opened here, and ``live_source`` is
untouched), and the CLOCK is virtual, because "today" here is a day whose candles exist.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import calendar as cal  # noqa: E402
from acumen import live_screener as ls  # noqa: E402
from acumen import run_screener  # noqa: E402
from acumen import signals as sig  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk13_fix2_live_morning.md"

#: The replayed today. HDFCBANK is SETTLED, so a live morning may screen it at all; NTPC is
#: QUARANTINED, so the run must name it excluded and never sweep it (CONTEXT 4.7 / Q-30).
REPLAYED_TODAY = date(2026, 6, 10)
SCREENED = "HDFCBANK"
QUARANTINED = "NTPC"


def scratch_cache(root: Path, day: date) -> Path:
    """A scratch cache_root holding the day's own master and the published holiday calendar."""
    config = load_config(include_env=False)
    cache = root / "cache"
    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        config.path("cache_root") / "instrument_master" / config.instrument_master,
        cache / "instrument_master" / ls.day_master_filename(day),
    )
    payload = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "holidays_2026.json").read_text(encoding="utf-8")
    )
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=day
    )
    raw = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    raw["paths"]["cache_root"] = str(cache)
    raw["paths"]["logs_dir"] = str(root / "logs")
    path = root / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Drive the shipped CLI and capture exactly what an operator would see."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = run_screener.main(argv)
    return code, buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    config = load_config(include_env=False)
    data_root = config.path("data_root")
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SCREENED, REPLAYED_TODAY):
        print(f"{SCREENED} {REPLAYED_TODAY} is not in the local lake")
        return 1

    root = Path(tempfile.mkdtemp(prefix="acumen-fix2-live-"))
    today = date.today()
    lines: list[str] = [
        "# chunk 13 FIX-2 -- the LIVE path, started on TODAY and run end to end",
        "",
        f"Run at {datetime.now().replace(microsecond=0).isoformat()} from "
        "`docs/evidence/chunk13_fix2_live_morning.py`. READ-ONLY over the stores; the day's own "
        "instrument master and the published holiday master are COPIED into a scratch "
        "`cache_root` outside them.",
        "",
        "## PART 1 -- the DERIVED calendar still refuses today, and that is correct",
        "",
        "QUESTIONS.md Q-3 safeguard 1 -- *a download error is NEVER treated as a holiday* -- is",
        "why the store-derived calendar refuses a range holding a date it has never attempted.",
        "It must not weaken by one date. What B6 changed is that a live morning stopped asking",
        "it a question only the published master can answer.",
        "",
        "```",
    ]
    try:
        bt.build_runner((SCREENED,), today, today, seed_from=today, label="fix2-evidence")
        lines.append("NO REFUSAL -- the store now covers today, so this half cannot be shown")
    except Exception as exc:
        lines.append(f"{type(exc).__name__}: {exc}")
    lines += ["```", ""]

    # --- PART 2: a live morning STARTS on a today-dated run -----------------------------------
    config_today = scratch_cache(root / "today", today)
    code_today, out_today = run_cli([
        "--mode", "live", "--day", today.isoformat(), "--symbols", SCREENED,
        "--preflight-only", "--config", str(config_today),
        "--recording-root", str(root / "today" / "rec"),
    ])
    lines += [
        f"## PART 2 -- `--mode live --day {today.isoformat()} --preflight-only` (exit {code_today})",
        "",
        "The date is TODAY, which the daily store has never attempted and, under Q-19's guard,",
        "structurally never will. Before this fix the same command exited 1 with",
        "*\"the screener cannot start: CalendarError ... date(s) never attempted\"*.",
        "",
        "**Read the `biases resolved` line honestly.** This machine's daily store ends before",
        "today (PART 1 names the first unattempted date), so today's CONTEXT 3.2 pair has no",
        "candles and the bias shown is a CARRY across that gap -- the `no-data` branch R1-Q6",
        "documents, reached only because the series is seeded 180 days back. On a real morning",
        "the pre-open refresh tops the store up to the last COMPLETED trading day and the pair is",
        "a real one. What PART 2 proves is that the morning STARTS, which is all B6 was about.",
        "",
        "```",
        out_today.rstrip(),
        "```",
        "",
    ]

    # --- PART 3: a whole live morning, end to end ---------------------------------------------
    config_replay = scratch_cache(root / "replayed", REPLAYED_TODAY)
    real_bar_source = run_screener._bar_source
    real_clock = ls.SystemClock
    run_screener._bar_source = (
        lambda live, config, data_root, *, allow_network: StoredDayBarSource(store)
    )
    ls.SystemClock = lambda: ls.VirtualClock(  # type: ignore[assignment]
        stamp=datetime.combine(REPLAYED_TODAY, sig.SESSION_OPEN)
    )
    try:
        code_live, out_live = run_cli([
            "--mode", "live", "--day", REPLAYED_TODAY.isoformat(),
            "--symbols", f"{SCREENED},{QUARANTINED}",
            "--config", str(config_replay),
            "--recording-root", str(root / "replayed" / "rec"),
        ])
    finally:
        run_screener._bar_source = real_bar_source
        ls.SystemClock = real_clock  # type: ignore[assignment]

    recording = LiveRecording.at(
        root / "replayed" / "rec" / f"{REPLAYED_TODAY.isoformat()}-live"
    )
    manifest = recording.read_manifest()
    inventory = recording.inventory()
    bars = recording.bars(SCREENED, REPLAYED_TODAY)
    events = [row["kind"] for row in recording.events()]
    alerts = recording.alerts()

    lines += [
        f"## PART 3 -- a whole live morning on a REPLAYED TODAY (exit {code_live})",
        "",
        "```",
        out_live.rstrip(),
        "```",
        "",
        "### What the run produced",
        "",
        "| reading | value |",
        "|---|---|",
        f"| mode / posture | `{manifest['mode']}` / oracle-free per sweep |",
        f"| symbols SCREENED | {', '.join(manifest['symbols'])} |",
        f"| symbols EXCLUDED (Q-30) | "
        f"{', '.join(row['symbol'] for row in manifest['excluded_symbols']) or '-'} |",
        f"| instrument master | `{manifest['master_file']}` |",
        f"| master provenance | {manifest['master_reason']} |",
        f"| governing calendar | `{manifest['calendar']['governing_source']}` |",
        f"| bias series seeded from | {manifest['seed_from']} |",
        f"| 1-minute bars recorded | {len(bars):,} |",
        f"| FIRST / LAST stamp | {min(b.stamp for b in bars):%H:%M} / "
        f"{max(b.stamp for b in bars):%H:%M} |",
        f"| sweeps closed | {events.count('sweep-closed')} "
        f"({len(ls.boundary_stamps(REPLAYED_TODAY))} boundaries + the 15:30 close-out) |",
        f"| POCs pinned (CONTEXT 3.3) | {events.count('poc-pinned')} |",
        f"| alerts delivered | {len(alerts)} |",
        f"| recording digest | `{inventory['digest'][:16]}...` |",
        "",
        "**B4 is closed by the LAST STAMP.** `close_day()`'s 15:30 poll is the reason the",
        f"recording reaches {max(b.stamp for b in bars):%H:%M} rather than stopping at 15:14. Over",
        "460 real July-2026 symbol-days REVIEW_13 measured that truncation flipping **22.05% of",
        "oracle-passing days to REFUSED** the next morning -- so CONTEXT 4.7's loud banner would",
        "have fired on roughly one alerted day in five, against a disclosed residual of 0.5229%.",
        "",
        "### The alerts, as the trader receives them",
        "",
        "```",
    ]
    for row in alerts:
        lines.append(
            f"[{row['at'][11:16]}] {row['symbol']:<12} {row['kind']:<12} "
            + json.dumps({k: v for k, v in row["payload"].items() if k != "disclosure"},
                         sort_keys=True)
        )
    lines += [
        "```",
        "",
        f"Every one of them carries CONTEXT 4.7's disclosed line: "
        f"*\"{ls.LIVE_DISCLOSURE}\"* "
        f"({sum(1 for row in alerts if row['payload'].get('disclosure') == ls.LIVE_DISCLOSURE)}"
        f"/{len(alerts)}).",
        "",
    ]

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"PART 2 exit {code_today}; PART 3 exit {code_live}, "
          f"{len(bars)} bars, last {max(b.stamp for b in bars):%H:%M}, {len(alerts)} alerts")
    return 0 if (code_today == 0 and code_live == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
