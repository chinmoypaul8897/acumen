"""Chunk-5B FIX-3 wiring: the hunt scope, the widened reroute, and relief inside the gate tally.

Offline. The floor SEARCH itself is proved in ``tests/test_fix3_map_model.py``; what is proved
here is the RUNNER discipline the two rulings ask for -- that floors are hunted only where failure
is systematic, that a table-path symbol below the hunt line is rerouted so the search has a price
oracle at all, that a hunt and a reroute are each one-shot across a resume, and that a relieved day
is counted SEPARATELY from a gate-1 pass everywhere the tally is read.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import universe_backfill as ub
from acumen import vendor_adjustment as va
from acumen.adjustment_route import ROUTE_MAP_REQUIRED, ROUTE_TABLE_PATH
from acumen.corp_actions import KIND_DIVIDEND, KIND_SPLIT
from acumen.minute_store import MinuteStore
from acumen.minute_store import StoredBar

_ONE = Decimal(1)


def _record(**kwargs) -> ub.SymbolRecord:
    record = ub.SymbolRecord(symbol=kwargs.pop("symbol", "ACME"))
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


# --- the hunt scope is the ruling's own -------------------------------------------------


def test_a_quarantined_symbol_is_always_in_the_hunt_scope() -> None:
    record = _record(status=ub.STATUS_QUARANTINED, gate1_pass=400, gate1_total=1000)
    assert ub.floor_hunt_owed(record)


def test_a_settled_symbol_below_98_percent_is_in_the_hunt_scope() -> None:
    record = _record(status=ub.STATUS_SETTLED, gate1_pass=970, gate1_total=1000)
    assert record.gate1_rate < ub.FLOOR_HUNT_GATE1_MAX_RATE
    assert ub.floor_hunt_owed(record)


def test_a_settled_symbol_at_or_above_98_percent_is_not_hunted() -> None:
    record = _record(status=ub.STATUS_SETTLED, gate1_pass=980, gate1_total=1000)
    assert not ub.floor_hunt_owed(record), "no systematic failure -> nothing for a floor to explain"


def test_relief_can_lift_a_symbol_out_of_the_hunt_scope_and_that_is_deliberate() -> None:
    """A PNBHOUSING-shaped symbol whose above-ceiling failures are relieved as a market property
    does NOT have an adjustment problem, so spending ~11 probes an event on it measures noise."""
    record = _record(status=ub.STATUS_SETTLED, gate1_pass=900, gate1_total=1000, gate1_relieved=90)
    assert record.gate1_strict_rate == Decimal("0.9")
    assert record.gate1_rate == Decimal("0.99")
    assert not ub.floor_hunt_owed(record)


def test_a_hunt_is_one_shot_across_a_resume() -> None:
    """One-shot PER DISCIPLINE. The row must carry the discipline it was hunted under: Q-11
    addendum 4 widened WHAT may be hunted, so a row hunted under the older one is owed exactly one
    more pass (pinned by the next test) and a row already on this one is never re-probed."""
    record = _record(status=ub.STATUS_QUARANTINED, gate1_pass=1, gate1_total=1000,
                     floors_hunted=True, floor_discipline=ub.FLOOR_DISCIPLINE)
    assert not ub.floor_hunt_owed(record)


def test_a_stale_floor_discipline_reopens_the_hunt_exactly_once() -> None:
    record = _record(status=ub.STATUS_QUARANTINED, gate1_pass=1, gate1_total=1000,
                     floors_hunted=True, floor_discipline="")
    assert ub.floor_hunt_owed(record), "the FIX-3 hunt never asked the addendum-4 question"
    record.floor_discipline = ub.FLOOR_DISCIPLINE
    assert not ub.floor_hunt_owed(record), "and it is not asked twice"


def test_a_symbol_with_no_gated_day_is_never_hunted() -> None:
    assert not ub.floor_hunt_owed(_record(status=ub.STATUS_QUARANTINED))


# --- the reroute widened to the hunt line (the ruling's "incl. table-path re-routes") ------


def test_a_table_path_symbol_below_the_hunt_line_is_rerouted_even_though_it_settled() -> None:
    """DIXON / MOTHERSON / HDFCBANK are named in the floor ruling and are all TABLE-PATH and
    SETTLED -- a floor search needs the map's price oracle, which they do not otherwise have."""
    record = _record(route=ROUTE_TABLE_PATH, status=ub.STATUS_SETTLED,
                     gate1_pass=878, gate1_total=1000)
    assert ub.reroute_owed(record)


def test_a_table_path_symbol_above_the_hunt_line_is_left_on_the_cheap_path() -> None:
    record = _record(route=ROUTE_TABLE_PATH, status=ub.STATUS_SETTLED,
                     gate1_pass=993, gate1_total=1000)
    assert not ub.reroute_owed(record)


def test_a_map_required_symbol_is_never_rerouted_it_is_already_on_the_map_path() -> None:
    record = _record(route=ROUTE_MAP_REQUIRED, status=ub.STATUS_QUARANTINED,
                     gate1_pass=100, gate1_total=1000)
    assert not ub.reroute_owed(record)


def test_a_reroute_is_one_shot_across_a_resume() -> None:
    record = _record(route=ROUTE_TABLE_PATH, status=ub.STATUS_QUARANTINED,
                     gate1_pass=100, gate1_total=1000, reroute_attempted=True)
    assert not ub.reroute_owed(record)


def test_needs_reprocessing_names_both_owed_passes(tmp_path: Path) -> None:
    config = ub.RunConfig(
        minute_store=MinuteStore.at(tmp_path / "m"),
        daily_store=None,  # unused on this path
        ledger_path=tmp_path / "ledger.json",
        map_data_dir=tmp_path,
        end=date(2026, 7, 26),
    )
    owed_reroute = _record(route=ROUTE_TABLE_PATH, status=ub.STATUS_SETTLED,
                           gate1_pass=878, gate1_total=1000,
                           gate_definition=ub.GATE_DEFINITION,
                           rebuild_discipline=ub.REBUILD_DISCIPLINE)
    assert "recovery pass owed" in (ub.needs_reprocessing(owed_reroute, config) or "")
    owed_floor = _record(route=ROUTE_MAP_REQUIRED, status=ub.STATUS_SETTLED,
                         gate1_pass=878, gate1_total=1000,
                         gate_definition=ub.GATE_DEFINITION,
                         rebuild_discipline=ub.REBUILD_DISCIPLINE)
    # a map-required row with no map on disk is caught earlier, which is also correct
    assert ub.needs_reprocessing(owed_floor, config) is not None


def test_a_record_claiming_a_floor_its_map_no_longer_carries_is_re_processed(tmp_path: Path) -> None:
    """The claim/evidence invariant, enforced at RESUME level. `floors_hunted` is sticky, so a map
    rebuilt before floors were carried forward would otherwise leave the claim outliving its
    evidence forever -- and the next fresh fetch of those days dividing by a chain the vendor never
    applied."""
    end = date(2026, 7, 27)
    config = ub.RunConfig(
        minute_store=MinuteStore.at(tmp_path / "m"),
        daily_store=None,
        ledger_path=tmp_path / "ledger.json",
        map_data_dir=tmp_path,
        end=end,
    )
    era = va.EraResolution(
        label="e", ex_dates=(date(2024, 5, 15),),
        choices=(va.EventChoice(KIND_SPLIT, date(2024, 5, 15), Decimal("0.2"), va.SOURCE_OURS,
                                Decimal("0.2"), va.SOURCE_OURS),),
        k_price=Decimal("0.2"), k_volume=Decimal("0.2"), price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
    )
    floorless = va.AdjustmentMap(
        symbol="CANBK", fetch_date=end, all_event_ex_dates=(date(2024, 5, 15),), eras=(era,),
    )
    va.persist_map(floorless, data_dir=tmp_path)

    record = _record(symbol="CANBK", route=ROUTE_MAP_REQUIRED, status=ub.STATUS_SETTLED,
                     gate1_pass=2319, gate1_total=2429,
                     gate_definition=ub.GATE_DEFINITION,
                     rebuild_discipline=ub.REBUILD_DISCIPLINE,
                     floors_hunted=True, floors_resolved=1,
                     # already hunted under the CURRENT discipline, so the only thing that can
                     # re-open this row is the claim/evidence invariant this test is about
                     floor_discipline=ub.FLOOR_DISCIPLINE)
    why = ub.needs_reprocessing(record, config)
    assert why is not None and "carries none" in why

    # ... and once the map carries the floor again, the row is left alone
    va.persist_map(
        va.with_floors(floorless, [va.EventFloor(date(2024, 5, 15), date(2022, 5, 10), True)]),
        data_dir=tmp_path,
    )
    assert ub.needs_reprocessing(record, config) is None


def test_a_transient_vendor_error_leaves_the_floor_hunt_OPEN_for_the_next_run(tmp_path: Path) -> None:
    """CONTEXT 4.3: a transient "access denied" burst is NORMAL and must be retried, never read as
    an answer. A sticky `floors_hunted` would turn one rate-limit burst into a floor that is never
    measured -- and the symbol would silently keep un-adjusting by a chain the vendor never applied.
    """
    from acumen import smartapi_client as sac

    end = date(2026, 7, 27)
    config = ub.RunConfig(
        minute_store=MinuteStore.at(tmp_path / "m"), daily_store=None,
        ledger_path=tmp_path / "ledger.json", map_data_dir=tmp_path, end=end,
    )
    era = va.EraResolution(
        label="e", ex_dates=(date(2024, 5, 15),),
        choices=(va.EventChoice(KIND_SPLIT, date(2024, 5, 15), Decimal("0.2"), va.SOURCE_OURS,
                                Decimal("0.2"), va.SOURCE_OURS),),
        k_price=Decimal("0.2"), k_volume=Decimal("0.2"), price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
    )
    va.persist_map(
        va.AdjustmentMap(symbol="ACME", fetch_date=end,
                         all_event_ex_dates=(date(2024, 5, 15),), eras=(era,)),
        data_dir=tmp_path,
    )
    record = _record(symbol="ACME", route=ROUTE_MAP_REQUIRED, status=ub.STATUS_QUARANTINED,
                     gate1_pass=100, gate1_total=1000)

    class _Master:
        def token(self, symbol): return "1234"

    class _View:
        """The CA view the signature gate reads its events off (Q-11 addendum 4); empty here --
        this test is about what happens when the vendor errors, not about the signatures."""

        factors: tuple = ()
        suppressions: tuple = ()
        pending_rights_ex_dates: tuple = ()
        parse_exceptions: tuple = ()

    def _boom(*args, **kwargs):
        raise sac.SmartApiError("Access denied because of exceeding access rate")

    original = ub.hunt_symbol_floors
    ub.hunt_symbol_floors = _boom
    try:
        ub.run_floor_pass(None, _Master(), None, None, record, _View(), date(2016, 10, 1),
                          config, None, ub.GateTally(), log=lambda _m: None)
    finally:
        ub.hunt_symbol_floors = original

    assert record.floors_hunted is False, "a transient burst must not close the hunt"
    assert "RETRIED on the next run" in record.floor_note
    assert ub.floor_hunt_owed(record), "so the next run picks it up again"


def test_a_deterministic_hunt_failure_does_close_the_hunt(tmp_path: Path) -> None:
    """The mirror: an error that would fail identically forever must not loop the run every time."""
    end = date(2026, 7, 27)
    config = ub.RunConfig(
        minute_store=MinuteStore.at(tmp_path / "m"), daily_store=None,
        ledger_path=tmp_path / "ledger.json", map_data_dir=tmp_path, end=end,
    )
    record = _record(symbol="NOMAP", route=ROUTE_MAP_REQUIRED, status=ub.STATUS_QUARANTINED,
                     gate1_pass=100, gate1_total=1000)
    ub.run_floor_pass(None, None, None, None, record, None, date(2016, 10, 1),
                      config, None, ub.GateTally(), log=lambda _m: None)
    assert record.floors_hunted is True
    assert "no adjustment map on disk" in record.floor_note


def test_the_gate_definition_marker_moved_so_every_row_is_re_gated_under_relief() -> None:
    assert "auction-relief" in ub.GATE_DEFINITION
    assert "floor" in va.MAP_MODEL
    # ... and the invariant the marker exists FOR: a map written under the superseded FIX-3 model
    # is not current, so it is rebuilt from probe windows rather than consumed (Q-11 addendum 4
    # made the builder floor-aware and restricted probe days to trading sessions).
    stale = va.AdjustmentMap(
        symbol="ACME", fetch_date=date(2026, 7, 27), all_event_ex_dates=(), eras=(),
        map_model_id="compound-unparsed-nodes+application-floors-v3",
    )
    assert not va.map_is_current(stale)
    assert va.map_is_current(replace(stale, map_model_id=va.MAP_MODEL))


# --- relief inside the tally --------------------------------------------------------------


def test_a_relieved_day_is_counted_separately_and_never_folded_into_the_strict_pass() -> None:
    tally = ub.GateTally(gate1_pass=900, gate1_total=1000, gate1_relieved=50)
    assert tally.gate1_effective_pass == 950
    record = ub.SymbolRecord(symbol="ACME")
    record.apply_tally(tally)
    assert record.gate1_pass == 900, "the strict numerator is never overwritten"
    assert record.gate1_relieved == 50
    assert record.gate1_effective_pass == 950
    assert record.gate1_strict_rate == Decimal("0.9")
    assert record.gate1_rate == Decimal("0.95")


def test_relief_can_lift_a_symbol_out_of_quarantine_and_the_note_shows_both_numbers() -> None:
    tally = ub.GateTally(gate1_pass=700, gate1_total=1000, gate1_relieved=150)
    record = ub.SymbolRecord(symbol="ACME")
    record.apply_tally(tally)
    ub._settle(record, tally, ())
    assert record.gate1_strict_rate == Decimal("0.7"), "strict alone would quarantine it"
    assert record.gate1_rate == Decimal("0.85")
    assert record.status == ub.STATUS_SETTLED


def test_a_symbol_still_below_the_floor_after_relief_stays_quarantined_and_names_both() -> None:
    tally = ub.GateTally(gate1_pass=500, gate1_total=1000, gate1_relieved=100)
    record = ub.SymbolRecord(symbol="ACME")
    record.apply_tally(tally)
    ub._settle(record, tally, ())
    assert record.status == ub.STATUS_QUARANTINED
    assert "strict 50.0%" in record.note and "100 relieved" in record.note


# --- the floor search domain --------------------------------------------------------------


def _map_with_provable_and_unprovable_eras() -> va.AdjustmentMap:
    split_ex, div_ex = date(2024, 5, 15), date(2022, 6, 15)
    provable = va.EraResolution(
        label="pre-2022-06-15", ex_dates=(div_ex, split_ex),
        choices=(
            va.EventChoice(KIND_DIVIDEND, div_ex, _ONE, va.SOURCE_ABSENT, _ONE, va.SOURCE_OURS),
            va.EventChoice(KIND_SPLIT, split_ex, Decimal("0.2"), va.SOURCE_OURS,
                           Decimal("0.2"), va.SOURCE_OURS),
        ),
        k_price=Decimal("0.2"), k_volume=Decimal("0.2"), price_containment_paise=0,
        volume_gap_pct=Decimal("0.04"), provable=True, probe_days=(), note="",
    )
    unprovable = va.EraResolution(
        label="pre-2017-02-17", ex_dates=(date(2017, 2, 17), div_ex, split_ex), choices=(),
        k_price=_ONE, k_volume=_ONE, price_containment_paise=-1, volume_gap_pct=None,
        provable=False, probe_days=(), note="UN-PROVABLE",
    )
    return va.AdjustmentMap(
        symbol="CANBK", fetch_date=date(2026, 7, 26),
        all_event_ex_dates=(date(2017, 2, 17), div_ex, split_ex),
        eras=(provable, unprovable),
    )


def test_the_floor_search_domain_excludes_un_provable_eras_and_days_after_the_ex_date() -> None:
    amap = _map_with_provable_and_unprovable_eras()
    days = [date(2016, 12, 1), date(2018, 3, 1), date(2021, 5, 3), date(2025, 1, 6)]
    inside = ub.floor_candidate_days(amap, days, date(2024, 5, 15))
    assert inside == [date(2018, 3, 1), date(2021, 5, 3)]


def test_an_event_carrying_factor_one_offers_no_hypotheses_to_separate() -> None:
    amap = _map_with_provable_and_unprovable_eras()
    inside = ub.floor_candidate_days(amap, [date(2018, 3, 1)], date(2022, 6, 15))
    assert inside == [], "an ABSENT event has the same chain in and out; the day answers nothing"


def test_unparsed_ex_dates_reads_only_this_symbols_parse_exceptions() -> None:
    class _Action:
        def __init__(self, symbol: str, ex_date: date) -> None:
            self.symbol, self.ex_date = symbol, ex_date

    class _Exception:
        def __init__(self, action: "_Action") -> None:
            self.action = action

    class _View:
        parse_exceptions = (
            _Exception(_Action("COLPAL", date(2019, 4, 5))),
            _Exception(_Action("COLPAL", date(2017, 12, 18))),
            _Exception(_Action("OTHER", date(2020, 1, 1))),
        )

    assert ub.unparsed_ex_dates(_View(), "COLPAL") == (date(2017, 12, 18), date(2019, 4, 5))
