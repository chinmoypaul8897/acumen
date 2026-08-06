"""Chunk 12: THE VALIDATION PACK -- the document the trader reads, in his own language.

``docs/validation/trader_pack.py`` is the launcher, ``docs/validation/trader_pack.md`` is the
committed output, ``docs/validation/trader_pack.json`` is its machine-readable companion and
``docs/reports/points_by_symbol.md`` is the full per-stock POINTS table page 7 shows both ends
of (the trader's own Round-4 request, in place of his Q43 capital question). All of them must
regenerate BYTE-IDENTICALLY from this code over the same run directory and the same read-only
stores (REVIEW_8 finding C2). Nothing in the output is written by hand, ever.

**Who this is for.** The trader. Not the architect, not a reviewer, not a future session. So the
page carries no jargon it does not immediately define, no metric name he never used, and no
verdict: plan.md's chunk-12 card asks him to confirm that the machine is HIS strategy, and a
document that argued a case would be answering the question for him.

**Where the numbers come from.** Every figure is PULLED, never retyped:

* the ten-year totals, the per-year table and the drawdown come from the run ledger through
  :func:`acumen.report_9b.read_run` -- the same reader the technical report uses, so the pack
  and the report cannot drift apart -- and from :mod:`acumen.portfolio`, which is pure and
  reviewed;
* the six walked days are REPLAYED through the very engines the run walked
  (:class:`acumen.backtest.BacktestRunner`), and each replay's ledger row is compared FIELD BY
  FIELD with the row the run committed; a divergence is printed, never hidden;
* the money on the page is formatted by :func:`acumen.portfolio.format_paise` from an integer
  paise value, and every one of those values is written into the JSON companion as it is
  emitted. ``tests/test_trader_pack.py`` asserts both halves: this module contains no
  money-shaped literal at all, and every rupee token on the rendered page is the formatting of
  a value the companion carries.

**What it does NOT do.** It computes no new strategy behaviour, opens no network connection,
and writes nothing outside ``docs/validation/``. The stores are READ-ONLY (CLAUDE.md, Q-18
layer 2).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

from . import backtest as bt
from . import bias as bias_engine
from . import poc as poc_engine
from . import points_view as pts
from . import portfolio as pf
from . import report_9b as r9
from . import signals as sig
from . import simulate as sim
from .aggregate import in_session_bars
from .bias_engine import DailyBias
from .config import load_config
from .minute_store import MinuteStore
from .signal_engine import StockDay

#: The run this pack is OF -- the same label the technical report reads (a label, not a path).
RUN_LABEL: str = r9.RUN_LABEL

DEFAULT_OUT: str = "docs/validation/trader_pack.md"
DEFAULT_JSON: str = "docs/validation/trader_pack.json"

#: The third artefact this generator writes: the FULL per-stock points table, all of it, beside
#: the technical report. Page 7 of the pack shows both ends of the same ranking and points here
#: for the rest, so no stock is only ever a row someone decided not to print.
DEFAULT_POINTS: str = pts.COMPANION_PATH

#: The technical report this pack sits beside. Named so the trader (and the architect's document
#: build) can find the long-form evidence for anything the pack states in one line.
REPORT_PATH: str = r9.DEFAULT_OUT

#: The Indian crore, as a SCALE. Not a money amount and not a spec constant: it is the unit the
#: trader thinks in, so the peak notional is printed in it beside the exact rupee figure. Written
#: as a power so that no CONTEXT 3.5 magnitude appears as a literal anywhere in this module.
RUPEES_PER_CRORE: int = 10 ** 7

#: The paise-to-rupee scale (CONTEXT 7-E11). A UNIT, like the crore above -- fourteen modules in
#: this package use it and it is not a money amount.
PAISE_PER_RUPEE: int = 100

#: The two days the architect NAMED for this pack (his chunk-12 prompt, 06-Aug-2026): a clean
#: recent winner and a recent gap-entry day. Each is used only if it QUALIFIES -- the test is in
#: :func:`_pick_winner` / :func:`_pick_gap` and its result is printed beside the day -- and a
#: named day that failed its test would be replaced by the computed fallback, with the swap
#: stated on the page rather than made quietly.
NAMED_WINNER: tuple[str, str] = ("HDFCBANK", "2026-06-10")
NAMED_GAP: tuple[str, str] = ("TIINDIA", "2026-07-27")

#: A "recent" day, for the two named choices' qualification test: inside the last quarter of the
#: run's own span. Days, because the span's end is a date and not a month index.
RECENT_DAYS: int = 90

WEEKDAYS: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)
MONTHS: tuple[str, ...] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: The trader's OWN words, verbatim from QUESTIONS.md's receipts, with the part of CONTEXT 3 each
#: one fixes. These are the only quotations of him this repo holds: Rounds 1 and 2 reached the
#: spec as answers recorded in CONTEXT 3's own sentences (the `R1-Qn` / `R2-Qn` tags) rather than
#: as transcribed speech, and the pack says so rather than inventing a quotation for them.
#: (QUESTIONS.md: ROUND-3 RECEIPTS 25-Jul-2026, ROUND-3 FINAL RECEIPTS 29-Jul-2026.)
TRADER_WORDS: tuple[tuple[str, str, str], ...] = (
    ("Round 3, Q29", "risk per trade = 1,000 rupees.",
     "how much of your money each trade is allowed to lose"),
    ("Round 3, Q32",
     "Rows Layout = 'Number of Rows'; Row Size = 24; Volume shows Up/Down split on the chart.",
     "the volume-profile settings the machine copies from your chart"),
    ("Round 3, Q42", "the box is the first two hours -- 9:15 to 11:15. Eight candles.",
     "which candles the volume profile is built from"),
    ("Round 3, Q38/Q39",
     "the colour of that one-minute candle does not matter. Red, green or a doji -- I look at "
     "where the DAY closed against the previous day's body.",
     "how an outside-bar tie is decided"),
    ("Round 3, Q31-WHY",
     "on the outside-bar tie, when the deciding 1-minute candle closes red near its bottom, the "
     "low was swept last, so the real break was the high -> BULLISH.",
     "why the first break decides the outside-bar day"),
    ("Round 3, Q41",
     "A -- that first candle only tells me which side I am playing. I still wait for the entry.",
     "what happens when the 11:15 candle closes exactly ON the POC"),
    ("Round 3, Q40", "d -- no limits, show me the honest numbers.",
     "whether the machine may skip a signal because the money is already committed"),
    ("Round 3, bias table", "confirmed -- that is what I would have called on each of those days.",
     "your confirmation of the bias engine on fifteen real days (the chunk-4 gate)"),
    ("Round 3, chart reading", "BHARTIARTL 17-Jul: POC reads about 1913.9, and I count 25 rows "
     "in the box.",
     "the chart reading that settled how the profile's rows are counted"),
)


# --- what one streaming pass over the ledger has to answer for the PACK ------------------------


@dataclass(frozen=True)
class Census:
    """The pack's own census of the ledger -- the facts :func:`acumen.report_9b.read_run` drops.

    ``read_run`` keeps the EXECUTED rows and counts the rest on the way past, which is everything
    the technical report needs. This pack additionally has to choose six days by rule and to
    COUNT two families the trader is owed a number for, and both questions live on rows that
    reader discards: the wait-rule days (reference exactly ON the POC) are mostly no-trade days,
    and the bias-rule tally spans every evaluated row. So there is one further pass, and it is
    the only one.
    """

    last_day: date
    trades_by_symbol: Mapping[str, int]
    risks_paise: tuple[int, ...]
    bias_rules: Mapping[str, int]
    #: Every day the 11:15 reference closed EXACTLY on the POC -- the trader's Q41-A wait rule.
    wait_rule_days: tuple[tuple[date, str, str, bool], ...]  # (day, symbol, outcome, executed)
    tie_days: tuple[tuple[date, str, str], ...]              # (day, symbol, bias) -- Rule-3 ties
    #: (symbol, day) -> POC in half-paise, for the last calendar year of the span only: the
    #: rounding probe's population, and the only rows it may look at (an unevaluated day has no
    #: profile to compare).
    recent_pocs: Mapping[tuple[str, date], int]
    winners: tuple[tuple[date, str], ...]     # executed, target-hit, net > 0, not a gap
    gaps: tuple[tuple[date, str], ...]        # executed gap entries
    #: EVERY executed stop-out with its per-share risk -- gap entries included. They were
    #: excluded until REVIEW_12 finding C2 pointed out that the page says "of that day's
    #: stop-outs" without qualification; a gap entry that stops out is one of that day's
    #: stop-outs, and the pool now matches the words.
    stops: tuple[tuple[date, str, int], ...]
    carries: tuple[tuple[date, str, str], ...]  # evaluated, bias CARRIED, no trade
    #: The entry CLOCK of every gap entry, so the gap slot's criterion can say how many stocks
    #: gapped in on its day and when -- REVIEW_12 finding Q1: the page claimed a superlative the
    #: ledger does not support, and nothing checked it. Defaulted so an existing construction of
    #: this census (the reviewers' own fixtures) needs no change.
    gap_clocks: Mapping[tuple[date, str], str] = field(default_factory=dict)

    @property
    def median_risk_paise(self) -> int:
        """The middle per-share risk of every executed trade -- what a TYPICAL trade risked."""
        ordered = sorted(self.risks_paise)
        count = len(ordered)
        middle = count // 2
        if count % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) // 2


CARRY_RULES: tuple[str, ...] = (
    bias_engine.RULE_INSIDE,
    bias_engine.RULE_CARRY,
    bias_engine.RULE_3_NO_MINUTE,
    bias_engine.RULE_3_NO_BREAK,
)


def census(run_dir: Path) -> Census:
    """One streaming pass over the ledger for the facts the pack's own choices rest on. I/O."""
    ledger = run_dir / bt.LEDGER_NAME
    if not ledger.is_file():
        raise bt.BacktestError(f"No run ledger at {ledger}.")

    trades: Counter = Counter()
    rules: Counter = Counter()
    risks: list[int] = []
    waits: list[tuple[date, str, str, bool]] = []
    ties: list[tuple[date, str, str]] = []
    winners: list[tuple[date, str]] = []
    gaps: list[tuple[date, str]] = []
    stops: list[tuple[date, str, int]] = []
    carries: list[tuple[date, str, str]] = []
    clocks: dict[tuple[date, str], str] = {}
    pocs: dict[tuple[str, date], int] = {}
    last: date | None = None

    with ledger.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            day = date.fromisoformat(row["day"])
            symbol = row["symbol"]
            last = day if last is None or day > last else last
            if row["bias_rule"]:
                rules[row["bias_rule"]] += 1
            if row["tie_case"]:
                ties.append((day, symbol, row["bias"]))

            reference = row["reference_paise"]
            profile_poc = row["poc_half_paise"]
            if reference is not None and profile_poc is not None:
                # CONTEXT 3.4: the POC is carried in HALF paise because a row midpoint may
                # legally sit on one, so "the reference is exactly the POC" is this comparison
                # and never a rounded one (CONTEXT 7-E11 bans a float equality on prices).
                if reference + reference == profile_poc:
                    waits.append((day, symbol, row["outcome"], bool(row["executed"])))
            if profile_poc is not None:
                pocs[(symbol, day)] = profile_poc

            if row["executed"]:
                trades[symbol] += 1
                risks.append(int(row["per_share_risk_paise"]))
                if row["gap_entry"]:
                    gaps.append((day, symbol))
                    stamp = row["entry_close_stamp"]
                    clocks[(day, symbol)] = stamp[11:16] if stamp else ""
                if row["exit_kind"] == sig.EXIT_STOP and row["net_pnl_paise"] < 0:
                    stops.append((day, symbol, int(row["per_share_risk_paise"])))
                if (row["exit_kind"] == sig.EXIT_TARGET and row["net_pnl_paise"] > 0
                        and not row["gap_entry"]):
                    winners.append((day, symbol))
            elif row["status"] == bt.STATUS_EVALUATED and row["bias_rule"] in CARRY_RULES:
                carries.append((day, symbol, row["outcome"]))

    if last is None:
        raise bt.BacktestError(f"{ledger} holds no rows.")
    year_start = date(last.year, 1, 1)
    return Census(
        last_day=last,
        trades_by_symbol=dict(trades),
        risks_paise=tuple(risks),
        bias_rules=dict(sorted(rules.items(), key=lambda kv: (-kv[1], kv[0]))),
        wait_rule_days=tuple(sorted(waits)),
        tie_days=tuple(sorted(ties)),
        recent_pocs={key: value for key, value in pocs.items() if key[1] >= year_start},
        winners=tuple(sorted(winners)),
        gaps=tuple(sorted(gaps)),
        stops=tuple(sorted(stops)),
        carries=tuple(sorted(carries)),
        gap_clocks=dict(sorted(clocks.items())),
    )


# --- choosing the six days (by RULE, and the rule is printed beside the day) --------------------


@dataclass(frozen=True)
class Choice:
    """One chosen day, and the stated rule that chose it."""

    key: str
    heading: str
    symbol: str
    day: date
    criterion: str
    named: bool = False


def _traded_most(census: Census, symbol: str) -> int:
    return census.trades_by_symbol.get(symbol, 0)


def _named(pair: tuple[str, str]) -> tuple[str, date]:
    return pair[0], date.fromisoformat(pair[1])


def _pick_winner(census: Census) -> Choice:
    """A clean recent winner: the architect NAMED one, and it is used if it qualifies."""
    symbol, day = _named(NAMED_WINNER)
    cutoff = census.last_day - timedelta(days=RECENT_DAYS)
    qualifies = (day, symbol) in set(census.winners) and day >= cutoff
    if qualifies:
        return Choice(
            key="a", heading="a winner", symbol=symbol, day=day, named=True,
            criterion=(
                "the day the architect named for this slot. It QUALIFIES on the ledger's own "
                "record: the trade was taken, it reached the target, it made money, it was not "
                "a gap entry, and it falls inside the last three months of the run"
            ),
        )
    recent = [pair for pair in census.winners if pair[0] >= cutoff]
    pool = recent or list(census.winners)
    best = max(pool, key=lambda pair: (pair[0], _traded_most(census, pair[1]), pair[1]))
    return Choice(
        key="a", heading="a winner", symbol=best[1], day=best[0],
        criterion=(
            "the most recent trade that reached its target and made money without gapping in, "
            "on the stock this run traded most often, and then the last one alphabetically. The "
            "day the architect named for this slot did not qualify on the ledger's own record, "
            "so the rule chose instead"
        ),
    )


def _pick_stop(census: Census) -> Choice:
    """A recent stop-out, and a TYPICAL one: nearest the middle per-share risk of the whole run."""
    middle = census.median_risk_paise
    same_day = [row for row in census.stops if row[0] == census.last_day]
    pool = same_day or list(census.stops)
    best = min(pool, key=lambda row: (abs(row[2] - middle), -_traded_most(census, row[1]), row[1]))
    return Choice(
        key="b", heading="a stop-out", symbol=best[1], day=best[0],
        criterion=(
            "a stop-out from the last day the machine walked, chosen so it is a TYPICAL one and "
            "not a freak: of that day's stop-outs -- all of them, gap entries included -- the "
            "one whose distance from entry to stop is nearest the middle distance of all the "
            "run's trades. Ties go to the stock this run traded most often, and if that ties "
            "too, to the first stock alphabetically"
        ),
    )


def _gap_neighbours(census: Census, day: date, symbol: str) -> str:
    """The OTHER stocks that gapped in on the same day, named with their entry times.

    REVIEW_12 finding Q1: the named branch used to print "the LAST gap entry of the whole ten
    years", which the ledger does not support -- the last gap-entry DAY carries more than one.
    The sentence now states what is true and COUNTS it, so a data change moves the words.
    """
    others = [(census.gap_clocks.get((day, other), ""), other)
              for one_day, other in census.gaps if one_day == day and other != symbol]
    if not others:
        return ""
    mine = census.gap_clocks.get((day, symbol), "")
    listed = ", ".join(f"{name} at {clock}" for clock, name in sorted(others))
    return (f". It was not the only gap entry that day: {len(others) + 1} stocks gapped in on it "
            f"({listed}, against this one at {mine}), so this is one of them and not a last of "
            "anything")


def _pick_gap(census: Census) -> Choice:
    """A gap-entry day: the architect NAMED one, used if it qualifies."""
    symbol, day = _named(NAMED_GAP)
    if (day, symbol) in set(census.gaps):
        last_gap_day = max(one_day for one_day, _symbol in census.gaps)
        placing = ("and it falls on the LAST DAY of the ten years that any stock gapped in"
                   if day == last_gap_day else
                   "and it is the day the ledger records for it")
        return Choice(
            key="c", heading="a gap day", symbol=symbol, day=day, named=True,
            criterion=(
                f"the day the architect named for this slot, {placing}. It QUALIFIES: the "
                "ledger records it as a gap entry"
                + _gap_neighbours(census, day, symbol)
            ),
        )
    best = max(census.gaps, key=lambda pair: (pair[0], _traded_most(census, pair[1]), pair[1]))
    return Choice(
        key="c", heading="a gap day", symbol=best[1], day=best[0],
        criterion=(
            "the most recent gap entry in the run, on the stock this run traded most often and "
            "then the last one alphabetically. The day the architect named for this slot is not "
            "a gap entry on the ledger's own record, so the rule chose instead"
            + _gap_neighbours(census, best[0], best[1])
        ),
    )


def _pick_wait(census: Census) -> Choice | None:
    """A wait-rule day: the 11:15 candle closed EXACTLY on the POC. ``None`` if there are none."""
    if not census.wait_rule_days:
        return None
    last = census.wait_rule_days[-1][0]
    on_that_day = [row for row in census.wait_rule_days if row[0] == last]
    traded = [row for row in on_that_day if row[3]]
    pool = traded or on_that_day
    best = max(pool, key=lambda row: (_traded_most(census, row[1]), row[1]))
    return Choice(
        key="d", heading="a day the 11:15 candle closed exactly ON the POC", symbol=best[1],
        day=best[0],
        criterion=(
            "the most recent day in the whole run where the 11:15 candle closed at exactly the "
            "POC price -- your Round-3 answer A, the one where the first candle only picks the "
            "side. Where more than one stock did that on the same day, the one that went on to "
            "take a trade is shown, because a day with no trade cannot show the rest of the "
            "rule; then the stock this run traded most often, and then the last one "
            "alphabetically"
        ),
    )


def _pick_carry(census: Census) -> Choice:
    """A day that traded nothing, and whose bias was CARRIED rather than freshly decided."""
    same_day = [row for row in census.carries if row[0] == census.last_day]
    pool = same_day or list(census.carries)
    best = max(pool, key=lambda row: (row[0], _traded_most(census, row[1]), row[1]))
    return Choice(
        key="e", heading="a day with no trade at all", symbol=best[1], day=best[0],
        criterion=(
            "a day from the last day the machine walked where no NEW rule fired on the two "
            "daily candles -- either an inside bar, which is your rule 1 and says the bias does "
            "not change, or nothing fitting at all -- so the machine kept the bias it already "
            "had, and no trade followed. Ties go to the stock this run traded most often, and "
            "then to the last one alphabetically"
        ),
    )


# --- the rounding probe: the one thing CONTEXT 3.3 still calls an INTERIM ----------------------


@dataclass(frozen=True)
class RoundingCandidate:
    """A day where the two ways of rounding ``totalTicks`` draw a DIFFERENT number of rows."""

    symbol: str
    day: date
    tick_paise: int
    top_paise: int
    bottom_paise: int
    ticks_half_even: int
    ticks_half_up: int
    rows_half_even: int
    rows_half_up: int
    tpr_half_even: int
    tpr_half_up: int
    poc_half_even: Fraction
    poc_half_up: Fraction
    executed: bool
    window_volume: int

    @property
    def poc_moves(self) -> bool:
        return self.poc_half_even != self.poc_half_up

    @property
    def separation(self) -> int:
        return abs(self.rows_half_even - self.rows_half_up)


def _grid_at(top_paise: int, bottom_paise: int, *, ticks: int, tick_paise: int,
             row_size: int) -> poc_engine.RowGrid:
    """CONTEXT 3.3's row grid with ``totalTicks`` SUPPLIED rather than rounded here.

    EVIDENCE ONLY. The engine's own :func:`acumen.poc.build_rows` rounds half-even and is not
    touched; this builds the very same grid from a given tick count so the OTHER rounding can be
    drawn beside it and the trader can say which one his chart shows.
    """
    per_row = poc_engine.ticks_per_row(ticks, row_size)
    rows: list[poc_engine.Row] = []
    filled = 0
    while filled < ticks:
        span = min(per_row, ticks - filled)
        rows.append(poc_engine.Row(
            lo_paise=bottom_paise + filled * tick_paise,
            hi_paise=bottom_paise + (filled + span) * tick_paise,
            ticks=span,
        ))
        filled += span
    return poc_engine.RowGrid(
        rows=tuple(rows), bottom_paise=bottom_paise, top_paise=top_paise,
        tick_paise=tick_paise, ticks_per_row=per_row, total_ticks=ticks, row_size=row_size,
    )


def _poc_at(bars: Sequence, grid: poc_engine.RowGrid) -> Fraction:
    volumes = poc_engine.spread_volume(bars, grid)
    return grid.rows[poc_engine.poc_row_index(volumes)].midpoint_paise


def rounding_candidates(
    census: Census, *, master, store, row_size: int, progress
) -> tuple[RoundingCandidate, ...]:
    """Every day of the span's LAST CALENDAR YEAR where the rounding mode changes the row count.

    CONTEXT 3.3 pins ``totalTicks``' rounding as **half-even, an INTERIM**, with its verification
    slot in this pack. The two modes can only differ when the profile's range is exactly half a
    tick off the grid, which needs an even tick, and even then they usually draw the same number
    of rows. This finds the days where they do NOT -- the only days a row count read off his own
    chart can settle it.

    Bounded to the last calendar year on purpose, and the bound is printed with the answer: a
    day he can still pull up is worth more here than an older one, and the scan is over the days
    THIS RUN evaluated, so every candidate has a profile the ledger already recorded.

    ``master`` is the Q-20 PINNED instrument master (the ticks the run itself used) and ``store``
    is the 1-minute lake. Neither is taken from a runner, because this scan has to finish BEFORE
    the runner is wired: it is what decides the sixth symbol, and a runner built without that
    symbol would carry no corporate-action factors for it.
    """
    by_symbol: dict[str, list[date]] = {}
    for (symbol, day) in census.recent_pocs:
        by_symbol.setdefault(symbol, []).append(day)

    traded = ({(day, symbol) for day, symbol in census.winners}
              | {(day, symbol) for day, symbol in census.gaps}
              | {(day, symbol) for day, symbol, _risk in census.stops})
    found: list[RoundingCandidate] = []
    for index, symbol in enumerate(sorted(by_symbol), start=1):
        tick = master.instrument(symbol).tick_size_paise
        if tick % 2:
            continue  # an odd tick has no half-tick residual: the two modes cannot differ
        for day in sorted(by_symbol[symbol]):
            session, _dropped = in_session_bars(store.minutes(symbol, day))
            window = poc_engine.window_bars(session, day)
            if not window:
                continue
            top = max(bar.high_paise for bar in window)
            bottom = min(bar.low_paise for bar in window)
            whole, remainder = divmod(top - bottom, tick)
            if remainder + remainder != tick or whole % 2:
                # Not a half-tick residual, or the floor is odd and both modes round the same
                # way. Either way there is nothing here for the trader to decide.
                continue
            even_grid = _grid_at(top, bottom, ticks=max(1, whole), tick_paise=tick,
                                 row_size=row_size)
            up_grid = _grid_at(top, bottom, ticks=max(1, whole + 1), tick_paise=tick,
                               row_size=row_size)
            if len(even_grid.rows) == len(up_grid.rows):
                continue
            found.append(RoundingCandidate(
                symbol=symbol, day=day, tick_paise=tick, top_paise=top, bottom_paise=bottom,
                ticks_half_even=even_grid.total_ticks, ticks_half_up=up_grid.total_ticks,
                rows_half_even=len(even_grid.rows), rows_half_up=len(up_grid.rows),
                tpr_half_even=even_grid.ticks_per_row, tpr_half_up=up_grid.ticks_per_row,
                poc_half_even=_poc_at(window, even_grid), poc_half_up=_poc_at(window, up_grid),
                executed=(day, symbol) in traded,
                window_volume=sum(int(bar.volume) for bar in window),
            ))
        if index % 40 == 0:
            progress(f"rounding probe: {index}/{len(by_symbol)} symbols, {len(found)} candidates")
    return tuple(sorted(found, key=lambda c: (c.day, c.symbol)))


def _rounding_rivals(candidates: Sequence[RoundingCandidate],
                     probe: RoundingCandidate) -> str:
    """The days tied with the chosen one on both stated keys, and the key that separated them.

    REVIEW_12 finding Q14: "the one with the widest gap" is a definite description, and on this
    run it is not unique -- two days tie at the maximum separation with a moving POC. The key
    that decided it (the day TRADED, so the walk can show the rest of the rule) lived only in a
    docstring. Both are printed now, and both are computed, so a run where the tie does not
    happen simply says so.
    """
    tied = [one for one in candidates
            if one.separation == probe.separation and one.poc_moves == probe.poc_moves
            and (one.symbol, one.day) != (probe.symbol, probe.day)]
    if not tied:
        return ", and it is the only such day"
    listed = ", ".join(f"{one.symbol} on {_long_date(one.day)}" for one in
                       sorted(tied, key=lambda one: (one.day, one.symbol)))
    traded = [one for one in tied if not one.executed]
    because = (" -- this one is shown because it also TOOK A TRADE, and a day with no trade "
               "cannot show the rest of the rule"
               if traded and probe.executed else
               " -- this one is shown because it is the more recent")
    return (f". {len(tied) + 1} days tie on both of those ({listed}){because}")


def pick_rounding_day(candidates: Sequence[RoundingCandidate]) -> RoundingCandidate | None:
    """The candidate a row count read off a chart can settle most cleanly.

    In order: the widest gap between the two row counts (the easiest thing to count and be sure
    of), then a day where the POC itself MOVES (so the answer is worth money and not only
    tidiness), then a day that actually took a trade, then the most recent.
    """
    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.separation, c.poc_moves, c.executed, c.day, c.symbol))


# --- one day, replayed through the engines that walked it --------------------------------------


@dataclass(frozen=True)
class Walk:
    """One chosen day, walked end to end, with the run's own committed row beside it."""

    choice: Choice
    bias: DailyBias
    stock_day: StockDay
    replayed: bt.LedgerRow
    committed: Mapping
    tick_paise: int
    #: The 1-minute candle that broke one of P's extremes FIRST on a Rule-3 day, as
    #: ``(stamp, level, side)`` -- the observable the whole day turns on, which REVIEW_12 finding
    #: Q6 found asserted but not printed. ``None`` on every day that is not decided by Rule 3.
    first_break: tuple[datetime, int, str] | None = None
    bias_set_on: date | None = None
    bias_set_by: str | None = None
    rounding: RoundingCandidate | None = None
    rounding_signal: sig.SignalDay | None = None
    rounding_trade: sim.TradeRecord | None = None
    divergences: tuple[str, ...] = ()

    @property
    def agrees(self) -> bool:
        return not self.divergences

    @property
    def fields_compared(self) -> int:
        return len(self.committed)


def _committed_row(run_dir: Path, symbol: str, day: date) -> dict:
    shard = run_dir / "symbols" / f"{symbol}.jsonl"
    wanted = day.isoformat()
    with shard.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload["day"] == wanted:
                return payload
    raise bt.BacktestError(f"{symbol} {wanted} is not in {shard}.")


HIGH_FIRST: str = "high"
LOW_FIRST: str = "low"
BOTH_AT_ONCE: str = "both"


def first_break(bars: Sequence, previous) -> tuple[datetime, int, str] | None:
    """The first 1-minute candle to break one of P's extremes, and which one. PURE.

    CONTEXT 3.2's own predicate, restated for the PAGE rather than for the engine: a break is a
    1-minute high strictly above P's high (or a low strictly below P's low), scanned in time
    order, and a minute that breaks both is the tie. :func:`acumen.bias._first_break` decides the
    bias with exactly this test; this returns the STAMP and the LEVEL as well, because REVIEW_12
    finding Q6 found the pack asserting which side broke first without printing the one
    observable the trader would have to look at to check it. ``tests/test_trader_pack.py``
    asserts the two agree.
    """
    for bar in bars:
        high_broke = bar.high_paise > previous.high
        low_broke = bar.low_paise < previous.low
        if high_broke and low_broke:
            return bar.stamp, bar.high_paise, BOTH_AT_ONCE
        if high_broke:
            return bar.stamp, bar.high_paise, HIGH_FIRST
        if low_broke:
            return bar.stamp, bar.low_paise, LOW_FIRST
    return None


def _bias_origin(series: Mapping[date, DailyBias], day: date) -> tuple[date | None, str | None]:
    """Walk back to the day this day's carried bias was last SET by a rule that fired."""
    ordered = sorted(d for d in series if d <= day)
    for earlier in reversed(ordered):
        entry = series[earlier]
        if entry.rule not in CARRY_RULES and entry.bias is not None:
            return earlier, entry.rule
    return None, None


def walk(
    runner: bt.BacktestRunner,
    choice: Choice,
    *,
    run_dir: Path,
    series: Mapping[date, DailyBias],
    rounding: RoundingCandidate | None = None,
) -> Walk:
    """Replay one chosen day through the run's own engines and compare it with the ledger. I/O."""
    bias = series[choice.day]
    stock_day = runner.pipeline.stock_day(choice.symbol, choice.day, bias=bias)
    replayed = runner.walk_day(choice.symbol, bias)
    committed = _committed_row(run_dir, choice.symbol, choice.day)
    fresh = replayed.as_dict()
    divergences = tuple(sorted(
        f"{key}: the run wrote {committed[key]!r}, this replay produced {fresh.get(key)!r}"
        for key in committed
        if committed[key] != fresh.get(key)
    ))
    set_on, set_by = (None, None)
    if bias.rule in CARRY_RULES:
        set_on, set_by = _bias_origin(series, choice.day)

    broke = None
    if (bias.rule in (bias_engine.RULE_3, bias_engine.RULE_3_TIE)
            and bias.current_date is not None and bias.previous_candle is not None):
        # The Rule-3 scan reads day C's OWN minutes, with CONTEXT 7-E2 / Q-17 strays dropped
        # first -- the same bars, through the same filter, the run's own loader handed the
        # engine. Read here only to PRINT the break the bias already turned on.
        minutes, _dropped = in_session_bars(
            runner.minute_store.minutes(choice.symbol, bias.current_date)
        )
        broke = first_break(minutes, bias.previous_candle)

    alt_signal = None
    alt_trade = None
    if rounding is not None and stock_day.signal is not None and stock_day.side is not None:
        alt_signal = sig.evaluate_day(
            stock_day.bars, day=choice.day, side=stock_day.side,
            poc_paise=rounding.poc_half_up, minute_bars=(),
        )
        alt_trade = sim.simulate_day(
            alt_signal, stock_day.bars, symbol=choice.symbol,
            risk_per_trade_paise=runner.spec.risk_per_trade_paise,
            cost_paise=runner.spec.cost_paise, bias=bias.bias, tie_case=bias.tie_case,
        )
    return Walk(
        choice=choice, bias=bias, stock_day=stock_day, replayed=replayed, committed=committed,
        tick_paise=runner.pipeline.master.instrument(choice.symbol).tick_size_paise,
        first_break=broke, bias_set_on=set_on, bias_set_by=set_by, rounding=rounding,
        rounding_signal=alt_signal, rounding_trade=alt_trade, divergences=divergences,
    )


# --- reading everything ------------------------------------------------------------------------


def build_everything(
    *,
    config_path: Path = Path("config.yaml"),
    run_label: str = RUN_LABEL,
    progress=lambda _message: None,
) -> dict:
    """Read the run, choose the six days, replay them. I/O; the rendering below is pure."""
    config = load_config(config_path)
    data_root = Path(config.paths["data_root"])
    run_dir = data_root / "backtests" / run_label

    progress("reading the run ledger")
    run = r9.read_run(run_dir)
    capital = config.initial_capital_paise()

    progress("taking the pack's census of the ledger")
    counted = census(run_dir)

    progress("computing the ten-year figures")
    columns = pf.metrics(run.executed, label="All", initial_capital_paise=capital, days=run.days)
    series = pf.daily_pnl(run.executed, days=run.days)
    curve = pf.equity_curve(series, capital)
    drawdown = pf.max_drawdown(curve)
    disclosures = pf.disclosures(run.executed)
    years = r9.per_year(run.executed, run.days, initial_capital_paise=capital,
                        gap_by_year=run.witnesses.gap_by_year)
    register = bt.load_residual_register(data_root / bt.RESIDUAL_LEDGER_RELPATH)

    spec = run.manifest["spec"]
    choices = [_pick_winner(counted), _pick_stop(counted), _pick_gap(counted)]
    wait = _pick_wait(counted)
    if wait is not None:
        choices.append(wait)
    choices.append(_pick_carry(counted))

    progress("looking for a day the rounding rule decides")
    master, _master_path, _master_sha = bt.pinned_master(
        Path(config.paths["cache_root"]), config.instrument_master
    )
    candidates = rounding_candidates(
        counted, master=master, store=MinuteStore.at(data_root / "minute_store"),
        row_size=config.row_size, progress=progress,
    )
    probe = pick_rounding_day(candidates)
    if probe is not None:
        choices.append(Choice(
            key="f", heading="the day that settles one open question",
            symbol=probe.symbol, day=probe.day,
            criterion=(
                "a day where the two possible ways of rounding the profile's tick count draw a "
                "DIFFERENT number of rows -- so counting the rows on your own chart settles a "
                "question the specification still calls provisional. Of the days in the span's "
                "last calendar year where that happens, this is one of the days with the widest "
                "gap between the two row counts and with the POC itself moving"
                + _rounding_rivals(candidates, probe)
            ),
        ))

    progress("wiring the engines the run walked")
    runner, _runner_master, _ca = bt.build_runner(
        tuple(sorted({choice.symbol for choice in choices})),
        date.fromisoformat(spec["start"]),
        date.fromisoformat(spec["end"]),
        seed_from=date.fromisoformat(spec["seed_from"]) if spec["seed_from"] else None,
        non_standard_sessions=frozenset(
            date.fromisoformat(day) for day in run.manifest["non_standard_sessions_excluded"]
        ),
        label=run_label,
    )

    walks: list[Walk] = []
    cached: dict[str, Mapping[date, DailyBias]] = {}
    for choice in choices:
        progress(f"replaying {choice.symbol} {choice.day.isoformat()}")
        if choice.symbol not in cached:
            biases, failure = runner.bias_map(choice.symbol)
            if failure is not None:
                raise bt.BacktestError(f"{choice.symbol}: {failure}")
            cached[choice.symbol] = biases
        walks.append(walk(
            runner, choice, run_dir=run_dir, series=cached[choice.symbol],
            rounding=probe if choice.key == "f" else None,
        ))

    progress("ranking the stocks in points")
    points = pts.per_symbol(run.executed)

    return dict(
        run=run,
        config=config,
        capital_paise=capital,
        counted=counted,
        columns=columns,
        drawdown=drawdown,
        disclosures=disclosures,
        years=years,
        register=register,
        walks=tuple(walks),
        candidates=candidates,
        probe=probe,
        row_size=config.row_size,
        points=points,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pieces = build_everything(config_path=Path(args.config), run_label=args.run, progress=print)
    text, payload = render(**pieces)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    companion = Path(args.json)
    companion.parent.mkdir(parents=True, exist_ok=True)
    companion.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n",
                         encoding="utf-8", newline="\n")
    table = Path(args.points)
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(render_points_companion(run=pieces["run"], points=pieces["points"]),
                     encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars), {companion} and {table}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen.trader_pack", description="chunk-12 trader validation pack"
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="markdown output path")
    parser.add_argument("--json", default=DEFAULT_JSON, help="JSON companion path")
    parser.add_argument("--points", default=DEFAULT_POINTS,
                        help="full per-stock points table (markdown)")
    parser.add_argument("--run", default=RUN_LABEL, help="run label under <data_root>/backtests")
    parser.add_argument("--config", default="config.yaml", help="config path")
    return parser.parse_args(argv)


# --- rendering (PURE: takes what was read above, returns the page and its companion) ----------


class _Emit:
    """The page, and a record of every figure it prints, built at the same time.

    Nothing on the page may be a number typed into this file, so every rupee amount, every
    percentage and every count leaves through one of the three methods below, which format it
    AND write it into the JSON companion. That is what makes ``tokens`` in the companion a
    complete list of the pack's own figures rather than a hopeful one, and it is what
    ``tests/test_trader_pack.py`` checks the rendered page against.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.money: list[dict] = []
        self.percent: list[dict] = []
        self.count: list[dict] = []
        self.points: list[dict] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, line: str = "") -> None:
        self.lines.append(line)

    def rs(self, paise) -> str:
        """A rupee amount, from integer (or exact-Fraction) paise."""
        text = pf.format_paise(paise)
        self._record(self.money, str(paise), text)
        return text

    def poc(self, value: Fraction) -> str:
        """A POC, which CONTEXT 3.3 lets sit on HALF a paisa -- printed as it really is.

        :func:`acumen.portfolio.format_paise` quantizes to the paisa, which is right for money
        and wrong for a row midpoint: it would silently move a half-paise POC by half a paisa on
        a page whose whole purpose is that the trader can check it against his own chart.
        """
        if value.denominator == 1:
            return self.rs(value)
        exact = (Decimal(value.numerator) / Decimal(value.denominator)
                 / Decimal(PAISE_PER_RUPEE)).quantize(Decimal("0.001"))
        sign = "-" if exact < 0 else ""
        text = f"{sign}Rs {abs(exact):,.3f}"
        self._record(self.money, str(value), text)
        return text

    def pt(self, paise, *, signed: bool = True) -> str:
        """A number of POINTS -- a per-share price move, in the same units his chart shows.

        Recorded in its own channel rather than with the money, because a point is not a rupee:
        page 7 exists precisely to keep the two apart, and the companion has to be able to say
        which of the two any figure on the page is.
        """
        text = pts.format_points(paise, signed=signed)
        self._record(self.points, str(paise), text)
        return text

    def pct(self, value, places: int = 2) -> str:
        text = pf.format_pct(value, places)
        self._record(self.percent, str(value), text)
        return text

    def ratio(self, value: Fraction, places: int = 4) -> str:
        """A plain multiple -- "how many times", not a percentage."""
        quantum = Decimal(1).scaleb(-places)
        text = str((Decimal(value.numerator) / Decimal(value.denominator)).quantize(quantum))
        self._record(self.percent, str(value), text)
        return text

    def n(self, value: int) -> str:
        text = f"{value:,}"
        self._record(self.count, str(value), text)
        return text

    def _record(self, into: list[dict], raw: str, text: str) -> None:
        key = (text, raw)
        if key in self._seen:
            return
        self._seen.add(key)
        into.append({"value": raw, "text": text})

    @property
    def text(self) -> str:
        return "\n".join(self.lines).rstrip("\n") + "\n"


def _long_date(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}"


def _clock(stamp: datetime | None) -> str:
    return "-" if stamp is None else stamp.strftime("%H:%M")


def _break_even_win_rate(metrics: pf.Metrics) -> Fraction | None:
    """The win rate at which this average winner and this average loser would break even. PURE.

    ``p * avg_profit + (1 - p) * avg_loss == 0`` solves to ``-avg_loss / (avg_profit - avg_loss)``
    with ``avg_loss`` negative, so it is a pure function of the two averages already on the page
    and of nothing else. It is taken over the trades that made or lost money -- a trade whose net
    is exactly zero is in neither average and cannot move the answer.
    """
    win, loss = metrics.avg_profit_paise, metrics.avg_loss_paise
    if win is None or loss is None or win == loss:
        return None
    return (-loss) / (win - loss)


def render(
    *,
    run: r9.RunData,
    config,
    capital_paise: int,
    counted: Census,
    columns: pf.Metrics,
    drawdown: pf.Excursion,
    disclosures: pf.Disclosures,
    years: Sequence[r9.YearRow],
    register,
    walks: Sequence[Walk],
    candidates: Sequence[RoundingCandidate],
    probe: RoundingCandidate | None,
    row_size: int,
    points: Sequence[pts.SymbolPoints],
) -> tuple[str, dict]:
    """The pack and its JSON companion, from the pieces above. PURE."""
    emit = _Emit()
    figures: dict = {}

    _page_header(emit, run=run, columns=columns)
    _page_arithmetic(emit, figures, run=run, columns=columns, counted=counted,
                     config=config, capital_paise=capital_paise)
    _page_rules(emit, figures, config=config, row_size=row_size)
    _page_days(emit, figures, walks=walks, counted=counted, candidates=candidates, probe=probe,
               row_size=row_size, run=run)
    _page_years(emit, figures, years=years, drawdown=drawdown, columns=columns,
                capital_paise=capital_paise)
    _page_limits(emit, figures, run=run, disclosures=disclosures, capital_paise=capital_paise,
                 config=config, register=register)
    _page_questions(emit, figures, run=run, walks=walks, probe=probe)
    _page_points(emit, figures, run=run, points=points)
    _page_footer(emit, run=run)

    payload = {
        "_note": (
            "Machine-readable companion to docs/validation/trader_pack.md. Every figure the pack "
            "quotes is here: `figures` carries them by name for a document build, `tokens` "
            "carries every rupee, percentage and count the page printed, in the order it first "
            "printed them, with the exact value beside the rendered text. Generated by "
            "src/acumen/trader_pack.py; never edited by hand."
        ),
        "run": {
            "label": run.manifest["spec"]["label"] or RUN_LABEL,
            "spec_version": run.manifest["spec_version"],
            "code_sha": run.manifest["code_sha"],
            "ledger_sha256": run.ledger_sha256,
            "manifest_sha256": run.manifest_sha256,
            "span_start": run.days[0].isoformat(),
            "span_end": run.days[-1].isoformat(),
            "report": REPORT_PATH,
        },
        "figures": figures,
        "tokens": {"money": emit.money, "percent": emit.percent, "count": emit.count,
                   "points": emit.points},
    }
    return emit.text, payload


def _page_header(emit: _Emit, *, run: r9.RunData, columns: pf.Metrics) -> None:
    emit.add("# Your strategy, run over ten years")
    emit.add("")
    emit.add("This is the evidence pack. It is written for you, not for the people who built "
             "the machine, so there is no jargon in it that is not explained on the spot.")
    emit.add("")
    emit.add("**What the machine is.** It is your strategy and nothing else: the bias rules you "
             "wrote down, the volume profile from your own chart settings, the entry, the stop "
             "and the target exactly as you described them. It was given no discretion. It took "
             "EVERY signal your rules produced, on every stock, on every day it had good data "
             f"for -- {emit.n(run.totals['executed'])} trades over "
             f"{emit.n(len(run.days))} trading days and {emit.n(len(run.symbols))} stocks, "
             f"risking up to {emit.rs(run.manifest['spec']['risk_per_trade_paise'])} on each "
             "one.")
    emit.add("")
    emit.add("**What this pack asks of you.** Two things, and nothing else. Read your rules on "
             "page 2 and tell us whether they are right. Open the six days on page 3 on your own "
             "TradingView chart and tell us whether the machine did what you would have done. "
             "Everything else here is there so that nothing is hidden from you.")
    emit.add("")
    emit.add("**What this pack does not do.** It does not tell you what to do next. Page 6 sets "
             "out three ways forward, written as flatly as we can manage, with no recommendation "
             "attached to any of them.")
    emit.add("")
    emit.add("**And the view you asked for.** Page 7 is the stocks in POINTS -- what each one "
             "moved per share, with no position size in it. It is the last page because page 1 "
             "is the one that says what the account did.")
    emit.add("")


def _page_arithmetic(emit: _Emit, figures: dict, *, run: r9.RunData, columns: pf.Metrics,
                     counted: Census, config, capital_paise: int) -> None:
    totals = run.totals
    executed = totals["executed"]
    cost_each = run.manifest["spec"]["cost_paise"]
    risk_each = run.manifest["spec"]["risk_per_trade_paise"]
    break_even = _break_even_win_rate(columns)
    cost_share = Fraction(cost_each, risk_each)

    emit.add("## 1. The arithmetic")
    emit.add("")
    emit.add("Three lines. There is no opinion in them.")
    emit.add("")
    emit.add("| | |")
    emit.add("|---|---:|")
    emit.add(f"| What the trades made, before costs | **{emit.rs(totals['gross_pnl_paise'])}** |")
    emit.add(f"| What the costs took: {emit.n(executed)} trades x "
             f"{emit.rs(cost_each)} | **{emit.rs(-totals['cost_paise'])}** |")
    emit.add(f"| What is left | **{emit.rs(totals['net_pnl_paise'])}** |")
    emit.add("")
    emit.add("**The costs are the whole story, and they are not a rounding error.** Every "
             f"round trip costs {emit.rs(cost_each)}. You risk {emit.rs(risk_each)} on a trade. "
             f"So the cost of taking a trade is {emit.pct(cost_share)} of the money you put at "
             "risk on it -- before the market has moved at all. A strategy that wins three times "
             "what it risks has to clear that on every single trade, and this one took "
             f"{emit.n(executed)} of them.")
    emit.add("")
    decided = columns.winners + columns.losers
    delivered_on_decided = (Fraction(columns.winners, decided) if decided else None)
    emit.add("**The one number that explains the rest.** With this strategy's own average "
             f"winner ({emit.rs(columns.avg_profit_paise)}) and its own average loser "
             f"({emit.rs(columns.avg_loss_paise)}), both after costs, it would need to win "
             f"**{emit.pct(break_even)}** of its trades just to end level. It won "
             f"**{emit.pct(delivered_on_decided)}** of them "
             f"({emit.n(columns.winners)} of {emit.n(decided)}). Both figures are taken over the "
             "trades that made or lost money, which is the same population the two averages come "
             f"from: {emit.n(columns.flat)} trades ended exactly level and are in neither. Over "
             f"all {emit.n(columns.total_trades)} trades the win rate is "
             f"{emit.pct(columns.percent_profitable)} -- the same story, a hundredth of a "
             "point apart. That gap is the whole result. Nothing else on this page changes it.")
    emit.add("")
    emit.add("**Say plainly what was run.** This is YOUR strategy, with your rules as YOU "
             "confirmed them -- every one of them is quoted back to you on the next page. Every "
             "signal those rules produced was taken; none was skipped, filtered, improved or "
             f"second-guessed. Every trade risked at most {emit.rs(risk_each)}, as whole shares "
             "allow -- the share count is rounded DOWN, so most trades risk a little less and "
             "none risks more (page 3 shows the exact figure on each day). The machine was never "
             "allowed to decide anything you had not already decided.")
    emit.add("")

    figures["arithmetic"] = {
        "gross_before_costs_paise": totals["gross_pnl_paise"],
        "trades": executed,
        "cost_per_trade_paise": cost_each,
        "costs_paise": totals["cost_paise"],
        "net_paise": totals["net_pnl_paise"],
        "risk_per_trade_paise": risk_each,
        "cost_share_of_risk": str(cost_share),
        "avg_profit_paise": str(columns.avg_profit_paise),
        "avg_loss_paise": str(columns.avg_loss_paise),
        "break_even_win_rate": str(break_even),
        "delivered_win_rate": str(columns.percent_profitable),
        "delivered_win_rate_over_decided_trades": str(delivered_on_decided),
        "decided_trades": decided,
        "winners": columns.winners,
        "losers": columns.losers,
        "flat": columns.flat,
        "initial_capital_paise": capital_paise,
    }


def _page_rules(emit: _Emit, figures: dict, *, config, row_size: int) -> None:
    emit.add("## 2. Your rules, written back to you")
    emit.add("")
    emit.add("This is the whole strategy as the machine has it. Where we have your own words, "
             "they are quoted. Where we do not, it is because the answer reached us as an answer "
             "rather than a sentence -- those are written out plainly and marked, and they need "
             "checking just as carefully.")
    emit.add("")
    emit.add("**Which stocks, and which days.** Every stock in the NSE futures-and-options list, "
             "on its own daily chart. No index filter, no market filter, no day-type filter: no "
             "expiry days skipped, no results days skipped, no news days skipped. Cash prices.")
    emit.add("")
    emit.add("**The bias, decided the evening before.** Take the two daily candles before the "
             "day you are trading -- call the older one P and the newer one C -- and work down "
             "this list in order. The first one that fits decides the day, and the day's bias "
             "never changes once the day has started.")
    emit.add("")
    emit.add("1. **Inside bar.** If C's high did not go above P's high AND C's low did not go "
             "below P's low, nothing changes: keep yesterday's bias. Touching the level exactly "
             "still counts as inside.")
    emit.add("2. **Rule 1, a breakout on the close.** If C closed above the top of P's body, "
             "BULLISH. If C closed below the bottom of P's body, BEARISH. The body is the "
             "open-to-close range, not the wicks.")
    emit.add("3. **Rule 2, a single sweep.** BULLISH if C's low went below P's low, C's high did "
             "NOT go above P's high, and C closed at or above the bottom of P's body. BEARISH is "
             "the mirror: C's high above P's high, C's low not below P's low, C closed at or "
             "below the top of P's body.")
    emit.add("4. **Rule 3, a sweep of both sides.** If C's high went above P's high AND C's low "
             "went below P's low, look at C's one-minute candles and find which side broke "
             "FIRST. High first means BULLISH, low first means BEARISH.")
    emit.add("5. **Nothing fits.** Keep yesterday's bias.")
    emit.add("")
    emit.add("**A bullish day is a long-only day and a bearish day is a short-only day.** The "
             "colour of a candle never matters anywhere; only closes do.")
    emit.add("")
    emit.add(f"**The volume profile.** Built once a day from the first two hours -- the "
             f"one-minute candles from 09:15 to 11:14, which is the eight 15-minute candles up "
             f"to and including the one that closes at 11:15. Row Size {emit.n(row_size)}, rows "
             "laid out by number of rows, volume split across every row a candle's range touches "
             "in proportion to how much of the candle sits in each row. The POC is the middle "
             "price of the row that ends up with the most volume, and if two rows tie, the "
             "higher one wins. Once it is fixed at 11:15 it does not move again that day.")
    emit.add("")
    emit.add("**The entry.** At 11:15 look at the close of the 11:00-11:15 candle.")
    emit.add("")
    emit.add("* On a bullish day: if that close is BELOW the POC you are armed straight away. If "
             "it is ABOVE, you wait for a 15-minute candle to close below the POC first, and "
             "then you are armed. If it is exactly ON the POC, you have no side yet -- the first "
             "candle that closes clearly above or clearly below picks the side, and that candle "
             "is never itself the entry.")
    emit.add("* Once armed, the FIRST 15-minute candle that closes above the POC is the entry, "
             "and you buy at that candle's close. A close exactly on the POC is not an entry.")
    emit.add("* Bearish days are the exact mirror, selling instead of buying.")
    emit.add("* The first entry uses the stock up for that day: one trade per stock per day, and "
             "no re-entry after an exit. Entries stop after the candle that closes at 15:00.")
    emit.add("")
    emit.add("**The stop.** The low of the entry candle on a long, the high of it on a short -- "
             "no buffer. Unless the entry candle gapped clean past the POC and never traded back "
             "to it, in which case the stop is the previous 15-minute candle's close.")
    emit.add("")
    emit.add("**The target.** Three times the distance from the entry to the stop.")
    emit.add("")
    emit.add("**Getting out.** Watching starts on the candle AFTER the one you entered on: the "
             "entry candle has already traded down to its own low, which on a long IS the stop, "
             "so it can never stop you out itself. From the next candle onwards -- if the price "
             "touches the stop, you are out at the stop; if it touches the target, you are out "
             "at the target; if one candle touches both, the stop wins. If neither is touched, "
             "you are out at the close of the 15:00-15:15 candle. No partial exits and no "
             "trailing.")
    emit.add("")
    emit.add("**The money.** Every trade risks the same rupee amount, and the number of shares "
             "is that amount divided by the distance from entry to stop, rounded DOWN. If that "
             "works out to zero shares the trade cannot be taken -- and the stock is still used "
             "up for the day.")
    emit.add("")
    emit.add("### The answers of yours we have in your own words")
    emit.add("")
    emit.add("| You said | Which fixed |")
    emit.add("|---|---|")
    for tag, quote, fixes in TRADER_WORDS:
        emit.add(f"| *\"{quote}\"* ({tag}) | {fixes} |")
    emit.add("")
    emit.add("Everything above that is not in that table reached us through earlier rounds of "
             "questions as an answer rather than a sentence, and it lives in the specification "
             "as our record of what you said. That is exactly why this page exists.")
    emit.add("")
    emit.add("**Confirm these are your rules, exactly.**")
    emit.add("")

    figures["rules"] = {
        "row_size": row_size,
        "quotes": [{"tag": tag, "words": quote, "fixes": fixes}
                   for tag, quote, fixes in TRADER_WORDS],
    }


def _page_days(emit: _Emit, figures: dict, *, walks: Sequence[Walk], counted: Census,
               candidates: Sequence[RoundingCandidate], probe: RoundingCandidate | None,
               row_size: int, run: r9.RunData) -> None:
    emit.add("## 3. Six days you can open on your own chart")
    emit.add("")
    emit.add("Each of these is a real day out of the ten years. None of them was picked by hand: "
             "each one is the answer to a written rule, and the rule is printed with the day so "
             "you can see there was no choosing involved.")
    emit.add("")
    emit.add(f"To follow along: open the stock on a 15-minute chart, put a Fixed Range Volume "
             f"Profile over 09:15 to 11:15 with Row Size {emit.n(row_size)}, and put the daily "
             "chart beside it for the two days before.")
    emit.add("")
    emit.add("Every one of these days was also RE-RUN through the machine while this pack was "
             "being written, and the answer was compared with what the machine wrote down on the "
             "day it ran. Each day says how many pieces of its record matched.")
    emit.add("")
    day_figures = []
    letters = "abcdef"
    moving = sum(1 for one in candidates if one.poc_moves)
    for index, one in enumerate(walks):
        day_figures.append(_render_walk(
            emit, one, index=index, letters=letters, row_size=row_size,
            candidate_count=len(candidates), moving_count=moving,
        ))
    emit.add("### And two counts you asked us to make")
    emit.add("")
    emit.add(f"**Days where the 11:15 candle closed exactly ON the POC: "
             f"{emit.n(len(counted.wait_rule_days))}** out of the "
             f"{emit.n(run.usable)} stock-days the machine was able to judge. That is the case "
             "you answered with option A -- the first candle only picks the side. "
             f"{emit.n(sum(1 for row in counted.wait_rule_days if row[3]))} of them went on to "
             "take a trade, so the rule is not a curiosity in the corner of the specification: "
             "it decided real money.")
    emit.add("")
    bullish_ties = sum(1 for row in counted.tie_days if row[2] == bias_engine.BULLISH)
    bearish_ties = sum(1 for row in counted.tie_days if row[2] == bias_engine.BEARISH)
    emit.add(f"**Outside-bar days where BOTH sides broke inside the same one-minute candle: "
             f"{emit.n(len(counted.tie_days))}** in ten years. That is the tie you settled in "
             "Round 3 when you said the colour of that one-minute candle does not matter and "
             "that you look at where the DAY closed against the previous day's body. It is not "
             f"zero, so your answer decided real days: {emit.n(bullish_ties)} of them came out "
             f"bullish and {emit.n(bearish_ties)} bearish"
             + (" -- and that split is your own rule showing through, not a coincidence: a close "
                "INSIDE the previous day's body goes bullish, and a close outside it was already "
                "decided by Rule 1 before the tie was ever reached, so on a tie there is nothing "
                "left for the bearish side to catch."
                if bearish_ties == 0 else ".")
             + f" The earliest was {counted.tie_days[0][1]} on "
             f"{_long_date(counted.tie_days[0][0])} and the latest {counted.tie_days[-1][1]} on "
             f"{_long_date(counted.tie_days[-1][0])}.")
    emit.add("")
    emit.add("**What the machine found on each stock-day it looked at.**")
    emit.add("")
    emit.add("| Rule | Days |")
    emit.add("|---|---:|")
    for rule, count in counted.bias_rules.items():
        emit.add(f"| {_rule_words(rule)} | {emit.n(count)} |")
    emit.add("")
    ruled = sum(counted.bias_rules.values())
    emit.add(f"**Those rows add up to {emit.n(ruled)}, and here is the rest of the arithmetic so "
             f"you can check it.** The machine walked {emit.n(run.walked)} stock-days in all. "
             f"{emit.n(run.walked - ruled)} of them carry no rule at all -- they are days the "
             "market was not open in the normal way (a Muhurat session, say), thrown out before "
             "any bias was computed. Of the ones that do carry a rule, three of the rows above "
             "say *not judged*: a bias could not be settled there, so no trade was possible. And "
             f"{emit.n(ruled - run.usable)} more had a bias but were refused afterwards on a "
             f"data check, which is why the table is bigger than the {emit.n(run.usable)} "
             "stock-days the machine actually judged and could have traded.")
    emit.add("")
    used = sorted({one.bias.rule for one in walks})
    missing = [rule for rule in counted.bias_rules
               if rule in (bias_engine.RULE_1, bias_engine.RULE_2, bias_engine.RULE_3,
                           bias_engine.RULE_INSIDE) and rule not in used]
    if missing:
        emit.add("The days above were chosen by what happened on them rather than by which rule "
                 "decided them, so they do not cover every rule: "
                 + ", ".join(_rule_words(rule) for rule in missing)
                 + (" is" if len(missing) == 1 else " are")
                 + " not among them. Said out loud rather than left to be noticed.")
        emit.add("")

    figures["days"] = day_figures
    figures["counts"] = {
        "wait_rule_days": len(counted.wait_rule_days),
        "wait_rule_days_that_traded": sum(1 for row in counted.wait_rule_days if row[3]),
        # REVIEW_12 finding C3: this used to be the LAST TUPLE of a list sorted by (day, symbol),
        # i.e. the alphabetically last stock on that day -- which is a sort artefact and was not
        # the day the page shows. The date and the SHOWN day are now separate and each says what
        # it is.
        "wait_rule_most_recent_day": (counted.wait_rule_days[-1][0].isoformat()
                                      if counted.wait_rule_days else None),
        "wait_rule_day_shown_on_page": next(
            ([one.choice.day.isoformat(), one.choice.symbol] for one in walks
             if one.choice.key == "d"), None),
        "rule3_tie_days": len(counted.tie_days),
        "rule3_tie_bullish": sum(1 for row in counted.tie_days
                                 if row[2] == bias_engine.BULLISH),
        "rule3_tie_bearish": sum(1 for row in counted.tie_days
                                 if row[2] == bias_engine.BEARISH),
        "rule3_tie_first": [counted.tie_days[0][0].isoformat(), counted.tie_days[0][1]]
        if counted.tie_days else None,
        "rule3_tie_last": [counted.tie_days[-1][0].isoformat(), counted.tie_days[-1][1]]
        if counted.tie_days else None,
        "bias_rules": dict(counted.bias_rules),
        "bias_rules_total": sum(counted.bias_rules.values()),
        "bias_rules_walked_without_a_rule": run.walked - sum(counted.bias_rules.values()),
        "bias_rules_ruled_then_refused": sum(counted.bias_rules.values()) - run.usable,
        "rounding_candidates_in_window": len(candidates),
        "rounding_candidates_where_the_poc_moves": sum(1 for c in candidates if c.poc_moves),
    }


def _rule_words(rule: str) -> str:
    return {
        bias_engine.RULE_1: "Rule 1 -- a breakout on the close",
        bias_engine.RULE_2: "Rule 2 -- a single sweep",
        bias_engine.RULE_3: "Rule 3 -- both sides swept, decided on the one-minute candles",
        bias_engine.RULE_3_TIE: "Rule 3 -- both sides swept inside ONE one-minute candle",
        bias_engine.RULE_INSIDE: "Inside bar -- yesterday's bias kept",
        bias_engine.RULE_CARRY: "No rule fitted -- yesterday's bias kept",
        bias_engine.RULE_3_NO_MINUTE: "Rule 3, but no one-minute data that day -- bias kept",
        bias_engine.RULE_3_NO_BREAK: "Rule 3, but no one-minute candle broke either side -- "
                                     "bias kept",
        "no-data": "no stored one-minute data for the stock that day -- not judged",
        "minutes-ungated": "the day before failed a data check, so the bias could not be "
                           "settled -- not judged",
        "suppressed": "a demerger sat inside the pair, so no bias could be computed -- not "
                      "judged",
    }.get(rule, rule)


def _render_walk(emit: _Emit, one: Walk, *, index: int, letters: str, row_size: int,
                 candidate_count: int, moving_count: int) -> dict:
    choice, bias, day = one.choice, one.bias, one.choice.day
    stock = one.stock_day
    signal = stock.signal
    record = one.replayed
    letter = letters[index] if index < len(letters) else str(index + 1)
    emit.add(f"### 3{letter}. {choice.symbol} -- {_long_date(day)} -- {choice.heading}")
    emit.add("")
    emit.add(f"*Why this day is here: {choice.criterion}.*")
    emit.add("")

    # --- the bias ------------------------------------------------------------------------
    emit.add("**Step 1 -- the bias, settled before the day opened.**")
    emit.add("")
    previous, current = bias.previous_candle, bias.current_candle
    if previous is not None and current is not None:
        emit.add("The two daily candles the machine looked at:")
        emit.add("")
        emit.add("| | Open | High | Low | Close |")
        emit.add("|---|---:|---:|---:|---:|")
        emit.add(f"| P -- {_long_date(bias.previous_date)} | {emit.rs(previous.open)} | "
                 f"{emit.rs(previous.high)} | {emit.rs(previous.low)} | "
                 f"{emit.rs(previous.close)} |")
        emit.add(f"| C -- {_long_date(bias.current_date)} | {emit.rs(current.open)} | "
                 f"{emit.rs(current.high)} | {emit.rs(current.low)} | "
                 f"{emit.rs(current.close)} |")
        emit.add("")
        emit.add(f"P's body runs from {emit.rs(previous.body_min)} to "
                 f"{emit.rs(previous.body_max)}.")
        emit.add("")
        emit.add(_bias_sentence(emit, bias, previous, current, one))
    else:
        emit.add(f"The machine recorded this day's bias as **{bias.bias}** under "
                 f"{_rule_words(bias.rule)}.")
    emit.add("")
    emit.add(f"**Bias: {(bias.bias or 'none').upper()}** -- so "
             + ("long trades only." if bias.bias == bias_engine.BULLISH else
                "short trades only." if bias.bias == bias_engine.BEARISH else
                "no trade at all.")
             + " Nothing that happened during the day could change it.")
    emit.add("")

    # --- the POC -------------------------------------------------------------------------
    profile = stock.profile
    if profile is not None and profile.grid is not None:
        grid = profile.grid
        emit.add("**Step 2 -- the volume profile, fixed at 11:15.**")
        emit.add("")
        emit.add(f"Between 09:15 and 11:14 the stock traded between "
                 f"{emit.rs(grid.bottom_paise)} and {emit.rs(grid.top_paise)}, on "
                 f"{emit.n(profile.window_volume)} shares across "
                 f"{emit.n(profile.bar_count)} one-minute candles.")
        emit.add("")
        emit.add(f"That range is {emit.n(grid.total_ticks)} ticks wide at this stock's tick size "
                 f"of {emit.rs(one.tick_paise)}. Asking for {emit.n(row_size)} rows gives "
                 f"{emit.n(grid.ticks_per_row)} ticks in each row, which draws "
                 f"**{emit.n(len(grid.rows))} rows** -- count them on your own chart.")
        emit.add("")
        emit.add(f"The busiest row runs from "
                 f"{emit.rs(grid.rows[profile.poc_row].lo_paise)} to "
                 f"{emit.rs(grid.rows[profile.poc_row].hi_paise)}, so the **POC is "
                 f"{emit.poc(profile.poc_paise)}** -- the middle of that row.")
        emit.add("")

    # --- the state machine ---------------------------------------------------------------
    if signal is not None:
        emit.add("**Step 3 -- 11:15, and what the machine was waiting for.**")
        emit.add("")
        reference = signal.reference_paise
        emit.add(f"The 11:00-11:15 candle closed at {emit.rs(reference)}, "
                 f"{_where(reference, signal.poc_paise)} the POC. "
                 f"{_opening_state(signal, bias)}")
        emit.add("")
        if signal.transitions:
            emit.add("Then, candle by candle:")
            emit.add("")
            emit.add("| Candle closing at | Close | Against the POC | What the machine did |")
            emit.add("|---|---:|---|---|")
            for step in signal.transitions:
                emit.add(f"| {_clock(step.close_stamp)} | {emit.rs(step.close_paise)} | "
                         f"{_where(step.close_paise, signal.poc_paise)} | "
                         f"{_step_words(step, signal)} |")
            emit.add("")

    # --- the trade -----------------------------------------------------------------------
    figures_day: dict = {
        "key": choice.key,
        "symbol": choice.symbol,
        "day": day.isoformat(),
        "heading": choice.heading,
        "criterion": choice.criterion,
        "architect_named": choice.named,
        "bias": bias.bias,
        "bias_rule": bias.rule,
        "bias_detail": bias.detail,
        "bias_pair": [bias.previous_date.isoformat() if bias.previous_date else None,
                      bias.current_date.isoformat() if bias.current_date else None],
        "bias_carried_from": one.bias_set_on.isoformat() if one.bias_set_on else None,
        "bias_carried_rule": one.bias_set_by,
        "poc_half_paise": record.poc_half_paise,
        "reference_paise": record.reference_paise,
        "outcome": record.outcome,
        "tick_paise": one.tick_paise,
        "fields_compared": one.fields_compared,
        "fields_matching": one.fields_compared - len(one.divergences),
        "divergences": list(one.divergences),
    }
    if profile is not None and profile.grid is not None:
        figures_day["profile"] = {
            "top_paise": profile.grid.top_paise,
            "bottom_paise": profile.grid.bottom_paise,
            "total_ticks": profile.grid.total_ticks,
            "ticks_per_row": profile.grid.ticks_per_row,
            "rows": len(profile.grid.rows),
            "window_volume": profile.window_volume,
            "window_bars": profile.bar_count,
        }

    if record.executed:
        emit.add("**Step 4 -- the trade.**")
        emit.add("")
        emit.add("| | |")
        emit.add("|---|---|")
        emit.add(f"| Entered at the close of the {_clock(record.entry_close_stamp)} candle | "
                 f"**{emit.rs(record.entry_paise)}** |")
        emit.add(f"| Stop | **{emit.rs(record.stop_paise)}** -- "
                 f"{_stop_words(emit, record, signal, one)} |")
        emit.add(f"| Distance from entry to stop | {emit.rs(record.per_share_risk_paise)} |")
        emit.add(f"| Target, three times that distance | **{emit.rs(record.target_paise)}** |")
        emit.add("")
        emit.add(f"The number of shares is the fixed risk divided by that distance, rounded "
                 f"down: **{emit.n(record.qty)} shares**. At the entry price that is "
                 f"{emit.rs(record.notional_paise)} of stock "
                 f"{_bought_or_sold(record.side)}, with "
                 f"{emit.rs(record.per_share_risk_paise * record.qty)} genuinely at risk.")
        emit.add("")
        emit.add(f"**Step 5 -- how it ended.** {_exit_words(emit, record)}")
        emit.add("")
        emit.add("| | |")
        emit.add("|---|---:|")
        emit.add(f"| Profit or loss on the shares | {emit.rs(record.gross_pnl_paise)} |")
        emit.add(f"| The round-trip cost | {emit.rs(-record.cost_paise)} |")
        emit.add(f"| **What the day was worth** | **{emit.rs(record.net_pnl_paise)}** |")
        emit.add("")
        figures_day["trade"] = {
            "entry_paise": record.entry_paise,
            "entry_close_stamp": record.entry_close_stamp.isoformat(),
            "stop_paise": record.stop_paise,
            "target_paise": record.target_paise,
            "per_share_risk_paise": record.per_share_risk_paise,
            "qty": record.qty,
            "notional_paise": record.notional_paise,
            "gap_entry": record.gap_entry,
            "exit_kind": record.exit_kind,
            "exit_paise": record.exit_paise,
            "exit_close_stamp": record.exit_close_stamp.isoformat()
            if record.exit_close_stamp else None,
            "gross_pnl_paise": record.gross_pnl_paise,
            "cost_paise": record.cost_paise,
            "net_pnl_paise": record.net_pnl_paise,
        }
    else:
        emit.add(f"**Step 4 -- no trade.** {_no_trade_words(signal, record)} Nothing was bought "
                 "or sold, and the day cost nothing.")
        emit.add("")

    if one.rounding is not None:
        _render_rounding(emit, one, figures_day, row_size=row_size,
                         candidate_count=candidate_count, moving_count=moving_count)

    emit.add(f"**Does the machine's own record agree?** This day was re-run from the stored "
             f"candles while the pack was written and compared with the row the ten-year run "
             f"wrote: **{emit.n(one.fields_compared - len(one.divergences))} of "
             f"{emit.n(one.fields_compared)}** pieces of the record match"
             + ("." if one.agrees else
                " -- and the ones that do not are listed here rather than dropped: "
                + "; ".join(one.divergences) + "."))
    emit.add("")
    return figures_day


def _render_rounding(emit: _Emit, one: Walk, figures_day: dict, *, row_size: int,
                     candidate_count: int, moving_count: int) -> None:
    """The one question in the specification that only the trader's own chart can settle."""
    probe = one.rounding
    emit.add("**Step 6 -- and the question this day is really here to settle.**")
    emit.add("")
    emit.add("When the machine works out how many ticks wide the profile is, the answer on this "
             "day landed exactly halfway between two whole numbers. There are two normal ways to "
             "round a number that sits exactly halfway, and on most days they give the same "
             "profile. On this day they do not:")
    emit.add("")
    emit.add("| | Ticks | Ticks per row | Rows drawn | POC |")
    emit.add("|---|---:|---:|---:|---:|")
    emit.add(f"| What the machine did | {emit.n(probe.ticks_half_even)} | "
             f"{emit.n(probe.tpr_half_even)} | **{emit.n(probe.rows_half_even)}** | "
             f"**{emit.poc(probe.poc_half_even)}** |")
    emit.add(f"| The other way of rounding | {emit.n(probe.ticks_half_up)} | "
             f"{emit.n(probe.tpr_half_up)} | **{emit.n(probe.rows_half_up)}** | "
             f"**{emit.poc(probe.poc_half_up)}** |")
    emit.add("")
    if probe.poc_moves:
        emit.add(f"So the two ways of rounding put the POC "
                 f"{emit.poc(abs(probe.poc_half_even - probe.poc_half_up))} apart on this day.")
    else:
        emit.add("The POC happens to land in the same place either way on this day; the row "
                 "count still differs.")
    emit.add("")
    if one.rounding_trade is not None and one.rounding_signal is not None:
        alt = one.rounding_trade
        record = one.replayed
        same = (alt.entry_paise == record.entry_paise and alt.stop_paise == record.stop_paise
                and alt.qty == record.qty and alt.net_pnl_paise == record.net_pnl_paise)
        if same:
            emit.add("On this particular day the trade comes out the same either way, so nothing "
                     "here turns on it. On other days it would not.")
        else:
            emit.add("And on this day it changes the trade: under the other rounding the machine "
                     f"would have {_alt_trade_words(emit, alt)}, against "
                     f"{emit.rs(record.net_pnl_paise)} as it stands.")
        emit.add("")
        figures_day["rounding_alternative_trade"] = {
            "entry_paise": alt.entry_paise,
            "stop_paise": alt.stop_paise,
            "target_paise": alt.target_paise,
            "qty": alt.qty,
            "net_pnl_paise": alt.net_pnl_paise,
            "outcome": alt.outcome,
            "same_as_committed": same,
        }
    emit.add(f"**This is the one thing in the specification we have not been able to settle "
             f"without you.** In the last calendar year the machine walked there are "
             f"{emit.n(candidate_count)} days like this one, "
             f"{emit.n(moving_count)} of them with the POC in a different place under the two "
             "roundings. This day is among the ones where the two row counts are furthest apart "
             "-- which is what makes it the easiest to read off a chart and be sure -- and of "
             "those it is one that also took a trade, so the rest of the rule is visible on the "
             "same day. The criterion at the top of this section names the others.")
    emit.add("")
    emit.add(f"**What we need: open {one.choice.symbol} on "
             f"{_long_date(one.choice.day)}, put the Fixed Range Volume Profile over 09:15 to "
             f"11:15 with Row Size {emit.n(row_size)}, count the rows in the box, and tell us "
             "the number you get.** "
             f"If you count {emit.n(probe.rows_half_even)}, the machine is already right. If you "
             f"count {emit.n(probe.rows_half_up)}, we change one line and re-run. **And if it is "
             "neither of those, write down the number you actually counted and send that** -- "
             "the row count you gave us last time (quoted on page 2) fell between the two "
             "answers we had then, and it still settled the question, because being one row from "
             "one answer and three from the other is itself the answer. What we need is your "
             "count, not a choice between our two.")
    emit.add("")
    figures_day["rounding"] = {
        "tick_paise": probe.tick_paise,
        "top_paise": probe.top_paise,
        "bottom_paise": probe.bottom_paise,
        "ticks_half_even": probe.ticks_half_even,
        "ticks_half_up": probe.ticks_half_up,
        "ticks_per_row_half_even": probe.tpr_half_even,
        "ticks_per_row_half_up": probe.tpr_half_up,
        "rows_half_even": probe.rows_half_even,
        "rows_half_up": probe.rows_half_up,
        "poc_half_even_paise": str(probe.poc_half_even),
        "poc_half_up_paise": str(probe.poc_half_up),
        "poc_moves": probe.poc_moves,
    }


def _bias_sentence(emit: _Emit, bias: DailyBias, previous, current, one: Walk) -> str:
    rule = bias.rule
    if rule == bias_engine.RULE_INSIDE:
        carried = ""
        if one.bias_set_on is not None:
            name, _, gloss = _rule_words(one.bias_set_by).partition(" -- ")
            carried = (f" It was last SET for trading on {_long_date(one.bias_set_on)}, when your "
                       f"{name}" + (f" ({gloss})" if gloss else "")
                       + " fired on that day's own pair of candles, and nothing since has "
                       "moved it.")
        return ("C's high did not go above P's high and C's low did not go below P's low: C sits "
                "entirely inside P. That is an inside bar, and your first rule says the bias does "
                f"not change -- so the machine kept the bias it was already carrying.{carried}")
    if rule == bias_engine.RULE_1:
        if bias.bias == bias_engine.BULLISH:
            return (f"C closed at {emit.rs(current.close)}, above the top of P's body "
                    f"({emit.rs(previous.body_max)}). That is your Rule 1, a breakout on the "
                    "close: BULLISH.")
        return (f"C closed at {emit.rs(current.close)}, below the bottom of P's body "
                f"({emit.rs(previous.body_min)}). That is your Rule 1, a breakout on the close: "
                "BEARISH.")
    if rule == bias_engine.RULE_2:
        if bias.bias == bias_engine.BULLISH:
            return (f"C's low ({emit.rs(current.low)}) went below P's low "
                    f"({emit.rs(previous.low)}), C's high ({emit.rs(current.high)}) did NOT go "
                    f"above P's high ({emit.rs(previous.high)}), and C closed at "
                    f"{emit.rs(current.close)}, at or above the bottom of P's body "
                    f"({emit.rs(previous.body_min)}). That is your Rule 2, a single sweep of the "
                    "low: BULLISH.")
        return (f"C's high ({emit.rs(current.high)}) went above P's high "
                f"({emit.rs(previous.high)}), C's low ({emit.rs(current.low)}) did NOT go below "
                f"P's low ({emit.rs(previous.low)}), and C closed at {emit.rs(current.close)}, "
                f"at or below the top of P's body ({emit.rs(previous.body_max)}). That is your "
                "Rule 2, a single sweep of the high: BEARISH.")
    if rule in (bias_engine.RULE_3, bias_engine.RULE_3_TIE):
        first = ("the HIGH broke first" if bias.bias == bias_engine.BULLISH
                 else "the LOW broke first")
        if one.first_break is not None:
            stamp, level, side = one.first_break
            broke_level = previous.high if side != LOW_FIRST else previous.low
            first += (f" -- at {_clock(stamp)}, the one-minute candle reaching "
                      f"{emit.rs(level)} against P's "
                      + ("high " if side != LOW_FIRST else "low ")
                      + f"of {emit.rs(broke_level)}, and no earlier minute had touched either "
                      "extreme")
        tie = ""
        if rule == bias_engine.RULE_3_TIE:
            tie = (" In fact both sides broke inside the SAME one-minute candle -- the tie you "
                   "settled in Round 3, where the colour of that candle does not matter and the "
                   "day's own close against P's body decides.")
        return (f"C's high ({emit.rs(current.high)}) went above P's high "
                f"({emit.rs(previous.high)}) AND C's low ({emit.rs(current.low)}) went below "
                f"P's low ({emit.rs(previous.low)}). Both sides swept -- your Rule 3. So the "
                f"machine read C's one-minute candles in order and found that {first}, with C "
                f"closing at {emit.rs(current.close)} inside P's body. That makes the day "
                f"{(bias.bias or '').upper()}.{tie}")
    return (f"No rule fitted the pair, so the machine kept the bias it already had "
            f"({_rule_words(rule)}).")


def _where(close_paise: int | None, poc: Fraction) -> str:
    if close_paise is None:
        return "-"
    side = sig.poc_side(close_paise, poc)
    return {sig.ABOVE_POC: "above", sig.BELOW_POC: "below",
            sig.AT_POC: "exactly ON"}[side]


def _opening_state(signal: sig.SignalDay, bias: DailyBias) -> str:
    state = signal.initial_state
    if state == sig.STATE_ARMED:
        return ("That is the side of the POC your rule wants, so the machine was armed straight "
                "away and waiting for the entry.")
    if state == sig.STATE_WAIT_BELOW:
        return ("On a bullish day that is the wrong side, so the machine could not arm yet: it "
                "had to see a 15-minute candle close BELOW the POC first.")
    if state == sig.STATE_WAIT_ABOVE:
        return ("On a bearish day that is the wrong side, so the machine could not arm yet: it "
                "had to see a 15-minute candle close ABOVE the POC first.")
    if state == sig.STATE_SIDE_UNSET:
        return ("Exactly on it -- which is the case you answered with option A. No side yet: the "
                "first candle to close clearly above or clearly below picks the side, and that "
                "candle is never itself the entry.")
    return "No reference could be read at all, so there was no trade."


def _step_words(step: sig.Transition, signal: sig.SignalDay) -> str:
    before, after = step.state_before, step.state_after
    if signal.entry is not None and step.close_stamp == signal.entry.close_stamp:
        return f"**this is the entry** -- {_bought_or_sold(signal.side)} at this close"
    if before == after:
        if after == sig.STATE_ARMED:
            return "armed, but this close is not a trigger -- waiting"
        return "nothing changes -- still waiting"
    if after == sig.STATE_ARMED and before in (sig.STATE_WAIT_BELOW, sig.STATE_WAIT_ABOVE):
        return "this is the close it was waiting for: now armed"
    if after == sig.STATE_ARMED and before == sig.STATE_SIDE_UNSET:
        return "the side is set by this close, and it arms the day at the same time"
    if after in (sig.STATE_WAIT_BELOW, sig.STATE_WAIT_ABOVE) and before == sig.STATE_SIDE_UNSET:
        return "the side is set by this close -- but it is not the entry; now waiting"
    return f"{before} -> {after}"


def _bought_or_sold(side: str | None) -> str:
    """A long BUYS and a short SELLS. Saying "bought or sold" makes the reader do the work."""
    return "sold short" if side == sig.SHORT else "bought"


def _stop_words(emit: _Emit, record: bt.LedgerRow, signal: sig.SignalDay | None,
                one: Walk) -> str:
    """What the stop IS, and on a gap day the two numbers that decide it are printed.

    REVIEW_12 finding Q6: the gap sentence asserted that the entry candle never traded back to
    the POC without printing the candle's own extreme or its distance from the POC -- and on the
    pack's own gap day the predicate turns on ten paise.
    """
    if record.gap_entry:
        margin = _gap_margin(signal, record, one)
        shown = ""
        if margin is not None:
            extreme, poc, gap = margin
            shown = (
                ": the entry candle's "
                + ("high was " if record.side == sig.SHORT else "low was ")
                + f"{emit.rs(extreme)} against a POC of {emit.poc(poc)} -- "
                + f"{emit.rs(gap)} clear of it, and one tick the other way would have made this "
                "an ordinary stop at the entry candle's own extreme"
            )
        return ("the entry candle opened clean past the POC and never traded back to it, so the "
                "stop is the PREVIOUS 15-minute candle's close" + shown)
    if record.side == sig.LONG:
        return ("the low of the entry candle, with no buffer -- and the entry candle itself "
                "cannot stop you out, so watching starts on the next one")
    return ("the high of the entry candle, with no buffer -- and the entry candle itself cannot "
            "stop you out, so watching starts on the next one")


def _gap_margin(signal: sig.SignalDay | None, record: bt.LedgerRow,
                one: Walk) -> tuple[int, Fraction, Fraction] | None:
    """The entry candle's own extreme, the POC, and the distance between them. PURE."""
    if signal is None or signal.entry is None or record.entry_close_stamp is None:
        return None
    # CONTEXT 7-E12: a 15-minute candle is OPEN-stamped, so the candle closing at HH:MM is the
    # one stamped fifteen minutes earlier. That identity is what finds the entry candle here.
    entry_bar = next(
        (bar for bar in one.stock_day.bars
         if bar.stamp + timedelta(minutes=15) == record.entry_close_stamp),
        None,
    )
    if entry_bar is None:
        return None
    poc = signal.poc_paise
    if record.side == sig.SHORT:
        return entry_bar.high_paise, poc, poc - entry_bar.high_paise
    return entry_bar.low_paise, poc, entry_bar.low_paise - poc


def _exit_words(emit: _Emit, record: bt.LedgerRow) -> str:
    when = _clock(record.exit_close_stamp)
    if record.exit_kind == sig.EXIT_TARGET:
        return (f"The target was reached on the candle closing at {when}. The fill is the target "
                f"itself, {emit.rs(record.exit_paise)}, even though the candle ran past it.")
    if record.exit_kind == sig.EXIT_STOP:
        return (f"The stop was hit on the candle closing at {when}. The fill is the stop itself, "
                f"{emit.rs(record.exit_paise)}.")
    return (f"Neither the stop nor the target was touched all day, so the position was closed at "
            f"the close of the 15:00-15:15 candle, {emit.rs(record.exit_paise)}.")


def _no_trade_words(signal: sig.SignalDay | None, record: bt.LedgerRow) -> str:
    outcome = record.outcome
    if outcome == sig.OUTCOME_NEVER_ARMED:
        return ("The machine never got armed: the price never closed on the side of the POC your "
                "rule needs before it can look for an entry.")
    if outcome == sig.OUTCOME_ARMED_NO_CROSS:
        return ("The machine was armed and waiting all day, but no 15-minute candle ever closed "
                "on the far side of the POC, so there was never an entry.")
    if outcome == sig.OUTCOME_SIDE_NEVER_SET:
        return ("The 11:15 candle closed exactly on the POC and no later candle ever closed "
                "clearly above or below it, so the side was never even set.")
    return f"The machine recorded this day as: {outcome}."


def _alt_trade_words(emit: _Emit, alt: sim.TradeRecord) -> str:
    if not alt.executed:
        return "taken no trade at all"
    return (f"entered at {emit.rs(alt.entry_paise)} with a stop at {emit.rs(alt.stop_paise)} and "
            f"{emit.n(alt.qty)} shares, ending at {emit.rs(alt.net_pnl_paise)}")


def _page_years(emit: _Emit, figures: dict, *, years: Sequence[r9.YearRow],
                drawdown: pf.Excursion, columns: pf.Metrics, capital_paise: int) -> None:
    emit.add("## 4. The years")
    emit.add("")
    emit.add("One row per calendar year. Each row is that year's trades alone.")
    emit.add("")
    emit.add("| Year | Trades | Won | What the year made or lost |")
    emit.add("|---|---:|---:|---:|")
    for row in years:
        emit.add(f"| {row.year} | {emit.n(row.metrics.total_trades)} | "
                 f"{emit.pct(row.metrics.percent_profitable)} | "
                 f"**{emit.rs(row.metrics.net_pnl_paise)}** |")
    emit.add("")
    losing = sum(1 for row in years if row.metrics.net_pnl_paise < 0)
    emit.add(f"{emit.n(losing)} of the {emit.n(len(years))} years lost money"
             + (". Not one of them made any." if losing == len(years) else ".")
             + " The first and the last are part-years: the data starts in October of the first "
             "and the run stops at the end of July in the last, so neither is a full twelve "
             "months and neither should be read as one.")
    emit.add("")
    emit.add("### The worst stretch")
    emit.add("")
    emit.add("**Drawdown** means the drop from the best the account had ever been to the worst it "
             "got afterwards -- the money you would have watched disappear if you had sat "
             "through it.")
    emit.add("")
    peak = (f"its best day ever, {_long_date(drawdown.peak_day)}," if drawdown.peak_day
            else "the money the account started with,")
    emit.add(f"The worst stretch here ran from {peak} down to "
             f"{_long_date(drawdown.trough_day)}, and it took "
             f"**{emit.rs(drawdown.amount_paise)}**"
             + (f" across {emit.n(drawdown.duration_days)} trading days"
                if drawdown.duration_days else "")
             + ". "
             + ("It never came back inside the ten years."
                if drawdown.recovered_on is None
                else f"It was made back on {_long_date(drawdown.recovered_on)}."))
    emit.add("")
    emit.add("Put in the plainest terms: the account started with "
             f"{emit.rs(capital_paise)} and the running total of the trades ends at "
             f"{emit.rs(columns.final_equity_paise)}. A real account cannot go below zero and "
             "would have stopped a long way before that; the machine keeps adding because you "
             "asked to see the arithmetic with no limits on it, and hiding the rest would have "
             "answered your question for you.")
    emit.add("")
    figures["years"] = [
        {"year": row.year, "trades": row.metrics.total_trades,
         "win_rate": str(row.metrics.percent_profitable),
         "net_paise": row.metrics.net_pnl_paise,
         "opening_equity_paise": row.opening_equity_paise,
         "closing_equity_paise": row.closing_equity_paise,
         "gap_entries": row.gap_entries}
        for row in years
    ]
    figures["drawdown"] = {
        "amount_paise": drawdown.amount_paise,
        "peak_day": drawdown.peak_day.isoformat() if drawdown.peak_day else None,
        "trough_day": drawdown.trough_day.isoformat() if drawdown.trough_day else None,
        "observations": drawdown.duration_days,
        "recovered_on": drawdown.recovered_on.isoformat() if drawdown.recovered_on else None,
        "losing_years": losing,
        "years_counted": len(years),
        "final_equity_paise": columns.final_equity_paise,
    }


def _page_limits(emit: _Emit, figures: dict, *, run: r9.RunData, disclosures: pf.Disclosures,
                 capital_paise: int, config, register) -> None:
    peak_positions = disclosures.max_concurrent_positions
    peak_notional = disclosures.peak_simultaneous_notional
    register = register or {}
    coverage = r9._usable_share(register)
    # The two counts BEHIND the coverage percentage, so a reader can do the division himself --
    # REVIEW_12 findings Q8 and C5: the figure was printed with neither of its own terms, one
    # sentence away from a different measurement over a different denominator.
    usable_days = sum(entry.usable_pass for entry in register.values()
                      if entry.status == "settled")
    stored_days = sum(entry.gate1p_total for entry in register.values())
    quarantined = sorted(symbol for symbol, entry in register.items()
                         if entry.status != "settled")
    crore = Fraction(peak_notional.notional_paise, 100) / RUPEES_PER_CRORE
    against_capital = Fraction(peak_notional.notional_paise, capital_paise)

    emit.add("## 5. What the machine did NOT do")
    emit.add("")
    emit.add("Everything on the pages before this is true. This page is the list of ways in "
             "which it is easier than the real thing. None of it is hidden in a footnote "
             "somewhere else.")
    emit.add("")
    emit.add("**The fills are perfect, and yours would not be.** An entry fills exactly at the "
             "15-minute candle's close. A stop fills exactly at the stop price even when the "
             "candle blew straight through it, and a target fills exactly at the target price "
             "for the same reason. There is no slippage, no partial fill and no allowance for "
             "the market moving away from you. In real trading that difference costs money, and "
             "on the stops it costs money every time.")
    emit.add("")
    emit.add("**There was no limit on how much money was in play.** You asked for the honest "
             "numbers with no limits, so the machine took every signal on every stock at the "
             "same time, whether or not the money existed. At its busiest it held "
             f"**{emit.n(peak_positions.positions)} positions at once**. At its largest it had "
             f"**{emit.rs(peak_notional.notional_paise)}** of stock open at a single moment -- "
             f"about **{emit.ratio(crore, 2)} crore rupees** -- which is "
             f"{emit.ratio(against_capital)} times the {emit.rs(capital_paise)} the account "
             "started with. No real account could have carried that, and the machine was never "
             "asked to check.")
    emit.add("")
    emit.add("**We have not marked which trades your money could not have taken, and we are not "
             "going to.** That would need a capital figure from you, and you withdrew the "
             "question in favour of the points view on page 7 -- so no trade carries such a "
             "flag, here or anywhere. Nothing is guessed in its place: the machinery is built "
             "and switched off rather than run against a number we invented.")
    emit.add("")
    emit.add("**The list of stocks is today's list, walked backwards.** The machine ran the "
             f"{emit.n(len(run.symbols))} stocks it could trust the data for, out of the "
             f"{emit.n(len(register))} in the futures-and-options list NOW, all the way back to "
             "2016. A stock that was in the list in 2017 and has since dropped out is not here "
             "at all, and a stock that only joined in 2024 was still traded from 2016. That "
             "flatters any strategy that trades large, liquid names, and it is our engineering "
             "shortcut, not your instruction.")
    emit.add("")
    if quarantined:
        emit.add(f"**And {emit.n(len(quarantined))} stocks are missing from the whole thing.** "
                 + ", ".join(quarantined)
                 + " are in the futures-and-options list but their stored price history failed "
                 "our own data checks badly enough that we would not trade on it, so they were "
                 "never walked at all -- not on any day, in any year. "
                 + (f"{quarantined[0]} " if len(quarantined) == 1 else "Some of them ")
                 + "are names you would expect to see, and their absence is a hole in the result "
                 "rather than a judgement about them: nothing here says what the strategy would "
                 "have done on them. The technical report lists each one with the measurement "
                 "that refused it.")
        emit.add("")
    emit.add(f"**The cost is a flat {emit.rs(run.manifest['spec']['cost_paise'])} a trade.** That "
             "is the figure you gave us. It does not vary with the size of the trade, and a "
             "trade in ten shares pays the same as a trade in thirty thousand.")
    emit.add("")
    emit.add("**One trade per stock per day, and the money never compounds.** The first entry "
             "uses that stock up for the day, and every trade risks the same rupee amount -- as "
             "near as whole shares allow -- from beginning to end, regardless of what the "
             "account is worth. The running total adds up; it does not grow on itself.")
    emit.add("")
    if coverage is not None:
        emit.add(f"**The machine could not use every day.** Of every stock-day in the stored "
                 f"data, **{emit.pct(coverage, 4)}** passed the checks that say the prices and "
                 "volumes really are that stock's, on that day, at the right scale -- that is "
                 f"{emit.n(usable_days)} days out of {emit.n(stored_days)}, and you can do the "
                 "division yourself. The rest were REFUSED and counted -- never quietly traded "
                 "on and never quietly dropped.")
        emit.add("")
        emit.add("**That percentage and the next one are two different measurements, and they "
                 f"are not meant to agree.** The {emit.pct(coverage, 4)} above is about the "
                 "stored DATA: every stock-day we hold, including the years and the stocks this "
                 f"run never walked. What the run itself did is a smaller thing: of the "
                 f"{emit.n(run.walked)} stock-days it walked, {emit.n(run.usable)} were judged "
                 f"and {emit.n(run.refused)} were refused, and the refusals are broken down by "
                 "reason in the technical report. A stock-day can be good data and still be "
                 "refused here (no bias could be settled that morning, say), which is why the "
                 "second fraction is the smaller one.")
        emit.add("")
    emit.add("**And one thing that is still open.** The rounding question on day 3f above -- the "
             "row count only your own chart can settle. The two questions you were carrying "
             "before this pack are both answered and are written up on page 6. Nothing here was "
             "ever blocked on any of them.")
    emit.add("")
    figures["limits"] = {
        "max_concurrent_positions": peak_positions.positions,
        "max_concurrent_at": peak_positions.at.isoformat() if peak_positions.at else None,
        "peak_notional_paise": peak_notional.notional_paise,
        "peak_notional_at": peak_notional.at.isoformat() if peak_notional.at else None,
        "peak_notional_positions": peak_notional.positions,
        "peak_notional_over_capital": str(against_capital),
        "largest_single_notional_paise": disclosures.largest_single_notional_paise,
        "coverage": str(coverage) if coverage is not None else None,
        "coverage_usable_days": usable_days,
        "coverage_stored_days": stored_days,
        "walked": run.walked,
        "usable": run.usable,
        "refused": run.refused,
        "symbols": len(run.symbols),
        "universe_symbols": len(register),
        "quarantined_symbols": quarantined,
        "cost_per_trade_paise": run.manifest["spec"]["cost_paise"],
    }


def _page_questions(emit: _Emit, figures: dict, *, run: r9.RunData, walks: Sequence[Walk],
                    probe: RoundingCandidate | None) -> None:
    emit.add("## 6. What we need from you")
    emit.add("")
    emit.add("### The two questions you have now answered")
    emit.add("")
    emit.add("Neither ever held anything up, and both are closed by what you sent back.")
    emit.add("")
    emit.add("**One -- the money figure for marking unaffordable trades. You withdrew the "
             "question and asked for something else instead, and we have built what you asked "
             "for.** The machine took every signal without asking whether the cash existed, and "
             "it still does; what we are NOT doing is going back to mark trades against a "
             "capital figure, because you would rather see the stocks in points, where the size "
             "of the position does not come into it. That is page 7. The flag machinery is left "
             "in place and switched off, so nothing is lost if you ever want it:")
    emit.add("")
    emit.add(f"> {run.manifest['capital_flags']['note']}")
    emit.add("")
    emit.add("That sentence is the one this run was stamped with while the question was open. It "
             "is the run's own record, so it is quoted as it stands rather than rewritten; what "
             "is true now is the line above it.")
    emit.add("")
    emit.add("**Two -- the worked example of the gap rule. You confirmed it, and it cost "
             "nothing.** Your diagram says the example day is one where the price jumped clean "
             "past the POC, so the stop comes from the last traded close before the jump -- "
             "which is exactly the rule the machine has been running. Nothing is recomputed, no "
             "number in this pack moves, and the specification's own example is corrected to "
             "match your reading of it. The run carries the note it was stamped with while the "
             "question was open:")
    emit.add("")
    for note in run.manifest["disclosures"]:
        if "Q44" in note and "PENDING" in note:
            emit.add(f"> {note}")
            emit.add("")
            break
    emit.add("-- and that pending note is now closed by your answer, with the rule unchanged.")
    emit.add("")
    emit.add("### And two things to confirm")
    emit.add("")
    emit.add("**Confirm the rules on page 2 are yours, exactly.** If one line is wrong, say "
             "which line -- the machine is built so that a rule change is a change to one place "
             "and a re-run, not a rebuild.")
    if probe is not None:
        named = next(one for one in walks if one.rounding is not None)
        emit.add("")
        emit.add(f"**Count the rows on {named.choice.symbol}, "
                 f"{_long_date(named.choice.day)}, and tell us the number.** Day 3f explains "
                 f"why. If the box has {emit.n(probe.rows_half_even)} rows we are already right; "
                 f"if it has {emit.n(probe.rows_half_up)} we change one line and run it again; "
                 "if it has some other number, that is the useful answer and we work from it.")
    emit.add("")
    emit.add("### Three ways forward")
    emit.add("")
    emit.add("These are set out flatly and in no order. There is no recommendation attached to "
             "any of them, and there will not be one: it is your strategy and your money.")
    emit.add("")
    emit.add("**Retire it.** The arithmetic on page 1 is what these rules did over ten years, "
             "across every stock, with no discretion applied. If you conclude that the edge you "
             "trade by is the judgement you add on top of these rules rather than the rules "
             "themselves, then this machine has answered the question it was built to answer, "
             "and it can be put down. What you would be giving up is the automated version of "
             "these rules; what you would keep is everything you already knew how to do by hand.")
    emit.add("")
    emit.add("**Change it.** The rules are yours to change, and the machinery is now yours too. "
             "A different target multiple, a different profile window, a filter on which days "
             "to trade, a stop placed somewhere else, entries on a different candle -- any of "
             "these is a change to one place in the code and a re-run over the same ten years, "
             "and the answer comes back in hours rather than months. What you would be taking on "
             "is that a rule changed until it looks good on ten years of history has been fitted "
             "to that history, and only the next ten years can tell you whether it was worth it.")
    emit.add("")
    emit.add("**Take it live knowing the arithmetic.** The live half of the tool -- the screener "
             "that watches the market and alerts you when a signal fires -- is designed and "
             "specified and is on hold, waiting for this decision. It would run the same code "
             "that produced these numbers, so what you saw tested is what you would be alerted "
             "on. What you would be taking on is what page 1 says: over these ten years, on "
             "these rules, taking every signal, the arithmetic came out as it came out.")
    emit.add("")
    figures["questions"] = {
        "capital_flags_note": run.manifest["capital_flags"]["note"],
        "q44_note": next((note for note in run.manifest["disclosures"]
                          if "Q44" in note and "PENDING" in note), None),
        "confirmations_asked": [
            "confirm the rules restated on page 2",
            "count the profile rows on the day in section 3f",
        ],
        "paths": ["retire it", "change it", "take it live knowing the arithmetic"],
    }


def _page_points(emit: _Emit, figures: dict, *, run: r9.RunData,
                 points: Sequence[pts.SymbolPoints]) -> None:
    """Page 7: the stocks in POINTS -- the view he asked for in Round 4, in place of Q43.

    Everything the architect's ruling makes mandatory travels with the ranking and none of it is
    a footnote: the cost line (points ignore size, and the cost does not), the
    multiple-comparisons caveat in full sentences, and the cross-reference to page 1 so the two
    views cannot be read as contradicting each other.
    """
    if not points:  # pragma: no cover -- a run with no executed trade has nothing to rank
        return
    table = pts.totals(points)
    top, bottom = pts.ends(points)
    cost_each = run.manifest["spec"]["cost_paise"]

    emit.add("## 7. Every stock, in points")
    emit.add("")
    emit.add("This is the page you asked for instead of the capital question. **A point is one "
             "rupee of price on one share** -- what a trade moved, before any decision about "
             "how many shares to take. Every figure here is that and nothing else: the entry "
             "price against the exit price, added up per stock. It is the same trades as the "
             "rest of the pack, read in the units your chart is drawn in.")
    emit.add("")
    emit.add("**Why it is not the same as page 1, and why neither is wrong.** Page 1 is money "
             "after size and after costs. This page is price movement per share, before either. "
             f"At one share, the {emit.rs(cost_each)} round-trip cost equals "
             f"**{emit.pt(pts.cost_in_points_paise(cost_each, shares=1), signed=False)} "
             "points** -- costs scale with SIZE, which this view deliberately ignores. So a "
             "stock can look positive here and still have lost money on page 1, and both "
             "statements are true of the same trades. Page 1 is the one that says what the "
             "account did.")
    emit.add("")
    caveat = pts.MULTIPLE_COMPARISONS_CAVEAT.format(
        symbols=emit.n(table.symbols), by_chance=emit.n(pts.by_chance(table.symbols)),
    )
    emit.add(f"**{caveat}** "
             "A ranking of this many stocks will always have a top of it, and the stocks at the "
             "top of one ten-year window are not reliably the stocks at the top of the next. "
             "Nothing on this page is a recommendation to trade one stock rather than another; "
             "it is here because you asked to see the spread.")
    emit.add("")
    emit.add(f"Across all {emit.n(table.symbols)} stocks the trades moved "
             f"**{emit.pt(table.points_paise)} points** in total over "
             f"{emit.n(table.trades)} trades -- an average of "
             f"{emit.pt(table.avg_points_paise)} points a trade, with "
             f"{emit.pct(table.win_rate)} of them positive in points. **That total is positive "
             "while page 1 is negative, and both are right**: this page has no costs in it and "
             "no share counts, and page 1 has both. The two do not disagree; they measure "
             f"different things. Both ends of the ranking are printed below; **all "
             f"{emit.n(table.symbols)} stocks are in `{pts.COMPANION_PATH}`**, so nothing here "
             "is a selection.")
    emit.add("")
    for heading, rows, note in (
        (f"The {emit.n(len(top))} stocks with the most points", top,
         "Read this list as candidates for a forward check, not as a result."),
        (f"The {emit.n(len(bottom))} stocks with the fewest", bottom,
         "The bottom of a ranking is as much a product of chance as the top of it."),
    ):
        emit.add(f"**{heading}.** {note}")
        emit.add("")
        emit.add("| Stock | Trades | Trades positive in points | Points | Points a trade | "
                 "Worst points drawdown | Best trade | Worst trade |")
        emit.add("|---|---:|---:|---:|---:|---:|---:|---:|")
        for one in rows:
            emit.add(f"| {one.symbol} | {emit.n(one.trades)} | {emit.pct(one.win_rate)} | "
                     f"**{emit.pt(one.points_paise)}** | {emit.pt(one.avg_points_paise)} | "
                     f"{emit.pt(one.max_drawdown_paise, signed=False)} | "
                     f"{emit.pt(one.best_paise)} | {emit.pt(one.worst_paise)} |")
        emit.add("")
    emit.add("**What the columns mean.** *Points* is the sum of every trade's move on that "
             "stock. *Points a trade* is that divided by the number of trades. *Worst points "
             "drawdown* is the deepest fall in the running total of those points, walked in date "
             "order -- the run of losses you would have sat through on that stock alone. *Best* "
             "and *worst trade* are its single largest move each way. None of them knows how "
             "many shares were taken, and none of them has had a cost subtracted.")
    emit.add("")

    figures["points"] = {
        "symbols": table.symbols,
        "trades": table.trades,
        "winners": table.winners,
        "win_rate": str(table.win_rate),
        "points_paise": table.points_paise,
        "avg_points_paise": str(table.avg_points_paise),
        "cost_in_points_paise_at_one_share": str(pts.cost_in_points_paise(cost_each, shares=1)),
        "shown_each_end": pts.SHOWN_EACH_END,
        "companion": pts.COMPANION_PATH,
        "caveat": pts.MULTIPLE_COMPARISONS_CAVEAT.format(
            symbols=f"{table.symbols:,}", by_chance=f"{pts.by_chance(table.symbols):,}"),
        "by_symbol": list(pts.as_payload(points)),
    }


def _page_footer(emit: _Emit, *, run: r9.RunData) -> None:
    """The provenance line, last on the page whatever the last page turns out to be."""
    emit.add("---")
    emit.add("")
    emit.add(f"Everything in this pack is computed from the machine's own record of the run "
             f"(ledger `{run.ledger_sha256[:16]}...`) by `src/acumen/trader_pack.py`. Nothing in "
             f"it is typed by hand. The long technical version, with every figure and every "
             f"check, is `{REPORT_PATH}`.")


def render_points_companion(*, run: r9.RunData, points: Sequence[pts.SymbolPoints]) -> str:
    """The FULL per-stock points table, published beside the technical report. PURE.

    Page 7 of the pack shows both ends of this ranking; this is all of it, in the same order and
    the same units, carrying the same two caveats. A reader who wants to check a stock the pack
    did not print looks here, and finds it.
    """
    table = pts.totals(points)
    lines: list[str] = []
    add = lines.append
    add("# Every stock, in points -- the full table")
    add("")
    add("The companion to page 7 of `docs/validation/trader_pack.md`. **A point is one rupee of "
        "price on one share**: the per-share move each trade made, signed by side "
        "(`exit - entry` on a long, `entry - exit` on a short), summed per stock. It is computed "
        "post-hoc from the completed run's ledger and it is INDEPENDENT OF POSITION SIZE, which "
        "is what the trader asked for in Round 4 in place of his own capital question "
        "(QUESTIONS.md, ROUND-4 RECEIPTS, 06-Aug-2026).")
    add("")
    caveat = pts.MULTIPLE_COMPARISONS_CAVEAT.format(
        symbols=f"{table.symbols:,}", by_chance=f"{pts.by_chance(table.symbols):,}",
    )
    add(f"**{caveat}**")
    add("")
    cost_each = run.manifest["spec"]["cost_paise"]
    cost_in_points = pts.format_points(
        pts.cost_in_points_paise(cost_each, shares=1), signed=False,
    )
    add("**No cost is subtracted anywhere on this page, and none can be**: a flat cost per trade "
        "is a rupee amount, and converting it to points needs a position size this view refuses "
        "to consult. At one share the round-trip cost of "
        f"{pf.format_paise(cost_each)} is "
        f"{cost_in_points} "
        "points; at three hundred shares it is a third of a point. The money after costs and "
        f"size is `{REPORT_PATH}` and page 1 of the pack.")
    add("")
    add(f"Ranked by points, biggest first. {table.symbols:,} stocks, {table.trades:,} trades, "
        f"{pts.format_points(table.points_paise)} points in total, "
        f"{pts.format_points(table.avg_points_paise)} a trade.")
    add("")
    add("| # | Stock | Trades | Trades positive in points | Points | Points a trade | "
        "Worst points drawdown | Best trade | on | Worst trade | on |")
    add("|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---|")
    for index, one in enumerate(points, start=1):
        add(f"| {index:,} | {one.symbol} | {one.trades:,} | {pf.format_pct(one.win_rate)} | "
            f"**{pts.format_points(one.points_paise)}** | "
            f"{pts.format_points(one.avg_points_paise)} | "
            f"{pts.format_points(one.max_drawdown_paise, signed=False)} | "
            f"{pts.format_points(one.best_paise)} | "
            f"{one.best_day.isoformat() if one.best_day else '-'} | "
            f"{pts.format_points(one.worst_paise)} | "
            f"{one.worst_day.isoformat() if one.worst_day else '-'} |")
    add("")
    add(f"Computed by `src/acumen/points_view.py` from the run ledger "
        f"`{run.ledger_sha256[:16]}...`, rendered by `src/acumen/trader_pack.py`. Nothing on "
        "this page is typed by hand.")
    return "\n".join(lines).rstrip("\n") + "\n"


__all__ = [
    "Census",
    "Choice",
    "RoundingCandidate",
    "TRADER_WORDS",
    "Walk",
    "build_everything",
    "census",
    "main",
    "pick_rounding_day",
    "render",
    "render_points_companion",
    "rounding_candidates",
    "walk",
]
