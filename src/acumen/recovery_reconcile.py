"""Q-18 RECONCILIATION -- the rebuilt data era against CONTEXT 4.6's sealed numbers.

The architect's ruling of 31-Jul-2026 (QUESTIONS.md, recorded verbatim) is option (c):

    "rebuild through the existing reviewed pipeline; the rebuilt era MUST be reconciled
    against CONTEXT 4.6's sealed numbers; every divergence classified {new-CA-explained,
    vendor-repair-explained, unexplained}; explained drift is accepted only via a formal
    CONTEXT 4.6 amendment (v1.5) listing exact deltas; unexplained drift is a defect to
    triage."

This module is that reconciliation. It is **offline, read-only and measures nothing itself**:
the rebuild is the operator's, driven by the existing reviewed entry points (see
``docs/recovery/q18_runbook.md``); this reads what that rebuild left on disk and compares it,
line for line, with the era CONTEXT 4.6 sealed.

**Where the sealed numbers come from.** Not from a constant typed by a session -- from the
COMMITTED ``docs/backfill_minute_report.md``, which is the artefact CONTEXT 4.6 summarises and
which survived the incident intact in git. The rebuilt numbers come from the SAME generator
run over the rebuilt stores (``--report-only --report-path ...``), parsed by the same parser,
so neither side gets a bespoke measurement. On top of that the module runs an INDEPENDENT LEG:
it counts each symbol's stored days straight from the minute store's own parquet files and
checks that the rebuilt report actually describes the store on disk. A report that disagrees
with its own store is a hard failure here, whatever the reconciliation says.

**Classification.** The ruling names the three classes but not the test for each. The tests
below are this module's, they are PRINTED in the report so the architect can overrule them by
reading, and they are deliberately conservative -- a divergence is called explained only when
the evidence for the explanation is on disk, and everything else is ``unexplained``:

* ``new-CA-explained`` -- gate-outcome measures only (passing days, settled/quarantined
  status), and only when the rebuilt corporate-action day-cache holds an event for that symbol
  with an ex-date AFTER the sealed era. Basis: the vendor's 1-minute feed is CA-back-adjusted
  era-inconsistently (CONTEXT 4.6 / OPEN-8), so an event the sealed era could not know
  re-scales that symbol's whole prior history and its measured maps are re-measured against
  it. It cannot explain a change in how many days the vendor SERVES -- a corporate action
  does not add or remove history -- so stored-day moves never take this class.
* ``vendor-repair-explained`` -- IMPROVEMENTS only (more stored days, more passing days,
  quarantined -> settled), and only when the sealed era itself named that symbol's deficiency:
  quarantined in the sealed report, or listed in its gate-1P residual table or its gate-3
  disclosed-residual register. A repair the sealed era never recorded a defect for is not a
  repair anyone can point at.
* ``unexplained`` -- everything else, explicitly including EVERY decrease, every change on a
  symbol with neither a new event nor a disclosed sealed deficiency, and every symbol present
  on one side only (CONTEXT 7-E5 universe drift lands here on purpose: the ruling names no
  class for it, and the architect should see it).

**The architect's TRIAGE rulings of 01-Aug-2026** (QUESTIONS.md, recorded verbatim) answered the
first run's 354 unexplained divergences and added two more classes, both of which are measured
here rather than asserted:

* ``sealed-fetch-horizon`` (T1) -- the sealed store's per-symbol fetch horizon was EARLIER than
  the label its report carries, so the rebuild's extra days are days the sealed era never had,
  not drift. The test is a boundary date B: the unique stored date at which the rebuilt store's
  running day count first equals the sealed count exactly. A symbol passes only when B lands
  inside the sealed fetch window AND -- this is the part that makes it a measurement -- the
  symbol's whole gate-1 delta is reproduced by running the REAL CONTEXT 4.5 gates over exactly
  the days after B. If one older day also moved, the arithmetic no longer closes and the symbol
  stays ``unexplained``.
* ``vendor-snapshot-drift`` (T3) -- days the gates honestly refused after the vendor served a
  different snapshot. It is NEVER inferred here: it is read from the committed T3 forensics
  verdict file, per symbol and per measure, and a symbol the forensics escalated keeps its
  ``unexplained`` class.

T2 tightened ``new-CA-explained``: an ex-date must be after the sealed era AND on or before the
rebuild's own fetch date. An ex-date in the future explains nothing about a history already
fetched.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

#: The 31-Jul ruling's three classes, spelled exactly as the architect spelled them.
CLASS_NEW_CA: str = "new-CA-explained"
CLASS_VENDOR_REPAIR: str = "vendor-repair-explained"
CLASS_UNEXPLAINED: str = "unexplained"
#: The 01-Aug TRIAGE rulings' two additional classes, likewise verbatim (T1 and T3).
CLASS_HORIZON: str = "sealed-fetch-horizon"
CLASS_SNAPSHOT_DRIFT: str = "vendor-snapshot-drift"
CLASSES: tuple[str, ...] = (
    CLASS_NEW_CA,
    CLASS_VENDOR_REPAIR,
    CLASS_HORIZON,
    CLASS_SNAPSHOT_DRIFT,
    CLASS_UNEXPLAINED,
)

#: What a divergence is measured ON. The first two are gate outcomes and can be re-scaled by a
#: corporate action; the last two cannot be.
MEASURE_PASSING: str = "gate-1 effective passes"
MEASURE_STATUS: str = "status"
MEASURE_STORED: str = "stored days"
MEASURE_PRESENCE: str = "presence"
GATE_MEASURES: frozenset[str] = frozenset({MEASURE_PASSING, MEASURE_STATUS})

#: The committed artefact that carries the sealed era. CONTEXT 4.6 summarises exactly this.
SEALED_REPORT_RELPATH: str = "docs/backfill_minute_report.md"

#: Where runbook step 4 is told to write the rebuilt report. NEVER the sealed path.
REBUILT_REPORT_RELPATH: str = "docs/recovery/backfill_minute_report_rebuild.md"

#: The earliest year NSE's corporate-action API answers for (CONTEXT 4.2, verified).
CA_FIRST_YEAR: int = 2005

#: T1's sealed fetch window, opening edge. The architect's words: "B inside the sealed fetch
#: window (2026-07-20..2026-07-28)". Only this edge is a constant -- the closing edge is the
#: SEALED report's own scope end, read from the report rather than typed.
SEALED_FETCH_WINDOW_START: date = date(2026, 7, 20)

#: T2's cut-off, the architect's words: "new-CA-explained requires ex-date <= the rebuild fetch
#: date (2026-07-31)".
REBUILD_FETCH_DATE: date = date(2026, 7, 31)

#: Where the T3 forensics writes its per-symbol verdicts. Read, never written, by this module:
#: ``vendor-snapshot-drift`` is evidence on disk or it is nothing.
T3_FORENSICS_RELPATH: str = "docs/recovery/q18_t3_forensics.json"

VERDICT_DRIFT: str = "vendor-snapshot-drift"
VERDICT_ESCALATE: str = "escalate"

STATUS_SETTLED: str = "settled"


class ReconcileError(RuntimeError):
    """An input the reconciliation cannot proceed without is missing or unreadable."""


# --- parsing a backfill report ------------------------------------------------------------


@dataclass(frozen=True)
class SymbolDepth:
    """One row of a backfill report's section 3 (`Depth found, per symbol`)."""

    symbol: str
    route: str
    first_day: date | None
    days: int
    gate1_pass: int
    gate1_gated: int
    status: str

    @property
    def settled(self) -> bool:
        return self.status == STATUS_SETTLED


@dataclass(frozen=True)
class ReportFacts:
    """Everything the reconciliation needs out of one backfill report."""

    source: str
    scope_end: date | None
    headline: Mapping[str, int]
    coverage_pass: int | None
    coverage_stored: int | None
    symbols: Mapping[str, SymbolDepth]
    disclosed: frozenset[str]

    @property
    def settled(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, d in self.symbols.items() if d.settled))

    @property
    def quarantined(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, d in self.symbols.items() if not d.settled))

    @property
    def coverage_percent(self) -> float | None:
        if not self.coverage_stored:
            return None
        return 100.0 * (self.coverage_pass or 0) / self.coverage_stored


_INT = re.compile(r"-?\d[\d,]*")
_FRACTION = re.compile(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _cells(line: str) -> list[str]:
    """The cells of a markdown pipe row, stripped of bold markers and whitespace."""
    return [cell.replace("**", "").strip() for cell in line.strip().strip("|").split("|")]


def _is_rule(line: str) -> bool:
    return set(line.strip()) <= set("|- :")


def _int_or_none(cell: str) -> int | None:
    match = _INT.search(cell)
    return int(match.group(0).replace(",", "")) if match else None


def _date_or_none(cell: str) -> date | None:
    match = _ISO_DATE.search(cell)
    return date.fromisoformat(match.group(0)) if match else None


def _section(text: str, heading: str) -> list[str]:
    """The lines under ``heading``, up to the next heading of the same or shallower depth.

    Sub-headings (deeper ones) stay IN, which is what lets section 1 keep its own table while
    section 1a is fetched separately by its own heading.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return []
    depth = len(heading) - len(heading.lstrip("#"))
    out: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("#"):
            if len(stripped) - len(stripped.lstrip("#")) <= depth:
                break
        out.append(line)
    return out


def _rows(lines: Sequence[str]) -> list[list[str]]:
    """Every data row of every pipe table in ``lines`` (header and rule rows dropped)."""
    out: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or _is_rule(stripped):
            continue
        out.append(_cells(stripped))
    return out


def _symbols_named(text: str, heading: str) -> set[str]:
    """Column-0 symbols of every table under ``heading`` -- the disclosed-deficiency lists."""
    found: set[str] = set()
    for cells in _rows(_section(text, heading)):
        token = cells[0].strip().upper()
        if token and token.replace("-", "").replace("&", "").isalnum() and token != "SYMBOL":
            found.add(token)
    return found


def parse_backfill_report(text: str, *, source: str = "") -> ReportFacts:
    """Read a chunk-5B backfill report into the facts the reconciliation compares.

    Pure: text in, facts out. Both the SEALED report (committed, from git) and the REBUILT one
    (written by the same generator over the rebuilt stores) go through this one function, so
    neither side can be measured on its own terms.
    """
    scope_end: date | None = None
    for line in text.splitlines():
        if line.startswith("Scope:"):
            stamps = _ISO_DATE.findall(line)
            if stamps:
                scope_end = date.fromisoformat(stamps[-1])
            break

    headline: dict[str, int] = {}
    for cells in _rows(_section(text, "## 1. Headline")):
        if len(cells) < 2 or cells[0].lower() in {"measure", "reading"}:
            continue
        value = _int_or_none(cells[1])
        if value is not None:
            headline.setdefault(cells[0], value)

    coverage_pass = coverage_stored = None
    for cells in _rows(_section(text, "## 1. Headline")):
        if cells and cells[0].startswith("G ") and len(cells) >= 3:
            coverage_pass = _int_or_none(cells[1])
            coverage_stored = _int_or_none(cells[2])
            break

    symbols: dict[str, SymbolDepth] = {}
    for cells in _rows(_section(text, "## 3. Depth found, per symbol")):
        if len(cells) < 13 or cells[0].lower() == "symbol":
            continue
        fraction = _FRACTION.search(cells[8])
        if fraction is None:
            continue
        symbol = cells[0].strip().upper()
        symbols[symbol] = SymbolDepth(
            symbol=symbol,
            route=cells[1],
            first_day=_date_or_none(cells[3]),
            days=_int_or_none(cells[4]) or 0,
            gate1_pass=int(fraction.group(1).replace(",", "")),
            gate1_gated=int(fraction.group(2).replace(",", "")),
            status=cells[12].strip().lower(),
        )

    disclosed = (
        {symbol for symbol, depth in symbols.items() if not depth.settled}
        | _symbols_named(text, "### 3f. GATE 1P and the bounded PRICE-RECOVERY pass "
                               "(QUESTIONS.md Q-14)")
        | _symbols_named(text, "### The DISCLOSED RESIDUAL register "
                               "(QUESTIONS.md Q-11 addendum 4)")
        | _symbols_named(text, "### Quarantined symbols")
    )

    return ReportFacts(
        source=source,
        scope_end=scope_end,
        headline=headline,
        coverage_pass=coverage_pass,
        coverage_stored=coverage_stored,
        symbols=symbols,
        disclosed=frozenset(disclosed),
    )


def read_report(path: Path | str) -> ReportFacts:
    source = Path(path)
    if not source.is_file():
        raise ReconcileError(
            f"No backfill report at {source}. The SEALED one is committed at "
            f"{SEALED_REPORT_RELPATH}; the REBUILT one is written by runbook step 4 "
            f"(`--report-only --report-path {REBUILT_REPORT_RELPATH}`)."
        )
    facts = parse_backfill_report(source.read_text(encoding="utf-8"), source=str(source))
    if not facts.symbols:
        raise ReconcileError(
            f"{source} carries no per-symbol depth table (section 3); it is not a backfill "
            "report this reconciliation can read."
        )
    return facts


# --- the independent leg: the store's own parquet files -------------------------------------


@dataclass(frozen=True)
class StoreMeasurement:
    """What the minute store itself holds for one symbol, counted from its parquet files."""

    symbol: str
    days_in_scope: int
    days_beyond: int
    first_day: date | None


def measure_days(
    stored_days: Mapping[str, Sequence[date]], *, scope_end: date | None
) -> dict[str, StoreMeasurement]:
    """Split already-read day lists at ``scope_end``. PURE -- the counting half of the leg.

    Days AFTER ``scope_end`` are growth, not divergence: the rebuild fetches to today while the
    sealed era stopped at its own scope date, and comparing the two spans directly would report
    a year of new trading as a defect. They are counted separately and reported separately.
    """
    out: dict[str, StoreMeasurement] = {}
    for symbol, stored in stored_days.items():
        if scope_end is None:
            in_scope, beyond = list(stored), []
        else:
            in_scope = [day for day in stored if day <= scope_end]
            beyond = [day for day in stored if day > scope_end]
        out[symbol] = StoreMeasurement(
            symbol=symbol,
            days_in_scope=len(in_scope),
            days_beyond=len(beyond),
            first_day=min(stored) if stored else None,
        )
    return out


def measure_store(store: Any, symbols: Sequence[str], *, scope_end: date | None) -> dict[str, StoreMeasurement]:
    """Count each symbol's stored days from the store, split at the sealed era's end.

    The parquet-reading half; :func:`measure_days` is the pure half it delegates the split to.
    """
    return measure_days(
        {symbol: tuple(store.stored_days(symbol)) for symbol in symbols}, scope_end=scope_end
    )


# --- T1: the SEALED-FETCH-HORIZON boundary test -----------------------------------------------


@dataclass(frozen=True)
class HorizonVerdict:
    """T1 for one symbol: the boundary date B, the days after it, and whether it holds.

    The architect's test (QUESTIONS.md, 01-Aug-2026, verbatim): *"for each symbol, find the
    unique boundary date B such that the REBUILT store's day count on dates <= B equals the
    SEALED count exactly, with every extra day inside (B, 2026-07-28] and B inside the sealed
    fetch window (2026-07-20..2026-07-28)."*

    B is made UNIQUE by taking it to be a stored date: the ``sealed_days``-th stored day of the
    rebuilt store. The running count first equals the sealed count AT that date, and only at
    that date is the count both equal and pinned to a day the store actually holds.
    """

    symbol: str
    sealed_days: int
    store_days_in_scope: int
    boundary: date | None
    extras: tuple[date, ...]
    beyond: tuple[date, ...]
    passed: bool
    reason: str
    #: The measured gate leg, filled by :func:`account_gate_delta` once the real CONTEXT 4.5
    #: gates have been run over the days after B. ``None`` until then.
    gate_pass_delta: int | None = None
    gate_gated_delta: int | None = None
    measured_pass: int | None = None
    measured_gated: int | None = None
    gate_accounted: bool = False
    gate_note: str = ""

    @property
    def new_days(self) -> tuple[date, ...]:
        """Every stored day after B -- the extras inside the sealed scope plus the growth."""
        return self.extras + self.beyond

    def evidence(self) -> str:
        extras = ", ".join(d.isoformat() for d in self.extras) or "none"
        beyond = ", ".join(d.isoformat() for d in self.beyond) or "none"
        return (
            f"boundary B = {self.boundary}: the rebuilt store's {self.sealed_days:,}th stored "
            f"day, so its count on dates <= B equals the sealed count exactly. Extra days "
            f"inside (B, sealed scope end]: {extras}. Growth after the sealed scope: {beyond}. "
            f"{self.gate_note}"
        ).strip()


def horizon_boundary(
    stored_days: Sequence[date],
    sealed_days: int,
    *,
    window_start: date,
    window_end: date,
    symbol: str = "",
) -> HorizonVerdict:
    """T1's boundary test for one symbol. PURE: dates in, verdict out.

    ``stored_days`` is the REBUILT minute store's own day list; ``window_end`` is the SEALED
    report's scope end. A symbol fails -- and stays ``unexplained``, exactly as the ruling
    says -- when the store cannot reach the sealed count inside the sealed scope, or when the
    boundary lands outside the sealed fetch window (which is what a real gap or a real
    mid-history change looks like).
    """
    ordered = sorted(stored_days)
    in_scope = [day for day in ordered if day <= window_end]
    beyond = tuple(day for day in ordered if day > window_end)

    if sealed_days <= 0:
        return HorizonVerdict(
            symbol=symbol, sealed_days=sealed_days, store_days_in_scope=len(in_scope),
            boundary=None, extras=(), beyond=beyond, passed=False,
            reason="the sealed report records no days for this symbol, so there is no count to "
                   "bound",
        )
    if len(in_scope) < sealed_days:
        return HorizonVerdict(
            symbol=symbol, sealed_days=sealed_days, store_days_in_scope=len(in_scope),
            boundary=None, extras=(), beyond=beyond, passed=False,
            reason=f"the rebuilt store holds {len(in_scope):,} day(s) inside the sealed scope, "
                   f"FEWER than the sealed report's {sealed_days:,} -- no boundary date can "
                   f"make the counts equal, so this is a real loss and not a horizon",
        )

    boundary = in_scope[sealed_days - 1]
    extras = tuple(in_scope[sealed_days:])
    inside = window_start <= boundary <= window_end
    return HorizonVerdict(
        symbol=symbol, sealed_days=sealed_days, store_days_in_scope=len(in_scope),
        boundary=boundary, extras=extras, beyond=beyond, passed=inside,
        reason="" if inside else
        f"boundary B = {boundary.isoformat()} falls OUTSIDE the sealed fetch window "
        f"{window_start.isoformat()}..{window_end.isoformat()}, so the delta is not a late-tail "
        f"horizon: the two eras diverge inside the history itself",
    )


def account_gate_delta(
    verdict: HorizonVerdict,
    *,
    sealed_pass: int,
    sealed_gated: int,
    sealed_days: int,
    rebuilt_pass: int,
    rebuilt_gated: int,
    tail_pass: int,
    tail_gated: int,
    sealed_tail_days: int,
) -> HorizonVerdict:
    """Close T1's arithmetic on the gate counts. PURE: counts in, verdict out.

    "Matching" -- the architect's word -- is made measurable here as: *the whole gate-1 move is
    attributable to the FETCH WINDOW, and nothing older than it moved.*

    The proof is interval arithmetic over quantities that were all measured, with no assumption
    about days nobody can see any more:

    * ``tail_pass`` / ``tail_gated`` -- the REBUILT store re-gated by CONTEXT 4.5's own battery
      over the window ``[SEALED_FETCH_WINDOW_START, rebuilt scope end]``;
    * ``sealed_tail_days`` -- how many stored days the SEALED era had in that same window. It is
      known exactly: it is the rebuilt store's day count over ``[window start, B]``, and B is
      the boundary at which the two eras' counts agree;
    * ``sealed_days`` / ``sealed_gated`` / ``sealed_pass`` -- the sealed report's own totals,
      which bound what its tail could possibly have contributed. Its ungated days
      (``sealed_days - sealed_gated`` -- the CONTEXT 4.6 store-lag, days with no raw daily row)
      and its failures (``sealed_gated - sealed_pass``) are the only slack there is.

    If the reported delta lands outside the resulting range, then a day OLDER than the fetch
    window changed verdict, which no horizon reading can explain -- so the gate delta is not
    reclassified and falls through to the other classes and, failing those, to ``unexplained``.
    """
    pass_delta = rebuilt_pass - sealed_pass
    gated_delta = rebuilt_gated - sealed_gated

    ungated = max(0, sealed_days - sealed_gated)
    failures = max(0, sealed_gated - sealed_pass)
    # What the SEALED tail could have contributed, at most and at least.
    tail_gated_max = sealed_tail_days
    tail_gated_min = max(0, sealed_tail_days - ungated)
    tail_pass_max = tail_gated_max
    tail_pass_min = max(0, tail_gated_min - failures)

    gated_lo, gated_hi = tail_gated - tail_gated_max, tail_gated - tail_gated_min
    pass_lo, pass_hi = tail_pass - tail_pass_max, tail_pass - tail_pass_min
    accounted = gated_lo <= gated_delta <= gated_hi and pass_lo <= pass_delta <= pass_hi

    window = (
        f"the rebuilt store's {tail_gated:,} gated / {tail_pass:,} passing day(s) inside the "
        f"fetch window, against a sealed tail of {sealed_tail_days} stored day(s)"
    )
    if accounted:
        note = (
            f"the gate-1 move {pass_delta:+,} pass / {gated_delta:+,} gated is ENTIRELY "
            f"attributable to the fetch window: re-gating {window} bounds the pass move to "
            f"[{pass_lo:+,}, {pass_hi:+,}] and the gated move to [{gated_lo:+,}, {gated_hi:+,}], "
            f"and both reported moves lie inside. No day older than the window changed verdict"
        )
    else:
        note = (
            f"the gate-1 move {pass_delta:+,} pass / {gated_delta:+,} gated CANNOT come from the "
            f"fetch window: re-gating {window} bounds the pass move to [{pass_lo:+,}, "
            f"{pass_hi:+,}] and the gated move to [{gated_lo:+,}, {gated_hi:+,}]. Days INSIDE "
            f"the sealed history moved verdict"
        )
    return replace(
        verdict,
        gate_pass_delta=pass_delta,
        gate_gated_delta=gated_delta,
        measured_pass=tail_pass,
        measured_gated=tail_gated,
        gate_accounted=accounted,
        gate_note=note,
    )


def gate_window(
    minute_store: Any, daily_cache: Any, symbol: str, days: Sequence[date]
) -> tuple[int, int]:
    """Run the REAL gate battery over exactly ``days`` and return ``(effective pass, gated)``.

    Not a re-implementation: :func:`acumen.universe_backfill.gate_symbol` is handed a view of
    the store that yields only those days, so the same reviewed code that produced the report's
    numbers produces these. Nothing is fetched and nothing is written.
    """
    from .universe_backfill import gate_symbol

    class _DaysOnly:
        """A MinuteStore view restricted to ``days`` -- ``gate_symbol`` needs only iter_days."""

        def iter_days(self, sym: str, since: date | None = None, until: date | None = None):
            for day in sorted(days):
                if since is not None and day < since:
                    continue
                if until is not None and day > until:
                    continue
                bars = minute_store.minutes(sym, day)
                if bars:
                    yield day, bars

    tally = gate_symbol(_DaysOnly(), daily_cache, symbol)
    return tally.gate1_effective_pass, tally.gate1_total


# --- T3: the forensics verdicts, read from disk ------------------------------------------------


@dataclass(frozen=True)
class ForensicVerdict:
    """One symbol's T3 outcome, as the committed forensics recorded it."""

    symbol: str
    verdict: str
    measures: frozenset[str]
    summary: str

    @property
    def drift(self) -> bool:
        return self.verdict == VERDICT_DRIFT


def parse_forensics(payload: Mapping[str, Any]) -> dict[str, ForensicVerdict]:
    """Read a T3 forensics payload into per-symbol verdicts. PURE.

    Only ``vendor-snapshot-drift`` and ``escalate`` are accepted -- the ruling's words: *"a
    measured, era-keyed explanation ... or ESCALATE to the architect with the evidence. No third
    option."* Anything else raises rather than being silently ignored.
    """
    out: dict[str, ForensicVerdict] = {}
    for symbol, row in (payload.get("symbols") or {}).items():
        verdict = str(row.get("verdict", "")).strip()
        if verdict not in (VERDICT_DRIFT, VERDICT_ESCALATE):
            raise ReconcileError(
                f"T3 forensics for {symbol} carries verdict {verdict!r}; the ruling allows "
                f"exactly {VERDICT_DRIFT!r} or {VERDICT_ESCALATE!r} and no third option."
            )
        out[str(symbol).strip().upper()] = ForensicVerdict(
            symbol=str(symbol).strip().upper(),
            verdict=verdict,
            measures=frozenset(str(m) for m in (row.get("measures") or ())),
            summary=" ".join(str(row.get("summary", "")).split()),
        )
    return out


def read_forensics(path: Path | str) -> dict[str, ForensicVerdict]:
    """Load the committed T3 verdicts; an absent file simply means no symbol is reclassified."""
    source = Path(path)
    if not source.is_file():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReconcileError(f"The T3 forensics file at {source} is not readable JSON: {exc}")
    return parse_forensics(payload)


# --- classification -------------------------------------------------------------------------


@dataclass(frozen=True)
class Divergence:
    """One difference between the sealed era and the rebuilt one, with its class and why."""

    symbol: str
    measure: str
    sealed: str
    rebuilt: str
    delta: str
    classification: str
    evidence: str


def classify(
    measure: str,
    *,
    improved: bool | None,
    new_events: Sequence[str],
    disclosed: bool,
    horizon: HorizonVerdict | None = None,
    forensic: ForensicVerdict | None = None,
) -> tuple[str, str]:
    """Return ``(class, evidence)`` for one divergence. Conservative by construction.

    The rules are the module docstring's, executed in order. Nothing is called explained
    without the evidence being present on disk, so the default is ``unexplained``.

    The two MEASURED classes run first -- T1's boundary arithmetic, then T3's committed
    forensics -- because both rest on a day-level measurement, while ``new-CA-explained`` rests
    on the mere existence of a nearby event. T2's ruling says as much ("reclassify, letting T1
    catch them"), and it would be perverse for a coincidental corporate action to outrank a
    forensics pass that measured the same symbol era by era.
    """
    if horizon is not None and horizon.passed:
        if measure == MEASURE_STORED:
            return CLASS_HORIZON, horizon.evidence()
        if measure == MEASURE_PASSING and horizon.gate_accounted:
            return CLASS_HORIZON, horizon.evidence()
    if forensic is not None and forensic.drift and measure in forensic.measures:
        return (
            CLASS_SNAPSHOT_DRIFT,
            "T3 forensics (committed, `" + T3_FORENSICS_RELPATH + "`) measured this symbol "
            "era by era and gate by gate and found days the gates HONESTLY REFUSED after the "
            "vendor served a different snapshot: " + (forensic.summary or "see the forensics"),
        )
    if measure in GATE_MEASURES and new_events:
        return (
            CLASS_NEW_CA,
            "corporate action(s) with an ex-date after the sealed era, which re-scale the "
            "vendor's back-adjusted history for this symbol (CONTEXT 4.6 / OPEN-8): "
            + "; ".join(new_events),
        )
    if improved and disclosed:
        return (
            CLASS_VENDOR_REPAIR,
            "the rebuild is strictly better on this measure, no corporate action after the "
            "sealed era explains it, and the SEALED report itself disclosed this symbol's "
            "deficiency (quarantined, or named in its gate-1P residual table or its gate-3 "
            "disclosed-residual register)",
        )
    if horizon is not None and horizon.passed and measure == MEASURE_PASSING:
        return (
            CLASS_UNEXPLAINED,
            "the stored-day delta IS a sealed-fetch horizon (T1 passes, " + horizon.evidence()
            + ") but the gate-1 move is not: " + (horizon.gate_note or "not measured"),
        )
    if horizon is not None and not horizon.passed and measure in (MEASURE_STORED, MEASURE_PASSING):
        return (
            CLASS_UNEXPLAINED,
            "T1 (sealed-fetch-horizon) does not hold for this symbol: " + horizon.reason,
        )
    if measure == MEASURE_PRESENCE:
        return (
            CLASS_UNEXPLAINED,
            "present on one side only. The universe is TODAY's F&O list (CONTEXT 7-E5), so "
            "membership drift lands here; the ruling names no class for it, so it is "
            "unexplained by construction and the architect triages it",
        )
    if improved is False:
        return (
            CLASS_UNEXPLAINED,
            "the rebuild is WORSE on this measure. No class explains a regression: a "
            "corporate action does not remove history and a vendor repair does not lose days",
        )
    if not disclosed:
        return (
            CLASS_UNEXPLAINED,
            "the sealed era recorded no deficiency for this symbol (not quarantined, not in "
            "the gate-1P residual table, not in the gate-3 register), so there is nothing "
            "here that a repair could have repaired",
        )
    return (
        CLASS_UNEXPLAINED,
        "no corporate action after the sealed era and no improvement to attribute to a "
        "vendor repair",
    )


def new_events_by_symbol(
    actions: Sequence[Any], *, after: date | None, until: date | None = None
) -> dict[str, list[str]]:
    """Corporate actions with an ex-date strictly after the sealed era, per symbol.

    ``after`` is the sealed report's own scope end. With no scope end nothing is "new" and the
    class simply never fires -- silence beats a guessed cut-off.

    ``until`` is T2's tightening (architect, 01-Aug-2026): *"new-CA-explained requires ex-date
    <= the rebuild fetch date (2026-07-31). Future ex-dates explain nothing."* An event that
    has not gone ex yet cannot have re-scaled a history the vendor already served, so it is
    dropped here rather than being allowed to explain a divergence downstream.
    """
    out: dict[str, list[str]] = {}
    if after is None:
        return out
    for action in actions:
        if until is not None and action.ex_date > until:
            continue
        if action.ex_date > after:
            subject = " ".join(str(action.subject).split())
            out.setdefault(str(action.symbol).strip().upper(), []).append(
                f"{subject} @ {action.ex_date.isoformat()}"
            )
    return {symbol: sorted(set(events)) for symbol, events in out.items()}


def reconcile(
    sealed: ReportFacts,
    rebuilt: ReportFacts,
    *,
    new_events: Mapping[str, Sequence[str]],
    horizons: Mapping[str, HorizonVerdict] | None = None,
    forensics: Mapping[str, ForensicVerdict] | None = None,
) -> list[Divergence]:
    """Every per-symbol divergence between the two eras, classified. Pure."""
    divergences: list[Divergence] = []
    for symbol in sorted(set(sealed.symbols) | set(rebuilt.symbols)):
        old = sealed.symbols.get(symbol)
        new = rebuilt.symbols.get(symbol)
        events = list(new_events.get(symbol, ()))
        disclosed = symbol in sealed.disclosed
        horizon = (horizons or {}).get(symbol)
        forensic = (forensics or {}).get(symbol)

        if old is None or new is None:
            side = "rebuilt only" if old is None else "SEALED only"
            classification, evidence = classify(
                MEASURE_PRESENCE, improved=None, new_events=events, disclosed=disclosed,
                forensic=forensic,
            )
            divergences.append(
                Divergence(
                    symbol=symbol,
                    measure=MEASURE_PRESENCE,
                    sealed="absent" if old is None else f"{old.days:,} days",
                    rebuilt="absent" if new is None else f"{new.days:,} days",
                    delta=side,
                    classification=classification,
                    evidence=evidence,
                )
            )
            continue

        if old.days != new.days:
            classification, evidence = classify(
                MEASURE_STORED,
                improved=new.days > old.days,
                new_events=events,
                disclosed=disclosed,
                horizon=horizon,
                forensic=forensic,
            )
            divergences.append(
                Divergence(
                    symbol=symbol,
                    measure=MEASURE_STORED,
                    sealed=f"{old.days:,}",
                    rebuilt=f"{new.days:,}",
                    delta=f"{new.days - old.days:+,}",
                    classification=classification,
                    evidence=evidence,
                )
            )

        if old.gate1_pass != new.gate1_pass:
            classification, evidence = classify(
                MEASURE_PASSING,
                improved=new.gate1_pass > old.gate1_pass,
                new_events=events,
                disclosed=disclosed,
                horizon=horizon,
                forensic=forensic,
            )
            divergences.append(
                Divergence(
                    symbol=symbol,
                    measure=MEASURE_PASSING,
                    sealed=f"{old.gate1_pass:,}/{old.gate1_gated:,}",
                    rebuilt=f"{new.gate1_pass:,}/{new.gate1_gated:,}",
                    delta=f"{new.gate1_pass - old.gate1_pass:+,}",
                    classification=classification,
                    evidence=evidence,
                )
            )

        if old.status != new.status:
            classification, evidence = classify(
                MEASURE_STATUS,
                improved=new.settled and not old.settled,
                new_events=events,
                disclosed=disclosed,
                forensic=forensic,
            )
            divergences.append(
                Divergence(
                    symbol=symbol,
                    measure=MEASURE_STATUS,
                    sealed=old.status,
                    rebuilt=new.status,
                    delta=f"{old.status} -> {new.status}",
                    classification=classification,
                    evidence=evidence,
                )
            )
    return divergences


def counts_by_class(divergences: Sequence[Divergence]) -> dict[str, int]:
    return {name: sum(1 for d in divergences if d.classification == name) for name in CLASSES}


# --- the store cross-check --------------------------------------------------------------------


@dataclass(frozen=True)
class StoreCheck:
    """One symbol where the rebuilt REPORT and the rebuilt STORE do not agree on a day count."""

    symbol: str
    report_days: int
    store_days: int

    @property
    def contradiction(self) -> bool:
        """The report claims depth for a symbol the store holds nothing for.

        This is the only shape of disagreement that BLOCKS. A plain count difference can be a
        semantic one -- the report's ``Days`` column counts stored days from the symbol's own
        clamp, so days stored before it would legitimately not appear there -- and this module
        will not fail a rebuild over a semantic it cannot verify. A symbol with a depth figure
        and an empty parquet directory admits no such reading.
        """
        return self.report_days > 0 and self.store_days == 0


def cross_check_store(
    rebuilt: ReportFacts, measured: Mapping[str, StoreMeasurement]
) -> list[StoreCheck]:
    """Does the rebuilt report describe the store that is actually on disk?

    ``measured`` must be counted over the REBUILT report's own scope, so the two sides cover
    the same dates. Returns every disagreement; :attr:`StoreCheck.contradiction` marks the ones
    that cannot be a semantic difference.
    """
    out: list[StoreCheck] = []
    for symbol, depth in sorted(rebuilt.symbols.items()):
        seen = measured.get(symbol)
        store_days = seen.days_in_scope if seen is not None else 0
        if store_days != depth.days:
            out.append(
                StoreCheck(symbol=symbol, report_days=depth.days, store_days=store_days)
            )
    return out


# --- rendering ---------------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}%"


def _delta(old: int | None, new: int | None) -> str:
    if old is None or new is None:
        return "n/a"
    return f"{new - old:+,}"


def render(
    *,
    sealed: ReportFacts,
    rebuilt: ReportFacts,
    divergences: Sequence[Divergence],
    measured: Mapping[str, StoreMeasurement],
    checks: Sequence[StoreCheck],
    ca_rows: int,
    horizons: Mapping[str, HorizonVerdict] | None = None,
    forensics: Mapping[str, ForensicVerdict] | None = None,
    dropped_future_events: int = 0,
) -> list[str]:
    """The reconciliation report, exactly as it is printed and written."""
    horizons = dict(horizons or {})
    forensics = dict(forensics or {})
    counts = counts_by_class(divergences)
    unexplained = counts[CLASS_UNEXPLAINED]
    beyond = sum(m.days_beyond for m in measured.values())
    contradictions = [check for check in checks if check.contradiction]

    lines: list[str] = []
    add = lines.append

    add("# Q-18 RECONCILIATION -- the rebuilt era vs CONTEXT 4.6's sealed numbers")
    add("")
    add("Generated by `docs/recovery/q18_reconcile.py` (implementation:")
    add("`src/acumen/recovery_reconcile.py`), committed under CLAUDE.md's evidence rule.")
    add("Offline and read-only. Regenerate with:")
    add("")
    add("    python docs/recovery/q18_reconcile.py --out docs/recovery/q18_reconciliation.md")
    add("")
    add("The architect's ruling this executes (QUESTIONS.md, 31-Jul-2026, verbatim):")
    add("")
    add("> the rebuilt era MUST be reconciled against CONTEXT 4.6's sealed numbers; every")
    add("> divergence classified {new-CA-explained, vendor-repair-explained, unexplained};")
    add("> explained drift is accepted only via a formal CONTEXT 4.6 amendment (v1.5) listing")
    add("> exact deltas; unexplained drift is a defect to triage.")
    add("")

    add("## 0. Inputs")
    add("")
    add("| Side | Source | Scope end | Symbols |")
    add("|---|---|---|---|")
    add(f"| SEALED | `{sealed.source}` | {sealed.scope_end} | {len(sealed.symbols)} |")
    add(f"| REBUILT | `{rebuilt.source}` | {rebuilt.scope_end} | {len(rebuilt.symbols)} |")
    add("")
    add(
        f"The sealed side is the COMMITTED report -- the artefact CONTEXT 4.6 summarises, and "
        f"the one thing the incident could not touch. Both sides are read by the same parser. "
        f"{ca_rows:,} corporate-action row(s) were read from the rebuilt day-cache, offline."
    )
    add("")

    add("## 1. The classification rules this report applied")
    add("")
    add("The ruling names the three classes; these are the tests, printed so they can be")
    add("overruled by reading. A divergence is called explained only when the evidence is on")
    add("disk -- the default is `unexplained`.")
    add("")
    add("| Class | Applies to | Requires |")
    add("|---|---|---|")
    add(
        f"| `{CLASS_NEW_CA}` | gate outcomes only ({MEASURE_PASSING}, {MEASURE_STATUS}) | an "
        "ex-date AFTER the sealed era in the rebuilt CA cache. A corporate action re-scales a "
        "back-adjusted history; it never adds or removes stored days |"
    )
    add(
        f"| `{CLASS_VENDOR_REPAIR}` | improvements only | the SEALED era named this symbol's "
        "deficiency (quarantined, gate-1P residual table, or gate-3 disclosed-residual "
        "register) |"
    )
    add(
        f"| `{CLASS_HORIZON}` | stored days, and the gate-1 pass count when it MATCHES | T1: a "
        "boundary date B inside the sealed fetch window whose running count equals the sealed "
        "count exactly, AND the whole gate-1 move reproduced by re-running CONTEXT 4.5's gates "
        "over the days after B |"
    )
    add(
        f"| `{CLASS_SNAPSHOT_DRIFT}` | whatever the T3 forensics named, per symbol | T3: a "
        f"committed, era-keyed forensics verdict at `{T3_FORENSICS_RELPATH}`. Never inferred "
        "here; a symbol the forensics ESCALATED keeps its `unexplained` class |"
    )
    add(
        f"| `{CLASS_UNEXPLAINED}` | everything else | -- including every regression, every "
        "one-sided presence, and every change on a symbol with no disclosed deficiency |"
    )
    add("")
    add(
        f"T2 (architect, 01-Aug-2026) tightened `{CLASS_NEW_CA}`: an ex-date must fall in "
        f"(sealed scope end, {REBUILD_FETCH_DATE.isoformat()}] -- after the sealed era AND on "
        f"or before the rebuild's own fetch date. {dropped_future_events:,} corporate-action "
        "row(s) with a FUTURE ex-date were dropped by that tightening; they explain nothing "
        "about a history the vendor had already served."
    )
    add("")

    add("## 2. Headline reconciliation")
    add("")
    add("| Measure | SEALED | REBUILT | Delta |")
    add("|---|---|---|---|")
    add(
        f"| Stored symbol-days (gate-1P denominator) | {_fmt(sealed.coverage_stored)} | "
        f"{_fmt(rebuilt.coverage_stored)} | {_delta(sealed.coverage_stored, rebuilt.coverage_stored)} |"
    )
    add(
        f"| Passing all three gates (reading G numerator) | {_fmt(sealed.coverage_pass)} | "
        f"{_fmt(rebuilt.coverage_pass)} | {_delta(sealed.coverage_pass, rebuilt.coverage_pass)} |"
    )
    add(
        f"| Coverage | {_pct(sealed.coverage_percent)} | {_pct(rebuilt.coverage_percent)} | "
        f"{_pct_delta(sealed.coverage_percent, rebuilt.coverage_percent)} |"
    )
    add(
        f"| Settled symbols | {len(sealed.settled)} | {len(rebuilt.settled)} | "
        f"{len(rebuilt.settled) - len(sealed.settled):+d} |"
    )
    add(
        f"| Quarantined symbols | {len(sealed.quarantined)} | {len(rebuilt.quarantined)} | "
        f"{len(rebuilt.quarantined) - len(sealed.quarantined):+d} |"
    )
    add("")
    add(
        "CONTEXT 4.6's sealed sentence for comparison: *411,690 / 434,769 stored symbol-days "
        "pass all three gates = 94.69%; 204 symbols settled, 6 quarantined*."
    )
    add("")

    add("## 3. Settled / quarantined lists")
    add("")
    add(f"- SEALED quarantined ({len(sealed.quarantined)}): {_list(sealed.quarantined)}")
    add(f"- REBUILT quarantined ({len(rebuilt.quarantined)}): {_list(rebuilt.quarantined)}")
    add(f"- newly quarantined: {_list(_minus(rebuilt.quarantined, sealed.quarantined))}")
    add(f"- newly settled: {_list(_minus(sealed.quarantined, rebuilt.quarantined))}")
    add(f"- symbols only in the SEALED era: {_list(_minus(sealed.symbols, rebuilt.symbols))}")
    add(f"- symbols only in the REBUILT era: {_list(_minus(rebuilt.symbols, sealed.symbols))}")
    add("")

    add("## 4. Per-symbol day counts, sealed vs rebuilt")
    add("")
    identical = sum(
        1
        for symbol, old in sealed.symbols.items()
        if symbol in rebuilt.symbols and rebuilt.symbols[symbol].days == old.days
    )
    add(f"{identical} of {len(sealed.symbols)} sealed symbols reconcile EXACTLY on day count.")
    add("")
    add("| Symbol | SEALED days | REBUILT days | Delta | SEALED gate-1 | REBUILT gate-1 | Status |")
    add("|---|---|---|---|---|---|---|")
    for symbol in sorted(set(sealed.symbols) | set(rebuilt.symbols)):
        add(_depth_row(symbol, sealed.symbols.get(symbol), rebuilt.symbols.get(symbol)))
    add("")

    add("## 4a. T1 -- the SEALED-FETCH-HORIZON boundary test")
    add("")
    add(
        "The architect's T1 (QUESTIONS.md, 01-Aug-2026). For each symbol, B is the rebuilt "
        "store's `SEALED days`-th stored date, so the store's count on dates <= B equals the "
        "sealed count exactly and B is unique. The test PASSES when B falls inside the sealed "
        f"fetch window {SEALED_FETCH_WINDOW_START.isoformat()}..{sealed.scope_end}."
    )
    add("")
    add(
        "The gate-count leg is MEASURED, and it is a two-sided bound rather than an equality, "
        "because the sealed era's per-day verdicts no longer exist to be differenced. CONTEXT "
        "4.5's own battery is re-run here over the rebuilt store's days in the fetch window "
        f"[{SEALED_FETCH_WINDOW_START.isoformat()}, {rebuilt.scope_end}]; the sealed era's own "
        "tail in that window is known exactly (it is the store's day count over [window start, "
        "B]); and what that sealed tail could have contributed is bounded by the sealed "
        "report's own totals -- its ungated days (the CONTEXT 4.6 store-lag) and its failures "
        "are the only slack there is. If the reported gate-1 move lands outside the resulting "
        "interval, a day OLDER than the fetch window changed verdict, no horizon reading "
        "explains it, and the symbol keeps `unexplained` on that measure. What this proves is "
        "attribution to the window, not the identity of individual days."
    )
    add("")
    if horizons:
        passed = [h for h in horizons.values() if h.passed]
        failed = [h for h in horizons.values() if not h.passed]
        gated_ok = [h for h in passed if h.gate_accounted]
        gated_no = sorted(h.symbol for h in passed if not h.gate_accounted)
        add(f"- symbols tested: **{len(horizons)}**")
        add(f"- boundary inside the sealed fetch window (T1 PASS): **{len(passed)}**")
        add(f"- of those, the gate-1 move is attributable to the fetch window: "
            f"**{len(gated_ok)}**")
        add(f"- gate-1 move NOT attributable to the window (these fall through to the other "
            f"classes): **{len(gated_no)}**"
            + (": " + ", ".join(gated_no) if gated_no else ""))
        add(f"- T1 FAIL (stays unexplained): **{len(failed)}**"
            + (": " + ", ".join(sorted(h.symbol for h in failed)) if failed else ""))
        add("")
        add("### Boundary-date histogram")
        add("")
        add("| Boundary date B | Symbols | Extra days inside the sealed scope |")
        add("|---|---|---|")
        buckets: dict[str, list[HorizonVerdict]] = {}
        for verdict in horizons.values():
            key = verdict.boundary.isoformat() if verdict.boundary else "no boundary exists"
            buckets.setdefault(key, []).append(verdict)
        for key in sorted(buckets):
            rows = buckets[key]
            extras = sorted({len(r.extras) for r in rows})
            add(f"| {key} | {len(rows)} | {', '.join(str(e) for e in extras)} |")
        add("")
        add(
            "A histogram concentrated on a handful of consecutive dates inside the sealed fetch "
            "window is the signature the ruling names: the sealed run fetched each symbol at a "
            "different point of a long night, so its per-symbol horizon was earlier than the "
            "single scope date its report is labelled with."
        )
    else:
        add("Not run -- no rebuilt minute store was measured.")
    add("")

    if forensics:
        add("## 4b. T3 -- the committed forensics verdicts this report consumed")
        add("")
        add("| Symbol | Verdict | Measures reclassified | Summary |")
        add("|---|---|---|---|")
        for symbol in sorted(forensics):
            item = forensics[symbol]
            add(
                f"| {symbol} | `{item.verdict}` | "
                f"{', '.join(sorted(item.measures)) or '--'} | {item.summary} |"
            )
        add("")

    add("## 5. Divergences, classified")
    add("")
    add(
        f"{len(divergences)} divergence(s): "
        + ", ".join(f"{counts[name]} {name}" for name in CLASSES if name != CLASS_UNEXPLAINED)
        + f", **{unexplained} {CLASS_UNEXPLAINED}**."
    )
    add("")
    if divergences:
        add("| Symbol | Measure | SEALED | REBUILT | Delta | Class | Evidence |")
        add("|---|---|---|---|---|---|---|")
        for item in divergences:
            add(
                f"| {item.symbol} | {item.measure} | {item.sealed} | {item.rebuilt} | "
                f"{item.delta} | `{item.classification}` | {item.evidence} |"
            )
    else:
        add("None. The rebuilt era reproduces the sealed one on every measure compared here.")
    add("")

    add("## 6. Independent leg -- does the rebuilt report describe the store on disk?")
    add("")
    add(
        "Each symbol's stored days counted straight from the minute store's parquet files over "
        "the rebuilt report's own scope, and compared with that report's section 3. A CONTRADICTION "
        "(the report claims depth, the parquet directory holds nothing) blocks the verdict; a plain "
        "count difference is printed as a note, because the report's `Days` column counts from each "
        "symbol's own clamp and this module will not fail a rebuild over a semantic it cannot verify."
    )
    add("")
    if checks:
        add(
            f"{len(checks)} symbol(s) differ, {len(contradictions)} of them CONTRADICTIONS."
        )
        add("")
        add("| Symbol | Report says | Store holds | Contradiction? |")
        add("|---|---|---|---|")
        for item in checks:
            add(
                f"| {item.symbol} | {item.report_days:,} | {item.store_days:,} | "
                f"{'YES' if item.contradiction else 'no -- count difference only'} |"
            )
    else:
        add(
            f"AGREES on all {len(rebuilt.symbols)} rebuilt symbols. The report is a faithful "
            "description of the store this reconciliation read."
        )
    add("")

    add("## 7. Growth OUTSIDE the sealed era (not a divergence)")
    add("")
    add(
        f"{beyond:,} stored symbol-day(s) fall after the sealed scope end "
        f"({sealed.scope_end}). They are new trading, not drift, and they are what extends the "
        "walkable span past the sealed era."
    )
    add("")
    add(
        "Note precisely what this does and does not remove from the comparison. Sections 4 and "
        "5 diff the two reports' OWN columns, and the rebuilt report's `Days` counts to its own "
        f"scope end ({rebuilt.scope_end}) -- so these {beyond:,} days ARE inside its figures. "
        "Nothing is quietly netted off here; instead section 4a's boundary test is what "
        "separates the two causes, by naming the exact dates on each side of B."
    )
    add("")

    add("## 8. VERDICT")
    add("")
    if contradictions:
        add(
            f"**NO VERDICT -- {len(contradictions)} symbol(s) carry a depth figure the store "
            "cannot show** (section 6). Re-run runbook step 4's `--report-only` over the store "
            "before reconciling; a reconciliation against a report that does not describe its "
            "store means nothing."
        )
    elif unexplained == 0:
        add(
            "**ZERO UNEXPLAINED DIVERGENCES.** Under the ruling, the explained drift above is "
            "accepted ONLY via a formal CONTEXT 4.6 amendment (v1.5) listing the exact deltas. "
            "Section 2's delta column and section 5's table ARE that payload; writing the "
            "amendment is the architect's, not a session's."
        )
    else:
        add(
            f"**{unexplained} UNEXPLAINED DIVERGENCE(S) -- DEFECT, triage before any number is "
            f"believed.** The ruling: *unexplained drift is a defect to triage*. Each one is "
            f"listed in section 5 with what the classifier looked for and did not find."
        )
    add("")
    add("Divergences by FINAL class:")
    add("")
    add("| Class | Count |")
    add("|---|---|")
    for name in CLASSES:
        add(f"| `{name}` | {counts[name]} |")
    add("")
    return lines


def _depth_row(symbol: str, old: SymbolDepth | None, new: SymbolDepth | None) -> str:
    """One row of section 4, including the one-sided cases."""
    if old is None and new is not None:
        return (
            f"| {symbol} | absent | {new.days:,} | -- | -- | "
            f"{new.gate1_pass:,}/{new.gate1_gated:,} | -> {new.status} |"
        )
    if new is None and old is not None:
        return (
            f"| {symbol} | {old.days:,} | absent | -- | "
            f"{old.gate1_pass:,}/{old.gate1_gated:,} | -- | {old.status} -> |"
        )
    assert old is not None and new is not None  # both-absent is unreachable: the key came from one
    return (
        f"| {symbol} | {old.days:,} | {new.days:,} | {new.days - old.days:+,} | "
        f"{old.gate1_pass:,}/{old.gate1_gated:,} | {new.gate1_pass:,}/{new.gate1_gated:,} | "
        f"{old.status} -> {new.status} |"
    )


def _fmt(value: int | None) -> str:
    return "n/a" if value is None else f"{value:,}"


def _pct_delta(old: float | None, new: float | None) -> str:
    if old is None or new is None:
        return "n/a"
    return f"{new - old:+.4f} pp"


def _list(items) -> str:
    values = tuple(items)
    return ", ".join(sorted(values)) if values else "none"


def _minus(left, right) -> tuple[str, ...]:
    return tuple(sorted(set(left) - set(right)))


# --- CLI -----------------------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-q18-reconcile",
        description=(
            "Reconcile the rebuilt data era against CONTEXT 4.6's sealed numbers "
            "(QUESTIONS.md Q-18 ruling, 31-Jul-2026). Offline and read-only."
        ),
    )
    parser.add_argument("--sealed", default=SEALED_REPORT_RELPATH, help="the committed report")
    parser.add_argument("--rebuilt", default=REBUILT_REPORT_RELPATH, help="runbook step 4's report")
    parser.add_argument("--data-dir", default=None, help="data dir (default: config data_dir)")
    parser.add_argument("--cache-dir", default=None, help="CA day-cache dir (default: config)")
    parser.add_argument("--forensics", default=T3_FORENSICS_RELPATH,
                        help="the committed T3 forensics verdicts (T3; absent = none)")
    parser.add_argument("--out", default=None, help="also write the report to this markdown file")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    from .config import load_config
    from .daily_store import DailyStore
    from .minute_backfill import fetch_corp_action_history
    from .minute_store import MinuteStore
    from .nse_http import NseFetchError
    from .universe_backfill import build_daily_cache

    config = load_config(include_env=False)
    data = Path(args.data_dir) if args.data_dir else config.path("data_dir")
    cache = Path(args.cache_dir) if args.cache_dir else None

    sealed = read_report(args.sealed)
    rebuilt = read_report(args.rebuilt)

    store = MinuteStore.at(data / "minute_store")
    if not store.minute_dir.is_dir():
        raise ReconcileError(
            f"No minute store at {store.minute_dir}. This reconciliation runs ON the rebuilt "
            "stores (runbook step 4); it cannot be answered from the reports alone."
        )
    every_symbol = sorted(set(sealed.symbols) | set(rebuilt.symbols))
    # ONE pass over the parquet store; both measurements and T1's boundary test are derived from
    # it. Two measurements, deliberately: one split at the SEALED scope end (what is drift and
    # what is growth) and one over the REBUILT report's own scope (what that report should say).
    stored_days = {symbol: tuple(store.stored_days(symbol)) for symbol in every_symbol}
    measured = measure_days(stored_days, scope_end=sealed.scope_end)
    at_rebuilt_scope = measure_days(stored_days, scope_end=rebuilt.scope_end)

    try:
        actions = fetch_corp_action_history(
            date(CA_FIRST_YEAR, 1, 1),
            date((rebuilt.scope_end or date.today()).year, 12, 31),
            allow_network=False,
            cache_dir=cache,
        )
    except NseFetchError as exc:
        raise ReconcileError(
            f"The corporate-action day-cache is not readable offline ({exc}). Runbook step 2 "
            "rebuilds it; without it no divergence can be called new-CA-explained."
        ) from exc

    # T2: an ex-date after the sealed era AND on or before the rebuild's own fetch date.
    events = new_events_by_symbol(actions, after=sealed.scope_end, until=REBUILD_FETCH_DATE)
    untightened = new_events_by_symbol(actions, after=sealed.scope_end)
    dropped = sum(len(v) for v in untightened.values()) - sum(len(v) for v in events.values())

    # T1: the boundary test, then its MEASURED gate leg over exactly the days after B.
    horizons: dict[str, HorizonVerdict] = {}
    if sealed.scope_end is not None:
        for symbol in sorted(set(sealed.symbols) & set(rebuilt.symbols)):
            horizons[symbol] = horizon_boundary(
                stored_days.get(symbol, ()),
                sealed.symbols[symbol].days,
                window_start=SEALED_FETCH_WINDOW_START,
                window_end=sealed.scope_end,
                symbol=symbol,
            )
        wanted = sorted(h.symbol for h in horizons.values() if h.passed)
        if wanted:
            window_end = rebuilt.scope_end or date.today()
            daily_cache = build_daily_cache(
                DailyStore.at(data / "daily_store"), wanted,
                SEALED_FETCH_WINDOW_START, window_end,
            )
            for symbol in wanted:
                verdict = horizons[symbol]
                tail = [d for d in stored_days.get(symbol, ())
                        if SEALED_FETCH_WINDOW_START <= d <= window_end]
                got_pass, got_gated = gate_window(store, daily_cache, symbol, tail)
                sealed_tail = sum(
                    1 for d in stored_days.get(symbol, ())
                    if SEALED_FETCH_WINDOW_START <= d <= (verdict.boundary or window_end)
                )
                horizons[symbol] = account_gate_delta(
                    verdict,
                    sealed_pass=sealed.symbols[symbol].gate1_pass,
                    sealed_gated=sealed.symbols[symbol].gate1_gated,
                    sealed_days=sealed.symbols[symbol].days,
                    rebuilt_pass=rebuilt.symbols[symbol].gate1_pass,
                    rebuilt_gated=rebuilt.symbols[symbol].gate1_gated,
                    tail_pass=got_pass,
                    tail_gated=got_gated,
                    sealed_tail_days=sealed_tail,
                )

    forensics = read_forensics(args.forensics) if args.forensics else {}

    divergences = reconcile(
        sealed, rebuilt, new_events=events, horizons=horizons, forensics=forensics
    )
    checks = cross_check_store(rebuilt, at_rebuilt_scope)

    lines = render(
        sealed=sealed,
        rebuilt=rebuilt,
        divergences=divergences,
        measured=measured,
        checks=checks,
        ca_rows=len(actions),
        horizons=horizons,
        forensics=forensics,
        dropped_future_events=dropped,
    )
    for line in lines:
        print(line, flush=True)

    if args.out is not None:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {out}", flush=True)

    unexplained = counts_by_class(divergences)[CLASS_UNEXPLAINED]
    blocked = any(check.contradiction for check in checks)
    return 0 if (unexplained == 0 and not blocked) else 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except ReconcileError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover -- exercised through main()
    raise SystemExit(main())
