"""Where the live screener's 1-minute bars come from (chunk 13).

CONTEXT 4.4's first line is the whole design: *"Source of truth for live bars = the SAME
``getCandleData`` endpoint the backtest data came from -> live bars == backtest bars by
construction; no tick-built candles, no drift"*. So a bar source is deliberately thin -- it
answers one question, *"give me this symbol's 1-minute bars for today up to this stamp"* -- and
every engine decision is made downstream of it, in the code the backtester runs.

Three sources, one interface:

* :class:`SmartApiBarSource` -- the live one. Read-only ``getCandleData`` through the reviewed
  chunk-5A client, which already carries CONTEXT 4.3's throttle, backoff and session refresh.
* :class:`StoredDayBarSource` -- **replay from the minute lake.** A historical day is served
  incrementally, stamp by stamp, exactly as the live poller would have served it. This is what
  makes the chunk's replay invariant a real test of the LIVE pipeline rather than of a second
  code path written to pass it.
* :class:`RecordingBarSource` -- replay from a previous session's recording, so a real live day
  can be re-run against the same bytes it consumed (chunk 14's parity harness).

**No order endpoint is reachable from here.** The only SmartAPI method this module names is
``get_candles``; :mod:`tests.test_live_safety` proves it by AST over the whole package.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol, Sequence

from .instrument_master import InstrumentMaster
from .live_recording import LiveRecording
from .minute_store import MinuteStore, StoredBar
from .smartapi_client import INTERVAL_ONE_MINUTE, SmartApiClient

#: The session's first and last 1-minute OPEN-stamps (CONTEXT 3.1 / 7-E12).
SESSION_OPEN: time = time(9, 15)
SESSION_LAST_MINUTE: time = time(15, 29)


class BarSourceError(RuntimeError):
    """A bar source could not answer. Distinct from an EMPTY answer, which is legal."""


class BarSource(Protocol):
    """Give me ``symbol``'s 1-minute bars for ``day``, open-stamped at or before ``upto``."""

    def fetch(self, symbol: str, day: date, upto: datetime) -> tuple[StoredBar, ...]:
        ...


def _clamp(day: date, upto: datetime) -> datetime:
    """The last 1-minute OPEN-stamp a poll at ``upto`` may legally have seen.

    A bar stamped ``t`` covers ``[t, t+1min)`` (CONTEXT 7-E12), so it has CLOSED only once the
    clock has reached ``t + 1min``. Asking for bars "up to 11:15" therefore means stamps up to
    and including 11:14 -- which is exactly CONTEXT 3.3's profile window, and getting this
    boundary wrong by one bar is the off-by-one E12 exists to kill.
    """
    if upto.date() != day:
        upto = datetime.combine(day, SESSION_LAST_MINUTE) + timedelta(minutes=1)
    last = upto - timedelta(minutes=1)
    ceiling = datetime.combine(day, SESSION_LAST_MINUTE)
    floor = datetime.combine(day, SESSION_OPEN)
    if last > ceiling:
        last = ceiling
    return max(last, floor - timedelta(minutes=1))


@dataclass(frozen=True)
class SmartApiBarSource:
    """The LIVE source: read-only ``getCandleData``, one symbol at a time (CONTEXT 4.3/4.4).

    The window asked for is always the whole session so far (09:15 -> ``upto``), never a
    delta. CONTEXT 4.4 measures the just-closed candle as arriving *"~0.2s after the boundary"*,
    and a full-session pull is one request either way -- so re-pulling the day is free, it heals
    any bar an earlier sweep missed, and it is what lets the recording notice a vendor revision.

    Attributes:
        client: a logged-in chunk-5A client. Its throttle IS the CONTEXT 4.3 pacing.
        master: the instrument master, for the symbol's ``symboltoken``.
    """

    client: SmartApiClient
    master: InstrumentMaster

    def fetch(self, symbol: str, day: date, upto: datetime) -> tuple[StoredBar, ...]:
        ticker = symbol.strip().upper()
        last = _clamp(day, upto)
        if last < datetime.combine(day, SESSION_OPEN):
            return ()
        bars = self.client.get_candles(
            self.master.token(ticker),
            INTERVAL_ONE_MINUTE,
            datetime.combine(day, SESSION_OPEN),
            last,
        )
        return tuple(
            StoredBar(
                symbol=ticker,
                stamp=bar.stamp,
                open_paise=bar.open_paise,
                high_paise=bar.high_paise,
                low_paise=bar.low_paise,
                close_paise=bar.close_paise,
                volume=bar.volume,
            )
            for bar in bars
            if bar.stamp.date() == day and bar.stamp <= last
        )


@dataclass(frozen=True)
class StoredDayBarSource:
    """REPLAY from the minute lake: a historical day served as if the clock were running.

    Nothing is filtered except by the clock. The stored day is handed over exactly as
    :meth:`acumen.minute_store.MinuteStore.minutes` returns it -- strays included, because
    CONTEXT 4.6's Q-17 drop belongs to the engines and a source that pre-filtered would be
    hiding the very bars the gates are meant to see.
    """

    store: MinuteStore

    def fetch(self, symbol: str, day: date, upto: datetime) -> tuple[StoredBar, ...]:
        last = _clamp(day, upto)
        return tuple(bar for bar in self.store.minutes(symbol, day) if bar.stamp <= last)


@dataclass(frozen=True)
class RecordingBarSource:
    """REPLAY from a previous session's recording -- the same bytes the screener acted on."""

    recording: LiveRecording

    def fetch(self, symbol: str, day: date, upto: datetime) -> tuple[StoredBar, ...]:
        last = _clamp(day, upto)
        return tuple(bar for bar in self.recording.bars(symbol, day) if bar.stamp <= last)


@dataclass
class FlakyBarSource:
    """A source that FAILS on demand -- the simulated disconnect the chunk card requires.

    Test-facing but shipped, because the failure it injects is CONTEXT 4.4's own (*"transient
    false 'access denied' bursts are NORMAL"*) and the sweep's retry-and-skip behaviour is a
    safety property, not a convenience. ``fail_symbols`` names the symbols that raise;
    ``fail_times`` is how many times each one raises before it starts answering, so a source can
    model a burst that heals rather than only a permanent outage.
    """

    inner: BarSource
    fail_symbols: frozenset[str] = frozenset()
    fail_times: int = 1
    seen: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.seen is None:
            self.seen = {}

    def fetch(self, symbol: str, day: date, upto: datetime) -> tuple[StoredBar, ...]:
        ticker = symbol.strip().upper()
        if ticker in self.fail_symbols:
            count = self.seen.get(ticker, 0)
            if count < self.fail_times:
                self.seen[ticker] = count + 1
                raise BarSourceError(
                    f"{ticker}: simulated feed failure {count + 1} of {self.fail_times} "
                    "(CONTEXT 4.3: transient access-denied bursts are normal)"
                )
        return self.inner.fetch(symbol, day, upto)


def merge_bars(*groups: Sequence[StoredBar]) -> tuple[StoredBar, ...]:
    """Merge polls into one day, LATEST answer per stamp, oldest stamp first.

    The same resolution :meth:`acumen.live_recording.LiveRecording.bars` applies, kept in one
    place so the in-memory day and the replayed day can never disagree about what a re-polled
    stamp resolves to.
    """
    latest: dict[datetime, StoredBar] = {}
    for group in groups:
        for bar in group:
            latest[bar.stamp] = bar
    return tuple(latest[stamp] for stamp in sorted(latest))


__all__ = [
    "BarSource",
    "BarSourceError",
    "FlakyBarSource",
    "RecordingBarSource",
    "SESSION_LAST_MINUTE",
    "SESSION_OPEN",
    "SmartApiBarSource",
    "StoredDayBarSource",
    "merge_bars",
]
