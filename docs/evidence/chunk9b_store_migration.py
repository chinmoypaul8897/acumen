"""Q-18 LAYER 1 verification: every store reached through the NEW out-of-repo roots.

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_store_migration.py --out docs/evidence/chunk9b_store_migration.md

OFFLINE and READ-ONLY on both stores. Every network entry point the corporate-action path can
reach is monkeypatched to RAISE before the CA check runs, so "served from disk" is proved by
construction rather than asserted -- the same discipline the Q-18 Part-0 sweep used.

WHAT THIS PROVES. On 02-Aug-2026 the operator moved the two mutable stores out of the
repository tree, to `paths.data_root` / `paths.cache_root` in config.yaml (CLAUDE.md,
"Data-store safety", Q-18 layer 1). A move is not a copy: if anything were lost or if any
code path still pointed at the old in-repo location, it would show up as a smaller number
here, not as an error. So each check re-measures a figure this repo already published
elsewhere and compares digit for digit:

* the daily ledger's coverage over 2000-01-01..2026-07-30 vs CONTEXT 4.6 (v1.5);
* the minute lake's stored symbol-day count vs CONTEXT 4.6 (v1.5)'s 435,641;
* the corporate-action day-cache's row count vs the reconciliation report's 41,372;
* the disclosed-residual register's 204 settled / 6 quarantined;
* the instrument master, resolved by token AND tick for real sealed symbols.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen.config import REPO_ROOT, ConfigError, load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402
from acumen.recovery_reconcile import (  # noqa: E402
    REBUILT_REPORT_RELPATH,
    measure_days,
    read_report,
)

#: CONTEXT 4.6 (v1.5) -- the RE-SEALED numbers this migration must not have moved.
EXPECTED_STORED_DAYS = 435_641
EXPECTED_SETTLED = 204
EXPECTED_QUARANTINED = 6
EXPECTED_DAILY_PRESENT = 6_610
DAILY_FROM = date(2000, 1, 1)
DAILY_TO = date(2026, 7, 30)

#: The rebuilt day-cache's row count, from `docs/recovery/q18_reconciliation.md` section 0 --
#: the artefact CONTEXT 4.6 (v1.5) names as the authoritative delta record, and the LAST thing
#: written against this cache.
#:
#: Not 41,371, which is what `docs/evidence/q18_part0_verification.md` recorded earlier the
#: same session. Both numbers are right at their own moment and the store is intact: the
#: Part-0 sweep ran at 01:13, the architect's T4 ruling then re-fetched EXIDEIND and NUVAMA
#: over the network (sanctioned for exactly those two), which REWROTE ELEVEN day-cache year
#: files -- 2016 through 2026, at 01:16:35.76 .. 01:16:55.61 -- and the reconciliation
#: regenerated afterwards saw 41,372. The file mtimes still order the three events that way on
#: disk, and the sweep re-lists them below rather than asserting the span from memory.
#:
#: What this evidence does and does NOT establish: it shows the cache was rewritten between
#: the two readings by a SANCTIONED fetch, which accounts for a changed count. It does not
#: localise WHICH single row differs -- the pre-T4 cache was overwritten in place and no copy
#: of it survives, so that row cannot be named from anything on this machine.
EXPECTED_CA_ROWS = 41_372
CA_FROM_YEAR, CA_TO_YEAR = 2005, 2026

#: The day the architect's T4 ruling re-fetched EXIDEIND and NUVAMA (the only sanctioned
#: network action of that session), which rewrote part of the day-cache.
T4_REFETCH_DATE = date(2026, 8, 2)


class Sweep:
    """Ordered checks with a PASS/FAIL and a measured detail each."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, fn: Callable[[], tuple[bool, str]]) -> None:
        try:
            ok, detail = fn()
        except Exception as exc:  # a check that cannot run has FAILED, loudly
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        self.rows.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {detail}", flush=True)

    @property
    def ok(self) -> bool:
        return all(ok for _name, ok, _detail in self.rows)


def _tree(root: Path, skip: Path | None = None) -> tuple[int, int, float]:
    files = dirs = 0
    size = 0
    for parent, dnames, fnames in os.walk(root):
        here = Path(parent).resolve()
        if skip is not None and (here == skip or skip in here.parents):
            continue
        dirs += len(dnames)
        files += len(fnames)
        for name in fnames:
            try:
                size += (Path(parent) / name).stat().st_size
            except OSError:
                pass
    return files, dirs, size / 1024 / 1024 / 1024


def _forbid_network() -> list[str]:
    """Make every reachable network entry point RAISE. Returns what was blocked."""
    import requests

    from acumen import nse_http

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "NETWORK REACHED. This verification is offline by contract: the corporate-action "
            "day-cache must be served from disk at any age (the architect's C3 ruling)."
        )

    blocked: list[str] = []
    for module, name in (
        (nse_http, "cached_json_fetch"),
        (nse_http, "fetch_json"),
        (nse_http, "fetch_binary"),
        (nse_http, "new_session"),
        (requests, "get"),
        (requests, "request"),
        (requests.Session, "get"),
        (requests.Session, "request"),
    ):
        if hasattr(module, name):
            setattr(module, name, refuse)
            label = getattr(module, "__name__", module.__class__.__name__)
            blocked.append(f"{label}.{name}")
    return blocked


def run(out_path: Path | None) -> int:
    sweep = Sweep()
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    cache_root = config.path("cache_root")
    repo = REPO_ROOT.resolve()

    # --- 1. the layer itself -------------------------------------------------------------
    def layer_one() -> tuple[bool, str]:
        inside = [
            name
            for name, root in (("data_root", data_root), ("cache_root", cache_root))
            if root.resolve().is_relative_to(repo)
        ]
        old = [p for p in (repo / "data", repo / "cache") if p.exists()]
        return (
            not inside and not old and data_root.is_dir() and cache_root.is_dir(),
            f"data_root={data_root} cache_root={cache_root}; neither is under {repo}; the old "
            f"in-repo locations are GONE ({', '.join(str(p) for p in old) or 'data/ and cache/ absent'})"
            if not inside and not old
            else f"inside the repo tree: {inside or 'none'}; old locations still present: {old}",
        )

    sweep.check("1. both store roots live OUTSIDE the repository tree; old locations gone",
                layer_one)

    def loader_refuses() -> tuple[bool, str]:
        """The layer is structural: prove the loader refuses a config that points back in."""
        import tempfile

        bad = (
            "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
            f"paths:\n  data_root: {(repo / 'data').as_posix()}\n"
            f"  cache_root: {cache_root.as_posix()}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(bad, encoding="utf-8")
            try:
                load_config(path, include_env=False)
            except ConfigError as exc:
                return "INSIDE the repository tree" in str(exc), f"refused: {exc}"
        return False, "a config pointing at an in-repo store root LOADED -- the layer is not enforced"

    sweep.check("2. the loader REFUSES a store root inside the repo (layer 1 is structural)",
                loader_refuses)

    def sizes() -> tuple[bool, str]:
        d_files, d_dirs, d_gb = _tree(data_root, skip=cache_root.resolve())
        c_files, c_dirs, c_gb = _tree(cache_root)
        return (
            d_files > 0 and c_files > 0,
            f"data_root {d_files:,} files / {d_dirs:,} dirs / {d_gb:.2f} GiB (excluding the "
            f"nested cache_root); cache_root {c_files:,} files / {c_dirs:,} dirs / {c_gb:.2f} GiB",
        )

    sweep.check("3. both trees are populated at the new location", sizes)

    # --- 2. the daily store (the gate-1 / gate-1P raw oracle) ----------------------------
    daily = DailyStore.at(data_root / "daily_store")

    def daily_ledger() -> tuple[bool, str]:
        from acumen import bhavcopy

        summary = daily.coverage_summary(DAILY_FROM, DAILY_TO)
        present = summary[bhavcopy.OUTCOME_PRESENT]
        errors = summary[bhavcopy.OUTCOME_ERROR]
        missing = summary["missing"]
        pending = summary.get(bhavcopy.OUTCOME_PENDING, 0)
        return (
            present == EXPECTED_DAILY_PRESENT and errors == 0 and missing == 0 and pending == 0,
            f"{DAILY_FROM} .. {DAILY_TO}: file-present {present:,} (CONTEXT 4.6 v1.5 says "
            f"{EXPECTED_DAILY_PRESENT:,}), confirmed-404 "
            f"{summary[bhavcopy.OUTCOME_NOT_FOUND]:,}, error {errors}, never-attempted "
            f"{missing}, pending {pending}, weekend sessions {summary['weekend_session']}",
        )

    sweep.check("4. daily ledger summary through data_root matches CONTEXT 4.6 (v1.5)",
                daily_ledger)

    # --- 3. the minute lake --------------------------------------------------------------
    store = MinuteStore.at(data_root / "minute_store")
    rebuilt = read_report(REPO / REBUILT_REPORT_RELPATH)

    def minute_days() -> tuple[bool, str]:
        # This check opens ~21,000 parquet month files, so it is the one step that takes
        # minutes rather than seconds. It prints as it goes: a silent quarter-hour is
        # indistinguishable from a hang, and this script gets run by an operator.
        stored: dict[str, tuple] = {}
        for index, symbol in enumerate(rebuilt.symbols, start=1):
            stored[symbol] = tuple(store.stored_days(symbol))
            if index % 25 == 0 or index == len(rebuilt.symbols):
                running = sum(len(v) for v in stored.values())
                print(
                    f"       ... {index}/{len(rebuilt.symbols)} symbols read, "
                    f"{running:,} stored symbol-days so far",
                    flush=True,
                )
        measured = measure_days(stored, scope_end=rebuilt.scope_end)
        total = sum(measured[s].days_in_scope for s in rebuilt.symbols)
        return (
            total == EXPECTED_STORED_DAYS,
            f"{total:,} stored symbol-days re-counted from the parquet files under "
            f"{store.minute_dir}, over {len(rebuilt.symbols)} symbols to the rebuilt scope end "
            f"{rebuilt.scope_end} -- CONTEXT 4.6 (v1.5) seals {EXPECTED_STORED_DAYS:,}",
        )

    sweep.check("5. minute-store day count = CONTEXT 4.6 (v1.5)'s 435,641", minute_days)

    # --- 4. the disclosed-residual register ----------------------------------------------
    def register() -> tuple[bool, str]:
        entries = bt.load_residual_register(data_root / bt.RESIDUAL_LEDGER_RELPATH)
        settled = sorted(s for s, e in entries.items() if e.status == "settled")
        quarantined = sorted(s for s, e in entries.items() if e.status != "settled")
        return (
            len(settled) == EXPECTED_SETTLED and len(quarantined) == EXPECTED_QUARANTINED,
            f"{len(settled)} settled / {len(quarantined)} quarantined "
            f"({', '.join(quarantined)}) from {bt.RESIDUAL_LEDGER_RELPATH} under data_root",
        )

    sweep.check("6. disclosed-residual register loads: 204 settled / 6 quarantined", register)

    # --- 5. the CA day-cache, offline ----------------------------------------------------
    blocked = _forbid_network()

    def ca_cache() -> tuple[bool, str]:
        from acumen.minute_backfill import fetch_corp_action_history

        # MEASURED, not remembered: which year files T4's sanctioned re-fetch actually touched.
        rewritten = sorted(
            (
                datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S.%f")[:-4],
                path.name.replace("nse_ca_", "").split("-")[0],
            )
            for path in (data_root / "nse" / "ca").glob("*.json")
            if datetime.fromtimestamp(path.stat().st_mtime).date() == T4_REFETCH_DATE
        )
        if not rewritten:
            rewritten = [("--", "--")]

        actions = fetch_corp_action_history(
            date(CA_FROM_YEAR, 1, 1), date(CA_TO_YEAR, 12, 31),
            allow_network=False, cache_dir=None,
        )
        return (
            len(actions) == EXPECTED_CA_ROWS,
            f"{len(actions):,} corporate-action rows parsed from the day-cache under "
            f"data_root for {CA_FROM_YEAR}..{CA_TO_YEAR}, with {len(blocked)} network entry "
            f"point(s) patched to raise ({', '.join(blocked)}) and no request escaped -- "
            f"docs/recovery/q18_reconciliation.md section 0 records {EXPECTED_CA_ROWS:,} "
            f"(NOT the 41,371 the earlier Part-0 sweep saw: T4's sanctioned EXIDEIND/NUVAMA "
            f"re-fetch rewrote {len(rewritten)} day-cache year file(s), "
            f"{rewritten[0][1]}..{rewritten[-1][1]}, at {rewritten[0][0]}..{rewritten[-1][0]}, "
            f"between the two readings; the single differing row cannot be localised because "
            f"the pre-T4 cache was overwritten in place)",
        )

    sweep.check("7. CA day-cache loads from cache_root/data_root, OFFLINE, at any age", ca_cache)

    # --- 6. the instrument master --------------------------------------------------------
    def master() -> tuple[bool, str]:
        loaded, path = bt.latest_cached_master(cache_root)
        probes = ("RELIANCE", "TCS", "HDFCBANK", "APLAPOLLO", "NESTLEIND")
        resolved = []
        for symbol in probes:
            entry = loaded.by_symbol.get(symbol)
            if entry is None:
                return False, f"{symbol} does not resolve in {path.name}"
            resolved.append(f"{symbol} token={entry.token} tick={entry.tick_size_paise}p")
        return (
            True,
            f"{path.name} ({len(loaded.by_symbol):,} NSE-EQ instruments) read through "
            f"cache_root; " + "; ".join(resolved),
        )

    sweep.check("8. instrument master resolves token AND tick through cache_root", master)

    lines = _render(sweep, data_root, cache_root, blocked)
    text = "\n".join(lines) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"\nwritten: {out_path}")
    print(f"\nVERDICT: {'ALL CHECKS PASS' if sweep.ok else 'FAILED'}")
    return 0 if sweep.ok else 1


def _render(sweep: Sweep, data_root: Path, cache_root: Path, blocked: list[str]) -> list[str]:
    lines = [
        "# chunk 9B RESUME-1 -- store migration verified through the NEW roots",
        "",
        "Generated by `docs/evidence/chunk9b_store_migration.py`, committed under CLAUDE.md's",
        "evidence rule. Offline and read-only on both stores.",
        "",
        "The operator moved the two mutable stores out of the repository tree on 02-Aug-2026",
        "(CLAUDE.md, \"Data-store safety\", Q-18 layer 1). A move is not a copy, so every check",
        "below re-measures a figure this repo already published and compares it digit for digit:",
        "a loss, or a code path still pointing at the old in-repo location, would show up as a",
        "smaller number rather than as an error.",
        "",
        f"- `data_root`  : `{data_root}`",
        f"- `cache_root` : `{cache_root}`",
        f"- network      : {len(blocked)} entry point(s) patched to raise before the CA check",
        "",
        "| # | Check | Verdict | Measured |",
        "|---|---|---|---|",
    ]
    for name, ok, detail in sweep.rows:
        number, _, title = name.partition(". ")
        lines.append(
            f"| {number} | {title} | {'**PASS**' if ok else '**FAIL**'} | {detail} |"
        )
    lines += [
        "",
        f"**VERDICT: {'ALL CHECKS PASS' if sweep.ok else 'FAILED'}** "
        f"({sum(1 for _n, ok, _d in sweep.rows if ok)} of {len(sweep.rows)}).",
        "",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chunk9b_store_migration")
    parser.add_argument("--out", default=None, help="write the report here as well as stdout")
    args = parser.parse_args(argv)
    return run(Path(args.out) if args.out else None)


if __name__ == "__main__":
    raise SystemExit(main())
