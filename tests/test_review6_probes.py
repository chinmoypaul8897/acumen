"""REVIEW_6 reviewer probes -- tripwires the chunk-6 build left open, plus an independent F6.

Kept in the repo per the review personas' step 4 ("write NEW tests the builder didn't think
of; keep the good ones"). Each test here was written against a MUTANT that survived the
chunk-6 suite, or rebuilds a golden from the spec text without reusing the builder's reading:

1. :func:`test_no_src_module_passes_a_literal_row_size_or_tick_paise` -- two mutants survived
   ``tests/test_poc.py`` + ``tests/test_poc_evidence.py``: replacing
   ``row_size=config.row_size`` with ``row_size=24`` and
   ``tick_paise=master.instrument(symbol).tick_size_paise`` with ``tick_paise=5`` inside
   :func:`acumen.poc_evidence.run`. Both are exactly what CONTEXT 3.3/4.3 forbid ("NEVER
   hardcode 0.05"; N comes from config) and neither was covered, because ``run()``'s wiring is
   never exercised past its offline refusal.
2. :func:`test_total_ticks_rounds_half_even_and_not_by_truncation` -- decision B114 states the
   rounding MODE for ``totalTicks``; truncating instead survived the suite, because the only
   off-grid fixture asserts volume conservation, which holds in both rounding directions.
3. :func:`test_f6_rebuilt_from_the_spec_on_ticks_outside_the_frozen_fixture` -- CONTEXT 8 F6
   rebuilt from CONTEXT 3.3's sentences at tick sizes that appear in no fixture (1 paise and
   25 paise), asserting edges, the remainder shape, contiguity and midpoints at BOTH N values.
4. :func:`test_the_tpr_tie_is_reconstructed_independently_of_the_engine` -- the Q-13 tie
   arithmetic, recomputed from the spec's own definition of "realized row count" rather than
   from :func:`acumen.poc.ticks_per_row`, so the interim's direction is pinned by a second
   reading of the spec and not only by the engine's own.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import poc

SRC = Path(__file__).resolve().parents[1] / "src" / "acumen"

#: The two keywords that carry a SPEC constant into the profile engine. CONTEXT 3.3 sources
#: both from outside the code -- N from ``config.yaml``, the tick from the instrument master.
SPEC_CONSTANT_KEYWORDS = ("row_size", "tick_paise")


def test_no_src_module_passes_a_literal_row_size_or_tick_paise() -> None:
    """CONTEXT 3.3/4.3: N comes from config and the tick from the instrument master.

    A literal in either place is silent and plausible -- QUESTIONS.md Q-2 measured that a
    hardcoded 0.05 mis-prices DIXON by rupees while the code still looks right. This probe
    fails on any ``src/`` call site that passes a NUMBER to either keyword. ``tick_paise=None``
    is not a spec constant -- it is the explicit "do not snap to a tick grid" sentinel
    :func:`acumen.minute_unadjust.unadjust_price_paise` takes -- so only numeric literals count.
    """
    offenders: list[str] = []
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg not in SPEC_CONSTANT_KEYWORDS:
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
                    offenders.append(
                        f"{path.name}:{value.lineno} {keyword.arg}={value.value!r}"
                    )
    assert not offenders, "spec constants hardcoded at a call site: " + "; ".join(offenders)


def test_total_ticks_rounds_half_even_and_not_by_truncation() -> None:
    """Decision B114's rounding MODE, pinned.

    ``totalTicks = round((top - bottom) / tick)`` (CONTEXT 3.3). On the tick grid the division
    is exact, so only an OFF-GRID range (a flagged un-adjustment residual) exercises the mode --
    and volume conservation holds in either direction, so nothing else can catch a change here.
    With a 10-paise tick, 15/25/35 paise of range are 1.5/2.5/3.5 ticks:

    * half-even (the decision)  -> 2 / 2 / 4
    * truncation                -> 1 / 2 / 3
    * half-up                   -> 2 / 3 / 4
    """
    assert poc.total_ticks(100_015, 100_000, 10) == 2  # 1.5 -> 2 (truncation would give 1)
    assert poc.total_ticks(100_025, 100_000, 10) == 2  # 2.5 -> 2 (half-up would give 3)
    assert poc.total_ticks(100_035, 100_000, 10) == 4  # 3.5 -> 4 (truncation would give 3)
    # and the spec's own floor still wins over the mode for a sub-tick range
    assert poc.total_ticks(100_004, 100_000, 10) == 1  # 0.4 -> 0, floored to 1 (CONTEXT 3.3)


@pytest.mark.parametrize("tick_paise", [1, 25])
def test_f6_rebuilt_from_the_spec_on_ticks_outside_the_frozen_fixture(tick_paise: int) -> None:
    """CONTEXT 8 F6, rebuilt from CONTEXT 3.3's sentences at ticks no fixture uses.

    "Rows are stacked from bottom upward, each spanning tpr ticks; the leftover ticks (if any)
    form final rows of tpr ticks with the LAST row holding the remainder" -- so at N=30 over
    100 ticks the answer is 33 rows of 3 followed by ONE row of 1, contiguous, reaching exactly
    top; at N=25 it is 25 rows of 4 with no remainder. The builder parametrized F6 over the
    three ticks in ``tests/fixtures/tick_sizes.json``; these two are outside it, so the row
    SHAPE is shown to be tick-independent by a second, independent construction.
    """
    bottom = 1_000_000

    grid30 = poc.build_rows(
        top_paise=bottom + 100 * tick_paise,
        bottom_paise=bottom,
        row_size=30,
        tick_paise=tick_paise,
    )
    assert (grid30.total_ticks, grid30.ticks_per_row, len(grid30.rows)) == (100, 3, 34)
    expected: list[tuple[int, int, int]] = [
        (bottom + 3 * i * tick_paise, bottom + 3 * (i + 1) * tick_paise, 3) for i in range(33)
    ]
    expected.append((bottom + 99 * tick_paise, bottom + 100 * tick_paise, 1))
    assert [(r.lo_paise, r.hi_paise, r.ticks) for r in grid30.rows] == expected
    for lower, upper in zip(grid30.rows, grid30.rows[1:]):
        assert lower.hi_paise == upper.lo_paise, "rows must tile the range with no gap or overlap"
    assert grid30.rows[0].lo_paise == bottom
    assert grid30.rows[-1].hi_paise == bottom + 100 * tick_paise == grid30.top_paise
    assert grid30.rows[0].midpoint_paise == Fraction(2 * bottom + 3 * tick_paise, 2)
    assert grid30.rows[-1].midpoint_paise == Fraction(2 * bottom + 199 * tick_paise, 2)

    grid25 = poc.build_rows(
        top_paise=bottom + 100 * tick_paise,
        bottom_paise=bottom,
        row_size=25,
        tick_paise=tick_paise,
    )
    assert (grid25.ticks_per_row, len(grid25.rows)) == (4, 25)
    assert [r.ticks for r in grid25.rows] == [4] * 25
    assert [(r.lo_paise, r.hi_paise) for r in grid25.rows] == [
        (bottom + 4 * i * tick_paise, bottom + 4 * (i + 1) * tick_paise) for i in range(25)
    ]


def test_the_tpr_tie_is_reconstructed_independently_of_the_engine() -> None:
    """QUESTIONS.md Q-13's interim, re-derived from the spec instead of from the engine.

    CONTEXT 3.3's rule is "direction chosen so the realized row count is closest to requested
    N". Realized count for a candidate height h over T ticks = ``ceil(T / h)`` (full rows plus
    the remainder row). This recomputes both candidates here, asserts the two distances are
    EQUAL (so the case really is the spec's silence and not a decided case), and then asserts
    the engine takes the finer side -- the direction that reproduces all 25 frozen
    ``poc_prorata`` values (the other moves six of them).
    """
    row_size = 24
    ties = [t for t in range(2, 4001) if _is_tie(t, row_size)]
    assert len(ties) > 100, "the tie is common, not a corner case"
    for ticks in ties:
        finer = ticks // row_size
        coarser = -(-ticks // row_size)
        assert finer >= 1 and coarser == finer + 1
        assert poc.ticks_per_row(ticks, row_size) == finer, (
            f"{ticks} ticks at N={row_size}: the Q-13 interim keeps the finer profile"
        )
    # the frozen calibration's six tie days, by their measured tick counts
    for ticks, finer in ((246, 10), (176, 7), (250, 10), (128, 5), (105, 4), (344, 14)):
        assert _is_tie(ticks, row_size)
        assert poc.ticks_per_row(ticks, row_size) == finer


def _is_tie(ticks: int, row_size: int) -> bool:
    """Are both rounding directions EQUALLY close to ``row_size`` realized rows?"""
    finer = ticks // row_size
    coarser = -(-ticks // row_size)
    if finer < 1 or finer == coarser:
        return False
    return abs(-(-ticks // finer) - row_size) == abs(-(-ticks // coarser) - row_size)
