"""REVIEW_9B_FINAL kept probes -- the chunk-9B FINAL-EDITS re-review (06-Aug-2026).

Six probes, added by the reviewer, kept in the repo. None of them modifies an existing test, a
fixture, a `src/` file or a store. Three of them turn a finding of this review into ARITHMETIC a
future session inherits rather than prose it can skim; two of them close a hole the shipped suite
does not cover:

* :func:`test_the_reports_Q23_quote_is_NOT_verbatim_against_the_QUESTIONS_md_record` -- finding
  **Q1**: section 10 presents a quote as the architect's words and the words differ.
* :func:`test_the_benchmark_factor_TALLY_counts_symbols_the_benchmark_itself_EXCLUDES` -- finding
  **Q2**: "what THE BENCHMARK applies: 125 factors across 86 symbols" is counted over every
  symbol with a daily series, not over the 134 the benchmark is built from.
* :func:`test_a_ZERO_LENGTH_holding_is_where_the_two_concurrency_conventions_diverge` -- finding
  **C1**: the running count dips below zero on a same-stamp trade; the maximum is provably
  unaffected, and that is asserted rather than assumed.
* :func:`test_the_partial_year_marker_follows_the_LAST_year_of_a_ten_year_span` -- B288 on the
  side the shipped tests reach only through a two-year fixture: a 2016..2026-shaped span whose
  BEST year is the partial last one.
* :func:`test_the_numeric_freeze_is_not_VACUOUS_the_pre_edit_report_fails_it` -- the freeze's own
  "other direction", proved against the committed pre-edit blob through ``git show`` rather than
  against a string the test wrote itself.
* :func:`test_the_priced_refusal_rows_RENDER_the_measured_base_and_not_the_full_day_count` --
  finding **C4**: B289 put the base in the data and the shipped suite never reads the cell back.
  Mutation-verified: printing the full day count there SURVIVES the whole shipped suite.

Offline: reads two files in the repository and one git blob. No store is touched.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen import report_9b as r9
from acumen.signals import LONG

COST = 10_000
CAPITAL = 10_000_000


def trade(day: date, symbol: str, qty: int, entry: int, gross: int, *,
          hour: int = 12, exit_hour: int = 14) -> bt.LedgerRow:
    """One executed LONG row -- the same shape `tests/test_report_9b.py` builds, self-contained."""
    base = datetime.combine(day, datetime.min.time())
    return bt.LedgerRow(
        symbol=symbol, day=day, status="evaluated", reason="evaluated", side=LONG,
        outcome="entered", consumed=True, signalled=True, executed=True,
        entry_paise=entry, stop_paise=entry - 100, target_paise=entry + 300,
        per_share_risk_paise=100, entry_close_stamp=base + timedelta(hours=hour),
        exit_kind="target-hit", exit_paise=entry + 300,
        exit_close_stamp=base + timedelta(hours=exit_hour), qty=qty,
        notional_paise=qty * entry, gross_pnl_paise=gross, cost_paise=COST,
        net_pnl_paise=gross - COST, mfe_paise=max(0, gross), mae_paise=min(0, gross),
    )


class _FakeDaily:
    """A daily store the size of the fixture: a few closes per symbol and nothing else."""

    def __init__(self, series: dict[str, dict[date, int]]) -> None:
        self._series = series

    def daily(self, symbol: str, start: date, end: date):
        class _Row:
            def __init__(self, day, close):
                self.trade_date = day
                self.close_paise = close

        class _Frame:
            def __init__(self, rows):
                self._rows = rows

            def itertuples(self):
                return iter(self._rows)

        return _Frame([_Row(day, close)
                       for day, close in sorted(self._series.get(symbol, {}).items())
                       if start <= day <= end])


REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "docs" / "reports" / "chunk9b_backtest_report.md"
QUESTIONS = REPO / "QUESTIONS.md"
BASELINE_PY = REPO / "docs" / "evidence" / "chunk9b_report_numeric_baseline.py"


#: (codepoint, ASCII replacement). Written as escapes, not as literals: this file is a runtime
#: source and `tests/test_smoke.py::test_project_runtime_sources_are_ascii_only` forbids a
#: non-ASCII source LINE (the operator's console is cp1252 and a traceback would die printing it).
_FOLD: tuple[tuple[str, str], ...] = (
    ("\u2014", "--"),   # em dash
    ("\u2013", "--"),   # en dash
    ("\u201c", '"'),   # left double quote
    ("\u201d", '"'),   # right double quote
    ("\u2019", "'"),   # right single quote
)


def _ascii_fold(text: str) -> str:
    """The one difference the repo LICENSES: report files are ASCII, QUESTIONS.md is not."""
    for bad, good in _FOLD:
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def test_the_reports_Q23_quote_is_NOT_verbatim_against_the_QUESTIONS_md_record() -> None:
    """REVIEW_9B_FINAL finding Q1, as a diff rather than as an opinion.

    `BENCHMARK_RULING`'s own comment says the ruling and its refinement are "quoted VERBATIM",
    and section 10 renders it as a blockquote attributed to the architect. Two things in it are
    not the architect's words: the pointer `QUESTIONS.md` is inserted into the ruling's opening,
    and the ruling's own parenthetical **(491.90% as generated)** -- the figure the refinement
    later supersedes, and the figure the bullet below the table calls "the figure the ruling
    first named" -- is DELETED.

    This probe pins the divergence in both directions. It goes red if the report's quote changes
    (including if it is corrected, which is the point: correcting it is a deliberate act) and red
    if QUESTIONS.md's verbatim record is ever edited.
    """
    questions = QUESTIONS.read_text(encoding="utf-8")
    blocks = re.findall(r'^> "(ARCHITECT.*?)"\s*$', questions, flags=re.M | re.S)
    ruling = next(b for b in blocks if b.startswith("ARCHITECT'S RULING (06-Aug-2026), Q-23:"))
    refinement = next(
        b for b in blocks if b.startswith("ARCHITECT'S REFINEMENT (06-Aug-2026), Q-23 'and stated':")
    )

    # what QUESTIONS.md records, ASCII-folded and with the ruling's trailing signature dropped
    recorded = _ascii_fold(ruling.replace("Architect.", "").strip()) + " " + _ascii_fold(refinement)

    published = _ascii_fold(r9.BENCHMARK_RULING)
    assert published in _ascii_fold(REPORT.read_text(encoding="utf-8")), (
        "the constant and the shipped report must at least agree with each other"
    )

    assert published != recorded.rstrip("."), (
        "if this ever becomes equal the finding is FIXED -- delete the rest of this probe"
    )
    # the two differences, named exactly
    assert "(491.90% as generated)" in recorded and "(491.90% as generated)" not in published, (
        "the ruling's own figure is dropped from the quote that carries the ruling"
    )
    assert "QUESTIONS.md Q-23:" in published and "QUESTIONS.md Q-23:" not in recorded, (
        "a pointer the architect did not write is inserted into the quote"
    )
    # and nothing ELSE differs: restoring those two turns the quote back into the record
    restored = published.replace("QUESTIONS.md Q-23:", "Q-23:").replace(
        "SHARE-COUNT-ADJUSTED construction --",
        "SHARE-COUNT-ADJUSTED construction (491.90% as generated) --",
    )
    assert restored == recorded.rstrip("."), (
        "those two edits are the WHOLE of the divergence; a third one has appeared"
    )


def test_the_benchmark_factor_TALLY_counts_symbols_the_benchmark_itself_EXCLUDES() -> None:
    """REVIEW_9B_FINAL finding Q2, as arithmetic.

    CONTEXT 7-E13's portfolio is bought at the FIRST TRADE DATE's close, so a symbol with no
    close on that date is not in it -- section 10 names all 70 of them. `benchmark_pair` counts
    `share_count_events` / `share_count_symbols` over every symbol that has ANY daily row in the
    window, the excluded ones included, and section 10 prints that tally under the words
    "What THE BENCHMARK applies".

    Here BBB has no close on the first day. Its bonus is counted by the tally and applied to
    nothing: the benchmark's own value is AAA's alone.
    """
    first, last = date(2020, 1, 1), date(2020, 12, 31)
    store = _FakeDaily({
        "AAA": {first: 100_000, last: 100_000},
        "BBB": {date(2020, 7, 1): 100_000, last: 100_000},   # no close on the first day
    })
    manifest = {"factor_table": {"per_symbol": {
        "AAA": {"in_span": [{"ex_date": "2020-06-01", "k": "1/2", "kind": "bonus",
                             "classification": ""}]},
        "BBB": {"in_span": [{"ex_date": "2020-08-01", "k": "1/2", "kind": "bonus",
                             "classification": ""}]},
    }}}
    pair = r9.benchmark_pair(store, manifest, symbols=["AAA", "BBB"], first_day=first,
                             last_day=last, initial_capital_paise=CAPITAL)

    assert tuple(pair.share_count.symbols) == ("AAA",), "only AAA is IN the benchmark"
    # ...but the tally section 10 prints beside it counts BBB's bonus too
    assert pair.share_count_events == 2 and pair.share_count_symbols == 2, (
        "the printed tally is over the whole universe, not over the benchmark's own members"
    )
    # the value is AAA's alone: 100,000 x 1/2 = 50,000 -> the holder doubled
    assert pair.share_count.total_return == 1, "BBB's factor moves no rupee of the benchmark"


def test_a_ZERO_LENGTH_holding_is_where_the_two_concurrency_conventions_diverge() -> None:
    """REVIEW_9B_FINAL finding C1, and the sharpest statement of what the two rows measure.

    A trade that exits at the stamp it entered is live on an EMPTY half-open interval. Sixteen
    executed rows of the real ledger are that shape (the entry-candle square-off B159 named).

    `concurrency_closing_first` sorts a CLOSE ahead of an OPEN at a shared stamp and applies the
    rule to a trade's OWN two events as well, so such a trade subtracts itself before it adds
    itself and the running count dips -- on the real run it reaches **-16**, a concurrency that
    cannot exist. The MAXIMUM is provably untouched by that: after every event at a stamp the
    count is `#{entry <= T < exit}` exactly, and the maximum is read at the last open of the
    stamp. Both halves are pinned here, with `pf.disclosures` beside them as the control that
    shows the divergence is the CONVENTION and not an accident.
    """
    day = date(2020, 1, 6)
    base = datetime.combine(day, datetime.min.time())
    same_stamp = trade(day, "AAA", 10, 100_000, 300_000, hour=12, exit_hour=12)
    assert same_stamp.exit_close_stamp == same_stamp.entry_close_stamp == base + timedelta(hours=12)

    # alone, the half-open sweep never sees it as concurrent at all -- correct for the convention
    assert r9.concurrency_closing_first((same_stamp,)).positions == 0
    # ...while the OPEN-first convention the headline uses counts it
    assert pf.disclosures((same_stamp,)).max_concurrent_positions.positions == 1

    held = (
        trade(day, "BBB", 10, 100_000, 300_000, hour=10, exit_hour=14),
        trade(day, "CCC", 10, 100_000, 300_000, hour=11, exit_hour=15),
    )
    peak = r9.concurrency_closing_first(held + (same_stamp,))
    assert peak.positions == 2 and peak.at == base + timedelta(hours=11), (
        "the transient never reaches the answer: #{entry <= T < exit} is 2 at every stamp here"
    )
    assert pf.disclosures(held + (same_stamp,)).max_concurrent_positions.positions == 3, (
        "the pessimistic row counts all three at 12:00 -- this shape IS the difference"
    )


def test_the_partial_year_marker_follows_the_LAST_year_of_a_ten_year_span() -> None:
    """B288, on the side the shipped fixture does not reach: the BEST year is the partial LAST.

    The real run opens 2016-10-03 and closes 2026-07-30, so 2016 is partial and carries the best
    net. The mirror -- a span whose partial LAST year is the best one -- must be marked the same
    way and must name the best FULL year beside it, with the years derived from the index.
    """
    days = tuple(sorted({date(2016, 10, 3), date(2016, 12, 30)}
                        | {date(y, 6, 1) for y in range(2017, 2026)}
                        | {date(2026, 1, 2), date(2026, 7, 30)}))
    assert r9._partial_years(days) == frozenset({"2016", "2026"})
    assert r9._partial_years(()) == frozenset()
    # a span that fills both end years end to end has NO partial year
    assert r9._partial_years((date(2016, 1, 1), date(2026, 12, 31))) == frozenset()

    rows = tuple(
        [trade(date(y, 6, 1), "AAA", 10, 100_000, -300_000) for y in range(2017, 2026)]
        + [trade(date(2016, 10, 3), "AAA", 10, 100_000, -500_000)]
        + [trade(date(2026, 7, 30), "AAA", 10, 100_000, 300_000)]     # the best, and PARTIAL
    )
    years = r9.per_year(rows, days, initial_capital_paise=CAPITAL, gap_by_year={})
    best = max(years, key=lambda y: y.metrics.net_pnl_paise)
    assert best.year == "2026"

    cell = r9._year_extreme_cell(best, years, r9._partial_years(days), best=True)
    assert "**a PARTIAL year**" in cell, "the marker is not tied to the first year of the span"
    assert "the best FULL year is 2017" in cell, (
        "every 2017..2025 year is -Rs 3,000.00 net; the earliest is picked, and it is a FULL one"
    )
    assert "2026" not in cell.split("the best FULL year is")[1]


def test_the_numeric_freeze_is_not_VACUOUS_the_pre_edit_report_fails_it() -> None:
    """The freeze's other direction, proved against the COMMITTED pre-edit blob.

    `test_each_of_the_six_corrections_is_PRESENT_in_the_regenerated_report` asserts the six
    corrections are on the page. This asserts the converse on the only artefact that can prove
    it: the report as committed at the baseline ref. Every one of those markers must be absent
    there, and the two replaced lines must still be present -- otherwise the freeze would pass on
    a report where the edits never landed.
    """
    spec = importlib.util.spec_from_file_location("chunk9b_numeric_baseline", BASELINE_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    blob = subprocess.run(
        ["git", "show", f"{module.DEFAULT_REF}:{module.REPORT_RELPATH}"],
        cwd=REPO, check=True, capture_output=True,
    ).stdout.decode("utf-8")
    lines = module.sections_1_to_9(blob)

    def present(where: int, marker: str) -> bool:
        return any(section == where and marker in line for section, line in lines)

    for where, marker in (
        (1, "ALL THREE GATES, not the price gate alone"),
        (4, "**Concurrency, and which convention the headline uses.**"),
        (5, "**a PARTIAL year**"),
        (6, "% of notional -- RANGE across the tied trades"),
        (6, "the fences do NOT"),
        (6, "the fences do sit outside the band"),
    ):
        assert not present(where, marker), f"section {where}: {marker!r} is NOT a correction"

    assert present(6, "% of its own notional"), "the pre-edit rows the corrections replace"
    assert present(6, "and the fences sit outside it"), "the pre-edit blanket claim"

    # ...and the token stream of that blob IS the frozen baseline, so the freeze is over the
    # reviewed artefact and not over whatever happens to be in the working tree.
    import json
    baseline = json.loads((BASELINE_PY.with_suffix(".json")).read_text(encoding="utf-8"))
    assert module.numeric_tokens(blob) == baseline["tokens"]
    assert baseline["token_count"] == 2457


def test_the_priced_refusal_rows_RENDER_the_measured_base_and_not_the_full_day_count() -> None:
    """REVIEW_9B_FINAL finding C4: B289 put the base in the data, and nothing reads the cell back.

    The shipped test asserts the column HEADER, the paragraph beneath the table and the evidence
    sentence -- all three of which are built from `RefusalClass.days_measured` -- but never the
    fourth column of a priced row. Rendering `item.rows` there instead reinstates exactly the
    "13 of 210" reading finding Q6 was raised for, and the whole shipped suite stays green
    (mutation-verified, M6). This reads the cell.
    """
    priced = r9.RefusalClass(
        reason="bias unresolvable (CONTEXT 3.2 pair could not be assembled): minutes-ungated",
        rows=210, share_of_walk=Fraction(210, 495_312),
        evidence=("103 of the crashed run's shards survive, and they walked 105 of these 210 days "
                  "under the pre-ruling code; 13 of those 105 executed a trade there"),
        trades_found=13, net_paise=-735_835, days_measured=105, priced=True,
    )
    unpriced = r9.RefusalClass(
        reason="gate 1 (volume reconciliation)", rows=6_056,
        share_of_walk=Fraction(6_056, 495_312),
        evidence="none -- the crashed run refused these days for the same reason",
        trades_found=0, net_paise=0, days_measured=0, priced=False,
    )
    run = SimpleNamespace(symbols=tuple(f"S{i:03d}" for i in range(204)),
                          witnesses=SimpleNamespace(gate2_days=()))
    crashed = r9.CrashedCheck(shards=103, rows_compared=250_084, rows_changed=145,
                              by_cause={}, identical_shards=(), by_symbol={}, lost_trades={})

    lines: list[str] = []
    r9._section_take_all(
        lines.append,
        disclosures=pf.disclosures(()),
        capital_flag_report=pf.capital_flags((), capital_reference_paise=None, margin_basis=None),
        daily_counts=(), refusals=(priced, unpriced), run=run, capital_paise=CAPITAL,
        crashed=crashed,
    )
    text = "\n".join(lines)

    def cells(prefix: str) -> list[str]:
        row = next(line for line in text.splitlines() if line.startswith(f"| {prefix}"))
        return [cell.strip() for cell in row.strip("|").split("|")]

    header = cells("Refusal reason")
    assert header[3] == "Days with a counterfactual"

    body = cells("bias unresolvable")
    assert body[1] == "210", "the class's own day count stays in column 2"
    assert body[3] == "105", (
        "column 4 must RENDER days_measured -- printing rows here is the 13-of-210 defect"
    )
    assert body[4] == "13" and body[5] == "-Rs 7,358.35"

    quiet = cells("gate 1 (volume reconciliation)")
    assert quiet[3] == quiet[4] == quiet[5] == "-", (
        "a class with no counterfactual prints dashes, not a zero that reads as a measurement"
    )
