"""REVIEW_9B_FIX4 -- the reviewer's OWN walk of the shipped BiasEngine.

Committed beside its output under CLAUDE.md's evidence rule (REVIEW_7 finding C3): this
review makes claims from real store data, so the generating script and what it printed are
both here. Re-run with `python docs/evidence/review9b_fix4_r1_walk.py`.

Question 1 (the decisive one): with each symbol's REAL factor table, walked from the run's own
span start, what bias carries INTO 2021-02-25 for GODREJCP and for LAURUSLABS?

Question 2: re-derive the 21 / 2 / 0 impact table on a chosen subset of the 16 stray-carrying
symbols -- BOTH halves of each walk (as shipped = every stored bar becomes a candle; as ruled =
aggregate.in_session_bars first), by the reviewer's own loaders rather than by the builder's.

READ-ONLY over <data_root>. Nothing under it is written, renamed or removed.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import json

from acumen import backtest as bt
from acumen import bias as pure_bias
from acumen.bias_engine import BiasEngine, UngatedMinuteDay
from acumen.calendar import TradingCalendar
from acumen.config import load_config
from acumen.daily_store import DailyStore
from acumen.minute_store import MinuteStore
from acumen.signal_engine import SignalPipeline

SPAN_START = date(2016, 10, 3)
SPAN_END = date(2026, 7, 30)

# The trade days named in the FIX-4 evidence table, per symbol -> [(trade_day, d_minus_1)].
TARGETS: dict[str, list[tuple[date, date]]] = {
    "GODREJCP": [(date(2021, 2, 25), date(2021, 2, 24))],
    "LAURUSLABS": [(date(2021, 2, 25), date(2021, 2, 24))],
    "COLPAL": [(date(2021, 2, 25), date(2021, 2, 24))],
    "VEDL": [(date(2021, 2, 25), date(2021, 2, 24))],
    "GODREJPROP": [(date(2021, 2, 25), date(2021, 2, 24))],
    "HAVELLS": [(date(2017, 5, 2), date(2017, 4, 28))],
    "MUTHOOTFIN": [(date(2017, 5, 2), date(2017, 4, 28))],
    "CDSL": [(date(2019, 10, 29), date(2019, 10, 25))],
    "RECLTD": [
        (date(2020, 12, 30), date(2020, 12, 29)),
        (date(2021, 1, 14), date(2021, 1, 13)),
        (date(2021, 6, 23), date(2021, 6, 22)),
        (date(2021, 8, 6), date(2021, 8, 5)),
        (date(2022, 3, 15), date(2022, 3, 14)),
        (date(2022, 8, 10), date(2022, 8, 8)),
    ],
    "PIDILITIND": [(date(2021, 12, 21), date(2021, 12, 20))],
}


def unfiltered_gated_loader(store: MinuteStore, pipeline: SignalPipeline):
    """AS SHIPPED at 6b6baaa: battery first, then a Candle for EVERY stored bar. My own code."""
    memo: dict[tuple[str, date], object] = {}

    def load(symbol: str, day: date):
        bars = store.minutes(symbol, day)
        if not bars:
            return None
        key = (symbol.upper(), day)
        if key not in memo:
            memo[key] = pipeline.gate_day(symbol, day, bars).refusal_detail
        refusal = memo[key]
        if refusal is not None:
            raise UngatedMinuteDay(
                symbol=symbol, day=day, gate=refusal[0], gate_reason=refusal[1]
            )
        return tuple(
            pure_bias.Candle(
                open=int(b.open_paise),
                high=int(b.high_paise),
                low=int(b.low_paise),
                close=int(b.close_paise),
                stamp=b.stamp,
                day=b.trade_date,
            )
            for b in bars
        )

    return load


def filtered_gated_loader(store: MinuteStore, pipeline: SignalPipeline):
    """AS RULED: identical, except in_session_bars runs before a single Candle is built."""
    from acumen.aggregate import in_session_bars

    memo: dict[tuple[str, date], object] = {}
    dropped_by_day: dict[tuple[str, date], int] = {}

    def load(symbol: str, day: date):
        bars = store.minutes(symbol, day)
        if not bars:
            return None
        key = (symbol.upper(), day)
        if key not in memo:
            memo[key] = pipeline.gate_day(symbol, day, bars).refusal_detail
        refusal = memo[key]
        if refusal is not None:
            raise UngatedMinuteDay(
                symbol=symbol, day=day, gate=refusal[0], gate_reason=refusal[1]
            )
        session, dropped = in_session_bars(bars)
        if dropped:
            dropped_by_day[key] = dropped
        return tuple(
            pure_bias.Candle(
                open=int(b.open_paise),
                high=int(b.high_paise),
                low=int(b.low_paise),
                close=int(b.close_paise),
                stamp=b.stamp,
                day=b.trade_date,
            )
            for b in session
        )

    return load, dropped_by_day


def main() -> int:
    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    master, master_path, master_sha = bt.pinned_master(
        config.path("cache_root"), config.instrument_master
    )

    sessions_path = data / "backtests" / "chunk9b_full" / bt.SESSIONS_NAME
    payload = json.loads(sessions_path.read_text(encoding="utf-8"))
    non_standard = frozenset(date.fromisoformat(d) for d in payload["non_standard"])
    print(f"non-standard sessions reused from the crashed run: {sorted(non_standard)}")
    assert date(2021, 2, 24) not in non_standard
    assert date(2017, 4, 28) not in non_standard

    symbols = tuple(sorted(TARGETS))
    factors, suppressions, digest, _summary = bt.build_factor_tables(
        symbols, daily_store, start=SPAN_START, end=SPAN_END, allow_network=False
    )
    print(f"factor digest for this subset: {digest}")
    for sym in symbols:
        fs = factors.get(sym, ())
        sup = suppressions.get(sym, ())
        print(
            f"  {sym}: {len(fs)} factor(s) "
            f"{[(f.ex_date.isoformat(), f.kind, str(f.k)) for f in fs]}; "
            f"{len(sup)} suppression(s) {[(s.ex_date.isoformat(), s.kind) for s in sup]}"
        )

    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )

    rows = []
    for sym in symbols:
        end = max(d for d, _ in TARGETS[sym])
        calendar = TradingCalendar.from_daily_store_range(
            daily_store, SPAN_START - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
        )
        calendar = replace(
            calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
        )
        shipped_engine = BiasEngine(
            store=daily_store,
            calendar=calendar,
            factors=factors.get(sym, ()),
            suppressions=suppressions.get(sym, ()),
            minute_loader=unfiltered_gated_loader(minute_store, pipeline),
        )
        ruled_loader, dropped_by_day = filtered_gated_loader(minute_store, pipeline)
        ruled_engine = BiasEngine(
            store=daily_store,
            calendar=calendar,
            factors=factors.get(sym, ()),
            suppressions=suppressions.get(sym, ()),
            minute_loader=ruled_loader,
        )
        shipped = shipped_engine.bias_series(sym, SPAN_START, end)
        ruled = ruled_engine.bias_series(sym, SPAN_START, end)
        assert len(shipped) == len(ruled)

        by_day_s = {b.trade_date: b for b in shipped}
        by_day_r = {b.trade_date: b for b in ruled}

        disagreements = [
            d for d in by_day_s if (by_day_s[d].bias, by_day_s[d].rule) != (by_day_r[d].bias, by_day_r[d].rule)
        ]
        bias_disagreements = [d for d in by_day_s if by_day_s[d].bias != by_day_r[d].bias]

        for trade_day, dm1 in TARGETS[sym]:
            s = by_day_s[trade_day]
            r = by_day_r[trade_day]
            # the carry INTO trade_day = the bias produced on the previous walked trading day
            days = sorted(by_day_s)
            idx = days.index(trade_day)
            prev = days[idx - 1]
            rows.append(
                {
                    "symbol": sym,
                    "trade_day": trade_day.isoformat(),
                    "d_minus_1": dm1.isoformat(),
                    "engine_current_date": None if s.current_date is None else s.current_date.isoformat(),
                    "prev_walked_day": prev.isoformat(),
                    "carry_in_bias(shipped)": by_day_s[prev].bias,
                    "carry_in_rule(shipped)": by_day_s[prev].rule,
                    "carry_in_bias(ruled)": by_day_r[prev].bias,
                    "carry_in_rule(ruled)": by_day_r[prev].rule,
                    "strays_dropped": dropped_by_day.get((sym, dm1), 0),
                    "shipped_rule": s.rule,
                    "shipped_bias": s.bias,
                    "ruled_rule": r.rule,
                    "ruled_bias": r.bias,
                    "bias_moves": s.bias != r.bias,
                }
            )
        print(
            f"\n=== {sym}: walked {len(shipped)} trading days {SPAN_START} -> {end} "
            f"| rule/bias disagreements over the WHOLE walk: {len(disagreements)} "
            f"{[d.isoformat() for d in sorted(disagreements)]} "
            f"| BIAS disagreements: {len(bias_disagreements)} "
            f"{[d.isoformat() for d in sorted(bias_disagreements)]}"
        )
        for trade_day, dm1 in TARGETS[sym]:
            days = sorted(by_day_s)
            idx = days.index(trade_day)
            for d in days[max(0, idx - 4): idx + 1]:
                s, r = by_day_s[d], by_day_r[d]
                mark = " <== TRADE DAY" if d == trade_day else ""
                print(
                    f"   {d} shipped[{s.rule:<24s} {str(s.bias):<8s}] "
                    f"ruled[{r.rule:<24s} {str(r.bias):<8s}]{mark}"
                )

    print("\n\n=== TABLE ===")
    for row in rows:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
