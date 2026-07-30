"""REVIEW_9A_2 reviewer probes -- the re-review of the chunk-9A Q-16 / E13 fix span.

Kept in the repo per the persona process (step 4). Nothing here weakens, replaces or edits an
existing test; every assertion is new. They fall into three groups.

**1. The ruling, pinned on REAL data rather than a fixture.** The fix ships hand-computed
fixtures for the Tukey fences and for the 15-minute path, and they are correct. What no test
covered is whether either rule BITES on the committed pilot: the exit-LEVEL rule is a two-line
branch that a fixture can satisfy and real data can still walk past. It does not -- 107 of the
146 exits fill at a level their own 15-minute candle did not close at, so marking closes would
break the reconciliation invariant on 107 rows and misstate one trade by Rs 2,843.75. These
probes measure that from the store and the ledger.

**2. Boundary and estimator coverage the build left open.** The build pins a trade sitting
exactly ON the UPPER fence; the LOWER fence has no such test, and this repo's own persona
checklist puts flipped boundary operators first. The quartile estimator is re-implemented from
its definition inside the test, so a bug in :func:`acumen.portfolio.quantile` cannot validate
itself.

**3. Three defects PINNED so a fix must be deliberate** -- the pattern REVIEW_9A used and this
fix session honoured. Each is green today and must be flipped by whoever fixes it:

* the pack still carries a THIRD before-costs figure (section 3's "Gross PnL Rs 12,665.05")
  outside both the one labelled line and the exception the definitions block states, so the
  pack's own "the only before-costs figures in this pack" is not literally true (finding Q1);
* the 15-minute run-up prints its giveback with drawdown vocabulary -- "never recovered in the
  window" on a RUN-UP row -- while the close-to-close run-up beside it correctly says "given
  back" (finding Q2);
* the runner's refusal-order docstring, rewritten by this very fix to close REVIEW_9A C4, says
  the first THREE reasons are decided by ``walk_symbol``; exactly TWO are (finding C1).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import inspect
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen.aggregate import aggregate_15min
from acumen.config import load_config
from acumen.minute_store import MinuteStore
from acumen.signals import LONG

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = REPO_ROOT / "docs" / "evidence" / "chunk9a_pilot.md"

#: The committed pilot run REVIEW_9A verified at four kill points (sha256 c3363f6f...c1e318).
PILOT_LEDGER_RELPATH = "backtests/chunk9a_pilot_a/ledger.jsonl"

CAPITAL = 10_000_000  # config.yaml initial_capital: 100000 rupees
DAY = date(2026, 3, 2)


# --- local helpers ---------------------------------------------------------------------------


def _pilot_rows() -> tuple[bt.LedgerRow, ...]:
    """The committed pilot ledger, or a skip -- ``data/`` is gitignored (chunk-8 precedent)."""
    config = load_config(include_env=False)
    ledger = config.path("data_dir") / PILOT_LEDGER_RELPATH
    if not ledger.is_file():
        pytest.skip(f"local run ledger {ledger} is absent (data/ is gitignored)")
    return bt.read_ledger(ledger)


def _pilot_paths() -> tuple[bt.TradePath, ...]:
    config = load_config(include_env=False)
    store_dir = config.path("data_dir") / "minute_store"
    if not store_dir.is_dir():
        pytest.skip(f"local minute store {store_dir} is absent (data/ is gitignored)")
    store = MinuteStore(store_dir)
    return bt.assemble_trade_paths(_pilot_rows(), bars_for=bt.minute_store_bars(store))


def _reviewer_quantile(values: list[int], p: Fraction) -> Fraction:
    """Type 7 written out from its DEFINITION, so `pf.quantile` cannot validate itself.

    ``(n - 1) * p`` splits into a whole part ``j`` and a fraction ``g``; the estimate is
    ``x[j] + g * (x[j+1] - x[j])`` over the ORDER statistics, with the top edge clamped.
    """
    ordered = sorted(values)
    n = len(ordered)
    position = Fraction(n - 1, 1) * p
    j = position.numerator // position.denominator
    g = position - j
    if j >= n - 1:
        return Fraction(ordered[-1])
    return Fraction(ordered[j]) * (1 - g) + Fraction(ordered[j + 1]) * g


def _daily_pnl(rows) -> dict[date, int]:
    out: dict[date, int] = defaultdict(int)
    for row in rows:
        if row.executed:
            out[row.day] += row.net_pnl_paise
    return out


# ==============================================================================================
# 1. Q-16(b) -- does the exit-LEVEL rule BITE on the committed pilot?
# ==============================================================================================


def test_the_exit_level_rule_bites_on_the_real_pilot_not_only_on_the_fixture() -> None:
    """The build proves the rule on one synthetic trade whose candle ran past its target. This
    measures it on the 146 real trades: most exits fill at a level their own 15-minute candle
    did NOT close at, so a close-marked path would be wrong on most of the run, not on a
    corner case."""
    rows = _pilot_rows()
    paths = _pilot_paths()
    config = load_config(include_env=False)
    store = MinuteStore(config.path("data_dir") / "minute_store")

    by_key = {(row.symbol, row.day): row for row in rows if row.executed}
    diverged = 0
    worst = 0
    for path in paths:
        row = by_key[(path.symbol, path.day)]
        bars = {bar.close_stamp: int(bar.close_paise) for bar in aggregate_15min(
            store.minutes(path.symbol, path.day)
        )}
        candle_close = bars.get(row.exit_close_stamp)
        if candle_close is None or candle_close == row.exit_paise:
            continue
        diverged += 1
        # marking the candle CLOSE instead of the fill LEVEL misstates the trade's money...
        wrong = pf.mark_pnl_paise(path, candle_close)
        assert wrong != path.net_pnl_paise
        worst = max(worst, abs(wrong - path.net_pnl_paise))

    assert diverged >= 100, diverged  # measured: 107 of 146
    assert worst >= 200_000  # measured: Rs 2,843.75 on HDFCBANK 2026-05-29


def test_every_pilot_path_reconciles_and_its_entry_mark_is_the_entry_candles_own_close() -> None:
    """Two facts the pack asserts as one. The second is the sharper of the pair: the entry mark
    is taken from the SAME aggregation the signal engine used, so the ledger-price fallback in
    `assemble_trade_paths` never has to fire -- if the two sources ever disagreed, the fallback
    would be papering over a real drift between the runner and the store."""
    rows = _pilot_rows()
    paths = _pilot_paths()
    config = load_config(include_env=False)
    store = MinuteStore(config.path("data_dir") / "minute_store")

    assert len(paths) == len([row for row in rows if row.executed])
    assert all(pf.path_reconciles(path) for path in paths)
    assert sum(len(path.marks) for path in paths) == 903

    for path in paths:
        bars = {bar.close_stamp: int(bar.close_paise) for bar in aggregate_15min(
            store.minutes(path.symbol, path.day)
        )}
        first = path.marks[0]
        assert bars[first.stamp] == first.price_paise == path.entry_paise


def test_the_pilot_path_never_skips_a_fifteen_minute_slot_it_held() -> None:
    """`_contribution` carries the last mark forward across a missing bar -- correct, but it
    means a gap is invisible in the output. On this pilot there is no gap to hide: every trade
    carries a mark at every 15-minute stamp between its entry and its exit, inclusive."""
    for path in _pilot_paths():
        stamps = [mark.stamp for mark in path.marks]
        expected = []
        stamp = stamps[0]
        while stamp <= stamps[-1]:
            expected.append(stamp)
            stamp += timedelta(minutes=15)
        assert stamps == expected, (path.symbol, path.day)


def test_the_pilot_paths_reproduce_the_packs_two_headline_path_figures() -> None:
    """Rs 14,231.00 (12.98%) and Rs 17,515.10 (19.00%) recomputed from the ledger and the store,
    so the pack's markdown and the code cannot drift apart without a red test."""
    rows = _pilot_rows()
    series = pf.daily_pnl(rows)
    points = pf.intraday_equity_path(
        series, _pilot_paths(), initial_capital_paise=CAPITAL
    )
    assert len(points) == 649

    fall = pf.path_max_drawdown(points, initial_capital_paise=CAPITAL)
    rise = pf.path_max_run_up(points, initial_capital_paise=CAPITAL)
    assert fall.amount_paise == 1_423_100
    assert fall.peak is not None and fall.peak.stamp == datetime(2026, 6, 11, 12, 15)
    assert fall.trough is not None and fall.trough.stamp == datetime(2026, 7, 23, 11, 45)
    assert fall.observations == 302 and fall.recovered is None
    assert rise.amount_paise == 1_751_510
    assert rise.observations == 197 and rise.recovered is None

    # and the day-close identity, on all 58 days, against the daily curve itself
    curve = {point.day: point.equity_paise for point in pf.equity_curve(series, CAPITAL)}
    closes = {point.day: point.equity_paise for point in points if point.stamp is None}
    assert closes == curve and len(closes) == 58


# ==============================================================================================
# 2. Q-16(a) -- estimator and fence coverage the build left open
# ==============================================================================================


def test_the_pilot_fences_reproduce_under_an_independently_written_estimator() -> None:
    """`pf.quantile` is not allowed to check itself: the type-7 estimator is written out again
    here from its definition, in the other algebraic form (`x[j](1-g) + x[j+1]g`)."""
    nets = [row.net_pnl_paise for row in _pilot_rows() if row.executed]
    assert len(nets) == 146

    q1 = _reviewer_quantile(nets, Fraction(1, 4))
    q3 = _reviewer_quantile(nets, Fraction(3, 4))
    assert (q1, q3) == (Fraction(-109_900), Fraction(99_720))
    assert pf.quantile(nets, Fraction(1, 4)) == q1
    assert pf.quantile(nets, Fraction(3, 4)) == q3

    iqr = q3 - q1
    assert iqr == Fraction(209_620)
    assert q1 - Fraction(3, 2) * iqr == Fraction(-424_330)
    assert q3 + Fraction(3, 2) * iqr == Fraction(414_150)

    found = pf.outliers(_pilot_rows())
    assert (found.lower_fence_paise, found.upper_fence_paise) == (
        Fraction(-424_330),
        Fraction(414_150),
    )
    assert found.count == 0 and found.population == 146
    # WHY it is zero, said as a property rather than an absence: a fixed-R trade is bounded by
    # construction, and both bounds sit well inside the fences.
    assert min(nets) == -110_000 and max(nets) == 290_000
    assert found.lower_fence_paise < min(nets) and max(nets) < found.upper_fence_paise


def test_a_trade_exactly_on_the_LOWER_fence_is_not_an_outlier_either() -> None:
    """The build covers the UPPER fence boundary only. This repo's own persona checklist puts
    flipped boundary operators first, and the two tails are separate branches of `outliers`."""
    from tests.test_portfolio import COST, D1, trade  # the build's own fixture helpers

    nets = (-180_000, -80_000, -60_000, -40_000, -20_000, 0, 20_000, 40_000, 60_000)
    rows = tuple(
        trade(D1 + timedelta(days=i), f"S{i}", LONG, 10, 100_000, net + COST)
        for i, net in enumerate(nets)
    )
    found = pf.outliers(rows)
    # Q1 = x[2] = -60,000; Q3 = x[6] = +20,000; IQR 80,000; lower fence exactly -180,000
    assert found.lower_fence_paise == Fraction(-180_000)
    assert found.count == 0
    assert all(item.net_paise != -180_000 for item in found.trades)

    # one paise past it IS an outlier, on the same tail -- the boundary is where it is claimed
    past = rows[:1] + rows[1:]
    past = (trade(D1, "S0", LONG, 10, 100_000, -180_001 + COST),) + rows[1:]
    beyond = pf.outliers(past)
    assert beyond.count == 1 and beyond.below_count == 1
    assert beyond.trades[0].side_of_fence == "below"


def test_the_outlier_shares_are_each_taken_against_their_own_pot() -> None:
    """A share above 1 or below 0 would mean the tail was divided by the wrong pot. Both are
    ratios of a tail's net sum to the net-basis pot it belongs to, so both sit in [0, 1]."""
    from tests.test_portfolio import outlier_rows

    found = pf.outliers(outlier_rows())
    assert found.share_of_gross_profit == Fraction(50, 53)
    assert found.share_of_gross_loss == Fraction(9, 11)
    for share in (found.share_of_gross_profit, found.share_of_gross_loss):
        assert 0 <= share <= 1


# ==============================================================================================
# 3. The E13 basis, measured end to end on the pilot
# ==============================================================================================


def test_the_net_basis_identities_hold_on_the_committed_pilot_ledger() -> None:
    """The identities the ruling exists to buy, checked on the real 146 rather than on four
    hand-built rows: both pots are net sums over net populations, their sum IS the net PnL, and
    the two averages multiply back to their own pots."""
    rows = _pilot_rows()
    m = pf.metrics(rows, initial_capital_paise=CAPITAL)

    assert (m.winners, m.losers, m.flat, m.total_trades) == (45, 101, 0, 146)
    assert m.gross_profit_paise == 9_648_960
    assert m.gross_loss_paise == -9_842_455
    assert m.net_pnl_paise == m.gross_profit_paise + m.gross_loss_paise == -193_495
    assert m.winners * m.avg_profit_paise == m.gross_profit_paise
    assert m.losers * m.avg_loss_paise == m.gross_loss_paise
    assert m.profit_factor == Fraction(1_929_792, 1_968_491)
    assert m.profit_factor < 1  # it no longer reads "profitable" above a negative net PnL

    # the before-costs pair, and the only arithmetic that reconciles the two bases
    assert m.before_cost_profit_paise == 10_109_920
    assert m.before_cost_loss_paise == -8_843_415
    assert (
        m.before_cost_profit_paise + m.before_cost_loss_paise - m.commission_paise
        == m.net_pnl_paise
    )
    # both largest-* shares are NET over NET
    assert m.largest_win_pct_of_gross_profit == Fraction(290_000, 9_648_960)
    assert m.largest_loss_pct_of_gross_loss == Fraction(-110_000, -9_842_455)


def test_the_mfe_mae_pair_is_a_BEFORE_COST_measure_in_a_net_basis_table() -> None:
    """**PINS A MEASURED FACT (REVIEW_9A_2 finding Q3, severity LOW) -- read before trusting
    section 8's excursion invariant.**

    The pack declares one NET basis and then prints avg/largest MFE and MAE, which carry no
    Rs 100. On 20 of the 146 rows the NET PnL therefore falls OUTSIDE [MAE, MFE]; the invariant
    that says "realized PnL sits inside [MAE, MFE]" is true of the GROSS PnL only. No number is
    wrong; the basis of these two rows is undeclared. Flip the count assertion if 9B restates
    the excursions on the net basis."""
    rows = [row for row in _pilot_rows() if row.executed]
    gross_inside = sum(
        1 for row in rows if row.mae_paise <= row.gross_pnl_paise <= row.mfe_paise
    )
    net_inside = sum(
        1 for row in rows if row.mae_paise <= row.net_pnl_paise <= row.mfe_paise
    )
    assert gross_inside == 146  # the invariant the pack asserts, and it holds -- on GROSS
    assert net_inside == 126  # <-- 20 rows a net-basis reader would call violations


def test_the_pack_still_carries_a_third_before_costs_figure() -> None:
    """**PINS A DEFECT (REVIEW_9A_2 finding Q1) -- flip this when it is fixed.**

    The ruling allows before-costs totals "ONCE, labelled". The pack's metric table carries one
    such line and section 3's reconciliation carries two more, which the definitions block
    discloses as "those two rows". There is a THIRD -- section 3's "Gross PnL Rs 12,665.05",
    the same 146 trades before the same costs -- and it is neither labelled nor covered by the
    stated exception, so the pack's own "the only before-costs figures in this pack" is not
    literally true. It cannot mislead the way REVIEW_9A Q1 did (the two rows beneath it are
    "Costs paid" and "Net PnL", which makes the triple self-explanatory), which is why this is
    a finding and not the verdict."""
    text = PACK.read_text(encoding="utf-8")
    labelled = [
        line
        for line in text.splitlines()
        if line.startswith("|") and "Rs 100/trade costs" in line.replace("BEFORE", "before")
    ]
    assert len(labelled) == 3  # two in section 3, one in the metric table

    unlabelled = [
        line
        for line in text.splitlines()
        if line.startswith("| Gross PnL |") and "before" not in line
    ]
    assert unlabelled == ["| Gross PnL | Rs 12,665.05 | Rs 12,665.05 | YES |"]  # <-- the third
    assert "the only before-costs figures in this pack" in text  # ...and the claim it breaks
    assert 'chunk 8\'s own "gross profit / gross loss" are before-costs totals' in text
    assert "Those two rows are labelled" in text  # the exception names two, not three


def test_the_fifteen_minute_run_up_prints_a_giveback_as_a_recovery() -> None:
    """**PINS A DEFECT (REVIEW_9A_2 finding Q2, severity LOW) -- flip when it is fixed.**

    `path_max_run_up.recovered` is the day the rise was GIVEN BACK (the first later observation
    at or below the trough) -- the correct mirror, and Q5's whole point. The pack prints it with
    the drawdown's vocabulary: the close-to-close run-up row says "given back never in the
    window" and the 15-minute run-up row beside it says "never recovered in the window" for the
    same quantity. A reader comparing the two rows is told two different things about one
    number."""
    text = PACK.read_text(encoding="utf-8")
    close_to_close = [ln for ln in text.splitlines() if ln.startswith("| Max run-up (equity")]
    path_line = [ln for ln in text.splitlines() if ln.startswith("| Max run-up (intra-trade")]
    assert len(close_to_close) == 1 and len(path_line) == 1
    assert "given back never in the window" in close_to_close[0]
    assert "never recovered in the window" in path_line[0]  # <-- drawdown vocabulary
    assert "given back" not in path_line[0]

    # the field itself IS the giveback, which is what makes the wording the defect:
    source = inspect.getsource(pf.path_max_run_up)
    assert "point.equity_paise <= level" in source


# ==============================================================================================
# 4. C1 -- the widened tripwire, and what it cannot see
# ==============================================================================================


def test_the_widened_tripwire_scans_the_whole_package_not_a_sample() -> None:
    """The chunk-8 tripwire scanned `simulate.py` alone, which is exactly how the capital hid in
    `portfolio.py` for a chunk. This asserts the scan's REACH -- every module file in the
    package -- independently of the tripwire's own glob."""
    package = REPO_ROOT / "src" / "acumen"
    modules = sorted(package.glob("*.py"))
    assert len(modules) >= 34
    assert {"portfolio.py", "simulate.py", "backtest.py", "poc.py"} <= {
        module.name for module in modules
    }

    config = load_config(include_env=False)
    forbidden = {
        config.require_risk_per_trade_paise(),
        int(config.risk_per_trade),
        config.cost_per_trade_paise(),
        config.initial_capital_paise(),
        int(config.initial_capital),
    }
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }
        assert not (literals & forbidden), module.name


def test_the_tripwire_sees_a_typed_magnitude_and_not_a_computed_one() -> None:
    """**PINS A MEASURED LIMIT (REVIEW_9A_2 finding C2, severity INFO).**

    The tripwire is a scan of integer LITERALS, so it catches an amount that is typed and not
    one that is computed -- and this fix span itself contains the worked precedent, rewriting
    `ratio * 10000` as `ratio * 100 * 100` to get out from under it (decision B200). The limit
    is real and the tripwire is still strictly stronger than the one it replaced; it belongs
    written down beside it rather than discovered later."""

    def literals(source: str) -> set[int]:
        return {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }

    assert 10_000_000 in literals("BUDGET = 10_000_000")
    assert 10_000_000 not in literals("BUDGET = 10 ** 7")  # <-- invisible to the tripwire
    assert 10_000_000 not in literals("BUDGET = 5_000_000 * 2")
    assert 10_000_000 not in literals("BUDGET = int(1e7)")


def test_the_percent_rewrite_moved_no_value() -> None:
    """B200's collateral edit: `int(ratio * 10000)` became `int(ratio * 100 * 100)`. The
    arithmetic is Fraction, so the two are the same number -- asserted over a dense grid of the
    (pass, total) pairs the residual register can actually hold, not argued."""
    for total in range(1, 200):
        for passed in range(0, total + 1):
            ratio = Fraction(passed, total)
            assert int(ratio * 10_000) == int(ratio * 100 * 100)
            entry = bt.ResidualEntry(
                symbol="X",
                status="settled",
                gate1p_pass=passed,
                gate1p_total=total,
                gate1p_no_oracle=0,
                residual_reason="probe",
            )
            assert entry.as_dict()["price_proven_pct_x100"] == int(ratio * 10_000)


# ==============================================================================================
# 5. C4 -- the refusal chain the fix rewrote
# ==============================================================================================


def test_walk_symbol_decides_exactly_two_of_the_documented_refusal_reasons() -> None:
    """**PINS A DEFECT (REVIEW_9A_2 finding C1, severity LOW) -- flip when it is fixed.**

    REVIEW_9A C4 was that the documented chain omitted `REASON_BIAS_UNRESOLVED`. The rewritten
    chain names it correctly and in the right position -- and then adds a sentence saying "the
    first three are decided by `BacktestRunner.walk_symbol`". Exactly TWO are: E2 and the bias
    failure. "No minutes" is `acumen.signal_engine`'s first reason, not the runner's. The chain
    itself is right; the attribution beneath it is off by one, which is the same class of slip
    C4 was."""
    module_doc = bt.__doc__ or ""
    assert "CONTEXT 7-E2 non-standard session" in module_doc
    assert "REASON_BIAS_UNRESOLVED" in module_doc
    assert module_doc.index("REASON_BIAS_UNRESOLVED") < module_doc.index("no minutes")
    assert "The first three are decided by" in module_doc  # <-- the claim

    # ...and what the code actually does: walk_symbol emits E2 and BIAS_UNRESOLVED, nothing else
    source = inspect.getsource(bt.BacktestRunner.walk_symbol)
    emitted = set(re.findall(r"REASON_[A-Z0-9_]+", source))
    assert emitted == {"REASON_E2_NON_STANDARD", "REASON_BIAS_UNRESOLVED"}
    assert "NO_MINUTES" not in inspect.getsource(bt)  # the runner owns no such reason


def test_the_refusal_chain_lists_every_reason_the_two_layers_can_emit() -> None:
    """The control for the probe above: whatever the attribution sentence says, no reason a
    layer can emit is missing from the documented chain."""
    from acumen import signal_engine as se

    module_doc = bt.__doc__ or ""
    for phrase in ("no minutes", "gate 1", "gate 2", "gate 1P", "suppressed", "no POC"):
        assert phrase in module_doc, phrase
    assert se.NOT_EVALUATED_NO_MINUTES  # the constant the chain's "no minutes" refers to


# ==============================================================================================
# 6. The evidence pack's own regenerability
# ==============================================================================================


def test_the_outlier_line_prints_every_quantity_the_ruling_names_when_a_tail_fires() -> None:
    """**CLOSES A COVERAGE GAP (REVIEW_9A_2 finding C4).**

    The pilot has zero outliers, so the committed pack only ever exercises the EMPTY branch of
    `_outlier_line`. The branch chunk 9B will actually hit -- a full-history run almost
    certainly has both tails -- had never been executed by any test. The Q-16(a) ruling names
    four things to report: count, summed net PnL, the two shares, and the definition. This
    asserts all four reach the page."""
    from acumen import pilot_evidence as pe
    from tests.test_portfolio import outlier_rows

    line = pe._outlier_line(pf.outliers(outlier_rows()))
    assert line.startswith("| Outliers | **2** of 9 executed trades")
    assert "summed net Rs 1,000.00" in line
    assert "1 above Rs 1,400.00 (Rs 10,000.00, 94.34% of gross profit)" in line
    assert "1 below -Rs 1,800.00 (-Rs 9,000.00, 81.82% of gross loss)" in line
    assert "Q1 -Rs 600.00, Q3 Rs 200.00, IQR Rs 800.00" in line
    assert pf.OUTLIER_DEFINITION in line


def test_the_path_line_prints_a_recovery_and_says_so_when_no_path_was_supplied() -> None:
    """**CLOSES A COVERAGE GAP (REVIEW_9A_2 finding C4).**

    Two more branches the pilot never reaches: an excursion that DOES recover inside the window
    (the pilot's does not), and a metric set handed no path at all. Both are ordinary for 9B."""
    from acumen import pilot_evidence as pe
    from tests.test_portfolio import CAPITAL as FIXTURE_CAPITAL
    from tests.test_portfolio import built_paths, path_rows

    rows = path_rows()
    with_path = pf.metrics(
        rows, initial_capital_paise=FIXTURE_CAPITAL, paths=built_paths()
    )
    line = pe._path_line("Max drawdown", with_path.intraday_max_drawdown, with_path)
    assert "Rs 2,500.00 (2.48%)" in line
    assert "2026-01-01 12:15 -> 2026-01-01 12:30" in line
    assert "1 observation(s) of 7" in line
    assert "recovered 2026-01-01 12:45" in line  # <-- the branch the pilot never takes
    assert pf.INTRADAY_PATH_LIMIT in line

    without = pf.metrics(rows, initial_capital_paise=FIXTURE_CAPITAL)
    blank = pe._path_line("Max run-up", without.intraday_max_run_up, without)
    assert blank == (
        "| Max run-up (intra-trade, 15-min path) | NOT COMPUTED -- "
        f"{pf.INTRADAY_PATH_NOT_SUPPLIED} |"
    )

    # and the three ways a path observation can be named
    assert pe._path_stamp(None) == "opening capital"
    day_close = pf.PathPoint(day=DAY, stamp=None, equity_paise=1, open_positions=0)
    assert pe._path_stamp(day_close) == "2026-03-02 close"
    stamped = pf.PathPoint(
        day=DAY, stamp=datetime(2026, 3, 2, 13, 15), equity_paise=1, open_positions=0
    )
    assert pe._path_stamp(stamped) == "2026-03-02 13:15"


def test_the_corporate_action_day_cache_refuses_a_stale_cache_offline(tmp_path) -> None:
    """**PINS A MEASURED FACT (REVIEW_9A_2 finding C3, severity LOW).**

    `fetch_corp_action_history`'s docstring promises that "with allow_network=False this reads
    only the day-cache, so a reviewer with the frozen cache gets a deterministic history and a
    bare clone gets an empty one". Neither half holds: a cache written on any EARLIER day
    raises, and a missing cache raises too. That is why the committed pack -- whose own header
    says "Regenerate with: python docs/evidence/chunk9a_pilot.py" -- cannot be regenerated on
    any day after its cache's `fetched_on`, which is the day REVIEW_8 finding C2's rule has to
    be checked on. Flip this when the evidence path is made age-independent."""
    from acumen import nse_http

    cache = tmp_path / "probe.json"
    nse_http.write_cache(cache, {"rows": []}, url="https://example.invalid/x",
                         fetched_on=date(2026, 7, 29))

    # same day: served offline, no network
    assert nse_http.cached_json(
        "https://example.invalid/x", cache, today=date(2026, 7, 29), allow_network=False
    ) == {"rows": []}

    # ONE day later, the same frozen bytes: refused rather than served or emptied
    with pytest.raises(nse_http.NseFetchError, match="the cache is from 2026-07-29"):
        nse_http.cached_json(
            "https://example.invalid/x", cache, today=date(2026, 7, 30), allow_network=False
        )
    with pytest.raises(nse_http.NseFetchError, match="no cache file exists"):
        nse_http.cached_json(
            "https://example.invalid/y",
            tmp_path / "absent.json",
            today=date(2026, 7, 30),
            allow_network=False,
        )
