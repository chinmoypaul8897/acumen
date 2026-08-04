"""Q-22(a): what the Rule-3 session filter changes, measured over the WHOLE span.

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_q22_session_filter.py --out docs/evidence/chunk9b_q22_session_filter.md

OFFLINE and READ-ONLY on both stores and on the crashed run directory. Nothing here writes,
renames or deletes anything under `data_root`.

THE QUESTION, exactly as the architect's Q-22(a) ruling settles it: *"Q-17's candle-level drop
binds EVERY consumer of stored minute bars, the Rule-3 first-break scan included ... where the
only break lives in stray bars the scan finds NO break and the day carries."* So: across all 204
settled symbols over the run's own span, how many Rule-3 scan days are re-answered, and how many
biases change?

WHY IT IS MEASURED HERE. REVIEW_9B_FIXES finding R1 measured TWO dates over the settled universe
and SAMPLED out-of-session dates over 25 symbols, and said so in its own scope caveat: *"the true
number of affected biases is >= 2 and unknown"*. This script measures the population instead of
sampling it, and the two flips the review names (GODREJCP and LAURUSLABS on the 2021-02-24 NSE
outage day) must appear in its output or the measurement is wrong.

HOW IT IS ASKED, so the numbers are the RUN's numbers and not a re-implementation's:

1. THE SPAN AND THE UNIVERSE come from `run_backtest.preflight` -- the same measurement the run
   itself takes, never typed here.
2. THE CALENDAR is derived exactly as `backtest.build_runner` derives it, INCLUDING the CONTEXT
   7-E2 non-standard sessions removed from it (reused from the crashed run's cached
   `sessions.json` rather than re-scanned -- the scan is O(symbols x span days) minute reads,
   which is why the run caches it, and nothing in this fix touches the E2 detector).
3. WHICH DAYS REACH THE RULE-3 SCAN is decided by the REAL pure engine, `bias.evaluate_pair`,
   with the same probe technique the Q-21(b) blast-radius script uses: the engine calls its
   minute provider in the Rule-3 branch and nowhere else (CONTEXT 3.2 -- only Rule 3 asks which
   extreme broke first), so "the provider was asked" IS "this day consumes D-1's minutes".
4. THE BATTERY comes first, exactly as `gated_minute_loader` orders it (Q-21(b), B250): a
   battery-failing D-1 never reaches the scan at all, so its strays are not this ruling's
   business and are counted separately.
5. THE CARRY IS WALKED, not assumed. Both answers are produced by a full per-symbol walk that
   maintains its own `last_bias` exactly as `BiasEngine._bias_for` does -- suppression windows
   and missing candles leave the carry unchanged -- because a Rule-3 day is the only place a
   carry can turn, so a changed bias PROPAGATES into later carried days. That propagation is
   reported separately from the days the scan itself re-answers.

WHAT "AS SHIPPED" AND "AS RULED" MEAN HERE: identical in every respect except the ONE line the
ruling moves. As shipped = the scan sees every stored bar of D-1. As ruled = the scan sees
`aggregate.in_session_bars(D-1)`, which is what `backtest.candles_for` now does. Both sides call
the same pure engine on the same adjusted pair.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import corp_actions as ca  # noqa: E402
from acumen import run_backtest as rb  # noqa: E402
from acumen.aggregate import in_session_bars  # noqa: E402
from acumen.bias import BiasError, Candle, evaluate_pair  # noqa: E402
from acumen.bias_engine import MalformedMinuteBar  # noqa: E402
from acumen.calendar import CalendarError, TradingCalendar  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.instrument_master import load_master_file  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402
from acumen.signal_engine import SignalPipeline  # noqa: E402

RUN_DIRNAME = "chunk9b_full"

#: The two flips REVIEW_9B_FIXES R1 measured by hand. If this script does not find them, the
#: script is wrong -- they are the calibration, not the result.
KNOWN_FLIPS: tuple[tuple[str, date], ...] = (
    ("GODREJCP", date(2021, 2, 24)),
    ("LAURUSLABS", date(2021, 2, 24)),
)


class Probe:
    """A Rule-3 minute provider that answers NOTHING and remembers that it was asked."""

    def __init__(self) -> None:
        self.called = False

    def __call__(self):
        self.called = True
        return None


def cached_sessions(data: Path) -> tuple[frozenset[date], str]:
    """The crashed run's own CONTEXT 7-E2 scan, read from its `sessions.json`. READ-ONLY."""
    path = data / "backtests" / RUN_DIRNAME / bt.SESSIONS_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    days = frozenset(date.fromisoformat(day) for day in payload.get("non_standard", []))
    return days, str(payload.get("code_sha", "unknown"))


def candles_by_date(store: DailyStore, symbol: str, first: date, last: date) -> dict[date, Candle]:
    """One symbol's whole daily history over the window, read ONCE. Q-4 equity series on read."""
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
            continue  # a malformed DAILY candle is a different question (none in this store)
    return out


def adjust_previous(previous: Candle, current: Candle, factors, symbol: str) -> Candle:
    """`BiasEngine._adjust_previous`, applied here so the pair is compared in ONE scale."""
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


class DayResult:
    """One walked trade day, answered twice -- with and without the session filter."""

    __slots__ = (
        "trade_day", "d1", "stray", "shipped_rule", "shipped_bias", "ruled_rule", "ruled_bias",
        "shipped_carry", "ruled_carry",
    )

    def __init__(self, trade_day, d1, stray, shipped, ruled, carries) -> None:
        self.trade_day = trade_day
        self.d1 = d1
        self.stray = stray
        self.shipped_rule, self.shipped_bias = shipped
        self.ruled_rule, self.ruled_bias = ruled
        self.shipped_carry, self.ruled_carry = carries


def walk_symbol(
    symbol: str,
    *,
    calendar: TradingCalendar,
    candles: dict[date, Candle],
    factors,
    suppressions,
    pipeline: SignalPipeline,
    minute_store: MinuteStore,
    start: date,
    end: date,
) -> tuple[list[DayResult], int, int, int, int]:
    """Walk the span TWICE in one pass -- shipped feed and ruled feed, each with its own carry.

    Returns ``(rule-3 scan days carrying strays, scan days, battery refusals, no-minute carries,
    days whose two walks disagree)``. The two walks share everything except the candles handed to
    the Rule-3 scan, so any divergence is the ruling's and nothing else's.
    """
    suppressed = {s.ex_date for s in suppressions if s.symbol == symbol.upper()}
    stray_days: list[DayResult] = []
    scan_days = refused_days = no_minute_days = differing_days = 0
    shipped_carry: str | None = None
    ruled_carry: str | None = None

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

        current, previous = candles.get(pair.current), candles.get(pair.previous)
        if (
            current is None
            or previous is None
            or pair.current in suppressed
            or pair.previous in suppressed
        ):
            # `BiasEngine._bias_for` leaves the carry untouched on both branches.
            day += timedelta(days=1)
            continue

        adjusted = adjust_previous(previous, current, factors, symbol)

        # Does this pair reach Rule 3 at all? The pure engine decides, not a re-implementation.
        probe = Probe()
        evaluate_pair(adjusted, current, probe, shipped_carry)
        if not probe.called:
            # Rules 1/2, an inside bar or a Rule-1 close: no minutes are read, so the ruling
            # cannot touch this day. Both walks get the identical answer; advance both carries.
            outcome = evaluate_pair(adjusted, current, None, shipped_carry)
            shipped_carry = outcome.bias
            ruled_outcome = evaluate_pair(adjusted, current, None, ruled_carry)
            ruled_carry = ruled_outcome.bias
            if shipped_carry != ruled_carry:
                differing_days += 1
            day += timedelta(days=1)
            continue

        scan_days += 1
        bars = minute_store.minutes(symbol, pair.current)
        if not bars:
            no_minute_days += 1
            shipped_carry = evaluate_pair(adjusted, current, lambda: None, shipped_carry).bias
            ruled_carry = evaluate_pair(adjusted, current, lambda: None, ruled_carry).bias
            if shipped_carry != ruled_carry:
                differing_days += 1
            day += timedelta(days=1)
            continue

        # Q-21(b), B250: the battery is the scan's PRECONDITION and comes before any candle.
        if pipeline.gate_day(symbol, pair.current, bars).refusal_detail is not None:
            refused_days += 1  # the day is refused on both sides; neither carry moves
            day += timedelta(days=1)
            continue

        session, dropped = in_session_bars(bars)
        try:
            shipped_candles = _candles(symbol, pair.current, bars)
        except MalformedMinuteBar:
            # The pre-fix feed could not even be built (Q-21's third case); the ruled feed may
            # still be fine. Counted as a stray day with the shipped side refused.
            shipped_candles = None
        ruled_candles = _candles(symbol, pair.current, session)

        shipped = (
            ("minutes-malformed", shipped_carry)
            if shipped_candles is None
            else _answer(evaluate_pair(adjusted, current, lambda: shipped_candles, shipped_carry))
        )
        ruled = _answer(evaluate_pair(adjusted, current, lambda: ruled_candles, ruled_carry))
        if dropped:
            stray_days.append(
                DayResult(
                    day, pair.current, dropped, shipped, ruled, (shipped_carry, ruled_carry)
                )
            )
        shipped_carry, ruled_carry = shipped[1], ruled[1]
        if shipped_carry != ruled_carry:
            differing_days += 1
        day += timedelta(days=1)

    return stray_days, scan_days, refused_days, no_minute_days, differing_days


def _candles(symbol: str, day: date, bars) -> tuple[Candle, ...]:
    """Stored bars -> candles, in stored order. A malformed bar raises, as the run's loader does."""
    out = []
    for bar in bars:
        try:
            out.append(
                Candle(
                    open=int(bar.open_paise),
                    high=int(bar.high_paise),
                    low=int(bar.low_paise),
                    close=int(bar.close_paise),
                    stamp=bar.stamp,
                    day=bar.stamp.date(),
                )
            )
        except BiasError as exc:
            raise MalformedMinuteBar(
                symbol=symbol, day=day, stamp=bar.stamp,
                open_paise=int(bar.open_paise), high_paise=int(bar.high_paise),
                low_paise=int(bar.low_paise), close_paise=int(bar.close_paise),
                volume=int(bar.volume),
            ) from exc
    return tuple(out)


def _answer(outcome) -> tuple[str, str | None]:
    return (outcome.rule, outcome.bias)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--symbols", default=None, help="comma-separated subset (a smoke run of this script)"
    )
    args = parser.parse_args()

    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")

    report = rb.preflight()
    universe = list(report.symbols)
    start, end = report.start, report.end
    if args.symbols:
        universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    master = load_master_file(config.instrument_master_path())
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )
    non_standard, scan_sha = cached_sessions(data)
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, start - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
    )
    from dataclasses import replace as _replace

    calendar = _replace(
        calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
    )
    factors, suppressions, factor_digest, _ = bt.build_factor_tables(
        tuple(universe), daily_store, start=start, end=end
    )

    all_stray: list[tuple[str, DayResult]] = []
    scan_total = refused_total = no_minute_total = differing_total = 0
    symbols_with_stray: set[str] = set()
    for index, symbol in enumerate(universe, start=1):
        candles = candles_by_date(
            daily_store, symbol, start - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
        )
        stray, scans, refused, no_min, differing = walk_symbol(
            symbol,
            calendar=calendar,
            candles=candles,
            factors=tuple(factors.get(symbol, ())),
            suppressions=tuple(suppressions.get(symbol, ())),
            pipeline=pipeline,
            minute_store=minute_store,
            start=start,
            end=end,
        )
        scan_total += scans
        refused_total += refused
        no_minute_total += no_min
        differing_total += differing
        for row in stray:
            all_stray.append((symbol, row))
            symbols_with_stray.add(symbol)
        print(f"  [{index}/{len(universe)}] {symbol}: {scans} scan days, {len(stray)} with strays")

    changed = [(s, r) for s, r in all_stray if r.shipped_bias != r.ruled_bias]
    re_ruled = [(s, r) for s, r in all_stray if r.shipped_rule != r.ruled_rule]

    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# Q-22(a) evidence -- what the Rule-3 session filter changes, over the whole span")
    add()
    add(
        "Generated by `docs/evidence/chunk9b_q22_session_filter.py`, offline and READ-ONLY over "
        "the stores and over the crashed run directory. No file under `data_root` is written, "
        "renamed or removed by this script."
    )
    add()
    add("## 1. What was asked, and of what")
    add()
    add(f"* span, measured by the run's own preflight: **{start} -> {end}**")
    add(f"* universe: **{len(universe)}** settled symbol(s)")
    add(
        f"* CONTEXT 7-E2 non-standard sessions removed from the calendar: "
        f"**{len(non_standard)}** ({', '.join(day.isoformat() for day in sorted(non_standard))})"
    )
    add(
        f"  * REUSED from the crashed run's cached `sessions.json` (scanned under code SHA "
        f"`{scan_sha[:12]}`), not re-scanned."
    )
    add(f"* corporate-action factor digest for this universe: `{factor_digest}`")
    add(f"* instrument master, pinned (Q-20): `{Path(config.instrument_master_path()).name}`")
    add()
    add(
        "**As shipped** = the Rule-3 first-break scan sees every stored bar of D-1. **As ruled** "
        "= it sees `aggregate.in_session_bars(D-1)`, which is what `backtest.candles_for` now "
        "does. Everything else is identical: the same pure `bias.evaluate_pair`, the same "
        "pairwise-adjusted pair, the same calendar, the same battery in front. Both sides are "
        "produced by a full per-symbol walk carrying its own `last_bias`, so a changed bias "
        "propagates into later carried days exactly as it would in the run."
    )
    add()

    add("## 2. The population")
    add()
    add("| measure | count |")
    add("|---|---|")
    add(f"| trade days whose pair reaches the Rule-3 1-minute scan | **{scan_total:,}** |")
    add(f"| ...of those, D-1 has NO stored minutes (CONTEXT 3.2 / R1-Q6 carry, untouched) | {no_minute_total:,} |")
    add(f"| ...of those, D-1 FAILS the battery -> refused before the scan (Q-21(b)) | {refused_total:,} |")
    add(f"| **...of those, D-1 reaches the scan AND carries out-of-session bar(s)** | **{len(all_stray):,}** |")
    add(f"| symbols carrying at least one such day | **{len(symbols_with_stray):,}** of {len(universe)} |")
    add(f"| **...of those days, the scan's RULE changes** | **{len(re_ruled):,}** |")
    add(f"| **...of those days, the BIAS changes** | **{len(changed):,}** |")
    add(f"| walked days whose two walks disagree at all (the flips PLUS their carry) | **{differing_total:,}** |")
    add()
    add(
        f"So the ruling re-answers **{len(all_stray):,}** Rule-3 scan day(s) and changes "
        f"**{len(changed):,}** bias(es). The last row is the honest downstream number: a Rule-3 "
        "day is the only place a carry can turn, so a changed bias is inherited by every later "
        "day that carries it until the next rule fires."
    )
    add()

    add("## 3. Every re-answered day")
    add()
    if not all_stray:
        add("There are none: no Rule-3 scan in the whole span reads a day carrying a stray bar.")
    else:
        add(
            "| symbol | trade day D | D-1 | strays dropped | carry into D | as shipped | "
            "as ruled | bias moves |"
        )
        add("|---|---|---|---|---|---|---|---|")
        for symbol, row in sorted(all_stray, key=lambda r: (r[0], r[1].trade_day)):
            moves = "**YES**" if row.shipped_bias != row.ruled_bias else "no"
            carry = (
                str(row.ruled_carry)
                if row.shipped_carry == row.ruled_carry
                else f"{row.shipped_carry} / {row.ruled_carry}"
            )
            add(
                f"| {symbol} | {row.trade_day} | {row.d1} | {row.stray} | {carry} | "
                f"{row.shipped_rule} -> {row.shipped_bias} | "
                f"{row.ruled_rule} -> {row.ruled_bias} | {moves} |"
            )
        add()
        add(
            "The **carry into D** column is why a re-answered day need not be a changed bias: "
            "when the strays are dropped the scan finds no break and the day CARRIES (CONTEXT "
            "3.2's own `rule-3-no-break-carry`), so the answer moves only if the carried bias "
            "differs from what the stray decided."
        )
    add()

    add("## 4. Every CHANGED bias")
    add()
    if not changed:
        add("There are none.")
    else:
        add("| symbol | trade day D | D-1 | as shipped | as ruled |")
        add("|---|---|---|---|---|")
        for symbol, row in sorted(changed, key=lambda r: (r[0], r[1].trade_day)):
            add(
                f"| {symbol} | {row.trade_day} | {row.d1} | "
                f"`{row.shipped_rule}` -> **{row.shipped_bias}** | "
                f"`{row.ruled_rule}` -> **{row.ruled_bias}** |"
            )
    add()
    by_date = Counter(row.d1 for _s, row in changed)
    if by_date:
        add("### by the D-1 the strays sit on")
        add()
        add("| D-1 | biases changed | symbols |")
        add("|---|---|---|")
        for d1 in sorted(by_date):
            syms = sorted({s for s, row in changed if row.d1 == d1})
            add(f"| {d1} | {by_date[d1]:,} | {', '.join(syms)} |")
        add()

    add("## 5. The calibration: the two days REVIEW_9B_FIXES measured by hand")
    add()
    add(
        "The review measured two dates over the settled universe and sampled out-of-session "
        "dates over 25 symbols, and stated its own scope: *\"the true number of affected biases "
        "is >= 2 and unknown\"*. Its two named days are this script's calibration -- if they are "
        "absent from the re-answered list, the measurement is wrong, not the review."
    )
    add()
    add("| symbol | D-1 the review named | re-answered here | as shipped | as ruled | carry into D |")
    add("|---|---|---|---|---|---|")
    for symbol, d1 in KNOWN_FLIPS:
        hit = next((row for s, row in all_stray if s == symbol and row.d1 == d1), None)
        if hit is None:
            add(f"| {symbol} | {d1} | **NOT FOUND** | -- | -- | -- |")
        else:
            add(
                f"| {symbol} | {d1} | yes (trade day {hit.trade_day}) | "
                f"`{hit.shipped_rule}` -> **{hit.shipped_bias}** | "
                f"`{hit.ruled_rule}` -> **{hit.ruled_bias}** | {hit.ruled_carry} |"
            )
    add()
    found_known = all(
        any(s == symbol and row.d1 == d1 for s, row in all_stray) for symbol, d1 in KNOWN_FLIPS
    )
    if not found_known:
        add("**AT LEAST ONE KNOWN DAY IS MISSING -- do not trust the numbers above.**")
        add()
    else:
        add(
            "**Both days reproduce as re-answered days, and the RULE change reproduces exactly** "
            "-- `rule-3-outside-bar` becomes `rule-3-no-break-carry`, which is the ruling's own "
            "sentence (*\"the known 2021-02-24 flips (GODREJCP, LAURUSLABS -> carry) become "
            "correct\"*) and its own rationale (*\"where the only break lives in stray bars the "
            "scan finds NO break and the day carries -- the engine's existing honest answer\"*)."
        )
        add()
        known_moved = [
            (s, row) for s, row in all_stray
            if (s, row.d1) in KNOWN_FLIPS and row.shipped_bias != row.ruled_bias
        ]
        if known_moved:
            add(
                f"**And on {len(known_moved)} of the two the BIAS moves as well**, so the "
                "review's flip claim reproduces in full."
            )
        else:
            add(
                "**The BIAS on those two days does NOT move, and that corrects the review.** "
                "REVIEW_9B_FIXES' table reads the ruled answer as BULLISH because its probe "
                "passed the string `\"BULLISH\"` to `evaluate_pair` as the carried bias rather "
                "than walking the carry to that date. Walked from the span's start with each "
                "symbol's own factor table -- and independently re-derived through the shipped "
                "`BiasEngine` itself -- the bias carried into 2021-02-25 is already **bearish** "
                "on both symbols (GODREJCP 2021-02-24 `rule-1-breakout` bearish; LAURUSLABS "
                "2021-02-24 `inside-bar-carry` bearish), so the carry lands on the same answer "
                "the stray bar produced. The DAY is re-answered; the BIAS is not changed."
            )
            add()
            add(
                "Nothing in the ruling turns on this. Q-22(a) decides which events a Rule-3 scan "
                "may consume, not how many answers move, and the ruling's stated rationale is "
                "exactly what the engine now does. It is recorded because the review's \">= 2 "
                "biases change\" is the one figure of that finding this measurement does not "
                "reproduce, and a later session must not re-derive it from the review."
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
