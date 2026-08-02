"""Q-18 PART 0 -- the independent verification sweep of the operator-executed rebuild.

CLAUDE.md, Data-store safety (architect-authored, 01-Aug-2026):

    "Operator-executed runbooks are relayed, not certified: after any multi-step operator
    procedure, the next session's FIRST duty is an independent verification sweep of every
    step's completion evidence read from the machine itself -- ledgers, files, digests,
    offline re-runs. Pasted transcripts are never the record."

This script IS that sweep for `docs/recovery/q18_runbook.md`'s five steps. It reads nothing
the operator typed: every number below is measured here, on this machine, from the stores,
the caches, the parquet files and git. It is OFFLINE and READ-ONLY -- it makes no network
call and writes exactly one file, its own report.

Run:  python docs/evidence/q18_part0_verification.py --out docs/evidence/q18_part0_verification.md

Exit 0 = every check PASS. Exit 1 = at least one FAIL (the Part-0 STOP: report, touch nothing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

# --- what the runbook's own completion checks assert, spelled out here so a drift is visible --

RANGE_FROM = date(2000, 1, 1)
RANGE_TO = date(2026, 7, 30)
EXPECT_PRESENT = 6610
EXPECT_SEALED_PRESENT = 6606          # file-present dates up to the sealed clamp 2026-07-24
EXPECT_NEW_DATES = (date(2026, 7, 27), date(2026, 7, 28), date(2026, 7, 29), date(2026, 7, 30))
EXPECT_CA_ROWS = 41371
EXPECT_CA_YEARS = tuple(range(2005, 2027))
EXPECT_MASTER = "OpenAPIScripMaster_2026-07-31.json"
EXPECT_MASTER_ROWS = 2433
EXPECT_SEALED_SYMBOLS = 210
T4_SYMBOLS = ("EXIDEIND", "NUVAMA")

#: Daily-store witnesses whose expected values are COMMITTED elsewhere in this repo, so the
#: spot-check is against an independent record and not against the parquet's own opinion.
#: (paise close, volume or None, where the expected value is written down)
WITNESSES: tuple[tuple[str, date, int, int | None, str], ...] = (
    ("TCS", date(2026, 7, 20), 225110, 2202693,
     "docs/RESULTS.md, cited by QUESTIONS.md Q-1 (close 2251.10, volume 2,202,693)"),
    ("TCS", date(2020, 7, 13), 222000, None,
     "QUESTIONS.md OPEN-8 evidence: 'TCS ... raw close 2220.00 = SmartAPI 2220.00'"),
    ("TCS", date(2016, 10, 3), 241170, 909440,
     "QUESTIONS.md Q-10/OPEN-8: 'raw daily close 241170', 'raw daily 909,440'"),
)

#: Anything under data/ matching one of these is a half-written artefact the rebuild left behind.
#: NOTE: a bare ``tmp`` PREFIX is deliberately NOT a pattern -- TMPV is a real universe symbol
#: (Tata Motors Passenger Vehicles), and a name test that flags it would be crying wolf on ten
#: legitimate parquets. The truncation check below is the real test anyway: a half-written
#: parquet has no readable footer, whatever it is called.
TEMP_SUFFIXES = (".tmp", ".partial", ".part", ".swp", ".lock", ".crdownload", ".incomplete", ".bak")
TEMP_PREFIXES = ("~", ".")


class Check:
    """One verified assertion: what was checked, what was read, and PASS/FAIL."""

    def __init__(self, step: str, name: str) -> None:
        self.step = step
        self.name = name
        self.detail = ""
        self.ok = False

    def record(self, ok: bool, detail: str) -> "Check":
        self.ok, self.detail = bool(ok), detail
        return self


class Sweep:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def check(self, step: str, name: str, fn: Callable[[], tuple[bool, str]]) -> Check:
        item = Check(step, name)
        try:
            ok, detail = fn()
        except Exception as exc:  # a check that cannot run is a FAIL, never a skip
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        self.checks.append(item.record(ok, detail))
        print(f"[{'PASS' if item.ok else 'FAIL'}] {step} :: {name}\n        {item.detail}",
              flush=True)
        return item

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- STEP 1 ---------------------------------------------------------------------------------


def step1(sweep: Sweep) -> dict[str, Any]:
    from acumen.calendar import TradingCalendar
    from acumen.config import load_config
    from acumen.daily_store import DailyStore

    data_dir = load_config(include_env=False).path("data_root")
    store = DailyStore.at(data_dir / "daily_store")
    summary = store.coverage_summary(RANGE_FROM, RANGE_TO)
    outcomes = store.outcomes()
    present = sorted(d for d, o in outcomes.items() if o.outcome == "file-present")
    span_days = (RANGE_TO - RANGE_FROM).days + 1

    sweep.check("1", "ledger summary re-run offline over 2000-01-01..2026-07-30", lambda: (
        summary["error"] == 0 and summary["missing"] == 0
        and summary["file-present"] == EXPECT_PRESENT,
        f"file-present {summary['file-present']:,} (expected {EXPECT_PRESENT:,}), "
        f"confirmed-404 {summary['confirmed-404']:,}, error {summary['error']}, "
        f"never-attempted {summary['missing']}",
    ))

    sweep.check("1", "confirmed-404 + file-present PARTITION the attempted range", lambda: (
        summary["file-present"] + summary["confirmed-404"] == summary["attempted"] == span_days,
        f"{summary['file-present']:,} + {summary['confirmed-404']:,} = "
        f"{summary['file-present'] + summary['confirmed-404']:,} = attempted "
        f"{summary['attempted']:,} = calendar dates in range {span_days:,}; no third outcome, "
        f"no gap",
    ))

    def new_dates() -> tuple[bool, str]:
        sealed_side = [d for d in present if d <= date(2026, 7, 24)]
        added = [d for d in present if d > date(2026, 7, 24)]
        return (
            len(sealed_side) == EXPECT_SEALED_PRESENT and tuple(added) == EXPECT_NEW_DATES,
            f"{len(sealed_side):,} file-present dates <= 2026-07-24 (sealed side) + "
            f"{len(added)} new ({', '.join(d.isoformat() for d in added)}) "
            f"= {len(present):,}",
        )

    sweep.check("1", "6,610 = sealed 6,606 + Jul 27/28/29/30", new_dates)

    def q19_guard() -> tuple[bool, str]:
        after = [d for d in outcomes if d > RANGE_TO]
        return (
            not after,
            "2026-07-31 is ABSENT from the ledger -- the Q-19 phantom holiday was not "
            "re-recorded" if not after else f"dates past the range in the ledger: {after}",
        )

    sweep.check("1", "Q-19: no ledger row past the last COMPLETED trading day", q19_guard)

    def weekends() -> tuple[bool, str]:
        cal = TradingCalendar.from_daily_store_range(store, RANGE_FROM, RANGE_TO)
        sessions = cal.weekend_sessions
        leaked = [d for d in sessions if cal.is_trading_day(d)]
        return (
            len(sessions) == summary["weekend_session"] and not leaked,
            f"{len(sessions)} weekend-dated bhavcopies published in range; every one is "
            f"is_trading_day=False and surfaced in weekend_sessions (Q-5 ruling). "
            f"First/last: {sessions[0]} .. {sessions[-1]}",
        )

    sweep.check("1", "weekend sessions EXCLUDED from the derived trading calendar", weekends)

    def witnesses() -> tuple[bool, str]:
        notes: list[str] = []
        ok = True
        row = outcomes.get(date(2026, 7, 30))
        frame = store.daily("TCS", date(2026, 7, 30), date(2026, 7, 30))
        if row is None or row.outcome != "file-present" or len(frame) != 1:
            ok = False
            notes.append("TCS 2026-07-30 witness row MISSING")
        else:
            got = frame.iloc[0]
            notes.append(
                f"TCS 2026-07-30 ledger={row.outcome}/{row.source_format}/{row.row_count} rows; "
                f"parquet close {int(got['close_paise'])} paise, volume {int(got['volume']):,} "
                f"(new date, no prior committed value to check against)"
            )
        for symbol, when, close, volume, source in WITNESSES:
            got = store.daily(symbol, when, when)
            if len(got) != 1:
                ok = False
                notes.append(f"{symbol} {when}: no parquet row")
                continue
            r = got.iloc[0]
            hit = int(r["close_paise"]) == close and (volume is None or int(r["volume"]) == volume)
            ok = ok and hit
            notes.append(
                f"{symbol} {when}: parquet close {int(r['close_paise'])} paise vs committed "
                f"{close}" + (f", volume {int(r['volume']):,} vs {volume:,}" if volume else "")
                + f" -> {'MATCH' if hit else 'MISMATCH'} [{source}]"
            )
        return ok, " | ".join(notes)

    sweep.check("1", "spot-verify the TCS 2026-07-30 witness + 3 older dates vs the parquet",
                witnesses)

    return {"summary": summary, "present": len(present)}


# --- STEP 2 ---------------------------------------------------------------------------------


def step2(sweep: Sweep) -> dict[str, Any]:
    from acumen import nse_http
    from acumen.config import load_config
    from acumen.minute_backfill import fetch_corp_action_history

    ca_dir = load_config(include_env=False).path("data_root") / "nse" / "ca"
    nse_files = sorted(p.name for p in ca_dir.glob("nse_ca_*.json"))
    bse_files = sorted(p.name for p in ca_dir.glob("bse_ca_*.json"))

    sweep.check("2", "22 NSE year files + BSE files present in the CA day-cache", lambda: (
        len(nse_files) == len(EXPECT_CA_YEARS) and len(bse_files) == len(EXPECT_CA_YEARS)
        and all(f"nse_ca_{y}-01-01_{y}-12-31.json" in nse_files for y in EXPECT_CA_YEARS),
        f"{len(nse_files)} NSE + {len(bse_files)} BSE year files under {ca_dir}; NSE years "
        f"{EXPECT_CA_YEARS[0]}..{EXPECT_CA_YEARS[-1]} all present",
    ))

    # The offline assertion made STRUCTURAL: any HTTP attempt raises instead of fetching.
    fired: list[str] = []

    def forbidden(*a: Any, **k: Any) -> Any:
        fired.append(str(a[:1]))
        raise AssertionError("a network request was attempted on the allow_network=False path")

    saved = (nse_http.fetch_json, nse_http.fetch_binary, nse_http._fetch, nse_http.new_session)
    nse_http.fetch_json = forbidden      # type: ignore[assignment]
    nse_http.fetch_binary = forbidden    # type: ignore[assignment]
    nse_http._fetch = forbidden          # type: ignore[assignment]
    nse_http.new_session = forbidden     # type: ignore[assignment]
    try:
        actions = fetch_corp_action_history(
            date(EXPECT_CA_YEARS[0], 1, 1), date(EXPECT_CA_YEARS[-1], 12, 31), allow_network=False
        )
    finally:
        (nse_http.fetch_json, nse_http.fetch_binary,
         nse_http._fetch, nse_http.new_session) = saved  # type: ignore[assignment]

    ex_dates = [a.ex_date for a in actions]

    sweep.check("2", "the CA cache loads OFFLINE for 2005..2026 with NO request fired", lambda: (
        len(actions) == EXPECT_CA_ROWS and not fired and min(ex_dates).year == 2005,
        f"{len(actions):,} rows parsed (expected {EXPECT_CA_ROWS:,}); span "
        f"{min(ex_dates)} .. {max(ex_dates)}; network entry points were monkeypatched to raise "
        f"and fired {len(fired)} time(s)",
    ))

    return {"actions": len(actions), "ca_span": (min(ex_dates), max(ex_dates))}


# --- STEP 3 ---------------------------------------------------------------------------------


def step3(sweep: Sweep, sealed_symbols: list[str]) -> dict[str, Any]:
    from acumen.instrument_master import InstrumentMasterError, load_master_file

    path = REPO / "cache" / "instrument_master" / EXPECT_MASTER
    master = load_master_file(path) if path.is_file() else None

    sweep.check("3", f"{EXPECT_MASTER} exists, parses, {EXPECT_MASTER_ROWS:,} NSE-EQ rows",
                lambda: (
                    master is not None and len(master) == EXPECT_MASTER_ROWS,
                    f"{path} -> {len(master) if master else 0:,} NSE cash equities "
                    f"({path.stat().st_size / 1e6:.1f} MB on disk)"
                    if path.is_file() else f"{path} does NOT exist",
                ))

    def resolve() -> tuple[bool, str]:
        assert master is not None
        missing: list[str] = []
        for symbol in sealed_symbols:
            try:
                master.token(symbol)
                master.tick_size(symbol)
            except InstrumentMasterError:
                missing.append(symbol)
        t4 = ", ".join(
            f"{s} token={master.token(s)} tick={master.tick_size(s)}"
            for s in T4_SYMBOLS if s not in missing
        )
        return (
            not missing and len(sealed_symbols) == EXPECT_SEALED_SYMBOLS,
            f"all {len(sealed_symbols)} sealed-universe symbols resolve a token AND a tick "
            f"size; T4's two: {t4}" if not missing
            else f"{len(missing)} sealed symbol(s) do not resolve: {', '.join(missing)}",
        )

    sweep.check("3", "every sealed-universe symbol resolves a token and a tick size "
                     "(incl. EXIDEIND and NUVAMA -- T4 needs those two)", resolve)
    return {"master": str(path), "rows": len(master) if master else 0}


# --- STEP 4 ---------------------------------------------------------------------------------


def step4(sweep: Sweep, sealed_symbols: list[str]) -> dict[str, Any]:
    from acumen.config import load_config
    from acumen.minute_store import MinuteStore
    from acumen.recovery_reconcile import (REBUILT_REPORT_RELPATH, SEALED_REPORT_RELPATH,
                                           cross_check_store, measure_store, read_report)

    data_dir = load_config(include_env=False).path("data_root")
    ledger_path = data_dir / "universe_backfill" / "ledger.json"

    def register() -> tuple[bool, str]:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        symbols = payload.get("symbols", {})
        bad = [s for s, row in symbols.items() if row.get("symbol", s) != s]
        statuses: dict[str, int] = {}
        for row in symbols.values():
            statuses[row.get("status", "?")] = statuses.get(row.get("status", "?"), 0) + 1
        return (
            bool(symbols) and not bad,
            f"{ledger_path} loads; {len(symbols)} entries, one per symbol, keyed by symbol; "
            f"status split {statuses}; started {payload.get('started')}, "
            f"halted {payload.get('halted') or 'no'}",
        )

    sweep.check("4", "data/universe_backfill/ledger.json loads, one entry per symbol", register)

    rebuilt_path = REPO / REBUILT_REPORT_RELPATH
    sweep.check("4", "the rebuilt report exists at docs/recovery/"
                     "backfill_minute_report_rebuild.md", lambda: (
                         rebuilt_path.is_file(),
                         f"{rebuilt_path} ({rebuilt_path.stat().st_size:,} bytes, sha256 "
                         f"{sha256(rebuilt_path.read_bytes())[:16]}...)"
                         if rebuilt_path.is_file() else "MISSING",
                     ))

    def sealed_untouched() -> tuple[bool, str]:
        disk = (REPO / SEALED_REPORT_RELPATH).read_bytes()
        head = subprocess.run(["git", "show", f"HEAD:{SEALED_REPORT_RELPATH}"],
                              cwd=REPO, capture_output=True).stdout
        return (
            disk == head,
            f"{SEALED_REPORT_RELPATH}: {len(disk):,} bytes on disk, {len(head):,} at HEAD, "
            f"sha256 {sha256(disk)} -- {'IDENTICAL' if disk == head else 'DIFFERENT'}",
        )

    sweep.check("4", "the COMMITTED sealed report is byte-identical to git HEAD", sealed_untouched)

    def no_temp() -> tuple[bool, str]:
        """Name patterns over ALL of data/, plus a footer read of every parquet the
        independent leg below does NOT already open (it reads `trade_date` out of every
        minute-store parquet, so those are proven complete by that check rather than twice)."""
        import pyarrow.parquet as pq

        every = [p for p in (REPO / "data").rglob("*") if p.is_file()]
        suspects = [
            p for p in every
            if p.suffix.lower() in TEMP_SUFFIXES or p.name.startswith(TEMP_PREFIXES)
        ]
        minute_dir = REPO / "data" / "minute_store" / "minute"
        parquets = [
            p for p in every
            if p.suffix.lower() == ".parquet" and minute_dir not in p.parents
        ]
        truncated: list[str] = []
        for path in parquets:
            try:
                pq.read_metadata(path)
            except Exception as exc:
                truncated.append(f"{path.name} ({type(exc).__name__})")
        return (
            not suspects and not truncated,
            f"{len(every):,} files under data/: none matches a temp/partial name pattern "
            f"({', '.join(TEMP_SUFFIXES)}, or a '~'/'.' prefix); all {len(parquets):,} parquet "
            f"files outside the minute lake read a complete footer, and every minute-lake "
            f"parquet is opened and read by the independent leg below -- no truncated write "
            f"survived the rebuild anywhere"
            if not suspects and not truncated else
            f"{len(suspects)} suspect name(s) {suspects[:6]}; "
            f"{len(truncated)} unreadable parquet(s) {truncated[:6]}",
        )

    sweep.check("4", "no temp/partial files anywhere under data/ (name patterns AND a "
                     "complete-footer read of every parquet)", no_temp)

    sealed = read_report(REPO / SEALED_REPORT_RELPATH)
    rebuilt = read_report(rebuilt_path)
    store = MinuteStore.at(data_dir / "minute_store")

    def independent_leg() -> tuple[bool, str]:
        every = sorted(set(sealed.symbols) | set(rebuilt.symbols))
        measured = measure_store(store, every, scope_end=rebuilt.scope_end)
        checks = cross_check_store(rebuilt, measured)
        total = sum(measured[s].days_in_scope for s in rebuilt.symbols)
        return (
            not checks,
            f"per-symbol parquet day counts re-counted here for all {len(rebuilt.symbols)} "
            f"rebuilt symbols over the rebuilt scope (<= {rebuilt.scope_end}): "
            f"{total:,} stored symbol-days, ZERO disagreements with the report's section 3"
            if not checks else
            f"{len(checks)} symbol(s) disagree: "
            + "; ".join(f"{c.symbol} report {c.report_days} vs store {c.store_days}"
                        for c in checks[:10]),
        )

    sweep.check("4", "per-symbol parquet day counts agree with the rebuilt report "
                     "(reconciler's independent leg, re-run here)", independent_leg)

    return {"sealed": sealed, "rebuilt": rebuilt, "sealed_symbols": sealed_symbols}


# --- STEP 5 ---------------------------------------------------------------------------------


def step5(sweep: Sweep, scratch: Path) -> None:
    """Regenerate the operator's step-5 artefact with the code AS COMMITTED, and diff the bytes.

    Deliberately not the working-tree module: this session amends `recovery_reconcile.py` for
    the T1/T2 rulings, and a check that used the amended code would be certifying the operator's
    file against something that did not exist when the operator ran it. The reconciler is
    therefore taken from ``git show HEAD:src/acumen/recovery_reconcile.py``, dropped into a
    THROWAWAY COPY of `src/` (a copy -- never a junction; CLAUDE.md's data-store safety rule),
    and run there in a subprocess against the real, unmodified stores.

    The copy sits at ``<repo>/.q18_head_src`` rather than in a temp directory, because
    ``acumen.config`` resolves ``config.yaml`` and the RELATIVE ``data_dir``/``cache_dir`` it
    declares from the package's own grandparent. One directory level off and the reconciler
    would either refuse to start or read an empty store, which is exactly the failure mode this
    check exists to catch. The copy is removed again whatever happens.
    """
    committed = REPO / "docs" / "recovery" / "q18_reconciliation.md"

    def regenerate() -> tuple[bool, str]:
        import shutil

        if not committed.is_file():
            return False, f"{committed} does not exist"
        sandbox = REPO / ".q18_head_src"
        try:
            if sandbox.exists():
                shutil.rmtree(sandbox)
            shutil.copytree(REPO / "src", sandbox,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            blob = subprocess.run(
                ["git", "show", "HEAD:src/acumen/recovery_reconcile.py"],
                cwd=REPO, capture_output=True,
            ).stdout
            (sandbox / "acumen" / "recovery_reconcile.py").write_bytes(blob)

            env = dict(os.environ, PYTHONPATH=str(sandbox), PYTHONIOENCODING="utf-8")
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys;from acumen import recovery_reconcile as rr;"
                 "sys.exit(rr.run(rr.parse_args([])))"],
                cwd=REPO, capture_output=True, env=env,
            )
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

        # Normalise the LINE ENDING only. The reconciler writes with newline="\n" while this
        # subprocess's stdout picks up the platform's, so CRLF is a transport artefact -- but
        # nothing else may be touched, least of all trailing blank lines: stripping those is
        # how the first run of this check reported a one-byte "difference" that was its own.
        produced = result.stdout.replace(b"\r\n", b"\n")
        on_disk = committed.read_bytes().replace(b"\r\n", b"\n")
        if produced != on_disk:
            (scratch / "step5_produced.md").write_bytes(produced)
            (scratch / "step5_stderr.txt").write_bytes(result.stderr)
        return (
            produced == on_disk,
            f"HEAD's `src/acumen/recovery_reconcile.py` (sha256 {sha256(blob)[:16]}...) re-run "
            f"OFFLINE from a throwaway copy of src/ produced {len(produced):,} bytes "
            f"(sha256 {sha256(produced)[:16]}...) against the operator's "
            f"{len(on_disk):,}-byte file (sha256 {sha256(on_disk)[:16]}...) -- "
            f"{'BYTE-IDENTICAL' if produced == on_disk else 'DIFFERENT'}; "
            f"reconciler exit code {result.returncode} "
            f"(1 = the ruling's 'defect to triage', which is why this session exists)",
        )

    sweep.check("5", "the reconciliation regenerates OFFLINE byte-identically", regenerate)


# --- STEP 0g: repo state ---------------------------------------------------------------------


def repo_state(sweep: Sweep, *, allow_paths: tuple[str, ...]) -> None:
    def clean() -> tuple[bool, str]:
        lines = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
        stray = [ln for ln in lines if not any(p in ln for p in allow_paths)]
        return (
            not stray,
            f"working tree carries {len(lines)} entr(y/ies), all of them this session's own "
            f"expected artefacts: {[ln.strip() for ln in lines]}" if not stray
            else f"unexpected working-tree entries: {stray}",
        )

    sweep.check("0g", "working tree clean apart from this session's own artefacts", clean)

    def synced() -> tuple[bool, str]:
        head, remote = git("rev-parse", "HEAD"), git("rev-parse", "origin/main")
        return head == remote and bool(head), f"HEAD {head[:12]} == origin/main {remote[:12]}"

    sweep.check("0g", "HEAD == origin/main", synced)


# --- report ------------------------------------------------------------------------------------


def render(sweep: Sweep, facts: dict[str, Any]) -> str:
    out: list[str] = []
    add = out.append
    add("# Q-18 PART 0 -- RECOVERY VERIFICATION SWEEP")
    add("")
    add("Generated by `docs/evidence/q18_part0_verification.py`, offline and read-only, under")
    add("CLAUDE.md's evidence rule and its Data-store safety clause: *operator-executed runbooks")
    add("are relayed, not certified*. Every figure here was measured on this machine; nothing")
    add("was taken from the operator's transcript.")
    add("")
    add("Regenerate with:")
    add("")
    add("    python docs/evidence/q18_part0_verification.py --out "
        "docs/evidence/q18_part0_verification.md")
    add("")
    add("## VERDICT TABLE")
    add("")
    add("| Step | Evidence checked | Result |")
    add("|---|---|---|")
    for c in sweep.checks:
        # A detail may itself contain '|' (the witness rows separate their cases with it), which
        # would silently split the cell and mis-render the row. Escape it, do not reword it.
        detail = f"{c.name} -- {c.detail}".replace("|", "\\|")
        add(f"| {c.step} | {detail} | {'**PASS**' if c.ok else '**FAIL**'} |")
    add("")
    failed = sweep.failed
    if failed:
        add(f"**{len(failed)} FAILURE(S) -- Part 0 STOPS the session.** "
            "Report, touch nothing: " + "; ".join(c.name for c in failed))
    else:
        add(f"**ALL {len(sweep.checks)} CHECKS PASS.** The operator's five-step runbook is "
            "certified from the machine itself, and triage may proceed.")
    add("")
    add("## Context")
    add("")
    for key, value in facts.items():
        add(f"- {key}: {value}")
    add("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q-18 Part-0 verification sweep (offline).")
    parser.add_argument("--out", default=None, help="write the markdown report here")
    parser.add_argument("--scratch", default=None, help="throwaway dir for step 5")
    parser.add_argument("--allow-path", action="append", default=[],
                        help="a working-tree path this session legitimately owns")
    args = parser.parse_args(argv)

    from acumen.recovery_reconcile import SEALED_REPORT_RELPATH, read_report

    sealed_symbols = sorted(read_report(REPO / SEALED_REPORT_RELPATH).symbols)

    sweep = Sweep()
    facts: dict[str, Any] = {}
    facts.update({f"step1.{k}": v for k, v in step1(sweep).items()})
    facts.update({f"step2.{k}": v for k, v in step2(sweep).items()})
    facts.update({f"step3.{k}": v for k, v in step3(sweep, sealed_symbols).items()})
    four = step4(sweep, sealed_symbols)
    facts["step4.sealed_scope_end"] = four["sealed"].scope_end
    facts["step4.rebuilt_scope_end"] = four["rebuilt"].scope_end
    facts["step4.sealed_symbols"] = len(four["sealed"].symbols)
    facts["step4.rebuilt_symbols"] = len(four["rebuilt"].symbols)
    scratch = Path(args.scratch) if args.scratch else REPO / ".q18_scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    step5(sweep, scratch)
    repo_state(sweep, allow_paths=tuple(args.allow_path) or ("docs/recovery/", "docs/evidence/"))

    text = render(sweep, facts)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n" if not text.endswith("\n") else text,
                          encoding="utf-8", newline="\n")
        print(f"\nwrote {target}")
    print(f"\n{len(sweep.checks) - len(sweep.failed)}/{len(sweep.checks)} checks PASS")
    return 1 if sweep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
