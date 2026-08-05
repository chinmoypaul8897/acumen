"""Probes kept by REVIEW_9B_FIX4 -- the FIX-4 re-review of `6b6baaa..bb2ad60` (Q-22).

Each one exists because this review ran a mutant that the shipped 2,111-test suite did not
catch, or because a claim the span publishes was pinned by prose rather than by a test. Each
was mutation-verified: it fails on its mutant and passes on restoration.

The review fixes nothing. These are tests only -- no `src/` file, no existing test, no fixture
and no evidence artefact was modified by the session that wrote them.

Store-backed probes SKIP when the local minute store is absent (decision B262's precedent).
They do NOT skip on the operator's machine.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import datetime as dt
import inspect
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import minute_backfill as mb
from acumen.aggregate import in_session_bars
from acumen.config import load_config
from acumen.minute_store import MinuteStore
from acumen.smartapi_client import OneMinuteBar


def _store_or_skip() -> tuple[Path, MinuteStore]:
    config = load_config(include_env=False)
    root = config.path("data_root") / "minute_store"
    if not root.is_dir():
        pytest.skip(f"local minute store {root} is absent (data/ is gitignored)")
    return root, MinuteStore(root)


# --- FIX4-P1: B267's filter was pinned by nothing ------------------------------------------


def test_the_third_rule3_loader_drops_out_of_session_stamps_too(tmp_path: Path) -> None:
    """**MUTANT KILLED (REVIEW_9B_FIX4 finding F1).** Decision B267 gives
    `minute_backfill.minute_loader` -- the module the repo's own docstring calls *"the REAL
    implementation of the MinuteLoader interface"* -- the same CONTEXT 7-E2 / Q-17 filter
    `backtest.candles_for` got, because the architect's Q-22(a) ruling binds *"EVERY consumer of
    stored minute bars"*, not every gated one.

    Deleting that filter again -- iterating `bars` instead of `in_session_bars(bars)` -- left the
    whole 2,111-test suite GREEN when this review measured it. That is the R5-class defect
    REVIEW_9B_FIXES found three times over: a load-bearing line that is right and pinned by
    nothing. It cannot move a published number today (no `src/` or `scripts/` caller reaches this
    loader -- verified by grep), which is exactly why nothing noticed; it is also exactly why an
    unpinned consistency fix rots.

    The fixture is the real shape: one pre-open 09:14 print (NSE 2017-04-28, market-wide) and one
    post-close print, around two ordinary session bars."""
    store = MinuteStore.at(tmp_path / "m")
    day = dt.date(2017, 4, 28)

    def at(h: int, m: int) -> dt.datetime:
        return dt.datetime.combine(day, dt.time(h, m))

    store.write_bars(
        "SYNTH",
        [
            OneMinuteBar(at(9, 14), 200000, 200500, 199500, 200000, 25015),  # PRE-OPEN stray
            OneMinuteBar(at(9, 15), 200000, 201000, 199000, 200500, 1000),
            OneMinuteBar(at(15, 29), 200500, 201500, 200000, 201000, 900),
            OneMinuteBar(at(15, 44), 201000, 209000, 191000, 201000, 100),  # POST-CLOSE stray
        ],
    )

    candles = mb.minute_loader(store)("SYNTH", day)

    assert len(candles) == 2, "the two strays must never become bias.Candle objects"
    assert [c.stamp.time() for c in candles] == [dt.time(9, 15), dt.time(15, 29)]
    # ...and the extremes the two strays carry are gone with them, which is the whole point:
    # a first-break scan must not be able to see 191000 or 209000.
    assert min(c.low for c in candles) == 199000
    assert max(c.high for c in candles) == 201500
    # the same bytes through the RUN's own boundary give the same candles (B263's "one boundary")
    run_candles, dropped = bt.candles_for("SYNTH", day, store.minutes("SYNTH", day))
    assert dropped == 2
    assert [(c.open, c.high, c.low, c.close, c.stamp) for c in run_candles] == [
        (c.open, c.high, c.low, c.close, c.stamp) for c in candles
    ]


# --- FIX4-P2: the ORDER of gate-then-filter, on the day it actually decides -----------------


def test_the_battery_is_fed_the_WHOLE_stored_day_and_the_order_is_load_bearing() -> None:
    """**REVIEW_9B_FIX4 finding V1 -- the half of CONTEXT 4.6's Q-17 law that has teeth.**

    Q-17 has two clauses: the stray is dropped at the candle level, AND *"gates still see the
    whole stored day for volume (NSE daily volume includes auctions)"*. `gated_minute_loader`
    hands `gate_day` the UNFILTERED bars and only then calls `candles_for`.

    The shipped test for this (`test_q22_the_gates_still_see_the_whole_stored_day`) asserts the
    INPUTS on a fixture where both readings pass, and says so honestly. On the REAL 2021-02-24
    outage day the two readings do NOT both pass: filtering first makes GODREJCP and LAURUSLABS
    FAIL gate 1 outright (a volume gap above 22%, because the 77 dropped bars carry a fifth of
    the day's traded volume), so the days would be refused as `minutes-ungated` instead of
    re-answered as `rule-3-no-break-carry`. Reversing the order does not merely lose a counter --
    it changes the verdict on the two days the whole Q-22 question was raised about.

    This probe pins the ordering against that consequence."""
    _root, store = _store_or_skip()
    pytest.importorskip("pandas")
    from acumen.daily_store import DailyStore
    from acumen.signal_engine import SignalPipeline

    config = load_config(include_env=False)
    daily = config.path("data_root") / "daily_store"
    if not daily.is_dir():
        pytest.skip(f"local daily store {daily} is absent")
    pipeline = SignalPipeline(
        minute_store=store,
        daily_store=DailyStore(daily),
        master=None,
        row_size=config.row_size,
    )
    day = dt.date(2021, 2, 24)

    for symbol in ("GODREJCP", "LAURUSLABS"):
        bars = store.minutes(symbol, day)
        assert bars, symbol
        session, dropped = in_session_bars(bars)
        assert dropped == 77 and len(session) == 147

        whole = pipeline.gate_day(symbol, day, bars)
        filtered = pipeline.gate_day(symbol, day, session)

        # the order the run uses: the battery PASSES, so the day reaches the scan...
        assert whole.refusal_detail is None, symbol
        # ...and the order it must never use: the battery REFUSES the day on volume
        assert filtered.refusal_detail is not None, symbol
        assert filtered.refusal_detail[0].startswith("gate 1"), filtered.refusal_detail
        # the gates were given every stored share, which is Q-17's own sentence
        assert whole.gate1.minute_volume_sum > filtered.gate1.minute_volume_sum
        # gate 2 COUNTS the strays and does not exclude the day for them (CONTEXT 7-E2)
        assert whole.gate2.out_of_session == dropped and whole.gate2.passed

        # and after all that, the SCAN gets only the session
        drops = bt.Rule3SessionDrops()
        candles = bt.gated_minute_loader(store, pipeline, drops=drops)(symbol, day)
        assert len(candles) == len(session)
        assert drops.dropped(symbol, day) == dropped


# --- FIX4-P3: the flag/label join, asserted rather than tautologically "asserted" -----------


def test_every_unresolved_flag_actually_increments_a_manifest_counter() -> None:
    """**REVIEW_9B_FIX4 finding F2.** `test_r9_every_unusable_evidence_case_is_flagged_and_the_
    gap_fails_LOUDLY` contains

        assert any(flag in label or label for label in bt.RARE_SHAPE_LABELS)

    which is VACUOUS: `label` is a non-empty string, so the disjunction is true for every flag,
    including one that appears in no label at all. The intended claim is also false as written --
    the flag strings are NOT substrings of the labels; they are separate namespaces joined by a
    hardcoded pair list inside `rare_shape_counts`.

    The join is covered behaviourally by REVIEW_9B_FIXES' own kept probe, so this is not a
    coverage hole; it is a dead assertion that reads as coverage. This probe states the property
    the way it has to be stated, and extends it to the flag Q-22(a) added."""
    for rule, flag in bt.UNRESOLVED_FLAG_BY_RULE.items():
        counts = bt.rare_shape_counts([_row_with(flag)])
        assert sum(counts.values()) == 1, f"{rule!r} -> {flag!r} increments no counter"

    # the same property for the flag this span gave a counter to (REVIEW_9B_FIXES R9)
    counts = bt.rare_shape_counts([_row_with(bt.FLAG_OUT_OF_SESSION_DROPPED)])
    assert counts["day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)"] == 1
    assert sum(counts.values()) == 1  # ...and it increments that counter and no other

    # a flag nobody wired increments nothing -- the control that makes the above mean something
    assert sum(bt.rare_shape_counts([_row_with("a flag no label knows about")]).values()) == 0


def _row_with(flag: str) -> bt.LedgerRow:
    return bt.LedgerRow(
        symbol="SYNTH",
        day=dt.date(2020, 1, 1),
        status=bt.STATUS_REFUSED,
        reason="probe",
        flags=(flag,),
    )


# --- FIX4-P4: the Q-22(b) sharing, from the other side --------------------------------------


def test_no_module_outside_backtest_builds_its_own_rule3_candles() -> None:
    """**REVIEW_9B_FIX4.** Q-22(b) was needed because `trade_evidence` kept a private copy of the
    Rule-3 loader and that copy fell behind two rulings. `test_q22_trade_evidence_gating` pins
    that THAT module now shares `backtest.gated_minute_loader`; this pins the general property --
    that `backtest.candles_for` is the only place in `src/` which turns a stored 1-minute bar
    into a `bias.Candle` for a first-break scan, so a third copy cannot appear unnoticed.

    `minute_backfill.minute_loader` is the one other builder and it is exempt BY NAME, because
    B267 records it deliberately (it is the chunk-5A interface implementation, on no production
    path, and it carries the same filter -- pinned by
    `test_the_third_rule3_loader_drops_out_of_session_stamps_too` above)."""
    import acumen

    package = Path(acumen.__file__).parent
    allowed = {"backtest.py", "minute_backfill.py"}
    offenders: list[str] = []
    for path in sorted(package.glob("*.py")):
        if path.name in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        # a Candle(...) built out of `*_paise` fields is a bar becoming a scan candle
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "Candle(" in line and "open_paise" in line:
                offenders.append(f"{path.name}:{line_no}")
    assert offenders == [], (
        "a module outside the two sanctioned builders constructs Rule-3 candles from raw bars; "
        f"it will drift from CONTEXT 4.6's Q-17 drop exactly as trade_evidence did: {offenders}"
    )

    # ...and the two sanctioned ones both filter before they build
    assert "in_session_bars(bars)" in inspect.getsource(bt.candles_for)
    assert "in_session_bars(bars)" in inspect.getsource(mb.minute_loader)
