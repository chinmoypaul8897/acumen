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

1. **It sends only when the operator asked.** Three separate deliberate acts stand between an
   operator and a message on somebody's phone -- ``--mode live``, ``--telegram`` and
   ``--live-alerts`` -- and all three are in the gate
   (:func:`acumen.run_screener.telegram_is_live`). REVIEW_14 **H1**: the gate used to be
   ``bool(args.live_alerts and args.telegram)``, with no mode term, while five places in this
   repository said otherwise -- so ``--day 2020-03-19 --telegram --live-alerts`` on the DEFAULT
   (replay) mode put a real 2020 trade on the trader's phone, carrying no date, no mode and no
   marker to tell it apart from an alert about today. A DRY-RUN alert is never sent either: it
   is logged, exactly as the screen and the sound sink log it.
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

## The end-of-day summary

plan.md's chunk-14 card lists *"end-of-day summary message"* beside the bot, and the architect's
14-Aug-2026 ruling says which surface it is about: *"the END-OF-DAY SUMMARY is a card line item
and lands in chunk 14 -- routed to the phone via the sink at close, not only the terminal."*
:meth:`TelegramSink.send_end_of_day` is that route, and it is the SAME route an alert takes --
same ``--live-alerts`` gate, same dry-run labelling, same degrade-to-silence-plus-a-banner, same
credential rule -- so the morning ends with exactly one message carrying the day's alerts by
symbol, :meth:`TelegramSink.summary`'s counters, the marker counts and the disclosed line. It is
sent once per sink, and once per RECORDING: the CLI records :data:`SUMMARY_EVENT` after a
successful send and reads it back before attempting another, which is what makes a resumed
morning end quietly rather than with a second summary.

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

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .live_recording import RecordedAlert
from .live_screener import (
    ALERT_ARMED,
    ALERT_EXIT,
    ALERT_FAILURE,
    ALERT_KINDS,
    ALERT_SQUARE_OFF,
    ALERT_TRIGGER,
    MARKER_POC_PROVISIONAL,
    MARKER_STALE,
    POSTURE_LIVE,
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

#: On any message a DRY RUN produced. REVIEW_14 H1: a message that did not come from a live
#: morning must never be readable on a phone as one, and the only thing separating them used to
#: be CONTEXT 4.7's disclosed line -- which a replay has no reason to carry.
DRY_RUN_MARKER: str = "[DRY RUN -- log only, nothing was sent to anyone else]"

#: On any message about a day that is not today. A replayed 2020 trade and today's trade were
#: byte-identical on the phone apart from a price (REVIEW_14 H1).
REPLAY_MARKER: str = (
    "[REPLAY of a PAST day -- this is not a live alert and nothing about it is about today]"
)

#: On any message whose payload does not say WHICH POSTURE produced it (REVIEW_14B **L2**).
#:
#: ``posture_markers`` read a missing ``mode`` as live -- and live is the one posture that
#: carries no marker at all, so an alert recorded before B411 existed, forwarded or replayed
#: months later, arrived on a phone looking exactly like this morning's. Backwards compatibility
#: was the right call and is kept (the message still goes, and the trade date still travels);
#: what was wrong was resolving the ambiguity in the one direction that cannot be checked. An
#: unstamped payload now says it is unstamped.
UNSTAMPED_MARKER: str = (
    "[POSTURE NOT STAMPED -- this alert's payload does not say which mode produced it, so it is "
    "NOT confirmed to be a live alert. Read its date]"
)

#: **REVIEW_14B L1**, stated rather than left to be read as a contradiction. The alert list in
#: the end-of-day summary is the RECORDING's -- the whole day, however many processes produced it
#: (REVIEW_14 H2) -- while :meth:`TelegramSink.summary`'s three counters are this PROCESS's. After
#: a resume they disagree by design, and each is right about its own subject: *"1 symbol(s)
#: alerted ... telegram: 0 sent"*. Counting deliveries this process did not make would be worse
#: than the ambiguity; saying which number is about what costs one line.
SUMMARY_SUBJECTS: str = (
    "(the list above is the whole day's, read from the recording; the counters are this "
    "process's own -- a resumed morning delivered its alerts before the restart)"
)

#: The end-of-day summary's first line. plan.md's chunk-14 card lists *"end-of-day summary
#: message"* beside the bot itself, and the architect's 14-Aug-2026 ruling says where it goes:
#: *"routed to the phone via the sink at close, not only the terminal"*.
SUMMARY_HEADING: str = "ACUMEN -- END OF DAY"

#: What the summary says when the morning produced nothing. A silent phone must never be
#: ambiguous: this line is the difference between "nothing fired" and "the tool stopped".
SUMMARY_NO_ALERTS: str = "no alerts today -- the screener ran the whole session and nothing fired"

#: The lifecycle event that records the summary really went out, written into the recording by
#: :func:`acumen.run_screener._end_of_day_summary` AFTER a successful send. It is what makes
#: "no duplicate on resume" true across PROCESSES: the sink's own flag dies with the process,
#: this line does not (the same discipline REVIEW_13 M23 set for the alert dedup set).
SUMMARY_EVENT: str = "telegram-end-of-day-summary"

#: The summary's outcome, as one word, for the operator's last line.
SUMMARY_SENT: str = "sent"
SUMMARY_DRY_RUN: str = "dry-run"
SUMMARY_FAILED: str = "failed"


class TelegramError(RuntimeError):
    """A Telegram send could not be made. Caught by the sink; never raised at the screener."""


def credentials_present() -> bool:
    """Are both keys in ``.env``? Reads no value into anything that outlives the call."""
    from .config import env_value

    return bool(env_value(ENV_BOT_TOKEN, required=False)) and bool(
        env_value(ENV_CHAT_ID, required=False)
    )


def message_for(alert: RecordedAlert) -> str:
    """The message body -- the alert line, its DATE, its posture, its states, and the disclosure.

    One message, in the order the trader needs it:

    1. **the alert itself**, in the same words the screen shows (``format_alert``), so what he
       reads on his phone and what the operator reads on the terminal cannot differ -- with the
       TRADE DATE beside the clock time (REVIEW_14 **H1**: the terminal line carries only
       ``[11:30]``, which is fine on a screen headed by the day and dangerous on a phone);
    2. **the posture**, when it is not a live morning: :data:`DRY_RUN_MARKER`,
       :data:`REPLAY_MARKER`, or both. A live alert carries CONTEXT 4.7's disclosed line and a
       replayed one has no reason to, so before this the two were separable only by a price;
    3. **the markers that qualify it**, on their own lines, because a phone wraps a long line
       into something nobody re-reads -- staleness (REVIEW_13B Q1) and B357's provisional POC;
    4. **CONTEXT 4.7's disclosed line**, always, on a live alert.

    ``format_alert`` already carries the middle parts on one line for the terminal. Here they are
    split, which is a presentation choice and not a second source of truth: every part is read
    off the same payload, the mode included.
    """
    payload = alert.payload
    head = format_alert(alert)
    disclosure = str(payload.get("disclosure") or "")
    notes = alert_state_notes(payload)
    if disclosure and disclosure in head:
        head = head.replace(f"   [{disclosure}]", "")
    for note in notes:
        head = head.replace(f"   [{note}]", "")
    lines = [_dated(head.rstrip(), alert)]
    for marker in posture_markers(payload):
        lines.append(marker)
    for note in notes:
        lines.append(f"!! {note}")
    if disclosure:
        lines.append(f"({disclosure})")
    return "\n".join(lines)


def posture_markers(payload) -> tuple[str, ...]:
    """Which posture markers this payload's message carries, in reading order (REVIEW_14 H1).

    Read off the payload like everything else: ``dry_run`` is the screener's own flag and
    ``mode`` is the session's, both already stamped on every alert. A live, live-alerting morning
    produces neither -- which is the ONLY posture that may look like one on a phone.
    """
    markers: list[str] = []
    if payload.get("dry_run"):
        markers.append(DRY_RUN_MARKER)
    mode = str(payload.get("mode") or "")
    if not mode:
        # REVIEW_14B **L2**: no stamp is not the same claim as "live", and only one of the two
        # can be checked. Said out loud instead of assumed in the flattering direction.
        markers.append(UNSTAMPED_MARKER)
    elif mode != POSTURE_LIVE:
        markers.append(REPLAY_MARKER)
    return tuple(markers)


def _dated(line: str, alert: RecordedAlert) -> str:
    """``[11:30]`` -> ``[2026-06-10 11:30]``. The one thing a phone cannot infer from context."""
    clock = alert.at.strftime("%H:%M")
    return line.replace(f"[{clock}]", f"[{alert.at.date().isoformat()} {clock}]", 1)


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
            silent phone is never ambiguous. They count ALERTS; the end-of-day summary carries
            them and is therefore never one of them.
        end_of_day: what became of the one end-of-day message -- unset, sent, dry-run or failed.
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
    #: What became of the ONE end-of-day message: ``""`` (not attempted yet),
    #: :data:`SUMMARY_SENT`, :data:`SUMMARY_DRY_RUN` or :data:`SUMMARY_FAILED`.
    end_of_day: str = ""
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
        """One line for the end of the morning. Never names a credential.

        Its three counters are about ALERTS. The end-of-day message is not one of them and never
        counts itself: it carries this line, so a counter that included it would be a number the
        message changed by being written.
        """
        return (
            f"telegram: {len(self.sent)} sent, {len(self.refused)} refused (unvouched price), "
            f"{len(self.failed)} failed"
            + ("" if self.live else "   [DRY RUN -- nothing was sent]")
        )

    # --- the end-of-day summary (plan.md chunk-14; architect 14-Aug-2026) ---------------

    def end_of_day_message(
        self,
        alerts: Sequence[RecordedAlert] = (),
        *,
        day: date | None = None,
        disclosure: str = "",
    ) -> str:
        """The ONE message that ends the morning, in the order the trader reads it.

        Five parts, and every one of them is read off something that already exists rather than
        recomputed here:

        1. **the heading**, with the trade date, so a message read at 21:00 names its own day;
        2. **the day's alerts BY SYMBOL** -- one line per symbol, each alert as ``kind HH:MM`` in
           the order they fired, because what the trader wants at the close is the shape of his
           day and not seventeen boundaries of detail;
        3. **:meth:`summary`'s own line** -- sent / refused / failed -- which is the ruling's
           "routed to the phone" made literal: the line that used to exist only on the operator's
           terminal now travels;
        4. **the marker counts**, stale and provisional-POC, counted off the same
           ``alert_states`` every alert carried when it was delivered (REVIEW_13B Q1 / B357);
        5. **CONTEXT 4.7's disclosed line**, last, exactly as every live alert carries it.

        A DRY-RUN sink labels the message with the same sentence a dry-run alert carries, so an
        operator reading a terminal transcript months later cannot mistake a rehearsal for a
        morning that reached somebody's phone.
        """
        lines = [
            f"{SUMMARY_HEADING}   {day.isoformat()}" if day is not None else SUMMARY_HEADING
        ]
        if not self.live:
            lines.append(DRY_RUN_MARKER)
        for marker in (REPLAY_MARKER, UNSTAMPED_MARKER):
            if any(marker in posture_markers(alert.payload) for alert in alerts):
                # REVIEW_14 H1: the same rule the alerts obey. One summary of a replayed day must
                # not read on a phone as the summary of today's morning -- and (REVIEW_14B L2) a
                # summary built from alerts nothing stamped must not either.
                lines.append(marker)
        by_symbol: dict[str, list[str]] = {}
        for alert in alerts:
            by_symbol.setdefault(alert.symbol.strip().upper(), []).append(
                f"{alert.kind} {alert.at.strftime('%H:%M')}"
            )
        if by_symbol:
            lines.append(f"{len(by_symbol)} symbol(s) alerted:")
            width = max(len(symbol) for symbol in by_symbol)
            for symbol in sorted(by_symbol):
                lines.append(f"  {symbol:<{width}}  {', '.join(by_symbol[symbol])}")
        else:
            lines.append(SUMMARY_NO_ALERTS)
        lines.append(self.summary())
        if alerts and not (self.sent or self.refused or self.failed):
            # REVIEW_14B **L1**: the two numbers above describe two different subjects, and after
            # a resume they look like a contradiction. One line says which is which.
            lines.append(SUMMARY_SUBJECTS)
        stale = sum(1 for alert in alerts if MARKER_STALE in set(
            alert.payload.get("alert_states") or ()
        ))
        provisional = sum(1 for alert in alerts if MARKER_POC_PROVISIONAL in set(
            alert.payload.get("alert_states") or ()
        ))
        lines.append(f"markers: {stale} stale, {provisional} provisional POC")
        if disclosure:
            lines.append(f"({disclosure})")
        return "\n".join(lines)

    def send_end_of_day(
        self,
        alerts: Sequence[RecordedAlert] = (),
        *,
        day: date | None = None,
        disclosure: str = "",
    ) -> bool:
        """Send the end-of-day summary down the SAME path an alert travels. Never raises.

        Every rule :meth:`deliver` obeys is obeyed here, deliberately by the same code shape:
        ``--live-alerts`` decides whether anything is sent at all, a dry run logs and sends
        nothing, a failure degrades to silence plus a visible failure, and the message is built
        before the transport is touched so nothing about the send can reach the text.

        It is sent at most ONCE per sink. The second guard against a resumed process sending a
        second one lives in the CLI, which records :data:`SUMMARY_EVENT` in the recording after a
        successful send and reads it back before the next attempt -- the sink holds no disk.

        Returns:
            True when a message really left this process.
        """
        if self.end_of_day:
            return False  # one morning, one summary
        text = self.end_of_day_message(alerts, day=day, disclosure=disclosure)
        if not self.live:
            self.end_of_day = SUMMARY_DRY_RUN
            self.out("[telegram, DRY RUN -- not sent] end-of-day summary")
            for line in text.splitlines():
                self.out(f"    {line}")
            return False
        transport = self.send if self.send is not None else post_message
        try:
            transport(text)
        except Exception as exc:  # the same degradation an alert gets: silence, plus a banner
            self.end_of_day = SUMMARY_FAILED
            self.out(f"!! {FAILURE_BANNER}: end-of-day summary ({type(exc).__name__})")
            return False
        self.end_of_day = SUMMARY_SENT
        self.out("telegram: the end-of-day summary went to the phone")
        return True


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
    "DRY_RUN_MARKER",
    "ENV_BOT_TOKEN",
    "ENV_CHAT_ID",
    "FAILURE_BANNER",
    "REPLAY_MARKER",
    "posture_markers",
    "REFUSED_BANNER",
    "SEND_TIMEOUT_SECONDS",
    "SUMMARY_DRY_RUN",
    "SUMMARY_EVENT",
    "SUMMARY_FAILED",
    "SUMMARY_HEADING",
    "SUMMARY_NO_ALERTS",
    "SUMMARY_SENT",
    "SUMMARY_SUBJECTS",
    "UNSTAMPED_MARKER",
    "TelegramError",
    "TelegramSink",
    "credentials_present",
    "message_for",
    "post_message",
]
