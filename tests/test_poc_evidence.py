"""The chunk-6 gate evidence generator (:mod:`acumen.poc_evidence`).

The pack this module writes is what the trader is shown to settle QUESTIONS.md **Q-8**
(Round-3 Q42), so the parts that decide what he reads are tested: how a day is parsed, how
"which window matches" is concluded, and that the pack carries the sentence the gate turns on.

Two structural guards ride along:

* the module NEVER writes the minute store (the universe backfill owns it -- this session's
  store rule), and
* the launcher under ``scripts/`` stays a launcher (REVIEW_2 Finding 12).

Everything here is offline: the frozen ``poc/data`` CSVs and the frozen instrument-master
sample, with no daily store and no network.
"""

from __future__ import annotations

import argparse
import ast
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import poc
from acumen import poc_evidence as ev
from acumen.instrument_master import InstrumentMaster

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROW_SIZE = 24


@pytest.fixture(scope="module")
def master() -> InstrumentMaster:
    return InstrumentMaster.from_rows(
        json.loads((FIXTURES / "instrument_master_sample.json").read_text(encoding="utf-8"))
    )


# --- argument parsing --------------------------------------------------------------------


def test_a_symbol_day_and_a_reading_parse_into_exactly_what_they_say() -> None:
    assert ev._parse_symbol_day("icicibank:2026-07-17") == ("ICICIBANK", date(2026, 7, 17))
    assert ev._parse_reading("TCS:2026-07-14=2205.3") == (
        ("TCS", date(2026, 7, 14)),
        Decimal("2205.3"),
    )


@pytest.mark.parametrize("bad", ["TCS", "TCS:", ":2026-07-14"])
def test_a_malformed_symbol_day_is_refused_not_guessed(bad: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        ev._parse_symbol_day(bad)


def test_a_reading_without_a_price_is_refused() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        ev._parse_reading("TCS:2026-07-14")


# --- reading a frozen day ----------------------------------------------------------------


def test_a_frozen_calibration_day_loads_as_naive_ist_integer_paise_bars() -> None:
    bars = ev.bars_from_frozen_csv("TCS", date(2026, 7, 14))
    assert len(bars) == 375
    assert bars[0].stamp.tzinfo is None
    assert bars[0].stamp.isoformat() == "2026-07-14T09:15:00"
    assert isinstance(bars[0].high_paise, int)


def test_a_missing_calibration_day_fails_loudly() -> None:
    with pytest.raises(FileNotFoundError):
        ev.bars_from_frozen_csv("TCS", date(1999, 1, 4))


# --- the evidence row --------------------------------------------------------------------


def _row(master: InstrumentMaster, symbol: str, day: date, reading: Decimal | None) -> ev.DayEvidence:
    return ev.evidence_for_day(
        symbol,
        day,
        ev.bars_from_frozen_csv(symbol, day),
        source=ev.SOURCE_FROZEN_CSV,
        tick_paise=master.instrument(symbol).tick_size_paise,
        row_size=ROW_SIZE,
        reading=reading,
        daily_store=None,
    )


def test_both_windows_are_computed_for_one_day_and_the_spec_one_is_the_8_candle_window(
    master: InstrumentMaster,
) -> None:
    row = _row(master, "TCS", date(2026, 7, 14), Decimal("2205.3"))
    assert row.spec.window is poc.SPEC_WINDOW
    assert row.alternate.window is poc.ALTERNATE_WINDOW
    assert row.spec.bar_count == 120
    assert row.alternate.bar_count == 135
    assert row.spec.poc_rupees == Decimal("2205.25")
    assert row.gate1 is None  # no daily store passed -- reported as "no daily row", never faked


def test_when_the_two_windows_agree_the_day_is_reported_as_not_discriminating(
    master: InstrumentMaster,
) -> None:
    row = _row(master, "TCS", date(2026, 7, 14), Decimal("2205.3"))
    assert row.spec.poc_rupees == row.alternate.poc_rupees
    assert row.matches.startswith("both")


def test_the_match_verdict_names_the_nearer_window_when_they_differ(
    master: InstrumentMaster,
) -> None:
    """Built by hand rather than found in the data: on the frozen calibration days the two
    windows agree everywhere, which is itself the finding -- so the DECIDING branch is proved
    on constructed profiles instead of being left untested."""
    base = _row(master, "TCS", date(2026, 7, 14), Decimal("2205.3"))

    def with_pocs(spec_paise: int, alt_paise: int, reading: str | None) -> ev.DayEvidence:
        from dataclasses import replace
        from fractions import Fraction

        return replace(
            base,
            spec=replace(base.spec, poc_paise=Fraction(spec_paise)),
            alternate=replace(base.alternate, poc_paise=Fraction(alt_paise)),
            reading=None if reading is None else Decimal(reading),
        )

    assert with_pocs(220_530, 230_000, "2205.3").matches.startswith("8-candle")
    assert with_pocs(230_000, 220_530, "2205.3").matches.startswith("9-candle")
    assert with_pocs(220_520, 220_540, "2205.3").matches.startswith("neither")
    assert with_pocs(220_530, 230_000, None).matches == "no reading yet"


# --- the pack ------------------------------------------------------------------------------


def test_the_pack_carries_the_sentence_the_gate_turns_on_and_one_row_per_day(
    master: InstrumentMaster,
) -> None:
    rows = [
        _row(master, "TCS", date(2026, 7, 14), Decimal("2205.3")),
        _row(master, "DIXON", date(2026, 7, 16), None),
    ]
    pack = ev.render_pack(rows, row_size=ROW_SIZE, command="acumen-poc-evidence ...")
    assert "Q42's answer selects the window; nothing is locked until then." in pack
    assert "| symbol | date | POC, 8-candle | POC, 9-candle |" in pack
    assert "| TCS | 2026-07-14 | 2205.25 | 2205.25 | 2205.3 |" in pack.replace("  ", " ")
    assert "not known yet" in pack  # DIXON has no reading and the pack says so
    assert "PENDING" in pack
    assert poc.SPEC_WINDOW.describe() in pack and poc.ALTERNATE_WINDOW.describe() in pack
    # the summary must state how many days cannot separate the two windows, and name the
    # missing readings rather than leaving a blank cell to be read as "matches"
    assert "2 of 2 days cannot tell the two windows apart" in pack
    assert "No day here separates the two windows" in pack
    assert "DIXON 2026-07-16" in pack


def test_the_pack_names_a_day_that_does_separate_the_two_windows(master: InstrumentMaster) -> None:
    """The whole point of the pack: when a day DOES discriminate it must be called out, with the
    size of the gap, not left for the reader to spot in the table."""
    from dataclasses import replace
    from fractions import Fraction

    base = _row(master, "TCS", date(2026, 7, 14), None)
    row = replace(base, alternate=replace(base.alternate, poc_paise=Fraction(220_515)))
    pack = ev.render_pack([row], row_size=ROW_SIZE, command="x")
    assert "DOES separate them" in pack
    assert "2205.25" in pack and "2205.15" in pack
    assert "0.10 rupees apart" in pack


def test_the_pack_is_ascii_so_the_operators_cp1252_console_can_print_it(
    master: InstrumentMaster,
) -> None:
    pack = ev.render_pack(
        [_row(master, "MANAPPURAM", date(2026, 7, 15), Decimal("329.75"))],
        row_size=ROW_SIZE,
        command="x",
    )
    pack.encode("ascii")


# --- structural guards ---------------------------------------------------------------------


def test_the_evidence_generator_never_writes_the_minute_store() -> None:
    """This session's store rule: the universe backfill is writing ``data/minute_store`` in the
    background, and chunk 6 READS it only. Proved structurally, not promised in prose."""
    source = (REPO / "src" / "acumen" / "poc_evidence.py").read_text(encoding="utf-8")
    for forbidden in ("write_bars", "record_window", "atomic_write", "rebuild_symbol_raw"):
        assert forbidden not in source, f"poc_evidence.py references {forbidden}"


def test_the_launcher_is_only_a_launcher() -> None:
    """REVIEW_2 Finding 12, applied to the new script: docstring, imports, defs and the
    ``__main__`` guard -- nothing executed on import."""
    path = REPO / "scripts" / "poc_window_evidence.py"
    body = ast.parse(path.read_text(encoding="utf-8")).body
    executed = [
        node
        for node in body
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.If))
        and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    ]
    assert executed == []
    guards = [node for node in body if isinstance(node, ast.If)]
    assert len(guards) == 1 and "__main__" in ast.unparse(guards[0].test)
    assert 'acumen-poc-evidence = "acumen.poc_evidence:main"' in (
        REPO / "pyproject.toml"
    ).read_text(encoding="utf-8")


def test_a_chart_day_that_is_not_in_the_store_refuses_to_invent_one_offline(tmp_path: Path) -> None:
    """Without ``--allow-network`` an unsettled chart day must STOP the run, never fall back to
    an empty profile or a guess."""
    from acumen.instrument_master import master_cache_path

    cache = tmp_path / "cache"
    cached = master_cache_path(cache, date.today())  # the loader's own once-a-day cache path
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text((FIXTURES / "instrument_master_sample.json").read_text(encoding="utf-8"),
                      encoding="utf-8")

    args = ev.parse_args(
        [
            "--chart", "ICICIBANK:2026-07-17",
            "--data-dir", str(tmp_path / "data"),
            "--cache-dir", str(cache),
            "--out", str(tmp_path / "out.md"),
        ]
    )
    with pytest.raises(SystemExit, match="not in the minute store"):
        ev.run(args, command="test")
    assert not (tmp_path / "out.md").exists()
