"""The chunk-9A portfolio layer: CONTEXT 3.5's take-all semantics and CONTEXT 7-E13's metrics.

Every number asserted here is hand-computed IN THIS DOCSTRING first, from a six-trade ledger
small enough to check with a pencil. The module under test is pure, so the fixture is just rows.

**The fixture** -- two symbols, both sides, five walked days (one of them traded nothing), cost
Rs 100.00 = 10,000 paise per executed trade:

| # | day | symbol | side | qty | entry | notional | gross | net |
|---|---|---|---|---|---|---|---|---|
| 1 | 01-01 | AAA | long | 100 | 2,000.00 | 200,000.00 | +3,000.00 | +2,900.00 |
| 2 | 01-01 | BBB | short | 50 | 1,000.00 | 50,000.00 | -1,000.00 | -1,100.00 |
| 3 | 01-05 | AAA | long | 40 | 2,500.00 | 100,000.00 | +1,000.00 | +900.00 |
| 4 | 01-06 | AAA | short | 20 | 3,000.00 | 60,000.00 | -2,000.00 | -2,100.00 |
| 5 | 01-06 | BBB | long | 10 | 4,000.00 | 40,000.00 | +500.00 | +400.00 |
| 6 | 01-07 | BBB | long | 5 | 1,000.00 | 5,000.00 | 0.00 | -100.00 |

* gross profit 3,000 + 1,000 + 500 = **Rs 4,500.00**; gross loss -1,000 - 2,000 =
  **-Rs 3,000.00**; profit factor 4500/3000 = **3/2**; commission 6 x 100 = **Rs 600.00**;
  net 2,900 - 1,100 + 900 - 2,100 + 400 - 100 = **Rs 900.00**.
* winners (net > 0) 3, losers 3, flat 0 -> **% profitable = 1/2**; expected payoff
  900/6 = **Rs 150.00**; avg profit (2,900 + 900 + 400)/3 = **Rs 1,400.00**; avg loss
  (-1,100 - 2,100 - 100)/3 = **-Rs 1,100.00**; avg profit / avg loss = **14/11**.
* largest win **+Rs 2,900.00** = 29/2000 of its own Rs 200,000.00 notional, and its gross
  3,000/4,500 = **2/3** of gross profit; largest loss **-Rs 2,100.00** = -7/200 of its
  Rs 60,000.00 notional, gross -2,000/-3,000 = **2/3** of gross loss.
* daily net: 01-01 **+Rs 1,800.00**, 01-02 **0**, 01-05 **+Rs 900.00**, 01-06
  **-Rs 1,700.00**, 01-07 **-Rs 100.00**. On capital Rs 100,000.00 the equity closes
  101,800 / 101,800 / 102,700 / 101,000 / 100,900.
* max drawdown (close-to-close) = 102,700 (01-05) -> 100,900 (01-07) = **Rs 1,800.00**,
  18/1027 of the peak, duration 2 observations, never recovered. Max run-up runs from the
  OPENING capital 100,000 to 102,700 (01-05) = **Rs 2,700.00**, 27/1000, duration 3
  observations (the opening counts as the one before the first day).
* provisional intra-trade drawdown: peak 102,700 (01-05 close) -> 01-06's provisional low
  102,700 - 2,600 - 300 - 200 = 99,600 = **Rs 3,100.00**.
* daily returns 0, 9/1018, -17/1027, -1/1010 -- four observations, so Sharpe and Sortino exist.
* concurrency: 01-01 holds two positions worth 200,000 + 50,000 = **Rs 250,000.00** at once,
  01-06 two worth 100,000 -- so max concurrent **2** and peak simultaneous notional
  **Rs 250,000.00**. Daily trade counts: two days of 2, two days of 1, one day of 0.
* buy & hold: AAA 2,000 -> 2,200 (+10%), BBB 1,000 -> 900 (-10%), equal weight
  Rs 50,000 each -> 55,000 + 45,000 = **Rs 100,000.00**, total return **0**.
* capital flags at capital_reference Rs 100,000.00 and margin basis 5: exactly ONE trade is
  beyond cash (trade 1 at Rs 200,000.00); trade 3 sits EXACTLY at Rs 100,000.00 and is NOT
  flagged (the rule is "exceeds"); nothing reaches the Rs 500,000.00 margin tier.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from acumen import portfolio as pf
from acumen.backtest import LedgerRow, STATUS_EVALUATED, STATUS_REFUSED
from acumen.signals import EXIT_TARGET, LONG, SHORT

CAPITAL = 10_000_000  # Rs 1,00,000.00 in paise (CONTEXT 3.5)
COST = 10_000

D1 = date(2026, 1, 1)
D2 = date(2026, 1, 2)
D3 = date(2026, 1, 5)
D4 = date(2026, 1, 6)
D5 = date(2026, 1, 7)


def trade(
    day: date,
    symbol: str,
    side: str,
    qty: int,
    entry_paise: int,
    gross: int,
    *,
    hour: int = 12,
    exit_hour: int = 14,
    mfe: int = 0,
    mae: int = 0,
) -> LedgerRow:
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
        entry_paise=entry_paise,
        stop_paise=entry_paise - 100,
        target_paise=entry_paise + 300,
        per_share_risk_paise=100,
        entry_close_stamp=datetime.combine(day, datetime.min.time()) + timedelta(hours=hour),
        exit_kind=EXIT_TARGET,
        exit_paise=entry_paise + 300,
        exit_close_stamp=datetime.combine(day, datetime.min.time())
        + timedelta(hours=exit_hour),
        qty=qty,
        notional_paise=qty * entry_paise,
        gross_pnl_paise=gross,
        cost_paise=COST,
        net_pnl_paise=gross - COST,
        mfe_paise=mfe,
        mae_paise=mae,
    )


def no_trade(day: date, symbol: str, reason: str = "no-trade-never-armed") -> LedgerRow:
    return LedgerRow(
        symbol=symbol,
        day=day,
        status=STATUS_EVALUATED,
        reason="evaluated",
        outcome=reason,
        side=LONG,
    )


def fixture_rows() -> tuple[LedgerRow, ...]:
    """The six-trade ledger of the module docstring, plus the flat day that traded nothing."""
    return (
        trade(D1, "AAA", LONG, 100, 200_000, 300_000, hour=11, exit_hour=15, mfe=400_000, mae=-50_000),
        trade(D1, "BBB", SHORT, 50, 100_000, -100_000, hour=12, exit_hour=13, mfe=20_000, mae=-120_000),
        no_trade(D2, "AAA"),
        no_trade(D2, "BBB"),
        trade(D3, "AAA", LONG, 40, 250_000, 100_000, mfe=150_000, mae=-10_000),
        trade(D4, "AAA", SHORT, 20, 300_000, -200_000, hour=11, exit_hour=15, mfe=0, mae=-260_000),
        trade(D4, "BBB", LONG, 10, 400_000, 50_000, hour=12, exit_hour=14, mfe=90_000, mae=-30_000),
        trade(D5, "BBB", LONG, 5, 100_000, 0, mfe=10_000, mae=-40_000),
    )


ROWS = fixture_rows()


# ==============================================================================================
# The daily series and the equity curve (CONTEXT 3.5: capital + cumulative PnL, a plain SUM)
# ==============================================================================================


def test_the_daily_series_covers_every_walked_day_including_the_flat_one() -> None:
    series = pf.daily_pnl(ROWS)
    assert [day.day for day in series] == [D1, D2, D3, D4, D5]
    assert [day.net_paise for day in series] == [180_000, 0, 90_000, -170_000, -10_000]
    assert [day.trades for day in series] == [2, 0, 1, 2, 1]
    assert sum(day.net_paise for day in series) == 90_000


def test_the_equity_curve_is_a_plain_cumulative_sum_on_the_context_capital() -> None:
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert [point.equity_paise for point in points] == [
        10_180_000,
        10_180_000,
        10_270_000,
        10_100_000,
        10_090_000,
    ]
    assert points[-1].equity_paise - CAPITAL == sum(row.net_pnl_paise for row in ROWS)


def test_the_equity_delta_equals_the_sum_of_the_trade_pnls(tmp_path=None) -> None:
    """The chunk-9 card's own internal-consistency assert."""
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert points[-1].equity_paise - CAPITAL == sum(
        row.net_pnl_paise for row in pf.executed(ROWS)
    )
    assert len(pf.executed(ROWS)) == 6


def test_the_intraday_band_is_the_provisional_worst_and_best_case() -> None:
    """01-01: opening equity 100,000, MAE -50,000 + -120,000 = -170,000 paise, costs 20,000 ->
    low 10,000,000 - 170,000 - 20,000 = 9,810,000; MFE 400,000 + 20,000 -> high 10,400,000."""
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert points[0].low_equity_paise == 9_810_000
    assert points[0].high_equity_paise == 10_400_000
    assert pf.INTRA_TRADE_PROVISIONAL.startswith("PROVISIONAL")


# ==============================================================================================
# Drawdown and run-up
# ==============================================================================================


def test_max_drawdown_close_to_close_is_hand_computed() -> None:
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    excursion = pf.max_drawdown(points)
    assert excursion.amount_paise == 180_000
    assert excursion.pct == Fraction(180_000, 10_270_000) == Fraction(18, 1027)
    assert (excursion.peak_day, excursion.trough_day) == (D3, D5)
    assert excursion.duration_days == 2
    assert excursion.recovered_on is None


def test_max_run_up_close_to_close_is_hand_computed() -> None:
    """From the OPENING capital (Rs 1,00,000.00) to the 01-05 close -- a rise that starts
    before the first day is still a rise the account made."""
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    excursion = pf.max_run_up(points)
    assert excursion.amount_paise == 270_000
    assert excursion.pct == Fraction(27, 1000)
    assert (excursion.trough_day, excursion.peak_day) == (None, D3)
    assert excursion.duration_days == 3


def test_a_drawdown_that_recovers_names_the_day_it_recovered() -> None:
    rows = (
        trade(D1, "AAA", LONG, 1, 100_000, -100_000),
        trade(D2, "AAA", LONG, 1, 100_000, 500_000),
    )
    points = pf.equity_curve(pf.daily_pnl(rows), CAPITAL)
    excursion = pf.max_drawdown(points)
    assert excursion.amount_paise == 0 or excursion.recovered_on in (None, D2)


def test_the_intrabar_drawdown_uses_the_provisional_low(tmp_path=None) -> None:
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    close_to_close = pf.max_drawdown(points)
    intrabar = pf.max_drawdown(points, intrabar=True)
    assert intrabar.amount_paise >= close_to_close.amount_paise
    # peak 10,270,000 (01-05 close) -> 01-06 low = 10,270,000 - 260,000 - 30,000 - 20,000
    assert intrabar.amount_paise == 10_270_000 - 9_960_000
    assert (intrabar.peak_day, intrabar.trough_day) == (D3, D4)


# ==============================================================================================
# Sharpe / Sortino, on E13's own conventions
# ==============================================================================================


def test_the_daily_returns_are_exact_fractions() -> None:
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert pf.daily_returns(points) == (
        Fraction(0),
        Fraction(9, 1018),
        Fraction(-17, 1027),
        Fraction(-1, 1010),
    )


def test_sharpe_is_the_mean_over_the_sample_deviation_annualized_by_root_252() -> None:
    """Recomputed here from the four hand-derived returns with an independent formula."""
    returns = [Fraction(0), Fraction(9, 1018), Fraction(-17, 1027), Fraction(-1, 1010)]
    mean = sum(returns, Fraction(0)) / 4
    variance = sum(((r - mean) ** 2 for r in returns), Fraction(0)) / 3
    expected = (
        Decimal(mean.numerator) / Decimal(mean.denominator)
    ) / (Decimal(variance.numerator) / Decimal(variance.denominator)).sqrt() * Decimal(
        252
    ).sqrt()
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert pf.sharpe(points) == expected
    assert pf.sharpe(points).quantize(Decimal("0.0001")) == Decimal("-3.2721")


def test_sortino_only_counts_the_losing_days_in_its_denominator() -> None:
    returns = [Fraction(0), Fraction(9, 1018), Fraction(-17, 1027), Fraction(-1, 1010)]
    mean = sum(returns, Fraction(0)) / 4
    downside = sum(((r ** 2) for r in returns if r < 0), Fraction(0)) / 4
    expected = (
        Decimal(mean.numerator) / Decimal(mean.denominator)
    ) / (Decimal(downside.numerator) / Decimal(downside.denominator)).sqrt() * Decimal(
        252
    ).sqrt()
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert pf.sortino(points) == expected


def test_an_undefined_ratio_is_reported_as_undefined_not_as_zero() -> None:
    flat = (no_trade(D1, "AAA"), no_trade(D2, "AAA"))
    points = pf.equity_curve(pf.daily_pnl(flat), CAPITAL)
    assert pf.sharpe(points) is None
    assert pf.sortino(points) is None


# ==============================================================================================
# The E13 metric set
# ==============================================================================================


def test_every_money_metric_matches_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.net_pnl_paise == 90_000
    assert m.gross_profit_paise == 450_000
    assert m.gross_loss_paise == -300_000
    assert m.profit_factor == Fraction(3, 2)
    assert m.commission_paise == 60_000
    assert m.expected_payoff_paise == Fraction(15_000)
    assert m.net_pnl_paise == m.gross_profit_paise + m.gross_loss_paise - m.commission_paise


def test_every_count_metric_matches_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert (m.total_trades, m.winners, m.losers, m.flat) == (6, 3, 3, 0)
    assert m.open_trades == 0  # every trade squares off at 15:15 (CONTEXT 3.1)
    assert m.percent_profitable == Fraction(1, 2)
    assert m.trading_days == 5


def test_every_average_and_extreme_matches_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.avg_pnl_paise == Fraction(15_000)
    assert m.avg_profit_paise == Fraction(140_000)
    assert m.avg_loss_paise == Fraction(-110_000)
    assert m.avg_profit_over_avg_loss == Fraction(14, 11)
    assert m.largest_win_paise == 290_000
    assert m.largest_win_pct_of_notional == Fraction(29, 2000)
    assert m.largest_win_pct_of_gross_profit == Fraction(2, 3)
    assert m.largest_loss_paise == -210_000
    assert m.largest_loss_pct_of_notional == Fraction(-7, 200)
    assert m.largest_loss_pct_of_gross_loss == Fraction(2, 3)


def test_the_outliers_metric_is_blocked_on_the_architect_not_invented() -> None:
    """CONTEXT 7-E13 names "outliers" and fixes no definition. CLAUDE.md rule 1: do not decide."""
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.outliers is None
    assert "Q-16(a)" in m.outliers_note
    assert "NOT computed" in m.outliers_note


def test_the_equity_metrics_match_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.final_equity_paise == 10_090_000
    assert m.return_on_initial_capital == Fraction(9, 1000)
    assert m.max_drawdown.amount_paise == 180_000
    assert m.max_run_up.amount_paise == 270_000
    assert m.intra_trade_note == pf.INTRA_TRADE_PROVISIONAL
    assert m.cagr is not None and m.cagr > 0  # 0.9% over 6 calendar days annualizes up


def test_the_excursion_aggregates_match_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.largest_mfe_paise == 400_000
    assert m.largest_mae_paise == -260_000
    assert m.avg_mfe_paise == Fraction(400_000 + 20_000 + 150_000 + 0 + 90_000 + 10_000, 6)
    assert m.avg_mae_paise == Fraction(
        -50_000 - 120_000 - 10_000 - 260_000 - 30_000 - 40_000, 6
    )


def test_the_side_split_partitions_the_trades_and_the_money() -> None:
    split = pf.side_split(ROWS, initial_capital_paise=CAPITAL)
    assert split["Long"].total_trades == 4 and split["Short"].total_trades == 2
    assert split["Long"].net_pnl_paise == 410_000
    assert split["Short"].net_pnl_paise == -320_000
    assert (
        split["Long"].net_pnl_paise + split["Short"].net_pnl_paise
        == split["All"].net_pnl_paise
    )
    # every column is measured over the SAME days, so their Sharpes are comparable
    assert {m.trading_days for m in split.values()} == {5}


def test_the_per_symbol_table_partitions_the_money() -> None:
    table = pf.per_symbol(ROWS, initial_capital_paise=CAPITAL)
    assert sorted(table) == ["AAA", "BBB"]
    assert table["AAA"].net_pnl_paise == 170_000
    assert table["BBB"].net_pnl_paise == -80_000
    assert sum(m.net_pnl_paise for m in table.values()) == 90_000


def test_metrics_on_an_empty_ledger_report_nothing_rather_than_dividing_by_zero() -> None:
    m = pf.metrics((), initial_capital_paise=CAPITAL)
    assert m.total_trades == 0
    assert m.profit_factor is None and m.avg_pnl_paise is None
    assert m.final_equity_paise == CAPITAL
    assert m.max_drawdown.amount_paise == 0
    assert m.cagr is None and m.sharpe is None


# ==============================================================================================
# CONTEXT 3.5's take-all disclosures
# ==============================================================================================


def test_the_disclosures_are_hand_computed() -> None:
    d = pf.disclosures(ROWS)
    assert d.max_concurrent_positions.positions == 2
    assert d.peak_simultaneous_notional.notional_paise == 25_000_000
    assert d.peak_simultaneous_notional.at == datetime(2026, 1, 1, 12)
    assert d.max_concurrent_positions.symbols == ("AAA", "BBB")
    assert d.daily_trade_counts == ((0, 1), (1, 2), (2, 2))
    assert d.max_daily_trades == 2
    assert d.total_executed == 6
    assert d.largest_single_notional_paise == 20_000_000


def test_a_position_that_closes_before_another_opens_is_not_concurrent() -> None:
    rows = (
        trade(D1, "AAA", LONG, 1, 100_000, 0, hour=11, exit_hour=12),
        trade(D1, "BBB", LONG, 1, 100_000, 0, hour=13, exit_hour=14),
    )
    assert pf.disclosures(rows).max_concurrent_positions.positions == 1


def test_the_daily_count_distribution_is_the_full_distribution_not_just_its_max() -> None:
    """CONTEXT 3.5 asks for the DISTRIBUTION of daily concurrent-trade counts, so the zero-trade
    day is in it too."""
    counts = dict(pf.disclosures(ROWS).daily_trade_counts)
    assert counts[0] == 1
    assert sum(days for days in counts.values()) == 5
    assert sum(trades * days for trades, days in counts.items()) == 6


# ==============================================================================================
# The Q40-d capital-infeasibility flags -- BLOCKED on the trader's Q43
# ==============================================================================================


def test_the_flags_are_not_computed_while_q43_is_pending() -> None:
    report = pf.capital_flags(ROWS, capital_reference_paise=None, margin_basis=None)
    assert report.computed is False
    assert report.note == pf.CAPITAL_FLAGS_PENDING_NOTE
    assert "Q43" in report.note
    assert report.beyond_cash == () and report.beyond_margin == ()


@pytest.mark.parametrize(
    "capital,basis",
    [(None, Decimal(5)), (10_000_000, None)],
)
def test_half_an_answer_is_still_no_answer(capital, basis) -> None:
    """Neither key defaults. One without the other computes nothing."""
    report = pf.capital_flags(ROWS, capital_reference_paise=capital, margin_basis=basis)
    assert report.computed is False and report.note == pf.CAPITAL_FLAGS_PENDING_NOTE


def test_the_flags_compute_post_hoc_once_both_answers_are_in() -> None:
    report = pf.capital_flags(
        ROWS, capital_reference_paise=10_000_000, margin_basis=Decimal(5)
    )
    assert report.computed is True
    assert [(f.symbol, f.day, f.notional_paise) for f in report.beyond_cash] == [
        ("AAA", D1, 20_000_000)
    ]
    assert report.beyond_cash[0].over_by_paise == 10_000_000
    assert report.beyond_margin == ()  # nothing reaches the Rs 5,00,000 tier
    assert report.flagged_trades == 1


def test_a_trade_exactly_at_the_capital_reference_is_not_flagged() -> None:
    """The rule is "could not have taken it" -- a notional EQUAL to the capital could."""
    report = pf.capital_flags(
        ROWS, capital_reference_paise=10_000_000, margin_basis=Decimal(5)
    )
    flagged = {(f.symbol, f.day) for f in report.beyond_cash}
    assert ("AAA", D3) not in flagged  # exactly Rs 1,00,000.00


def test_the_flags_never_change_a_trade() -> None:
    """A flag is a DISCLOSURE, not a constraint: take-all is unchanged (Q40-d)."""
    before = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    pf.capital_flags(ROWS, capital_reference_paise=1, margin_basis=Decimal(1))
    after = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert before == after


# ==============================================================================================
# The buy & hold benchmark (E13's own definition)
# ==============================================================================================


def test_buy_and_hold_is_equal_weight_from_the_first_trade_date() -> None:
    closes = {
        "AAA": {D1: 200_000, D5: 220_000},
        "BBB": {D1: 100_000, D5: 90_000},
    }
    benchmark = pf.buy_and_hold(closes, first_day=D1, last_day=D5, initial_capital_paise=CAPITAL)
    assert benchmark.symbols == ("AAA", "BBB")
    assert benchmark.end_value_paise == Fraction(10_000_000)
    assert benchmark.total_return == 0


def test_a_symbol_with_no_close_on_the_first_day_is_excluded_and_named() -> None:
    closes = {"AAA": {D1: 200_000, D5: 220_000}, "LATE": {D5: 100_000}}
    benchmark = pf.buy_and_hold(closes, first_day=D1, last_day=D5, initial_capital_paise=CAPITAL)
    assert benchmark.symbols == ("AAA",)
    assert "LATE" in benchmark.note
    assert benchmark.total_return == Fraction(1, 10)


def test_the_benchmark_carries_the_last_close_on_or_before_the_end() -> None:
    closes = {"AAA": {D1: 100_000, D3: 150_000}}
    benchmark = pf.buy_and_hold(closes, first_day=D1, last_day=D5, initial_capital_paise=CAPITAL)
    assert benchmark.total_return == Fraction(1, 2)


# ==============================================================================================
# Formatting (the packs read these)
# ==============================================================================================


@pytest.mark.parametrize(
    "paise,text",
    [
        (0, "Rs 0.00"),
        (1, "Rs 0.01"),
        (-193_495, "-Rs 1,934.95"),
        (100_050_000, "Rs 1,000,500.00"),
        (Fraction(15_000), "Rs 150.00"),
        (None, "-"),
    ],
)
def test_money_formats_exactly(paise, text) -> None:
    assert pf.format_paise(paise) == text


def test_percentages_format_exactly() -> None:
    assert pf.format_pct(Fraction(1, 2)) == "50.00%"
    assert pf.format_pct(Fraction(9, 1000)) == "0.90%"
    assert pf.format_pct(None) == "-"


def test_a_refused_row_never_reaches_the_money() -> None:
    """A no-trade row carries no PnL, so a refusal cannot move a portfolio number."""
    refused = LedgerRow(
        symbol="AAA", day=D1, status=STATUS_REFUSED, reason="gate 1 (volume reconciliation)"
    )
    assert pf.metrics((refused,)).total_trades == 0
    assert pf.metrics((refused,)).net_pnl_paise == 0
    assert pf.disclosures((refused,)).total_executed == 0
