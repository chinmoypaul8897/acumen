"""The chunk-9B run layer: the preflight gate, the universe/span measurement, the E2 scan
cache, the ETA reporter and the manifest disclosures.

What this file attacks is everything that decides WHAT the full-history run walks and whether
it is allowed to start at all. The engines under it are reviewed (chunks 4, 6, 7, 8) and the
runner itself is reviewed (chunk 9A); the risk here is different in kind:

* a universe or a span that is TYPED rather than MEASURED would silently freeze a fact about
  the stores into the code -- so both are read from the register and from the parquet files,
  and the tests build stores whose answers a reader can count;
* a preflight that PASSES on a broken input is worse than no preflight, because the run then
  produces a ledger nobody can qualify -- so every check has a test that makes it FAIL, and a
  failing preflight must not emit the run command;
* the CONTEXT 7-E2 scan cache must never serve a scan built for a different universe, span or
  code state -- three separate mismatches, three tests;
* the manifest disclosures must reach the run's manifest and NOTHING else: a chunk-9A artefact
  whose manifest gained a key would move its published digest, so that is asserted directly.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import os
from dataclasses import fields, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import run_backtest as rb
from acumen.config import ConfigError, load_config
from acumen.minute_store import MinuteStore

from tests.test_backtest import (
    LEAD_A,
    SEED_A,
    SYMBOL,
    TRADE_DAY,
    Minute,
    at,
    build_stores,
    daily_row,
    make_runner,
    row_for_minutes,
    synthetic_minutes,
    R,
)

CODE_SHA = "0" * 40


# ==============================================================================================
# The universe: measured from the disclosed-residual register, never typed
# ==============================================================================================


def register(**statuses: str) -> dict[str, bt.ResidualEntry]:
    return {
        symbol: bt.ResidualEntry(symbol, status, 100, 100, 0, "")
        for symbol, status in statuses.items()
    }


def test_the_universe_is_the_settled_symbols_alphabetical() -> None:
    """CONTEXT 4.6: 204 settled, 6 quarantined. A quarantined symbol has no usable minute era,
    so it is not a symbol the run can walk -- and the order is the register's, sorted, so two
    runs over the same register produce the same spec digest."""
    found = rb.settled_symbols(
        register(ZEE="settled", ASTRAL="quarantined", ABB="settled", IEX="quarantined")
    )
    assert found == ("ABB", "ZEE")


def test_an_empty_register_yields_an_empty_universe_rather_than_a_guess() -> None:
    assert rb.settled_symbols({}) == ()


# ==============================================================================================
# The span: measured from the minute store's own parquet files
# ==============================================================================================


def minute_store_with(tmp_path: Path, days: dict[str, list[date]]) -> MinuteStore:
    """A minute store carrying ONE bar per named day per symbol -- enough to date the era."""
    store = MinuteStore.at(tmp_path / "minute_store")
    for symbol, dates in days.items():
        for day in dates:
            store.write_bars(
                symbol,
                [Minute(at(time(9, 15), day), R(100), R(100), R(100), R(100), 1)],
            )
    return store


def test_a_symbols_era_is_its_first_and_last_stored_day(tmp_path: Path) -> None:
    store = minute_store_with(
        tmp_path, {"AAA": [date(2016, 10, 3), date(2019, 5, 6), date(2026, 7, 24)]}
    )
    assert rb.symbol_era(store, "AAA") == (date(2016, 10, 3), date(2026, 7, 24))


def test_a_symbol_with_no_stored_candles_has_no_era(tmp_path: Path) -> None:
    store = minute_store_with(tmp_path, {"AAA": [date(2020, 1, 2)]})
    assert rb.symbol_era(store, "BBB") is None


def test_the_era_spans_the_whole_universe_not_one_symbol(tmp_path: Path) -> None:
    """The run's span is the union: the earliest first day of any symbol and the latest last
    day of any symbol. A later listing must not shorten the era for everyone else."""
    store = minute_store_with(
        tmp_path,
        {
            "OLD": [date(2016, 10, 3), date(2024, 1, 2)],
            "NEW": [date(2019, 3, 1), date(2026, 7, 24)],
        },
    )
    first, last, counted = rb.era_span(store, ("OLD", "NEW"))
    assert (first, last, counted) == (date(2016, 10, 3), date(2026, 7, 24), 2)


def test_a_symbol_without_candles_is_counted_out_of_the_era_measurement(tmp_path: Path) -> None:
    """`with_data` is what preflight compares against the universe size: a settled symbol with
    no stored candles must show up as a MISSING symbol, not silently narrow the span."""
    store = minute_store_with(tmp_path, {"AAA": [date(2020, 1, 2)]})
    first, last, counted = rb.era_span(store, ("AAA", "GHOST"))
    assert (first, last, counted) == (date(2020, 1, 2), date(2020, 1, 2), 1)


def test_the_era_of_an_empty_store_is_nothing_rather_than_today(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "minute_store")
    assert rb.era_span(store, ("AAA",)) == (None, None, 0)


def test_the_clamp_note_names_only_the_weekday_sessions() -> None:
    """The clamp note tells the operator which SESSIONS the daily oracle cannot qualify. A
    Saturday is not a session, so naming it would overstate what is missing."""
    # 2026-07-24 is a Friday; 25/26 are the weekend; 27 and 28 are Monday and Tuesday.
    beyond = rb._trading_days_between(None, date(2026, 7, 24), date(2026, 7, 28))
    assert beyond == (date(2026, 7, 27), date(2026, 7, 28))


# ==============================================================================================
# The CONTEXT 7-E2 scan cache (decision B181): reuse it, but never the wrong one
# ==============================================================================================


SCAN_ARGS = (("AAA", "BBB"), date(2016, 10, 3), date(2026, 7, 24), CODE_SHA)


def test_a_saved_scan_comes_back_for_exactly_the_same_run(tmp_path: Path) -> None:
    days = frozenset({date(2024, 11, 1), date(2020, 11, 14)})
    rb.save_session_scan(tmp_path, *SCAN_ARGS, days)
    assert rb.load_session_scan(tmp_path, *SCAN_ARGS) == days


def test_an_empty_scan_round_trips_as_an_empty_set_not_as_a_miss(tmp_path: Path) -> None:
    """"No non-standard sessions in this span" is a RESULT. Returning None for it would make
    every resume re-scan the universe -- the exact cost B181 exists to avoid."""
    rb.save_session_scan(tmp_path, *SCAN_ARGS, frozenset())
    assert rb.load_session_scan(tmp_path, *SCAN_ARGS) == frozenset()


@pytest.mark.parametrize(
    "changed",
    [
        (("AAA",), date(2016, 10, 3), date(2026, 7, 24), CODE_SHA),          # universe
        (("AAA", "BBB"), date(2016, 10, 4), date(2026, 7, 24), CODE_SHA),    # start
        (("AAA", "BBB"), date(2016, 10, 3), date(2026, 7, 23), CODE_SHA),    # end
        (("AAA", "BBB"), date(2016, 10, 3), date(2026, 7, 24), "f" * 40),    # code state
    ],
)
def test_a_scan_built_for_a_different_run_is_ignored(tmp_path: Path, changed) -> None:
    """The scan is a function of the universe, the span and the E2 predicate. Serving one built
    for a different set would silently exclude (or admit) trading days for the whole run."""
    rb.save_session_scan(tmp_path, *SCAN_ARGS, frozenset({date(2024, 11, 1)}))
    assert rb.load_session_scan(tmp_path, *changed) is None


def test_a_missing_or_damaged_scan_cache_is_a_miss_not_a_crash(tmp_path: Path) -> None:
    assert rb.load_session_scan(tmp_path, *SCAN_ARGS) is None
    (tmp_path / bt.SESSIONS_NAME).write_text("{not json", encoding="utf-8")
    assert rb.load_session_scan(tmp_path, *SCAN_ARGS) is None


def test_the_scan_cache_carries_no_clock_read(tmp_path: Path) -> None:
    """Like the ledger and the manifest, it must be a pure function of the run -- otherwise a
    resumed run's artefacts stop being byte-identical (chunk-9A decision B179)."""
    rb.save_session_scan(tmp_path, *SCAN_ARGS, frozenset({date(2024, 11, 1)}))
    payload = json.loads((tmp_path / bt.SESSIONS_NAME).read_text(encoding="utf-8"))
    assert set(payload) == {"key", "symbols", "start", "end", "code_sha", "non_standard"}
    assert payload["non_standard"] == ["2024-11-01"]


def test_a_supplied_scan_replaces_the_store_walk(tmp_path: Path, monkeypatch) -> None:
    """`build_runner` must USE a scan it is handed and not re-run one. The scan is O(symbols x
    span days) reads of the minute store -- the same order as the walk itself -- so a resume
    that re-scanned would pay for the whole universe before writing its first new row."""
    calls: list[int] = []

    def explode(*args, **kwargs):  # pragma: no cover -- the point is that it is NOT called
        calls.append(1)
        raise AssertionError("build_runner re-scanned despite being handed a scan")

    monkeypatch.setattr(bt, "scan_non_standard_sessions", explode)
    runner = make_runner(tmp_path)
    supplied = frozenset({TRADE_DAY})
    rebuilt = replace(runner, non_standard_sessions=supplied)
    assert rebuilt.non_standard_sessions == supplied
    assert calls == []


# ==============================================================================================
# The manifest disclosures: on the RUN's manifest, and on nothing else
# ==============================================================================================


def test_a_run_with_no_disclosures_writes_a_manifest_without_the_key(tmp_path: Path) -> None:
    """**This is the guard on every chunk-9A artefact.** The pilot pack publishes manifest
    digests; if `disclosures` appeared unconditionally, every one of them would move and the
    committed pack could no longer regenerate byte-identically (REVIEW_8 finding C2)."""
    runner = make_runner(tmp_path)
    manifest = runner.build_manifest(runner.walk_symbol(SYMBOL).rows, {SYMBOL: {}})
    assert "disclosures" not in manifest


def test_the_disclosures_reach_the_manifest_verbatim_and_in_order(tmp_path: Path) -> None:
    """The architect's GO ruling (31-Jul-2026) stamps two sentences on the run manifest. They
    are carried VERBATIM -- a paraphrased disclosure is not the disclosure that was ruled."""
    stamped = replace(
        make_runner(tmp_path),
        disclosures=(bt.CAPITAL_FLAGS_PENDING_NOTE, rb.Q44_PENDING_STAMP, rb.Q44_ESCALATION),
    )
    manifest = stamped.build_manifest(stamped.walk_symbol(SYMBOL).rows, {SYMBOL: {}})
    assert manifest["disclosures"] == [
        "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending",
        "PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)",
        rb.Q44_ESCALATION,
    ]
    # ...and the Q43 half is ALSO where it always was, so neither reading of "every report
    # output carries it" depends on the other
    assert manifest["capital_flags"]["computed"] is False
    assert manifest["capital_flags"]["note"] == bt.CAPITAL_FLAGS_PENDING_NOTE


def test_the_q44_stamp_is_the_rulings_own_sentence() -> None:
    """Pinned as a literal so a later edit cannot soften it into something the architect did
    not write, and so the escalation travels with it."""
    assert rb.Q44_PENDING_STAMP == "PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)"
    assert "spec version bump" in rb.Q44_ESCALATION
    assert "retained and labelled, never deleted" in rb.Q44_ESCALATION


def test_the_disclosures_do_not_change_what_the_run_walked(tmp_path: Path) -> None:
    """A disclosure is a label on the manifest. It must not touch a row, a count or a total."""
    plain = make_runner(tmp_path)
    stamped = replace(plain, disclosures=("anything at all",))
    rows = plain.walk_symbol(SYMBOL).rows
    bare = plain.build_manifest(rows, {SYMBOL: {}})
    marked = stamped.build_manifest(stamped.walk_symbol(SYMBOL).rows, {SYMBOL: {}})
    assert {k: v for k, v in marked.items() if k != "disclosures"} == bare


# ==============================================================================================
# The progress reporter: honest ETA, from the work that is actually work
# ==============================================================================================


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> float:
        self.t += seconds
        return self.t


def test_the_reporter_counts_every_symbol_and_prints_an_eta_line() -> None:
    """The runner WALKS first and REPORTS afterwards, so a symbol's cost is the interval that
    ENDS at its progress call. The clock is advanced BEFORE each call here, which is where a
    real run spends it; the previous version of this test advanced it BETWEEN the progress call
    and `after_symbol` -- a window the runner spends two print statements in -- and so it
    passed while production printed "rate --" for six hours (fixed 03-Aug-2026).
    """
    lines: list[str] = []
    clock = FakeClock()
    reporter = rb.ProgressReporter(
        4, out=lines.append, clock=clock, now=lambda: datetime(2026, 7, 31, 12, 0)
    )
    clock.advance(100)                # AAA is walked...
    reporter("  AAA: 10 walked")      # ...and only then reported
    reporter.after_symbol("AAA")
    clock.advance(100)
    reporter("  BBB: 10 walked")
    reporter.after_symbol("BBB")

    assert lines[0] == "  AAA: 10 walked"
    assert "[1/4]  25.0%" in lines[1]
    assert "ETA -- (no symbol walked yet)" in lines[1]  # nothing CONFIRMED walked yet: say so
    assert "[2/4]  50.0%" in lines[3]
    assert "100.0s/symbol" in lines[3]
    assert "ETA 0:03:20" in lines[3]  # 2 symbols left x 100s
    assert "(~2026-07-31 12:03)" in lines[3]


def test_the_rate_feeds_after_n_fresh_symbols() -> None:
    """The regression the operator hit: 101 of 204 symbols freshly walked, six hours in, and the
    line still read `rate -- | ETA -- (no symbol walked yet)`. Fresh walks must produce a rate
    AND an ETA, and the arithmetic must be the walking, not the elapsed wall clock."""
    lines: list[str] = []
    clock = FakeClock()
    reporter = rb.ProgressReporter(
        204, out=lines.append, clock=clock, now=lambda: datetime(2026, 8, 3, 6, 0)
    )
    for index in range(1, 102):  # 101 fresh symbols at 95 seconds each
        clock.advance(95)
        reporter(f"  SYM{index}: 2,428 walked")
        reporter.after_symbol(f"SYM{index}")

    line = lines[-1]
    assert "[101/204]" in line
    assert "no symbol walked yet" not in line
    assert "95.0s/symbol" in line
    assert "ETA 2:43:05" in line  # 103 symbols left x 95s = 9,785s
    assert "(~2026-08-03 08:43)" in line  # the stub now() + the remaining 2:43:05


def test_a_resumed_shard_does_not_flatter_the_eta() -> None:
    """A resumed symbol costs nothing and `after_symbol` does not fire for it. If the rate came
    from the progress calls, a run resuming 200 finished symbols would report an ETA of
    seconds for the 4 that are left."""
    lines: list[str] = []
    clock = FakeClock()
    reporter = rb.ProgressReporter(4, out=lines.append, clock=clock)

    reporter("  AAA: resumed from shard (AAA.jsonl)")   # free
    reporter("  BBB: resumed from shard (BBB.jsonl)")   # free
    clock.advance(60)
    reporter("  CCC: 10 walked")                        # ...only these two are really walked
    reporter.after_symbol("CCC")
    clock.advance(60)
    reporter("  DDD: 10 walked")
    reporter.after_symbol("DDD")

    assert reporter.seen == 4 and reporter.walked == 2
    assert "60.0s/symbol" in lines[-1]   # 120s over TWO walks...
    assert "30.0s/symbol" not in lines[-1]  # ...not 120s spread over four symbols
    assert "ETA 0:00:00" in lines[-1]    # nothing left after DDD


def test_a_resumed_shards_free_interval_is_discarded_not_carried() -> None:
    """The interval before a RESUMED symbol's line must not survive to be charged to the next
    walked one. Here the run stalls 500s before replaying a finished shard; that stall belongs
    to nobody, and the one real walk that follows must still measure 60 seconds."""
    lines: list[str] = []
    clock = FakeClock()
    reporter = rb.ProgressReporter(3, out=lines.append, clock=clock)

    clock.advance(500)
    reporter("  AAA: resumed from shard (AAA.jsonl)")   # no after_symbol: never charged
    clock.advance(60)
    reporter("  BBB: 10 walked")
    reporter.after_symbol("BBB")
    clock.advance(60)
    reporter("  CCC: 10 walked")
    reporter.after_symbol("CCC")

    assert reporter.walked == 2
    assert "60.0s/symbol" in lines[-1]


def test_the_reporter_measures_the_runners_real_call_order(tmp_path: Path) -> None:
    """The defect was never in the arithmetic -- it was in WHICH interval was measured -- so the
    regression test drives the REAL runner rather than a hand-written imitation of it:
    walk_symbol -> shard -> progress -> after_symbol. The fake clock is advanced inside
    `walk_symbol`, the only place a real run spends its time."""
    clock = FakeClock()
    runner = make_runner(tmp_path, symbols=(SYMBOL, "OTHER"))
    walk = runner.walk_symbol

    def slow(symbol: str):
        clock.advance(95)
        return walk(symbol)

    object.__setattr__(runner, "walk_symbol", slow)  # BacktestRunner is a frozen dataclass

    lines: list[str] = []
    reporter = rb.ProgressReporter(2, out=lines.append, clock=clock)
    runner.run(tmp_path / "run", progress=reporter, after_symbol=reporter.after_symbol)

    assert reporter.seen == 2 and reporter.walked == 2
    assert "[2/2]" in lines[-1]
    assert "95.0s/symbol" in lines[-1]  # the walk -- not the two print statements after it


def test_the_reporter_never_reports_a_negative_remaining() -> None:
    lines: list[str] = []
    clock = FakeClock()
    reporter = rb.ProgressReporter(1, out=lines.append, clock=clock)
    clock.advance(10)
    reporter("  AAA: 10 walked")
    reporter.after_symbol("AAA")
    clock.advance(10)
    reporter("  BBB: an extra symbol nobody expected")
    assert "ETA 0:00:00" in lines[-1]


@pytest.mark.parametrize(
    "seconds,text",
    [(0, "0:00:00"), (59.4, "0:00:59"), (60, "0:01:00"), (3661, "1:01:01"), (-5, "0:00:00")],
)
def test_elapsed_is_printed_as_hours_minutes_seconds(seconds, text) -> None:
    assert rb._hms(seconds) == text


# ==============================================================================================
# The run command: one place, so it cannot drift from what the operator is told
# ==============================================================================================


def test_the_default_run_command_is_the_bare_clone_path() -> None:
    """`python scripts/run_backtest.py` and not `-m`: the launcher works with no install step
    (chunk-0 B2), which is what every other operator command in this repo uses."""
    assert rb.run_command(rb.DEFAULT_LABEL) == "python scripts/run_backtest.py"


def test_a_subset_or_a_label_is_spelled_into_the_command() -> None:
    assert rb.run_command("chunk9b_smoke", ("RELIANCE", "MARUTI")) == (
        "python scripts/run_backtest.py --label chunk9b_smoke --symbols RELIANCE,MARUTI"
    )


# ==============================================================================================
# The preflight: it must PASS on a good world and REFUSE on every broken one
# ==============================================================================================


def preflight_world(tmp_path: Path, **kwargs) -> Path:
    """A miniature but REAL data directory: both stores, the register and the master.

    The daily ledger reaches back past ``CALENDAR_LEAD_DAYS`` before the span, because that is
    what the real one does and what CONTEXT 3.2's D-1/D-2 pair needs -- the calendar REFUSES to
    derive over dates the bhavcopy ledger never attempted (QUESTIONS.md Q-3 safeguard 1).
    """
    data = tmp_path / "data"
    minutes = synthetic_minutes(TRADE_DAY)
    rows = {
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_A + timedelta(days=1): daily_row(
            SEED_A + timedelta(days=1), R(1995), R(2010), R(1990), R(2008), 1000
        ),
        TRADE_DAY: row_for_minutes(TRADE_DAY, minutes),
        LEAD_A: daily_row(LEAD_A, R(1980), R(1990), R(1970), R(1985), 1000),
        LEAD_A - timedelta(days=bt.CALENDAR_LEAD_DAYS + 5): daily_row(
            LEAD_A - timedelta(days=bt.CALENDAR_LEAD_DAYS + 5),
            R(1900), R(1910), R(1890), R(1905), 1000,
        ),
    }
    build_stores(data, minute_days={TRADE_DAY: minutes}, daily_rows=rows, symbols=(SYMBOL,))
    ledger = data / "universe_backfill" / "ledger.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(
            {
                "symbols": {
                    SYMBOL: {
                        "status": kwargs.get("status", "settled"),
                        "gate1p_pass": 100,
                        "gate1p_total": 100,
                        "gate1p_no_oracle": 0,
                        "residual_reason": "",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return data


def test_the_preflight_reports_every_check_and_names_the_failures() -> None:
    """A `Preflight` with one failing check is NO-GO, and `failures` names exactly that one."""
    report = rb.Preflight(
        checks=(rb.Check("a", True, ""), rb.Check("b", False, "why")),
        symbols=("AAA",),
        start=date(2016, 10, 3),
        end=date(2026, 7, 24),
        data_dir=Path("data"),
        run_dir=Path("data/backtests/x"),
    )
    assert report.ok is False
    assert [check.name for check in report.failures] == ["b"]


def test_a_preflight_with_no_checks_is_not_a_pass() -> None:
    """`all(())` is True. An empty check list must never read as GO."""
    empty = rb.Preflight(
        checks=(), symbols=(), start=None, end=None,
        data_dir=Path("data"), run_dir=Path("data/backtests/x"),
    )
    assert empty.ok is False


def test_a_failing_preflight_does_NOT_print_the_run_command() -> None:
    """The card's own rule: any check failing -> refuse to emit the run command. A ledger built
    on a half-open store cannot be qualified by anyone."""
    report = rb.Preflight(
        checks=(rb.Check("minute store reachable", False, "0 symbol directories"),),
        symbols=(),
        start=None,
        end=None,
        data_dir=Path("data"),
        run_dir=Path("data/backtests/x"),
    )
    text = "\n".join(
        rb.render_preflight(report, label="x", command="python scripts/run_backtest.py")
    )
    assert "NO-GO" in text
    assert "minute store reachable" in text
    assert "python scripts/run_backtest.py" not in text
    assert "The run command is NOT emitted" in text


def test_a_passing_preflight_prints_the_command_and_how_to_know_it_finished() -> None:
    report = rb.Preflight(
        checks=(rb.Check("all good", True, "measured"),),
        symbols=("AAA", "BBB"),
        start=date(2016, 10, 3),
        end=date(2026, 7, 24),
        data_dir=Path("data"),
        run_dir=Path("data/backtests/chunk9b_full"),
    )
    text = "\n".join(
        rb.render_preflight(report, label="chunk9b_full", command="python scripts/run_backtest.py")
    )
    assert "VERDICT: GO" in text
    assert "python scripts/run_backtest.py" in text
    assert "2016-10-03 -> 2026-07-24" in text
    assert "RUN COMPLETE" in text                      # how the operator knows it finished
    assert bt.LEDGER_NAME in text and bt.MANIFEST_NAME in text
    assert "do NOT commit or check out anything while it runs" in text


def test_disclosed_conditions_are_printed_above_the_verdict_and_are_not_failures() -> None:
    """A clamped span is a measured fact, not a failure -- and it must not be silent either."""
    report = rb.Preflight(
        checks=(rb.Check("all good", True, "measured"),),
        symbols=("AAA",),
        start=date(2016, 10, 3),
        end=date(2026, 7, 24),
        data_dir=Path("data"),
        run_dir=Path("data/backtests/chunk9b_full"),
        notes=("SPAN CLAMPED TO THE RAW DAILY ORACLE. ...",),
    )
    text = "\n".join(rb.render_preflight(report, label="x", command="cmd"))
    assert report.ok is True
    assert "DISCLOSED CONDITIONS (measured, not failures -- and not silent):" in text
    assert text.index("DISCLOSED CONDITIONS") < text.index("VERDICT: GO")


def test_the_preflight_passes_on_a_complete_miniature_world(tmp_path: Path) -> None:
    """End to end on a real (tiny) data directory: both stores, the register, the master and
    the calendar. Everything is measured from it -- nothing about it is typed into the code."""
    data = preflight_world(tmp_path)
    report = rb.preflight(data_dir=data, cache_dir=_cache_with_master(tmp_path))
    named = {check.name: check for check in report.checks}
    assert named["disclosed-residual register loads"].ok
    assert named["universe = the settled symbols, all present in the store"].ok
    assert named["span = the full minute era, taken from the stores"].ok
    assert named["trading calendar loaded over the span"].ok
    assert report.symbols == (SYMBOL,)
    assert (report.start, report.end) == (TRADE_DAY, TRADE_DAY)
    # ...and the PIN, resolved and digested (QUESTIONS.md Q-20).
    assert named[MASTER_CHECK].ok
    assert report.master_path is not None and len(report.master_sha256) == 64
    # The miniature world deliberately carries no corporate-action day-cache (building one is
    # chunk-3 work and this fixture is about the stores), so exactly ONE check may fail here.
    # Naming it is what keeps a check that quietly started failing for everyone -- which is what
    # the Q-20 pin did to this test before `_cache_with_master` learned the pinned name -- from
    # hiding behind a per-check assertion list.
    assert [check.name for check in report.failures] == [
        "CA day-cache 2005..2026 present and served offline"
    ]


def test_the_preflight_FAILS_when_the_residual_register_is_absent(tmp_path: Path) -> None:
    """CONTEXT 4.6 makes reading the register a chunk-9 duty. Without it the run cannot say
    which symbols are price-partial, so it must not start."""
    data = preflight_world(tmp_path)
    (data / "universe_backfill" / "ledger.json").unlink()
    report = rb.preflight(data_dir=data, cache_dir=_cache_with_master(tmp_path))
    assert report.ok is False
    assert any(
        check.name == "disclosed-residual register loads" and not check.ok
        for check in report.checks
    )


def test_the_preflight_FAILS_when_a_settled_symbol_has_no_minute_data(tmp_path: Path) -> None:
    """A symbol the register calls settled but the store has never heard of is a broken input,
    not an empty result: every one of its days would refuse for "no minutes"."""
    data = preflight_world(tmp_path)
    ledger = data / "universe_backfill" / "ledger.json"
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["symbols"]["GHOST"] = dict(payload["symbols"][SYMBOL])
    ledger.write_text(json.dumps(payload), encoding="utf-8")

    report = rb.preflight(data_dir=data, cache_dir=_cache_with_master(tmp_path))
    universe_check = next(
        check for check in report.checks
        if check.name == "universe = the settled symbols, all present in the store"
    )
    assert universe_check.ok is False
    assert "GHOST" in universe_check.detail
    assert report.ok is False


MASTER_CHECK = "instrument master PINNED (Q-20) and its digest taken"


def test_the_preflight_FAILS_when_the_instrument_master_is_missing(tmp_path: Path) -> None:
    """CONTEXT 4.3 forbids hardcoding a tick size, so a run with no master has no tick grid."""
    data = preflight_world(tmp_path)
    report = rb.preflight(data_dir=data, cache_dir=tmp_path / "empty_cache")
    assert report.ok is False
    assert any(check.name == MASTER_CHECK and not check.ok for check in report.checks)
    assert report.master_path is None and report.master_sha256 is None


def test_the_preflight_REFUSES_a_cache_holding_only_an_UNPINNED_master(tmp_path: Path) -> None:
    """**QUESTIONS.md Q-20, the whole point.** A cache carrying a perfectly good, NEWER master
    that is not the pinned one is NO-GO -- the old newest-by-filename resolver would have taken
    it happily and silently changed the tick on 11 walked symbols. The refusal names the pin."""
    data = preflight_world(tmp_path)
    cache = _cache_with_master(tmp_path, name="OpenAPIScripMaster_2099-01-01.json")
    report = rb.preflight(data_dir=data, cache_dir=cache)
    assert report.ok is False
    failed = next(check for check in report.checks if check.name == MASTER_CHECK)
    assert not failed.ok
    assert load_config(include_env=False).instrument_master in failed.detail
    assert "Q-20" in failed.detail


def test_the_preflight_prints_the_pin_and_its_digest_in_the_GO_block(tmp_path: Path) -> None:
    """The operator is shown WHICH ticks the run will use, by name and by content digest --
    Q-20's own complaint was that a finished ledger could not be traced back to its ticks."""
    data = preflight_world(tmp_path)
    measured = rb.preflight(data_dir=data, cache_dir=_cache_with_master(tmp_path))
    # The one check this fixture cannot satisfy is the CA day-cache (see the miniature-world
    # test above); the renderer's GO block is what is under test here, so it is forced.
    report = replace(
        measured, checks=tuple(replace(check, ok=True) for check in measured.checks)
    )
    assert report.ok is True
    text = "\n".join(rb.render_preflight(report, label="x", command="python go"))
    assert "VERDICT: GO" in text
    assert f"tick pin : {report.master_path.name} (Q-20)" in text
    assert f"sha256 {report.master_sha256}" in text
    assert len(report.master_sha256) == 64


def _cache_with_master(tmp_path: Path, name: str | None = None) -> Path:
    """A cache directory holding one instrument-master dump, in the shape the loader expects.

    The file is written under the PINNED name by default (QUESTIONS.md Q-20): the preflight
    resolves exactly the filename ``config.yaml`` names and no other, so a miniature world whose
    dump is called something else is a world with no tick grid, by design.
    """
    from acumen.config import load_config
    from acumen.instrument_master import CACHE_SUBDIR

    home = tmp_path / "cache" / CACHE_SUBDIR
    home.mkdir(parents=True, exist_ok=True)
    filename = name if name is not None else load_config(include_env=False).instrument_master
    (home / filename).write_text(
        json.dumps(
            [
                {
                    "exch_seg": "NSE",
                    "symbol": f"{SYMBOL}-EQ",
                    "token": "90000",
                    "tick_size": "10.000000",
                    "name": SYMBOL,
                    "lotsize": "1",
                }
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path / "cache"


# --- CLAUDE.md Q-18 layer 3: the store-freshness stamps ------------------------------------
#
# The layer's own words: "The operator keeps TWO snapshot generations; a new snapshot never
# overwrites the previous until verified. The preflight prints the stores' last-changed
# timestamps so the operator can confirm the snapshot is newer." These pin the instrument that
# sentence promises. It is advisory -- it must never fail a preflight and must never reach the
# run manifest, which stays byte-identical across runs and therefore carries no clock read.


def test_a_store_stamp_reports_the_newest_mtime_anywhere_under_the_root(
    tmp_path: Path,
) -> None:
    """A file rewritten DEEP inside the tree must move the number the operator compares to.

    This is the whole point: the stores are nested (minute_store/minute/<SYMBOL>/*.parquet), so
    a stamp taken from the root directory's own mtime would sit still while the lake changed
    underneath it, and an out-of-date snapshot would be accepted.
    """
    root = tmp_path / "store"
    deep = root / "minute_store" / "minute" / "ACME"
    deep.mkdir(parents=True)
    (deep / "ACME_2016-10.parquet").write_text("x", encoding="utf-8")

    old = datetime(2020, 1, 1, 9, 15).timestamp()
    for path in (root, root / "minute_store", root / "minute_store" / "minute", deep,
                 deep / "ACME_2016-10.parquet"):
        os.utime(path, (old, old))
    assert rb.store_last_changed("data_root", root).last_changed == datetime(2020, 1, 1, 9, 15)

    newer = datetime(2026, 8, 2, 1, 21, 16).timestamp()
    os.utime(deep / "ACME_2016-10.parquet", (newer, newer))
    stamp = rb.store_last_changed("data_root", root)
    assert stamp.last_changed == datetime(2026, 8, 2, 1, 21, 16)
    assert stamp.exists is True
    assert stamp.entries == 4, "3 nested directories + 1 parquet"


def test_a_missing_store_root_stamps_as_missing_rather_than_raising(tmp_path: Path) -> None:
    """A store that is not there is an operator fact, not an exception."""
    stamp = rb.store_last_changed("cache_root", tmp_path / "gone")
    assert stamp.exists is False
    assert stamp.last_changed is None
    assert stamp.entries == 0
    assert "MISSING" in stamp.line(len("cache_root"))


def test_the_freshness_block_is_rendered_with_both_roots_and_the_two_generation_rule() -> None:
    """The operator must be able to answer "is my snapshot newer?" from the print-out alone."""
    report = rb.Preflight(
        checks=(rb.Check("a", True, ""),),
        symbols=("AAA",),
        start=date(2016, 10, 3),
        end=date(2026, 7, 30),
        data_dir=Path("X:/acumen-data"),
        run_dir=Path("X:/acumen-data/backtests/x"),
        store_stamps=(
            rb.StoreStamp("data_root", Path("X:/acumen-data"), True,
                          datetime(2026, 8, 2, 1, 21, 16), 21_837),
            rb.StoreStamp("cache_root", Path("X:/acumen-data/cache"), True,
                          datetime(2026, 8, 2, 1, 17, 8), 2),
        ),
    )
    text = "\n".join(rb.render_preflight(report, label="unit", command="cmd"))
    assert "STORE FRESHNESS" in text
    assert "2026-08-02 01:21:16" in text and "2026-08-02 01:17:08" in text
    assert "21,837 entries" in text
    assert "data_root" in text and "cache_root" in text
    assert "TWO generations" in text
    assert "OPERATOR" in text, "snapshotting is never a session's job"


def test_the_freshness_stamps_never_reach_the_run_manifest() -> None:
    """`notes` flow into the manifest's disclosures; `store_stamps` must NOT.

    A clock read on the manifest would move its digest on every run and destroy the
    byte-identical-resume property chunk 9A proved.
    """
    assert "store_stamps" not in {field.name for field in fields(bt.RunSpec)}
    stamped = rb.Preflight(
        checks=(rb.Check("a", True, ""),),
        symbols=("AAA",),
        start=date(2016, 10, 3),
        end=date(2026, 7, 30),
        data_dir=Path("X:/acumen-data"),
        run_dir=Path("X:/acumen-data/backtests/x"),
        notes=("a real disclosed condition",),
        store_stamps=(
            rb.StoreStamp("data_root", Path("X:/acumen-data"), True, datetime.now(), 1),
        ),
    )
    # main() builds disclosures from report.notes ONLY -- this is that expression, pinned.
    disclosures = (bt.CAPITAL_FLAGS_PENDING_NOTE, rb.Q44_PENDING_STAMP, rb.Q44_ESCALATION,
                   *stamped.notes)
    assert "a real disclosed condition" in disclosures
    assert not any("last changed" in sentence for sentence in disclosures)
    assert not any("STORE FRESHNESS" in sentence for sentence in disclosures)


def test_a_preflight_that_could_not_read_the_config_invents_no_store_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one branch where the store roots are UNKNOWN must say so, not guess `data/`.

    Before the Q-18 migration this branch fell back to a repo-relative ``Path("data")``, which
    is precisely the in-repo location CLAUDE.md layer 1 abolished.
    """
    def refuse(*_args: object, **_kwargs: object):
        raise ConfigError("config.yaml is unreadable")

    monkeypatch.setattr(rb, "load_config", refuse)
    report = rb.preflight(label="unit")
    assert report.ok is False
    assert report.data_dir is None and report.run_dir is None
    # And the renderer must survive it: NO-GO reads neither field.
    text = "\n".join(rb.render_preflight(report, label="unit", command="cmd"))
    assert "NO-GO" in text
    assert "data/backtests" not in text
