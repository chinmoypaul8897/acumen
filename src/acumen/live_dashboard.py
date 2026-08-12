"""THE MORNING DASHBOARD (chunk 13): one screen, one trader, 09:00.

Two surfaces over the same state, because the operator and the trader are not looking at the
same thing: a **terminal** view for whoever is running the session, and an **HTML page** written
to the recording after every sweep, which is the one the trader keeps open.

**Every token here comes from DESIGN.md and nothing is invented** -- CLAUDE.md's code standards
make that a rule for UI work and the architect's 07-Aug-2026 design law makes the *judgment* half
a rule too. The judgment is written down in DESIGN.md PART II and this module is its execution;
the mapping below is that page's own table, in code:

* colour carries STATE and nothing else -- there is no brand colour on this screen, no coloured
  heading, no accent for emphasis;
* ``waiting`` recedes (muted), ``armed`` is the system's only warm colour (coral), ``triggered``
  is its highest-contrast band (deep green, filled), ``in-trade`` is the same family one step
  quieter, ``exited`` is settled ink, and ``refused``/``skipped`` carry a 2px left rule and
  never a fill, so a refusal is visible without out-shouting an armed stock;
* symbols and prices are set in ``mono-label`` so the digits form a scannable column;
* no display type, no card radius, no shadow, no chart -- the four questions at the end of
  DESIGN.md PART II are the acceptance test, and each of those would fail one of them.

The failure banner is the only element permitted the full width, because silence has two
meanings on this screen -- *nothing has fired* and *I am broken* -- and they must never look
alike.

**CONTEXT 4.7 adds two things to this screen and nothing else.** The header of a LIVE session
(dry run included -- a dry-run morning reads the same unverified feed) carries the disclosed
line *"live feed, not yet verified against the exchange's end-of-day record"*, in the same muted
register as the date and the clock: it is a standing condition of the morning, not an alarm. And
the previous day's verdict appears as its own section at the BOTTOM, quiet when the oracle
agreed and in the banner's own colour -- full width, `error`, the only other element allowed it
-- when the exchange's record refuses a day this tool alerted on. Those are the two states that
must never look alike here, for the same reason silence has two meanings above.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import html
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

from .atomic_io import atomic_write_text
from .live_recording import RecordedAlert
from .live_screener import (
    POC_PROVISIONAL,
    PHASE_ARMED,
    PHASE_EXITED,
    PHASE_IN_TRADE,
    PHASE_REFUSED,
    PHASE_SKIPPED,
    PHASE_TRIGGERED,
    PHASE_WAITING,
    PHASES,
    SymbolState,
    format_alert,
)
from .live_screener import rupees as _rupees

#: DESIGN.md's palette, by the names the token file gives them. Nothing outside this dict may
#: appear as a colour anywhere in this module -- the test asserts it.
TOKENS: Mapping[str, str] = {
    "canvas": "#ffffff",
    "ink": "#212121",
    "primary": "#17171c",
    "deep-green": "#003c33",
    "pale-green": "#edfce9",
    "soft-stone": "#eeece7",
    "coral": "#ff7759",
    "muted": "#93939f",
    "slate": "#75758a",
    "hairline": "#d9d9dd",
    "error": "#b30000",
    "on-dark": "#ffffff",
}

#: DESIGN.md PART II's state table, executed. One entry per state, and the seven states are
#: exactly :data:`acumen.live_screener.PHASES`.
STATE_STYLE: Mapping[str, dict] = {
    PHASE_TRIGGERED: {"fg": "on-dark", "bg": "deep-green", "rule": "", "label": "TRIGGERED"},
    PHASE_IN_TRADE: {"fg": "deep-green", "bg": "pale-green", "rule": "deep-green",
                     "label": "IN TRADE"},
    PHASE_ARMED: {"fg": "coral", "bg": "canvas", "rule": "coral", "label": "ARMED"},
    PHASE_WAITING: {"fg": "muted", "bg": "canvas", "rule": "", "label": "waiting"},
    PHASE_EXITED: {"fg": "ink", "bg": "canvas", "rule": "", "label": "exited"},
    PHASE_SKIPPED: {"fg": "slate", "bg": "canvas", "rule": "slate", "label": "skipped"},
    PHASE_REFUSED: {"fg": "muted", "bg": "canvas", "rule": "error", "label": "refused"},
}

#: How far behind the boundary a row's last 1-minute bar may be before the row is STALE.
#:
#: A poll at boundary ``T`` may legally have seen stamps up to ``T - 1min`` (CONTEXT 7-E12, and
#: :func:`acumen.live_source._clamp`), so a fresh row's last stamp IS ``T - 1min``. Anything
#: older means the screener is looking at a prefix that stopped somewhere before now, and
#: REVIEW_13 **B10** is what that cost: a feed answering 200 with an empty candle array froze
#: every row on its last good prefix, and the page rendered "IN TRADE (1) -- position open,
#: being watched" off bars that had stopped an hour earlier, byte-identical to a fresh row,
#: while the header clock asserted the current boundary. DESIGN.md PART II's third acceptance
#: question -- *"if the tool were broken, would this screen look different from a quiet
#: market?"* -- was answered NO by the rendered artifact. One minute of tolerance, because one
#: minute is the honest width of the clamp and not a judgment about liveness.
STALE_AFTER_MINUTES: int = 1

#: What each state means, in the trader's words rather than the engine's. Shown once, as a
#: group heading -- not as a legend, because a screen that needs a legend has already failed
#: DESIGN.md PART II's first question.
STATE_WORDS: Mapping[str, str] = {
    PHASE_TRIGGERED: "just fired -- this is the alert",
    PHASE_IN_TRADE: "position open, being watched",
    PHASE_ARMED: "watch these: a close across the POC enters",
    PHASE_WAITING: "nothing to do yet",
    PHASE_EXITED: "done for the day",
    PHASE_SKIPPED: "no data this sweep -- NOT being watched",
    PHASE_REFUSED: "no trade today, and why",
}


#: Paise as rupees, EXACT -- half-paise POCs included. **The same object the alert line uses.**
#:
#: REVIEW_13 **M10**: this module rendered a half-paise POC exactly (148.695) while
#: ``live_screener._rs`` ran the same number through a binary float and printed 148.69 on the
#: alert line -- so one page showed two different POCs for one stock, and the direction of the
#: difference was IEEE-754's rather than a stated rule. Two implementations of one spec sentence
#: is the defect; this is the fix, and it is an import rather than a copy.
rupees = _rupees


# --- the terminal surface ----------------------------------------------------------------------


def render_text(
    *,
    day: date,
    now: datetime,
    grouped: Mapping[str, Sequence[SymbolState]],
    alerts: Sequence[RecordedAlert],
    banner: str = "",
    dry_run: bool = True,
    width: int = 96,
    disclosure: str = "",
    verification=None,
) -> str:
    """The operator's view: the same seven groups, in the same reading order, as plain text."""
    lines: list[str] = []
    mode = "DRY RUN (log only)" if dry_run else "LIVE"
    lines.append("=" * width)
    lines.append(f"ACUMEN SCREENER   {day.isoformat()}   {now.strftime('%H:%M')}   {mode}")
    if disclosure:
        lines.append(f"({disclosure})")
    lines.append("=" * width)
    if banner:
        lines.append("")
        lines.append("!! " + banner)
    for phase in PHASES:
        rows = list(grouped.get(phase, ()))
        if not rows:
            continue
        lines.append("")
        lines.append(f"{STATE_STYLE[phase]['label']}  ({len(rows)})  -- {STATE_WORDS[phase]}")
        lines.append("-" * width)
        for row in rows:
            lines.append("  " + _text_row(row, now))
    lines.append("")
    lines.append(f"ALERTS ({len(alerts)})")
    lines.append("-" * width)
    if not alerts:
        lines.append("  none yet")
    for alert in alerts:
        lines.append("  " + format_alert(alert))
    if verification is not None:
        lines.append("")
        lines.append(f"YESTERDAY, VERIFIED (CONTEXT 4.7)")
        lines.append("-" * width)
        if verification.refused_after_alert:
            lines.append("  !! " + verification.headline)
        else:
            lines.append("  " + verification.headline)
    lines.append("")
    return "\n".join(lines) + "\n"


def data_age(row: SymbolState, now: datetime) -> tuple[bool, int]:
    """``(is this row STALE, how many minutes behind the boundary its last bar is)``.

    REVIEW_13 B10 / M20. ``SymbolState`` has carried ``last_stamp`` and ``minute_count`` since
    the chunk was built and neither reached either surface, so a row an hour stale was
    indistinguishable from a fresh one. Both are rendered now, and this is the predicate that
    decides whether the row is additionally MARKED -- because a number the reader has to
    subtract in his head at 11:31 is a number he will not subtract at 14:31.

    A ``refused`` row is never stale: its data is not what the reader is being asked to act on,
    and marking it would spend the flag on the one state that is already explaining itself.
    """
    if row.phase == PHASE_REFUSED:
        return (False, 0)
    if row.last_stamp is None:
        return (row.minute_count == 0, 0)
    behind = int((now - row.last_stamp).total_seconds() // 60)
    return (behind > STALE_AFTER_MINUTES, max(0, behind))


def _data_words(row: SymbolState, now: datetime) -> str:
    """The freshness cell: how many bars this verdict stands on, and how old the last one is."""
    stale, behind = data_age(row, now)
    last = "-" if row.last_stamp is None else row.last_stamp.strftime("%H:%M")
    text = f"bars {row.minute_count:>3}  last {last}"
    if stale:
        # Bracketed, never "!!": that marker belongs to the failure banner alone, and a row-level
        # flag that borrowed it would blunt the one element DESIGN.md PART II gives full width.
        text += f"  [STALE {behind}m BEHIND - NOT being watched]"
    if row.poc_provisional:
        text += f"  [{POC_PROVISIONAL}: {row.poc_missing_minutes}m absent]"
    return text


def _text_row(row: SymbolState, now: datetime) -> str:
    head = f"{row.symbol:<14}"
    tail = "   " + _data_words(row, now)
    if row.phase in (PHASE_TRIGGERED, PHASE_IN_TRADE, PHASE_EXITED) and row.entry_paise:
        body = (
            f"{str(row.side or '').upper():<6}"
            f"entry {rupees(row.entry_paise):>11}  "
            f"SL {rupees(row.stop_paise):>11}  "
            f"TP {rupees(row.target_paise):>11}  "
            f"qty {str(row.qty or '-'):>5}"
        )
        if row.exit_kind:
            body += f"  -> {row.exit_kind} at {rupees(row.exit_paise)}"
        return head + body + tail
    if row.phase in (PHASE_ARMED, PHASE_WAITING) and row.poc_paise is not None:
        return (
            head
            + f"{str(row.side or '').upper():<6}"
            + f"POC {rupees(row.poc_paise):>11}  "
            + f"ref {rupees(row.reference_paise):>11}  "
            + f"{row.detail}"
            + tail
        )
    return head + f"{str(row.bias or '-'):<8}{row.detail or row.refusal or ''}" + tail


# --- the HTML surface --------------------------------------------------------------------------


def render_html(
    *,
    day: date,
    now: datetime,
    grouped: Mapping[str, Sequence[SymbolState]],
    alerts: Sequence[RecordedAlert],
    banner: str = "",
    dry_run: bool = True,
    disclosure: str = "",
    verification=None,
) -> str:
    """The trader's screen. Self-contained: no network, no font file, no script.

    Self-contained is not a convenience here. This page is opened at 09:00 on a laptop that may
    have nothing else working; a stylesheet that had to be fetched is a screen that can go blank
    for a reason the trader cannot diagnose.
    """
    parts: list[str] = []
    add = parts.append
    add("<!doctype html>")
    add('<html lang="en"><head><meta charset="utf-8">')
    add('<meta name="viewport" content="width=device-width, initial-scale=1">')
    add(f"<title>Acumen screener {html.escape(day.isoformat())}</title>")
    add(f"<style>{_CSS}</style>")
    add("</head><body>")

    add('<header class="top">')
    add('<div class="title">Acumen screener</div>')
    add(
        '<div class="meta"><span class="mono">'
        + html.escape(day.isoformat())
        + '</span><span class="mono">'
        + html.escape(now.strftime("%H:%M"))
        + "</span><span>"
        + ("dry run - log only" if dry_run else "live")
        + "</span></div>"
    )
    add("</header>")

    if disclosure:
        # CONTEXT 4.7's disclosed line. Muted, in the header's own register: it is true of every
        # figure below it all morning, and a red strip that is always present is a red strip
        # nobody sees by 09:30.
        add(f'<div class="disclosure">{html.escape(disclosure)}</div>')

    if banner:
        add(f'<div class="banner" role="alert">{html.escape(banner)}</div>')

    for phase in PHASES:
        rows = list(grouped.get(phase, ()))
        if not rows:
            continue
        add(f'<section class="group {_slug(phase)}">')
        add(
            '<h2><span class="chip">' + html.escape(STATE_STYLE[phase]["label"]) + "</span>"
            + f'<span class="count">{len(rows)}</span>'
            + f'<span class="words">{html.escape(STATE_WORDS[phase])}</span></h2>'
        )
        add('<div class="rows">')
        for row in rows:
            add(_html_row(row, phase, now))
        add("</div></section>")

    add('<section class="group log"><h2><span class="chip">ALERT LOG</span>'
        f'<span class="count">{len(alerts)}</span></h2><div class="rows">')
    if not alerts:
        add('<div class="row quiet"><span class="mono">nothing has fired today</span></div>')
    for alert in alerts:
        add(
            '<div class="row alert"><span class="mono time">'
            + html.escape(alert.at.strftime("%H:%M"))
            + '</span><span class="mono logsym">'
            + html.escape(alert.symbol)
            + '</span><span class="body">'
            + html.escape(format_alert(alert).split("] ", 1)[-1])
            + "</span></div>"
        )
    add("</div></section>")

    if verification is not None:
        loud = bool(verification.refused_after_alert)
        add('<section class="group verify"><h2><span class="chip">YESTERDAY, VERIFIED</span>'
            '<span class="words">CONTEXT 4.7 -- the full battery, against the published '
            'bhavcopy</span></h2>')
        if loud:
            add(f'<div class="banner" role="alert">'
                f'{html.escape(verification.headline)}</div>')
        else:
            add(f'<div class="row quiet"><span class="body">'
                f'{html.escape(verification.headline)}</span></div>')
        add("</section>")

    add("</body></html>")
    return "\n".join(parts) + "\n"


def _html_row(row: SymbolState, phase: str, now: datetime) -> str:
    cells = [f'<span class="mono sym">{html.escape(row.symbol)}</span>']
    if row.side:
        cells.append(f'<span class="side">{html.escape(row.side)}</span>')
    if phase in (PHASE_TRIGGERED, PHASE_IN_TRADE, PHASE_EXITED) and row.entry_paise:
        for label, value in (
            ("entry", row.entry_paise), ("SL", row.stop_paise), ("TP", row.target_paise)
        ):
            cells.append(
                f'<span class="num"><i>{label}</i><b class="mono">{rupees(value)}</b></span>'
            )
        cells.append(f'<span class="num"><i>qty</i><b class="mono">{row.qty or "-"}</b></span>')
        if row.exit_kind:
            cells.append(
                f'<span class="num"><i>{html.escape(row.exit_kind)}</i>'
                f'<b class="mono">{rupees(row.exit_paise)}</b></span>'
            )
    elif row.poc_paise is not None:
        cells.append(
            f'<span class="num"><i>POC</i><b class="mono">{rupees(row.poc_paise)}</b></span>'
        )
        cells.append(
            f'<span class="num"><i>ref</i><b class="mono">{rupees(row.reference_paise)}</b></span>'
        )
    else:
        cells.append(f'<span class="num"><i>bias</i><b>{html.escape(str(row.bias or "-"))}</b></span>')
    detail = row.detail or row.refusal or ""
    if detail:
        cells.append(f'<span class="detail">{html.escape(detail)}</span>')
    # The freshness cell. Always present, on every row, in the muted register the other
    # secondary numbers use -- and marked when it is old, so a stale row and a fresh one are
    # not the same pixels (REVIEW_13 B10, DESIGN.md PART II question 3).
    stale, behind = data_age(row, now)
    last = "-" if row.last_stamp is None else row.last_stamp.strftime("%H:%M")
    cells.append(
        f'<span class="num data"><i>bars</i><b class="mono">{row.minute_count}</b></span>'
        f'<span class="num data"><i>last</i><b class="mono">{html.escape(last)}</b></span>'
    )
    if stale:
        cells.append(
            f'<span class="flag">STALE - {behind}m behind, NOT being watched</span>'
        )
    if row.poc_provisional:
        # CONTEXT 3.3 / B3's completeness flag, on the surface the trader reads.
        cells.append(
            f'<span class="flag">{html.escape(POC_PROVISIONAL)} '
            f'({row.poc_missing_minutes}m absent)</span>'
        )
    classes = "row stale" if stale else "row"
    return f'<div class="{classes}">{"".join(cells)}</div>'


def _slug(phase: str) -> str:
    return phase.replace("-", "")


def _css() -> str:
    """Built from :data:`TOKENS` so a colour cannot enter this page except through DESIGN.md."""
    t = TOKENS
    rules = [
        f"*{{box-sizing:border-box}}",
        # Type: Unica77 for UI, CohereMono for the scannable columns, both with DESIGN.md's
        # documented fallbacks (the proprietary files are not bundled -- its Known Gaps).
        f"body{{margin:0;background:{t['canvas']};color:{t['ink']};"
        "font-family:'Unica77 Cohere Web',Inter,Arial,ui-sans-serif,system-ui;"
        "font-size:16px;line-height:1.5}",
        ".mono{font-family:CohereMono,'SFMono-Regular',Consolas,Arial,ui-monospace;"
        "font-size:14px;letter-spacing:0.28px;font-variant-numeric:tabular-nums}",
        # Layout: the 8px scale. xl (24px) between groups, lg (16px) inside them -- so the
        # grouping is legible before a word is read (DESIGN.md PART II, Space).
        ".top{display:flex;align-items:baseline;justify-content:space-between;"
        f"padding:24px 24px 16px;border-bottom:1px solid {t['hairline']}}}",
        ".title{font-size:32px;line-height:1.2;letter-spacing:-0.32px}",
        f".meta{{display:flex;gap:16px;color:{t['muted']};font-size:14px}}",
        # The banner: the only full-width element on the page, and it is present or absent.
        f".banner{{background:{t['error']};color:{t['on-dark']};padding:12px 24px;"
        "font-size:16px}",
        # CONTEXT 4.7's disclosed line: the header's own muted register, one hairline below it.
        f".disclosure{{color:{t['muted']};font-size:14px;padding:8px 24px;"
        f"border-bottom:1px solid {t['hairline']}}}",
        ".group{padding:24px 24px 0}",
        "h2{display:flex;align-items:baseline;gap:12px;margin:0 0 12px;font-size:16px;"
        "font-weight:400}",
        f".chip{{font-family:CohereMono,Consolas,Arial,ui-monospace;font-size:14px;"
        f"letter-spacing:0.28px;border-radius:4px;padding:2px 8px;"
        f"background:{t['soft-stone']};color:{t['ink']}}}",
        f".count{{color:{t['muted']};font-size:14px}}",
        f".words{{color:{t['muted']};font-size:14px}}",
        # Rows: unframed, rule-separated. DESIGN.md's own instruction, and 210 boxes would
        # compete with the four that matter.
        f".row{{display:flex;flex-wrap:wrap;align-items:baseline;gap:16px;padding:8px 12px;"
        f"border-bottom:1px solid {t['hairline']}}}",
        ".sym,.logsym{min-width:9rem;font-weight:400}",
        f".side{{font-size:12px;letter-spacing:0.28px;color:{t['muted']};text-transform:uppercase}}",
        ".num{display:inline-flex;gap:6px;align-items:baseline}",
        f".num i{{font-style:normal;font-size:12px;color:{t['muted']}}}",
        ".num b{font-weight:400}",
        f".detail{{color:{t['muted']};font-size:14px}}",
        f".quiet{{color:{t['muted']}}}",
        # The freshness cell and its flag. The flag is `error` ink on the row's own ground --
        # not a fill and not a full-width strip, both of which the banner owns: a stale row must
        # be unmistakable without competing with "the sweep did not complete" (DESIGN.md PART
        # II, and REVIEW_13 B10).
        f".data i{{color:{t['muted']}}}",
        f".flag{{color:{t['error']};font-size:14px}}",
        f".row.stale{{border-left:2px solid {t['error']}}}",
        f".stale .flag{{color:{t['error']}}}",
    ]
    # The seven states. Position on the page decides first, colour second, the word third --
    # so the style below is deliberately small.
    for phase, style in STATE_STYLE.items():
        selector = f".{_slug(phase)} .row"
        decl = [f"color:{t[style['fg']]}"]
        if style["bg"] != "canvas":
            decl.append(f"background:{t[style['bg']]}")
        if style["rule"]:
            decl.append(f"border-left:2px solid {t[style['rule']]}")
        rules.append(f"{selector}{{{';'.join(decl)}}}")
        rules.append(f".{_slug(phase)} .chip{{background:{t[style['bg']]};"
                     f"color:{t[style['fg']]}}}")
    rules.append(f".triggered .num i,.triggered .side,.triggered .detail{{color:{t['on-dark']}}}")
    rules.append("@media (max-width:640px){.sym{min-width:100%}.group{padding:16px 12px 0}}")
    return "".join(rules)


_CSS: str = _css()


def write_dashboard(
    root: Path,
    *,
    day: date,
    now: datetime,
    grouped: Mapping[str, Sequence[SymbolState]],
    alerts: Sequence[RecordedAlert],
    banner: str = "",
    dry_run: bool = True,
    disclosure: str = "",
    verification=None,
) -> tuple[Path, Path]:
    """Write both surfaces into the recording, atomically. Returns ``(html, text)``."""
    page = render_html(day=day, now=now, grouped=grouped, alerts=alerts,
                       banner=banner, dry_run=dry_run, disclosure=disclosure,
                       verification=verification)
    text = render_text(day=day, now=now, grouped=grouped, alerts=alerts,
                       banner=banner, dry_run=dry_run, disclosure=disclosure,
                       verification=verification)
    return (
        atomic_write_text(Path(root) / "dashboard.html", page),
        atomic_write_text(Path(root) / "dashboard.txt", text),
    )


__all__ = [
    "STALE_AFTER_MINUTES",
    "STATE_STYLE",
    "STATE_WORDS",
    "TOKENS",
    "data_age",
    "render_html",
    "render_text",
    "rupees",
    "write_dashboard",
]
