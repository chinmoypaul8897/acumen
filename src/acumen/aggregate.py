"""Build 15-minute candles from stored 1-minute candles. PURE (CONTEXT 7-E1/E12).

CONTEXT 7-E1 makes 15-min bars an AGGREGATE of the stored 1-min bars, never a separate fetch:
one source of truth, so a 15-min bar the signal engine (chunk 7) reads is byte-identical
whether it came from the backtest store or a live poll (CONTEXT 6).

CONTEXT 7-E12 fixes the arithmetic exactly, and this module implements it literally:

* 1-min bars are OPEN-stamped -- the 09:15 bar covers 09:15:00..09:15:59.
* "a 15-min candle closing at HH:MM aggregates the 15 open-stamps in [HH:MM-15, HH:MM)".
  Equivalently, a 15-min bar OPEN-stamped at T covers the fifteen 1-min stamps [T, T+15) and
  CLOSES at T+15. The 15:00-close candle is stamps 14:45..14:59 (open-stamp 14:45).
* the grid is the session grid from 09:15: valid 15-min open-stamps are 09:15, 09:30, ...,
  15:15 (25 bars), and 15:15 is the bar closing at 15:30. Off-grid stamps are REJECTED
  (REVIEW_1 Finding 4): a 15-min stamp that is not on the 09:15 grid, or a 1-min bar outside
  the 09:15..15:29 session, is a bug in the data, not a bar to silently bucket.

The aggregation is the natural one: OPEN = the first minute's open, CLOSE = the last minute's
close, HIGH/LOW = the extremes, VOLUME = the sum -- over the minutes actually present in the
bucket. Completeness (a bucket missing minutes) is NOT this module's job: CONTEXT 4.5 gate 2
and CONTEXT 7-E4 decide whether a day/window is usable; the aggregator faithfully aggregates
whatever passed those gates.

**Completeness ruling (2026-07-26; QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"), for chunk 6.**
A missing 1-minute stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute,
not missing data -- the vendor omits tradeless minutes. E4 is redefined accordingly: the
09:15-11:14 profile window is valid when the DAY passes gate 1, and **E4's minute-count trigger
("missing > 5 of its 120") is RETIRED**. Nothing here or anywhere in ``src/`` counts window
minutes as a usability test, and chunk 6 must not reintroduce one: a tradeless minute contributes
zero volume to the profile, so a prorata POC over the traded minutes is the same number either
way. No liquidity filter exists (the trader specified none).

Prices stay integer paise (CONTEXT 7-E11); stamps stay naive IST (CONTEXT 7-E8).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Protocol, Sequence

from .calendar import SESSION_OPEN, is_session_time

#: One aggregation step. CONTEXT 3.4 works on 15-minute candles.
FIFTEEN_MINUTES: int = 15


class AggregateError(RuntimeError):
    """1-minute input cannot be aggregated into grid-aligned 15-minute bars."""


class _HasBarFields(Protocol):
    """Anything with the 1-min bar fields -- so this pure module needs no import from I/O."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


@dataclass(frozen=True)
class Bar:
    """One 15-minute candle: OPEN-stamped on the 09:15 grid, integer paise, naive IST."""

    stamp: datetime  # open-stamp: this bar covers [stamp, stamp + 15min) and closes at +15
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int

    @property
    def day(self) -> date:
        return self.stamp.date()

    @property
    def close_stamp(self) -> datetime:
        """When this bar closes (CONTEXT 7-E12): 15 minutes after its open-stamp."""
        return self.stamp + timedelta(minutes=FIFTEEN_MINUTES)


def bucket_open_stamp(stamp: datetime) -> datetime:
    """The 15-min grid open-stamp that a session 1-min ``stamp`` falls into. PURE.

    The grid starts at 09:15, so bucket = 09:15 + 15 * floor((stamp - 09:15) / 15). Every
    session minute 09:15..15:29 lands in a grid bar 09:15..15:15.

    Raises:
        AggregateError: ``stamp`` is not a naive session minute (09:15..15:29). This is the
            "09:14 out" boundary (CONTEXT 7-E2/E12): a bar outside the session has no bucket.
    """
    if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
        raise AggregateError(f"1-minute stamp must be naive IST (CONTEXT 7-E8); got {stamp!r}.")
    if not is_session_time(stamp, minutes=1):
        raise AggregateError(
            f"1-minute stamp {stamp.isoformat()} is outside the 09:15..15:29 session "
            "(CONTEXT 7-E2); it belongs to no 15-minute grid bar."
        )
    open_dt = datetime.combine(stamp.date(), SESSION_OPEN)
    minutes_in = int((stamp - open_dt).total_seconds() // 60)
    bucket_index = minutes_in // FIFTEEN_MINUTES
    return open_dt + timedelta(minutes=FIFTEEN_MINUTES * bucket_index)


def in_session_bars(
    one_minute_bars: Sequence[_HasBarFields],
) -> tuple[tuple[_HasBarFields, ...], int]:
    """Split 1-minute bars into ``(the session ones, how many were dropped)``. PURE.

    CONTEXT 7-E2 as CONTEXT 4.5's gate 2 already reads it, in gate 2's own words: an
    out-of-session candle is excluded **at the CANDLE level (drop the stray bar), not at the
    day level** -- a day that is ENTIRELY a non-standard session is caught by gate 1 and by the
    missing-minutes trigger instead, so nothing slips through.

    This helper exists so the CONSUMERS apply that same rule. :func:`aggregate_15min` keeps its
    refusal (a stray stamp belongs to no 15-minute bucket and guessing one would be an invented
    candle), and every caller that reads a real store filters first. Before this existed, a
    single vendor pre-open print -- RELIANCE 2017-04-28 09:14, one bar, 25,015 shares -- killed
    a whole full-history run with an ``AggregateError`` on a day gate 2 had deliberately
    admitted (found by the chunk-9B smoke run; QUESTIONS.md Q-17).

    The COUNT is returned rather than swallowed: a caller that drops candles silently would
    hide vendor damage, and this number is what the run records on the day's ledger row.
    """
    kept: list[_HasBarFields] = []
    dropped = 0
    for bar in one_minute_bars:
        if is_session_time(bar.stamp, minutes=1):
            kept.append(bar)
        else:
            dropped += 1
    return tuple(kept), dropped


def aggregate_15min(one_minute_bars: Sequence[_HasBarFields]) -> tuple[Bar, ...]:
    """Aggregate one day's 1-minute bars into 15-minute bars, oldest first. PURE.

    All input bars must share ONE trade date (a day at a time -- the minute store and the
    Rule-3 loader both hand over one day). Bars need not be pre-sorted; OPEN/CLOSE are taken
    from the earliest/latest stamp in each bucket.

    Returns the grid-aligned 15-minute bars (open-stamps 09:15..15:15), one per NON-EMPTY
    bucket, in time order.

    Raises:
        AggregateError: a stamp is outside the session, is tz-aware, the input mixes dates, or
            two bars share a 1-minute stamp (a duplicate that would double-count volume -- the
            integrity gate should have excluded such a day, so reaching here is a bug).
    """
    bars = list(one_minute_bars)
    if not bars:
        return ()

    days = {b.stamp.date() for b in bars}
    if len(days) != 1:
        raise AggregateError(
            f"aggregate_15min expects one trade date at a time; got {sorted(d.isoformat() for d in days)}."
        )

    seen_minutes: set[datetime] = set()
    buckets: dict[datetime, list[_HasBarFields]] = {}
    for bar in bars:
        if bar.stamp in seen_minutes:
            raise AggregateError(
                f"duplicate 1-minute stamp {bar.stamp.isoformat()} in the input; the "
                "integrity gate (CONTEXT 4.5 gate 2) rejects a day with duplicates."
            )
        seen_minutes.add(bar.stamp)
        buckets.setdefault(bucket_open_stamp(bar.stamp), []).append(bar)

    result: list[Bar] = []
    for open_stamp in sorted(buckets):
        if not is_session_time(open_stamp, minutes=FIFTEEN_MINUTES):
            # Defensive: bucket_open_stamp only ever yields 09:15..15:15, all of which pass;
            # this pins the "reject off-grid 15-min stamp" invariant (REVIEW_1 F4) explicitly.
            raise AggregateError(
                f"15-minute stamp {open_stamp.isoformat()} is off the session grid (CONTEXT 7-E12)."
            )
        members = sorted(buckets[open_stamp], key=lambda b: b.stamp)
        result.append(
            Bar(
                stamp=open_stamp,
                open_paise=members[0].open_paise,
                high_paise=max(b.high_paise for b in members),
                low_paise=min(b.low_paise for b in members),
                close_paise=members[-1].close_paise,
                volume=sum(b.volume for b in members),
            )
        )
    return tuple(result)


def grid_open_stamps(day: date) -> tuple[datetime, ...]:
    """The 25 valid 15-minute open-stamps for ``day``: 09:15, 09:30, ..., 15:15. PURE.

    Provided so a test (and the aggregator's own invariant) can name the exact grid the card
    asks for: "15-min stamps 09:15..15:15 exactly".
    """
    open_dt = datetime.combine(day, SESSION_OPEN)
    stamps = tuple(open_dt + timedelta(minutes=FIFTEEN_MINUTES * i) for i in range(25))
    last = stamps[-1]
    assert last.time() == time(15, 15), "grid must end at the 15:15 open-stamp (closes 15:30)"
    return stamps
