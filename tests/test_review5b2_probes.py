"""RE-REVIEW probes for chunk 5B FIX-5 (docs/reviews/REVIEW_5B_2.md).

Written by the re-review session, not by the builder. Each one is an attack the FIX-5 suite did not
carry, kept in the repo per `personas/quant_reviewer.md` step 4:

* **the ruling's "one always escapes" claim, on its hard side.** A wrong SCALE moves both ends of
  the fold the same way, so the architect's containment gate catches it on whichever end leaves the
  raw interval. These probes build days where one end lands INSIDE by coincidence and pin that the
  other end still fails -- in both directions.
* **the blind spot that claim leaves, measured and pinned.** Containment can only see a factor
  bigger than the day's own range slack `raw_range / fold_range`. On real days that slack is a few
  paise; the probe states the arithmetic so that any future widening of the tolerance is visible as
  a test change rather than as a silent loss of resolution.
* **the boundary, at BOTH bounds at once.**
* **gate 1P's denominator at the WIRING level** -- a stored day with no bhavcopy row is counted and
  FAILED (REVIEW_5B finding Q4), while gate 1's own denominator still excludes it.
* **the acceptance rule's refusal side, on the shape that actually occurred** (BSE 2025-05-23): a
  floor that RESOLVES and moves days into gate 1 while moving none into "usable" must be discarded
  and never written (decision B148).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import price_recovery as pr
from acumen import quality_gates as qg
from acumen import universe_backfill as ub
from acumen import vendor_adjustment as va
from acumen.bhavcopy import FORMAT_UDIFF, OUTCOME_PRESENT, DailyRow, DateOutcome
from acumen.daily_store import DailyStore
from acumen.minute_store import MinuteStore, StoredBar

_ONE = Decimal(1)
NOW = datetime(2026, 7, 28, 8, 0, 0)


# --- A. the "one always escapes" claim, attacked ----------------------------------------


def test_a_wrong_scale_hiding_on_the_high_end_still_fails_on_the_low_end() -> None:
    """0.667x: the fold high lands INSIDE the daily high by coincidence; the low must still fail.

    The day carries a large block print at the top, so the raw daily high sits far above the
    continuous high. Scaled DOWN, the fold high therefore stays comfortably inside the interval --
    the end that would have caught a 5x day escapes nothing here. The ruling's claim is that the
    OTHER end cannot also hide, because a scale moves both ends the same way.
    """
    raw_high, raw_low = 20000, 10000          # a very wide raw interval (block print at the top)
    fold_high, fold_low = 12000, 11000        # the continuous session, well inside it
    k = Decimal("0.667")
    result = qg.price_containment_gate(
        int(Decimal(fold_high) * k), int(Decimal(fold_low) * k), raw_high, raw_low
    )
    # the HIGH end is genuinely inside -- the coincidence the probe is built on
    assert int(Decimal(fold_high) * k) < raw_high
    assert not result.passed
    assert result.cause == qg.GATE1P_BELOW
    assert result.high_excess_paise == 0 and result.low_excess_paise > 0


def test_a_wrong_scale_hiding_on_the_low_end_still_fails_on_the_high_end() -> None:
    """The mirror: 1.417x (NMDC's factor) with a deep auction low."""
    raw_high, raw_low = 20000, 10000
    fold_high, fold_low = 19000, 18000
    k = Decimal("1.417")
    result = qg.price_containment_gate(
        int(Decimal(fold_high) * k), int(Decimal(fold_low) * k), raw_high, raw_low
    )
    assert int(Decimal(fold_low) * k) > raw_low        # the LOW end is inside
    assert not result.passed
    assert result.cause == qg.GATE1P_ABOVE
    assert result.low_excess_paise == 0 and result.high_excess_paise > 0


def test_containment_cannot_see_a_factor_smaller_than_the_days_own_range_slack() -> None:
    """The measured LIMIT of the gate, pinned so it can never be lost silently.

    A day is contained for every factor ``f`` in ``[(raw_low - tol)/fold_low,
    (raw_high + tol)/fold_high]`` -- a window that always contains 1 and whose width is the day's
    own slack between the raw interval and the fold interval. On an ordinary day the fold IS very
    nearly the raw interval, so the window is a few hundredths of a percent and every real
    corporate-action factor (the smallest being the ~0.33% rights ours-vs-vendor gap) is caught.
    The probe states both halves: a tight day resolves far below 0.33%, and a pathologically wide
    day does not.
    """
    tol = qg.PRICE_CONTAINMENT_REL

    def window(fold_high: int, fold_low: int, raw_high: int, raw_low: int) -> Decimal:
        hi = (Decimal(raw_high) * (1 + tol)) / Decimal(fold_high)
        lo = (Decimal(raw_low) * (1 - tol)) / Decimal(fold_low)
        return max(hi - 1, 1 - lo)

    # an ORDINARY day: the fold is the raw interval bar a few paise of auction print
    ordinary = window(153700, 152600, 153725, 152580)
    assert ordinary < Decimal("0.0015")                  # < 0.15%, far below the 0.33% floor
    # the PATHOLOGICAL day the probes above are built on: raw twice as wide as the fold
    pathological = window(12000, 11000, 20000, 10000)
    assert pathological > Decimal("0.6")                 # a 60% error could hide on such a day
    # and the gate agrees with the arithmetic: a factor inside the window is NOT seen
    hidden = qg.price_containment_gate(int(12000 * 1.5), int(11000 * 1.5), 20000, 10000)
    assert hidden.passed


def test_a_day_exactly_at_both_tolerance_bounds_passes_and_one_paise_past_either_fails() -> None:
    raw_high, raw_low = 100000, 99000                    # tolerances 100 and 99 paise
    assert qg.price_containment_limit(raw_high) == Decimal(100)
    assert qg.price_containment_limit(raw_low) == Decimal(99)
    at_both = qg.price_containment_gate(raw_high + 100, raw_low - 99, raw_high, raw_low)
    assert at_both.passed
    assert at_both.high_excess_paise == 0 and at_both.low_excess_paise == 0
    assert not qg.price_containment_gate(raw_high + 101, raw_low - 99, raw_high, raw_low).passed
    assert not qg.price_containment_gate(raw_high + 100, raw_low - 100, raw_high, raw_low).passed


# --- B. gate 1P's denominator, at the wiring level (REVIEW_5B finding Q4) ---------------

DAYS = [
    date(2021, 3, 1) + timedelta(days=i)
    for i in range(90)
    if (date(2021, 3, 1) + timedelta(days=i)).weekday() < 5
]
RAW_HIGH, RAW_LOW, RAW_VOL = 100000, 90000, 900000


def _row(day: date, symbol: str) -> DailyRow:
    return DailyRow(
        trade_date=day, symbol=symbol, series="EQ",
        open_paise=RAW_LOW + 100, high_paise=RAW_HIGH, low_paise=RAW_LOW,
        close_paise=RAW_LOW + 500, volume=RAW_VOL, last_paise=RAW_LOW + 500,
        prev_close_paise=RAW_LOW, turnover_paise=RAW_LOW * RAW_VOL, trades=100,
        isin=None, instrument_type=None, source_format=FORMAT_UDIFF,
    )


def _bars(symbol: str, day: date, high: int, low: int, volume: int) -> list[StoredBar]:
    stamp = datetime.combine(day, time(9, 15))
    third = volume // 3
    return [
        StoredBar(symbol, stamp, low, high, low, low + 100, volume - 2 * third),
        StoredBar(symbol, stamp + timedelta(minutes=1), low + 100, high, low, low + 200, third),
        StoredBar(symbol, stamp + timedelta(minutes=2), low + 200, high, low, low + 300, third),
    ]


def _stores(tmp_path: Path, *, skip_daily: set[date] = frozenset()) -> tuple:
    daily = DailyStore.at(tmp_path / "daily_store")
    outcomes = []
    for day in DAYS:
        if day not in skip_daily:
            daily.write_rows(day, (_row(day, "ACME"),))
        outcomes.append(DateOutcome(
            trade_date=day, outcome=OUTCOME_PRESENT, source_format=FORMAT_UDIFF,
            url="https://example.invalid", http_status=200,
            row_count=0 if day in skip_daily else 1, attempted_at=NOW,
        ))
    daily.record_outcomes(outcomes)
    minute = MinuteStore.at(tmp_path / "minute_store")
    for day in DAYS:
        minute.write_bars("ACME", _bars("ACME", day, RAW_HIGH, RAW_LOW, RAW_VOL))
    return daily, minute


def test_a_stored_day_with_no_bhavcopy_row_is_gated_failed_and_counted_by_gate_1p(
    tmp_path: Path,
) -> None:
    """Finding Q4's closure at the WIRING level, not just in the pure gate.

    Such a day is outside gate 1's denominator -- there is nothing to reconcile against -- and the
    review's complaint was that it therefore sat in neither numerator nor denominator anywhere.
    Under the Q-14 ruling gate 1P's denominator is EVERY stored day, so the day is now counted and
    failed under its own cause, and the two denominators differ by exactly the no-oracle days.
    """
    missing = {DAYS[3], DAYS[9]}
    daily, minute = _stores(tmp_path, skip_daily=missing)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = ub.gate_symbol(minute, cache, "ACME")

    assert tally.gate1p_total == len(DAYS)                       # every STORED day
    assert tally.gate1_total == len(DAYS) - len(missing)         # gate 1 can only gate what it can compare
    assert tally.gate1p_total - tally.gate1_total == len(missing)
    assert tally.gate1p_no_oracle == len(missing)
    assert tally.gate1p_pass == len(DAYS) - len(missing)
    assert {day for day, cause in tally.gate1p_failures
            if cause == qg.GATE1P_NO_ORACLE} == missing
    # and the failure is NEVER folded into gate 1's count
    assert tally.gate1_pass == len(DAYS) - len(missing)


def test_a_gate_1p_failure_is_never_folded_into_gate_ones_numerator(tmp_path: Path) -> None:
    """A day whose volume reconciles perfectly but whose PRICE is off scale: gate 1 passes it."""
    daily = DailyStore.at(tmp_path / "daily_store")
    for day in DAYS:
        daily.write_rows(day, (_row(day, "ACME"),))
    daily.record_outcomes([
        DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, source_format=FORMAT_UDIFF,
                    url="https://example.invalid", http_status=200, row_count=1, attempted_at=NOW)
        for day in DAYS
    ])
    minute = MinuteStore.at(tmp_path / "minute_store")
    for index, day in enumerate(DAYS):
        scale = 2 if index < 5 else 1                     # the first five days stored at 2x
        minute.write_bars("ACME", _bars("ACME", day, RAW_HIGH * scale, RAW_LOW * scale, RAW_VOL))
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = ub.gate_symbol(minute, cache, "ACME")

    assert tally.gate1_pass == tally.gate1_total          # volume reconciles on every day
    assert tally.gate1p_pass == len(DAYS) - 5
    assert tally.gate1p_above == 5 and tally.gate1p_below == 0
    assert tally.usable_pass == len(DAYS) - 5             # the intersection is what drops


# --- C. acceptance refuses the BSE shape (decision B148) --------------------------------

EX_DATE = DAYS[30]
SPLICE = DAYS[10]
K_VOLUME = Decimal("0.5")


def _volume_only_map() -> va.AdjustmentMap:
    """An event that moved the SHARE COUNT only -- its price factor is exactly 1."""
    choice = va.EventChoice(
        kind="bonus", ex_date=EX_DATE,
        price_factor=_ONE, price_source=va.SOURCE_ABSENT,
        volume_factor=K_VOLUME, volume_source=va.SOURCE_MEASURED,
    )
    era = va.EraResolution(
        label=f"pre-{EX_DATE.isoformat()}", ex_dates=(EX_DATE,), choices=(choice,),
        k_price=_ONE, k_volume=K_VOLUME, price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True, probe_days=tuple(DAYS[26:30]), note="synthetic",
    )
    return va.AdjustmentMap(
        symbol="BSHAPE", fetch_date=DAYS[-1] + timedelta(days=1), all_event_ex_dates=(EX_DATE,),
        eras=(era,), tick_paise=1, floors=(),
    )


def test_a_floor_that_buys_gate_1_but_no_usable_day_is_rejected_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    """The BSE 2025-05-23 shape, reproduced: the volume side resolves, and it is still refused.

    Below the vendor's splice the volume was never scaled, so the ingest's multiplication left it
    at half the traded share count and gate 1 fails there. A volume floor at the splice repairs
    exactly that -- and the same days' PRICES are off scale for an unrelated reason the floor model
    cannot express, so not one of them becomes usable. Decision B148's acceptance ("MORE days pass
    BOTH gates, and no fewer pass gate 1") must therefore discard the measurement, leaving the map
    on disk untouched. This is the case the FIX-5 suite exercised only through a no-splice store.
    """
    daily = DailyStore.at(tmp_path / "daily_store")
    for day in DAYS:
        daily.write_rows(day, (_row(day, "BSHAPE"),))
    daily.record_outcomes([
        DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, source_format=FORMAT_UDIFF,
                    url="https://example.invalid", http_status=200, row_count=1, attempted_at=NOW)
        for day in DAYS
    ])
    minute = MinuteStore.at(tmp_path / "minute_store")
    for day in DAYS:
        if day >= SPLICE:
            volume = RAW_VOL                                     # vendor applied it; ingest undid it
        else:
            volume = int(Decimal(RAW_VOL) * K_VOLUME)            # vendor applied nothing: half count
        # every pre-ex day is stored at 1.9x the traded price, which NO event factor explains
        # (the event's own price factor is exactly 1), so gate 1P fails and no floor can move it
        scale = Decimal("1.9") if day < EX_DATE else _ONE
        minute.write_bars("BSHAPE", _bars(
            "BSHAPE", day, int(RAW_HIGH * scale), int(RAW_LOW * scale), volume))

    amap = _volume_only_map()
    va.persist_map(amap, data_dir=tmp_path / "data")
    rows = {day: (RAW_HIGH, RAW_LOW, RAW_LOW + 100, RAW_VOL) for day in DAYS}
    stored = pr.stored_days(minute, rows, "BSHAPE")

    # the volume side genuinely RESOLVES -- this is not a "no splice" refusal
    floor, record = pr.measure_event_floor(amap, stored, EX_DATE, "forced, for the test")
    assert floor is not None
    assert record.volume_resolved and record.volume_floor == SPLICE
    assert not record.price_resolved                 # a price factor of 1 can decide nothing

    # and it would genuinely buy gate-1 days ...
    trial = va.with_floors(amap, [floor])
    before = pr.predict_counts(stored, amap, amap)
    after = pr.predict_counts(stored, amap, trial)
    assert after.gate1 > before.gate1
    assert after.both == before.both                 # ... while buying no USABLE day

    result = pr.recover_symbol(
        minute, daily, rows, "BSHAPE", amap, {EX_DATE: "forced, for the test"},
        data_dir=tmp_path / "data", tick_paise=1, log=lambda _m: None,
    )
    assert result.accepted_floors == 0
    assert not result.applied and result.days_rewritten == 0
    assert "REJECTED by acceptance" in result.events[0].verdict
    assert not va.load_map("BSHAPE", data_dir=tmp_path / "data").floors


# --- D. the recovery path spends no credentialed call (decision B143) -------------------


def test_no_credentialed_call_is_reachable_from_the_recovery_path() -> None:
    """B143, proved by AST rather than by trust: nothing on the pass can build a client.

    `binary_search_floor` takes its classifier as a PARAMETER, so a name-based call graph reports a
    false path through the LIVE searcher's own `classify`. This walks the real bodies instead.
    """
    import ast

    src = Path(va.__file__).parent
    network = {
        "SmartApiClient", "SmartConnect", "generateSession", "getCandleData", "get_candles",
        "probe_one_day", "fetch_json", "fetch_binary", "Credentials",
    }
    targets = {
        "price_recovery": ("recover_symbol", "measure_event_floor", "predict_counts",
                           "judge_day", "stored_days", "candidate_days", "rescaled", "_merged"),
        "vendor_adjustment": ("search_event_floor_stored", "classify_stored_price_day",
                              "classify_stored_volume_day", "binary_search_floor"),
        "universe_backfill": ("_recover_one",),
    }
    for module, names in targets.items():
        tree = ast.parse((src / f"{module}.py").read_text(encoding="utf-8"))
        found = {
            node.name: node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name in names
        }
        assert set(found) == set(names), f"{module}: missing {set(names) - set(found)}"
        for name, node in found.items():
            called = {
                (call.func.id if isinstance(call.func, ast.Name) else call.func.attr)
                for call in ast.walk(node) if isinstance(call, ast.Call)
            }
            params = {a.arg for a in node.args.args + node.args.kwonlyargs}
            assert not (called & network) - params, f"{module}.{name} reaches {called & network}"


@pytest.mark.parametrize("side", [va.FLOOR_SIDE_PRICE, va.FLOOR_SIDE_VOLUME])
def test_a_floor_search_never_probes_a_day_of_an_unprovable_era(side: str, tmp_path: Path) -> None:
    """`candidate_days` is the only domain a per-side search may bisect over."""
    unprovable = va.AdjustmentMap(
        symbol="BSHAPE", fetch_date=DAYS[-1] + timedelta(days=1), all_event_ex_dates=(EX_DATE,),
        eras=(va.EraResolution(
            label="pre", ex_dates=(EX_DATE,), choices=(), k_price=_ONE, k_volume=_ONE,
            price_containment_paise=-1, volume_gap_pct=None, provable=False, probe_days=(),
            note="UN-PROVABLE",
        ),),
    )
    assert pr.candidate_days(unprovable, DAYS, EX_DATE, side=side) == []
    provable = _volume_only_map()
    days = pr.candidate_days(provable, DAYS, EX_DATE, side=side)
    if side == va.FLOOR_SIDE_VOLUME:
        assert days and all(d < EX_DATE for d in days)
    else:
        assert days == []          # the event's price factor is 1: nothing to drop, nothing to probe
