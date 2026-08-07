"""REVIEW_12C reviewer probes -- the REVIEW_12_2 FIX re-review.

Probes the fix session did not write, kept in the repo per `personas/quant_reviewer.md` step 4
and `personas/code_reviewer.md` step 4. All four close ONE gap, and it is the gap
`personas/code_reviewer.md` checklist item 10 exists for (the architect's 06-Aug-2026 ruling
(2), the M1/M6 pattern): **a rendering fix must be pinned at the RENDERED OUTPUT, not only at
the helper that computes it.**

Three of the REVIEW_12_2 fix's four page-text changes were pinned only at their helper --
`_rule_words` for Q2's relabel, `PointsTotals` for Q3's flat-trade sentence, `format_points`
for C7's signed zero. Measured by this review rather than argued: reverting Q2's label in the
committed page, deleting Q3's sentence from BOTH committed documents, and stripping the seven
signed zeros back to unsigned zeros each leaves the whole suite GREEN. Q3 is worse than the
other two -- deleting its two `emit.add` blocks from the GENERATOR is green as well, so the
fix is revertible at both levels. Only Q1's page-5 paragraph was pinned on the page itself.

These four probes read the COMMITTED documents -- the ones the trader actually receives -- and
turn red on exactly those mutations. They are green as committed: the documents are correct
today, and what was missing was the guard, not the fix.

Offline: every probe reads committed files in this repository and no store.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "docs/validation/trader_pack.md"
COMPANION = REPO / "docs/validation/trader_pack.json"
POINTS_TABLE = REPO / "docs/reports/points_by_symbol.md"

#: A row of the 204-stock companion table, by the columns it prints:
#: ``| # | Stock | Trades | Trades positive | Points | Points a trade | ... |``
_ROW = re.compile(r"^\| (\d+) \| ([A-Z0-9&\-.]+) \|")


def _figures() -> dict:
    return json.loads(COMPANION.read_text(encoding="utf-8"))["figures"]


def _table_rows() -> list[list[str]]:
    """The committed points table as its reader sees it: one list of cells per printed row."""
    rows = []
    for line in POINTS_TABLE.read_text(encoding="utf-8").splitlines():
        if not _ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 11:
            rows.append(cells)
    return rows


def test_page_5s_no_data_row_names_the_DAILY_pair_ON_THE_PAGE_ITSELF() -> None:
    """REVIEW_12_2 finding Q2, pinned where the trader reads it.

    The fix pins the wording at `trader_pack._rule_words`. That catches a change to the helper
    and nothing else: the row could revert on the page -- the SECOND-LARGEST row of the table --
    with the suite green, because the only probe that reads the printed table selects rows by
    the words *not judged*, which both the right label and the wrong one contain.

    `bias_engine` emits this rule when `store.daily(...)` has no candle for D-1 or D-2 (the
    DAILY store, on the bias PAIR days, per CONTEXT 3.2). The old label said *"no stored
    one-minute data for the stock that day"* -- the wrong store, the wrong resolution and the
    wrong day, all three.
    """
    page = PACK.read_text(encoding="utf-8")
    counts = _figures()["counts"]
    printed = counts["bias_rules"]["no-data"]
    row = next((line for line in page.splitlines()
                if line.startswith("| ") and line.rstrip().endswith(f"| {printed:,} |")
                and "not judged" in line), None)
    assert row is not None, "the no-data row is on the page with the companion's own count"
    assert "DAILY" in row and "bias pair" in row, (
        "the trader's page names the DAILY store and the bias pair, which is what the rule means"
    )
    assert "one-minute" not in row and "that day" not in row, (
        "and it no longer names the one-minute store or the trade day, which it never meant"
    )


def test_page_7_AND_its_companion_state_the_FLAT_trades_on_the_page_itself() -> None:
    """REVIEW_12_2 finding Q3, pinned where the trader reads it -- on BOTH documents.

    The fix pins `PointsTotals.flat` and `.symbols_with_a_flat` in the dataclass. Nothing read
    the rendered sentence, so both `emit.add` blocks could be deleted from the generator, and
    the sentence itself deleted from both committed documents, with the suite green. Measured,
    not argued (REVIEW_12C finding M1).

    The figures are taken from the companion rather than typed, so this probe cannot drift from
    the document it guards, and the win-rate identity is asserted the way page 7 states it:
    positives + flats + negatives is every trade, and the rate's denominator is all of them
    (CONTEXT 7-E13's one denominator).
    """
    points = _figures()["points"]
    flat, with_a_flat = points["flat"], points["symbols_with_a_flat"]
    trades, winners, symbols = points["trades"], points["winners"], points["symbols"]
    assert flat > 0 and 0 < with_a_flat <= symbols

    pack = PACK.read_text(encoding="utf-8")
    assert f"{flat:,} trades ended exactly level in points" in pack, (
        "page 7 states its flat trades, as REVIEW_12 Q5 made page 1 state its own"
    )
    assert f"across {with_a_flat:,} of the {symbols:,} stocks" in pack
    assert f"{winners:,} positive out of all {trades:,} trades" in pack, (
        "and it names the denominator of its percentage out loud"
    )

    table = POINTS_TABLE.read_text(encoding="utf-8")
    assert f"**{flat:,} of those trades ended exactly level in points**" in table, (
        "the 204-row companion carries the same count in its own words"
    )
    assert f"{with_a_flat:,} of the {symbols:,} stocks" in table

    # the sentence is true of the table it sits above
    by_symbol = _figures()["points"]["by_symbol"]
    assert sum(one["flat"] for one in by_symbol) == flat
    assert sum(1 for one in by_symbol if one["flat"]) == with_a_flat
    assert sum(one["trades"] for one in by_symbol) == trades


def test_a_points_a_trade_cell_that_rounds_to_zero_KEEPS_its_sign() -> None:
    """REVIEW_12_2 finding C7, pinned in the CELL rather than only in `format_points`.

    The helper's own probe catches a revert of the helper. It does not catch the committed
    document losing the signs, and it does not catch a renderer that quantizes before handing
    the value over -- which is precisely the defect C7 was.

    Read off the committed table: every *Points a trade* cell whose magnitude rounds away must
    still carry a sign, and that sign must be the sign of the row's own *Points* column. Only an
    exact zero may be unsigned, and this run has none (no stock's ten-year points total is
    exactly zero), so the unsigned form must not appear at all.
    """
    rows = _table_rows()
    assert len(rows) == _figures()["points"]["symbols"] > 0

    zeros = [row for row in rows if row[5].endswith("0.00")]
    assert zeros, "this run has rows whose average move rounds away; if it stops, re-measure"
    for row in zeros:
        symbol, points, per_trade = row[1], row[4].strip("*"), row[5]
        assert per_trade[0] in "+-", (
            f"{symbol}: a rounded-away average still shows which way it went, not a bare zero"
        )
        assert Decimal(points.replace(",", "")) != 0, f"{symbol}: an exact zero would be neither"
        assert per_trade[0] == ("-" if Decimal(points.replace(",", "")) < 0 else "+"), (
            f"{symbol}: the sign of the average is the sign of its own points total"
        )


def test_the_overlap_days_page_5_counts_are_NAMED_on_the_traders_page() -> None:
    """The architect's Q-26 ruling of 07-Aug-2026, pinned.

    His words: *"the report stays FROZEN; the committed evidence file is the technical record
    and the pack's clause is its pointer"*. So the clause on page 5 is where the boundary case
    is published, and nothing else guards it: the fix's own clause test renders
    `_render_bias_overlap_clause` over synthetic rows and never reads the committed page.

    Every specific is taken from the companion -- the count, the stock and both dates -- so this
    probe pins the page against the data it was built from rather than against a memory of this
    run.
    """
    counts = _figures()["counts"]
    overlap = counts["bias_rules_judged_inside_the_not_judged_rows"]
    days = counts["bias_rules_judged_inside_the_not_judged_rows_days"]
    assert overlap == len(days) > 0

    page = PACK.read_text(encoding="utf-8")
    assert f"those two groups overlap by {overlap:,} days" in page
    for symbol in {row[1] for row in days}:
        assert symbol in page, f"{symbol} carries an overlap day and is not named on the page"
    assert not any(row[3] for row in days), (
        "none of the overlap days traded on this run; if one ever does, the clause says so and "
        "this probe must be re-read rather than edited"
    )
    assert "none of them ended up taking a trade" in page

    # the arithmetic the clause exists to make honest
    ruled, usable = counts["bias_rules_total"], _figures()["limits"]["usable"]
    not_judged, then_refused = counts["bias_rules_not_judged"], counts["bias_rules_then_refused"]
    assert usable + not_judged + then_refused == ruled
    assert f"is {then_refused + overlap:,}" in page, (
        "and the larger population the clause discloses is printed, not left to be inferred"
    )
