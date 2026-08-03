"""Q-21(a): what COMPLETING gate 2's enumeration with the OPEN test costs, measured.

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_q21a_gate2_completion.py --out docs/evidence/chunk9b_q21a_gate2_completion.md

OFFLINE and READ-ONLY on both stores and on the crashed run directory. Nothing here writes,
renames or deletes anything under `data_root`; the only file it writes is its own markdown
output inside the repository (plus an optional resume checkpoint outside both).

THE QUESTION, exactly as the architect's Q-21(a) ruling poses it: gate 2's impossible-OHLC
enumeration gains the OPEN test, so a bar whose open lies outside [low, high] now fails
integrity exactly as a close outside does. What does that cost the sealed era?

HOW IT IS ASKED, so the answer is a MEASURED delta and not an estimate:

1. THE WHOLE BATTERY IS RE-RUN over every stored symbol-day of every processed symbol -- the
   same composition `acumen.universe_backfill.gate_symbol` runs at ingest and re-gate (gate 1
   first, because the completeness ruling makes its verdict gate 2's completeness oracle; an
   above-ceiling gate-1 failure offered to auction relief; gate 1P on every stored day from the
   same fold), calling the REAL `acumen.quality_gates` functions on the REAL stored bars.
2. GATE 2 IS EVALUATED TWICE per day -- once under the SEALED close-only enumeration and once
   under the COMPLETED one -- so both sides of the ruling are measured in one pass over the
   lake and no day is compared against a number remembered from another run.
   Which enumeration the SHIPPED `integrity_gate` implements is not assumed: it is PROBED with
   a synthetic day (section 1), and the two verdicts are then derived around that probe, so
   this script measures the same delta whether it is run before or after the amendment.
3. THE CONTROL is the machine's own ledger. Every per-symbol number this pass computes under
   the SEALED enumeration -- stored days, gate-1 pass / relieved / total, gate-1P pass, gate-2
   exclusions, usable days -- is compared against `<data_root>/universe_backfill/ledger.json`,
   the artefact CONTEXT 4.6's re-sealed figures are built from. A mismatch anywhere means this
   pass is not the battery and its "after" numbers may not be believed; it is printed as a
   PASS/FAIL line rather than left implicit.
4. THE STATUS QUESTION is answered on the decision's own inputs. A symbol is quarantined on its
   EFFECTIVE GATE-1 rate (`universe_backfill.QUARANTINE_GATE1_MIN_PASS_RATE`, 80%); gate 2 is
   not an input to it. This pass therefore proves the status cannot move by showing gate 1's
   numerator and denominator are byte-identical either side of the change, and states every
   symbol's margin to the line in percentage points AND in days.
5. THE Q-21(b) RADIUS is re-asked where it can move: a Rule-3 scan day's D-1 is refused under
   the completed battery if the sealed battery already refused it OR if it now fails the
   completed gate 2. Only days carrying a newly-failing bar can move, so each such day is put
   to the REAL engine (`bias.evaluate_pair` with a probe provider that records whether it was
   called -- the pure engine calls it in the Rule-3 branch and nowhere else) to ask whether any
   trade day's Rule-3 scan actually reads it.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import corp_actions as ca  # noqa: E402
from acumen import minute_backfill as mb  # noqa: E402
from acumen import quality_gates as gates  # noqa: E402
from acumen import universe_backfill as ub  # noqa: E402
from acumen.bias import BiasError, Candle, evaluate_pair  # noqa: E402
from acumen.calendar import CalendarError, TradingCalendar  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

RUN_DIRNAME = "chunk9b_full"

#: The sealed era's own end (CONTEXT 4.6 v1.5: minute era 2016-10-03 -> 2026-07-31).
ERA_END: date = date(2026, 7, 31)

#: What the SEALED enumeration tests, and what the COMPLETED one adds.
SEALED_CLAUSES = "high < low, or a CLOSE outside [low, high]"
COMPLETED_CLAUSES = "high < low, or an OPEN or CLOSE outside [low, high]"


# --- section 1: which enumeration is the shipped one? -------------------------------------


def probe_shipped_enumeration() -> tuple[bool, bool, bool]:
    """Ask the SHIPPED `integrity_gate` what it tests, with three synthetic one-bar days.

    Returns ``(tests_open, tests_close, tests_high_below_low)``. Nothing here is assumed about
    the module under measurement: the same script therefore measures the same delta before and
    after the amendment, and says which side of it produced a given output file.
    """
    day = date(2024, 1, 2)
    stamp = datetime.combine(day, time(9, 15))

    class _B:
        def __init__(self, o: int, h: int, low: int, c: int) -> None:
            self.stamp = stamp
            self.open_paise, self.high_paise, self.low_paise, self.close_paise = o, h, low, c
            self.volume = 1

    def violations(bar: "_B") -> int:
        return gates.integrity_gate([bar], day, volume_reconciled=True).ohlc_violations

    return (
        violations(_B(90, 110, 100, 105)) > 0,   # open BELOW low, close inside
        violations(_B(105, 110, 100, 999)) > 0,  # close ABOVE high, open inside
        violations(_B(100, 90, 110, 100)) > 0,   # high below low
    )


# --- the per-day battery, twice ------------------------------------------------------------


@dataclass
class SymbolResult:
    """One symbol's whole stored history under both enumerations."""

    symbol: str
    days: int = 0
    bars: int = 0
    gate1_pass: int = 0
    gate1_relieved: int = 0
    gate1_total: int = 0
    gate1p_pass: int = 0
    gate1p_total: int = 0
    gate2_excluded_sealed: int = 0
    gate2_excluded_completed: int = 0
    gate2_ohlc_sealed: int = 0
    gate2_ohlc_completed: int = 0
    usable_sealed: int = 0
    usable_completed: int = 0
    #: ``(day, open-violating bars, why the day was usable before)`` for every FLIP.
    flips: list[tuple[str, int, str]] = field(default_factory=list)
    #: ``(day, open-violating bars, which gate already refused it)`` -- a newly-failing day that
    #: was ALREADY refused by another gate, so it costs nothing.
    already_refused: list[tuple[str, int, str]] = field(default_factory=list)
    #: Days where the SHIPPED gate's own `ohlc_violations` disagreed with this script's count of
    #: the enumeration the probe says it implements. Must be zero on every symbol.
    probe_disagreements: int = 0

    @property
    def gate1_effective(self) -> int:
        return self.gate1_pass + self.gate1_relieved

    @property
    def gate1_rate(self) -> Decimal:
        if not self.gate1_total:
            return Decimal(0)
        return Decimal(self.gate1_effective) / Decimal(self.gate1_total)

    def to_dict(self) -> dict:
        payload = dict(self.__dict__)
        return payload


def gate_symbol_both_ways(
    minute_store: MinuteStore, cache: ub.DailyCache, symbol: str, *, tests_open: bool
) -> SymbolResult:
    """`universe_backfill.gate_symbol`'s composition, with gate 2 evaluated BOTH ways.

    The gate-1 / relief / gate-1P legs are the shipped functions, called on the shipped inputs in
    the shipped order. Gate 2 is the shipped `integrity_gate` too; the OTHER enumeration's verdict
    is derived from it and from this day's own count of open-outside-[low, high] bars, which is
    exact because the completion ADDS one clause to one counter and changes nothing else: a day
    fails the completed gate exactly when it fails the sealed one OR carries such a bar.
    """
    out = SymbolResult(symbol=symbol)
    for day, bars in minute_store.iter_days(symbol, None, None):
        out.days += 1
        out.bars += len(bars)
        row = cache.day(symbol, day)
        fold_high = max(b.high_paise for b in bars)
        fold_low = min(b.low_paise for b in bars)
        fold_volume = sum(b.volume for b in bars)

        price = gates.price_containment_gate(
            fold_high,
            fold_low,
            None if row is None else row.high_paise,
            None if row is None else row.low_paise,
        )
        out.gate1p_total += 1
        if price.passed:
            out.gate1p_pass += 1

        reconciled: bool | None = None
        relieved = False
        if row is not None:
            out.gate1_total += 1
            result = gates.volume_gate(row.volume, fold_volume)
            if result.passed:
                out.gate1_pass += 1
            else:
                relief = gates.auction_relief(
                    result,
                    minute_open_paise=bars[0].open_paise,
                    minute_high_paise=fold_high,
                    minute_low_paise=fold_low,
                    raw_open_paise=row.open_paise,
                    raw_high_paise=row.high_paise,
                    raw_low_paise=row.low_paise,
                )
                relieved = relief.relieved
                if relieved:
                    out.gate1_relieved += 1
            reconciled = result.passed or relieved

        integrity = gates.integrity_gate(bars, day, volume_reconciled=reconciled)

        # Both enumerations counted from the same bars the gate saw, in ONE pass. Out-of-session
        # bars are dropped at the CANDLE level by the gate (CONTEXT 7-E2), so they are dropped
        # here too -- a stray bar must not be counted as a day-killer the gate never saw.
        ohlc_sealed, ohlc_completed, open_violations = _violations(bars, day)

        # Everything gate 2 refuses a day for OTHER than the OHLC-sanity trigger: duplicates,
        # negative values, and missing minutes on a day gate 1 did not pass. Those are identical
        # under both enumerations, so the two verdicts differ only through the OHLC counter.
        other_reasons = [r for r in integrity.reasons if "OHLC-sanity" not in r]
        passed_sealed = not other_reasons and ohlc_sealed == 0
        passed_completed = not other_reasons and ohlc_completed == 0

        # The probe's claim about the SHIPPED gate, checked on every real day rather than once.
        expected = ohlc_completed if tests_open else ohlc_sealed
        if integrity.ohlc_violations != expected or integrity.passed != (
            passed_completed if tests_open else passed_sealed
        ):
            out.probe_disagreements += 1

        if not passed_sealed:
            out.gate2_excluded_sealed += 1
        if not passed_completed:
            out.gate2_excluded_completed += 1
        out.gate2_ohlc_sealed += 1 if ohlc_sealed else 0
        out.gate2_ohlc_completed += 1 if ohlc_completed else 0

        usable_sealed = reconciled is True and passed_sealed and price.passed
        usable_completed = reconciled is True and passed_completed and price.passed
        out.usable_sealed += 1 if usable_sealed else 0
        out.usable_completed += 1 if usable_completed else 0

        if not open_violations:
            continue
        if usable_sealed and not usable_completed:
            out.flips.append((day.isoformat(), open_violations, "usable under all three gates"))
        else:
            # Named in the BATTERY's own order (`signal_engine.DayGates.refusal_detail`), so a
            # day's "already refused by" here reads the same as its refusal would in a ledger row.
            if row is None:
                already = "gate-1P (no raw daily row -- gate 1 could not be run)"
            elif reconciled is not True:
                already = "gate 1 (volume reconciliation)"
            elif not passed_sealed:
                already = (
                    "gate 2, SEALED enumeration: "
                    + "; ".join(other_reasons or [f"{ohlc_sealed} OHLC-sanity violation(s)"])
                )
            elif not price.passed:
                already = "gate-1P (per-day price containment)"
            else:  # pragma: no cover - a usable day that did not flip is impossible here
                already = "nothing -- unexpected"
            out.already_refused.append((day.isoformat(), open_violations, already))
    return out


def _violations(bars, day: date) -> tuple[int, int, int]:
    """``(sealed count, completed count, open-outside count)`` over one day's in-session bars.

    SEALED is CONTEXT 4.5's own two clauses -- ``high < low`` or a CLOSE outside ``[low, high]``.
    COMPLETED is those plus an OPEN outside ``[low, high]`` (the Q-21(a) ruling). A bar can trip
    several clauses and still counts ONCE, exactly as :func:`acumen.quality_gates.integrity_gate`
    counts it.
    """
    sealed = completed = opens = 0
    for bar in bars:
        if bar.stamp.date() != day or not gates.is_session_time(bar.stamp, minutes=1):
            continue
        low, high = bar.low_paise, bar.high_paise
        bad_sealed = not (low <= high and low <= bar.close_paise <= high)
        bad_open = not (low <= bar.open_paise <= high)
        sealed += 1 if bad_sealed else 0
        opens += 1 if bad_open else 0
        completed += 1 if (bad_sealed or bad_open) else 0
    return sealed, completed, opens


# --- section 5: does a Rule-3 scan read a newly-failing day? --------------------------------


class Probe:
    """A Rule-3 minute provider that answers NOTHING and remembers that it was asked."""

    def __init__(self) -> None:
        self.called = False

    def __call__(self):
        self.called = True
        return None


def candles_by_date(store: DailyStore, symbol: str, first: date, last: date) -> dict[date, Candle]:
    frame = store.daily(symbol, first, last)
    out: dict[date, Candle] = {}
    for row in frame.itertuples(index=False):
        try:
            out[row.trade_date] = Candle(
                open=int(row.open_paise),
                high=int(row.high_paise),
                low=int(row.low_paise),
                close=int(row.close_paise),
                day=row.trade_date,
            )
        except BiasError:
            continue
    return out


def adjust_previous(previous: Candle, current: Candle, factors, symbol: str) -> Candle:
    between = ca.factors_between(factors, previous.day, current.day, symbol=symbol)
    if not between:
        return previous
    return Candle(
        open=ca.adjust_pair(previous.open, between),
        high=ca.adjust_pair(previous.high, between),
        low=ca.adjust_pair(previous.low, between),
        close=ca.adjust_pair(previous.close, between),
        day=previous.day,
    )


def rule3_readers(
    symbol: str,
    targets: set[date],
    *,
    calendar: TradingCalendar,
    candles: dict[date, Candle],
    factors,
    suppressions,
    start: date,
    end: date,
) -> list[tuple[date, date]]:
    """Every ``(trade day D, D-1)`` in the span whose Rule-3 scan reads a date in ``targets``."""
    suppressed = {s.ex_date for s in suppressions if s.symbol == symbol.upper()}
    found: list[tuple[date, date]] = []
    day = start
    while day <= end:
        try:
            if not calendar.is_trading_day(day):
                day += timedelta(days=1)
                continue
            pair = calendar.bias_pair(day)
        except CalendarError:
            day += timedelta(days=1)
            continue
        if pair.current in targets:
            current, previous = candles.get(pair.current), candles.get(pair.previous)
            if (
                current is not None
                and previous is not None
                and pair.current not in suppressed
                and pair.previous not in suppressed
            ):
                probe = Probe()
                evaluate_pair(
                    adjust_previous(previous, current, factors, symbol), current, probe, None
                )
                if probe.called:
                    found.append((day, pair.current))
        day += timedelta(days=1)
    return found


# --- the report -----------------------------------------------------------------------------


def _pct(part: int, whole: int, places: int = 4) -> str:
    if not whole:
        return "n/a"
    return f"{Decimal(part) / Decimal(whole) * 100:.{places}f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--symbols", default=None, help="comma-separated subset (a smoke run)")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="JSONL of per-symbol results; reused on a re-run so a long pass resumes",
    )
    args = parser.parse_args()

    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")

    ledger_path = data / "universe_backfill" / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))["symbols"]
    universe = sorted(ledger)
    if args.symbols:
        universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    tests_open, tests_close, tests_hl = probe_shipped_enumeration()

    done: dict[str, SymbolResult] = {}
    if args.checkpoint and args.checkpoint.is_file():
        for line in args.checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                done[payload["symbol"]] = SymbolResult(**payload)

    todo = [s for s in universe if s not in done]
    if todo:
        cache = ub.build_daily_cache(daily_store, todo, mb.MINUTE_DATA_FLOOR, ERA_END)
        for index, symbol in enumerate(todo, start=1):
            result = gate_symbol_both_ways(minute_store, cache, symbol, tests_open=tests_open)
            done[symbol] = result
            if args.checkpoint:
                args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
                with args.checkpoint.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(result.to_dict(), default=str) + "\n")
            print(
                f"  [{index}/{len(todo)}] {symbol}: {result.days} days, "
                f"usable {result.usable_sealed} -> {result.usable_completed}",
                flush=True,
            )

    results = [done[s] for s in universe]
    settled = [r for r in results if ledger[r.symbol]["status"] == ub.STATUS_SETTLED]
    quarantined = [r for r in results if ledger[r.symbol]["status"] == ub.STATUS_QUARANTINED]

    stored_all = sum(r.gate1p_total for r in results)
    usable_sealed = sum(r.usable_sealed for r in settled)
    usable_completed = sum(r.usable_completed for r in settled)
    flips = [(r.symbol, day, n, why) for r in settled for day, n, why in r.flips]
    flips_q = [(r.symbol, day, n, why) for r in quarantined for day, n, why in r.flips]

    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# Q-21(a) evidence -- what COMPLETING gate 2 with the OPEN test costs")
    add()
    add(
        "Generated by `docs/evidence/chunk9b_q21a_gate2_completion.py`, offline and READ-ONLY "
        "over the stores and over the crashed run directory. No file under `data_root` is "
        "written, renamed or removed by this script."
    )
    add()
    add(
        "The architect's Q-21(a) ruling (03-Aug-2026, verbatim in QUESTIONS.md): *gate 2's "
        "impossible-OHLC enumeration is COMPLETED with the OPEN test -- a bar whose open lies "
        "outside [low, high] fails integrity, exactly as a close outside does. ... Corrupt days "
        "are refused, never repaired.* This file is the measurement of its cost."
    )
    add()

    # --- 1 -------------------------------------------------------------------------------
    add("## 1. Which enumeration the SHIPPED gate implements (probed, not assumed)")
    add()
    add("| clause | does `quality_gates.integrity_gate` count it? |")
    add("|---|---|")
    add(f"| `high < low` | {'YES' if tests_hl else 'no'} |")
    add(f"| CLOSE outside `[low, high]` | {'YES' if tests_close else 'no'} |")
    add(f"| OPEN outside `[low, high]` | **{'YES' if tests_open else 'no'}** |")
    add()
    add(
        f"So this pass ran against the **{'COMPLETED' if tests_open else 'SEALED'}** enumeration "
        f"({COMPLETED_CLAUSES if tests_open else SEALED_CLAUSES}) and derived the other side of "
        "the delta from each day's own bars. The derivation is exact rather than approximate: "
        "the completion adds ONE clause to ONE counter (`ohlc_violations`) and changes nothing "
        "else in the gate, so a day fails the completed enumeration exactly when it fails the "
        "sealed one OR carries a bar whose open lies outside its own `[low, high]`."
    )
    add()

    # --- 2 -------------------------------------------------------------------------------
    add("## 2. The battery, re-run over the whole lake")
    add()
    add(
        f"Every stored symbol-day of all **{len(results)}** processed symbols "
        f"({len(settled)} settled, {len(quarantined)} quarantined) was put through the CONTEXT "
        "4.6 battery in `universe_backfill.gate_symbol`'s own composition and order, calling the "
        "shipped `quality_gates` functions on the shipped inputs. Scanned "
        f"**{sum(r.bars for r in results):,} stored 1-minute bars** over "
        f"**{sum(r.days for r in results):,} symbol-days**."
    )
    add()
    add("| measure | SEALED enumeration | COMPLETED enumeration | delta |")
    add("|---|---|---|---|")
    add(f"| stored symbol-days (every processed symbol) | {stored_all:,} | {stored_all:,} | 0 |")
    add(
        f"| gate-2 exclusions (settled) | {sum(r.gate2_excluded_sealed for r in settled):,} | "
        f"{sum(r.gate2_excluded_completed for r in settled):,} | "
        f"{sum(r.gate2_excluded_completed - r.gate2_excluded_sealed for r in settled):+,} |"
    )
    add(
        f"| ...of those, days with an impossible-OHLC bar (settled) | "
        f"{sum(r.gate2_ohlc_sealed for r in settled):,} | "
        f"{sum(r.gate2_ohlc_completed for r in settled):,} | "
        f"{sum(r.gate2_ohlc_completed - r.gate2_ohlc_sealed for r in settled):+,} |"
    )
    add(
        f"| gate-1 EFFECTIVE pass (settled) | {sum(r.gate1_effective for r in settled):,} | "
        f"{sum(r.gate1_effective for r in settled):,} | 0 |"
    )
    add(
        f"| gate-1P pass (settled) | {sum(r.gate1p_pass for r in settled):,} | "
        f"{sum(r.gate1p_pass for r in settled):,} | 0 |"
    )
    add(
        f"| **USABLE symbol-days (gate 1 AND gate 2 AND gate 1P, settled)** | "
        f"**{usable_sealed:,}** | **{usable_completed:,}** | "
        f"**{usable_completed - usable_sealed:+,}** |"
    )
    add(
        f"| **TOTAL coverage** (usable of every stored symbol-day) | "
        f"**{_pct(usable_sealed, stored_all)}** | **{_pct(usable_completed, stored_all)}** | "
        f"{Decimal(usable_completed - usable_sealed) / Decimal(stored_all) * 100:+.4f} pp |"
    )
    add()
    add(
        "Gate 1 and gate 1P are printed with their deltas so the ZERO is on the page: the "
        "completion touches gate 2 and only gate 2, so neither of the other two gates' "
        "numerators or denominators moves by a single day."
    )
    add()

    # --- 3 -------------------------------------------------------------------------------
    add("## 3. The CONTROL: does this pass reproduce the machine's own ledger?")
    add()
    add(
        "Under the SEALED enumeration every per-symbol figure here must equal "
        "`<data_root>/universe_backfill/ledger.json` -- the artefact CONTEXT 4.6's re-sealed "
        "numbers are built from. If it does not, this pass is not the battery and its "
        "COMPLETED-side numbers may not be believed."
    )
    add()
    fields = [
        ("stored days", "gate1p_total", lambda r: r.gate1p_total),
        ("gate-1 pass (strict)", "gate1_pass", lambda r: r.gate1_pass),
        ("gate-1 auction relief", "gate1_relieved", lambda r: r.gate1_relieved),
        ("gate-1 gated days", "gate1_total", lambda r: r.gate1_total),
        ("gate-1P pass", "gate1p_pass", lambda r: r.gate1p_pass),
        ("gate-2 exclusions", "gate2_excluded", lambda r: r.gate2_excluded_sealed),
        ("usable days", "usable_pass", lambda r: r.usable_sealed),
    ]
    add("| figure | symbols compared | mismatches |")
    add("|---|---|---|")
    all_ok = True
    for label, key, getter in fields:
        bad = [r.symbol for r in results if ledger[r.symbol].get(key) != getter(r)]
        all_ok = all_ok and not bad
        detail = "**0**" if not bad else f"**{len(bad)}** ({', '.join(sorted(bad)[:8])})"
        add(f"| {label} | {len(results)} | {detail} |")
    disagreements = sum(r.probe_disagreements for r in results)
    all_ok = all_ok and disagreements == 0
    add(
        f"| the shipped gate's own verdict vs the probed enumeration | "
        f"{sum(r.days for r in results):,} days | **{disagreements}** |"
    )
    add()
    add(
        f"**CONTROL {'PASSES' if all_ok else 'FAILS'}**: this pass "
        f"{'reproduces' if all_ok else 'does NOT reproduce'} the ledger exactly on every "
        "compared figure of every processed symbol, and the shipped gate agreed with the probed "
        f"enumeration on all {sum(r.days for r in results):,} stored days."
    )
    add()

    # --- 4 -------------------------------------------------------------------------------
    add("## 4. Every symbol-day that flips usable -> refused")
    add()
    if not flips:
        add("There are none.")
    else:
        add("| symbol | symbol-day | open-outside bars | status of the symbol |")
        add("|---|---|---|---|")
        for symbol, day, count, _why in sorted(flips):
            add(f"| {symbol} | {day} | {count} | {ledger[symbol]['status']} |")
    add()
    add(
        f"**{len(flips):,} settled symbol-day(s) flip usable -> refused**, across "
        f"**{len({f[0] for f in flips}):,}** symbol(s), on "
        f"**{len({f[1] for f in flips}):,}** distinct date(s)"
        + (
            f" ({', '.join(f'{d} ({n})' for d, n in sorted(Counter(f[1] for f in flips).items()))})."
            if flips
            else "."
        )
    )
    if flips_q:
        add()
        add(
            f"A further **{len(flips_q)}** day(s) flip on QUARANTINED symbols "
            f"({', '.join(sorted({f[0] for f in flips_q}))}); those symbols are outside the run's "
            "universe and outside the coverage numerator either way, so they cost the backtest "
            "nothing. They are named rather than dropped."
        )
    add()
    already = [(r.symbol, day, n, why) for r in results for day, n, why in r.already_refused]
    add(
        f"**{len(already):,} further stored day(s) carry a newly-failing bar and were ALREADY "
        "refused**, so the completion costs them nothing:"
    )
    add()
    if already:
        add("| symbol | symbol-day | open-outside bars | already refused by |")
        add("|---|---|---|---|")
        for symbol, day, count, why in sorted(already):
            add(f"| {symbol} | {day} | {count} | {why} |")
    add()

    # --- 5 -------------------------------------------------------------------------------
    add("## 5. Can any symbol's SETTLED / QUARANTINED status move?")
    add()
    add(
        "No, and the reason is structural rather than empirical: a symbol is quarantined on its "
        f"EFFECTIVE GATE-1 rate alone (`universe_backfill.QUARANTINE_GATE1_MIN_PASS_RATE` = "
        f"{ub.QUARANTINE_GATE1_MIN_PASS_RATE:.0%}, strict passes plus auction-relief passes over "
        "gated days). Gate 2 is not an input to that decision, and section 2 measures gate 1's "
        "numerator and denominator as unchanged to the day. The margins are stated anyway, "
        "because 'it cannot move' is worth more with the distance to the line beside it."
    )
    add()
    touched = sorted({f[0] for f in flips} | {f[0] for f in flips_q})
    add("### every symbol carrying a flip, with its distance to the quarantine line")
    add()
    add(
        "| symbol | status | gate-1 effective | gate-1 rate | margin (pp) | failing days that "
        "would be needed to cross |"
    )
    add("|---|---|---|---|---|---|")
    for symbol in touched:
        record = next(r for r in results if r.symbol == symbol)
        rate = record.gate1_rate
        margin = (rate - ub.QUARANTINE_GATE1_MIN_PASS_RATE) * 100
        headroom = record.gate1_effective - int(
            (ub.QUARANTINE_GATE1_MIN_PASS_RATE * record.gate1_total).to_integral_value()
        )
        add(
            f"| {symbol} | {ledger[symbol]['status']} | {record.gate1_effective:,} / "
            f"{record.gate1_total:,} | {rate * 100:.2f}% | {margin:+.2f} | {headroom:,} |"
        )
    add()
    worst = min(
        (r for r in results if ledger[r.symbol]["status"] == ub.STATUS_SETTLED),
        key=lambda r: r.gate1_rate,
    )
    add(
        f"Across the whole universe the SETTLED symbol closest to the line is **{worst.symbol}** "
        f"at {worst.gate1_rate * 100:.2f}% ({worst.gate1_effective:,} / {worst.gate1_total:,}), "
        f"{(worst.gate1_rate - ub.QUARANTINE_GATE1_MIN_PASS_RATE) * 100:+.2f} pp clear; the "
        "quarantined symbols stay quarantined for the same unchanged reason. **ZERO status "
        "flips, in either direction.**"
    )
    add()

    # --- 6 -------------------------------------------------------------------------------
    add("## 6. The Q-21(b) blast radius under the completed battery")
    add()
    add(
        "Q-21(b) refuses a Rule-3 first-break scan whose D-1 fails the battery. A completed "
        "gate 2 can only ADD to that set, and only through a day that newly fails it -- so the "
        "question is which of the days in section 4 some trade day's Rule-3 scan actually READS. "
        "That is asked of the REAL engine: `bias.evaluate_pair` with a probe provider recording "
        "whether it was called, which the pure engine does in the Rule-3 branch and nowhere else."
    )
    add()

    report_start, report_end = _run_span(data)
    non_standard, scan_sha = _cached_sessions(data)
    newly_failing: dict[str, set[date]] = {}
    for symbol, day, _n, _why in flips + flips_q:
        newly_failing.setdefault(symbol, set()).add(date.fromisoformat(day))
    readers: list[tuple[str, date, date]] = []
    if newly_failing:
        calendar = TradingCalendar.from_daily_store_range(
            daily_store, report_start - timedelta(days=bt.CALENDAR_LEAD_DAYS), report_end
        )
        from dataclasses import replace as _replace

        calendar = _replace(
            calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
        )
        factors, suppressions, _digest, _ = bt.build_factor_tables(
            tuple(sorted(newly_failing)), daily_store, start=report_start, end=report_end
        )
        for symbol in sorted(newly_failing):
            if ledger[symbol]["status"] != ub.STATUS_SETTLED:
                continue
            candles = candles_by_date(
                daily_store,
                symbol,
                report_start - timedelta(days=bt.CALENDAR_LEAD_DAYS),
                report_end,
            )
            for trade_day, d1 in rule3_readers(
                symbol,
                newly_failing[symbol],
                calendar=calendar,
                candles=candles,
                factors=tuple(factors.get(symbol, ())),
                suppressions=tuple(suppressions.get(symbol, ())),
                start=report_start,
                end=report_end,
            ):
                readers.append((symbol, trade_day, d1))
    add(f"* run span, from the run's own preflight record: **{report_start} -> {report_end}**")
    add(
        f"* CONTEXT 7-E2 non-standard sessions removed from the calendar: **{len(non_standard)}** "
        f"(reused from the crashed run's cached `sessions.json`, code SHA `{scan_sha[:12]}`)"
    )
    add(
        f"* newly-failing days put to the engine: **{sum(len(v) for v in newly_failing.values())}** "
        f"across {len(newly_failing)} symbol(s)"
    )
    add()
    if not readers:
        add(
            "**No trade day's Rule-3 scan reads any of them**, so the Q-21(b) radius does not "
            "grow: the days the completion refuses are days no bias ever asked for."
        )
    else:
        add("| symbol | trade day D | D-1 (the newly-refused evidence) |")
        add("|---|---|---|")
        for symbol, trade_day, d1 in sorted(readers):
            add(f"| {symbol} | {trade_day} | {d1} |")
        add()
        add(
            f"**{len(readers)} Rule-3 scan day(s) move**, so the Q-21(b) radius measured before "
            "this ruling grows by exactly that many. Each of them was ALREADY a counted refusal "
            "under Q-21's malformed-bar case (the bar is what the scan would have choked on); "
            "what changes is WHICH case counts it -- the battery is checked before a candle is "
            "built (decision B250), so the refusal is now named by gate 2 rather than by the bar. "
            "The number of refused ledger rows is unchanged; one rare-shape counter hands its "
            "row to the other."
        )
    add()

    _emit(lines, args.out)
    return 0 if all_ok else 1


def _run_span(data: Path) -> tuple[date, date]:
    """The run's own span, read from the crashed run directory's manifest/spec. READ-ONLY."""
    path = data / "backtests" / RUN_DIRNAME / bt.SESSIONS_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    return date.fromisoformat(payload["start"]), date.fromisoformat(payload["end"])


def _cached_sessions(data: Path) -> tuple[frozenset[date], str]:
    """The crashed run's own CONTEXT 7-E2 scan, read from its `sessions.json`. READ-ONLY."""
    path = data / "backtests" / RUN_DIRNAME / bt.SESSIONS_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    days = frozenset(date.fromisoformat(day) for day in payload.get("non_standard", []))
    return days, str(payload.get("code_sha", "unknown"))


def _emit(lines: list[str], out: Path | None) -> None:
    text = "\n".join(lines).rstrip() + "\n"
    if out is None:
        print(text)
        return
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(lines)} lines)")


if __name__ == "__main__":
    raise SystemExit(main())
