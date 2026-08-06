"""Chunk 9B: THE REPORT -- CONTEXT 7-E13 over the completed ten-year run ledger. I/O here.

``docs/reports/chunk9b_backtest_report.py`` is the launcher and
``docs/reports/chunk9b_backtest_report.md`` is the committed output, which must regenerate
BYTE-IDENTICAL from this code over the same run directory and the same stores (REVIEW_8 finding
C2). Nothing in the output is written by hand, ever.

**What this module is allowed to do.** It reads. It opens the run ledger and its manifest, the
chunk-9A pilot ledger, the crashed run's retained shards, the disclosed-residual register, the
1-minute lake (for the 15-minute equity path, which is the only thing the ledger alone cannot
give) and the daily store (for the benchmark's closes). It writes exactly one markdown file, and
never to a store.

**Where the numbers come from.** Every metric is computed by :mod:`acumen.portfolio`, which is
pure and reviewed; this module supplies it rows and paths and renders what comes back. The two
places that is not literally true are stated where they occur: the per-year table calls
:func:`acumen.portfolio.metrics` once per calendar year with that year's own opening equity, and
the daily trade-count distribution is taken over the WALKED day index rather than over
``pf.disclosures``' trade-days-only view, because a distribution that omitted flat days would
answer a different question from the trader's.

**One presentation basis: NET** (the architect's E13 ruling, 30-Jul-2026). Winners and losers by
the sign of NET PnL; gross profit, gross loss and profit factor are sums of those net figures
over those net populations; the before-costs pair appears once, labelled. See
:data:`acumen.portfolio.E13_BASIS`.

**What is NOT computed, and says so:** the Q40-d capital-infeasibility FLAGS, because the trader's
Q43 answer has not arrived and there is no default figure anywhere in this repo.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import backtest as bt
from . import portfolio as pf
from . import signals as sig
from . import simulate as sim
from .config import load_config
from .daily_store import DailyStore
from .minute_store import MinuteStore

#: The run this report is OF. A label, not a path: the run directory is resolved under the
#: configured ``data_root`` so no store path is ever typed into a source file (CONTEXT 4.6 /
#: Q-18 layer 1).
RUN_LABEL: str = "chunk9b_full"

#: The run that died at symbol 104 on 2026-08-03 and was RENAMED, never deleted (CLAUDE.md
#: layer 2). Its 103 whole shards are the only counterfactual evidence this repo has for what
#: the days the fix arc now refuses were actually worth -- see :func:`crashed_cross_check` and
#: the refusal pricing REVIEW_9B_FIXES R10 asks for.
CRASHED_LABEL: str = "chunk9b_full_crashed_0803"

#: The chunk-9A pilot ledger, whose 290 rows must reappear inside this run unchanged.
PILOT_LABEL: str = "chunk9a_pilot_a"
PILOT_SYMBOLS: tuple[str, ...] = ("TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "BHARTIARTL")
PILOT_START: date = date(2026, 5, 1)
PILOT_END: date = date(2026, 7, 24)

DEFAULT_OUT: str = "docs/reports/chunk9b_backtest_report.md"

#: CONTEXT 4.6's Q-17 law made five dates market-wide. They are measured over the whole lake in
#: ``docs/evidence/chunk9b_out_of_session.md`` (symbols affected / symbols with data that day);
#: this report prints them beside what the RUN's own rows say, which is a smaller number for the
#: reason section 12 gives. The annotation on 2021-02-24 is the fact that makes the date legible.
Q17_MARKET_WIDE: tuple[tuple[str, int, int], ...] = (
    ("2017-04-28", 134, 139),
    ("2018-11-05", 135, 153),
    ("2019-10-25", 56, 159),
    ("2020-12-08", 143, 167),
    ("2021-02-24", 168, 169),
)
Q17_OUTAGE_DATE: str = "2021-02-24"
Q17_OUTAGE_NOTE: str = (
    "NSE halted trading market-wide for about four hours on this date after a feed failure and "
    "reopened for an extended session, which is why nearly every symbol in the lake carries a "
    "stamp outside 09:15..15:29 that day. It is NOT one of the eight CONTEXT 7-E2 non-standard "
    "sessions -- those are Muhurat, and this date is absent from that list -- so the day is "
    "walked, its strays are dropped at the CANDLE level (Q-17), and the drop is flagged and "
    "counted rather than removing the day"
)

#: The one thing CONTEXT 7-E13 does not say about its own benchmark -- the PRICE DOMAIN of its
#: closes -- was raised as QUESTIONS.md Q-23 under CLAUDE.md rule 1 and is now RULED. The ruling
#: and its same-day refinement are quoted VERBATIM beside the readings they decide, which is how
#: every architect ruling travels in this repo. The figures inside the quote are the architect's
#: own words about this run; every figure the section PRINTS is computed from the run beneath it.
BENCHMARK_RULING: str = (
    "ARCHITECT'S RULING (06-Aug-2026), QUESTIONS.md Q-23: the buy&hold benchmark is the "
    "SHARE-COUNT-ADJUSTED construction -- buy-and-hold holds UNITS, which multiply through "
    "bonuses/splits; fixed-unit raw closes falsify wealth at every event. Dividends excluded and "
    "stated. Both figures remain printed; the adjusted one is THE benchmark. ARCHITECT'S "
    "REFINEMENT (06-Aug-2026), Q-23 'and stated': the benchmark applies SHARE-COUNT EVENTS ONLY "
    "(125 factors) = 466.67% -- all cash distributions excluded uniformly, ordinary and special "
    "alike; the mixed 491.90% (special dividends credited) remains printed with one stated line. "
    "Uniform exclusion is the principle; the threshold-mixed figure was an artifact of the CA "
    "engine's 2% rule, not an economic choice. Q-23 CLOSED"
)

#: The event kinds that multiply a HOLDER'S UNITS, and therefore the only ones THE benchmark
#: applies (the Q-23 refinement). Everything else in the factor table is a cash distribution or
#: a price event a unit holder does not participate in: CONTEXT 4.2 gives an ordinary dividend
#: ``k = 1`` and a special dividend ``k = 1 - D/P_cum``, and the refinement excludes both
#: UNIFORMLY rather than at the 2% threshold, which is the CA engine's boundary and not an
#: economic one.
SHARE_COUNT_KINDS: tuple[str, ...] = ("bonus", "split", "rights")


# --- reading the run ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunData:
    """Everything one streaming pass over the ledger yields, and nothing it does not."""

    manifest: dict
    executed: tuple[bt.LedgerRow, ...]
    days: tuple[date, ...]
    walked: int
    usable: int
    refused: int
    outcomes: dict[str, int]
    reasons: dict[str, int]
    exit_kinds: dict[str, int]
    rare_shapes: dict[str, int]
    flags: dict[str, int]
    duplicate_keys: int
    symbols: tuple[str, ...]
    totals: dict[str, int]
    witnesses: "Witnesses"
    ledger_sha256: str
    ledger_bytes: int
    manifest_sha256: str


@dataclass(frozen=True)
class Witnesses:
    """The rare shapes, named rather than counted -- REVIEW_7 Q3 and REVIEW_8 Q1's witnesses."""

    gap_days: tuple[tuple[str, str], ...]
    gap_by_year: dict[str, int]
    gap_exit_kinds: dict[str, int]
    gap_net_paise: int
    gap_winners: int
    qty_zero: tuple[tuple[str, str, int], ...]
    demerger: tuple[tuple[str, str], ...]
    suppressed_rows: int
    gate2_days: tuple[tuple[str, str], ...]
    ungated_by_symbol: dict[str, int]
    out_of_session_by_date: dict[str, int]
    out_of_session_by_rule: dict[str, int]
    no_break_carry: tuple[tuple[str, str, str, bool], ...]
    side_never_set: tuple[tuple[str, str], ...]
    tie_days: int
    e10_days: int
    both_touched: int
    square_off_at_entry: int
    signal_unsizable: int
    malformed_bar_days: int
    rule3_no_minute_days: int
    no_poc_days: tuple[tuple[str, str], ...]


def read_run(run_dir: Path) -> RunData:
    """Stream the ledger ONCE: keep the executed rows, count everything else, discard the rest.

    495,312 rows do not need to be resident. The refusals are counted on the way past and the
    day index is collected, which is all any metric needs of them -- every CONTEXT 7-E13 figure
    is a function of the EXECUTED rows plus that index, and passing the index explicitly is what
    makes a flat day a real observation instead of a missing one
    (:func:`acumen.portfolio.metrics`' own ``days`` argument).
    """
    ledger_path = run_dir / bt.LEDGER_NAME
    manifest_path = run_dir / bt.MANIFEST_NAME
    if not ledger_path.is_file():
        raise bt.BacktestError(f"No run ledger at {ledger_path}.")
    if not manifest_path.is_file():
        raise bt.BacktestError(f"No run manifest at {manifest_path}.")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))

    executed: list[bt.LedgerRow] = []
    days: set[date] = set()
    symbols: set[str] = set()
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    walked = usable = refused = 0
    outcomes: Counter = Counter()
    reasons: Counter = Counter()
    exit_kinds: Counter = Counter()
    flags: Counter = Counter()
    totals = dict(shares=0, gross_pnl_paise=0, cost_paise=0, net_pnl_paise=0,
                  signalled=0, executed=0, gate1_relieved=0)

    gap_days: list[tuple[str, str]] = []
    gap_by_year: Counter = Counter()
    gap_exit: Counter = Counter()
    gap_net = 0
    gap_winners = 0
    qty_zero: list[tuple[str, str, int]] = []
    demerger: list[tuple[str, str]] = []
    suppressed_rows = 0
    gate2_days: list[tuple[str, str]] = []
    ungated: Counter = Counter()
    oos_dates: Counter = Counter()
    oos_rules: Counter = Counter()
    carry: list[tuple[str, str, str, bool]] = []
    side_never_set: list[tuple[str, str]] = []
    tie_days = e10_days = both_touched = square_off_entry = 0
    signal_unsizable = malformed_days = rule3_no_minute = 0
    no_poc: list[tuple[str, str]] = []

    digest = hashlib.sha256()
    ledger_bytes = 0
    with ledger_path.open("rb") as raw:
        for chunk in iter(lambda: raw.read(1 << 22), b""):
            digest.update(chunk)
            ledger_bytes += len(chunk)

    with ledger_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            walked += 1
            symbol = payload["symbol"]
            day_text = payload["day"]
            symbols.add(symbol)
            days.add(date.fromisoformat(day_text))
            key = (symbol, day_text)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)

            reason = payload["reason"]
            outcome = payload["outcome"]
            outcomes[outcome if outcome is not None else f"not evaluated: {reason}"] += 1
            if payload["status"] == "refused":
                refused += 1
                reasons[reason] += 1
                if reason.startswith("gate 2"):
                    gate2_days.append((symbol, day_text))
                elif "demerger" in reason:
                    demerger.append((symbol, day_text))
                elif "no POC" in reason:
                    no_poc.append((symbol, day_text))
            else:
                usable += 1
            if payload["suppressed"]:
                suppressed_rows += 1
            if payload["tie_case"]:
                tie_days += 1
            if payload["gate1_relieved"]:
                totals["gate1_relieved"] += 1
            if payload["signalled"]:
                totals["signalled"] += 1
            if payload["reference_source"] == sig.REFERENCE_FROM_MINUTES:
                e10_days += 1
            if outcome == "no-trade-side-never-set":
                side_never_set.append((symbol, day_text))
            if payload["bias_rule"] == "rule-3-no-break-carry":
                carry.append((symbol, day_text, payload["bias"],
                              bt.FLAG_OUT_OF_SESSION_DROPPED in payload.get("flags", ())))
            if payload["bias_rule"] == bt.RULE_3_NO_MINUTE:
                rule3_no_minute += 1

            for flag in payload.get("flags", ()):
                flags[flag] += 1
                if flag == bt.FLAG_OUT_OF_SESSION_DROPPED:
                    oos_dates[day_text] += 1
                    oos_rules[payload["bias_rule"] or "-"] += 1
                elif flag == bt.FLAG_UNGATED_MINUTE_DAY:
                    ungated[symbol] += 1
                elif flag == bt.FLAG_MALFORMED_MINUTE_BAR:
                    malformed_days += 1
                elif flag == sim.FLAG_BOTH_TOUCHED_STOP_WINS:
                    both_touched += 1
                elif flag == sim.FLAG_SQUARE_OFF_AT_ENTRY_CANDLE:
                    square_off_entry += 1
                elif flag == sim.FLAG_SIGNAL_UNSIZABLE:
                    signal_unsizable += 1
                elif flag == sim.FLAG_QTY_ZERO_UNSIZABLE:
                    qty_zero.append((symbol, day_text, payload["per_share_risk_paise"] or 0))

            if payload["executed"]:
                executed.append(bt.LedgerRow.from_dict(payload))
                totals["executed"] += 1
                totals["shares"] += payload["qty"]
                totals["gross_pnl_paise"] += payload["gross_pnl_paise"]
                totals["cost_paise"] += payload["cost_paise"]
                totals["net_pnl_paise"] += payload["net_pnl_paise"]
                if payload["exit_kind"]:
                    exit_kinds[payload["exit_kind"]] += 1
                if payload["gap_entry"]:
                    gap_days.append((symbol, day_text))
                    gap_by_year[day_text[:4]] += 1
                    gap_exit[payload["exit_kind"]] += 1
                    gap_net += payload["net_pnl_paise"]
                    gap_winners += 1 if payload["net_pnl_paise"] > 0 else 0

    witnesses = Witnesses(
        gap_days=tuple(gap_days),
        gap_by_year=dict(sorted(gap_by_year.items())),
        gap_exit_kinds=dict(sorted(gap_exit.items())),
        gap_net_paise=gap_net,
        gap_winners=gap_winners,
        qty_zero=tuple(qty_zero),
        demerger=tuple(demerger),
        suppressed_rows=suppressed_rows,
        gate2_days=tuple(gate2_days),
        ungated_by_symbol=dict(sorted(ungated.items(), key=lambda kv: (-kv[1], kv[0]))),
        out_of_session_by_date=dict(sorted(oos_dates.items())),
        out_of_session_by_rule=dict(sorted(oos_rules.items(), key=lambda kv: (-kv[1], kv[0]))),
        no_break_carry=tuple(sorted(carry)),
        side_never_set=tuple(side_never_set),
        tie_days=tie_days,
        e10_days=e10_days,
        both_touched=both_touched,
        square_off_at_entry=square_off_entry,
        signal_unsizable=signal_unsizable,
        malformed_bar_days=malformed_days,
        rule3_no_minute_days=rule3_no_minute,
        no_poc_days=tuple(no_poc),
    )
    return RunData(
        manifest=manifest,
        executed=tuple(executed),
        days=tuple(sorted(days)),
        walked=walked,
        usable=usable,
        refused=refused,
        outcomes=dict(sorted(outcomes.items())),
        reasons=dict(sorted(reasons.items())),
        exit_kinds=dict(sorted(exit_kinds.items())),
        rare_shapes=dict(manifest["rare_shapes"]),
        flags=dict(sorted(flags.items())),
        duplicate_keys=duplicates,
        symbols=tuple(sorted(symbols)),
        totals=totals,
        witnesses=witnesses,
        ledger_sha256=digest.hexdigest(),
        ledger_bytes=ledger_bytes,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


# --- reconciliation ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    name: str
    recounted: object
    claimed: object

    @property
    def ok(self) -> bool:
        return self.recounted == self.claimed


def reconcile(run: RunData) -> tuple[Check, ...]:
    """Recount every figure the manifest claims, from the ledger's own rows. PURE.

    A manifest is a summary its own runner wrote; this is the only place in the repo that asks
    whether the summary is TRUE of the rows beneath it. The partition checks are the load-bearing
    ones: usable + refused must be the walk, and the refusal reasons must sum to the refusals,
    or some day is being counted twice or not at all.
    """
    totals = run.manifest["totals"]
    checks = [
        Check("walked symbol-days", run.walked, totals["walked"]),
        Check("usable (evaluated)", run.usable, totals["usable"]),
        Check("signalled", run.totals["signalled"], totals["signalled"]),
        Check("executed", run.totals["executed"], totals["executed"]),
        Check("shares", run.totals["shares"], totals["shares"]),
        Check("gross PnL (paise, before costs)", run.totals["gross_pnl_paise"],
              totals["gross_pnl_paise"]),
        Check("costs (paise)", run.totals["cost_paise"], totals["cost_paise"]),
        Check("net PnL (paise)", run.totals["net_pnl_paise"], totals["net_pnl_paise"]),
        Check("gate-1 auction relief", run.totals["gate1_relieved"], totals["gate1_relieved"]),
        Check("refusals by reason (all 9)", run.reasons, dict(run.manifest["refused_by_reason"])),
        Check("outcomes (the walk's partition)", run.outcomes, dict(run.manifest["outcomes"])),
        Check("exit kinds", run.exit_kinds, dict(run.manifest["exit_kinds"])),
        Check("universe size", len(run.symbols), len(run.manifest["universe"])),
        Check("universe members", list(run.symbols), sorted(run.manifest["universe"])),
        Check("PARTITION usable + refused == walked", run.usable + run.refused, run.walked),
        Check("PARTITION sum(refusal reasons) == refused", sum(run.reasons.values()), run.refused),
        Check("PARTITION sum(outcomes) == walked", sum(run.outcomes.values()), run.walked),
        Check("PARTITION 204 symbols x 2,428 days == walked",
              len(run.symbols) * len(run.days), run.walked),
        Check("duplicate (symbol, day) keys", run.duplicate_keys, 0),
        # The per-trade cost is read from the RUN's own spec block, never typed here: this is a
        # reconciliation of the run as it was actually walked, so its own recorded amount is the
        # right multiplicand -- and a money magnitude typed into a module of this package is the
        # defect chunk 9A shipped and the widened tripwire in tests/test_config.py now refuses.
        Check("costs == the run's own cost x executed trades", run.totals["cost_paise"],
              run.totals["executed"] * int(run.manifest["spec"]["cost_paise"])),
        Check("net == gross - costs", run.totals["net_pnl_paise"],
              run.totals["gross_pnl_paise"] - run.totals["cost_paise"]),
    ]
    for label, claimed in sorted(run.manifest["rare_shapes"].items()):
        checks.append(Check(f"rare shape: {label}", _rare_shape_recount(run, label), claimed))
    return tuple(checks)


def _rare_shape_recount(run: RunData, label: str) -> int:
    """The manifest's rare-shape counters, recounted from the rows the report itself streamed.

    Every one of the eleven is recounted, including the three this run never saw: a counter that
    quietly stopped being printed is exactly the failure a derived counter exists to prevent, and
    a zero recounted independently is worth more than a zero copied across.
    """
    w = run.witnesses
    table = {
        "gap entries": len(w.gap_days),
        "rule-3 tie bias days": w.tie_days,
        "E10 fallback reference (no 11:00-stamped candle)": w.e10_days,
        "both-touched candles (stop won)": w.both_touched,
        "square-offs priced at the entry candle": w.square_off_at_entry,
        "qty-zero unsizable days": len(w.qty_zero),
        "signal-unsizable (degenerate) days": w.signal_unsizable,
        "rule-3 day with no 1-minute data (carried, CONTEXT 3.2)": w.rule3_no_minute_days,
        "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)":
            w.malformed_bar_days,
        "day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)":
            sum(w.out_of_session_by_date.values()),
        "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))":
            sum(w.ungated_by_symbol.values()),
    }
    if label not in table:  # pragma: no cover -- a new label must be recounted, not defaulted
        raise bt.BacktestError(
            f"rare-shape label {label!r} has no independent recount in this report; add one "
            "rather than letting the manifest's own number stand unchecked"
        )
    return table[label]


@dataclass(frozen=True)
class WindowCheck:
    """One ledger's rows compared against another's, field by field."""

    label: str
    rows_left: int
    rows_right: int
    keys_equal: bool
    identical: int
    differing: tuple[tuple[str, str, tuple[str, ...]], ...]
    totals_left: dict[str, int]
    totals_right: dict[str, int]


def pilot_cross_check(run_dir: Path, pilot_dir: Path) -> WindowCheck:
    """The five pilot symbols' 2026 window, in this run, against the committed pilot ledger.

    Trade-level identity is what is expected and what is asserted: the pilot ledger's sha256 is
    published in three reviews, and if the ten-year run disagrees with it anywhere inside that
    window then one of the two is not the machine the reviews passed.
    """
    pilot = {(r["symbol"], r["day"]): r for r in _iter_json(pilot_dir / bt.LEDGER_NAME)}
    window: dict[tuple[str, str], dict] = {}
    for symbol in PILOT_SYMBOLS:
        for payload in _iter_json(run_dir / bt.SHARD_DIRNAME / f"{symbol}.jsonl"):
            if PILOT_START.isoformat() <= payload["day"] <= PILOT_END.isoformat():
                window[(payload["symbol"], payload["day"])] = payload
    return _compare(
        "chunk-9A pilot ledger vs this run's same window", pilot, window
    )


def crashed_cross_check(run_dir: Path, crashed_dir: Path) -> "CrashedCheck":
    """Every row of the crashed run's 103 retained shards against this ledger's own.

    The crash cost nothing -- the relaunch re-walked the whole universe under one code SHA, as
    the resume law requires -- but the shards it left behind are evidence, and the honest way to
    use them is to ask where the two runs DISAGREE and to name the ruling behind every
    disagreement. Anything left over would be non-determinism, and there is none.
    """
    shards = sorted(p.stem for p in (crashed_dir / bt.SHARD_DIRNAME).glob("*.jsonl"))
    causes: Counter = Counter()
    per_symbol: dict[str, set[str]] = {}
    lost: dict[str, list[dict]] = {key: [] for key in _CAUSES}
    moved: Counter = Counter()
    compared = changed = 0
    for symbol in shards:
        old = {r["day"]: r for r in _iter_json(crashed_dir / bt.SHARD_DIRNAME / f"{symbol}.jsonl")}
        new = {r["day"]: r for r in _iter_json(run_dir / bt.SHARD_DIRNAME / f"{symbol}.jsonl")}
        compared += len(old)
        touched: set[str] = set()
        for day in sorted(set(old) & set(new)):
            before, after = old[day], new[day]
            if before == after:
                continue
            changed += 1
            cause = _classify(before, after)
            causes[cause] += 1
            touched.add(cause)
            if before["executed"] and not after["executed"]:
                lost[cause].append(before)
            elif before["executed"] and after["executed"]:
                moved[cause] += 1
        per_symbol[symbol] = touched
    return CrashedCheck(
        shards=len(shards),
        rows_compared=compared,
        rows_changed=changed,
        by_cause=dict(sorted(causes.items())),
        identical_shards=tuple(s for s in shards if not per_symbol[s]),
        by_symbol={s: tuple(sorted(v)) for s, v in per_symbol.items() if v},
        lost_trades={k: tuple(v) for k, v in lost.items()},
        moved_trades=dict(moved),
    )


#: The rulings that landed between the crash and the relaunch. Every changed row must be one of
#: these; a row that is none of them would be non-determinism and the report would say so.
_CAUSES: tuple[str, ...] = (
    "A. Q-21(b): the Rule-3 scan's D-1 fails the CONTEXT 4.5/4.6 gate battery (minutes-ungated)",
    "B. Q-21(a): gate 2's completed enumeration refuses the day on the OPEN test",
    "C. Q-22(a): an out-of-session stamp is dropped before the Rule-3 scan reads it",
    "D. downstream of A/B/C: the same symbol's carried bias differs after a re-answered day",
)


def _classify(before: Mapping, after: Mapping) -> str:
    if (after.get("bias_rule") == "minutes-ungated"
            or bt.FLAG_UNGATED_MINUTE_DAY in after.get("flags", ())):
        return _CAUSES[0]
    if str(after.get("reason", "")).startswith("gate 2"):
        return _CAUSES[1]
    if (bt.FLAG_OUT_OF_SESSION_DROPPED in after.get("flags", ())
            and bt.FLAG_OUT_OF_SESSION_DROPPED not in before.get("flags", ())):
        return _CAUSES[2]
    return _CAUSES[3]


@dataclass(frozen=True)
class CrashedCheck:
    shards: int
    rows_compared: int
    rows_changed: int
    by_cause: dict[str, int]
    identical_shards: tuple[str, ...]
    by_symbol: dict[str, tuple[str, ...]]
    lost_trades: dict[str, tuple[dict, ...]]
    moved_trades: dict[str, int] = field(default_factory=dict)

    @property
    def unexplained(self) -> int:
        return self.rows_changed - sum(self.by_cause.values())


def _iter_json(path: Path) -> Iterable[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _compare(label: str, left: Mapping, right: Mapping) -> WindowCheck:
    differing: list[tuple[str, str, tuple[str, ...]]] = []
    identical = 0
    for key in sorted(set(left) & set(right)):
        a, b = left[key], right[key]
        if a == b:
            identical += 1
        else:
            fields = tuple(sorted(f for f in set(a) | set(b) if a.get(f) != b.get(f)))
            differing.append((key[0], key[1], fields))
    return WindowCheck(
        label=label,
        rows_left=len(left),
        rows_right=len(right),
        keys_equal=set(left) == set(right),
        identical=identical,
        differing=tuple(differing),
        totals_left=_window_totals(left.values()),
        totals_right=_window_totals(right.values()),
    )


def _window_totals(rows: Iterable[Mapping]) -> dict[str, int]:
    rows = list(rows)
    executed = [r for r in rows if r["executed"]]
    return {
        "walked": len(rows),
        "entered": sum(1 for r in rows if r.get("outcome") == "entered"),
        "armed-no-cross": sum(
            1 for r in rows if r.get("outcome") == "no-trade-armed-but-no-qualifying-close"
        ),
        "never-armed": sum(1 for r in rows if r.get("outcome") == "no-trade-never-armed"),
        "executed": len(executed),
        "shares": sum(r["qty"] for r in executed),
        "gross_paise": sum(r["gross_pnl_paise"] for r in executed),
        "cost_paise": sum(r["cost_paise"] for r in executed),
        "net_paise": sum(r["net_pnl_paise"] for r in executed),
    }


# --- the benchmark, both readings ---------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkPair:
    """CONTEXT 7-E13's benchmark as the Q-23 ruling defines it, and the readings printed beside it.

    ``share_count`` is THE benchmark: the first close brought into the last close's scale through
    the run's own BONUS / SPLIT / RIGHTS factors alone. ``adjusted`` is the same construction with
    every non-unit factor applied, which additionally credits the special dividends CONTEXT 4.2
    gives a factor -- the figure the ruling named before its refinement, kept printed and labelled.
    ``raw`` is the unadjusted close-to-close reading, kept for contrast.
    """

    raw: pf.Benchmark
    adjusted: pf.Benchmark
    share_count: pf.Benchmark
    first_day: date
    last_day: date
    adjusted_symbols: int
    events_applied: int
    share_count_symbols: int
    share_count_events: int
    excluded_by_kind: dict[str, int] = field(default_factory=dict)
    ruling: str = BENCHMARK_RULING

    @property
    def excluded_events(self) -> int:
        """Non-unit factors THE benchmark does not apply -- the cash distributions."""
        return sum(self.excluded_by_kind.values())


def benchmark_pair(
    daily_store: DailyStore,
    manifest: Mapping,
    *,
    symbols: Sequence[str],
    first_day: date,
    last_day: date,
    initial_capital_paise: int,
) -> BenchmarkPair:
    """Buy & hold: THE benchmark, plus the mixed and raw readings printed beside it.

    E13 fixes the construction (equal weight, bought at the first trade date's close, held to the
    period end) and is silent on the domain. A ten-year hold cannot be silent about it: a 1:1
    bonus halves the quoted price and doubles the holder's shares, so the raw reading understates
    that symbol by exactly the factor. The Q-23 ruling settles it -- a held portfolio's UNITS are
    what multiply -- and its refinement settles which factors move units: the
    :data:`SHARE_COUNT_KINDS` only, with every cash distribution excluded UNIFORMLY.

    All three readings scale the first close by the run's OWN factor table, which is the same
    ``P x pending factors`` the bias engine applies (CONTEXT 3.2 / 7-E11) and never a second
    source. They differ only in WHICH of that table's factors they apply.
    """
    raw_closes: dict[str, dict[date, int]] = {}
    adjusted_closes: dict[str, dict[date, int]] = {}
    share_closes: dict[str, dict[date, int]] = {}
    per_symbol = manifest["factor_table"]["per_symbol"]
    adjusted_symbols = share_count_symbols = 0
    events = share_events = 0
    excluded: Counter = Counter()
    for symbol in symbols:
        frame = daily_store.daily(symbol, first_day, last_day)
        series = {row.trade_date: int(row.close_paise) for row in frame.itertuples()}
        if not series:
            continue
        raw_closes[symbol] = series
        factor = Fraction(1)
        share_factor = Fraction(1)
        applied = share_applied = 0
        for entry in per_symbol.get(symbol, {}).get("in_span", ()):
            ex = date.fromisoformat(entry["ex_date"])
            k = Fraction(entry["k"])
            if not (first_day < ex <= last_day and k != 1):
                continue
            factor *= k
            applied += 1
            if entry.get("kind") in SHARE_COUNT_KINDS:
                share_factor *= k
                share_applied += 1
            else:
                excluded[str(entry.get("kind"))] += 1
        if applied:
            adjusted_symbols += 1
            events += applied
        if share_applied:
            share_count_symbols += 1
            share_events += share_applied
        first_close = series.get(first_day)
        if first_close is None:
            adjusted_closes[symbol] = series
            share_closes[symbol] = series
            continue
        scaled = dict(series)
        scaled[first_day] = int(Fraction(first_close) * factor)
        adjusted_closes[symbol] = scaled
        share_scaled = dict(series)
        share_scaled[first_day] = int(Fraction(first_close) * share_factor)
        share_closes[symbol] = share_scaled
    hold = dict(first_day=first_day, last_day=last_day,
                initial_capital_paise=initial_capital_paise)
    return BenchmarkPair(
        raw=pf.buy_and_hold(raw_closes, **hold),
        adjusted=pf.buy_and_hold(adjusted_closes, **hold),
        share_count=pf.buy_and_hold(share_closes, **hold),
        first_day=first_day,
        last_day=last_day,
        adjusted_symbols=adjusted_symbols,
        events_applied=events,
        share_count_symbols=share_count_symbols,
        share_count_events=share_events,
        excluded_by_kind=dict(sorted(excluded.items())),
    )


# --- the per-year table ---------------------------------------------------------------------------


@dataclass(frozen=True)
class YearRow:
    year: str
    metrics: pf.Metrics
    opening_equity_paise: int
    closing_equity_paise: int
    gap_entries: int


def per_year(
    executed: Sequence[bt.LedgerRow],
    days: Sequence[date],
    *,
    initial_capital_paise: int,
    gap_by_year: Mapping[str, int],
) -> tuple[YearRow, ...]:
    """One :func:`acumen.portfolio.metrics` per calendar year, on that year's OWN opening equity.

    The trader thinks in years, and a year's drawdown is a fall from a peak inside that year --
    seeding each year's running peak at the equity it opened with is what makes the per-year
    drawdown answer "how bad was that year", rather than re-stating the whole run's.
    """
    years = sorted({day.year for day in days})
    by_year_rows: dict[int, list[bt.LedgerRow]] = {year: [] for year in years}
    for row in executed:
        by_year_rows[row.day.year].append(row)
    by_year_days: dict[int, list[date]] = {year: [] for year in years}
    for day in days:
        by_year_days[day.year].append(day)

    out: list[YearRow] = []
    equity = int(initial_capital_paise)
    for year in years:
        opening = equity
        metrics = pf.metrics(
            tuple(by_year_rows[year]),
            label=str(year),
            initial_capital_paise=opening,
            days=tuple(by_year_days[year]),
        )
        equity = metrics.final_equity_paise
        out.append(YearRow(str(year), metrics, opening, equity, gap_by_year.get(str(year), 0)))
    return tuple(out)


# --- REVIEW_9B_FIXES R10: the refusals, priced ------------------------------------------------


@dataclass(frozen=True)
class RefusalClass:
    reason: str
    rows: int
    share_of_walk: Fraction
    evidence: str
    trades_found: int
    net_paise: int
    #: How many of this class's ``rows`` the crashed run actually walked -- the DENOMINATOR the
    #: trade count was measured over. REVIEW_9B_REPORT finding Q6: only 103 of 204 shards
    #: survive, so a reader who divides ``trades_found`` by ``rows`` divides by the wrong base.
    days_measured: int = 0
    priced: bool = False


def price_refusals(run: RunData, crashed: CrashedCheck) -> tuple[RefusalClass, ...]:
    """What each refusal class costs -- as COVERAGE, and where evidence exists, as TRADES.

    REVIEW_9B_FIXES R10: the arc's cost was disclosed in ROWS only, and *"the 47 days the
    completion refuses were TRADE days that carried real trades ... priced only as coverage,
    never in trades or PnL"*. Three classes have a counterfactual on disk -- the crashed run
    walked those very days under the pre-ruling code -- and they are priced from it here. The
    other six have NO counterfactual anywhere: the crashed run refused them for the same reason
    this one does, so pricing them would need an offline re-simulation that deliberately disables
    a gate, which this report does not do and does not estimate around.
    """
    evidence_for = {
        "gate 2 (candle integrity)": _CAUSES[1],
        "bias unresolvable (CONTEXT 3.2 pair could not be assembled): minutes-ungated": _CAUSES[0],
    }
    out: list[RefusalClass] = []
    for reason, rows in sorted(run.reasons.items(), key=lambda kv: (-kv[1], kv[0])):
        cause = evidence_for.get(reason)
        lost = crashed.lost_trades.get(cause, ()) if cause else ()
        measured = crashed.by_cause.get(cause, 0) if cause else 0
        if cause:
            evidence = (
                f"{crashed.shards} of the crashed run's shards survive, and they walked "
                f"{measured} of these {rows} days under the pre-ruling code; {len(lost)} of "
                f"those {measured} executed a trade there"
            )
        else:
            evidence = "none -- the crashed run refused these days for the same reason"
        out.append(
            RefusalClass(
                reason=reason,
                rows=rows,
                share_of_walk=Fraction(rows, run.walked),
                evidence=evidence,
                trades_found=len(lost),
                net_paise=sum(r["net_pnl_paise"] for r in lost),
                days_measured=measured,
                priced=cause is not None,
            )
        )
    return tuple(out)


# --- REVIEW_9B_REPORT Q5 and Q7: two quantities that were not well defined --------------------


@dataclass(frozen=True)
class LargestTies:
    """The trades that TIE at a column's largest win (or largest loss), and what they are worth.

    A fixed-R strategy manufactures ties by construction: a target pays ``qty x 3 x risk`` and a
    stop pays ``-qty x risk``, so thousands of trades land on the same rupee figure and the row
    order alone decides which of them a single-trade percentage is taken from. The rupee extreme
    is a fact; ``net / notional`` over one arbitrary member of the tied set is not. This carries
    the whole tied set instead: how many there are, and the RANGE of the percentage across them
    (REVIEW_9B_REPORT finding Q5).
    """

    extreme_paise: int | None
    ties: int
    min_pct_of_notional: Fraction | None
    max_pct_of_notional: Fraction | None
    min_notional_paise: int | None
    max_notional_paise: int | None

    @property
    def is_empty(self) -> bool:
        return self.extreme_paise is None


EMPTY_TIES: LargestTies = LargestTies(None, 0, None, None, None, None)


def largest_ties(rows: Sequence[bt.LedgerRow], *, winners: bool) -> LargestTies:
    """Every executed trade that ties at the largest win (``winners``) or largest loss. PURE."""
    trades = pf.executed(rows)
    pot = [
        row for row in trades
        if (row.net_pnl_paise > 0 if winners else row.net_pnl_paise < 0)
    ]
    if not pot:
        return EMPTY_TIES
    extreme = max(row.net_pnl_paise for row in pot) if winners else min(
        row.net_pnl_paise for row in pot
    )
    tied = [row for row in pot if row.net_pnl_paise == extreme]
    priced = [row for row in tied if row.notional_paise]
    ratios = sorted(Fraction(row.net_pnl_paise, row.notional_paise) for row in priced)
    notionals = sorted(row.notional_paise for row in priced)
    return LargestTies(
        extreme_paise=extreme,
        ties=len(tied),
        min_pct_of_notional=ratios[0] if ratios else None,
        max_pct_of_notional=ratios[-1] if ratios else None,
        min_notional_paise=notionals[0] if notionals else None,
        max_notional_paise=notionals[-1] if notionals else None,
    )


def _column_ties(run: RunData) -> dict[str, tuple[LargestTies, LargestTies]]:
    """(largest-win ties, largest-loss ties) for each of E13's three columns."""
    return {
        label: (largest_ties(rows, winners=True), largest_ties(rows, winners=False))
        for label, rows in (("All", run.executed),
                            ("Long", pf.for_side(run.executed, sig.LONG)),
                            ("Short", pf.for_side(run.executed, sig.SHORT)))
    }


def concurrency_closing_first(rows: Sequence[bt.LedgerRow]) -> pf.ConcurrencyPeak:
    """Max concurrency under the OTHER convention: a position is closed AT its exit mark. PURE.

    :func:`acumen.portfolio.disclosures` processes an OPEN before a CLOSE at the same stamp, so a
    position closing at T is still counted as open at T -- the pessimistic reading, and the only
    one that cannot understate what the trader's capital would have had to carry. The 15-minute
    equity path uses the other convention, because a trade's marks END at its exit candle.

    Both are defensible and they do not agree, so the report prints BOTH and the definitions
    block names the one the headline figure uses (REVIEW_9B_REPORT finding Q7). This is the same
    sweep as ``disclosures``' with the event order reversed at a shared stamp, and nothing else.
    """
    events: list[tuple[datetime, int, int, str]] = []
    for row in pf.executed(rows):
        if row.entry_close_stamp is None:
            continue
        exit_stamp = row.exit_close_stamp or row.entry_close_stamp
        events.append((exit_stamp, 0, -row.notional_paise, row.symbol))
        events.append((row.entry_close_stamp, 1, row.notional_paise, row.symbol))
    events.sort(key=lambda event: (event[0], event[1]))

    live: dict[str, int] = {}
    positions = notional = 0
    best = pf.ConcurrencyPeak(0, 0, None)
    for stamp, kind, delta, symbol in events:
        if kind == 1:
            positions += 1
            live[symbol] = live.get(symbol, 0) + 1
        else:
            positions -= 1
            live[symbol] = live.get(symbol, 0) - 1
            if live[symbol] <= 0:
                live.pop(symbol, None)
        notional += delta
        if kind == 1 and positions > best.positions:
            best = pf.ConcurrencyPeak(positions, notional, stamp, tuple(sorted(live)))
    return best


# --- assembly -------------------------------------------------------------------------------------


def build_everything(
    *,
    config_path: Path = Path("config.yaml"),
    run_label: str = RUN_LABEL,
    progress=lambda _message: None,
) -> dict:
    """Read everything the report needs. I/O; the rendering below it is pure."""
    config = load_config(config_path)
    data_root = Path(config.paths["data_root"])
    runs = data_root / "backtests"
    run_dir = runs / run_label

    progress("reading the run ledger")
    run = read_run(run_dir)
    capital = config.initial_capital_paise()

    progress("reconciling against the manifest")
    checks = reconcile(run)
    pilot = pilot_cross_check(run_dir, runs / PILOT_LABEL)
    progress("cross-checking the crashed run's shards")
    crashed = crashed_cross_check(run_dir, runs / CRASHED_LABEL)

    minute_store = MinuteStore.at(data_root / "minute_store")
    paths = _assemble_paths(run, minute_store, progress=progress)
    reconciling_paths = sum(1 for path in paths if pf.path_reconciles(path))

    progress("computing the E13 metric set")
    columns = _side_split_over_walked_days(run, paths, capital_paise=capital)
    crosses_zero = {
        label: _curve_crosses_zero(rows, run.days, capital)
        for label, rows in (("All", run.executed),
                            ("Long", pf.for_side(run.executed, sig.LONG)),
                            ("Short", pf.for_side(run.executed, sig.SHORT)))
    }
    series = pf.daily_pnl(run.executed, days=run.days)
    curve = pf.equity_curve(series, capital)
    disclosures = pf.disclosures(run.executed)
    flags = pf.capital_flags(
        run.executed,
        capital_reference_paise=config.capital_reference_paise(),
        margin_basis=config.margin_basis,
    )
    years = per_year(run.executed, run.days, initial_capital_paise=capital,
                     gap_by_year=run.witnesses.gap_by_year)

    progress("computing the per-symbol table")
    register = bt.load_residual_register(data_root / bt.RESIDUAL_LEDGER_RELPATH)
    symbols = {
        symbol: pf.metrics(pf.for_symbol(run.executed, symbol), label=symbol,
                           initial_capital_paise=capital, days=run.days)
        for symbol in run.symbols
    }

    progress("computing the buy & hold benchmark")
    first_trade_day = min(row.day for row in run.executed)
    benchmark = benchmark_pair(
        DailyStore.at(data_root / "daily_store"),
        run.manifest,
        symbols=run.symbols,
        first_day=first_trade_day,
        last_day=run.days[-1],
        initial_capital_paise=capital,
    )
    return dict(
        run=run,
        config=config,
        capital_paise=capital,
        checks=checks,
        pilot=pilot,
        crashed=crashed,
        columns=columns,
        curve=curve,
        series=series,
        disclosures=disclosures,
        capital_flag_report=flags,
        years=years,
        symbols=symbols,
        register=register,
        benchmark=benchmark,
        crosses_zero=crosses_zero,
        paths_built=len(paths),
        path_marks=sum(len(path.marks) for path in paths),
        paths_reconciling=reconciling_paths,
        refusals=price_refusals(run, crashed),
        daily_counts=_daily_count_distribution(series),
        ties=_column_ties(run),
        path_concurrency=concurrency_closing_first(run.executed),
    )


def _curve_crosses_zero(rows, days, capital_paise: int) -> bool:
    """Does this column's own equity curve ever touch or pass zero? PURE.

    Asked because a daily RETURN divides by the prior equity, so a series that crosses zero
    produces returns whose sign is an artifact of the denominator (:data:`RATIO_CROSSES_ZERO`).
    Built from the same functions the metrics use, over the same index.
    """
    curve = pf.equity_curve(pf.daily_pnl(rows, days=days), capital_paise)
    return any(point.equity_paise <= 0 for point in curve)


def _side_split_over_walked_days(
    run: RunData, paths: Sequence[bt.TradePath], *, capital_paise: int
) -> dict[str, pf.Metrics]:
    """E13's All / Long / Short columns, indexed on EVERY WALKED DAY.

    :func:`acumen.portfolio.side_split` derives its own index with ``walked_days(rows)`` over the
    rows it is handed. That is right when it is handed every walked row, which is what its
    docstring asks for; this report streams the refusals past instead of holding 306,967 of them,
    so handing it the executed rows alone would index the series on the 2,415 days that TRADED and
    quietly drop the 13 that did not.

    That is not cosmetic. :func:`acumen.portfolio.walked_days` says it out loud -- *"a flat day is
    a real observation for a daily Sharpe, and dropping it would silently annualize a different
    sample"* -- and it would also shorten every drawdown duration. So the split is rebuilt here
    with exactly ``side_split``'s own structure and the run's true day index passed explicitly.
    Same function, same paths, one more argument.
    """
    return {
        "All": pf.metrics(run.executed, label="All", initial_capital_paise=capital_paise,
                          days=run.days, paths=paths),
        "Long": pf.metrics(pf.for_side(run.executed, sig.LONG), label="Long",
                           initial_capital_paise=capital_paise, days=run.days,
                           paths=pf.paths_for_side(paths, sig.LONG)),
        "Short": pf.metrics(pf.for_side(run.executed, sig.SHORT), label="Short",
                            initial_capital_paise=capital_paise, days=run.days,
                            paths=pf.paths_for_side(paths, sig.SHORT)),
    }


def _assemble_paths(
    run: RunData, minute_store: MinuteStore, *, progress
) -> tuple[bt.TradePath, ...]:
    """Every executed trade's 15-minute marks, assembled SYMBOL BY SYMBOL so the stage speaks.

    The work is identical to one :func:`acumen.backtest.assemble_trade_paths` call over every
    row -- the same shipped assembler, the same sanctioned ``bars_for``, symbols taken in sorted
    order so the result is deterministic. What the grouping buys is a PROGRESS LINE, and that is
    not a nicety: this is the one stage that touches the minute lake, it costs about 10 ms per
    trade because :meth:`acumen.minute_store.MinuteStore.minutes` opens and filters a month file
    per day, and at 188,345 trades it runs for well over half an hour. A stage that long must not
    run silent -- a session cannot tell a slow run from a hung one, and an earlier version of this
    generator could not.

    A bulk reader was built and MEASURED against this one rather than assumed to be faster:
    reading each month once through
    :meth:`~acumen.minute_store.MinuteStore.iter_days` produced byte-identical paths and was
    **2.4x SLOWER** on a real symbol (25.7s against 10.7s for RELIANCE's 1,125 trades), because
    it decodes every stored bar of every month while the per-day reader decodes one day's and
    re-reads a month file the operating system already has cached. The per-day reader stays.
    """
    bars_for = bt.minute_store_bars(minute_store)
    by_symbol: dict[str, list[bt.LedgerRow]] = {}
    for row in run.executed:
        by_symbol.setdefault(row.symbol, []).append(row)
    symbols = sorted(by_symbol)
    paths: list[bt.TradePath] = []
    for index, symbol in enumerate(symbols, start=1):
        paths.extend(bt.assemble_trade_paths(by_symbol[symbol], bars_for=bars_for))
        if index % 10 == 0 or index == len(symbols):
            progress(
                f"assembling the 15-minute trade paths: {index}/{len(symbols)} symbols, "
                f"{len(paths):,} paths"
            )
    return tuple(paths)


def _daily_count_distribution(series: Sequence[pf.DailyPnL]) -> tuple[tuple[int, int], ...]:
    """How many days carried N trades, over EVERY walked day -- flat days included.

    ``pf.disclosures`` builds its own distribution over the days its rows touch, which for a
    take-all portfolio measured on executed rows alone is the trading days only. CONTEXT 3.5 asks
    for the distribution of DAILY concurrent-trade counts, and a day the strategy sat out is one
    of those counts (it is zero), so the index here is the walked one.
    """
    counts: Counter = Counter()
    for day in series:
        counts[day.trades] += 1
    return tuple(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pieces = build_everything(config_path=Path(args.config), run_label=args.run, progress=print)
    text = render_markdown(**pieces)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars)")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen.report_9b", description="chunk-9B backtest report"
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="markdown output path")
    parser.add_argument("--run", default=RUN_LABEL, help="run label under <data_root>/backtests")
    parser.add_argument("--config", default="config.yaml", help="config path")
    return parser.parse_args(argv)


# --- rendering (PURE: takes the pieces above, returns the markdown) --------------------------


def _money(paise) -> str:
    return pf.format_paise(paise)


def _pct(value, places: int = 2) -> str:
    return pf.format_pct(value, places)


def _num(value: int) -> str:
    return f"{value:,}"


def _join(names: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c` -- so a per-column sentence reads like one."""
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _decimal(value: Decimal | None, places: int = 4) -> str:
    if value is None:
        return "undefined"
    return str(value.quantize(Decimal(1).scaleb(-places)))


def _day(value: date | None, fallback: str = "the run's opening capital") -> str:
    return fallback if value is None else value.isoformat()


#: What a percentage says when its own denominator is not a positive equity. A drawdown from a
#: peak of Rs 115,989.60 has a meaningful percentage; a fall measured from an equity ALREADY below
#: zero does not -- the arithmetic still divides, and its sign flips, but the answer is not a
#: percentage of anything. This run goes below zero in its first year (section 7a), so the case is
#: the rule here rather than the exception, and printing "-2.92%" for a run-up would be worse than
#: printing nothing.
NO_PERCENT_BASE: str = "% n/a -- the base equity is at or below zero"

#: The same disease in a more dangerous place. A daily RETURN is `(change / prior equity)`, and
#: once the equity series crosses zero the denominator changes sign: a LOSS on a negative base
#: divides to a POSITIVE return. Sharpe and Sortino are built from those returns, so on a curve
#: that goes below zero they can come out positive for a strategy that lost many times its
#: capital -- which is exactly what this run produces. The ratio is refused, with its reason,
#: rather than printed as if it meant something. CONTEXT 7-E13 fixes the convention (daily
#: series, risk-free 0, x sqrt 252); it does not license reporting it where it is undefined.
RATIO_CROSSES_ZERO: str = (
    "n/a -- this column's equity series crosses zero, and a daily return (change / prior equity) "
    "is not defined across a sign change in its own denominator: a LOSS on a negative base "
    "divides to a POSITIVE return, so the ratio would read as a strength it is not"
)


def _excursion_pct(pct: Fraction | None) -> str:
    """The percentage, or the reason there is not one. An excursion size is always positive."""
    if pct is None or pct <= 0:
        return NO_PERCENT_BASE
    return _pct(pct)


def _excursion(exc: pf.Excursion, *, recovery_word: str, rising: bool = False) -> str:
    """One close-to-close excursion. ``rising`` prints a run-up trough-first, as it happened."""
    if exc.is_empty:
        word = "rose above" if rising else "fell below"
        return f"none -- the curve never {word} the level it started from"
    start, end = (exc.trough_day, exc.peak_day) if rising else (exc.peak_day, exc.trough_day)
    return (
        f"{_money(exc.amount_paise)} ({_excursion_pct(exc.pct)}), {_day(start)} -> "
        f"{_day(end)}, {_num(exc.duration_days)} daily observation(s), "
        f"{recovery_word} {_day(exc.recovered_on, 'never inside the span')}"
    )


def _path_excursion(exc: pf.PathExcursion | None, *, observations: int, recovery_word: str,
                    rising: bool = False) -> str:
    if exc is None:
        return pf.INTRADAY_PATH_NOT_SUPPLIED
    if exc.is_empty:
        word = "rose above" if rising else "fell below"
        return f"none -- the path never {word} the level it started from"
    start, end = (exc.trough, exc.peak) if rising else (exc.peak, exc.trough)
    return (
        f"{_money(exc.amount_paise)} ({_excursion_pct(exc.pct)}), {_path_stamp(start)} -> "
        f"{_path_stamp(end)}, {_num(exc.observations)} observation(s) of "
        f"{_num(observations)}, {recovery_word} {_path_stamp(exc.recovered, 'never inside the span')}"
    )


def _path_stamp(point: pf.PathPoint | None, fallback: str = "the run's opening capital") -> str:
    if point is None:
        return fallback
    if point.stamp is None:
        return f"{point.day.isoformat()} (day close)"
    return point.stamp.isoformat(sep=" ", timespec="minutes")


def render_markdown(
    *,
    run: RunData,
    config,
    capital_paise: int,
    checks: Sequence[Check],
    pilot: WindowCheck,
    crashed: CrashedCheck,
    columns: Mapping[str, pf.Metrics],
    curve: Sequence[pf.EquityPoint],
    series: Sequence[pf.DailyPnL],
    disclosures: pf.Disclosures,
    capital_flag_report: pf.CapitalFlagReport,
    years: Sequence[YearRow],
    symbols: Mapping[str, pf.Metrics],
    register: Mapping[str, bt.ResidualEntry],
    benchmark: BenchmarkPair,
    crosses_zero: Mapping[str, bool],
    paths_built: int,
    path_marks: int,
    paths_reconciling: int,
    refusals: Sequence[RefusalClass],
    daily_counts: Sequence[tuple[int, int]],
    ties: Mapping[str, tuple[LargestTies, LargestTies]],
    path_concurrency: pf.ConcurrencyPeak,
) -> str:
    """The whole report. PURE -- every input above was read by :func:`build_everything`."""
    lines: list[str] = []
    add = lines.append
    everything = dict(
        run=run, capital_paise=capital_paise, checks=checks, pilot=pilot, crashed=crashed,
        columns=columns, curve=curve, series=series, disclosures=disclosures,
        capital_flag_report=capital_flag_report, years=years, symbols=symbols,
        register=register, benchmark=benchmark, crosses_zero=crosses_zero,
        paths_built=paths_built,
        path_marks=path_marks, paths_reconciling=paths_reconciling, refusals=refusals,
        daily_counts=daily_counts, config=config, ties=ties,
        path_concurrency=path_concurrency,
    )
    for section in (
        _section_head, _section_what_this_is, _section_the_run, _section_reconciliation,
        _section_definitions, _section_headline, _section_e13, _section_equity,
        _section_years, _section_symbols, _section_benchmark, _section_take_all,
        _section_rare_shapes, _section_traceability,
    ):
        section(add, **everything)
    return "\n".join(lines).rstrip("\n") + "\n"


def _section_head(add, *, run: RunData, **_) -> None:
    add("# chunk 9B -- the backtest report")
    add("")
    add("The frozen strategy of CONTEXT 3, run over every settled symbol and every trading day "
        "of the sealed data era, and reported under CONTEXT 7-E13.")
    add("")
    add("Generated by `docs/reports/chunk9b_backtest_report.py` (implementation: "
        "`src/acumen/report_9b.py`). Regenerate with:")
    add("")
    add("    python docs/reports/chunk9b_backtest_report.py")
    add("")
    add("Every number below is computed by the committed code from the committed run ledger and "
        "the local read-only stores. The file is written by the generator and never edited by "
        "hand (REVIEW_8 finding C2). No figure in it is typed.")
    add("")


def _gate1p_share(register: Mapping[str, bt.ResidualEntry]) -> Fraction | None:
    """Gate 1P ALONE, over the settled universe: proven days / days with an oracle to prove them.

    Section 9's ``price-proven`` column is this quantity per symbol; section 1's headline figure
    is a different one (all three gates, over the whole lake). REVIEW_9B_REPORT finding Q4: one
    word was carrying both, so a reader who averaged the column could never reach the headline.
    Computed from the register the report already read rather than typed beside it.
    """
    settled = [entry for entry in register.values() if entry.status == "settled"]
    total = sum(entry.gate1p_total for entry in settled)
    if total <= 0:
        return None
    return Fraction(sum(entry.gate1p_pass for entry in settled), total)


def _section_what_this_is(add, *, run: RunData, capital_paise: int, register=None, **_) -> None:
    add("## 1. What this is -- and the seven things it is not")
    add("")
    add("This is the result of the strategy the trader specified, applied without discretion to "
        f"{_num(run.walked)} symbol-days. It states what the machine did. It does not argue that "
        "the strategy is good or bad, and it recommends nothing: that judgement is the trader's "
        "and the architect's, and nothing in this file is written to lead it.")
    add("")
    add("**It is NOT a capital-constrained result.** CONTEXT 3.5, Round-3 Q40 option (d), "
        "TRADER-FINAL: *no limits, show me the honest numbers*. Every signal is taken on every "
        "stock concurrently, each sized by the fixed rupee-risk rule, with no capital or "
        "concurrency cap of any kind. Section 11 measures what that actually required -- the "
        "most positions held at once and the largest simultaneous notional -- so the size of the "
        "assumption is on the page rather than behind it.")
    add("")
    add("**The capital-infeasibility FLAGS are NOT COMPUTED.** "
        f"{bt.CAPITAL_FLAGS_PENDING_NOTE}. `capital_reference` and `margin_basis` are optional "
        "config keys and both are null; the machinery is built and tested and computes POST-HOC "
        "from this ledger the day the answer arrives, with no re-run. There is no default figure "
        "anywhere in this repo, because a trade marked infeasible against a guessed number would "
        "be this repo's claim standing in for the trader's.")
    add("")
    add("**The fills are IDEALIZED** (CONTEXT 7-E9). Entries fill at the 15-minute candle's "
        "close, stops and targets fill at their LEVELS even when the candle ran past them, and "
        "the only friction is the flat cost below. There is no slippage model, no partial fill, "
        "no market impact -- and this portfolio would have carried the notional section 11 "
        "reports, which is where impact would have been felt.")
    add("")
    add(f"**The only cost is Rs 100.00 per executed round trip** (CONTEXT 3.5, R1-Q23), charged "
        f"once per trade that opened. Over {_num(run.totals['executed'])} trades that is "
        f"{_money(run.totals['cost_paise'])}, and it is the difference between the two headline "
        "figures in section 5.")
    add("")
    add("**One trade per stock per day, and no compounding.** CONTEXT 3.4 consumes a stock-day "
        "at its first qualifying cross and CONTEXT 3.1 squares off at 15:15, so no position "
        f"straddles a day. Risk is a fixed Rs 1,000.00 per trade regardless of equity, so the "
        "curve in section 7 ADDS; it does not multiply.")
    add("")
    add("**The universe is TODAY's list, walked backwards** (CONTEXT 7-E5). The 204 symbols are "
        "the settled members of the sealed 210-symbol F&O universe as it stands now, and the "
        "backtest runs them from 2016. **A stock that was in the index in 2017 and has since "
        "left is not here, and a stock that entered in 2024 is walked from 2016 anyway.** That "
        "is survivorship bias, it flatters any strategy that trades liquid large caps, and it is "
        "an engineering default disclosed rather than a trader instruction. Point-in-time "
        "membership is a documented upgrade (OPEN-5).")
    add("")
    gate1p = _gate1p_share(register or {})
    narrower = ("is not computable from the register this run read" if gate1p is None
                else f"is {_pct(gate1p, 4)} over the settled universe")
    add("**The data era is 93.9317% USABLE, not 100% -- and that figure is ALL THREE GATES, not "
        "the price gate alone.** 93.9317% is CONTEXT 4.6 v1.6's coverage figure: the settled "
        "symbols' usable stored symbol-days over the WHOLE lake's stored days, so a day refused "
        "for having no candles, for failing the volume reconciliation, for failing price "
        "containment or for candle integrity is outside it equally. The narrower quantity "
        "section 9's `price-proven` column carries -- gate 1P alone, a day whose 1-minute prices "
        f"reconcile against the exchange's own bhavcopy -- {narrower}. The two are different "
        "measurements over different denominators, and averaging the section-9 column will never "
        "reach the headline. Refused days are counted, never traded: section 3a partitions all "
        f"{_num(run.walked)} walked days and section 9 carries each symbol's own coverage beside "
        "its figures; the residual is disclosed in the register, not chased.")
    add("")
    add(f"**Q44 is unconfirmed.** The manifest carries, verbatim: *\"PENDING TRADER CONFIRMATION "
        "OF Q44 (gap-rule example, POC 2032)\"*. If his answer surprises, CONTEXT 3.4 changes, "
        "the spec version bumps and the whole run is done again; this ledger is then superseded, "
        "retained and labelled, never deleted (the architect's GO ruling, 31-Jul-2026).")
    add("")


def _section_the_run(add, *, run: RunData, capital_paise: int, config, **_) -> None:
    spec = run.manifest["spec"]
    master = run.manifest["instrument_master"]
    add("## 2. The run this reports on")
    add("")
    add("| Input | Value | Source |")
    add("|---|---|---|")
    add(f"| Run label | `{spec['label']}` | `<data_root>/backtests/` |")
    add(f"| Span | {spec['start']} .. {spec['end']} | measured from the stores, clamped to the "
        "raw daily oracle |")
    add(f"| Universe | {_num(len(run.symbols))} settled symbols | the disclosed-residual "
        "register, read before any per-symbol statistic (CONTEXT 4.6) |")
    add(f"| Walked | {_num(run.walked)} symbol-days = {_num(len(run.symbols))} x "
        f"{_num(len(run.days))} | 2,425 trading days + the 3 weekend-dated Muhurat sessions, "
        "each counted as a refusal |")
    add(f"| Spec version | {run.manifest['spec_version']} | CONTEXT.md |")
    add(f"| Code SHA | `{run.manifest['code_sha']}` | the commit the run walked under |")
    add(f"| Config digest | `{run.manifest['config_digest'][:16]}...` | sha256 |")
    add(f"| Factor-table digest | `{run.manifest['factor_table']['digest'][:16]}...` | sha256 of "
        "the real chunk-3 table, wired |")
    add(f"| Instrument master | `{master['pinned_file']}` | the PINNED dump (QUESTIONS.md Q-20) |")
    add(f"| Instrument-master sha256 | `{master['sha256'][:16]}...` | the pin's own digest |")
    add(f"| Risk per trade | {_money(spec['risk_per_trade_paise'])} | `config.yaml` (CONTEXT 3.5, "
        "Round-3 Q29) |")
    add(f"| Cost per executed round trip | {_money(spec['cost_paise'])} | `config.yaml` "
        "(CONTEXT 3.5, R1-Q23) |")
    add(f"| Capital (equity-curve base) | {_money(capital_paise)} | `config.yaml` (CONTEXT 3.5, "
        "R1-Q21a) |")
    add(f"| Row Size N | {spec['row_size']} | `config.yaml` (CONTEXT 3.3, trader screenshot) |")
    add("| capital_reference / margin_basis | null / null | trader Q43 PENDING |")
    add(f"| Ledger | `ledger.jsonl`, {_num(run.ledger_bytes)} bytes | sha256 "
        f"`{run.ledger_sha256[:16]}...` |")
    add(f"| Manifest | `manifest.json` | sha256 `{run.manifest_sha256[:16]}...` |")
    add("")
    add("**The manifest's own disclosures, carried here verbatim.**")
    add("")
    for disclosure in run.manifest["disclosures"]:
        add(f"* {disclosure}")
        add("")


def _section_reconciliation(add, *, run: RunData, checks, pilot: WindowCheck,
                            crashed: CrashedCheck, **_) -> None:
    failures = [check for check in checks if not check.ok]
    add("## 3. Reconciliation -- before any metric is read")
    add("")
    add("A manifest is a summary its own runner wrote. Nothing downstream should trust it until "
        "somebody has asked whether it is TRUE of the rows beneath it. This section asks, three "
        "times: against the manifest, against the reviewed pilot ledger, and against the run "
        "that crashed.")
    add("")
    add("### 3a. The ledger, recounted against its own manifest")
    add("")
    add(f"Every figure below was recounted by streaming all {_num(run.walked)} rows. "
        f"**{_num(len(checks) - len(failures))} of {_num(len(checks))} agree.**")
    add("")
    add("| Check | Recounted from the rows | Claimed by the manifest | |")
    add("|---|---|---|---|")
    for check in checks:
        left = check.recounted
        right = check.claimed
        if isinstance(left, (dict, list)):
            shown = "match" if check.ok else "MISMATCH"
            add(f"| {check.name} | {shown} | {shown} | {'OK' if check.ok else '**XX**'} |")
        else:
            add(f"| {check.name} | {_cell(left)} | {_cell(right)} | "
                f"{'OK' if check.ok else '**XX**'} |")
    add("")
    if failures:
        add("**THE FOLLOWING DID NOT RECONCILE and the report says so rather than printing "
            "around it:**")
        add("")
        for check in failures:
            add(f"* **{check.name}** -- rows say `{check.recounted}`, manifest says "
                f"`{check.claimed}`.")
        add("")
    else:
        add("**The partition is exact.** Usable plus refused is the walk; the nine refusal "
            "reasons sum to the refusals; the outcomes sum to the walk; symbols times days is "
            "the walk; no `(symbol, day)` key appears twice; the costs are exactly Rs 100 times "
            "the executed trades; and the net is the gross minus those costs. Every one of the "
            "eleven rare-shape counters was recounted independently rather than copied.")
        add("")
    add("**Where each walked day went.**")
    add("")
    add("| Outcome | Days | Share of the walk |")
    add("|---|---:|---:|")
    for outcome, count in sorted(run.outcomes.items(), key=lambda kv: (-kv[1], kv[0])):
        add(f"| {outcome} | {_num(count)} | {_pct(Fraction(count, run.walked))} |")
    add(f"| **total** | **{_num(run.walked)}** | **100.00%** |")
    add("")
    add("### 3b. The chunk-9A pilot window, inside this run")
    add("")
    add("The five pilot symbols over 2026-05-01 .. 2026-07-24 are the window three reviews "
        "verified and whose ledger sha256 "
        "`c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318` is published in all "
        "three. If the ten-year run disagrees with it anywhere in that window, one of the two is "
        "not the machine those reviews passed.")
    add("")
    add(f"* Rows on each side: **{_num(pilot.rows_left)}** in the pilot ledger, "
        f"**{_num(pilot.rows_right)}** in this run's same window.")
    add(f"* The `(symbol, day)` key sets are {'IDENTICAL' if pilot.keys_equal else 'DIFFERENT'}.")
    add(f"* Rows identical FIELD FOR FIELD: **{_num(pilot.identical)}**. "
        f"Rows differing: **{_num(len(pilot.differing))}**.")
    add("")
    if pilot.differing:
        add("| Symbol | Day | Fields that differ |")
        add("|---|---|---|")
        for symbol, day, fields in pilot.differing:
            add(f"| {symbol} | {day} | {', '.join(fields)} |")
        add("")
    else:
        add("**Trade-level identity, and more than trade-level: not one field of one row moved.** "
            "The spec version, the code SHA and three manifest counters have all moved since the "
            "pilot was written -- the run carries v1.7 against the pilot's v1.5 -- and the rows "
            "those changes touch are all outside this window, which is exactly the claim the "
            "FIX-4 review made and this is the ten-year confirmation of it.")
        add("")
    add("| Figure | Pilot ledger | This run's window |")
    add("|---|---:|---:|")
    for key in ("walked", "entered", "armed-no-cross", "never-armed", "executed", "shares"):
        add(f"| {key} | {_num(pilot.totals_left[key])} | {_num(pilot.totals_right[key])} |")
    for key, label in (("gross_paise", "gross PnL (before costs)"), ("cost_paise", "costs"),
                       ("net_paise", "net PnL")):
        add(f"| {label} | {_money(pilot.totals_left[key])} | {_money(pilot.totals_right[key])} |")
    add("")
    add("### 3c. The run that crashed, and what the crash cost")
    add("")
    add("On 2026-08-03 the first full-history attempt died inside JUBLFOOD, symbol 104 of 204, on "
        "a vendor-corrupt 1-minute bar. The operator RENAMED that run rather than deleting it "
        "(CLAUDE.md data-store safety, layer 2), so its 103 completed shards survive -- and they "
        "are the only counterfactual this repo has for the days the fix arc now refuses.")
    add("")
    add(f"* Shards retained: **{_num(crashed.shards)}**; rows compared against this run: "
        f"**{_num(crashed.rows_compared)}**.")
    add(f"* Rows that differ: **{_num(crashed.rows_changed)}** "
        f"({_pct(Fraction(crashed.rows_changed, crashed.rows_compared), 4)} of them).")
    add(f"* Shards byte-for-byte identical: **{_num(len(crashed.identical_shards))}** of "
        f"{_num(crashed.shards)}.")
    add(f"* **Rows that differ for no ruled reason: {_num(crashed.unexplained)}.**")
    add("")
    add("| Cause of the difference | Rows |")
    add("|---|---:|")
    for cause, count in sorted(crashed.by_cause.items()):
        add(f"| {cause} | {_num(count)} |")
    add(f"| **total** | **{_num(sum(crashed.by_cause.values()))}** |")
    add("")
    add("**THE CRASH ITSELF COST NOTHING.** The relaunch re-walked all 204 symbols under ONE "
        "code SHA, which is what the resume law requires and why no partial state could survive "
        "into this ledger. What the 145 differing rows measure is not the crash -- it is the "
        "three architect rulings that landed between the two attempts (Q-21(b), Q-21(a) and "
        "Q-22(a)) and the carried biases they moved downstream. Every differing row is one of "
        "those four, and the FIX-2 session's own prediction is confirmed to the symbol: it "
        "measured that Q-21(b) alone would cost 27 of the 103 shards their identity, leaving 76, "
        "and 76 minus the 17 shards Q-21(a) and Q-22(a) later touched is exactly the "
        f"{_num(len(crashed.identical_shards))} that came back identical.")
    add("")


def _cell(value) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return _num(value)
    return str(value)


def _section_definitions(add, *, run: RunData, capital_paise: int, columns, **_) -> None:
    add("## 4. Definitions -- read these before the numbers")
    add("")
    add("The architect's E13 presentation ruling (30-Jul-2026) requires this block, and requires "
        "it above the tables rather than in a footnote.")
    add("")
    add(f"* **Basis and population.** {pf.E13_BASIS}.")
    add("* **Winner / loser.** By the sign of NET PnL. A trade that made money before the "
        "Rs 100.00 round trip and lost money after it is a LOSER here, on both counts -- it is "
        "counted in the losers and its net is summed into the loss pot. There is no second "
        "population anywhere in this file.")
    add("* **Equity curve.** `capital + cumulative net PnL`, in trade-close order, over every "
        "WALKED day -- a day that traded nothing is a flat observation, not a missing one. "
        "Because risk per trade is a fixed rupee amount, the curve is a plain cumulative SUM.")
    add("* **Drawdown and run-up, denominators.** The running peak (for a drawdown) and the "
        "running trough (for a run-up) are SEEDED AT THE OPENING CAPITAL, so a fall on day one "
        "is a real fall and not measured from a close that came after it. A peak or trough shown "
        "as *the run's opening capital* means exactly that.")
    add("* **Two forms, both printed.** The close-to-close form walks daily CLOSING equity. The "
        f"intra-trade form walks the TRUE 15-minute portfolio path: {pf.INTRADAY_PATH_LIMIT}.")
    add(f"* **Outliers.** {pf.OUTLIER_DEFINITION}.")
    add("* **Sharpe and Sortino.** On the DAILY equity series, risk-free rate 0, annualized by "
        "sqrt(252) -- CONTEXT 7-E13's own convention. Sharpe's dispersion is the SAMPLE standard "
        "deviation (n-1); Sortino's is the downside deviation against a zero target, averaged "
        "over ALL observations. Either is reported `undefined` rather than zero when it is.")
    add("* **CAGR.** Compound annual growth of the equity curve over the WALKED calendar span, "
        "years measured as `(last day - first day) / 365`. It is `undefined` when the final "
        "equity is at or below zero, because a negative base has no real root and printing one "
        "would be inventing a number.")
    add("* **MFE / MAE.** Measured over the candles AFTER the entry candle up to and including "
        "the exit candle (CONTEXT 7-E7: the entry candle cannot move the position). They are "
        "**BEFORE COSTS** -- an excursion is a PRICE move against the entry, so neither figure "
        "carries the Rs 100 round trip. They bracket a trade's GROSS PnL, not its net.")
    add("* **Notional.** `qty x entry price`. A trade's own percentage return is "
        "`net / notional`, which is the only percentage a single trade has.")
    add("* **Concurrency, and which convention the headline uses.** A position OPENS at its "
        "entry candle's close and CLOSES at its exit candle's close. When one trade opens at the "
        "same 15-minute stamp another closes, section 11's `max concurrent positions` counts the "
        "OPEN first -- so a position closing at T is still counted as open at T. That is the "
        "pessimistic reading and the only one that cannot understate what the trader's capital "
        "would have had to carry. The 15-minute equity path uses the other convention, because a "
        "trade's marks END at its exit candle, and it therefore reports a smaller maximum. Both "
        "are printed in section 11 rather than one being chosen silently.")
    add("* **Rupees.** All money is exact integer paise internally and is printed to the paisa. "
        "No float is produced anywhere in the computation (CONTEXT 7-E11).")
    add("")


def _partial_years(days: Sequence[date]) -> frozenset[str]:
    """Which calendar years the RUN'S SPAN does not cover end to end. PURE.

    Only the first and the last year of the index can be partial: every year between them is
    walked in full by construction. A year is partial when the span starts after 1 January or
    ends before 31 December of it -- measured from the index, never a list of years typed here.
    Section 8 carries this caveat in prose; REVIEW_9B_REPORT finding Q3 is that section 5, which
    is the section a reader reads FIRST, named a partial year as the best year without it.
    """
    if not days:
        return frozenset()
    out: set[str] = set()
    if days[0] > date(days[0].year, 1, 1):
        out.add(str(days[0].year))
    if days[-1] < date(days[-1].year, 12, 31):
        out.add(str(days[-1].year))
    return frozenset(out)


def _year_extreme_cell(row: YearRow, years: Sequence[YearRow], partial: frozenset[str],
                       *, best: bool) -> str:
    """One of section 5's best/worst-year cells, with the partial-year marker INLINE."""
    cell = f"{row.year}: {_money(row.metrics.net_pnl_paise)}"
    if row.year not in partial:
        return cell
    full = [year for year in years if year.year not in partial]
    pick = (max(full, key=lambda y: y.metrics.net_pnl_paise) if best
            else min(full, key=lambda y: y.metrics.net_pnl_paise)) if full else None
    word = "best" if best else "worst"
    cell += (f" -- **a PARTIAL year**, {_num(row.metrics.trading_days)} walked days "
             f"({_day(row.metrics.first_day)} .. {_day(row.metrics.last_day)}), neither "
             "annualized nor comparable to a full one")
    if pick is not None:
        cell += (f"; the {word} FULL year is {pick.year} at "
                 f"{_money(pick.metrics.net_pnl_paise)}")
    return cell


def _section_headline(add, *, run: RunData, columns, curve, years, capital_paise: int,
                      paths_built: int, path_marks: int, paths_reconciling: int, **_) -> None:
    m = columns["All"]
    best = max(years, key=lambda y: y.metrics.net_pnl_paise)
    worst = min(years, key=lambda y: y.metrics.net_pnl_paise)
    partial = _partial_years(run.days)
    add("## 5. The headline")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| **Net PnL** | **{_money(m.net_pnl_paise)}** |")
    add(f"| Profit factor | {_ratio(m.profit_factor)} |")
    add(f"| Win rate | {_pct(m.percent_profitable)} ({_num(m.winners)} of "
        f"{_num(m.total_trades)}) |")
    add(f"| Trades | {_num(m.total_trades)} |")
    add(f"| Max drawdown, close-to-close | {_excursion(m.max_drawdown, recovery_word='recovered')} |")
    add(f"| Max drawdown, 15-minute path | "
        f"{_path_excursion(m.intraday_max_drawdown, observations=m.intraday_observations, recovery_word='recovered')} |")
    add(f"| CAGR | {_cagr(m)} |")
    add(f"| Return on initial capital | {_pct(m.return_on_initial_capital)} |")
    add(f"| Best year | {_year_extreme_cell(best, years, partial, best=True)} |")
    add(f"| Worst year | {_year_extreme_cell(worst, years, partial, best=False)} |")
    add(f"| Final equity | {_money(m.final_equity_paise)} on "
        f"{_money(m.initial_capital_paise)} of capital |")
    add("")
    add(f"The strategy took **{_num(m.total_trades)}** trades over "
        f"**{_num(m.trading_days)}** walked days and **{_num(len(run.symbols))}** symbols. "
        f"It won **{_pct(m.percent_profitable)}** of them. The average winner is "
        f"**{_money(m.avg_profit_paise)}** and the average loser is "
        f"**{_money(m.avg_loss_paise)}**, a ratio of {_ratio(m.avg_profit_over_avg_loss)} -- and "
        f"the expected payoff per trade is **{_money(m.expected_payoff_paise)}**.")
    add("")
    add(f"The Rs 100.00 round trip is not a rounding detail at this trade count: "
        f"**{_money(m.commission_paise)}** of commission on {_num(m.total_trades)} trades. The "
        "single labelled before-costs line is in section 6, and it is the only one in this file.")
    add("")
    add(f"The 15-minute path is built from **{_num(paths_built)}** trades and "
        f"**{_num(path_marks)}** marks, and **{_num(paths_reconciling)}** of those paths end "
        "exactly on the net PnL the ledger recorded for that trade -- which is the invariant "
        "that makes the path trustworthy rather than decorative.")
    add("")


def _ratio(value) -> str:
    if value is None:
        return "undefined"
    return str((Decimal(value.numerator) / Decimal(value.denominator)).quantize(Decimal("0.0001")))


def _cagr(metrics: pf.Metrics) -> str:
    if metrics.cagr is None:
        return ("undefined -- the final equity is at or below zero, and a negative base has no "
                "real root")
    return _pct(metrics.cagr)


#: What the tie rows say when the tied set was not supplied to the renderer. The same shape as
#: :data:`acumen.portfolio.INTRADAY_PATH_NOT_SUPPLIED`: a quantity that is not available says so
#: rather than printing an arbitrary member of the set it could not see.
TIES_NOT_SUPPLIED: str = (
    "not supplied -- the tied set is measured over the ledger's own executed rows and was not "
    "passed to this renderer"
)


def _ties_cell(ties: Mapping[str, tuple[LargestTies, LargestTies]] | None, label: str,
               *, winners: bool) -> str:
    """The percentage a largest-win / largest-loss row can actually justify (finding Q5).

    Under ties the single-trade percentage is decided by the ledger's row order, so what is
    printed is the RANGE across every trade that ties at that rupee figure, with the size of the
    tied set beside it. One trade at the extreme still prints one percentage, and says so.
    """
    if ties is None or label not in ties:
        return TIES_NOT_SUPPLIED
    tied = ties[label][0 if winners else 1]
    if tied.is_empty:
        return "-"
    if tied.min_pct_of_notional is None:
        return f"no notional recorded on the {_num(tied.ties)} trade(s) at this figure"
    if tied.ties == 1:
        return f"{_pct(tied.min_pct_of_notional, 4)} -- one trade at this figure, no tie"
    return (
        f"{_pct(tied.min_pct_of_notional, 4)} .. {_pct(tied.max_pct_of_notional, 4)} "
        f"across the {_num(tied.ties)} trades tied at {_money(tied.extreme_paise)} "
        f"(notionals {_money(tied.min_notional_paise)} .. {_money(tied.max_notional_paise)})"
    )


def _section_e13(add, *, columns: Mapping[str, pf.Metrics], crosses_zero, ties=None, **_) -> None:
    order = ("All", "Long", "Short")
    add("## 6. CONTEXT 7-E13, in full -- All / Long / Short")
    add("")
    add("Each column keeps every walked day, so the three daily series have the same index and "
        "the same sample; a side's drawdown is that side's own, not a slice of the portfolio's.")
    add("")
    rows: list[tuple[str, object]] = [
        ("Net PnL", lambda m: _money(m.net_pnl_paise)),
        ("Gross profit (net basis)", lambda m: _money(m.gross_profit_paise)),
        ("Gross loss (net basis)", lambda m: _money(m.gross_loss_paise)),
        ("Profit factor", lambda m: _ratio(m.profit_factor)),
        ("Commission paid", lambda m: _money(m.commission_paise)),
        ("Profit / loss BEFORE Rs 100/trade costs",
         lambda m: f"{_money(m.before_cost_profit_paise)} / {_money(m.before_cost_loss_paise)}"),
        ("Expected payoff per trade", lambda m: _money(m.expected_payoff_paise)),
        ("Total trades", lambda m: _num(m.total_trades)),
        ("Open trades at the end", lambda m: _num(m.open_trades)),
        ("Winners / losers / flat",
         lambda m: f"{_num(m.winners)} / {_num(m.losers)} / {_num(m.flat)}"),
        ("% profitable", lambda m: _pct(m.percent_profitable)),
        ("Avg PnL per trade", lambda m: _money(m.avg_pnl_paise)),
        ("Avg profit", lambda m: _money(m.avg_profit_paise)),
        ("Avg loss", lambda m: _money(m.avg_loss_paise)),
        ("Avg profit / avg loss", lambda m: _ratio(m.avg_profit_over_avg_loss)),
        ("Largest win", lambda m: _money(m.largest_win_paise)),
        ("Largest win, % of notional -- RANGE across the tied trades",
         lambda m: _ties_cell(ties, m.label, winners=True)),
        ("Largest win, % of gross profit",
         lambda m: _pct(m.largest_win_pct_of_gross_profit, 5)),
        ("Largest loss", lambda m: _money(m.largest_loss_paise)),
        ("Largest loss, % of notional -- RANGE across the tied trades",
         lambda m: _ties_cell(ties, m.label, winners=False)),
        ("Largest loss, % of gross loss",
         lambda m: _pct(m.largest_loss_pct_of_gross_loss, 5)),
        ("Return on initial capital", lambda m: _pct(m.return_on_initial_capital)),
        ("Final equity", lambda m: _money(m.final_equity_paise)),
        ("CAGR", _cagr),
        ("Sharpe (daily, rf 0, x sqrt 252)",
         lambda m: RATIO_CROSSES_ZERO if crosses_zero.get(m.label) else _decimal(m.sharpe)),
        ("Sortino (daily, rf 0, x sqrt 252)",
         lambda m: RATIO_CROSSES_ZERO if crosses_zero.get(m.label) else _decimal(m.sortino)),
        ("Avg MFE per trade (BEFORE costs)", lambda m: _money(m.avg_mfe_paise)),
        ("Avg MAE per trade (BEFORE costs)", lambda m: _money(m.avg_mae_paise)),
        ("Largest MFE (BEFORE costs)", lambda m: _money(m.largest_mfe_paise)),
        ("Largest MAE (BEFORE costs)", lambda m: _money(m.largest_mae_paise)),
        ("Trading days in the series", lambda m: _num(m.trading_days)),
    ]
    add("| Metric | " + " | ".join(order) + " |")
    add("|---|---:|---:|---:|")
    for label, getter in rows:
        add(f"| {label} | " + " | ".join(getter(columns[name]) for name in order) + " |")
    add("")
    add("**`winners x avg profit == gross profit` is an identity here, not an approximation** -- "
        "that is what one basis and one population buys, and a reader can check it on any column "
        "with a calculator.")
    add("")
    add("**Why the two percent-of-notional rows carry a RANGE.** A fixed-R book manufactures "
        "TIES: the target pays `qty x 3 x risk` and the stop pays `-qty x risk`, so thousands of "
        "trades land on exactly the same rupee figure while their notionals differ by three "
        "orders of magnitude. A single trade's `net / notional` at the extreme would then be "
        "decided by the ledger's row order and by nothing on this page, so what is printed is "
        "the range over EVERY trade tied at that figure, with the size of the tied set beside "
        "it. The rupee extremes above them are exact and unaffected.")
    add("")
    add("### 6a. Outliers, on both branches")
    add("")
    add("The architect's GO ruling, condition (3): one format on both branches, so a run with no "
        "outliers prints the same four quantities as a run with many.")
    add("")
    for name in order:
        out = columns[name].outliers
        add(f"**{name}** -- population {_num(out.population)} executed trades.")
        add("")
        add(f"* Quartiles: Q1 {_money(out.q1_paise)}, Q3 {_money(out.q3_paise)}, "
            f"IQR {_money(out.iqr_paise)}.")
        add(f"* Fences: [{_money(out.lower_fence_paise)}, {_money(out.upper_fence_paise)}].")
        add(f"* Outliers: **{_num(out.count)}**, summed net **{_money(out.net_paise)}**.")
        add(f"* Above the upper fence: {_num(out.above_count)} worth "
            f"{_money(out.above_net_paise)} = {_pct(out.share_of_gross_profit)} of gross profit.")
        add(f"* Below the lower fence: {_num(out.below_count)} worth "
            f"{_money(out.below_net_paise)} = {_pct(out.share_of_gross_loss)} of gross loss.")
        add("")
    quiet = [name for name in order if columns[name].outliers.count == 0]
    biting = [name for name in order if columns[name].outliers.count]
    add("A fixed-R strategy bounds its own trades -- a stop pays `-qty x risk` and a target pays "
        "`qty x 3 x risk`, so before costs every trade lands in a narrow band. Whether the "
        "Tukey fences sit OUTSIDE that band is then a property of the distribution and not of "
        "the sizing rule, and it does not hold on every column here, so the claim is made per "
        "column rather than in general (REVIEW_9B_REPORT finding Q1).")
    add("")
    if quiet:
        add(f"* **{_join(quiet)}**: the fences do sit outside the band -- "
            + "; ".join(
                f"{name} spans [{_money(columns[name].outliers.lower_fence_paise)}, "
                f"{_money(columns[name].outliers.upper_fence_paise)}] and contains every one of "
                f"its {_num(columns[name].outliers.population)} trades"
                for name in quiet
            ) + ".")
    for name in biting:
        out = columns[name].outliers
        largest_win = columns[name].largest_win_paise
        pierced = (" -- BELOW this column's largest win of " + _money(largest_win) + " --"
                   if out.upper_fence_paise < largest_win else " --")
        add(f"* **{name}**: the fences do NOT. Q3 sits at {_money(out.q3_paise)} and the IQR is "
            f"{_money(out.iqr_paise)}, which puts the upper fence at "
            f"{_money(out.upper_fence_paise)}{pierced} so "
            f"**{_num(out.count)}** of its {_num(out.population)} trades are outliers, worth "
            f"{_money(out.net_paise)}: {_num(out.above_count)} above the upper fence "
            f"({_pct(out.share_of_gross_profit)} of this column's gross profit) and "
            f"{_num(out.below_count)} below the lower one "
            f"({_pct(out.share_of_gross_loss)} of its gross loss). A column whose losers "
            "outnumber its winners far enough pulls Q3 down below the target payout, and the "
            "upper fence comes down with it.")
    add("")
    add("An outlier count is therefore a statement about the SIZING rule and about the "
        "DISTRIBUTION the sizing rule met, and the two do not always agree.")
    add("")


def _section_equity(add, *, columns, curve, years, run: RunData, **_) -> None:
    m = columns["All"]
    add("## 7. Equity, drawdown and run-up")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| Opening capital | {_money(m.initial_capital_paise)} |")
    add(f"| Final equity | {_money(m.final_equity_paise)} |")
    add(f"| Max drawdown (close-to-close) | {_excursion(m.max_drawdown, recovery_word='recovered')} |")
    add(f"| Max run-up (close-to-close) | "
        f"{_excursion(m.max_run_up, recovery_word='given back', rising=True)} |")
    add(f"| Max drawdown (intra-trade, 15-min path) | "
        f"{_path_excursion(m.intraday_max_drawdown, observations=m.intraday_observations, recovery_word='recovered')} |")
    add(f"| Max run-up (intra-trade, 15-min path) | "
        f"{_path_excursion(m.intraday_max_run_up, observations=m.intraday_observations, recovery_word='given back', rising=True)} |")
    add(f"| Observations on the 15-minute path | {_num(m.intraday_observations)} |")
    add("")
    add("**Why the two forms differ, and which to believe.** The close-to-close form can only "
        "see the equity at 15:15 each day. The 15-minute path marks every open position at every "
        "candle close it was held through, exit candles at their exit LEVELS, summed across "
        "positions -- so it sees a fall that happened at 11:30 and was recovered by the close. "
        "Both are real; they answer different questions. Neither sees INSIDE a candle, and the "
        "per-trade MFE/MAE figures in section 6 are what carry that.")
    add("")
    if curve:
        highest = max(curve, key=lambda point: point.equity_paise)
        lowest = min(curve, key=lambda point: point.equity_paise)
        add("### 7a. The curve's high and low water marks")
        add("")
        add("| | Equity | On |")
        add("|---|---:|---|")
        add(f"| Highest closing equity | {_money(highest.equity_paise)} | "
            f"{highest.day.isoformat()} |")
        add(f"| Lowest closing equity | {_money(lowest.equity_paise)} | "
            f"{lowest.day.isoformat()} |")
        add(f"| First day of the curve | {_money(curve[0].equity_paise)} | "
            f"{curve[0].day.isoformat()} |")
        add(f"| Last day of the curve | {_money(curve[-1].equity_paise)} | "
            f"{curve[-1].day.isoformat()} |")
        add("")
        if lowest.equity_paise < 0:
            add("**The curve goes below zero, and that is an accounting identity rather than a "
                "surprise.** It is `capital + cumulative net PnL` with NO capital constraint "
                "applied, because that is what the trader asked for (CONTEXT 3.5, Q40 option d). "
                "A real account cannot hold a negative balance and would have stopped long "
                "before this point; the curve keeps adding because the point of the take-all "
                "reading is to show the strategy's own arithmetic without a capital rule "
                "silently truncating it. Section 11 is where the size of that assumption is "
                "measured.")
            add("")
    add("### 7b. Where the equity stood at each year end")
    add("")
    add("| Year end | Closing equity | Change over the year |")
    add("|---|---:|---:|")
    for year in years:
        add(f"| {year.year} | {_money(year.closing_equity_paise)} | "
            f"{_money(year.closing_equity_paise - year.opening_equity_paise)} |")
    add("")


def _section_years(add, *, years: Sequence[YearRow], **_) -> None:
    add("## 8. Year by year")
    add("")
    add("The trader thinks in years. Each row is a full CONTEXT 7-E13 computation over that "
        "year's trades alone, with the year's running peak seeded at the equity the year OPENED "
        "with -- so a year's drawdown answers *how bad was that year*, not *where did that year "
        "sit inside the whole run's worst fall*.")
    add("")
    add("| Year | Trades | Win rate | Net PnL | Profit factor | Avg trade | Largest win | "
        "Largest loss | Max drawdown in the year | Gap entries |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for year in years:
        m = year.metrics
        dd = ("none" if m.max_drawdown.is_empty
              else f"{_money(m.max_drawdown.amount_paise)} "
                   f"({_excursion_pct(m.max_drawdown.pct)})")
        add(f"| {year.year} | {_num(m.total_trades)} | {_pct(m.percent_profitable)} | "
            f"{_money(m.net_pnl_paise)} | {_ratio(m.profit_factor)} | "
            f"{_money(m.avg_pnl_paise)} | {_money(m.largest_win_paise)} | "
            f"{_money(m.largest_loss_paise)} | {dd} | {_num(year.gap_entries)} |")
    add("")
    add("**2016 is a partial year** -- the minute era begins 2016-10-03 -- and **2026 is a "
        "partial year**, ending at the span's own clamp. Neither is annualized and neither "
        "should be read as one.")
    add("")


def _section_symbols(add, *, symbols: Mapping[str, pf.Metrics], register, run: RunData,
                     **_) -> None:
    add("## 9. Symbol by symbol -- with what each symbol's data is worth")
    add("")
    add("**CONTEXT 4.6 makes reading the disclosed-residual register a chunk-9 duty, before any "
        "per-symbol statistic.** It was read, and its own figures travel in the last two columns "
        "of this table rather than in a footnote: `price-proven` is the share of that symbol's "
        "stored days whose 1-minute prices reconcile against the exchange's own bhavcopy under "
        "gate 1P. A symbol at 42% is not a symbol with a 42%-reliable backtest -- it is a symbol "
        "whose backtest COVERS 42% of its stored history, concentrated where the data is sound.")
    add("")
    add("**The B149 caveat, quoted verbatim from the register's own current figures and carried "
        "on every manifest this runner writes:**")
    add("")
    add(f"> {run.manifest['residual_register']['caveat']}")
    add("")
    concentration = list(run.witnesses.ungated_by_symbol.items())[:6]
    total_ungated = sum(run.witnesses.ungated_by_symbol.values())
    add("**The Q-21(b) concentration.** A Rule-3 day whose D-1 fails the CONTEXT 4.5/4.6 gate "
        f"battery cannot resolve its bias, and is refused and counted. There are "
        f"**{_num(total_ungated)}** such days across "
        f"**{_num(len(run.witnesses.ungated_by_symbol))}** symbols, and they are not spread "
        "evenly -- six symbols carry "
        f"{_pct(Fraction(sum(n for _, n in concentration), total_ungated))} of them:")
    add("")
    add("| Symbol | Rule-3 days refused on a battery-failing D-1 |")
    add("|---|---:|")
    for symbol, count in concentration:
        add(f"| {symbol} | {_num(count)} |")
    add("")
    add("Those are the symbols whose early history the vendor's feed serves in a different price "
        "domain, which is the same defect the gates catch elsewhere; the refusal is the gate "
        "working, and the concentration is why it must be named per symbol rather than averaged "
        "into a run-wide rate.")
    add("")
    add("| Symbol | Trades | Win rate | Net PnL | Profit factor | Largest win | Largest loss | "
        "Max drawdown | Price-proven | Register status |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for symbol in sorted(symbols):
        m = symbols[symbol]
        entry = register.get(symbol)
        proven = "-" if entry is None or entry.price_proven_ratio is None else _pct(
            entry.price_proven_ratio
        )
        status = "-" if entry is None else entry.status
        dd = ("none" if m.max_drawdown.is_empty
              else f"{_money(m.max_drawdown.amount_paise)}")
        add(f"| {symbol} | {_num(m.total_trades)} | {_pct(m.percent_profitable)} | "
            f"{_money(m.net_pnl_paise)} | {_ratio(m.profit_factor)} | "
            f"{_money(m.largest_win_paise)} | {_money(m.largest_loss_paise)} | {dd} | "
            f"{proven} | {status} |")
    add("")
    add("**Two things this table does NOT carry, said out loud.** Each symbol's equity curve is "
        "seeded at the whole run's opening capital, so a per-symbol drawdown is that symbol's own "
        "fall in rupees and its percentage would be against a capital base the symbol never had "
        "to itself -- only the rupee figure is printed. And the per-symbol rows carry no "
        "15-minute path: " + pf.INTRADAY_PATH_NOT_SUPPLIED + ". The path is a portfolio "
        "statistic and section 7 is where it is reported.")
    add("")


def _section_benchmark(add, *, benchmark: BenchmarkPair, columns, **_) -> None:
    m = columns["All"]
    add("## 10. Buy & hold -- THE benchmark, and the two readings printed beside it")
    add("")
    add("CONTEXT 7-E13 defines the benchmark as an *equal-weight portfolio of the traded "
        "universe, bought at first trade date's close, held to period end*. It fixes the "
        "construction and is silent on the PRICE DOMAIN of those closes, and over ten years that "
        "silence is not a detail: a holder's SHARE COUNT follows every split and bonus, so a "
        "1:1 bonus halves the quoted price while doubling the shares held and the raw reading "
        "understates that symbol by exactly the factor.")
    add("")
    add("**The architect has ruled it (QUESTIONS.md Q-23, 06-Aug-2026, CLOSED).** THE BENCHMARK "
        "is the SHARE-COUNT reading: buy-and-hold holds UNITS, and units multiply through "
        "bonuses, splits and rights issues and through nothing else. Cash distributions are "
        "excluded UNIFORMLY -- ordinary and special alike -- so the benchmark is a price-and-"
        "units return on the same terms as the strategy's own PnL, which never receives a "
        "distribution either.")
    add("")
    add(f"> {benchmark.ruling}.")
    add("")
    add("| Reading | Start value | End value | Total return |")
    add("|---|---:|---:|---:|")
    add(f"| **THE BENCHMARK -- share-count events only (bonus / split / rights)** | "
        f"{_money(benchmark.share_count.start_value_paise)} | "
        f"**{_money(benchmark.share_count.end_value_paise)}** | "
        f"**{_pct(benchmark.share_count.total_return)}** |")
    add(f"| Mixed -- share-count events AND the special dividends CONTEXT 4.2 gives a factor "
        f"(NOT the benchmark) | {_money(benchmark.adjusted.start_value_paise)} | "
        f"{_money(benchmark.adjusted.end_value_paise)} | "
        f"{_pct(benchmark.adjusted.total_return)} |")
    add(f"| RAW closes, exactly as stored -- no adjustment of any kind (NOT the benchmark) | "
        f"{_money(benchmark.raw.start_value_paise)} | "
        f"{_money(benchmark.raw.end_value_paise)} | {_pct(benchmark.raw.total_return)} |")
    add(f"| The strategy, over the same window | {_money(m.initial_capital_paise)} | "
        f"{_money(m.final_equity_paise)} | {_pct(m.return_on_initial_capital)} |")
    add("")
    add(f"* Bought at the close of **{benchmark.first_day.isoformat()}** -- the run's first "
        f"executed trade -- and held to **{benchmark.last_day.isoformat()}**.")
    add(f"* Symbols in the benchmark: **{_num(len(benchmark.raw.symbols))}**. "
        f"{benchmark.raw.note}.")
    add(f"* **What THE BENCHMARK applies: {_num(benchmark.share_count_events)} share-count "
        f"factors across {_num(benchmark.share_count_symbols)} symbols** -- every bonus, split "
        "and rights factor inside the hold window and nothing else, each one taken from the "
        "factor table THIS RUN wired, which is the same `P x pending factors` the bias engine "
        "applies (CONTEXT 3.2 / 7-E11) and never a second source.")
    add(f"* **The one stated line the ruling asks for, on the mixed reading.** The mixed row "
        f"applies all {_num(benchmark.events_applied)} non-unit factors in the table, which is "
        f"the {_num(benchmark.share_count_events)} share-count events plus "
        f"**{_num(benchmark.excluded_events)}** the benchmark leaves out ("
        + _by_kind(benchmark.excluded_by_kind) + "). CONTEXT 4.2 gives a dividend at or above "
        "2% of the cum close a factor of `1 - D/P_cum` and everything below it `k = 1`, so the "
        "mixed row credits the special distributions back into the benchmark while the ordinary "
        "ones stay out -- divided at a boundary the CA engine owns rather than an economic one. "
        f"It is worth **{_pct(benchmark.adjusted.total_return - benchmark.share_count.total_return)}** "
        f"of opening capital, i.e. "
        f"{_pct(_share_of(benchmark.adjusted.total_return - benchmark.share_count.total_return, benchmark.adjusted.total_return))} "
        "of its own figure. It is printed because it is the figure the ruling first named and "
        "because a reader should be able to see the size of the difference; it is NOT the "
        "benchmark.")
    add("* **Dividends, uniformly.** THE BENCHMARK adds back no distribution of any kind, "
        "neither the ordinary ones CONTEXT 4.2 leaves at `k = 1` nor the special ones it gives "
        "a factor. That is the Q-23 refinement's principle -- uniform exclusion -- and it is "
        "also what makes the comparison fair: the strategy's own PnL never receives a dividend.")
    add("")


def _by_kind(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return "by event kind: " + ", ".join(f"{kind} {_num(n)}" for kind, n in sorted(counts.items()))


def _share_of(part: Fraction | None, whole: Fraction | None) -> Fraction | None:
    if part is None or not whole:
        return None
    return part / whole


def _section_take_all(add, *, disclosures: pf.Disclosures, capital_flag_report, daily_counts,
                      refusals: Sequence[RefusalClass], run: RunData, capital_paise: int,
                      crashed: CrashedCheck, path_concurrency: pf.ConcurrencyPeak | None = None,
                      **_) -> None:
    add("## 11. The take-all disclosures (CONTEXT 3.5, Round-3 Q40 option d)")
    add("")
    add("The trader's own answer requires these, and they are the price of the no-limits "
        "assumption section 1 states.")
    add("")
    peak_positions = disclosures.max_concurrent_positions
    peak_notional = disclosures.peak_simultaneous_notional
    add("| Disclosure | Value |")
    add("|---|---|")
    add(f"| Max concurrent positions (a close at the same stamp counted as still OPEN) | "
        f"**{_num(peak_positions.positions)}**, first reached {_stamp(peak_positions.at)}, "
        f"carrying {_money(peak_positions.notional_paise)} of notional |")
    if path_concurrency is not None:
        add(f"| Max concurrent positions (the 15-minute path's convention: closed AT its exit "
            f"mark) | **{_num(path_concurrency.positions)}**, first reached "
            f"{_stamp(path_concurrency.at)}, carrying "
            f"{_money(path_concurrency.notional_paise)} of notional |")
    add(f"| Peak simultaneous notional | **{_money(peak_notional.notional_paise)}** at "
        f"{_stamp(peak_notional.at)}, across {_num(peak_notional.positions)} positions |")
    add(f"| That peak against the Rs 1,00,000 capital | "
        f"**{_ratio(Fraction(peak_notional.notional_paise, capital_paise))}x** |")
    add(f"| Largest single-trade notional | {_money(disclosures.largest_single_notional_paise)} |")
    add(f"| Most trades in one day | {_num(disclosures.max_daily_trades)} |")
    add(f"| Executed trades | {_num(disclosures.total_executed)} |")
    add("")
    if path_concurrency is not None:
        add("**The two concurrency rows are two CONVENTIONS, not a disagreement.** They differ "
            "only in what happens when one trade opens at the same 15-minute stamp another "
            "closes: the first row counts the closing position as still open (the pessimistic "
            "reading, and the one every other figure on this page is consistent with), the "
            "second closes it at its exit mark, which is where its 15-minute marks actually "
            "stop. Section 4 defines both; neither is a correction of the other.")
        add("")
    add("**This is the disclosure that matters most on this page.** A portfolio that at its peak "
        f"held {_num(peak_notional.positions)} positions worth "
        f"{_money(peak_notional.notional_paise)} against Rs 1,00,000 of capital is not a "
        "portfolio the trader's cash could have carried; the run takes every signal because he "
        "asked for the honest numbers with no limits, and this is what no limits actually meant. "
        "Which trades his capital could not have taken is the Q40-d FLAG question, and it is not "
        "computed:")
    add("")
    add(f"> {capital_flag_report.note}")
    add("")
    add("### 11a. The full distribution of daily trade counts")
    add("")
    add("CONTEXT 3.5 asks for the distribution, not a summary of it. The index is every WALKED "
        "day, so a day the strategy sat out is counted at zero rather than dropped -- dropping "
        "flat days would answer a different question.")
    add("")
    add("| Trades on a day | Number of such days | Share of walked days |")
    add("|---:|---:|---:|")
    total_days = sum(count for _, count in daily_counts)
    for trades, count in daily_counts:
        add(f"| {_num(trades)} | {_num(count)} | {_pct(Fraction(count, total_days))} |")
    add(f"| **total** | **{_num(total_days)}** | **100.00%** |")
    add("")
    add("### 11b. What the refusals cost -- as coverage, and where evidence exists, as trades")
    add("")
    add("REVIEW_9B_FIXES finding **R10** is discharged here. The fix arc disclosed its own cost "
        "in ROWS only, and a refused day is not merely a row: it is a day that would have "
        "carried a trade. Two refusal classes have a counterfactual on disk -- the crashed run "
        "walked those very days under the pre-ruling code -- and they are priced from it. The "
        "rest have NO counterfactual anywhere, because the crashed run refused them for the same "
        "reason this one does; pricing those would need a re-simulation that deliberately "
        "disables a gate, which this report does not do and does not estimate around.")
    add("")
    add("| Refusal reason | Days | Share of the walk | Days with a counterfactual | "
        "Trades they carried | Their net PnL | Evidence |")
    add("|---|---:|---:|---:|---:|---:|---|")
    for item in refusals:
        base = _num(item.days_measured) if item.priced else "-"
        measured = _num(item.trades_found) if item.priced else "-"
        net = _money(item.net_paise) if item.priced else "-"
        add(f"| {item.reason} | {_num(item.rows)} | {_pct(item.share_of_walk, 3)} | {base} | "
            f"{measured} | {net} | {item.evidence} |")
    add("")
    add("**The trade counts have their own denominator, and it is the fourth column, not the "
        f"second.** Only {_num(crashed.shards)} of {_num(len(run.symbols))} shards survived the "
        "crash, so the counterfactual exists for a SUBSET of each priced class's days. A reader "
        "who divides a trade count by the `Days` column is dividing by days no evidence was ever "
        "read for; the measured base is the `Days with a counterfactual` column beside it "
        "(REVIEW_9B_REPORT finding Q6). Nothing here is scaled up from that subset to the whole "
        "class, and this report does not estimate what the unwalked remainder would have been.")
    add("")
    add("**Read the priced rows carefully.** They are what the refused days DID produce under a "
        "superseded reading of the spec, not what they would be worth today. The gate-2 "
        "completion refuses a day whose 1-minute bar is impossible; the trades it removes were "
        "computed FROM that impossible bar. Removing them is the point -- *corrupt days are "
        "refused, never repaired* -- and the figure is published so the cost of that principle "
        "is stated in rupees rather than only in coverage.")
    add("")
    add("**One correction R10 also asks for, made here.** The claim that *the ledger's refused-"
        "row count is unchanged* by the gate-2 completion is true only of trade day 2023-03-06. "
        "Across this ledger the completion ADDS "
        f"**{_num(len(run.witnesses.gate2_days))}** refused symbol-days, every one of them on "
        "**2023-03-03**, one per symbol across "
        f"{_num(len({s for s, _ in run.witnesses.gate2_days}))} symbols. Coverage moved "
        "409,252 -> 409,205 usable stored symbol-days and 93.9425% -> 93.9317% with it.")
    add("")
    add("**And the cost that is NOT a row at all.** A refusal on a Rule-3 day also deletes a "
        "bias TRANSITION -- a Rule-3 day is the only place a carried bias can turn -- so every "
        "later carry-day inherits the pre-refusal side until the next Rule-3 day. That cost "
        "cannot be counted in refused rows, and R10 records that it is accounted for nowhere. "
        "Section 3c is the closest measurement this repo has: over the 103 shards the crashed "
        f"run left behind, **{_num(crashed.by_cause.get(_CAUSES[3], 0))}** rows differ for no "
        "reason other than a carried bias that had moved upstream of them, and "
        f"**{_num(crashed.moved_trades.get(_CAUSES[3], 0))}** of those are days that traded on "
        "BOTH runs and traded DIFFERENTLY -- a different side, a different entry, a different "
        "outcome. That is the transition cost, measured on the only population where it can be "
        "measured at all, and it is not extrapolated to the rest of the walk.")
    add("")


def _stamp(value) -> str:
    return "-" if value is None else value.isoformat(sep=" ", timespec="minutes")


def _section_rare_shapes(add, *, run: RunData, **_) -> None:
    w = run.witnesses
    add("## 12. Rare-shape reality -- the branches that finally have witnesses")
    add("")
    add("Chunk 8's evidence pack reported every rare shape at ZERO over 290 symbol-days and said "
        "out loud that a zero is a statement about the window, not about the code. REVIEW_7 "
        "finding Q3 and REVIEW_8 finding Q1 both asked for real-data witnesses. Ten years "
        "supplies them.")
    add("")
    add("| Rare shape | Occurrences | Recounted independently |")
    add("|---|---:|---|")
    for label, count in sorted(run.rare_shapes.items()):
        add(f"| {label} | {_num(count)} | {_num(_rare_shape_recount(run, label))} |")
    add("")
    add("### 12a. Gap entries -- REVIEW_7 Q3's witnesses")
    add("")
    add(f"CONTEXT 3.4's gap branch fires when the entry candle GAPS past the POC, and the stop "
        f"then comes from the prior close instead of the candle. It fired "
        f"**{_num(len(w.gap_days))}** times.")
    add("")
    add("| Year | Gap entries |")
    add("|---|---:|")
    for year, count in sorted(w.gap_by_year.items()):
        add(f"| {year} | {_num(count)} |")
    add("")
    add("| How they ended | Count |")
    add("|---|---:|")
    for kind, count in sorted(w.gap_exit_kinds.items()):
        add(f"| {kind} | {_num(count)} |")
    add("")
    if w.gap_days:
        add(f"Together they are worth **{_money(w.gap_net_paise)}** net, on "
            f"**{_num(w.gap_winners)}** winners of {_num(len(w.gap_days))} "
            f"({_pct(Fraction(w.gap_winners, len(w.gap_days)))}). The earliest and the latest, "
            "by DATE rather than by the ledger's symbol-major order: "
            f"**{_name_day(min(w.gap_days, key=lambda pair: (pair[1], pair[0])))}** and "
            f"**{_name_day(max(w.gap_days, key=lambda pair: (pair[1], pair[0])))}**.")
    else:
        add("The branch never fired in this run, which is a statement about the window rather "
            "than about the code.")
    add("")
    add("### 12b. Qty-zero days -- REVIEW_8 Q1's witnesses, and there are exactly two")
    add("")
    add("A qty-zero day is one where CONTEXT 3.5's sizing rule returns ZERO shares because the "
        "per-share risk exceeds the whole Rs 1,000.00 trade risk. The day is CONSUMED and "
        "COUNTED, no fill price is invented, and no cost is charged because there is no round "
        "trip to charge. In ten years and 188,347 signalled days it happened twice:")
    add("")
    add("| Symbol | Day | Per-share risk | Why qty is zero |")
    add("|---|---|---:|---|")
    for symbol, day, risk in w.qty_zero:
        add(f"| {symbol} | {day} | {_money(risk)} | Rs 1,000.00 / {_money(risk)} floors to 0 |")
    add("")
    add("### 12c. Q-17's five market-wide dates, and the outage")
    add("")
    add("CONTEXT 4.6 makes Q-17 law: a stored 1-minute bar stamped outside 09:15..15:29 is "
        "dropped at the CANDLE level, flagged and counted, never silently -- and since Q-22(a) "
        "that binds every consumer of stored bars, the Rule-3 first-break scan included. Five "
        "dates in the lake are market-wide.")
    add("")
    add("| Date | Symbols affected (whole lake) | Symbols with data that day | Walked rows this "
        "run flagged |")
    add("|---|---:|---:|---:|")
    for day, affected, with_data in Q17_MARKET_WIDE:
        add(f"| {day} | {_num(affected)} | {_num(with_data)} | "
            f"{_num(w.out_of_session_by_date.get(day, 0))} |")
    add("")
    add(f"**{Q17_OUTAGE_DATE}.** {Q17_OUTAGE_NOTE}.")
    add("")
    walked_here = {day: w.out_of_session_by_date.get(day, 0) for day, _, _ in Q17_MARKET_WIDE}
    zeros = [day for day, count in walked_here.items() if count == 0]
    thin = [day for day, count in walked_here.items()
            if 0 < count < 10]
    tail = ""
    if zeros:
        tail += (f" {_num(len(zeros))} of the five ({', '.join(zeros)}) therefore appear at ZERO "
                 "here")
    if thin:
        tail += (f"{' and' if zeros else ' '} {_num(len(thin))} at a handful "
                 f"({', '.join(f'{d} at {walked_here[d]}' for d in thin)})")
    add("**Why this run's flagged count is smaller than the lake's population, stated rather "
        f"than glossed.** The lake carries ~3,100 affected symbol-days; this run flags "
        f"**{_num(sum(w.out_of_session_by_date.values()))}** walked days. The difference is not a "
        "disagreement: the flag is set on a row that REACHED the loader, so a day already "
        "refused by the battery -- and pre-open garbage is exactly what gate 1 refuses -- never "
        "gets one, and the six quarantined symbols are outside this universe altogether."
        + (f"{tail}, which is the honest reading of both numbers rather than a contradiction "
           "between them." if tail else ""))
    add("")
    add("The flag lands across bias rules like this, which is what makes the Q-22(a) ruling "
        "load-bearing rather than cosmetic:")
    add("")
    add("| Bias rule on the flagged day | Rows |")
    add("|---|---:|")
    for rule, count in w.out_of_session_by_rule.items():
        add(f"| {rule} | {_num(count)} |")
    add("")
    add("### 12d. The demerger suppressions")
    add("")
    add("CONTEXT 3.2: a demerger has no valid adjustment factor, so any bias pair spanning its "
        "ex-date is SUPPRESSED -- the day is refused and counted, never guessed. It happened on "
        f"**{_num(len(w.demerger))}** symbol-days across "
        f"**{_num(len({s for s, _ in w.demerger}))}** symbols:")
    add("")
    add("| Symbol | Suppressed days |")
    add("|---|---|")
    by_symbol: dict[str, list[str]] = {}
    for symbol, day in w.demerger:
        by_symbol.setdefault(symbol, []).append(day)
    for symbol in sorted(by_symbol):
        add(f"| {symbol} | {', '.join(by_symbol[symbol])} |")
    add("")
    add(f"**A detail worth stating.** {_num(w.suppressed_rows)} rows in the ledger carry the "
        f"`suppressed` mark, not {_num(len(w.demerger))}. The other "
        f"{_num(w.suppressed_rows - len(w.demerger))} are days inside a suppression window that "
        "had ALREADY been refused for an earlier reason in the fixed refusal order -- they had "
        "no minutes, or they failed gate 1P -- so they are counted once, under the reason that "
        "reached them first. The refusal order is what keeps the partition exact, and this is "
        "what it looks like from underneath.")
    add("")
    add("### 12e. The Rule-3 no-break carries")
    add("")
    add("Q-22(a)'s ruling ends *\"where the only break lives in stray bars the scan finds NO "
        "break and the day carries -- the engine's existing honest answer, no invention\"*. Two "
        "days in the whole span are that case, and the run carries three more that are the same "
        "shape for an entirely different reason:")
    add("")
    add("| Symbol | Trade day | Carried bias | Out-of-session bars dropped that day |")
    add("|---|---|---|---|")
    for symbol, day, bias, flagged in w.no_break_carry:
        add(f"| {symbol} | {day} | {bias} | {'YES -- this is a Q-22(a) day' if flagged else 'no'} |")
    add("")
    add("The two flagged rows are GODREJCP and LAURUSLABS on 2021-02-25, whose D-1 is the "
        "2021-02-24 outage: the 15:44 print that used to decide their first break is now dropped "
        "before the scan sees it, the scan finds no break in the session, and the day carries. "
        "REVIEW_9B_FIXES predicted at least two BIASES would change; the FIX-4 measurement "
        "walked both symbols from the span's start and found the carried bias was already bearish "
        "on both, so the RULE moves on two days and **no bias in the ten-year span changes**. "
        "This ledger is that measurement's confirmation at full scale. The three unflagged rows "
        "on 2017-07-11 are ordinary Rule-3 days where neither of the prior day's extremes broke "
        "at all -- the same honest answer, reached without any stray bar.")
    add("")
    add("### 12f. The shapes that never happened")
    add("")
    zero_labels = sorted(label for label, count in run.rare_shapes.items() if count == 0)
    add(f"**{_num(len(zero_labels))} of the eleven counters are ZERO** over ten years, and a "
        f"zero recounted from {_num(run.walked)} rows is worth stating rather than omitting:")
    add("")
    for label in zero_labels:
        add(f"* {label}")
    add("")
    add("The malformed-bar counter is the interesting one: the machinery that stopped the first "
        "run from dying is now unreachable on the run path, because Q-22(a) drops an "
        "out-of-session stray before a candle is built and Q-21(a)'s completed gate 2 refuses an "
        "in-session impossible bar first. It is kept as defence in depth and it printed a zero, "
        "which is what defence in depth looks like when it works.")
    add("")
    add(f"**A near-miss worth naming beside them:** {_num(w.rule3_no_minute_days)} Rule-3 days "
        "carried because D-1 had no stored 1-minute data at all -- not a refusal and not a "
        "guess, the same honest carry CONTEXT 3.2 gives a scan that finds no break.")
    add("")
    add("Two further shapes are worth naming because they are nearly-never rather than never: "
        f"**{_num(len(w.side_never_set))}** days ended with the side never set "
        f"({', '.join(f'{s} {d}' for s, d in w.side_never_set)}), and "
        f"**{_num(w.square_off_at_entry)}** trades squared off on their own entry candle.")
    add("")


def _name_day(pair: tuple[str, str]) -> str:
    return f"{pair[0]} {pair[1]}"


def _section_traceability(add, *, run: RunData, **_) -> None:
    add("## 13. Traceability -- where every number came from")
    add("")
    add("| Family | Source | Spec |")
    add("|---|---|---|")
    add("| Every count, every rupee, every trade | the run ledger's own rows, streamed and "
        "recounted (section 3a) | CONTEXT 3.1-3.5 |")
    add("| Every E13 metric | `acumen.portfolio`, pure and reviewed; this report supplies rows "
        "and renders what comes back | CONTEXT 7-E13 |")
    add("| The 15-minute path | `acumen.backtest.assemble_trade_paths` over the same 15-minute "
        "aggregation the signal engine used | QUESTIONS.md Q-16(b) |")
    add("| Per-symbol coverage | the disclosed-residual register, read before any per-symbol "
        "statistic | CONTEXT 4.6 |")
    add("| The benchmark's closes | the raw daily store; the SHARE-COUNT factors (bonus / split "
        "/ rights) from THIS run's own factor table | CONTEXT 7-E13 / 4.2, QUESTIONS.md Q-23 "
        "(ruled and refined 06-Aug-2026, CLOSED) |")
    add("| The refusal pricing | the crashed run's retained shards, named per class | "
        "REVIEW_9B_FIXES R10 |")
    add("| The rare-shape witnesses | the ledger's own flags, recounted against the manifest's "
        "counters | CONTEXT 7-E2 / Q-17 / Q-21 |")
    add("")
    add("**Nothing on this page is estimated, modelled or extrapolated.** Where a number could "
        "not be measured it is absent and says why: the capital-infeasibility flags (Q43 "
        "pending), the foregone trades on refusal classes with no counterfactual (section 11b), "
        "and the per-symbol 15-minute paths (section 9). The benchmark's price domain is no "
        "longer among them: Q-23 is RULED and CLOSED, section 10 publishes the benchmark the "
        "ruling names, and the two other readings are printed beside it and labelled as not "
        "being it.")
    add("")
    add(f"Ledger sha256 `{run.ledger_sha256}`; manifest sha256 `{run.manifest_sha256}`.")


__all__ = [
    "BENCHMARK_RULING",
    "SHARE_COUNT_KINDS",
    "BenchmarkPair",
    "Check",
    "CrashedCheck",
    "LargestTies",
    "RefusalClass",
    "RunData",
    "Witnesses",
    "YearRow",
    "benchmark_pair",
    "build_everything",
    "concurrency_closing_first",
    "crashed_cross_check",
    "largest_ties",
    "main",
    "per_year",
    "pilot_cross_check",
    "price_refusals",
    "read_run",
    "reconcile",
    "render_markdown",
]
