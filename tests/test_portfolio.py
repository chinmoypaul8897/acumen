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

**Every figure below is on the E13 PRESENTATION BASIS the architect ruled on 30-Jul-2026:
ONE basis (NET of the Rs 100 round trip) over ONE population (the sign of NET).**

* winners (net > 0) 3, losers 3, flat 0 -> **% profitable = 1/2**.
* gross profit = the winners' NET sum 2,900 + 900 + 400 = **Rs 4,200.00**; gross loss = the
  losers' NET sum -1,100 - 2,100 - 100 = **-Rs 3,300.00**; profit factor 4200/3300 =
  **14/11**; net = 4,200 - 3,300 = **Rs 900.00** -- the identity `net == gross profit +
  gross loss`, with no commission term to reconcile because both pots are already net.
* expected payoff 900/6 = **Rs 150.00**; avg profit 4,200/3 = **Rs 1,400.00**; avg loss
  -3,300/3 = **-Rs 1,100.00**; avg profit / avg loss = **14/11**. With three winners and
  three losers that ratio EQUALS the profit factor -- an arithmetic consequence of the single
  basis, not a coincidence to rely on.
* **winners x avg profit = 3 x 1,400 = Rs 4,200.00 = gross profit, exactly** -- the identity a
  report reader would try, which the old mixed basis failed by Rs 4,609.60 on the pilot
  (REVIEW_9A findings Q1 and Q2).
* largest win **+Rs 2,900.00** = 29/2000 of its own Rs 200,000.00 notional and 2,900/4,200 =
  **29/42** of gross profit -- both NET; largest loss **-Rs 2,100.00** = -7/200 of its
  Rs 60,000.00 notional and -2,100/-3,300 = **7/11** of gross loss.
* the ONE before-costs line the ruling allows: profit before Rs 100/trade costs 3,000 + 1,000
  + 500 = **Rs 4,500.00**, loss before costs -1,000 - 2,000 = **-Rs 3,000.00**, commission
  6 x 100 = **Rs 600.00**, and 4,500 - 3,000 - 600 = **Rs 900.00** = the net.
* daily net: 01-01 **+Rs 1,800.00**, 01-02 **0**, 01-05 **+Rs 900.00**, 01-06
  **-Rs 1,700.00**, 01-07 **-Rs 100.00**. On capital Rs 100,000.00 the equity closes
  101,800 / 101,800 / 102,700 / 101,000 / 100,900.
* max drawdown (close-to-close) = 102,700 (01-05) -> 100,900 (01-07) = **Rs 1,800.00**,
  18/1027 of the peak, duration 2 observations, never recovered. Max run-up runs from the
  OPENING capital 100,000 to 102,700 (01-05) = **Rs 2,700.00**, 27/1000, duration 3
  observations (the opening counts as the one before the first day).
* daily returns 0, 9/1018, -17/1027, -1/1010 -- four observations, so Sharpe and Sortino exist.
* concurrency: 01-01 holds two positions worth 200,000 + 50,000 = **Rs 250,000.00** at once,
  01-06 two worth 100,000 -- so max concurrent **2** and peak simultaneous notional
  **Rs 250,000.00**. Daily trade counts: two days of 2, two days of 1, one day of 0.
* buy & hold: AAA 2,000 -> 2,200 (+10%), BBB 1,000 -> 900 (-10%), equal weight
  Rs 50,000 each -> 55,000 + 45,000 = **Rs 100,000.00**, total return **0**.
* capital flags at capital_reference Rs 100,000.00 and margin basis 5: exactly ONE trade is
  beyond cash (trade 1 at Rs 200,000.00); trade 3 sits EXACTLY at Rs 100,000.00 and is NOT
  flagged (the rule is "exceeds"); nothing reaches the Rs 500,000.00 margin tier.

**Q-16(a) TUKEY FENCES on this same six-trade ledger, hand-computed** (the architect's ruling
of 30-Jul-2026: outliers are the trades whose NET PnL falls outside
`[Q1 - 3/2 x IQR, Q3 + 3/2 x IQR]`; quartiles by linear interpolation between order statistics,
R/numpy type 7, exact in Fractions):

* the six net PnLs in paise, sorted: **-210,000 / -110,000 / -10,000 / +40,000 / +90,000 /
  +290,000** (n = 6).
* Q1: position (n-1) x 1/4 = 5/4 -> between x[1] and x[2], one quarter of the way:
  -110,000 + (1/4)(-10,000 + 110,000) = **-85,000**.
* Q3: position (n-1) x 3/4 = 15/4 -> between x[3] and x[4], three quarters of the way:
  40,000 + (3/4)(90,000 - 40,000) = **+77,500**.
* IQR = 77,500 - (-85,000) = **162,500**; 3/2 x IQR = **243,750**.
* fences = [-85,000 - 243,750, 77,500 + 243,750] = **[-328,750, +321,250]**.
* every one of the six sits INSIDE that band, so this ledger has **zero outliers** -- which is
  the honest answer for it, and the reason the second fixture below exists.

**The nine-trade OUTLIER fixture** (:func:`outlier_rows`), hand-computed the same way, built so
that both tails fire:

| net PnL (paise) | -900,000 | -80,000 | -60,000 | -40,000 | -20,000 | 0 | +20,000 | +40,000 | +1,000,000 |
|---|---|---|---|---|---|---|---|---|---|

* n = 9, so (n-1) x 1/4 = 2 and (n-1) x 3/4 = 6 land EXACTLY on order statistics -- no
  interpolation, which makes the fixture checkable without trusting the estimator:
  **Q1 = -60,000**, **Q3 = +20,000**, **IQR = 80,000**, 3/2 x IQR = **120,000**.
* fences = **[-180,000, +140,000]**; outliers = **-900,000** and **+1,000,000** -- count **2**,
  summed net **+100,000** (Rs 1,000.00).
* net-basis gross profit = 20,000 + 40,000 + 1,000,000 = **1,060,000**; net-basis gross loss =
  -900,000 - 80,000 - 60,000 - 40,000 - 20,000 = **-1,100,000** (the zero row is FLAT and is in
  neither).
* share of gross profit = 1,000,000 / 1,060,000 = **50/53**; share of gross loss =
  -900,000 / -1,100,000 = **9/11**.

**Q-16(b) THE 15-MINUTE PATH FIXTURE** (:func:`path_rows`), worked by hand step by step. The
architect's ruling: "every open position marked to its 15-min candle closes (exit candles at
their exit levels), summed across positions". Two symbols, OVERLAPPING, and the first of them
exits MID-PATH at a LEVEL its candle ran past -- which is the case that separates a correct
path from one marked at candle closes. Capital Rs 1,00,000.00 = 10,000,000 paise, cost 10,000
paise per trade, charged from the ENTRY mark (decision B194).

*Trade A -- AAA, LONG, 100 shares, entry Rs 2,000.00 (200,000 paise) on the candle closing
12:00; target Rs 2,030.00 (203,000); the 12:45 candle blows through it and CLOSES at
Rs 2,020.00 (202,000), so the fill is the LEVEL 203,000.* Marks, PnL = (mark - 200,000) x 100
- 10,000:

| 12:00 close 200,000 | 12:15 close 201,000 | 12:30 close 199,000 | 12:45 LEVEL 203,000 |
|---|---|---|---|
| **-10,000** | **+90,000** | **-110,000** | **+290,000** |

The last mark reproduces the ledger's net (+Rs 2,900.00) exactly -- the invariant. Marked at
the candle's CLOSE instead it would read +190,000, which is the Rs 1,000.00 error the level
rule exists to prevent.

*Trade B -- BBB, SHORT, 50 shares, entry Rs 1,000.00 (100,000) on the candle closing 12:15;
squared off at the 13:15 candle's close Rs 996.00 (99,600).* Marks, PnL =
(100,000 - mark) x 50 - 10,000:

| 12:15 close 100,000 | 12:30 close 101,000 | 12:45 close 100,500 | 13:00 close 99,000 | 13:15 EXIT 99,600 |
|---|---|---|---|---|
| **-10,000** | **-60,000** | **-35,000** | **+40,000** | **+10,000** |

Day net = 290,000 + 10,000 = **+300,000** (Rs 3,000.00). **The portfolio path**, opening equity
10,000,000, each stamp summing every position open at it (a closed one contributes its realized
net, an unopened one nothing):

| stamp | A | B | equity | open |
|---|---|---|---|---|
| 12:00 | -10,000 | - | **9,990,000** | 1 |
| 12:15 | +90,000 | -10,000 | **10,080,000** | 2 |
| 12:30 | -110,000 | -60,000 | **9,830,000** | 2 |
| 12:45 | +290,000 (closed) | -35,000 | **10,255,000** | 1 |
| 13:00 | +290,000 | +40,000 | **10,330,000** | 1 |
| 13:15 | +290,000 | +10,000 | **10,300,000** | 0 |
| day close | | | **10,300,000** | 0 |

* the day's last observation equals the day's CLOSING equity (10,000,000 + 300,000) -- the
  invariant that ties this path to the daily curve.
* **max drawdown on the path**: the running peak starts at the opening capital, is raised to
  10,080,000 at 12:15, and the 12:30 observation falls to 9,830,000 -> **250,000**
  (Rs 2,500.00), 25/1008 of that peak, 1 observation, RECOVERED at 12:45 (10,255,000 is the
  first observation back at or above 10,080,000).
* **max run-up on the path**: the running trough drops to 9,830,000 at 12:30 and the peak
  after it is 10,330,000 at 13:00 -> **500,000** (Rs 5,000.00), 50/983, 2 observations, and it
  never falls back to the trough, so `recovered` is None.
* the CLOSE-TO-CLOSE forms of the same day see none of this: one day, equity 10,300,000 above
  the opening capital, so the daily drawdown is **0** and the daily run-up is 300,000. That
  gap -- Rs 2,500.00 against Rs 0.00 -- is exactly what E13's intra-trade form is for.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen.aggregate import Bar
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


def test_the_retired_worst_case_band_is_gone_from_the_equity_curve() -> None:
    """**Q-16(b) RULED (architect, 30-Jul-2026): the coinciding worst case is RETIRED** -- it
    invented co-timing, which is an assumption. The daily curve carries closing equity and
    nothing else; the intraday question is answered by the true 15-minute path instead."""
    point = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)[0]
    assert not hasattr(point, "low_equity_paise")
    assert not hasattr(point, "high_equity_paise")
    assert not hasattr(pf, "INTRA_TRADE_PROVISIONAL")
    assert "PROVISIONAL" not in pf.INTRADAY_PATH_LIMIT
    assert "Q-16(b)" in pf.INTRADAY_PATH_LIMIT


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


def test_the_six_trade_run_up_is_never_given_back_inside_the_window() -> None:
    """E13's "same forms" (REVIEW_9A finding Q5): the run-up now reports the day its rise was
    handed back. This ledger's equity never returns to the opening capital, so the honest
    answer is None -- meaningfully empty rather than structurally dead."""
    points = pf.equity_curve(pf.daily_pnl(ROWS), CAPITAL)
    assert pf.max_run_up(points).recovered_on is None
    assert min(point.equity_paise for point in points) > CAPITAL


def test_the_capital_denominators_are_guarded_like_every_other_ratio() -> None:
    """REVIEW_9A finding C2: the two divisions that used to raise instead of returning None."""
    degenerate = pf.metrics(ROWS, initial_capital_paise=0)
    assert degenerate.return_on_initial_capital is None
    assert degenerate.cagr is None
    assert pf.buy_and_hold(
        {"AAA": {D1: 200_000}}, first_day=D1, last_day=D5, initial_capital_paise=0
    ).total_return is None


def test_a_drawdown_that_recovers_names_the_day_it_recovered() -> None:
    rows = (
        trade(D1, "AAA", LONG, 1, 100_000, -100_000),
        trade(D2, "AAA", LONG, 1, 100_000, 500_000),
    )
    points = pf.equity_curve(pf.daily_pnl(rows), CAPITAL)
    excursion = pf.max_drawdown(points)
    assert excursion.amount_paise == 0 or excursion.recovered_on in (None, D2)


def test_the_intrabar_switch_is_gone_from_both_daily_excursions() -> None:
    """The retired construction's entry point. Both daily forms are close-to-close only now."""
    import inspect

    for name in ("max_drawdown", "max_run_up"):
        assert "intrabar" not in inspect.signature(getattr(pf, name)).parameters


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
    assert m.gross_profit_paise == 420_000  # the WINNERS' net sum (E13 basis ruling)
    assert m.gross_loss_paise == -330_000  # the LOSERS' net sum
    assert m.profit_factor == Fraction(14, 11)
    assert m.commission_paise == 60_000
    assert m.expected_payoff_paise == Fraction(15_000)
    # one basis: no commission term to reconcile, because both pots are already net
    assert m.net_pnl_paise == m.gross_profit_paise + m.gross_loss_paise
    # the before-costs pair, which exists for exactly one labelled line
    assert m.before_cost_profit_paise == 450_000
    assert m.before_cost_loss_paise == -300_000
    assert (
        m.before_cost_profit_paise + m.before_cost_loss_paise - m.commission_paise
        == m.net_pnl_paise
    )
    assert m.basis == pf.E13_BASIS


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
    assert m.largest_win_pct_of_gross_profit == Fraction(29, 42)  # NET / NET
    assert m.largest_loss_paise == -210_000
    assert m.largest_loss_pct_of_notional == Fraction(-7, 200)
    assert m.largest_loss_pct_of_gross_loss == Fraction(7, 11)  # NET / NET
    # the identity the single basis buys: winners x avg profit IS gross profit
    assert m.winners * m.avg_profit_paise == m.gross_profit_paise
    assert m.losers * m.avg_loss_paise == m.gross_loss_paise


def test_the_outliers_metric_carries_its_definition_beside_the_number() -> None:
    """Q-16(a) RULED (architect, 30-Jul-2026): Tukey fences on net PnL. The ruling requires
    the definition to be printed beside the figure, so the record carries it."""
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.outliers is not None
    assert m.outliers.definition == pf.OUTLIER_DEFINITION == m.outliers_note
    assert "Q-16(a)" in m.outliers_note
    assert "Tukey" in m.outliers_note
    assert not hasattr(pf, "OUTLIERS_NOT_COMPUTED")


def test_the_equity_metrics_match_the_hand_computation() -> None:
    m = pf.metrics(ROWS, initial_capital_paise=CAPITAL)
    assert m.final_equity_paise == 10_090_000
    assert m.return_on_initial_capital == Fraction(9, 1000)
    assert m.max_drawdown.amount_paise == 180_000
    assert m.max_run_up.amount_paise == 270_000
    assert m.intraday_note == pf.INTRADAY_PATH_NOT_SUPPLIED  # no path handed to it
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
# Q-16(b) -- the TRUE 15-minute portfolio equity path (architect's ruling, 30-Jul-2026)
# ==============================================================================================


def at(hour: int, minute: int) -> datetime:
    return datetime.combine(D1, datetime.min.time()) + timedelta(hours=hour, minutes=minute)


def path_trade(
    symbol: str,
    side: str,
    qty: int,
    entry_paise: int,
    exit_paise: int,
    entry_stamp: datetime,
    exit_stamp: datetime,
) -> LedgerRow:
    """One executed row whose money is CONSISTENT with its prices -- the path's own fixture."""
    gross = (
        (exit_paise - entry_paise) * qty
        if side == LONG
        else (entry_paise - exit_paise) * qty
    )
    return LedgerRow(
        symbol=symbol,
        day=D1,
        status=STATUS_EVALUATED,
        reason="evaluated",
        side=side,
        outcome="entered",
        consumed=True,
        signalled=True,
        executed=True,
        entry_paise=entry_paise,
        entry_close_stamp=entry_stamp,
        exit_kind=EXIT_TARGET,
        exit_paise=exit_paise,
        exit_close_stamp=exit_stamp,
        qty=qty,
        notional_paise=qty * entry_paise,
        gross_pnl_paise=gross,
        cost_paise=COST,
        net_pnl_paise=gross - COST,
    )


def path_rows() -> tuple[LedgerRow, ...]:
    """The two OVERLAPPING trades of the module docstring's 15-minute path fixture."""
    return (
        path_trade("AAA", LONG, 100, 200_000, 203_000, at(12, 0), at(12, 45)),
        path_trade("BBB", SHORT, 50, 100_000, 99_600, at(12, 15), at(13, 15)),
    )


def path_bars() -> dict[str, tuple[Bar, ...]]:
    """The 15-minute candles the marks are taken from, OPEN-stamped (CONTEXT 7-E12).

    AAA's exit candle CLOSES at 202,000 while the trade filled at its 203,000 level -- the
    discriminating case.
    """

    def bar(hour: int, minute: int, close: int, high: int | None = None) -> Bar:
        stamp = at(hour, minute) - timedelta(minutes=15)  # open-stamp; closes at (hour, minute)
        return Bar(
            stamp=stamp,
            open_paise=close,
            high_paise=high if high is not None else close,
            low_paise=close,
            close_paise=close,
            volume=1,
        )

    return {
        "AAA": (
            bar(12, 0, 200_000),
            bar(12, 15, 201_000),
            bar(12, 30, 199_000),
            bar(12, 45, 202_000, high=204_000),  # ran PAST the 203,000 target and closed under
        ),
        "BBB": (
            bar(12, 15, 100_000),
            bar(12, 30, 101_000),
            bar(12, 45, 100_500),
            bar(13, 0, 99_000),
            bar(13, 15, 99_600),
        ),
    }


def built_paths() -> tuple[bt.TradePath, ...]:
    bars = path_bars()
    return bt.assemble_trade_paths(path_rows(), bars_for=lambda symbol, day: bars[symbol])


def test_the_marks_run_from_the_entry_candle_to_the_exit_candles_LEVEL() -> None:
    """The hand-computed mark table, both trades, straight from the docstring."""
    long_path, short_path = built_paths()

    assert [(m.stamp.strftime("%H:%M"), m.price_paise) for m in long_path.marks] == [
        ("12:00", 200_000),
        ("12:15", 201_000),
        ("12:30", 199_000),
        ("12:45", 203_000),  # the LEVEL, not the 202,000 candle close
    ]
    assert [pf.mark_pnl_paise(long_path, m.price_paise) for m in long_path.marks] == [
        -10_000,
        90_000,
        -110_000,
        290_000,
    ]
    assert [pf.mark_pnl_paise(short_path, m.price_paise) for m in short_path.marks] == [
        -10_000,
        -60_000,
        -35_000,
        40_000,
        10_000,
    ]


def test_marking_the_exit_candle_at_its_close_would_have_been_wrong_by_a_thousand_rupees() -> None:
    """Why the exit LEVEL rule exists: a target fills at its level even when the candle ran
    past it (CONTEXT 3.4-5), so a close-marked exit reports money the trade never made."""
    long_path = built_paths()[0]
    assert pf.mark_pnl_paise(long_path, 202_000) == 190_000  # the candle's close
    assert pf.mark_pnl_paise(long_path, 203_000) == 290_000  # the fill level == the ledger net
    assert long_path.net_pnl_paise == 290_000


def test_every_assembled_path_reconciles_with_the_ledgers_own_money() -> None:
    """The invariant that makes the path trustworthy: the last mark reproduces the net PnL."""
    assert all(pf.path_reconciles(path) for path in built_paths())


def test_the_portfolio_path_is_the_hand_computed_table() -> None:
    rows = path_rows()
    series = pf.daily_pnl(rows)
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)

    assert [
        (point.stamp.strftime("%H:%M") if point.stamp else "close", point.equity_paise, point.open_positions)
        for point in points
    ] == [
        ("12:00", 9_990_000, 1),
        ("12:15", 10_080_000, 2),
        ("12:30", 9_830_000, 2),
        ("12:45", 10_255_000, 1),
        ("13:00", 10_330_000, 1),
        ("13:15", 10_300_000, 0),
        ("close", 10_300_000, 0),
    ]


def test_the_days_last_path_point_equals_the_days_closing_equity() -> None:
    """The invariant that ties the path to the daily curve: nothing straddles a day, because
    CONTEXT 3.1 squares everything off at 15:15."""
    rows = path_rows()
    series = pf.daily_pnl(rows)
    curve = pf.equity_curve(series, CAPITAL)
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)
    closes = {point.day: point.equity_paise for point in points if point.stamp is None}
    assert closes == {point.day: point.equity_paise for point in curve}


def test_the_path_drawdown_and_run_up_are_hand_computed() -> None:
    series = pf.daily_pnl(path_rows())
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)

    fall = pf.path_max_drawdown(points, initial_capital_paise=CAPITAL)
    assert fall.amount_paise == 250_000
    assert fall.pct == Fraction(25, 1008)
    assert fall.peak is not None and fall.peak.stamp == at(12, 15)
    assert fall.trough is not None and fall.trough.stamp == at(12, 30)
    assert fall.observations == 1
    assert fall.recovered is not None and fall.recovered.stamp == at(12, 45)
    assert fall.note == pf.INTRADAY_PATH_LIMIT

    rise = pf.path_max_run_up(points, initial_capital_paise=CAPITAL)
    assert rise.amount_paise == 500_000
    assert rise.pct == Fraction(50, 983)
    assert rise.trough is not None and rise.trough.stamp == at(12, 30)
    assert rise.peak is not None and rise.peak.stamp == at(13, 0)
    assert rise.observations == 2
    assert rise.recovered is None  # it never falls back to the trough


def test_the_daily_close_to_close_forms_cannot_see_the_intraday_fall() -> None:
    """Rs 2,500.00 on the path against Rs 0.00 on the daily curve -- which is the whole reason
    E13 asks for both forms."""
    series = pf.daily_pnl(path_rows())
    curve = pf.equity_curve(series, CAPITAL)
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)
    assert pf.max_drawdown(curve).amount_paise == 0
    assert pf.path_max_drawdown(points, initial_capital_paise=CAPITAL).amount_paise == 250_000
    assert pf.max_run_up(curve).amount_paise == 300_000


def test_a_day_that_traded_nothing_still_appears_on_the_path() -> None:
    """So that a drawdown can span it -- the path is not a trade log."""
    rows = path_rows() + (no_trade(D2, "AAA"), no_trade(D3, "AAA"))
    series = pf.daily_pnl(rows)
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)
    days = [point.day for point in points if point.stamp is None]
    assert days == [D1, D2, D3]
    assert points[-1].equity_paise == 10_300_000


def test_the_metric_set_reports_both_forms_and_refuses_to_invent_a_path() -> None:
    rows = path_rows()
    with_path = pf.metrics(rows, initial_capital_paise=CAPITAL, paths=built_paths())
    without = pf.metrics(rows, initial_capital_paise=CAPITAL)

    assert with_path.max_drawdown.amount_paise == 0  # close-to-close, unchanged
    assert with_path.intraday_max_drawdown is not None
    assert with_path.intraday_max_drawdown.amount_paise == 250_000
    assert with_path.intraday_max_run_up is not None
    assert with_path.intraday_max_run_up.amount_paise == 500_000
    assert with_path.intraday_observations == 7
    assert with_path.intraday_note == pf.INTRADAY_PATH_LIMIT

    assert without.intraday_max_drawdown is None and without.intraday_max_run_up is None
    assert without.intraday_observations == 0
    assert without.intraday_note == pf.INTRADAY_PATH_NOT_SUPPLIED
    assert "assembled in the I/O layer" in without.intraday_note


def test_each_side_column_gets_its_own_path_not_a_slice_of_the_portfolios() -> None:
    split = pf.side_split(path_rows(), initial_capital_paise=CAPITAL, paths=built_paths())
    assert split["Long"].intraday_max_drawdown is not None
    assert split["Short"].intraday_max_drawdown is not None
    # AAA alone: marks 9,990,000 / 10,090,000 / 9,890,000 / 10,290,000 -- the fall from the
    # 12:15 peak is 200,000, which the PORTFOLIO path never shows, because BBB was open too.
    assert split["Long"].intraday_max_drawdown.amount_paise == 200_000
    # BBB alone: 9,990,000 / 9,940,000 / 9,965,000 / 10,040,000 / 10,010,000 -- 60,000 below
    # the opening capital at 12:30.
    assert split["Short"].intraday_max_drawdown.amount_paise == 60_000


def test_the_path_carries_no_float_anywhere() -> None:
    series = pf.daily_pnl(path_rows())
    points = pf.intraday_equity_path(series, built_paths(), initial_capital_paise=CAPITAL)
    assert all(isinstance(point.equity_paise, int) for point in points)
    fall = pf.path_max_drawdown(points, initial_capital_paise=CAPITAL)
    assert isinstance(fall.amount_paise, int) and isinstance(fall.pct, Fraction)


# ==============================================================================================
# Q-16(a) -- outliers by Tukey fences (architect's ruling, 30-Jul-2026)
# ==============================================================================================


def outlier_rows() -> tuple[LedgerRow, ...]:
    """The nine-trade fixture hand-computed in this module's docstring: both tails fire."""
    nets = (-900_000, -80_000, -60_000, -40_000, -20_000, 0, 20_000, 40_000, 1_000_000)
    return tuple(
        trade(D1 + timedelta(days=index), f"S{index}", LONG, 10, 100_000, net + COST)
        for index, net in enumerate(nets)
    )


def test_the_quartiles_are_exact_fractions_by_linear_interpolation() -> None:
    """Decision B195: R/numpy type 7. Both hand-computed cases -- the six-trade ledger, where
    the position lands BETWEEN two order statistics, and the nine-trade one, where it lands
    exactly ON them."""
    six = [-210_000, -110_000, -10_000, 40_000, 90_000, 290_000]
    assert pf.quantile(six, Fraction(1, 4)) == Fraction(-85_000)
    assert pf.quantile(six, Fraction(3, 4)) == Fraction(77_500)

    nine = [-900_000, -80_000, -60_000, -40_000, -20_000, 0, 20_000, 40_000, 1_000_000]
    assert pf.quantile(nine, Fraction(1, 4)) == Fraction(-60_000)
    assert pf.quantile(nine, Fraction(3, 4)) == Fraction(20_000)
    # unsorted input is sorted first -- the estimator is over ORDER statistics
    assert pf.quantile(list(reversed(nine)), Fraction(1, 4)) == Fraction(-60_000)
    assert pf.quantile([], Fraction(1, 2)) is None
    assert pf.quantile([7], Fraction(3, 4)) == Fraction(7)


def test_the_six_trade_ledger_has_no_outliers_and_says_so_with_its_fences() -> None:
    """Hand-computed in the module docstring: fences [-328,750, +321,250], nothing outside."""
    found = pf.outliers(ROWS)
    assert found.population == 6
    assert found.q1_paise == Fraction(-85_000)
    assert found.q3_paise == Fraction(77_500)
    assert found.iqr_paise == Fraction(162_500)
    assert found.lower_fence_paise == Fraction(-328_750)
    assert found.upper_fence_paise == Fraction(321_250)
    assert found.count == 0 and found.net_paise == 0
    assert found.trades == ()
    assert found.share_of_gross_profit == 0 and found.share_of_gross_loss == 0


def test_the_nine_trade_fixture_reproduces_the_hand_computed_fences_and_both_tails() -> None:
    rows = outlier_rows()
    found = pf.outliers(rows)
    assert found.population == 9
    assert (found.q1_paise, found.q3_paise, found.iqr_paise) == (
        Fraction(-60_000),
        Fraction(20_000),
        Fraction(80_000),
    )
    assert found.lower_fence_paise == Fraction(-180_000)
    assert found.upper_fence_paise == Fraction(140_000)
    assert found.count == 2
    assert found.net_paise == 100_000
    assert (found.above_count, found.above_net_paise) == (1, 1_000_000)
    assert (found.below_count, found.below_net_paise) == (1, -900_000)
    assert found.share_of_gross_profit == Fraction(50, 53)
    assert found.share_of_gross_loss == Fraction(9, 11)
    assert [(item.net_paise, item.side_of_fence) for item in found.trades] == [
        (-900_000, "below"),
        (1_000_000, "above"),
    ]


def test_a_trade_exactly_on_a_fence_is_not_an_outlier() -> None:
    """The same "exceeds" convention every other threshold in this repo uses."""
    rows = outlier_rows()
    on_the_fence = trade(D5, "EDGE", LONG, 10, 100_000, 140_000 + COST)  # net == upper fence
    found = pf.outliers(rows[:-1] + (on_the_fence,))
    assert found.upper_fence_paise is not None
    assert Fraction(140_000) <= found.upper_fence_paise
    assert all(item.net_paise != 140_000 for item in found.trades)


def test_the_outlier_population_is_executed_trades_only() -> None:
    """A refused day has no net PnL to be an outlier of, and must not enter the quartiles."""
    refused = LedgerRow(
        symbol="ZZZ", day=D1, status=STATUS_REFUSED, reason="gate 1 (volume reconciliation)"
    )
    assert pf.outliers(outlier_rows() + (refused,)) == pf.outliers(outlier_rows())
    assert pf.outliers((refused,)).population == 0
    assert pf.outliers(()).count == 0
    assert pf.outliers(()).definition == pf.OUTLIER_DEFINITION


def test_the_fence_arithmetic_carries_no_float() -> None:
    """CONTEXT 7-E11: the 1.5 multiplier is Fraction(3, 2), never 1.5."""
    found = pf.outliers(outlier_rows())
    for value in (
        found.q1_paise,
        found.q3_paise,
        found.iqr_paise,
        found.lower_fence_paise,
        found.upper_fence_paise,
    ):
        assert isinstance(value, Fraction)
    assert pf.TUKEY_MULTIPLIER == Fraction(3, 2)


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
    assert pf.metrics((refused,), initial_capital_paise=CAPITAL).total_trades == 0
    assert pf.metrics((refused,), initial_capital_paise=CAPITAL).net_pnl_paise == 0
    assert pf.disclosures((refused,)).total_executed == 0
