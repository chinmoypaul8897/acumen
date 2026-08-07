"""THE MORNING DASHBOARD (chunk 13), held against DESIGN.md rather than against taste.

The architect's 07-Aug-2026 design law has two halves -- the getdesign ``cohere`` system, and
deliberate design judgment. The first half is checkable by a machine and this file checks it:
**every colour on the screen exists in DESIGN.md**, and there is no other source of colour. The
second half is written down in DESIGN.md PART II and its four acceptance questions are what the
reviewer holds the rendered page against; the ones that can be made executable are made
executable here (one state per stock, colour carries state and nothing else, a broken screener
does not look like a quiet market).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

from acumen import live_dashboard as dash
from acumen import live_screener as ls
from acumen.live_recording import RecordedAlert

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN = REPO_ROOT / "DESIGN.md"
DAY = date(2026, 7, 17)
NOW = datetime(2026, 7, 17, 11, 30)


def states() -> dict[str, tuple[ls.SymbolState, ...]]:
    """One stock in each of the seven states -- the screen at its most crowded."""
    return {
        ls.PHASE_TRIGGERED: (ls.SymbolState(
            symbol="HDFCBANK", phase=ls.PHASE_TRIGGERED, side="long", bias="bullish",
            poc_paise=Fraction(73_980), reference_paise=73_820, entry_paise=74_095,
            stop_paise=73_810, target_paise=74_950, qty=350, detail="entry on the 11:30 close",
        ),),
        ls.PHASE_IN_TRADE: (ls.SymbolState(
            symbol="RELIANCE", phase=ls.PHASE_IN_TRADE, side="short", bias="bearish",
            poc_paise=Fraction(146_585), entry_paise=146_200, stop_paise=146_700,
            target_paise=144_700, qty=20,
        ),),
        ls.PHASE_ARMED: (ls.SymbolState(
            symbol="TCS", phase=ls.PHASE_ARMED, side="long", bias="bullish",
            poc_paise=Fraction(225_025), reference_paise=224_900,
            detail="armed -- waiting for a close across the POC",
        ),),
        ls.PHASE_WAITING: (ls.SymbolState(
            symbol="DIXON", phase=ls.PHASE_WAITING, side="long", bias="bullish",
            poc_paise=Fraction(1_426_350), reference_paise=1_427_000,
            detail="wait-below: needs a close on the other side of the POC first",
        ),),
        ls.PHASE_EXITED: (ls.SymbolState(
            symbol="INFY", phase=ls.PHASE_EXITED, side="long", bias="bullish",
            entry_paise=150_000, stop_paise=149_000, target_paise=153_000, qty=100,
            exit_kind="stop-loss-hit", exit_paise=149_000,
        ),),
        ls.PHASE_SKIPPED: (ls.SymbolState(
            symbol="BEL", phase=ls.PHASE_SKIPPED, bias="bullish",
            detail="missed the 11:30 window; will be re-polled",
        ),),
        ls.PHASE_REFUSED: (ls.SymbolState(
            symbol="IOC", phase=ls.PHASE_REFUSED, bias="bearish",
            detail="gate 1 (volume reconciliation)", refusal="gate 1 (volume reconciliation)",
        ),),
    }


def alerts() -> tuple[RecordedAlert, ...]:
    return (
        RecordedAlert(kind=ls.ALERT_ARMED, symbol="TCS", at=datetime(2026, 7, 17, 11, 15),
                      payload={"side": "long", "poc_paise": "225025",
                               "reference_paise": 224_900, "bias": "bullish"}),
        RecordedAlert(kind=ls.ALERT_TRIGGER, symbol="HDFCBANK", at=NOW,
                      payload={"side": "long", "entry_paise": 74_095, "stop_paise": 73_810,
                               "target_paise": 74_950, "qty": 350, "poc_paise": "73980",
                               "bias": "bullish"}),
    )


# --- the design law, half one: the tokens ----------------------------------------------------------


def test_EVERY_COLOUR_ON_THE_SCREEN_COMES_FROM_DESIGN_MD() -> None:
    """CLAUDE.md code standards: *"UI work: tokens from DESIGN.md only -- never invent colors"*.

    Checked at the RENDERED page, not at the token dict, because the dict is not what ships.
    Every hex value in the emitted HTML is looked up in DESIGN.md itself; a colour typed into the
    module would have to exist in the design system to survive, which is the whole rule.
    """
    design = DESIGN.read_text(encoding="utf-8").lower()
    page = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=alerts(),
                            banner="a sweep did not complete")
    used = {value.lower() for value in re.findall(r"#[0-9a-fA-F]{3,8}", page)}
    assert used, "the page really does carry colour"
    missing = sorted(value for value in used if value not in design)
    assert not missing, f"invented colours, absent from DESIGN.md: {missing}"

    # and the module's own palette is DESIGN.md's, name for name
    for name, value in dash.TOKENS.items():
        assert value.lower() in design, f"token {name} = {value} is not in DESIGN.md"


def test_the_module_carries_no_hex_colour_outside_the_token_table() -> None:
    """The other direction: a colour cannot enter the page except through :data:`TOKENS`."""
    text = (REPO_ROOT / "src" / "acumen" / "live_dashboard.py").read_text(encoding="utf-8")
    hexes = re.findall(r'"(#[0-9a-fA-F]{3,8})"', text)
    assert sorted(set(hexes)) == sorted({value for value in dash.TOKENS.values()})


def test_COLOUR_CARRIES_STATE_AND_NOTHING_ELSE() -> None:
    """DESIGN.md PART II's second acceptance question, made executable.

    There is no brand colour on this screen, no coloured heading and no accent for emphasis. So
    every state style must draw from the state table, the seven states must be exactly the
    screener's seven, and no two states may be styled identically -- a state a stranger cannot
    tell apart from another is a state the first acceptance question fails on.
    """
    assert set(dash.STATE_STYLE) == set(ls.PHASES) == set(dash.STATE_WORDS)
    signatures = {
        phase: (style["fg"], style["bg"], style["rule"])
        for phase, style in dash.STATE_STYLE.items()
    }
    assert len(set(signatures.values())) == len(signatures), (
        f"two states look alike: {signatures}"
    )
    for phase, style in dash.STATE_STYLE.items():
        for key in ("fg", "bg", "rule"):
            if style[key]:
                assert style[key] in dash.TOKENS, f"{phase}.{key} is not a DESIGN.md token"

    # the design intent's own assignments, as PART II's table writes them
    assert dash.STATE_STYLE[ls.PHASE_ARMED]["fg"] == "coral"
    assert dash.STATE_STYLE[ls.PHASE_TRIGGERED]["bg"] == "deep-green"
    assert dash.STATE_STYLE[ls.PHASE_WAITING]["fg"] == "muted"
    assert dash.STATE_STYLE[ls.PHASE_REFUSED]["rule"] == "error"
    assert dash.STATE_STYLE[ls.PHASE_REFUSED]["bg"] == "canvas", (
        "a refusal is a 2px rule and NEVER a fill -- it must not out-shout an armed stock"
    )


def test_no_display_type_no_shadow_no_card_radius() -> None:
    """DESIGN.md PART II: *"96px is a marketing gesture and this is an instrument panel"*.

    And its fourth question -- could an element be deleted with no loss of meaning? A shadow, a
    22px media radius on a page with no media, and hero type all answer yes.
    """
    page = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=alerts())
    style = page.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "box-shadow" not in style and "text-shadow" not in style
    assert "22px" not in style, "the signature media radius on a page with no media"
    for marketing in ("96px", "72px", "60px", "48px"):
        assert marketing not in style, f"display type {marketing} on an instrument panel"
    assert "border-radius:4px" in style, "the state chips, and nothing else, carry xs"


# --- the design law, half two: the judgment, where it can be executed --------------------------------


def test_a_BROKEN_screener_does_not_look_like_a_QUIET_market() -> None:
    """DESIGN.md PART II's third acceptance question, and the safety rail's visible half.

    Silence has two meanings on this screen. The banner is the only full-width element and it is
    present or absent -- never a small grey note that a busy reader takes for chrome.
    """
    quiet = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=())
    broken = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=(),
                              banner="11:30 sweep INCOMPLETE -- 4 symbol(s) never answered")
    assert 'class="banner"' not in quiet
    assert 'class="banner" role="alert"' in broken
    assert "never answered" in broken
    assert dash.TOKENS["error"] in broken.split("<style>", 1)[1]
    assert len(broken) > len(quiet), "the difference is visible, not a colour change"

    text_quiet = dash.render_text(day=DAY, now=NOW, grouped=states(), alerts=())
    text_broken = dash.render_text(day=DAY, now=NOW, grouped=states(), alerts=(),
                                   banner="11:30 sweep INCOMPLETE")
    assert "!!" in text_broken and "!!" not in text_quiet


def test_every_stock_appears_ONCE_and_the_groups_read_in_urgency_order() -> None:
    """PART II: *"a stock never appears twice, never in two states"* -- and the order is the
    morning's, not the alphabet's: what just fired, then what is open, then what to watch."""
    page = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=alerts())
    for symbol in ("HDFCBANK", "RELIANCE", "TCS", "DIXON", "INFY", "BEL", "IOC"):
        assert page.count(f'class="mono sym">{symbol}<') == 1, f"{symbol} is shown twice"

    order = [page.index(f'class="group {phase.replace("-", "")}"') for phase in ls.PHASES]
    assert order == sorted(order), "the groups render in PHASES order"
    assert ls.PHASES[0] == ls.PHASE_TRIGGERED and ls.PHASES[-1] == ls.PHASE_REFUSED


def test_the_page_is_SELF_CONTAINED_and_needs_no_network_to_render() -> None:
    """It is opened at 09:00 on a laptop that may have nothing else working.

    A stylesheet, a font or a script that had to be fetched is a screen that can go blank for a
    reason the trader cannot diagnose -- and this page's job is to be readable when things are
    going wrong.
    """
    page = dash.render_html(day=DAY, now=NOW, grouped=states(), alerts=alerts())
    for forbidden in ("<script", "http://", "https://", "@import", "<link"):
        assert forbidden not in page, f"the dashboard reaches out: {forbidden}"
    assert "<style>" in page


def test_prices_are_rendered_from_exact_paise_and_never_from_a_float() -> None:
    """CONTEXT 7-E11: integer paise internally, no float equality. The POC may be HALF a paisa.

    A dashboard that rounded a half-paise POC to the paisa would print a number that is not the
    number the engine compared against, on the one screen the trader checks it on.
    """
    assert dash.rupees(200_005) == "2,000.05"
    assert dash.rupees(Fraction(400_011, 2)) == "2,000.055", "half a paisa survives to the screen"
    assert dash.rupees(None) == "-"
    assert dash.rupees(0) == "0.00"
    page = dash.render_html(
        day=DAY, now=NOW,
        grouped={ls.PHASE_ARMED: (ls.SymbolState(symbol="X", phase=ls.PHASE_ARMED,
                                                 poc_paise=Fraction(400_011, 2)),)},
        alerts=(),
    )
    assert "2,000.055" in page


def test_both_surfaces_are_written_into_the_recording(tmp_path: Path) -> None:
    """The operator's terminal view and the trader's page come from the same state, every sweep."""
    page, text = dash.write_dashboard(
        tmp_path, day=DAY, now=NOW, grouped=states(), alerts=alerts(), banner="", dry_run=True,
    )
    assert page.name == "dashboard.html" and text.name == "dashboard.txt"
    body = page.read_text(encoding="utf-8")
    assert "HDFCBANK" in body and "Acumen screener" in body
    plain = text.read_text(encoding="utf-8")
    assert "TRIGGERED" in plain and "DRY RUN" in plain
    assert "740.95" in plain and "738.10" in plain and "749.50" in plain


def test_the_text_surface_shows_the_same_seven_groups(tmp_path: Path) -> None:
    """The operator must not be reading a different screen from the trader."""
    plain = dash.render_text(day=DAY, now=NOW, grouped=states(), alerts=alerts())
    for phase in ls.PHASES:
        assert dash.STATE_STYLE[phase]["label"] in plain
        assert dash.STATE_WORDS[phase] in plain
    assert plain.index("TRIGGERED") < plain.index("ARMED") < plain.index("refused")
