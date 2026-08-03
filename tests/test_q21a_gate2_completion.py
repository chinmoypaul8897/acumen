"""QUESTIONS.md Q-21(a): the OPEN test completes CONTEXT 4.5 gate 2 (CONTEXT v1.6).

The gate's own arithmetic is tested in `tests/test_quality_gates.py` and its effect on the run
path in `tests/test_backtest.py`. What is pinned HERE is the pair of claims a session can only
make against the real stores, and which CONTEXT v1.6 and the FIX-3 report both rest on:

* the published chunk-9A PILOT window does not move -- no stored day of the five pilot symbols
  between 2026-05-01 and 2026-07-24 carries a bar the completion newly refuses, so the pack's
  290 / 146 / 88 / 56 reconciliation, pinned by tests and quoted in three reviews, is untouched;
* the days the completion DOES refuse are the ones the evidence names -- the market-wide
  2023-03-03 09:15 vendor print and JIOFIN 2023-08-21 -- and not a wider population that crept
  in with the new clause.

Both read the gitignored minute store and SKIP when it is absent, the precedent chunk 8 set for
store-backed probes (`tests/test_simulate.py`, `tests/test_review9a2_probes.py`). Nothing here
writes to any store.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date

import pytest

from acumen import pilot_evidence as pe
from acumen import quality_gates as qg
from acumen.config import load_config
from acumen.minute_store import MinuteStore

#: The two dates the whole-lake scan found malformed bars on
#: (docs/evidence/chunk9b_q21_malformed_bar.md, 153,712,320 stored bars).
KNOWN_MALFORMED_DATES: frozenset[date] = frozenset({date(2023, 3, 3), date(2023, 8, 21)})


def _minute_store() -> MinuteStore:
    config = load_config(include_env=False)
    store_dir = config.path("data_root") / "minute_store"
    if not store_dir.is_dir():
        pytest.skip(f"local minute store {store_dir} is absent (data/ is gitignored)")
    return MinuteStore(store_dir)


def _open_outside_days(store: MinuteStore, symbol: str, first: date, last: date) -> list[date]:
    """Every stored day of ``symbol`` in the window carrying an in-session open-outside bar."""
    found: list[date] = []
    for day, bars in store.iter_days(symbol, first, last):
        if any(
            not (bar.low_paise <= bar.open_paise <= bar.high_paise)
            for bar in bars
            if bar.stamp.date() == day and qg.is_session_time(bar.stamp, minutes=1)
        ):
            found.append(day)
    return found


def test_the_completed_gate_2_moves_no_day_of_the_chunk9a_pilot_window() -> None:
    """The pilot pack's figures are published, pinned and quoted in three reviews. A single day
    of its window newly failing gate 2 would move a bias, a POC or a trade -- so the claim is
    measured over every stored day of all five symbols rather than assumed from the flip list."""
    store = _minute_store()

    offenders = {
        symbol: _open_outside_days(store, symbol, pe.PILOT_START, pe.PILOT_END)
        for symbol in pe.PILOT_SYMBOLS
    }

    assert not any(offenders.values()), offenders
    # ...and the window really was read, so an empty store could never pass this quietly.
    assert all(
        store.iter_days(symbol, pe.PILOT_START, pe.PILOT_END) is not None
        for symbol in pe.PILOT_SYMBOLS
    )
    assert sum(
        1
        for symbol in pe.PILOT_SYMBOLS
        for _day, _bars in store.iter_days(symbol, pe.PILOT_START, pe.PILOT_END)
    ) > 0


@pytest.mark.parametrize("symbol", ["TCS", "JUBLFOOD"])
def test_a_symbol_the_completion_does_refuse_is_refused_on_the_known_dates_only(
    symbol: str,
) -> None:
    """TCS carries one of the 47 market-wide 2023-03-03 09:15 bars and JUBLFOOD carries the one
    that killed the run. Over their WHOLE stored history the completion may refuse those days
    and no others -- the new clause must not have quietly widened into ordinary days."""
    store = _minute_store()
    if not (store.minute_dir / symbol).is_dir():
        pytest.skip(f"{symbol} is not in the local minute store")

    days = _open_outside_days(store, symbol, date(2000, 1, 1), date(2100, 1, 1))

    assert days, f"{symbol} is expected to carry the vendor's 2023-03-03 09:15 print"
    assert set(days) <= KNOWN_MALFORMED_DATES, sorted(days)
