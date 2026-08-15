"""CHUNK 15 -- the carried defects, MEASURED on whichever tree this script is run in.

Written so it runs unchanged on the tree BEFORE the chunk-15 fixes and on the tree after them,
and prints the same table either way. That is the point: the difference between the two outputs
is the evidence, and neither number is typed by hand.

    python docs/evidence/chunk15_flip.py

Everything here is duck-typed against the shipped modules (``getattr`` with defaults, no import
of a name chunk 15 introduced), because a probe that cannot even be imported on the defective
tree measures nothing.

**Read-only with respect to the stores.** The one section that needs real bars builds a COPY of
the slices one symbol-day needs, through ``tests.test_review14_fix.build_scratch_world`` -- a
copy, never a link (CLAUDE.md data-store safety). Nothing under the real ``data_root`` or
``cache_root`` is written, and the copy is removed at the end.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
import tempfile
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from acumen import live_dashboard as dash          # noqa: E402
from acumen import live_refresh as refresh         # noqa: E402
from acumen import live_screener as ls             # noqa: E402
from acumen import telegram_sink as tg             # noqa: E402
from acumen.config import load_config              # noqa: E402
from acumen.live_recording import LiveRecording, RecordedAlert, StoredBar  # noqa: E402

FANOUT = ("HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
          "RELIANCE", "AXISBANK", "ITC", "LT", "WIPRO")
POISONED = "ITC"
SYMBOL = "HDFCBANK"
DAY = date(2026, 6, 10)

OUT: list[str] = []


def say(line: str = "") -> None:
    OUT.append(line)
    print(line, flush=True)


def head(title: str) -> None:
    say("")
    say("=" * 78)
    say(title)
    say("=" * 78)


# --- R1: seven malformed shapes, driven through run_day -----------------------------------------


def poison(shape: str, bar):
    if shape == "next-day stray stamp":
        return replace(bar, stamp=bar.stamp - timedelta(days=1))
    if shape == "high below low":
        return replace(bar, high_paise=bar.low_paise - 1)
    if shape == "negative volume":
        return replace(bar, volume=-1)
    if shape == "sub-minute stamp":
        return replace(bar, stamp=bar.stamp + timedelta(seconds=30))
    if shape == "tz-aware stamp":
        return replace(bar, stamp=bar.stamp.replace(
            tzinfo=timezone(timedelta(hours=5, minutes=30))))
    if shape == "close_paise is None":
        return replace(bar, close_paise=None)
    if shape == "volume is None":
        return replace(bar, volume=None)
    raise AssertionError(shape)


SHAPES = ("next-day stray stamp", "high below low", "negative volume", "sub-minute stamp",
          "tz-aware stamp", "close_paise is None", "volume is None")


def screener_for(config, root: Path, source, symbols=FANOUT, sinks=None):
    from test_review14_fix import _bias, _pipeline

    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(root)
    screener = ls.LiveScreener(
        day=DAY, symbols=tuple(symbols), pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in symbols},
        gates={}, source=source, recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,) if sinks is None else tuple(sinks),
        risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=getattr(ls, "POSTURE_LIVE", "live"), dry_run=True,
    )
    recording.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(symbols)}
    )
    return screener, screener.sinks[0], recording


def r1_census(config, scratch: Path, real) -> None:
    head("R1 -- the seven malformed shapes of REVIEW_14B's census, through run_day()")
    say(f"{'shape':<24} {'sweeps':>6}  {'evaluated/sweep':>15}  outcome")
    say("-" * 78)
    for index, shape in enumerate(SHAPES):
        bad = poison(shape, real[0])

        class Fanout:
            def fetch(self, symbol, day, upto):
                bars = tuple(bar for bar in real if bar.stamp <= upto)
                if symbol == POISONED and bars:
                    return (bad,) + bars
                return bars

        screener, _sink, recording = screener_for(
            config, scratch / f"r1-{index}", Fanout()
        )
        try:
            reports = screener.run_day()
        except Exception as exc:
            say(f"{shape:<24} {0:>6}  {'-':>15}  ESCAPED run_day: "
                f"{type(exc).__name__}: {str(exc)[:34]}")
            continue
        evaluated = sorted({report.evaluated for report in reports})
        events = recording.events()
        kinds = {row["kind"] for row in events}
        if getattr(ls, "EVENT_INTAKE_FAILED", "intake-failed") in kinds:
            outcome = "CONTAINED by the intake guard"
        elif ls.EVENT_EVALUATION_FAILED in kinds:
            outcome = "CONTAINED by the evaluation guard"
        else:
            outcome = "no exception at all -- the gates refuse it"
        say(f"{shape:<24} {len(reports):>6}  {str(evaluated):>15}  {outcome}")


def r1_locked_file(config, scratch: Path, real) -> None:
    head("R1 -- one candle file that cannot be written at 11:30 (the reachable cause)")
    from test_review14_fix import _bias, _pipeline

    class Fanout:
        def fetch(self, symbol, day, upto):
            return tuple(bar for bar in real if bar.stamp <= upto)

    class Locked(LiveRecording):
        def __init__(self, root: Path) -> None:
            super().__init__(root=Path(root))
            self.blocked = 0

        def record_bars(self, symbol, bars, *, sweep, at):
            if symbol == POISONED and sweep == "11:30":
                self.blocked += 1
                raise OSError(13, "the candle file is locked by another process")
            return super().record_bars(symbol, bars, sweep=sweep, at=at)

    recording = Locked(scratch / "r1-locked")
    screener = ls.LiveScreener(
        day=DAY, symbols=FANOUT, pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in FANOUT},
        gates={}, source=Fanout(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(ls.CollectingAlertSink(),), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=getattr(ls, "POSTURE_LIVE", "live"), dry_run=True,
    )
    recording.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(FANOUT)}
    )
    lost: list[str] = []
    try:
        reports = screener.run_day(on_sweep=lambda r: lost.append(
            r.boundary.strftime("%H:%M")
        ) if r.unevaluated else None)
    except Exception as exc:
        say(f"sweeps completed        : 0  -- ESCAPED run_day: {type(exc).__name__}: {exc}")
        say("boundaries lost         : the whole morning")
        return
    say(f"sweeps completed        : {len(reports)}")
    say(f"boundaries lost by {POISONED:<5}: {[label for label in lost if label]}")
    say(f"record_bars attempts     : {recording.blocked}   (a retry would double the intake)")
    say(f"duplicate stamps created : {len(recording.duplicate_bars(POISONED, DAY))}")
    say(f"{POISONED} phase at the close  : {screener.states[POISONED].phase}")


# --- M4: what the post-session poll puts on the phone --------------------------------------------


def m4(config, scratch: Path, real) -> None:
    head("M4 -- what the 15:30 post-session poll delivers")
    frozen_at = datetime.combine(DAY, datetime.min.time()).replace(hour=11, minute=15)

    class Starved:
        def fetch(self, symbol, day, upto):
            ceiling = upto if upto.time() >= ls.SESSION_END else frozen_at
            return tuple(bar for bar in real if bar.stamp <= min(upto, ceiling))

    sent: list[str] = []
    telegram = tg.TelegramSink(live=True, send=sent.append, out=lambda line: None)
    screener, collecting, recording = screener_for(
        config, scratch / "m4", Starved(), symbols=(SYMBOL,),
        sinks=(ls.CollectingAlertSink(), telegram),
    )
    seen: dict = {}

    def after(report):
        if report.boundary.strftime("%H:%M") == ls.LAST_BOUNDARY:
            seen["phase"] = screener.states[SYMBOL].phase
            seen["alerts"] = len(collecting.alerts)

    screener.run_day(on_sweep=after)
    after_close = [
        alert for alert in collecting.alerts if alert.at.strftime("%H:%M") == "15:30"
    ]
    say(f"phase at 15:15                : {seen.get('phase')}")
    say(f"phase after the 15:30 poll    : {screener.states[SYMBOL].phase}")
    say(f"alerts delivered to a SINK at 15:30 : {[a.kind for a in after_close]}")
    say(f"messages on the TELEGRAM transport stamped 15:30 : "
        f"{len([t for t in sent if ' 15:30]' in t])}")
    for text in sent:
        if " 15:30]" in text:
            say("    " + text.splitlines()[0])
    withheld = [
        row for row in recording.events()
        if row["kind"] == getattr(ls, "EVENT_POST_SESSION_ALERT", "post-session-alert-withheld")
    ]
    say(f"alerts RECORDED as withheld   : {[row.get('alert_kind') for row in withheld]}")


def m4_no_new_trade(config, scratch: Path, real) -> None:
    head("M4 -- do post-15:29 bars change the DECISION?")
    strays = tuple(
        replace(real[0], stamp=datetime.combine(DAY, datetime.min.time()).replace(
            hour=15, minute=minute), close_paise=real[0].close_paise + 10_000)
        for minute in (30, 40, 55)
    )

    class Clean:
        def fetch(self, symbol, day, upto):
            return tuple(bar for bar in real if bar.stamp <= upto)

    class Dirty:
        def fetch(self, symbol, day, upto):
            return tuple(bar for bar in real if bar.stamp <= upto) + strays

    clean, _s1, _r1 = screener_for(config, scratch / "m4-clean", Clean(), symbols=(SYMBOL,))
    dirty, _s2, _r2 = screener_for(config, scratch / "m4-dirty", Dirty(), symbols=(SYMBOL,))
    clean.run_day()
    dirty.run_day()
    fields = ("phase", "side", "entry_paise", "stop_paise", "target_paise", "qty",
              "exit_paise", "exit_kind", "refusal")
    a, b = clean.states[SYMBOL], dirty.states[SYMBOL]
    same = [f for f in fields if getattr(a, f) == getattr(b, f)]
    say(f"decision fields identical with and without three post-15:29 bars : "
        f"{len(same)}/{len(fields)}")
    say(f"differing fields : {[f for f in fields if f not in same] or 'none'}")


# --- M13 / M14: the verification queue ------------------------------------------------------------


def plant(root: Path, day: date, label: str, mode: str = "live", verified: bool = False):
    recording = LiveRecording.at(root / f"{day.isoformat()}-{label}")
    recording.open_session({
        "trade_date": day.isoformat(), "mode": mode, "symbols": [SYMBOL],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    recording.record_bars(SYMBOL, (StoredBar(
        symbol=SYMBOL,
        stamp=datetime.combine(day, datetime.min.time()).replace(hour=9, minute=15),
        open_paise=100, high_paise=101, low_paise=99, close_paise=100, volume=10,
    ),), sweep="11:15", at=datetime.combine(day, datetime.min.time()))
    recording.record_alert(RecordedAlert(
        kind=ls.ALERT_ARMED, symbol=SYMBOL,
        at=datetime.combine(day, datetime.min.time()).replace(hour=11, minute=15),
        payload={"side": "long"},
    ))
    if verified:
        recording.write_verification({"trade_date": day.isoformat(), "verdicts": []})
    return recording


def m13_m14(scratch: Path) -> None:
    head("M13 / M14 -- two stacked unverified days, one of them holding two recordings")
    from acumen.calendar import TradingCalendar

    root = scratch / "live"
    monday, tuesday, wednesday = date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)
    for day, label in ((monday, "live"), (tuesday, "live"), (tuesday, "live-2")):
        plant(root, day, label)
    plant(root, date(2026, 8, 7), "live", verified=True)
    plant(root, monday, "replay", mode="replay")

    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    say(f"recordings on disk       : {sorted(p.name for p in root.iterdir())}")
    scan = getattr(refresh, "unverified_recordings", None)
    if scan is None:
        say("unverified_recordings    : ABSENT -- the job cannot ask which recordings "
            "nobody has judged")
    else:
        pending, unreadable = scan(root, before=wednesday)
        say(f"pending (oldest first)   : {[p.root.name for p in pending]}")
        say(f"unreadable               : {[str(p) for p, _why in unreadable]}")

    runner = getattr(refresh, "verify_prior_recordings", None) or getattr(
        refresh, "verify_yesterday"
    )
    result, step = runner(
        today=wednesday, calendar=calendar, data_root=scratch / "stores",
        cache_dir=scratch / "cache", recording_root=root,
    )
    named = re.findall(r"2026-\d\d-\d\d-live(?:-2)?", step.detail)
    say(f"step name                : {step.name}")
    say(f"step ok                  : {step.ok}")
    say(f"recordings NAMED by it   : {sorted(set(named))}")
    say(f"recordings it looked at  : {step.figures.get('pending', 1)}")


# --- M12 / M25 / L2 / L3 / L4: read straight off the shipped tree ---------------------------------


def m12() -> None:
    head("M12 -- the dashboard's type against DESIGN.md")
    design = (REPO / "DESIGN.md").read_text(encoding="utf-8")
    page = dash.render_html(
        day=DAY, now=datetime(2026, 6, 10, 11, 30), grouped={}, alerts=(), banner="",
    )
    css = page.split("<style>", 1)[1].split("</style>", 1)[0]
    families = {
        part.strip().strip("'\"")
        for stack in re.findall(r"font-family:([^;}]+)", css)
        for part in stack.split(",")
    }
    undocumented = sorted(f for f in families if f"`{f}`" not in design)
    say(f"font families on the page : {len(families)}")
    say(f"NOT in any DESIGN.md row  : {undocumented or 'none'}")

    pairs = set()
    for rule in css.split("}"):
        size = re.search(r"font-size:([^;}]+)", rule)
        if size is None:
            continue
        spacing = re.search(r"letter-spacing:([^;}]+)", rule)
        pairs.add((size.group(1), "0" if spacing is None else spacing.group(1)))
    rows = {
        (cells[3].strip(), cells[6].strip())
        for cells in (line.split("|") for line in design.splitlines() if line.count("|") >= 6)
        if len(cells) >= 8 and cells[3].strip().endswith("px")
    }
    rows = {(size, spacing if spacing != "0" else "0") for size, spacing in rows}
    say(f"(size, tracking) pairs    : {sorted(pairs)}")
    say(f"pairs in NO DESIGN.md row : {sorted(p for p in pairs if p not in rows) or 'none'}")


def m25() -> None:
    head("M25 -- where the live layer's aggregation import lives, and how far the tripwire sees")
    source = Path(ls.__file__).read_text(encoding="utf-8")
    module_level = "from .aggregate import Bar, aggregate_15min, in_session_bars" in source
    say(f"module-level aggregation import : {module_level}")
    tree = ast.parse(source)
    local = [
        parent.name
        for parent in ast.walk(tree)
        if isinstance(parent, ast.FunctionDef)
        for node in ast.walk(parent)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and "aggregate" in ast.unparse(node)
    ]
    say(f"function-local ones             : {local or 'none'}")
    calls = {}
    for parent in ast.walk(tree):
        if not isinstance(parent, ast.FunctionDef):
            continue
        for node in ast.walk(parent):
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                if name in ("day_profile", "gate_day", "evaluate_day", "aggregate_15min",
                            "in_session_bars"):
                    calls.setdefault(name, set()).add(parent.name)
    for name in sorted(calls):
        say(f"  {name:<18} called in {sorted(calls[name])}")


def lows() -> None:
    head("L2 / L3 / L4 -- the three that are readable straight off the shipped code")
    unstamped = {"side": "long", "entry_paise": 74_095, "dry_run": False}
    markers = tg.posture_markers(unstamped)
    say(f"L2  posture_markers(no mode)  : {markers or '()  <- read as a LIVE morning'}")

    alert = RecordedAlert(kind=ls.ALERT_TRIGGER, symbol=SYMBOL,
                          at=datetime(2026, 6, 10, 11, 30),
                          payload={"entry_paise": 100, "stale": False})
    say(f"L3  unvouched_price(stale, no age) : "
        f"{(ls.unvouched_price(alert) or 'None  <- forwarded')[:60]}")

    blind = ast.parse(Path(refresh.__file__).read_text(encoding="utf-8"))
    caught = []
    for node in ast.walk(blind):
        if isinstance(node, ast.FunctionDef) and node.name == "refresh_corporate_actions":
            for handler in (h for h in ast.walk(node) if isinstance(h, ast.ExceptHandler)):
                caught.append("bare Exception" if handler.type is None
                              else ast.unparse(handler.type))
    say(f"L4  the blind branch catches  : {caught}")


def main() -> int:
    from test_review14_fix import build_scratch_world
    from acumen.minute_store import MinuteStore

    scratch = Path(tempfile.mkdtemp(prefix="chunk15-flip-"))
    try:
        say(f"tree        : {REPO}")
        say(f"HEAD        : " + (REPO / ".git" / "HEAD").read_text(encoding="utf-8").strip())
        config_path = build_scratch_world(scratch / "world")
        config = load_config(config_path, include_env=False)
        real = tuple(MinuteStore.at(config.path("data_root") / "minute_store").minutes(
            SYMBOL, DAY
        ))
        say(f"probe day   : {SYMBOL} {DAY.isoformat()}  ({len(real)} stored 1-minute bars)")

        r1_census(config, scratch, real)
        r1_locked_file(config, scratch, real)
        m4(config, scratch, real)
        m4_no_new_trade(config, scratch, real)
        m13_m14(scratch)
        m12()
        m25()
        lows()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
