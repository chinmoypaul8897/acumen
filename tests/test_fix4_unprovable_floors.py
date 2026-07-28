"""The chunk-5B FIX-4 ruling: FLOORS IN UN-PROVABLE ERAS (QUESTIONS.md Q-11 addendum 4).

All OFFLINE and deterministic -- the vendor is synthetic, so the four guards are proved without a
network call:

* **clause (i) SIGNATURE GATE** -- an event is admitted into an un-provable era's hunt only by the
  gate-3 raw-gap-near-zero signature or by an era failure-rate cliff. The decisive tests here are
  the NEGATIVE ones: a non-qualifying event is not hunted, and its domain stays exactly the one
  decision B123 gave it.
* **clause (ii) ONE FRESH UNKNOWN** -- the hypothesis an un-provable era is tested against is built
  from previously committed sources (else our own CONTEXT 4.2 factor), and an era holding an event
  with neither is REFUSED rather than fitted.
* **clause (iii) ACCEPTANCE UNCHANGED** -- a measured floor goes back through the map BUILDER, and
  the era becomes provable only if it satisfies the same 2-paise containment and the same unwidened
  gate-1 band as every other era. The refusal path (no fit -> stays un-provable) is tested beside
  the acceptance path, on the same data with one number moved.
* **clause (iv) PROVENANCE** -- the floor round-trips through the map JSON with its probes, its
  verdicts and the factor they were classified under.

Plus the enriched baseline classifier the promotion needs: a day of a newly-provable era sits at the
vendor's OWN chain (`as-fetched-floored`), which no pre-FIX-4 hypothesis named.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from acumen import minute_backfill as mb
from acumen import universe_backfill as ub
from acumen import vendor_adjustment as va
from acumen.corp_actions import Factor, KIND_BONUS, KIND_DIVIDEND, KIND_SPLIT

_ONE = Decimal(1)


def _factor(kind: str, ex: date, k: str, symbol: str = "ACME") -> Factor:
    return Factor(symbol, ex, kind, Decimal(k), "synthetic")


def _trading_days(start: date, count: int) -> list[date]:
    out: list[date] = []
    day = start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _probe(day: date, applied: Decimal, *, raw_high=12_000, raw_low=11_800,
           raw_volume=100_000) -> va.ProbeDay:
    """A probe day whose fetched bars carry exactly ``applied`` of adjustment."""
    q = lambda value: int((Decimal(value) * applied).quantize(_ONE, ROUND_HALF_EVEN))  # noqa: E731
    return va.ProbeDay(
        day=day,
        fetched_high=q(raw_high), fetched_low=q(raw_low), fetched_close=q(11_900),
        fetched_volume=int((Decimal(raw_volume) / applied).quantize(_ONE, ROUND_HALF_EVEN)),
        raw_high=raw_high, raw_low=raw_low, raw_close=11_900, raw_volume=raw_volume,
    )


def _gate3_row(symbol: str, ex: date, k: str, raw_gap: str, adjusted_gap: str) -> str:
    return "|".join((
        symbol, KIND_BONUS, ex.isoformat(), k,
        (ex - timedelta(days=1)).isoformat(), ex.isoformat(), raw_gap, adjusted_gap, "synthetic",
    ))


# =========================================================================================
# clause (i) -- the SIGNATURE GATE
# =========================================================================================


@pytest.mark.parametrize(
    "k, raw_gap, admitted",
    [
        # the eleven the architect named, by shape: a raw gap far smaller than the event's own step
        ("0.5", "0.17", True),      # IOC 2016-10-18
        ("0.5", "-2.77", True),     # IOC 2018-03-15
        ("0.6666666666666666666666666667", "1.43", True),   # IOC 2022-06-30
        ("0.5", "-0.87", True),     # PETRONET 2017-07-03
        ("0.6666666666666666666666666667", "-0.35", True),  # HINDPETRO 2017-07-11
        ("0.1", "5.22", True),      # BEL 2017-03-16
        ("0.25", "10.98", True),    # INOXWIND 2024-05-24
        ("0.5", "10.44", True),     # BDL 2024-05-24
        ("0.75", "-2.52", True),    # GAIL 2017-03-09
        ("0.75", "-4.63", True),    # OIL 2017-01-12
        ("0.6666666666666666666666666667", "8.62", True),   # UPL 2019-07-02
        # and the six that are a DIFFERENT defect -- a mis-scaled span, not a floor
        ("0.8", "38.49", False),    # ASTRAL 2019-09-16: +38% against a 10% half-step
        ("0.6666666666666666666666666667", "101.21", False),   # BPCL 2017-07-13
        ("0.75", "201.98", False),  # GAIL 2018-03-27
        ("0.6666666666666666666666666667", "42.44", False),    # OIL 2018-03-27
        ("0.6666666666666666666666666667", "-65.70", False),   # VBL 2021-06-10
        ("0.5", "-40.00", False),   # COCHINSHIP 2024-01-10: nearly its own healthy -50%
    ],
)
def test_the_gate3_signature_admits_exactly_the_rows_the_architect_named(
    k: str, raw_gap: str, admitted: bool
) -> None:
    ex = date(2019, 9, 16)
    found = ub.gate3_signature_events([_gate3_row("ACME", ex, k, raw_gap, "99.00")])
    assert (ex in found) is admitted, (
        f"|raw {raw_gap}%| vs half-step {abs(Decimal(k) - _ONE) / 2 * 100:.2f}%"
    )


def test_the_signature_is_scale_free_not_a_percentage_threshold() -> None:
    """A 5:1 split's step is 80%; a 5% special dividend's is 5%. The same raw gap of 3% is the
    same-domain signature for the split and a healthy move for the dividend -- one threshold could
    never say both."""
    ex = date(2020, 1, 6)
    split = ub.gate3_signature_events([_gate3_row("ACME", ex, "0.2", "3.00", "80.00")])
    dividend = ub.gate3_signature_events([_gate3_row("ACME", ex, "0.95", "3.00", "25.00")])
    assert ex in split
    assert ex not in dividend


def test_an_era_failure_rate_cliff_admits_an_event_with_no_gate3_row_at_all() -> None:
    ex = date(2021, 6, 10)
    days = _trading_days(date(2021, 1, 4), 200)
    tally = ub.GateTally(gate1_days=list(days))
    tally.gate1_failures = [(d, Decimal("-9"), 1) for d in days if d < ex]
    found = ub.era_cliff_events(tally, [ex])
    assert ex in found and ub.SIGNATURE_CLIFF in found[ex]


def test_a_short_span_cannot_manufacture_a_cliff() -> None:
    """A handful of days at 100% is a coincidence, not a property of a span -- admitting it would
    turn the signature gate into the blanket hunt the ruling forbids."""
    ex = date(2021, 6, 10)
    days = _trading_days(date(2021, 6, 1), 5)
    tally = ub.GateTally(gate1_days=list(days))
    tally.gate1_failures = [(d, Decimal("-9"), 1) for d in days]
    assert ub.era_cliff_events(tally, [ex]) == {}
    assert len(days) < ub.MIN_CLIFF_DAYS


def test_a_span_that_mostly_reconciles_is_not_a_cliff() -> None:
    ex = date(2021, 6, 10)
    days = _trading_days(date(2021, 1, 4), 100)
    tally = ub.GateTally(gate1_days=list(days))
    below = [d for d in days if d < ex]
    tally.gate1_failures = [(d, Decimal("-9"), 1) for d in below[: int(len(below) * 0.9)]]
    assert ub.era_cliff_events(tally, [ex]) == {}, "90% is below the ruling's 95% cliff"


# =========================================================================================
# clause (i), the decisive negative -- a NON-QUALIFYING event is NOT hunted
# =========================================================================================


def _unprovable_map(ex: date, fetch: date) -> va.AdjustmentMap:
    """A one-era map whose only era is UN-PROVABLE -- the B123 deadlock, in miniature."""
    era = va.EraResolution(
        label="pre-" + ex.isoformat(), ex_dates=(ex,), choices=(),
        k_price=_ONE, k_volume=_ONE, price_containment_paise=-1, volume_gap_pct=None,
        provable=False, probe_days=(), note="UN-PROVABLE",
    )
    return va.AdjustmentMap(
        symbol="ACME", fetch_date=fetch, all_event_ex_dates=(ex,), eras=(era,),
    )


def test_a_non_qualifying_event_is_never_hunted_inside_an_un_provable_era() -> None:
    """The ruling's own guard: "hunting is SIGNATURE-GATED, never blanket". Without a signature the
    domain is exactly what decision B123 allowed -- the provable-era days, of which there are
    none -- so no probe is spent and the map is untouched."""
    ex = date(2024, 5, 24)
    amap = _unprovable_map(ex, date(2026, 7, 27))
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    gated = _trading_days(date(2022, 1, 3), 400)
    tally = ub.GateTally(gate1_days=gated)

    probed: list[date] = []

    def _probe_one(_client, _store, _symbol, _token, day):
        probed.append(day)
        return None

    original = va.probe_one_day
    va.probe_one_day = _probe_one
    try:
        floors, findings, spent = ub.hunt_symbol_floors(
            None, None, "ACME", "1", amap, tally,
            events=events, signatures={}, log=lambda _m: None,
        )
    finally:
        va.probe_one_day = original

    assert floors == [] and spent == 0 and probed == []
    assert any("no signature admits" in f for f in findings)


def test_the_same_event_IS_hunted_once_a_signature_admits_it() -> None:
    """One number moves -- the signature -- and the identical map, days and tally are searched.
    That is the whole widening, isolated."""
    ex = date(2024, 5, 24)
    amap = _unprovable_map(ex, date(2026, 7, 27))
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    hypotheses, refusals = ub.era_hypotheses_for(amap, events, ex)
    assert not refusals and hypotheses, "our own k=0.5 is the TARGET's hypothesis (clause ii)"
    gated = _trading_days(date(2022, 1, 3), 400)
    tally = ub.GateTally(gate1_days=gated)
    tally.gate1_failures = [(d, Decimal("-9"), 1) for d in gated]

    splice = gated[200]

    def _probe_one(_client, _store, _symbol, _token, day):
        # a synthetic vendor spliced at `splice`: from it on the 0.5 split is baked in
        return _probe(day, Decimal("0.5") if day >= splice else _ONE)

    original = va.probe_one_day
    va.probe_one_day = _probe_one
    try:
        floors, _findings, spent = ub.hunt_symbol_floors(
            None, None, "ACME", "1", amap, tally,
            events=events,
            signatures={ex: "test signature"},
            log=lambda _m: None,
        )
    finally:
        va.probe_one_day = original

    assert len(floors) == 1 and floors[0].resolved
    assert floors[0].floor_date == splice
    assert 0 < spent <= va.MAX_FLOOR_PROBES
    assert floors[0].event_price_factor == Decimal("0.5"), "clause (iv): provenance"


def test_a_previously_measured_floor_re_admits_itself_without_a_signature() -> None:
    """The repair erases its own justification: once a floor fixes a span, that span no longer
    fails, so neither signature fires and a re-measurement would be impossible. A floor the record
    already holds is therefore its own admission -- the same trap decision B125 caught on the
    failure-rate gate, one level up."""
    ex = date(2024, 5, 24)
    amap = _unprovable_map(ex, date(2026, 7, 27))
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    gated = _trading_days(date(2022, 1, 3), 400)
    tally = ub.GateTally(gate1_days=gated)  # NOTHING fails: the floor already repaired it
    splice = gated[200]

    def _probe_one(_client, _store, _symbol, _token, day):
        return _probe(day, Decimal("0.5") if day >= splice else _ONE)

    original = va.probe_one_day
    va.probe_one_day = _probe_one
    try:
        floors, _findings, _spent = ub.hunt_symbol_floors(
            None, None, "ACME", "1", amap, tally, events=events, signatures={},
            force_ex_dates=frozenset({ex}), log=lambda _m: None,
        )
    finally:
        va.probe_one_day = original
    assert len(floors) == 1 and floors[0].resolved and floors[0].floor_date == splice


# =========================================================================================
# the Q-5 ruling reaches the MEASUREMENT days
# =========================================================================================


def test_a_weekend_session_is_never_a_probe_day() -> None:
    """Q-5: "weekend-dated sessions are EXCLUDED from trading days ... even when a bhavcopy
    exists". A day that is not a trading day cannot be a measurement day either. Measured live:
    NSE's Saturday 2024-05-18 sits inside BDL's and INOXWIND's pre-ex probe windows and the
    vendor's 1-minute volume for it recovers 0.259 / 0.196 of the raw daily against 0.500 / 0.246
    on the sessions beside it -- which made the only correct chain un-provable."""
    saturday = date(2024, 5, 18)
    assert saturday.weekday() == 5 and not ub.is_measurable_session(saturday)
    ex = date(2024, 5, 24)
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    days = [date(2024, 5, 15), date(2024, 5, 16), date(2024, 5, 17), saturday,
            date(2024, 5, 21), date(2024, 5, 22), date(2024, 5, 23)]
    windows, unprobeable = ub.era_probe_windows(
        events, days, date(2016, 10, 1), date(2026, 7, 27),
    )
    assert not unprobeable and len(windows) == 1
    assert windows[0].start == date(2024, 5, 17) and windows[0].end == date(2024, 5, 23)


def test_a_weekend_session_returned_INSIDE_a_probe_window_is_dropped_at_the_fold() -> None:
    """The window is a date RANGE, so choosing weekday-only days is not enough -- the vendor still
    returns the Saturday inside it. This is the half that actually saved BDL: without it the era's
    measurement still carries the excluded session's volume."""
    ex = date(2024, 5, 24)
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    days = [date(2024, 5, 17), date(2024, 5, 18), date(2024, 5, 21), date(2024, 5, 22)]

    class _Client:
        def get_candles(self, _token, _interval, start, end):
            from acumen.minute_unadjust import OneMinuteBar
            from datetime import datetime, time as _time
            bars = []
            for day in days:
                # the Saturday's volume is HALF what the real sessions carry -- the live shape
                volume = 50_000 if day.weekday() >= 5 else 100_000
                bars.append(OneMinuteBar(
                    stamp=datetime.combine(day, _time(9, 15)),
                    open_paise=6_000, high_paise=6_000, low_paise=5_900, close_paise=5_950,
                    volume=volume,
                ))
            return bars

    class _DailyStore:
        def daily(self, _symbol, day, _to):
            import pandas as pd
            return pd.DataFrame([{
                "high_paise": 12_000, "low_paise": 11_800, "close_paise": 11_900,
                "volume": 50_000,
            }])

    eras = va.measure_symbol_live(
        _Client(), _DailyStore(), "ACME", "1", events,
        [va.WindowSpec(label="pre-2024-05-24", start=days[0], end=days[-1])],
        date(2026, 7, 27),
    )
    probed = {p.day for era in eras for p in era.probe_days}
    assert date(2024, 5, 18) not in probed
    assert probed == {date(2024, 5, 17), date(2024, 5, 21), date(2024, 5, 22)}


def test_a_weekend_session_is_never_a_floor_probe_day_either() -> None:
    ex = date(2024, 5, 24)
    amap = _unprovable_map(ex, date(2026, 7, 27))
    events = va.events_from_factor_table([_factor(KIND_SPLIT, ex, "0.5")], symbol="ACME")
    hypotheses, _ = ub.era_hypotheses_for(amap, events, ex)
    days = [date(2024, 5, 17), date(2024, 5, 18), date(2024, 5, 21)]
    assert ub.floor_candidate_days(amap, days, ex, hypotheses) == [
        date(2024, 5, 17), date(2024, 5, 21),
    ]


# =========================================================================================
# clause (ii) -- one fresh unknown per era, and the refusal when there is none
# =========================================================================================


def test_the_hypothesis_uses_a_committed_source_before_our_own_factor() -> None:
    newer, older = date(2024, 5, 24), date(2020, 2, 24)
    fetch = date(2026, 7, 27)
    committed = va.EraResolution(
        label="pre-" + newer.isoformat(), ex_dates=(newer,),
        choices=(va.EventChoice(KIND_SPLIT, newer, Decimal("0.4"), va.SOURCE_MEASURED,
                                Decimal("0.4"), va.SOURCE_PRICE_FACTOR),),
        k_price=Decimal("0.4"), k_volume=Decimal("0.4"), price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
    )
    unprovable = va.EraResolution(
        label="pre-" + older.isoformat(), ex_dates=(older, newer), choices=(),
        k_price=_ONE, k_volume=_ONE, price_containment_paise=-1, volume_gap_pct=None,
        provable=False, probe_days=(), note="UN-PROVABLE",
    )
    amap = va.AdjustmentMap(
        symbol="ACME", fetch_date=fetch, all_event_ex_dates=(older, newer),
        eras=(committed, unprovable),
    )
    events = va.events_from_factor_table(
        [_factor(KIND_SPLIT, newer, "0.5"), _factor(KIND_BONUS, older, "0.5")], symbol="ACME"
    )
    by_event = {e.ex_date: e for e in events}
    choices = va.era_hypothesis(amap, unprovable, by_event, target_ex_date=older)
    assert choices is not None
    by_ex = {c.ex_date: c for c in choices}
    assert by_ex[newer].price_factor == Decimal("0.4"), "the MEASURED value the newer era committed"
    assert by_ex[newer].price_source == va.SOURCE_MEASURED
    assert by_ex[older].price_factor == Decimal("0.5"), "the TARGET may use our own factor"
    assert by_ex[older].price_source == va.SOURCE_OURS


def test_a_second_uncommitted_event_is_two_unknowns_and_the_era_is_REFUSED() -> None:
    """Clause (ii) is a discipline, not a preference. Filling a second uncommitted slot with `ours`
    would assume the vendor used our factor -- measured live on IOC, where the vendor applies NO
    special dividend, so `ours` there puts BOTH hypotheses ~3% off and turns every decisive probe
    into an undecided one. Refusing is what keeps a floor search a measurement."""
    target, other = date(2020, 2, 24), date(2022, 3, 10)
    fetch = date(2026, 7, 27)
    era = va.EraResolution(
        label="pre-old", ex_dates=(target, other), choices=(),
        k_price=_ONE, k_volume=_ONE, price_containment_paise=-1, volume_gap_pct=None,
        provable=False, probe_days=(), note="UN-PROVABLE",
    )
    amap = va.AdjustmentMap("ACME", fetch, (target, other), (era,))
    events = va.events_from_factor_table(
        [_factor(KIND_BONUS, target, "0.5"), _factor(KIND_DIVIDEND, other, "0.97")], symbol="ACME"
    )
    hypotheses, refusals = ub.era_hypotheses_for(amap, events, target)
    assert hypotheses == {}
    assert refusals and "more than one unknown" in refusals[0]
    assert other.isoformat() in refusals[0]


def test_an_era_whose_only_event_has_no_ours_and_no_commitment_is_REFUSED() -> None:
    """A demerger has no `ours` factor at all. Even as the target there is nothing to test the
    presence of, so the era is refused rather than fitted."""
    from acumen.corp_actions import Suppression

    ex = date(2019, 12, 20)
    amap = _unprovable_map(ex, date(2026, 7, 27))
    events = va.events_from_factor_table(
        [], [Suppression("ACME", ex, "demerger", "synthetic")], symbol="ACME",
    )
    hypotheses, refusals = ub.era_hypotheses_for(amap, events, ex)
    assert hypotheses == {}
    assert refusals and "no committed source" in refusals[0]


# =========================================================================================
# the missing outcome: a floor ABOVE our whole history
# =========================================================================================


def test_absent_throughout_needs_three_out_probes_not_one() -> None:
    days = _trading_days(date(2016, 10, 3), 800)
    ex = date(2024, 5, 24)
    seen: list[date] = []

    def never_applied(day: date) -> va.FloorProbe:
        seen.append(day)
        return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)

    search = va.binary_search_floor(days, never_applied, absent_floor_date=ex)
    assert search.resolved and search.floor_date == ex
    assert len(seen) == 3, "newest, oldest and a midpoint -- one probe is not a measurement"
    assert "absent from every chain in our history" in search.note


def test_one_event_in_day_refuses_the_absent_throughout_conclusion() -> None:
    days = _trading_days(date(2016, 10, 3), 800)
    ex = date(2024, 5, 24)

    def classify(day: date) -> va.FloorProbe:
        # the oldest day DOES carry the event: the step model does not hold, so nothing is claimed
        verdict = va.FLOOR_IN if day == days[0] else va.FLOOR_OUT
        return va.FloorProbe(day=day, verdict=verdict)

    search = va.binary_search_floor(days, classify, absent_floor_date=ex)
    assert not search.resolved and search.floor_date is None


def test_an_undecided_day_refuses_the_absent_throughout_conclusion() -> None:
    days = _trading_days(date(2016, 10, 3), 800)
    ex = date(2024, 5, 24)

    def classify(day: date) -> va.FloorProbe:
        if day == days[len(days) // 2]:
            return va.FloorProbe(day=day, verdict=va.FLOOR_UNDECIDED)
        return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)

    search = va.binary_search_floor(days, classify, absent_floor_date=ex)
    assert not search.resolved


def test_without_the_ruling_the_same_all_out_span_stays_unresolved() -> None:
    """The pre-FIX-4 behaviour is untouched: no ``absent_floor_date``, no new conclusion."""
    days = _trading_days(date(2016, 10, 3), 800)

    def never_applied(day: date) -> va.FloorProbe:
        return va.FloorProbe(day=day, verdict=va.FLOOR_OUT)

    search = va.binary_search_floor(days, never_applied)
    assert not search.resolved and "no floor to find" in search.note


def test_an_absent_throughout_floor_removes_the_event_from_every_chain() -> None:
    ex = date(2024, 5, 24)
    floor = va.EventFloor(ex_date=ex, floor_date=ex, resolved=True)
    assert floor.absent_throughout
    assert not floor.applies_on(ex - timedelta(days=1))
    assert not floor.applies_on(date(2016, 10, 3))


# =========================================================================================
# clause (iii) -- ACCEPTANCE is the map builder's own oracle, and REFUSAL is its refusal
# =========================================================================================


def _era_pair(ex_new: date, ex_old: date, older_applied: Decimal):
    """A two-era measurement set: the newer era carries a 0.5 split, the older one carries
    ``older_applied`` (== 0.5 when the vendor applied the split there, 1 when it did not)."""
    newer = va.measure_era(
        [ex_new], "pre-new",
        [_probe(ex_new - timedelta(days=n), Decimal("0.5")) for n in (5, 4, 3, 2)],
    )
    older = va.measure_era(
        [ex_old, ex_new], "pre-old",
        [_probe(ex_old - timedelta(days=n), older_applied) for n in (5, 4, 3, 2)],
    )
    return [newer, older]


def test_a_measured_floor_PROMOTES_an_era_that_then_satisfies_the_normal_oracle() -> None:
    """The deadlock, broken. The vendor never applied the split below its splice, so the older era
    is un-provable under the floor-less model (the split is committed OURS in the newer era and a
    carried `ours` event cannot flip to absent). With the floor in force the builder forces it
    absent, the era's own probe days then contain within 2 paise AND reconcile inside gate-1's
    band, and the era is PROMOTED -- by the same oracle as every other era, not by hand."""
    ex_new, ex_old = date(2024, 5, 24), date(2020, 2, 24)
    fetch = date(2026, 7, 27)
    events = va.events_from_factor_table(
        [_factor(KIND_SPLIT, ex_new, "0.5"), _factor(KIND_BONUS, ex_old, "0.5")], symbol="ACME"
    )
    eras = _era_pair(ex_new, ex_old, _ONE)  # the vendor applied NEITHER event below the splice

    floorless = va.build_map("ACME", fetch, events, eras)
    older = next(e for e in floorless.eras if len(e.ex_dates) == 2)
    assert not older.provable, "the B123 deadlock: nothing can drop the carried `ours` split"

    floor = va.EventFloor(ex_date=ex_new, floor_date=ex_new, resolved=True,
                          event_price_factor=Decimal("0.5"))
    floored = va.build_map("ACME", fetch, events, eras, floors=[floor])
    promoted = next(e for e in floored.eras if len(e.ex_dates) == 2)
    assert promoted.provable, "clause (iii): it became provable under the NORMAL oracle"
    assert promoted.k_price == _ONE, "split floored out, bonus absent -> the identity chain"
    split_choice = next(c for c in promoted.choices if c.ex_date == ex_new)
    assert split_choice.price_source == va.SOURCE_ABSENT
    assert floored.factors_for_day(ex_old - timedelta(days=3)) == (_ONE, _ONE)


def test_no_fit_no_floor_the_era_STAYS_un_provable() -> None:
    """The refusal path, on the same shape with the observable moved: the older era's own probe days
    DISAGREE with each other (two carry 0.5, two carry 1.0), so no single chain -- floored or not,
    measured or not -- contains all four within 2 paise. The builder refuses, the era stays
    un-provable, and its days stay excluded + counted. A floor buys nothing it has not earned."""
    ex_new, ex_old = date(2024, 5, 24), date(2020, 2, 24)
    fetch = date(2026, 7, 27)
    events = va.events_from_factor_table(
        [_factor(KIND_SPLIT, ex_new, "0.5"), _factor(KIND_BONUS, ex_old, "0.5")], symbol="ACME"
    )
    newer = va.measure_era(
        [ex_new], "pre-new",
        [_probe(ex_new - timedelta(days=n), Decimal("0.5")) for n in (5, 4, 3, 2)],
    )
    bimodal = va.measure_era(
        [ex_old, ex_new], "pre-old",
        [_probe(ex_old - timedelta(days=n), Decimal("0.5") if n > 3 else _ONE)
         for n in (5, 4, 3, 2)],
    )
    floor = va.EventFloor(ex_date=ex_new, floor_date=ex_new, resolved=True,
                          event_price_factor=Decimal("0.5"))
    floored = va.build_map("ACME", fetch, events, [newer, bimodal], floors=[floor])
    older = next(e for e in floored.eras if len(e.ex_dates) == 2)
    assert not older.provable
    assert floored.factors_for_day(ex_old - timedelta(days=3)) is None, "excluded + counted"


def test_a_floored_event_stops_consuming_the_probe_gap_guards_degree_of_freedom() -> None:
    """Why a cascade unwinds: an event whose floor was MEASURED is not an unknown, so an era that
    introduces it plus one genuinely new event is still solvable -- which under the floor-less model
    was refused as "under-determined" and took every older era down with it."""
    ex_new, ex_mid, ex_old = date(2024, 5, 24), date(2022, 3, 10), date(2020, 2, 24)
    fetch = date(2026, 7, 27)
    events = va.events_from_factor_table(
        [
            _factor(KIND_SPLIT, ex_new, "0.5"),
            _factor(KIND_BONUS, ex_mid, "0.5"),
            _factor(KIND_DIVIDEND, ex_old, "0.9"),
        ],
        symbol="ACME",
    )
    newer = va.measure_era(
        [ex_new], "pre-new", [_probe(ex_new - timedelta(days=n), Decimal("0.5")) for n in (5, 4, 3, 2)]
    )
    # the mid era was never probed -> the oldest era introduces TWO events at once
    oldest = va.measure_era(
        [ex_old, ex_mid, ex_new], "pre-old",
        [_probe(ex_old - timedelta(days=n), Decimal("0.5")) for n in (5, 4, 3, 2)],
    )
    floorless = va.build_map("ACME", fetch, events, [newer, oldest])
    old_era = next(e for e in floorless.eras if len(e.ex_dates) == 3)
    assert not old_era.provable and "probe gap" in old_era.note

    # the MID event's floor is the measured one: the oldest era then carries the committed split,
    # a measured-absent bonus, and exactly ONE fresh unknown (the dividend)
    floor = va.EventFloor(ex_date=ex_mid, floor_date=ex_mid, resolved=True,
                          event_price_factor=Decimal("0.5"))
    floored = va.build_map("ACME", fetch, events, [newer, oldest], floors=[floor])
    old_era = next(e for e in floored.eras if len(e.ex_dates) == 3)
    assert old_era.provable, "one measured floor + one fresh unknown is solvable"
    assert "probe gap" not in old_era.note


def test_a_probe_window_straddling_a_floor_is_refused_rather_than_averaged() -> None:
    ex_new, ex_old = date(2024, 5, 24), date(2020, 2, 24)
    fetch = date(2026, 7, 27)
    events = va.events_from_factor_table(
        [_factor(KIND_SPLIT, ex_new, "0.5"), _factor(KIND_BONUS, ex_old, "0.5")], symbol="ACME"
    )
    eras = _era_pair(ex_new, ex_old, _ONE)
    older_days = [p.day for p in eras[1].probe_days]
    straddling = va.EventFloor(
        ex_date=ex_new, floor_date=sorted(older_days)[2], resolved=True,
        event_price_factor=Decimal("0.5"),
    )
    built = va.build_map("ACME", fetch, events, eras, floors=[straddling])
    older = next(e for e in built.eras if len(e.ex_dates) == 2)
    assert not older.provable and "straddles" in older.note


# =========================================================================================
# clause (iv) -- provenance survives the round trip and the carry-forward
# =========================================================================================


def test_the_floor_round_trips_through_the_map_json_with_its_provenance() -> None:
    ex = date(2024, 5, 24)
    floor = va.EventFloor(
        ex_date=ex, floor_date=date(2022, 5, 10), resolved=True,
        probes=(va.FloorProbe(day=date(2022, 5, 9), verdict=va.FLOOR_OUT,
                              k_in=Decimal("0.2"), k_out=_ONE,
                              ratio_high=Decimal("1.0"), ratio_low=Decimal("1.0")),),
        note="measured", event_price_factor=Decimal("0.2"),
    )
    amap = va.AdjustmentMap(
        symbol="ACME", fetch_date=date(2026, 7, 27), all_event_ex_dates=(ex,), eras=(),
        floors=(floor,),
    )
    back = va.from_dict(va.to_dict(amap))
    assert back.floors[0] == floor
    assert va.to_dict(amap)["floors"][0]["absent_throughout"] is False


def test_a_floor_that_made_its_own_event_absent_is_CARRIED_not_dropped() -> None:
    """Otherwise the repair destroys its own justification: the floor forces the event absent, the
    rebuilt map's canonical factor becomes 1, a "same factor" carry test reads that as a change,
    drops the floor and re-opens a hunt that measures the same floor again, forever."""
    ex = date(2024, 5, 24)
    fetch = date(2026, 7, 27)
    floor = va.EventFloor(ex_date=ex, floor_date=ex, resolved=True,
                          event_price_factor=Decimal("0.5"))
    before = va.AdjustmentMap(
        symbol="ACME", fetch_date=fetch, all_event_ex_dates=(ex,),
        eras=(va.EraResolution(
            label="e", ex_dates=(ex,),
            choices=(va.EventChoice(KIND_SPLIT, ex, Decimal("0.5"), va.SOURCE_OURS,
                                    Decimal("0.5"), va.SOURCE_OURS),),
            k_price=Decimal("0.5"), k_volume=Decimal("0.5"), price_containment_paise=0,
            volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
        ),),
        floors=(floor,),
    )
    rebuilt = va.AdjustmentMap(
        symbol="ACME", fetch_date=fetch, all_event_ex_dates=(ex,),
        eras=(va.EraResolution(
            label="e", ex_dates=(ex,),
            choices=(va.EventChoice(KIND_SPLIT, ex, _ONE, va.SOURCE_ABSENT, _ONE, va.SOURCE_ABSENT),),
            k_price=_ONE, k_volume=_ONE, price_containment_paise=0,
            volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
        ),),
    )
    carried, dropped = va.carry_floors_forward(before, rebuilt)
    assert not dropped and carried.floors == (floor,)


def test_a_freshly_measured_floor_is_not_overwritten_by_the_carry() -> None:
    ex = date(2024, 5, 24)
    fetch = date(2026, 7, 27)
    era = va.EraResolution(
        label="e", ex_dates=(ex,),
        choices=(va.EventChoice(KIND_SPLIT, ex, Decimal("0.5"), va.SOURCE_OURS,
                                Decimal("0.5"), va.SOURCE_OURS),),
        k_price=Decimal("0.5"), k_volume=Decimal("0.5"), price_containment_paise=0,
        volume_gap_pct=Decimal(0), provable=True, probe_days=(), note="",
    )
    stale = va.EventFloor(ex_date=ex, floor_date=date(2018, 1, 1), resolved=True,
                          event_price_factor=Decimal("0.5"))
    fresh = va.EventFloor(ex_date=ex, floor_date=date(2022, 5, 10), resolved=True,
                          event_price_factor=Decimal("0.5"))
    previous = va.AdjustmentMap("ACME", fetch, (ex,), (era,), floors=(stale,))
    rebuilt = va.AdjustmentMap("ACME", fetch, (ex,), (era,), floors=(fresh,))
    carried, dropped = va.carry_floors_forward(previous, rebuilt)
    assert carried.floors == (fresh,) and not dropped


# =========================================================================================
# the ENRICHED baseline classifier a promotion needs
# =========================================================================================


class _Bar:
    """The two fields :func:`stored_day_baseline` reads off a stored bar."""

    def __init__(self, high: int, low: int, volume: int) -> None:
        self.high_paise, self.low_paise, self.volume = high, low, volume


def _row(high: int = 12_000, low: int = 11_800, volume: int = 100_000) -> dict:
    return {"high_paise": high, "low_paise": low, "volume": volume}


@pytest.mark.parametrize(
    "ratio, expected",
    [
        (Decimal(1), mb.BASELINE_RAW),
        (Decimal("0.5"), mb.BASELINE_AS_FETCHED),          # the ERA chain
        (Decimal(2), mb.BASELINE_OVER_DIVIDED),
        (Decimal(4), mb.BASELINE_OVER_DIVIDED_TWICE),
        (Decimal("0.8"), mb.BASELINE_AS_FETCHED_FLOORED),  # the day's OWN chain (0.5 / 0.625)
    ],
)
def test_the_enriched_hypothesis_set_names_the_vendors_own_floored_chain(
    ratio: Decimal, expected: str
) -> None:
    """A day of a newly-PROMOTED era was never touched by any pass, so it sits at the chain the
    VENDOR applied -- which a floor has just made different from the era chain. Before this
    hypothesis existed the day classified UNKNOWN and the floor repaired nothing."""
    era_chain, day_chain = Decimal("0.5"), Decimal("0.8")
    stored = [_Bar(int(12_000 * ratio), int(11_800 * ratio), 1)]
    assert mb.stored_day_baseline(
        stored, _row(), era_chain, era_chain,
        k_price_target=day_chain, k_volume_target=day_chain,
    ) == expected


def test_every_named_baseline_is_corrected_by_the_multiple_it_matched() -> None:
    """One rule, every provenance: divide by what the day is stored at, land on raw."""
    era, target = Decimal("0.5"), Decimal("0.8")
    cases = {
        mb.BASELINE_AS_FETCHED: (era, era),
        mb.BASELINE_AS_FETCHED_FLOORED: (target, target),
        mb.BASELINE_OVER_DIVIDED: (1 / era, 1 / era),
        mb.BASELINE_OVER_DIVIDED_TWICE: (1 / (era * era), 1 / (era * era)),
        mb.BASELINE_PRE_FLOOR_DIVIDED: (target / era, target / era),
        mb.BASELINE_FLOOR_OVERREACHED: (era / target, era / target),
    }
    for baseline, expected in cases.items():
        assert mb.baseline_correction(baseline, era, era, target, target) == expected, baseline
    for baseline in (mb.BASELINE_RAW, mb.BASELINE_UNKNOWN):
        assert mb.baseline_correction(baseline, era, era, target, target) is None


def test_a_floorless_day_classifies_exactly_as_it_did_before_the_ruling() -> None:
    """The enrichment must be invisible where no floor is committed: with target == era the extra
    hypotheses are not even generated, so every pre-FIX-4 verdict is byte-identical."""
    era = Decimal("0.5")
    for ratio, expected in (
        (Decimal(1), mb.BASELINE_RAW),
        (era, mb.BASELINE_AS_FETCHED),
        (1 / era, mb.BASELINE_OVER_DIVIDED),
        (1 / (era * era), mb.BASELINE_OVER_DIVIDED_TWICE),
        (Decimal("0.83"), mb.BASELINE_UNKNOWN),
    ):
        stored = [_Bar(int(12_000 * ratio), int(11_800 * ratio), 1)]
        assert mb.stored_day_baseline(stored, _row(), era, era,
                                      k_price_target=era, k_volume_target=era) == expected


def test_the_report_reads_back_only_the_floors_that_were_actually_MEASURED() -> None:
    """The acceptance table must not turn a skip, an UNRESOLVED search or an "applied throughout"
    into a measured floor -- those are findings, not measurements."""
    rows = ub._parse_floor_findings([
        "2023-12-27 -> 2023-12-27 (resolved, 3 probe(s)): absent from every chain [admitted by x]",
        "[round 2] 2018-11-06 -> 2018-11-06 (resolved, 3 probe(s)): absent throughout [admitted by y]",
        "2024-05-15 -> 2022-05-10 (resolved, 13 probe(s)): vendor application floor 2022-05-10",
        "2026-04-30 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too",
        "2016-10-18 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day is undecided",
        "2020-02-24 -> not searched: no day of a provable era carries this event",
    ])
    assert [(ex, floor, probes) for ex, floor, probes, _note in rows] == [
        ("2023-12-27", "2023-12-27", "3"),
        ("2018-11-06", "2018-11-06", "3"),
        ("2024-05-15", "2022-05-10", "13"),
    ]


def test_a_signature_containing_a_pipe_cannot_break_the_report_table() -> None:
    """The gate-3 signature quotes ``|raw gap|``, and a pipe is markdown's column separator. An
    unescaped one does not hide the evidence -- it silently splits the row into extra columns, so
    the register is MISREAD. Every cell built from a measured string is escaped."""
    signature = "gate-3 raw-gap-near-zero: |raw gap| 5.22% is nearer 0 than the step |k-1| 90.00%"
    assert "|" in signature
    assert "|" not in ub._cell(signature).replace("\\|", "")
    assert ub._cell("a\nb") == "a b"


def test_a_ratio_between_two_hypotheses_is_still_refused() -> None:
    """Extending the candidate set may never make the classifier greedier: the tolerance is derived
    from the set itself, so a ratio that sits between hypotheses is UNKNOWN and left alone."""
    era, target = Decimal("0.5"), Decimal("0.8")
    ratio = Decimal("0.65")  # between 0.5 (as-fetched) and 0.8 (as-fetched-floored)
    stored = [_Bar(int(12_000 * ratio), int(11_800 * ratio), 1)]
    assert mb.stored_day_baseline(
        stored, _row(), era, era, k_price_target=target, k_volume_target=target
    ) == mb.BASELINE_UNKNOWN
