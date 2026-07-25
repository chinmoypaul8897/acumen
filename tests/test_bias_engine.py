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
from datetime import date, timedelta
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
from acumen.bias_engine import BiasEngine, csv_minute_loader
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
