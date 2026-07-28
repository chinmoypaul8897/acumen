"""The chunk-5B FIX-3 map model: compound nodes, unparsed nodes, and vendor application floors.

All OFFLINE and deterministic. Three architect rulings are exercised here:

* **Q-11 addendum 3 clause (i)** -- events sharing an ex-date compose into ONE node (k = product,
  share-count flags combined). BAJAJFINSV is the live case: a 1:1 bonus AND a 5->1 face-value
  split, both ex 2022-09-13, which the pre-FIX-3 builder refused outright.
* **Q-11 addendum 3 clause (ii)** -- an UNPARSED subject enters the map with candidates
  ``{measured, absent}`` only. COLPAL is the live case: two unparsed dividend subjects forced it
  onto the map path and then contributed no era to probe, so its map was unbuildable.
* **Q-11 addendum 2** -- per-event vendor APPLICATION FLOORS, binary-searched. The search is
  driven here by a synthetic classifier, so its RESOLUTION (does it land on the true boundary, in
  the ruling's ~11 probes?) is proved without a network call.

The floor searches use a synthetic vendor: "the archive was spliced on date T, so bars before T
never carried the event". The tests assert the search recovers T exactly, and that every way the
model can fail to fit leaves the map UNCHANGED rather than guessing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from acumen import vendor_adjustment as va
from acumen.corp_actions import (
    DIVIDEND_SPECIAL,
    Factor,
    KIND_BONUS,
    KIND_DEMERGER,
    KIND_DIVIDEND,
    KIND_RIGHTS,
    KIND_SPLIT,
    Suppression,
)

_ONE = Decimal(1)


def _factor(kind: str, ex: date, k: str, symbol: str = "ACME") -> Factor:
    return Factor(symbol, ex, kind, Decimal(k), "synthetic")


# =========================================================================================
# Q-11 addendum 3 clause (i) -- the COMPOUND node
# =========================================================================================


def test_two_share_count_events_on_one_ex_date_compose_into_one_node() -> None:
    """The BAJAJFINSV shape: bonus 1:1 (k=0.5) + face-value split 5->1 (k=0.2), both ex the same
    day. k = product on BOTH sides, and the node stays share-count."""
    events = va.events_from_factor_table(
        [
            _factor(KIND_BONUS, date(2022, 9, 13), "0.5"),
            _factor(KIND_SPLIT, date(2022, 9, 13), "0.2"),
        ],
        symbol="ACME",
    )
    assert len(events) == 1, "one ex-date is one node -- the map keys eras by ex-date"
    node = events[0]
    assert node.ex_date == date(2022, 9, 13)
    assert node.our_price_factor == Decimal("0.1")
    assert node.our_volume_factor() == Decimal("0.1")
    assert node.is_share_count and node.is_compound
    assert node.kind == "bonus+split" and set(node.component_kinds) == {KIND_BONUS, KIND_SPLIT}


def test_the_pre_fix3_builder_refusal_can_no_longer_be_reached_from_the_factor_table() -> None:
    """The FIX-2 builder RAISED on two events sharing an ex-date. That guard is kept for a direct
    caller, but composition means the factor-table path can never hand it two."""
    events = va.events_from_factor_table(
        [
            _factor(KIND_BONUS, date(2022, 9, 13), "0.5"),
            _factor(KIND_SPLIT, date(2022, 9, 13), "0.2"),
        ],
        symbol="ACME",
    )
    assert len({e.ex_date for e in events}) == len(events)
    # the guard itself still fires when a caller builds the collision by hand
    hand_built = (
        va.EventSpec(KIND_BONUS, date(2022, 9, 13), Decimal("0.5"), True),
        va.EventSpec(KIND_SPLIT, date(2022, 9, 13), Decimal("0.2"), True),
    )
    with pytest.raises(va.VendorAdjustmentError, match="share an ex-date"):
        va.build_map("ACME", date(2026, 7, 26), hand_built, [])


def test_a_bonus_plus_a_special_dividend_composes_price_by_both_and_volume_by_the_bonus_only() -> None:
    """"share-count flags combined": a cash dividend moves the price and NOT the share count, so
    the node's volume ``ours`` must not inherit the dividend's price factor."""
    events = va.events_from_factor_table(
        [
            _factor(KIND_BONUS, date(2021, 5, 4), "0.5"),
            Factor("ACME", date(2021, 5, 4), KIND_DIVIDEND, Decimal("0.98"), "special",
                   classification=DIVIDEND_SPECIAL),
        ],
        symbol="ACME",
    )
    node = events[0]
    assert node.our_price_factor == Decimal("0.49")
    assert node.our_volume_factor() == Decimal("0.5")
    assert not node.is_share_count, "a mixed node must not claim volume-scales-with-price"


def test_a_component_with_no_factor_makes_the_whole_compound_have_no_ours() -> None:
    """A demerger sharing an ex-date with a bonus: we cannot claim to know a step we can only
    observe, so the node has no ``ours`` at all and is measured-or-absent."""
    events = va.events_from_factor_table(
        [_factor(KIND_BONUS, date(2023, 7, 20), "0.5")],
        [Suppression("ACME", date(2023, 7, 20), KIND_DEMERGER, "demerger")],
        symbol="ACME",
    )
    node = events[0]
    assert node.is_compound
    assert node.our_price_factor is None and node.our_volume_factor() is None


def test_a_single_event_date_composes_to_exactly_the_pre_compound_node() -> None:
    """Nothing about a symbol WITHOUT same-date events may move."""
    events = va.events_from_factor_table([_factor(KIND_BONUS, date(2020, 1, 1), "0.5")], symbol="ACME")
    node = events[0]
    assert node.kind == KIND_BONUS and not node.is_compound
    assert node.our_price_factor == Decimal("0.5") and node.our_volume_factor() == Decimal("0.5")


# =========================================================================================
# Q-11 addendum 3 clause (ii) -- the UNPARSED node
# =========================================================================================


def test_an_unparsed_subject_becomes_a_node_with_no_ours() -> None:
    events = va.events_from_factor_table(
        [], symbol="COLPAL", unparsed_ex_dates=[date(2017, 12, 18), date(2019, 4, 5)]
    )
    assert [e.ex_date for e in events] == [date(2017, 12, 18), date(2019, 4, 5)]
    for node in events:
        assert node.kind == va.KIND_UNPARSED
        assert node.our_price_factor is None, "clause (ii): candidates are {measured, absent}, no ours"
        assert node.our_volume_factor() is None
        assert not node.is_share_count


def test_a_symbol_whose_only_events_are_unparsed_now_produces_era_keys_to_probe() -> None:
    """The COLPAL defect exactly: parse exceptions forced MAP-REQUIRED but contributed no era, so
    the map had nothing to be built from and the symbol was 'map-required-but-unbuildable'."""
    before = va.events_from_factor_table([], symbol="COLPAL")
    after = va.events_from_factor_table(
        [], symbol="COLPAL", unparsed_ex_dates=[date(2017, 12, 18), date(2019, 4, 5)]
    )
    assert before == (), "the pre-FIX-3 behaviour: no events at all -> no era -> unbuildable map"
    assert len(after) == 2


def test_an_unparsed_subject_sharing_an_ex_date_with_a_real_event_joins_that_node() -> None:
    events = va.events_from_factor_table(
        [_factor(KIND_BONUS, date(2019, 4, 5), "0.5")],
        symbol="ACME",
        unparsed_ex_dates=[date(2019, 4, 5)],
    )
    assert len(events) == 1
    assert events[0].our_price_factor is None, "an unknown component makes the product unknown"
    assert va.KIND_UNPARSED in events[0].component_kinds


def test_two_unparsed_subjects_on_one_date_add_only_one_unknown() -> None:
    events = va.events_from_factor_table(
        [], symbol="ACME", unparsed_ex_dates=[date(2019, 4, 5), date(2019, 4, 5)]
    )
    assert len(events) == 1 and events[0].component_kinds == (va.KIND_UNPARSED,)


def test_an_unparsed_node_resolves_to_absent_when_it_moved_no_price() -> None:
    """An informational notice the parser could not classify must cost a probe window and change
    NO chain: ``absent`` (cost 1) beats ``measured`` (cost 2) in the min-cost arbitration."""
    ex = date(2019, 4, 5)
    fetch = date(2026, 7, 26)
    events = va.events_from_factor_table([], symbol="ACME", unparsed_ex_dates=[ex])
    # the vendor applied nothing: fetched == raw on every probe day
    probes = [
        va.ProbeDay(
            day=ex - timedelta(days=n), fetched_high=12_000, fetched_low=11_800,
            fetched_close=11_900, fetched_volume=99_500,
            raw_high=12_000, raw_low=11_800, raw_close=11_900, raw_volume=100_000,
        )
        for n in (5, 4, 3, 2)
    ]
    era = va.measure_era([ex], "pre-unparsed", probes)
    amap = va.build_map("ACME", fetch, events, [era])
    resolved = amap.eras[0]
    assert resolved.provable
    assert resolved.choices[0].price_source == va.SOURCE_ABSENT
    assert resolved.k_price == _ONE


def test_an_unparsed_node_that_DID_move_the_price_is_measured() -> None:
    """The other half of clause (ii): a real price move the parser could not name is MEASURED
    against the daily oracle like any other event."""
    ex = date(2019, 4, 5)
    fetch = date(2026, 7, 26)
    events = va.events_from_factor_table([], symbol="ACME", unparsed_ex_dates=[ex])
    k = Decimal("0.94")
    probes = [
        va.ProbeDay(
            day=ex - timedelta(days=n),
            fetched_high=int((Decimal(12_000) * k).quantize(_ONE, ROUND_HALF_EVEN)),
            fetched_low=int((Decimal(11_800) * k).quantize(_ONE, ROUND_HALF_EVEN)),
            fetched_close=int((Decimal(11_900) * k).quantize(_ONE, ROUND_HALF_EVEN)),
            fetched_volume=int((Decimal(100_000) / k).quantize(_ONE, ROUND_HALF_EVEN)),
            raw_high=12_000, raw_low=11_800, raw_close=11_900, raw_volume=100_000,
        )
        for n in (5, 4, 3, 2)
    ]
    era = va.measure_era([ex], "pre-unparsed", probes)
    amap = va.build_map("ACME", fetch, events, [era])
    choice = amap.eras[0].choices[0]
    assert amap.eras[0].provable
    assert choice.price_source == va.SOURCE_MEASURED
    assert abs(choice.price_factor - k) < Decimal("0.0005")


# =========================================================================================
# Q-11 addendum 2 -- the vendor APPLICATION FLOOR binary search
# =========================================================================================


def _spliced_classifier(days, floor: date, probes_seen: list[date]):
    """A synthetic vendor whose archive was spliced on ``floor``: bars stamped on or after it carry
    the event, bars before it do not. The classifier is what the real search injects, so this
    exercises the SEARCH, not the arithmetic."""

    def classify(day: date) -> va.FloorProbe:
        probes_seen.append(day)
        verdict = va.FLOOR_IN if day >= floor else va.FLOOR_OUT
        return va.FloorProbe(day=day, verdict=verdict)

    return classify


def _trading_days(start: date, count: int) -> list[date]:
    """``count`` weekday-only days from ``start`` -- a stand-in for a stored trading calendar."""
    out: list[date] = []
    day = start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


@pytest.mark.parametrize("floor_index", [1, 2, 37, 500, 1200, 2398])
def test_the_binary_search_lands_on_the_true_splice_date(floor_index: int) -> None:
    """Resolution: whatever the true boundary, the search returns it EXACTLY -- and within the
    ruling's own probe budget (~11), not by sweeping."""
    days = _trading_days(date(2016, 10, 3), 2400)
    floor = days[floor_index]
    seen: list[date] = []
    search = va.binary_search_floor(days, _spliced_classifier(days, floor, seen))
    assert search.resolved
    assert search.floor_date == floor
    assert len(seen) <= va.MAX_FLOOR_PROBES
    assert len(search.probes) == len(seen)


def test_the_search_reports_no_splice_when_the_event_is_applied_throughout() -> None:
    days = _trading_days(date(2016, 10, 3), 2400)
    seen: list[date] = []
    search = va.binary_search_floor(days, _spliced_classifier(days, days[0], seen))
    assert search.resolved and search.floor_date is None
    assert len(seen) == 2, "two endpoint probes settle it; no bisection is needed"
    assert "no splice inside our history" in search.note


def test_the_search_is_unresolved_when_the_event_is_absent_even_beside_its_ex_date() -> None:
    """If the newest day does not carry the event at all there is no floor to find -- and the map
    must be left exactly as it was, not given a fabricated boundary."""
    days = _trading_days(date(2016, 10, 3), 500)

    def never_applied(day: date) -> va.FloorProbe:
        return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)

    search = va.binary_search_floor(days, never_applied)
    assert not search.resolved and search.floor_date is None
    assert "no floor to find" in search.note


def test_an_undecided_midpoint_steps_to_a_neighbour_rather_than_sinking_the_search() -> None:
    """One damaged session in the middle of a decade must not cost the whole measurement."""
    days = _trading_days(date(2016, 10, 3), 2400)
    floor = days[1000]
    damaged = {days[1199]}  # the very first midpoint the bisection reaches

    def classify(day: date) -> va.FloorProbe:
        if day in damaged:
            return va.FloorProbe(day=day, verdict=va.FLOOR_UNDECIDED)
        return va.FloorProbe(day=day, verdict=va.FLOOR_IN if day >= floor else va.FLOOR_OUT)

    search = va.binary_search_floor(days, classify)
    assert search.resolved and search.floor_date == floor


def test_a_run_of_undecided_days_abandons_the_search_rather_than_guessing() -> None:
    days = _trading_days(date(2016, 10, 3), 400)

    def classify(day: date) -> va.FloorProbe:
        if day == days[-1]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_IN)
        if day == days[0]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)
        return va.FloorProbe(day=day, verdict=va.FLOOR_UNDECIDED)

    search = va.binary_search_floor(days, classify)
    assert not search.resolved and search.floor_date is None
    assert "no boundary is guessed" in search.note


def test_an_undecided_pair_next_to_the_boundary_terminates_instead_of_spinning() -> None:
    """The bisection must never step onto an endpoint: an endpoint's verdict is already the loop's
    invariant, so accepting it moves neither bound and the search would spin forever without
    spending a probe. Two undecided days wedged against the boundary is the exact shape."""
    days = _trading_days(date(2016, 10, 3), 4)

    def classify(day: date) -> va.FloorProbe:
        if day == days[-1]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_IN)
        if day == days[0]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)
        return va.FloorProbe(day=day, verdict=va.FLOOR_UNDECIDED)

    search = va.binary_search_floor(days, classify)
    assert not search.resolved
    assert len(search.probes) <= va.MAX_FLOOR_PROBES


@pytest.mark.parametrize("size", [2, 3, 4, 5, 6, 7, 9, 15, 33])
@pytest.mark.parametrize("undecided_from", [1, 2])
def test_no_arrangement_of_undecided_days_can_hang_the_bisection(size: int, undecided_from: int) -> None:
    """A hang is not a test failure -- it is a stuck live run. Sweep the small domains where the
    bounds sit closest together and assert every one of them TERMINATES with a bounded probe count."""
    days = _trading_days(date(2016, 10, 3), size)

    def classify(day: date) -> va.FloorProbe:
        if day == days[-1]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_IN)
        if day == days[0]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)
        index = days.index(day)
        if index >= undecided_from:
            return va.FloorProbe(day=day, verdict=va.FLOOR_UNDECIDED)
        return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)

    search = va.binary_search_floor(days, classify)
    assert len(search.probes) <= va.MAX_FLOOR_PROBES


def test_an_empty_domain_resolves_nothing() -> None:
    search = va.binary_search_floor([], lambda day: va.FloorProbe(day=day, verdict=va.FLOOR_IN))
    assert not search.resolved and not search.probes


def test_the_probe_budget_is_a_hard_cap() -> None:
    days = _trading_days(date(2016, 10, 3), 2400)
    seen: list[date] = []
    search = va.binary_search_floor(
        days, _spliced_classifier(days, days[1234], seen), max_probes=4
    )
    assert len(seen) <= 4
    assert not search.resolved, "a spent budget abandons; it never commits a half-searched boundary"


# --- the classifier that drives the real search -------------------------------------------


def _probe_at(day: date, cumulative: Decimal) -> va.ProbeDay:
    """A probe day whose fetched prices are ``raw x cumulative`` -- a known vendor, inverted."""
    raw_high, raw_low = 50_000, 49_000
    return va.ProbeDay(
        day=day,
        fetched_high=int((Decimal(raw_high) * cumulative).quantize(_ONE, ROUND_HALF_EVEN)),
        fetched_low=int((Decimal(raw_low) * cumulative).quantize(_ONE, ROUND_HALF_EVEN)),
        fetched_close=int((Decimal(49_500) * cumulative).quantize(_ONE, ROUND_HALF_EVEN)),
        fetched_volume=200_000,
        raw_high=raw_high, raw_low=raw_low, raw_close=49_500, raw_volume=200_000,
    )


def test_the_classifier_reads_event_in_and_event_out_off_price_containment() -> None:
    day = date(2021, 6, 1)
    # the vendor applied the event: fetched == raw x 0.2
    assert va.classify_floor_day(_probe_at(day, Decimal("0.2")), Decimal("0.2"), _ONE) == va.FLOOR_IN
    # the vendor did NOT: fetched == raw
    assert va.classify_floor_day(_probe_at(day, _ONE), Decimal("0.2"), _ONE) == va.FLOOR_OUT
    # a day that fits neither
    assert va.classify_floor_day(_probe_at(day, Decimal("0.7")), Decimal("0.2"), _ONE) == va.FLOOR_UNDECIDED
    # two identical hypotheses answer nothing
    assert va.classify_floor_day(_probe_at(day, _ONE), _ONE, _ONE) == va.FLOOR_UNDECIDED


# --- consumption: a committed floor drops the event from the older days' chain --------------


def _canbk_shaped_map(floor: date | None) -> va.AdjustmentMap:
    """One split (k=0.2) plus one absent dividend, the CANBK shape, with an optional floor."""
    split_ex, div_ex = date(2024, 5, 15), date(2022, 6, 15)
    era = va.EraResolution(
        label="pre-2022-06-15",
        ex_dates=(div_ex, split_ex),
        choices=(
            va.EventChoice(KIND_DIVIDEND, div_ex, _ONE, va.SOURCE_ABSENT, _ONE, va.SOURCE_OURS),
            va.EventChoice(KIND_SPLIT, split_ex, Decimal("0.2"), va.SOURCE_OURS,
                           Decimal("0.2"), va.SOURCE_OURS),
        ),
        k_price=Decimal("0.2"), k_volume=Decimal("0.2"),
        price_containment_paise=0, volume_gap_pct=Decimal("0.04"), provable=True,
        probe_days=(), note="",
    )
    floors = (
        () if floor is None
        else (va.EventFloor(ex_date=split_ex, floor_date=floor, resolved=True, note="measured"),)
    )
    return va.AdjustmentMap(
        symbol="CANBK", fetch_date=date(2026, 7, 26),
        all_event_ex_dates=(div_ex, split_ex), eras=(era,), floors=floors,
    )


def test_without_floors_the_chain_is_exactly_the_eras_committed_k() -> None:
    amap = _canbk_shaped_map(None)
    assert amap.factors_for_day(date(2018, 3, 1)) == (Decimal("0.2"), Decimal("0.2"))
    assert amap.factors_for_day(date(2022, 6, 1)) == (Decimal("0.2"), Decimal("0.2"))


def test_below_a_committed_floor_the_event_is_ABSENT_from_that_days_chain() -> None:
    amap = _canbk_shaped_map(date(2022, 6, 1))
    assert amap.factors_for_day(date(2018, 3, 1)) == (_ONE, _ONE), "below the splice: identity"
    assert amap.factors_for_day(date(2022, 6, 1)) == (Decimal("0.2"), Decimal("0.2"))
    assert amap.factors_for_day(date(2022, 6, 14)) == (Decimal("0.2"), Decimal("0.2"))


def test_a_floor_never_rescues_an_UN_PROVABLE_era() -> None:
    """The ruling's own closing sentence: "un-provable remains the honest fallback where no floor
    fits". There is no committed per-event chain to drop an event FROM."""
    amap = _canbk_shaped_map(date(2022, 6, 1))
    unprovable = va.EraResolution(
        label="pre-2017-02-17", ex_dates=(date(2017, 2, 17), date(2022, 6, 15), date(2024, 5, 15)),
        choices=(), k_price=_ONE, k_volume=_ONE, price_containment_paise=-1,
        volume_gap_pct=None, provable=False, probe_days=(), note="UN-PROVABLE",
    )
    amap = va.AdjustmentMap(
        symbol="CANBK", fetch_date=amap.fetch_date,
        all_event_ex_dates=(date(2017, 2, 17), date(2022, 6, 15), date(2024, 5, 15)),
        eras=(*amap.eras, unprovable), floors=amap.floors,
    )
    assert amap.factors_for_day(date(2016, 12, 1)) is None


def test_an_unresolved_floor_changes_nothing() -> None:
    amap = _canbk_shaped_map(None)
    unresolved = va.EventFloor(
        ex_date=date(2024, 5, 15), floor_date=None, resolved=False, note="stalled"
    )
    with_none = va.with_floors(amap, [unresolved])
    assert with_none.factors_for_day(date(2018, 3, 1)) == (Decimal("0.2"), Decimal("0.2"))


# --- persistence + staleness ---------------------------------------------------------------


def test_floors_survive_the_json_round_trip_with_their_probe_evidence() -> None:
    floor = va.EventFloor(
        ex_date=date(2024, 5, 15), floor_date=date(2022, 6, 1), resolved=True,
        probes=(
            va.FloorProbe(date(2018, 1, 2), va.FLOOR_OUT, Decimal("0.2"), _ONE,
                          Decimal("1.0"), Decimal("1.0")),
            va.FloorProbe(date(2023, 1, 2), va.FLOOR_IN, Decimal("0.2"), _ONE,
                          Decimal("0.2"), Decimal("0.2")),
        ),
        note="measured",
    )
    amap = va.with_floors(_canbk_shaped_map(None), [floor])
    restored = va.from_dict(va.to_dict(amap))
    assert restored.floors == amap.floors
    assert restored.factors_for_day(date(2018, 3, 1)) == (_ONE, _ONE)


def test_a_map_without_the_current_model_marker_is_stale_and_must_be_rebuilt() -> None:
    payload = va.to_dict(_canbk_shaped_map(None))
    assert va.map_is_current(va.from_dict(payload))
    payload.pop("map_model")
    assert not va.map_is_current(va.from_dict(payload)), (
        "a map written before the FIX-3 rulings has pre-compound era keys and must be rebuilt"
    )
    payload = va.to_dict(_canbk_shaped_map(None))
    payload["volume_estimator"] = "median-v1"
    assert not va.map_is_current(va.from_dict(payload))


# =========================================================================================
# The in-place rebuild must stay able to REPAIR a day once a floor drops its chain to 1
# =========================================================================================


def test_the_era_chain_ignores_floors_so_a_floored_day_stays_recognisable() -> None:
    """``factors_for_day`` says what the day should be un-adjusted BY; ``era_chain_for_day`` says
    what has ever been applied to it. The rebuild needs the second to generate its hypotheses."""
    amap = _canbk_shaped_map(date(2022, 6, 1))
    old_day = date(2018, 3, 1)
    assert amap.factors_for_day(old_day) == (_ONE, _ONE)
    assert amap.era_chain_for_day(old_day) == (Decimal("0.2"), Decimal("0.2"))
    assert amap.era_chain_for_day(date(2025, 1, 6)) == (_ONE, _ONE), "empty era key is the identity"


def test_a_day_divided_by_the_same_chain_TWICE_is_recognised_and_repaired() -> None:
    """The measured CANBK damage: 25x the raw price and 0.04x the raw volume, i.e. 1/k^2 for its
    k = 0.2 split -- the superseded one-way rebuild dividing a span the vendor never adjusted."""
    from acumen import minute_backfill as mb

    k = Decimal("0.2")
    raw_high, raw_low, raw_volume = 20_000, 19_500, 1_000_000
    stored = [
        _StoredBar(int(raw_high / (k * k)), int(raw_low / (k * k)), int(raw_volume * k * k)),
    ]
    row = {"high_paise": raw_high, "low_paise": raw_low, "volume": raw_volume}
    assert mb.stored_day_baseline(stored, row, k, k) == mb.BASELINE_OVER_DIVIDED_TWICE


@pytest.mark.parametrize(
    "power, expected",
    [
        (0, "raw"),
        (1, "over-divided"),
        (2, "over-divided-twice"),
    ],
)
def test_each_over_division_depth_is_a_distinct_well_separated_verdict(power: int, expected: str) -> None:
    from acumen import minute_backfill as mb

    k = Decimal("0.2")
    raw_high, raw_low, raw_volume = 20_000, 19_500, 1_000_000
    scale = _ONE / (k ** power)
    stored = [_StoredBar(int(raw_high * scale), int(raw_low * scale),
                         int(Decimal(raw_volume) / scale))]
    row = {"high_paise": raw_high, "low_paise": raw_low, "volume": raw_volume}
    assert mb.stored_day_baseline(stored, row, k, k) == expected


def test_the_vendors_own_bars_are_still_as_fetched_and_a_third_division_is_still_unknown() -> None:
    from acumen import minute_backfill as mb

    k = Decimal("0.2")
    raw_high, raw_low, raw_volume = 20_000, 19_500, 1_000_000
    as_fetched = [_StoredBar(int(raw_high * k), int(raw_low * k), int(Decimal(raw_volume) / k))]
    row = {"high_paise": raw_high, "low_paise": raw_low, "volume": raw_volume}
    assert mb.stored_day_baseline(as_fetched, row, k, k) == mb.BASELINE_AS_FETCHED
    thrice = [_StoredBar(int(raw_high / k**3), int(raw_low / k**3), int(Decimal(raw_volume) * k**3))]
    assert mb.stored_day_baseline(thrice, row, k, k) == mb.BASELINE_UNKNOWN, (
        "no factor is guessed past the hypotheses we can justify; gate 1 decides instead"
    )


class _StoredBar:
    """The structural minimum :func:`stored_day_baseline` reads off a stored bar."""

    def __init__(self, high: int, low: int, volume: int) -> None:
        self.high_paise, self.low_paise, self.volume = high, low, volume


def _day(scale: Decimal, raw_high: int = 20_000, raw_low: int = 19_500, raw_volume: int = 1_000_000):
    """A stored day sitting at ``scale`` x raw on price (and 1/scale on volume), plus its raw row."""
    stored = [_StoredBar(int(Decimal(raw_high) * scale), int(Decimal(raw_low) * scale),
                         int(Decimal(raw_volume) / scale))]
    return stored, {"high_paise": raw_high, "low_paise": raw_low, "volume": raw_volume}


def test_a_floor_that_removes_PART_of_the_chain_is_a_named_provenance_not_unknown() -> None:
    """The RELIANCE shape: the 2023 demerger (0.908) floored out of a chain that also carries two
    bonuses and a rights. The store sits at ``k_target/k_era`` = 1/0.908 of raw, which is NOT a
    power of either chain -- the pre-FIX-3 classifier refused it and the floor rewrote nothing."""
    from acumen import minute_backfill as mb

    k_era = Decimal("0.45")            # the full era chain
    k_target = k_era / Decimal("0.908")  # the demerger floored out
    stored, row = _day(k_target / k_era)
    assert mb.stored_day_baseline(stored, row, k_era, k_era) == mb.BASELINE_UNKNOWN, (
        "without the target chain the day's provenance is genuinely unnameable"
    )
    assert mb.stored_day_baseline(
        stored, row, k_era, k_era, k_price_target=k_target, k_volume_target=k_target
    ) == mb.BASELINE_PRE_FLOOR_DIVIDED


def test_a_wrong_floor_is_caught_rather_than_storing_a_scaled_price() -> None:
    """If the vendor DID apply the full chain on a day the floor calls unadjusted, the day sits at
    ``k_era/k_target`` and is named -- so the repair still lands on raw."""
    from acumen import minute_backfill as mb

    k_era = Decimal("0.45")
    k_target = k_era / Decimal("0.908")
    stored, row = _day(k_era / k_target)
    assert mb.stored_day_baseline(
        stored, row, k_era, k_era, k_price_target=k_target, k_volume_target=k_target
    ) == mb.BASELINE_FLOOR_OVERREACHED


def test_the_floor_provenances_are_not_offered_when_no_floor_changes_the_chain() -> None:
    """Passing the same chain twice must reproduce the pre-floor verdicts exactly."""
    from acumen import minute_backfill as mb

    k = Decimal("0.2")
    for scale, expected in ((_ONE, mb.BASELINE_RAW), (k, mb.BASELINE_AS_FETCHED),
                            (_ONE / k, mb.BASELINE_OVER_DIVIDED),
                            (_ONE / (k * k), mb.BASELINE_OVER_DIVIDED_TWICE)):
        stored, row = _day(scale)
        assert mb.stored_day_baseline(stored, row, k, k) == expected
        assert mb.stored_day_baseline(
            stored, row, k, k, k_price_target=k, k_volume_target=k
        ) == expected


def test_a_floored_factor_close_to_one_tightens_the_tolerance_instead_of_colliding() -> None:
    """The extension is only safe because the tolerance is DERIVED from the candidate set.

    A 0.5% floored factor puts two hypotheses 0.5% apart. The property that must hold is that no
    ratio can ever be claimed by two of them -- with the old fixed 2% window both would have claimed
    everything in between. A ratio far from every hypothesis must still come back UNKNOWN.
    """
    from acumen import minute_backfill as mb

    k_era = Decimal("0.45")
    k_target = k_era / Decimal("0.995")           # a 0.5% floored factor
    kwargs = {"k_price_target": k_target, "k_volume_target": k_target}

    exact, row = _day(k_target / k_era)            # exactly on the new hypothesis
    assert mb.stored_day_baseline(exact, row, k_era, k_era, **kwargs) == mb.BASELINE_PRE_FLOOR_DIVIDED
    raw_day, row = _day(_ONE)
    assert mb.stored_day_baseline(raw_day, row, k_era, k_era, **kwargs) == mb.BASELINE_RAW

    # 1% off both -- outside every window, so no factor is guessed
    off, row = _day(Decimal("1.0150"))
    assert mb.stored_day_baseline(off, row, k_era, k_era, **kwargs) == mb.BASELINE_UNKNOWN

    # and the uniqueness property itself, swept: no ratio is ever within tolerance of two candidates
    candidates = [_ONE, k_era, _ONE / k_era, _ONE / (k_era * k_era),
                  k_target / k_era, k_era / k_target]
    gaps = [abs(a / b - _ONE) for i, a in enumerate(candidates) for b in candidates[i + 1:] if a != b]
    tol = min([Decimal("0.02"), *[gap / Decimal(2) for gap in gaps]])
    for value in candidates:
        claimants = [c for c in candidates if abs(value / c - _ONE) <= tol]
        assert claimants == [value], f"{value} is claimed by more than one hypothesis"


# =========================================================================================
# A rebuilt map must not silently drop an already-measured floor
# =========================================================================================


def test_a_measured_floor_is_carried_onto_a_map_rebuilt_under_a_newer_fetch_date() -> None:
    """The map is rebuilt whenever its fetch date moves -- i.e. every calendar day. A floor is a
    property of the VENDOR'S ARCHIVE, not of when we last looked, so it must survive the rebuild;
    otherwise the committed probe evidence the ruling requires is lost the next morning."""
    measured = _canbk_shaped_map(date(2022, 6, 1))
    rebuilt = replace(_canbk_shaped_map(None), fetch_date=date(2026, 7, 28))
    assert rebuilt.floors == (), "a freshly-built map has no floors of its own"
    carried, dropped = va.carry_floors_forward(measured, rebuilt)
    assert dropped == ()
    assert len(carried.floors) == 1 and carried.floors[0].floor_date == date(2022, 6, 1)
    assert carried.factors_for_day(date(2018, 3, 1)) == (_ONE, _ONE)


def test_a_floor_whose_event_now_resolves_differently_is_DROPPED_not_reused() -> None:
    """Each probe asked "does this day fit with THIS factor in the chain, or out of it?" -- so a
    changed factor invalidates the measurement. Reusing it would be committing a floor nothing
    measured."""
    measured = _canbk_shaped_map(date(2022, 6, 1))
    moved = _canbk_shaped_map(None)
    era = moved.eras[0]
    changed = replace(
        era,
        choices=tuple(
            replace(c, price_factor=Decimal("0.5")) if c.kind == KIND_SPLIT else c
            for c in era.choices
        ),
    )
    rebuilt = replace(moved, eras=(changed,), fetch_date=date(2026, 7, 28))
    carried, dropped = va.carry_floors_forward(measured, rebuilt)
    assert carried.floors == ()
    assert len(dropped) == 1 and dropped[0].ex_date == date(2024, 5, 15)


def test_carrying_forward_is_a_no_op_when_there_was_nothing_to_carry() -> None:
    fresh = _canbk_shaped_map(None)
    assert va.carry_floors_forward(None, fresh) == (fresh, ())
    assert va.carry_floors_forward(_canbk_shaped_map(None), fresh) == (fresh, ())


def test_canonical_event_factors_reads_the_newest_provable_era_and_skips_unprovable_ones() -> None:
    amap = _canbk_shaped_map(None)
    canon = va.canonical_event_factors(amap)
    assert canon[date(2024, 5, 15)][0] == Decimal("0.2")
    assert canon[date(2022, 6, 15)][0] == _ONE
    empty = va.AdjustmentMap(
        symbol="X", fetch_date=date(2026, 7, 26), all_event_ex_dates=(date(2020, 1, 1),),
        eras=(va.EraResolution("e", (date(2020, 1, 1),), (), _ONE, _ONE, -1, None, False, (), ""),),
    )
    assert va.canonical_event_factors(empty) == {}
