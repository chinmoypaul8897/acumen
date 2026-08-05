"""Chunk 9B: the report generator's own tests.

Every one of these builds a SMALL run on disk -- a ledger, a manifest, a shard directory -- and
drives the shipped code over it. The report's job is to say true things about a ledger it did not
write, so the tests that matter are the ones where the ledger and the manifest DISAGREE and the
report has to notice.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen import report_9b as r9
from acumen.signals import LONG, SHORT

COST = 10_000
CAPITAL = 10_000_000


def trade(day: date, symbol: str, side: str, qty: int, entry: int, gross: int, *,
          hour: int = 12, exit_hour: int = 14, gap: bool = False,
          flags: tuple[str, ...] = ()) -> bt.LedgerRow:
    base = datetime.combine(day, datetime.min.time())
    return bt.LedgerRow(
        symbol=symbol, day=day, status="evaluated", reason="evaluated", side=side,
        outcome="entered", consumed=True, signalled=True, executed=True, gap_entry=gap,
        entry_paise=entry, stop_paise=entry - 100, target_paise=entry + 300,
        per_share_risk_paise=100, entry_close_stamp=base + timedelta(hours=hour),
        exit_kind="target-hit", exit_paise=entry + 300,
        exit_close_stamp=base + timedelta(hours=exit_hour), qty=qty,
        notional_paise=qty * entry, gross_pnl_paise=gross, cost_paise=COST,
        net_pnl_paise=gross - COST, mfe_paise=max(0, gross), mae_paise=min(0, gross),
        flags=flags,
    )


def refused(day: date, symbol: str, reason: str, *, flags: tuple[str, ...] = (),
            bias_rule: str | None = None) -> bt.LedgerRow:
    return bt.LedgerRow(symbol=symbol, day=day, status="refused", reason=reason,
                        bias_rule=bias_rule, flags=flags)


def flat(day: date, symbol: str) -> bt.LedgerRow:
    return bt.LedgerRow(symbol=symbol, day=day, status="evaluated", reason="evaluated",
                        outcome="no-trade-never-armed", side=LONG)


D = [date(2020, 1, 6), date(2020, 1, 7), date(2021, 1, 6), date(2021, 1, 7)]


def sample_rows() -> tuple[bt.LedgerRow, ...]:
    """Two symbols, two years, one of every shape the report has to partition."""
    return (
        trade(D[0], "AAA", LONG, 100, 200_000, 300_000),
        trade(D[0], "BBB", SHORT, 50, 100_000, -100_000, gap=True),
        flat(D[1], "AAA"),
        refused(D[1], "BBB", "gate 1 (volume reconciliation)"),
        trade(D[2], "AAA", LONG, 40, 250_000, 100_000),
        refused(D[2], "BBB", "gate 2 (candle integrity)"),
        trade(D[3], "AAA", SHORT, 20, 300_000, -200_000,
              flags=(bt.FLAG_OUT_OF_SESSION_DROPPED,)),
        refused(D[3], "BBB",
                "bias unresolvable (CONTEXT 3.2 pair could not be assembled): minutes-ungated",
                flags=(bt.FLAG_UNGATED_MINUTE_DAY,)),
    )


def write_run(root: Path, rows, *, label: str = "run", manifest_edits: dict | None = None) -> Path:
    """A run directory the shipped reader can open: ledger, shards and a TRUE manifest."""
    run_dir = root / label
    (run_dir / bt.SHARD_DIRNAME).mkdir(parents=True, exist_ok=True)
    (run_dir / bt.LEDGER_NAME).write_text(
        "".join(row.to_json() + "\n" for row in rows), encoding="utf-8", newline="\n"
    )
    by_symbol: dict[str, list[bt.LedgerRow]] = {}
    for row in rows:
        by_symbol.setdefault(row.symbol, []).append(row)
    for symbol, shard in by_symbol.items():
        (run_dir / bt.SHARD_DIRNAME / f"{symbol}.jsonl").write_text(
            "".join(row.to_json() + "\n" for row in shard), encoding="utf-8", newline="\n"
        )
    executed = [row for row in rows if row.executed]
    manifest = {
        "spec_version": "v1.7",
        "code_sha": "0" * 40,
        "config_digest": "c" * 64,
        "instrument_master": {"pinned_file": "master.json", "sha256": "m" * 64, "note": ""},
        "spec": {"label": label, "start": rows[0].day.isoformat(), "end": rows[-1].day.isoformat(),
                 "risk_per_trade_paise": 100_000, "cost_paise": COST, "row_size": 24},
        "span": {"start": rows[0].day.isoformat(), "end": rows[-1].day.isoformat()},
        "universe": sorted(by_symbol),
        "disclosures": [bt.CAPITAL_FLAGS_PENDING_NOTE],
        "factor_table": {"digest": "f" * 64, "per_symbol": {}},
        "residual_register": {"caveat": "no settled-but-partial symbol in this fixture"},
        "totals": {
            "walked": len(rows),
            "usable": sum(1 for r in rows if r.status != "refused"),
            "signalled": sum(1 for r in rows if r.signalled),
            "executed": len(executed),
            "shares": sum(r.qty for r in executed),
            "gross_pnl_paise": sum(r.gross_pnl_paise for r in executed),
            "cost_paise": sum(r.cost_paise for r in executed),
            "net_pnl_paise": sum(r.net_pnl_paise for r in executed),
            "gate1_relieved": 0,
        },
        "refused_by_reason": _reasons(rows),
        "outcomes": bt.outcome_counts(rows),
        "exit_kinds": bt.exit_kind_counts(rows),
        "rare_shapes": bt.rare_shape_counts(rows),
    }
    if manifest_edits:
        _deep_update(manifest, manifest_edits)
    (run_dir / bt.MANIFEST_NAME).write_text(
        bt.canonical_json(manifest), encoding="utf-8", newline="\n"
    )
    return run_dir


def _reasons(rows) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row.status == "refused":
            counts[row.reason] = counts.get(row.reason, 0) + 1
    return dict(sorted(counts.items()))


def _deep_update(target: dict, edits: dict) -> None:
    for key, value in edits.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


# --- the reader and the reconciliation -------------------------------------------------------


def test_the_reader_keeps_the_executed_rows_and_counts_everything_else(tmp_path: Path) -> None:
    """495,312 rows do not need to be resident; the report needs the trades and the day index."""
    run = r9.read_run(write_run(tmp_path, sample_rows()))
    assert run.walked == 8
    assert len(run.executed) == 4, "only the executed rows are kept"
    assert run.usable + run.refused == run.walked, "the partition holds in the reader itself"
    assert run.days == tuple(D), "every walked day is in the index, flat days included"
    assert run.totals["net_pnl_paise"] == sum(r.net_pnl_paise for r in run.executed)


def test_a_manifest_that_lies_about_its_own_rows_is_CAUGHT(tmp_path: Path) -> None:
    """The whole point of section 3a. A manifest is a summary its own runner wrote."""
    honest = r9.reconcile(r9.read_run(write_run(tmp_path / "a", sample_rows())))
    assert all(check.ok for check in honest), "the fixture's manifest is true of its rows"

    liar = write_run(tmp_path / "b", sample_rows(),
                     manifest_edits={"totals": {"executed": 999, "net_pnl_paise": 1}})
    broken = r9.reconcile(r9.read_run(liar))
    failed = {check.name for check in broken if not check.ok}
    assert "executed" in failed and "net PnL (paise)" in failed
    # ...and the partition checks, which are recount-vs-recount, still pass: they are the ones
    # that cannot be fooled by editing the manifest at all.
    assert {c.name: c.ok for c in broken}["PARTITION usable + refused == walked"] is True


def test_a_dropped_refusal_reason_is_CAUGHT(tmp_path: Path) -> None:
    """A reason quietly missing from the manifest is a day nobody can account for."""
    run_dir = write_run(tmp_path, sample_rows())
    path = run_dir / bt.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["refused_by_reason"].pop("gate 2 (candle integrity)")
    path.write_text(bt.canonical_json(manifest), encoding="utf-8", newline="\n")

    checks = {check.name: check for check in r9.reconcile(r9.read_run(run_dir))}
    assert not checks["refusals by reason (all 9)"].ok
    # ...and the recount-vs-recount partition is untouched, because it never reads the manifest.
    assert checks["PARTITION sum(refusal reasons) == refused"].ok


def test_every_rare_shape_label_must_be_recounted_not_defaulted(tmp_path: Path) -> None:
    """A label with no independent recount RAISES rather than echoing the manifest's number."""
    run = r9.read_run(write_run(tmp_path, sample_rows()))
    for label in bt.RARE_SHAPE_LABELS:
        r9._rare_shape_recount(run, label)  # every shipped label has one
    with pytest.raises(bt.BacktestError, match="no independent recount"):
        r9._rare_shape_recount(run, "a rare shape invented after this report was written")


def test_the_rare_shape_recount_is_independent_of_the_manifest(tmp_path: Path) -> None:
    """It counts from the rows the report streamed, so a wrong counter shows up as a mismatch."""
    label = "gap entries"
    run_dir = write_run(tmp_path, sample_rows(), manifest_edits={"rare_shapes": {label: 77}})
    run = r9.read_run(run_dir)
    assert r9._rare_shape_recount(run, label) == 1
    checks = {check.name: check for check in r9.reconcile(run)}
    assert not checks[f"rare shape: {label}"].ok


def test_a_missing_ledger_raises_rather_than_reporting_on_nothing(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(bt.BacktestError, match="No run ledger"):
        r9.read_run(tmp_path / "empty")


# --- the two cross-checks ---------------------------------------------------------------------


def test_the_pilot_cross_check_finds_a_single_moved_field(tmp_path: Path) -> None:
    """Trade-level identity is the claim; one field is enough to break it and must be named."""
    rows = sample_rows()
    run_dir = write_run(tmp_path / "run", rows, label="run")
    pilot_rows = [r for r in rows if r.symbol == "AAA"]
    pilot_dir = write_run(tmp_path / "pilot", pilot_rows, label="pilot")

    monkey = r9.PILOT_SYMBOLS, r9.PILOT_START, r9.PILOT_END
    try:
        r9.PILOT_SYMBOLS = ("AAA",)
        r9.PILOT_START, r9.PILOT_END = D[0], D[-1]
        same = r9.pilot_cross_check(run_dir, pilot_dir)
        assert same.keys_equal and not same.differing and same.identical == 4

        moved = [r for r in pilot_rows]
        moved[0] = bt.LedgerRow(**{**moved[0].__dict__, "net_pnl_paise": 1})
        other = write_run(tmp_path / "pilot2", moved, label="pilot2")
        check = r9.pilot_cross_check(run_dir, other)
        assert len(check.differing) == 1
        assert check.differing[0][2] == ("net_pnl_paise",)
    finally:
        r9.PILOT_SYMBOLS, r9.PILOT_START, r9.PILOT_END = monkey


def test_the_crashed_cross_check_classifies_every_ruling_and_leaves_none_unexplained(
    tmp_path: Path,
) -> None:
    """Every differing row must be one of the four rulings; anything else is non-determinism."""
    before = list(sample_rows())
    after = list(sample_rows())
    # A: a day that traded then, refused now under Q-21(b).
    after[0] = refused(D[0], "AAA", "bias unresolvable (CONTEXT 3.2 pair could not be assembled)"
                       ": minutes-ungated", flags=(bt.FLAG_UNGATED_MINUTE_DAY,),
                       bias_rule="minutes-ungated")
    # B: a day that traded then, refused now under the completed gate 2.
    after[1] = refused(D[0], "BBB", "gate 2 (candle integrity)")
    # C: a day that gained the out-of-session flag.
    before[6] = trade(D[3], "AAA", SHORT, 20, 300_000, -200_000)
    # D: a day whose carried bias moved, so it traded differently on both runs.
    before[4] = trade(D[2], "AAA", SHORT, 40, 250_000, -100_000)

    run_dir = write_run(tmp_path / "new", after, label="new")
    crashed_dir = write_run(tmp_path / "old", before, label="old")
    check = r9.crashed_cross_check(run_dir, crashed_dir)

    assert check.rows_changed == 4
    assert check.unexplained == 0, "every changed row is attributed to a ruling"
    assert set(check.by_cause) == set(r9._CAUSES)
    assert all(count == 1 for count in check.by_cause.values())
    assert len(check.lost_trades[r9._CAUSES[0]]) == 1, "Q-21(b) took a real trade away"
    assert len(check.lost_trades[r9._CAUSES[1]]) == 1, "the gate-2 completion took a real trade"
    assert check.moved_trades[r9._CAUSES[3]] == 1, "a carried-bias day traded differently"


# --- what the refusals cost (REVIEW_9B_FIXES R10) ---------------------------------------------


def test_refusals_are_priced_only_where_a_counterfactual_EXISTS(tmp_path: Path) -> None:
    """R10 asks for trades and PnL, and forbids inventing them where no evidence exists."""
    before = list(sample_rows())
    after = list(sample_rows())
    after[1] = refused(D[0], "BBB", "gate 2 (candle integrity)")
    run_dir = write_run(tmp_path / "new", after, label="new")
    crashed_dir = write_run(tmp_path / "old", before, label="old")
    run = r9.read_run(run_dir)
    priced = {item.reason: item for item in
              r9.price_refusals(run, r9.crashed_cross_check(run_dir, crashed_dir))}

    gate2 = priced["gate 2 (candle integrity)"]
    assert gate2.trades_found == 1
    assert gate2.net_paise == before[1].net_pnl_paise
    assert "crashed run" in gate2.evidence

    gate1 = priced["gate 1 (volume reconciliation)"]
    assert gate1.trades_found == 0 and gate1.net_paise == 0
    assert gate1.evidence.startswith("none"), "no counterfactual means no number, not a guess"


# --- the per-year table -------------------------------------------------------------------------


def test_each_year_starts_where_the_last_one_ended_and_the_nets_sum_to_the_run(
    tmp_path: Path,
) -> None:
    """A year's drawdown must be a fall inside that year, which is what the seeding buys."""
    run = r9.read_run(write_run(tmp_path, sample_rows()))
    years = r9.per_year(run.executed, run.days, initial_capital_paise=CAPITAL,
                        gap_by_year={"2020": 1})
    assert [y.year for y in years] == ["2020", "2021"]
    assert years[0].opening_equity_paise == CAPITAL
    assert years[1].opening_equity_paise == years[0].closing_equity_paise
    assert sum(y.metrics.net_pnl_paise for y in years) == run.totals["net_pnl_paise"]
    assert years[-1].closing_equity_paise == CAPITAL + run.totals["net_pnl_paise"]
    assert years[0].gap_entries == 1


# --- the benchmark, both readings (Q-23) ---------------------------------------------------------


class _FakeDaily:
    """A daily store the size of the fixture: two closes per symbol and nothing else."""

    def __init__(self, series: dict[str, dict[date, int]]) -> None:
        self._series = series

    def daily(self, symbol: str, start: date, end: date):
        class _Frame:
            def __init__(self, rows):
                self._rows = rows

            def itertuples(self):
                return iter(self._rows)

        class _Row:
            def __init__(self, day, close):
                self.trade_date = day
                self.close_paise = close

        return _Frame([
            _Row(day, close)
            for day, close in sorted(self._series.get(symbol, {}).items())
            if start <= day <= end
        ])


def test_a_bonus_moves_the_benchmark_by_exactly_the_factor_and_BOTH_readings_are_kept() -> None:
    """The hand-computed case: 1:1 bonus, k = 1/2, price halves, the holder's shares double.

    RAW reads the symbol as flat (100 -> 100 after a halving that doubled the share count is a
    100% gain a raw series cannot see). ADJUSTED brings the first close into the last close's
    scale through the run's OWN factor -- 100 x 1/2 = 50 -- and reads +100%.
    """
    first, last = date(2020, 1, 1), date(2021, 1, 1)
    store = _FakeDaily({"AAA": {first: 100_000, last: 100_000}})
    manifest = {"factor_table": {"per_symbol": {
        "AAA": {"in_span": [{"ex_date": "2020-06-01", "k": "0.5", "kind": "bonus",
                             "classification": ""}]}
    }}}
    pair = r9.benchmark_pair(store, manifest, symbols=["AAA"], first_day=first, last_day=last,
                             initial_capital_paise=1_000_000)
    assert pair.raw.total_return == Fraction(0), "raw sees a flat price"
    assert pair.adjusted.total_return == Fraction(1), "adjusted sees the doubling it really was"
    assert pair.adjusted_symbols == 1 and pair.events_applied == 1
    assert "Q-23" in pair.stop, "the silence is raised, not decided"


def test_an_ordinary_dividend_moves_NEITHER_reading() -> None:
    """CONTEXT 4.2 gives an ordinary dividend k = 1, so the two readings must coincide."""
    first, last = date(2020, 1, 1), date(2021, 1, 1)
    store = _FakeDaily({"AAA": {first: 100_000, last: 120_000}})
    manifest = {"factor_table": {"per_symbol": {
        "AAA": {"in_span": [{"ex_date": "2020-06-01", "k": "1", "kind": "dividend",
                             "classification": "ordinary"}]}
    }}}
    pair = r9.benchmark_pair(store, manifest, symbols=["AAA"], first_day=first, last_day=last,
                             initial_capital_paise=1_000_000)
    assert pair.raw.total_return == pair.adjusted.total_return == Fraction(1, 5)
    assert pair.events_applied == 0, "a k of 1 is not an adjustment and is not counted as one"


def test_a_factor_outside_the_hold_window_is_NOT_applied() -> None:
    """Only events between the buy and the period end change a holder's share count."""
    first, last = date(2020, 1, 1), date(2021, 1, 1)
    store = _FakeDaily({"AAA": {first: 100_000, last: 100_000}})
    manifest = {"factor_table": {"per_symbol": {
        "AAA": {"in_span": [{"ex_date": "2019-06-01", "k": "0.5", "kind": "bonus",
                             "classification": ""},
                            {"ex_date": "2022-06-01", "k": "0.5", "kind": "bonus",
                             "classification": ""}]}
    }}}
    pair = r9.benchmark_pair(store, manifest, symbols=["AAA"], first_day=first, last_day=last,
                             initial_capital_paise=1_000_000)
    assert pair.events_applied == 0
    assert pair.raw.total_return == pair.adjusted.total_return == Fraction(0)


# --- the disclosures ------------------------------------------------------------------------------


def test_the_daily_count_distribution_counts_the_days_that_traded_NOTHING(
    tmp_path: Path,
) -> None:
    """CONTEXT 3.5 asks for the distribution; a day the strategy sat out is one of its counts."""
    run = r9.read_run(write_run(tmp_path, sample_rows()))
    series = pf.daily_pnl(run.executed, days=run.days)
    counts = dict(r9._daily_count_distribution(series))
    assert counts == {0: 1, 1: 2, 2: 1}, "2020-01-07 traded nothing and is counted at zero"
    assert sum(counts.values()) == len(run.days)


# --- rendering ------------------------------------------------------------------------------------


def render(tmp_path: Path, rows=None):
    rows = sample_rows() if rows is None else rows
    run_dir = write_run(tmp_path / "run", rows, label="run")
    crashed_dir = write_run(tmp_path / "old", rows, label="old")
    run = r9.read_run(run_dir)
    crashed = r9.crashed_cross_check(run_dir, crashed_dir)
    columns = pf.side_split(run.executed, initial_capital_paise=CAPITAL)
    series = pf.daily_pnl(run.executed, days=run.days)
    first = min(row.day for row in run.executed)
    store = _FakeDaily({s: {first: 100_000, run.days[-1]: 110_000} for s in run.symbols})
    return r9.render_markdown(
        run=run,
        config=None,
        capital_paise=CAPITAL,
        checks=r9.reconcile(run),
        pilot=r9._compare("fixture", {}, {}),
        crashed=crashed,
        columns=columns,
        curve=pf.equity_curve(series, CAPITAL),
        series=series,
        disclosures=pf.disclosures(run.executed),
        capital_flag_report=pf.capital_flags(run.executed, capital_reference_paise=None,
                                             margin_basis=None),
        years=r9.per_year(run.executed, run.days, initial_capital_paise=CAPITAL,
                          gap_by_year=run.witnesses.gap_by_year),
        symbols={s: pf.metrics(pf.for_symbol(run.executed, s), label=s,
                               initial_capital_paise=CAPITAL, days=run.days)
                 for s in run.symbols},
        register={},
        crosses_zero={label: r9._curve_crosses_zero(rows, run.days, CAPITAL)
                      for label, rows in (("All", run.executed),
                                          ("Long", pf.for_side(run.executed, LONG)),
                                          ("Short", pf.for_side(run.executed, SHORT)))},
        benchmark=r9.benchmark_pair(store, run.manifest, symbols=run.symbols, first_day=first,
                                    last_day=run.days[-1], initial_capital_paise=CAPITAL),
        paths_built=0,
        path_marks=0,
        paths_reconciling=0,
        refusals=r9.price_refusals(run, crashed),
        daily_counts=r9._daily_count_distribution(series),
    )


def test_the_report_is_a_pure_function_of_its_inputs(tmp_path: Path) -> None:
    """Byte-reproducibility starts here: no clock, no dict iteration order, no randomness."""
    assert render(tmp_path / "a") == render(tmp_path / "b")


def test_the_report_carries_the_Q43_pending_sentence_VERBATIM_and_no_flag_value(
    tmp_path: Path,
) -> None:
    """The GO ruling's condition (1). A computed flag here would be this repo's number, not his."""
    text = render(tmp_path)
    assert bt.CAPITAL_FLAGS_PENDING_NOTE in text
    assert "capital_reference / margin_basis | null / null" in text
    assert "beyond cash" not in text.lower() and "beyond margin" not in text.lower()


def test_the_report_states_its_basis_and_the_outlier_rule_beside_the_numbers(
    tmp_path: Path,
) -> None:
    """The E13 ruling requires the definitions block ABOVE the tables, not in a footnote."""
    text = render(tmp_path)
    assert pf.E13_BASIS in text
    assert pf.OUTLIER_DEFINITION in text
    assert pf.INTRADAY_PATH_LIMIT in text
    assert text.index(pf.E13_BASIS) < text.index("## 5. The headline")


def test_the_report_prints_the_outlier_block_on_BOTH_branches(tmp_path: Path) -> None:
    """GO ruling condition (3): one format, so a zero prints the same four quantities."""
    text = render(tmp_path)
    for column in ("**All**", "**Long**", "**Short**"):
        assert column in text
    assert text.count("* Outliers: **") == 3, "every column prints the count, zero or not"
    assert text.count("* Fences: [") == 3


def test_the_report_says_survivorship_and_idealized_fills_OUT_LOUD(tmp_path: Path) -> None:
    """CONTEXT 7-E5 and 7-E9. A disclosure a reader has to hunt for is not a disclosure."""
    text = render(tmp_path)
    head = text.split("## 2.")[0]
    assert "survivorship" in head.lower()
    assert "IDEALIZED" in head
    assert "no capital or concurrency cap" in head


def test_a_reconciliation_failure_is_PRINTED_not_swallowed(tmp_path: Path) -> None:
    """The report must be readable as a FAIL. A generator that hides a mismatch is worthless."""
    rows = sample_rows()
    run_dir = write_run(tmp_path / "run", rows, label="run",
                        manifest_edits={"totals": {"executed": 999}})
    run = r9.read_run(run_dir)
    lines: list[str] = []
    r9._section_reconciliation(lines.append, run=run, checks=r9.reconcile(run),
                              pilot=r9._compare("fixture", {}, {}),
                              crashed=r9.crashed_cross_check(run_dir, run_dir))
    text = "\n".join(lines)
    assert "DID NOT RECONCILE" in text
    assert "**XX**" in text
    assert "The partition is exact" not in text


def test_a_percentage_is_REFUSED_when_its_base_equity_is_not_positive() -> None:
    """This run's equity goes below zero in its first year, so the case is the rule, not an edge.

    `Fraction(rise, trough)` still divides when the trough is negative -- and flips sign, so a
    run-up of Rs 407,255.90 printed as "-2.92%". That is not a percentage of anything. It is
    suppressed with its reason, and a genuine positive-base percentage still prints.
    """
    assert r9._excursion_pct(Fraction(1, 4)) == "25.00%"
    assert r9._excursion_pct(Fraction(-292, 10000)) == r9.NO_PERCENT_BASE
    assert r9._excursion_pct(None) == r9.NO_PERCENT_BASE
    assert r9._excursion_pct(Fraction(0)) == r9.NO_PERCENT_BASE


def test_a_run_up_is_printed_TROUGH_first_because_that_is_the_order_it_happened(
    tmp_path: Path,
) -> None:
    """A drawdown runs peak -> trough; a run-up runs trough -> peak. Printing both the same way
    put the later date first on every run-up row."""
    rise = pf.Excursion(amount_paise=5_000, pct=Fraction(1, 2), peak_day=date(2021, 3, 1),
                        trough_day=date(2020, 11, 8), duration_days=43,
                        recovered_on=date(2021, 5, 1))
    text = r9._excursion(rise, recovery_word="given back", rising=True)
    assert text.index("2020-11-08") < text.index("2021-03-01"), "trough first on a run-up"
    fall = pf.Excursion(amount_paise=5_000, pct=Fraction(1, 2), peak_day=date(2020, 11, 8),
                        trough_day=date(2021, 3, 1), duration_days=43, recovered_on=None)
    text = r9._excursion(fall, recovery_word="recovered")
    assert text.index("2020-11-08") < text.index("2021-03-01"), "peak first on a drawdown"
    assert "never inside the span" in text


def test_the_E13_columns_are_indexed_on_EVERY_WALKED_DAY_not_only_trading_days(
    tmp_path: Path,
) -> None:
    """A flat day is an observation. Dropping it annualizes a different sample -- silently.

    `pf.side_split` builds its own index from the rows it is given, and this report streams the
    refusals past instead of holding them, so handing it the executed rows alone would index on
    the days that TRADED. This asserts the report does not: the series must span every walked day,
    including the one this fixture's ledger walked without trading.
    """
    run = r9.read_run(write_run(tmp_path, sample_rows()))
    paths: tuple = ()
    columns = r9._side_split_over_walked_days(run, paths, capital_paise=CAPITAL)

    assert len(run.days) == 4, "the fixture walks four days"
    traded = {row.day for row in run.executed}
    assert len(traded) == 3, "and one of them traded nothing"

    for label, metrics in columns.items():
        assert metrics.trading_days == len(run.days), (
            f"{label} is indexed on {metrics.trading_days} days, not the {len(run.days)} walked"
        )
        assert metrics.first_day == run.days[0] and metrics.last_day == run.days[-1]

    # ...and the defect this replaces is demonstrated rather than described: the shipped
    # convenience wrapper, handed the same executed rows, really does lose the flat day.
    naive = pf.side_split(run.executed, initial_capital_paise=CAPITAL)
    assert naive["All"].trading_days == len(traded) < len(run.days)
    # the money is identical either way -- it is the SAMPLE that moves, which is the point
    assert naive["All"].net_pnl_paise == columns["All"].net_pnl_paise


def test_the_per_symbol_table_carries_each_symbol_s_own_coverage_from_the_REGISTER(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.6's chunk-9 duty. A per-symbol figure without its coverage is half a statement."""
    rows = sample_rows()
    run_dir = write_run(tmp_path / "run", rows, label="run")
    run = r9.read_run(run_dir)
    register = {
        "AAA": bt.ResidualEntry(symbol="AAA", status="settled", gate1p_pass=42,
                                gate1p_total=100, gate1p_no_oracle=0, residual_reason=""),
        "BBB": bt.ResidualEntry(symbol="BBB", status="quarantined", gate1p_pass=10,
                                gate1p_total=100, gate1p_no_oracle=0, residual_reason=""),
    }
    lines: list[str] = []
    r9._section_symbols(
        lines.append,
        symbols={s: pf.metrics(pf.for_symbol(run.executed, s), label=s,
                               initial_capital_paise=CAPITAL, days=run.days)
                 for s in run.symbols},
        register=register,
        run=run,
    )
    text = "\n".join(lines)
    assert "42.00%" in text and "10.00%" in text, "each symbol's price-proven share is printed"
    assert "quarantined" in text, "and its register status beside it"
    assert run.manifest["residual_register"]["caveat"] in text, "the B149 caveat, verbatim"
    assert pf.INTRADAY_PATH_NOT_SUPPLIED in text, "the missing path is stated, not implied"


def test_the_report_names_the_rare_shape_witnesses_rather_than_only_counting_them(
    tmp_path: Path,
) -> None:
    """REVIEW_7 Q3 and REVIEW_8 Q1 asked for witnesses, which means symbols and dates."""
    text = render(tmp_path)
    assert "BBB 2020-01-06" in text, "the gap-entry witness is NAMED"
    assert "2021-02-24" in text and "outage" in text.lower()
    assert "REVIEW_7" in text and "REVIEW_8" in text
