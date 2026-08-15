"""REVIEW_14B probes 2-8 -- the re-review's own attacks on the FIX-2 session's claims.

Every measurement below is taken by driving the SHIPPED path, and every one is the re-reviewer's
own construction rather than a re-run of the fix session's test:

  2. **B3** -- the runbook's own 08:45 command through ``run_screener.main`` on a SCRATCH layout.
  3. **THE TELEGRAM GATE** -- a replay with ``--telegram --live-alerts`` through ``main()``, the
     five-case truth table, the markers, and the five three-act claims read out of the tree.
  4. **M19** -- ten symbols, ONE poisoned the re-reviewer's own way (a NEXT-day stray stamp, the
     mirror of the fix session's fixture), a raising sink, and -- section 4b -- a CENSUS of seven
     malformed-bar shapes that measures how far the new isolation actually reaches. Three of the
     seven still end the morning, which is this re-review's own new finding.
  5. **H3 / M21** -- BOSCHLTD 2021-05-20's eight phase-regression events, re-derived by hand
     from the raw minute store before the screener is asked, and the ordinary qty-0 day.
  6. **H4 / Q1** -- a refused state's REAL age, a FALSE fresh stamp, a marked stale price.
  7. **H2** -- a resumed morning's summary, and an actually-empty one.
  8. **M15 / M16 / H5** -- oracle-silent vs oracle-refuses on BOTH dashboards, and the parity
     harness in live posture.

STORE SAFETY: the stores are READ here and never written. The one section that drives a mutating
CLI (``--refresh``, section 2) runs against a COPY of both roots -- CLAUDE.md's newest rule. The
whole re-review is bracketed by ``housekeeping_13aug_store_fingerprint.py`` either side.

ASCII-only, like every other source file in this repo (chunk-0 B7).

Usage:  python docs/evidence/review14b_live_attacks.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone

UTC = timezone.utc
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from acumen import calendar as cal              # noqa: E402
from acumen import live_dashboard as dash       # noqa: E402
from acumen import live_refresh as refresh      # noqa: E402
from acumen import live_screener as ls          # noqa: E402
from acumen import parity                       # noqa: E402
from acumen import run_screener                 # noqa: E402
from acumen import telegram_sink as tg          # noqa: E402
from acumen.config import load_config           # noqa: E402
from acumen.daily_store import DailyStore       # noqa: E402
from acumen.live_recording import LiveRecording, RecordedAlert   # noqa: E402
from acumen.live_source import StoredDayBarSource                # noqa: E402
from acumen.minute_store import MinuteStore                      # noqa: E402

DAY = date(2026, 6, 10)
SYMBOL = "HDFCBANK"
BOSCH, BOSCH_DAY = "BOSCHLTD", date(2021, 5, 20)
REPORT: list[str] = []
VERDICTS: list[tuple[str, bool, str]] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    REPORT.append(line)


def check(label: str, ok: bool, detail: str = "") -> bool:
    VERDICTS.append((label, bool(ok), detail))
    say(f"   [{'PASS' if ok else 'FAIL'}] {label}" + (f"  -- {detail}" if detail else ""))
    return bool(ok)


# --- the scratch world (a COPY, never a link) ---------------------------------------------------


def build_scratch_world(root: Path) -> Path:
    config = load_config(include_env=False)
    real_data, real_cache = config.path("data_root"), config.path("cache_root")
    data, cache = root / "data", root / "cache"

    (data / "daily_store").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "daily_store" / "ledger.parquet",
                    data / "daily_store" / "ledger.parquet")
    for year in (2025, 2026):
        shutil.copytree(real_data / "daily_store" / "daily" / str(year),
                        data / "daily_store" / "daily" / str(year), dirs_exist_ok=True)
    shutil.copytree(real_data / "minute_store" / "ledger", data / "minute_store" / "ledger")
    shutil.copytree(real_data / "minute_store" / "minute" / SYMBOL,
                    data / "minute_store" / "minute" / SYMBOL)
    shutil.copytree(real_data / "nse", data / "nse")
    (data / "universe_backfill").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "universe_backfill" / "ledger.json",
                    data / "universe_backfill" / "ledger.json")

    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    pin = real_cache / "instrument_master" / config.instrument_master
    shutil.copyfile(pin, cache / "instrument_master" / config.instrument_master)
    shutil.copyfile(pin, cache / "instrument_master" / ls.day_master_filename(DAY))

    payload = json.loads(
        (REPO / "tests" / "fixtures" / "holidays_2026.json").read_text(encoding="utf-8")
    )
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY
    )
    window_start = DAY - timedelta(days=refresh.DEFAULT_LOOKBACK_DAYS)
    ca_file = cache / "ca" / f"nse_ca_{window_start.isoformat()}_{DAY.isoformat()}.json"
    ca_file.parent.mkdir(parents=True, exist_ok=True)
    ca_file.write_text(json.dumps({"fetched_on": DAY.isoformat(), "payload": []}),
                       encoding="utf-8")

    text = (REPO / "config.yaml").read_text(encoding="utf-8")
    for key, value in (("data_root", data), ("cache_root", cache)):
        text = "\n".join(
            f"  {key}: {value.as_posix()}" if line.strip().startswith(f"{key}:") else line
            for line in text.splitlines()
        )
    path = root / "config.yaml"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def pipeline_for(config):
    from acumen import backtest as bt
    from acumen.signal_engine import SignalPipeline

    master, _path, _sha = bt.pinned_master(config.path("cache_root"), config.instrument_master)
    return SignalPipeline(
        minute_store=MinuteStore.at(config.path("data_root") / "minute_store"),
        daily_store=DailyStore.at(config.path("data_root") / "daily_store"),
        master=master, row_size=config.row_size,
    )


def fixed_bias(day: date):
    from acumen.bias_engine import DailyBias

    return DailyBias(
        trade_date=day, bias="bullish", tradeable=True, rule="rule-1-breakout",
        detail="fixed by the re-review's probe", current_date=day - timedelta(days=1),
        previous_date=day - timedelta(days=2),
    )


# --- 2. B3 -- the runbook's own command --------------------------------------------------------


def section_b3(scratch_config: Path, work: Path) -> None:
    say("")
    say("2. B3 -- THE RUNBOOK'S OWN 08:45 COMMAND, THROUGH run_screener.main")
    say("-" * 78)
    import io
    from contextlib import redirect_stdout

    rec_root = work / "b3-rec"
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = run_screener.main([
            "--mode", "live", "--day", DAY.isoformat(), "--symbols", SYMBOL,
            "--refresh", "--allow-network", "--preflight-only",
            "--config", str(scratch_config), "--recording-root", str(rec_root),
        ])
    out = buffer.getvalue()
    say(f"   command : --mode live --day {DAY} --refresh --allow-network --preflight-only")
    say(f"   exit    : {code}")

    check("B3: exit 0", code == 0, out.strip().splitlines()[-1] if out.strip() else "")
    check("B3: the screener does NOT say it cannot start",
          "the screener cannot start" not in out)
    check("B3: the preflight says READY and not NOT READY",
          "READY" in out and "NOT READY" not in out)
    check("B3: the screener really started (preflight header printed)",
          "ACUMEN SCREENER PREFLIGHT" in out)

    manifest_path = rec_root / f"{DAY.isoformat()}-live" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    governing = manifest["calendar"]["governing_source"]
    say(f"   manifest calendar.governing_source : {governing}")
    say(f"   manifest calendar.is_trading_day   : {manifest['calendar']['is_trading_day']}")
    check("B3: the manifest names the PUBLISHED master",
          governing == "published-nse-holiday-master", governing)
    check("B3: and calls the day a trading day", manifest["calendar"]["is_trading_day"] is True)

    ca_line = [line for line in out.splitlines() if "corporate action" in line.lower()]
    say(f"   preflight CA line: {ca_line[-1][:150] if ca_line else '<none>'}")
    check("B3: the preflight discloses the fence to the operator",
          any("FENCED" in line for line in ca_line))


# --- 3. the Telegram gate ------------------------------------------------------------------------


def section_telegram(scratch_config: Path, work: Path) -> None:
    say("")
    say("3. THE TELEGRAM GATE -- three acts, and a message a phone cannot misread")
    say("-" * 78)
    import io
    from contextlib import redirect_stdout

    # (a) the review's own command, through main(), with the transport watched.
    transport: list[str] = []
    original = tg.post_message
    tg.post_message = lambda text, **kwargs: transport.append(text)
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            code = run_screener.main([
                "--day", DAY.isoformat(), "--symbols", SYMBOL,   # mode DEFAULTS to replay
                "--telegram", "--live-alerts",
                "--config", str(scratch_config), "--recording-root", str(work / "tg-rec"),
            ])
    finally:
        tg.post_message = original
    alerts = list(LiveRecording.at(work / "tg-rec" / f"{DAY.isoformat()}-replay").alerts())
    say(f"   replay + --telegram + --live-alerts -> exit {code}, "
        f"{len(alerts)} alert(s) produced, {len(transport)} message(s) on the transport")
    check("H1: a replay with both flags sends NOTHING through main()", transport == [],
          "\n".join(transport)[:200])
    check("H1: ...and it is not an empty morning (alerts really were produced)", bool(alerts))

    # (b) the five-case table, over the gate the CLI computes.
    cases = {
        ("live", True, True): True,
        ("live", True, False): False,
        ("live", False, True): False,
        ("replay", True, True): False,
        ("replay", True, False): False,
    }
    table_ok = True
    for (mode, telegram, live_alerts), expected in cases.items():
        argv = ["--mode", mode, "--day", DAY.isoformat(), "--symbols", SYMBOL,
                "--config", str(scratch_config)]
        argv += ["--telegram"] if telegram else []
        argv += ["--live-alerts"] if live_alerts else []
        got = run_screener.telegram_is_live(run_screener.parse_args(argv))
        say(f"     mode={mode:<6} telegram={telegram!s:<5} live_alerts={live_alerts!s:<5}"
            f" -> sends={got}  (expected {expected})")
        table_ok = table_ok and got is expected
    # and the sixth case nobody wrote down: --mode live --live-alerts with NO --telegram
    sixth = run_screener.telegram_is_live(run_screener.parse_args(
        ["--mode", "live", "--day", DAY.isoformat(), "--live-alerts",
         "--config", str(scratch_config)]))
    say(f"     mode=live   telegram=False live_alerts=True  -> sends={sixth}  (expected False)")
    check("H1: the five-case table holds", table_ok)
    check("H1: ...and the sixth case (no --telegram) too", sixth is False)

    # (c) a replay / dry message carries the date and a marker.
    def alert(**payload) -> RecordedAlert:
        body = {"side": "long", "entry_paise": 74095, "stop_paise": 73810,
                "target_paise": 74950, "qty": 350, "poc_paise": 73980, "bias": "bullish",
                "stale": False, "data_behind_minutes": 0}
        body.update(payload)
        return RecordedAlert(kind=ls.ALERT_TRIGGER, symbol="SHREECEM",
                             at=datetime(2020, 3, 19, 11, 30), payload=body)

    dry = tg.message_for(alert(dry_run=True, mode="replay"))
    live_msg = tg.message_for(alert(dry_run=False, mode="live", disclosure=ls.LIVE_DISCLOSURE))
    say("   the message a replayed 2020 trade would produce:")
    for line in dry.splitlines():
        say(f"        {line}")
    check("H1: a replayed/dry message carries its TRADE DATE",
          "2020-03-19" in dry)
    check("H1: ...and both posture markers",
          tg.DRY_RUN_MARKER in dry and tg.REPLAY_MARKER in dry)
    check("H1: a LIVE alert carries neither marker",
          tg.DRY_RUN_MARKER not in live_msg and tg.REPLAY_MARKER not in live_msg)
    check("H1: ...and still carries CONTEXT 4.7's disclosure",
          ls.LIVE_DISCLOSURE in live_msg)
    summary = tg.TelegramSink(live=True).end_of_day_message(
        (alert(mode="replay"),), day=date(2020, 3, 19))
    check("H1: the end-of-day summary of a replayed day names itself a replay",
          tg.REPLAY_MARKER in summary)

    # (d) the five places that claim three acts.
    say("   the five places REVIEW_14 H1 counted:")
    places = {
        "src/acumen/telegram_sink.py": None,
        "src/acumen/run_screener.py": None,
        "docs/morning_runbook_stub.md": None,
        "PROGRESS.md": "B393",
        "tests/test_telegram_sink.py": None,
    }
    consistent = True
    for relpath, marker in places.items():
        text = (REPO / relpath).read_text(encoding="utf-8", errors="replace")
        if marker == "B393":
            # The decision bullet AND the correction line indented under it -- REVIEW_14
            # PART 7 challenged B393 and the FIX-2 session appended the correction rather
            # than rewriting the original, so the claim now lives across two lines.
            lines = text.splitlines()
            start = next(i for i, line in enumerate(lines) if "**B393**" in line)
            body = "\n".join(lines[start:start + 2])
        else:
            body = text
        names_three = "three" in body.lower() and "deliberate act" in body.lower()
        names_all = all(flag in body for flag in ("--mode live", "--telegram", "--live-alerts"))
        says_two = "Two separate deliberate acts" in body or "sends only on TWO" in body
        say(f"     {relpath:<32} three-act={names_three} names-all-3={names_all} "
            f"says-two={says_two}")
        consistent = consistent and names_three and names_all and not says_two
    check("H1: all five places make the SAME three-act claim, and none still says two",
          consistent)


# --- 4. M19 -- MY poison -------------------------------------------------------------------------


def section_m19(scratch_config: Path, work: Path) -> None:
    say("")
    say("4. M19 -- TEN SYMBOLS, ONE POISONED WITH AN INVERTED CANDLE (high < low)")
    say("-" * 78)
    config = load_config(scratch_config, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    real = tuple(store.minutes(SYMBOL, DAY))
    if not real:
        say("   SKIPPED: the minute lake does not hold the probe day")
        return

    symbols = ("HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
               "RELIANCE", "AXISBANK", "ITC", "LT", "WIPRO")
    poisoned = symbols[7]        # ITC -- deliberately NOT the fix session's choice (INFY)
    say(f"   poisoned symbol : {poisoned}")
    say("   the poison      : the 09:20 candle re-served stamped on the NEXT trading day -- the "
        "MIRROR of the fix session's fixture, chosen after measuring five malformed shapes "
        "(section 4b) to find one that actually reaches the evaluation guard")

    class NextDayStray:
        def fetch(self, symbol: str, day: date, upto: datetime):
            bars = tuple(bar for bar in real if bar.stamp <= upto)
            if symbol != poisoned or not bars:
                return bars
            target = bars[5] if len(bars) > 5 else bars[0]
            stray = replace(target, stamp=target.stamp + timedelta(days=1))
            return bars + (stray,)

    InvertedCandle = NextDayStray

    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(work / "m19-rec")
    screener = ls.LiveScreener(
        day=DAY, symbols=symbols, pipeline=pipeline_for(config),
        biases={s: fixed_bias(DAY) for s in symbols},
        gates={}, source=InvertedCandle(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    recording.open_session({"trade_date": DAY.isoformat(), "mode": "live",
                            "symbols": list(symbols)})

    def after(report: ls.SweepReport) -> None:
        dash.write_dashboard(
            recording.root, day=DAY, now=report.boundary, grouped=screener.by_phase(),
            alerts=tuple(sink.alerts), banner=screener.banner, dry_run=screener.dry_run,
            disclosure=screener.disclosure, verification=None,
        )

    reports = screener.run_day(on_sweep=after)
    healthy = [s for s in symbols if s != poisoned]
    failures = [row for row in recording.events()
                if row["kind"] == ls.EVENT_EVALUATION_FAILED]

    say(f"   sweeps completed        : {len(reports)}  (sweeps_done={len(screener.sweeps_done)})")
    say(f"   evaluated per sweep     : {sorted({r.evaluated for r in reports})}")
    say(f"   unevaluated per sweep   : {sorted({r.unevaluated for r in reports})}")
    say(f"   dashboard.html written  : {(recording.root / 'dashboard.html').is_file()}")
    say(f"   banner                  : {screener.banner[:160]}")
    say(f"   evaluation-failed events: {len(failures)}")

    check("M19: the morning survives -- 18 of 18 boundaries",
          len(reports) == 18 and len(screener.sweeps_done) == 18, str(len(reports)))
    check("M19: nine symbols evaluated at ALL 18 boundaries",
          all(r.evaluated == 9 for r in reports))
    check("M19: the tenth is unevaluated at every boundary",
          all(r.unevaluated == (poisoned,) for r in reports))
    check("M19: the trader's screen was written", (recording.root / "dashboard.html").is_file())
    check("M19: the banner NAMES the tenth", poisoned in screener.banner)
    check("M19: the reason is on disk, per symbol per boundary",
          len(failures) == 18 and failures[0]["symbol"] == poisoned, str(len(failures)))
    check("M19: the nine healthy symbols are not marked skipped",
          all(screener.states[s].phase != ls.PHASE_SKIPPED for s in healthy))
    check("M19: the nine healthy symbols alerted",
          {a.symbol for a in sink.alerts} >= set(healthy))

    resumed = ls.LiveScreener(
        day=DAY, symbols=symbols, pipeline=screener.pipeline, biases=screener.biases,
        gates={}, source=InvertedCandle(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(ls.CollectingAlertSink(),), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    restored = resumed.restore()
    resumed_reports = resumed.run_day()
    check("M19: a RESTART recovers (the review measured it could not)",
          bool(restored) and len(resumed_reports) == 18)

    # The record is PER BOUNDARY, which is the granularity the fix claims: eighteen separate
    # events, each naming its own sweep, rather than one line per day.
    sweeps_named = [row.get("sweep") for row in failures]
    say(f"   the boundaries the failures name: {sweeps_named[:4]} ... {sweeps_named[-2:]}")
    check("M19: the failure is recorded PER BOUNDARY, each naming its own sweep",
          len(set(sweeps_named)) == 18 and sweeps_named[0] == "11:15")
    # ...and an honest note about what isolation does NOT buy: a STRAY bar is permanent
    # within a session, because `merge_bars` accumulates and never forgets a stamp it was
    # once served. The morning survives; that symbol does not come back.
    say("   NOTE: a stray-stamp poison is PERMANENT for its symbol inside one session -- "
        "merge_bars accumulates, so a feed that heals still serves a screener that "
        "remembers. The other nine finish the day; the tenth is lost until a new recording.")

    # --- 4b. HOW FAR THE ISOLATION REACHES -- the re-review's own new finding ------------------
    say("")
    say("   4b. THE SHAPE CENSUS: which malformed bars reach the guard, and which walk past it")
    say("   `_poll` wraps ONLY `self.source.fetch(...)` (live_screener.py:1055-1066). The merge,")
    say("   the duplicate-stamp scan and the two recording writes that follow it are OUTSIDE")
    say("   both guards, so a bar that survives the fetch and dies in THAT block still ends the")
    say("   sweep -- and the morning -- exactly as M19 described.")
    shapes = {
        "NEXT-day stray stamp": lambda b: replace(b, stamp=b.stamp + timedelta(days=1)),
        "high < low": lambda b: replace(b, high_paise=int(b.low_paise) - 1),
        "negative volume": lambda b: replace(b, volume=-1),
        "sub-minute stamp": lambda b: replace(b, stamp=b.stamp.replace(second=30)),
        "tz-AWARE stamp": lambda b: replace(b, stamp=b.stamp.replace(tzinfo=UTC)),
        "close_paise = None": lambda b: replace(b, close_paise=None),
        "volume = None": lambda b: replace(b, volume=None),
    }
    census: dict[str, str] = {}
    CENSUS_SYMBOL = SYMBOL   # a REAL F&O name: an unknown ticker fails in the master instead
    for name, mutate in shapes.items():
        target = real[5]

        class OneShape:
            def fetch(self, symbol: str, day: date, upto: datetime):
                got = tuple(bar for bar in real if bar.stamp <= upto)
                if symbol != CENSUS_SYMBOL or not got:
                    return got
                return tuple(mutate(bar) if bar.stamp == target.stamp else bar for bar in got)

        rec = LiveRecording.at(work / f"shape-{abs(hash(name))}")
        rec.open_session({"trade_date": DAY.isoformat(), "mode": "live",
                          "symbols": [CENSUS_SYMBOL]})
        one = ls.LiveScreener(
            day=DAY, symbols=(CENSUS_SYMBOL,), pipeline=pipeline_for(config),
            biases={CENSUS_SYMBOL: fixed_bias(DAY)}, gates={}, source=OneShape(), recording=rec,
            clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
            sinks=(ls.CollectingAlertSink(),), risk_per_trade_paise=100_000,
            cost_paise=10_000, posture=ls.POSTURE_LIVE, dry_run=True,
        )
        try:
            one.run_day()
            failed = [r for r in rec.events() if r["kind"] == ls.EVENT_EVALUATION_FAILED]
            census[name] = (
                f"CONTAINED by the guard ({failed[0]['error']})" if failed
                else "handled by the gates -- no exception at all"
            )
        except Exception as exc:
            census[name] = f"** ESCAPES run_day: {type(exc).__name__} **"
        say(f"        {name:<22} {census[name]}")
    escapes = [name for name, verdict in census.items() if "ESCAPES" in verdict]
    say(f"   shapes that walk past BOTH guards: {escapes}")
    check("M19: no malformed-bar shape escapes run_day (RESIDUAL -- see REVIEW_14B)",
          not escapes, f"{len(escapes)} of {len(shapes)} escape: {escapes}")

    # the sink loop -- a raising sink costs only its own delivery.
    class Exploding:
        def deliver(self, alert):
            raise RuntimeError("this sink is broken")

    collected = ls.CollectingAlertSink()
    rec2 = LiveRecording.at(work / "m19-sinks")
    rec2.open_session({"trade_date": DAY.isoformat(), "mode": "replay", "symbols": []})
    lonely = ls.LiveScreener(
        day=DAY, symbols=(), pipeline=None, biases={}, gates={}, source=None, recording=rec2,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(Exploding(), collected), risk_per_trade_paise=100_000, cost_paise=10_000,
    )
    probe_alert = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol="SHREECEM", at=datetime(2026, 6, 10, 11, 30),
        payload={"detail": "the screener is not answering", "stale": False,
                 "data_behind_minutes": 0},
    )
    delivered = lonely._deliver(probe_alert)
    sink_failures = [row for row in rec2.events() if row["kind"] == ls.EVENT_SINK_FAILED]
    check("M19: a RAISING sink costs only its own delivery",
          delivered is True and [a.kind for a in collected.alerts] == [ls.ALERT_FAILURE])
    check("M19: ...and the miss is recorded by sink name",
          bool(sink_failures) and "RuntimeError" in sink_failures[0]["detail"])


# --- 5. H3 / M21 -- BOSCHLTD 2021-05-20, re-derived ---------------------------------------------


def section_h3(work: Path) -> None:
    say("")
    say("5. H3 / M21 -- BOSCHLTD 2021-05-20, THE EIGHT EVENTS RE-DERIVED BY HAND FIRST")
    say("-" * 78)
    config = load_config(include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    bars = tuple(store.minutes(BOSCH, BOSCH_DAY))
    if not bars:
        say("   SKIPPED: the minute lake does not hold BOSCHLTD 2021-05-20")
        return

    entry_at = datetime.combine(BOSCH_DAY, time(13, 30))
    window = [bar for bar in bars if entry_at - timedelta(minutes=15) <= bar.stamp < entry_at]
    by_low = sorted(window, key=lambda bar: bar.low_paise)
    late = {bar.stamp for bar in by_low[:2]}
    true_low = int(by_low[0].low_paise)
    without_late = min(int(bar.low_paise) for bar in window if bar.stamp not in late)
    entry_close = [bar for bar in bars if bar.stamp == entry_at - timedelta(minutes=1)]
    entry_paise = int(entry_close[0].close_paise) if entry_close else None

    risk_budget = config.require_risk_per_trade() * 100
    say("   HAND DERIVATION, straight off the raw minute store (nothing imported from the "
        "screener):")
    say(f"     entry candle 13:15..13:29, {len(window)} one-minute bars")
    say(f"     entry (13:29 close)                 : {entry_paise} paise")
    say(f"     candle low WITHOUT the two late bars: {without_late} paise")
    say(f"     candle low WITH them (the true low) : {true_low} paise")
    say(f"     risk without the late bars          : {entry_paise - without_late} paise "
        f"-> qty {(entry_paise - without_late) and risk_budget // (entry_paise - without_late)}")
    say(f"     risk with them                      : {entry_paise - true_low} paise "
        f"-> qty {risk_budget // (entry_paise - true_low)}")
    boundaries = [datetime.combine(BOSCH_DAY, time(11, 15)) + timedelta(minutes=15 * i)
                  for i in range(17)] + [datetime.combine(BOSCH_DAY, time(15, 30))]
    after_entry = [b for b in boundaries if b > entry_at]
    say(f"     boundaries in a session             : {len(boundaries)} "
        f"(11:15..15:15 plus close_day's 15:30)")
    say(f"     boundaries AFTER the 13:30 entry    : {len(after_entry)} "
        f"<- the number of regressions a consumed-unsizable re-read must produce")

    class TwoLateCandles:
        def fetch(self, symbol: str, day: date, upto: datetime):
            served = [bar for bar in bars if bar.stamp <= upto]
            if upto <= entry_at:
                served = [bar for bar in served if bar.stamp not in late]
            return tuple(served)

    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(work / "h3-rec")
    screener = ls.build_live_screener(
        BOSCH_DAY, (BOSCH,), source=TwoLateCandles(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(BOSCH_DAY, datetime.min.time())),
        mode="replay", sinks=(sink,),
    )
    screener.run_day()
    trigger = [a for a in sink.alerts if a.kind == ls.ALERT_TRIGGER]
    state = screener.states[BOSCH]
    regressions = [r for r in recording.events() if r["kind"] == "phase-regression-refused"]

    say(f"   MEASURED: trigger alerts={len(trigger)}  qty="
        f"{trigger[0].payload['qty'] if trigger else None}  final phase={state.phase}  "
        f"final qty={state.qty}  regressions={len(regressions)}")
    check("H3: the trade really was delivered at 13:30 with qty 1",
          len(trigger) == 1 and trigger[0].at == entry_at and trigger[0].payload["qty"] == 1)
    check("H3: entry/stop are the hand-derived numbers",
          trigger and (trigger[0].payload["entry_paise"], trigger[0].payload["stop_paise"])
          == (entry_paise, without_late))
    check("H3: two late candles do NOT walk it into a numberless row",
          state.phase == ls.PHASE_TRIGGERED and state.entry_paise == entry_paise
          and state.qty == 1)
    check(f"H3: exactly {len(after_entry)} phase-regression events, as hand-derived",
          len(regressions) == len(after_entry), f"measured {len(regressions)}")
    check("H3: each names TRIGGERED -> refused",
          bool(regressions) and regressions[0]["was"] == ls.PHASE_TRIGGERED
          and regressions[0]["proposed"] == ls.PHASE_REFUSED)

    # the ordinary qty-0 day, byte-compared against the reviewed tip's own answer
    plain_sink = ls.CollectingAlertSink()
    plain_rec = LiveRecording.at(work / "h3-plain")
    plain = ls.build_live_screener(
        BOSCH_DAY, (BOSCH,), source=StoredDayBarSource(store), recording=plain_rec,
        clock=ls.VirtualClock(stamp=datetime.combine(BOSCH_DAY, datetime.min.time())),
        mode="replay", sinks=(plain_sink,),
    )
    plain.run_day()
    plain_state = plain.states[BOSCH]
    say(f"   ORDINARY qty-0 day: phase={plain_state.phase} refusal={plain_state.refusal!r} "
        f"qty={plain_state.qty} alerts={[a.kind for a in plain_sink.alerts]}")
    check("M21: the ordinary qty-0 day is still consumed-and-logged with no trigger",
          plain_state.phase == ls.PHASE_REFUSED
          and plain_state.refusal == ls.REFUSAL_QTY_ZERO
          and [a.kind for a in plain_sink.alerts] == [ls.ALERT_ARMED])
    check("M21: ...and it produced NO phase-regression event",
          not [r for r in plain_rec.events() if r["kind"] == "phase-regression-refused"])
    digest = (plain_rec.root / "alerts.jsonl").read_bytes()
    (work / "h3-plain-alerts.jsonl").write_bytes(digest)
    say(f"   ordinary-day alerts.jsonl written to {work / 'h3-plain-alerts.jsonl'} "
        f"({len(digest)} bytes) for the 993d57a byte comparison")


# --- 6. H4 / Q1 ---------------------------------------------------------------------------------


def section_h4() -> None:
    say("")
    say("6. H4 / Q1 -- A REFUSED STATE'S REAL AGE, AND A STAMP THAT LIES")
    say("-" * 78)
    frozen = ls.SymbolState(
        symbol=BOSCH, phase=ls.PHASE_REFUSED, refusal="gate 2 (integrity)",
        entry_paise=1_556_990, stop_paise=1_458_000, qty=1, minute_count=120,
        last_stamp=datetime(2026, 6, 10, 11, 29),
    )
    stale, behind = ls.data_age(frozen, datetime(2026, 6, 10, 15, 0))
    say(f"   a feed frozen at 11:29, read at 15:00 -> stale={stale} behind={behind}")
    check("H4: a refused state reports its REAL age (211 minutes)",
          (stale, behind) == (True, 211), f"{(stale, behind)}")

    waiting = replace(frozen, phase=ls.PHASE_WAITING)
    check("H4: ...and an unrefused state is unchanged by the fix",
          ls.data_age(waiting, datetime(2026, 6, 10, 15, 0)) == (True, 211))

    lying = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol=BOSCH, at=datetime(2026, 6, 10, 15, 0),
        payload={"entry_paise": 1_556_990, "stop_paise": 1_458_000, "qty": 1,
                 "stale": False, "data_behind_minutes": 211},
    )
    refusal = ls.unvouched_price(lying)
    say(f"   unvouched_price(a FALSE fresh stamp) -> {str(refusal)[:130]}")
    check("Q1: a FALSE fresh stamp is rejected, not only a missing one",
          refusal is not None and "contradicts itself" in refusal and "211" in refusal)

    sent: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None)
    sink.deliver(lying)
    check("Q1: ...and the sink really refuses it rather than merely being able to",
          sent == [] and len(sink.refused) == 1)

    marked = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol=BOSCH, at=datetime(2026, 6, 10, 15, 0),
        payload={"entry_paise": 1_556_990, "stale": True, "data_behind_minutes": 211,
                 "alert_states": [ls.MARKER_STALE], "stale_note": ls.stale_note(211)},
    )
    sent2: list[str] = []
    sink2 = tg.TelegramSink(send=sent2.append, live=True, out=lambda _line: None)
    sink2.deliver(marked)
    check("Q1: a marked STALE price still travels",
          ls.unvouched_price(marked) is None and len(sent2) == 1 and not sink2.refused)
    # the boundary: exactly at the clamp is not a contradiction
    edge = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol=BOSCH, at=datetime(2026, 6, 10, 15, 0),
        payload={"entry_paise": 1, "stale": False,
                 "data_behind_minutes": ls.STALE_AFTER_MINUTES},
    )
    check(f"Q1: an age exactly at the clamp ({ls.STALE_AFTER_MINUTES}) is NOT called a lie",
          ls.unvouched_price(edge) is None)


# --- 7. H2 -- the resumed summary ----------------------------------------------------------------


def section_h2(work: Path) -> None:
    say("")
    say("7. H2 -- THE SUMMARY OF A MORNING THIS PROCESS DID NOT DELIVER")
    say("-" * 78)
    recording = LiveRecording.at(work / "h2-rec" / f"{DAY.isoformat()}-live")
    for kind, minute in ((ls.ALERT_ARMED, 15), (ls.ALERT_TRIGGER, 30), (ls.ALERT_EXIT, 45)):
        recording.record_alert(RecordedAlert(
            kind=kind, symbol=SYMBOL, at=datetime.combine(DAY, time(11, minute)),
            payload={"side": "long", "entry_paise": 74095, "qty": 350, "stale": False,
                     "data_behind_minutes": 0, "mode": "live"},
        ))
    sent: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None)
    ok = run_screener._end_of_day_summary(
        sink, recording, day=DAY, disclosure=ls.LIVE_DISCLOSURE
    )
    say("   the summary a resumed process sends:")
    for line in (sent[0] if sent else "").splitlines():
        say(f"        {line}")
    check("H2: a resumed morning reports the day's REAL alerts",
          ok and len(sent) == 1 and tg.SUMMARY_NO_ALERTS not in sent[0]
          and "armed 11:15" in sent[0] and "trigger 11:30" in sent[0]
          and "exit 11:45" in sent[0])

    quiet = LiveRecording.at(work / "h2-rec" / "2026-06-11-live")
    quiet_sent: list[str] = []
    run_screener._end_of_day_summary(
        tg.TelegramSink(send=quiet_sent.append, live=True, out=lambda _line: None),
        quiet, day=date(2026, 6, 11),
    )
    check("H2: an actually-empty morning still says so",
          bool(quiet_sent) and tg.SUMMARY_NO_ALERTS in quiet_sent[0])

    second: list[str] = []
    run_screener._end_of_day_summary(
        tg.TelegramSink(send=second.append, live=True, out=lambda _line: None),
        recording, day=DAY, disclosure=ls.LIVE_DISCLOSURE,
    )
    check("H2: ...and the summary is still sent ONCE per recording",
          second == [])


# --- 8. M15 / M16 / H5 ---------------------------------------------------------------------------


def section_m15_m16_h5(scratch_config: Path, work: Path) -> None:
    say("")
    say("8. M15 / M16 -- 'NOT JUDGED' IS NEITHER 'PASSED' NOR 'REFUSED', ON BOTH SURFACES")
    say("-" * 78)
    from acumen.signal_engine import SignalPipeline

    config = load_config(scratch_config, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")

    # M15: a symbol that ALERTED and whose candles are absent.
    rec15 = LiveRecording.at(work / "m15-rec" / f"{DAY.isoformat()}-live")
    rec15.open_session({"trade_date": DAY.isoformat(), "mode": "live", "symbols": [SYMBOL],
                        "master_file": "x", "row_size": 24})
    for kind in ("armed", "trigger", "exit"):
        rec15.record_alert(RecordedAlert(kind=kind, symbol=SYMBOL,
                                         at=datetime.combine(DAY, time(11, 30)), payload={}))

    class NeverGated:
        def gate_day(self, *args, **kwargs):
            raise AssertionError("a symbol with no candles must not be gated")

    v15 = refresh.verify_prior_recording(rec15, NeverGated(), day=DAY)
    say(f"   M15 headline: {v15.headline[:220]}")
    check("M15: the alerted-but-uncandled symbol is IN the verdict list",
          [v.symbol for v in v15.verdicts] == [SYMBOL])
    check("M15: it is NOT reported as '0 alerted'",
          "0 alerted" not in v15.headline and SYMBOL in v15.headline)
    check("M15: it is NOT withdrawn (refused_after_alert is False)",
          v15.verdicts[0].refused_after_alert is False
          and v15.verdicts[0].alerted_but_unverified is True)
    check("M15: the render marks it NOT-VERIFIED", refresh.NOT_VERIFIED_MARK in v15.render())

    # M16: the oracle that has not spoken, against a real recording.
    sink = ls.CollectingAlertSink()
    rec16 = LiveRecording.at(work / "m16-rec")
    screener = ls.build_live_screener(
        DAY, (SYMBOL,), source=StoredDayBarSource(store), recording=rec16,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        mode="replay", sinks=(sink,),
        data_dir=config.path("data_root"), cache_dir=config.path("cache_root"),
    )
    screener.run_day()
    silent = SignalPipeline(
        minute_store=store, daily_store=DailyStore.at(work / "no-bhavcopy-here"),
        master=screener.pipeline.master, row_size=config.row_size,
    )
    v16 = refresh.verify_prior_recording(rec16, silent, day=DAY)
    real = SignalPipeline(
        minute_store=store,
        daily_store=DailyStore.at(config.path("data_root") / "daily_store"),
        master=screener.pipeline.master, row_size=config.row_size,
    )
    v16_real = refresh.verify_prior_recording(rec16, real, day=DAY)
    say(f"   M16 silent-oracle headline : {v16.headline[:200]}")
    say(f"   M16 real-oracle headline   : {v16_real.headline[:200]}")
    check("M16: a SILENT oracle is not a refusal",
          v16.verdicts[0].verified is False
          and v16.verdicts[0].refused_after_alert is False
          and "treat them as withdrawn" not in v16.headline
          and "NOT VERIFIED" in v16.headline)
    check("M16: ...and it names the oracle as the thing that did not speak",
          refresh.NO_ORACLE_ROW in v16.verdicts[0].oracle_reason)
    check("M16: a REAL answer still reads as one (the loud line is not softened)",
          v16_real.verdicts[0].verified is True)

    # both dashboards.
    states = {ls.PHASE_WAITING: [screener.states[SYMBOL]]}
    text_silent = dash.render_text(day=DAY, now=datetime.combine(DAY, time(15, 30)),
                                   grouped=states, alerts=(), verification=v15)
    html_silent = dash.render_html(day=DAY, now=datetime.combine(DAY, time(15, 30)),
                                   grouped=states, alerts=(), verification=v15)
    text_pass = dash.render_text(day=DAY, now=datetime.combine(DAY, time(15, 30)),
                                 grouped=states, alerts=(), verification=v16_real)
    loud_text = "!! " + v15.headline in text_silent
    quiet_text = "!! " + v16_real.headline not in text_pass
    say(f"   dashboard TEXT: unjudged loud={loud_text}  a passing day quiet={quiet_text}")
    check("M15/M16: the TEXT dashboard puts an unjudged alerted day in the loud register",
          loud_text and quiet_text)
    # render_html puts a loud verdict in `<div class="banner" role="alert">` and a quiet one in
    # `<div class="row quiet">` -- read the block that follows the section heading, not a class
    # name invented by this probe.
    html_pass = dash.render_html(day=DAY, now=datetime.combine(DAY, time(15, 30)),
                                 grouped=states, alerts=(), verification=v16_real)
    block_silent = html_silent.split("YESTERDAY, VERIFIED")[1]
    block_pass = html_pass.split("YESTERDAY, VERIFIED")[1]
    say(f"   dashboard HTML: unjudged -> banner={'role=\"alert\"' in block_silent}  "
        f"a passing day -> quiet row={'row quiet' in block_pass}")
    check("M15/M16: the HTML dashboard does the same",
          'role="alert"' in block_silent and "row quiet" in block_pass
          and 'role="alert"' not in block_pass)

    # ORACLE-SILENT vs ORACLE-REFUSES -- the pair the re-review was asked to separate. (M15's
    # no-candles verdict and M16's silent-oracle verdict deliberately SHARE a headline: both
    # are "not judged". They are separated on the row, by their reason.)
    refusing = refresh.MorningVerification(
        day=DAY, oracle_available=True, note="", recording_root=work / "m16-rec",
        verdicts=(replace(v16.verdicts[0], verified=True, oracle_passed=False,
                          oracle_reason="gate 1 (volume reconciliation): "
                                        "gap 52.135% is above the band [-0.1, 5.0]"),),
    )
    say(f"   oracle SILENT  : {v16.headline[:120]}")
    say(f"   oracle REFUSES : {refusing.headline[:120]}")
    check("M15/M16: oracle-SILENT and oracle-REFUSES are distinct on the headline",
          "NOT VERIFIED" in v16.headline
          and "REFUSES" in refusing.headline
          and "treat them as withdrawn" in refusing.headline
          and "treat them as withdrawn" not in v16.headline)
    check("M15/M16: ...and distinct on the row, by reason and by mark",
          refresh.NO_ORACLE_ROW in v16.render()
          and refresh.NOT_VERIFIED_MARK in v16.render()
          and refresh.NOT_VERIFIED_MARK not in refusing.render()
          and "REFUSED-AFTER-ALERT" in refusing.render())
    check("M15/M16: no-candles and silent-oracle share a headline but NOT a reason",
          refresh.NO_CANDLES_RECORDED in v15.render()
          and refresh.NO_ORACLE_ROW in v16.render()
          and refresh.NO_ORACLE_ROW not in v15.render())

    # H5 -- the live posture.
    say("")
    say("   H5 -- THE PARITY HARNESS IN LIVE POSTURE")
    live_screener = ls.build_live_screener(
        DAY, (SYMBOL,), source=StoredDayBarSource(store),
        recording=LiveRecording.at(work / "h5-rec"),
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        mode="live", sinks=(ls.CollectingAlertSink(),),
        data_dir=config.path("data_root"), cache_dir=config.path("cache_root"),
    )
    result = parity.parity_for_screener(live_screener, SYMBOL, source="lake")
    say(f"   posture={live_screener.posture} gates={live_screener.gates} "
        f"judged={result.judged} matched={result.matched} "
        f"transitions_equal={result.transitions_equal} mismatches={list(result.mismatches)[:3]}")
    check("H5: a live-posture day is JUDGED", bool(result.judged), str(result.oracle_reason))
    check("H5: the trail comparison is real again", bool(result.transitions_equal))
    check("H5: and the day MATCHES", bool(result.matched), str(list(result.mismatches))[:200])


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="review14b-attacks-"))
    say("REVIEW_14B PROBES 2-8 -- the re-review's own attacks")
    say("=" * 78)
    say(f"work root: {work}")
    scratch_config = build_scratch_world(work / "world")

    section_b3(scratch_config, work)
    section_telegram(scratch_config, work)
    section_m19(scratch_config, work)
    section_h3(work)
    section_h4()
    section_h2(work)
    section_m15_m16_h5(scratch_config, work)

    say("")
    say("=" * 78)
    failed = [label for label, ok, _ in VERDICTS if not ok]
    say(f"CHECKS: {len(VERDICTS) - len(failed)} PASS / {len(failed)} FAIL")
    for label in failed:
        say(f"   FAILED: {label}")
    (Path(__file__).with_suffix(".out.txt")).write_text(
        "\n".join(REPORT) + "\n", encoding="utf-8"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
