"""Tests for the instrument-master loader (CONTEXT 4.3, QUESTIONS.md Q-2).

Offline against a DERIVED master sample -- five real NSE ``-EQ`` rows (the F7 calibration
symbols) plus two distractors (a BSE row of the same name, an NFO option sharing the ``name``)
that force the ``exch_seg == NSE AND symbol == <SYMBOL>-EQ`` selection. The five ticks are
cross-checked against the frozen ``tick_sizes.json`` (Q-2), which is the tripwire; production
code always reads the master.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import instrument_master as im
from acumen.instrument_master import Instrument, InstrumentMaster, InstrumentMasterError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = FIXTURES / "instrument_master_sample.json"
TICKS = FIXTURES / "tick_sizes.json"

_SYMBOLS = ("TCS", "RELIANCE", "HDFCBANK", "DIXON", "MANAPPURAM")


@pytest.fixture
def rows() -> list[dict]:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def master() -> InstrumentMaster:
    return im.load_master_file(SAMPLE)


# --- tick conversion (CONTEXT 4.3: paise / 100) ---------------------------------------


@pytest.mark.parametrize("raw,paise", [("5.000000", 5), ("10.000000", 10), ("100.000000", 100), (5, 5)])
def test_parse_tick_size_paise(raw: object, paise: int) -> None:
    assert im.parse_tick_size_paise(raw) == paise


@pytest.mark.parametrize("bad", ["0", "-5", "5.5", "abc"])
def test_parse_tick_size_rejects_bad_values(bad: str) -> None:
    with pytest.raises(InstrumentMasterError):
        im.parse_tick_size_paise(bad)


def test_tick_size_is_paise_over_100_exact() -> None:
    inst = Instrument(symbol="TCS-EQ", token="11536", tick_size_paise=10, name="TCS")
    assert inst.tick_size == Decimal("0.10")
    assert isinstance(inst.tick_size, Decimal)  # exact, never a float (CONTEXT 7-E11)


# --- selection: NSE -EQ only ----------------------------------------------------------


def test_find_instrument_selects_the_nse_eq_row(rows: list[dict]) -> None:
    inst = im.find_instrument(rows, "TCS")
    assert (inst.token, inst.exch_seg, inst.symbol) == ("11536", "NSE", "TCS-EQ")


def test_find_instrument_ignores_bse_and_nfo_rows_of_the_same_name(rows: list[dict]) -> None:
    # The sample carries a BSE 'TCS' (token 532540) and an NFO 'TCS' option (token 144307);
    # both share the name 'TCS'. Neither may be chosen -- only the NSE -EQ row.
    inst = im.find_instrument(rows, "TCS")
    assert inst.token == "11536"  # not 532540 (BSE) and not 144307 (NFO)


def test_find_instrument_raises_for_an_unknown_symbol(rows: list[dict]) -> None:
    with pytest.raises(InstrumentMasterError, match="No NSE NOTASYMBOL-EQ"):
        im.find_instrument(rows, "NOTASYMBOL")


# --- the F7 tick cross-check (Q-2 tripwire) -------------------------------------------


def test_the_five_calibration_ticks_match_the_frozen_fixture(master: InstrumentMaster) -> None:
    """QUESTIONS.md Q-2: the master-derived ticks equal the frozen F7 tick_sizes.json.

    tick_sizes.json is TEST-ONLY (an architect ruling); production always reads the master.
    This pins that the loader's paise/100 reproduces the calibration ticks exactly.
    """
    frozen = json.loads(TICKS.read_text(encoding="utf-8"))
    for symbol in _SYMBOLS:
        assert master.tick_size(symbol) == Decimal(str(frozen[symbol])), symbol


def test_the_five_calibration_tokens_match_q2(master: InstrumentMaster) -> None:
    expected = {"TCS": "11536", "RELIANCE": "2885", "HDFCBANK": "1333", "DIXON": "21690", "MANAPPURAM": "19061"}
    for symbol, token in expected.items():
        assert master.token(symbol) == token, symbol


# --- InstrumentMaster index -----------------------------------------------------------


def test_master_indexes_only_nse_equities(master: InstrumentMaster) -> None:
    assert len(master) == 5  # the 5 -EQ rows; the BSE + NFO distractors are not indexed
    assert set(master.by_symbol) == set(_SYMBOLS)


def test_master_lookup_of_a_missing_symbol_raises(master: InstrumentMaster) -> None:
    with pytest.raises(InstrumentMasterError, match="No NSE ZZZ-EQ"):
        master.instrument("ZZZ")


def test_from_rows_rejects_an_empty_or_non_list() -> None:
    with pytest.raises(InstrumentMasterError):
        InstrumentMaster.from_rows([])
    with pytest.raises(InstrumentMasterError):
        InstrumentMaster.from_rows("not a list")


# --- the cached loader (offline discipline) -------------------------------------------


def test_load_instrument_master_offline_without_cache_raises(tmp_path: Path) -> None:
    from datetime import date

    with pytest.raises(InstrumentMasterError, match="allow_network is False"):
        im.load_instrument_master(cache_dir=tmp_path, today=date(2026, 7, 25), allow_network=False)


def test_load_instrument_master_serves_a_same_day_cache(tmp_path: Path) -> None:
    from datetime import date

    today = date(2026, 7, 25)
    path = im.master_cache_path(tmp_path, today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SAMPLE.read_bytes())
    master = im.load_instrument_master(cache_dir=tmp_path, today=today, allow_network=False)
    assert master.token("TCS") == "11536"


def test_load_instrument_master_uses_the_injected_fetcher_then_caches(tmp_path: Path) -> None:
    from datetime import date

    today = date(2026, 7, 25)
    payload = SAMPLE.read_bytes()
    master = im.load_instrument_master(
        cache_dir=tmp_path, today=today, allow_network=True, fetcher=lambda url: payload
    )
    assert master.token("RELIANCE") == "2885"
    assert im.master_cache_path(tmp_path, today).is_file()  # cached after a successful parse


# --- the operator CLI (QUESTIONS.md Q-18 runbook step 3) -------------------------------


def _seed_master(cache_dir: Path, stamp: str) -> Path:
    path = cache_dir / im.CACHE_SUBDIR / f"OpenAPIScripMaster_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SAMPLE.read_bytes())
    return path


def test_cached_masters_is_empty_on_a_bare_tree(tmp_path: Path) -> None:
    assert im.cached_masters(tmp_path) == ()


def test_cached_masters_lists_every_dump_oldest_first(tmp_path: Path) -> None:
    _seed_master(tmp_path, "2026-07-28")
    _seed_master(tmp_path, "2026-07-31")
    _seed_master(tmp_path, "2026-07-30")
    names = [path.name for path in im.cached_masters(tmp_path)]
    assert names == [
        "OpenAPIScripMaster_2026-07-28.json",
        "OpenAPIScripMaster_2026-07-30.json",
        "OpenAPIScripMaster_2026-07-31.json",
    ]


def test_cli_without_allow_network_fetches_nothing_and_fails_on_an_empty_cache(
    tmp_path: Path, capsys
) -> None:
    """The Q-18 rebuild must not be able to 'pass' step 3 with no master on disk."""
    code = im.main(["--cache-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "Nothing was fetched" in out
    assert im.cached_masters(tmp_path) == ()


def test_cli_without_allow_network_reports_an_existing_cache_and_succeeds(
    tmp_path: Path, capsys
) -> None:
    _seed_master(tmp_path, "2026-07-28")
    code = im.main(["--cache-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "OpenAPIScripMaster_2026-07-28.json" in out


def test_cli_names_the_file_it_wrote(tmp_path: Path, monkeypatch, capsys) -> None:
    """Step 3's whole point: the filename the packs cite is PRINTED, not inferred."""
    from datetime import date

    monkeypatch.setattr(im, "_download_master", lambda url: SAMPLE.read_bytes())
    monkeypatch.setattr(im, "date", _FrozenDate)
    code = im.main(["--cache-dir", str(tmp_path), "--allow-network"])
    out = capsys.readouterr().out
    assert code == 0
    expected = im.master_cache_path(tmp_path, date(2026, 7, 31))
    assert expected.is_file()
    assert expected.name in out
    assert "cite it as" in out


def test_cli_is_idempotent_serving_the_same_day_cache_without_fetching(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Safe to Ctrl-C and re-run (the runbook's promise): a second call fetches nothing."""

    def _refuse(url: str) -> bytes:
        raise AssertionError("a same-day cache must be served without touching the network")

    _seed_master(tmp_path, "2026-07-31")
    monkeypatch.setattr(im, "_download_master", _refuse)
    monkeypatch.setattr(im, "date", _FrozenDate)
    assert im.main(["--cache-dir", str(tmp_path), "--allow-network"]) == 0
    assert "OpenAPIScripMaster_2026-07-31.json" in capsys.readouterr().out


class _FrozenDate:
    """A stand-in for ``datetime.date`` whose ``today()`` never reads the clock."""

    @staticmethod
    def today():
        from datetime import date as _date

        return _date(2026, 7, 31)

    def __call__(self, *args, **kwargs):  # pragma: no cover -- constructor path unused here
        from datetime import date as _date

        return _date(*args, **kwargs)
