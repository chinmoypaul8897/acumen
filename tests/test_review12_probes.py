"""REVIEW_12 reviewer probes -- the chunk-12 validation pack.

Six probes the builder did not write, kept in the repo per `personas/quant_reviewer.md` step 4
and `personas/code_reviewer.md` step 4. One PROVES a claim the pack makes to the trader; the
other five PINNED a finding, written to turn red the moment the finding was fixed.

**FIVE OF THEM ARE NOW FLIPPED (06-Aug-2026).** The architect ordered REVIEW_12's sentence fixes
in the Round-4 execution session, so each of those five probes was run FIRST against the pre-fix
source and was RED there, and now asserts the CORRECTED property in both directions -- the
repo's established discipline (REVIEW_9A/9B probes that pinned a defect and were later flipped).
A flipped probe is not a weakened one: every original assertion about what the code DOES is
kept, and what changed is the claim about what the page SAYS.

**How red they were, exactly** (REVIEW_12_2 finding C5, which measured it against
``git archive 15a72b6``). All five FAIL on the pre-fix source, and the session that flipped them
said each "FAILED on its own assertion". That is true of TWO of them -- the ones whose
page-text assertion is what the interpreter reaches first. The other three die EARLIER, before
their page-text assertion runs: one on ``AttributeError`` for a helper the fix introduced
(``trader_pack._rounding_rivals``) and two on ``KeyError`` for companion fields the fix added
(``bias_rules_total``, ``delivered_win_rate_over_decided_trades``). All five do carry page-text
assertions, so the discipline holds in substance; the claim's wording overreached, and this note
is the correction rather than a re-run of the proof. Recorded because the whole point of
red-then-green is that the ASSERTION discriminates, not merely that the test was not green.

**A sixth is flipped on 07-Aug-2026** by the REVIEW_12_2 fix session:
``test_the_bias_rule_tables_population_is_now_STATED_and_reconciles`` pinned the very sentence
REVIEW_12_2 finding Q1 found to be wrong, so leaving it as written would have held the error in
place. It now asserts the CORRECTED three-way reconciliation, in both directions.

Offline: the artefact probes read committed files in the repository and no store.
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


def test_the_gap_days_provenance_sentence_is_now_CHECKED_against_the_census() -> None:
    """REVIEW_12 finding Q1 -- FLIPPED 06-Aug-2026, and RED on the pre-fix source.

    It pinned the defect: `_pick_gap`'s named branch printed *"the LAST gap entry of the whole
    ten years"* while its qualification test was only membership (`(day, symbol) in
    census.gaps`), so a named day that was a gap entry but NOT the last one got the sentence
    anyway. The fix makes the sentence state only what the census can show. This now asserts the
    corrected property in BOTH directions:

    * a named day that is NOT on the last gap-entry day claims no superlative at all;
    * a named day that IS on it says so about the DAY, and counts and names the other stocks
      that gapped in beside it, with their entry times.
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
    assert "the LAST gap entry of the whole ten years" not in picked.criterion, (
        "the unchecked superlative is gone"
    )
    assert "LAST DAY" not in picked.criterion, (
        "and it does not claim the day either, because a later gap entry exists in this census"
    )

    # the shipped shape: the named day IS the last gap-entry day, and it is not alone on it
    shared = tp.Census(
        last_day=named_day, trades_by_symbol={symbol: 10, "INDUSINDBK": 99}, risks_paise=(100,),
        bias_rules={}, wait_rule_days=(), tie_days=(), recent_pocs=(),
        winners=(), gaps=((named_day, symbol), (named_day, "INDUSINDBK")), stops=(), carries=(),
        gap_clocks={(named_day, symbol): "12:30", (named_day, "INDUSINDBK"): "12:45"},
    )
    words = tp._pick_gap(shared).criterion
    assert "LAST DAY of the ten years that any stock gapped in" in words
    assert "2 stocks gapped in on it" in words and "INDUSINDBK at 12:45" in words
    assert "not a last of anything" in words


# --- 3. PINS a finding: a tie-break the page never states ------------------------------------------


def test_the_selection_rules_state_the_SYMBOL_NAME_last_resort_they_really_use() -> None:
    """REVIEW_12 finding Q3 -- FLIPPED 06-Aug-2026, and RED on the pre-fix source.

    It pinned the defect: every criterion beside a day named at most one tie-break (*"Ties go to
    the stock this run traded most often"*), while the real last resort is the SYMBOL NAME --
    which runs in OPPOSITE directions in `min` and `max` and appeared on no page. The behaviour
    is unchanged and is still asserted below; what is fixed is that each criterion now says so,
    and says which way round it goes.
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
    assert "first stock alphabetically" in picked.criterion, (
        "the deciding rule on a full tie is the symbol name, and the page now says so"
    )
    # the same last resort decides the carry day and the wait-rule day -- the other way round,
    # and each of those criteria now says THAT
    carry = tp._pick_carry(tp.Census(
        last_day=date(2026, 7, 30), trades_by_symbol={"AAA": 7, "ZZZ": 7}, risks_paise=(1,),
        bias_rules={}, wait_rule_days=(), tie_days=(), recent_pocs={}, winners=(), gaps=(),
        stops=(), carries=((date(2026, 7, 30), "AAA", "x"), (date(2026, 7, 30), "ZZZ", "x")),
    ))
    assert carry.symbol == "ZZZ", "here the last resort runs the other way -- `max`, not `min`"
    assert "then to the last one alphabetically" in carry.criterion
    wait = tp._pick_wait(tp.Census(
        last_day=date(2026, 7, 30), trades_by_symbol={"AAA": 7, "ZZZ": 7}, risks_paise=(1,),
        bias_rules={}, wait_rule_days=((date(2026, 7, 30), "AAA", "entered", True),
                                       (date(2026, 7, 30), "ZZZ", "entered", True)),
        tie_days=(), recent_pocs={}, winners=(), gaps=(), stops=(), carries=(),
    ))
    assert wait.symbol == "ZZZ" and "then the last one alphabetically" in wait.criterion


# --- 3b. PINS a finding: the rounding day's uniqueness claim, and the key that really decided it ---


def test_the_rounding_days_tie_and_the_key_that_breaks_it_are_both_STATED() -> None:
    """REVIEW_12 finding Q14 -- FLIPPED 06-Aug-2026, and RED on the pre-fix source.

    It pinned the defect: page 3f called its day *"the one with the widest gap between the two
    row counts"* twice, a definite description that is not unique on this run -- the recount
    finds TWO candidates at the maximum separation of 4 rows, both with a moving POC (ZYDUSLIFE
    2026-03-11 and BAJFINANCE 2026-04-10) -- and the key that really separated them (`executed`:
    ZYDUSLIFE took no trade) lived only in a docstring. The ordering is unchanged and is still
    asserted below; what is fixed is that the criterion now COUNTS the tie, NAMES the rival and
    states the key.
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
        "the deciding key is whether the day traded"
    )

    # THE FIX: the criterion no longer claims uniqueness, and it names both the rival and the key
    words = tp._rounding_rivals((no_trade, traded), traded)
    assert "2 days tie on both of those" in words
    assert "ZYDUSLIFE" in words and "it also TOOK A TRADE" in words
    page = PACK.read_text(encoding="utf-8")
    assert "this is the one with the widest gap between the two row counts" not in page
    assert "the one where the two row counts are furthest apart" not in page


# --- 4. PINS a finding: the bias-rule table's population is unstated --------------------------------


def test_the_bias_rule_tables_population_is_now_STATED_and_reconciles() -> None:
    """REVIEW_12 finding Q2 -- FLIPPED 06-Aug-2026, then RE-FLIPPED 07-Aug-2026.

    It pinned the defect: the table was headed *"Which of your bias rules decided the days the
    machine judged"* while its rows summed to neither of the two counts page 5 prints, and no
    total was printed, so a reader had nothing to check. The counts are unchanged -- and they
    still do not equal either figure, which is the point -- but the page now prints the sum and
    reconciles it, so the arithmetic is the reader's to verify.

    **RE-FLIPPED for REVIEW_12_2 finding Q1.** The 06-Aug version of this probe asserted the
    reconciling sentence VERBATIM -- *"N more had a bias but were refused afterwards"* -- and
    that sentence was wrong: it presented `ruled - usable` as a population standing BESIDE the
    three *not judged* rows when in fact it CONTAINS them, so a reader following the paragraph
    literally subtracted those rows twice and missed the stated answer by their whole size. The
    probe checked that a figure was printed and nothing about whether the arithmetic closed, so
    it would have held the error in place. It now asserts the three-way split that does close,
    in both directions: the wrong sentence must be GONE, and the sum must be exact.
    """
    figures = _companion()["figures"]
    counts = figures["counts"]
    rules = counts["bias_rules"]
    limits = figures["limits"]
    total = sum(rules.values())

    assert counts["bias_rules_total"] == total
    assert total != limits["usable"] and total != limits["walked"], (
        "the table's population is genuinely neither, which is why it has to be stated"
    )
    assert counts["bias_rules_walked_without_a_rule"] == limits["walked"] - total > 0
    assert counts["bias_rules_ruled_then_refused"] == total - limits["usable"] > 0

    # THE PAGE FIRST -- what the trader actually receives, and the assertion that has to be the
    # one discriminating (REVIEW_12_2 finding C5: a probe that dies on a KeyError for a field
    # the fix added has not tested the fix).
    page = PACK.read_text(encoding="utf-8")
    assert "Which of your bias rules decided the days the machine judged" not in page, (
        "the heading no longer claims a population the table is not"
    )
    assert "What the machine found on each stock-day it looked at" in page
    assert f"Those rows add up to {total:,}" in page, "the total is printed for the reader"
    assert f"{limits['walked'] - total:,} of them carry no rule at all" in page
    assert f"{total - limits['usable']:,} more had a bias but were refused afterwards" not in page, (
        "the sentence REVIEW_12_2 Q1 found to be wrong is GONE from the trader's page"
    )
    assert "not judged" in page, "three rows are explicitly outside the judged population"

    # the three-way split, and it CLOSES -- the property the old assertion never checked
    not_judged = counts["bias_rules_not_judged"]
    then_refused = counts["bias_rules_then_refused"]
    assert sum(counts["bias_rules_not_judged_rows"].values()) == not_judged > 0
    assert limits["usable"] + not_judged + then_refused == total, (
        "the reconciliation the trader is invited to check has to add up"
    )
    assert (f"{limits['usable']:,} + {not_judged:,} + {then_refused:,} = {total:,}") in page, (
        "and the split that does close is printed, so the reader can add it up"
    )


# --- 5. PINS a finding: page 1 compares two rates over different denominators -----------------------


def test_page_ones_two_win_rates_are_now_ONE_denominator_with_the_flats_stated() -> None:
    """REVIEW_12 finding Q5 -- FLIPPED 06-Aug-2026, and RED on the pre-fix source.

    It pinned the defect: *"it would need to win 34.60% ... It won 31.53% of them"* compared a
    break-even rate taken over the trades that made or lost money with a delivered rate taken
    over ALL of them. Both figures are unchanged and both are still printed; what is fixed is
    that the comparison is now made on ONE denominator, the flat trades are counted out loud,
    and the all-trades rate is stated separately as the other reading.
    """
    arithmetic = _companion()["figures"]["arithmetic"]
    winners, losers, flat = arithmetic["winners"], arithmetic["losers"], arithmetic["flat"]
    delivered = Fraction(arithmetic["delivered_win_rate"])
    matched = Fraction(arithmetic["delivered_win_rate_over_decided_trades"])
    assert flat > 0, "with no flat trades the two denominators coincide and there is nothing here"
    assert delivered == Fraction(winners, winners + losers + flat)
    assert matched == Fraction(winners, winners + losers) == Fraction(
        winners, arithmetic["decided_trades"]
    )
    assert matched != delivered, "the denominators differ by exactly the flat trades"
    assert abs(matched - delivered) < Fraction(1, 1000), (
        "and the difference is under a tenth of a percentage point on this run"
    )

    page = PACK.read_text(encoding="utf-8")
    assert f"({winners:,} of {winners + losers:,})" in page, (
        "the comparison names the population the two averages are built from"
    )
    assert f"{flat:,} trades ended exactly level and are in neither" in page
    assert f"Over all {winners + losers + flat:,} trades the win rate is" in page
