"""REVIEW_8 reviewer probes -- kept in the repo, per the review persona's step 4.

Each probe below was written because a MUTANT survived the chunk-8 build's own suite. A
probe that only lives in a review document cannot stop the next session reintroducing the
defect, so they live here. Every one is verified to FAIL on its mutant and pass on HEAD, and
each carries the mutant it kills in its docstring.

Two areas were left uncovered by the build:

1. ``acumen.trade_evidence.run_sweep`` -- the loop that ACCUMULATES the priced days. The
   build unit-tests every function that CONSUMES a ``SweepResult`` (the totals, the partition,
   the shape counts, the eight invariants) on synthetic records, but nothing exercised the
   loop that BUILDS it. Three separate mutations of that loop survived the entire 1,542-test
   suite: double-appending every day, dropping the days that produced no executed trade, and
   resetting the accumulator per symbol. Each one silently rewrites every number in the
   committed evidence pack -- which is the artifact CLAUDE.md's evidence rule (REVIEW_7 C3)
   exists so a later chunk can re-check.

2. The square-off's candle, priced from a candle that is neither the marked one nor an
   adjacent one. The build pins the marked-candle close; these pin that the day's OTHER
   candles cannot be the source.

The probes use hand-built fakes -- no store, no network, no clock -- so they run in a bare
clone. ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import signals as sig
from acumen import simulate as sim
from acumen import trade_evidence as evidence
from acumen.aggregate import Bar
from acumen.signal_engine import StockDay

DAY_ONE = date(2026, 5, 4)
POC = Fraction(203_000)  # Rs 2,030.00 in paise


def _R(rupees: float) -> int:
    return int(round(rupees * 100))


def _bars(*rows) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            stamp=sig.bar_open_stamp(day, ordinal),
            open_paise=_R(o),
            high_paise=_R(h),
            low_paise=_R(low),
            close_paise=_R(c),
            volume=1_000,
        )
        for ordinal, o, h, low, c, day in rows
    )


#: An entered day: reference 2025 arms at POC 2030, the 11:30 close 2035 triggers (entry
#: 2035, stop = the entry candle's low 2029, risk 6.00 -> qty 166), and the next candle's
#: high 2053 pays the target. Hand-computed: gross 166 x 1,800 = Rs 2,988.00, net Rs 2,888.00.
def _entered_day(day: date) -> StockDay:
    bars = _bars(
        (8, 2028, 2029, 2024, 2025, day),
        (9, 2031, 2036, 2029, 2035, day),
        (10, 2035, 2053, 2034, 2050, day),
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.LONG, poc_paise=POC)
    return StockDay(
        symbol="TCS",
        day=day,
        evaluated=True,
        reason="evaluated",
        side=sig.LONG,
        bars=bars,
        signal=signal,
    )


#: A day that never crosses: armed, but no close ever gets above the POC. It produces a
#: TradeRecord with no entry and no money -- and it must still be COUNTED.
def _no_cross_day(day: date) -> StockDay:
    bars = _bars(
        (8, 2028, 2029, 2024, 2025, day),
        (9, 2025, 2029, 2020, 2022, day),
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.LONG, poc_paise=POC)
    return StockDay(
        symbol="TCS",
        day=day,
        evaluated=True,
        reason="evaluated",
        side=sig.LONG,
        bars=bars,
        signal=signal,
    )


#: A day the gate battery refused: it never reached the signal engine, so it has no record at
#: all -- and it must STILL be one row of the sweep (CONTEXT 7-E3: exclusions are counted,
#: never silently dropped).
def _refused_day(day: date) -> StockDay:
    return StockDay(
        symbol="TCS", day=day, evaluated=False, reason="gate 1 failed: volume gap +7.2%"
    )


@dataclass(frozen=True)
class _FakeBias:
    trade_date: date
    bias: str = "bullish"
    tie_case: bool = False


class _FakePipeline:
    """Hands back a pre-built StockDay per date. Stands in for the real pipeline."""

    row_size = 24

    def __init__(self, by_day: dict[date, StockDay]) -> None:
        self._by_day = by_day

    def stock_day(self, symbol: str, day: date, *, bias=None) -> StockDay:
        return self._by_day[day]


class _FakeBiasEngine:
    def __init__(self, days: list[date]) -> None:
        self._days = days

    def bias_series(self, symbol: str, start: date, end: date):
        return [_FakeBias(trade_date=d) for d in self._days]


def _context(by_day: dict[date, StockDay]) -> evidence.SweepContext:
    days = sorted(by_day)
    return evidence.SweepContext(
        pipeline=_FakePipeline(by_day),
        bias_engine=_FakeBiasEngine(days),
        risk_per_trade_paise=100_000,
        cost_paise=10_000,
        master_path=Path("cache/instrument_master/fake.json"),
    )


def _three_shapes() -> dict[date, StockDay]:
    """One entered day, one no-cross day, one gate-refused day -- the three sweep shapes."""
    return {
        date(2026, 5, 4): _entered_day(date(2026, 5, 4)),
        date(2026, 5, 5): _no_cross_day(date(2026, 5, 5)),
        date(2026, 5, 6): _refused_day(date(2026, 5, 6)),
    }


# ==============================================================================================
# The sweep loop: every walked day appears EXACTLY ONCE, whatever happened to it
# ==============================================================================================


def test_the_sweep_keeps_every_walked_day_exactly_once() -> None:
    """MUTANT KILLED: ``days.append(...)`` written twice -- the sweep double-counts every day.

    That mutation survived all 1,542 tests of the chunk-8 build and would double every figure
    in the committed evidence pack: 290 stock-days would print as 580 and the net PnL would
    double. The partition is the pack's own claim (146 entered / 88 armed-no-cross / 56
    never-armed = 290), so it has to be the loop that is pinned, not only the counters.
    """
    by_day = _three_shapes()
    result = evidence.run_sweep(
        _context(by_day), symbols=("TCS",), start=date(2026, 5, 4), end=date(2026, 5, 6)
    )

    assert len(result.days) == 3
    assert [priced.day for priced in result.days] == sorted(by_day)
    assert len({priced.day for priced in result.days}) == 3  # no duplicates
    assert sum(evidence.outcome_counts(result).values()) == 3


def test_the_sweep_keeps_the_days_that_produced_no_executed_trade() -> None:
    """MUTANT KILLED: the loop appends only ``if priced.executed``.

    CONTEXT 7-E3 and CONTEXT 3.5's disclosures need the days that did NOT trade as much as
    the ones that did -- a win rate over kept-if-executed days is 100% by construction. The
    surviving mutant reduced the pack's 290 walked days to its 146 executed ones and left
    every printed total unchanged, so nothing in the pack itself would have looked wrong.
    """
    result = evidence.run_sweep(
        _context(_three_shapes()),
        symbols=("TCS",),
        start=date(2026, 5, 4),
        end=date(2026, 5, 6),
    )

    assert len(result.days) == 3
    assert len(result.executed) == 1
    assert len(result.evaluated) == 2  # the refused day has no record at all
    assert len(result.entered) == 1
    counts = evidence.outcome_counts(result)
    assert counts[sig.OUTCOME_ENTERED] == 1
    assert counts[sig.OUTCOME_ARMED_NO_CROSS] == 1
    assert counts["not evaluated: gate 1 failed: volume gap +7.2%"] == 1


def test_the_sweep_accumulates_across_symbols_rather_than_resetting() -> None:
    """MUTANT KILLED: ``days = []`` reset at the top of the per-symbol loop.

    The pack walks five symbols; that mutation kept only the last one's 58 days and still
    printed a self-consistent pack. Two symbols with a different number of days each make the
    reset visible.
    """
    by_day = _three_shapes()
    context = _context(by_day)
    result = evidence.run_sweep(
        context, symbols=("TCS", "RELIANCE"), start=date(2026, 5, 4), end=date(2026, 5, 6)
    )

    assert len(result.days) == 6  # 3 days x 2 symbols, not 3
    assert result.symbols == ("TCS", "RELIANCE")
    assert sum(evidence.outcome_counts(result).values()) == 6
    assert evidence.money_totals(result)["trades"] == 2


def test_the_sweep_carries_its_money_inputs_onto_the_result() -> None:
    """The pack prints the risk and cost it ran with; a result that lost them would let the
    pack claim CONTEXT 3.5's amounts while the run used others."""
    result = evidence.run_sweep(
        _context(_three_shapes()),
        symbols=("TCS",),
        start=date(2026, 5, 4),
        end=date(2026, 5, 6),
    )

    assert result.risk_per_trade_paise == 100_000
    assert result.cost_paise == 10_000
    assert result.row_size == 24
    assert (result.start, result.end) == (date(2026, 5, 4), date(2026, 5, 6))


# ==============================================================================================
# The square-off fills at the MARKED candle -- not at any other candle of the day
# ==============================================================================================


def test_a_square_off_cannot_be_priced_from_any_other_candle_of_the_day() -> None:
    """MUTANT KILLED: the square-off returns the close of the candle BEFORE the marked one.

    The build pins that the fill IS the marked candle's close. This pins the complement: no
    other candle of the day carries that price, so a mutation that walks one candle either
    way cannot coincide with the right answer. Every close in this day is distinct on purpose.

    HAND-COMPUTED at POC 2030: entry 2035 (11:30 close), stop 2029, risk 6.00, qty 166;
    nothing touches 2029 or 2053 by 15:15, so the fill is the 15:00-stamped candle's close
    **2044**: gross = 166 x 900 = Rs 1,494.00, net Rs 1,394.00.
    """
    day = date(2026, 5, 4)
    bars = _bars(
        (8, 2028, 2029, 2024, 2025, day),
        (9, 2031, 2036, 2029, 2035, day),
        (10, 2035, 2040, 2033, 2038, day),
        (23, 2038, 2044, 2036, 2041, day),  # the candle BEFORE the marked one
        (24, 2041, 2046, 2038, 2044, day),  # the 15:00-stamped candle -- the marked one
        (25, 2045, 2060, 2040, 2058, day),  # 15:15-stamped: after the square-off
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.LONG, poc_paise=POC)
    record = sim.simulate_day(
        signal, bars, symbol="TCS", risk_per_trade_paise=100_000, cost_paise=10_000
    )

    marked = [b for b in bars if b.stamp == record.exit_stamp]
    assert len(marked) == 1
    assert record.exit_kind == sig.EXIT_SQUARE_OFF
    assert record.exit_paise == marked[0].close_paise == _R(2044)

    others = [b for b in bars if b.stamp != record.exit_stamp]
    assert record.exit_paise not in {b.close_paise for b in others}
    assert record.exit_paise not in {b.open_paise for b in others}
    assert record.exit_paise != marked[0].open_paise
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (_R(1_494), _R(1_394))


# ==============================================================================================
# A target fill is the LEVEL however far the candle ran past it (CONTEXT 7-E9)
# ==============================================================================================


def test_a_candle_that_blows_ten_rupees_through_the_target_still_pays_three_r() -> None:
    """MUTANT KILLED: a target exit priced at the candle's HIGH instead of the target level.

    The build's exact-touch test has high == target, so it cannot distinguish the two. Here
    the high runs Rs 10 past the target and the two answers differ by Rs 1,660.

    HAND-COMPUTED at POC 2030: entry 2035, stop 2029, risk 6.00, target **2053**, qty 166.
    The next candle's high is 2063. gross = 166 x 1,800 = **Rs 2,988.00** (= qty x 3 x risk),
    net Rs 2,888.00. Paying the high 2063 would have been Rs 4,648.00 -- Rs 1,660 of money
    the trade never made.
    """
    day = date(2026, 5, 4)
    bars = _bars(
        (8, 2028, 2029, 2024, 2025, day),
        (9, 2031, 2036, 2029, 2035, day),
        (10, 2035, 2063, 2034, 2060, day),
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.LONG, poc_paise=POC)
    record = sim.simulate_day(
        signal, bars, symbol="TCS", risk_per_trade_paise=100_000, cost_paise=10_000
    )

    assert record.exit_kind == sig.EXIT_TARGET
    assert record.exit_paise == _R(2053) == record.target_paise
    assert record.gross_pnl_paise == record.qty * 3 * record.per_share_risk_paise
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (_R(2_988), _R(2_888))
    assert record.gross_pnl_paise != record.qty * (_R(2063) - record.entry_paise)


def test_the_short_mirror_of_a_stop_blown_through() -> None:
    """The short mirror of the same idea: the candle's high runs Rs 10 past the stop and the
    fill is still the stop LEVEL.

    HAND-COMPUTED at POC 1970 (bearish): reference 1975 arms; the 11:30 close 1965 triggers;
    stop = the entry candle's high **1971**, risk 6.00, qty 166. The next candle's high is
    1981. gross = 166 x (196,500 - 197,100) = **-Rs 996.00**, net -Rs 1,096.00 -- exactly one
    R. Filling at 1981 would have lost Rs 2,656.00.
    """
    day = date(2026, 5, 4)
    bars = _bars(
        (8, 1972, 1976, 1971, 1975, day),
        (9, 1969, 1971, 1963, 1965, day),
        (10, 1965, 1981, 1962, 1978, day),
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.SHORT, poc_paise=Fraction(197_000))
    record = sim.simulate_day(
        signal, bars, symbol="TCS", risk_per_trade_paise=100_000, cost_paise=10_000
    )

    assert record.exit_kind == sig.EXIT_STOP
    assert record.exit_paise == _R(1971) == record.stop_paise
    assert record.gross_pnl_paise == -record.qty * record.per_share_risk_paise
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (_R(-996), _R(-1_096))


# ==============================================================================================
# The sizing floor at the exact budget, END TO END (the build asserts it on position_size)
# ==============================================================================================


@pytest.mark.parametrize(
    "stop_rupees,expected_qty,expected_risk_paise",
    [(1035.00, 1, 100_000), (1034.99, 0, 100_001), (1035.01, 1, 99_999)],
)
def test_the_floor_at_the_exact_budget_end_to_end(
    stop_rupees: float, expected_qty: int, expected_risk_paise: int
) -> None:
    """MUTANT KILLED: ``(risk + 1) // per_share_risk`` -- an off-by-one floor that sizes a
    share at Rs 1,000.01 of per-share risk.

    CONTEXT 3.5's floor decided on the paisa: a per-share risk of exactly the whole budget
    buys ONE share, one paisa more buys NONE, one paisa less still buys one. The build pins
    this on :func:`position_size`; this pins it through the whole pipeline, where the risk is
    derived from real candles rather than passed in.
    """
    day = date(2026, 5, 4)
    bars = _bars(
        (8, 2028, 2029, 2024, 2025, day),
        (9, 2031, 2036, stop_rupees, 2035, day),
    )
    signal = sig.evaluate_day(bars, day=day, side=sig.LONG, poc_paise=POC)
    record = sim.simulate_day(
        signal, bars, symbol="TCS", risk_per_trade_paise=100_000, cost_paise=10_000
    )

    assert record.per_share_risk_paise == expected_risk_paise
    assert record.qty == expected_qty
    assert record.qty * record.per_share_risk_paise <= 100_000
    assert (record.qty + 1) * record.per_share_risk_paise > 100_000
    if expected_qty == 0:
        assert record.flags == (sim.FLAG_QTY_ZERO_UNSIZABLE,)
        assert (record.cost_paise, record.gross_pnl_paise, record.net_pnl_paise) == (0, 0, 0)
        assert record.exit_paise is None
    else:
        assert record.cost_paise == 10_000
