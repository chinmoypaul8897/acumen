"""TELEGRAM (chunk 14): the alert on the trader's phone, and nothing else.

CONTEXT 4.4: *"Alerts: dashboard + Telegram bot (both -- R2-Q37b). Alert payload: symbol, side,
entry, SL, TP, POC, bias, timestamp."* plan.md's chunk-14 card: *"Telegram bot ... alert dedup;
no duplicate alerts on re-poll"*.

**It attaches by being an AlertSink and by nothing else.** :class:`acumen.live_screener.
AlertSink` is the protocol chunk 13 reserved for exactly this -- *"Chunk 14 adds Telegram by
adding a sink, not by editing this"* -- so this module adds one class and the CLI adds it to a
tuple. Not one line of the screener changed to make it work, which is the property that keeps
the reviewed live half reviewed.

## The four rules this sink is built around

1. **It sends only when the operator asked.** ``--live-alerts`` is what turns dry run off, and a
   DRY-RUN alert is never sent: it is logged, exactly as the screen and the sound sink log it.
   Two separate deliberate acts stand between an operator and a message on somebody's phone --
   ``--mode live`` and ``--live-alerts``.
2. **It never carries a price the screener cannot vouch for.**
   :func:`acumen.live_screener.unvouched_price` runs on every alert BEFORE it is sent, and an
   alert that names a price with no freshness stamp, or a stale one with no marker, is REFUSED
   and reported rather than forwarded (REVIEW_13B Q1). What is sent carries the numbers, CONTEXT
   4.7's disclosed line, and any marker that qualifies them.
3. **A send failure degrades to silence plus a VISIBLE failure.** Never a crash -- an exception
   escaping a sink would end the sweep and cost the other 203 symbols their boundary -- and
   never a retry storm. The failure is counted, printed once per alert, and the morning
   continues.
4. **No duplicate on resume.** The dedup key is on DISK before the message leaves: the screener
   writes ``state.json`` inside :meth:`~acumen.live_screener.LiveScreener._deliver` before it
   calls any sink (REVIEW_13 M23), so a process killed between the write and the send re-reads a
   set that already contains the alert and never sends it twice. This sink adds its own second
   guard for the case the screener cannot cover -- two sinks over one process, a retry loop, a
   caller that delivers the same object twice -- keyed the same way.

## Credentials

``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` come from ``.env`` through
:func:`acumen.config.env_value`, at the moment of use, and are never printed, logged, echoed,
committed or put in a repr. The token is not in the URL this module builds a string of -- it is
in the URL the request is made to, and no code path here formats it into a message, an
exception, a log line or a ``__repr__``. :mod:`tests.test_telegram_sink` asserts that by walking
every byte of everything this sink emits.

**No order endpoint is imported or named here**, and :mod:`tests.test_live_safety`'s tripwire
scans this file with the rest of the package.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .live_recording import RecordedAlert
from .live_screener import (
    ALERT_ARMED,
    ALERT_EXIT,
    ALERT_FAILURE,
    ALERT_KINDS,
    ALERT_SQUARE_OFF,
    ALERT_TRIGGER,
    LiveScreener,
    alert_state_notes,
    format_alert,
    unvouched_price,
)

#: The ``.env`` keys. Named here so the CLI can say WHICH key is missing without reading either.
ENV_BOT_TOKEN: str = "TELEGRAM_BOT_TOKEN"
ENV_CHAT_ID: str = "TELEGRAM_CHAT_ID"

#: Telegram's own send endpoint, as a template the token is substituted into at call time.
#: The token never appears in any string this module keeps, prints or records.
API_TEMPLATE: str = "https://api.telegram.org/bot{token}/sendMessage"

#: How long one send may take. A screener that blocks on a phone notification is a screener that
#: misses a boundary; CONTEXT 4.4's whole sweep budget is 75-105 seconds for 210 symbols.
SEND_TIMEOUT_SECONDS: float = 5.0

#: What the operator sees when a send fails. Silence on the phone, a line on the screen.
FAILURE_BANNER: str = "TELEGRAM SEND FAILED (the alert is on this screen and in the recording)"

#: What the operator sees when an alert is REFUSED rather than failed -- the Q1 rule.
REFUSED_BANNER: str = "TELEGRAM REFUSED an alert whose price the screener cannot vouch for"


class TelegramError(RuntimeError):
    """A Telegram send could not be made. Caught by the sink; never raised at the screener."""


def credentials_present() -> bool:
    """Are both keys in ``.env``? Reads no value into anything that outlives the call."""
    from .config import env_value

    return bool(env_value(ENV_BOT_TOKEN, required=False)) and bool(
        env_value(ENV_CHAT_ID, required=False)
    )


def message_for(alert: RecordedAlert) -> str:
    """The message body -- the alert line, its states, and CONTEXT 4.7's disclosed line.

    One message, three parts, in the order the trader needs them:

    1. **the alert itself**, in the same words the screen shows (``format_alert``), so what he
       reads on his phone and what the operator reads on the terminal cannot differ;
    2. **the markers that qualify it**, on their own lines, because a phone wraps a long line
       into something nobody re-reads -- staleness (REVIEW_13B Q1) and B357's provisional POC;
    3. **CONTEXT 4.7's disclosed line**, always, on a live alert.

    ``format_alert`` already carries all three on one line for the terminal. Here they are split,
    which is a presentation choice and not a second source of truth: every part is read off the
    same payload.
    """
    payload = alert.payload
    head = format_alert(alert)
    disclosure = str(payload.get("disclosure") or "")
    notes = alert_state_notes(payload)
    if disclosure and disclosure in head:
        head = head.replace(f"   [{disclosure}]", "")
    for note in notes:
        head = head.replace(f"   [{note}]", "")
    lines = [head.rstrip()]
    if payload.get("dry_run"):
        lines.append("[DRY RUN -- log only, nothing was sent to anyone else]")
    for note in notes:
        lines.append(f"!! {note}")
    if disclosure:
        lines.append(f"({disclosure})")
    return "\n".join(lines)


@dataclass
class TelegramSink:
    """An :class:`acumen.live_screener.AlertSink` that puts the alert on the trader's phone.

    Attributes:
        send: the transport. Defaults to :func:`post_message`, which is the only place a
            credential is read and the only place a request is made; a test passes its own and
            never touches the network (the suite's socket guard would block it anyway).
        live: send for real. False -- the DEFAULT -- logs and sends nothing, which is what a
            dry-run morning does. ``run_screener`` sets this from ``--live-alerts`` and from
            nothing else.
        out: where the sink's own lines go (the operator's screen).
        kinds: which alert kinds are forwarded. Everything by default: the trader wants the
            trigger and the exit, and a FAILURE alert is the one that says the tool has stopped
            watching a position, which is the most important message a screener can send.
        sent / refused / failed: counters the CLI prints at the end of the morning, so a
            silent phone is never ambiguous.
    """

    send: Callable[[str], None] | None = None
    live: bool = False
    out: Callable[[str], None] = print
    kinds: frozenset[str] = frozenset(
        {ALERT_ARMED, ALERT_TRIGGER, ALERT_EXIT, ALERT_SQUARE_OFF, ALERT_FAILURE}
    )
    sent: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    _seen: set[tuple[str, str, str]] = field(default_factory=set, repr=False)

    def __repr__(self) -> str:  # CLAUDE.md rule 4: nothing about this object may print a secret
        return (
            f"TelegramSink(live={self.live}, sent={len(self.sent)}, "
            f"refused={len(self.refused)}, failed={len(self.failed)})"
        )

    def deliver(self, alert: RecordedAlert) -> None:
        """The AlertSink protocol. **This method never raises** -- see rule 3 in the module doc."""
        if alert.kind not in self.kinds:
            return
        refusal = unvouched_price(alert)
        if refusal is not None:
            # The chunk-14 rule: no alert forwarded to Telegram may carry a price the screener
            # cannot vouch for. Refused, counted, and said out loud -- the alert is still on the
            # screen and in the recording, so nothing is lost except the forwarding.
            self.refused.append(refusal)
            self.out(f"!! {REFUSED_BANNER}: {refusal}")
            return
        key = LiveScreener._alert_key(alert)
        if key in self._seen:
            return  # CONTEXT 4.4's "no duplicate alerts", held a second time at the sink
        text = message_for(alert)
        if not self.live:
            self._seen.add(key)
            self.out(f"[telegram, DRY RUN -- not sent] {alert.symbol} {alert.kind}")
            return
        transport = self.send if self.send is not None else post_message
        try:
            transport(text)
        except Exception as exc:  # degrade to SILENCE plus a VISIBLE failure, never a crash
            self.failed.append(f"{alert.symbol} {alert.kind}: {type(exc).__name__}")
            self.out(f"!! {FAILURE_BANNER}: {alert.symbol} {alert.kind} ({type(exc).__name__})")
            return
        self._seen.add(key)
        self.sent.append(f"{alert.symbol} {alert.kind}")

    def summary(self) -> str:
        """One line for the end of the morning. Never names a credential."""
        return (
            f"telegram: {len(self.sent)} sent, {len(self.refused)} refused (unvouched price), "
            f"{len(self.failed)} failed"
            + ("" if self.live else "   [DRY RUN -- nothing was sent]")
        )


def post_message(text: str, *, timeout: float = SEND_TIMEOUT_SECONDS) -> None:
    """POST one message to Telegram. The ONLY place a credential is read or a request is made.

    Read-only with respect to the broker in the strongest sense: this talks to Telegram and
    nothing else, and the repository holds no order-placement code for it to reach even if it
    wanted to (:mod:`tests.test_live_safety`).

    Raises:
        TelegramError: the send did not succeed. The message NEVER contains the token, the chat
            id or any part of either -- Telegram's own error bodies are quoted only by status
            code, because an API error body can echo the request.
    """
    import requests

    from .config import env_value

    token = str(env_value(ENV_BOT_TOKEN))
    chat_id = str(env_value(ENV_CHAT_ID))
    try:
        response = requests.post(
            API_TEMPLATE.format(token=token),
            data={"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"},
            timeout=timeout,
        )
    except Exception as exc:
        # `exc` may carry the request URL, and the URL carries the token -- so the TYPE is
        # reported and the original is not chained. This is the one place in the repository
        # where dropping the cause is the safer choice.
        raise TelegramError(f"the Telegram send failed: {type(exc).__name__}") from None
    if response.status_code != 200:
        raise TelegramError(
            f"Telegram answered HTTP {response.status_code}. Check that "
            f"{ENV_BOT_TOKEN} and {ENV_CHAT_ID} in .env are the bot's own token and the chat "
            "you started with it (send the bot a message once, or it cannot reply to you)."
        )


__all__ = [
    "API_TEMPLATE",
    "ENV_BOT_TOKEN",
    "ENV_CHAT_ID",
    "FAILURE_BANNER",
    "REFUSED_BANNER",
    "SEND_TIMEOUT_SECONDS",
    "TelegramError",
    "TelegramSink",
    "credentials_present",
    "message_for",
    "post_message",
]
