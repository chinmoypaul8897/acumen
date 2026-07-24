"""Gentle HTTP access to NSE's public JSON endpoints (CONTEXT 4.1).

This module is I/O ONLY. It fetches bytes and caches them; it understands nothing about
universes, holidays or trading. The parsing lives in :mod:`acumen.universe` and
:mod:`acumen.calendar` as pure functions, so every rule this project cares about can be
tested from a frozen snapshot with no network in sight (CONTEXT 6: fetch and compute are
separated).

Politeness (CONTEXT 4.1: "the JSON endpoints are pulled gently (once/day max) -- never
bulk-scraped"):

* one live pull per calendar DAY per endpoint -- :func:`cached_json` serves the on-disk copy
  for the rest of the day and never opens a socket;
* the network is only ever touched when the caller passes ``allow_network=True``, which is
  what keeps the test suite offline;
* at most ~2 requests/second, exponential backoff between attempts;
* a browser-like User-Agent, because NSE answers a bare client with HTTP 403.

Failure is always LOUD. A transient 403 burst is normal and is retried (CLAUDE.md network
rules), but an exhausted retry budget raises :class:`NseFetchError` -- it is never reported
as "no data". A silently empty universe or an empty holiday list would look exactly like a
market where nothing trades, which is the most expensive lie this repo could tell.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Callable

import requests

from .atomic_io import atomic_write_text

#: NSE serves HTTP 403 to clients without a browser-like User-Agent. This is not evasion:
#: the pull is one request per endpoint per day of a page the site publishes publicly.
DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

#: Fetched only to pick up cookies when an API call is refused; never parsed.
NSE_HOME_URL: str = "https://www.nseindia.com/"

#: CLAUDE.md: polite throttle, at most ~2 requests/second.
MIN_SECONDS_BETWEEN_REQUESTS: float = 0.5

DEFAULT_TIMEOUT: float = 30.0

#: One initial try plus three retries. CONTEXT 4.3: transient "access denied" bursts are
#: NORMAL -- retry, never treat the first failure as empty.
DEFAULT_MAX_ATTEMPTS: int = 4

#: HTTP codes worth retrying: NSE's bot-shield (401/403), rate limiting (429), and any
#: server-side fault. Anything else is a real error and fails immediately.
_RETRYABLE_STATUS: frozenset[int] = frozenset({401, 403, 408, 429, 500, 502, 503, 504})

#: Monotonic timestamp of the last outbound request, for the process-wide throttle.
_last_request_at: list[float] = [0.0]


class NseFetchError(RuntimeError):
    """An NSE endpoint could not be fetched, or its cached copy is unusable."""


def new_session() -> requests.Session:
    """Return a :class:`requests.Session` with the browser-like headers NSE requires."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": NSE_HOME_URL,
            "Connection": "keep-alive",
        }
    )
    return session


def fetch_json(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET ``url`` and return its decoded JSON, retrying transient failures.

    Args:
        url: the endpoint to fetch.
        session: an existing session (a fresh one is built when omitted).
        timeout: per-request timeout in seconds.
        max_attempts: total attempts, including the first.
        sleep: injected for tests; the throttle and backoff call it.

    Raises:
        NseFetchError: every attempt failed. The message names the URL and the last reason
            -- never a partial body, never a credential (there are none on these endpoints).
    """
    if max_attempts < 1:
        raise NseFetchError(f"max_attempts must be >= 1, got {max_attempts}.")

    http = session if session is not None else new_session()
    reason = "no attempt was made"
    warmed_up = False

    for attempt in range(1, max_attempts + 1):
        _throttle(sleep)
        try:
            response = http.get(url, timeout=timeout)
        except requests.RequestException as exc:
            reason = f"{type(exc).__name__} on request"
        else:
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    # HTTP 200 carrying a bot-shield HTML page: a retry usually clears it.
                    reason = "HTTP 200 whose body is not JSON"
            elif response.status_code in _RETRYABLE_STATUS:
                reason = f"HTTP {response.status_code}"
                if response.status_code in (401, 403) and not warmed_up:
                    # Once per call only: a second warm-up would not tell us anything new
                    # and would double our request count against a site we pull once a day.
                    warmed_up = True
                    _warm_up_cookies(http, timeout=timeout, sleep=sleep)
            else:
                raise NseFetchError(
                    f"{url} returned HTTP {response.status_code}; not a transient status, "
                    "so no retry was attempted."
                )

        if attempt < max_attempts:
            sleep(float(2 ** (attempt - 1)))

    raise NseFetchError(
        f"Could not fetch {url} after {max_attempts} attempts (last reason: {reason}). "
        "This is an ERROR, not an empty result -- callers must not continue with an empty "
        "universe or an empty holiday list."
    )


def read_cache(cache_path: Path) -> tuple[date, Any] | None:
    """Return ``(fetched_on, payload)`` from a day-cache file, or ``None`` if absent.

    Raises:
        NseFetchError: the file exists but is not a well-formed cache envelope. A damaged
            cache is reported, never silently treated as "nothing cached" -- deleting it is
            the operator's call, not this module's.
    """
    path = Path(cache_path)
    if not path.is_file():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NseFetchError(f"Cache file {path} is unreadable or not valid JSON: {exc}") from exc

    if not isinstance(envelope, dict) or "fetched_on" not in envelope or "payload" not in envelope:
        raise NseFetchError(
            f"Cache file {path} is not an acumen day-cache envelope "
            "(expected keys: source_url, fetched_on, payload). Delete it to force a refetch."
        )
    try:
        fetched_on = date.fromisoformat(str(envelope["fetched_on"]))
    except ValueError as exc:
        raise NseFetchError(
            f"Cache file {path} has a malformed fetched_on value; expected YYYY-MM-DD."
        ) from exc
    return fetched_on, envelope["payload"]


def write_cache(cache_path: Path, payload: Any, *, url: str, fetched_on: date) -> Path:
    """Write the day-cache envelope for ``payload`` ATOMICALLY, creating parent directories.

    The write goes to a temp file in the same directory and is then ``os.replace``d into
    position, so an interrupted run leaves either the previous cache or the complete new one
    -- never a truncated file (REVIEW_1 Finding 2).
    """
    envelope = {
        "source_url": url,
        "fetched_on": fetched_on.isoformat(),
        "payload": payload,
    }
    return atomic_write_text(
        Path(cache_path), json.dumps(envelope, indent=1, sort_keys=True) + "\n"
    )


def cached_json(
    url: str,
    cache_path: Path,
    *,
    today: date,
    allow_network: bool,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Return the endpoint payload, pulling it live at most once per calendar day.

    A cache written earlier on ``today`` is served without touching the network. Anything
    older is refetched -- but only when ``allow_network`` is true.

    Args:
        url: the endpoint.
        cache_path: the day-cache file for this endpoint.
        today: the current IST calendar date, supplied by the caller so nothing here reads
            the clock (CONTEXT 7-E8).
        allow_network: the explicit opt-in to a live pull. False means "offline": a stale
            or missing cache raises instead of silently reaching out. pytest never passes
            True, which is what keeps the suite offline.
        session: an existing session; a fresh one is built when omitted.
        sleep: injected for tests.

    Raises:
        NseFetchError: offline with no cache for ``today``, the cache is damaged and no live
            pull was authorised, or the live pull failed.
    """
    try:
        cached = read_cache(cache_path)
    except NseFetchError as exc:
        # A damaged cache stays LOUD on the read path (read_cache and the load_cached_*
        # helpers still raise). What changes here is that the operator has a way out: an
        # explicit allow_network=True refetch is allowed to overwrite it, so a truncated
        # file no longer has to be deleted by hand (REVIEW_1 Finding 2).
        if not allow_network:
            raise
        warnings.warn(
            f"Replacing a damaged day-cache at {Path(cache_path)} with a fresh pull "
            f"({exc}).",
            RuntimeWarning,
            stacklevel=2,
        )
        cached = None

    if cached is not None and cached[0] == today:
        return cached[1]

    if not allow_network:
        age = "no cache file exists" if cached is None else f"the cache is from {cached[0]}"
        raise NseFetchError(
            f"Refusing to fetch {url}: {age} and allow_network is False. "
            "Live pulls are opt-in (CONTEXT 4.1 keeps these endpoints to one pull per day); "
            f"pass allow_network=True to refresh {Path(cache_path)}."
        )

    payload = cached_json_fetch(url, session=session, sleep=sleep)
    write_cache(cache_path, payload, url=url, fetched_on=today)
    return payload


def cached_json_fetch(
    url: str,
    *,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """The live half of :func:`cached_json`, split out so tests can replace just this."""
    return fetch_json(url, session=session, sleep=sleep)


def _throttle(sleep: Callable[[float], None]) -> None:
    """Keep outbound requests at or below ~2 per second, process-wide."""
    wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - _last_request_at[0])
    if wait > 0:
        sleep(wait)
    _last_request_at[0] = time.monotonic()


def _warm_up_cookies(
    session: requests.Session, *, timeout: float, sleep: Callable[[float], None]
) -> None:
    """Fetch the NSE home page once so the session picks up its cookies.

    Best-effort by design: the home page itself answers 403 to this client, yet the API
    endpoints answer 200, so a failure here must not abort the real request.
    """
    _throttle(sleep)
    try:
        session.get(NSE_HOME_URL, timeout=timeout)
    except requests.RequestException:
        return
