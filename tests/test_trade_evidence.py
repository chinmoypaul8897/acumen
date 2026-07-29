"""The chunk-8 evidence pack's own arithmetic (`src/acumen/trade_evidence.py`).

The pack under `docs/evidence/` is committed so a later session can re-check a claim without
redoing the work (CLAUDE.md's evidence rule, REVIEW_7 finding C3). That only means anything if
the numbers it prints are computed correctly and its PASS lines can actually FAIL -- an
invariant report that always says PASS is decoration, not evidence. Both are asserted here on
SYNTHETIC records, so none of this needs the local stores.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction
from pathlib import Path

from acumen import signals as sig
from acumen import simulate as sim
from acumen import trade_evidence as evidence
from acumen.signal_engine import EVALUATED, StockDay

DAY = date(2026, 7, 20)


def record(
    *,
    symbol: str = "TCS",
    day: date = DAY,
    side: str = sig.LONG,
    qty: int = 200,
    entry: int = 203_700,
    stop: int = 203_200,
    target: int = 205_200,
    risk: int = 500,
    exit_kind: str | None = sig.EXIT_TARGET,
    exit_paise: int | None = 205_200,
    gross: int = 300_000,
    cost: int = 10_000,
    net: int = 290_000,
    outcome: str = sig.OUTCOME_ENTERED,
    consumed: bool = True,
    gap: bool = False,
    tie: bool = False,
    flags: tuple[str, ...] = (),
) -> sim.TradeRecord:
    """A TradeRecord with F1's money by default; every field overridable per test."""
    return sim.TradeRecord(
        symbol=symbol,
        day=day,
        side=side,
        entry_paise=entry,
        stop_paise=stop,
        target_paise=target,
        per_share_risk_paise=risk,
        entry_stamp=sig.bar_open_stamp(day, 9),
        entry_close_stamp=sig.bar_close_stamp(day, 9),
        exit_kind=exit_kind,
        exit_paise=exit_paise,
        exit_stamp=sig.bar_open_stamp(day, 11),
        exit_close_stamp=sig.bar_close_stamp(day, 11),
        qty=qty,
        gross_pnl_paise=gross,
        cost_paise=cost,
        net_pnl_paise=net,
        risk_per_trade_paise=100_000,
        outcome=outcome,
        consumed=consumed,
        gap_entry=gap,
        tie_case=tie,
        bias="bullish",
        poc_paise=Fraction(203_200),
        reference_paise=202_500,
        flags=flags,
        detail="synthetic record built by this test",
    )


def priced_day(rec: sim.TradeRecord | None, *, reason: str = EVALUATED, bars=()) -> evidence.PricedDay:
    return evidence.PricedDay(
        stock_day=StockDay(
            symbol="TCS" if rec is None else rec.symbol,
            day=DAY if rec is None else rec.day,
            evaluated=rec is not None,
            reason=reason,
            bars=bars,
        ),
        record=rec,
    )


def result(days) -> evidence.SweepResult:
    return evidence.SweepResult(
        days=tuple(days),
        symbols=("TCS",),
        start=DAY,
        end=DAY,
        risk_per_trade_paise=100_000,
        cost_paise=10_000,
        row_size=24,
        master_path=Path("cache/instrument_master/OpenAPIScripMaster_2026-07-28.json"),
    )


# --- the totals ---------------------------------------------------------------------------


def test_money_totals_add_up_the_executed_trades_only() -> None:
    """HAND-COMPUTED: a +Rs 3,000 winner, a -Rs 994 loser and a qty-zero day.

    gross = 300,000 + (-99,400) = **200,600 paise**; cost = 2 x 10,000 = **20,000**;
    net = 290,000 + (-109,400) = **180,600** = gross - cost. The qty-zero day contributes
    nothing to any of the three, and is not counted as a trade.
    """
    sweep = result(
        [
            priced_day(record()),
            priced_day(
                record(
                    qty=71, risk=1_400, exit_kind=sig.EXIT_STOP, exit_paise=202_800,
                    gross=-99_400, net=-109_400,
                )
            ),
            priced_day(
                record(
                    qty=0, exit_paise=None, gross=0, cost=0, net=0,
                    flags=(sim.FLAG_QTY_ZERO_UNSIZABLE,),
                )
            ),
        ]
    )
    totals = evidence.money_totals(sweep)

    assert totals["trades"] == 2
    assert totals["gross_paise"] == 200_600
    assert totals["cost_paise"] == 20_000
    assert totals["net_paise"] == 180_600
    assert totals["net_paise"] == totals["gross_paise"] - totals["cost_paise"]
    assert (totals["winners"], totals["losers"], totals["flat"]) == (1, 1, 0)
    assert totals["gross_profit_paise"] == 300_000
    assert totals["gross_loss_paise"] == -99_400
    assert totals["shares"] == 271


def test_the_day_partition_counts_every_day_including_the_refused_ones() -> None:
    """A day that never reached the signal engine is still a day. The counts must partition
    the sweep, or chunk 9's disclosures start losing stock-days."""
    sweep = result(
        [
            priced_day(record()),
            priced_day(record(outcome=sig.OUTCOME_ARMED_NO_CROSS, qty=0, gross=0, cost=0, net=0)),
            priced_day(None, reason="gate 1 (volume reconciliation)"),
        ]
    )
    counts = evidence.outcome_counts(sweep)

    assert counts[sig.OUTCOME_ENTERED] == 1
    assert counts[sig.OUTCOME_ARMED_NO_CROSS] == 1
    assert counts["not evaluated: gate 1 (volume reconciliation)"] == 1
    assert sum(counts.values()) == len(sweep.days) == 3


def test_shape_counts_report_zero_rather_than_staying_silent() -> None:
    """REVIEW_7 finding Q3: a branch with no real-data witness must be SAID, not implied by
    an absent row -- otherwise silence reads as coverage."""
    sweep = result([priced_day(record(gap=True, tie=True, flags=(sim.FLAG_BOTH_TOUCHED_STOP_WINS,)))])
    shapes = evidence.shape_counts(sweep)

    assert shapes["gap entries"] == 1
    assert shapes["rule-3 tie bias days"] == 1
    assert shapes["both-touched candles (stop won)"] == 1
    assert shapes["qty-zero unsizable days"] == 0  # present and zero, not missing
    assert shapes["signal-unsizable (degenerate) days"] == 0


# --- the invariant report has to be able to FAIL --------------------------------------------


def test_the_invariant_report_passes_on_a_correct_run() -> None:
    sweep = result([priced_day(record())])
    assert all("PASS" in line for line in evidence.invariant_report(sweep))


def test_an_oversized_position_is_reported_as_a_failure() -> None:
    """201 shares at 500 paise of risk = 100,500 paise > the Rs 1,000 budget."""
    sweep = result([priced_day(record(qty=201))])
    lines = evidence.invariant_report(sweep)

    assert "FAIL" in lines[0] and "1 violations" in lines[0]


def test_an_undersized_position_is_reported_as_a_failure() -> None:
    """199 shares at 500 paise leaves room for another share, so the floor was not tight."""
    sweep = result([priced_day(record(qty=199))])
    assert "FAIL" in evidence.invariant_report(sweep)[1]


def test_a_wrong_net_is_reported_as_a_failure() -> None:
    sweep = result([priced_day(record(net=299_999))])
    assert "FAIL" in evidence.invariant_report(sweep)[2]


def test_a_target_exit_that_does_not_pay_three_r_is_reported_as_a_failure() -> None:
    sweep = result([priced_day(record(gross=299_999, net=289_999))])
    lines = evidence.invariant_report(sweep)
    assert "FAIL" in lines[3]


def test_a_stop_exit_that_does_not_pay_one_r_is_reported_as_a_failure() -> None:
    sweep = result(
        [priced_day(record(exit_kind=sig.EXIT_STOP, exit_paise=203_200, gross=-99_999, net=-109_999))]
    )
    assert "FAIL" in evidence.invariant_report(sweep)[4]


def test_a_no_trade_day_that_charged_a_cost_is_reported_as_a_failure() -> None:
    sweep = result([priced_day(record(qty=0, gross=0, cost=10_000, net=-10_000))])
    assert "FAIL" in evidence.invariant_report(sweep)[5]


def test_a_square_off_priced_off_its_own_candle_is_reported_as_a_failure() -> None:
    """The square-off fill must BE the marked candle's close; the check reads the candle, not
    the record's claim about it."""
    from acumen.aggregate import Bar

    marked = Bar(
        stamp=sig.bar_open_stamp(DAY, 11),
        open_paise=204_100,
        high_paise=204_600,
        low_paise=203_800,
        close_paise=204_400,
        volume=1_000,
    )
    honest = priced_day(
        record(exit_kind=sig.EXIT_SQUARE_OFF, exit_paise=204_400, gross=140_000, net=130_000),
        bars=(marked,),
    )
    assert "PASS" in evidence.invariant_report(result([honest]))[6]

    lying = priced_day(
        record(exit_kind=sig.EXIT_SQUARE_OFF, exit_paise=204_500, gross=160_000, net=150_000),
        bars=(marked,),
    )
    assert "FAIL" in evidence.invariant_report(result([lying]))[6]


def test_a_square_off_marked_away_from_the_15_00_candle_is_reported() -> None:
    """R1-Q18 puts the square-off on the 15:00-stamped candle; anything else is worth naming
    (the one legal exception -- nothing traded after the entry -- is flagged on the record)."""
    sweep = result(
        [priced_day(record(exit_kind=sig.EXIT_SQUARE_OFF, exit_paise=205_200, gross=150_000, net=140_000))]
    )
    assert "FAIL" in evidence.invariant_report(sweep)[7]


# --- rendering ------------------------------------------------------------------------------


def test_the_half_paise_poc_is_printed_exactly_never_rounded() -> None:
    """CONTEXT 3.3: a row midpoint may sit half a paisa off the tick grid (CONTEXT 7-E11
    forbids rounding it). 73,980.5 paise prints as 739.805, not 739.80 or 739.81."""
    assert evidence._poc_text(Fraction(73_980)) == "739.80"
    assert evidence._poc_text(Fraction(147_961, 2)) == "739.805"
    assert evidence._poc_text(None) == "-"


def test_the_rendered_pack_states_its_disclosures_inputs_and_totals() -> None:
    """The pack must carry the empty-factor-table disclosure and its money inputs, or a later
    reader could mistake a wiring witness for a backtest result."""
    sweep = result([priced_day(record()), priced_day(None, reason="gate 2 (candle integrity)")])
    text = evidence.render_markdown(sweep, command="python docs/evidence/chunk8_sweep.py")

    assert "Empty factor table" in text
    assert "not** a backtest result" in text
    assert "Rs 1,000.00 = 100,000 paise" in text
    assert "Rs 100.00 = 10,000 paise" in text
    assert "| not evaluated: gate 2 (candle integrity) | 1 |" in text
    assert "| **Net PnL** | **Rs 2,900.00** |" in text
    assert "OpenAPIScripMaster_2026-07-28.json" in text
