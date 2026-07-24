"""Chunk 0 smoke tests: the package imports and the repo really has the CONTEXT 6 layout.

These are deliberately structural. Chunk 0 ships no trading logic, so what has to be
guarded here is the scaffold itself: the seed documents, the frozen PoC fixtures, and the
directories every later chunk writes into.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_imports_and_reports_a_version() -> None:
    import acumen

    assert acumen.__version__ == "0.1.0"


def test_python_is_at_least_3_10() -> None:
    """pyproject declares requires-python >= 3.10 (CLAUDE.md code standards)."""
    assert sys.version_info >= (3, 10)


@pytest.mark.parametrize(
    "relative",
    [
        # CONTEXT 6 repo layout
        "src/acumen",
        "tests/fixtures",
        "docs",
        "docs/reviews",
        "personas",
        "poc",
        "poc/data",
    ],
)
def test_context_layout_directory_exists(relative: str) -> None:
    assert (REPO_ROOT / relative).is_dir(), f"missing directory from CONTEXT 6 layout: {relative}"


@pytest.mark.parametrize(
    "relative",
    [
        # seed documents (must exist and stay put)
        "CLAUDE.md",
        "CONTEXT.md",
        "plan.md",
        "personas/quant_reviewer.md",
        "personas/code_reviewer.md",
        # session ledgers created by chunk 0
        "PROGRESS.md",
        "QUESTIONS.md",
        "STATUS.md",
        # scaffold
        "pyproject.toml",
        "config.yaml",
        ".gitignore",
        "src/acumen/__init__.py",
        "src/acumen/config.py",
    ],
)
def test_required_file_exists(relative: str) -> None:
    assert (REPO_ROOT / relative).is_file(), f"missing required file: {relative}"


def test_frozen_poc_fixtures_are_present() -> None:
    """poc/data CSVs are frozen inputs for F7/F10 (CONTEXT 8) -- never regenerated."""
    data_dir = REPO_ROOT / "poc" / "data"
    minute_files = sorted(data_dir.glob("*_1min.csv"))
    assert len(minute_files) == 25, f"expected 25 frozen 1-min CSVs, found {len(minute_files)}"
    for name in ("volume_poc_summary.csv", "quality_report.csv", "depth_probe_results.csv"):
        assert (data_dir / name).is_file(), f"missing frozen PoC output: {name}"


def test_archived_poc_scripts_are_present() -> None:
    poc_dir = REPO_ROOT / "poc"
    expected = {
        "common.py",
        "poc1_login_test.py",
        "poc2_depth_probe.py",
        "poc3_volume_poc_test.py",
        "poc4_latency_test.py",
        "poc5_quality_report.py",
    }
    assert expected <= {p.name for p in poc_dir.glob("*.py")}


def test_project_python_sources_are_ascii_only() -> None:
    """The operator's console is cp1252.

    A traceback whose source line carries a rupee or section sign raises UnicodeEncodeError
    while it is being printed, hiding the real error at the worst possible moment. Spec
    symbols belong in the markdown documents, not in code we will have to print.
    """
    offenders = []
    for source in sorted((REPO_ROOT / "src").rglob("*.py")) + sorted(
        (REPO_ROOT / "tests").rglob("*.py")
    ):
        text = source.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.isascii():
                offenders.append(f"{source.relative_to(REPO_ROOT)}:{lineno}")
    assert not offenders, f"non-ASCII source lines: {offenders}"


def test_env_file_is_ignored_by_git() -> None:
    """CLAUDE.md rule 4: .env is never committed."""
    ignore_lines = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    assert ".env" in ignore_lines


def test_gitignore_does_not_swallow_the_frozen_poc_fixtures() -> None:
    """`data/` unanchored would also ignore poc/data/ -- the golden fixtures. It must be `/data/`."""
    ignore_lines = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "/data/" in ignore_lines
    assert "data/" not in ignore_lines
