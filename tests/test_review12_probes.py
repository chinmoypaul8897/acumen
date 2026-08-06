"""REVIEW_12 reviewer probes -- the chunk-12 validation pack.

Five probes the builder did not write, kept in the repo per `personas/quant_reviewer.md` step 4
and `personas/code_reviewer.md` step 4. Two of them PROVE a claim the pack makes to the trader;
three PIN a finding, so that the fix the architect may order turns them red rather than passing
silently (the repo's established discipline -- REVIEW_9A/9B probes that pinned a defect and were
later FLIPPED to assert the corrected property).

Offline: the artefact probes read two committed files in the repository and no store.
"""

from __future__ import annotations

import json
from datetime import date
from fractions import Fraction
from pathlib import Path

from acumen import bias as bias_engine
from acumen import trader_pack as tp

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = REPO_ROOT / "docs" / "validation" / "trader_pack.md"
COMPANION = REPO_ROOT / "docs" / "validation" / "trader_pack.json"


def _companion() -> dict:
    return json.loads(COMPANION.read_text(encoding="utf-8"))


def _candle(open_: int, high: int, low: int, close: int) -> bias_engine.Candle:
    return bias_engine.Candle(open=open_, high=high, low=low, close=close)


# --- 1. PROVES a claim the pack makes ------------------------------------------------------------


def test_the_packs_zero_bearish_ties_is_STRUCTURAL_over_a_dense_grid() -> None:
    """Page 3: "62 of them came out bullish and 0 bearish -- and that split is your own rule
    showing through, not a coincidence".

    CONTEXT 3.2 v1.3 says the bearish tie branch is unreachable, and `test_bias.py` pins that on
    ONE routed pair. The pack states the zero as a property of ten years of real days, so the
    property is proved here EXHAUSTIVELY instead: over every close on a dense grid spanning far
    below P's body to far above it, with a genuine outside bar and both extremes broken inside
    the SAME 1-minute candle, no routed pair ever produces a BEARISH tie -- and every close
    outside the body is taken by Rule 1 before the tie is reached, which is the other half of
    the pack's sentence.
    """
    previous = _candle(201_000, 205_000, 200_000, 204_000)      # body 2010.00 -- 2040.00
    body_min, body_max = 201_000, 204_000
    seen_rules: set[str] = set()
    for close in range(199_000, 206_001, 5):                    # 1,401 closes, 5 paise apart
        current = _candle(202_000, 206_000, 198_500, close)     # a real outside bar every time
        minute = _candle(202_000, 206_000, 198_500, 199_000)    # both extremes in ONE minute
        result = bias_engine.evaluate_pair(
            previous, current, lambda: [minute], last_bias=bias_engine.BEARISH,
        )
        seen_rules.add(result.rule)
        if result.rule == bias_engine.RULE_3_TIE:
            assert body_min <= close <= body_max, (
                "the tie is only ever reached for a close INSIDE the body -- outside it, "
                "Rule 1 has already decided the day"
            )
            assert result.bias == bias_engine.BULLISH, (
                f"a BEARISH tie at close {close}: the pack's 0 is then a coincidence, not a rule"
            )
        else:
            assert result.rule == bias_engine.RULE_1, result.rule
            assert not result.tie_case
    assert {bias_engine.RULE_1, bias_engine.RULE_3_TIE} <= seen_rules, (
        "the grid must actually exercise both branches or it proves nothing"
    )


# --- 2. PINS a finding: an unverified uniqueness claim on the trader's page -----------------------


def test_the_gap_days_LAST_GAP_ENTRY_claim_is_printed_without_being_checked() -> None:
    """REVIEW_12 finding Q1, pinned.

    `_pick_gap`'s named branch prints *"the LAST gap entry of the whole ten years"*, but its
    qualification test is only membership -- `(day, symbol) in census.gaps`. A named day that is
    a gap entry but NOT the last one still gets the sentence. This probe builds exactly that
    census and asserts the false sentence is produced, so that a fix (checking the claim, or
    softening it to the last gap-entry DAY) turns this red instead of passing unnoticed.

    On the shipped run the day really is on the last gap-entry DAY, but it shares that day with
    INDUSINDBK, whose entry is 15 minutes LATER -- so the printed superlative is not the
    ledger's own record even there.
    """
    symbol, day_text = tp.NAMED_GAP
    named_day = date.fromisoformat(day_text)
    later = date(2026, 7, 30)
    assert later > named_day, "the fixture needs a gap entry AFTER the named one"

    census = tp.Census(
        last_day=later, trades_by_symbol={symbol: 10, "ZZZ": 99}, risks_paise=(100,),
        bias_rules={}, wait_rule_days=(), tie_days=(), recent_pocs=(),
        winners=(), gaps=((named_day, symbol), (later, "ZZZ")), stops=(), carries=(),
    )
    picked = tp._pick_gap(census)
    assert (picked.symbol, picked.day) == (symbol, named_day) and picked.named
    assert "the LAST gap entry of the whole ten years" in picked.criterion, (
        "the claim is unconditional prose in the named branch -- nothing tests it"
    )


# --- 3. PINS a finding: a tie-break the page never states ------------------------------------------


def test_the_selection_rules_fall_back_to_the_SYMBOL_NAME_and_no_criterion_says_so() -> None:
    """REVIEW_12 finding Q3, pinned.

    Every criterion printed beside a day names at most one tie-break -- *"Ties go to the stock
    this run traded most often"*. When two candidates tie on that too, the choice is decided by
    the SYMBOL NAME (alphabetical), which appears on no page. Two stop-outs identical in every
    stated respect are separated here by nothing but their names.
    """
    census = tp.Census(
        last_day=date(2026, 7, 30), trades_by_symbol={"AAA": 500, "ZZZ": 500},
        risks_paise=(100, 200, 300), bias_rules={}, wait_rule_days=(), tie_days=(),
        recent_pocs={}, winners=(),
        gaps=(), carries=(),
        stops=((date(2026, 7, 30), "AAA", 200), (date(2026, 7, 30), "ZZZ", 200)),
    )
    picked = tp._pick_stop(census)
    assert picked.symbol == "AAA", "the alphabetically first symbol wins a fully tied pair"
    assert "traded most often" in picked.criterion
    assert "name" not in picked.criterion and "alphabet" not in picked.criterion, (
        "the deciding rule on a full tie is the symbol name, and the page does not say so"
    )
    # the same silent last resort decides the carry day and the wait-rule day
    carry = tp._pick_carry(tp.Census(
        last_day=date(2026, 7, 30), trades_by_symbol={"AAA": 7, "ZZZ": 7}, risks_paise=(1,),
        bias_rules={}, wait_rule_days=(), tie_days=(), recent_pocs={}, winners=(), gaps=(),
        stops=(), carries=((date(2026, 7, 30), "AAA", "x"), (date(2026, 7, 30), "ZZZ", "x")),
    ))
    assert carry.symbol == "ZZZ", "here the last resort runs the other way -- `max`, not `min`"


# --- 3b. PINS a finding: the rounding day's uniqueness claim, and the key that really decided it ---


def test_the_rounding_days_FURTHEST_APART_claim_is_not_unique_and_a_hidden_key_breaks_the_tie() -> None:
    """REVIEW_12 finding Q14, pinned.

    Page 3f prints *"this is the one with the widest gap between the two row counts, and on it
    the POC itself moves"* and, below the table, *"This is the one where the two row counts are
    furthest apart"* -- both definite descriptions. On the shipped run they are not unique: this
    session's independent recount of the span's last calendar year finds **two** candidates at
    the maximum separation of 4 rows, BOTH with a moving POC -- ZYDUSLIFE 2026-03-11 and
    BAJFINANCE 2026-04-10. What separated them is `executed`: ZYDUSLIFE took no trade that day.
    That key is in `pick_rounding_day`'s docstring and on no page the trader reads.

    The fixture reproduces exactly that shape. If the criterion is ever widened to state the key,
    or the ordering changed, this turns red.
    """
    def candidate(day: date, symbol: str, executed: bool) -> tp.RoundingCandidate:
        return tp.RoundingCandidate(
            symbol=symbol, day=day, tick_paise=10, top_paise=92_535, bottom_paise=91_230,
            ticks_half_even=130, ticks_half_up=131, rows_half_even=26, rows_half_up=22,
            tpr_half_even=5, tpr_half_up=6, poc_half_even=Fraction(91_855),
            poc_half_up=Fraction(91_860), executed=executed, window_volume=1,
        )

    no_trade = candidate(date(2026, 3, 11), "ZYDUSLIFE", executed=False)
    traded = candidate(date(2026, 4, 10), "BAJFINANCE", executed=True)
    assert no_trade.separation == traded.separation == 4
    assert no_trade.poc_moves and traded.poc_moves, "both stated keys are tied"
    assert tp.pick_rounding_day((no_trade, traded)).symbol == "BAJFINANCE"
    # ...and the tie really is broken by `executed`, not by the date: reverse the dates and the
    # traded day still wins.
    older_traded = candidate(date(2026, 1, 5), "BAJFINANCE", executed=True)
    newer_untraded = candidate(date(2026, 6, 30), "ZYDUSLIFE", executed=False)
    assert tp.pick_rounding_day((older_traded, newer_untraded)).symbol == "BAJFINANCE", (
        "the deciding key is whether the day traded -- which no criterion on the page states"
    )


# --- 4. PINS a finding: the bias-rule table's population is unstated --------------------------------


def test_the_bias_rule_table_sums_to_a_population_the_page_never_names() -> None:
    """REVIEW_12 finding Q2, pinned, read off the COMMITTED artefacts.

    The table is headed *"Which of your bias rules decided the days the machine judged"*, but
    its rows sum to neither of the two counts page 5 prints. Three of its own rows are labelled
    *not judged*, some rule-labelled rows were refused after the bias was computed, and the
    stock-days refused as non-standard sessions carry no rule at all and appear in no row. No
    total is printed, so none of that is visible to the reader.
    """
    figures = _companion()["figures"]
    rules = figures["counts"]["bias_rules"]
    limits = figures["limits"]
    total = sum(rules.values())

    assert total != limits["usable"], "if these ever agree, the heading has become true"
    assert total != limits["walked"], "and it is not the walk either"
    assert limits["walked"] - total > 0, (
        "walked stock-days that carry no bias rule at all and so appear in no row"
    )
    page = PACK.read_text(encoding="utf-8")
    assert "Which of your bias rules decided the days the machine judged" in page
    assert f"| {total:,} |" not in page, "the table prints no total for the reader to check"
    assert "not judged" in page, "three rows are explicitly outside the heading's own population"


# --- 5. PINS a finding: page 1 compares two rates over different denominators -----------------------


def test_page_ones_two_win_rates_are_taken_over_different_denominators() -> None:
    """REVIEW_12 finding Q5, pinned.

    *"it would need to win 34.60% of its trades just to end level. It won 31.53% of them"* -- the
    break-even rate is a fraction of the trades that made or lost money (the flat ones are in
    neither average and `_break_even_win_rate` says so), while the delivered rate is a fraction
    of ALL trades. The gap is immaterial on this run, and it is a real mismatch: pinned so that
    it stays immaterial rather than silently growing.
    """
    arithmetic = _companion()["figures"]["arithmetic"]
    winners, losers, flat = arithmetic["winners"], arithmetic["losers"], arithmetic["flat"]
    delivered = Fraction(arithmetic["delivered_win_rate"])
    assert flat > 0, "with no flat trades the two denominators coincide and there is nothing here"
    assert delivered == Fraction(winners, winners + losers + flat)
    matched = Fraction(winners, winners + losers)
    assert matched != delivered, "the denominators differ by exactly the flat trades"
    assert abs(matched - delivered) < Fraction(1, 1000), (
        "and the difference is under a tenth of a percentage point on this run"
    )
