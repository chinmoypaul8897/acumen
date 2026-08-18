"""REVIEW_15B **R1** -- the three printable strings that still named a command nobody can run.

C1 fixed the readiness gate's master refusal; R1 is the same defect in the three operator-facing
strings the review's AST sweep found afterwards, none of them in the cleanup's span:

* ``live_screener._require_day_master`` -- **the LIVE MORNING's own 09:00 refusal**, naming both
  ``-m acumen.run_screener --refresh`` and ``-m acumen.instrument_master``;
* ``backtest.named_master`` -- reached by the pre-open verification step;
* ``backtest.CA_REFRESH_FENCED`` -- printed on EVERY preflight, naming ``-m acumen.ca_report``.

The defect is not cosmetic and it is not about style. ``pyproject.toml``'s ``pythonpath = ["src"]``
is PYTEST's path, not a hand-typed subprocess's, so on a bare clone with ``PYTHONPATH`` unset --
the operator's own shell -- ``python -m acumen.<x>`` answers ``No module named 'acumen'`` while a
green suite sees nothing. That is REVIEW_14 **B3** -> **B429** -> REVIEW_15 **C1**, and these were
the three sites the lesson had not reached.

So each probe here does three things to ONE string, and reads the string AT ITS SOURCE (the
function that raises it, or the constant the caller is handed) rather than hunting a substring in
some document downstream:

1. the working launcher is named, pinned through the module constant, and its file exists;
2. no ``-m acumen.`` survives anywhere in the string;
3. the command is EXTRACTED from the string and RUN as a real subprocess with ``PYTHONPATH``
   stripped -- and every flag it names is parsed by that launcher's own parser -- because a
   remedy that has never been executed is exactly what B429 was.

Store-free and network-free by construction: the only launcher run with real arguments is the
instrument-master fetch, run WITHOUT ``--allow-network`` (the fetch's own opt-in, CONTEXT 4.3)
against a ``tmp_path`` cache of its own; the other two are run with ``--help``, which argparse
answers before any body executes. Nothing here opens ``data_root`` or ``cache_root``.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from acumen import backtest as bt
from acumen import ca_report
from acumen import dry_run_readiness as gate
from acumen import instrument_master
from acumen import live_screener as ls
from acumen import run_screener

REPO = Path(__file__).resolve().parents[1]

#: A day with no dump anywhere near it, so every refusal under test really refuses.
DAY = date(2026, 8, 18)

#: What a placeholder (``<today>``, ``<D>``) is replaced by before the flags are parsed. The
#: string prints a placeholder because the operator supplies the date; the parse check needs a
#: value, and any ISO date proves the same thing about the flag.
PLACEHOLDER_DATE = "2026-08-18"


def _commands(message: str) -> list[list[str]]:
    """Every backtick-quoted ``python ...`` command a message prints, split into argv."""
    quoted = re.findall(r"`([^`]+)`", message)
    return [text.split() for text in quoted if text.startswith("python ")]


def _resolved(argv: list[str]) -> list[str]:
    """``argv`` with every ``<placeholder>`` replaced by a real date, ready for a parser."""
    return [PLACEHOLDER_DATE if token.startswith("<") and token.endswith(">") else token
            for token in argv]


def _printable(source: str) -> list[str]:
    """Every string literal a module can PRINT -- docstrings excluded.

    The docstrings are excluded on purpose: this session's own provenance notes RECORD the dead
    form and why it changed, which is what a later session needs to understand the constant. What
    must not survive is a printable one.
    """
    tree = ast.parse(source)
    docs: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docs
    ]


def _run_bare(argv: list[str]) -> "subprocess.CompletedProcess[str]":
    """Run a command with ``PYTHONPATH`` stripped -- the operator's shell, not pytest's path."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, *argv], cwd=str(REPO), capture_output=True, text=True, timeout=180,
        env=env,
    )


def _refusal_of_the_live_morning() -> str:
    """The 09:00 refusal itself -- raised, not quoted from anywhere else."""
    try:
        ls._require_day_master(
            ls.day_master_filename(DAY), cache_dir=Path("nowhere-at-all-r1")
        )
    except ls.ScreenerError as exc:
        return str(exc)
    raise AssertionError("the day master resolved from a directory that does not exist")


# --- site 1: the LIVE MORNING's own refusal ----------------------------------------------------


def test_R1_the_LIVE_MORNINGS_own_refusal_names_LAUNCHERS_and_not_the_dead_module_form() -> None:
    """The most operator-facing of the three: it fires at 09:00, on the morning itself.

    The readiness gate C1 fixed runs the day BEFORE. This one is what CONTEXT 4.7 raises when the
    day's own dump is missing at the moment the morning starts, so its remedy is the one that can
    least afford to answer ``No module named 'acumen'``.
    """
    message = _refusal_of_the_live_morning()
    assert "-m acumen." not in message, message

    assert ls.SCREENER_LAUNCHER == "scripts/run_screener.py"
    assert bt.MASTER_LAUNCHER == "scripts/fetch_instrument_master.py"
    assert (REPO / ls.SCREENER_LAUNCHER).is_file()
    assert (REPO / bt.MASTER_LAUNCHER).is_file()

    assert (
        f"`python {ls.SCREENER_LAUNCHER} --mode live --day <today> --refresh --allow-network`"
        in message
    ), message
    assert f"`python {bt.MASTER_LAUNCHER} --allow-network`" in message, message


def test_R1_the_LIVE_MORNINGS_two_remedies_PARSE_and_RUN_with_PYTHONPATH_stripped(
    tmp_path: Path,
) -> None:
    """Both commands taken OUT of the refusal, then parsed and run rather than read.

    The refresh command is not executed with its own flags -- ``--refresh --allow-network`` on a
    live day fetches and writes, and a test may never do that (CLAUDE.md data-store safety). What
    is proved instead is the whole of the finding: that the launcher RESOLVES on a tree with no
    editable install (run with ``--help``, which argparse answers before any body runs), and that
    every flag the string names is one that launcher's own parser accepts.
    """
    commands = _commands(_refusal_of_the_live_morning())
    assert len(commands) == 2, commands
    assert all((REPO / argv[1]).is_file() for argv in commands), (
        f"the refusal prints a command whose target is not a file in this repo: {commands}"
    )
    refresh, fetch = commands
    assert refresh[:2] == ["python", ls.SCREENER_LAUNCHER], refresh
    assert fetch[:2] == ["python", bt.MASTER_LAUNCHER], fetch

    # the flags, through the launcher's OWN parser -- a pure parse, nothing is executed
    parsed = run_screener.parse_args(_resolved(refresh[2:]))
    assert (parsed.mode, parsed.day) == ("live", PLACEHOLDER_DATE)
    assert parsed.refresh is True and parsed.allow_network is True
    assert instrument_master.parse_args(_resolved(fetch[2:])).allow_network is True

    # the launcher, as a real subprocess, with nothing but its own bootstrap on the path
    helped = _run_bare([refresh[1], "--help"])
    output = (helped.stdout or "") + (helped.stderr or "")
    assert "No module named" not in output, output
    assert "Traceback" not in output, output
    assert helped.returncode == 0, output
    assert "--refresh" in output and "--allow-network" in output, output

    # the fetch, with its real flags MINUS the network opt-in, against a scratch cache
    cache = tmp_path / "cache"
    cache.mkdir()
    done = _run_bare([fetch[1], "--cache-dir", str(cache)])
    output = (done.stdout or "") + (done.stderr or "")
    assert "No module named" not in output, output
    assert "Traceback" not in output, output
    assert "Nothing was fetched and nothing was written." in output, output


# --- site 2: named_master, reached by the pre-open verification step ---------------------------


def _named_master_refusal() -> str:
    try:
        bt.named_master(Path("nowhere-at-all-r1"), ls.day_master_filename(DAY))
    except bt.BacktestError as exc:
        return str(exc)
    raise AssertionError("a master loaded from a directory that does not exist")


def test_R1_the_named_master_refusal_names_the_LAUNCHER_and_not_the_dead_module_form() -> None:
    """``backtest.named_master`` -- CONTEXT 4.7's door, and what the verification step hits."""
    message = _named_master_refusal()
    assert "-m acumen." not in message, message
    assert f"`python {bt.MASTER_LAUNCHER} --allow-network`" in message, message
    assert (REPO / bt.MASTER_LAUNCHER).is_file()


def test_R1_the_named_master_remedy_PARSES_and_RUNS_with_PYTHONPATH_stripped(
    tmp_path: Path,
) -> None:
    """The same drive as site 1's fetch, on site 2's own string, extracted from that string."""
    commands = _commands(_named_master_refusal())
    assert len(commands) == 1, commands
    argv = commands[0]
    assert (REPO / argv[1]).is_file(), (
        f"the refusal prints a command whose target is not a file in this repo: {argv}"
    )
    assert argv[:2] == ["python", bt.MASTER_LAUNCHER], argv
    assert instrument_master.parse_args(_resolved(argv[2:])).allow_network is True

    cache = tmp_path / "cache"
    cache.mkdir()
    done = _run_bare([argv[1], "--cache-dir", str(cache)])
    output = (done.stdout or "") + (done.stderr or "")
    assert "No module named" not in output, output
    assert "Traceback" not in output, output
    assert "Nothing was fetched and nothing was written." in output, output


# --- site 3: the corporate-action fence, printed on every preflight ----------------------------


def _fence_message(tmp_path: Path) -> str:
    """The fence's own return value -- what the preflight is HANDED to print, not the constant.

    Driven against a scratch pair of roots so the fence takes its fenced branch (the cache is
    inside the stores) without either real root being named, let alone read.
    """
    data_root = tmp_path / "store"
    cache = data_root / "nse"
    cache.mkdir(parents=True)
    _resolved_dir, network, why = bt.fence_ca_cache(
        cache_dir=cache, allow_network=True, data_root=data_root, cache_root=data_root / "cache",
    )
    assert network is False, "the fence must have fired for its message to be under test"
    return why


def test_R1_the_CA_REFRESH_FENCE_names_the_LAUNCHER_and_not_the_dead_module_form(
    tmp_path: Path,
) -> None:
    """Printed on EVERY preflight, which is what makes this the most-read of the three."""
    message = _fence_message(tmp_path)
    assert message == bt.CA_REFRESH_FENCED, "the fence hands the caller its own constant"
    assert "-m acumen." not in message, message
    assert bt.CA_REPORT_LAUNCHER == "scripts/ca_report.py"
    assert (REPO / bt.CA_REPORT_LAUNCHER).is_file()
    assert (
        f"`python {bt.CA_REPORT_LAUNCHER} --from <D> --to <D> --allow-network`" in message
    ), message


def test_R1_the_CA_REFRESH_ingest_path_PARSES_and_RUNS_with_PYTHONPATH_stripped(
    tmp_path: Path,
) -> None:
    """The ingest path is a WRITING command, so it is parsed and resolved -- never executed.

    ``--allow-network`` on ``ca_report`` pulls a window and writes it into the cache, which lives
    inside the stores; CLAUDE.md makes that an operator step taken after a snapshot, and the
    string under test says so itself. So the flags go through the launcher's own parser and the
    launcher is resolved with ``--help``. Neither touches a store or a socket.
    """
    commands = _commands(_fence_message(tmp_path))
    assert len(commands) == 1, commands
    argv = commands[0]
    assert (REPO / argv[1]).is_file(), (
        f"the fence prints an ingest command whose target is not a file in this repo: {argv}"
    )
    assert argv[:2] == ["python", bt.CA_REPORT_LAUNCHER], argv

    parsed = ca_report.parse_args(_resolved(argv[2:]))
    assert (parsed.start, parsed.end) == (PLACEHOLDER_DATE, PLACEHOLDER_DATE)
    assert parsed.allow_network is True

    helped = _run_bare([argv[1], "--help"])
    output = (helped.stdout or "") + (helped.stderr or "")
    assert "No module named" not in output, output
    assert "Traceback" not in output, output
    assert helped.returncode == 0, output
    assert "--from" in output and "--to" in output and "--allow-network" in output, output


# --- the two modules, swept, and the one name they must agree on -------------------------------


def test_R1_no_printable_string_in_EITHER_touched_module_names_the_dead_form() -> None:
    """The sweep at the two sources R1 named, by AST rather than by grep."""
    for module in (ls, bt):
        printable = _printable(Path(module.__file__).read_text(encoding="utf-8"))
        assert printable, f"the AST walk found no strings in {module.__name__}"
        offenders = [text for text in printable if "-m acumen." in text]
        assert not offenders, f"{module.__name__} can still print the dead form: {offenders}"


def test_R1_the_master_launcher_is_ONE_name_across_the_gate_and_the_two_fixed_sites() -> None:
    """Three strings and a gate naming the same file must not be able to drift apart.

    ``dry_run_readiness`` named it first (C1's :data:`MASTER_LAUNCHER`); ``backtest`` names it for
    its own refusal and ``live_screener`` reads it from there rather than repeating it. This is
    what fails if a later edit renames the launcher in one place only.
    """
    assert hasattr(bt, "MASTER_LAUNCHER"), (
        "backtest names the launcher its two operator-facing strings print"
    )
    assert hasattr(bt, "CA_REPORT_LAUNCHER") and hasattr(ls, "SCREENER_LAUNCHER")
    assert gate.MASTER_LAUNCHER == bt.MASTER_LAUNCHER
    for launcher in (bt.MASTER_LAUNCHER, bt.CA_REPORT_LAUNCHER, ls.SCREENER_LAUNCHER):
        assert (REPO / launcher).is_file(), launcher
