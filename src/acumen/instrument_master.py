"""Angel One instrument master: symbol -> token and per-symbol tick size (CONTEXT 4.3).

CONTEXT 4.3 names one instrument-master source -- the daily
``OpenAPIScripMaster.json`` dump -- and two facts the rest of the project needs from it:

* the ``symboltoken`` a ``getCandleData`` request is keyed on (chunk 5A's downloader), and
* the per-symbol ``tick_size``, which is **in paise and must be divided by 100**
  (CONTEXT 4.3 / 3.3: "NEVER hardcode 0.05"). Chunk 6's POC row grid
  (``totalTicks = round((top-bottom)/tick)``) depends on getting this right per symbol, and
  QUESTIONS.md Q-2 measured that hardcoding 0.05 silently mis-prices DIXON by rupees.

Two layers, deliberately separate (CONTEXT 6):

* :func:`find_instrument` / :class:`InstrumentMaster` are PURE -- rows in, instrument out,
  no I/O, no clock -- so a frozen master sample drives the whole test suite offline;
* :func:`load_instrument_master` does the gentle once-a-day live download, cached to a
  date-stamped file, opt-in behind ``allow_network`` exactly like :mod:`acumen.nse_http`.

The selection is strict: the instrument is the NSE cash-equity row ``<SYMBOL>-EQ`` on
``exch_seg == "NSE"``. A BSE listing of the same name, or an NFO derivative that shares the
``name`` field, is NOT the instrument -- matching either would hand the backtest the wrong
token (and, for a derivative, the wrong tick). A symbol with no NSE ``-EQ`` row raises, so a
typo or a delisted name fails loudly instead of resolving to something plausible.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Sequence

from .atomic_io import atomic_write_bytes

#: CONTEXT 4.3 -- the daily instrument dump.
SCRIP_MASTER_URL: str = (
    "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
)

#: The exchange segment and symbol suffix that identify an NSE cash-equity row.
EXCH_NSE: str = "NSE"
EQ_SUFFIX: str = "-EQ"

#: Subdirectory (under the cache dir) the date-stamped master files live in.
CACHE_SUBDIR: str = "instrument_master"


class InstrumentMasterError(RuntimeError):
    """The instrument master could not be read, or does not carry the symbol asked for."""


@dataclass(frozen=True)
class Instrument:
    """One NSE cash-equity instrument from the master.

    ``tick_size_paise`` is the raw master value (already a whole number of paise); ``tick_size``
    exposes it in RUPEES as an exact :class:`~decimal.Decimal` (CONTEXT 4.3: divide by 100).
    Never compare a price against ``float(tick_size)`` in the engine -- the Decimal is exact
    and the tick grid must stay exact (CONTEXT 7-E11).
    """

    symbol: str
    token: str
    tick_size_paise: int
    name: str
    lot_size: int | None = None
    exch_seg: str = EXCH_NSE

    @property
    def tick_size(self) -> Decimal:
        """The tick size in RUPEES, exact (paise / 100)."""
        return Decimal(self.tick_size_paise) / Decimal(100)


def parse_tick_size_paise(raw: Any) -> int:
    """Parse a master ``tick_size`` field (e.g. ``"5.000000"``) to whole paise. PURE.

    CONTEXT 4.3 states the field is in paise; this keeps it in paise (the ``/100`` to rupees
    is :attr:`Instrument.tick_size`). A value that is not a whole number of paise raises
    rather than being rounded -- the PoC's ``tick/100 if tick >= 1`` heuristic is deliberately
    NOT carried, because the spec is unconditional and a surprising value should be loud.
    """
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise InstrumentMasterError(f"tick_size {raw!r} is not a number.") from exc
    if value <= 0:
        raise InstrumentMasterError(f"tick_size {raw!r} must be positive.")
    if value != value.to_integral_value():
        raise InstrumentMasterError(
            f"tick_size {raw!r} is not a whole number of paise (CONTEXT 4.3 says the master "
            "stores paise; a fractional-paise tick is unexpected and is not silently rounded)."
        )
    return int(value)


def _instrument_from_row(row: Any) -> Instrument:
    if not isinstance(row, dict):
        raise InstrumentMasterError(f"instrument-master row is {type(row).__name__}, expected object.")
    token = row.get("token")
    symbol = row.get("symbol")
    if not isinstance(token, str) or not token.strip():
        raise InstrumentMasterError(f"instrument-master row {symbol!r} has no usable token.")
    lot_raw = row.get("lotsize")
    try:
        lot = int(lot_raw) if lot_raw not in (None, "") else None
    except (TypeError, ValueError):
        lot = None
    return Instrument(
        symbol=str(symbol).strip().upper(),
        token=token.strip(),
        tick_size_paise=parse_tick_size_paise(row.get("tick_size")),
        name=str(row.get("name", "")).strip().upper(),
        lot_size=lot,
        exch_seg=str(row.get("exch_seg", "")).strip().upper(),
    )


def find_instrument(rows: Sequence[Any], symbol: str) -> Instrument:
    """Return the NSE cash-equity instrument for ``symbol`` from raw master rows. PURE.

    Matches ``exch_seg == "NSE"`` AND ``symbol == "<SYMBOL>-EQ"`` -- both, so a BSE row of the
    same name or an NFO derivative sharing the ``name`` field is never chosen.

    Raises:
        InstrumentMasterError: no NSE ``-EQ`` row, or (a corrupt master) more than one.
    """
    target = f"{symbol.strip().upper()}{EQ_SUFFIX}"
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("exch_seg", "")).strip().upper() == EXCH_NSE
        and str(row.get("symbol", "")).strip().upper() == target
    ]
    if not matches:
        raise InstrumentMasterError(
            f"No NSE {target} row in the instrument master. The symbol may be misspelled, "
            "delisted, or not an NSE cash equity (CONTEXT 4.3 keys candles on the -EQ token)."
        )
    if len(matches) > 1:
        raise InstrumentMasterError(
            f"{len(matches)} NSE {target} rows in the instrument master; expected exactly one. "
            "The master is corrupt or duplicated."
        )
    return _instrument_from_row(matches[0])


@dataclass(frozen=True)
class InstrumentMaster:
    """An indexed view of the master: O(1) ``symbol -> Instrument`` for NSE equities."""

    by_symbol: dict[str, Instrument]

    @classmethod
    def from_rows(cls, rows: Any) -> InstrumentMaster:
        """Index the NSE ``-EQ`` rows of a raw master list. PURE.

        Only the cash-equity rows are indexed (the other ~160k derivative/other-exchange rows
        are never the instrument), so a lookup is a dict hit and the memory stays small.
        """
        if not isinstance(rows, (list, tuple)) or not rows:
            raise InstrumentMasterError(
                "The instrument master must be a non-empty list of rows; got "
                f"{type(rows).__name__}."
            )
        index: dict[str, Instrument] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("exch_seg", "")).strip().upper() != EXCH_NSE:
                continue
            sym = str(row.get("symbol", "")).strip().upper()
            if not sym.endswith(EQ_SUFFIX):
                continue
            base = sym[: -len(EQ_SUFFIX)]
            instrument = _instrument_from_row(row)
            if base in index:
                raise InstrumentMasterError(
                    f"Duplicate NSE {base}{EQ_SUFFIX} rows in the instrument master."
                )
            index[base] = instrument
        if not index:
            raise InstrumentMasterError(
                "The instrument master carried no NSE -EQ rows; it is not the expected dump."
            )
        return cls(by_symbol=index)

    def instrument(self, symbol: str) -> Instrument:
        """The instrument for ``symbol``. Raises if absent (never returns a guess)."""
        key = symbol.strip().upper()
        try:
            return self.by_symbol[key]
        except KeyError:
            raise InstrumentMasterError(
                f"No NSE {key}{EQ_SUFFIX} in the instrument master (CONTEXT 4.3)."
            ) from None

    def token(self, symbol: str) -> str:
        """The ``symboltoken`` for ``symbol`` -- what ``getCandleData`` is keyed on."""
        return self.instrument(symbol).token

    def tick_size(self, symbol: str) -> Decimal:
        """The tick size in RUPEES for ``symbol`` (CONTEXT 4.3: paise / 100)."""
        return self.instrument(symbol).tick_size

    def __len__(self) -> int:
        return len(self.by_symbol)


# --- I/O (opt-in; the live download) ---------------------------------------------------


def default_cache_dir() -> Path:
    """``cache_root`` from config.yaml -- OUTSIDE the repo tree (CLAUDE.md Q-18 layer 1)."""
    from .config import load_config  # local import: parsing must not require a config file

    return load_config(include_env=False).path("cache_root")


def master_cache_path(cache_dir: Path | str, today: date) -> Path:
    """The date-stamped cache file for ``today``'s master dump."""
    return Path(cache_dir) / CACHE_SUBDIR / f"OpenAPIScripMaster_{today.isoformat()}.json"


def load_master_file(path: Path | str) -> InstrumentMaster:
    """Build an :class:`InstrumentMaster` from a saved raw master JSON (e.g. the test fixture).

    Reads a file, so not pure -- but no network and no clock. Used by the frozen-fixture test
    and, internally, by :func:`load_instrument_master` after a cache hit.
    """
    source = Path(path)
    if not source.is_file():
        raise InstrumentMasterError(f"Instrument-master file not found: {source}")
    try:
        rows = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstrumentMasterError(f"Could not read instrument master {source}: {exc}") from exc
    return InstrumentMaster.from_rows(rows)


def load_instrument_master(
    *,
    cache_dir: Path | str | None = None,
    today: date | None = None,
    allow_network: bool = False,
    fetcher: Callable[[str], bytes] | None = None,
) -> InstrumentMaster:
    """Return today's instrument master, downloading it at most once per calendar day.

    A dump already fetched on ``today`` is served from the date-stamped cache without touching
    the network. Otherwise a live download runs -- but only when ``allow_network`` is true, so
    pytest (which never passes it) stays offline.

    Args:
        cache_dir: where the date-stamped files live; defaults to config ``cache_dir``.
        today: the IST calendar date; defaults to the system date.
        allow_network: explicit opt-in to the live download.
        fetcher: how to pull the raw bytes live; defaults to :func:`_download_master`.

    Raises:
        InstrumentMasterError: offline with no cache for ``today``, or the download failed.
    """
    stamp = today if today is not None else date.today()
    base = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    path = master_cache_path(base, stamp)
    if path.is_file():
        return load_master_file(path)
    if not allow_network:
        raise InstrumentMasterError(
            f"No instrument master cached for {stamp} at {path} and allow_network is False. "
            "The daily dump is downloaded once per day behind an explicit opt-in "
            "(CONTEXT 4.3); pass allow_network=True to fetch it."
        )
    payload = (fetcher or _download_master)(SCRIP_MASTER_URL)
    try:
        rows = json.loads(payload)
    except ValueError as exc:
        raise InstrumentMasterError(f"Downloaded instrument master is not valid JSON: {exc}") from exc
    master = InstrumentMaster.from_rows(rows)
    atomic_write_bytes(path, payload)  # cache only after it parsed to a usable master
    return master


def _download_master(url: str) -> bytes:
    """Fetch the ~40 MB master dump once. Called only under allow_network=True."""
    import requests

    response = requests.get(url, timeout=180, headers={"User-Agent": "acumen/1.0"})
    response.raise_for_status()
    return response.content


# --- CLI (the operator's own step; QUESTIONS.md Q-18 runbook step 3) --------------------


def cached_masters(cache_dir: Path | str | None = None) -> tuple[Path, ...]:
    """Every date-stamped master file on disk, oldest name first. Never fetches."""
    base = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    home = base / CACHE_SUBDIR
    if not home.is_dir():
        return ()
    return tuple(sorted(home.glob("OpenAPIScripMaster_*.json")))


def parse_args(argv: Sequence[str] | None = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="acumen-instrument-master",
        description=(
            "Fetch today's Angel One instrument master and NAME the file it wrote "
            "(CONTEXT 4.3). Every pack that quotes a tick size cites that filename."
        ),
    )
    parser.add_argument("--cache-dir", default=None, help="cache root (default: config cache_root)")
    parser.add_argument(
        "--allow-network", action="store_true", help="REQUIRED to fetch; without it, report only"
    )
    return parser.parse_args(argv)


def run(args: Any) -> int:
    """Report what is cached, fetch today's dump when allowed, and name the file.

    Idempotent by construction: :func:`load_instrument_master` serves a dump already fetched
    today from the date-stamped cache without touching the network, so re-running this command
    after a Ctrl-C costs one file read. It is a separate operator step (rather than a side
    effect of the backfill) precisely so the filename is decided and printed BEFORE the long
    run starts -- QUESTIONS.md Q-18, runbook step 3.
    """
    base = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    existing = cached_masters(base)
    print(f"cache dir    : {base / CACHE_SUBDIR}")
    print(f"already held : {len(existing)} dump(s)" + (f", newest {existing[-1].name}" if existing else ""))

    if not args.allow_network:
        print("\nSTOPPING (no --allow-network). Nothing was fetched and nothing was written.")
        return 0 if existing else 1

    today = date.today()
    path = master_cache_path(base, today)
    master = load_instrument_master(cache_dir=base, today=today, allow_network=True)
    print(f"\nMASTER FILE  : {path}")
    print(f"  instruments: {len(master):,} NSE {EQ_SUFFIX.lstrip('-')} rows")
    print(f"  cite it as : {path.name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except InstrumentMasterError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover -- exercised through main()
    raise SystemExit(main())
