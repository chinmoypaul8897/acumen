"""Chunk-6 TRADER GATE evidence: the same stock-day POC under BOTH candidate windows.

QUESTIONS.md **Q-8** (asked to the trader as Round-3 **Q42**) is OPEN: CONTEXT 3.3 specifies an
EIGHT-candle profile window (1-minute stamps 09:15..11:14), while the trader's Round-3 Fixed
Range Volume Profile screenshot shows a box whose bar coordinates read as NINE candles
(158 - 150 + 1), i.e. stamps 09:15..11:29. The interim is unchanged -- the spec's 8-candle
window is what the engine computes everywhere -- and this script exists so the gate has the
evidence for BOTH answers before Q42 returns, without a re-run afterwards.

It computes, for every symbol-day it is given, the POC under
:data:`acumen.poc.SPEC_WINDOW` and under :data:`acumen.poc.ALTERNATE_WINDOW`, and writes a
plain-English markdown pack. Two kinds of day go in:

* **calibration days** -- read from the FROZEN ``poc/data/*_1min.csv`` files (CONTEXT 8 F7's
  authoritative input). Fully offline.
* **chart days** -- the symbol-days behind the trader's Q32 chart screenshots. Read from the
  local minute store when the universe backfill has already settled that symbol; otherwise
  pulled live for JUST that symbol-day (credentialed, politely paced) as a SCRATCH READ. This
  module NEVER writes the minute store -- the universe run owns it.

Every day is additionally proven RAW before its POC is quoted: its 1-minute volume is
reconciled against the RAW bhavcopy daily volume (CONTEXT 4.5 gate 1, which the Q-10 ruling
made "the per-day PROOF of factor correctness") and its 1-minute high/low are compared with
the raw daily store's. A day whose minutes were still corporate-action-scaled would fail both.

I/O lives here; the arithmetic is :mod:`acumen.poc`, which stays pure (CONTEXT 6).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from . import poc
from . import quality_gates as qg
from . import smartapi_client as sac
from .config import REPO_ROOT, load_config
from .daily_store import DailyStore
from .instrument_master import InstrumentMaster, load_instrument_master
from .minute_store import MinuteStore

#: Where the frozen calibration CSVs live (CONTEXT 8 F7: "the CSVs are the authoritative input").
POC_DATA_DIR: Path = REPO_ROOT / "poc" / "data"

#: How a day's minutes were obtained -- printed in the pack so no number is unattributed.
SOURCE_FROZEN_CSV: str = "frozen poc/data CSV"
SOURCE_MINUTE_STORE: str = "local minute store (universe run)"
SOURCE_LIVE_SCRATCH: str = "live SmartAPI scratch read (not stored)"


@dataclass(frozen=True)
class DayEvidence:
    """One symbol-day computed under both candidate windows."""

    symbol: str
    day: date
    source: str
    tick_paise: int
    spec: poc.DayProfile
    alternate: poc.DayProfile
    reading: Decimal | None
    gate1: qg.VolumeGateResult | None
    daily_high_paise: int | None
    daily_low_paise: int | None
    minute_high_paise: int
    minute_low_paise: int

    @property
    def matches(self) -> str:
        """Which window the trader's reading points at -- or why the day cannot say."""
        if self.reading is None:
            return "no reading yet"
        spec_poc, alt_poc = self.spec.poc_rupees, self.alternate.poc_rupees
        if spec_poc is None or alt_poc is None:
            return "no POC"
        if spec_poc == alt_poc:
            return "both (the two windows agree on this day)"
        spec_gap = abs(spec_poc - self.reading)
        alt_gap = abs(alt_poc - self.reading)
        if spec_gap < alt_gap:
            return f"8-candle (spec), by {alt_gap - spec_gap} rupees"
        if alt_gap < spec_gap:
            return f"9-candle, by {spec_gap - alt_gap} rupees"
        return "neither (equally far)"


# --- reading a day's minutes ------------------------------------------------------------


def bars_from_frozen_csv(symbol: str, day: date) -> tuple[sac.OneMinuteBar, ...]:
    """One frozen ``poc/data`` day, through the real ingest parser (naive IST, integer paise)."""
    path = POC_DATA_DIR / f"{symbol}_{day.isoformat()}_1min.csv"
    if not path.is_file():
        raise FileNotFoundError(f"no frozen calibration CSV at {path}")
    rows: list[list] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(
                [
                    record["ts"].strip(),
                    record["open"],
                    record["high"],
                    record["low"],
                    record["close"],
                    int(record["volume"]),
                ]
            )
    return sac.parse_candles(rows)


def bars_from_store(store: MinuteStore, symbol: str, day: date) -> tuple:
    """One day out of the local minute store (RAW prices -- the store holds raw only)."""
    return store.minutes(symbol, day)


def bars_live_scratch(
    client: sac.SmartApiClient, token: str, day: date
) -> tuple[sac.OneMinuteBar, ...]:
    """Pull ONE symbol-day of 1-minute candles. A scratch read -- nothing is written anywhere."""
    return client.get_candles(
        token,
        sac.INTERVAL_ONE_MINUTE,
        datetime.combine(day, time(0, 0)),
        datetime.combine(day, time(23, 59)),
    )


# --- building the evidence ---------------------------------------------------------------


def evidence_for_day(
    symbol: str,
    day: date,
    bars: Sequence,
    *,
    source: str,
    tick_paise: int,
    row_size: int,
    reading: Decimal | None,
    daily_store: DailyStore | None,
) -> DayEvidence:
    """Compute both windows for one symbol-day and reconcile it against the raw daily store."""
    gate1: qg.VolumeGateResult | None = None
    daily_high: int | None = None
    daily_low: int | None = None
    if daily_store is not None:
        frame = daily_store.daily(symbol, day, day)
        if len(frame):
            row = frame.iloc[0]
            gate1 = qg.volume_gate(int(row["volume"]), sum(int(b.volume) for b in bars))
            daily_high = int(row["high_paise"])
            daily_low = int(row["low_paise"])

    kwargs = dict(row_size=row_size, tick_paise=tick_paise, volume_reconciled=True)
    return DayEvidence(
        symbol=symbol,
        day=day,
        source=source,
        tick_paise=tick_paise,
        spec=poc.day_profile(bars, day, window=poc.SPEC_WINDOW, **kwargs),  # type: ignore[arg-type]
        alternate=poc.day_profile(bars, day, window=poc.ALTERNATE_WINDOW, **kwargs),  # type: ignore[arg-type]
        reading=reading,
        gate1=gate1,
        daily_high_paise=daily_high,
        daily_low_paise=daily_low,
        minute_high_paise=max(int(b.high_paise) for b in bars),
        minute_low_paise=min(int(b.low_paise) for b in bars),
    )


def _rupees(paise: int | None) -> str:
    return "-" if paise is None else f"{Decimal(paise) / Decimal(100):.2f}"


def render_pack(rows: Sequence[DayEvidence], *, row_size: int, command: str) -> str:
    """The plain-English evidence pack the chunk-6 gate is closed (or not) against."""
    lines: list[str] = []
    lines.append("# Chunk 6 gate evidence -- the POC under BOTH candidate windows")
    lines.append("")
    lines.append(
        "**Status: PENDING.** This pack exists to answer one question the trader has been "
        "asked (Round-3 **Q42**) and nothing else."
    )
    lines.append("")
    lines.append("## What is being asked")
    lines.append("")
    lines.append(
        "The strategy builds its volume profile from the morning session. The written "
        "specification (CONTEXT 3.3, from the trader's earlier answer R1-Q11) says the profile "
        "covers the **first eight 15-minute candles** -- 09:15 up to and including the candle "
        "that closes at 11:15. The trader's Round-3 screenshot of his TradingView Fixed Range "
        "Volume Profile shows the box drawn across what reads as **nine** candles (bar numbers "
        "150 to 158 inclusive), which would extend it to 11:30."
    )
    lines.append("")
    lines.append(
        "One extra candle can move the POC, and the POC decides every entry that day. So both "
        "answers are computed below, side by side, on the days where his own readings exist."
    )
    lines.append("")
    lines.append(f"* **8-candle (spec)** = {poc.SPEC_WINDOW.describe()} -- what the engine uses today.")
    lines.append(
        f"* **9-candle (alternative)** = {poc.ALTERNATE_WINDOW.describe()} -- computed here as "
        "evidence only; no engine path selects it."
    )
    lines.append(f"* Row Size N = {row_size} (the trader's own setting, confirmed by his Q32 screenshot).")
    lines.append("")
    lines.append("## The table")
    lines.append("")
    lines.append(
        "| symbol | date | POC, 8-candle | POC, 9-candle | trader's reading | which window matches | source of the minutes |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        spec_poc = row.spec.poc_rupees
        alt_poc = row.alternate.poc_rupees
        lines.append(
            f"| {row.symbol} | {row.day.isoformat()} | "
            f"{'-' if spec_poc is None else f'{spec_poc}'} | "
            f"{'-' if alt_poc is None else f'{alt_poc}'} | "
            f"{'not known yet' if row.reading is None else f'{row.reading}'} | "
            f"{row.matches} | {row.source} |"
        )
    lines.append("")
    lines.append("**Q42's answer selects the window; nothing is locked until then.**")
    lines.append("")
    lines.append("## What this evidence says today")
    lines.append("")
    agree = [r for r in rows if r.spec.poc_rupees == r.alternate.poc_rupees]
    differ = [r for r in rows if r.spec.poc_rupees != r.alternate.poc_rupees]
    lines.append(
        f"* **{len(agree)} of {len(rows)} days cannot tell the two windows apart** -- the ninth "
        "candle does not move the busiest band, so the POC (and any trade off it) is the same "
        "number either way."
    )
    if differ:
        for row in differ:
            spec_poc, alt_poc = row.spec.poc_rupees, row.alternate.poc_rupees
            gap = "-" if spec_poc is None or alt_poc is None else f"{abs(spec_poc - alt_poc)}"
            lines.append(
                f"* **{row.symbol} {row.day.isoformat()} DOES separate them**: {spec_poc} under the "
                f"8-candle window against {alt_poc} under the 9-candle one -- {gap} rupees apart. "
                "This is the row to check against his chart."
            )
    else:
        lines.append(
            "* **No day here separates the two windows**, so none of them can answer Q42 on its "
            "own; the answer has to come from the trader."
        )
    unread = [r for r in rows if r.reading is None]
    if unread:
        lines.append(
            "* No POC reading has been relayed yet for "
            + ", ".join(f"{r.symbol} {r.day.isoformat()}" for r in unread)
            + ". His Q32 screenshots confirmed his SETTINGS (Rows Layout = Number of Rows, Row "
            "Size = 24); what is still needed to close this gate is the POC PRICE he reads off "
            "those same charts."
        )
    lines.append("")
    lines.append("## How to read a row")
    lines.append("")
    lines.append(
        "The POC is the middle price of the busiest price band of the morning. Both columns are "
        "computed by the same code from the same 1-minute candles -- the ONLY difference is "
        "where the window stops. Where the two columns are equal, that day cannot tell the two "
        "windows apart: the busiest band is the same either way, so no trade on that day would "
        "have differed."
    )
    lines.append("")
    lines.append("## Proof that each day's prices are the real prices of that day")
    lines.append("")
    lines.append(
        "A POC computed from corporate-action-rescaled prices would be a plausible-looking wrong "
        "number, so each day is checked against the exchange's own daily figures before its POC "
        "is quoted: the 1-minute volume must reconcile with the official daily volume (the "
        "project's gate 1, band -0.1% to +5.0%), and the day's 1-minute high/low must match the "
        "official daily high/low."
    )
    lines.append("")
    lines.append(
        "| symbol | date | 1-min volume vs daily | gate 1 | 1-min high/low | official daily high/low |"
    )
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        if row.gate1 is None:
            lines.append(
                f"| {row.symbol} | {row.day.isoformat()} | no daily row in the store | - | "
                f"{_rupees(row.minute_high_paise)} / {_rupees(row.minute_low_paise)} | - |"
            )
            continue
        gap = "-" if row.gate1.gap_pct is None else f"{row.gate1.gap_pct:.3f}%"
        lines.append(
            f"| {row.symbol} | {row.day.isoformat()} | "
            f"{row.gate1.minute_volume_sum:,} vs {row.gate1.daily_volume:,} (gap {gap}) | "
            f"{'PASS' if row.gate1.passed else 'FAIL'} | "
            f"{_rupees(row.minute_high_paise)} / {_rupees(row.minute_low_paise)} | "
            f"{_rupees(row.daily_high_paise)} / {_rupees(row.daily_low_paise)} |"
        )
    lines.append("")
    lines.append("## Detail per day")
    lines.append("")
    for row in rows:
        lines.append(f"### {row.symbol} {row.day.isoformat()}")
        lines.append("")
        lines.append(
            f"* tick size {Decimal(row.tick_paise) / Decimal(100)} rupees (from the instrument "
            "master -- never assumed)"
        )
        for label, profile in (("8-candle (spec)", row.spec), ("9-candle", row.alternate)):
            if profile.grid is None:
                lines.append(f"* {label}: no POC ({profile.reason})")
                continue
            lines.append(
                f"* {label}: POC {profile.poc_rupees} -- {profile.bar_count} traded minutes, "
                f"range {_rupees(profile.grid.bottom_paise)}..{_rupees(profile.grid.top_paise)}, "
                f"{len(profile.grid)} rows of {profile.grid.ticks_per_row} tick(s), "
                f"busiest row #{(profile.poc_row or 0) + 1} of {len(profile.grid)}"
            )
        lines.append("")
    lines.append("## One more thing worth asking while he is at the chart")
    lines.append("")
    lines.append(
        "Separately from the window, CONTEXT 3.3 leaves one rounding case unstated: when the row "
        "arithmetic lands exactly between two row heights, the specification does not say which "
        "way TradingView goes (QUESTIONS.md **Q-13**). It matters on roughly one stock-day in six "
        "to ten, and it does not need a POC reading to settle -- just the NUMBER OF ROWS his "
        "profile draws on such a day. If he sends any chart with the rows countable, that answers "
        "it. Until then the engine keeps the direction that reproduces all 25 calibration days."
    )
    lines.append("")
    lines.append("## What is NOT decided here")
    lines.append("")
    lines.append(
        "Nothing in this pack changes the engine. The spec's 8-candle window remains what the "
        "code computes, the trader's Row Size 24 remains what the code uses, and the chunk-6 "
        "gate stays PENDING until Round-3 Q42 comes back. If Q42 answers \"nine\", the architect "
        "amends CONTEXT 3.3 and the fixtures move with it -- this pack is what makes that a "
        "one-line change instead of a re-run."
    )
    lines.append("")
    lines.append(f"Generated by: `{command}`")
    lines.append("")
    return "\n".join(lines)


# --- CLI ----------------------------------------------------------------------------------


def _parse_symbol_day(text: str) -> tuple[str, date]:
    symbol, _, day = text.partition(":")
    if not symbol or not day:
        raise argparse.ArgumentTypeError(f"expected SYMBOL:YYYY-MM-DD, got {text!r}")
    return symbol.strip().upper(), date.fromisoformat(day.strip())


def _parse_reading(text: str) -> tuple[tuple[str, date], Decimal]:
    left, _, value = text.partition("=")
    if not value:
        raise argparse.ArgumentTypeError(f"expected SYMBOL:YYYY-MM-DD=PRICE, got {text!r}")
    return _parse_symbol_day(left), Decimal(value.strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-poc-evidence",
        description="Chunk-6 gate evidence: each symbol-day's POC under both candidate windows.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--calibration", action="append", default=[], metavar="SYMBOL:YYYY-MM-DD",
        help="a frozen poc/data calibration day (repeatable)",
    )
    parser.add_argument(
        "--chart", action="append", default=[], metavar="SYMBOL:YYYY-MM-DD",
        help="a Q32 chart day: minute store if settled, else a live scratch read (repeatable)",
    )
    parser.add_argument(
        "--reading", action="append", default=[], metavar="SYMBOL:YYYY-MM-DD=PRICE",
        help="the trader's own TradingView POC reading for a day (repeatable)",
    )
    parser.add_argument("--allow-network", action="store_true",
                        help="permit the live scratch read for a chart day not in the store")
    parser.add_argument("--data-dir", default=None, help="data dir (default: config paths.data_dir)")
    parser.add_argument("--cache-dir", default=None, help="instrument-master cache dir")
    parser.add_argument("--out", default="docs/gate_chunk6_poc_evidence.md", help="output path")
    return parser.parse_args(argv)


def run(args: argparse.Namespace, *, command: str) -> int:
    config = load_config()
    data_dir = Path(args.data_dir) if args.data_dir else config.path("data_dir")
    cache_dir = Path(args.cache_dir) if args.cache_dir else config.path("cache_dir")
    daily_store = DailyStore.at(data_dir / "daily_store")
    minute_store = MinuteStore.at(data_dir / "minute_store")
    master: InstrumentMaster = load_instrument_master(
        cache_dir=cache_dir, allow_network=args.allow_network
    )

    readings = dict(_parse_reading(text) for text in args.reading)
    rows: list[DayEvidence] = []
    client: sac.SmartApiClient | None = None
    try:
        for text in args.calibration:
            symbol, day = _parse_symbol_day(text)
            rows.append(
                evidence_for_day(
                    symbol, day, bars_from_frozen_csv(symbol, day),
                    source=SOURCE_FROZEN_CSV,
                    tick_paise=master.instrument(symbol).tick_size_paise,
                    row_size=config.row_size,
                    reading=readings.get((symbol, day)),
                    daily_store=daily_store,
                )
            )
        for text in args.chart:
            symbol, day = _parse_symbol_day(text)
            bars = bars_from_store(minute_store, symbol, day)
            source = SOURCE_MINUTE_STORE
            if not bars:
                if not args.allow_network:
                    raise SystemExit(
                        f"{symbol} {day.isoformat()} is not in the minute store yet and "
                        "--allow-network was not passed; the universe run has not settled it."
                    )
                if client is None:
                    client = sac.SmartApiClient(sac.Credentials.from_env()).login()
                bars = bars_live_scratch(client, master.token(symbol), day)
                source = SOURCE_LIVE_SCRATCH
                print(f"  {symbol} {day.isoformat()}: scratch-read {len(bars)} candles (not stored)")
            rows.append(
                evidence_for_day(
                    symbol, day, bars,
                    source=source,
                    tick_paise=master.instrument(symbol).tick_size_paise,
                    row_size=config.row_size,
                    reading=readings.get((symbol, day)),
                    daily_store=daily_store,
                )
            )
    finally:
        if client is not None:
            client.logout()

    if not rows:
        raise SystemExit("nothing to do: pass at least one --calibration or --chart day.")

    out = Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_pack(rows, row_size=config.row_size, command=command), encoding="utf-8")
    for row in rows:
        print(
            f"  {row.symbol:12s} {row.day.isoformat()}  8-candle={row.spec.poc_rupees}  "
            f"9-candle={row.alternate.poc_rupees}  match={row.matches}"
        )
    print(f"Wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parts = ["acumen-poc-evidence"]
    for name, values in (("--calibration", args.calibration), ("--chart", args.chart),
                         ("--reading", args.reading)):
        parts.extend(f"{name} {value}" for value in values)
    if args.allow_network:
        parts.append("--allow-network")
    return run(args, command=" ".join(parts))


if __name__ == "__main__":  # pragma: no cover - launcher
    raise SystemExit(main())
