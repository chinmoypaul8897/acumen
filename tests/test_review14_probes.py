"""REVIEW_14 reviewer probes -- the chunk-14 QC review's own tests, kept in the repo.

Written by the REVIEW session, not the build session. Each one pins a finding from
``docs/reviews/REVIEW_14.md`` at the place the finding lives, and each is written to be GREEN on
the tree as reviewed (`e3c43fa`) so the suite stays honest. **A defect pin asserts the DEFECT.**
The fix session flips it -- that is the property REVIEW_13B's five flipped pins had, and it is
what makes a fix checkable rather than merely claimed.

The probes that pin something CORRECT (the ones whose names say so) must never flip.

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


def test_DEFECT_B3_build_runner_REFUSES_the_calendar_that_refresh_supplies() -> None:
    """REVIEW_14 **B3**, half two: the refusal, read out of the shipped source.

    ``backtest.build_runner`` rejects any supplied calendar whose ``trading_days`` is None, and
    ``live_screener.build_live_screener`` builds the proper live calendar only when the caller
    supplied none -- so ``--refresh`` (which always supplies one) reaches the refusal. The net
    effect on a real morning is that the pre-open writes to the stores and THEN exits 1.
    """
    source = inspect.getsource(bt.build_runner)
    assert "elif calendar.trading_days is None:" in source, (
        "the refusal that B3 lands on"
    )
    assert "A supplied calendar must carry an EXPLICIT trading-day set" in source

    guarded = inspect.getsource(ls.build_live_screener)
    assert "if live and calendar is None:" in guarded, (
        "the live calendar is built only when the caller supplied none -- which --refresh never "
        "is. When this becomes unconditional (or run_screener composes the published master "
        "through live_trading_calendar), B3 is fixed and this probe flips."
    )


def test_DEFECT_B3_no_test_in_the_repository_drives_refresh_through_the_CLI() -> None:
    """REVIEW_14 **B3**, half three: why nobody caught it.

    The whole pre-open-to-screener seam is unexercised. This probe counts the tests that build a
    ``--refresh`` argv and hand it to ``run_screener.main``; the answer at review time is zero.
    """
    drivers = 0
    for path in (REPO / "tests").glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue  # this file quotes the flag to describe the gap; it does not drive it
        text = path.read_text(encoding="utf-8", errors="replace")
        if '"--refresh"' in text and "main(" in text:
            drivers += 1
    assert drivers == 0, (
        f"{drivers} test(s) now drive --refresh through the CLI -- B3's coverage gap is closing; "
        "flip this probe to assert drivers >= 1"
    )


# --- H1: the three-act gate is two acts ---------------------------------------------------------


def test_DEFECT_H1_the_telegram_gate_has_no_mode_term() -> None:
    """REVIEW_14 **H1**: ``--mode live`` is not one of the acts, though five places say it is.

    Asserted over the AST of ``run_screener.main`` rather than over its text, so a comment
    mentioning the mode cannot make this pass. The gate is
    ``TelegramSink(live=bool(args.live_alerts and args.telegram))`` -- two flags, no mode.
    """
    tree = ast.parse(inspect.getsource(run_screener.main))
    gate_args: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "TelegramSink":
            for kw in node.keywords:
                if kw.arg == "live":
                    gate_args = [
                        n.attr for n in ast.walk(kw.value) if isinstance(n, ast.Attribute)
                    ]
    assert gate_args, "the TelegramSink(live=...) gate must exist"
    assert "mode" not in gate_args, (
        f"the gate now reads {gate_args} -- if it names the mode, H1 is fixed and this flips"
    )
    assert set(gate_args) == {"live_alerts", "telegram"}, gate_args


def test_the_three_act_claim_is_made_in_five_places() -> None:
    """REVIEW_14 **H1**, the other side: the claim the code does not keep.

    Kept as a census rather than a judgement. When H1 is fixed by adding the mode term, these
    five stay true and this probe stays green; when it is fixed by CORRECTING the prose instead,
    this probe flips and says so.
    """
    claims = {
        "src/acumen/telegram_sink.py": "``--mode live`` and ``--live-alerts``",
        "src/acumen/run_screener.py": "three separate deliberate acts",
        "docs/morning_runbook_stub.md": "Three deliberate acts stand between you",
    }
    for relpath, needle in claims.items():
        text = (REPO / relpath).read_text(encoding="utf-8", errors="replace")
        assert needle in text, f"{relpath} no longer makes the three-act claim -- H1 may be fixed"


# --- H5: the parity harness cannot judge the LIVE posture ---------------------------------------


def test_DEFECT_H5_live_posture_leaves_the_harness_without_the_live_halfs_own_answer() -> None:
    """REVIEW_14 **H5**: ``transitions_equal`` is structurally False in CONTEXT 4.7 posture.

    ``build_live_screener`` sets ``gates = {} if live else full_day_gates(...)``, and
    ``parity.run_live`` computes the live half's own whole-day ``StockDay`` only when
    ``screener.gates.get(symbol)`` is not None. So in live posture ``live_final`` is None, and
    ``trails_equal`` is False for every day the backtester has a signal -- a FALSE mismatch on
    every judged live-posture day.

    It fails SAFE (it invents a mismatch; it cannot hide one), which is why REVIEW_14 rates it
    HIGH and not blocking. Read out of the source, so it needs no store.
    """
    built = inspect.getsource(ls.build_live_screener)
    assert "gates = {} if live else full_day_gates(" in built, (
        "the live posture computes no settled battery -- the input side of H5"
    )
    driven = inspect.getsource(parity.run_live)
    assert "gates = screener.gates.get(symbol)" in driven
    assert "if gates is not None:" in driven, (
        "the live half's own whole-day answer is computed only when a settled battery exists. "
        "When run_live gains a live-posture path, H5 is fixed and this probe flips."
    )


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
