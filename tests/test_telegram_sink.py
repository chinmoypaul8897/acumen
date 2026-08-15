"""TELEGRAM (chunk 14): the sink, the safety rails, and the message shown verbatim.

plan.md's chunk-14 Done-when is *"test-mode alerts delivered to both channels; payload fields
complete; no duplicate alerts on re-poll"*, and the architect's card adds the four rules the
sink is built around. Each is a test here:

* it attaches as an :class:`acumen.live_screener.AlertSink` and the screener is UNCHANGED;
* it sends only when ``--live-alerts`` is passed; dry run is log-only;
* every message carries the alert AND CONTEXT 4.7's disclosed line AND, when applicable, the
  staleness or provisional-POC marker;
* a send FAILURE degrades to silence plus a visible failure, never a crash and never a
  duplicate on resume;
* no order endpoint, and no credential in anything the sink emits.

The architect's **14-Aug-2026 ruling** adds the card's last line item to the same surface --
*"the END-OF-DAY SUMMARY is a card line item and lands in chunk 14 -- routed to the phone via
the sink at close, not only the terminal"* -- and it is tested under exactly the four rules
above, one test each, in the last section of this file.

**No network is touched anywhere in this file** -- the suite's socket guard would block it, and
the transport is injected in every test. ``post_message`` is exercised only by AST and by
signature.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime
from pathlib import Path

import pytest

from acumen import live_screener as ls
from acumen import telegram_sink as tg
from acumen.live_recording import LiveRecording, RecordedAlert

REPO = Path(__file__).resolve().parents[1]

DAY = date(2026, 6, 10)


def _trigger(**overrides) -> RecordedAlert:
    """A TRIGGER alert shaped exactly as :meth:`LiveScreener._alert` builds one."""
    payload = {
        "side": "long", "entry_paise": 74_095, "stop_paise": 73_810, "target_paise": 74_950,
        "poc_paise": "73980", "bias": "bullish", "qty": 350, "risk_paise": 285,
        "entry_stamp": "2026-06-10T11:15:00", "gap_entry": False, "dry_run": False,
        # B411's posture stamp. It is in the fixture because `LiveScreener._alert` puts it on
        # EVERY alert, and a helper that claims to be shaped like a real one has to carry it --
        # REVIEW_14B **L2**: an unstamped payload is no longer read as a live morning's.
        "mode": ls.POSTURE_LIVE,
        "disclosure": ls.LIVE_DISCLOSURE,
        "bars": 135, "last_bar_stamp": "2026-06-10T11:29:00",
        "data_behind_minutes": 1, "stale": False,
    }
    payload.update(overrides)
    return RecordedAlert(kind=ls.ALERT_TRIGGER, symbol="HDFCBANK",
                         at=datetime(2026, 6, 10, 11, 30), payload=payload)


# --- it attaches by being a sink, and the screener is untouched ---------------------------------


def test_the_sink_ATTACHES_without_a_single_edit_to_the_screener() -> None:
    """The design chunk 13 reserved: *"chunk 14 adds Telegram by adding a sink"*.

    Two properties, both structural: the sink satisfies the protocol by shape, and the screener
    knows nothing about it -- ``live_screener.py`` does not name Telegram anywhere, so the
    reviewed live half is still the reviewed live half.
    """
    sink = tg.TelegramSink()
    assert hasattr(sink, "deliver") and callable(sink.deliver)
    signature = inspect.signature(sink.deliver)
    assert list(signature.parameters) == ["alert"], "the AlertSink protocol, exactly"

    # The screener knows nothing about it in CODE. Asserted over the tree rather than over the
    # text, because the module's prose may well mention where an alert ends up -- what must not
    # exist is an import, a construction or a reference. Adding a sink is all chunk 14 was
    # allowed to do to the reviewed live half.
    screener_tree = ast.parse(
        (REPO / "src" / "acumen" / "live_screener.py").read_text(encoding="utf-8")
    )
    reached: list[str] = []
    for node in ast.walk(screener_tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            reached.extend(name for name in names if "telegram" in name.lower())
        elif isinstance(node, ast.Name):
            if "telegram" in node.id.lower():
                reached.append(node.id)
        elif isinstance(node, ast.Attribute):
            if "telegram" in node.attr.lower():
                reached.append(node.attr)
    assert not reached, f"the screener reaches its sink by name: {reached}"

    # ...and it really is accepted where the screener takes its sinks.
    collecting = ls.CollectingAlertSink()
    screener = ls.LiveScreener(
        day=DAY, symbols=(), pipeline=None, biases={}, gates={},
        source=None, recording=LiveRecording.at(Path(".")),
        clock=ls.VirtualClock(stamp=datetime(2026, 6, 10, 9, 0)),
        sinks=(collecting, sink),
    )
    assert screener.sinks[-1] is sink


# --- the message, shown verbatim ----------------------------------------------------------------


def test_the_MESSAGE_carries_the_alert_the_disclosure_and_the_markers() -> None:
    """What lands on the phone, in full, for the three shapes it can have.

    The alert line is ``format_alert``'s own -- one source of truth for what the terminal shows
    and what the phone shows -- and the qualifiers are split onto their own lines because a
    phone wraps a long line into something nobody re-reads.

    **The clock time carries its DATE** (REVIEW_14 H1). ``[11:30]`` is unambiguous on a terminal
    headed by the trade date and dangerous on a phone, where the message is the whole context:
    the review put a replayed 2020 trade on the transport and not one byte of it said 2020.
    """
    plain = tg.message_for(_trigger())
    assert plain == (
        "[2026-06-10 11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   "
        "(POC 739.80, bias bullish)\n"
        "(live feed, not yet verified against the exchange's end-of-day record)"
    )

    stale = tg.message_for(_trigger(
        stale=True, data_behind_minutes=226, stale_note=ls.stale_note(226),
        alert_states=[ls.MARKER_STALE],
    ))
    assert stale.splitlines()[0].endswith("(POC 739.80, bias bullish)")
    assert stale.splitlines()[1] == (
        "!! STALE 226m BEHIND -- this price stands on a window the screener cannot vouch for"
    )
    assert stale.splitlines()[-1] == f"({ls.LIVE_DISCLOSURE})"

    provisional = tg.message_for(_trigger(
        poc_note=ls.POC_PROVISIONAL, poc_missing_minutes=5,
        alert_states=[ls.MARKER_POC_PROVISIONAL],
    ))
    assert f"!! {ls.POC_PROVISIONAL}" in provisional

    dry = tg.message_for(_trigger(dry_run=True))
    assert "[DRY RUN -- log only, nothing was sent to anyone else]" in dry

    # REVIEW_14B **L2**: a payload that does not say which posture produced it is not read as a
    # live morning's. `live` is the only posture that carries no marker, so silence used to be
    # the strongest claim a message could make and the only one nobody could check.
    unstamped = dict(_trigger().payload)
    unstamped.pop("mode")
    message = tg.message_for(RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol="HDFCBANK",
        at=datetime(2026, 6, 10, 11, 30), payload=unstamped,
    ))
    assert tg.UNSTAMPED_MARKER in message
    assert tg.REPLAY_MARKER not in message, (
        "it is not claimed to be a replay either -- what is unknown is stated as unknown"
    )
    assert tg.UNSTAMPED_MARKER not in tg.message_for(_trigger()), "a stamped alert says nothing"
    assert tg.UNSTAMPED_MARKER not in tg.message_for(_trigger(mode="settled"))


# --- it sends only when the operator asked -------------------------------------------------------


def test_a_DRY_RUN_sink_sends_NOTHING() -> None:
    """``--live-alerts`` is the switch, and the default is off.

    A dry-run morning reads the same feed and produces the same alerts; what it must not do is
    put them on somebody's phone. The transport here would raise if it were ever called.
    """
    printed: list[str] = []

    def never(_text: str) -> None:  # pragma: no cover -- ASSERTED BY NOT BEING CALLED
        raise AssertionError("a dry-run sink reached the transport")

    sink = tg.TelegramSink(send=never, live=False, out=printed.append)
    sink.deliver(_trigger())
    assert sink.sent == [] and sink.failed == [] and sink.refused == []
    assert printed and "DRY RUN -- not sent" in printed[0]
    assert "DRY RUN" in sink.summary()


def test_a_LIVE_sink_sends_exactly_once_per_distinct_alert() -> None:
    """The trader's phone, and CONTEXT 4.4's "no duplicate alerts on re-poll", at the sink."""
    sent: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None)

    alert = _trigger()
    sink.deliver(alert)
    sink.deliver(alert)                      # the same answer re-derived at a later boundary
    sink.deliver(_trigger())                 # ...and a fresh object carrying the same identity
    assert len(sent) == 1, "one distinct alert, one message"
    assert sink.sent == ["HDFCBANK trigger"]

    # A DIFFERENT answer -- the entry healed to a new price -- is a second message, not silence.
    sink.deliver(_trigger(entry_paise=74_195, target_paise=75_050))
    assert len(sent) == 2
    assert "741.95" in sent[1]


# --- the Q1 rule: no unvouched price is ever forwarded --------------------------------------------


def test_the_sink_REFUSES_an_alert_whose_price_it_cannot_vouch_for() -> None:
    """The chunk-14 rule, at the surface it is about (REVIEW_13B **Q1**).

    Two failure shapes, both refused and both VISIBLE: a payload that names a price and carries
    no freshness stamp at all, and a stale one whose marker did not travel. A refusal is not
    silence -- the alert is still on the screen and in the recording, and the operator is told
    that the phone did not get it.
    """
    sent: list[str] = []
    printed: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=printed.append)

    naked = _trigger()
    del naked.payload["stale"]
    del naked.payload["data_behind_minutes"]
    sink.deliver(naked)
    assert sent == [] and len(sink.refused) == 1
    assert tg.REFUSED_BANNER in printed[0] and "no freshness stamp" in printed[0]

    unmarked = _trigger(stale=True, data_behind_minutes=226)  # no alert_states, no note
    sink.deliver(unmarked)
    assert sent == [] and len(sink.refused) == 2
    assert "no staleness marker" in printed[1]

    # ...and the same alert WITH its marker is forwarded, carrying the marker to the phone.
    marked = _trigger(
        stale=True, data_behind_minutes=226, stale_note=ls.stale_note(226),
        alert_states=[ls.MARKER_STALE],
    )
    sink.deliver(marked)
    assert len(sent) == 1 and "STALE 226m BEHIND" in sent[0]
    assert "2 refused (unvouched price)" in sink.summary()


# --- a failure degrades to silence plus a visible failure -----------------------------------------


def test_a_SEND_FAILURE_degrades_to_silence_plus_a_VISIBLE_failure() -> None:
    """Rule 3: never a crash, never a retry storm, never a duplicate on resume.

    An exception escaping a sink would end the sweep inside
    :meth:`LiveScreener._deliver` and cost every later symbol its boundary, so the sink swallows
    it -- and then SAYS so, because a screener that degrades silently is the failure mode chunk
    13 spent a review closing.
    """
    printed: list[str] = []
    attempts: list[str] = []

    def explode(text: str) -> None:
        attempts.append(text)
        raise tg.TelegramError("the Telegram send failed: ConnectionError")

    sink = tg.TelegramSink(send=explode, live=True, out=printed.append)
    sink.deliver(_trigger())                      # must not raise

    assert len(attempts) == 1, "one attempt, no retry storm inside a sweep"
    assert sink.sent == [] and len(sink.failed) == 1
    assert printed and tg.FAILURE_BANNER in printed[0]
    assert "ConnectionError" not in printed[0] or "TelegramError" in printed[0]

    # The failed alert is NOT marked as sent, so a later re-derivation may still deliver it...
    healed: list[str] = []
    sink.send = healed.append
    sink.deliver(_trigger())
    assert healed and sink.sent == ["HDFCBANK trigger"]
    # ...and now that it HAS gone, it does not go twice.
    sink.deliver(_trigger())
    assert len(healed) == 1


def test_the_sink_NEVER_RAISES_whatever_the_transport_does() -> None:
    """The property, stated over the exception types a real transport can throw."""
    class _Boom(BaseException):
        pass

    for error in (RuntimeError("x"), OSError("x"), ValueError("x"), TimeoutError("x")):
        def raiser(_text: str, exc=error) -> None:
            raise exc

        sink = tg.TelegramSink(send=raiser, live=True, out=lambda _line: None)
        sink.deliver(_trigger())
        assert len(sink.failed) == 1, f"{type(error).__name__} was not absorbed"


def test_the_dedup_key_is_ON_DISK_before_a_message_can_leave(tmp_path: Path) -> None:
    """"No duplicate on resume", proved where it is really decided -- in the screener's order.

    REVIEW_13 M23 put the ``state.json`` write BEFORE the sinks fire, and that ordering is what
    makes a crash between the two safe: the resumed screener reads a dedup set that already
    contains the alert. The sink's own guard cannot provide this -- it lives in one process --
    so what is asserted here is the ORDER in ``_deliver``, at the source.
    """
    body = inspect.getsource(ls.LiveScreener._deliver)
    persist = body.index("self.persist()")
    fire = body.index("for sink in self.sinks")
    assert persist < fire, (
        "the dedup set must reach disk BEFORE any sink fires, or a death in between re-sends "
        "the morning on resume"
    )
    record = body.index("self.recording.record_alert(alert)")
    assert record < fire, "and the recording must hold it too"


# --- the safety rails, restated over the new module ----------------------------------------------


def test_NO_ORDER_ENDPOINT_IS_REACHABLE_FROM_THE_TELEGRAM_MODULE() -> None:
    """CONTEXT section 1 R4, re-asserted over the module chunk 14 added.

    The repository-wide tripwire already scans this file (``tests/test_live_safety.py`` walks
    ``src/`` recursively). This is the same rule stated where the new code is, plus the positive
    half: the ONLY host this module can reach is Telegram's own API, and the only import that
    can make a request is ``requests`` inside ``post_message``.
    """
    from tests.test_live_safety import scan_source

    path = REPO / "src" / "acumen" / "telegram_sink.py"
    source = path.read_text(encoding="utf-8")
    assert not scan_source(source, "telegram_sink.py")

    tree = ast.parse(source)
    urls = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("http")
    ]
    assert urls == ["https://api.telegram.org/bot{token}/sendMessage"], urls

    requesting = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "requests"
    ]
    assert len(requesting) == 1, "one request, in one function"
    assert requesting[0].func.attr == "post"
    inside = inspect.getsource(tg.post_message)
    assert "requests.post" in inside


def test_NO_CREDENTIAL_REACHES_ANY_STRING_THE_SINK_PRODUCES(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAUDE.md rule 4, over everything this sink can emit.

    Invented values are planted in the environment and then hunted for in the sink's repr, its
    summary, every message it builds, every line it prints and every exception it raises. No
    real credential is read: ``.env`` is not opened by this test at all.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "NOT-A-REAL-TOKEN-000:AAquiteFakeTokenValue")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1009999999999")
    planted = ("NOT-A-REAL-TOKEN-000:AAquiteFakeTokenValue", "-1009999999999")

    printed: list[str] = []
    sent: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=printed.append)
    sink.deliver(_trigger())
    sink.deliver(_trigger(entry_paise=1, stale=True, data_behind_minutes=99))  # a refusal too

    emitted = [repr(sink), sink.summary(), *printed, *sent,
               tg.message_for(_trigger()), str(tg.TelegramError("x"))]
    for text in emitted:
        for secret in planted:
            assert secret not in text, f"a planted credential reached: {text[:80]}"

    # `credentials_present` answers from `.env` through `env_value`, which RELOADS the file --
    # so the absent case is exercised at the loader rather than by deleting an environment
    # variable the next call would put straight back. Still no value is read here.
    assert tg.credentials_present() is True

    from acumen import config as config_module

    monkeypatch.setattr(config_module, "env_value", lambda name, required=True: None)
    assert tg.credentials_present() is False

    # The module source itself names the KEYS and never a value, and the token is only ever
    # substituted into the URL at call time.
    source = (REPO / "src" / "acumen" / "telegram_sink.py").read_text(encoding="utf-8")
    assert "{token}" in source and "env_value(ENV_BOT_TOKEN)" in source


def test_post_message_reports_a_failure_WITHOUT_the_url_it_failed_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one place a token could leak through a traceback, closed deliberately.

    ``requests`` puts the request URL into most of its exceptions, and the URL carries the bot
    token. So the transport reports the exception TYPE and does not chain the original -- the
    single place in this repository where dropping ``__cause__`` is the safer choice.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "NOT-A-REAL-TOKEN-000:AAquiteFakeTokenValue")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1009999999999")

    import requests

    def boom(*_args, **_kwargs):
        raise requests.ConnectionError(
            "HTTPSConnectionPool(host='api.telegram.org'): /botNOT-A-REAL-TOKEN-000:"
            "AAquiteFakeTokenValue/sendMessage"
        )

    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(tg.TelegramError) as caught:
        tg.post_message("hello")
    message = str(caught.value)
    assert "NOT-A-REAL-TOKEN-000" not in message
    assert caught.value.__cause__ is None, "the original is NOT chained: it carries the URL"
    assert "ConnectionError" in message

    class _Response:
        status_code = 401
        text = "Unauthorized: bot token NOT-A-REAL-TOKEN-000 is invalid"

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response())
    with pytest.raises(tg.TelegramError) as rejected:
        tg.post_message("hello")
    assert "NOT-A-REAL-TOKEN-000" not in str(rejected.value)
    assert "HTTP 401" in str(rejected.value), "the status code, never the body"


# --- the CLI wiring -------------------------------------------------------------------------------


def test_the_CLI_attaches_the_sink_only_on_a_FLAG_and_sends_only_on_THREE() -> None:
    """``--telegram`` attaches it; ``--mode live`` and ``--live-alerts`` are what make it send.

    Read at the source, because what is being asserted is a wiring decision rather than an
    outcome: three deliberate acts stand between an operator and a message on somebody's phone,
    and each of them is a separate flag.

    **REVIEW_14 H1 renamed this test.** It made the three-act claim in its own docstring and then
    asserted a gate with TWO terms in it -- so the one place a reader would go to check the claim
    confirmed the defect instead. The mode is now in the gate, and the gate is a named function
    rather than an expression, so there is one thing to read and one thing to assert.
    """
    from acumen import run_screener

    args = run_screener.parse_args(["--day", "2026-06-10"])
    assert args.telegram is False and args.live_alerts is False
    assert args.mode == "replay", "and the mode DEFAULTS to replay, which is why it must be a term"

    source = Path(run_screener.__file__).read_text(encoding="utf-8")
    assert "TelegramSink(live=telegram_is_live(args))" in source, (
        "the sink SENDS only under the three-act gate"
    )
    assert 'args.mode == "live" and args.telegram and args.live_alerts' in source, (
        "and all three acts are in it"
    )
    assert "sinks = sinks + (telegram,)" in source, "and it attaches by joining the sink tuple"
    tree = ast.parse(source)
    built = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "TelegramSink"
    ]
    assert len(built) == 1, "one construction, at the one place sinks are assembled"


# --- THE END-OF-DAY SUMMARY (the architect's 14-Aug-2026 ruling) ----------------------------------


def _armed(symbol: str = "ICICIBANK", minute: int = 15, **overrides) -> RecordedAlert:
    """An ARMED alert, for building a day out of more than one symbol."""
    alert = _trigger(**overrides)
    return RecordedAlert(kind=ls.ALERT_ARMED, symbol=symbol,
                         at=datetime(2026, 6, 10, 11, minute), payload=alert.payload)


def _a_day() -> tuple[RecordedAlert, ...]:
    """One morning's alerts: two symbols, three alerts, one of them STALE and marked."""
    return (
        _armed("HDFCBANK", 15),
        _trigger(),
        _armed(
            "ICICIBANK", 15, stale=True, data_behind_minutes=226,
            stale_note=ls.stale_note(226), alert_states=[ls.MARKER_STALE],
        ),
    )


def test_the_END_OF_DAY_SUMMARY_is_SENT_ONCE_at_close_and_shown_here_VERBATIM() -> None:
    """The card's last line item, on the phone, in full.

    plan.md's chunk-14 build line is *"live dashboard view ...; Telegram bot ...; alert dedup;
    end-of-day summary message"*, and the architect's ruling names the surface: *"routed to the
    phone via the sink at close, not only the terminal"*. So it goes down the same transport an
    alert goes down, and it carries the three things the ruling lists -- the day's alerts BY
    SYMBOL, ``summary()``'s own line, and the disclosed line -- plus the marker counts.
    """
    sent: list[str] = []
    printed: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=printed.append)
    day = _a_day()
    for alert in day:
        sink.deliver(alert)
    assert len(sent) == 3, "the three alerts went first, as alerts"

    assert sink.send_end_of_day(day, day=DAY, disclosure=ls.LIVE_DISCLOSURE) is True
    assert len(sent) == 4, "ONE summary message, at the close"
    assert sent[-1] == (
        "ACUMEN -- END OF DAY   2026-06-10\n"
        "2 symbol(s) alerted:\n"
        "  HDFCBANK   armed 11:15, trigger 11:30\n"
        "  ICICIBANK  armed 11:15\n"
        "telegram: 3 sent, 0 refused (unvouched price), 0 failed\n"
        "markers: 1 stale, 0 provisional POC\n"
        "(live feed, not yet verified against the exchange's end-of-day record)"
    )
    assert sink.end_of_day == tg.SUMMARY_SENT
    assert any("end-of-day summary" in line for line in printed), "the operator is told too"

    # ...ONCE. A second call at the same close sends nothing (the CLI's own guard is on disk;
    # this one is the sink's, for two sinks over one process or a caller that asks twice).
    assert sink.send_end_of_day(day, day=DAY, disclosure=ls.LIVE_DISCLOSURE) is False
    assert len(sent) == 4

    # A morning that produced NOTHING still ends with a message, and says so in words: a silent
    # phone must never be ambiguous between "no signal" and "the tool stopped".
    quiet: list[str] = []
    empty = tg.TelegramSink(send=quiet.append, live=True, out=lambda _line: None)
    assert empty.send_end_of_day((), day=DAY, disclosure=ls.LIVE_DISCLOSURE) is True
    assert tg.SUMMARY_NO_ALERTS in quiet[0]
    assert "markers: 0 stale, 0 provisional POC" in quiet[0]


def test_the_END_OF_DAY_SUMMARY_IS_NOT_SENT_on_a_DRY_RUN_morning() -> None:
    """The same ``--live-alerts`` gate the alerts pass through, on the summary.

    A dry-run morning ends on the terminal, labelled with the sentence a dry-run alert carries.
    The transport here would raise if it were ever reached.
    """
    printed: list[str] = []

    def never(_text: str) -> None:  # pragma: no cover -- ASSERTED BY NOT BEING CALLED
        raise AssertionError("a dry-run sink reached the transport at the close")

    sink = tg.TelegramSink(send=never, live=False, out=printed.append)
    assert sink.send_end_of_day(_a_day(), day=DAY, disclosure=ls.LIVE_DISCLOSURE) is False
    assert sink.end_of_day == tg.SUMMARY_DRY_RUN

    page = "\n".join(printed)
    assert "DRY RUN -- not sent" in page, "and it is on the terminal, in full"
    assert "[DRY RUN -- log only, nothing was sent to anyone else]" in page
    assert tg.SUMMARY_HEADING in page and "HDFCBANK" in page
    assert ls.LIVE_DISCLOSURE in page


def test_a_FAILED_END_OF_DAY_SEND_degrades_to_SILENCE_plus_a_VISIBLE_failure() -> None:
    """Rule 3, on the last message of the morning: never a crash, never a retry storm.

    The close is the one moment where an escaping exception costs nothing else -- every sweep is
    already done -- which is exactly why it must still not escape: the CLI has two lines left to
    print (the recording's path and the dashboard's), and the operator needs both.
    """
    printed: list[str] = []

    def explode(_text: str) -> None:
        raise tg.TelegramError("the Telegram send failed: ConnectionError")

    sink = tg.TelegramSink(send=explode, live=True, out=printed.append)
    assert sink.send_end_of_day(_a_day(), day=DAY) is False  # must not raise
    assert sink.end_of_day == tg.SUMMARY_FAILED
    assert printed and tg.FAILURE_BANNER in printed[0]
    assert "end-of-day summary" in printed[0] and "TelegramError" in printed[0]

    # ...and the failure is not counted as an ALERT failure: the summary carries those counters,
    # so a summary that counted itself would report a number it created.
    assert sink.failed == [] and sink.sent == []

    for error in (RuntimeError("x"), OSError("x"), ValueError("x"), TimeoutError("x")):
        def raiser(_text: str, exc=error) -> None:
            raise exc

        one = tg.TelegramSink(send=raiser, live=True, out=lambda _line: None)
        one.send_end_of_day((), day=DAY)
        assert one.end_of_day == tg.SUMMARY_FAILED, f"{type(error).__name__} was not absorbed"


def test_a_RESUMED_MORNING_does_NOT_SEND_A_SECOND_END_OF_DAY_SUMMARY(tmp_path: Path) -> None:
    """"No duplicate on resume", for the message the sink's own flag cannot protect.

    A resumed morning re-runs the whole day into the same recording (REVIEW_13 B8), in a NEW
    process with a NEW sink -- so the sink's flag is gone and only something on disk can remember
    that the trader already has his summary. That something is the recording's own event log,
    written after a real send and read before the next attempt, which is the discipline REVIEW_13
    M23 set for the alert dedup set.

    **The day's alerts come from the RECORDING** (REVIEW_14 H2), so this test writes them where
    the shipped CLI writes them instead of handing the same tuple to both calls -- which is
    precisely what the CLI does not do, and what let the resumed-morning defect live under a
    green test.
    """
    from acumen import run_screener

    recording = LiveRecording.at(tmp_path / "rec" / "2026-06-10-live")
    for alert in _a_day():
        recording.record_alert(alert)

    first: list[str] = []
    sink = tg.TelegramSink(send=first.append, live=True, out=lambda _line: None)
    assert run_screener._end_of_day_summary(
        sink, recording, day=DAY, disclosure=ls.LIVE_DISCLOSURE
    ) is True
    assert len(first) == 1
    marks = [row for row in recording.events() if row["kind"] == tg.SUMMARY_EVENT]
    assert len(marks) == 1 and marks[0]["at"].endswith("15:30:00"), "stamped at the close"

    # The restart: a fresh sink, the same recording. Nothing leaves.
    second: list[str] = []
    resumed = tg.TelegramSink(send=second.append, live=True, out=lambda _line: None)
    assert run_screener._end_of_day_summary(
        resumed, recording, day=DAY, disclosure=ls.LIVE_DISCLOSURE
    ) is False
    assert second == [], "the trader does not get a second summary for the same day"
    assert len([row for row in recording.events() if row["kind"] == tg.SUMMARY_EVENT]) == 1

    # A send that FAILED writes no mark, so a restart still owes the trader his summary.
    other = LiveRecording.at(tmp_path / "rec" / "2026-06-11-live")
    for alert in _a_day():
        other.record_alert(alert)

    def explode(_text: str) -> None:
        raise tg.TelegramError("the Telegram send failed: ConnectionError")

    failing = tg.TelegramSink(send=explode, live=True, out=lambda _line: None)
    assert run_screener._end_of_day_summary(failing, other, day=DAY) is False
    assert [row for row in other.events() if row["kind"] == tg.SUMMARY_EVENT] == []
    healed: list[str] = []
    assert run_screener._end_of_day_summary(
        tg.TelegramSink(send=healed.append, live=True, out=lambda _line: None),
        other, day=DAY,
    ) is True
    assert len(healed) == 1


def test_NO_CREDENTIAL_REACHES_THE_END_OF_DAY_SUMMARY(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAUDE.md rule 4, over the bytes of the last message of the morning.

    The same planted-value hunt the alert path gets, run over the summary's text, the sink's
    outcome word, everything it printed and its repr -- in all three outcomes (sent, dry run and
    failed), because the failure path is the one that has an exception to quote.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "NOT-A-REAL-TOKEN-000:AAquiteFakeTokenValue")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1009999999999")
    planted = ("NOT-A-REAL-TOKEN-000:AAquiteFakeTokenValue", "-1009999999999")

    emitted: list[str] = []
    for live, transport in (
        (True, lambda text: emitted.append(text)),
        (False, None),
        (True, lambda _text: (_ for _ in ()).throw(tg.TelegramError("send failed"))),
    ):
        printed: list[str] = []
        sink = tg.TelegramSink(send=transport, live=live, out=printed.append)
        for alert in _a_day():
            sink.deliver(alert)
        sink.send_end_of_day(_a_day(), day=DAY, disclosure=ls.LIVE_DISCLOSURE)
        emitted.extend([
            *printed, repr(sink), sink.end_of_day,
            sink.end_of_day_message(_a_day(), day=DAY, disclosure=ls.LIVE_DISCLOSURE),
        ])

    assert emitted, "the hunt must have something to hunt through"
    for text in emitted:
        for secret in planted:
            assert secret not in text, f"a planted credential reached: {text[:80]}"


def test_the_CLI_ENDS_THE_MORNING_with_the_summary_AFTER_the_day_is_whole() -> None:
    """Where the send sits, read at the source: after ``run_day()``, which ends in ``close_day``.

    The ruling says *at close*, and "close" has a precise meaning in this repository:
    ``run_day()`` sweeps seventeen boundaries and then calls ``close_day()``, whose 15:30 poll is
    what makes the recording a whole session (REVIEW_13 B4). The summary is sent after that call
    returns, so the message it carries describes a finished day rather than a partial one -- and
    it is inside the ``--telegram`` branch, so a morning without the flag sends nothing.
    """
    from acumen import run_screener

    source = Path(run_screener.__file__).read_text(encoding="utf-8")
    ran = source.index("reports = screener.run_day(")
    summarised = source.index("_end_of_day_summary(\n")
    assert ran < summarised, "the summary is sent after close_day, not before it"

    body = inspect.getsource(run_screener.main)
    branch = body.index("if args.telegram:\n        # A silent phone")
    assert branch < body.index("_end_of_day_summary("), "and only when --telegram was passed"
    assert body.index("print(telegram.summary())") < body.index("_end_of_day_summary("), (
        "the terminal line still prints -- the ruling ADDS the phone, it does not move the line"
    )
