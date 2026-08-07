"""Chunk 12: the trader validation pack -- its selection rules, its arithmetic, and its tripwire.

The pack is the one document in this repo a non-technical reader is expected to act on, so two
properties matter more here than anywhere else and both are asserted rather than asserted-about:

* **No figure on the page is typed by hand.** Two halves, and it takes both. At the SOURCE, the
  generator carries no money-shaped literal at all -- no rupee amount as text, no comma-grouped
  digit group, no CONTEXT 3.5 magnitude as an integer. At the RENDERED OUTPUT, every rupee token
  on the committed page is one the generator emitted through :meth:`acumen.trader_pack._Emit.rs`
  and therefore recorded in the JSON companion, with the exact value beside it. A number typed
  into the prose would fail the second half even if it slipped past the first (the architect's
  ruling (2) of 06-Aug-2026: a rendering fix is pinned at the rendered output).
* **The six days are chosen by rule, not by hand.** Each selection rule is exercised here on a
  synthetic census, including the branch where the day the architect NAMED does not qualify and
  the rule has to choose instead.

Offline: reads two committed files in the repository and no store.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import poc as poc_engine
from acumen import points_view as pv
from acumen import portfolio as pf
from acumen import report_9b as r9
from acumen import trader_pack as tp
from acumen.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "src" / "acumen" / "trader_pack.py"
POINTS_MODULE = REPO_ROOT / "src" / "acumen" / "points_view.py"
PACK = REPO_ROOT / "docs" / "validation" / "trader_pack.md"
COMPANION = REPO_ROOT / "docs" / "validation" / "trader_pack.json"
POINTS_TABLE = REPO_ROOT / "docs" / "reports" / "points_by_symbol.md"

#: A rupee amount as it is printed: ``Rs 1,234.56``, or a POC's honest ``Rs 918.555``.
MONEY = re.compile(r"-?Rs [0-9][0-9,]*\.[0-9]{2,3}")
#: A POINTS figure as page 7 prints it -- a signed decimal with no currency, in a table cell or
#: in a sentence. Anchored on the cell/word boundaries so it cannot swallow a date or a rupee.
POINTS = re.compile(r"(?<![0-9Rs.])[-+][0-9][0-9,]*\.[0-9]{2}(?![0-9])")
#: A paisa-shaped decimal and an Indian/Western grouped digit run -- what a hand-typed figure
#: looks like when someone writes one into prose without the formatter.
PAISA_TEXT = re.compile(r"[0-9][0-9,]*\.[0-9]{2,3}(?![0-9])")
GROUPED_TEXT = re.compile(r"[0-9]{1,3}(?:,[0-9]{2,3})+")
#: A `Decimal` rounding quantum (`0.001`) is a PRECISION, not an amount: it says how many places
#: a figure is rounded to and can carry no rupee of its own. Exempted by shape, so a quantum is
#: the only decimal below one this file may contain.
QUANTUM = re.compile(r"^0\.0*1$")


def _string_constants(source: str) -> list[str]:
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


# --- the tripwire, in both halves --------------------------------------------------------------


def test_the_pack_generator_carries_no_hand_typed_money_literal() -> None:
    """Half one: nothing in the SOURCE can supply a rupee figure.

    The only strings allowed to carry a grouped digit run are the TRADER'S OWN WORDS, which are
    quoted verbatim from `QUESTIONS.md` and must not be reworded to satisfy a test -- his Q29
    answer is literally *"risk per trade = 1,000 rupees."* That exemption is checked, not
    assumed: an offending string has to BE one of his quotes.
    """
    quoted = " || ".join(quote for _tag, quote, _fixes in tp.TRADER_WORDS)
    config = load_config(include_env=False)
    forbidden = {
        config.require_risk_per_trade_paise(),
        int(config.risk_per_trade),
        config.cost_per_trade_paise(),
        config.initial_capital_paise(),
        int(config.initial_capital),
    }

    # Both halves of the generator: the pack's own module and the POINTS module page 7 is built
    # from. A points figure is a price and would read as one on the page, so it is held to the
    # same standard as a rupee (the Round-4 extension of B301).
    for module in (MODULE, POINTS_MODULE):
        source = module.read_text(encoding="utf-8")
        assert not re.search(r"Rs\s*-?[0-9]", source), (
            f"a rupee amount typed into {module.name}, instead of formatted from a value"
        )

        for text in _string_constants(source):
            if QUANTUM.match(text):
                continue
            for pattern, what in ((PAISA_TEXT, "a paisa-shaped decimal"),
                                  (GROUPED_TEXT, "a grouped digit run")):
                for hit in pattern.findall(text):
                    assert hit in quoted, (
                        f"{what} typed into {module.name}'s prose: {hit!r} in {text!r}"
                    )

        literals = {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }
        assert not (literals & forbidden), (
            f"CONTEXT 3.5 money magnitudes hardcoded in {module.name}: "
            f"{sorted(literals & forbidden)}"
        )


def _rendered(value: str) -> set[str]:
    """Both spellings the pack may print a recorded value as: to the paisa, and to the tenth.

    Recomputed here from the recorded VALUE, not copied from the generator, so a formatter that
    started lying would be caught by this test rather than confirmed by it.
    """
    from decimal import Decimal

    exact = Fraction(value)
    amount = (Decimal(exact.numerator) / Decimal(exact.denominator)
              / Decimal(tp.PAISE_PER_RUPEE)).quantize(Decimal("0.001"))
    sign = "-" if amount < 0 else ""
    return {pf.format_paise(exact), f"{sign}Rs {abs(amount):,.3f}"}


def test_every_rupee_on_the_committed_page_is_a_figure_the_companion_carries() -> None:
    """Half two, at the RENDERED OUTPUT: the page cannot print a rupee the data does not hold.

    This is the half that survives a refactor. A figure typed straight into an f-string would
    never pass through the emitter, would never reach `tokens.money`, and would fail here.
    """
    payload = json.loads(COMPANION.read_text(encoding="utf-8"))
    recorded: dict[str, str] = {token["text"]: token["value"]
                                for token in payload["tokens"]["money"]}
    assert recorded, "the companion records no money at all"

    for text, value in recorded.items():
        assert text in _rendered(value), (
            f"the companion's own record disagrees with itself: {value} rendered as {text}"
        )

    on_page = set(MONEY.findall(PACK.read_text(encoding="utf-8")))
    assert on_page, "the pack prints no money at all"
    unaccounted = sorted(on_page - set(recorded))
    assert not unaccounted, f"rupee figures on the page that no value produced: {unaccounted}"


def test_every_POINTS_figure_on_the_committed_page_is_one_the_companion_carries() -> None:
    """The same tripwire, extended to page 7 (Round 4).

    A point is a price, and a price typed into prose is exactly what the money half of this
    tripwire exists to catch. Page 7 prints its figures through `_Emit.pt`, which records each
    one in the companion's own `points` channel with its exact paise value beside it; anything
    on the page that did not come through the emitter fails here.
    """
    payload = json.loads(COMPANION.read_text(encoding="utf-8"))
    recorded = {token["text"]: token["value"] for token in payload["tokens"]["points"]}
    assert recorded, "the companion records no points at all"

    for text, value in recorded.items():
        exact = Fraction(value)
        assert text in {pv.format_points(exact), pv.format_points(exact, signed=False)}, (
            f"the companion's own record disagrees with itself: {value} rendered as {text}"
        )

    on_page = set(POINTS.findall(PACK.read_text(encoding="utf-8")))
    assert on_page, "the pack prints no points at all"
    unaccounted = sorted(on_page - set(recorded))
    assert not unaccounted, f"points figures on the page that no value produced: {unaccounted}"


def test_the_points_ranking_can_never_be_printed_without_its_caveat() -> None:
    """The architect made the multiple-comparisons caveat MANDATORY on any per-stock ranking.

    Asserted at the RENDERED OUTPUT on BOTH documents that carry a ranking -- the pack's page 7
    and the full companion table -- so a renderer that dropped it would go red rather than ship
    a league table of 204 stocks with nothing beside it.
    """
    companion = json.loads(COMPANION.read_text(encoding="utf-8"))
    figures = companion["figures"]["points"]
    caveat = figures["caveat"]
    assert caveat == pv.MULTIPLE_COMPARISONS_CAVEAT.format(
        symbols=f"{figures['symbols']:,}", by_chance=f"{pv.by_chance(figures['symbols']):,}"
    )
    for page in (PACK, POINTS_TABLE):
        text = page.read_text(encoding="utf-8")
        assert caveat in text, f"the ranking is printed without its caveat in {page.name}"
        assert "never as proof." in text
    # ...and the cost line, which is the other half of reading a points table honestly
    pack = PACK.read_text(encoding="utf-8")
    assert "costs scale with SIZE, which this view deliberately ignores" in pack
    assert f"all {figures['symbols']:,} stocks are in `{pv.COMPANION_PATH}`" in pack


def test_the_full_points_table_carries_every_stock_the_ranking_ranks() -> None:
    """Page 7 shows both ends; the companion shows all of them, and it is the same ranking."""
    figures = json.loads(COMPANION.read_text(encoding="utf-8"))["figures"]["points"]
    rows = figures["by_symbol"]
    assert len(rows) == figures["symbols"]
    assert [one["symbol"] for one in rows] == sorted(
        (one["symbol"] for one in rows),
        key=lambda symbol: (-next(r["points_paise"] for r in rows if r["symbol"] == symbol),
                            symbol),
    ), "the companion's order is the ranking's order"
    assert sum(one["points_paise"] for one in rows) == figures["points_paise"]
    assert sum(one["trades"] for one in rows) == figures["trades"]

    table = POINTS_TABLE.read_text(encoding="utf-8")
    for one in rows:
        assert f"| {one['symbol']} |" in table, f"{one['symbol']} is ranked but not published"


def test_the_companion_carries_the_run_the_pack_was_built_from() -> None:
    """A figure is only as good as its provenance: the companion names the exact ledger."""
    payload = json.loads(COMPANION.read_text(encoding="utf-8"))
    page = PACK.read_text(encoding="utf-8")
    assert len(payload["run"]["ledger_sha256"]) == 64
    assert payload["run"]["ledger_sha256"][:16] in page, (
        "the page cites the ledger it was built from, and it is the companion's own"
    )
    assert payload["run"]["report"] in page
    figures = payload["figures"]
    assert set(figures) >= {"arithmetic", "rules", "days", "counts", "years", "drawdown",
                            "limits", "questions"}
    assert len(figures["days"]) >= 5, "five of the six slots are unconditional"


def test_the_pack_asks_the_two_things_it_exists_to_ask() -> None:
    """plan.md's chunk-12 card is a GATE: the pack that does not ask cannot close it."""
    page = PACK.read_text(encoding="utf-8")
    assert "**Confirm these are your rules, exactly.**" in page
    assert "count the rows in the box" in page
    for heading in ("## 1. The arithmetic",
                    "## 2. Your rules, written back to you",
                    "## 3. Six days you can open on your own chart",
                    "## 4. The years",
                    "## 5. What the machine did NOT do",
                    "## 6. What we need from you",
                    "## 7. Every stock, in points"):
        assert heading in page, heading
    # ...and it recommends nothing: the three paths are stated, none is preferred.
    for path in ("**Retire it.**", "**Change it.**",
                 "**Take it live knowing the arithmetic.**"):
        assert path in page, path
    assert "we recommend" not in page.lower()
    assert "you should" not in page.lower()


def test_the_arithmetic_page_reconciles_inside_the_companion() -> None:
    """Page one is three lines and they must add up, in the data as well as in the prose."""
    figures = json.loads(COMPANION.read_text(encoding="utf-8"))["figures"]["arithmetic"]
    assert (figures["gross_before_costs_paise"] - figures["costs_paise"]
            == figures["net_paise"])
    assert figures["costs_paise"] == figures["trades"] * figures["cost_per_trade_paise"]
    assert Fraction(figures["cost_share_of_risk"]) == Fraction(
        figures["cost_per_trade_paise"], figures["risk_per_trade_paise"]
    )
    assert figures["winners"] + figures["losers"] + figures["flat"] == figures["trades"]


# --- the arithmetic the pack does itself -------------------------------------------------------


def _metrics(avg_profit: Fraction | None, avg_loss: Fraction | None) -> pf.Metrics:
    """Only the two fields `_break_even_win_rate` reads -- everything else is irrelevant to it."""
    class _Stub:
        def __init__(self) -> None:
            self.avg_profit_paise = avg_profit
            self.avg_loss_paise = avg_loss

    return _Stub()  # type: ignore[return-value]


def test_the_break_even_win_rate_is_the_one_number_that_explains_the_result() -> None:
    """Hand-computed: win 2 for every 1 risked and you need one win in three to stand still.

    p * 200 + (1 - p) * (-100) == 0  ->  300p == 100  ->  p == 1/3.
    """
    assert tp._break_even_win_rate(_metrics(Fraction(200), Fraction(-100))) == Fraction(1, 3)
    # a 3R payout against a 1R loss needs one in four
    assert tp._break_even_win_rate(_metrics(Fraction(300), Fraction(-100))) == Fraction(1, 4)
    # symmetric payoffs need half of them
    assert tp._break_even_win_rate(_metrics(Fraction(100), Fraction(-100))) == Fraction(1, 2)
    # and it refuses rather than inventing one when a side of the book is empty
    assert tp._break_even_win_rate(_metrics(None, Fraction(-100))) is None
    assert tp._break_even_win_rate(_metrics(Fraction(100), None)) is None


def test_the_evidence_only_row_grid_is_the_ENGINE_grid_when_given_the_engines_own_ticks() -> None:
    """`_grid_at` exists to draw the OTHER rounding. Given the engine's own tick count it must
    reproduce `poc.build_rows` exactly, or the comparison the trader is asked to make is between
    the engine and something else."""
    for top, bottom, tick, rows in ((100_000, 90_000, 10, 24), (5_000, 4_999, 1, 24),
                                    (679_950, 670_700, 100, 24)):
        engine = poc_engine.build_rows(top, bottom, row_size=rows, tick_paise=tick)
        mine = tp._grid_at(top, bottom, ticks=engine.total_ticks, tick_paise=tick, row_size=rows)
        assert mine == engine


# --- choosing the six days ---------------------------------------------------------------------


def _census(**overrides) -> tp.Census:
    base = dict(
        last_day=date(2026, 7, 30),
        trades_by_symbol={"AAA": 100, "BBB": 10},
        risks_paise=(100, 200, 300),
        bias_rules={"rule-1-breakout": 5},
        wait_rule_days=(),
        tie_days=(),
        recent_pocs={},
        winners=(),
        gaps=(),
        stops=(),
        carries=(),
    )
    base.update(overrides)
    return tp.Census(**base)


def test_the_median_per_share_risk_is_the_middle_one_on_both_parities() -> None:
    assert _census(risks_paise=(300, 100, 200)).median_risk_paise == 200
    assert _census(risks_paise=(100, 200, 300, 500)).median_risk_paise == 250


def test_the_named_winner_is_used_when_it_qualifies_and_REPLACED_when_it_does_not() -> None:
    """The architect named a day for slot (a). A named day is a preference, never an override."""
    named_symbol, named_text = tp.NAMED_WINNER
    named_day = date.fromisoformat(named_text)

    good = _census(winners=((named_day, named_symbol), (date(2026, 7, 30), "AAA")))
    picked = tp._pick_winner(good)
    assert (picked.symbol, picked.day) == (named_symbol, named_day)
    assert picked.named and "QUALIFIES" in picked.criterion

    # the same census WITHOUT the named day: the rule has to choose, and it says so
    missing = _census(winners=((date(2026, 7, 30), "AAA"), (date(2026, 7, 30), "BBB")))
    fallback = tp._pick_winner(missing)
    assert not fallback.named
    assert (fallback.symbol, fallback.day) == ("AAA", date(2026, 7, 30)), (
        "most recent first, then the stock the run traded most often"
    )
    assert "did not qualify" in fallback.criterion

    # a named day that is a winner but is OLD is not 'recent' and is replaced too
    stale = _census(winners=((date(2016, 10, 3), named_symbol), (date(2026, 7, 30), "AAA")))
    assert tp._pick_winner(stale).day == date(2026, 7, 30)


def test_the_stop_out_chosen_is_a_TYPICAL_one_and_not_the_tail() -> None:
    """A stop-out three paise wide is real and is not representative; the rule says so."""
    census = _census(
        risks_paise=(100, 200, 300, 400, 500),          # median 300
        stops=((date(2026, 7, 30), "AAA", 3),           # the freak: most-traded, wildly off
               (date(2026, 7, 30), "BBB", 290),         # nearest the middle
               (date(2026, 7, 29), "AAA", 300)),        # exactly the middle, but older
    )
    picked = tp._pick_stop(census)
    assert (picked.symbol, picked.day) == ("BBB", date(2026, 7, 30))
    assert "TYPICAL" in picked.criterion


def test_the_wait_rule_day_is_the_most_recent_one_that_went_on_to_TRADE() -> None:
    """A walk that stops at 'no trade' cannot show the rest of the rule, so a trade breaks ties."""
    census = _census(wait_rule_days=(
        (date(2026, 7, 20), "AAA", "entered", True),
        (date(2026, 7, 29), "AAA", "no-trade-never-armed", False),
        (date(2026, 7, 29), "BBB", "entered", True),
    ))
    picked = tp._pick_wait(census)
    assert picked is not None
    assert (picked.symbol, picked.day) == ("BBB", date(2026, 7, 29))
    # ...and when the rule never fired in ten years, the slot is simply absent
    assert tp._pick_wait(_census()) is None


def test_the_rounding_day_is_the_one_a_row_COUNT_can_settle_most_cleanly() -> None:
    """Widest row-count gap first, then a moving POC, then a day that actually traded."""
    def candidate(day: date, symbol: str, rows_even: int, rows_up: int, poc_up: int,
                  executed: bool) -> tp.RoundingCandidate:
        return tp.RoundingCandidate(
            symbol=symbol, day=day, tick_paise=10, top_paise=100_000, bottom_paise=90_000,
            ticks_half_even=100, ticks_half_up=101, rows_half_even=rows_even,
            rows_half_up=rows_up, tpr_half_even=4, tpr_half_up=5,
            poc_half_even=Fraction(95_000), poc_half_up=Fraction(poc_up), executed=executed,
            window_volume=1,
        )

    narrow = candidate(date(2026, 7, 1), "AAA", 26, 25, 95_005, True)
    wide_flat = candidate(date(2026, 6, 1), "BBB", 26, 22, 95_000, True)
    wide_moving = candidate(date(2026, 5, 1), "CCC", 26, 22, 95_005, False)
    assert tp.pick_rounding_day((narrow, wide_flat, wide_moving)).symbol == "CCC", (
        "four rows apart beats one, and a moving POC beats a still one"
    )
    assert tp.pick_rounding_day((narrow,)).symbol == "AAA"
    assert tp.pick_rounding_day(()) is None


def test_a_day_with_no_rounding_disagreement_is_never_offered_as_one() -> None:
    """`separation` is what the trader is asked to count; zero of it is not a question."""
    same = tp.RoundingCandidate(
        symbol="AAA", day=date(2026, 7, 1), tick_paise=10, top_paise=100_000,
        bottom_paise=90_000, ticks_half_even=100, ticks_half_up=101, rows_half_even=25,
        rows_half_up=25, tpr_half_even=4, tpr_half_up=4, poc_half_even=Fraction(95_000),
        poc_half_up=Fraction(95_000), executed=True, window_volume=1,
    )
    assert same.separation == 0 and not same.poc_moves


def test_the_gap_criterion_STATES_what_it_checked_and_names_the_other_stocks() -> None:
    """REVIEW_12 finding Q1, closed: the named branch printed a superlative the ledger does not
    support ("the LAST gap entry of the whole ten years") and nothing tested it.

    It now says only what the census can show -- that the day is the last DAY any stock gapped
    in -- and it counts and NAMES the others that gapped in beside it, with their entry times.
    """
    symbol, day_text = tp.NAMED_GAP
    named_day = date.fromisoformat(day_text)
    census = _census(
        gaps=((named_day, symbol), (named_day, "OTHER")),
        gap_clocks={(named_day, symbol): "12:30", (named_day, "OTHER"): "12:45"},
    )
    picked = tp._pick_gap(census)
    assert (picked.symbol, picked.day) == (symbol, named_day) and picked.named
    assert "LAST gap entry of the whole ten years" not in picked.criterion
    assert "LAST DAY of the ten years that any stock gapped in" in picked.criterion
    assert "2 stocks gapped in on it" in picked.criterion
    assert "OTHER at 12:45" in picked.criterion and "this one at 12:30" in picked.criterion

    # ...and a day that is NOT the last gap-entry day does not claim to be one
    later = _census(
        gaps=((named_day, symbol), (date(2026, 7, 30), "ZZZ")),
        gap_clocks={(named_day, symbol): "12:30", (date(2026, 7, 30), "ZZZ"): "10:00"},
    )
    other = tp._pick_gap(later)
    assert (other.symbol, other.day) == (symbol, named_day)
    assert "LAST DAY" not in other.criterion
    assert "the day the ledger records for it" in other.criterion


def test_the_rounding_criterion_STATES_the_key_that_broke_the_tie() -> None:
    """REVIEW_12 finding Q14, closed: two days tied on both stated keys and the key that really
    chose between them (the day TRADED) was in a docstring and on no page."""
    def candidate(day: date, symbol: str, executed: bool) -> tp.RoundingCandidate:
        return tp.RoundingCandidate(
            symbol=symbol, day=day, tick_paise=10, top_paise=92_535, bottom_paise=91_230,
            ticks_half_even=130, ticks_half_up=131, rows_half_even=26, rows_half_up=22,
            tpr_half_even=5, tpr_half_up=6, poc_half_even=Fraction(91_855),
            poc_half_up=Fraction(91_860), executed=executed, window_volume=1,
        )

    tied = (candidate(date(2026, 3, 11), "ZYDUSLIFE", executed=False),
            candidate(date(2026, 4, 10), "BAJFINANCE", executed=True))
    probe = tp.pick_rounding_day(tied)
    assert probe.symbol == "BAJFINANCE"
    words = tp._rounding_rivals(tied, probe)
    assert "2 days tie on both of those" in words
    assert "ZYDUSLIFE on Wednesday 11 March 2026" in words
    assert "it also TOOK A TRADE" in words
    # a genuinely unique day says so instead of inventing a rival
    assert tp._rounding_rivals((tied[1],), tied[1]) == ", and it is the only such day"


def test_the_first_break_helper_is_the_ENGINES_predicate_and_adds_the_stamp() -> None:
    """REVIEW_12 finding Q6: the Rule-3 walk asserted which side broke first without printing
    the observable. The page's helper must decide exactly as `acumen.bias` does, or it prints a
    number that belongs to a different rule."""
    from datetime import datetime

    from acumen import bias as bias_engine
    from acumen.aggregate import Bar

    previous = bias_engine.Candle(open=73_800, high=74_150, low=73_450, close=73_865)

    def minute(at: int, high: int, low: int) -> Bar:
        return Bar(stamp=datetime(2026, 6, 9, 9, at), open_paise=high, high_paise=high,
                   low_paise=low, close_paise=low, volume=1)

    #: 09:15 breaks the HIGH (74,190 > 74,150); the low never breaks before it.
    bars = (minute(15, 74_190, 73_900), minute(16, 74_000, 73_400))
    stamp, level, side = tp.first_break(bars, previous)
    assert (stamp.hour, stamp.minute) == (9, 15) and level == 74_190
    assert side == tp.HIGH_FIRST
    engine = bias_engine._first_break(
        [bias_engine.Candle(open=bar.open_paise, high=bar.high_paise, low=bar.low_paise,
                            close=bar.close_paise) for bar in bars],
        previous.high, previous.low,
    )
    assert engine is not None and engine[0] == bias_engine._HIGH_FIRST

    # the low first, and the same-minute tie, both agree with the engine too
    low_first = (minute(15, 74_000, 73_400), minute(16, 74_190, 73_300))
    assert tp.first_break(low_first, previous)[2] == tp.LOW_FIRST
    both = (minute(15, 74_190, 73_400),)
    assert tp.first_break(both, previous)[2] == tp.BOTH_AT_ONCE
    assert tp.first_break((minute(15, 74_000, 73_500),), previous) is None


# --- the plain-English layer --------------------------------------------------------------------


def test_the_dates_are_written_the_way_a_person_reads_them() -> None:
    assert tp._long_date(date(2026, 6, 10)) == "Wednesday 10 June 2026"
    assert tp._long_date(date(2016, 10, 3)) == "Monday 3 October 2016"


def test_a_half_paise_POC_is_printed_as_a_half_paise_and_not_rounded_away() -> None:
    """CONTEXT 3.3 lets a row midpoint sit on half a paisa. Rounding it on a page whose purpose
    is chart-checking would hand the trader a number his chart cannot show."""
    emit = tp._Emit()
    assert emit.poc(Fraction(183_711, 2)) == "Rs 918.555"
    assert emit.poc(Fraction(91_855)) == "Rs 918.55"
    assert {token["text"] for token in emit.money} == {"Rs 918.555", "Rs 918.55"}


def test_every_figure_that_leaves_the_emitter_is_recorded_exactly_once() -> None:
    emit = tp._Emit()
    emit.rs(100_000)
    emit.rs(100_000)
    emit.n(24)
    emit.pct(Fraction(1, 10))
    emit.ratio(Fraction(1000, 3))
    assert emit.money == [{"value": "100000", "text": "Rs 1,000.00"}]
    assert emit.count == [{"value": "24", "text": "24"}]
    assert {token["text"] for token in emit.percent} == {"10.00%", "333.3333"}


@pytest.mark.parametrize("rule,expected", [
    ("rule-1-breakout", "Rule 1"),
    ("rule-2-sweep", "Rule 2"),
    ("rule-3-outside-bar", "Rule 3"),
    ("inside-bar-carry", "Inside bar"),
])
def test_the_rules_are_named_in_the_traders_own_vocabulary(rule: str, expected: str) -> None:
    assert tp._rule_words(rule).startswith(expected)
    assert tp._rule_words("something-new") == "something-new", "an unknown rule is not dressed up"


# --- REVIEW_12_2 findings Q1, Q2 and the architect's page-6 addition ------------------------------


def test_the_NOT_JUDGED_rules_and_the_printed_labels_are_ONE_thing() -> None:
    """REVIEW_12_2 findings Q1 and Q2, locked together.

    Page 5's reconciliation splits the rule table on :data:`tp.NOT_JUDGED_RULES` while its
    sentence tells the trader to look at "the rows above that say *not judged*". Those are the
    same rows only for as long as the constant and the labels agree, and nothing else in the
    module makes them agree -- so it is asserted in BOTH directions. A rule added to the
    constant without its label, or a label whose wording drifts, turns this red.
    """
    labelled = {rule for rule, words in tp._RULE_WORDS.items()
                if tp.NOT_JUDGED_WORDS in words}
    assert labelled == set(tp.NOT_JUDGED_RULES), (
        "every not-judged rule says so on the page, and no other rule does"
    )
    assert len(tp.NOT_JUDGED_RULES) == 3, "page 5's sentence says 'three of the rows above'"


def test_the_no_data_row_names_the_DAILY_candle_and_the_bias_pair() -> None:
    """REVIEW_12_2 finding Q2. `bias_engine` emits this rule when `store.daily(...)` has no
    candle for D-1 or D-2 -- the DAILY store, on the bias PAIR days. The page called it "no
    stored one-minute data for the stock that day", which is the wrong store, the wrong
    resolution and the wrong day, on the SECOND-LARGEST row the trader reads.
    """
    words = tp._rule_words("no-data")
    assert "DAILY" in words and "bias pair" in words
    assert "one-minute" not in words and "that day" not in words
    assert words.endswith(tp.NOT_JUDGED_WORDS)


def _questions_page(counted: tp.Census) -> str:
    """Page 6 alone, rendered over a synthetic census -- no store, no ledger."""
    emit = tp._Emit()
    run = r9.RunData(
        manifest={"capital_flags": {"note": "flags RETIRED"},
                  "disclosures": ["Q44 stamp PENDING"]},
        executed=(), days=(), walked=1, usable=1, refused=0, outcomes={}, reasons={},
        exit_kinds={}, rare_shapes={}, flags={}, duplicate_keys=0, symbols=(), totals={},
        witnesses=None, ledger_sha256="", ledger_bytes=0, manifest_sha256="",
    )
    tp._page_questions(emit, {}, run=run, walks=(), probe=None, counted=counted)
    return "\n".join(emit.lines)


def test_page_6_reports_the_gap_stop_check_and_has_a_LOSING_branch() -> None:
    """The architect's 07-Aug-2026 addition: the trader's Round-4 stop constraint, checked
    against every gap trade the run took rather than against the two worked examples.

    The sentence is the measurement, so it must be able to say the bad news. Both branches are
    driven here, because a verdict with only one reachable outcome asserts nothing -- and on
    this run the count really is zero, which is exactly when an unreachable branch goes unnoticed.
    """
    clean = _census(gaps=((date(2026, 7, 27), "AAA"), (date(2026, 7, 28), "BBB")),
                    gap_longs=1, gap_shorts=1, gap_stop_violations=0)
    text = _questions_page(clean)
    assert "2 of them, 1 long and 1 short" in text
    assert "the stop sat on the correct side of the POC in every single one." in text
    assert "WRONG side" not in text

    broken = _census(gaps=((date(2026, 7, 27), "AAA"), (date(2026, 7, 28), "BBB")),
                     gap_longs=1, gap_shorts=1, gap_stop_violations=1)
    loud = _questions_page(broken)
    assert "on 1 of them the stop sat on the WRONG side of the POC" in loud
    assert "That is a defect and it is printed here" in loud
    assert "in every single one" not in loud


def test_the_page_5_overlap_clause_MEASURES_what_it_claims() -> None:
    """REVIEW_12_2 finding Q1's honest half. The three-way split closes only because the days
    that were judged INSIDE a not-judged row are counted in two of its buckets, so the clause
    that explains it is load-bearing -- and every specific in it (one stock or several, whether
    any of them traded) is data, not a remembered fact about this particular run.

    Driven at all four combinations, because on the real run the answer happens to be the
    flattering one -- one stock, nothing traded -- and a sentence that can only say that is a
    sentence that would go on saying it after the data changed.
    """
    def clause(rows) -> str:
        emit = tp._Emit()
        tp._render_bias_overlap_clause(emit, rows, then_refused=100)
        return "\n".join(emit.lines)

    one_stock_quiet = clause(((date(2024, 2, 14), "FORCEMOT", "no-trade", False),
                              (date(2024, 2, 15), "FORCEMOT", "no-trade", False)))
    assert "overlap by 2 days" in one_stock_quiet
    assert "all of them FORCEMOT, at the edge of a long hole" in one_stock_quiet
    assert "none of them ended up taking a trade" in one_stock_quiet
    # REVIEW_12C finding Q2: the two dates name the two OVERLAP DAYS and must not be readable as
    # the hole's span. They sit against "on 2 days", joined by "and" -- not inside a parenthesis
    # trailing "a long hole in that one stock's daily history", and not joined by "to".
    assert ("on 2 days -- Wednesday 14 February 2024 and Thursday 15 February 2024 -- all of "
            "them FORCEMOT") in one_stock_quiet
    assert "2024 to Thursday 15 February 2024" not in one_stock_quiet
    assert "reads 100 where the number of days that settled a bias and were then refused is 102"\
        in one_stock_quiet

    many_stocks_busy = clause(((date(2024, 2, 14), "FORCEMOT", "target-hit", True),
                               (date(2025, 1, 2), "AAA", "no-trade", False),
                               (date(2025, 1, 3), "BBB", "stop-hit", True)))
    assert "overlap by 3 days" in many_stocks_busy
    assert "across 3 stocks" in many_stocks_busy and "all of them" not in many_stocks_busy
    assert "2 of them took a trade" in many_stocks_busy
    # three or more days ARE a span, so they keep "to" -- the Q2 fix is the two-day form only
    assert ("on 3 days -- Wednesday 14 February 2024 to Friday 3 January 2025 -- across 3 "
            "stocks") in many_stocks_busy


# --- REVIEW_12_2 finding C4: a generator that cannot be run is a generator that will not be ------


REPORT_MODULE = REPO_ROOT / "src" / "acumen" / "report_9b.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_both_document_generators_can_actually_be_INVOKED() -> None:
    """REVIEW_12_2 finding C4. Both modules define `main(argv)` with a full argparse CLI, and
    neither had a `__main__` guard or a `[project.scripts]` entry -- so
    `python -m acumen.trader_pack --out ... --json ... --points ...` parsed nothing, wrote
    nothing and **exited 0**. For the two documents a human decision rests on, a silent
    successful-looking no-op is the worst available failure mode.

    Asserted at the source rather than by launching a subprocess: a real invocation reads the
    ledger and the stores and takes many minutes, which is exactly why nobody noticed.
    """
    scripts = PYPROJECT.read_text(encoding="utf-8").split("[project.scripts]", 1)[1]
    for module, entry in ((MODULE, "acumen.trader_pack:main"),
                          (REPORT_MODULE, "acumen.report_9b:main")):
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source)
        guards = [node for node in tree.body
                  if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "__name__ == '__main__'"]
        assert len(guards) == 1, f"{module.name} has no __main__ guard"
        assert "SystemExit(main())" in ast.unparse(guards[0]), (
            f"{module.name}'s guard must PROPAGATE main's exit code, not swallow it"
        )
        assert entry in scripts, f"{module.name} is not on [project.scripts]"


def test_a_generator_that_wrote_nothing_CANNOT_report_success() -> None:
    """The other half of C4: the exit code must not be able to say "written" of a file that is
    missing or short. `confirm_written` reads the file back and compares its size in BYTES --
    not characters, because a non-ASCII page would otherwise pass a short write.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "document.md"
        with pytest.raises(r9.WriteError, match="was not written"):
            r9.confirm_written(path, "anything at all")

        path.write_text("the whole document\n", encoding="utf-8", newline="\n")
        r9.confirm_written(path, "the whole document\n")  # the good case is silent

        with pytest.raises(r9.WriteError, match="bytes on disk against"):
            r9.confirm_written(path, "the whole document, and then some more of it\n")


# --- REVIEW_12C findings C1 and C2: the guard's OWN account of itself, and the operator's exit --


def test_the_two_main_guards_do_not_claim_a_subprocess_test_that_does_not_exist() -> None:
    """REVIEW_12C finding C1.

    Both guards read ``# pragma: no cover -- exercised as a subprocess in the tests`` and **no
    test launches either module as a subprocess** -- the C4 test above says so in its own
    docstring (*"Asserted at the source rather than by launching a subprocess"*). The guard
    genuinely works; only its comment was wrong, and it was wrong in the one direction this
    repo's recording discipline exists to prevent: a future reader's only account of how the
    guard is verified described a verification that was deliberately not written.

    This test is the account, made executable. It asserts the comment matches reality in BOTH
    directions: no guard may claim a subprocess, and if a session ever writes one it must move
    this test rather than quietly re-add the sentence.
    """
    here = Path(__file__).resolve()  # this file names both, to say they are NOT launched
    launched = 0
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        if path.resolve() == here:
            continue
        text = path.read_text(encoding="utf-8")
        if "subprocess" in text and ("acumen.trader_pack" in text or "acumen.report_9b" in text):
            launched += 1
    assert launched == 0, (
        "a test now launches one of the two generators as a subprocess -- update the guards' "
        "pragma comments to say so, and retire this test"
    )
    for module in (MODULE, REPORT_MODULE):
        line = next(
            row for row in module.read_text(encoding="utf-8").splitlines()
            if row.startswith("if __name__ ==")
        )
        assert "subprocess" not in line, (
            f"{module.name}'s guard claims a subprocess verification that no test performs"
        )
        assert "ASSERTED AT THE SOURCE" in line, (
            f"{module.name}'s guard must say HOW it is verified; the AST test above is the how"
        )


def test_a_missing_ledger_reaches_the_operator_as_ONE_LINE_and_exit_1() -> None:
    """REVIEW_12C finding C2.

    A mistyped ``--run`` label is an OPERATOR error, and it is the only failure mode either
    generator has that is always the command rather than the code. ``run_backtest.main`` -- the
    model these two joined on ``[project.scripts]`` -- prints its preflight and returns 1. Before
    this fix the two document generators raised :class:`acumen.backtest.BacktestError` all the
    way out, so the operator who typed the command got a traceback where the third runnable
    module gives an answer.

    Driven through ``main`` itself with a run label that cannot exist, so it is the OPERATOR's
    experience that is pinned and not a helper's return value.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        for module, argv, word in (
            (tp, ["--run", "no_such_run_12c", "--out", str(base / "p.md"),
                  "--json", str(base / "p.json"), "--points", str(base / "t.md")], "pack"),
            (r9, ["--run", "no_such_run_12c", "--out", str(base / "r.md")], "report"),
        ):
            printed: list[str] = []
            code = module.main([*argv, "--config", str(REPO_ROOT / "config.yaml")])
            assert code == 1, f"{module.__name__} must return 1, not raise, on a missing ledger"
            del printed, word
        # and nothing was written -- an exit code of 1 beside a half-written document would be
        # the C4 defect wearing the other sign
        assert not any(base.iterdir()), "a refused run must leave no document behind"
