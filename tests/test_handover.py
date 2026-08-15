"""THE OPERATOR HANDOVER (chunk 15), checked for the things a plain-English document can lie about.

A document written for a non-technical reader is the easiest one in this repository to get
quietly wrong, because nothing about it is executable and its readers cannot check it. What CAN
be checked is checked here:

* every file it points the trader at exists;
* every figure it states is the figure the code and the reviewed reports state;
* it says what the tool is NOT, in the terms CONTEXT section 1 R4 uses;
* and it stays plain English -- no flag, no command, no code path leaks into it, because the
  moment it needs one it has become a second, worse copy of the runbook.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
from pathlib import Path

from acumen import dry_run_readiness as gate
from acumen import live_screener as ls

REPO = Path(__file__).resolve().parents[1]
HANDOVER = REPO / "docs" / "handover.md"


def _text() -> str:
    return HANDOVER.read_text(encoding="utf-8")


def test_the_handover_exists_and_is_plain_english() -> None:
    """No command, no flag, no module path. The runbook is the operator's; this is the trader's.

    Two documents that both try to be the procedure is how one of them goes stale, and the one
    that goes stale is always the one nobody runs.
    """
    assert HANDOVER.is_file()
    text = _text()
    assert text.isascii()
    for technical in ("python ", "--mode", "--live-alerts", "--refresh", "argparse",
                      "pytest", "def ", "import "):
        assert technical not in text, f"{technical!r} belongs in the runbook, not here"
    # ...and it is a document a person reads in one sitting, not a manual.
    assert 100 < len(text.splitlines()) < 400


def test_it_says_what_the_tool_is_NOT_before_anything_clever() -> None:
    """CONTEXT section 1 R4 is the sentence with real money behind it, and it comes early."""
    text = _text()
    assert "It does not trade" in text
    assert "has never placed an order and it cannot place one" in text
    assert "it alerts; you trade." in text.lower() or "it alerts; you trade" in text
    assert "read-only at the broker" in text
    # early: inside the first third of the document.
    position = text.index("It does not trade")
    assert position < len(text) / 3, "the rule with money behind it is not on page four"


def test_the_THREE_PATHS_are_the_packs_own_three_and_the_chosen_one_is_named() -> None:
    """The three the handover lists are read OUT OF THE PACK, not out of the handover.

    **REVIEW_15 Q1.** This test used to assert the handover's own three headings and never open
    the pack -- so it certified that the document agreed with itself, which it did, while the
    document named three paths the pack never offered (*Stop here / the complete tool /
    Automation*, with the pack's *Change it* dropped and automation invented). That is the
    REVIEW_14 B2 / M1-M6 shape, and the sixth time this repository has pinned a claim at the
    place that makes it rather than at its source. So the source is the pack: its own section
    heading, its own three bolded options, parsed here and required of the handover.
    """
    text = _text()
    pack = (REPO / "docs" / "validation" / "trader_pack.md").read_text(encoding="utf-8")

    assert "### Three ways forward" in pack, "the pack's own section, by its own heading"
    forward = pack.split("### Three ways forward", 1)[1].split("\n## ", 1)[0]
    offered = re.findall(r"^\*\*(.+?)\*\*", forward, flags=re.MULTILINE)
    assert len(offered) == 3, f"the pack offers three ways forward, not {len(offered)}: {offered}"

    for option in offered:
        assert f"**{option}**" in text, (
            f"the pack offers {option!r} and the handover does not carry it -- the trader is "
            "being shown a set of choices that is not the set he was given"
        )
    # ...and each of them is a numbered item of the handover's own list, in the pack's order.
    positions = [text.index(f"**{option}**") for option in offered]
    assert positions == sorted(positions), f"the handover reorders the pack's three: {offered}"

    # The delivered path is NAMED as the delivered one, and it is the pack's third.
    assert offered[2].startswith("Take it live"), offered
    assert "This is the path being delivered" in text
    delivered = text.index("This is the path being delivered")
    assert positions[2] < delivered < text.index("**Automation was never one of the three.**"), (
        "the 'this is the one' sentence must sit under the option it is about"
    )

    # Automation is stated as what it is -- a v2 backlog item -- and NOT as a fourth path the
    # pack offered. It is the half of the old paragraph that was true and load-bearing.
    assert "Automation" not in forward, "automation was never one of the pack's three"
    assert "**Automation was never one of the three.**" in text
    assert "explicitly *not* built" in text
    assert "v2 conversation" in text and "plan's own backlog" in text


def test_every_figure_it_states_is_the_one_the_code_and_the_reports_state() -> None:
    """A plain-English document is still a document of record. Its numbers are checked."""
    text = _text()
    assert str(gate.SETTLED_UNIVERSE_SIZE) in text, "the 204 it screens"
    assert "Rs 1,000" in text, "CONTEXT 3.5's risk per trade, in rupees"
    assert "0.52%" in text and "2.68%" in text, (
        "the measured residual bracket, rounded for a human but not softened"
    )
    assert ls.LIVE_DISCLOSURE in text, "CONTEXT 4.7's sentence, quoted exactly"
    # the boundaries of the session, in the trader's terms
    for stamp in ("09:15", "11:15", "11:30", "15:00", "15:15", "15:30"):
        assert stamp in text, stamp
    # chunk 14's parity result, as the review recorded it
    assert "fifteen" in text and "fourteen" in text, (
        "15 days, 14 judged and matched, 1 disclosed -- in words, and honest about the fifteenth"
    )


def test_every_document_it_points_the_trader_at_EXISTS() -> None:
    """A handover whose 'where everything lives' table names a missing file is worse than none."""
    text = _text()
    cited = set(re.findall(r"`([A-Za-z0-9_./]+\.md)`", text))
    assert cited, "it really does point at documents"
    for relpath in sorted(cited):
        assert (REPO / relpath).is_file(), f"the handover cites {relpath}, which does not exist"
    for expected in ("docs/morning_runbook.md", "docs/reports/chunk9b_backtest_report.md",
                     "docs/validation/trader_pack.md", "CONTEXT.md"):
        assert f"`{expected}`" in text, expected


def test_it_states_the_ONE_limitation_without_flattering_it() -> None:
    """The live/backtest difference is disclosed as a RANGE, not as its narrow end."""
    text = _text()
    assert "no way to check today's data against the exchange's official record" in text
    assert "between 0.52% and 2.68%" in text
    assert "not the flattering end of it" in text
    assert "withdrawn" in text, "and what happens to an alert the next morning refuses"


def test_it_tells_the_trader_what_SILENCE_means() -> None:
    """The safety rail, in the trader's own terms: three silences, and how to tell them apart."""
    text = _text()
    assert "nothing fired" in text
    assert "something is broken" in text
    assert "the tool has stopped" in text
    assert "every day, whether or not anything fired" in text
    assert "If 15:30 comes and no message arrives" in text
