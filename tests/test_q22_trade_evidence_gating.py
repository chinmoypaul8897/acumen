"""QUESTIONS.md Q-22(b): the Q-21(b) battery precondition reaches chunk-8's `trade_evidence`.

The architect, 03-Aug-2026: *"the Q-21(b) battery precondition binds trade_evidence too --
B255's caution was procedurally right and this is the ruling it waited for; FIX-2's measurement
(zero refusals in the pilot window) must be ASSERTED when gating it."*

That last clause is what this file is. Gating a REVIEWED chunk's generator can only be safe if
the window it generates over contains no day the gate refuses -- otherwise a published number
moves with no ruling behind it. FIX-2 measured that ("no refusal falls inside the pilot
window", `docs/evidence/chunk9b_q21b_blast_radius.md` section 5) and this session is required to
assert it rather than cite it. Three things are pinned:

1. **the SHARING** -- `trade_evidence` wires `backtest.gated_minute_loader` itself, not a copy.
   A private near-duplicate is how two consumers of one law drift apart (the Q-14 lesson), and
   the copy this replaced had already fallen behind twice: it neither gated the day (Q-21(b))
   nor dropped an out-of-session stamp (Q-22(a));
2. **the PRECONDITION** -- every Rule-3 scan the committed sweep window performs reads a D-1
   that PASSES the CONTEXT 4.5/4.6 battery, so the gate refuses nothing there;
3. **the ARTEFACT** -- the committed pack's own counts and money totals, re-derived through the
   now-gated path, are unchanged to the paisa.

Store-backed and READ-ONLY; they SKIP when the minute store is absent, the precedent chunk 8 set
for store-backed probes (decision B262). Nothing here writes to any store, and nothing here
regenerates the committed pack.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import trade_evidence as evidence
from acumen.bias_engine import RULE_MINUTES_MALFORMED, RULE_MINUTES_UNGATED
from acumen.config import load_config

#: The committed pack's headline figures (docs/evidence/chunk8_sweep.md), which REVIEW_8
#: re-derived independently and three later reviews quote. They are typed here as the pin they
#: are: if the gating moved one, this file fails rather than the pack quietly changing.
PACK_WALKED = 290
PACK_ENTERED = 146
PACK_EXECUTED = 146
PACK_SHARES = 53_750
PACK_GROSS_PAISE = 1_266_505
PACK_COST_PAISE = 1_460_000
PACK_NET_PAISE = -193_495


def _stores_or_skip() -> None:
    config = load_config(include_env=False)
    for relpath in ("minute_store", "daily_store"):
        store_dir = config.path("data_root") / relpath
        if not store_dir.is_dir():
            pytest.skip(f"local {relpath} {store_dir} is absent (data/ is gitignored)")
    master = config.instrument_master_path()
    if not Path(master).is_file():
        pytest.skip(f"pinned instrument master {master} is absent")


def test_trade_evidence_uses_the_RUNS_OWN_gated_loader_and_not_a_copy() -> None:
    """Q-22(b), pinned by reading the source rather than by running it: the object handed to the
    `BiasEngine` must be `backtest.gated_minute_loader` itself.

    Reverting it to a private loader is the mutant -- the whole ruling rests on this one line,
    exactly as the Q-21(b) ruling rested on `build_runner`'s (REVIEW_9B_FIXES R2)."""
    source = inspect.getsource(evidence.build_context)

    assert "bt.gated_minute_loader(minute_store, pipeline)" in source
    assert not hasattr(evidence, "_minute_loader"), (
        "the private near-duplicate must be GONE, not merely unused: a second loader is what "
        "let this module fall behind two rulings (Q-21(b), Q-22(a))"
    )
    # ...and the module reaches the run's own function, not a re-exported lookalike
    assert evidence.bt.gated_minute_loader is bt.gated_minute_loader


def test_the_gated_sweep_window_contains_ZERO_battery_refusals() -> None:
    """**The architect's condition, asserted.** Gating a reviewed chunk's generator is only safe
    because no Rule-3 scan in its window asks for a battery-failing D-1. FIX-2 measured that;
    this asserts it, over the committed window, through the shipped path.

    A refusal here would not be a test failure to paper over -- it would mean the committed pack
    is stale and needs an architect's ruling, so the message says so."""
    _stores_or_skip()
    context = evidence.build_context()

    refused = []
    for symbol in evidence.SWEEP_SYMBOLS:
        for bias in context.bias_engine.bias_series(
            symbol, evidence.SWEEP_START, evidence.SWEEP_END
        ):
            if bias.rule in (RULE_MINUTES_UNGATED, RULE_MINUTES_MALFORMED):
                refused.append((symbol, bias.trade_date, bias.rule, bias.unresolved_detail))

    assert refused == [], (
        "a day of the committed chunk-8 window is now refused by the battery, so the pack's "
        f"published figures would move: {refused}"
    )


def test_the_committed_pack_figures_survive_the_gating_to_the_paisa() -> None:
    """The artefact itself, re-derived through the gated path. REVIEW_8 verified these numbers
    independently and three reviews quote them; B255 declined to gate this module precisely so
    they could not move without a ruling. The ruling has arrived, and this is the proof it costs
    the pack nothing."""
    _stores_or_skip()
    context = evidence.build_context()

    result = evidence.run_sweep(context)
    totals = evidence.money_totals(result)
    partition = evidence.outcome_counts(result)

    assert len(result.days) == PACK_WALKED
    assert len(result.entered) == PACK_ENTERED
    assert len(result.executed) == PACK_EXECUTED
    assert totals["shares"] == PACK_SHARES
    assert totals["gross_paise"] == PACK_GROSS_PAISE
    assert totals["cost_paise"] == PACK_COST_PAISE
    assert totals["net_paise"] == PACK_NET_PAISE
    # the chunk-7 partition the pack is line-comparable to: 146 entered / 88 / 56
    assert sum(partition.values()) == PACK_WALKED
    assert evidence.invariant_report(result)
    assert all("FAIL" not in line for line in evidence.invariant_report(result))
