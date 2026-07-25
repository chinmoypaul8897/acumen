"""F10 golden -- the volume gate over all 25 PoC symbol-days (CONTEXT 8 F10, chunk 5A card).

The 25 frozen ``poc/data/*_1min.csv`` files are re-derived through the NEW chunk-5A pipeline --
:func:`acumen.smartapi_client.parse_candles` (the +05:30 -> naive normalization and the
Decimal-exact paise), the Parquet minute store, and :func:`acumen.quality_gates.volume_gate` --
and every day's gap% must:

* reproduce the frozen ``gap_pct`` in ``poc/data/volume_poc_summary.csv`` (to 3 dp);
* lie in the observed band **[+0.02%, +3.6%]** (CONTEXT 8 F10); and
* PASS the CONTEXT 4.5 acceptance band **[-0.1%, +5.0%]**.

This proves the new ingest path reconciles exactly as the PoC's did -- the pipeline did not
lose or double a single share on the way through the store.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from decimal import Decimal

from acumen import minute_unadjust as u
from acumen import quality_gates as qg
from acumen import smartapi_client as sac
from acumen.corp_actions import Factor, Suppression, KIND_BONUS, KIND_DEMERGER
from acumen.minute_store import MinuteStore

POC_DATA = Path(__file__).resolve().parents[1] / "poc" / "data"
SUMMARY = POC_DATA / "volume_poc_summary.csv"

#: CONTEXT 8 F10: the observed gap% band across the 25 PoC days.
F10_MIN_PCT = 0.02
F10_MAX_PCT = 3.6


def _load_summary() -> list[dict]:
    with SUMMARY.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _minute_csv_as_smartapi_rows(path: Path) -> list[list]:
    """Read a frozen poc/data 1-min CSV back into SmartAPI ``[ts,o,h,l,c,v]`` row shape."""
    rows: list[list] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            rows.append([r["ts"].strip(), r["open"], r["high"], r["low"], r["close"], int(r["volume"])])
    return rows


@pytest.fixture(scope="module")
def summary() -> list[dict]:
    rows = _load_summary()
    assert len(rows) == 25, "F10 asserts all 25 PoC symbol-days"
    return rows


def test_f10_all_25_days_reconcile_through_the_new_pipeline(summary: list[dict], tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "minute_store")
    checked = 0
    for row in summary:
        symbol = row["symbol"]
        day = date.fromisoformat(row["date"])
        daily_vol = int(float(row["daily_vol"]))
        frozen_gap = float(row["gap_pct"])
        frozen_sum = int(float(row["sum_1min_vol"]))

        csv_path = POC_DATA / f"{symbol}_{day.isoformat()}_1min.csv"
        bars = sac.parse_candles(_minute_csv_as_smartapi_rows(csv_path))  # the real ingest path
        assert bars[0].stamp.tzinfo is None  # +05:30 normalized away (CONTEXT 7-E8)
        store.write_bars(symbol, bars)

        minute_sum = sum(int(b.volume) for b in store.minutes(symbol, day))
        assert minute_sum == frozen_sum, f"{symbol} {day}: pipeline lost/gained shares"

        result = qg.volume_gate(daily_vol, minute_sum)
        gap = float(result.gap_pct)  # type: ignore[arg-type]

        assert round(gap, 3) == round(frozen_gap, 3), f"{symbol} {day}: gap {gap} != frozen {frozen_gap}"
        assert F10_MIN_PCT <= gap <= F10_MAX_PCT, f"{symbol} {day}: gap {gap}% outside [{F10_MIN_PCT}, {F10_MAX_PCT}]"
        assert result.passed, f"{symbol} {day}: gap {gap}% failed the [-0.1, 5.0] band"
        checked += 1
    assert checked == 25


def test_f10_extremes_are_the_expected_days(summary: list[dict]) -> None:
    """The band edges are real days: MANAPPURAM 07-20 is the min (+0.025%), HDFCBANK 07-16 the max (+3.581%)."""
    gaps = {(r["symbol"], r["date"]): float(r["gap_pct"]) for r in summary}
    assert min(gaps.values()) == gaps[("MANAPPURAM", "2026-07-20")] == 0.025
    assert max(gaps.values()) == gaps[("HDFCBANK", "2026-07-16")] == 3.581


def test_f10_days_unadjust_to_the_exact_identity(summary: list[dict]) -> None:
    """Q-10 acceptance 4d: F10 is untouched by un-adjustment. Every F10 day is in 2026, and each
    symbol's corporate actions all pre-date it (TCS's only bonus is 2018), so the factor window
    (D, F] is EMPTY, k_cum == 1, and un-adjustment is the EXACT identity -- the stored raw bars
    equal the fetched bars byte-for-byte. Proven by running the un-adjuster with a factor table
    whose events (a 2018 bonus, a 2023 demerger) are all before the F10 dates and a 2026 fetch
    date: the bars come back unchanged."""
    fetch_date = date(2026, 7, 25)
    for row in summary:
        symbol = row["symbol"]
        day = date.fromisoformat(row["date"])
        assert day.year == 2026  # the whole point: F10 is a recent, post-CA window
        csv_path = POC_DATA / f"{symbol}_{day.isoformat()}_1min.csv"
        bars = sac.parse_candles(_minute_csv_as_smartapi_rows(csv_path))
        # a realistic (pre-2026) factor table -- none of it falls in (D, F] for a 2026 day
        factors = (Factor(symbol=symbol, ex_date=date(2018, 6, 1), kind=KIND_BONUS,
                          k=Decimal(1) / 2, basis="pre-2026 bonus"),)
        supp = (Suppression(symbol, date(2023, 7, 20), KIND_DEMERGER, "pre-2026 demerger"),)
        result = u.unadjust_bars(bars, factors=factors, fetch_date=fetch_date, symbol=symbol,
                                 tick_paise=5, suppressions=supp)
        assert result.raw_bars == tuple(bars)  # identity: byte-for-byte unchanged
        assert all(d.identity and d.provable for d in result.days)
