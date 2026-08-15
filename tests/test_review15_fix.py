"""THE REVIEW_15 CLEANUP, driven rather than asserted (chunk 15, final session).

REVIEW_15 passed chunk 15 and recorded nine findings, none of them blocking and none of them
touching a decision: two MEDIUM quant (Q1, Q2), one MEDIUM code (C1), two LOW (Q3, C2) and four
INFO (Q4, C3, C5, C4). Every one of them that has a subject a test can reach is closed with its
test flipped where the review pinned the defect, or driven here where the fix needed a new one.

What lives in THIS file is the part that needed a new drive:

* **C1** -- the gate's own refusal remedy is executed, as a real subprocess, on a tree with no
  editable install. A remedy that answers ``No module named 'acumen'`` at 08:00 is not a remedy,
  and this is the one way to know it does not: run it.
* **C5** -- ``QUESTIONS.md``'s Q-30 heading, read from the ledger and compared against the two
  questions closed by the same rulings block on the same day.
* **Q2** -- the refusal a recording that cannot say which day it is now produces, carried up to
  the report that stops the morning.

The rest are flipped in place, beside the pins that recorded them:

* Q1  -> ``tests/test_handover.py::test_the_THREE_PATHS_are_the_packs_own_three...`` (repaired to
  read the PACK) and ``test_review15_probes.py::test_FLIPPED_the_HANDOVERS_THREE_PATHS...``
* Q2  -> ``test_review15_probes.py::test_FLIPPED_B420_a_prior_day_recording...DOES_block``
* Q3  -> ``test_chunk15_carried_defects.py::test_L1_a_RESUMED_summary_says_which_number...``
* Q4  -> ``test_review15_probes.py::test_FLIPPED_B420_a_recording_with_NO_manifest...SURFACED``
* C2  -> ``test_review15_probes.py::test_the_RUNBOOK_and_the_GATE_agree_on_the_SEVEN_CHECK_NAMES``

Store-free by construction: nothing here reads ``data_root`` or ``cache_root`` except through a
scratch tree it built itself, so these run on a bare clone.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from acumen import dry_run_readiness as gate
from acumen import live_refresh as refresh
from acumen.calendar import TradingCalendar
from acumen.live_recording import LiveRecording

REPO = Path(__file__).resolve().parents[1]
DAY = date(2026, 6, 10)


# --- C1: the refusal's remedy, EXECUTED --------------------------------------------------------


def _remedy_command(detail: str) -> list[str]:
    """The command the refusal tells the operator to run, taken out of the refusal itself."""
    quoted = re.findall(r"`([^`]+)`", detail)
    commands = [text for text in quoted if text.startswith("python ")]
    assert len(commands) == 1, f"the refusal names {len(commands)} commands: {quoted}"
    return commands[0].split()


def test_C1_the_MASTER_refusals_own_remedy_RUNS_on_a_tree_with_no_editable_install(
    tmp_path: Path,
) -> None:
    """**REVIEW_15 C1**, driven: the remedy is run as a subprocess and must not answer "No module".

    The refusal used to end ``python -m acumen.instrument_master --allow-network``. On the
    operator's own machine ``import acumen`` raises ``ModuleNotFoundError`` -- there is no
    editable install -- so that remedy answered ``No module named 'acumen'`` at exactly the
    moment it was most needed: 08:00, on a refusal, before a live week. That is REVIEW_14 **B3**'s
    defect, one layer up from where **B429** removed it.

    The command is read OUT OF THE REFUSAL rather than written down here, so a future edit of the
    string is what this test sees. It is run WITHOUT ``--allow-network`` (the flag is the fetch's
    own opt-in, CONTEXT 4.3) and against a scratch cache directory, so the drive touches no
    network and no store: what is being proved is that the launcher resolves and runs, which is
    the whole of the finding.
    """
    refusal = gate.check_master(DAY, cache_dir=tmp_path / "empty")
    assert not refusal.ok, "the check must be refusing for its remedy to be under test"
    argv = _remedy_command(refusal.detail)
    assert argv[0] == "python" and argv[-1] == "--allow-network", argv

    launcher = REPO / argv[1]
    assert launcher.is_file(), f"the remedy names {argv[1]}, which is not a file in this repo"

    cache = tmp_path / "cache"
    (cache / "instrument_master").mkdir(parents=True)
    (cache / "instrument_master" / "OpenAPIScripMaster_2026-06-10.json").write_text(
        "[]", encoding="utf-8"
    )

    # A genuinely bare invocation: no PYTHONPATH, so nothing but the launcher's own bootstrap can
    # put the package on the path. pyproject's `pythonpath = ["src"]` is pytest's, not a
    # subprocess's, which is exactly how the original defect stayed invisible to the suite.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    done = subprocess.run(
        [sys.executable, str(launcher), "--cache-dir", str(cache)],
        cwd=str(REPO), capture_output=True, text=True, timeout=180, env=env,
    )
    output = (done.stdout or "") + (done.stderr or "")

    assert "No module named" not in output, (
        f"the gate's own remedy does not run on a tree with no editable install:\n{output}"
    )
    assert "Traceback" not in output, output
    assert done.returncode == 0, output
    assert "already held : 1 dump(s)" in output, output
    assert "Nothing was fetched and nothing was written." in output, (
        "without the network flag the launcher reports and writes nothing"
    )


def _printable_strings(source: str) -> list[str]:
    """Every string literal in a module EXCEPT the docstrings -- i.e. everything it can print."""
    import ast

    tree = ast.parse(source)
    docs: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docs
    ]


def test_C1_the_DEAD_module_form_is_gone_from_the_gate_and_the_launcher_is_named() -> None:
    """No string this gate can PRINT names the dead form -- checked by AST, not by grep.

    The docstrings are excluded on purpose: :func:`acumen.dry_run_readiness.check_master`'s own
    docstring records what the remedy used to say and why it changed, which is the provenance a
    later session needs. What must not survive is a printable one.
    """
    assert gate.MASTER_LAUNCHER == "scripts/fetch_instrument_master.py"
    assert (REPO / gate.MASTER_LAUNCHER).is_file()

    detail = gate.check_master(DAY, cache_dir=Path("nowhere-at-all")).detail
    assert f"`python {gate.MASTER_LAUNCHER} --allow-network`" in detail
    assert "-m acumen.instrument_master" not in detail

    printable = _printable_strings(Path(gate.__file__).read_text(encoding="utf-8"))
    assert printable, "the AST walk found no strings at all, so it is proving nothing"
    offenders = [text for text in printable if "-m acumen.instrument_master" in text]
    assert not offenders, f"a printable string still names the dead module form: {offenders}"
    assert any(gate.MASTER_LAUNCHER in text for text in printable), (
        "...and the working launcher is named in one that can be printed"
    )


# --- C5: the ledger's own bookkeeping ----------------------------------------------------------


def _heading(ledger: str, question: str) -> str:
    found = [
        line for line in ledger.splitlines()
        if line.startswith(f"## {question} ")
    ]
    assert len(found) == 1, f"{question} has {len(found)} headings in QUESTIONS.md"
    return found[0]


def test_C5_Q30s_heading_says_CLOSED_like_the_two_questions_ruled_beside_it() -> None:
    """**REVIEW_15 C5**: a heading that reads OPEN on a question that is ruled and shipped.

    CLAUDE.md's read order step 5 is *"QUESTIONS.md -- open items; if one touches your chunk,
    STOP on that part"*. Q-30's ruling (08-Aug-2026, option (a): a live morning screens the 204
    SETTLED symbols only) is recorded in the ledger, carried as law in CONTEXT v2.1 section 4.7
    and asserted by chunk 15's own readiness gate -- but its heading still read
    ``class A - OPEN - binds the first live morning``, so a dry-run-week session reading the
    ledger would stop on a question that was answered eight days earlier.

    Q-28 and Q-29 were closed by the SAME rulings block and their headings say so. This compares
    Q-30's against theirs rather than against a sentence written here.
    """
    ledger = (REPO / "QUESTIONS.md").read_text(encoding="utf-8")
    q30 = _heading(ledger, "Q-30")

    for closed in ("Q-28", "Q-29"):
        assert "**CLOSED 08-Aug-2026**" in _heading(ledger, closed), closed
    assert "**CLOSED 08-Aug-2026**" in q30, f"Q-30's heading still reads: {q30}"
    assert "OPEN" not in q30, f"Q-30's heading still reads: {q30}"
    assert "ARCHITECT'S RULINGS 08-Aug-2026" in q30, "and it points at the ruling that closed it"
    assert "204" in q30 and "SETTLED" in q30, "with what was ruled, in one line"

    # The ruling itself is where it always was -- the heading was the only thing missing.
    assert "**Q-30 is CLOSED, option (a).**" in ledger
    assert "a live morning screens the 204 SETTLED symbols only" in ledger
    # ...and the gate's constant still cites it, which is why the heading mattered at all.
    assert gate.SETTLED_UNIVERSE_SIZE == 204
    assert "Q-30" in Path(gate.__file__).read_text(encoding="utf-8")


# --- Q2: the refusal, carried up to the thing that stops the morning ---------------------------


def _plant(root: Path, day: date, label: str, *, mode: str = "live") -> LiveRecording:
    recording = LiveRecording.at(root / f"{day.isoformat()}-{label}")
    recording.open_session({
        "trade_date": day.isoformat(), "mode": mode, "symbols": ["HDFCBANK"],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    return recording


def test_Q2_an_UNVERIFIABLE_YESTERDAY_makes_the_whole_REPORT_refuse(tmp_path: Path) -> None:
    """**REVIEW_15 Q2**, driven to the report that stops the screener, not only to the step.

    B420's rule is *"stops the morning only when it is the prior trading day's"*. The one entry
    whose manifest could not be read was the one entry that could not answer that question, and
    the old code read its silence as "not yesterday's". It now reads it as "possibly yesterday's"
    -- and the refusal has to survive the trip up into :class:`RefreshReport`, whose ``ok`` is
    what ``run_screener`` refuses on, or nothing about the morning changes.
    """
    root = tmp_path / "live"
    friday, monday = date(2026, 8, 14), date(2026, 8, 17)
    calendar = TradingCalendar.from_holidays((date(2026, 1, 26),), covered_years=(2026,))
    assert calendar.prev_trading_day(monday) == friday

    recording = _plant(root, friday, "live")
    (recording.root / "manifest.json").write_text("{ not json at all", encoding="utf-8")

    _verifications, step = refresh.verify_prior_recordings(
        today=monday, calendar=calendar, data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache", recording_root=root,
    )
    assert step.ok is False

    report = refresh.RefreshReport(day=monday, steps=(step,))
    assert report.ok is False, "the step's refusal must reach the report"
    rendered = report.render()
    assert "NOT READY -- the screener must not start" in rendered
    assert str(recording.root) in rendered, "and the operator is told WHICH entry did it"


def test_Q2_the_NAME_is_read_only_when_the_MANIFEST_cannot_speak(tmp_path: Path) -> None:
    """The fallback's own boundary: the manifest wins wherever it can be read.

    ``recording_day`` is unchanged and still reads the manifest and only the manifest -- a label
    is the operator's and ``trade_date`` is the screener's, and only one of those is a fact about
    the day. The name is consulted for the BLOCKING TEST alone, and never when the manifest can
    answer: a recording of the 14th sitting in a directory somebody named ``2026-08-10-live`` is
    still, for every purpose, a recording of the 14th.
    """
    root = tmp_path / "live"
    misnamed = LiveRecording.at(root / "2026-08-10-live")
    misnamed.open_session({
        "trade_date": "2026-08-14", "mode": "live", "symbols": ["HDFCBANK"],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    assert refresh.recording_day(misnamed) == date(2026, 8, 14)
    assert refresh.recording_day_or_name(misnamed.root) == date(2026, 8, 14), (
        "the manifest is believed over the directory name wherever it can be read"
    )

    # ...and with the manifest gone, the name is all there is -- so the name is what answers.
    (misnamed.root / "manifest.json").unlink()
    assert refresh.recording_day(misnamed) is None
    assert refresh.recording_day_or_name(misnamed.root) == date(2026, 8, 10)

    # A directory nothing can date answers None, and its caller must treat that as unknown.
    (root / "not-a-day").mkdir()
    assert refresh.recording_day_or_name(root / "not-a-day") is None
