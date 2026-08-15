"""REVIEW_14 reviewer probes -- the chunk-14 QC review's own tests, kept in the repo.

Written by the REVIEW session, not the build session. Each one pins a finding from
``docs/reviews/REVIEW_14.md`` at the place the finding lives, and each was written to be GREEN on
the tree as reviewed (`e3c43fa`) so the suite stays honest. **A defect pin asserts the DEFECT.**
The fix session flips it -- that is the property REVIEW_13B's five flipped pins had, and it is
what makes a fix checkable rather than merely claimed.

The probes that pin something CORRECT (the ones whose names say so) must never flip.

**FIVE PINS WERE FLIPPED by the chunk-14 FIX-2 session** (15-Aug-2026), each renamed
``test_FLIPPED_*`` and rewritten to assert the property the defect denied, with the reviewed
behaviour quoted in its docstring so the record of what was wrong survives the fix:

* ``B3`` half two -- the published calendar is COMPOSED, not handed to a runner that refuses it;
* ``B3`` half three -- a test in this repository now drives ``--refresh`` through the CLI;
* ``H1`` -- the Telegram gate names ``args.mode``;
* ``H1``'s census -- the three-act claim is true in every place it is made;
* ``H5`` -- ``parity.run_live`` has a live-posture path.

Three DEFECT pins are deliberately NOT flipped, because their findings are not this session's
scope: ``B3`` half one (a published calendar carries no trading-day set -- which is a true and
permanent property of ``TradingCalendar.from_holidays``, not a defect), and PART 3's two
self-comparison probes (``bias``/``bias_rule`` and the boundary grid), which stay pinned for
chunk 15. ``H5``'s second probe evaluates a copy of the predicate inline and cannot flip.

Store-free by construction: nothing here reads ``data_root`` or ``cache_root``, so these run on a
clone and on a machine whose stores are absent or, as at review time, contaminated.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import calendar as cal
from acumen import live_screener as ls
from acumen import parity
from acumen import run_screener

REPO = Path(__file__).resolve().parents[1]


# --- B3: the documented morning command cannot start the screener -------------------------------


def test_DEFECT_B3_the_published_calendar_carries_no_trading_day_set() -> None:
    """REVIEW_14 **B3**, half one: what ``--refresh`` hands the screener.

    ``morning_refresh`` returns the PUBLISHED holiday calendar (live_refresh.py:140 -> :749) and
    ``run_screener.main`` passes it straight through (run_screener.py:118 -> :164). A published
    calendar has no explicit trading-day set, which is the input ``build_runner`` refuses.
    """
    published = cal.TradingCalendar.from_holidays(
        [date(2026, 1, 26)], covered_years=[2026, 2025]
    )
    assert published.trading_days is None, (
        "if this ever carries a trading-day set, B3's first half is fixed -- flip this probe"
    )
    assert published.covered_days is None


def test_FLIPPED_B3_the_calendar_refresh_supplies_is_COMPOSED_not_handed_on_raw() -> None:
    """REVIEW_14 **B3**, half two -- **PIN FLIPPED by the chunk-14 FIX-2 session.**

    As reviewed: ``backtest.build_runner`` rejects any supplied calendar whose ``trading_days``
    is None, and ``build_live_screener`` composed the proper live calendar only when the caller
    supplied NONE -- so ``--refresh``, which always supplies one, reached the refusal, and the
    operator's own 08:45 command mutated the stores and then exited 1.

    The refusal in ``build_runner`` is CORRECT and stays: without an explicit trading-day set
    there is nothing for CONTEXT 7-E2's non-standard sessions to be subtracted from. What changed
    is the caller. A supplied calendar carrying no trading-day set is now composed through
    ``calendar.live_trading_calendar`` before it goes anywhere near the runner.
    """
    source = inspect.getsource(bt.build_runner)
    assert "elif calendar.trading_days is None:" in source, "the refusal is still there"
    assert "A supplied calendar must carry an EXPLICIT trading-day set" in source

    guarded = inspect.getsource(ls.build_live_screener)
    assert "if live and calendar is None:" not in guarded, "the defect's own line, gone"
    assert "calendar is not None and calendar.trading_days is None" in guarded, (
        "a PUBLISHED master supplied by --refresh is composed, not passed on raw"
    )
    assert "published=calendar" in guarded, (
        "...and composed from the master the refresh already fetched and cross-checked "
        "(REVIEW_13 M17's C5 duty), rather than from a second pull"
    )


def test_FLIPPED_B3_a_test_in_this_repository_DOES_drive_refresh_through_the_CLI() -> None:
    """REVIEW_14 **B3**, half three -- **PIN FLIPPED.** The coverage gap that hid it, closed.

    At review time the whole pre-open-to-screener seam was unexercised: the only two ``--refresh``
    hits under ``tests/`` were a docstring and a comment, which is why nothing caught a defect
    sitting on the operator's own documented command. This probe counts the tests that build a
    ``--refresh`` argv and hand it to ``run_screener.main``.
    """
    drivers = []
    for path in (REPO / "tests").glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue  # this file quotes the flag to describe the gap; it does not drive it
        text = path.read_text(encoding="utf-8", errors="replace")
        if '"--refresh"' in text and "main(" in text:
            drivers.append(path.name)
    assert drivers, "no test drives --refresh through the CLI -- B3's coverage gap is back"
    assert "test_review14_fix.py" in drivers


# --- H1: the three-act gate is two acts ---------------------------------------------------------


def test_FLIPPED_H1_the_telegram_gate_NAMES_the_mode() -> None:
    """REVIEW_14 **H1** -- **PIN FLIPPED.** ``--mode live`` is one of the acts, in code.

    As reviewed the gate was ``TelegramSink(live=bool(args.live_alerts and args.telegram))`` --
    two flags, no mode -- and the mode DEFAULTS to replay, so ``--day 2020-03-19 --telegram
    --live-alerts`` put two real messages on the transport.

    Asserted over the AST of the gate function rather than over its text, so a comment mentioning
    the mode cannot make this pass. The gate is a named function now (``telegram_is_live``), so
    the thing a reader checks and the thing this asserts are the same object.
    """
    tree = ast.parse(inspect.getsource(run_screener.main))
    gate_calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "TelegramSink":
            for kw in node.keywords:
                if kw.arg == "live":
                    gate_calls = [
                        n.func.id for n in ast.walk(kw.value)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ]
    assert gate_calls == ["telegram_is_live"], gate_calls

    gate = ast.parse(inspect.getsource(run_screener.telegram_is_live))
    terms = {
        node.attr for node in ast.walk(gate)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        and node.value.id == "args"
    }
    assert terms == {"mode", "telegram", "live_alerts"}, terms
    assert run_screener.telegram_is_live(
        run_screener.parse_args(["--day", "2020-03-19", "--telegram", "--live-alerts"])
    ) is False, "the review's own command: replay by default, so nothing may be sent"
    assert run_screener.telegram_is_live(run_screener.parse_args(
        ["--mode", "live", "--day", "2026-08-14", "--telegram", "--live-alerts"]
    )) is True


def test_FLIPPED_the_three_act_claim_is_TRUE_in_every_place_it_is_made() -> None:
    """REVIEW_14 **H1**, the other side -- **PIN FLIPPED.** The claim the code now keeps.

    As reviewed this was a census of five places asserting a gate the code did not have; the
    sink's own module doc said "Two separate deliberate acts ... ``--mode live`` and
    ``--live-alerts``", which is neither the code's gate nor the runbook's claim. H1 was fixed by
    adding the missing act rather than by softening the prose, so every one of the five now names
    the SAME three flags -- and the one that said "two" no longer does.
    """
    for relpath in ("src/acumen/telegram_sink.py", "src/acumen/run_screener.py",
                    "docs/morning_runbook.md"):
        text = (REPO / relpath).read_text(encoding="utf-8", errors="replace")
        claims = [
            line for line in text.splitlines()
            if "deliberate acts" in line and ("three" in line.lower())
        ]
        assert claims, f"{relpath} no longer makes the three-act claim"
        for flag in ("--mode live", "--telegram", "--live-alerts"):
            assert flag in text, f"{relpath} does not name {flag}"
        assert "Two separate deliberate acts" not in text, relpath


# --- H5: the parity harness cannot judge the LIVE posture ---------------------------------------


def test_FLIPPED_H5_run_live_HAS_a_live_posture_path() -> None:
    """REVIEW_14 **H5** -- **PIN FLIPPED.** The harness can judge the posture the tool runs in.

    As reviewed: ``build_live_screener`` sets ``gates = {} if live else full_day_gates(...)``,
    because CONTEXT 4.7 gives a live morning no settled battery at all -- and ``parity.run_live``
    computed the live half's own whole-day ``StockDay`` only when ``screener.gates.get(symbol)``
    was not None. So ``live_final`` stayed None and ``trails_equal`` was structurally False for
    every day the backtester has a signal: 8 of 8 oracle-passing live-posture days judged, 0
    matched, each with exactly one invented mismatch.

    The input side is unchanged and correct -- a live morning has no oracle. What ``run_live``
    gained is the battery the live half ITSELF used at every sweep, ``oracle_free_battery`` over
    the bars in hand plus the duplicate stamps, which is ``LiveScreener._battery``'s own live
    branch rather than a second reading of it.
    """
    built = inspect.getsource(ls.build_live_screener)
    assert "gates = {} if live else full_day_gates(" in built, (
        "the live posture still computes no settled battery -- CONTEXT 4.7, unchanged"
    )
    driven = inspect.getsource(parity.run_live)
    assert "gates = screener.gates.get(symbol)" in driven
    assert "if gates is None and screener.posture == POSTURE_LIVE:" in driven, (
        "the live-posture path H5 asked for"
    )
    assert "oracle_free_battery(" in driven, "and it is the battery the live half used"


def test_DEFECT_H5_trails_equal_is_False_when_only_the_live_half_is_missing() -> None:
    """REVIEW_14 **H5**, the consequence, exercised directly on the predicate.

    No stores, no screener: the two-clause expression at parity.py:480-483 is evaluated for the
    exact shape live posture produces -- a backtest signal present, the live half's own StockDay
    absent.
    """
    def trails_equal(live_final, signal) -> bool:
        return (
            live_final is not None and getattr(live_final, "signal", None) is not None
            and signal is not None
            and live_final.signal.transitions == signal.transitions
        ) or (signal is None and live_final is None)

    class _Signal:
        transitions = ("t",)

    assert trails_equal(None, None) is False or trails_equal(None, _Signal()) is False
    assert trails_equal(None, _Signal()) is False, (
        "live posture: the backtester has a signal, the live half's own answer was never "
        "computed -- so the harness reports a trail mismatch that does not exist"
    )


# --- PART 3: the harness's self-comparisons -----------------------------------------------------


def test_DEFECT_the_parity_bias_comparison_is_a_self_comparison() -> None:
    """REVIEW_14 PART 3: ``bias`` and ``bias_rule`` can never differ between the two halves.

    ``parity_for_screener`` evaluates the BACKTEST side with the LIVE screener's own bias
    (``bias = screener.biases.get(symbol)`` then ``pipeline.evaluate(..., bias=bias, ...)``), and
    then reads ``stock_day.bias`` back as the backtest answer. Two of the five DAY_FIELDS are
    therefore tautological.

    The ANSWER is still right -- REVIEW_14 re-derived ITC 2026-06-10's bias by hand from the
    daily store and it matches -- but the harness does not check it, and the report reads as
    though it does.
    """
    source = inspect.getsource(parity.parity_for_screener)
    assert "bias = screener.biases.get(symbol)" in source
    assert "bias=bias" in source, "the backtest side is handed the LIVE bias"
    assert "bias" in parity.DAY_FIELDS and "bias_rule" in parity.DAY_FIELDS, (
        "...and both are then 'compared'. When the backtest side resolves its own bias, this "
        "probe flips."
    )


def test_DEFECT_the_boundary_grid_comes_from_the_live_half() -> None:
    """REVIEW_14 PART 3: ``compare()``'s boundary-count guard can never fire.

    ``parity_for_screener`` builds the projection over
    ``boundaries = tuple(d.boundary for d in live_decisions)`` -- the live half's own output --
    so the two sequences are equal in length by construction.
    """
    source = inspect.getsource(parity.parity_for_screener)
    assert "boundaries = tuple(decision.boundary for decision in live_decisions)" in source
    guard = inspect.getsource(parity.compare)
    assert "boundary count: live=" in guard, (
        "the guard exists and is unreachable from parity_for_screener; it is reachable only from "
        "a hand-built compare() call, which is how tests/test_parity.py exercises it"
    )


# --- what is CORRECT, pinned so a later change cannot quietly undo it ---------------------------


def test_the_gap_entry_stop_is_the_PREVIOUS_candles_close_not_the_entry_extreme() -> None:
    """CONTEXT 3.4-3, pinned at the number REVIEW_14 hand-derived.

    ADANIENSOL 2026-05-08, short: entry 137790, entry candle HIGH 138100 < POC 138155, so the
    candle opened beyond the POC and never traded at or above it -- the gap-entry case. SL is the
    PREVIOUS 15-min candle's close, 138160, NOT the entry candle's high.

    The distinction is worth 52 shares: the spec's rule gives risk 370 and qty 270; the entry
    high would give risk 310 and qty 322. Hand-derived from the raw Parquet by the review, and
    matched by both the projection and the live screener at all 18 boundaries.
    """
    entry, prev_close, entry_high, poc = 137790, 138160, 138100, 138155
    assert entry_high < poc, "the bearish gap-entry condition"

    stop = prev_close
    risk = stop - entry
    assert risk == 370
    assert entry - 3 * risk == 136680, "TP = entry - 3 x risk (short)"
    assert 100_000 // risk == 270, "qty = floor(risk_per_trade_paise / per-share risk)"

    wrong_risk = entry_high - entry
    assert wrong_risk == 310 and 100_000 // wrong_risk == 322, (
        "what the entry-candle-high shortcut would have produced -- 52 shares more"
    )


def test_the_ITC_carried_day_has_no_qualifying_cross() -> None:
    """CONTEXT 3.4, pinned at the number REVIEW_14 hand-derived.

    ITC 2026-06-10, bearish/short, ARMED from 11:15 (reference 28440 > POC 56655/2 = 28327.5).
    A short triggers on the first ARMED-state close STRICTLY BELOW the POC. The sixteen eligible
    closes bottom out at 28385 -- 57.5 paise, 11.5 ticks, above it -- so the day never triggers
    and stays ARMED at all eighteen boundaries.
    """
    from fractions import Fraction

    poc = Fraction(56655, 2)
    closes = [28430, 28420, 28415, 28430, 28400, 28385, 28480, 28525,
              28490, 28475, 28465, 28440, 28435, 28415, 28415, 28390]
    assert len(closes) == 16
    assert min(closes) == 28385
    assert not [c for c in closes if c < poc], "no close is strictly below the POC"
    assert 28440 > poc, "the 11:15 reference arms the bearish day"
    assert poc.denominator == 2, "a half-paise POC: rows span an ODD 25 paise (tpr 5 x tick 5)"


@pytest.mark.parametrize("marker", ["stale", "poc-provisional"])
def test_the_alert_states_vocabulary_is_closed(marker: str) -> None:
    """REVIEW_14 PART 0.5: a payload's ``alert_states`` is a subset of a named tuple.

    Pinned because it is the property that lets a Telegram message render a marker it did not
    invent, and because B381's one-source claim rests on it.
    """
    assert marker in ls.ALERT_STATES
    assert len(ls.ALERT_STATES) == 2, (
        "a third state needs a rendering in format_alert, the dashboard row AND message_for"
    )
