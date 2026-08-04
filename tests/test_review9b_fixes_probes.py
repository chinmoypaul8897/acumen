"""REVIEW_9B_FIXES kept probes -- the coverage the chunk-9B fix arc left open.

Written by the QC REVIEW session for `20b45c9..a707615` (Q-21, Q-21(b), Q-21(a)). Every
probe here exists because a MUTANT survived the shipped 2,083-test suite: the arc's code is
correct, but several of its load-bearing lines were pinned by nothing, so a later edit could
undo a ruling and leave the suite green. Each test names the mutant it kills.

Nothing here weakens or replaces a shipped test; these are additions. No fixture byte is
touched, and the store-backed probes SKIP when the minute store is absent (the chunk-8
precedent, decision B262).
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import json
import time
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import bias_engine as be
from acumen import run_backtest as rb
from acumen import universe_backfill as ub

# --- 1. the Q-21(b) wiring: build_runner must hand the runner the GATED loader ----------------
#
# MUTANT KILLED: revert `minute_loader=gated_minute_loader(minute_store, pipeline)` in
# build_runner to the bare `minute_loader(minute_store)`. The whole Q-21(b) ruling rests on
# that ONE line -- 210 trade days across 59 symbols ride on it -- and the shipped suite is
# green with it reverted, because every unit test wires the gated loader by hand through
# `make_runner` and nothing exercises what `build_runner` (the function `run_backtest.execute`
# actually calls) builds. Pinned by reading build_runner's own syntax tree, so the probe needs
# no store and cannot itself drift into re-implementing the wiring.


def _build_runner_keywords() -> dict[str, str]:
    """Every ``BacktestRunner(...)`` keyword in build_runner, as source text."""
    tree = ast.parse(inspect.getsource(bt.build_runner))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "BacktestRunner":
            return {kw.arg: ast.unparse(kw.value) for kw in node.keywords if kw.arg}
    raise AssertionError("build_runner no longer constructs a BacktestRunner")


def test_build_runner_wires_the_GATED_minute_loader_not_the_bare_one() -> None:
    """QUESTIONS.md Q-21(b): the battery is a PRECONDITION of the Rule-3 scan on the RUN path.

    `build_runner` is the only place the real run wires it. Decision B251 makes the gated
    loader a separate function precisely so the ungated one cannot be reached by argument --
    but nothing stopped a later edit from calling the bare one here.
    """
    keywords = _build_runner_keywords()
    wiring = keywords["minute_loader"]
    assert wiring.startswith("gated_minute_loader("), (
        "build_runner must wire gated_minute_loader -- the bare minute_loader leaves the RUN's "
        f"Rule-3 scan ungated (QUESTIONS.md Q-21(b)). Found: {wiring}"
    )
    assert "pipeline" in wiring, "the gated loader needs the battery it gates on"


def test_the_bare_minute_loader_survives_but_reaches_no_runner() -> None:
    """B251's other half: the ungated loader is kept for the evidence scripts and the
    bar-naming tests, so it must still EXIST -- but it must not be what any runner is built
    from. If both loaders vanish or the bare one is deleted, the tests that ask about the BAR
    rather than the day lose their subject."""
    assert callable(bt.minute_loader) and callable(bt.gated_minute_loader)
    assert "minute_loader=minute_loader(" not in inspect.getsource(bt.build_runner)


# --- 2. B259: the GATE_DEFINITION marker -------------------------------------------------------
#
# MUTANT KILLED: drop the `+gate2-open-test-2026-08-03` suffix (or revert the bump entirely).
# The suite stays green at 2,083/0, while every stored ledger row silently claims a currency it
# does not have -- which is the exact failure the marker exists to prevent. The only shipped
# assertions on this constant are self-referential (`record.gate_definition == ub.GATE_DEFINITION`)
# or satisfied by the pre-arc value (`"auction-relief" in ...`).


def test_the_gate_definition_marker_carries_the_q21a_open_test() -> None:
    """The Q-21(a) completion moved gate 2, so the marker must move with it (decision B259).

    The marker is what makes a re-gate automatic, bounded and auditable; a moved gate behind a
    stale marker is a ledger that lies about which law measured it.
    """
    assert "gate2-open-test-2026-08-03" in ub.GATE_DEFINITION
    # ...and the earlier clauses are still there: the marker ACCUMULATES, it does not replace.
    for earlier in ("gate1p-price-containment", "gate2-completeness", "auction-relief-2026-07-28"):
        assert earlier in ub.GATE_DEFINITION, earlier


def test_the_gate_definition_marker_is_one_clean_concatenation() -> None:
    """It is written as two adjacent string literals; a missing or doubled `+` at the seam
    would produce a marker that never equals the one a re-gate writes."""
    assert ub.GATE_DEFINITION == (
        "gate1p-price-containment+gate2-completeness+auction-relief-2026-07-28"
        "+gate2-open-test-2026-08-03"
    )
    assert "++" not in ub.GATE_DEFINITION and not ub.GATE_DEFINITION.endswith("+")


# --- 3. B248: the reporter's clock and its honest silence --------------------------------------
#
# MUTANTS KILLED: (a) revert the two `time.perf_counter` defaults to `time.monotonic` -- 233
# targeted tests stay green, while on this box monotonic's 15.625 ms floor (GetTickCount64) is
# what produced six hours of `rate -- | ETA -- (no symbol walked yet)`; every shipped reporter
# test injects a FakeClock and so never exercises the default. (b) revert the `<= 0` branch to
# the old wording -- the branch is never entered by any shipped test.


def test_the_reporter_and_execute_default_to_perf_counter() -> None:
    """Decision B248. The interval-selection half of the FIX-1 fix is pinned hard; this is the
    half that this machine's clock resolution depends on."""
    assert inspect.signature(rb.ProgressReporter.__init__).parameters["clock"].default is (
        time.perf_counter
    )
    assert inspect.signature(rb.execute).parameters["clock"].default is time.perf_counter


def test_the_zero_interval_line_names_WHICH_silence_it_is() -> None:
    """The old line claimed "no symbol walked yet" while the run was a hundred symbols deep,
    which is precisely what hid the bug for six hours. A reporter that has walked symbols but
    measured no time must say so, and must not fabricate a rate or an ETA."""
    lines: list[str] = []
    frozen = 1234.5  # a clock that never advances: every interval is exactly zero
    reporter = rb.ProgressReporter(4, out=lines.append, clock=lambda: frozen)

    reporter("  AAA: 10 walked")
    reporter.after_symbol("AAA")
    reporter("  BBB: 10 walked")
    reporter.after_symbol("BBB")
    reporter("  CCC: 10 walked")
    reporter.after_symbol("CCC")

    line = lines[-1]
    assert "no symbol walked yet" not in line, "symbols HAVE been walked -- say so"
    # The line is printed BEFORE `after_symbol` confirms the symbol just reported, so the
    # count it quotes is the confirmed one: two walked by the time CCC is announced.
    assert "2 walked, none took a measurable interval yet" in line
    assert "rate --" in line and "ETA --" in line  # no fabricated number
    assert "s/symbol" not in line


def test_the_reporter_still_says_nothing_walked_when_nothing_was() -> None:
    """The control for the test above: the OTHER silence must keep its own words."""
    lines: list[str] = []
    reporter = rb.ProgressReporter(4, out=lines.append, clock=lambda: 0.0)
    reporter("  AAA: resumed from shard (AAA.jsonl)")
    assert "no symbol walked yet" in lines[-1]


# --- 4. the refusal machinery cannot reach the ledger unflagged --------------------------------


def _refused_row(flag: str | None) -> bt.LedgerRow:
    """One refused ledger row carrying ``flag`` (or none), as `walk_symbol` would emit it."""
    return bt.LedgerRow(
        symbol="AAA",
        day=dt.date(2023, 3, 6),
        status=bt.STATUS_REFUSED,
        reason=bt.REASON_BIAS_UNRESOLVED,
        flags=() if flag is None else (flag,),
    )


def test_every_unusable_evidence_rule_has_a_flag_and_that_flag_is_a_rare_shape() -> None:
    """B252's guard, restated as a property over the RULES rather than the subclasses, so a
    case whose module the tripwire never imports is still caught if it reaches the map.

    `walk_symbol` does `flags=(UNRESOLVED_FLAG_BY_RULE[bias.rule],)` -- an UNGUARDED lookup.
    A rule without an entry would raise KeyError out of the walk and kill the full-history run,
    which is the exact outcome the Q-21 ruling ("counted, never a crash") forbids.
    """
    for rule in (be.RULE_MINUTES_MALFORMED, be.RULE_MINUTES_UNGATED):
        assert rule in bt.UNRESOLVED_FLAG_BY_RULE, rule
    assert bt.UNRESOLVED_FLAG_BY_RULE[be.RULE_MINUTES_MALFORMED] == bt.FLAG_MALFORMED_MINUTE_BAR
    assert bt.UNRESOLVED_FLAG_BY_RULE[be.RULE_MINUTES_UNGATED] == bt.FLAG_UNGATED_MINUTE_DAY

    # ...and every flag the map can put on a row is one the manifest actually TOTALS. The flag
    # strings and the rare-shape labels are separate namespaces joined by a hardcoded pair list
    # inside `rare_shape_counts`, so this is asserted BEHAVIOURALLY -- a flag added to the map
    # but forgotten in that list would leave a refusal counted nowhere.
    for rule, flag in bt.UNRESOLVED_FLAG_BY_RULE.items():
        counts = bt.rare_shape_counts([_refused_row(flag)])
        assert sum(counts.values()) == 1, (
            f"{rule!r} carries flag {flag!r}, which increments no manifest counter"
        )


def test_both_q21_rare_shapes_are_counted_from_the_row_flags() -> None:
    """MUTANT KILLED: suppress the flag on a minutes-malformed refusal (the day is still
    refused and its reason is still right, but the manifest reports ZERO). After FIX-3 flipped
    the only behavioural test of that counter to assert 0, nothing pinned the live direction.

    Counts are DERIVED from committed rows (decision B245), which is what keeps a resumed run
    identical to a fresh one -- so the derivation is where the property can be pinned without
    a store.
    """
    malformed = "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)"
    ungated = "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))"

    counts = bt.rare_shape_counts(
        [
            _refused_row(bt.FLAG_MALFORMED_MINUTE_BAR),
            _refused_row(bt.FLAG_UNGATED_MINUTE_DAY),
            _refused_row(None),
        ]
    )
    assert counts[malformed] == 1, "a malformed-bar refusal must reach the manifest"
    assert counts[ungated] == 1
    assert set(counts) == set(bt.RARE_SHAPE_LABELS)  # every shape reported, even at zero
    assert sum(counts.values()) == 2  # the unflagged row counts nowhere


# --- 5. store-backed: the findings this review raises to the architect --------------------------

DATA = Path("C:/Users/chinm/acumen-data")
MINUTE = DATA / "minute_store" / "minute"
LEDGER = DATA / "universe_backfill" / "ledger.json"

store_backed = pytest.mark.skipif(
    not MINUTE.is_dir() or not LEDGER.is_file(),
    reason="needs the real minute store (READ-ONLY; chunk-8 precedent, decision B262)",
)


@store_backed
def test_the_quarantined_side_carries_THREE_malformed_bars_not_two() -> None:
    """A correction to the FIX-3 correction (REVIEW_9B_FIXES finding R7).

    QUESTIONS.md corrects CONTEXT v1.6's "48-bar population" to 50 over the 210 processed
    symbols. That 50 is derived from the FLIP list -- days that change verdict under the
    completed enumeration -- which structurally cannot see a day the SEALED gate 2 already
    refused. APLAPOLLO 2017-10-05 15:28 is exactly such a day (close BELOW the low, one of
    CONTEXT 4.5's original two clauses), so the whole-lake population is 51.

    Nothing costs anything: the bar is on a quarantined symbol, outside the run's universe and
    outside the coverage numerator, and its day was refused before v1.6 and after it.
    """
    pd = pytest.importorskip("pandas")
    statuses = {
        sym.upper(): (row.get("status") or "").lower()
        for sym, row in json.loads(LEDGER.read_text(encoding="utf-8"))["symbols"].items()
    }
    quarantined = sorted(sym for sym, st in statuses.items() if st != "settled")
    assert len(quarantined) == 6, quarantined  # CONTEXT 4.6 names six

    columns = ["stamp", "open_paise", "high_paise", "low_paise", "close_paise"]
    found = []
    for symbol in quarantined:
        for path in sorted((MINUTE / symbol).glob(f"{symbol}_*.parquet")):
            frame = pd.read_parquet(path, columns=columns)
            bad = frame[
                (frame.high_paise < frame.low_paise)
                | (frame.open_paise < frame.low_paise)
                | (frame.open_paise > frame.high_paise)
                | (frame.close_paise < frame.low_paise)
                | (frame.close_paise > frame.high_paise)
            ]
            found.extend((symbol, row) for row in bad.itertuples(index=False))

    assert len(found) == 3, [(s, str(r.stamp)) for s, r in found]
    stamps = sorted(f"{s} {r.stamp}" for s, r in found)
    assert stamps == [
        "APLAPOLLO 2017-10-05 15:28:00",
        "APLAPOLLO 2023-03-03 09:15:00",
        "UPL 2023-03-03 09:15:00",
    ]
    missed = next(r for s, r in found if str(r.stamp).startswith("2017-10-05"))
    assert missed.close_paise < missed.low_paise  # a SEALED clause -- already refused pre-v1.6
    assert missed.low_paise <= missed.open_paise <= missed.high_paise  # its open is fine


@store_backed
def test_the_rule3_scan_DROPS_out_of_session_bars_on_the_real_outage_day() -> None:
    """FINDING R1 -- **FLIPPED by the chunk-9B FIX-4 session, exactly as this probe promised.**

    As written by the review this test asserted the DEFECT and said so: *"it will go RED the day
    the architect rules and the scan starts dropping stray candles -- which is the point: it is
    a tripwire on an open question (QUESTIONS.md Q-22), not a blessing of the behaviour."* The
    architect ruled option (a) on 03-Aug-2026: *"Q-17's candle-level drop binds EVERY consumer of
    stored minute bars, the Rule-3 first-break scan included."* So the probe now asserts the RULE
    on the same two real symbols, on the same real day, through the RUN's own loader.

    On 2021-02-24 -- the NSE outage day, whose session ran past 15:29, and which is NOT one of
    the eight CONTEXT 7-E2 non-standard sessions the run removes from its calendar -- a bar
    stamped 15:44 breaks P's low on GODREJCP and LAURUSLABS, both SETTLED, and it was the ONLY
    thing that broke either extreme. Fed every stored bar the scan answered `rule-3-outside-bar`
    -> bearish off that print; fed the session it finds no break and CARRIES, which is CONTEXT
    3.2's own answer for a Rule-3 day whose minutes break nothing.

    **What this probe does NOT assert, because it is not true:** that the resulting BIAS moves.
    The review's table read the carry as BULLISH because its probe passed the literal string to
    `evaluate_pair` instead of walking the carry; walked from the span's start the bias carried
    into 2021-02-25 is already bearish on both symbols, so the two answers coincide. Measured in
    full over all 204 settled symbols in `docs/evidence/chunk9b_q22_session_filter.md`.
    """
    pytest.importorskip("pandas")
    from acumen.bias import Candle, evaluate_pair
    from acumen.daily_store import DailyStore
    from acumen.minute_store import MinuteStore
    from acumen.signal_engine import SignalPipeline

    minute_store = MinuteStore(DATA / "minute_store")
    daily_store = DailyStore(DATA / "daily_store")
    pipeline = SignalPipeline(minute_store, daily_store, None, 24)
    d1, d2 = dt.date(2021, 2, 24), dt.date(2021, 2, 23)

    for symbol in ("GODREJCP", "LAURUSLABS"):
        bars = minute_store.minutes(symbol, d1)
        assert bars, symbol
        stray = [
            b for b in bars if not (dt.time(9, 15) <= b.stamp.time() <= dt.time(15, 29))
        ]
        assert stray, f"{symbol} 2021-02-24 should carry post-close bars"

        # the battery PASSES, so Q-21(b) does not refuse the day: the strays really would be read
        assert pipeline.gate_day(symbol, d1, bars).refusal_detail is None

        # THE RULING, at the boundary: the run's own loader drops them and counts them.
        candles, dropped = bt.candles_for(symbol, d1, bars)
        assert dropped == len(stray) > 0
        assert len(candles) == len(bars) - dropped
        assert all(dt.time(9, 15) <= c.stamp.time() <= dt.time(15, 29) for c in candles)
        assert bt.gated_minute_loader(minute_store, pipeline)(symbol, d1) == candles

        previous = daily_store.daily(symbol, d2, d2).iloc[0]
        current = daily_store.daily(symbol, d1, d1).iloc[0]
        pair = [
            Candle(
                open=int(row.open_paise),
                high=int(row.high_paise),
                low=int(row.low_paise),
                close=int(row.close_paise),
                day=day,
            )
            for row, day in ((previous, d2), (current, d1))
        ]
        every_bar = tuple(
            Candle(
                open=int(b.open_paise), high=int(b.high_paise), low=int(b.low_paise),
                close=int(b.close_paise), stamp=b.stamp, day=d1,
            )
            for b in bars
        )

        as_shipped = evaluate_pair(*pair, lambda: every_bar, "bearish")
        as_ruled = evaluate_pair(*pair, lambda: candles, "bearish")

        assert as_shipped.rule == "rule-3-outside-bar" and as_shipped.bias == "bearish"
        assert as_ruled.rule == "rule-3-no-break-carry", (
            f"{symbol}: with the strays dropped nothing may break either extreme (Q-22(a))"
        )
        assert as_ruled.bias == "bearish"  # the CARRY, which on this day is the same answer
