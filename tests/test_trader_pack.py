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
from acumen import portfolio as pf
from acumen import trader_pack as tp
from acumen.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "src" / "acumen" / "trader_pack.py"
PACK = REPO_ROOT / "docs" / "validation" / "trader_pack.md"
COMPANION = REPO_ROOT / "docs" / "validation" / "trader_pack.json"

#: A rupee amount as it is printed: ``Rs 1,234.56``, or a POC's honest ``Rs 918.555``.
MONEY = re.compile(r"-?Rs [0-9][0-9,]*\.[0-9]{2,3}")
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
    source = MODULE.read_text(encoding="utf-8")
    quoted = " || ".join(quote for _tag, quote, _fixes in tp.TRADER_WORDS)

    assert not re.search(r"Rs\s*-?[0-9]", source), (
        "a rupee amount typed into the generator, instead of formatted from a value"
    )

    for text in _string_constants(source):
        if QUANTUM.match(text):
            continue
        for pattern, what in ((PAISA_TEXT, "a paisa-shaped decimal"),
                              (GROUPED_TEXT, "a grouped digit run")):
            for hit in pattern.findall(text):
                assert hit in quoted, f"{what} typed into the pack's prose: {hit!r} in {text!r}"

    config = load_config(include_env=False)
    forbidden = {
        config.require_risk_per_trade_paise(),
        int(config.risk_per_trade),
        config.cost_per_trade_paise(),
        config.initial_capital_paise(),
        int(config.initial_capital),
    }
    literals = {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    }
    assert not (literals & forbidden), (
        f"CONTEXT 3.5 money magnitudes hardcoded in the pack generator: "
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
                    "## 6. What we need from you"):
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
