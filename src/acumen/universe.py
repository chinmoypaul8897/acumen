"""The tradable universe: NSE F&O stock underlyings (CONTEXT 3.1, 4.1).

CONTEXT 3.1: "Universe: all NSE F&O stock underlyings (~210; source 4.1). Indexes are NOT
traded and need no data (trader R1-Q10) ... skip them entirely." The endpoint returns both
lists in one payload; :func:`parse_universe` keeps ``UnderlyingList`` and drops
``IndexList``.

Two layers, deliberately separate (CONTEXT 6):

* :func:`parse_universe` is PURE -- payload in, symbols out, no I/O, no clock;
* :func:`fetch_universe` does the gentle once-a-day live pull via :mod:`acumen.nse_http`.

An empty or unparseable universe is always an ERROR. Returning ``()`` would let a
backtest or a live sweep run over nothing and report a clean, meaningless zero.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from . import nse_http

#: CONTEXT 4.1 -- verified live 21-Jul-2026, 210 stocks.
UNDERLYING_INFORMATION_URL: str = "https://www.nseindia.com/api/underlying-information"

#: Day-cache file name under the cache directory (which lives under data_root, outside the repo).
CACHE_FILENAME: str = "underlying_information.json"

#: The key holding the F&O STOCK underlyings. ``IndexList`` is the other one and is dropped.
_UNDERLYING_KEY: str = "UnderlyingList"
_INDEX_KEY: str = "IndexList"


class UniverseError(RuntimeError):
    """The F&O universe could not be determined."""


def parse_universe(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Extract the F&O stock underlyings from an ``underlying-information`` payload.

    PURE: no I/O, no network, no clock.

    Args:
        payload: the decoded endpoint JSON, i.e. ``{"data": {"IndexList": [...],
            "UnderlyingList": [...]}}``.

    Returns:
        Every underlying's symbol, upper-cased, de-duplicated, sorted -- so the order is a
        property of the data and not of NSE's ``serialNumber`` field.

    Raises:
        UniverseError: the payload has the wrong shape, a row has no usable symbol, or the
            list is empty. Never returns an empty tuple.
    """
    if not isinstance(payload, Mapping):
        raise UniverseError(
            f"Universe payload must be a JSON object, got {type(payload).__name__}."
        )
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise UniverseError(
            "Universe payload has no 'data' object "
            f"(top-level keys: {_key_list(payload)}). The endpoint format may have changed."
        )
    rows = data.get(_UNDERLYING_KEY)
    if not isinstance(rows, list):
        raise UniverseError(
            f"Universe payload has no '{_UNDERLYING_KEY}' array "
            f"(keys under 'data': {_key_list(data)})."
        )
    if not rows:
        raise UniverseError(
            f"'{_UNDERLYING_KEY}' is empty. Refusing to return an empty universe: a "
            "backtest or live sweep over zero stocks reports a clean, meaningless zero."
        )

    symbols: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise UniverseError(
                f"{_UNDERLYING_KEY}[{index}] is {type(row).__name__}, expected an object."
            )
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise UniverseError(f"{_UNDERLYING_KEY}[{index}] has no usable 'symbol' value.")
        symbols.add(symbol.strip().upper())

    if not symbols:
        raise UniverseError(f"'{_UNDERLYING_KEY}' yielded no symbols.")
    return tuple(sorted(symbols))


def parse_index_symbols(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the INDEX symbols, which CONTEXT 3.1 excludes from trading.

    PURE. Provided so the exclusion can be asserted (an index must never appear in
    :func:`parse_universe`'s output), not so anything downstream trades them.
    """
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
        raise UniverseError("Universe payload has no 'data' object.")
    rows = payload["data"].get(_INDEX_KEY)
    if not isinstance(rows, list):
        raise UniverseError(f"Universe payload has no '{_INDEX_KEY}' array.")
    symbols = {
        row["symbol"].strip().upper()
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("symbol"), str) and row["symbol"].strip()
    }
    return tuple(sorted(symbols))


def load_universe(path: Path) -> tuple[str, ...]:
    """Parse a saved RAW endpoint payload (e.g. the frozen test snapshot).

    Reads a file, so it is not pure -- but it does no network and no clock read.

    Raises:
        UniverseError: the file is missing, is not JSON, or fails :func:`parse_universe`.
    """
    source = Path(path)
    if not source.is_file():
        raise UniverseError(f"Universe snapshot not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UniverseError(f"Could not read universe snapshot {source}: {exc}") from exc
    return parse_universe(payload)


def cache_path(cache_dir: Path | None = None) -> Path:
    """Return the day-cache path for the universe endpoint."""
    base = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    return base / CACHE_FILENAME


def default_cache_dir() -> Path:
    """``<data_root>/nse`` from config.yaml -- OUTSIDE the repo tree (CLAUDE.md Q-18 layer 1)."""
    from .config import load_config  # local import: parsing must not require a config file

    return load_config(include_env=False).path("data_root") / "nse"


def fetch_universe(
    *,
    cache_dir: Path | None = None,
    today: date | None = None,
    allow_network: bool = False,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
) -> tuple[str, ...]:
    """Return today's F&O universe, pulling it live at most once per calendar day.

    Args:
        cache_dir: where the day-cache lives; defaults to :func:`default_cache_dir`.
        today: the IST calendar date; defaults to the system date. Injectable so the
            once-a-day rule can be tested without waiting a day.
        allow_network: explicit opt-in to a live pull. While False nothing reaches out --
            whatever is cached is served at ANY age (offline means "use exactly what is on
            disk", architect 31-Jul-2026) and only a MISSING or damaged cache raises. This
            is what keeps pytest offline.
        session: an existing :class:`requests.Session`.
        sleep: injected for tests.

    Raises:
        NseFetchError: offline with no cache file at all, or the live pull failed.
        UniverseError: the payload parsed but is not a usable universe.
    """
    kwargs: dict[str, Any] = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    payload = nse_http.cached_json(
        UNDERLYING_INFORMATION_URL,
        cache_path(cache_dir),
        today=today if today is not None else date.today(),
        allow_network=allow_network,
        session=session,
        **kwargs,
    )
    return parse_universe(payload)


def load_cached_universe(cache_dir: Path | None = None) -> tuple[date, tuple[str, ...]]:
    """Return ``(fetched_on, symbols)`` from the day-cache at ANY age.

    The staleness is handed back to the caller instead of being hidden: a caller that
    decides yesterday's universe is good enough must say so in its own code.

    Raises:
        UniverseError: no cache file exists.
        NseFetchError: the cache file is damaged.
    """
    path = cache_path(cache_dir)
    cached = nse_http.read_cache(path)
    if cached is None:
        raise UniverseError(
            f"No cached universe at {path}. Run fetch_universe(allow_network=True) once."
        )
    fetched_on, payload = cached
    return fetched_on, parse_universe(payload)


def _key_list(mapping: Mapping[str, Any]) -> str:
    return ", ".join(sorted(str(key) for key in mapping)) or "<none>"
