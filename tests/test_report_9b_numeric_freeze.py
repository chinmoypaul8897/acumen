"""The FINAL-EDITS claim, as a test: NO NUMBER IN SECTIONS 1..9 OF THE REPORT MOVED.

The session of 06-Aug-2026 publishes the architect's Q-23 ruling in section 10 and makes the six
presentational corrections REVIEW_9B_REPORT asks for (Q1, Q3, Q4, Q5, Q6, Q7). Section 10 changes
by design. Everything above it must not, and "must not" asserted in a commit message is worth
nothing -- so every numeric token of sections 1 through 9 of the PRE-EDIT report is frozen in
`docs/evidence/chunk9b_report_numeric_baseline.json` (taken from the committed file through
`git show`, so a regeneration cannot move the thing it is compared against) and re-extracted here
from the regenerated file.

The six corrected lines are excluded on BOTH sides -- a correction that changed nothing would not
be one -- and the exclusion is SCOPED to the section it belongs to, so it cannot quietly swallow
an untouched line that happens to share a word. This test also asserts, in the other direction,
that each correction is actually PRESENT in the regenerated report: a freeze that passed on a
report where the edits never landed would be measuring nothing.

Offline: it reads two files inside the repository and no store.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PY = REPO_ROOT / "docs" / "evidence" / "chunk9b_report_numeric_baseline.py"
BASELINE_JSON = REPO_ROOT / "docs" / "evidence" / "chunk9b_report_numeric_baseline.json"
REPORT = REPO_ROOT / "docs" / "reports" / "chunk9b_backtest_report.md"


def _baseline_module():
    """The generator's own extraction code, so both sides are tokenised identically."""
    spec = importlib.util.spec_from_file_location("chunk9b_numeric_baseline", BASELINE_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_every_numeric_token_of_sections_1_to_9_is_UNCHANGED_by_the_final_edits() -> None:
    """2,457 tokens, in order. One moved figure anywhere above section 10 turns this red."""
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    module = _baseline_module()
    tokens = module.numeric_tokens(REPORT.read_text(encoding="utf-8"))

    frozen = baseline["tokens"]
    assert baseline["token_count"] == len(frozen) > 0
    if tokens != frozen:  # pragma: no cover -- only on a real regression
        differ = [i for i, (a, b) in enumerate(zip(tokens, frozen)) if a != b]
        first = differ[0] if differ else min(len(tokens), len(frozen))
        raise AssertionError(
            f"a number in sections 1..9 moved: {len(tokens)} tokens now against "
            f"{len(frozen)} frozen; first difference at index {first}: "
            f"{tokens[first: first + 6]} vs {frozen[first: first + 6]}"
        )


def test_the_frozen_baseline_covers_the_whole_of_sections_1_to_9() -> None:
    """The freeze must be over the real thing: nine sections, and only five excluded lines."""
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    module = _baseline_module()
    lines = module.sections_1_to_9(REPORT.read_text(encoding="utf-8"))

    assert {section for section, _ in lines} == set(range(1, 10)), (
        "the baseline must span sections 1 through 9 of the regenerated report"
    )
    assert baseline["lines_excluded_as_edited"] == 8, (
        "the PRE-EDIT report has exactly eight lines the corrections rewrite: FIVE from the "
        "final-edits session (section 5's `Worst year` row goes through the same renderer but "
        "comes out byte-identical, so it is COMPARED, not excluded) and THREE from the Round-4 "
        "execution session, where the trader's own answers retire the Q43 flag sentence, confirm "
        "Q44 and relabel the config row. A ninth means the exclusion list grew again, and an "
        "exclusion list that grows is how a moved number hides"
    )
    assert baseline["ref"] == module.DEFAULT_REF


def test_each_of_the_six_corrections_is_PRESENT_in_the_regenerated_report() -> None:
    """The other direction. A freeze that passes on an unedited report measures nothing."""
    module = _baseline_module()
    lines = module.sections_1_to_9(REPORT.read_text(encoding="utf-8"))

    def present(where: int, marker: str) -> bool:
        return any(section == where and marker in line for section, line in lines)

    assert present(1, "ALL THREE GATES, not the price gate alone"), "Q4"
    assert present(4, "**Concurrency, and which convention the headline uses.**"), "Q7"
    assert present(5, "**a PARTIAL year**"), "Q3"
    assert present(5, "FULL year is"), "Q3"
    assert present(6, "% of notional -- RANGE across the tied trades"), "Q5"
    assert present(6, "the fences do NOT"), "Q1"
    assert present(6, "the fences do sit outside the band"), "Q1"
    assert not present(6, "% of its own notional"), "Q5: the ill-defined rows are gone"
    assert not present(6, "and the fences sit outside it"), "Q1: the blanket claim is gone"

    # ...and the same in both directions for the three Round-4 lines (06-Aug-2026)
    assert present(1, "The capital-infeasibility FLAGS are RETIRED, not pending."), "Round 4"
    assert present(1, "**Q44 is CONFIRMED (the trader, Round 4, 06-Aug-2026).**"), "Round 4"
    assert present(2, "| retired by trader, Round 4 |"), "Round 4"
    assert not present(1, "**Q44 is unconfirmed.**"), "Round 4: the pending claim is gone"
    assert not present(2, "| trader Q43 PENDING |"), "Round 4: so is the pending config label"
    assert present(1, "PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)"), (
        "the run's own stamp is still quoted verbatim -- the manifest is frozen and says what "
        "it said; what changed is the sentence around the quotation"
    )


def test_the_ruled_benchmark_and_the_Q6_base_are_published_where_they_belong() -> None:
    """Section 10 and section 11b are the two places the edits are ALLOWED to move numbers."""
    text = REPORT.read_text(encoding="utf-8")
    section_10 = text.split("\n## 10. ")[1].split("\n## 11. ")[0]
    assert "THE BENCHMARK -- share-count events only (bonus / split / rights)" in section_10
    assert "Q-23 CLOSED" in section_10
    assert section_10.count("(NOT the benchmark)") == 2
    assert "neither published" not in text and "Q-23 open" not in text

    section_11b = text.split("### 11b.")[1].split("\n## 12.")[0]
    assert "Days with a counterfactual" in section_11b
    assert "the measured base is the `Days with a counterfactual` column" in section_11b
