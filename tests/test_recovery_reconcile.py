"""Tests for the Q-18 reconciliation (QUESTIONS.md, architect's ruling of 31-Jul-2026).

Two halves:

* the PARSER is pinned against the REAL committed `docs/backfill_minute_report.md` -- the
  sealed era itself. These assertions are the CONTEXT 4.6 numbers, so if the parser ever drifts
  the sealed baseline stops reproducing and the tests say so;
* everything else runs on synthetic reports built here, because the sealed store no longer
  exists and a rebuilt one does not exist yet. The classifier is pure, so the interesting cases
  (a new corporate action, a repaired residual, a regression, a one-sided symbol) are all
  reachable without any store at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pytest

from acumen import recovery_reconcile as rr
from acumen.minute_store import MinuteStore

REPO_ROOT = Path(__file__).resolve().parents[1]
SEALED = REPO_ROOT / "docs" / "backfill_minute_report.md"


# --- the parser against the real sealed report ------------------------------------------


@pytest.fixture(scope="module")
def sealed() -> rr.ReportFacts:
    return rr.read_report(SEALED)


def test_the_sealed_report_reproduces_context_4_6s_headline(sealed: rr.ReportFacts) -> None:
    """CONTEXT 4.6, verbatim: 411,690 / 434,769 = 94.69%, 204 settled, 6 quarantined."""
    assert sealed.coverage_pass == 411_690
    assert sealed.coverage_stored == 434_769
    assert round(sealed.coverage_percent, 4) == 94.6917
    assert len(sealed.settled) == 204
    assert sealed.quarantined == ("ASTRAL", "IEX", "NESTLEIND", "NTPC", "UPL", "VBL")


def test_the_sealed_report_carries_every_universe_symbol(sealed: rr.ReportFacts) -> None:
    assert len(sealed.symbols) == 210
    assert sealed.headline["Universe symbols"] == 210
    assert sealed.headline["Settled"] == 204


def test_the_sealed_scope_end_is_read_from_the_report_not_typed(sealed: rr.ReportFacts) -> None:
    """The clamp that separates drift from growth comes from the artefact itself."""
    assert sealed.scope_end == date(2026, 7, 28)


def test_a_sealed_per_symbol_row_parses_whole(sealed: rr.ReportFacts) -> None:
    abb = sealed.symbols["ABB"]
    assert (abb.route, abb.days, abb.gate1_pass, abb.gate1_gated) == ("map-required", 2431, 2416, 2429)
    assert abb.first_day == date(2016, 10, 3) and abb.settled


def test_the_disclosed_deficiency_set_is_the_union_of_the_sealed_registers(
    sealed: rr.ReportFacts,
) -> None:
    """vendor-repair-explained needs a deficiency the SEALED era itself named."""
    assert set(sealed.quarantined) <= sealed.disclosed  # quarantine is a disclosed deficiency
    for symbol in ("IOC", "TATASTEEL", "GAIL", "NMDC"):  # gate-1P residual / gate-3 register
        assert symbol in sealed.disclosed, symbol
    assert "TCS" not in sealed.disclosed  # a clean symbol is NOT disclosed


def test_a_file_that_is_not_a_backfill_report_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "not_a_report.md"
    path.write_text("# hello\n", encoding="utf-8")
    with pytest.raises(rr.ReconcileError, match="no per-symbol depth table"):
        rr.read_report(path)


def test_a_missing_report_names_both_expected_paths(tmp_path: Path) -> None:
    with pytest.raises(rr.ReconcileError) as excinfo:
        rr.read_report(tmp_path / "absent.md")
    assert rr.SEALED_REPORT_RELPATH in str(excinfo.value)
    assert rr.REBUILT_REPORT_RELPATH in str(excinfo.value)


# --- synthetic reports ---------------------------------------------------------------------


def build_report(rows, *, scope_end: str = "2026-07-28", coverage=(400, 500)) -> str:
    """The smallest text `parse_backfill_report` accepts, in the real generator's shape."""
    lines = [
        "# Minute backfill report -- chunk 5B (full-universe 1-minute run)",
        "",
        f"Scope: CONTEXT 3.1's F&O stock underlyings, 1-minute candles from `2016-10-01` "
        f"to `{scope_end}`.",
        "",
        "## 1. Headline",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Universe symbols | {len(rows)} |",
        "",
        "### 1a. Coverage under every defensible reading",
        "",
        "| Reading | Numerator | Denominator | Coverage | DoD |",
        "|---|---|---|---|---|",
        f"| **G gate 1 AND gate 2 AND GATE 1P, stored-day denominator** | {coverage[0]:,} | "
        f"{coverage[1]:,} | 80.0000% | **NOT MET** |",
        "",
        "## 3. Depth found, per symbol",
        "",
        "| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 (strict) | "
        "Relief | Gate-1 (effective) | Floors | Gate-2 excl | Avg min/day | Status |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for symbol, days, gate1_pass, gated, status in rows:
        lines.append(
            f"| {symbol} | table-path | 2016-10-01 | 2016-10-03 | {days} | 1/0/0 | "
            f"{gate1_pass}/{gated} (99.0%) | 0 | {gate1_pass}/{gated} (99.0%) | - | 0 | 370.0 | "
            f"{status} |"
        )
    lines += ["", "### Quarantined symbols", "", "| Symbol | Route | Why |", "|---|---|---|"]
    for symbol, _days, _p, _g, status in rows:
        if status != "settled":
            lines.append(f"| {symbol} | table-path | below 80% |")
    lines.append("")
    return "\n".join(lines)


def facts(rows, **kwargs) -> rr.ReportFacts:
    return rr.parse_backfill_report(build_report(rows, **kwargs), source="synthetic")


BASE = [("TCS", 100, 98, 100, "settled"), ("GAIL", 100, 60, 100, "quarantined")]


def test_a_synthetic_report_round_trips_through_the_parser() -> None:
    parsed = facts(BASE)
    assert parsed.scope_end == date(2026, 7, 28)
    assert parsed.symbols["TCS"].days == 100
    assert parsed.quarantined == ("GAIL",)
    assert parsed.coverage_pass == 400 and parsed.coverage_stored == 500


def test_an_identical_rebuild_produces_no_divergence() -> None:
    assert rr.reconcile(facts(BASE), facts(BASE), new_events={}) == []


# --- classification: the three classes, one test each and one for the default ---------------


def test_a_new_corporate_action_explains_a_gate_outcome_move() -> None:
    rebuilt = [("TCS", 100, 90, 100, "settled"), ("GAIL", 100, 60, 100, "quarantined")]
    found = rr.reconcile(
        facts(BASE), facts(rebuilt), new_events={"TCS": ["Bonus 1:1 @ 2026-07-30"]}
    )
    assert [(d.symbol, d.measure, d.classification) for d in found] == [
        ("TCS", rr.MEASURE_PASSING, rr.CLASS_NEW_CA)
    ]
    assert "Bonus 1:1 @ 2026-07-30" in found[0].evidence


def test_a_new_corporate_action_does_NOT_explain_a_stored_day_move() -> None:
    """A corporate action re-scales history; it never adds or removes stored days."""
    rebuilt = [("TCS", 140, 98, 100, "settled"), ("GAIL", 100, 60, 100, "quarantined")]
    found = rr.reconcile(
        facts(BASE), facts(rebuilt), new_events={"TCS": ["Bonus 1:1 @ 2026-07-30"]}
    )
    assert [(d.measure, d.classification) for d in found] == [
        (rr.MEASURE_STORED, rr.CLASS_UNEXPLAINED)
    ]


def test_an_improvement_on_a_disclosed_symbol_is_a_vendor_repair() -> None:
    rebuilt = [("TCS", 100, 98, 100, "settled"), ("GAIL", 100, 99, 100, "settled")]
    found = rr.reconcile(facts(BASE), facts(rebuilt), new_events={})
    assert {d.measure: d.classification for d in found} == {
        rr.MEASURE_PASSING: rr.CLASS_VENDOR_REPAIR,
        rr.MEASURE_STATUS: rr.CLASS_VENDOR_REPAIR,
    }


def test_an_improvement_on_an_UNdisclosed_symbol_is_unexplained() -> None:
    """Nothing was ever wrong with TCS, so there is nothing a repair could have repaired."""
    rebuilt = [("TCS", 100, 100, 100, "settled"), ("GAIL", 100, 60, 100, "quarantined")]
    found = rr.reconcile(facts(BASE), facts(rebuilt), new_events={})
    assert [(d.symbol, d.classification) for d in found] == [("TCS", rr.CLASS_UNEXPLAINED)]
    assert "no deficiency" in found[0].evidence


def test_every_regression_is_unexplained_even_with_a_new_event_and_a_disclosure() -> None:
    """The ruling's teeth: no class explains the era getting worse."""
    rebuilt = [("TCS", 100, 98, 100, "settled"), ("GAIL", 90, 50, 90, "quarantined")]
    found = rr.reconcile(
        facts(BASE), facts(rebuilt), new_events={"GAIL": ["Split @ 2026-07-31"]}
    )
    stored = next(d for d in found if d.measure == rr.MEASURE_STORED)
    assert stored.classification == rr.CLASS_UNEXPLAINED
    assert "WORSE" in stored.evidence


def test_a_settled_symbol_falling_into_quarantine_without_an_event_is_unexplained() -> None:
    rebuilt = [("TCS", 100, 40, 100, "quarantined"), ("GAIL", 100, 60, 100, "quarantined")]
    found = rr.reconcile(facts(BASE), facts(rebuilt), new_events={})
    assert {d.classification for d in found} == {rr.CLASS_UNEXPLAINED}


def test_a_symbol_present_on_one_side_only_is_unexplained_and_says_why() -> None:
    rebuilt = BASE + [("NEWCO", 50, 50, 50, "settled")]
    found = rr.reconcile(facts(BASE), facts(rebuilt), new_events={})
    assert [(d.symbol, d.measure, d.classification) for d in found] == [
        ("NEWCO", rr.MEASURE_PRESENCE, rr.CLASS_UNEXPLAINED)
    ]
    assert "CONTEXT 7-E5" in found[0].evidence


def test_a_symbol_lost_by_the_rebuild_is_unexplained() -> None:
    found = rr.reconcile(facts(BASE), facts(BASE[:1]), new_events={})
    assert [(d.symbol, d.delta, d.classification) for d in found] == [
        ("GAIL", "SEALED only", rr.CLASS_UNEXPLAINED)
    ]


def test_classify_defaults_to_unexplained_on_an_unknown_measure() -> None:
    """The default is the safe one: an unrecognised measure is never called explained."""
    assert rr.classify("something new", improved=None, new_events=["e"], disclosed=True)[0] == (
        rr.CLASS_UNEXPLAINED
    )


def test_counts_by_class_reports_all_three_classes_even_at_zero() -> None:
    assert rr.counts_by_class(()) == {name: 0 for name in rr.CLASSES}


# --- new_events_by_symbol -------------------------------------------------------------------


@dataclass(frozen=True)
class _Action:
    symbol: str
    ex_date: date
    subject: str


def test_only_events_after_the_sealed_era_count_as_new() -> None:
    actions = [
        _Action("TCS", date(2026, 7, 28), " Bonus 1:1"),  # ON the scope end: not after it
        _Action("TCS", date(2026, 7, 29), " Bonus 1:1"),
        _Action("GAIL", date(2020, 1, 1), " Split"),
    ]
    events = rr.new_events_by_symbol(actions, after=date(2026, 7, 28))
    assert events == {"TCS": ["Bonus 1:1 @ 2026-07-29"]}


def test_with_no_sealed_scope_end_nothing_is_new() -> None:
    """Silence beats a guessed cut-off -- the class simply never fires."""
    actions = [_Action("TCS", date(2026, 7, 29), " Bonus 1:1")]
    assert rr.new_events_by_symbol(actions, after=None) == {}


def test_duplicate_event_rows_collapse() -> None:
    actions = [_Action("TCS", date(2026, 7, 29), " Bonus  1:1")] * 3
    assert rr.new_events_by_symbol(actions, after=date(2026, 7, 28)) == {
        "TCS": ["Bonus 1:1 @ 2026-07-29"]
    }


# --- the independent store leg ----------------------------------------------------------------


@dataclass(frozen=True)
class _Bar:
    symbol: str
    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


def _day(symbol: str, day: date) -> _Bar:
    return _Bar(symbol, datetime(day.year, day.month, day.day, 9, 15), 100, 101, 99, 100, 10)


@pytest.fixture
def store(tmp_path: Path) -> MinuteStore:
    return MinuteStore.at(tmp_path / "minute_store")


def test_measure_store_splits_at_the_sealed_scope_end(store: MinuteStore) -> None:
    store.write_bars("TCS", [_day("TCS", date(2026, 7, 27)), _day("TCS", date(2026, 7, 28))])
    store.write_bars("TCS", [_day("TCS", date(2026, 7, 30))])
    measured = rr.measure_store(store, ["TCS"], scope_end=date(2026, 7, 28))
    assert measured["TCS"].days_in_scope == 2  # drift is measured on these
    assert measured["TCS"].days_beyond == 1  # growth, reported separately
    assert measured["TCS"].first_day == date(2026, 7, 27)


def test_measure_store_with_no_scope_end_counts_everything(store: MinuteStore) -> None:
    store.write_bars("TCS", [_day("TCS", date(2026, 7, 30))])
    measured = rr.measure_store(store, ["TCS"], scope_end=None)
    assert (measured["TCS"].days_in_scope, measured["TCS"].days_beyond) == (1, 0)


def test_a_symbol_with_no_parquet_directory_measures_zero(store: MinuteStore) -> None:
    measured = rr.measure_store(store, ["ABSENT"], scope_end=date(2026, 7, 28))
    assert measured["ABSENT"] == rr.StoreMeasurement("ABSENT", 0, 0, None)


def test_a_report_claiming_depth_the_store_cannot_show_is_a_CONTRADICTION() -> None:
    rebuilt = facts([("TCS", 100, 98, 100, "settled")])
    checks = rr.cross_check_store(rebuilt, {"TCS": rr.StoreMeasurement("TCS", 0, 0, None)})
    assert len(checks) == 1 and checks[0].contradiction


def test_a_plain_count_difference_is_reported_but_does_not_block() -> None:
    """The report's Days column counts from the symbol's clamp; that semantic is not fought."""
    rebuilt = facts([("TCS", 100, 98, 100, "settled")])
    checks = rr.cross_check_store(rebuilt, {"TCS": rr.StoreMeasurement("TCS", 97, 0, None)})
    assert len(checks) == 1 and not checks[0].contradiction


def test_an_agreeing_store_produces_no_check_rows() -> None:
    rebuilt = facts([("TCS", 100, 98, 100, "settled")])
    assert rr.cross_check_store(rebuilt, {"TCS": rr.StoreMeasurement("TCS", 100, 5, None)}) == []


# --- rendering and the verdict ------------------------------------------------------------------


def _render(sealed_rows, rebuilt_rows, *, events=None, measured=None, checks=()) -> str:
    sealed_facts = facts(sealed_rows)
    rebuilt_facts = facts(rebuilt_rows)
    divergences = rr.reconcile(sealed_facts, rebuilt_facts, new_events=events or {})
    return "\n".join(
        rr.render(
            sealed=sealed_facts,
            rebuilt=rebuilt_facts,
            divergences=divergences,
            measured=measured or {},
            checks=checks,
            ca_rows=41_351,
        )
    )


def test_a_clean_reconciliation_says_amendment_payload_not_defect() -> None:
    text = _render(BASE, BASE)
    assert "ZERO UNEXPLAINED DIVERGENCES" in text
    assert "v1.5" in text and "the architect's" in text
    assert "DEFECT" not in text


def test_one_unexplained_divergence_says_DEFECT_and_counts_it() -> None:
    rebuilt = [("TCS", 90, 98, 100, "settled"), ("GAIL", 100, 60, 100, "quarantined")]
    text = _render(BASE, rebuilt)
    assert "1 UNEXPLAINED DIVERGENCE(S) -- DEFECT" in text
    assert "triage before any number is believed" in text


def test_a_contradiction_blocks_the_verdict_entirely() -> None:
    text = _render(BASE, BASE, checks=(rr.StoreCheck("TCS", 100, 0),))
    assert "NO VERDICT" in text
    assert "ZERO UNEXPLAINED" not in text


def test_the_report_prints_the_ruling_and_its_own_classification_rules() -> None:
    text = _render(BASE, BASE)
    assert "unexplained drift is a defect to triage" in text  # the ruling, quoted
    for name in rr.CLASSES:
        assert f"`{name}`" in text
    assert "411,690 / 434,769" in text  # CONTEXT 4.6's sealed sentence, for the eye


def test_growth_beyond_the_sealed_era_is_reported_but_not_a_divergence() -> None:
    measured = {"TCS": rr.StoreMeasurement("TCS", 100, 42, date(2016, 10, 3))}
    text = _render(BASE, BASE, measured=measured)
    assert "42 stored symbol-day(s) fall after the sealed scope end" in text
    assert "ZERO UNEXPLAINED DIVERGENCES" in text


def test_the_per_symbol_table_carries_one_sided_symbols_too() -> None:
    text = _render(BASE, BASE[:1] + [("NEWCO", 50, 50, 50, "settled")])
    assert "| NEWCO | absent | 50 |" in text
    assert "| GAIL | 100 | absent |" in text


def test_the_headline_table_shows_both_eras_and_the_delta() -> None:
    text = "\n".join(
        rr.render(
            sealed=rr.parse_backfill_report(build_report(BASE, coverage=(400, 500))),
            rebuilt=rr.parse_backfill_report(build_report(BASE, coverage=(410, 505))),
            divergences=(),
            measured={},
            checks=(),
            ca_rows=0,
        )
    )
    assert "| 400 | 410 | +10 |" in text
    assert "+1.1881 pp" in text  # 410/505 = 81.1881% less 400/500 = 80.0000%


# --- the CLI's refusals -------------------------------------------------------------------------


def test_the_cli_refuses_without_a_rebuilt_report(tmp_path: Path, capsys) -> None:
    code = rr.main(["--sealed", str(SEALED), "--rebuilt", str(tmp_path / "nope.md")])
    assert code == 2
    assert "runbook step 4" in capsys.readouterr().out


def test_the_cli_refuses_without_a_minute_store(tmp_path: Path, capsys) -> None:
    """It runs ON the rebuilt stores; it cannot be answered from the reports alone."""
    rebuilt = tmp_path / "rebuilt.md"
    rebuilt.write_text(build_report(BASE), encoding="utf-8")
    code = rr.main(
        [
            "--sealed", str(SEALED),
            "--rebuilt", str(rebuilt),
            "--data-dir", str(tmp_path / "empty"),
        ]
    )
    assert code == 2
    assert "No minute store" in capsys.readouterr().out
