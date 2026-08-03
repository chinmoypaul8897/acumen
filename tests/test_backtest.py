"""The chunk-9A backtest RUNNER: the walk, the refusal partition, and the ledger's contract.

The engines under it are already reviewed (chunks 4, 6, 7, 8); what this file attacks is the
machine around them -- the thing a full-history run trusts:

* every walked symbol-day produces exactly ONE row, whether it traded or not;
* a day is refused for exactly ONE reason, in the fixed order E2 -> no minutes -> gate 1 ->
  gate 2 -> gate 1P -> suppressed -> no bias -> no POC, so the counts PARTITION the run;
* a bias that cannot be assembled is a counted no-trade, never an exception;
* the REAL chunk-3 factor table is applied pairwise, into the CURRENT candle's scale;
* the ledger is resumable (zero duplicates after an interruption), idempotent and
  BYTE-IDENTICAL on a completed re-run;
* the manifest carries the residual-register acknowledgment and CONTEXT 4.6's IOC/TATASTEEL
  caveat verbatim, and says the Q40-d capital flags are NOT computed while Q43 is open.

**The synthetic trade day**, hand-derived once and used throughout (it is the chunk-7 test
day, priced): tick 10 paise, Row Size 24; 120 one-minute bars in the profile window, 119 of
them point bars at Rs 2000.00 and a first minute running 1999.50..2000.50, so bottom = 199950,
top = 200050, totalTicks = 10, tpr = 1 and the busiest row is [200000, 200010) -> **POC =
200005 paise**. The 11:00-11:15 candle closes 200000, below the POC -> **ARMED**. The candle
closing 11:30 closes 200100 > POC -> **entry 200100**, its low 199900 is below the POC so the
stop is that low -> **risk 200 paise**, **target 200700**. The candle closing 11:45 runs
200100..200800 and takes the target.

Money on that day, hand-computed: ``qty = floor(100000 / 200) = 500`` (500 x 200 = 100,000
exactly at the budget; 501 x 200 = 100,200 over it), ``gross = 500 x (200700 - 200100) =
300,000 paise = Rs 3,000.00``, ``net = 300,000 - 10,000 = 290,000 paise = Rs 2,900.00``,
``notional = 500 x 200,100 = 100,050,000 paise = Rs 1,000,500.00``. Excursions over the one
monitored candle (high 200800, low 200100): ``MFE = (200800 - 200100) x 500 = 350,000`` and
``MAE = 0``.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import corp_actions as ca
from acumen import signal_engine as se
from acumen import signals as sig
from acumen import simulate as sim
from acumen.aggregate import Bar
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
)
from acumen.bias import BEARISH, BULLISH, BiasError, Candle, evaluate_pair
from acumen.bias_engine import (
    RULE_MINUTES_MALFORMED,
    RULE_MINUTES_UNGATED,
    MalformedMinuteBar,
    UngatedMinuteDay,
)
from acumen.calendar import TradingCalendar
from acumen.daily_store import DailyStore
from acumen.instrument_master import InstrumentMaster
from acumen.minute_store import MinuteStore
from acumen.signal_engine import SignalPipeline

SYMBOL = "SYNTH"
TICK_PAISE = 10
ROW_SIZE = 24
RISK_PAISE = 100_000
COST_PAISE = 10_000

#: Three consecutive weekdays. The first two are daily-only (they seed the bias); the third
#: is the synthetic trade day above. Two further weekdays BEFORE them give the calendar the
#: lead ``bias_pair(SEED_A)`` needs -- exactly what ``build_runner`` derives in production.
LEAD_A = date(2026, 7, 13)
LEAD_B = date(2026, 7, 14)
SEED_A = date(2026, 7, 15)
SEED_B = date(2026, 7, 16)
TRADE_DAY = date(2026, 7, 17)


def R(rupees: float) -> int:
    return int(round(rupees * 100))


def at(t: time, day: date) -> datetime:
    return datetime.combine(day, t)


class Minute:
    """One 1-minute bar in the shape ``MinuteStore.write_bars`` accepts."""

    def __init__(self, stamp, o, h, l, c, volume):
        self.stamp = stamp
        self.open_paise, self.high_paise, self.low_paise, self.close_paise = o, h, l, c
        self.volume = volume


def synthetic_minutes(day: date, *, session_start: time = time(9, 15)) -> list[Minute]:
    """The hand-derived trade day. ``session_start`` moves it out of session for the E2 test."""
    offset = (
        datetime.combine(day, session_start) - datetime.combine(day, time(9, 15))
    )
    minutes: list[Minute] = []
    window_open = at(time(9, 15), day) + offset
    for index in range(120):
        stamp = window_open + timedelta(minutes=index)
        if index == 0:
            minutes.append(Minute(stamp, R(2000.00), R(2000.50), R(1999.50), R(2000.00), 10))
        else:
            minutes.append(Minute(stamp, R(2000.00), R(2000.00), R(2000.00), R(2000.00), 100))
    minutes += [
        Minute(at(time(11, 15), day) + offset, R(2000.00), R(2000.50), R(1999.00), R(1999.50), 200),
        Minute(at(time(11, 16), day) + offset, R(1999.50), R(2001.20), R(1999.50), R(2001.00), 300),
        Minute(at(time(11, 29), day) + offset, R(2001.00), R(2001.00), R(2001.00), R(2001.00), 50),
        Minute(at(time(11, 30), day) + offset, R(2001.00), R(2008.00), R(2001.00), R(2007.50), 400),
    ]
    return minutes


def daily_row(day: date, o: int, h: int, l: int, c: int, volume: int, symbol: str = SYMBOL):
    return DailyRow(
        trade_date=day,
        symbol=symbol,
        series="EQ",
        open_paise=o,
        high_paise=h,
        low_paise=l,
        close_paise=c,
        volume=volume,
        source_format=FORMAT_ARCHIVE,
    )


def row_for_minutes(day: date, minutes: list[Minute], **override):
    fields = dict(
        day=day,
        o=minutes[0].open_paise,
        h=max(m.high_paise for m in minutes),
        l=min(m.low_paise for m in minutes),
        c=minutes[-1].close_paise,
        volume=sum(m.volume for m in minutes),
    )
    fields.update(override)
    return daily_row(**fields)


def build_stores(
    tmp_path: Path,
    *,
    minute_days: dict[date, list[Minute]] | None = None,
    daily_rows: dict[date, DailyRow] | None = None,
    symbols: tuple[str, ...] = (SYMBOL,),
) -> tuple[MinuteStore, DailyStore, InstrumentMaster, TradingCalendar]:
    minute_store = MinuteStore.at(tmp_path / "minute_store")
    daily_store = DailyStore.at(tmp_path / "daily_store")
    for day, minutes in (minute_days or {}).items():
        for symbol in symbols:
            minute_store.write_bars(symbol, minutes)
    rows = dict(daily_rows or {})
    for day, row in sorted(rows.items()):
        daily_store.write_rows(day, [row])
    first, last = min(rows), max(rows)
    outcomes = []
    current = first
    while current <= last:
        if current in rows:
            outcomes.append(
                DateOutcome(
                    current,
                    OUTCOME_PRESENT,
                    source_format=FORMAT_ARCHIVE,
                    http_status=200,
                    row_count=1,
                )
            )
        else:
            outcomes.append(DateOutcome(current, OUTCOME_NOT_FOUND, http_status=404))
        current += timedelta(days=1)
    daily_store.record_outcomes(outcomes)
    calendar = TradingCalendar.from_daily_store_range(daily_store, first, last)
    master = InstrumentMaster.from_rows(
        [
            {
                "exch_seg": "NSE",
                "symbol": f"{symbol}-EQ",
                "token": str(90000 + index),
                "tick_size": f"{TICK_PAISE}.000000",
                "name": symbol,
                "lotsize": "1",
            }
            for index, symbol in enumerate(symbols)
        ]
    )
    return minute_store, daily_store, master, calendar


def standard_world(tmp_path: Path, *, symbols: tuple[str, ...] = (SYMBOL,)):
    """Two seeding days (daily only) then the synthetic trade day, for every symbol."""
    minutes = synthetic_minutes(TRADE_DAY)
    rows = dict(lead_rows())
    rows.update(
        {
            SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
            SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
            TRADE_DAY: row_for_minutes(TRADE_DAY, minutes),
        }
    )
    return build_stores(
        tmp_path, minute_days={TRADE_DAY: minutes}, daily_rows=rows, symbols=symbols
    )


def lead_rows() -> dict[date, DailyRow]:
    """Two daily-only weekdays before the span, so ``bias_pair(SEED_A)`` exists."""
    return {
        LEAD_A: daily_row(LEAD_A, R(1980), R(1990), R(1970), R(1985), 1000),
        LEAD_B: daily_row(LEAD_B, R(1985), R(1995), R(1975), R(1990), 1000),
    }


def make_runner(
    tmp_path: Path,
    *,
    symbols: tuple[str, ...] = (SYMBOL,),
    start: date = SEED_A,
    end: date = TRADE_DAY,
    factors=(),
    suppressions=(),
    residual=None,
    stores=None,
    non_standard=frozenset(),
    capital_reference_paise=None,
    margin_basis=None,
) -> bt.BacktestRunner:
    minute_store, daily_store, master, calendar = stores or standard_world(
        tmp_path, symbols=symbols
    )
    if non_standard:
        calendar = replace(
            calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
        )
    spec = bt.RunSpec(
        symbols=symbols,
        start=start,
        end=end,
        row_size=ROW_SIZE,
        risk_per_trade_paise=RISK_PAISE,
        cost_paise=COST_PAISE,
        code_sha="0" * 40,
        factor_digest="test-digest",
        # The Q-20 pin, as a run really carries it: the filename AND the file's own digest.
        master_file="OpenAPIScripMaster_2026-07-31.json",
        master_sha256="c" * 64,
        capital_reference_paise=capital_reference_paise,
        margin_basis=margin_basis,
        label="unit",
    )
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=ROW_SIZE,
    )
    return bt.BacktestRunner(
        spec=spec,
        pipeline=pipeline,
        calendar=calendar,
        minute_store=minute_store,
        daily_store=daily_store,
        factors={symbol: tuple(factors) for symbol in symbols},
        suppressions={symbol: tuple(suppressions) for symbol in symbols},
        residual=residual
        if residual is not None
        else {
            symbol: bt.ResidualEntry(symbol, "settled", 100, 100, 0, "") for symbol in symbols
        },
        non_standard_sessions=frozenset(non_standard),
        # Exactly what ``build_runner`` wires (QUESTIONS.md Q-21(b)): the GATED loader, sharing
        # the pipeline that gates the day being traded. A test runner on the bare loader would
        # be testing a machine the operator never runs.
        minute_loader=bt.gated_minute_loader(minute_store, pipeline),
    )


# ==============================================================================================
# The walk: one row per day, priced
# ==============================================================================================


def test_a_clean_day_runs_end_to_end_and_prices_the_trade(tmp_path: Path) -> None:
    """Every number here is hand-computed in the module docstring: entry 200100, stop 199900,
    risk 200, target 200700, qty 500, gross Rs 3,000.00, net Rs 2,900.00, MFE 350,000, MAE 0.
    """
    rows = make_runner(tmp_path).walk_symbol(SYMBOL).rows
    traded = [row for row in rows if row.executed]
    assert len(traded) == 1
    row = traded[0]

    assert (row.symbol, row.day, row.side) == (SYMBOL, TRADE_DAY, sig.LONG)
    assert row.status == bt.STATUS_EVALUATED and row.outcome == sig.OUTCOME_ENTERED
    assert row.poc_half_paise == 400_010  # 200005 paise x 2 -- exact, no float
    assert row.poc_paise == 200_005
    assert (row.entry_paise, row.stop_paise, row.target_paise) == (200_100, 199_900, 200_700)
    assert row.per_share_risk_paise == 200
    assert row.qty == 500
    assert row.gross_pnl_paise == 300_000
    assert row.cost_paise == COST_PAISE
    assert row.net_pnl_paise == 290_000
    assert row.notional_paise == 100_050_000
    assert row.exit_kind == sig.EXIT_TARGET and row.exit_paise == 200_700
    assert (row.mfe_paise, row.mae_paise) == (350_000, 0)
    assert row.gate1_passed and row.gate2_passed and row.gate1p_passed


def test_every_walked_day_produces_exactly_one_row_including_the_refusals(
    tmp_path: Path,
) -> None:
    """The two seeding days have no stored minutes; they are COUNTED, never dropped."""
    rows = make_runner(tmp_path).walk_symbol(SYMBOL).rows
    assert [row.day for row in rows] == [SEED_A, SEED_B, TRADE_DAY]
    assert [row.status for row in rows] == [
        bt.STATUS_REFUSED,
        bt.STATUS_REFUSED,
        bt.STATUS_EVALUATED,
    ]
    assert all(row.reason == se.NOT_EVALUATED_NO_MINUTES for row in rows[:2])


def test_the_counts_partition_the_walked_days(tmp_path: Path) -> None:
    rows = make_runner(tmp_path).walk_symbol(SYMBOL).rows
    counts = bt.outcome_counts(rows)
    assert sum(counts.values()) == len(rows)
    assert counts[sig.OUTCOME_ENTERED] == 1


def test_a_gate_failure_is_counted_under_its_own_reason(tmp_path: Path) -> None:
    """A raw daily row whose interval does not contain the fold FAILS gate 1P, and the day is
    refused under gate 1P's own reason rather than folded into gate 1's count (Q-14)."""
    minutes = synthetic_minutes(TRADE_DAY)
    rows = dict(lead_rows())
    rows.update({
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
        # the raw high is BELOW the stored fold high -> impossible on raw prices -> gate 1P
        TRADE_DAY: row_for_minutes(TRADE_DAY, minutes, h=R(2000.00)),
    })
    stores = build_stores(tmp_path, minute_days={TRADE_DAY: minutes}, daily_rows=rows)
    walked = make_runner(tmp_path, stores=stores).walk_symbol(SYMBOL).rows
    day = walked[-1]
    assert day.status == bt.STATUS_REFUSED
    assert day.reason == se.NOT_EVALUATED_GATE1P
    assert day.gate1p_passed is False
    assert day.gate1_passed is True  # gate 1 itself passed; it is not blamed


def test_a_suppressed_pair_is_a_counted_no_trade(tmp_path: Path) -> None:
    """CONTEXT 3.2: a demerger ex-date at D-1 or D-2 means no bias update AND no trade."""
    suppression = ca.Suppression(SYMBOL, SEED_B, ca.KIND_DEMERGER, "demerger")
    rows = make_runner(tmp_path, suppressions=(suppression,)).walk_symbol(SYMBOL).rows
    trade = rows[-1]
    assert trade.status == bt.STATUS_REFUSED
    assert trade.reason == se.NOT_EVALUATED_SUPPRESSED
    assert trade.suppressed is True
    assert trade.qty == 0 and trade.net_pnl_paise == 0


def test_a_bias_that_cannot_be_assembled_is_counted_never_raised(tmp_path: Path) -> None:
    """A calendar that cannot reach D-2 makes the pair unassemblable. A 400,000-day run must
    not die of it: every day of the symbol is refused, counted, with the reason recorded."""
    minute_store, daily_store, master, calendar = standard_world(tmp_path)
    # a calendar covering ONLY the trade day: bias_pair(TRADE_DAY) has no D-1/D-2 in range
    narrow = TradingCalendar.from_daily_store_range(daily_store, TRADE_DAY, TRADE_DAY)
    runner = make_runner(
        tmp_path, stores=(minute_store, daily_store, master, narrow), start=TRADE_DAY
    )
    rows = runner.walk_symbol(SYMBOL).rows
    assert len(rows) == 1
    assert rows[0].status == bt.STATUS_REFUSED
    assert rows[0].reason.startswith(bt.REASON_BIAS_UNRESOLVED)


# ==============================================================================================
# CONTEXT 7-E2 -- the non-standard session
# ==============================================================================================


def test_the_e2_detector_reads_the_clock_on_every_stored_candle() -> None:
    assert bt.is_standard_session_stamp(datetime(2026, 7, 17, 9, 15))
    assert bt.is_standard_session_stamp(datetime(2026, 7, 17, 15, 29))
    assert not bt.is_standard_session_stamp(datetime(2026, 7, 17, 9, 14))
    assert not bt.is_standard_session_stamp(datetime(2026, 7, 17, 15, 30))
    assert not bt.is_standard_session_stamp(datetime(2024, 11, 1, 18, 0))  # Muhurat


def test_a_session_wholly_outside_the_window_is_detected_and_excluded(
    tmp_path: Path,
) -> None:
    """The Muhurat shape: an 18:00-19:00 hour on a date NSE published a bhavcopy for. E2's own
    detection ("candle data ... outside 09:15-15:30") makes it a non-standard session, so it is
    refused under E2 and never becomes a trading day."""
    muhurat = synthetic_minutes(TRADE_DAY, session_start=time(18, 0))
    rows = dict(lead_rows())
    rows.update({
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
        TRADE_DAY: row_for_minutes(TRADE_DAY, muhurat),
    })
    stores = build_stores(tmp_path, minute_days={TRADE_DAY: muhurat}, daily_rows=rows)
    minute_store = stores[0]

    detected = bt.scan_non_standard_sessions(
        minute_store, (SYMBOL,), (SEED_A, SEED_B, TRADE_DAY)
    )
    assert detected == (TRADE_DAY,)

    walked = make_runner(tmp_path, stores=stores, non_standard=frozenset(detected)).walk_symbol(
        SYMBOL
    )
    assert walked.rows[-1].reason == bt.REASON_E2_NON_STANDARD
    assert walked.rows[-1].bias is None  # it never reached the bias engine


def test_a_date_with_a_session_candle_anywhere_in_the_universe_is_standard(
    tmp_path: Path,
) -> None:
    """A session is a property of the MARKET: one symbol trading inside the window is enough."""
    normal = synthetic_minutes(TRADE_DAY)
    rows = dict(lead_rows())
    rows[TRADE_DAY] = row_for_minutes(TRADE_DAY, normal)
    minute_store, *_ = build_stores(
        tmp_path, minute_days={TRADE_DAY: normal}, daily_rows=rows, symbols=(SYMBOL, "OTHER")
    )
    assert bt.scan_non_standard_sessions(minute_store, (SYMBOL, "OTHER"), (TRADE_DAY,)) == ()


# ==============================================================================================
# The REAL factor table, applied pairwise
# ==============================================================================================


def test_the_factor_table_is_applied_pairwise_into_the_current_candles_scale(
    tmp_path: Path,
) -> None:
    """A 1:1 bonus on the CURRENT candle's own date halves the PREVIOUS candle (CONTEXT 3.2).

    Hand-computed: P (SEED_A) is O 1990.00 H 2000.00 L 1980.00 C 1995.00; with k = 0.5 it
    becomes O 995.00 H 1000.00 L 990.00 C 997.50, bodyMax 997.50. C (SEED_B) closes 2008.00.
    Adjusted, 2008.00 > 997.50 -> Rule 1 BULLISH. Unadjusted the same pair is an ordinary
    2008.00 vs 1995.00 close, which is ALSO Rule 1 -- so the discriminating assertion is the
    PRICE the engine compared, which the row carries through the bias it produced on a pair
    that only the adjustment can decide: the factor moves P by 50%, and the run must show the
    factor in its manifest so the comparison is auditable rather than assumed.
    """
    factor = ca.Factor(SYMBOL, SEED_B, ca.KIND_BONUS, Decimal("0.5"), "bonus 1:1")
    runner = make_runner(tmp_path, factors=(factor,))
    rows = runner.walk_symbol(SYMBOL).rows
    assert rows[-1].bias == BULLISH

    manifest = runner.build_manifest(rows, {SYMBOL: bt.SymbolRun(SYMBOL, rows).counts()})
    in_span = manifest["factor_table"]["per_symbol"][SYMBOL]["in_span"]
    assert in_span == [
        {
            "ex_date": SEED_B.isoformat(),
            "kind": ca.KIND_BONUS,
            "k": "0.5",
            "classification": "",
        }
    ]


def test_a_factor_that_changes_the_previous_candle_changes_the_bias(tmp_path: Path) -> None:
    """The discriminating case: the SAME candles give opposite biases with and without the
    factor -- which is the whole reason CONTEXT 3.2 adjusts pairwise.

    The pair for the trade day is C = SEED_B, P = SEED_A. P raw is O 2950.00 H 3000.00
    L 2900.00 C 2990.00, so bodyMin 2950.00; C is O 1995.00 H 2010.00 L 1990.00 C 2008.00.
    UNADJUSTED: C.close 2008.00 < bodyMin 2950.00 -> Rule 1 **BEARISH** (a fake 33% collapse,
    which is exactly what an unadjusted 1:2 bonus looks like).
    ADJUSTED by k = 2/3: P becomes O 1966.67 H 2000.00 L 1933.33 C 1993.33, bodyMax 1993.33;
    C.close 2008.00 > 1993.33 -> Rule 1 **BULLISH**. Opposite side, same candles.
    """
    rows_daily = dict(lead_rows())
    rows_daily.update({
        SEED_A: daily_row(SEED_A, R(2950), R(3000), R(2900), R(2990), 1000),
        SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
        TRADE_DAY: row_for_minutes(TRADE_DAY, synthetic_minutes(TRADE_DAY)),
    })
    stores = build_stores(
        tmp_path,
        minute_days={TRADE_DAY: synthetic_minutes(TRADE_DAY)},
        daily_rows=rows_daily,
    )
    naked = make_runner(tmp_path, stores=stores).walk_symbol(SYMBOL).rows
    assert naked[-1].bias == BEARISH
    assert naked[-1].side == sig.SHORT

    factor = ca.Factor(SYMBOL, SEED_B, ca.KIND_BONUS, Decimal(2) / Decimal(3), "bonus 1:2")
    adjusted = make_runner(tmp_path, stores=stores, factors=(factor,)).walk_symbol(SYMBOL).rows
    assert adjusted[-1].bias == BULLISH
    assert adjusted[-1].side == sig.LONG
    assert adjusted[-1].status == bt.STATUS_EVALUATED


# ==============================================================================================
# MFE / MAE (PURE)
# ==============================================================================================


def bar(close_stamp: datetime, high: int, low: int) -> Bar:
    return Bar(
        stamp=close_stamp - timedelta(minutes=15),
        open_paise=low,
        high_paise=high,
        low_paise=low,
        close_paise=high,
        volume=1,
    )


def test_excursions_are_measured_only_over_the_candles_the_position_was_held() -> None:
    entry_close = datetime(2026, 7, 17, 11, 30)
    bars = [
        bar(datetime(2026, 7, 17, 11, 30), 999_999, 1),  # the ENTRY candle: E7 excludes it
        bar(datetime(2026, 7, 17, 11, 45), 210, 90),
        bar(datetime(2026, 7, 17, 12, 0), 300, 50),  # AFTER the exit: excluded
    ]
    mfe, mae = bt.trade_excursion_paise(
        sig.LONG, 100, 10, bars, entry_close, datetime(2026, 7, 17, 11, 45)
    )
    assert (mfe, mae) == ((210 - 100) * 10, (90 - 100) * 10)


def test_the_short_mirror_of_an_excursion() -> None:
    entry_close = datetime(2026, 7, 17, 11, 30)
    bars = [bar(datetime(2026, 7, 17, 11, 45), 210, 90)]
    mfe, mae = bt.trade_excursion_paise(
        sig.SHORT, 100, 10, bars, entry_close, datetime(2026, 7, 17, 11, 45)
    )
    assert (mfe, mae) == ((100 - 90) * 10, (100 - 210) * 10)


def test_an_excursion_is_never_signed_against_the_trade() -> None:
    """A trade that only ever went up has MAE 0, not a positive "adverse" excursion."""
    entry_close = datetime(2026, 7, 17, 11, 30)
    bars = [bar(datetime(2026, 7, 17, 11, 45), 210, 150)]
    mfe, mae = bt.trade_excursion_paise(
        sig.LONG, 100, 10, bars, entry_close, datetime(2026, 7, 17, 11, 45)
    )
    assert mfe == 1100 and mae == 0


def test_a_trade_with_no_monitored_candle_has_no_excursion() -> None:
    """The chunk-7 B159 shape: nothing traded after the entry candle."""
    entry_close = datetime(2026, 7, 17, 15, 0)
    assert bt.trade_excursion_paise(sig.LONG, 100, 10, [], entry_close, entry_close) == (0, 0)


# ==============================================================================================
# The ledger contract: round trip, determinism, resume
# ==============================================================================================


def test_a_row_round_trips_through_json_byte_identically(tmp_path: Path) -> None:
    rows = make_runner(tmp_path).walk_symbol(SYMBOL).rows
    for row in rows:
        again = bt.LedgerRow.from_dict(json.loads(row.to_json()))
        assert again == row
        assert again.to_json() == row.to_json()


def test_the_ledger_is_byte_identical_on_a_completed_re_run(tmp_path: Path) -> None:
    """The determinism pin: same spec, same stores, same bytes -- ledger AND manifest."""
    first = make_runner(tmp_path).run(tmp_path / "run1")
    second = make_runner(tmp_path).run(tmp_path / "run2")
    assert first.ledger_path.read_bytes() == second.ledger_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()

    # and a re-run INTO THE SAME directory (every symbol already complete) is a no-op
    before = first.ledger_path.read_bytes()
    make_runner(tmp_path).run(tmp_path / "run1")
    assert first.ledger_path.read_bytes() == before


def test_an_interrupted_run_resumes_with_zero_duplicates_and_identical_bytes(
    tmp_path: Path,
) -> None:
    """Kill the run after the first symbol's shard is durable, then resume: the ledger must be
    byte-identical to an uninterrupted run and must not carry one duplicated row."""
    symbols = (SYMBOL, "OTHER", "THIRD")
    stores = standard_world(tmp_path, symbols=symbols)
    whole = make_runner(tmp_path, symbols=symbols, stores=stores).run(tmp_path / "whole")

    class Interrupt(RuntimeError):
        pass

    def die_after_first(symbol: str) -> None:
        if symbol == SYMBOL:
            raise Interrupt(symbol)

    run_dir = tmp_path / "resumed"
    with pytest.raises(Interrupt):
        make_runner(tmp_path, symbols=symbols, stores=stores).run(
            run_dir, after_symbol=die_after_first
        )
    assert not (run_dir / bt.LEDGER_NAME).exists()  # nothing is published mid-run
    progress = json.loads((run_dir / bt.PROGRESS_NAME).read_text(encoding="utf-8"))
    assert progress["completed"] == [SYMBOL]

    resumed = make_runner(tmp_path, symbols=symbols, stores=stores).run(run_dir)
    assert resumed.ledger_path.read_bytes() == whole.ledger_path.read_bytes()
    assert resumed.manifest_path.read_bytes() == whole.manifest_path.read_bytes()
    keys = [(row.symbol, row.day) for row in resumed.rows]
    assert len(keys) == len(set(keys)) == 3 * 3


def test_a_partial_symbol_is_never_left_behind(tmp_path: Path) -> None:
    """The shard is written only when its symbol is COMPLETE, so an interruption INSIDE a
    symbol leaves no shard for it -- which is what makes the resume duplicate-free."""
    symbols = (SYMBOL, "OTHER")
    stores = standard_world(tmp_path, symbols=symbols)
    runner = make_runner(tmp_path, symbols=symbols, stores=stores)
    original = runner.walk_symbol

    def explode(symbol: str):
        if symbol == "OTHER":
            raise RuntimeError("killed mid-symbol")
        return original(symbol)

    object.__setattr__(runner, "walk_symbol", explode)
    run_dir = tmp_path / "partial"
    with pytest.raises(RuntimeError):
        runner.run(run_dir)
    shards = sorted(path.name for path in (run_dir / bt.SHARD_DIRNAME).glob("*.jsonl"))
    assert shards == [f"{SYMBOL}.jsonl"]


def test_a_resume_against_a_different_spec_is_refused(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    make_runner(tmp_path).run(run_dir)
    moved = make_runner(tmp_path)
    object.__setattr__(moved, "spec", replace(moved.spec, code_sha="1" * 40))
    with pytest.raises(bt.BacktestError, match="different run"):
        moved.run(run_dir)


@pytest.mark.parametrize(
    "change",
    [
        {"master_file": "OpenAPIScripMaster_2026-08-02.json"},
        {"master_sha256": "b" * 64},
    ],
)
def test_a_resume_under_a_DIFFERENT_INSTRUMENT_MASTER_is_refused(tmp_path: Path, change) -> None:
    """**QUESTIONS.md Q-20 (architect, 02-Aug-2026): "a resume under any other master REFUSES
    (same discipline as the code SHA)."**

    Both halves are covered, because both failure shapes are real: the operator re-points the
    pin at the other cached snapshot (``master_file`` moves), or the vendor's file is
    overwritten in place under the SAME name (only ``master_sha256`` moves). A different tick
    is a different CONTEXT 3.3 row grid and therefore a different POC, so mixing two masters
    into one ledger is exactly as inadmissible as mixing two code states -- and the mechanism
    is the same one: both fields sit inside :meth:`RunSpec.digest`, which
    ``_resume_state`` compares. The sibling test above is the moved-SHA case, unchanged.
    """
    run_dir = tmp_path / "run"
    make_runner(tmp_path).run(run_dir)
    moved = make_runner(tmp_path)
    object.__setattr__(moved, "spec", replace(moved.spec, **change))
    with pytest.raises(bt.BacktestError, match="different run"):
        moved.run(run_dir)


def test_the_shard_and_the_ledger_are_written_through_atomic_io(tmp_path: Path) -> None:
    """No temp file survives, and the ledger is exactly the concatenated shards."""
    result = make_runner(tmp_path).run(tmp_path / "run")
    shard = (tmp_path / "run" / bt.SHARD_DIRNAME / f"{SYMBOL}.jsonl").read_bytes()
    assert result.ledger_path.read_bytes() == shard
    leftovers = [
        path.name for path in (tmp_path / "run").rglob("*") if path.suffix == ".tmp"
    ]
    assert leftovers == []


# ==============================================================================================
# The manifest
# ==============================================================================================


def test_the_manifest_carries_the_spec_version_code_sha_and_config_digest(
    tmp_path: Path,
) -> None:
    manifest = make_runner(tmp_path).run(tmp_path / "run").manifest
    assert manifest["spec_version"] == "v1.5"
    assert manifest["code_sha"] == "0" * 40
    assert manifest["config_digest"] == make_runner(tmp_path).spec.digest()
    assert manifest["universe"] == [SYMBOL]
    assert manifest["span"] == {"start": SEED_A.isoformat(), "end": TRADE_DAY.isoformat()}


def test_the_manifest_records_the_pinned_master_by_filename_AND_sha256(tmp_path: Path) -> None:
    """**QUESTIONS.md Q-20: "the run manifest records the pin by filename AND sha256".**

    Q-20's own complaint was that `build_manifest` carried no master field of any kind, so a
    finished ledger could not be traced back to the ticks that shaped its POCs -- the filename
    survived only in whatever console log the operator happened to keep. Both halves are
    recorded because a filename alone is not enough: a vendor file can be overwritten in place.
    """
    manifest = make_runner(tmp_path).run(tmp_path / "run").manifest
    pin = manifest["instrument_master"]
    assert pin["pinned_file"] == "OpenAPIScripMaster_2026-07-31.json"
    assert pin["sha256"] == "c" * 64
    assert "Q-20" in pin["note"]
    # ...and it is inside the STABLE digest, not one of the volatile keys: a ledger produced
    # under a different tick regime must not hash equal to this one.
    other = make_runner(tmp_path)
    object.__setattr__(
        other, "spec", replace(other.spec, master_sha256="d" * 64)
    )
    assert bt.stable_manifest_digest(
        other.run(tmp_path / "run2").manifest
    ) != bt.stable_manifest_digest(manifest)


def test_the_manifest_counts_every_symbol_walked_usable_and_refused(tmp_path: Path) -> None:
    manifest = make_runner(tmp_path).run(tmp_path / "run").manifest
    counts = manifest["per_symbol"][SYMBOL]
    assert counts["walked"] == 3
    assert counts["usable"] == 1
    assert counts["executed"] == 1
    assert counts["refused"] == {se.NOT_EVALUATED_NO_MINUTES: 2}
    assert sum(counts["refused"].values()) + counts["usable"] == counts["walked"]


def test_the_manifest_counts_every_rare_shape_even_at_zero(tmp_path: Path) -> None:
    """A zero says "this window carries no witness"; a missing key would let silence read as
    coverage (REVIEW_8 finding Q1)."""
    manifest = make_runner(tmp_path).run(tmp_path / "run").manifest
    assert set(manifest["rare_shapes"]) == set(bt.RARE_SHAPE_LABELS)
    assert manifest["rare_shapes"]["gap entries"] == 0


def test_the_manifest_carries_the_residual_register_acknowledgment_verbatim(
    tmp_path: Path,
) -> None:
    # CONTEXT 4.6 (v1.5): the settled-but-partial figures are "quoted from the register's own
    # current figures", never a frozen string. These are the REBUILT register's real numbers.
    residual = {
        SYMBOL: bt.ResidualEntry(SYMBOL, "settled", 100, 100, 0, ""),
        "IOC": bt.ResidualEntry("IOC", "settled", 1024, 2436, 1, ""),
        "TATASTEEL": bt.ResidualEntry("TATASTEEL", "settled", 1604, 2436, 1, ""),
    }
    manifest = make_runner(tmp_path, residual=residual).run(tmp_path / "run").manifest
    register = manifest["residual_register"]
    assert register["acknowledged"] is True
    assert register["caveat"] == (
        "IOC (42.0% price-proven) and TATASTEEL (65.8% price-proven) are settled-but-partial "
        "under B149 -- their backtests cover only part of stored history, concentrated in "
        "recent years."
    )
    # The pre-Q-18 era's IOC figure was 41.9%; the rebuilt register says 42.0%. A frozen
    # string would still be claiming the destroyed era's number here.
    assert "41.9%" not in register["caveat"]
    assert register["per_symbol"][SYMBOL]["status"] == "settled"


def test_the_manifest_says_the_capital_flags_are_not_computed_while_q43_is_open(
    tmp_path: Path,
) -> None:
    manifest = make_runner(tmp_path).run(tmp_path / "run").manifest
    flags = manifest["capital_flags"]
    assert flags["computed"] is False
    assert flags["note"] == bt.CAPITAL_FLAGS_PENDING_NOTE
    assert "Q43" in flags["note"]
    assert flags["capital_reference_paise"] is None and flags["margin_basis"] is None


def test_the_manifest_marks_the_flags_computable_once_both_inputs_are_set(
    tmp_path: Path,
) -> None:
    manifest = (
        make_runner(tmp_path, capital_reference_paise=10_000_000, margin_basis="5")
        .run(tmp_path / "run")
        .manifest
    )
    assert manifest["capital_flags"]["computed"] is True
    assert "POST-HOC" in manifest["capital_flags"]["note"]


def test_the_stable_digest_ignores_the_commit_dependent_fields(tmp_path: Path) -> None:
    """The pack quotes this digest, so it must not move when the repo commits (REVIEW_8 C2)."""
    first = make_runner(tmp_path).run(tmp_path / "run1").manifest
    moved = make_runner(tmp_path)
    object.__setattr__(moved, "spec", replace(moved.spec, code_sha="f" * 40))
    second = moved.run(tmp_path / "run2").manifest
    assert first["code_sha"] != second["code_sha"]
    assert bt.stable_manifest_digest(first) == bt.stable_manifest_digest(second)


# ==============================================================================================
# The spec digest and the residual register
# ==============================================================================================


@pytest.mark.parametrize(
    "change",
    [
        {"symbols": ("OTHER",)},
        {"start": date(2026, 7, 14)},
        {"end": date(2026, 7, 20)},
        {"row_size": 25},
        {"risk_per_trade_paise": 200_000},
        {"cost_paise": 5_000},
        {"code_sha": "deadbeef"},
        {"factor_digest": "other"},
        # QUESTIONS.md Q-20: the tick input is an input that can move a number, so both halves
        # of the pin are inside the digest -- the filename AND the bytes behind it.
        {"master_file": "OpenAPIScripMaster_2099-01-01.json"},
        {"master_sha256": "a" * 64},
        {"capital_reference_paise": 1},
        {"margin_basis": "5"},
    ],
)
def test_the_spec_digest_moves_with_every_input_that_can_move_a_number(change) -> None:
    base = bt.RunSpec(
        symbols=(SYMBOL,),
        start=SEED_A,
        end=TRADE_DAY,
        row_size=ROW_SIZE,
        risk_per_trade_paise=RISK_PAISE,
        cost_paise=COST_PAISE,
        code_sha="0" * 40,
        factor_digest="test-digest",
    )
    assert replace(base, **change).digest() != base.digest()


def test_the_residual_register_is_read_not_assumed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(
            {
                "symbols": {
                    "IOC": {
                        "status": "settled",
                        "gate1p_pass": 1020,
                        "gate1p_total": 2432,
                        "gate1p_no_oracle": 1,
                        "residual_reason": "un-provable eras",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    register = bt.load_residual_register(path)
    entry = register["IOC"]
    assert entry.status == "settled"
    assert entry.gate1p_pass == 1020 and entry.gate1p_total == 2432
    # 1020/2432 = 41.94% -- the 41.9% CONTEXT 4.6 names
    assert entry.as_dict()["price_proven_pct_x100"] == 4194
    assert "un-provable" in entry.residual_reason


def test_a_missing_residual_register_is_an_error_not_an_empty_one(tmp_path: Path) -> None:
    with pytest.raises(bt.BacktestError, match="disclosed-residual register"):
        bt.load_residual_register(tmp_path / "nope.json")


def test_read_ledger_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(bt.BacktestError, match="No ledger"):
        bt.read_ledger(tmp_path / "nope.jsonl")


def test_the_ledger_carries_no_clock_read(tmp_path: Path) -> None:
    """Nothing in a row or a manifest may come from the wall clock -- that is what makes a
    re-run byte-identical. Proved by running twice and diffing, and by the schema itself."""
    result = make_runner(tmp_path).run(tmp_path / "run")
    payload = json.loads(result.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    stamps = [key for key in payload if key.endswith("stamp")]
    assert stamps == ["entry_close_stamp", "exit_close_stamp"]  # both are CANDLE stamps
    assert "generated_at" not in result.manifest and "timestamp" not in result.manifest

# ==============================================================================================
# The out-of-session candle: a full run must survive one (QUESTIONS.md Q-17)
# ==============================================================================================


def world_with_a_pre_open_print(tmp_path: Path):
    """The synthetic trade day plus ONE bar stamped 09:14 -- the real shape the chunk-9B smoke
    hit on RELIANCE 2017-04-28 (one bar, 25,015 shares, a plausible price). The daily row is
    built over ALL the stored minutes, because that is what the vendor and the bhavcopy agree
    on: NSE's daily volume includes the pre-open auction, which is why gate 1 wants it."""
    minutes = synthetic_minutes(TRADE_DAY)
    stray = Minute(at(time(9, 14), TRADE_DAY), R(2000.00), R(2000.20), R(1999.80), R(2000.00), 250)
    everything = [stray] + minutes
    rows = {
        LEAD_A: daily_row(LEAD_A, R(1980), R(1990), R(1970), R(1985), 1000),
        LEAD_A + timedelta(days=1): daily_row(
            LEAD_A + timedelta(days=1), R(1985), R(1995), R(1975), R(1990), 1000
        ),
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_A + timedelta(days=1): daily_row(
            SEED_A + timedelta(days=1), R(1995), R(2010), R(1990), R(2008), 1000
        ),
        TRADE_DAY: row_for_minutes(TRADE_DAY, everything),
    }
    return build_stores(
        tmp_path, minute_days={TRADE_DAY: everything}, daily_rows=rows, symbols=(SYMBOL,)
    )


def test_a_pre_open_print_no_longer_kills_the_run(tmp_path: Path) -> None:
    """**The chunk-9B smoke run's finding, pinned.** Before this, ONE vendor bar stamped 09:14
    raised `AggregateError` out of `aggregate_15min` and took the whole full-history run with
    it -- on a day CONTEXT 4.5's gate 2 had deliberately ADMITTED, because gate 2's own reading
    of CONTEXT 7-E2 is that a stray candle is dropped at the CANDLE level and is "not a
    day-killer". The engines now apply that same reading, so the day walks."""
    runner = make_runner(tmp_path, stores=world_with_a_pre_open_print(tmp_path))
    rows = runner.walk_symbol(SYMBOL).rows
    traded = [row for row in rows if row.executed]

    assert len(traded) == 1  # it did not raise, and it did not silently refuse either
    row = traded[0]
    assert row.status == bt.STATUS_EVALUATED
    assert bt.FLAG_OUT_OF_SESSION_DROPPED in row.flags  # ...and the drop is NOT silent
    assert row.minute_count == 125  # the stored count still reports every stored bar


def test_the_dropped_candle_changes_no_price_the_strategy_reads(tmp_path: Path) -> None:
    """The stray bar is outside the 09:15..11:14 profile window and outside the 15-minute grid,
    so dropping it must reproduce the clean day's numbers to the paisa. If it ever did move
    one, that would mean an out-of-session print had been feeding the strategy."""
    dirty = make_runner(tmp_path / "dirty", stores=world_with_a_pre_open_print(tmp_path / "dirty"))
    clean = make_runner(tmp_path / "clean")

    dirty_row = next(row for row in dirty.walk_symbol(SYMBOL).rows if row.executed)
    clean_row = next(row for row in clean.walk_symbol(SYMBOL).rows if row.executed)

    for field in ("poc_half_paise", "entry_paise", "stop_paise", "target_paise", "qty",
                  "gross_pnl_paise", "net_pnl_paise", "exit_kind", "mfe_paise", "mae_paise"):
        assert getattr(dirty_row, field) == getattr(clean_row, field), field
    assert clean_row.flags == ()  # and a clean day carries no flag, so the bytes do not move


def test_the_fifteen_minute_path_reader_applies_the_same_drop(tmp_path: Path) -> None:
    """`assemble_trade_paths` reads the store a SECOND time to mark open positions. If it did
    not drop the stray bar too, it would raise on exactly the days the engine survived -- and
    the 15-minute equity path would stop reconciling with the ledger it is built from."""
    stores = world_with_a_pre_open_print(tmp_path)
    runner = make_runner(tmp_path, stores=stores)
    rows = runner.walk_symbol(SYMBOL).rows
    paths = bt.assemble_trade_paths(rows, bars_for=bt.minute_store_bars(stores[0]))
    assert len(paths) == 1
    assert paths[0].marks  # it produced marks rather than raising


# ==============================================================================================
# QUESTIONS.md Q-21: the Rule-3 scan meets a vendor-corrupt 1-minute bar
#
# The bar that killed the full-history run at symbol 104/204 was JUBLFOOD 2023-03-03 09:15,
# O 44210 H 44440 L 44295 C 44295 V 12909 -- an open 85 paise BELOW the low. The world below is
# that shape, synthetic and hand-derived, on the D-1 of a genuine Rule-3 pair:
#
#   D-2 = SEED_A  O 199000 H 200000 L 198000 C 199500   -> body [199000, 199500]
#   D-1 = SEED_B  O 199200 H 200500 L 197500 C 199300   -> C.high > P.high AND C.low < P.low,
#                                                          close inside the body -> RULE 3
#
# and D-1's three stored minutes are chosen so that the corruption is DECISIVE:
#
#   09:15  O 199000  H 200500  L 199100  C 199250  V 12909  <- malformed (O below L); breaks
#                                                              P.high 200000 FIRST -> BULLISH
#   09:16  O 199250  H 199300  L 197500  C 197600  V 300    <- breaks P.low 198000 -> BEARISH
#   09:17  O 197600  H 199350  L 197550  C 199300  V 200       if the corrupt bar were skipped
#
# Repaired, the day is BULLISH; with the corrupt bar quietly dropped it is BEARISH. That is the
# architect's rationale in one fixture -- "a scan minus a corrupt bar could reverse a
# first-break" -- and it is why the DAY is refused rather than the bar skipped.
# ==============================================================================================

Q21_STAMP = at(time(9, 15), SEED_B)
Q21_DETAIL = (
    f"malformed-minute-bar {SYMBOL} {SEED_B.isoformat()} stamp {Q21_STAMP.isoformat(sep=' ')} "
    "O 199000 H 200500 L 199100 C 199250 V 12909"
)


def q21_prior_minutes(*, malformed: bool) -> list[Minute]:
    """D-1's three bars. ``malformed`` puts the open 2 rupees below the low, as the vendor did."""
    return [
        Minute(
            at(time(9, 15), SEED_B),
            R(1990.00) if malformed else R(1992.00),
            R(2005.00),
            R(1991.00),
            R(1992.50),
            12909,
        ),
        Minute(at(time(9, 16), SEED_B), R(1992.50), R(1993.00), R(1975.00), R(1976.00), 300),
        Minute(at(time(9, 17), SEED_B), R(1976.00), R(1993.50), R(1975.50), R(1993.00), 200),
    ]


def q21_world(tmp_path: Path, *, malformed: bool = True, rule_3: bool = True):
    """The standard trade day, with a Rule-3 (or, for the control, a Rule-1) D-1 carrying the bar."""
    minutes = synthetic_minutes(TRADE_DAY)
    prior = q21_prior_minutes(malformed=malformed)
    rows = dict(lead_rows())
    rows.update(
        {
            SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
            # The Rule-3 outside bar, or the ORIGINAL day (a Rule-1 breakout) for the control.
            SEED_B: daily_row(SEED_B, R(1992), R(2005), R(1975), R(1993), 13409)
            if rule_3
            else daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 13409),
            TRADE_DAY: row_for_minutes(TRADE_DAY, minutes),
        }
    )
    return build_stores(
        tmp_path, minute_days={SEED_B: prior, TRADE_DAY: minutes}, daily_rows=rows
    )


def q21_trade_day_row(runner) -> bt.LedgerRow:
    return next(row for row in runner.walk_symbol(SYMBOL).rows if row.day == TRADE_DAY)


def test_q21_the_loader_names_the_offending_bar_instead_of_dying_anonymously(
    tmp_path: Path,
) -> None:
    """The RUN's loader is the narrowest place that still holds the RAW bar, so it is the only
    place that can say WHICH bar. Before Q-21 it raised BiasError with four prices and no
    symbol, no date, no stamp and no volume -- and killed the run."""
    minute_store, _, _, _ = q21_world(tmp_path)
    load = bt.minute_loader(minute_store)

    with pytest.raises(MalformedMinuteBar) as excinfo:
        load(SYMBOL, SEED_B)

    assert excinfo.value.detail() == Q21_DETAIL
    assert (excinfo.value.symbol, excinfo.value.day, excinfo.value.stamp) == (
        SYMBOL,
        SEED_B,
        Q21_STAMP,
    )
    assert isinstance(excinfo.value.__cause__, BiasError)  # the pure invariant caught it
    assert load(SYMBOL, TRADE_DAY) is not None  # a clean day still loads


def test_q21_a_malformed_bar_refuses_the_day_and_counts_it_instead_of_crashing(
    tmp_path: Path,
) -> None:
    """The architect's ruling: the day joins REASON_BIAS_UNRESOLVED as its third case, counted,
    never a crash, with the offending bar's stamp and OHLCV in the refusal detail."""
    runner = make_runner(tmp_path, stores=q21_world(tmp_path))

    rows = runner.walk_symbol(SYMBOL).rows  # it does not raise
    row = next(row for row in rows if row.day == TRADE_DAY)

    assert len(rows) == 3  # every other day of the span still walked
    assert row.status == bt.STATUS_REFUSED
    assert row.reason == f"{bt.REASON_BIAS_UNRESOLVED}: {Q21_DETAIL}"
    assert row.bias_rule == RULE_MINUTES_MALFORMED
    assert row.flags == (bt.FLAG_MALFORMED_MINUTE_BAR,)
    assert row.executed is False and row.signalled is False and row.qty == 0


def test_q21_the_same_day_with_the_bar_corrected_is_an_ordinary_rule_3_bias(
    tmp_path: Path,
) -> None:
    """The CONTROL. One field moves -- the corrupt open, 199000 -> 199200 -- and the day is a
    normal Rule-3 bullish bias that trades the golden trade. So the refusal above is caused by
    the corruption and by nothing else in the fixture."""
    runner = make_runner(tmp_path, stores=q21_world(tmp_path, malformed=False))

    row = q21_trade_day_row(runner)

    assert row.status == bt.STATUS_EVALUATED
    assert row.bias == BULLISH and row.bias_rule == "rule-3-outside-bar"
    assert row.flags == ()
    assert row.executed is True
    assert (row.entry_paise, row.stop_paise, row.target_paise) == (200100, 199900, 200700)
    assert row.qty == 500 and row.net_pnl_paise == 290_000  # the hand-computed golden trade


def test_q21_a_malformed_bar_on_a_non_rule_3_day_changes_nothing(tmp_path: Path) -> None:
    """Rules 1 and 2 read NO minutes (CONTEXT 3.2 -- only Rule 3 asks which extreme broke
    first), so the identical corrupt bar sitting on a Rule-1 D-1 must be invisible. This is the
    measure of the fix's blast radius: it touches Rule-3 scan days and nothing else."""
    runner = make_runner(tmp_path, stores=q21_world(tmp_path, rule_3=False))

    row = q21_trade_day_row(runner)

    assert row.status == bt.STATUS_EVALUATED
    assert row.bias == BULLISH and row.bias_rule == "rule-1-breakout"
    assert row.flags == ()  # never loaded, so never refused
    assert row.executed is True and row.net_pnl_paise == 290_000


def test_q21_skipping_the_corrupt_bar_would_have_reversed_the_bias(tmp_path: Path) -> None:
    """WHY the DAY is refused rather than the bar skipped, proved on the fixture rather than
    asserted: with the bar repaired the high breaks first (BULLISH); with the bar simply
    dropped the low breaks first (BEARISH). Two opposite trades from the same stored day."""
    P = Candle(open=R(1990), high=R(2000), low=R(1980), close=R(1995))
    C = Candle(open=R(1992), high=R(2005), low=R(1975), close=R(1993))

    def candles(minutes: list[Minute]) -> tuple[Candle, ...]:
        return tuple(
            Candle(
                open=m.open_paise,
                high=m.high_paise,
                low=m.low_paise,
                close=m.close_paise,
                stamp=m.stamp,
            )
            for m in minutes
        )

    repaired = candles(q21_prior_minutes(malformed=False))
    skipped = candles(q21_prior_minutes(malformed=True)[1:])

    assert evaluate_pair(P, C, lambda: repaired, None).bias == BULLISH
    assert evaluate_pair(P, C, lambda: skipped, None).bias == BEARISH


def test_q21_the_manifest_counts_the_rare_shape(tmp_path: Path) -> None:
    """The ruling requires a rare-shape counter. Like every other one it is DERIVED from the
    row flags, so a resumed run replaying the shard counts it identically."""
    runner = make_runner(tmp_path, stores=q21_world(tmp_path))
    rows = runner.walk_symbol(SYMBOL).rows
    clean = make_runner(tmp_path / "clean")

    manifest = runner.build_manifest(rows, {SYMBOL: {}})
    label = "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)"

    assert label in bt.RARE_SHAPE_LABELS
    assert manifest["rare_shapes"][label] == 1
    assert set(manifest["rare_shapes"]) == set(bt.RARE_SHAPE_LABELS)
    # ...and a window without one still says so out loud, rather than omitting the row.
    spotless = clean.build_manifest(clean.walk_symbol(SYMBOL).rows, {SYMBOL: {}})
    assert spotless["rare_shapes"][label] == 0


# ==============================================================================================
# QUESTIONS.md Q-21(b): the Rule-3 scan asks for a D-1 that fails the CONTEXT 4.6 battery
#
# The architect's ruling of 03-Aug-2026: "a day's minutes may serve a Rule-3 first-break scan
# ONLY if that day passes the CONTEXT 4.5/4.6 gate battery ... a battery-failing D-1 makes the
# bias UNRESOLVABLE: fourth counted case (minutes-ungated) ... detail naming which gate failed."
#
# The world below is the Q-21 Rule-3 pair with its corrupt bar REPAIRED, so the only thing under
# test is the gate:
#
#   D-2 = SEED_A  O 199000 H 200000 L 198000 C 199500   -> body [199000, 199500]
#   D-1 = SEED_B  O 199200 H 200500 L 197500 C 199300   -> outside bar, close inside the body
#
# and D-1's three stored minutes are broken ONE GATE AT A TIME:
#
#   "1P" -- every PRICE doubled, every VOLUME untouched. That is the Q-14 wrong-price-domain
#           shape exactly: gate 1 reconciles (the volume is right), gate 2 sees nothing wrong
#           (each bar is internally consistent at 2x), and only gate 1P catches it, because the
#           fold interval [395000, 401000] cannot sit inside the raw bhavcopy [197500, 200500].
#           It is the same population the Q-14 ruling was written for -- 1,963 stored symbol-days
#           at 0.1x-5x the traded price that passed every gate there was.
#   "1"  -- the raw daily volume is 20,000 against a 13,409 minute sum: a 32.955% gap, above the
#           +5.0% ceiling and beyond auction relief's 20% cap.
#   "2"  -- the 09:15 bar is JIOFIN 2023-08-21's real shape (high BELOW low, close outside the
#           range), which gate 2 DOES enumerate -- and which `bias.Candle` would also refuse.
#           That day is the precedence witness: the gate is the ruling's precondition, so the
#           refusal names the GATE, not the bar.
# ==============================================================================================


def q21b_minutes(*, gate: str | None) -> list[Minute]:
    """D-1's three bars, broken for exactly one gate (or for none -- the control)."""
    scale = 2 if gate == "1P" else 1
    minutes = [
        Minute(at(time(9, 15), SEED_B), R(1992.00) * scale, R(2005.00) * scale,
               R(1991.00) * scale, R(1992.50) * scale, 12909),
        Minute(at(time(9, 16), SEED_B), R(1992.50) * scale, R(1993.00) * scale,
               R(1975.00) * scale, R(1976.00) * scale, 300),
        Minute(at(time(9, 17), SEED_B), R(1976.00) * scale, R(1993.50) * scale,
               R(1975.50) * scale, R(1993.00) * scale, 200),
    ]
    if gate == "2":
        # JIOFIN 2023-08-21's shape, in this world's prices: high below low, close outside.
        minutes[0] = Minute(
            at(time(9, 15), SEED_B), R(1992.00), R(1991.50), R(1993.00), R(1991.50), 12909
        )
    return minutes


def q21b_world(tmp_path: Path, *, gate: str | None = "1P", rule_3: bool = True):
    """The standard trade day, with a Rule-3 (or, for the control, a Rule-1) D-1 that fails ``gate``."""
    minutes = synthetic_minutes(TRADE_DAY)
    prior = q21b_minutes(gate=gate)
    rows = dict(lead_rows())
    rows.update(
        {
            SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
            # The Rule-3 outside bar, or a Rule-1 breakout for the blast-radius control. Its
            # OHLC is the RAW bhavcopy: gate 1P measures the stored fold against exactly this.
            SEED_B: daily_row(
                SEED_B, R(1992), R(2005), R(1975), R(1993), 20000 if gate == "1" else 13409
            )
            if rule_3
            else daily_row(
                SEED_B, R(1995), R(2010), R(1990), R(2008), 20000 if gate == "1" else 13409
            ),
            TRADE_DAY: row_for_minutes(TRADE_DAY, minutes),
        }
    )
    return build_stores(
        tmp_path, minute_days={SEED_B: prior, TRADE_DAY: minutes}, daily_rows=rows
    )


def q21b_battery(stores, day: date = SEED_B):
    """The CONTEXT 4.6 battery for ``day``, asked of the same pipeline the runner uses."""
    minute_store, daily_store, master, _ = stores
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    return pipeline.gate_day(SYMBOL, day, minute_store.minutes(SYMBOL, day))


@pytest.mark.parametrize(
    "gate, expected",
    [
        ("1P", se.NOT_EVALUATED_GATE1P),
        ("1", se.NOT_EVALUATED_GATE1),
        ("2", se.NOT_EVALUATED_GATE2),
    ],
)
def test_q21b_the_gated_loader_refuses_a_battery_failing_day_and_names_the_gate(
    tmp_path: Path, gate: str, expected: str
) -> None:
    """The load boundary is where the ruling bites, and the refusal carries the battery's OWN
    verdict -- which gate, and that gate's own reason -- rather than a sentence composed here."""
    stores = q21b_world(tmp_path / gate, gate=gate)
    minute_store, daily_store, master, _ = stores
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    load = bt.gated_minute_loader(minute_store, pipeline)

    with pytest.raises(UngatedMinuteDay) as excinfo:
        load(SYMBOL, SEED_B)

    battery = q21b_battery(stores)
    assert not battery.usable and battery.refusal == expected
    assert excinfo.value.gate == expected
    assert excinfo.value.gate_reason == battery.refusal_detail[1]
    assert excinfo.value.detail() == (
        f"minutes-ungated {SYMBOL} {SEED_B.isoformat()} gate {expected} "
        f"reason {battery.refusal_detail[1]}"
    )
    # ...and the day the battery passes still loads, through the same loader.
    assert load(SYMBOL, TRADE_DAY) is not None


def test_q21b_a_battery_failing_D1_refuses_the_trade_day_and_counts_it(tmp_path: Path) -> None:
    """The ruling's own shape: a Rule-3 pair whose D-1 fails gate 1P becomes ONE counted refusal
    naming gate 1P -- no trade, no crash, and the carried bias untouched."""
    stores = q21b_world(tmp_path, gate="1P")
    runner = make_runner(tmp_path, stores=stores)

    rows = runner.walk_symbol(SYMBOL).rows  # it does not raise
    row = next(r for r in rows if r.day == TRADE_DAY)
    battery = q21b_battery(stores)

    assert len(rows) == 3  # every other day of the span still walked
    assert battery.gate1 is not None and battery.gate1.passed  # the volume DOES reconcile...
    assert battery.gate2.passed  # ...and each bar is internally consistent...
    assert battery.gate1p.passed is False  # ...only the PRICE DOMAIN is wrong (Q-14's shape)
    assert row.status == bt.STATUS_REFUSED
    assert row.reason == (
        f"{bt.REASON_BIAS_UNRESOLVED}: minutes-ungated {SYMBOL} {SEED_B.isoformat()} "
        f"gate {se.NOT_EVALUATED_GATE1P} reason {battery.gate1p.reason}"
    )
    assert se.NOT_EVALUATED_GATE1P in row.reason and "fold HIGH" in row.reason
    assert row.bias_rule == RULE_MINUTES_UNGATED
    assert row.flags == (bt.FLAG_UNGATED_MINUTE_DAY,)
    assert row.executed is False and row.signalled is False and row.qty == 0
    # the carry is printed UNCHANGED -- the refused day moved nothing (the engine-level test
    # `test_q21b_a_battery_failing_day_leaves_the_carry_untouched` is the discriminating one,
    # where the Rule-3 answer and the carry differ)
    assert row.bias == next(r for r in rows if r.day == SEED_B).bias


def test_q21b_the_same_pair_with_a_gated_D1_is_an_ordinary_rule_3_bias(tmp_path: Path) -> None:
    """The CONTROL. The prices come back to their true scale -- nothing else moves -- and the
    day is a normal Rule-3 bullish bias that trades the golden trade. So the refusal above is
    caused by the failing battery and by nothing else in the fixture."""
    stores = q21b_world(tmp_path, gate=None)
    runner = make_runner(tmp_path, stores=stores)

    row = next(r for r in runner.walk_symbol(SYMBOL).rows if r.day == TRADE_DAY)

    assert q21b_battery(stores).usable is True
    assert row.status == bt.STATUS_EVALUATED
    assert row.bias == BULLISH and row.bias_rule == "rule-3-outside-bar"
    assert row.flags == ()
    assert row.executed is True
    assert (row.entry_paise, row.stop_paise, row.target_paise) == (200100, 199900, 200700)
    assert row.qty == 500 and row.net_pnl_paise == 290_000  # the hand-computed golden trade


def test_q21b_a_rule_1_day_with_a_battery_failing_D1_is_UNTOUCHED(tmp_path: Path) -> None:
    """CONTEXT 3.2: Rules 1 and 2 read NO minutes -- only Rule 3 asks which extreme broke first.
    So a D-1 that fails the battery outright is invisible to a day the daily candles decide, and
    the ruling costs that day nothing. This is the measure of the fix's blast radius."""
    stores = q21b_world(tmp_path, gate="1P", rule_3=False)
    runner = make_runner(tmp_path, stores=stores)

    row = next(r for r in runner.walk_symbol(SYMBOL).rows if r.day == TRADE_DAY)

    assert q21b_battery(stores).usable is False, "the fixture must really fail the battery"
    assert row.status == bt.STATUS_EVALUATED
    assert row.bias == BULLISH and row.bias_rule == "rule-1-breakout"
    assert row.flags == ()  # never asked for, so never refused
    assert row.executed is True and row.net_pnl_paise == 290_000


def test_q21b_the_gate_is_the_precondition_so_it_outranks_the_malformed_bar(
    tmp_path: Path,
) -> None:
    """JIOFIN 2023-08-21's real shape: a bar gate 2 CAN see (high < low, close outside) and that
    `bias.Candle` would also refuse. The ruling makes the battery a PRECONDITION of the scan, so
    the day is counted as `minutes-ungated` -- one day, one reason, and the reason is the gate."""
    stores = q21b_world(tmp_path, gate="2")
    minute_store, daily_store, master, _ = stores
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )

    # both faults are genuinely present on that stored day
    assert q21b_battery(stores).gate2.passed is False
    with pytest.raises(MalformedMinuteBar):
        bt.minute_loader(minute_store)(SYMBOL, SEED_B)  # the UNgated loader still names the bar

    row = next(
        r for r in make_runner(tmp_path, stores=stores).walk_symbol(SYMBOL).rows
        if r.day == TRADE_DAY
    )
    assert bt.gated_minute_loader is not bt.minute_loader
    assert row.bias_rule == RULE_MINUTES_UNGATED
    assert row.flags == (bt.FLAG_UNGATED_MINUTE_DAY,)
    assert RULE_MINUTES_MALFORMED not in (row.bias_rule or "")


def test_q21b_the_manifest_counts_the_rare_shape_and_a_resume_counts_it_identically(
    tmp_path: Path,
) -> None:
    """The counter is DERIVED from the row flag, so a resumed run -- which replays a shard it
    did not walk -- prints the same number as an uninterrupted one, and the manifest bytes are
    identical. That is the invariant a running counter would break."""
    stores = q21b_world(tmp_path, gate="1P")
    label = "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))"
    assert label in bt.RARE_SHAPE_LABELS

    whole = make_runner(tmp_path, stores=stores).run(tmp_path / "whole")
    assert whole.manifest["rare_shapes"][label] == 1
    assert set(whole.manifest["rare_shapes"]) == set(bt.RARE_SHAPE_LABELS)

    class Interrupt(RuntimeError):
        pass

    run_dir = tmp_path / "resumed"
    with pytest.raises(Interrupt):
        make_runner(tmp_path, stores=stores).run(
            run_dir, after_symbol=lambda symbol: (_ for _ in ()).throw(Interrupt(symbol))
        )
    resumed = make_runner(tmp_path, stores=stores).run(run_dir)

    assert resumed.manifest["rare_shapes"][label] == 1
    assert resumed.ledger_path.read_bytes() == whole.ledger_path.read_bytes()
    assert resumed.manifest_path.read_bytes() == whole.manifest_path.read_bytes()

    # ...and a window with no such day still prints the label, at zero, rather than omitting it.
    clean = make_runner(tmp_path / "clean")
    spotless = clean.build_manifest(clean.walk_symbol(SYMBOL).rows, {SYMBOL: {}})
    assert spotless["rare_shapes"][label] == 0


def test_q21b_the_battery_verdict_is_computed_once_per_symbol_day_and_reused(
    tmp_path: Path,
) -> None:
    """The ruling says "computes (or reuses)". Reuse is a MEMO, not a persisted exclusion file:
    CONTEXT 4.6 says outright there is no per-day exclusion file, so the verdict is recomputed
    from the stores on every run and merely not recomputed twice within one."""
    minute_store, daily_store, master, _ = q21b_world(tmp_path, gate="1P")
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    calls: list[tuple[str, date]] = []
    original = pipeline.gate_day

    def counted(symbol, day, minutes):
        calls.append((symbol, day))
        return original(symbol, day, minutes)

    object.__setattr__(pipeline, "gate_day", counted)
    load = bt.gated_minute_loader(minute_store, pipeline)

    for _ in range(4):
        with pytest.raises(UngatedMinuteDay):
            load(SYMBOL, SEED_B)

    assert calls == [(SYMBOL, SEED_B)]


def test_q21b_a_day_with_no_stored_minutes_is_the_documented_carry_not_a_gate_verdict(
    tmp_path: Path,
) -> None:
    """CONTEXT 3.2 / R1-Q6: a Rule-3 day with no 1-minute data carries the last bias. That is a
    SPEC branch, not a data verdict, and the battery cannot be run on a day with no bars at all
    -- so an empty day must come back as None and never as a refusal."""
    minute_store, daily_store, master, _ = standard_world(tmp_path)
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )

    assert minute_store.minutes(SYMBOL, SEED_A) == ()
    assert bt.gated_minute_loader(minute_store, pipeline)(SYMBOL, SEED_A) is None


def test_every_unusable_minute_evidence_case_has_a_flag_and_a_counter() -> None:
    """The tripwire that keeps a FIFTH case from reaching the ledger unflagged and uncounted.

    `walk_symbol` looks the row flag up in `UNRESOLVED_FLAG_BY_RULE` rather than branching per
    case, so a new `UnusableMinuteEvidence` subclass that forgets its entry fails HERE -- at
    import time in the suite -- instead of writing refused rows that no rare shape counts. Every
    flag must also key a real rare-shape label, or the manifest would carry a flag it never
    totals."""
    from acumen.bias_engine import UnusableMinuteEvidence

    def subclasses(cls):
        for child in cls.__subclasses__():
            yield child
            yield from subclasses(child)

    cases = list(subclasses(UnusableMinuteEvidence))
    assert {case.rule for case in cases} == {RULE_MINUTES_MALFORMED, RULE_MINUTES_UNGATED}
    for case in cases:
        assert case.rule in bt.UNRESOLVED_FLAG_BY_RULE, f"{case.__name__} has no ledger flag"
    counted = {
        flag
        for flag, label in (
            (bt.FLAG_MALFORMED_MINUTE_BAR, "malformed 1-minute bar"),
            (bt.FLAG_UNGATED_MINUTE_DAY, "battery-failing D-1"),
        )
        if any(label in shape for shape in bt.RARE_SHAPE_LABELS)
    }
    assert counted == set(bt.UNRESOLVED_FLAG_BY_RULE.values())


def test_q21b_the_run_path_wires_the_GATED_loader(tmp_path: Path) -> None:
    """A tripwire on the wiring itself. `build_runner` needs real stores, so what is pinned here
    is the property that makes the wiring checkable: the gated loader REFUSES a day the bare one
    happily returns, so the two are not interchangeable and a runner carrying the bare one is
    visibly a different machine."""
    minute_store, daily_store, master, _ = q21b_world(tmp_path, gate="1P")
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )

    assert bt.minute_loader(minute_store)(SYMBOL, SEED_B) is not None
    with pytest.raises(UngatedMinuteDay):
        bt.gated_minute_loader(minute_store, pipeline)(SYMBOL, SEED_B)
