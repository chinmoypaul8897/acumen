"""Operator/reviewer report for the corporate-action engine (chunk 3; CONTEXT 4.2).

Prints, for one or more windows:

* the parse summary per source, and the **parse-exceptions report** -- every subject no
  CONTEXT 4.2 row explains, with the F&O-universe ones called out separately, because those
  are the ones that can change a price;
* the factor table, and the **pending** factors: events whose factor needs a price this
  engine was not given (rights issue price -- QUESTIONS.md Q-6; the pre-announcement close --
  Q-7). Nothing is ever filled in with k = 1;
* the demerger table (CONTEXT 3.2 suppresses the bias pair across those ex-dates);
* the **cross-source join**: NSE vs BSE vs Yahoo, ex-date and factor, disagreements listed.

By default it reads the FROZEN snapshots under `tests/fixtures/ca/`, so it runs offline and
reproduces exactly what the goldens assert. With ``--allow-network`` it pulls a live window
instead, through the same day-cached, politely paced fetchers.

    python -m acumen.ca_report
    python -m acumen.ca_report --from 2016-01-01 --to 2016-01-31 --allow-network

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from . import corp_actions as ca
from . import universe

#: The three windows the chunk-3 card names, and the snapshots frozen for them.
FROZEN_WINDOWS: tuple[tuple[str, date, date], ...] = (
    ("2016-01", date(2016, 1, 1), date(2016, 1, 31)),
    ("2023-07", date(2023, 7, 1), date(2023, 7, 31)),
    ("2024-10", date(2024, 10, 1), date(2024, 10, 31)),
)

#: Yahoo is a per-ticker stream, so the frozen tiebreak set is per symbol and window.
FROZEN_YAHOO: tuple[tuple[str, str], ...] = (
    ("KOTHARIPRO", "2015-12"),
    ("GREENPLY", "2015-12"),
    ("RELIANCE", "2024-10"),
    ("RELIANCE", "2023-07"),
)


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ca"


def load_frozen(
    directory: Path | None = None,
) -> tuple[list[ca.CorporateAction], list[ca.CorporateAction], list[ca.SplitRatio]]:
    """The frozen snapshots, parsed: (NSE actions, BSE actions, Yahoo splits)."""
    base = directory if directory is not None else fixtures_dir()
    nse: list[ca.CorporateAction] = []
    bse: list[ca.CorporateAction] = []
    for tag, _start, _end in FROZEN_WINDOWS:
        nse.extend(ca.parse_nse_payload(ca.load_snapshot(base / f"nse_ca_{tag}.json")))
        bse.extend(ca.parse_bse_csv(ca.load_snapshot(base / f"bse_ca_{tag}.csv")))
    yahoo: list[ca.SplitRatio] = []
    for symbol, tag in FROZEN_YAHOO:
        yahoo.extend(
            ca.parse_yahoo_chart(
                ca.load_snapshot(base / f"yahoo_splits_{symbol}_{tag}.json"), symbol
            )
        )
    return nse, bse, yahoo


def load_live(
    start: date, end: date, *, symbols: Sequence[str]
) -> tuple[list[ca.CorporateAction], list[ca.CorporateAction], list[ca.SplitRatio]]:
    """One live window from all three sources, day-cached and politely paced."""
    nse = list(ca.fetch_nse_corporate_actions(start, end, allow_network=True))
    bse = list(ca.fetch_bse_corporate_actions(start, end, allow_network=True))
    yahoo: list[ca.SplitRatio] = []
    for symbol in symbols:
        yahoo.extend(ca.fetch_yahoo_splits(symbol, start, end, allow_network=True))
    return nse, bse, yahoo


def _overrides() -> dict:
    """The committed rights-price overrides (QUESTIONS.md Q-6 tier 3); empty by design."""
    try:
        return ca.load_rights_overrides()
    except ca.CorporateActionError:
        return {}


def universe_symbols() -> tuple[str, ...]:
    """The F&O list, from the cached pull if there is one, else the frozen snapshot."""
    try:
        _fetched_on, symbols = universe.load_cached_universe()
        return symbols
    except Exception:
        snapshot = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "universe_snapshot.json"
        return universe.load_universe(snapshot)


def print_report(
    nse_actions: Iterable[ca.CorporateAction],
    bse_actions: Iterable[ca.CorporateAction],
    yahoo_splits: Iterable[ca.SplitRatio],
    *,
    symbols: Sequence[str],
) -> dict[str, int]:
    """Print every section and return the headline counts (also used by the tests)."""
    nse = ca.parse_actions(nse_actions)
    bse = ca.parse_actions(bse_actions)
    splits = list(yahoo_splits)

    print("PARSE SUMMARY " + "-" * 62)
    print(f"  NSE : {nse.summary()}")
    print(f"  BSE : {bse.summary()}")
    print(f"  Yahoo splits: {len(splits)}")

    print("\nPARSE EXCEPTIONS (never dropped; F&O-universe ones decide prices) " + "-" * 8)
    universe_exceptions = nse.exceptions_in(symbols) + bse.exceptions_in(symbols)
    for label, items in (("NSE", nse.exceptions), ("BSE", bse.exceptions)):
        distinct: dict[str, int] = {}
        for item in items:
            distinct[item.action.subject.strip()] = distinct.get(item.action.subject.strip(), 0) + 1
        print(f"  {label}: {len(items)} rows, {len(distinct)} distinct subject(s)")
        for subject, count in sorted(distinct.items(), key=lambda pair: -pair[1]):
            print(f"      {count:>4}x {subject!r}")
    print(f"  ON AN F&O-UNIVERSE SYMBOL: {len(universe_exceptions)}")
    for item in universe_exceptions:
        print(f"      {item.action.symbol} {item.action.ex_date} {item.action.subject!r}")
        print(f"          -> {item.reason}")

    table = ca.build_factor_table(nse.events, rights_overrides=_overrides())
    print("\nFACTOR TABLE (NSE) " + "-" * 57)
    print(f"  built: {len(table.factors)}   pending: {len(table.pending)}   "
          f"demergers: {len(table.demergers)}   suppressions: {len(table.suppressions)}")
    in_universe = [f for f in table.factors if f.symbol in set(symbols)]
    for factor in in_universe:
        print(f"      {factor.symbol:12} {factor.ex_date} {factor.kind:9} k={factor.k}")
        print(f"          {factor.basis}")
    if not in_universe:
        print("      (none on an F&O-universe symbol in this window)")

    print("\nPENDING FACTORS (a missing price is NEVER k=1) " + "-" * 30)
    reasons: dict[str, int] = {}
    for item in table.pending:
        key = "Q-6 rights, S recoverable, needs cum-close P" if "rights S recoverable" in item.needs else (
            "Q-7 dividend, needs P_cum" if "cum-date close" in item.needs else "other"
        )
        reasons[key] = reasons.get(key, 0) + 1
    for key, count in sorted(reasons.items()):
        print(f"      {count:>4}  {key}")

    print("\nDEMERGER TABLE (CONTEXT 3.2 blocks the bias pair across these) " + "-" * 13)
    for event in ca.demerger_table(nse.events):
        mark = "  <-- F&O universe" if event.symbol in set(symbols) else ""
        print(f"      {event.symbol:12} {event.ex_date}  {event.subject!r}{mark}")

    print("\nSUPPRESSIONS (demerger + Q-6 tier-2 rights; bias engine suppresses these) " + "-" * 2)
    for supp in ca.suppression_dates(table):
        mark = "  <-- F&O universe" if supp.symbol in set(symbols) else ""
        print(f"      {supp.symbol:12} {supp.ex_date} {supp.kind:9}{mark}  {supp.reason}")

    unresolved_rights = ca.unresolved_rights(table, symbols)
    print("\nUNRESOLVED RIGHTS ON F&O-UNIVERSE SYMBOLS (Q-6 override work-list) " + "-" * 8)
    if not unresolved_rights:
        print("      (none in this window)")
    for supp in unresolved_rights:
        print(f"      {supp.symbol:12} {supp.ex_date}  {supp.reason}")

    print("\nCROSS-SOURCE JOIN (NSE vs BSE vs Yahoo) " + "-" * 36)
    comparisons = ca.cross_source_report(nse.events, bse.events, splits)
    verdicts: dict[str, int] = {}
    for row in comparisons:
        verdicts[row.verdict] = verdicts.get(row.verdict, 0) + 1
    print(f"  {len(comparisons)} comparisons: " + ", ".join(
        f"{name}={count}" for name, count in sorted(verdicts.items())
    ))
    shared = [row for row in comparisons if row.nse_k is not None and row.bse_k is not None]
    print(f"  ratio compared with BSE: {len(shared)}, identical: "
          f"{sum(1 for row in shared if row.nse_k == row.bse_k)}")
    yahoo_rows = [row for row in comparisons if row.yahoo_k is not None]
    print(f"  ratio compared with Yahoo: {len(yahoo_rows)}, identical: "
          f"{sum(1 for row in yahoo_rows if row.nse_k == row.yahoo_k)}")
    disagreements = [row for row in comparisons if row.verdict == ca.DISAGREE]
    print(f"  DISAGREEMENTS: {len(disagreements)}")
    for row in disagreements:
        print(f"      {row.symbol} {row.ex_date} {row.kind}: {row.note}")

    return {
        "nse_events": len(nse.events),
        "bse_events": len(bse.events),
        "yahoo_splits": len(splits),
        "exceptions": len(nse.exceptions) + len(bse.exceptions),
        "universe_exceptions": len(universe_exceptions),
        "factors": len(table.factors),
        "pending": len(table.pending),
        "demergers": len(table.demergers),
        "suppressions": len(table.suppressions),
        "rights_suppressions": sum(1 for s in table.suppressions if s.kind == ca.KIND_RIGHTS),
        "unresolved_universe_rights": len(unresolved_rights),
        "comparisons": len(comparisons),
        "disagreements": len(disagreements),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-ca-report",
        description="Corporate-action parse, factor and cross-source report (CONTEXT 4.2).",
    )
    parser.add_argument("--from", dest="start", default=None, help="window start, YYYY-MM-DD")
    parser.add_argument("--to", dest="end", default=None, help="window end, YYYY-MM-DD")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="pull the window live instead of reading the frozen snapshots",
    )
    parser.add_argument(
        "--yahoo",
        default="",
        help="comma-separated symbols to pull Yahoo splits for (live mode only)",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    symbols = universe_symbols()
    if args.allow_network:
        if not args.start or not args.end:
            print("--allow-network needs --from and --to.")
            return 2
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
        tickers = [s.strip().upper() for s in args.yahoo.split(",") if s.strip()]
        print(f"LIVE window {start} .. {end} (Yahoo: {tickers or 'none'})\n")
        nse, bse, yahoo = load_live(start, end, symbols=tickers)
    else:
        print("FROZEN snapshots: " + ", ".join(tag for tag, _s, _e in FROZEN_WINDOWS) + "\n")
        nse, bse, yahoo = load_frozen()
    print_report(nse, bse, yahoo, symbols=symbols)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
