"""Angel One SmartAPI client for historical 1-minute / daily candles (CONTEXT 4.3).

This is the intraday counterpart of :mod:`acumen.nse_http`: it is I/O ONLY -- it logs in,
paces requests and fetches candle bytes; it understands nothing about quality gates, stores
or the strategy. The parsing half (:func:`parse_candles`) is PURE, so a frozen SmartAPI
response can be turned into candles with no network in sight and the whole test suite stays
offline (CONTEXT 6: fetch and compute are separated).

What CONTEXT 4.3 pins, and where it lives here:

* **Auth** -- a daily session (dies at midnight); login = client code + PIN + a pyotp TOTP
  computed on the ``.env`` TOTP secret. Credentials come from ``.env`` via
  :class:`acumen.config` and are NEVER printed, logged, put in an exception message, or
  stored anywhere they could be repr'd (CLAUDE.md rule 4). :class:`Credentials` redacts
  itself; the client's ``__repr__`` shows only non-secret state.
* **Read-only** -- the only endpoints used are ``getCandleData`` and ``getProfile``. No
  order-placement call exists in this module or this repo (R4, CONTEXT 1).
* **Throttle** -- SmartAPI allows 3/s; the chunk-5A card sets a 0.5s gap (~2/s), enforced by
  a process-wide monotonic clock so nothing here can outrun it.
* **Backoff** -- transient "access denied" / "couldn't parse the json response" bursts are
  NORMAL, especially in live hours (PoC4 measured them; RESULTS.md G). They are retried with
  exponential backoff, never treated as "no data" on the first failure (CONTEXT 4.3). A
  window that never comes back after the retry budget is exhausted RAISES -- the backfill
  records it as an error and retries it on the next run, exactly like the daily store.
* **Session refresh** -- a mid-run session expiry (rare on a minutes-long backfill, real on a
  run that crosses midnight) is detected from the error and repaired by a fresh
  ``generateSession`` with a new TOTP, then the call is retried.
* **The ONE_DAY 00:00 trap** -- SmartAPI stamps a ONE_DAY candle at 00:00, so a request whose
  ``fromdate`` starts at 09:15 returns EMPTY (RESULTS.md G, PoC-discovered). :meth:`get_candles`
  forces a ONE_DAY window to start at 00:00 rather than silently returning nothing.

Everything is naive IST (CONTEXT 7-E8): SmartAPI stamps candles ``...T09:15:00+05:30`` and
:func:`parse_candles` verifies the offset is IST and drops the tzinfo, so nothing downstream
ever carries a timezone (the normalization REVIEW_0/REVIEW_3 F7 asked the ingest layer to do).
Prices are integer paise via :class:`~decimal.Decimal` on the text form, never via a float
product (CONTEXT 7-E11), the same discipline :mod:`acumen.bhavcopy` uses on the daily side.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Sequence

#: The four ``.env`` keys CONTEXT 4.3 names for the SmartAPI login. Read via
#: :func:`acumen.config.env_value`; their VALUES never leave this process in any message.
ENV_API_KEY: str = "SMARTAPI_KEY"
ENV_CLIENT_CODE: str = "SMARTAPI_CLIENT_CODE"
ENV_PIN: str = "SMARTAPI_PIN"
ENV_TOTP_SECRET: str = "SMARTAPI_TOTP_SECRET"

#: chunk-5A card: "polite throttle (0.5s between calls)". SmartAPI permits 3/s; 0.5s is ~2/s,
#: the same courtesy margin CONTEXT 4.3 describes ("our client throttles to ~2/s").
MIN_SECONDS_BETWEEN_REQUESTS: float = 0.5

#: One initial try plus four retries -- the PoC's 1+2+4+8+16s backoff ladder (RESULTS.md F/G:
#: a transient-403 burst clears within that budget, and the data arrives on the next poll).
DEFAULT_MAX_ATTEMPTS: int = 5

#: NSE cash exchange segment, the only one this project trades (CONTEXT 3.1).
EXCHANGE_NSE: str = "NSE"

#: CONTEXT 4.3 intervals we use. FIFTEEN_MINUTE exists at the API but we build 15-min bars
#: from 1-min for one source of truth (CONTEXT 7-E1), so it is deliberately NOT allowed here.
INTERVAL_ONE_MINUTE: str = "ONE_MINUTE"
INTERVAL_ONE_DAY: str = "ONE_DAY"
_ALLOWED_INTERVALS: frozenset[str] = frozenset({INTERVAL_ONE_MINUTE, INTERVAL_ONE_DAY})

#: CONTEXT 4.3 request-size caps (the API's DATE-range limits), enforced so a too-wide window
#: fails loudly here rather than returning a silently truncated candle set from the server.
MAX_DAYS_ONE_MINUTE: int = 30
MAX_DAYS_ONE_DAY: int = 2000

#: **PoC-discovered (live, 2026-07-25): SmartAPI's ONE_MINUTE endpoint also caps the RESPONSE
#: at 8000 candles**, independent of the 30-day date cap above. A 30-calendar-day window can
#: hold up to ~22 trading days (8250 candles); when the response would exceed 8000, the server
#: returns the MOST RECENT 8000 and silently DROPS the oldest -- so the first day of an
#: over-large window comes back missing its morning. Measured: a 30-day TCS window returned
#: exactly 8000 candles first-stamped 13:25 (250 morning candles gone), while the same first
#: day fetched alone returned a full 375. The backfill therefore uses a window narrow enough
#: to never exceed this (:data:`acumen.minute_backfill.ONE_MINUTE_WINDOW_DAYS`), and
#: :func:`get_candles` flags any response that hits the cap so a future caller cannot truncate
#: silently.
ONE_MINUTE_RESPONSE_CAP: int = 8000

#: IST -- the exchange timezone. Every SmartAPI candle stamp must carry exactly this offset;
#: anything else means the data is not what CONTEXT 7-E8 assumes and is rejected, not converted.
_IST: timezone = timezone(timedelta(hours=5, minutes=30))

#: How a non-success reply is classified (see :meth:`SmartApiClient._attempt_once`): a reply
#: whose message/errorcode matches :data:`_NO_DATA_MARKERS` is an empty window (a real answer);
#: one matching :data:`_SESSION_EXPIRED_MARKERS` is repaired by a fresh login; **everything
#: else non-success is TRANSIENT and retried**. Defaulting the unrecognized case to "retry" is
#: deliberate -- CONTEXT 4.3 says the false "access denied" / unparseable-JSON bursts are NORMAL
#: and must be retried, and an unfamiliar transient message must not be mistaken for "no data".
#: (There is intentionally no allow-list of transient substrings: an allow-list would let an
#: unlisted transient message fall through to a hard failure, the exact mistake CONTEXT 4.3
#: warns against.)

#: Substrings / error codes that mark the SESSION as expired -- repaired by a fresh login
#: rather than a plain retry (the daily session dies at midnight, CONTEXT 4.3).
_SESSION_EXPIRED_MARKERS: tuple[str, ...] = (
    "invalid token",
    "token is invalid",
    "expired",
    "invalid session",
    "session expired",
    "ag8001",  # SmartAPI: Invalid Token
    "ag8002",  # SmartAPI: Token Expired
    "ag8003",  # SmartAPI: Token missing
)

#: Substrings / error codes that mean the window genuinely holds NO candles -- a real answer
#: (before-listing months, RESULTS.md B), never an error to retry.
_NO_DATA_MARKERS: tuple[str, ...] = ("no data", "ab1004")


class SmartApiError(RuntimeError):
    """A SmartAPI call could not be completed, or returned an unusable reply.

    Raised only after the retry / session-refresh budget is spent. The message never carries
    a credential -- there are none in a candle reply, and the login path is careful not to
    echo the secrets it was given (CLAUDE.md rule 4).
    """


@dataclass(frozen=True)
class OneMinuteBar:
    """One candle as SmartAPI returned it, normalized to this repo's conventions.

    ``stamp`` is naive IST and OPEN-stamped (CONTEXT 7-E8/E12); prices are integer paise
    (CONTEXT 7-E11); ``volume`` is shares. The same shape serves ONE_MINUTE and ONE_DAY --
    a ONE_DAY candle is just stamped at 00:00.
    """

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


# --- parsing (PURE) --------------------------------------------------------------------


def parse_candles(data: Any) -> tuple[OneMinuteBar, ...]:
    """Turn a ``getCandleData`` ``data`` array into normalized bars. PURE.

    The SmartAPI shape is a list of ``[timestamp, open, high, low, close, volume]``, with the
    timestamp an ISO string carrying the +05:30 IST offset. This function:

    * verifies the offset is IST and DROPS the tzinfo (naive IST, CONTEXT 7-E8) -- the
      +05:30 normalization the ingest layer owes (REVIEW_0/REVIEW_3 F7);
    * converts each price to integer paise via :class:`~decimal.Decimal` on its text form,
      never a float product (CONTEXT 7-E11);
    * returns the bars in the order given (SmartAPI returns them chronologically).

    Args:
        data: the ``data`` value from a ``getCandleData`` reply -- a list of rows, or ``None``
            / ``[]`` for a window with no candles.

    Returns:
        The parsed bars, possibly empty (an empty window is a legitimate answer, RESULTS.md B).

    Raises:
        SmartApiError: a row has the wrong shape, a stamp is not IST-offset, or a price is not
            a whole number of paise. A malformed reply is never silently dropped to empty.
    """
    if data is None:
        return ()
    if not isinstance(data, (list, tuple)):
        raise SmartApiError(
            f"getCandleData 'data' must be a list, got {type(data).__name__}."
        )
    bars: list[OneMinuteBar] = []
    for index, row in enumerate(data):
        if not isinstance(row, (list, tuple)) or len(row) != 6:
            raise SmartApiError(
                f"candle row {index} has the wrong shape (expected 6 fields "
                f"[ts,o,h,l,c,v], got {row!r})."
            )
        stamp = _parse_stamp(row[0], index)
        bars.append(
            OneMinuteBar(
                stamp=stamp,
                open_paise=_paise(row[1], "open", index),
                high_paise=_paise(row[2], "high", index),
                low_paise=_paise(row[3], "low", index),
                close_paise=_paise(row[4], "close", index),
                volume=_whole(row[5], "volume", index),
            )
        )
    return tuple(bars)


def _parse_stamp(value: Any, index: int) -> datetime:
    """Parse a SmartAPI IST timestamp to a naive-IST datetime, rejecting any other offset."""
    if not isinstance(value, str) or not value.strip():
        raise SmartApiError(f"candle row {index} has an empty timestamp.")
    text = value.strip()
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise SmartApiError(f"candle row {index} timestamp {text!r} is not an ISO datetime.")
    if parsed.tzinfo is not None:
        if parsed.utcoffset() != _IST.utcoffset(None):
            raise SmartApiError(
                f"candle row {index} timestamp {text!r} is not IST (+05:30). SmartAPI stamps "
                "IST; a different offset means the data is not what CONTEXT 7-E8 assumes."
            )
        parsed = parsed.replace(tzinfo=None)  # normalize to naive IST (drop, never convert)
    return parsed


def _paise(value: Any, field: str, index: int) -> int:
    """Convert a candle price to integer paise EXACTLY via Decimal on its text (CONTEXT 7-E11)."""
    try:
        scaled = Decimal(str(value)) * 100
    except (InvalidOperation, ValueError) as exc:
        raise SmartApiError(f"candle row {index}: {field}={value!r} is not a number.") from exc
    if scaled != scaled.to_integral_value():
        raise SmartApiError(
            f"candle row {index}: {field}={value!r} is not a whole number of paise "
            "(prices are integer paise internally, CONTEXT 7-E11)."
        )
    return int(scaled)


def _whole(value: Any, field: str, index: int) -> int:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SmartApiError(f"candle row {index}: {field}={value!r} is not a number.") from exc
    if number != number.to_integral_value():
        raise SmartApiError(f"candle row {index}: {field}={value!r} must be a whole number.")
    return int(number)


# --- credentials (secret; never printed) -----------------------------------------------


@dataclass(frozen=True)
class Credentials:
    """The four SmartAPI secrets. Redacts itself so no repr / log / traceback leaks them."""

    api_key: str
    client_code: str
    pin: str
    totp_secret: str

    def __repr__(self) -> str:  # CLAUDE.md rule 4: never print/log credential contents
        return "Credentials(<redacted>)"

    @classmethod
    def from_env(cls) -> Credentials:
        """Read the four keys from ``.env`` via :func:`acumen.config.env_value`.

        Raises:
            ConfigError: any of the four keys is missing (the message names the KEY, never a
                value).
        """
        from .config import env_value

        return cls(
            api_key=str(env_value(ENV_API_KEY)),
            client_code=str(env_value(ENV_CLIENT_CODE)),
            pin=str(env_value(ENV_PIN)),
            totp_secret=str(env_value(ENV_TOTP_SECRET)),
        )


def _quiet_library_logging() -> None:
    """Silence the SmartApi library's own logging (CLAUDE.md rule 4).

    The vendor ``SmartConnect`` logs via ``logzero`` at ERROR level on a failed request, and
    that error line includes the FULL request headers -- ``Authorization: Bearer <jwt>`` and
    ``X-PrivateKey: <api key>``. A transient timeout (NORMAL, CONTEXT 4.3) would otherwise spill
    a session token and the API key to stderr / any run log. We raise its threshold above ERROR
    so the credential-bearing lines are never emitted. Best-effort: if logzero is absent (tests
    never build a real connect) this is a no-op.
    """
    import logging

    for name in ("logzero", "logzero_default", "SmartApi", "smartConnect"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        import logzero

        logzero.loglevel(logging.CRITICAL)  # the default logger SmartConnect actually uses
    except Exception:
        pass


def _default_connect_factory(api_key: str) -> Any:
    """Build a real ``SmartConnect``. Imported lazily so tests never need the package."""
    _quiet_library_logging()  # before anything the library might log a credential (rule 4)
    from SmartApi import SmartConnect  # type: ignore[import-not-found]

    return SmartConnect(api_key=api_key)


def _default_totp(secret: str) -> str:
    """Current TOTP for ``secret`` (spaces stripped, as the PoC found some secrets carry them)."""
    import pyotp  # local import: only the login path needs it

    return pyotp.TOTP(secret.replace(" ", "")).now()


# --- the client (I/O) ------------------------------------------------------------------


class SmartApiClient:
    """A logged-in SmartAPI session with pacing, backoff and session refresh.

    Injectable end to end so the whole thing is testable offline: ``connect_factory`` builds
    the underlying ``SmartConnect`` (a fake in tests), ``totp_provider`` computes the OTP, and
    ``sleep`` is the throttle/backoff clock. The default factory imports the real library.

    Not a dataclass on purpose: it holds :class:`Credentials`, and a frozen dataclass would
    expose them through ``repr``/``asdict``. ``__repr__`` here shows only non-secret state.
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        connect_factory: Callable[[str], Any] = _default_connect_factory,
        totp_provider: Callable[[str], str] = _default_totp,
        sleep: Callable[[float], None] = time.sleep,
        min_interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_relogins: int = 2,
    ) -> None:
        if max_attempts < 1:
            raise SmartApiError(f"max_attempts must be >= 1, got {max_attempts}.")
        self._credentials = credentials
        self._connect_factory = connect_factory
        self._totp_provider = totp_provider
        self._sleep = sleep
        self._min_interval = float(min_interval)
        self._max_attempts = int(max_attempts)
        self._max_relogins = int(max_relogins)
        self._connect: Any | None = None
        self._logged_in = False
        self._last_call = 0.0

    def __repr__(self) -> str:
        return f"SmartApiClient(logged_in={self._logged_in})"  # no secret ever in here

    # --- login ---------------------------------------------------------------

    def login(self) -> SmartApiClient:
        """Open a session with a fresh TOTP. Returns self so it can be chained.

        Raises:
            SmartApiError: the login was refused. The message carries SmartAPI's own status
                text (which never includes the PIN or TOTP secret), never the credentials.
        """
        connect = self._connect_factory(self._credentials.api_key)
        otp = self._totp_provider(self._credentials.totp_secret)
        try:
            response = connect.generateSession(self._credentials.client_code, self._credentials.pin, otp)
        except Exception as exc:  # network / library error during login
            raise SmartApiError(f"SmartAPI login failed: {type(exc).__name__}: {exc}") from exc
        if not isinstance(response, dict) or not response.get("status"):
            raise SmartApiError(f"SmartAPI login was refused: {_safe_message(response)}")
        self._connect = connect
        self._logged_in = True
        return self

    def logout(self) -> None:
        """Best-effort terminate the session (read-only client; harmless if it fails)."""
        if self._connect is None:
            return
        try:
            self._connect.terminateSession(self._credentials.client_code)
        except Exception:  # a logout that fails changes nothing -- the session dies at midnight
            pass
        finally:
            self._logged_in = False

    def _require_connect(self) -> Any:
        if self._connect is None or not self._logged_in:
            raise SmartApiError("Not logged in. Call login() before requesting candles.")
        return self._connect

    # --- candles -------------------------------------------------------------

    def get_candles(
        self,
        token: str,
        interval: str,
        from_dt: datetime,
        to_dt: datetime,
        *,
        exchange: str = EXCHANGE_NSE,
    ) -> tuple[OneMinuteBar, ...]:
        """Fetch and parse candles for ``[from_dt, to_dt]`` (naive IST), paced and retried.

        Args:
            token: the instrument ``symboltoken`` (from the instrument master, chunk 5A).
            interval: :data:`INTERVAL_ONE_MINUTE` or :data:`INTERVAL_ONE_DAY`.
            from_dt: window start, naive IST. For ONE_DAY it is forced to 00:00 -- SmartAPI
                stamps the daily candle at midnight and a 09:15 start returns EMPTY
                (RESULTS.md G, the PoC-discovered trap).
            to_dt: window end, naive IST.
            exchange: the exchange segment; NSE cash by default (CONTEXT 3.1).

        Returns:
            The bars (empty when the window genuinely holds none).

        Raises:
            SmartApiError: bad arguments, or the call failed after the retry / relogin budget.
        """
        if interval not in _ALLOWED_INTERVALS:
            raise SmartApiError(
                f"interval {interval!r} is not used by this project; allowed: "
                f"{sorted(_ALLOWED_INTERVALS)} (15-min bars are built from 1-min, CONTEXT 7-E1)."
            )
        for label, value in (("from_dt", from_dt), ("to_dt", to_dt)):
            if not isinstance(value, datetime):
                raise SmartApiError(f"{label} must be a datetime, got {type(value).__name__}.")
            if value.tzinfo is not None:
                raise SmartApiError(f"{label} must be naive IST (CONTEXT 7-E8); got {value!r}.")
        if to_dt < from_dt:
            raise SmartApiError(f"Empty window: {to_dt} is before {from_dt}.")

        start = from_dt
        if interval == INTERVAL_ONE_DAY:
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)  # the 00:00 trap
        self._check_span(interval, start.date(), to_dt.date())

        params = {
            "exchange": exchange,
            "symboltoken": str(token),
            "interval": interval,
            "fromdate": start.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        data = self._call_with_retry(params)
        return parse_candles(data)

    @staticmethod
    def _check_span(interval: str, start: date, end: date) -> None:
        span_days = (end - start).days + 1
        cap = MAX_DAYS_ONE_MINUTE if interval == INTERVAL_ONE_MINUTE else MAX_DAYS_ONE_DAY
        if span_days > cap:
            raise SmartApiError(
                f"{interval} window spans {span_days} days; SmartAPI caps it at {cap} "
                f"(CONTEXT 4.3). Split the request into smaller windows."
            )

    def _call_with_retry(self, params: dict[str, str]) -> Any:
        """The CONTEXT 4.3 retry loop: transient bursts are normal, expiry re-logs in."""
        connect = self._require_connect()
        relogins = 0
        reason = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            self._throttle()
            outcome = self._attempt_once(connect, params)
            kind, payload = outcome
            if kind == "ok":
                return payload
            if kind == "empty":
                return None  # a genuine no-data window (before listing) -- a real answer
            reason = str(payload)
            if kind == "expired" and relogins < self._max_relogins:
                relogins += 1
                self.login()  # fresh TOTP; the session dies at midnight (CONTEXT 4.3)
                connect = self._require_connect()
                continue
            if attempt < self._max_attempts:
                self._sleep(float(2 ** (attempt - 1)))  # 1,2,4,8,16s -- the PoC ladder
        raise SmartApiError(
            f"getCandleData failed after {self._max_attempts} attempts (last reason: {reason}). "
            "This is an ERROR, not an empty window -- an empty candle set (before listing) and "
            "a fetch that never succeeded are different (CONTEXT 4.3)."
        )

    def _attempt_once(self, connect: Any, params: dict[str, str]) -> tuple[str, Any]:
        """One getCandleData call. Returns ``(kind, payload)`` -- kind classifies the reply."""
        try:
            response = connect.getCandleData(dict(params))
        except Exception as exc:  # network hiccup / 403 burst -- transient by default
            return ("transient", f"{type(exc).__name__}: {exc}")
        if isinstance(response, dict) and response.get("status") and "data" in response:
            return ("ok", response.get("data"))
        message = _safe_message(response).lower()
        code = str(response.get("errorcode", "")).lower() if isinstance(response, dict) else ""
        haystack = f"{message} {code}"
        if any(marker in haystack for marker in _NO_DATA_MARKERS):
            return ("empty", message)
        if any(marker in haystack for marker in _SESSION_EXPIRED_MARKERS):
            return ("expired", message)
        return ("transient", message)

    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()


def _safe_message(response: Any) -> str:
    """A short, credential-free description of a SmartAPI reply for an error message."""
    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        return f"status={response.get('status')!r} errorcode={response.get('errorcode')!r}"
    return "no response" if response is None else f"{type(response).__name__}"


def one_minute_windows(start: date, end: date, *, days: int = MAX_DAYS_ONE_MINUTE) -> list[tuple[date, date]]:
    """Split ``[start, end]`` into consecutive windows of at most ``days`` calendar days.

    PURE. The 30-day ONE_MINUTE window walk the backfill runs over (CONTEXT 4.3): each window
    is inclusive on both ends and no wider than ``days``.
    """
    if days < 1:
        raise SmartApiError(f"window size must be >= 1 day, got {days}.")
    if end < start:
        return []
    windows: list[tuple[date, date]] = []
    cursor = start
    step = timedelta(days=days - 1)
    while cursor <= end:
        window_end = min(cursor + step, end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows
