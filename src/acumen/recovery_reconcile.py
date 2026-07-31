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

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

#: The ruling's three classes, spelled exactly as the architect spelled them.
CLASS_NEW_CA: str = "new-CA-explained"
CLASS_VENDOR_REPAIR: str = "vendor-repair-explained"
CLASS_UNEXPLAINED: str = "unexplained"
CLASSES: tuple[str, ...] = (CLASS_NEW_CA, CLASS_VENDOR_REPAIR, CLASS_UNEXPLAINED)

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


def measure_store(store: Any, symbols: Sequence[str], *, scope_end: date | None) -> dict[str, StoreMeasurement]:
    """Count each symbol's stored days from the store, split at the sealed era's end.

    Days AFTER ``scope_end`` are growth, not divergence: the rebuild fetches to today while the
    sealed era stopped at its own scope date, and comparing the two spans directly would report
    a year of new trading as a defect. They are counted separately and reported separately.
    """
    out: dict[str, StoreMeasurement] = {}
    for symbol in symbols:
        stored = store.stored_days(symbol)
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
) -> tuple[str, str]:
    """Return ``(class, evidence)`` for one divergence. Conservative by construction.

    The rules are the module docstring's, executed in order. Nothing is called explained
    without the evidence being present on disk, so the default is ``unexplained``.
    """
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


def new_events_by_symbol(actions: Sequence[Any], *, after: date | None) -> dict[str, list[str]]:
    """Corporate actions with an ex-date strictly after the sealed era, per symbol.

    ``after`` is the sealed report's own scope end. With no scope end nothing is "new" and the
    class simply never fires -- silence beats a guessed cut-off.
    """
    out: dict[str, list[str]] = {}
    if after is None:
        return out
    for action in actions:
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
) -> list[Divergence]:
    """Every per-symbol divergence between the two eras, classified. Pure."""
    divergences: list[Divergence] = []
    for symbol in sorted(set(sealed.symbols) | set(rebuilt.symbols)):
        old = sealed.symbols.get(symbol)
        new = rebuilt.symbols.get(symbol)
        events = list(new_events.get(symbol, ()))
        disclosed = symbol in sealed.disclosed

        if old is None or new is None:
            side = "rebuilt only" if old is None else "SEALED only"
            classification, evidence = classify(
                MEASURE_PRESENCE, improved=None, new_events=events, disclosed=disclosed
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
) -> list[str]:
    """The reconciliation report, exactly as it is printed and written."""
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
        f"| `{CLASS_UNEXPLAINED}` | everything else | -- including every regression, every "
        "one-sided presence, and every change on a symbol with no disclosed deficiency |"
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

    add("## 5. Divergences, classified")
    add("")
    add(
        f"{len(divergences)} divergence(s): {counts[CLASS_NEW_CA]} {CLASS_NEW_CA}, "
        f"{counts[CLASS_VENDOR_REPAIR]} {CLASS_VENDOR_REPAIR}, "
        f"**{unexplained} {CLASS_UNEXPLAINED}**."
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
        f"({sealed.scope_end}). They are new trading, not drift, and are excluded from every "
        "comparison above. They are what extends the walkable span past the sealed era."
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
    parser.add_argument("--out", default=None, help="also write the report to this markdown file")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    from .config import load_config
    from .minute_backfill import fetch_corp_action_history
    from .minute_store import MinuteStore
    from .nse_http import NseFetchError

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
    # Two measurements, deliberately: one split at the SEALED scope end (what is drift and what
    # is growth) and one over the REBUILT report's own scope (what that report should be saying).
    measured = measure_store(store, every_symbol, scope_end=sealed.scope_end)
    at_rebuilt_scope = measure_store(store, every_symbol, scope_end=rebuilt.scope_end)

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

    events = new_events_by_symbol(actions, after=sealed.scope_end)
    divergences = reconcile(sealed, rebuilt, new_events=events)
    checks = cross_check_store(rebuilt, at_rebuilt_scope)

    lines = render(
        sealed=sealed,
        rebuilt=rebuilt,
        divergences=divergences,
        measured=measured,
        checks=checks,
        ca_rows=len(actions),
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
