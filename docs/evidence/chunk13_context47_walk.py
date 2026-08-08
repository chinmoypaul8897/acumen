"""Chunk 13 fix evidence: CONTEXT 4.7 walked over real symbol-days.

Committed here beside its own output under CLAUDE.md's git rules (REVIEW_7 finding C3): a
session making claims from real store data commits the generating script and its output.

    python docs/evidence/chunk13_context47_walk.py [--out docs/evidence/chunk13_context47_walk.md]

**READ-ONLY over the stores.** It opens the daily store, the 1-minute lake and the instrument
master cache, and it writes exactly two things: this document, and a RECORDING per replayed day
into a directory the caller names (``--recording-root``, defaulting to a temporary directory
OUTSIDE the stores). Nothing under ``data_root`` is created, modified or removed.

What it proves, on the SAME three real symbol-days the chunk-13 build session walked:

1. **The oracle-free battery reaches the same answer as the full battery**, on days where the
   full battery passes -- same POC, same reference, same entry, stop, target, quantity, same
   exit, same alerts. CONTEXT 4.7 changed the validity test, not the strategy, and this is that
   claim measured rather than argued.
2. **The next pre-open's verification** runs the FULL battery over the recording the live pass
   produced, against the published bhavcopy, and reports both verdicts per symbol.
3. **The loud case is reachable and it is loud** -- the same recording re-verified against a
   deliberately wrong oracle (a bhavcopy volume the fold cannot reconcile) names the
   live-alerted symbol-day the oracle refuses. The wrong oracle is built in memory from the real
   row; no store is touched to produce it.
4. **Q-29**: the divergence between the Q-20 pin and the newest cached dump is reported over the
   walked symbols, as information.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import replace as dataclass_replace
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import live_refresh as refresh  # noqa: E402
from acumen import live_screener as ls  # noqa: E402
from acumen import signal_engine as se  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.instrument_master import cached_masters, load_master_file  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk13_context47_walk.md"

#: The same three days the chunk-13 build session's replay walk used, for the same reasons --
#: the one day three sessions have already agreed on every number of, plus a second symbol on
#: that day and a second date, so no shared-day coincidence can explain a match.
DAYS: tuple[tuple[str, date], ...] = (
    ("HDFCBANK", date(2026, 6, 10)),
    ("ICICIBANK", date(2026, 6, 10)),
    ("RELIANCE", date(2026, 6, 11)),
)


def rupees(paise) -> str:
    if paise is None:
        return "-"
    return f"{float(Fraction(paise) / 100):,.2f}"


class WrongOracle:
    """A daily store whose row for one day carries a volume the fold cannot reconcile.

    Built in memory around the REAL store, for one purpose: to reach CONTEXT 4.7's loud case on
    a real recording without touching a byte of the stores. Every other query passes straight
    through, so the day being judged is the real day in every respect but the one under test.
    """

    def __init__(self, inner, symbol: str, day: date, factor: int = 1000) -> None:
        self.inner = inner
        self.symbol = symbol
        self.day = day
        self.factor = factor

    def daily(self, symbol: str, start: date, end: date):
        frame = self.inner.daily(symbol, start, end)
        if symbol == self.symbol and start == self.day == end and not frame.empty:
            frame = frame.copy()
            frame.loc[frame.index[0], "volume"] = int(frame.iloc[0]["volume"]) * self.factor
        return frame

    def __getattr__(self, name):
        return getattr(self.inner, name)


def walk(symbol: str, day: date, recording_root: Path) -> dict:
    """Replay one symbol-day under BOTH batteries and verify the live one the next morning."""
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    store = MinuteStore.at(data_root / "minute_store")

    settled_rec = LiveRecording.at(recording_root / f"{symbol}-{day.isoformat()}-settled")
    live_rec = LiveRecording.at(recording_root / f"{symbol}-{day.isoformat()}-live")

    settled = ls.build_live_screener(
        day, (symbol,), source=StoredDayBarSource(store), recording=settled_rec,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    settled.run_day()

    # The SAME wiring, under CONTEXT 4.7's posture. Built from the replay screener rather than
    # through mode="live" because a live morning needs today's dump and today is not 2026-06-10;
    # everything that differs between the two paths is set here, explicitly and visibly.
    live = ls.build_live_screener(
        day, (symbol,), source=StoredDayBarSource(store), recording=live_rec,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    live.gates = {}
    live.posture = se.POSTURE_LIVE
    live.disclosure = ls.LIVE_DISCLOSURE
    live.run_day()

    settled_state = settled.states[symbol]
    live_state = live.states[symbol]

    bars = live.bars[symbol]
    live_battery = se.oracle_free_battery(day, bars)
    full_battery = settled.pipeline.gate_day(symbol, day, bars)

    verification = refresh.verify_prior_recording(live_rec, settled.pipeline, day=day)
    wrong = dataclass_replace(
        settled.pipeline, daily_store=WrongOracle(settled.pipeline.daily_store, symbol, day)
    )
    loud = refresh.verify_prior_recording(live_rec, wrong, day=day)

    return {
        "symbol": symbol,
        "day": day,
        "settled": settled_state,
        "live": live_state,
        "identical": settled_state == live_state,
        "settled_alerts": tuple(settled.sinks[0].alerts),
        "live_alerts": tuple(live.sinks[0].alerts),
        "live_battery": live_battery,
        "full_battery": full_battery,
        "verification": verification,
        "loud": loud,
        "stored_bars": len(store.minutes(symbol, day)),
        "bars_collected": len(bars),
        "manifest": live_rec.read_manifest(),
    }


def tick_divergence(symbols: tuple[str, ...]) -> dict:
    """QUESTIONS.md Q-29's detector, run as the ruling instructs: reported, deciding nothing."""
    config = load_config(include_env=False)
    cache = config.path("cache_root")
    pinned, _path, _sha = bt.pinned_master(cache, config.instrument_master)
    others = [p for p in cached_masters(cache) if p.name != config.instrument_master]
    if not others:
        return {"pin": config.instrument_master, "other": None, "divergence": {}}
    newest = others[-1]
    return {
        "pin": config.instrument_master,
        "other": newest.name,
        "divergence": ls.master_tick_divergence(pinned, load_master_file(newest), symbols),
    }


def render(walks: list[dict], divergence: dict) -> str:
    out: list[str] = []
    add = out.append
    add("# Chunk 13 fix evidence -- CONTEXT 4.7 walked over real symbol-days")
    add("")
    add("Generated by `docs/evidence/chunk13_context47_walk.py`, read-only over the stores.")
    add("")
    add("CONTEXT 4.7: *\"Live sweeps therefore run the ORACLE-FREE battery -- gate 2 (with the "
        "open test), Q-17 candle-level drops, candle validity -- per sweep ... The next pre-open "
        "runs the FULL battery on the prior recording against the published bhavcopy and reports "
        "both verdicts; a live-alerted day the oracle refuses is named loudly.\"* This document "
        "is those two sentences, measured on real days.")
    add("")

    add("## 1 -- The two batteries reach the SAME trade")
    add("")
    add("| symbol | day | POC | entry | SL | TP | qty | exit | state identical |")
    add("|---|---|---:|---:|---:|---:|---:|---|---|")
    for row in walks:
        state = row["live"]
        add(
            f"| {row['symbol']} | {row['day'].isoformat()} | {rupees(state.poc_paise)} | "
            f"{rupees(state.entry_paise)} | {rupees(state.stop_paise)} | "
            f"{rupees(state.target_paise)} | {state.qty or '-'} | "
            f"{state.exit_kind or state.phase} | "
            f"{'YES' if row['identical'] else 'NO'} |"
        )
    add("")
    add("`state identical` compares the WHOLE `SymbolState` produced by the settled replay "
        "against the one produced under CONTEXT 4.7's live posture -- phase, bias, side, POC, "
        "reference, entry, stop, target, quantity, exit kind, exit price, minute count and the "
        "last stamp. Not a selection of figures.")
    add("")
    add("| symbol | day | settled alerts | live alerts | every live alert disclosed |")
    add("|---|---|---|---|---|")
    for row in walks:
        alerts = row["live_alerts"]
        disclosed = (
            "n/a (no alert)" if not alerts else
            "YES" if all(a.payload.get("disclosure") == ls.LIVE_DISCLOSURE for a in alerts)
            else "**NO**"
        )
        add(
            f"| {row['symbol']} | {row['day'].isoformat()} | "
            f"{', '.join(a.kind for a in row['settled_alerts']) or 'none'} | "
            f"{', '.join(a.kind for a in alerts) or 'none'} | {disclosed} |"
        )
    add("")
    add("One rendered live alert, in full, as the trader receives it:")
    add("")
    add("```")
    for alert in walks[0]["live_alerts"]:
        add(ls.format_alert(alert))
    add("```")
    add("")

    add("## 2 -- What each battery actually said")
    add("")
    add("| symbol | day | bars | ORACLE-FREE verdict | FULL battery verdict | gate 2 missing | "
        "Q-17 strays |")
    add("|---|---|---:|---|---|---:|---:|")
    for row in walks:
        live_gates = row["live_battery"]
        full = row["full_battery"]
        add(
            f"| {row['symbol']} | {row['day'].isoformat()} | {row['bars_collected']:,} | "
            f"{'PASS' if live_gates.usable else 'REFUSED: ' + str(live_gates.refusal)} | "
            f"{'PASS' if full.usable else 'REFUSED: ' + str(full.refusal)} | "
            f"{live_gates.gate2.missing} | {live_gates.gate2.out_of_session} |"
        )
    add("")
    add("The oracle-free battery leaves gate 1 and gate 1P UNRUN, not failed -- "
        "`gate1 is None`, `gate1p is None`, `volume_reconciled is None`, posture `live`. On "
        "these days the two verdicts agree, which is the ordinary case and the one the ")
    add("measured residual quantifies (0.5229% of settled symbol-days over the ten-year ledger "
        "failed gate 1 alone; `docs/evidence/chunk13_q28_residual.md`).")
    add("")

    add("## 3 -- The next pre-open's verdict, on the recording each live pass wrote")
    add("")
    for row in walks:
        verification = row["verification"]
        add(f"**{row['symbol']} {row['day'].isoformat()}** -- {verification.headline}")
        add("")
        add("```")
        add(verification.render().rstrip())
        add("```")
        add("")

    add("## 4 -- THE LOUD CASE, reached on a real recording")
    add("")
    add("The same recordings, re-verified against a deliberately wrong oracle: the day's real "
        "bhavcopy row with its VOLUME multiplied by 1,000, built in memory around the real store "
        "so that not one byte of the stores is touched. Gate 1 then cannot reconcile, the FULL "
        "battery refuses a day the live pass alerted on, and this is what the operator sees.")
    add("")
    for row in walks:
        loud = row["loud"]
        alerted = bool(row["live_alerts"])
        add(f"**{row['symbol']} {row['day'].isoformat()}** -- "
            + ("the day ALERTED, so this is the loud case"
               if alerted else
               "the day produced NO alert, so this is the DISCRIMINATION: refused, reported, "
               "and deliberately not shouted"))
        add("")
        add("```")
        add(loud.render().rstrip())
        add("```")
        add("")
    shouted = [row for row in walks if row["loud"].refused_after_alert]
    quiet = [row for row in walks if row["live_alerts"] and not row["loud"].refused_after_alert]
    add(f"**{len(shouted)} of the {len([r for r in walks if r['live_alerts']])} days that "
        "alerted are named LOUDLY** -- the headline carries THE EXCHANGE'S RECORD REFUSES and "
        "the instruction *\"treat them as withdrawn\"*, and `RefreshReport.render()` appends that "
        "line AFTER its READY verdict so an operator who stops reading at READY still sees it. "
        f"There are {len(quiet)} days that alerted and were refused without being named, which "
        "is the number that must stay zero.")
    add("")
    add("The third day is the other half of the same rule and it matters as much: the oracle "
        "refuses it too, and because the tool never alerted on it the verdict is REPORTED and "
        "not shouted. A screen that shouted every refusal would spend, on the ordinary disclosed "
        "residual, exactly the attention the one alerted-then-refused morning needs.")
    add("")

    add("## 5 -- Q-29: the pin, the day's dump, and the difference between them")
    add("")
    add(f"Pinned master (the historical ledger's law): `{divergence['pin']}`")
    add("")
    if divergence["other"] is None:
        add("The cache holds only the pin, so there is no second dump to compare against today.")
    else:
        add(f"Newest other cached dump: `{divergence['other']}`")
        add("")
        if divergence["divergence"]:
            add("| symbol | pin tick (paise) | dump tick (paise) |")
            add("|---|---:|---:|")
            for symbol, (pin_tick, day_tick) in sorted(divergence["divergence"].items()):
                add(f"| {symbol} | {pin_tick} | {day_tick} |")
        else:
            add("**No tick divergence** over the walked symbols. The detector reports; it "
                "decides nothing, which is the ruling's own instruction.")
    add("")
    add("The recording of each live pass pins its master by filename AND sha256, which is what "
        "lets a replay run under the ticks the morning ran on:")
    add("")
    manifest = walks[0]["manifest"]
    add("```")
    add(f"master_file    {manifest['master_file']}")
    add(f"master_sha256  {manifest['master_sha256']}")
    add(f"mode           {manifest['mode']}")
    add(f"trade_date     {manifest['trade_date']}")
    add("```")
    add("")

    add("## 6 -- What this does NOT show")
    add("")
    add("* **A real live morning.** Every walk here is driven from the minute lake on a virtual "
        "clock; what is exercised is the live POSTURE (the oracle-free battery per sweep, the "
        "disclosure on every alert, the verification of the recording), not a broker session.")
    add("* **A day where the two batteries DISAGREE on a real trade.** These three days pass "
        "both. The frequency at which they can disagree is the measured residual, and the loud "
        "case above is what a disagreement looks like when it happens.")
    add("* **Money.** No PnL figure moves in this chunk; the screener sizes the alert and prices "
        "nothing.")
    add("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chunk13_context47_walk")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--recording-root", default="",
        help="where the replay recordings go; default a temporary directory OUTSIDE the stores",
    )
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="acumen-chunk13-47-") as scratch:
        root = Path(args.recording_root) if args.recording_root else Path(scratch)
        walks = []
        for symbol, day in DAYS:
            print(f"walking {symbol} {day.isoformat()} under both batteries", flush=True)
            walks.append(walk(symbol, day, root))
        divergence = tick_divergence(tuple(symbol for symbol, _day in DAYS))
        text = render(walks, divergence)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars)")

    bad = [row for row in walks if not row["identical"]]
    if bad:
        print("THE TWO BATTERIES DISAGREED on: "
              + ", ".join(f"{row['symbol']} {row['day']}" for row in bad))
        return 1
    # The loud case is owed on every day that ALERTED. A day with no alert cannot produce an
    # alerted-then-refused verdict, and demanding one of it would be demanding a false positive.
    alerted = [row for row in walks if row["live_alerts"]]
    silent = [row for row in alerted if not row["loud"].refused_after_alert]
    if not alerted:
        print("NO DAY ALERTED, so the loud case could not be exercised at all")
        return 1
    if silent:
        print("A DAY THAT ALERTED WAS REFUSED WITHOUT BEING NAMED: "
              + ", ".join(f"{row['symbol']} {row['day']}" for row in silent))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
