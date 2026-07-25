"""Tests for the SmartAPI client -- fully offline (a fake SmartConnect; CONTEXT 4.3).

The client's network is injected (``connect_factory``/``totp_provider``/``sleep``), so every
CONTEXT 4.3 behavior -- the retry ladder, the session refresh, the ONE_DAY 00:00 trap, the
+05:30 normalization, credential secrecy -- is exercised without a socket.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from acumen import smartapi_client as sac
from acumen.smartapi_client import Credentials, OneMinuteBar, SmartApiClient, SmartApiError


#: Distinctive values so a "secret does not leak" assertion is meaningful (a single char like
#: "s" appears in ordinary English and would make the check vacuous).
CREDS = Credentials(
    api_key="APIKEY_ZZZ1", client_code="CLIENT_ZZZ2", pin="PIN_ZZZ3", totp_secret="TOTP_ZZZ4"
)


# --- parse_candles (PURE) --------------------------------------------------------------


def test_parse_candles_normalizes_ist_offset_to_naive() -> None:
    bars = sac.parse_candles([["2016-10-03T09:15:00+05:30", 100.5, 101.0, 100.0, 100.25, 5000]])
    assert bars == (OneMinuteBar(datetime(2016, 10, 3, 9, 15), 10050, 10100, 10000, 10025, 5000),)
    assert bars[0].stamp.tzinfo is None  # +05:30 dropped, naive IST (CONTEXT 7-E8)


def test_parse_candles_rejects_a_non_ist_offset() -> None:
    with pytest.raises(SmartApiError, match="not IST"):
        sac.parse_candles([["2016-10-03T09:15:00+00:00", 100.0, 100.0, 100.0, 100.0, 1]])


def test_parse_candles_prices_are_exact_paise_via_decimal() -> None:
    # 2189.20 * 100 is 218919 through float; Decimal on the text is the exact 218920.
    bars = sac.parse_candles([["2026-07-15T09:15:00+05:30", 2189.20, 2189.20, 2189.20, 2189.20, 1]])
    assert bars[0].open_paise == 218920


def test_parse_candles_rejects_a_fractional_paisa() -> None:
    with pytest.raises(SmartApiError, match="whole number of paise"):
        sac.parse_candles([["2026-07-15T09:15:00+05:30", 100.005, 100.0, 100.0, 100.0, 1]])


@pytest.mark.parametrize("data", [None, []])
def test_parse_candles_empty_window_is_empty_not_error(data: object) -> None:
    assert sac.parse_candles(data) == ()


def test_parse_candles_rejects_a_malformed_row() -> None:
    with pytest.raises(SmartApiError, match="wrong shape"):
        sac.parse_candles([["2016-10-03T09:15:00+05:30", 1, 2, 3]])


# --- one_minute_windows (PURE) ---------------------------------------------------------


def test_one_minute_windows_are_30_day_and_cover_the_range() -> None:
    from datetime import date

    windows = sac.one_minute_windows(date(2016, 10, 1), date(2016, 12, 15))
    assert windows == [
        (date(2016, 10, 1), date(2016, 10, 30)),
        (date(2016, 10, 31), date(2016, 11, 29)),
        (date(2016, 11, 30), date(2016, 12, 15)),
    ]
    # each window is at most 30 calendar days
    assert all((e - s).days + 1 <= 30 for s, e in windows)


def test_one_minute_windows_empty_when_end_before_start() -> None:
    from datetime import date

    assert sac.one_minute_windows(date(2016, 10, 5), date(2016, 10, 1)) == []


# --- a scripted fake SmartConnect ------------------------------------------------------


class FakeConnect:
    """A minimal SmartConnect double: scripted candle replies + login counting."""

    def __init__(self, candle_replies: list[object]) -> None:
        self._candle_replies = list(candle_replies)
        self.login_calls = 0
        self.last_params: dict[str, str] | None = None
        self.terminated = False

    def generateSession(self, client_code: str, pin: str, totp: str) -> dict[str, object]:
        self.login_calls += 1
        return {"status": True, "data": {"jwtToken": "j", "refreshToken": "r", "feedToken": "f"}}

    def getCandleData(self, params: dict[str, str]) -> object:
        self.last_params = dict(params)
        reply = self._candle_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def terminateSession(self, client_code: str) -> dict[str, object]:
        self.terminated = True
        return {"status": True}


def _client(fake: FakeConnect, **kw: object) -> SmartApiClient:
    sleeps: list[float] = kw.pop("sleeps", [])  # type: ignore[assignment]
    return SmartApiClient(
        CREDS,
        connect_factory=lambda api_key: fake,
        totp_provider=lambda secret: "000000",
        sleep=lambda s: sleeps.append(s),  # type: ignore[union-attr]
        **kw,  # type: ignore[arg-type]
    )


_OK = {"status": True, "message": "SUCCESS", "data": [["2016-10-03T09:15:00+05:30", 100.0, 100.0, 100.0, 100.0, 7]]}


# --- login ---------------------------------------------------------------------------


def test_login_required_before_candles() -> None:
    client = _client(FakeConnect([_OK]))
    with pytest.raises(SmartApiError, match="Not logged in"):
        client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))


def test_login_refused_raises_without_leaking_credentials() -> None:
    class Refuses(FakeConnect):
        def generateSession(self, *a: object) -> dict[str, object]:
            return {"status": False, "message": "Invalid PIN"}

    client = _client(Refuses([]))
    with pytest.raises(SmartApiError) as excinfo:
        client.login()
    assert "refused" in str(excinfo.value)
    for secret in (CREDS.api_key, CREDS.client_code, CREDS.pin, CREDS.totp_secret):
        assert secret not in str(excinfo.value)  # no credential VALUE leaked


# --- the happy path + the ONE_DAY trap ------------------------------------------------


def test_get_candles_returns_parsed_bars() -> None:
    client = _client(FakeConnect([_OK])).login()
    bars = client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))
    assert bars[0].volume == 7


def test_one_day_request_is_forced_to_start_at_midnight() -> None:
    fake = FakeConnect([_OK])
    client = _client(fake).login()
    client.get_candles("11536", sac.INTERVAL_ONE_DAY, datetime(2020, 7, 13, 9, 15), datetime(2020, 7, 13, 9, 15))
    assert fake.last_params is not None
    assert fake.last_params["fromdate"].endswith("00:00")  # the RESULTS.md G trap


def test_rejects_a_disallowed_interval() -> None:
    client = _client(FakeConnect([_OK])).login()
    with pytest.raises(SmartApiError, match="not used by this project"):
        client.get_candles("11536", "FIFTEEN_MINUTE", datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))


def test_rejects_tz_aware_bounds() -> None:
    from datetime import timezone

    client = _client(FakeConnect([_OK])).login()
    aware = datetime(2016, 10, 3, 9, 15, tzinfo=timezone.utc)
    with pytest.raises(SmartApiError, match="naive IST"):
        client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, aware, aware)


def test_one_minute_span_cap_is_enforced() -> None:
    client = _client(FakeConnect([_OK])).login()
    with pytest.raises(SmartApiError, match="caps it at 30"):
        client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 1, 9, 15), datetime(2016, 11, 15, 15, 30))


# --- retry / backoff / no-data / session refresh (CONTEXT 4.3) ------------------------


def test_transient_then_success_retries_and_returns() -> None:
    sleeps: list[float] = []
    transient = {"status": False, "message": "Access denied because of exceeding access rate", "errorcode": "AB2001"}
    fake = FakeConnect([transient, _OK])
    client = _client(fake, sleeps=sleeps).login()
    bars = client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))
    assert bars and 1.0 in sleeps  # first backoff step fired (2**0)


def test_no_data_reply_is_an_empty_window_not_an_error() -> None:
    fake = FakeConnect([{"status": False, "message": "No Data", "errorcode": "AB1004", "data": None}])
    client = _client(fake).login()
    bars = client.get_candles("2885", sac.INTERVAL_ONE_MINUTE, datetime(2016, 1, 3, 9, 15), datetime(2016, 1, 3, 15, 30))
    assert bars == ()


def test_exhausted_retries_raise_an_error_never_empty() -> None:
    transient = {"status": False, "message": "couldn't parse the json response"}
    fake = FakeConnect([transient] * 5)
    client = _client(fake, sleeps=[]).login()
    with pytest.raises(SmartApiError, match="failed after 5 attempts"):
        client.get_candles("2885", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))


def test_a_thrown_exception_is_treated_as_transient() -> None:
    fake = FakeConnect([RuntimeError("boom"), _OK])
    client = _client(fake, sleeps=[]).login()
    bars = client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))
    assert bars


def test_session_expiry_triggers_a_relogin_then_succeeds() -> None:
    expired = {"status": False, "message": "Invalid Token", "errorcode": "AG8002"}
    fake = FakeConnect([expired, _OK])
    client = _client(fake, sleeps=[]).login()
    assert fake.login_calls == 1
    bars = client.get_candles("11536", sac.INTERVAL_ONE_MINUTE, datetime(2016, 10, 3, 9, 15), datetime(2016, 10, 3, 15, 30))
    assert bars and fake.login_calls == 2  # a fresh session was generated (CONTEXT 4.3 midnight)


# --- secrets never leak (CLAUDE.md rule 4) --------------------------------------------


def test_credentials_repr_is_redacted() -> None:
    assert repr(CREDS) == "Credentials(<redacted>)"
    for secret in ("api_key='k'", "pin='p'", "totp_secret='s'"):
        assert secret not in repr(CREDS)


def test_client_repr_carries_no_secret() -> None:
    client = _client(FakeConnect([_OK]))
    text = repr(client)
    assert "logged_in" in text
    for secret in (CREDS.api_key, CREDS.client_code, CREDS.pin, CREDS.totp_secret):
        assert secret not in text


def test_library_logging_is_silenced_to_protect_credentials() -> None:
    """The vendor SmartConnect logs full request headers (Bearer token + API key) on a failed
    request; _quiet_library_logging raises those loggers above ERROR so nothing leaks (rule 4)."""
    import logging

    for name in ("logzero", "SmartApi", "smartConnect"):
        logging.getLogger(name).setLevel(logging.DEBUG)  # start noisy
    sac._quiet_library_logging()
    for name in ("logzero", "SmartApi", "smartConnect"):
        assert logging.getLogger(name).level == logging.CRITICAL
