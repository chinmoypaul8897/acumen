"""Tests for the 15-minute aggregator (CONTEXT 7-E1/E12). PURE.

Includes the chunk-5A aggregator golden: the 15-minute bars built from the frozen
``poc/data/TCS_2026-07-14_1min.csv`` match the same bars derived independently in the test
(a hand-built groupby), bar for bar.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import aggregate
from acumen.aggregate import AggregateError, Bar, aggregate_15min, bucket_open_stamp, grid_open_stamps

POC_DATA = Path(__file__).resolve().parents[1] / "poc" / "data"


@dataclass(frozen=True)
class M:
    """A minimal 1-minute bar (structural match for the aggregator)."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


def _paise(text: str) -> int:
    scaled = Decimal(text) * 100
    assert scaled == scaled.to_integral_value(), text
    return int(scaled)


def load_poc_minutes(path: Path) -> list[M]:
    """Load a frozen poc/data 1-minute CSV (``ts,open,high,low,close,volume``, +05:30)."""
    bars: list[M] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stamp = datetime.fromisoformat(row["ts"].strip()).replace(tzinfo=None)  # drop +05:30
            bars.append(
                M(stamp, _paise(row["open"]), _paise(row["high"]), _paise(row["low"]),
                  _paise(row["close"]), int(row["volume"]))
            )
    return bars


# --- the grid (CONTEXT 7-E12) ---------------------------------------------------------


def test_grid_open_stamps_are_0915_to_1515_exactly() -> None:
    stamps = grid_open_stamps(date(2026, 7, 14))
    assert len(stamps) == 25
    assert stamps[0].time() == time(9, 15)
    assert stamps[-1].time() == time(15, 15)  # the bar closing at 15:30


@pytest.mark.parametrize(
    "clock,bucket",
    [
        (time(9, 15), time(9, 15)),   # first session minute -> first bar
        (time(9, 29), time(9, 15)),   # still the 09:15 bar (covers [09:15, 09:30))
        (time(9, 30), time(9, 30)),   # next bucket
        (time(14, 59), time(14, 45)), # the 15:00-close bar is stamps 14:45..14:59 (E12 example)
        (time(15, 29), time(15, 15)), # last session minute -> last bar (closes 15:30)
    ],
)
def test_bucket_open_stamp_maps_minutes_to_the_grid(clock: time, bucket: time) -> None:
    stamp = datetime.combine(date(2026, 7, 14), clock)
    assert bucket_open_stamp(stamp).time() == bucket


def test_0914_is_out_of_session() -> None:
    """The '09:14 out' boundary (CONTEXT 7-E2): a pre-open minute has no bucket."""
    with pytest.raises(AggregateError, match="outside the 09:15..15:29 session"):
        bucket_open_stamp(datetime(2026, 7, 14, 9, 14))


def test_1530_is_out_of_session() -> None:
    with pytest.raises(AggregateError):
        bucket_open_stamp(datetime(2026, 7, 14, 15, 30))


# --- aggregation golden (TCS 2026-07-14) ----------------------------------------------


def test_aggregator_golden_matches_independent_bars() -> None:
    minutes = load_poc_minutes(POC_DATA / "TCS_2026-07-14_1min.csv")
    bars = aggregate_15min(minutes)

    # independent reference: bucket by the 09:15 grid with a plain groupby, no shared code path
    day = date(2026, 7, 14)
    grid = grid_open_stamps(day)
    reference: list[Bar] = []
    for open_stamp in grid:
        members = [m for m in minutes if open_stamp <= m.stamp < open_stamp + _fifteen()]
        members.sort(key=lambda m: m.stamp)
        if not members:
            continue
        reference.append(
            Bar(
                stamp=open_stamp,
                open_paise=members[0].open_paise,
                high_paise=max(m.high_paise for m in members),
                low_paise=min(m.low_paise for m in members),
                close_paise=members[-1].close_paise,
                volume=sum(m.volume for m in members),
            )
        )

    assert bars == tuple(reference)
    assert len(bars) == 25  # a full day -> 25 fifteen-minute bars
    assert bars[0].stamp.time() == time(9, 15) and bars[-1].stamp.time() == time(15, 15)
    # every 15-min bar sums exactly the 15 minutes it covers (volume conservation)
    assert sum(b.volume for b in bars) == sum(m.volume for m in minutes)


def _fifteen():
    from datetime import timedelta

    return timedelta(minutes=15)


def test_each_15min_bar_closes_15_minutes_after_its_open_stamp() -> None:
    minutes = load_poc_minutes(POC_DATA / "TCS_2026-07-14_1min.csv")
    bars = aggregate_15min(minutes)
    for bar in bars:
        assert bar.close_stamp == bar.stamp + _fifteen()
    # the 15:00-close bar (open-stamp 14:45) exists (CONTEXT 7-E12 example)
    assert any(b.stamp.time() == time(14, 45) and b.close_stamp.time() == time(15, 0) for b in bars)


# --- guards ---------------------------------------------------------------------------


def test_empty_input_is_empty() -> None:
    assert aggregate_15min([]) == ()


def test_mixed_dates_are_rejected() -> None:
    a = M(datetime(2026, 7, 14, 9, 15), 100, 100, 100, 100, 1)
    b = M(datetime(2026, 7, 15, 9, 15), 100, 100, 100, 100, 1)
    with pytest.raises(AggregateError, match="one trade date"):
        aggregate_15min([a, b])


def test_duplicate_minute_stamp_is_rejected() -> None:
    a = M(datetime(2026, 7, 14, 9, 15), 100, 100, 100, 100, 1)
    with pytest.raises(AggregateError, match="duplicate"):
        aggregate_15min([a, a])


def test_out_of_session_minute_is_rejected() -> None:
    a = M(datetime(2026, 7, 14, 9, 14), 100, 100, 100, 100, 1)
    with pytest.raises(AggregateError, match="outside the 09:15"):
        aggregate_15min([a])
