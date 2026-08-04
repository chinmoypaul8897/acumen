"""The bias ORCHESTRATION (chunk 4): store -> pairwise adjustment -> suppression -> seeding.

Two layers of golden:

* **F9** -- 15 REAL TCS days from the settled daily store (frozen as DERIVED cuts in
  ``tests/fixtures/f9_tcs_daily.csv``), each hand-computed with candle numbers and rule
  reasoning in ``f9_tcs_expected.csv``. The engine's bias must match every hand computation.
  The store here is a temp store loaded FROM the frozen cut, so the test is hermetic.
* the orchestration mechanics -- seeding, carry, the pairwise CA adjustment, the suppression
  list (demerger + Q-6 tier-2 rights), and the Rule-3 missing-1-minute fallback -- on small
  SYNTHETIC stores.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import corp_actions as ca
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
)
from acumen.bias import BEARISH, BULLISH, Candle
from acumen.bias_engine import (
    RULE_MINUTES_MALFORMED,
    RULE_MINUTES_UNGATED,
    BiasEngine,
    BiasEngineError,
    MalformedMinuteBar,
    UngatedMinuteDay,
    UnusableMinuteEvidence,
    csv_minute_loader,
)
from acumen.calendar import TradingCalendar
from acumen.daily_store import DailyStore

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINUTE_DIR = FIXTURES / "minute"


def _paise(text: str) -> int:
    return int(Decimal(text) * 100)


def _row(day: date, o: int, h: int, l: int, c: int, symbol: str = "TCS") -> DailyRow:
    return DailyRow(
        trade_date=day, symbol=symbol, series="EQ",
        open_paise=o, high_paise=h, low_paise=l, close_paise=c,
        volume=1000, source_format=FORMAT_ARCHIVE,
    )


def _store_from_candles(root: Path, symbol: str, candles: dict[date, tuple[int, int, int, int]]) -> tuple[DailyStore, TradingCalendar]:
    """Write daily candles into a temp store, mark the ledger, and derive a calendar.

    Trading days = the candle dates; every other in-range date is confirmed-404, so the
    derived calendar answers exactly the frozen set.
    """
    store = DailyStore.at(root)
    for day, (o, h, l, c) in sorted(candles.items()):
        store.write_rows(day, [_row(day, o, h, l, c, symbol)])
    first, last = min(candles), max(candles)
    outcomes = []
    d = first
    while d <= last:
        if d in candles:
            outcomes.append(DateOutcome(d, OUTCOME_PRESENT, source_format=FORMAT_ARCHIVE,
                                        http_status=200, row_count=1))
        else:
            outcomes.append(DateOutcome(d, OUTCOME_NOT_FOUND, http_status=404))
        d += timedelta(days=1)
    store.record_outcomes(outcomes)
    calendar = TradingCalendar.from_daily_store_range(store, first, last)
    return store, calendar


# =========================================================================================
# F9 -- the real-TCS golden
# =========================================================================================


def _load_f9_daily() -> dict[date, tuple[int, int, int, int]]:
    candles: dict[date, tuple[int, int, int, int]] = {}
    with (FIXTURES / "f9_tcs_daily.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            candles[date.fromisoformat(row["trade_date"])] = (
                _paise(row["open"]), _paise(row["high"]), _paise(row["low"]), _paise(row["close"])
            )
    return candles


def _load_f9_expected() -> list[dict[str, str]]:
    with (FIXTURES / "f9_tcs_expected.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_f9_real_tcs_days_match_every_hand_computation(tmp_path) -> None:
    """The engine's bias for each frozen real TCS day equals the hand-computed golden."""
    candles = _load_f9_daily()
    store, calendar = _store_from_candles(tmp_path, "TCS", candles)
    # TCS had no split/bonus/special dividend in this window (max day-over-day gap 7%, a
    # genuine market move), so the factor list is legitimately empty -- raw == adjusted, and
    # the trader sees the same numbers on his chart.
    engine = BiasEngine(store=store, calendar=calendar, factors=(), suppressions=())

    expected = _load_f9_expected()
    first_expected = date.fromisoformat(expected[0]["trade_date"])
    last_expected = date.fromisoformat(expected[-1]["trade_date"])
    series = {b.trade_date: b for b in engine.bias_series("TCS", first_expected, last_expected)}

    for exp in expected:
        day = date.fromisoformat(exp["trade_date"])
        result = series[day]
        assert result.bias == exp["expected_bias"], f"{day}: {result.detail}"
        assert result.rule == exp["rule"], f"{day}: rule {result.rule} != {exp['rule']}"
        assert result.tradeable is True


def test_f9_covers_every_rule_the_card_requires() -> None:
    """The F9 set must demonstrate seeding, inside-bar carry, and Rule 1 / Rule 2 both sides."""
    expected = _load_f9_expected()
    rules = [e["rule"] for e in expected]
    biases = {(e["rule"], e["expected_bias"]) for e in expected}
    assert len(expected) >= 13, "the card asks for 13+ real days"
    assert rules.count("inside-bar-carry") >= 2
    assert ("rule-1-breakout", "bullish") in biases
    assert ("rule-1-breakout", "bearish") in biases
    assert ("rule-2-sweep", "bullish") in biases
    assert ("rule-2-sweep", "bearish") in biases
    assert "SEED DAY" in expected[0]["reason"]


# =========================================================================================
# orchestration mechanics
# =========================================================================================


def test_seeding_carries_none_until_a_rule_first_fires(tmp_path) -> None:
    """CONTEXT 3.2 seeding: no bias (and no trading) until a rule fires; then it seeds."""
    d = [date(2024, 1, 1) + timedelta(days=i) for i in range(5)]  # Mon..Fri
    candles = {
        d[0]: (10000, 11000, 9000, 10500),  # Mon P0
        d[1]: (10200, 10800, 9500, 10400),  # Tue inside P0
        d[2]: (10300, 10700, 9600, 10450),  # Wed inside Tue
        d[3]: (10450, 12000, 10400, 11800),  # Thu breakout of Wed (close > bodyMax)
        d[4]: (11800, 11900, 11000, 11200),  # Fri filler
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    engine = BiasEngine(store=store, calendar=calendar)
    # evaluate from the 3rd trading day so each pair resolves inside the covered range
    series = engine.bias_series("ACME", d[2], d[4])
    assert [b.bias for b in series[:2]] == [None, None]  # inside bars carry None (still seeding)
    assert [b.tradeable for b in series[:2]] == [False, False]
    assert series[2].bias == BULLISH and series[2].tradeable is True  # seeded on the breakout


def test_a_suppression_ex_date_blocks_the_pair_and_trading(tmp_path) -> None:
    """CONTEXT 3.2 / Q-6 tier 2: a day whose D-1 or D-2 is a suppression ex-date makes no bias
    update and takes no trade, and the carried bias is preserved across it."""
    base = date(2024, 3, 4)  # Monday
    days = [base + timedelta(days=i) for i in range(4)]  # Mon..Thu
    candles = {
        days[0]: (10000, 11000, 9000, 10500),
        days[1]: (10450, 12000, 10400, 11800),  # breakout -> seeds bullish on Wed's pair
        days[2]: (11800, 12500, 11700, 12100),
        days[3]: (12100, 12300, 11000, 11100),
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    # a demerger with ex-date on days[2] (Wed): it is D-1 of Thu's pair -> Thu suppressed.
    supp = (ca.Suppression("ACME", days[2], ca.KIND_DEMERGER, "demerger test"),)
    engine = BiasEngine(store=store, calendar=calendar, suppressions=supp)
    series = {b.trade_date: b for b in engine.bias_series("ACME", days[2], days[3])}

    thu = series[days[3]]
    assert thu.suppressed is True and thu.tradeable is False and thu.rule == "suppressed"
    assert thu.suppression_reason == "demerger test"
    # the bias carried across the suppression is whatever was in effect (unchanged)
    assert thu.bias == series[days[2]].bias


def test_pairwise_adjustment_brings_the_previous_candle_into_current_scale(tmp_path) -> None:
    """A split between D-2 and D-1 must halve the previous candle before comparison
    (CONTEXT 3.2 / 7-E11). Without it the raw pre-split prices would look like a huge gap."""
    base = date(2024, 5, 6)  # Monday
    days = [base + timedelta(days=i) for i in range(3)]
    # P (Mon) is on the OLD scale (~2000); a 10->? no: use a 1:1 style k=0.5 split ex Tue so
    # P's prices halve into Tue's scale. Post-split C (Tue) trades ~1000.
    candles = {
        days[0]: (200000, 205000, 199000, 204000),   # Mon, pre-split (~2000)
        days[1]: (102000, 103000, 99000, 102500),    # Tue, post-split (~1000)
        days[2]: (102500, 130000, 102400, 128000),   # Wed breakout (its pair is Tue, Mon)
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    split = ca.Factor("ACME", days[1], ca.KIND_SPLIT, Decimal("0.5"), "1:1 test split")
    engine = BiasEngine(store=store, calendar=calendar, factors=(split,))

    # Wed's pair is (Tue current, Mon previous). Mon must be halved into Tue's scale.
    result = engine.bias_for_day("ACME", days[2], seed_from=days[2])
    assert result.previous_candle is not None
    assert result.previous_candle.close == 102000, "Mon close 204000 * 0.5 = 102000 (in Tue scale)"
    assert result.previous_candle.high == 102500 and result.previous_candle.open == 100000


def test_rule3_day_without_a_minute_loader_carries(tmp_path) -> None:
    """An outside bar with no injected 1-minute loader falls back to carry (documented)."""
    d = [date(2024, 7, 1) + timedelta(days=i) for i in range(4)]  # Mon..Thu
    candles = {
        d[0]: (10000, 11000, 9000, 10500),   # Mon P0
        d[1]: (10450, 12000, 10400, 11800),  # Tue breakout of Mon (seeds bullish on Wed's pair)
        d[2]: (10600, 13000, 8000, 10450),   # Wed outside bar, close inside body (R3 on Thu)
        d[3]: (10450, 10600, 10300, 10500),  # Thu filler
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    engine = BiasEngine(store=store, calendar=calendar, minute_loader=None)
    series = {b.trade_date: b for b in engine.bias_series("ACME", d[2], d[3])}
    assert series[d[2]].bias == BULLISH  # seeded on Tue's breakout
    thu = series[d[3]]  # its pair is (Wed outside bar, Tue) -> R3, no minute data -> carry
    assert thu.rule == "rule-3-no-1min-carry" and thu.bias == BULLISH  # carried from Wed


def test_minute_loader_interface_drives_a_synthetic_rule3_through_the_engine(tmp_path) -> None:
    """The (symbol, date) MinuteLoader interface, exercised via csv_minute_loader on the frozen
    synthetic fixture SYNTH_2099-01-05 -- the shape chunk 5A's real loader will satisfy.

    The outside bar is candle(2099-01-05); the bias computed is for 2099-01-06, whose pair is
    (2099-01-05 current, 2099-01-02 previous), so Rule 3 reads 2099-01-05's minutes."""
    candles = {
        date(2099, 1, 2): (R(2010), R(2050), R(2000), R(2040)),  # Fri  P (D-2)
        date(2099, 1, 5): (R(2005), R(2060), R(1990), R(2020)),  # Mon  C outside bar (D-1)
        date(2099, 1, 6): (R(2020), R(2030), R(2010), R(2025)),  # Tue  D (the day we score)
    }
    store, calendar = _store_from_candles(tmp_path, "SYNTH", candles)
    loader = csv_minute_loader(MINUTE_DIR)  # SYNTH_2099-01-05_1min.csv breaks P.high first
    engine = BiasEngine(store=store, calendar=calendar, minute_loader=loader)
    result = engine.bias_for_day("SYNTH", date(2099, 1, 6), seed_from=date(2099, 1, 6))
    assert result.rule == "rule-3-outside-bar" and result.bias == BULLISH


def R(rupees: float) -> int:
    return int(round(rupees * 100))


# ==============================================================================================
# QUESTIONS.md Q-21: a Rule-3 scan that meets a vendor-corrupt 1-minute bar
# ==============================================================================================


def _malformed_loader(day: date, *, symbol: str = "ACME"):
    """A MinuteLoader that refuses exactly the way the RUN's loader refuses (Q-21)."""

    def load(sym: str, when: date):
        if when == day:
            raise MalformedMinuteBar(
                symbol=sym,
                day=when,
                stamp=datetime(when.year, when.month, when.day, 9, 15),
                open_paise=44210,
                high_paise=44440,
                low_paise=44295,
                close_paise=44295,
                volume=12909,
            )
        return None

    return load


def _q21_world(tmp_path) -> tuple[list[date], DailyStore, TradingCalendar]:
    """Mon..Thu, where Wed is an outside bar -> Thursday's pair is Rule 3 and reads Wed's
    minutes. The same shape the missing-1-minute carry test uses, so the ONLY difference
    between the two is what the loader does."""
    d = [date(2024, 7, 1) + timedelta(days=i) for i in range(4)]
    candles = {
        d[0]: (10000, 11000, 9000, 10500),
        d[1]: (10450, 12000, 10400, 11800),  # seeds BULLISH on Wednesday's pair
        d[2]: (10600, 13000, 8000, 10450),   # outside bar -> Rule 3 on Thursday
        d[3]: (10450, 10600, 10300, 10500),
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    return d, store, calendar


def test_q21_a_malformed_minute_bar_makes_the_day_unresolvable_and_never_raises(tmp_path) -> None:
    """The architect's Q-21 ruling: malformed minute evidence makes the bias UNRESOLVABLE for
    that pair. The engine must return that verdict, not propagate the exception -- a
    full-history run over 400,000 stock-days may not die on one vendor-corrupt bar."""
    d, store, calendar = _q21_world(tmp_path)
    engine = BiasEngine(
        store=store, calendar=calendar, minute_loader=_malformed_loader(d[2])
    )

    series = {b.trade_date: b for b in engine.bias_series("ACME", d[2], d[3])}

    thu = series[d[3]]
    assert thu.rule == RULE_MINUTES_MALFORMED
    assert thu.tradeable is False
    assert thu.unresolved_detail is not None
    # The offending bar rides in the detail, stamp and OHLCV, exactly as the ruling requires.
    assert "malformed-minute-bar ACME 2024-07-03 stamp 2024-07-03 09:15:00" in thu.unresolved_detail
    assert "O 44210 H 44440 L 44295 C 44295 V 12909" in thu.unresolved_detail


def test_q21_a_corrupt_day_decides_nothing_and_leaves_the_carry_untouched(tmp_path) -> None:
    """A corrupt day must not move the bias in EITHER direction. Wednesday seeded BULLISH; the
    unresolvable Thursday reports that same carried bias and is not tradeable on it."""
    d, store, calendar = _q21_world(tmp_path)
    engine = BiasEngine(
        store=store, calendar=calendar, minute_loader=_malformed_loader(d[2])
    )

    series = {b.trade_date: b for b in engine.bias_series("ACME", d[2], d[3])}

    assert series[d[2]].bias == BULLISH          # seeded on Tuesday's breakout
    assert series[d[3]].bias == BULLISH          # carried, UNCHANGED
    assert series[d[3]].tradeable is False       # ...but the day itself is refused


def test_q21_is_not_the_missing_minute_carry(tmp_path) -> None:
    """Corrupt data and ABSENT data are different answers to different questions. R1-Q6's
    documented fallback (no 1-minute data -> carry, day tradeable on the carried bias) must not
    swallow the Q-21 case, or a run would trade a day whose evidence is impossible."""
    d, store, calendar = _q21_world(tmp_path)
    absent = BiasEngine(store=store, calendar=calendar, minute_loader=None)
    corrupt = BiasEngine(
        store=store, calendar=calendar, minute_loader=_malformed_loader(d[2])
    )

    missing = absent.bias_for_day("ACME", d[3], seed_from=d[2])
    malformed = corrupt.bias_for_day("ACME", d[3], seed_from=d[2])

    assert missing.rule == "rule-3-no-1min-carry" and missing.tradeable is True
    assert malformed.rule == RULE_MINUTES_MALFORMED and malformed.tradeable is False
    assert missing.unresolved_detail is None and malformed.unresolved_detail is not None


# ==============================================================================================
# QUESTIONS.md Q-21(b): a Rule-3 scan that asks for a D-1 the gate battery refuses
#
# Same world, same Thursday, same machinery -- only the reason the minutes are inadmissible is
# different. The architect's 03-Aug-2026 ruling: "a day's minutes may serve a Rule-3 first-break
# scan ONLY if that day passes the CONTEXT 4.5/4.6 gate battery ... same machinery as Q-21's
# third, detail naming which gate failed."
# ==============================================================================================

Q21B_GATE = "gate-1P (per-day price containment)"
Q21B_REASON = "not price-proven: fold HIGH 401000 is 200299.5 paise past the tolerated daily high"


def _ungated_loader(day: date):
    """A MinuteLoader that refuses exactly the way the RUN's gated loader refuses (Q-21(b))."""

    def load(sym: str, when: date):
        if when == day:
            raise UngatedMinuteDay(
                symbol=sym, day=when, gate=Q21B_GATE, gate_reason=Q21B_REASON
            )
        return None

    return load


def _low_first_loader(day: date):
    """Day C's real minutes, with P.low (10400) broken FIRST -- so the admissible Rule-3 answer
    is BEARISH, the OPPOSITE of the bias carried into Thursday. That is what makes the
    carry-untouched assertion below discriminating rather than a coincidence."""

    def load(sym: str, when: date):
        if when != day:
            return None
        return (
            Candle(open=10450, high=10500, low=8000, close=10450,
                   stamp=datetime(when.year, when.month, when.day, 9, 15)),
            Candle(open=10450, high=13000, low=10450, close=13000,
                   stamp=datetime(when.year, when.month, when.day, 9, 16)),
        )

    return load


def test_q21b_a_battery_failing_D1_makes_the_day_unresolvable_and_never_raises(tmp_path) -> None:
    """The fourth REASON_BIAS_UNRESOLVED case, in the third's shape: a counted verdict, not a
    propagated exception, with the refusing gate and its own reason in the detail."""
    d, store, calendar = _q21_world(tmp_path)
    engine = BiasEngine(store=store, calendar=calendar, minute_loader=_ungated_loader(d[2]))

    thu = {b.trade_date: b for b in engine.bias_series("ACME", d[2], d[3])}[d[3]]

    assert thu.rule == RULE_MINUTES_UNGATED
    assert thu.tradeable is False
    assert thu.unresolved_detail == (
        f"minutes-ungated ACME 2024-07-03 refused by {Q21B_GATE} reason {Q21B_REASON}"
    )
    # the detail NAMES WHICH GATE failed -- the ruling's own requirement
    assert Q21B_GATE in thu.unresolved_detail
    # ...and names it ONCE: every battery name already begins with the word "gate", so the
    # earlier `gate {gate}` printed "gate gate-1P (...)" (REVIEW_9B_FIXES R9).
    assert "gate gate" not in thu.unresolved_detail


def test_q21b_a_battery_failing_day_leaves_the_carry_untouched(tmp_path) -> None:
    """The discriminating carry test. Fed ADMISSIBLE minutes this Thursday flips the bias to
    BEARISH (P.low breaks first); refused, it reports the carried BULLISH unchanged and is not
    tradeable on it. A day whose evidence is inadmissible decides nothing, in either direction."""
    d, store, calendar = _q21_world(tmp_path)
    admissible = BiasEngine(store=store, calendar=calendar, minute_loader=_low_first_loader(d[2]))
    refused = BiasEngine(store=store, calendar=calendar, minute_loader=_ungated_loader(d[2]))

    would_have = admissible.bias_for_day("ACME", d[3], seed_from=d[2])
    actual = refused.bias_for_day("ACME", d[3], seed_from=d[2])

    assert would_have.rule == "rule-3-outside-bar" and would_have.bias == BEARISH
    assert actual.rule == RULE_MINUTES_UNGATED
    assert actual.bias == BULLISH  # the carry, UNCHANGED -- not the BEARISH answer it lost
    assert actual.tradeable is False


def test_q21b_is_neither_the_missing_minute_carry_nor_the_malformed_bar(tmp_path) -> None:
    """Three different questions, three different answers. ABSENT data carries and TRADES
    (R1-Q6); a CORRUPT bar refuses the day naming the bar (Q-21); an INADMISSIBLE day refuses
    the day naming the gate (Q-21(b)). Collapsing any pair would trade a day it should not."""
    d, store, calendar = _q21_world(tmp_path)
    make = lambda loader: BiasEngine(  # noqa: E731 -- three engines, one differing field
        store=store, calendar=calendar, minute_loader=loader
    )

    missing = make(None).bias_for_day("ACME", d[3], seed_from=d[2])
    malformed = make(_malformed_loader(d[2])).bias_for_day("ACME", d[3], seed_from=d[2])
    ungated = make(_ungated_loader(d[2])).bias_for_day("ACME", d[3], seed_from=d[2])

    assert missing.rule == "rule-3-no-1min-carry" and missing.tradeable is True
    assert malformed.rule == RULE_MINUTES_MALFORMED and malformed.tradeable is False
    assert ungated.rule == RULE_MINUTES_UNGATED and ungated.tradeable is False
    assert missing.unresolved_detail is None
    assert malformed.unresolved_detail.startswith("malformed-minute-bar")
    assert ungated.unresolved_detail.startswith("minutes-ungated")


def test_q21b_both_unusable_evidence_cases_escape_as_a_counted_symbol_no_trade(tmp_path) -> None:
    """Defence in depth, unchanged from Q-21's B244 and now shared by both cases: each is an
    `UnusableMinuteEvidence`, which is a `BiasEngineError`, so an escape past the per-day catch
    is still a COUNTED whole-symbol no-trade in `BacktestRunner.bias_map` rather than a dead
    run over 400,000 stock-days."""
    for exc in (
        MalformedMinuteBar(
            symbol="ACME", day=date(2024, 7, 3), stamp=None,
            open_paise=1, high_paise=2, low_paise=3, close_paise=4, volume=5,
        ),
        UngatedMinuteDay(
            symbol="ACME", day=date(2024, 7, 3), gate=Q21B_GATE, gate_reason=Q21B_REASON
        ),
    ):
        assert isinstance(exc, UnusableMinuteEvidence)
        assert isinstance(exc, BiasEngineError)
        assert exc.detail() and exc.rule in (RULE_MINUTES_MALFORMED, RULE_MINUTES_UNGATED)
