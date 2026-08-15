"""THE MORNING RUNBOOK (chunk 15), checked against the code it describes.

An operator card is a document that goes stale silently: a flag is renamed, a banner is
reworded, and the card still reads perfectly while telling somebody the wrong thing at 08:50 on
a live morning. Nothing about that failure is visible until the morning it costs a trade. So
every checkable claim the runbook makes is checked here:

* every command it prints PARSES against the shipped CLI, and the launcher it names really runs;
* every sentence it quotes from the code is still that sentence, compared to the CONSTANT rather
  than to a copy of the words;
* every preflight line it tells the operator to read exists in the preflight;
* every recording file it tells the operator to keep is one the recording writes;
* every readiness check it tabulates is one of the seven the gate runs.

Chunk 14 shipped a one-screen STUB (``docs/morning_runbook_stub.md``) and this file grew from
the tests that kept it honest; chunk 15 replaces it with the full procedure, and the same
discipline applies to the whole of it.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from acumen import dry_run_readiness as gate
from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import run_screener
from acumen import telegram_sink as tg

REPO = Path(__file__).resolve().parents[1]
RUNBOOK = REPO / "docs" / "morning_runbook.md"
LAUNCHER = REPO / "scripts" / "run_screener.py"


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def _commands() -> list[str]:
    return [
        line.strip() for line in _text().splitlines()
        if line.strip().startswith(("python scripts/run_screener.py",
                                    "python -m acumen.run_screener"))
    ]


def test_the_runbook_exists_and_the_stub_is_GONE() -> None:
    """One operator card, not two. Two documents both claiming to be it is how one goes stale."""
    assert RUNBOOK.is_file(), "chunk 15's card requires the full runbook under docs/"
    assert not (REPO / "docs" / "morning_runbook_stub.md").exists(), (
        "the chunk-14 stub is REPLACED, not kept beside its successor"
    )
    text = _text()
    assert "THIS TOOL PLACES NO ORDERS" in text, "the rule with real money behind it, first"
    assert text.isascii(), "ASCII-only, like every other source file in this repo"
    assert len(text.splitlines()) > 200, "the full procedure, not the one-screen stub"


def test_every_command_the_runbook_prints_PARSES_against_the_shipped_CLI() -> None:
    """No invented flag, no renamed one, and the placeholder is a placeholder.

    The card is the operator's copy-paste source, so a flag it names that argparse does not know
    is a morning that dies at the first command.
    """
    commands = _commands()
    assert len(commands) >= 5, (
        "the readiness gate, its --send-test-message form, the pre-open check, the dry run and "
        "the live-alerts run"
    )
    for command in commands:
        argv = [
            part.replace("<TODAY>", "2026-06-10")
            for part in command.split()
            if not part.startswith(("python", "scripts/", "-m", "acumen.run_screener"))
        ]
        args = run_screener.parse_args(argv)   # raises SystemExit on an unknown flag
        assert args.day == "2026-06-10", command

    joined = "\n".join(commands)
    assert "--preflight-only" in joined
    assert "--live-alerts" in joined, "the flag that makes the phone ring"
    assert "--readiness" in joined and "--send-test-message" in joined
    assert "--no-wait" in joined, "section 2's late start"
    live = [c for c in commands if "--mode live" in c]
    assert sum("--live-alerts" in c for c in live) == 1, (
        "exactly one command in the whole card makes the phone ring, and it is labelled"
    )


def test_the_LAUNCHER_the_runbook_tells_the_operator_to_run_really_runs() -> None:
    """The gap chunk 14's stub had: its command needed an editable install and no test ran it.

    Every chunk-14 test drove ``run_screener.main([...])`` in-process, where pyproject's
    ``pythonpath = ["src"]`` had already put the package on the path -- so
    ``python -m acumen.run_screener`` was never executed as a shell command by anything, and on a
    fresh clone it answers ``No module named 'acumen'``. This runs the launcher the runbook now
    gives, as a real subprocess, from the repository root.
    """
    assert LAUNCHER.is_file()
    assert _commands()[0].startswith("python scripts/run_screener.py"), (
        "the FIRST command an operator meets must be the one that works from a bare clone"
    )
    done = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        cwd=str(REPO), capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    for flag in ("--mode", "--day", "--refresh", "--allow-network", "--telegram",
                 "--live-alerts", "--preflight-only", "--no-wait", "--readiness",
                 "--send-test-message"):
        assert flag in done.stdout, flag


def test_the_runbook_quotes_the_CODE_and_not_a_paraphrase_of_it() -> None:
    """Every sentence the card puts in the operator's eye is the one the code will print."""
    text = _text()

    # CONTEXT 4.7's disclosed line, byte for byte.
    assert ls.LIVE_DISCLOSURE in text

    # The markers that qualify a price (REVIEW_13B Q1 / B357 / REVIEW_14 H1 / REVIEW_14B L2).
    assert "this price stands on a window the screener cannot vouch for" in text
    assert ls.stale_note(0).split("--")[1].strip() in text
    assert ls.POC_PROVISIONAL in text
    assert tg.DRY_RUN_MARKER in text
    assert tg.REPLAY_MARKER in text
    assert tg.UNSTAMPED_MARKER.split("--")[0].strip() in text

    # CONTEXT 3.5's qty-zero outcome, in the screener's own words.
    assert ls.REFUSAL_QTY_ZERO in text

    # The banner's four phrases, from `_settle_banner`.
    for phrase in ("never answered", "are stale", "could NOT be evaluated",
                   "hit its hard deadline"):
        assert phrase in text, phrase

    # The two Telegram banners, from the sink's own constants.
    assert tg.FAILURE_BANNER.split("(")[0].strip() in text
    assert tg.REFUSED_BANNER in text

    # The end-of-day summary: its heading, its empty-morning sentence, its dry-run label, and
    # the event kind whose presence in the recording is why a restart does not send a second one.
    assert tg.SUMMARY_HEADING in text
    assert tg.SUMMARY_NO_ALERTS in text
    assert tg.SUMMARY_EVENT in text
    assert tg.SUMMARY_SUBJECTS.split(";")[0].strip("( ") in text

    # The fence's own first clause -- the line the card tells the operator is CORRECT.
    from acumen import backtest as bt

    assert bt.CA_REFRESH_FENCED.split(":")[0] in text
    assert "that is CORRECT and expected" in text.lower() or "CORRECT and expected" in text

    # The measured residual bracket, as a number rather than an adjective.
    assert "0.5229%" in text and "2.6808%" in text

    # The quarantined six, named (CONTEXT 4.7 / Q-30), and the settled count.
    for symbol in gate.QUARANTINED:
        assert symbol in text, symbol
    assert str(gate.SETTLED_UNIVERSE_SIZE) in text


def test_the_runbook_quotes_the_MORNING_AFTER_verdicts_in_the_jobs_own_words() -> None:
    """Section 8's four outcomes are the four the verification really produces.

    A card that described three of them would train the operator to file the fourth under
    whichever of the three it looked most like -- and the four differ exactly where it matters:
    withdrawn, unjudged, unjudgeable, and fine.
    """
    text = _text()
    assert refresh.VERIFY_STEP in text
    assert "THE EXCHANGE'S RECORD REFUSES" in text
    assert "treat them as withdrawn." in text
    assert refresh.NO_ORACLE_ROW in text
    assert refresh.NOT_VERIFIED_MARK in text
    assert "REFUSED-AFTER-ALERT" in text
    assert "NOT JUDGED and still queued" in text
    assert "verified against the published bhavcopy" in text
    assert "NOT READY -- the screener must not start" in text


def test_the_runbook_names_the_recording_layout_that_really_exists() -> None:
    """What the card tells an operator to keep must be what the recording actually writes."""
    from acumen import live_recording as rec

    text = _text()
    for name in (rec.MANIFEST_NAME, rec.BIAS_NAME, rec.STATE_NAME, rec.ALERTS_NAME,
                 rec.EVENTS_NAME, rec.CANDLES_DIRNAME, rec.VERIFICATION_NAME):
        assert name in text, name
    assert "dashboard.html" in text
    assert ls.EVENT_POST_SESSION_ALERT in text, (
        "the withheld post-session alert is in events.jsonl and the card says where"
    )


def test_the_preflight_lines_the_runbook_tells_the_operator_to_READ_exist() -> None:
    """Each row of the card's preflight table names a line the preflight really prints."""
    source = Path(run_screener.__file__).read_text(encoding="utf-8")
    for label in ("instrument master", "symbols", "biases resolved", "gate battery",
                  "calendar", "corporate actions", "telegram", "alerts", "recording",
                  "EXCLUDED"):
        # The preflight pads its labels to a fixed column, so the label is followed by at least
        # two spaces in the source. Matching on that is what tells a LABEL apart from the same
        # words appearing in a sentence.
        assert re.search(rf'"{label} {{2,}}', source), (
            f"the card tells the operator to read a preflight line called {label!r}"
        )
        assert f"| `{label}`" in _text(), f"...and the card's table really names {label!r}"


def test_the_readiness_section_tabulates_the_SEVEN_checks_the_gate_runs() -> None:
    """Section 0 is the gate's own check list, or it is a second source of truth about it."""
    text = _text()
    for name in gate.CHECKS:
        assert f"`{name}`" in text, name
    assert gate.READY_LINE in text
    assert gate.TEST_MESSAGE_HEADING in text
    assert "opt-in and required" in text
    assert gate.TRIPWIRE_SUITE in text


def test_the_runbook_carries_the_rules_that_never_change() -> None:
    """The five-and-one that outrank everything else in this document."""
    text = _text().lower()
    for rule in ("no orders, ever", "never printed, logged or committed",
                 "read-only during a session", "snapshot", "two generations",
                 "one session at a time", "the strategy is frozen"):
        assert rule in text, rule


def test_the_runbook_gives_every_command_a_TIME_and_the_sessions_shape() -> None:
    """*"Every command with its time"* -- the card is a procedure, not a reference sheet."""
    text = _text()
    for stamp in ("08:45", "08:50", "09:15", "11:15", "11:30", "15:00", "15:15", "15:30"):
        assert stamp in text, stamp
    assert "--live-alerts ONLY when" in text or "ONLY when the trader wants" in text, (
        "the live-alerts run is presented as a separate deliberate act"
    )
    assert "Three deliberate acts" in text
    for act in ("--mode live", "--telegram", "--live-alerts"):
        assert act in text, act
