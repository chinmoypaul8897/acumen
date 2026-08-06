"""Freeze every numeric token of sections 1..9 of the chunk-9B report, BEFORE the final edits.

The FINAL-EDITS session (06-Aug-2026) publishes the architect's Q-23 ruling in section 10 and
makes six presentational corrections. The claim that goes with it is that **no number in sections
1 to 9 moves**. A claim like that is worth nothing asserted, so it is frozen here and re-checked
by a test the suite runs from a bare clone (`tests/test_report_9b_numeric_freeze.py`).

    python docs/evidence/chunk9b_report_numeric_baseline.py [<git-ref>]

The baseline is taken from the COMMITTED report as of `<git-ref>` (default: the last commit that
touched it before this session, resolved below), read through `git show` so that regenerating the
file cannot change what it was compared against. It writes exactly one JSON file beside this
script and touches nothing else. No store is read at all.

**What is compared.** Every numeric token -- integers, decimals, thousands-separated groups,
percentages, dates and clock stamps -- appearing on any line of sections 1 through 9, in order,
as a list. Section 10 is excluded because the ruling changes it by design, and the lines the six
corrections rewrite are excluded on BOTH sides by the markers in :data:`EDITED_LINE_MARKERS`:
those lines are the corrections, and a correction that changed nothing would not be one. Every
other line of sections 1..9 must produce exactly the same tokens in exactly the same order.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPORT_RELPATH = "docs/reports/chunk9b_backtest_report.md"
OUT = Path(__file__).with_suffix(".json")

#: The commit the baseline is taken from: `chunk9B: THE REPORT reviewed PASS`, the head of the
#: reviewed arc and the last state of the file before the final edits.
DEFAULT_REF = "3cbfafa"

#: A numeric token: a date, a clock stamp, or any digit group with its separators and sign.
TOKEN = re.compile(r"-?\d[\d,:.\-]*\d|\d")

#: The lines the six presentational corrections rewrite, as (section number, substring). Scoped
#: to a SECTION on purpose: an unscoped `price-proven` would also swallow section 9's own
#: paragraph and the B149 caveat, which this session does not touch and which carry numbers of
#: their own -- an exclusion list that quietly covers unedited lines is not a freeze. A line is
#: dropped from the comparison on the baseline and on the new file alike; everything else in
#: sections 1..9 must be token-identical, in order.
EDITED_LINE_MARKERS: tuple[tuple[int, str], ...] = (
    (1, "price-proven"),                            # Q4: section 1's gates sentence
    (4, "**Concurrency, and which convention"),     # Q7: the new definitions bullet
    (5, "| Best year |"),                           # Q3: section 5's extreme-year rows
    (5, "| Worst year |"),                          # Q3
    (6, "% of its own notional"),                   # Q5: the old single-trade percentage rows
    (6, "% of notional -- RANGE"),                  # Q5: the rows that replace them
    (6, "percent-of-notional rows carry a RANGE"),  # Q5: the paragraph explaining them
    (6, "fixed-R strategy bounds its own trades"),  # Q1: section 6a's closing claim
    (6, "the fences do sit outside the band"),      # Q1: the per-column bullets replacing it
    (6, "the fences do NOT"),                       # Q1
    (6, "An outlier count is therefore a statement"),   # Q1: the sentence that follows them
)

SECTION = re.compile(r"^## (\d+)\. ")
FIRST_SECTION = 1
LAST_SECTION = 9


def sections_1_to_9(text: str) -> list[tuple[int, str]]:
    """(section number, line) from the section-1 heading up to (not including) section 10's."""
    out: list[tuple[int, str]] = []
    current: int | None = None
    for line in text.splitlines():
        match = SECTION.match(line)
        if match:
            current = int(match.group(1))
        if current is None or not (FIRST_SECTION <= current <= LAST_SECTION):
            continue
        out.append((current, line))
    return out


def is_edited(section: int, line: str) -> bool:
    return any(section == where and marker in line for where, marker in EDITED_LINE_MARKERS)


def numeric_tokens(text: str) -> list[str]:
    """Every numeric token of sections 1..9, in order, with the edited lines dropped."""
    tokens: list[str] = []
    for section, line in sections_1_to_9(text):
        if is_edited(section, line):
            continue
        tokens.extend(TOKEN.findall(line))
    return tokens


def committed_report(ref: str) -> str:
    blob = subprocess.run(
        ["git", "show", f"{ref}:{REPORT_RELPATH}"],
        cwd=REPO, check=True, capture_output=True,
    ).stdout
    return blob.decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ref = argv[0] if argv else DEFAULT_REF
    text = committed_report(ref)
    lines = sections_1_to_9(text)
    tokens = numeric_tokens(text)
    payload = {
        "_note": (
            "Numeric tokens of sections 1..9 of docs/reports/chunk9b_backtest_report.md as "
            f"committed at {ref}, with the lines the FINAL-EDITS corrections rewrite excluded "
            "by marker. Regenerated by docs/evidence/chunk9b_report_numeric_baseline.py and "
            "checked by tests/test_report_9b_numeric_freeze.py. FROZEN: a token that moves is "
            "a number that moved."
        ),
        "ref": ref,
        "report": REPORT_RELPATH,
        "lines_in_sections_1_to_9": len(lines),
        "lines_excluded_as_edited": sum(1 for section, line in lines if is_edited(section, line)),
        "edited_line_markers": [list(pair) for pair in EDITED_LINE_MARKERS],
        "token_count": len(tokens),
        "tokens": tokens,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} -- {len(tokens):,} tokens over {len(lines):,} lines "
          f"({payload['lines_excluded_as_edited']} excluded as edited)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
