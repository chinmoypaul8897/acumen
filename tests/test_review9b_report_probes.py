"""Probes kept by REVIEW_9B_REPORT -- the QC of the chunk-9B backtest report (`41f3e3e..796c39d`).

Each one exists because this review ran a mutant that the shipped 2,140-test suite did NOT catch,
or because a claim the report publishes was pinned by prose rather than by a test. Each was
mutation-verified: it fails on its mutant and passes on restoration.

The review fixes nothing. These are tests only -- no `src/` file, no existing test, no fixture and
no evidence artefact was modified by the session that wrote them.

The four the mutation matrix demanded:

* the **Sharpe and Sortino** refusal (`crosses_zero` -> `RATIO_CROSSES_ZERO`). This is the more
  dangerous half of the defect the report session headlines -- Sharpe printed **+0.5833** for a
  strategy that lost 168x its capital -- and the shipped test covers only `_excursion_pct`.
  Mutants M2 and M3 (print the ratio unconditionally) survived the whole suite.
* section **12f**'s zero-counter list, which the session says it made COMPUTED rather than
  asserted. Mutant M7 (assert three) survived.
* section **12c**'s "N of the five appear at ZERO" sentence, same fix, same commit. Mutant M8
  survived.
* section **12a**'s gap witnesses, which must be the earliest and latest by DATE rather than by
  the ledger's symbol-major order. Mutant M9 survived.

Plus four that pin findings this review raised, so the next session inherits them as red tests
rather than as prose:

* the money magnitudes the generator types into its own PROSE (finding C4);
* three more section-12 sentences that still ASSERT a count the ledger could supply (finding C6);
* the benchmark's "share-count factors" count, which includes special DIVIDENDS (finding Q2);
* the Tukey fences, which do NOT always sit outside a fixed-R band (finding Q1).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from acumen import backtest as bt
from acumen import portfolio as pf
from acumen import report_9b as r9
from acumen.config import load_config
from acumen.signals import LONG, SHORT

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPITAL = 10_000_000
COST = 10_000


def _render(section, **pieces) -> str:
    lines: list[str] = []
    section(lines.append, **pieces)
    return "\n".join(lines)


def _trade(day: date, symbol: str, side: str, qty: int, entry: int, gross: int) -> bt.LedgerRow:
    base = datetime.combine(day, datetime.min.time())
    return bt.LedgerRow(
        symbol=symbol, day=day, status="evaluated", reason="evaluated", side=side,
        outcome="entered", consumed=True, signalled=True, executed=True,
        entry_paise=entry, stop_paise=entry - 100, target_paise=entry + 300,
        per_share_risk_paise=100, entry_close_stamp=base + timedelta(hours=12),
        exit_kind="target-hit", exit_paise=entry + 300,
        exit_close_stamp=base + timedelta(hours=14), qty=qty, notional_paise=qty * entry,
        gross_pnl_paise=gross, cost_paise=COST, net_pnl_paise=gross - COST,
        mfe_paise=max(0, gross), mae_paise=min(0, gross),
    )


# --- P1/P2: the Sharpe and Sortino REFUSAL (mutants M2, M3) ------------------------------------


def _columns_and_days() -> tuple[dict[str, pf.Metrics], tuple[date, ...]]:
    """A tiny run whose equity NEVER crosses zero, so both ratios are genuinely computable."""
    days = tuple(date(2020, 1, d) for d in (6, 7, 8, 9))
    rows = (
        _trade(days[0], "AAA", LONG, 10, 100_000, 60_000),
        _trade(days[1], "AAA", SHORT, 10, 100_000, -20_000),
        _trade(days[2], "AAA", LONG, 10, 100_000, 90_000),
        _trade(days[3], "AAA", SHORT, 10, 100_000, -30_000),
    )
    columns = {
        "All": pf.metrics(rows, label="All", initial_capital_paise=CAPITAL, days=days),
        "Long": pf.metrics(pf.for_side(rows, LONG), label="Long",
                           initial_capital_paise=CAPITAL, days=days),
        "Short": pf.metrics(pf.for_side(rows, SHORT), label="Short",
                            initial_capital_paise=CAPITAL, days=days),
    }
    return columns, days


def test_sharpe_and_sortino_are_REFUSED_on_a_column_whose_equity_crosses_zero() -> None:
    """The dangerous half of the report session's defect 2, which its own test does not reach.

    A daily return is `change / prior equity`. Once the equity series crosses zero the
    denominator changes sign, so a LOSS on a negative base divides to a POSITIVE return -- and
    Sharpe came out **+0.5833** for a strategy that lost 168x its capital. The shipped suite
    pins `_excursion_pct` and nothing else: reverting the Sharpe branch, the Sortino branch, or
    both leaves all 2,140 tests green.

    Both rows must carry the REASON, on every column that crosses zero.
    """
    columns, _days = _columns_and_days()
    text = _render(r9._section_e13, columns=columns,
                   crosses_zero={"All": True, "Long": True, "Short": True})

    sharpe = [line for line in text.splitlines() if line.startswith("| Sharpe")]
    sortino = [line for line in text.splitlines() if line.startswith("| Sortino")]
    assert len(sharpe) == 1 and len(sortino) == 1
    for row in (sharpe[0], sortino[0]):
        assert row.count(r9.RATIO_CROSSES_ZERO) == 3, (
            "every column that crosses zero must carry the reason, not a number: " + row
        )
        # and no ratio-shaped number may survive anywhere in the row
        assert not re.search(r"\|\s*-?\d+\.\d{4}\s*\|", row), row


def test_sharpe_and_sortino_still_PRINT_when_the_equity_never_crosses_zero() -> None:
    """The control. A refusal that fires unconditionally would be its own defect."""
    columns, _days = _columns_and_days()
    text = _render(r9._section_e13, columns=columns,
                   crosses_zero={"All": False, "Long": False, "Short": False})

    sharpe = next(line for line in text.splitlines() if line.startswith("| Sharpe"))
    sortino = next(line for line in text.splitlines() if line.startswith("| Sortino"))
    for row in (sharpe, sortino):
        assert r9.RATIO_CROSSES_ZERO not in row
        assert re.search(r"\|\s*-?\d+\.\d{4}\s*\|", row), (
            "a computable ratio must print as a number: " + row
        )
    assert columns["All"].sharpe is not None and columns["All"].sortino is not None


# --- P3/P4/P5: section 12's computed sentences (mutants M7, M8, M9) ----------------------------


def _witnesses(**edits) -> r9.Witnesses:
    base = dict(
        gap_days=(("BBB", "2016-10-06"), ("AAA", "2020-01-06")),
        gap_by_year={"2016": 1, "2020": 1}, gap_exit_kinds={"target-hit": 2},
        gap_net_paise=1_000, gap_winners=1, qty_zero=(), demerger=(), suppressed_rows=0,
        gate2_days=(), ungated_by_symbol={}, out_of_session_by_date={}, out_of_session_by_rule={},
        no_break_carry=(), side_never_set=(), tie_days=0, e10_days=0, both_touched=0,
        square_off_at_entry=0, signal_unsizable=0, malformed_bar_days=0, rule3_no_minute_days=0,
        no_poc_days=(),
    )
    base.update(edits)
    return r9.Witnesses(**base)


def _run(rare_shapes: dict[str, int], witnesses: r9.Witnesses) -> r9.RunData:
    return r9.RunData(
        manifest={}, executed=(), days=(), walked=100, usable=100, refused=0, outcomes={},
        reasons={}, exit_kinds={}, rare_shapes=rare_shapes, flags={}, duplicate_keys=0,
        symbols=(), totals={}, witnesses=witnesses, ledger_sha256="", ledger_bytes=0,
        manifest_sha256="",
    )


#: The eleven labels the manifest's rare-shape block carries, in the generator's own words.
ELEVEN = (
    "E10 fallback reference (no 11:00-stamped candle)",
    "both-touched candles (stop won)",
    "day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)",
    "gap entries",
    "qty-zero unsizable days",
    "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))",
    "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)",
    "rule-3 day with no 1-minute data (carried, CONTEXT 3.2)",
    "rule-3 tie bias days",
    "signal-unsizable (degenerate) days",
    "square-offs priced at the entry candle",
)


def test_section_12f_COMPUTES_which_counters_are_zero_rather_than_asserting_a_number() -> None:
    """Defect 3's second half: 12f claimed THREE zero counters while printing 30 for one of them.

    The fix is that the list comes from `run.rare_shapes`. Nothing pinned it -- a mutant that
    hardcodes three labels passes all 2,140 tests. This drives the section at two different
    zero-counts and asserts the sentence and the bullet list both follow the data.
    """
    for zeros in (2, 5):
        counts = {label: (0 if i < zeros else i + 1) for i, label in enumerate(ELEVEN)}
        text = _render(r9._section_rare_shapes, run=_run(counts, _witnesses()))
        assert f"**{zeros} of the eleven counters are ZERO**" in text, text[-900:]
        listed = {label for label in ELEVEN if f"\n* {label}" in text}
        assert listed == {label for label, count in counts.items() if count == 0}


def test_section_12c_COMPUTES_how_many_of_the_five_Q17_dates_this_run_flagged() -> None:
    """The same fix, in the same commit, one section up -- and equally unpinned.

    The sentence must name the dates the RUN flagged at zero, not a remembered count.
    """
    all_zero = _render(r9._section_rare_shapes, run=_run({label: 1 for label in ELEVEN},
                                                        _witnesses()))
    assert "5 of the five" in all_zero
    for day, _affected, _with_data in r9.Q17_MARKET_WIDE:
        assert day in all_zero

    # one date flagged heavily, one thinly: the sentence must drop the first from the zero list
    heavy, thin = r9.Q17_MARKET_WIDE[0][0], r9.Q17_MARKET_WIDE[1][0]
    text = _render(
        r9._section_rare_shapes,
        run=_run({label: 1 for label in ELEVEN},
                 _witnesses(out_of_session_by_date={heavy: 123, thin: 4})),
    )
    assert "3 of the five" in text
    listed = text.split("3 of the five (")[1].split(") therefore appear at ZERO")[0]
    assert heavy not in listed and thin not in listed, listed
    assert set(listed.split(", ")) == {day for day, _a, _w in r9.Q17_MARKET_WIDE[2:]}
    assert f"1 at a handful ({thin} at 4)" in text


def test_section_12a_names_the_gap_witnesses_by_DATE_not_by_the_ledger_s_row_order() -> None:
    """The ledger is symbol-major, so its first gap row is not the earliest gap DAY.

    The witnesses list here is deliberately built in ledger order (BBB's 2016 day first, AAA's
    2020 day second) with the SYMBOLS sorted the other way, so an implementation that takes
    `gap_days[0]` and `gap_days[-1]` gets the right answer by accident. A third row breaks that.
    """
    witnesses = _witnesses(
        gap_days=(("BBB", "2020-01-06"), ("AAA", "2016-10-06"), ("CCC", "2026-07-27")),
        gap_by_year={"2016": 1, "2020": 1, "2026": 1},
        gap_exit_kinds={"target-hit": 3}, gap_winners=2,
    )
    text = _render(r9._section_rare_shapes, run=_run({label: 1 for label in ELEVEN}, witnesses))
    sentence = next(line for line in text.splitlines() if "by DATE rather than" in line)
    assert "AAA 2016-10-06" in sentence and "CCC 2026-07-27" in sentence
    assert "BBB 2020-01-06" not in sentence


# --- P6: defect 1's CALL SITE, which its own test does not reach (mutant M1) -------------------


def test_build_everything_uses_the_walked_day_split_and_NOT_the_convenience_wrapper() -> None:
    """The shipped test pins the HELPER. Nothing pins that the report actually calls it.

    `test_the_E13_columns_are_indexed_on_EVERY_WALKED_DAY_not_only_trading_days` calls
    `_side_split_over_walked_days` directly and proves it right. It does not touch
    `build_everything`, which is where the defect lived: putting `pf.side_split(run.executed, ...)`
    back at the call site reintroduces the exact 2,415-vs-2,428 bug and leaves all 2,140 tests
    green -- the helper stays correct and stops being used.

    `build_everything` is the I/O entry point and cannot be driven from a unit test, so the pin
    is structural: read the function's own call graph out of the AST.
    """
    import ast

    source = (REPO_ROOT / "src" / "acumen" / "report_9b.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_everything"
    )
    called: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            target = node.func
            called.add(target.attr if isinstance(target, ast.Attribute) else
                       getattr(target, "id", ""))

    assert "_side_split_over_walked_days" in called, (
        "build_everything no longer builds the E13 columns on the WALKED day index"
    )
    assert "side_split" not in called, (
        "build_everything calls pf.side_split, which derives its index from the rows it is "
        "handed -- over executed rows alone that is the 2,415 days that TRADED, dropping the 13 "
        "flat ones (the exact defect REVIEW_9B_REPORT's B279 records as fixed)"
    )


# --- P7: the 15-minute path's run-up order, which the close-to-close test does not cover (M6) ---


def test_a_run_up_on_the_15_MINUTE_PATH_is_printed_TROUGH_first_too() -> None:
    """Defect 3 was fixed on BOTH excursion renderers; only the close-to-close one is tested.

    `_path_excursion` has its own `rising` branch and its own mutant: dropping it prints the
    later stamp first on the path run-up row, and the shipped suite stays green because its one
    run-up test drives `_excursion` only.
    """
    trough = pf.PathPoint(date(2024, 11, 5), datetime(2024, 11, 5, 13, 30), -1_000, 2)
    peak = pf.PathPoint(date(2025, 1, 14), datetime(2025, 1, 14, 12, 30), 40_000, 3)
    rise = pf.PathExcursion(41_000, None, peak, trough, 795, None)

    text = r9._path_excursion(rise, observations=40_981, recovery_word="given back", rising=True)
    assert text.index("2024-11-05 13:30") < text.index("2025-01-14 12:30"), text

    fall = pf.PathExcursion(41_000, None, trough, peak, 795, None)
    text = r9._path_excursion(fall, observations=40_981, recovery_word="recovered")
    assert text.index("2024-11-05 13:30") < text.index("2025-01-14 12:30"), text

    # ...and the caller must still ask for it on BOTH run-up rows, close-to-close and path.
    source = (REPO_ROOT / "src" / "acumen" / "report_9b.py").read_text(encoding="utf-8")
    equity = source.split("def _section_equity")[1].split("\ndef ")[0]
    assert equity.count("rising=True") == 2, (
        "both run-up rows -- close-to-close and 15-minute path -- must print trough-first"
    )


# --- P8: finding C4 -- the money magnitudes the generator types into its own prose -------------


def test_the_money_magnitudes_typed_into_the_report_s_PROSE_match_the_configured_amounts() -> None:
    """REVIEW_9B_REPORT finding C4.

    Section 2's Risk / Cost / Capital rows are computed from the RUN's own spec block. The prose
    around them is not: `report_9b.py` writes "Rs 100.00", "Rs 1,000.00" and "Rs 1,00,000" as
    string literals at eight sites, including inside the qty-zero table's own "why" column. The
    AST money tripwire in `tests/test_config.py` walks every module in the package but scans
    INT CONSTANTS, and its own docstring says a magnitude spelled another way walks past it -- a
    string is exactly that.

    So this ties the strings to the config. If `risk_per_trade` or `cost_per_trade` ever moves,
    this test goes red and the prose must move with the table, instead of the report quietly
    disagreeing with itself.
    """
    config = load_config(include_env=False)
    source = (REPO_ROOT / "src" / "acumen" / "report_9b.py").read_text(encoding="utf-8")

    risk = pf.format_paise(config.require_risk_per_trade_paise())      # "Rs 1,000.00"
    cost = pf.format_paise(config.cost_per_trade_paise())              # "Rs 100.00"
    capital_lakh = "Rs 1,00,000"                                       # the Indian-format prose

    assert source.count(risk) >= 1, "the risk magnitude is no longer spelled as the config says"
    assert source.count(cost) >= 1, "the cost magnitude is no longer spelled as the config says"
    assert source.count(capital_lakh) >= 1
    assert config.initial_capital_paise() == 10_000_000, (
        "the prose spells the capital as Rs 1,00,000; the config no longer agrees"
    )

    # No OTHER money-shaped literal may reach the RENDERED page: a second magnitude would mean
    # the report is quoting an amount that comes from nowhere. Comment lines are excluded --
    # `NO_PERCENT_BASE`'s own note illustrates with this run's peak equity and prints nothing.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    spelled = {m.group(0) for m in re.finditer(r"Rs [\d,]+\.\d\d", code)}
    assert spelled == {risk, cost}, spelled


# --- P7: finding C6 -- section 12 sentences that still ASSERT a count --------------------------


def test_three_section_12_sentences_still_ASSERT_counts_the_ledger_could_supply() -> None:
    """REVIEW_9B_REPORT finding C6, pinned as a test rather than left as prose.

    The report session made 12f's zero list and 12c's tail COMPUTED. Three sentences beside them
    were not converted and still hardcode this run's answers: 12b's "188,347 signalled days" and
    "it happened twice", and 12e's "Two days ... three more". On THIS run all three are correct.
    They are still the same defect class, in the same section, and a re-run with one more
    qty-zero day would print a false sentence with a true table beneath it.

    This test asserts the strings are STILL THERE, so the day someone converts them it goes red
    and gets deleted deliberately -- and so a re-run that moves the counts cannot ship silently.
    """
    source = (REPO_ROOT / "src" / "acumen" / "report_9b.py").read_text(encoding="utf-8")
    for asserted in ("188,347 signalled days it happened twice",
                     "days in the whole span are that case, and the run carries three more"):
        assert asserted in source, (
            f"{asserted!r} is gone -- if it was made computed, delete this test and say so"
        )

    # ...and the table beneath each one is genuinely driven by the data, which is the contrast.
    witnesses = _witnesses(qty_zero=(("AAA", "2020-01-06", 101_970),
                                     ("BBB", "2021-05-20", 117_330),
                                     ("CCC", "2022-03-04", 130_000)))
    text = _render(r9._section_rare_shapes, run=_run({label: 1 for label in ELEVEN}, witnesses))
    assert text.count("floors to 0") == 3, "the TABLE follows the data"
    assert "it happened twice" in text, "the SENTENCE above it does not -- that is the finding"


# --- P8: finding Q2 -- what is actually inside the benchmark's factor count --------------------


def test_the_benchmark_s_share_count_factor_TALLY_also_counts_special_dividends() -> None:
    """REVIEW_9B_REPORT finding Q2, and the architect's Q-23 ruling makes it load-bearing.

    Section 10 calls its tally "share-count factors". `benchmark_pair` counts every non-unit
    factor in the run's table, and CONTEXT 4.2 gives a SPECIAL dividend a factor too. On the real
    run 308 of the 433 are special dividends and only 125 are bonus/split/rights -- worth
    +25.23 pp of the ruled 491.90%.

    A holder's UNITS do not change on a dividend, so this pins the behaviour as it is (the ruling
    names 491.90% "as generated") while making the mixing visible to the next session.
    """
    first, last = date(2020, 1, 1), date(2020, 12, 31)
    manifest = {
        "factor_table": {
            "per_symbol": {
                "AAA": {"in_span": [
                    {"ex_date": "2020-06-01", "k": "1/2", "kind": "bonus",
                     "classification": ""},
                    {"ex_date": "2020-09-01", "k": "24/25", "kind": "dividend",
                     "classification": "special"},
                    {"ex_date": "2020-10-01", "k": "1", "kind": "dividend",
                     "classification": "ordinary"},
                ]}
            }
        }
    }

    class _Store:
        def daily(self, symbol, first_day, last_day):
            import pandas as pd

            return pd.DataFrame({"trade_date": [first, last], "close_paise": [100_00, 100_00]})

    pair = r9.benchmark_pair(_Store(), manifest, symbols=("AAA",), first_day=first,
                             last_day=last, initial_capital_paise=CAPITAL)

    assert pair.events_applied == 2, (
        "the tally counts the bonus AND the special dividend; only the bonus moves a share count"
    )
    assert pair.adjusted_symbols == 1
    # the ordinary dividend (k == 1) is correctly invisible on both sides
    assert pair.raw.total_return == 0
    # 1/2 x 24/25 = 12/25 -- the dividend factor is inside the published multiple
    assert pair.adjusted.total_return == Fraction(25, 12) - 1


# --- P9: finding Q1 -- a fixed-R band does NOT always sit inside its own fences ----------------


def test_the_tukey_fences_do_NOT_always_sit_outside_a_fixed_R_band() -> None:
    """REVIEW_9B_REPORT finding Q1, as arithmetic rather than as prose.

    Section 6a closes with "a fixed-R strategy bounds its own trades ... and the fences sit
    outside it". On the real run's LONG column they do not: Q3 Rs 440.00 and IQR Rs 1,539.60 put
    the upper fence at Rs 2,749.40, BELOW the Rs 2,900.00 maximum win, and 13,243 long trades are
    outliers worth 76.48% of that column's gross profit.

    Reproduced here on the smallest population that shows it: a fixed-R book that loses often
    enough for Q3 to sit low. The claim is a property of the DISTRIBUTION, not of the sizing rule.
    """
    stop, target = -110_000, 290_000  # the run's own structural band, in paise
    nets = [stop] * 70 + [0] * 10 + [target] * 20

    q1 = pf.quantile(sorted(nets), Fraction(1, 4))
    q3 = pf.quantile(sorted(nets), Fraction(3, 4))
    upper = q3 + Fraction(3, 2) * (q3 - q1)

    assert max(nets) == target
    assert upper < target, "the upper fence sits INSIDE the band -- the general claim is false"
    outliers = [n for n in nets if n > upper]
    assert len(outliers) == 20
    assert sum(outliers) == 20 * target
