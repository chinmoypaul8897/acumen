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
    """
    plain = tg.message_for(_trigger())
    assert plain == (
        "[11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   "
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


def test_the_CLI_attaches_the_sink_only_on_a_FLAG_and_sends_only_on_TWO() -> None:
    """``--telegram`` attaches it; ``--live-alerts`` is what makes it send.

    Read at the source, because what is being asserted is a wiring decision rather than an
    outcome: three deliberate acts stand between an operator and a message on somebody's phone,
    and each of them is a separate flag.
    """
    from acumen import run_screener

    args = run_screener.parse_args(["--day", "2026-06-10"])
    assert args.telegram is False and args.live_alerts is False

    source = Path(run_screener.__file__).read_text(encoding="utf-8")
    assert "TelegramSink(live=bool(args.live_alerts and args.telegram))" in source, (
        "the sink SENDS only when both flags are present"
    )
    assert "sinks = sinks + (telegram,)" in source, "and it attaches by joining the sink tuple"
    tree = ast.parse(source)
    built = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "TelegramSink"
    ]
    assert len(built) == 1, "one construction, at the one place sinks are assembled"
