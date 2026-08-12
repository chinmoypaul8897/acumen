"""The REPLAY CONTRACT (chunk 13): everything a live day consumed, written down.

CONTEXT section 6 is this chunk's law -- *"One engine, two modes ... the backtester feeds them
stored history, the screener feeds them the live poll -- same code path, guaranteed no
backtest/live drift"*. A guarantee nobody can check is a hope, so this module makes the live day
CHECKABLE: it records every input the screener consumed, in enough detail that the same day can
be pushed back through the backtest path and compared candle for candle. Chunk 14's parity
harness is the consumer; this module is the contract it reads.

**What a recording holds**, one directory per live session (``<data_root>/live/<label>/``):

* ``manifest.json`` -- the day's identity: the spec version and code SHA the screener ran under,
  the config digest, the **instrument master by filename AND sha256** (QUESTIONS.md Q-20's own
  discipline, applied to the live side), Row Size, the money constants, the universe, and the
  CALENDAR READING with its source named (the C5 duty: live takes non-standard sessions from the
  PUBLISHED NSE calendar, and the store scan is recorded beside it as the backtest cross-check).
* ``candles/<SYMBOL>.jsonl`` -- **every fetched 1-minute bar**, append-only, in fetch order, with
  the poll that produced it. Not the de-duplicated result: the raw sequence, so a vendor that
  revises a bar between polls is visible rather than absorbed.
* ``fetches.jsonl`` -- every fetch ATTEMPT and its outcome, including the ones that failed and
  the ones the CONTEXT 4.4 deadline skipped. A sweep that silently shrank is the failure this
  file exists to make impossible.
* ``bias.json`` -- the pre-open bias per symbol, with the rule, the pair dates and the detail.
* ``alerts.jsonl`` -- every alert, with its timestamp and its whole payload.
* ``events.jsonl`` -- the session's own lifecycle: sweeps opened and closed, deadlines, failure
  banners raised and cleared, resumes.
* ``state.json`` -- the crash-safe intraday state (whole-file, atomic), so a screener that dies
  at 12:47 comes back at 12:47 instead of at 09:15.

**Append-only, and fsynced.** The JSONL files are opened, written and fsynced per record: a
recording's value is entirely in surviving the crash it is meant to explain. The two whole-file
documents go through :mod:`acumen.atomic_io`, the same path every other store write in this repo
takes.

**No clock is read in here.** Every stamp arrives as an argument. The recorder is I/O, not an
engine, but a recording whose timestamps came from inside itself could not be replayed
deterministically, and this repo's determinism proofs (chunk 9A's byte-identical resume) are
built on exactly that discipline.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .atomic_io import atomic_write_text
from .minute_store import StoredBar

#: Directory names inside one recording. Named constants because chunk 14 reads them.
CANDLES_DIRNAME: str = "candles"
MANIFEST_NAME: str = "manifest.json"
BIAS_NAME: str = "bias.json"
STATE_NAME: str = "state.json"
FETCHES_NAME: str = "fetches.jsonl"
ALERTS_NAME: str = "alerts.jsonl"
EVENTS_NAME: str = "events.jsonl"
#: CONTEXT 4.7: the NEXT pre-open's verdict on this day, written back into the day's own
#: recording. It is a separate document and not a manifest field on purpose -- the manifest
#: describes the machine the morning RAN on and is frozen against drift, while this is what a
#: later day, holding an oracle the morning did not have, concluded about it.
VERIFICATION_NAME: str = "verification.json"

#: The recording format's own version. Bumped when a field's MEANING changes, never for an
#: addition -- chunk 14 must be able to read an older day and say so.
RECORDING_VERSION: str = "1"

#: Where the live calendar reading came from. The C5 duty (QUESTIONS.md, recorded by the
#: chunk-9A fix session): *"chunk 13 takes non-standard sessions from the published NSE calendar;
#: the store scan stays the backtest cross-check"*. Both readings are recorded, and which one
#: GOVERNED is stated rather than inferred from which is present.
CALENDAR_PUBLISHED: str = "published-nse-holiday-master"
CALENDAR_STORE_SCAN: str = "daily-store-scan (backtest cross-check)"


class RecordingError(RuntimeError):
    """A recording cannot be written, or cannot be read back as one."""


@dataclass(frozen=True)
class FetchOutcome:
    """One fetch ATTEMPT: what was asked for, what came back, and how long it took.

    ``outcome`` is one of :data:`FETCH_OK`, :data:`FETCH_EMPTY`, :data:`FETCH_ERROR` or
    :data:`FETCH_SKIPPED`. The last is CONTEXT 4.4's own word: *"on failure SKIP the symbol and
    re-poll at sweep end"*, and a skipped symbol that the second pass never recovered is the
    thing the sweep report must be able to name.
    """

    symbol: str
    sweep: str
    outcome: str
    bars: int
    at: datetime
    attempt: int = 1
    elapsed_ms: int = 0
    detail: str = ""


FETCH_OK: str = "ok"
FETCH_EMPTY: str = "empty"
FETCH_ERROR: str = "error"
FETCH_SKIPPED: str = "skipped-deadline"

ALL_FETCH_OUTCOMES: frozenset[str] = frozenset(
    {FETCH_OK, FETCH_EMPTY, FETCH_ERROR, FETCH_SKIPPED}
)


@dataclass(frozen=True)
class RecordedAlert:
    """One alert, exactly as it was delivered.

    The payload is CONTEXT 4.4's own list where the alert is a trigger (*"symbol, side, entry,
    SL, TP, POC, bias, timestamp"*) and whatever the kind carries otherwise. It is stored as a
    plain mapping so a later reader needs no import from this package to understand it.
    """

    kind: str
    symbol: str
    at: datetime
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class BarRevision:
    """The vendor returned a DIFFERENT value for a stamp it had already served.

    Recorded rather than resolved. CONTEXT 4.4 builds the live day from the same
    ``getCandleData`` endpoint the backtest used, so a revision is a real event about the feed
    and not a bug in the screener -- but a screener that silently took the newer value would
    have made a decision on data the recording could not explain.
    """

    symbol: str
    stamp: datetime
    first: tuple[int, int, int, int, int]
    later: tuple[int, int, int, int, int]
    first_seq: int
    later_seq: int


@dataclass
class LiveRecording:
    """One live (or replayed) session's recording, rooted at ``root``.

    Cheap to construct and safe to re-open: every writer appends, so a resumed session continues
    the same files rather than starting a second set. :meth:`open_session` is what creates the
    directory and stamps the manifest.
    """

    root: Path
    _seq: int = field(default=0, repr=False)

    @classmethod
    def at(cls, root: Path | str) -> "LiveRecording":
        return cls(root=Path(root))

    @classmethod
    def for_day(
        cls, data_root: Path | str, day: date, *, label: str = ""
    ) -> "LiveRecording":
        """The conventional location: ``<data_root>/live/<YYYY-MM-DD>[-<label>]``."""
        name = day.isoformat() if not label else f"{day.isoformat()}-{label}"
        return cls(root=Path(data_root) / "live" / name)

    # --- layout -------------------------------------------------------------------

    @property
    def candles_dir(self) -> Path:
        return self.root / CANDLES_DIRNAME

    def candle_path(self, symbol: str) -> Path:
        return self.candles_dir / f"{symbol.strip().upper()}.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    @property
    def bias_path(self) -> Path:
        return self.root / BIAS_NAME

    @property
    def state_path(self) -> Path:
        return self.root / STATE_NAME

    @property
    def fetches_path(self) -> Path:
        return self.root / FETCHES_NAME

    @property
    def alerts_path(self) -> Path:
        return self.root / ALERTS_NAME

    @property
    def events_path(self) -> Path:
        return self.root / EVENTS_NAME

    @property
    def verification_path(self) -> Path:
        return self.root / VERIFICATION_NAME

    def exists(self) -> bool:
        return self.manifest_path.is_file()

    # --- writing ------------------------------------------------------------------

    def open_session(self, manifest: Mapping[str, Any]) -> Path:
        """Create the directory and write ``manifest.json``. Idempotent for a RESUME.

        A resume re-opens the same recording and the manifest must not have moved: if the code
        SHA, the config digest or the instrument master changed under a half-finished day, the
        recording would describe two different machines and the replay could not be trusted. The
        refusal is the same discipline :meth:`acumen.backtest.BacktestRunner._resume_state`
        applies to a moved code SHA, for the same reason.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        self.candles_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(manifest)
        payload.setdefault("recording_version", RECORDING_VERSION)
        if self.manifest_path.is_file():
            existing = self.read_manifest()
            frozen = ("code_sha", "config_digest", "master_file", "master_sha256",
                      "spec_version", "row_size", "trade_date", "recording_version")
            drifted = [
                key for key in frozen
                if key in existing and key in payload and existing[key] != payload[key]
            ]
            if drifted:
                detail = "; ".join(
                    f"{key}: recorded {existing[key]!r}, now {payload[key]!r}" for key in drifted
                )
                raise RecordingError(
                    f"Refusing to resume the recording at {self.root}: it was opened under a "
                    f"different machine ({detail}). A recording that describes two machines "
                    "cannot be replayed against either. Start a new label, or restore the "
                    "inputs the day began with."
                )
            return self.manifest_path
        return atomic_write_text(self.manifest_path, _canonical(payload))

    def record_bars(
        self, symbol: str, bars: Sequence[StoredBar], *, sweep: str, at: datetime
    ) -> int:
        """Append every fetched bar for ``symbol``. Returns how many lines were written.

        Nothing is de-duplicated here. The replay reader (:meth:`bars`) is what resolves a
        re-polled stamp, and it can only do that honestly if the raw sequence survives.
        """
        ticker = symbol.strip().upper()
        lines = []
        for bar in bars:
            self._seq += 1
            lines.append(
                _compact({
                    "seq": self._seq,
                    "sweep": sweep,
                    "at": at.isoformat(),
                    "stamp": bar.stamp.isoformat(),
                    "o": int(bar.open_paise),
                    "h": int(bar.high_paise),
                    "l": int(bar.low_paise),
                    "c": int(bar.close_paise),
                    "v": int(bar.volume),
                })
            )
        if lines:
            self.candles_dir.mkdir(parents=True, exist_ok=True)
            _append(self.candle_path(ticker), lines)
        return len(lines)

    def record_fetch(self, outcome: FetchOutcome) -> None:
        """Append one fetch attempt. Every attempt, including the ones that returned nothing."""
        if outcome.outcome not in ALL_FETCH_OUTCOMES:
            raise RecordingError(
                f"Unknown fetch outcome {outcome.outcome!r}; known: "
                f"{', '.join(sorted(ALL_FETCH_OUTCOMES))}."
            )
        _append(self.fetches_path, [_compact({
            "symbol": outcome.symbol.strip().upper(),
            "sweep": outcome.sweep,
            "outcome": outcome.outcome,
            "bars": int(outcome.bars),
            "attempt": int(outcome.attempt),
            "elapsed_ms": int(outcome.elapsed_ms),
            "at": outcome.at.isoformat(),
            "detail": outcome.detail,
        })])

    def record_alert(self, alert: RecordedAlert) -> None:
        """Append one alert, payload and all."""
        _append(self.alerts_path, [_compact({
            "kind": alert.kind,
            "symbol": alert.symbol.strip().upper(),
            "at": alert.at.isoformat(),
            "payload": dict(alert.payload),
        })])

    def record_event(self, kind: str, *, at: datetime, detail: str = "", **fields: Any) -> None:
        """Append one lifecycle event (sweep opened/closed, deadline, banner, resume)."""
        row: dict[str, Any] = {"kind": kind, "at": at.isoformat(), "detail": detail}
        row.update(fields)
        _append(self.events_path, [_compact(row)])

    def write_bias(self, payload: Mapping[str, Any]) -> Path:
        """Write the pre-open bias table, whole-file and atomically."""
        return atomic_write_text(self.bias_path, _canonical(payload))

    def write_state(self, payload: Mapping[str, Any]) -> Path:
        """Write the crash-safe intraday state, whole-file and atomically."""
        return atomic_write_text(self.state_path, _canonical(payload))

    def write_verification(self, payload: Mapping[str, Any]) -> Path:
        """Write the NEXT pre-open's full-battery verdict on this day (CONTEXT 4.7).

        The only write this repo makes into a CLOSED recording, and it is the one CONTEXT 4.7
        requires: the day the morning could not verify is verified the next morning, and the
        verdict belongs beside the day it judges rather than only in the log of the session that
        computed it. Whole-file and atomic, like every other document here.
        """
        return atomic_write_text(self.verification_path, _canonical(payload))

    def read_verification(self) -> dict[str, Any]:
        """The verification verdict, or ``{}`` when no morning has verified this day yet."""
        if not self.verification_path.is_file():
            return {}
        return _read_json(self.verification_path, "verification")

    # --- reading (what chunk 14's parity harness consumes) -------------------------

    def read_manifest(self) -> dict[str, Any]:
        return _read_json(self.manifest_path, "manifest")

    def read_bias(self) -> dict[str, Any]:
        return _read_json(self.bias_path, "bias table")

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {}
        return _read_json(self.state_path, "state")

    def symbols(self) -> tuple[str, ...]:
        """Every symbol this recording holds candles for, sorted."""
        if not self.candles_dir.is_dir():
            return ()
        return tuple(sorted(path.stem for path in self.candles_dir.glob("*.jsonl")))

    def bars(self, symbol: str, day: date) -> tuple[StoredBar, ...]:
        """The de-duplicated 1-minute bars for ``symbol`` on ``day``, oldest first.

        A stamp served more than once resolves to the LAST record for it -- the vendor's own
        latest answer, which is what the screener acted on. Any stamp whose VALUES changed
        between polls is reported by :meth:`revisions`; it is never silently absorbed.

        The result is :class:`acumen.minute_store.StoredBar`, so a recording drops into
        :meth:`acumen.signal_engine.SignalPipeline.gate_day` and the POC engine with no adapter
        at all -- which is the whole point of the one-engine law.
        """
        ticker = symbol.strip().upper()
        latest: dict[datetime, StoredBar] = {}
        for row in self._candle_rows(ticker):
            stamp = _parse_stamp(row["stamp"])
            if stamp.date() != day:
                continue
            latest[stamp] = StoredBar(
                symbol=ticker,
                stamp=stamp,
                open_paise=int(row["o"]),
                high_paise=int(row["h"]),
                low_paise=int(row["l"]),
                close_paise=int(row["c"]),
                volume=int(row["v"]),
            )
        return tuple(latest[stamp] for stamp in sorted(latest))

    def duplicate_bars(self, symbol: str, day: date) -> tuple[StoredBar, ...]:
        """Bars ONE reply served under a stamp that same reply had already served.

        CONTEXT 4.5 gate 2's first exclusion trigger is *"any duplicate stamp"*, and both the
        screener and the next morning's verification resolve a re-polled stamp before the gate
        can see it -- :meth:`bars` de-duplicates exactly as ``merge_bars`` does, and it must,
        because the engines need one bar per minute. So the twins are recoverable HERE, from the
        append-only sequence that was written precisely so nothing would be absorbed silently
        (REVIEW_13 **B2**).

        The unit is one reply -- rows sharing both a ``sweep`` and a ``stamp``. The same stamp
        arriving in a LATER sweep is the whole-session re-pull :class:`SmartApiBarSource` does
        by design and is not a duplicate; a stamp whose VALUES moved between replies is a
        revision and is :meth:`revisions`'s answer, not this one's.
        """
        ticker = symbol.strip().upper()
        seen: set[tuple[str, datetime]] = set()
        extra: list[StoredBar] = []
        for row in self._candle_rows(ticker):
            stamp = _parse_stamp(row["stamp"])
            if stamp.date() != day:
                continue
            key = (str(row.get("sweep", "")), stamp)
            if key in seen:
                extra.append(StoredBar(
                    symbol=ticker, stamp=stamp,
                    open_paise=int(row["o"]), high_paise=int(row["h"]),
                    low_paise=int(row["l"]), close_paise=int(row["c"]),
                    volume=int(row["v"]),
                ))
            else:
                seen.add(key)
        return tuple(extra)

    def revisions(self, symbol: str) -> tuple[BarRevision, ...]:
        """Stamps the vendor served twice with DIFFERENT values, oldest first."""
        ticker = symbol.strip().upper()
        seen: dict[datetime, tuple[tuple[int, int, int, int, int], int]] = {}
        found: list[BarRevision] = []
        for row in self._candle_rows(ticker):
            stamp = _parse_stamp(row["stamp"])
            values = (int(row["o"]), int(row["h"]), int(row["l"]), int(row["c"]), int(row["v"]))
            seq = int(row.get("seq", 0))
            if stamp in seen:
                before, before_seq = seen[stamp]
                if before != values:
                    found.append(
                        BarRevision(
                            symbol=ticker, stamp=stamp, first=before, later=values,
                            first_seq=before_seq, later_seq=seq,
                        )
                    )
            seen[stamp] = (values, seq)
        return tuple(sorted(found, key=lambda rev: (rev.stamp, rev.later_seq)))

    def fetches(self) -> tuple[dict[str, Any], ...]:
        return tuple(_read_jsonl(self.fetches_path))

    def alerts(self) -> tuple[dict[str, Any], ...]:
        return tuple(_read_jsonl(self.alerts_path))

    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(_read_jsonl(self.events_path))

    def _candle_rows(self, ticker: str) -> Iterable[dict[str, Any]]:
        return _read_jsonl(self.candle_path(ticker))

    # --- integrity ----------------------------------------------------------------

    def digest(self) -> str:
        """A sha256 over every file in the recording, path by path, sorted.

        What makes a recording quotable. Chunk 14 can state which recording it replayed and a
        later reader can prove the bytes have not moved since.
        """
        digest = hashlib.sha256()
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            digest.update(path.relative_to(self.root).as_posix().encode("ascii"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def inventory(self) -> dict[str, Any]:
        """What the recording holds, for the session report's contract listing."""
        symbols = self.symbols()
        bar_lines = 0
        for ticker in symbols:
            bar_lines += sum(1 for _ in self._candle_rows(ticker))
        return {
            "root": str(self.root),
            "symbols": len(symbols),
            "candle_lines": bar_lines,
            "fetch_rows": len(self.fetches()),
            "alerts": len(self.alerts()),
            "events": len(self.events()),
            "has_manifest": self.manifest_path.is_file(),
            "has_bias": self.bias_path.is_file(),
            "has_state": self.state_path.is_file(),
            "has_verification": self.verification_path.is_file(),
            "digest": self.digest(),
        }


# --- helpers -------------------------------------------------------------------------


def _canonical(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON: sorted keys, two-space indent, one trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, default=_default) + "\n"


def _compact(payload: Mapping[str, Any]) -> str:
    """One JSONL record: no spaces, sorted keys, so a diff of two recordings is readable."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"{type(value).__name__} is not JSON-recordable: {value!r}")


def _append(path: Path, lines: Sequence[str]) -> None:
    """Append lines and FSYNC. A recording that did not survive the crash explains nothing."""
    if not lines:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except ValueError as exc:
                raise RecordingError(f"{path}:{number} is not JSON: {exc}") from exc
    return rows


def _read_json(path: Path, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise RecordingError(f"No {what} at {path}; this is not a recording.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RecordingError(f"{path} is not readable as the {what}: {exc}") from exc


def _parse_stamp(text: str) -> datetime:
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is not None:
        raise RecordingError(
            f"Recorded stamp {text!r} is tz-aware; CONTEXT 7-E8 stores naive IST."
        )
    return stamp


__all__ = [
    "ALL_FETCH_OUTCOMES",
    "ALERTS_NAME",
    "BIAS_NAME",
    "BarRevision",
    "CALENDAR_PUBLISHED",
    "CALENDAR_STORE_SCAN",
    "CANDLES_DIRNAME",
    "EVENTS_NAME",
    "FETCHES_NAME",
    "FETCH_EMPTY",
    "FETCH_ERROR",
    "FETCH_OK",
    "FETCH_SKIPPED",
    "FetchOutcome",
    "LiveRecording",
    "MANIFEST_NAME",
    "RECORDING_VERSION",
    "RecordedAlert",
    "RecordingError",
    "STATE_NAME",
    "VERIFICATION_NAME",
]
