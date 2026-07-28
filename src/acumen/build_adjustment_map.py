"""Build + persist a symbol's Q-11 vendor-adjustment map from live probe windows, and PROVE it.

The operator's runbook for the QUESTIONS.md Q-11 reconstruction. Credentialed, polite: for each
probe WINDOW it makes one ONE_MINUTE call, folds it, measures the era's cumulative ratios against
the RAW daily store, then (once every window is in) builds the :class:`acumen.vendor_adjustment.
AdjustmentMap`, persists it under ``data/adjustment_maps/`` (gitignored), prints the full map, and
runs the CONSUMPTION acceptance -- un-adjust every probe day THROUGH the map and check price
containment (<= 2 paise on a CA era) + gate-1 volume band per day.

    acumen-build-adjustment-map --symbol RELIANCE --allow-network \
        --window 2016-10:2016-10-03:2016-10-07 --window 2019-07:2019-07-01:2019-07-05 \
        --window 2022-07:2022-07-01:2022-07-06 --window 2023-06:2023-06-15:2023-06-20 \
        --window 2023-09:2023-09-01:2023-09-06 --window 2024-11:2024-11-04:2024-11-08

Each ``--window`` is ``label:start:end`` (ISO dates); pick a few pre-ex days per era (two windows
may share one era -- RELIANCE's 2022-07 and 2023-06 both sit in the demerger era, and are merged).
The factor table (bonus/split/rights/demerger/pending) is built from the cached NSE CA history +
the RAW daily store exactly as the ingest path does; ``--allow-network`` is required to fetch.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from . import vendor_adjustment as va
from .daily_store import DailyStore, DailyStoreError
from .instrument_master import InstrumentMaster, InstrumentMasterError, load_instrument_master
from .minute_backfill import (
    MINUTE_DATA_FLOOR,
    _tick_paise,
    corp_actions_for_symbol,
    fetch_corp_action_history,
)
from .quality_gates import volume_gate
from .smartapi_client import Credentials, OneMinuteBar, SmartApiClient, SmartApiError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="acumen-build-adjustment-map",
        description="Build, persist and prove a symbol's Q-11 vendor-adjustment map.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--symbol", required=True, help="symbol (NSE cash equity)")
    p.add_argument("--window", dest="windows", action="append", default=[],
                   help="probe window label:START:END (ISO); repeatable")
    p.add_argument("--from", dest="from_year", default="2016",
                   help="first year of CA history to read for the factor table")
    p.add_argument("--fetch-date", default=None, help="F, the fetch date (default: today)")
    p.add_argument("--allow-network", action="store_true", help="REQUIRED to fetch")
    p.add_argument("--store-dir", default="data", help="data dir for the persisted map")
    p.add_argument("--daily-store", default=None, help="daily store root (default: <data>/daily_store)")
    p.add_argument("--cache-dir", default=None, help="instrument-master cache dir")
    p.add_argument("--no-persist", action="store_true", help="do not write the map to disk")
    return p.parse_args(argv)


def _parse_window(spec: str) -> va.WindowSpec:
    parts = spec.split(":")
    if len(parts) != 3:
        raise SystemExit(f"bad --window {spec!r}; expected label:START:END (ISO)")
    label, start, end = parts
    return va.WindowSpec(label, date.fromisoformat(start), date.fromisoformat(end))


def run(args: argparse.Namespace) -> int:
    symbol = args.symbol.strip().upper()
    windows = [_parse_window(w) for w in args.windows]
    if not windows:
        raise SystemExit("at least one --window label:START:END is required")
    fetch_date = date.fromisoformat(args.fetch_date) if args.fetch_date else datetime.now().date()
    data_dir = Path(args.store_dir)
    daily_root = Path(args.daily_store) if args.daily_store else data_dir / "daily_store"
    daily_store = DailyStore.at(daily_root)

    print(f"symbol     : {symbol}")
    print(f"fetch date : {fetch_date} (F -- k_cum window is (D, F])")
    print(f"windows    : {[w.label for w in windows]}")

    master = load_instrument_master(cache_dir=args.cache_dir, allow_network=args.allow_network)
    tick_paise = _tick_paise(master, symbol)
    token = master.token(symbol)
    print(f"token      : {token}   tick = {master.tick_size(symbol)} ({tick_paise} paise)")

    actions = fetch_corp_action_history(
        date(int(args.from_year), 1, 1), fetch_date,
        allow_network=args.allow_network, cache_dir=args.cache_dir,
    )
    view = corp_actions_for_symbol(symbol, actions, daily_store)
    sf = view.symbol_factors(tick_paise=tick_paise)
    # Q-11 addendum 3 clause (ii): unparsed subjects are map NODES too, with {measured, absent}.
    unparsed = tuple(sorted({
        e.action.ex_date for e in view.parse_exceptions if e.action.symbol == symbol
    }))
    events = va.events_from_factor_table(
        sf.factors, sf.suppressions, sf.pending_ex_dates, symbol=symbol,
        unparsed_ex_dates=unparsed,
    )
    print("\nPRICE-MOVING EVENTS (era keys are built from these):")
    for e in events:
        compound = f"  [compound of {'+'.join(e.component_kinds)}]" if e.is_compound else ""
        print(f"   {e.ex_date}  {e.kind:16s} ours_price={e.our_price_factor} "
              f"share_count={e.is_share_count}{compound}")

    if not args.allow_network:
        print("\nSTOPPING: --allow-network is required to fetch the probe windows.")
        return 0

    print("\nlogging in to SmartAPI ...")
    client = SmartApiClient(Credentials.from_env()).login()
    print("  login OK; measuring probe windows (one ONE_MINUTE call each) ...")

    def on_window(w: va.WindowSpec, n: int) -> None:
        print(f"    fetched {w.label:12s} {w.start}..{w.end}  ->  {n} day(s)")

    try:
        eras = va.measure_symbol_live(client, daily_store, symbol, token, events, windows, fetch_date,
                                      on_window=on_window)
    finally:
        client.logout()

    amap = va.build_map(symbol, fetch_date, events, eras, tick_paise=tick_paise)
    _print_map(amap)
    _print_acceptance(amap, eras, tick_paise)

    if not args.no_persist:
        path = va.persist_map(amap, data_dir=data_dir)
        print(f"\npersisted map -> {path}")
    return 0


def _print_map(amap: va.AdjustmentMap) -> None:
    print("\n" + "=" * 78)
    print(f"ADJUSTMENT MAP  {amap.symbol}  (fetch F = {amap.fetch_date})")
    print("=" * 78)
    for era in amap.eras:
        print(f"\nERA [{era.label}]  events={[d.isoformat() for d in era.ex_dates]}  "
              f"PROVABLE={era.provable}")
        print(f"   k_price={era.k_price}")
        print(f"   k_volume={era.k_volume}")
        gap = "n/a" if era.volume_gap_pct is None else f"{era.volume_gap_pct:.4f}%"
        print(f"   price containment <= {era.price_containment_paise} paise | gate-1 median gap {gap}"
              f" | probes {[d.isoformat() for d in era.probe_days]}")
        for c in era.choices:
            print(f"     {c.kind:9s}@{c.ex_date}  price {c.price_source:8s} {c.price_factor}"
                  f"   vol {c.volume_source:8s} {c.volume_factor}")


def _print_acceptance(amap: va.AdjustmentMap, eras: list[va.EraMeasurement], tick_paise: int | None) -> None:
    """Consume the map on every probe day (folded to a 1-bar day) and check gate-1 + containment."""
    print("\n" + "-" * 78)
    print("CONSUMPTION ACCEPTANCE -- un-adjust each probe day THROUGH the map")
    print("-" * 78)
    all_ok = True
    for era in sorted(eras, key=lambda e: (len(e.ex_dates), e.ex_dates)):
        for p in era.probe_days:
            bar = OneMinuteBar(datetime.combine(p.day, time(9, 15)),
                               p.fetched_high, p.fetched_high, p.fetched_low, p.fetched_close, p.fetched_volume)
            res = va.unadjust_with_map([bar], amap, symbol=amap.symbol, tick_paise=tick_paise)
            day = res.days[0]
            un = res.raw_bars[0]
            g = volume_gate(p.raw_volume, un.volume)
            contained = max(abs(un.high_paise - p.raw_high), abs(un.low_paise - p.raw_low))
            ok = day.provable and g.passed
            all_ok = all_ok and ok
            flag = "" if ok else "   <-- FAIL"
            print(f"  {p.day}  provable={day.provable}  gate1={g.passed} ({g.gap_pct:.3f}%)  "
                  f"price|dH/dL|<= {contained}p{flag}")
    print(f"\nALL PROBE DAYS provable + gate-1 PASS: {all_ok}")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except (DailyStoreError, InstrumentMasterError, SmartApiError, va.VendorAdjustmentError) as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
