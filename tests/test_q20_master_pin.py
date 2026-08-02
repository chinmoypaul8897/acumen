"""Q-20 -- ONE PINNED instrument master governs the whole backtest.

QUESTIONS.md Q-20, architect's ruling 02-Aug-2026, verbatim in the item:

    "...ONE PINNED master snapshot governs the whole backtest:
    OpenAPIScripMaster_2026-07-31.json. The run manifest records the pin by filename AND
    sha256; a resume under any other master REFUSES (same discipline as the code SHA);
    latest-by-filename selection is retired from the run path."

The manifest half and the resume half are pinned in `tests/test_backtest.py` (beside their
moved-code-SHA siblings, which is where a reader looks for them). What lives HERE is the
clause those two cannot express: **retired from the run path**. A selector that still exists
somewhere reachable from a run is not retired, it is merely unused today -- and the whole
failure mode Q-20 records is a silent, plausible-looking wrong number.

So this file walks `src/acumen` with `ast` and asserts WHERE newest-by-filename selection is
allowed to live, by name. It is a structural test on purpose: an import-graph fact cannot be
established by exercising one code path, and the drift it guards against (someone reaching for
"just take the newest dump" again) reads perfectly reasonable at the call site.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import instrument_master as im
from acumen import trade_evidence as te
from acumen.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "acumen"

#: The glob the vendor's date-stamped dumps answer to. Sorting it and taking the last element
#: IS newest-by-filename selection, which is what the ruling retired from the run path.
MASTER_GLOB = "OpenAPIScripMaster_*.json"

#: The ONE place in `src/` allowed to scan that glob, and why: `cached_masters` LISTS the cache
#: for the operator's CLI and for `newest_cached_master`, its only in-package consumer. Neither
#: is on the run path -- listing a cache is not selecting a tick regime. Anything that computes
#: a POC goes through `backtest.pinned_master` and the `config.yaml` pin instead.
GLOB_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {("instrument_master.py", "cached_masters")}
)

#: The modules a RUN loads. `backtest` wires the runner, `run_backtest` drives it, and the two
#: evidence modules compute POCs of their own; before the ruling, three of the four resolved a
#: master by sorting the glob above.
RUN_PATH: frozenset[str] = frozenset(
    {"backtest.py", "run_backtest.py", "pilot_evidence.py", "trade_evidence.py"}
)


def _enclosing_function(tree: ast.Module, node: ast.AST) -> str:
    """The name of the nearest enclosing def, or ``"<module>"``."""
    best = "<module>"
    for candidate in ast.walk(tree):
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = candidate.lineno
            end = getattr(candidate, "end_lineno", start)
            if start <= node.lineno <= end:
                best = candidate.name
    return best


def _glob_sites() -> list[tuple[str, str]]:
    """Every ``(module, enclosing function)`` in `src/acumen` that globs the master pattern."""
    found: list[tuple[str, str]] = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == MASTER_GLOB:
                found.append((path.name, _enclosing_function(tree, node)))
    return found


def test_newest_by_filename_selection_survives_only_where_it_is_named() -> None:
    """The retirement, asserted as a fact about the package rather than about one call."""
    assert set(_glob_sites()) == set(GLOB_ALLOWED), sorted(_glob_sites())


def test_the_run_path_modules_neither_scan_for_a_master_nor_ask_for_the_newest() -> None:
    """The stronger half: the modules a run loads never see the glob AND never call either
    cache-inspection helper. `backtest.latest_cached_master` is the one Q-20 measured handing
    the run the wrong snapshot; naming the helpers too closes the obvious way back in."""
    assert [site for site in _glob_sites() if site[0] in RUN_PATH] == []

    banned = {"cached_masters", "newest_cached_master", "latest_cached_master"}
    offenders: list[tuple[str, str]] = []
    for name in sorted(RUN_PATH):
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            called = None
            if isinstance(node, ast.Call):
                called = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if called in banned:
                offenders.append((name, called))
    assert offenders == []


def test_the_retired_selector_is_gone_from_the_run_path_by_name() -> None:
    """`latest_cached_master` was the name on both copies. Neither answers any more."""
    assert not hasattr(bt, "latest_cached_master")
    assert not hasattr(te, "latest_cached_master")
    assert hasattr(bt, "pinned_master")
    assert hasattr(te, "pinned_cached_master")


# --- what the pin actually resolves to -------------------------------------------------------


def _write_master(home: Path, name: str, tick_paise: str) -> Path:
    import json

    home.mkdir(parents=True, exist_ok=True)
    path = home / name
    path.write_text(
        json.dumps(
            [
                {
                    "exch_seg": "NSE",
                    "symbol": "PINTEST-EQ",
                    "token": "1",
                    "tick_size": tick_paise,
                    "name": "PINTEST",
                    "lotsize": "1",
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_the_pin_is_read_even_when_a_newer_dump_sits_beside_it(tmp_path: Path) -> None:
    """The measured Q-20 shape, in miniature: two snapshots, DIFFERENT ticks, and the run takes
    the PINNED one -- not the newer one, which is what the retired selector took.

    The tick values mirror a real row of the Q-20 evidence table (BAJAJ-AUTO 50p -> 100p): a
    doubled tick halves the CONTEXT 3.3 row grid, so this is the exact silence the ruling ends.
    """
    home = tmp_path / "instrument_master"
    _write_master(home, "OpenAPIScripMaster_2026-07-31.json", "50.000000")
    _write_master(home, "OpenAPIScripMaster_2026-08-02.json", "100.000000")

    master, path, digest = bt.pinned_master(tmp_path, "OpenAPIScripMaster_2026-07-31.json")
    assert path.name == "OpenAPIScripMaster_2026-07-31.json"
    assert master.by_symbol["PINTEST"].tick_size_paise == 50
    assert len(digest) == 64

    # ...and the newest-by-filename helper, asked directly, really would have taken the other
    # one -- so the test is discriminating rather than vacuous.
    newest, newest_path = im.newest_cached_master(tmp_path)
    assert newest_path.name == "OpenAPIScripMaster_2026-08-02.json"
    assert newest.by_symbol["PINTEST"].tick_size_paise == 100


def test_an_absent_pin_refuses_and_never_falls_back_to_a_neighbour(tmp_path: Path) -> None:
    """No fallback of any kind: substituting another snapshot is the defect, not the recovery."""
    home = tmp_path / "instrument_master"
    _write_master(home, "OpenAPIScripMaster_2026-08-02.json", "100.000000")
    with pytest.raises(bt.BacktestError) as excinfo:
        bt.pinned_master(tmp_path, "OpenAPIScripMaster_2026-07-31.json")
    message = str(excinfo.value)
    assert "Q-20" in message
    assert "do NOT substitute another snapshot" in message


def test_the_sha256_is_the_files_own_digest(tmp_path: Path) -> None:
    """Streaming digest over the real bytes -- the manifest's second half must be checkable."""
    import hashlib

    home = tmp_path / "instrument_master"
    path = _write_master(home, "OpenAPIScripMaster_2026-07-31.json", "5.000000")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert bt.pinned_master(tmp_path, path.name)[2] == expected
    assert bt.file_sha256(path) == expected


def test_the_committed_pin_exists_on_this_machine_and_is_the_ruled_one() -> None:
    """Reads the real cache: the pin config names is present, parses, and is the 2026-07-31
    snapshot the ruling names. Skips on a bare clone, like every other store-backed probe."""
    config = load_config(include_env=False)
    path = config.instrument_master_path()
    if not path.is_file():
        pytest.skip(f"pinned instrument master {path} is absent (cache/ is gitignored)")
    master, resolved, digest = bt.pinned_master(
        config.path("cache_root"), config.instrument_master
    )
    assert resolved == path
    assert config.instrument_master == "OpenAPIScripMaster_2026-07-31.json"
    assert len(master.by_symbol) > 2_000
    assert len(digest) == 64
