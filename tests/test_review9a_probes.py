"""REVIEW_9A reviewer probes -- kept in the repo per the persona process (step 4).

These close holes the chunk-9A build left open. Nothing here weakens or replaces an existing
test; every assertion is new.

**FLIPPED by the chunk-9A fix session (2026-07-30).** Six of these probes were written to PIN A
DEFECT rather than assert correct behaviour -- the E13 basis pair, the mixed largest-win line,
the lost drawdown recovery date, the dead run-up recovery field and the unguarded capital
division -- with the instruction "flip this when it is fixed". The architect's Q-16 and E13
rulings and REVIEW_9A's conditions have now been executed, so each of those probes asserts the
RULE instead, citing the ruling, and its docstring records what it used to pin. That is the
tripwire working as designed: the defect could not be fixed silently, and the rule cannot now
regress silently either.

**The E13 basis fixture**, hand-computed here before coding -- four executed trades, cost
Rs 100.00 = 10,000 paise each. Trade 3 is the discriminating row: it made money BEFORE the
round trip and lost it after.

| # | before costs | net | in gross_profit? | counted a WINNER? |
|---|---|---|---|---|
| 1 | +3,000.00 | +2,900.00 | yes | yes |
| 2 | +1,000.00 |   +900.00 | yes | yes |
| 3 |    +40.00 |    -60.00 | **no** | **no** |
| 4 | -2,000.00 | -2,100.00 | no  | no |

**Recomputed on the architect's E13 PRESENTATION BASIS (30-Jul-2026), which these probes now
assert instead of pinning the defect they were written for:**

* gross profit = the WINNERS' net sum 2,900 + 900 = **Rs 3,800.00** over TWO rows
* winners = **2**; avg profit = 3,800/2 = **Rs 1,900.00**
* winners x avg profit = **Rs 3,800.00 == gross profit** -- the identity a reader would try,
  which under the old mixed basis failed by Rs 240.00 (Rs 200.00 of winners' commission plus
  trade 3's Rs 40.00 of membership)
* gross loss = -60.00 - 2,100.00 = **-Rs 2,160.00**; net = 3,800 - 2,160 = **Rs 1,640.00**
* the before-costs pair, for the single labelled line: +Rs 4,040.00 and -Rs 2,000.00, and
  4,040 - 2,000 - 400 (four round trips) = **Rs 1,640.00** = the net

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


def test_the_gross_profit_population_is_the_winner_population() -> None:
    """**FLIPPED (REVIEW_9A finding Q1 + Q2, closed by the architect's E13 basis ruling).**

    The probe used to pin the defect: `gross_profit` counted rows by the sign of GROSS while
    `winners` counted them by the sign of NET, so two adjacent numbers described different
    trades. The ruling fixes ONE population -- the sign of NET -- and this now asserts it.
    Trade 3 (+Rs 40.00 before costs, -Rs 60.00 after) is the row that used to sit in one set
    and not the other; it is now a loser on both counts."""
    rows = basis_rows()
    m = pf.metrics(rows, initial_capital_paise=CAPITAL)

    net_positive = [r for r in rows if r.net_pnl_paise > 0]
    assert len(net_positive) == 2 and m.winners == 2
    assert m.gross_profit_paise == 380_000  # the WINNERS' net sum, Rs 3,800.00
    assert m.gross_profit_paise == sum(r.net_pnl_paise for r in net_positive)
    assert m.gross_loss_paise == -216_000  # CCC's -60 and DDD's -2,100, both net
    assert m.percent_profitable == Fraction(2, 4)
    # the discriminating row is a LOSER on the one basis that exists now:
    ccc = next(r for r in rows if r.symbol == "CCC")
    assert ccc.gross_pnl_paise > 0 > ccc.net_pnl_paise
    assert ccc.net_pnl_paise in [r.net_pnl_paise for r in rows if r.net_pnl_paise < 0]
    assert m.net_pnl_paise == m.gross_profit_paise + m.gross_loss_paise


def test_winners_times_avg_profit_equals_gross_profit() -> None:
    """**FLIPPED (REVIEW_9A finding Q1, the arithmetic).** The identity a report reader would
    try used to fail by two terms -- the winners' commission (BASIS) and the gross of every
    gross-positive row the winner set excluded (MEMBERSHIP). On the ruled basis both terms are
    zero by construction, and the two old terms are asserted here to be exactly what the
    conversion removed."""
    rows = basis_rows()
    m = pf.metrics(rows, initial_capital_paise=CAPITAL)

    assert m.avg_profit_paise == Fraction(190_000)  # Rs 1,900.00, a NET average
    assert m.winners * m.avg_profit_paise == m.gross_profit_paise == 380_000
    assert m.losers * m.avg_loss_paise == m.gross_loss_paise

    # what the old basis added on top, now provably absent from the reported figure:
    old_basis_term = m.winners * COST
    old_membership_term = sum(
        r.gross_pnl_paise for r in rows if r.gross_pnl_paise > 0 and r.net_pnl_paise <= 0
    )
    assert old_basis_term == 20_000 and old_membership_term == 4_000
    assert m.before_cost_profit_paise == m.gross_profit_paise + old_basis_term + old_membership_term
    assert m.before_cost_profit_paise == 404_000  # printed ONCE, labelled, nowhere else


def test_the_largest_win_line_is_net_on_every_one_of_its_three_numbers() -> None:
    """**FLIPPED (REVIEW_9A finding Q4).** The line used to print three numbers on two bases
    inside one parenthesis: a NET amount, a NET percent-of-notional and a GROSS share of a
    GROSS pot. All three are NET now."""
    rows = basis_rows()
    m = pf.metrics(rows, initial_capital_paise=CAPITAL)
    best = max(rows, key=lambda r: r.net_pnl_paise)

    assert m.largest_win_paise == best.net_pnl_paise == 290_000
    assert m.largest_win_pct_of_notional == Fraction(290_000, 1_000_000)  # NET / notional
    assert m.largest_win_pct_of_gross_profit == Fraction(290_000, 380_000)  # NET / NET
    # the old mixed figure -- that trade's GROSS over the old GROSS pot -- is gone:
    assert m.largest_win_pct_of_gross_profit != Fraction(300_000, 404_000)

    # and the loss line mirrors it, so its share of the loss pot is a NET ratio too
    worst = min(rows, key=lambda r: r.net_pnl_paise)
    assert m.largest_loss_paise == worst.net_pnl_paise == -210_000
    assert m.largest_loss_pct_of_gross_loss == Fraction(-210_000, -216_000)


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


def test_a_drawdown_whose_peak_is_the_opening_capital_keeps_its_recovery_date() -> None:
    """**FLIPPED -- REVIEW_9A finding Q3 is FIXED.**

    This probe used to pin the defect: decision B185 makes ``peak_day is None`` a first-class
    case meaning "the run's opening capital", and a strategy that goes down from its first day
    lands there -- but `_first_recovery` only learned the peak equity from a point whose ``day``
    equalled ``peak_day``, so no point ever matched and the report said "recovered never" for a
    drawdown that demonstrably recovered. The level is now resolved before the walk.

    Here equity falls to 92,000 and is back above the opening 100,000 two days later."""
    points = _points([-500_000, -300_000, +900_000, +100_000])
    fall = pf.max_drawdown(points)

    assert fall.peak_day is None  # B185: the peak IS the opening capital
    assert fall.amount_paise == 800_000
    assert fall.trough_day == DAY + timedelta(days=1)
    assert points[2].equity_paise > CAPITAL  # the equity really does recover...
    assert fall.recovered_on == DAY + timedelta(days=2)  # ...and the metric says which day

    # and a run that never gets back above its opening capital still reports None, so the
    # fix did not turn "never recovered" into a date that is always there:
    under_water = pf.max_drawdown(_points([-500_000, -300_000, +100_000]))
    assert under_water.peak_day is None and under_water.recovered_on is None


def test_the_max_run_up_reports_when_its_rise_was_given_back() -> None:
    """**FLIPPED -- REVIEW_9A finding Q5 is FIXED.**

    E13 asks for run-ups in the "same forms" as drawdowns. `max_drawdown` filled
    `recovered_on`; `max_run_up` never did, on any input, so the field was structurally dead
    rather than meaningfully empty. It is now the mirror: the first day AFTER the peak whose
    closing equity falls back to the trough level -- the day the rise was given back."""
    # rises from the opening capital to +300,000 on day 3, then hands it all back on day 4:
    given_back = pf.max_run_up(_points([+100_000, +100_000, +100_000, -300_000]))
    assert given_back.trough_day is None  # the trough IS the opening capital
    assert given_back.amount_paise == 300_000
    assert given_back.peak_day == DAY + timedelta(days=2)
    assert given_back.recovered_on == DAY + timedelta(days=3)

    # a rise that is never given back still reports None -- meaningfully empty, not dead:
    kept = pf.max_run_up(_points([+100_000, +100_000, +100_000]))
    assert kept.amount_paise == 300_000 and kept.recovered_on is None


# ==============================================================================================
# Division guards
# ==============================================================================================


def test_metrics_guard_the_initial_capital_like_every_other_ratio() -> None:
    """**FLIPPED -- REVIEW_9A finding C2 is FIXED.**

    This used to pin the two divisions that raised `ZeroDivisionError` where every other ratio
    in the module returned None (`_ratio`, `profit_factor`, `_pct_of_notional`, the drawdown
    percent). Both now return None, so the module keeps its one property: an undefined ratio is
    reported as undefined and never as an exception or a zero."""
    m = pf.metrics(basis_rows(), initial_capital_paise=0)
    assert m.return_on_initial_capital is None
    assert m.net_pnl_paise == 164_000  # the money is unaffected by the degenerate capital

    benchmark = pf.buy_and_hold(
        {"AAA": {DAY: 100_000}}, first_day=DAY, last_day=DAY, initial_capital_paise=0
    )
    assert benchmark.total_return is None


def test_every_other_ratio_returns_none_instead_of_dividing_by_zero() -> None:
    """The contrast that makes the probe above a finding rather than a style note."""
    empty = pf.metrics((), initial_capital_paise=CAPITAL)
    assert empty.profit_factor is None
    assert empty.avg_pnl_paise is None
    assert empty.percent_profitable is None
    assert empty.avg_profit_over_avg_loss is None
    assert pf.sharpe(()) is None and pf.sortino(()) is None


# ==============================================================================================
# The per-trade excursions -- what carries intra-candle moves under the Q-16(b) ruling
# ==============================================================================================


def _bar(hour: int, minute: int, high: int, low: int) -> Bar:
    stamp = datetime.combine(DAY, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
    return Bar(stamp=stamp, open_paise=low, high_paise=high, low_paise=low, close_paise=high, volume=1)


def test_the_ledger_excursions_are_position_scaled_not_per_share() -> None:
    """Still load-bearing for Q-16(b), for a NEW reason: the ruling's one disclosed limit is
    that the 15-minute path cannot see inside a candle, and it names the per-trade MFE/MAE as
    what carries those excursions instead. So they must be in portfolio rupees, not per share.
    Doubling the position doubles both."""
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
    """Q43 is RETIRED (the trader superseded it in Round 4), so `capital_flags` must hold no
    number of its own -- not even
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
        == pf.CAPITAL_FLAGS_RETIRED_NOTE
    )


def test_the_two_blocked_e13_entries_never_come_back_as_numbers() -> None:
    """**FLIPPED by the Q-16 fix session (architect's ruling, 30-Jul-2026).** The probe used
    to assert that neither blocked entry ever came back as a number while Q-16 was OPEN. Q-16
    is RESOLVED, so it now asserts the RULING instead: `outliers` is a computed record that
    carries its own definition, and the definition names the rule that produced it."""
    m = pf.metrics(basis_rows(), initial_capital_paise=CAPITAL)
    assert m.outliers is not None
    assert m.outliers.definition == m.outliers_note
    assert "Q-16(a)" in m.outliers_note and "Tukey" in m.outliers_note
    assert m.outliers.lower_fence_paise is not None
    assert m.outliers.upper_fence_paise is not None

    # ...and the intra-trade form is now the TRUE 15-minute path, with the worst-case
    # coincidence construction retired outright: nothing here is PROVISIONAL any more.
    assert not hasattr(pf, "INTRA_TRADE_PROVISIONAL")
    assert "PROVISIONAL" not in m.intraday_note
    assert "Q-16(b)" in pf.INTRADAY_PATH_LIMIT
    assert m.intraday_note == pf.INTRADAY_PATH_NOT_SUPPLIED  # no path was handed to it
    assert m.intraday_max_drawdown is None and m.intraday_max_run_up is None
