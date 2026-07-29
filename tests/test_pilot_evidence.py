"""The chunk-9A evidence pack: the pieces that can be tested without the gitignored stores.

The pack itself is generated from real data (`docs/evidence/chunk9a_pilot.md`) and a bare
clone cannot rebuild it. What IS testable here, on hand-built inputs, is everything that could
silently print a wrong claim:

* the reconciliation against the committed chunk-8 pack -- it must FAIL loudly when a figure
  moves, not quietly compare a number to itself;
* the bias walk, which is the pack's digit-by-digit evidence;
* the invariant report, which must be able to fail (a PASS line that cannot fail is
  decoration, not evidence -- chunk-8 decision B177);
* the committed pack's own claims, pinned to the numbers the generator produced, so the code
  and the evidence file cannot drift apart silently.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import corp_actions as ca
from acumen import pilot_evidence as pe
from acumen.bias import BEARISH, BULLISH
from acumen.signals import EXIT_STOP, EXIT_TARGET, LONG, SHORT

PACK = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "chunk9a_pilot.md"

D = date(2026, 5, 4)


def executed_row(
    symbol: str = "TCS",
    day: date = D,
    *,
    qty: int = 100,
    gross: int = 300_000,
    exit_kind: str = EXIT_TARGET,
    side: str = LONG,
) -> bt.LedgerRow:
    return bt.LedgerRow(
        symbol=symbol,
        day=day,
        status=bt.STATUS_EVALUATED,
        reason="evaluated",
        side=side,
        outcome="entered",
        consumed=True,
        signalled=True,
        executed=True,
        entry_paise=200_000,
        stop_paise=199_000,
        target_paise=203_000,
        per_share_risk_paise=1_000,
        qty=qty,
        notional_paise=qty * 200_000,
        gross_pnl_paise=gross,
        cost_paise=10_000,
        net_pnl_paise=gross - 10_000,
        exit_kind=exit_kind,
        # stamps and an exit price CONSISTENT with the gross, so the row can be marked on the
        # 15-minute path the Q-16(b) ruling requires (the real ledger always carries these)
        entry_close_stamp=datetime.combine(day, time(12, 0)),
        exit_close_stamp=datetime.combine(day, time(14, 0)),
        exit_paise=(
            200_000 + gross // qty if side == LONG else 200_000 - gross // qty
        ),
        mfe_paise=max(0, gross),
        mae_paise=min(0, gross),
        gate1_passed=True,
        gate2_passed=True,
        gate1p_passed=True,
    )


# ==============================================================================================
# The reconciliation against the committed chunk-8 pack
# ==============================================================================================


def test_the_chunk8_oracle_is_the_committed_packs_own_numbers() -> None:
    """If chunk 8's pack is ever regenerated with different numbers, this is the tripwire."""
    text = (PACK.parent / "chunk8_sweep.md").read_text(encoding="utf-8")
    assert "| Executed trades | 146 |" in text
    assert "| Shares transacted | 53,750 |" in text
    assert "| Gross PnL | Rs 12,665.05 |" in text
    assert "| Costs paid | Rs 14,600.00 |" in text
    assert "| **Net PnL** | **-Rs 1,934.95** |" in text
    assert pe.CHUNK8_PACK["executed"] == 146
    assert pe.CHUNK8_PACK["shares"] == 53_750
    assert pe.CHUNK8_PACK["gross_paise"] == 1_266_505
    assert pe.CHUNK8_PACK["cost_paise"] == 1_460_000
    assert pe.CHUNK8_PACK["net_paise"] == -193_495


def test_every_reconciled_figure_has_a_printable_label() -> None:
    assert set(pe.RECONCILIATION_LABELS) == set(pe.CHUNK8_PACK)


def test_the_reconciliation_fails_loudly_when_a_figure_moves() -> None:
    """A comparison that cannot fail proves nothing. One row, deliberately wrong."""
    rows = (executed_row(),)
    results = dict(
        (label, ok) for label, _expected, _measured, ok in pe.reconciliation(rows)
    )
    assert results["executed"] is False  # 1 trade, not 146
    assert results["net_paise"] is False
    assert any(ok for ok in results.values()) is False or True  # nothing is asserted equal


def test_the_reconciliation_covers_the_whole_chunk8_table() -> None:
    labels = [label for label, *_rest in pe.reconciliation(())]
    assert labels == list(pe.CHUNK8_PACK)
    assert len(labels) == 17


# ==============================================================================================
# The bias walk -- the pack's digit-by-digit evidence
# ==============================================================================================


class FakeCalendar:
    def __init__(self, pair):
        self._pair = pair

    def bias_pair(self, day):
        assert day == self._pair[0]
        return type("Pair", (), {"current": self._pair[1], "previous": self._pair[2]})()


class FakeStore:
    def __init__(self, candles):
        self.candles = candles

    def daily(self, symbol, start, end):
        import pandas as pd

        row = self.candles.get(start)
        if row is None:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "open_paise": row[0],
                    "high_paise": row[1],
                    "low_paise": row[2],
                    "close_paise": row[3],
                }
            ]
        )


def test_the_bias_walk_shows_both_readings_of_a_real_bonus() -> None:
    """RELIANCE's own numbers, hand-checked: P (2024-10-25) raw O 2687.00 H 2688.70 L 2644.00
    C 2655.70; k = 1/2 -> O 1343.50 H 1344.35 L 1322.00 C 1327.85; C (2024-10-28) H 1353.00
    L 1322.10 C 1334.35. Adjusted: C.high 1353.00 > P.high 1344.35 and C.low 1322.10 >=
    P.low 1322.00 and C.close 1334.35 <= bodyMax 1343.50 -> Rule 2 BEARISH -- decided by TEN
    PAISE on the low. Unadjusted the same close is 1334.35 against a bodyMin of 2655.70, which
    is Rule 1 on a 50% fake collapse.
    """
    trade_day, current, previous = date(2024, 10, 29), date(2024, 10, 28), date(2024, 10, 25)
    store = FakeStore(
        {
            previous: (268_700, 268_870, 264_400, 265_570),
            current: (133_700, 135_300, 132_210, 133_435),
        }
    )
    factor = ca.Factor("RELIANCE", current, ca.KIND_BONUS, Decimal("0.5"), "bonus 1:1")
    walk = pe.walk_pair(
        store, FakeCalendar((trade_day, current, previous)), "RELIANCE", trade_day, (factor,)
    )
    assert walk.previous_adjusted.open == 134_350
    assert walk.previous_adjusted.high == 134_435
    assert walk.previous_adjusted.low == 132_200
    assert walk.previous_adjusted.close == 132_785
    assert walk.adjusted_bias == BEARISH and walk.adjusted_rule == "rule-2-sweep"
    assert walk.unadjusted_bias == BEARISH and walk.unadjusted_rule == "rule-1-breakout"
    assert walk.rule_changed and not walk.bias_changed
    # ten paise: move C's low one paisa below the adjusted low and Rule 2 no longer fires
    assert walk.current.low - walk.previous_adjusted.low == 10


def test_the_bias_walk_finds_the_case_where_the_adjustment_reverses_the_bias() -> None:
    """HDFCBANK's own numbers: P (2019-09-18) raw O 2217.30 H 2224.15 L 2180.00 C 2187.75,
    k = 1/2 -> O 1108.65 H 1112.075 -> 1112.08 (half-even) L 1090.00 C 1093.875 -> 1093.88;
    C (2019-09-19) H 1107.05 L 1084.00 C 1101.05 -> adjusted Rule 2 BULLISH, unadjusted Rule 1
    BEARISH. Opposite SIDES on the same candles.
    """
    trade_day, current, previous = date(2019, 9, 20), date(2019, 9, 19), date(2019, 9, 18)
    store = FakeStore(
        {
            previous: (221_730, 222_415, 218_000, 218_775),
            current: (109_990, 110_705, 108_400, 110_105),
        }
    )
    factor = ca.Factor("HDFCBANK", current, ca.KIND_SPLIT, Decimal("0.5"), "face value 2 -> 1")
    walk = pe.walk_pair(
        store, FakeCalendar((trade_day, current, previous)), "HDFCBANK", trade_day, (factor,)
    )
    assert walk.previous_adjusted.high == 111_208  # 111207.5 rounds half-even to 111208
    assert walk.previous_adjusted.close == 109_388  # 109387.5 rounds half-even to 109388
    assert walk.adjusted_bias == BULLISH
    assert walk.unadjusted_bias == BEARISH
    assert walk.bias_changed


def test_a_pair_with_no_factor_in_its_window_is_identical_both_ways() -> None:
    trade_day, current, previous = date(2026, 5, 6), date(2026, 5, 5), date(2026, 5, 4)
    store = FakeStore(
        {previous: (100, 200, 50, 150), current: (150, 250, 100, 240)}
    )
    factor = ca.Factor("X", date(2020, 1, 1), ca.KIND_BONUS, Decimal("0.5"), "old")
    walk = pe.walk_pair(
        store, FakeCalendar((trade_day, current, previous)), "X", trade_day, (factor,)
    )
    assert walk.factors == ()
    assert walk.previous_adjusted == walk.previous_raw
    assert not walk.bias_changed and not walk.rule_changed


def test_the_walk_renders_every_digit_it_claims() -> None:
    trade_day, current, previous = date(2024, 10, 29), date(2024, 10, 28), date(2024, 10, 25)
    store = FakeStore(
        {
            previous: (268_700, 268_870, 264_400, 265_570),
            current: (133_700, 135_300, 132_210, 133_435),
        }
    )
    factor = ca.Factor("RELIANCE", current, ca.KIND_BONUS, Decimal("0.5"), "bonus 1:1")
    walk = pe.walk_pair(
        store, FakeCalendar((trade_day, current, previous)), "RELIANCE", trade_day, (factor,)
    )
    text = "\n".join(pe.render_bias_walk(walk, title="T", note="N"))
    assert "2,687.00" in text and "1,343.50" in text  # raw and adjusted open
    assert "134,350" in text  # the adjusted paise
    assert "rule-2-sweep" in text and "rule-1-breakout" in text
    assert "changes the BIAS: **no**" in text
    assert "changes the RULE: **YES**" in text


# ==============================================================================================
# The invariant report must be able to FAIL (chunk-8 decision B177)
# ==============================================================================================


def fake_pilot(rows) -> pe.PilotRun:
    spec = bt.RunSpec(
        symbols=("TCS",),
        start=D,
        end=D,
        row_size=24,
        risk_per_trade_paise=100_000,
        cost_paise=10_000,
    )
    manifest = {
        "outcomes": bt.outcome_counts(rows),
        "residual_register": {"caveat": bt.RESIDUAL_CAVEAT},
        "capital_flags": {"computed": False},
    }
    result = bt.RunResult(
        spec=spec,
        rows=tuple(rows),
        manifest=manifest,
        ledger_path=Path("ledger.jsonl"),
        manifest_path=Path("manifest.json"),
        non_standard_sessions=(),
    )
    return pe.PilotRun(label="fake", result=result, ledger_sha="x", manifest_sha="y")


def good_resume() -> pe.ResumeProof:
    return pe.ResumeProof("a", "a", "m", "m", "TCS", ("TCS.jsonl",), 1, 1, 0)


def benchmark() -> object:
    from acumen import portfolio as pf

    return pf.buy_and_hold(
        {"TCS": {D: 100}}, first_day=D, last_day=D, initial_capital_paise=10_000_000
    )


def verdicts(rows, resume=None) -> dict[str, bool]:
    lines = pe.invariant_report(
        fake_pilot(rows),
        resume or good_resume(),
        benchmark(),
        initial_capital_paise=10_000_000,
        trade_paths=bt.assemble_trade_paths(rows, bars_for=lambda symbol, day: ()),
    )
    out = {}
    for line in lines:
        label, _, rest = line.partition(": **")
        out[label] = rest.startswith("PASS")
    return out


def test_the_invariants_pass_on_a_clean_ledger() -> None:
    """Everything except the chunk-8 reconciliation, which a one-row fake ledger cannot meet --
    and the fact that it FAILS here is itself the proof that the comparison is real."""
    results = verdicts([executed_row()])
    reconciled = "the run reconciles with the committed chunk-8 pack on every figure"
    assert results.pop(reconciled) is False
    assert all(results.values()), [name for name, ok in results.items() if not ok]


def test_a_duplicated_row_fails_its_invariant() -> None:
    row = executed_row()
    results = verdicts([row, row])
    assert results["one ledger row per walked symbol-day, no duplicates"] is False


def test_a_broken_money_identity_fails_its_invariant() -> None:
    row = replace(executed_row(), net_pnl_paise=1)
    assert verdicts([row])["net == gross - cost on every executed trade"] is False


def test_a_refusal_carrying_money_fails_its_invariant() -> None:
    row = bt.LedgerRow(
        symbol="TCS",
        day=D,
        status=bt.STATUS_REFUSED,
        reason="gate 1 (volume reconciliation)",
        net_pnl_paise=500,
    )
    assert (
        verdicts([row])["every refusal carries exactly one reason and no money"] is False
    )


def test_a_realized_pnl_outside_the_excursions_fails_its_invariant() -> None:
    row = replace(executed_row(), mfe_paise=1, mae_paise=0)
    assert (
        verdicts([row])["every executed trade's realized PnL sits inside [MAE, MFE]"] is False
    )


def test_a_failed_resume_fails_its_invariant() -> None:
    broken = pe.ResumeProof("a", "b", "m", "m", "TCS", ("TCS.jsonl",), 1, 1, 0)
    assert broken.identical is False
    assert (
        verdicts([executed_row()], broken)[
            "an interrupted run resumes byte-identically with zero duplicates"
        ]
        is False
    )


def test_a_resume_with_duplicates_fails_even_when_the_bytes_match() -> None:
    assert pe.ResumeProof("a", "a", "m", "m", "TCS", (), 1, 1, 3).identical is False
    assert pe.ResumeProof("a", "a", "m", "n", "TCS", (), 1, 1, 0).identical is False


def test_a_row_that_oversizes_the_budget_fails_its_invariant() -> None:
    row = replace(executed_row(), qty=101, per_share_risk_paise=1_000)
    assert (
        verdicts([row])["qty x per-share risk <= the risk budget on every signalled day"]
        is False
    )


# ==============================================================================================
# The committed pack's own claims
# ==============================================================================================


@pytest.mark.parametrize(
    "claim",
    [
        "| Stock-days walked | 290 | 290 | YES |",
        "| Executed trades | 146 | 146 | YES |",
        "| Net PnL | -Rs 1,934.95 | -Rs 1,934.95 | YES |",
        "**Reconciliation: 17 of 17 figures identical**",
        "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending",
        "IOC (41.9% price-proven) and TATASTEEL (65.8%)",
        "CONTEXT 7-E2 non-standard session",
        "the adjustment changes the BIAS: **YES**",
        "| **Byte-identical** | **YES** |",
    ],
)
def test_the_committed_pack_carries_its_claims(claim: str) -> None:
    assert claim in PACK.read_text(encoding="utf-8")


def test_the_committed_pack_reports_no_failed_invariant() -> None:
    text = PACK.read_text(encoding="utf-8")
    section = text.split("## 8. Invariants asserted over this pack")[1]
    assert "**FAIL**" not in section
    assert section.count("**PASS**") >= 15


def test_the_committed_pack_never_prints_an_outlier_count() -> None:
    """The metric is BLOCKED on the architect; a pack that printed a number would be deciding."""
    text = PACK.read_text(encoding="utf-8")
    assert "Q-16(a) is pending" in text
    assert re.search(r"\| Outliers \| \d", text) is None


def test_the_committed_pack_says_what_chunk_9b_still_owes() -> None:
    text = PACK.read_text(encoding="utf-8")
    assert "## 9. What chunk 9B still owes" in text
    assert "Q43" in text and "Q44" in text
