"""The chunk-5B FIX-5 work: per-side floors, the gate-1P cluster signature, the recovery pass,
and the REVIEW_5B punch list (Q3, Q5, Q6, C1-C6, C10-C16).

All OFFLINE and deterministic. The recovery pass is offline BY CONSTRUCTION -- it reads the store
rather than the vendor (decision B143) -- so the end-to-end case here is the real one, not a double:
a symbol whose vendor spliced its archive on the PRICE side only, stored at twice the traded price
with its volume reconciling perfectly, which is exactly the shape REVIEW_5B finding Q1 measured.
"""

from __future__ import annotations

import ast
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import minute_backfill as mb
from acumen import price_recovery as pr
from acumen import quality_gates as qg
from acumen import universe_backfill as ub
from acumen import vendor_adjustment as va
from acumen.bhavcopy import FORMAT_UDIFF, OUTCOME_PRESENT, DailyRow, DateOutcome
from acumen.daily_store import DailyStore
from acumen.minute_store import MinuteStore, StoredBar

_ONE = Decimal(1)
NOW = datetime(2026, 7, 28, 8, 0, 0)


# --- a synthetic symbol whose vendor spliced the PRICE side only -------------------------

DAYS = [
    date(2020, 1, 6) + timedelta(days=i)
    for i in range(130)
    if (date(2020, 1, 6) + timedelta(days=i)).weekday() < 5
]
EX_DATE = DAYS[60]
SPLICE = DAYS[30]           # the vendor applied the event from here on, and not before
RAW_HIGH, RAW_LOW, RAW_VOL = 100000, 90000, 900000
K_PRICE = Decimal("0.5")    # the event moved price...
K_VOLUME = _ONE             # ...and did not move the share count, so gate 1 sees nothing


def _daily_row(day: date, symbol: str) -> DailyRow:
    return DailyRow(
        trade_date=day, symbol=symbol, series="EQ",
        open_paise=RAW_LOW + 100, high_paise=RAW_HIGH, low_paise=RAW_LOW,
        close_paise=RAW_LOW + 500, volume=RAW_VOL, last_paise=RAW_LOW + 500,
        prev_close_paise=RAW_LOW, turnover_paise=RAW_LOW * RAW_VOL, trades=100,
        isin=None, instrument_type=None, source_format=FORMAT_UDIFF,
    )


def _daily_store(tmp_path: Path, symbol: str = "ACME") -> DailyStore:
    store = DailyStore.at(tmp_path / "daily_store")
    outcomes = []
    for day in DAYS:
        store.write_rows(day, (_daily_row(day, symbol),))
        outcomes.append(DateOutcome(
            trade_date=day, outcome=OUTCOME_PRESENT, source_format=FORMAT_UDIFF,
            url="https://example.invalid", http_status=200, row_count=1, attempted_at=NOW,
        ))
    store.record_outcomes(outcomes)
    return store


def _bars(symbol: str, day: date, high: int, low: int, volume: int) -> list[StoredBar]:
    stamp = datetime.combine(day, time(9, 15))
    third = volume // 3
    return [
        StoredBar(symbol, stamp, low, high, low, low + 100, volume - 2 * third),
        StoredBar(symbol, stamp + timedelta(minutes=1), low + 100, high, low, low + 200, third),
        StoredBar(symbol, stamp + timedelta(minutes=2), low + 200, high, low, low + 300, third),
    ]


def _minute_store(tmp_path: Path, symbol: str = "ACME") -> MinuteStore:
    """The store as the FIX-4 ingest left it: every pre-ex day divided by the era's k_price.

    Below the vendor's splice that division is WRONG -- the vendor had applied nothing there -- so
    those days sit at 1/k_price = 2x the traded price while their volume reconciles exactly. That is
    the defect gate 1P exists to see and gate 1 cannot.
    """
    store = MinuteStore.at(tmp_path / "minute_store")
    for day in DAYS:
        if day >= EX_DATE:
            high, low = RAW_HIGH, RAW_LOW                      # post-ex: raw as fetched
        elif day >= SPLICE:
            high, low = RAW_HIGH, RAW_LOW                      # vendor applied it; ingest undid it
        else:
            high = int(RAW_HIGH / K_PRICE)                     # vendor applied NOTHING here...
            low = int(RAW_LOW / K_PRICE)                       # ...so the ingest's division is wrong
        store.write_bars(symbol, _bars(symbol, day, high, low, RAW_VOL))
    return store


def _map(symbol: str = "ACME", floors: list[va.EventFloor] | None = None) -> va.AdjustmentMap:
    choice = va.EventChoice(
        kind="demerger", ex_date=EX_DATE,
        price_factor=K_PRICE, price_source=va.SOURCE_MEASURED,
        volume_factor=K_VOLUME, volume_source=va.SOURCE_ABSENT,
    )
    era = va.EraResolution(
        label=f"pre-{EX_DATE.isoformat()}", ex_dates=(EX_DATE,), choices=(choice,),
        k_price=K_PRICE, k_volume=K_VOLUME, price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True,
        probe_days=tuple(DAYS[55:59]), note="synthetic",
    )
    return va.AdjustmentMap(
        symbol=symbol, fetch_date=DAYS[-1] + timedelta(days=1), all_event_ex_dates=(EX_DATE,),
        eras=(era,), tick_paise=1, floors=tuple(floors or ()),
    )


def _daily_rows() -> dict[date, tuple[int, int, int, int]]:
    return {day: (RAW_HIGH, RAW_LOW, RAW_LOW + 100, RAW_VOL) for day in DAYS}


# --- A. the per-side floor model (PURE) --------------------------------------------------


def _floor(price: date | None, volume: date | None, *, volume_measured: bool = True) -> va.EventFloor:
    return va.EventFloor(
        ex_date=EX_DATE, floor_date=price, resolved=price is not None,
        floor_volume=volume, volume_resolved=volume is not None,
        volume_measured=volume_measured,
    )


def test_the_two_sides_of_a_floor_drop_independently() -> None:
    """The Q-14 mechanism: price and volume applied back to DIFFERENT dates for one event."""
    amap = _map(floors=[_floor(DAYS[30], DAYS[10])])
    # below BOTH splices: neither side carries the event
    assert amap.factors_for_day(DAYS[5]) == (_ONE, _ONE)
    # between them: the VOLUME side carries it, the price side does not
    assert amap.factors_for_day(DAYS[20]) == (_ONE, K_VOLUME)
    # above both: the full chain
    assert amap.factors_for_day(DAYS[40]) == (K_PRICE, K_VOLUME)


def test_a_floor_measured_before_the_q14_ruling_still_drives_both_sides() -> None:
    """Every map committed before Q-14 must answer exactly as it did then."""
    legacy = _floor(DAYS[30], None, volume_measured=False)
    amap = _map(floors=[legacy])
    assert amap.factors_for_day(DAYS[5]) == (_ONE, _ONE)         # both dropped, as before
    assert amap.factors_for_day(DAYS[40]) == (K_PRICE, K_VOLUME)
    assert not legacy.per_side


def test_a_per_side_floor_round_trips_through_the_map_json() -> None:
    amap = _map(floors=[va.EventFloor(
        ex_date=EX_DATE, floor_date=DAYS[30], resolved=True,
        probes=(va.FloorProbe(day=DAYS[29], verdict=va.FLOOR_OUT, ratio_high=Decimal(2)),),
        note="price side", event_price_factor=K_PRICE,
        floor_volume=DAYS[10], volume_resolved=True, volume_measured=True,
        volume_probes=(va.FloorProbe(day=DAYS[9], verdict=va.FLOOR_OUT),),
        volume_note="volume side", event_volume_factor=K_VOLUME,
    )])
    back = va.from_dict(va.to_dict(amap))
    floor = back.floors[0]
    assert floor.floor_price == DAYS[30] and floor.floor_volume == DAYS[10]
    assert floor.volume_measured and floor.volume_resolved
    assert floor.volume_note == "volume side" and len(floor.volume_probes) == 1
    assert floor.per_side


def test_a_pre_q14_map_json_reads_back_with_the_volume_side_unmeasured() -> None:
    payload = va.to_dict(_map(floors=[_floor(DAYS[30], None, volume_measured=False)]))
    for key in ("floor_volume", "volume_resolved", "volume_measured", "volume_probes"):
        payload["floors"][0].pop(key, None)
    back = va.from_dict(payload)
    assert not back.floors[0].volume_measured
    assert back.factors_for_day(DAYS[5]) == (_ONE, _ONE)


# --- B. the STORE-backed classifier (PURE; decision B143) --------------------------------


def _stored(high: int, low: int, volume: int = RAW_VOL) -> va.StoredDay:
    return va.StoredDay(
        day=DAYS[0], stored_high=high, stored_low=low, stored_volume=volume,
        raw_high=RAW_HIGH, raw_low=RAW_LOW, raw_volume=RAW_VOL,
    )


def test_a_stored_day_already_contained_in_raw_is_event_in() -> None:
    assert va.classify_stored_price_day(_stored(RAW_HIGH, RAW_LOW), K_PRICE) == va.FLOOR_IN


def test_a_stored_day_that_only_contains_after_multiplying_back_is_event_out() -> None:
    off = _stored(int(RAW_HIGH / K_PRICE), int(RAW_LOW / K_PRICE))
    assert va.classify_stored_price_day(off, K_PRICE) == va.FLOOR_OUT


def test_a_stored_day_that_fits_neither_hypothesis_answers_nothing() -> None:
    assert va.classify_stored_price_day(_stored(31337, 29000), K_PRICE) == va.FLOOR_UNDECIDED


def test_an_event_with_factor_one_can_never_decide_a_day() -> None:
    assert va.classify_stored_price_day(_stored(RAW_HIGH, RAW_LOW), _ONE) == va.FLOOR_UNDECIDED
    assert va.classify_stored_volume_day(_stored(RAW_HIGH, RAW_LOW), _ONE) == va.FLOOR_UNDECIDED


def test_the_volume_classifier_uses_gate_ones_own_band() -> None:
    half = Decimal("0.5")
    # stored == raw: the committed chain already reconciles, so the event IS applied here
    assert va.classify_stored_volume_day(_stored(RAW_HIGH, RAW_LOW, RAW_VOL), half) == va.FLOOR_IN
    # stored x (1/k) == raw: only the event-OUT chain reconciles, so the day sits below the splice
    halved = _stored(RAW_HIGH, RAW_LOW, RAW_VOL // 2)
    assert va.classify_stored_volume_day(halved, half) == va.FLOOR_OUT


def test_the_bisection_finds_the_splice_date_exactly(tmp_path: Path) -> None:
    stored = {
        day: va.StoredDay(
            day=day,
            stored_high=RAW_HIGH if day >= SPLICE else int(RAW_HIGH / K_PRICE),
            stored_low=RAW_LOW if day >= SPLICE else int(RAW_LOW / K_PRICE),
            stored_volume=RAW_VOL, raw_high=RAW_HIGH, raw_low=RAW_LOW, raw_volume=RAW_VOL,
        )
        for day in DAYS if day < EX_DATE
    }
    amap = _map()
    days = pr.candidate_days(amap, sorted(stored), EX_DATE)
    search, factor = va.search_event_floor_stored(stored, amap, EX_DATE, days)
    assert search.resolved and search.floor_date == SPLICE
    assert factor == K_PRICE
    assert len(search.probes) <= va.MAX_FLOOR_PROBES


# --- C. the gate-1P cluster signature (PURE) ---------------------------------------------


def test_a_step_is_a_cluster_and_a_scatter_is_not() -> None:
    span = DAYS[:50]
    step = set(span[:30])
    assert ub.cluster_prefix(span, step) == 30
    scatter = set(span[::4])          # every fourth day, evenly spread
    assert ub.cluster_prefix(span, scatter) is None


def test_a_block_shorter_than_the_minimum_is_refused() -> None:
    span = DAYS[:50]
    assert ub.cluster_prefix(span, set(span[:ub.MIN_CLIFF_DAYS - 1])) is None
    assert ub.cluster_prefix(span, set(span[:ub.MIN_CLIFF_DAYS])) == ub.MIN_CLIFF_DAYS


def test_a_block_with_a_dirty_remainder_above_it_is_not_a_step() -> None:
    span = DAYS[:50]
    dirty = set(span[:30]) | set(span[30:40])   # 40 failing, but the "clean" part is not clean
    assert ub.cluster_prefix(span, dirty) == 40  # the block simply extends
    patchy = set(span[:25]) | {span[30], span[35], span[41], span[44], span[47]}
    assert ub.cluster_prefix(span, patchy) is None


def test_a_whole_span_failing_is_still_a_cluster_so_the_two_signatures_agree() -> None:
    span = DAYS[:30]
    assert ub.cluster_prefix(span, set(span)) == 30


def _tally_from(stored: MinuteStore, cache, symbol: str = "ACME") -> ub.GateTally:
    return ub.gate_symbol(stored, cache, symbol)


def test_the_cluster_signature_admits_the_eras_own_events_and_only_those(tmp_path: Path) -> None:
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = _tally_from(minute, cache)
    assert tally.gate1p_pass < tally.gate1p_total       # the defect is visible to gate 1P ...
    assert tally.gate1_pass == tally.gate1_total        # ... and invisible to gate 1
    admitted = ub.gate1p_recovery_events(tally, _map())
    assert list(admitted) == [EX_DATE]
    assert ub.SIGNATURE_GATE1P in admitted[EX_DATE]


def test_an_un_provable_era_admits_nothing_because_it_commits_no_chain(tmp_path: Path) -> None:
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = _tally_from(minute, cache)
    amap = _map()
    unprovable = va.AdjustmentMap(
        symbol=amap.symbol, fetch_date=amap.fetch_date,
        all_event_ex_dates=amap.all_event_ex_dates,
        eras=(va.EraResolution(
            label=amap.eras[0].label, ex_dates=amap.eras[0].ex_dates, choices=(),
            k_price=_ONE, k_volume=_ONE, price_containment_paise=-1, volume_gap_pct=None,
            provable=False, probe_days=amap.eras[0].probe_days, note="UN-PROVABLE",
        ),),
        tick_paise=1,
    )
    assert ub.gate1p_recovery_events(tally, unprovable) == {}


# --- D. the bounded recovery pass, end to end (offline) ----------------------------------


def _run_recovery(tmp_path: Path, *, apply: bool = True):
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    amap = _map()
    va.persist_map(amap, data_dir=tmp_path / "data")
    tally = _tally_from(minute, cache)
    signatures = ub.gate1p_recovery_events(tally, amap)
    result = pr.recover_symbol(
        minute, daily, _daily_rows(), "ACME", amap, signatures,
        data_dir=tmp_path / "data", tick_paise=1, apply=apply, log=lambda _m: None,
    )
    return result, minute, daily, cache


def test_the_recovery_pass_measures_the_price_splice_and_repairs_the_store(tmp_path: Path) -> None:
    result, minute, daily, cache = _run_recovery(tmp_path)
    assert result.accepted_floors == 1
    assert result.applied and result.days_rewritten > 0
    event = result.events[0]
    assert event.accepted and event.price_floor == SPLICE and event.price_resolved
    # the ruling's acceptance: MORE days pass BOTH per-day gates afterwards
    assert result.after.both > result.before.both
    # and the store now holds the traded price on the repaired days
    after = ub.gate_symbol(minute, cache, "ACME")
    assert after.gate1p_pass == after.gate1p_total
    assert after.gate1_pass == after.gate1_total
    for day, bars in minute.iter_days("ACME", DAYS[0], DAYS[0]):
        assert max(b.high_paise for b in bars) == RAW_HIGH


def test_the_measured_floor_is_committed_to_the_map_with_its_probes(tmp_path: Path) -> None:
    _run_recovery(tmp_path)
    committed = va.load_map("ACME", data_dir=tmp_path / "data")
    assert len(committed.floors) == 1
    floor = committed.floors[0]
    assert floor.floor_price == SPLICE and floor.resolved
    assert floor.probes and all(p.verdict in (va.FLOOR_IN, va.FLOOR_OUT) for p in floor.probes)
    assert floor.event_price_factor == K_PRICE


def test_a_fresh_floor_never_drops_the_floors_the_map_already_carried(tmp_path: Path) -> None:
    """`with_floors` REPLACES the tuple, so committing without merging would lose FIX-3/FIX-4 work."""
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    older = va.EventFloor(
        ex_date=DAYS[70], floor_date=DAYS[12], resolved=True, note="measured by an earlier pass",
    )
    amap = _map(floors=[older])
    va.persist_map(amap, data_dir=tmp_path / "data")
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    signatures = ub.gate1p_recovery_events(_tally_from(minute, cache), amap)
    pr.recover_symbol(
        minute, daily, _daily_rows(), "ACME", amap, signatures,
        data_dir=tmp_path / "data", tick_paise=1, log=lambda _m: None,
    )
    committed = va.load_map("ACME", data_dir=tmp_path / "data")
    assert {f.ex_date for f in committed.floors} == {DAYS[70], EX_DATE}


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    result, minute, _daily, cache = _run_recovery(tmp_path, apply=False)
    assert result.accepted_floors == 1 and not result.applied
    assert not va.load_map("ACME", data_dir=tmp_path / "data").floors
    still = ub.gate_symbol(minute, cache, "ACME")
    assert still.gate1p_pass < still.gate1p_total


def test_a_floor_that_would_not_pay_for_itself_is_rejected_and_never_written(tmp_path: Path) -> None:
    """The ruling's acceptance, exercised on its refusal side."""
    daily = _daily_store(tmp_path)
    minute = MinuteStore.at(tmp_path / "minute_store")
    for day in DAYS:                       # a CLEAN store: every day already at the traded price
        minute.write_bars("ACME", _bars("ACME", day, RAW_HIGH, RAW_LOW, RAW_VOL))
    amap = _map()
    va.persist_map(amap, data_dir=tmp_path / "data")
    # force the hunt regardless of the signature, so the ACCEPTANCE is what refuses it
    result = pr.recover_symbol(
        minute, daily, _daily_rows(), "ACME", amap, {EX_DATE: "forced, for the test"},
        data_dir=tmp_path / "data", tick_paise=1, log=lambda _m: None,
    )
    assert result.accepted_floors == 0
    assert not va.load_map("ACME", data_dir=tmp_path / "data").floors
    assert "no splice" in result.events[0].verdict or "REJECTED" in result.events[0].verdict


def test_the_residual_reason_is_recorded_when_nothing_is_recovered(tmp_path: Path) -> None:
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    amap = _map()
    result = pr.recover_symbol(
        minute, daily, _daily_rows(), "ACME", amap, {},
        data_dir=tmp_path / "data", tick_paise=1, log=lambda _m: None,
    )
    record = ub.SymbolRecord(symbol="ACME")
    assert "no event admitted" in result.note
    assert ub._residual_reason(record, result)  # noqa: SLF001


# --- E. REVIEW_5B punch list -------------------------------------------------------------


def test_q3_the_both_gates_intersection_is_counted_per_day_not_subtracted(tmp_path: Path) -> None:
    """Finding Q3: `gate1_effective - gate2_excluded` double-counts every overlapping exclusion."""
    daily = _daily_store(tmp_path)
    minute = MinuteStore.at(tmp_path / "minute_store")
    for index, day in enumerate(DAYS):
        if index < 5:
            # gate 1 fails (volume short by 50%) AND gate 2 excludes (only 3 of 375 minutes)
            minute.write_bars("ACME", _bars("ACME", day, RAW_HIGH, RAW_LOW, RAW_VOL // 2))
        else:
            minute.write_bars("ACME", _bars("ACME", day, RAW_HIGH, RAW_LOW, RAW_VOL))
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = ub.gate_symbol(minute, cache, "ACME")
    naive = tally.gate1_effective_pass - tally.gate2_excluded
    assert tally.gate2_excluded == 5                      # all five overlap gate 1's own failures
    assert tally.gate1_and_gate2_pass == len(DAYS) - 5    # the honest intersection
    assert tally.gate1_and_gate2_pass > naive             # the subtraction understates it
    assert tally.usable_pass == tally.gate1_and_gate2_pass  # gate 1P passes on every day here


def test_c3_the_dod_not_met_branch_and_its_shortfall_are_rendered(tmp_path: Path) -> None:
    """Finding C3: every report the suite rendered was a degenerate 100%-pass case."""
    ledger = ub.RunLedger(path=tmp_path / "ledger.json")
    record = ub.SymbolRecord(symbol="ACME", status=ub.STATUS_SETTLED)
    record.gate1_pass, record.gate1_total = 900, 1000
    record.gate1p_pass, record.gate1p_total = 800, 1000
    record.gate1_and_gate2_pass, record.usable_pass = 880, 780
    record.gate2_excluded, record.depth_days = 20, 1000
    ledger.records["ACME"] = record
    config = ub.RunConfig(
        minute_store=MinuteStore.at(tmp_path / "m"), daily_store=DailyStore.at(tmp_path / "d"),
        ledger_path=tmp_path / "ledger.json", map_data_dir=tmp_path, end=DAYS[-1],
    )
    import pandas as pd

    text = ub.build_report(
        ledger, ["ACME"], pd.DataFrame(), generated_at=NOW, config=config,
    )
    assert "DoD VERDICT: NOT MET" in text
    assert "more passing" in text and "would be needed to reach 95%" in text
    assert "**G gate 1 AND gate 2 AND GATE 1P" in text
    assert "### 3f." in text and "DISCLOSED-RESIDUAL register" in text


def test_c2_gate_symbol_drives_the_auction_relief_branch(tmp_path: Path) -> None:
    """Finding C2: no test drove `gate_symbol` itself into the relief branch."""
    daily = _daily_store(tmp_path)
    minute = MinuteStore.at(tmp_path / "minute_store")
    for index, day in enumerate(DAYS):
        # a THIN day: extremes and opening print intact, volume short by 10% (above the ceiling)
        volume = int(RAW_VOL * 0.9) if index == 0 else RAW_VOL
        stamp = datetime.combine(day, time(9, 15))
        third = volume // 3
        minute.write_bars("ACME", [
            StoredBar("ACME", stamp, RAW_LOW + 100, RAW_HIGH, RAW_LOW, RAW_LOW + 100,
                      volume - 2 * third),
            StoredBar("ACME", stamp + timedelta(minutes=1), RAW_LOW + 100, RAW_HIGH, RAW_LOW,
                      RAW_LOW + 200, third),
            StoredBar("ACME", stamp + timedelta(minutes=2), RAW_LOW + 200, RAW_HIGH, RAW_LOW,
                      RAW_LOW + 300, third),
        ])
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    tally = ub.gate_symbol(minute, cache, "ACME")
    assert tally.gate1_relieved == 1
    assert tally.gate1_pass == len(DAYS) - 1              # never folded into the strict count
    assert tally.gate1_effective_pass == len(DAYS)
    assert tally.gate1_relieved_days == [DAYS[0]]


def test_q5_a_row_claims_every_floor_its_map_carries_not_just_this_passes(tmp_path: Path) -> None:
    """Finding Q5: `run_floor_pass` ASSIGNED, so a carried-forward floor vanished from the ledger."""
    record = ub.SymbolRecord(symbol="ACME")
    record.floor_ex_dates = ["1999-01-01"]              # a stale claim from an older pass
    amap = _map(floors=[
        _floor(DAYS[30], None, volume_measured=False),
        va.EventFloor(ex_date=DAYS[70], floor_date=None, resolved=False,
                      floor_volume=DAYS[12], volume_resolved=True, volume_measured=True),
    ])
    record.claim_floors_from_map(amap)
    assert record.floors_resolved == 2
    assert record.floor_ex_dates == sorted([EX_DATE.isoformat(), DAYS[70].isoformat()])
    # a volume-ONLY splice is as much a measured floor as a price one
    assert DAYS[70].isoformat() in record.floor_ex_dates


def test_q6_unprovable_days_are_measured_from_the_map_against_the_stored_days(tmp_path: Path) -> None:
    """Finding Q6: the count was the FETCH pass's, which is empty on a resumed store."""
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    unprovable = va.AdjustmentMap(
        symbol="ACME", fetch_date=DAYS[-1] + timedelta(days=1), all_event_ex_dates=(EX_DATE,),
        eras=(va.EraResolution(
            label="pre", ex_dates=(EX_DATE,), choices=(), k_price=_ONE, k_volume=_ONE,
            price_containment_paise=-1, volume_gap_pct=None, provable=False,
            probe_days=(), note="UN-PROVABLE",
        ),),
    )
    va.persist_map(unprovable, data_dir=tmp_path / "data")
    config = ub.RunConfig(
        minute_store=minute, daily_store=daily, ledger_path=tmp_path / "l.json",
        map_data_dir=tmp_path / "data", end=DAYS[-1],
    )
    tally = ub.gate_symbol(minute, cache, "ACME")
    counted = ub.count_unprovable_days(config, "ACME", tally)
    assert counted == sum(1 for d in DAYS if d < EX_DATE)   # every pre-ex day, none of the rest
    assert counted > 0


def test_c4_persist_map_is_atomic_and_a_torn_map_raises_instead_of_crashing(tmp_path: Path) -> None:
    """Finding C4: the only store write bypassing `atomic_io`, and JSONDecodeError escaped."""
    source = ast.parse(Path(va.__file__).read_text(encoding="utf-8"))
    body = next(
        n for n in ast.walk(source)
        if isinstance(n, ast.FunctionDef) and n.name == "persist_map"
    )
    calls = {n.func.id for n in ast.walk(body) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "atomic_write_text" in calls
    methods = {
        n.func.attr for n in ast.walk(body)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert "write_text" not in methods   # no plain truncate-then-write survives

    path = va.persist_map(_map(), data_dir=tmp_path / "data")
    assert not list(path.parent.glob("*.tmp*"))
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(va.VendorAdjustmentError, match="will not parse"):
        va.load_map("ACME", data_dir=tmp_path / "data")


def test_c5_a_rebuild_arbitrates_with_the_previously_measured_floors_in_force() -> None:
    """Finding C5: the steady-state rebuild paths called `build_map_for` without `floors=`."""
    source = ast.parse(Path(ub.__file__).read_text(encoding="utf-8"))
    body = next(
        n for n in ast.walk(source)
        if isinstance(n, ast.FunctionDef) and n.name == "build_map_for"
    )
    text = ast.dump(body)
    assert "load_adjustment_map_for" in text          # the previous map is read BEFORE the build
    assert "carry_floors_forward" in text
    # and the build itself receives floors
    build = next(
        n for n in ast.walk(body)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "build_map"
    )
    assert any(kw.arg == "floors" for kw in build.keywords)


def test_c6_the_operator_map_build_command_carries_floors_forward() -> None:
    """Finding C6: the runbook command silently discarded a measured floor."""
    from acumen import build_adjustment_map as bam

    text = Path(bam.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    names = {
        n.func.attr for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert "carry_floors_forward" in names
    assert "load_map" in names


def test_c13_the_same_domain_predicate_is_written_once() -> None:
    """Finding C13: the signature gate and the report classifier each had their own copy."""
    source = ast.parse(Path(ub.__file__).read_text(encoding="utf-8"))
    classifier = next(
        n for n in ast.walk(source)
        if isinstance(n, ast.FunctionDef) and n.name == "_gate3_classification"
    )
    assert "same_price_domain" in ast.dump(classifier)
    # and it agrees with the signature gate on the review's own rows
    assert ub.same_price_domain(Decimal("0.1044"), Decimal("0.5"))        # BDL: admitted
    assert not ub.same_price_domain(Decimal("0.3849"), Decimal("0.8"))    # ASTRAL: refused


def test_c16_the_report_only_constants_are_recorded_as_class_b_choices() -> None:
    """Finding C16: three Class-B numbers carried no `decisions:` entry and one blamed the architect."""
    text = Path(ub.__file__).read_text(encoding="utf-8")
    for marker in ("decision B144", "decision B145", "Class-B, decision B145"):
        assert marker in text
    assert "80% is the architect's" not in text


class _Master:
    def token(self, symbol: str) -> str:
        return "1234"


class _View:
    factors: tuple = ()
    suppressions: tuple = ()
    pending_rights_ex_dates: tuple = ()
    parse_exceptions: tuple = ()

    def symbol_factors(self, **_kwargs):  # pragma: no cover - not reached by these paths
        return None


def _floor_pass_fixture(tmp_path: Path):
    daily = _daily_store(tmp_path)
    minute = _minute_store(tmp_path)
    cache = ub.build_daily_cache(daily, ["ACME"], DAYS[0], DAYS[-1])
    va.persist_map(_map(), data_dir=tmp_path / "data")
    config = ub.RunConfig(
        minute_store=minute, daily_store=daily, ledger_path=tmp_path / "l.json",
        map_data_dir=tmp_path / "data", end=DAYS[-1] + timedelta(days=1), start=DAYS[0],
    )
    record = ub.SymbolRecord(
        symbol="ACME", status=ub.STATUS_QUARANTINED, clamp_start=DAYS[0].isoformat(),
        gate1_pass=100, gate1_total=1000,
    )
    floor = va.EventFloor(
        ex_date=EX_DATE, floor_date=SPLICE, resolved=True,
        probes=(va.FloorProbe(day=SPLICE, verdict=va.FLOOR_IN),),
        note="measured", event_price_factor=K_PRICE,
    )
    return daily, minute, cache, config, record, floor


def test_c1_the_floor_passes_acceptance_orchestration_is_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding C1: 36 of 68 statements in `run_floor_pass` were executed by no test at all.

    This drives the SUCCESS path end to end -- hunt, floor-aware rebuild, re-apply to the store,
    re-gate, settle -- against real Parquet stores, with only the two network-touching helpers
    stubbed. The assertions are on what the acceptance block is FOR: the claims come off the map,
    the promotion is counted, the before/after snapshot is taken, and the store is actually repaired.
    """
    daily, minute, cache, config, record, floor = _floor_pass_fixture(tmp_path)
    rebuilt = _map(floors=[floor])
    monkeypatch.setattr(ub, "hunt_symbol_floors", lambda *a, **k: ([floor], ["measured"], 7))
    monkeypatch.setattr(ub, "build_map_for", lambda *a, **k: (rebuilt, 0, 0))

    ub.run_floor_pass(
        None, _Master(), cache, daily, record, _View(), DAYS[0], config, 1,
        ub.GateTally(), log=lambda _m: None,
    )

    assert record.floors_hunted and record.floor_discipline == ub.FLOOR_DISCIPLINE
    assert record.floors_resolved == 1                      # claimed FROM THE MAP (finding Q5)
    assert record.floor_ex_dates == [EX_DATE.isoformat()]
    assert record.pre_floor_gate1_total >= 0                # the before/after snapshot was taken
    assert "floor(s) resolved over 7 probe(s)" in record.floor_note
    assert record.status == ub.STATUS_SETTLED               # _settle ran on the fresh tally
    # and the acceptance actually repaired the store
    after = ub.gate_symbol(minute, cache, "ACME")
    assert after.gate1p_pass == after.gate1p_total


def test_c1_a_hunt_that_promotes_nothing_stops_composing_rounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision B136's round composition, executed: a round that promotes no era is the last."""
    daily, minute, cache, config, record, floor = _floor_pass_fixture(tmp_path)
    calls: list[int] = []

    def _hunt(*_a, **_k):
        calls.append(1)
        return ([floor], ["measured"], 3) if len(calls) == 1 else ([], [], 0)

    monkeypatch.setattr(ub, "hunt_symbol_floors", _hunt)
    monkeypatch.setattr(ub, "build_map_for", lambda *a, **k: (_map(floors=[floor]), 0, 0))
    ub.run_floor_pass(
        None, _Master(), cache, daily, record, _View(), DAYS[0], config, 1,
        ub.GateTally(), log=lambda _m: None,
    )
    # round 1 finds the floor; the rebuild promotes nothing new, so the composition stops there
    assert len(calls) == 1
    assert record.floor_probes_spent == 3


def test_the_gate1_band_and_the_containment_tolerance_are_still_byte_identical() -> None:
    """Nothing in FIX-5 widened an oracle: gate 1P is an ADDITION to the battery."""
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")
    assert qg.VOLUME_GAP_MAX_PCT == Decimal("5.0")
    assert va.DEFAULT_PRICE_CONTAINMENT_PAISE == 2
    assert va._PRICE_CONTAINMENT_REL == Decimal("0.001")   # noqa: SLF001
