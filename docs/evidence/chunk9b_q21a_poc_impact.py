"""Q-21(a): would clamping a malformed bar's low move that day's CONTEXT 3.3 POC?

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_q21a_poc_impact.py --out docs/evidence/chunk9b_q21a_poc_impact.md

OFFLINE and READ-ONLY on both stores. Nothing here writes, renames or deletes anything under
`data_root`, and NOTHING here decides anything.

**THIS SCRIPT DECIDES NOTHING.** The architect's Q-21(b) ruling of 03-Aug-2026 says of Q-21(a):
*"whether gate 2's enumeration gains the OPEN test -- is DEFERRED pending measurement (Part C);
the sealed battery is not touched by this session."* So this measures, prints, and stops. No
gate, no threshold, no enumeration and no fixture is changed anywhere by this file; the sealed
CONTEXT 4.5/4.6 battery is untouched and `acumen.quality_gates` is not modified.

WHAT IS MEASURED, and why this comparison and not another:

The 48 malformed bars in the lake are all stamped 09:15, which is INSIDE CONTEXT 3.3's profile
window (1-minute stamps 09:15..11:14). So each of those dates, taken as a TRADE day, has its POC
built from a bar that cannot exist. The natural repair for the 47 whose only fault is an open
BELOW the low is to widen the bar's range down to its own opening print -- `low = min(low, open)`
-- because the open IS a traded price and a bar's low cannot be above it. The comparison is
therefore:

    (a) the bar exactly AS STORED, which is what a run today would use; against
    (b) the same day with every bar's low clamped to `min(low, open)`.

The clamp is written as a rule over EVERY bar rather than as a patch to one, because on a
well-formed bar it is the identity (`open >= low` already), so nothing but the malformed bars can
move. A bar whose fault is the other way round -- an open ABOVE the high, which several of the 47
have -- is NOT repaired by this clamp and is reported as unchanged, honestly, rather than being
quietly widened at the top too: the architect asked for this clamp, and inventing a second one
would answer a question nobody put.

The POC is computed by the REAL engine (`acumen.poc.day_profile`) at the RUN's own inputs: the
config's Row Size and the symbol's own tick from the Q-20 PINNED instrument master. The day's
bars are first passed through `aggregate.in_session_bars`, which is the CONTEXT 7-E2 candle-level
drop `SignalPipeline.stock_day` applies before it builds a profile -- so the window this script
builds is the window the strategy would have seen.

ONE DISCLOSED FORCING. `day_profile` refuses to build a profile for a day whose gate-1 verdict is
not PASS. The architect's question is what the POC WOULD be on these days as trade days, so
`volume_reconciled=True` is passed unconditionally and each day's REAL battery verdict is printed
beside its POC instead. A day the battery refuses is marked in the table and would produce no POC
and no trade in a real run; its numbers are still measured, because "the gate already stops it"
is an answer the architect can only weigh if the size of what is being stopped is on the page.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import glob
import sys
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from datetime import date, datetime  # noqa: E402

from acumen import backtest as bt  # noqa: E402
from acumen import poc as poc_engine  # noqa: E402
from acumen import run_backtest as rb  # noqa: E402
from acumen.aggregate import in_session_bars  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.instrument_master import load_master_file  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402
from acumen.signal_engine import SignalPipeline  # noqa: E402

SCAN_COLUMNS = ["stamp", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]


@dataclass(frozen=True)
class Bar:
    """One 1-minute bar in the shape the POC engine consumes. Immutable, so the clamp COPIES."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


def clamp_low(bar: Bar) -> Bar:
    """``low = min(low, open)`` -- the identity on any well-formed bar (``open >= low``)."""
    return Bar(
        stamp=bar.stamp,
        open_paise=bar.open_paise,
        high_paise=bar.high_paise,
        low_paise=min(bar.low_paise, bar.open_paise),
        close_paise=bar.close_paise,
        volume=bar.volume,
    )


def faults(o: int, h: int, l: int, c: int) -> list[str]:
    """Everything impossible about one stored bar, named (the Q-21 evidence's own predicate)."""
    out: list[str] = []
    if h < l:
        out.append("H<L")
    if not (l <= o <= h):
        out.append("O outside [L,H]")
    if not (l <= c <= h):
        out.append("C outside [L,H]")
    return out


def scan_lake(data: Path, symbols) -> tuple[list[dict], int, int]:
    """Every stored 1-minute bar whose open or close is outside ``[low, high]``. READ-ONLY.

    Vectorised in pyarrow rather than looped in Python: the predicate is the SAME one
    `chunk9b_q21_malformed_bar.py` used (``high < low`` or open/close outside the range), asked
    of ~150 million bars, and a per-row Python loop over that is minutes of pure interpreter.
    """
    found: list[dict] = []
    files = bars = 0
    for symbol in symbols:
        pattern = str(data / "minute_store" / "minute" / symbol / f"{symbol}_*.parquet")
        for path in sorted(glob.glob(pattern)):
            files += 1
            table = pq.read_table(path, columns=SCAN_COLUMNS)
            bars += table.num_rows
            o = table.column("open_paise")
            h = table.column("high_paise")
            low = table.column("low_paise")
            c = table.column("close_paise")
            bad = pc.or_(
                pc.less(h, low),
                pc.or_(
                    pc.or_(pc.less(o, low), pc.greater(o, h)),
                    pc.or_(pc.less(c, low), pc.greater(c, h)),
                ),
            )
            for index in pc.indices_nonzero(bad).to_pylist():
                found.append(
                    {
                        "symbol": symbol,
                        "stamp": table.column("stamp")[index].as_py(),
                        "open": o[index].as_py(),
                        "high": h[index].as_py(),
                        "low": low[index].as_py(),
                        "close": c[index].as_py(),
                        "volume": table.column("volume")[index].as_py(),
                    }
                )
    return found, files, bars


def stored_bars(store: MinuteStore, symbol: str, day: date) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            stamp=b.stamp,
            open_paise=int(b.open_paise),
            high_paise=int(b.high_paise),
            low_paise=int(b.low_paise),
            close_paise=int(b.close_paise),
            volume=int(b.volume),
        )
        for b in store.minutes(symbol, day)
    )


def profile_of(bars, day: date, *, row_size: int, tick_paise: int):
    """CONTEXT 3.3 for one day, or the exception it refused with. Never raises to the caller."""
    session, _dropped = in_session_bars(bars)
    if not session:
        return None, "no in-session bars"
    try:
        return (
            poc_engine.day_profile(
                session,
                day,
                row_size=row_size,
                tick_paise=tick_paise,
                # DISCLOSED FORCING -- see the module docstring. The question is what the POC
                # would be on this day as a TRADE day; the day's real battery verdict is printed
                # in its own column rather than silently suppressing the measurement.
                volume_reconciled=True,
            ),
            "",
        )
    except poc_engine.PocError as exc:
        return None, f"PocError: {exc}"


def rupees(paise: Fraction | None) -> str:
    if paise is None:
        return "--"
    return f"{float(paise) / 100:,.3f}".rstrip("0").rstrip(".")


def paise(value: Fraction) -> str:
    """An exact paise figure as a decimal. A POC is a row MIDPOINT and may be HALF a paisa
    (CONTEXT 3.3 / 7-E11), so a difference of two POCs can legally be ``x.5`` -- rendered here
    as ``-2.5`` rather than as the raw ``-5/2`` the exact Fraction prints."""
    text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--symbols", default=None, help="comma-separated subset (a smoke run)")
    args = parser.parse_args()

    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    master = load_master_file(config.instrument_master_path())
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )

    register = bt.load_residual_register(data / bt.RESIDUAL_LEDGER_RELPATH)
    universe = list(rb.settled_symbols(register))
    if args.symbols:
        universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    found, files, bars = scan_lake(data, universe)

    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# Q-21(a) evidence -- the POC impact of clamping a malformed bar's low")
    add()
    add(
        "Generated by `docs/evidence/chunk9b_q21a_poc_impact.py`, offline and READ-ONLY over the "
        "stores. No file under `data_root` is written, renamed or removed by this script."
    )
    add()
    add(
        "**NOTHING IS DECIDED HERE.** The architect's Q-21(b) ruling defers Q-21(a) -- whether "
        "CONTEXT 4.5's gate-2 enumeration gains the OPEN test -- *\"pending measurement\"*, and "
        "adds that *\"the sealed battery is not touched by this session\"*. This file is that "
        "measurement and nothing else: no gate, threshold, enumeration or fixture is changed by "
        "the session that produced it, and `src/acumen/quality_gates.py` is byte-identical to "
        "its committed blob."
    )
    add()

    add("## 1. The population, re-read from the machine")
    add()
    add(
        f"Scanned **{bars:,} stored 1-minute bars** in {files:,} parquet files across "
        f"{len(universe)} settled symbols for the impossible shape (open or close outside "
        "`[low, high]`, or high below low) -- the same predicate the Q-21 evidence used, asked "
        "again here rather than read off that file, so this document stands on its own."
    )
    add()
    add(f"**{len(found)} malformed bar(s)**, on {len({h['stamp'].date() for h in found})} date(s).")
    add()

    add("## 2. Each malformed-bar day AS A TRADE DAY: the CONTEXT 3.3 POC, twice")
    add()
    add(
        "Row Size N = **" + str(config.row_size) + "** (config, CONTEXT 3.3) and each symbol's "
        "own tick from the PINNED master `"
        + Path(config.instrument_master_path()).name
        + "` (QUESTIONS.md Q-20). `stored` is the day exactly as the store holds it -- what a "
        "run today would build a profile from. `clamped` is the same day with every bar's low "
        "set to `min(low, open)`, which is the identity on every well-formed bar."
    )
    add()
    add(
        "| symbol | day | tick | fault | clamp moves the bar | POC stored | POC clamped | POC "
        "moved | move (paise) | rows stored | rows clamped | row change | profile bottom move "
        "(paise) | day's battery |"
    )
    add("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    moved_rows = 0
    moved_poc = 0
    clamp_bites = 0
    unbuildable = 0
    battery_refused = 0
    details: list[str] = []
    movers: list[str] = []

    for hit in sorted(found, key=lambda h: (h["symbol"], h["stamp"])):
        symbol, day = hit["symbol"], hit["stamp"].date()
        tick = master.instrument(symbol).tick_size_paise
        original = stored_bars(minute_store, symbol, day)
        clamped_bars = tuple(clamp_low(bar) for bar in original)
        bar_moved = clamped_bars != original
        clamp_bites += 1 if bar_moved else 0

        a, why_a = profile_of(original, day, row_size=config.row_size, tick_paise=tick)
        b, why_b = profile_of(clamped_bars, day, row_size=config.row_size, tick_paise=tick)

        verdict = pipeline.gate_day(symbol, day, minute_store.minutes(symbol, day))
        gate = "PASSES" if verdict.usable else f"FAILS: {verdict.refusal}"
        battery_refused += 0 if verdict.usable else 1

        buildable = (
            a is not None and a.grid is not None and b is not None and b.grid is not None
        )
        poc_a = a.poc_paise if a is not None else None
        poc_b = b.poc_paise if b is not None else None
        rows_a = str(len(a.grid.rows)) if a is not None and a.grid is not None else "--"
        rows_b = str(len(b.grid.rows)) if b is not None and b.grid is not None else "--"
        if not buildable:
            unbuildable += 1
            move = row_change = bottom_move = "--"
            poc_moved = "n/a"
            details.append(
                f"* **{symbol} {day}** -- no profile could be built. "
                f"{why_a or (a.reason if a is not None else '')}"
            )
        else:
            same = poc_a == poc_b
            poc_moved = "no" if same else "**YES**"
            moved_poc += 0 if same else 1
            move = "0" if same else paise(poc_b - poc_a)
            delta_rows = len(b.grid.rows) - len(a.grid.rows)
            row_change = "0" if delta_rows == 0 else f"**{delta_rows:+d}**"
            moved_rows += 1 if delta_rows else 0
            bottom_move = str(b.grid.bottom_paise - a.grid.bottom_paise)
            if not same:
                movers.append(
                    f"* **{symbol} {day}** -- POC {rupees(poc_a)} -> {rupees(poc_b)} "
                    f"({move} paise), rows {len(a.grid.rows)} -> {len(b.grid.rows)}"
                )

        add(
            f"| {symbol} | {day} | {tick} | "
            f"{'; '.join(faults(hit['open'], hit['high'], hit['low'], hit['close']))} "
            f"| {'yes' if bar_moved else 'no'} | {rupees(poc_a)} | {rupees(poc_b)} | {poc_moved} "
            f"| {move} | {rows_a} | {rows_b} | {row_change} | {bottom_move} | {gate} |"
        )

    add()
    add(
        "`profile bottom move` is the mechanism column: CONTEXT 3.3 takes `bottom = min(low)` "
        "over the window, so the clamp can only move a POC by moving that bottom (which re-sizes "
        "`totalTicks`, hence `tpr`, hence every row edge) or by re-spreading the one bar's own "
        "volume across the rows its widened range now overlaps. A bottom move of 0 means some "
        "OTHER bar in the 09:15..11:14 window already traded at or below the malformed open, so "
        "the grid is untouched and only that bar's prorata share can shift."
    )
    add()
    if details:
        add("Days with no computable profile:")
        add()
        lines.extend(details)
        add()

    add("## 3. The totals")
    add()
    add("| measure | count |")
    add("|---|---|")
    add(f"| malformed-bar days measured | {len(found)} |")
    add(f"| ...where `low = min(low, open)` actually CHANGES the bar | {clamp_bites} |")
    add(f"| ...where the day's POC MOVES under the clamp | **{moved_poc}** |")
    add(f"| ...where the profile's ROW COUNT changes under the clamp | **{moved_rows}** |")
    add(f"| ...where no profile can be built at all (either side) | {unbuildable} |")
    add(f"| ...where the day's own CONTEXT 4.6 battery already REFUSES it | {battery_refused} |")
    add()
    add(
        f"The clamp is a no-op on **{len(found) - clamp_bites}** of the {len(found)} bars, "
        "because their fault is an open ABOVE the high rather than below the low -- widening the "
        "low cannot repair those, and this session did not invent a second clamp to try."
    )
    add()
    if movers:
        add(f"### The {len(movers)} day(s) whose POC moves")
        add()
        lines.extend(movers)
        add()
    add(
        "**For the architect.** The POC decides every trade's reference, trigger, entry, stop "
        "and target (CONTEXT 3.4), so a POC that moves is a different trade and a POC that does "
        "not move is a bar shape that costs the strategy nothing on that day. Whether CONTEXT "
        "4.5's gate 2 should enumerate the OPEN is that call, on these numbers. Nothing in this "
        "repo has been changed either way."
    )
    add()

    _emit(lines, args.out)
    return 0


def _emit(lines: list[str], out: Path | None) -> None:
    text = "\n".join(lines).rstrip() + "\n"
    if out is None:
        print(text)
        return
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(lines)} lines)")


if __name__ == "__main__":
    raise SystemExit(main())
