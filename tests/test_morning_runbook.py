"""THE MORNING RUNBOOK STUB (chunk 14), checked against the code it describes.

An operator card is a document that goes stale silently: a flag is renamed, a banner is
reworded, and the card still reads perfectly while telling somebody the wrong thing at 08:50 on
a live morning. So the card's checkable claims are checked here -- every command it prints must
parse against the shipped CLI, every flag it names must exist, and every sentence it quotes from
the code must still be that sentence.

Chunk 15 owns the FULL runbook (the dry-run week, the debrief, the incident log); this is the
stub the chunk-14 card asks for, and these tests are what keep the stub honest until then.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
from pathlib import Path

from acumen import live_screener as ls
from acumen import run_screener
from acumen import telegram_sink as tg

REPO = Path(__file__).resolve().parents[1]
RUNBOOK = REPO / "docs" / "morning_runbook_stub.md"


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_the_runbook_exists_and_fits_on_one_screen() -> None:
    """The card's own constraint: *"a card that scrolls is a card nobody reads at 08:50"*."""
    assert RUNBOOK.is_file(), "chunk 14's card requires the stub to be committed under docs/"
    text = _text()
    assert "THIS TOOL PLACES NO ORDERS" in text, "the rule with real money behind it, first"
    assert len(text.splitlines()) < 200, "a stub, not a manual -- chunk 15 owns the full one"
    assert text.isascii(), "ASCII-only, like every other source file in this repo"


def test_every_command_the_runbook_prints_PARSES_against_the_shipped_CLI() -> None:
    """No invented flag, no renamed one, and the placeholder is a placeholder.

    The card is the operator's copy-paste source, so a flag it names that argparse does not know
    is a morning that dies at the first command.
    """
    commands = [
        line.strip() for line in _text().splitlines()
        if line.strip().startswith("python -m acumen.run_screener")
    ]
    assert len(commands) >= 3, "the pre-open check, the dry run and the live-alerts run"
    for command in commands:
        argv = command.split()[3:]                     # drop `python -m acumen.run_screener`
        argv = [part.replace("<TODAY>", "2026-06-10") for part in argv]
        args = run_screener.parse_args(argv)           # raises SystemExit on an unknown flag
        assert args.mode == "live", command
        assert args.day == "2026-06-10", command
    assert any(a.split() and "--preflight-only" in a for a in commands)
    assert any("--live-alerts" in a for a in commands), "the flag that makes the phone ring"
    assert sum("--telegram" in a for a in commands) == 2


def test_the_runbook_quotes_the_CODE_and_not_a_paraphrase_of_it() -> None:
    """Every sentence the card puts in the operator's eye is the one the code will print."""
    text = _text()

    # CONTEXT 4.7's disclosed line, byte for byte.
    assert ls.LIVE_DISCLOSURE in text

    # The two markers that qualify a price (REVIEW_13B Q1 / B357).
    assert "this price stands on a window the screener cannot vouch for" in text
    assert ls.stale_note(0).split("--")[1].strip() in text
    assert ls.POC_PROVISIONAL in text

    # The banner's three phrases, from `_settle_banner`.
    for phrase in ("never answered", "are stale", "hit its hard deadline"):
        assert phrase in text, phrase

    # The two Telegram banners, from the sink's own constants.
    assert tg.FAILURE_BANNER.split("(")[0].strip() in text
    assert tg.REFUSED_BANNER in text

    # The end-of-day summary the morning now ends with (the architect's 14-Aug-2026 ruling):
    # its heading, and the event kind whose presence in the recording is why a restart does not
    # send a second one. Both from the sink's own constants, so a rename cannot leave the card
    # describing a message that no longer looks like that.
    assert tg.SUMMARY_HEADING in text
    assert tg.SUMMARY_EVENT in text

    # The measured residual bracket, as a number rather than an adjective.
    assert "0.5229%" in text and "2.6808%" in text

    # The quarantined six, named (CONTEXT 4.7 / Q-30).
    for symbol in ("APLAPOLLO", "ASTRAL", "IEX", "NTPC", "UPL", "VBL"):
        assert symbol in text, symbol
    assert "204" in text, "the settled universe the screener alerts on"


def test_the_runbook_names_the_recording_layout_that_really_exists() -> None:
    """What the card tells an operator to keep must be what the recording actually writes."""
    from acumen import live_recording as rec

    text = _text()
    for name in (rec.MANIFEST_NAME, rec.BIAS_NAME, rec.STATE_NAME, rec.ALERTS_NAME,
                 rec.EVENTS_NAME, rec.CANDLES_DIRNAME):
        assert name in text, name
    assert "dashboard.html" in text


def test_the_preflight_lines_the_runbook_tells_the_operator_to_READ_exist() -> None:
    """Each row of the card's preflight table names a line the preflight really prints."""
    source = Path(run_screener.__file__).read_text(encoding="utf-8")
    for label in ("instrument master", "symbols", "biases resolved", "gate battery",
                  "calendar", "corporate actions", "telegram", "alerts", "EXCLUDED"):
        # The preflight pads its labels to a fixed column, so the label is followed by at least
        # two spaces in the source. Matching on that is what tells a LABEL apart from the same
        # words appearing in a sentence.
        assert re.search(rf'"{label} {{2,}}', source), (
            f"the card tells the operator to read a preflight line called {label!r}"
        )
