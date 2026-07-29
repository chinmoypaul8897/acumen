"""REVIEW_9A reviewer probes -- kept in the repo per the persona process (step 4).

These close holes the chunk-9A build left open. Nothing here weakens or replaces an existing
test; every assertion is new. Three of them PIN A DEFECT rather than assert correct behaviour
(REVIEW_9A findings Q3, Q4 and C2): they are green today and must be deliberately flipped by
whoever fixes the defect, which is exactly the tripwire a silent regression needs.

**The E13 basis fixture**, hand-computed here before coding -- four executed trades, cost
Rs 100.00 = 10,000 paise each:

| # | gross | net | in gross_profit? | counted a WINNER? |
|---|---|---|---|---|
| 1 | +3,000.00 | +2,900.00 | yes | yes |
| 2 | +1,000.00 |   +900.00 | yes | yes |
| 3 |    +40.00 |    -60.00 | **yes** | **no** |
| 4 | -2,000.00 | -2,100.00 | no  | no |

* gross profit = 3,000 + 1,000 + 40 = **Rs 4,040.00** over THREE rows (gross > 0)
* winners = **2** (net > 0); avg profit = (2,900 + 900)/2 = **Rs 1,900.00**
* winners x avg profit = **Rs 3,800.00** != gross profit **Rs 4,040.00**
* the gap Rs 240.00 = 2 x Rs 100.00 commission (BASIS) + Rs 40.00 (MEMBERSHIP: trade 3 is
  inside gross profit and outside the winner set)

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timedelta
from fractions import Fraction

import pytest

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen.aggregate import Bar
from acumen.backtest import LedgerRow, STATUS_EVALUATED, STATUS_REFUSED
from acumen.signals import EXIT_TARGET, LONG, SHORT

COST = 10_000
CAPITAL = 10_000_000
DAY = date(2026, 3, 2)


def _trade(day: date, symbol: str, gross: int, *, side: str = LONG, qty: int = 10) -> LedgerRow:
    return LedgerRow(
        symbol=symbol,
        day=day,
        status=STATUS_EVALUATED,
        reason="evaluated",
        side=side,
        outcome="entered",
        consumed=True,
        signalled=True,
        executed=True,
        entry_paise=100_000,
        stop_paise=99_000,
        target_paise=103_000,
        per_share_risk_paise=1_000,
        entry_close_stamp=datetime.combine(day, datetime.min.time()) + timedelta(hours=12),
        exit_kind=EXIT_TARGET,
        exit_paise=103_000,
        exit_close_stamp=datetime.combine(day, datetime.min.time()) + timedelta(hours=14),
        qty=qty,
        notional_paise=qty * 100_000,
        gross_pnl_paise=gross,
        cost_paise=COST,
        net_pnl_paise=gross - COST,
        mfe_paise=0,
        mae_paise=0,
    )


def basis_rows() -> tuple[LedgerRow, ...]:
    """The four-trade ledger of the module docstring."""
    return (
        _trade(DAY, "AAA", 300_000),
        _trade(DAY, "BBB", 100_000),
        _trade(DAY, "CCC", 4_000),  # gross POSITIVE, net NEGATIVE after the Rs 100 cost
        _trade(DAY, "DDD", -200_000),
    )


# ==============================================================================================
# CONTEXT 7-E13 basis: gross-basis and net-basis metrics do NOT describe the same population
# ==============================================================================================


def test_the_gross_profit_population_is_not_the_winner_population() -> None:
    """REVIEW_9A finding Q1. `gross_profit` counts rows by the sign of GROSS; `winners`,
    `losers` and `percent_profitable` count them by the sign of NET. A trade whose gross
    profit is smaller than the Rs 100 round trip is inside the first set and outside the
    second -- so the two numbers, printed side by side, describe different trades."""
    rows = basis_rows()
    m = pf.metrics(rows)

    gross_positive = [r for r in rows if r.gross_pnl_paise > 0]
    net_positive = [r for r in rows if r.net_pnl_paise > 0]

    assert len(gross_positive) == 3
    assert len(net_positive) == 2
    assert m.winners == 2
    assert m.gross_profit_paise == 404_000  # Rs 4,040.00 over THREE rows
    # the row that is in one population and not the other:
    odd = set(r.symbol for r in gross_positive) - set(r.symbol for r in net_positive)
    assert odd == {"CCC"}
    # and the headline rate is the NET one, so the gross-basis rate is never printed:
    assert m.percent_profitable == Fraction(2, 4)
    assert Fraction(len(gross_positive), m.total_trades) == Fraction(3, 4)


def test_winners_times_avg_profit_does_not_equal_gross_profit() -> None:
    """REVIEW_9A finding Q1, the arithmetic. The identity a report reader would try fails,
    and it fails by exactly two terms: the winners' commission (BASIS: avg profit is NET,
    gross profit is GROSS) and the gross of every gross-positive row that the winner set
    excludes (MEMBERSHIP)."""
    rows = basis_rows()
    m = pf.metrics(rows)

    assert m.avg_profit_paise == Fraction(190_000)  # Rs 1,900.00, a NET average
    naive = m.winners * m.avg_profit_paise
    assert naive == 380_000  # Rs 3,800.00
    assert naive != m.gross_profit_paise

    basis_term = m.winners * COST
    membership_term = sum(
        r.gross_pnl_paise for r in rows if r.gross_pnl_paise > 0 and r.net_pnl_paise <= 0
    )
    assert basis_term == 20_000  # Rs 200.00
    assert membership_term == 4_000  # Rs 40.00
    assert naive + basis_term + membership_term == m.gross_profit_paise


def test_the_largest_win_line_mixes_a_net_number_with_a_gross_share() -> None:
    """REVIEW_9A finding Q2. `largest_win_paise` and its percent-of-notional are NET; the
    percent-of-gross-profit beside them divides that trade's GROSS by gross profit. Three
    numbers, two bases, printed inside one parenthesis in the pack."""
    rows = basis_rows()
    m = pf.metrics(rows)
    best = max(rows, key=lambda r: r.net_pnl_paise)

    assert m.largest_win_paise == best.net_pnl_paise == 290_000
    assert m.largest_win_pct_of_notional == Fraction(290_000, 1_000_000)  # NET / notional
    assert m.largest_win_pct_of_gross_profit == Fraction(300_000, 404_000)  # GROSS / gross
    # the same figure on a NET basis would be a different number entirely:
    assert m.largest_win_pct_of_gross_profit != Fraction(290_000, 404_000)


# ==============================================================================================
# Max drawdown / run-up: the recovery date (E13 asks for drawdowns "with durations")
# ==============================================================================================


def _points(nets: list[int]) -> tuple[pf.EquityPoint, ...]:
    series = [
        pf.DailyPnL(
            day=DAY + timedelta(days=i),
            trades=1,
            gross_paise=n,
            cost_paise=0,
            net_paise=n,
            mfe_paise=0,
            mae_paise=0,
        )
        for i, n in enumerate(nets)
    ]
    return pf.equity_curve(series, CAPITAL)


def test_a_drawdown_from_a_real_peak_names_the_day_it_recovered() -> None:
    """The control for the probe below: when the peak is a real trading day the recovery
    date is found, which is what `_first_recovery` was written for."""
    points = _points([+200_000, -500_000, -300_000, +900_000])
    fall = pf.max_drawdown(points)
    assert fall.peak_day == DAY
    assert fall.trough_day == DAY + timedelta(days=2)
    assert fall.recovered_on == DAY + timedelta(days=3)


def test_a_drawdown_whose_peak_is_the_opening_capital_loses_its_recovery_date() -> None:
    """**REVIEW_9A finding Q3 -- PINS A DEFECT, flip this test when it is fixed.**

    Decision B185 makes ``peak_day is None`` a first-class case meaning "the run's opening
    capital", and a strategy that goes down from its first day lands there. But
    `_first_recovery` only learns the peak equity from a point whose ``day`` equals
    ``peak_day``; with ``peak_day`` None no point ever matches, so it returns None and the
    report says "recovered never" for a drawdown that demonstrably recovered.

    Here equity falls to 92,000 and is back above the opening 100,000 two days later."""
    points = _points([-500_000, -300_000, +900_000, +100_000])
    fall = pf.max_drawdown(points)

    assert fall.peak_day is None  # B185: the peak IS the opening capital
    assert fall.amount_paise == 800_000
    assert fall.trough_day == DAY + timedelta(days=1)
    # the equity really does recover, on the third day:
    assert points[2].equity_paise > CAPITAL
    # ...but the metric cannot say so:
    assert fall.recovered_on is None  # <-- the defect. Should be DAY + 2 days.


def test_the_max_run_up_never_reports_a_recovery_date() -> None:
    """**REVIEW_9A finding Q4 -- PINS A DEFECT (severity INFO), flip when fixed.**

    E13 asks for run-ups in the "same forms" as drawdowns. `max_drawdown` fills
    `recovered_on`; `max_run_up` never does, on any input, so the field is structurally
    dead rather than meaningfully empty."""
    for nets in ([+200_000, -500_000, -300_000, +900_000], [+100_000, +100_000, +100_000]):
        assert pf.max_run_up(_points(nets)).recovered_on is None


# ==============================================================================================
# Division guards
# ==============================================================================================


def test_metrics_divide_by_the_initial_capital_without_guarding_it() -> None:
    """**REVIEW_9A finding C2 -- PINS A DEFECT (severity LOW), flip when fixed.**

    Every other ratio in the module returns None rather than dividing by zero (`_ratio`,
    `profit_factor`, `_pct_of_notional`, the drawdown percent). `return_on_initial_capital`
    and the benchmark's `total_return` do not: a zero capital reaches `Fraction(x, 0)`.
    Not reachable through the runner -- CONTEXT 3.5 fixes the capital -- but it is the one
    unguarded division left in a module whose whole point is that it has none."""
    with pytest.raises(ZeroDivisionError):
        pf.metrics(basis_rows(), initial_capital_paise=0)
    with pytest.raises(ZeroDivisionError):
        pf.buy_and_hold(
            {"AAA": {DAY: 100_000}}, first_day=DAY, last_day=DAY, initial_capital_paise=0
        )


def test_every_other_ratio_returns_none_instead_of_dividing_by_zero() -> None:
    """The contrast that makes the probe above a finding rather than a style note."""
    empty = pf.metrics(())
    assert empty.profit_factor is None
    assert empty.avg_pnl_paise is None
    assert empty.percent_profitable is None
    assert empty.avg_profit_over_avg_loss is None
    assert pf.sharpe(()) is None and pf.sortino(()) is None


# ==============================================================================================
# The excursions the PROVISIONAL band is built from (Q-16(b))
# ==============================================================================================


def _bar(hour: int, minute: int, high: int, low: int) -> Bar:
    stamp = datetime.combine(DAY, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
    return Bar(stamp=stamp, open_paise=low, high_paise=high, low_paise=low, close_paise=high, volume=1)


def test_the_ledger_excursions_are_position_scaled_not_per_share() -> None:
    """Load-bearing for Q-16(b): the provisional intraday band adds a day's MFE and MAE
    straight onto the equity curve, so the ledger's excursions must already be in portfolio
    rupees. Doubling the position doubles both -- if they were per-share the band would be
    wrong by a factor of qty on every day."""
    bars = (_bar(11, 15, 105_000, 95_000), _bar(11, 30, 108_000, 99_000))
    entry_stamp = bars[0].close_stamp - timedelta(minutes=15)

    mfe_10, mae_10 = bt.trade_excursion_paise(LONG, 100_000, 10, bars, entry_stamp, None)
    mfe_20, mae_20 = bt.trade_excursion_paise(LONG, 100_000, 20, bars, entry_stamp, None)

    assert (mfe_10, mae_10) == (80_000, -50_000)  # (108,000-100,000) x 10, (95,000-100,000) x 10
    assert (mfe_20, mae_20) == (160_000, -100_000)
    assert mfe_10 >= 0 and mae_10 <= 0


def test_the_short_excursion_mirrors_the_long_one() -> None:
    """The mirror the pack never exercises: on a short, a HIGH is adverse and a LOW is
    favourable, and the signs still come back MFE >= 0, MAE <= 0."""
    bars = (_bar(11, 15, 105_000, 95_000), _bar(11, 30, 108_000, 99_000))
    entry_stamp = bars[0].close_stamp - timedelta(minutes=15)
    mfe, mae = bt.trade_excursion_paise(SHORT, 100_000, 10, bars, entry_stamp, None)
    assert (mfe, mae) == (50_000, -80_000)
    assert mfe >= 0 and mae <= 0


def test_an_unheld_position_has_no_excursion_on_either_side() -> None:
    """Chunk-7 decision B159's entry-candle square-off: no monitored candle, so nothing to
    measure -- and zero rather than a negative number invented from the entry candle."""
    bars = (_bar(11, 15, 105_000, 95_000),)
    late = bars[0].close_stamp + timedelta(hours=3)
    assert bt.trade_excursion_paise(LONG, 100_000, 10, bars, late, None) == (0, 0)
    assert bt.trade_excursion_paise(LONG, 100_000, 0, bars, late, None) == (0, 0)


# ==============================================================================================
# The refusal partition and the pending-answer discipline
# ==============================================================================================


def test_the_reason_counts_partition_every_walked_day() -> None:
    """One row per walked day, one reason per row: `refused_by_reason` plus the evaluated
    count must equal the walk, or a manifest reader is double-counting a day that failed
    two ways. Verified on real damaged data too (REVIEW_9A section on IOC/TATASTEEL 2018)."""
    rows = basis_rows() + (
        LedgerRow(symbol="EEE", day=DAY, status=STATUS_REFUSED, reason=bt.REASON_E2_NON_STANDARD),
        LedgerRow(symbol="FFF", day=DAY, status=STATUS_REFUSED, reason="gate 1 (volume)"),
        LedgerRow(symbol="GGG", day=DAY, status=STATUS_REFUSED, reason="gate 1 (volume)"),
    )
    refused: dict[str, int] = {}
    for row in rows:
        if row.status == STATUS_REFUSED:
            refused[row.reason] = refused.get(row.reason, 0) + 1
    evaluated = sum(1 for row in rows if row.status == STATUS_EVALUATED)

    assert sum(refused.values()) + evaluated == len(rows)
    assert sum(bt.outcome_counts(rows).values()) == len(rows)
    assert all(row.reason for row in rows)  # never an empty reason


def test_no_capital_figure_is_hidden_in_the_flag_machinery() -> None:
    """Q43 is pending, so `capital_flags` must hold no number of its own -- not even
    CONTEXT 3.5's Rs 1,00,000. Asserted structurally over the function's numeric literals,
    so a constant cannot hide where a `.get(default)` would."""
    tree = ast.parse(inspect.getsource(pf.capital_flags))
    numbers = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    }
    assert numbers == set()
    assert not pf.capital_flags((), capital_reference_paise=None, margin_basis=None).computed
    assert (
        pf.capital_flags((), capital_reference_paise=None, margin_basis=None).note
        == pf.CAPITAL_FLAGS_PENDING_NOTE
    )


def test_the_two_blocked_e13_entries_never_come_back_as_numbers() -> None:
    """Q-16 is OPEN: `outliers` must stay None with its reason attached, and the intra-trade
    excursions must always carry the PROVISIONAL sentence beside them."""
    m = pf.metrics(basis_rows())
    assert m.outliers is None
    assert "Q-16(a)" in m.outliers_note
    assert "PROVISIONAL" in m.intra_trade_note
    assert "Q-16(b)" in m.intra_trade_note
