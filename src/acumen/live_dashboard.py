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


def rupees(paise) -> str:
    """Integer (or exact Fraction) paise as rupees -- and a HALF-paise POC as it really is.

    CONTEXT 3.3 lets a POC sit on half a paisa (it is a row MIDPOINT) and CONTEXT 7-E11 says
    every comparison against it runs at full precision. Two decimal places are right for money
    and wrong for a row midpoint: they would move the POC by half a paisa on the one screen
    whose purpose is that the trader can check it against his own chart. So a value that is a
    whole number of paise prints in two places and one that is not prints in three -- the same
    rule ``trader_pack._Emit.poc`` applies to the validation pack, for the same reason.

    Exact throughout: :class:`~fractions.Fraction` and :class:`~decimal.Decimal`, never a float.
    """
    if paise is None:
        return "-"
    value = Fraction(paise)
    if value.denominator == 1:
        exact = (Decimal(value.numerator) / Decimal(100)).quantize(Decimal("0.01"))
        return f"{exact:,.2f}"
    exact = (
        Decimal(value.numerator) / Decimal(value.denominator) / Decimal(100)
    ).quantize(Decimal("0.001"))
    return f"{exact:,.3f}"


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
            lines.append("  " + _text_row(row))
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


def _text_row(row: SymbolState) -> str:
    head = f"{row.symbol:<14}"
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
        return head + body
    if row.phase in (PHASE_ARMED, PHASE_WAITING) and row.poc_paise is not None:
        return (
            head
            + f"{str(row.side or '').upper():<6}"
            + f"POC {rupees(row.poc_paise):>11}  "
            + f"ref {rupees(row.reference_paise):>11}  "
            + f"{row.detail}"
        )
    return head + f"{str(row.bias or '-'):<8}{row.detail or row.refusal or ''}"


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
            add(_html_row(row, phase))
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


def _html_row(row: SymbolState, phase: str) -> str:
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
    return f'<div class="row">{"".join(cells)}</div>'


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
    "STATE_STYLE",
    "STATE_WORDS",
    "TOKENS",
    "render_html",
    "render_text",
    "rupees",
    "write_dashboard",
]
