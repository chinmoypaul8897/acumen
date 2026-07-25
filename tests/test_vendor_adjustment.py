"""Tests for the Q-11 vendor-adjustment reconstruction (per-event measurement).

All OFFLINE. The map builder and its consumption are pure, so every test drives them with
synthetic :class:`ProbeDay` measurements built by inverting a KNOWN vendor -- "the vendor made
``fetched = raw x cumulative``; prove the builder recovers the per-event decomposition". The
headline cases the card names:

* an ERA-FLIP symbol (a demerger the vendor baked into a RECENT pre-ex era but NOT an OLD one,
  disambiguated by an intervening rights -- exactly the RELIANCE shape) resolved correctly;
* a VENDOR-VOLUME-SCALED rights (the vendor's volume factor differs from its price factor and
  from our TERP) resolved to ``measured`` for both, independently;
* a NO-FIT span (a demerger whose vendor treatment flips WITHIN one era key -- no single factor
  reconciles) marked un-provable, so gate 1 excludes and counts it;

plus the identity era, the consumption path, JSON round-trip, and determinism. The RELIANCE
live acceptance is a SCRIPT (credentialed), never pytest.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from acumen import vendor_adjustment as va
from acumen import quality_gates as qg
from acumen.corp_actions import (
    DIVIDEND_ORDINARY,
    Factor,
    KIND_BONUS,
    KIND_DEMERGER,
    KIND_DIVIDEND,
    KIND_RIGHTS,
    Suppression,
)
from acumen.smartapi_client import OneMinuteBar


def _r(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _probe(
    day: date,
    raw_high: int,
    raw_low: int,
    raw_vol: int,
    price_cum: Decimal,
    vol_cum: Decimal,
) -> va.ProbeDay:
    """Invert a known vendor: ``fetched_price = raw x price_cum`` (the vendor's back-adjustment),
    ``fetched_vol = raw / vol_cum`` (so ``raw = fetched x vol_cum`` recovers it). Rounded to paise
    /shares exactly as the vendor would, so the builder faces real rounding."""
    raw_close = (raw_high + raw_low) // 2
    return va.ProbeDay(
        day=day,
        fetched_high=_r(Decimal(raw_high) * price_cum),
        fetched_low=_r(Decimal(raw_low) * price_cum),
        fetched_close=_r(Decimal(raw_close) * price_cum),
        fetched_volume=_r(Decimal(raw_vol) / vol_cum),
        raw_high=raw_high,
        raw_low=raw_low,
        raw_close=raw_close,
        raw_volume=raw_vol,
    )


# --- small pure helpers ----------------------------------------------------------------


def test_median_odd_and_even() -> None:
    assert va._median([Decimal(3), Decimal(1), Decimal(2)]) == Decimal(2)
    assert va._median([Decimal(1), Decimal(2), Decimal(3), Decimal(4)]) == Decimal("2.5")


def test_events_from_factor_table_drops_k1_keeps_movers_and_suppressions() -> None:
    factors = [
        Factor("ACME", date(2020, 1, 1), KIND_BONUS, Decimal("0.5"), "b"),
        Factor("ACME", date(2021, 1, 1), KIND_DIVIDEND, Decimal(1), "ordinary", classification=DIVIDEND_ORDINARY),
        Factor("OTHER", date(2019, 1, 1), KIND_BONUS, Decimal("0.5"), "b"),
    ]
    supp = [Suppression("ACME", date(2022, 1, 1), KIND_DEMERGER, "demerger")]
    pend = [date(2018, 6, 1)]
    events = va.events_from_factor_table(factors, supp, pend, symbol="ACME")
    kinds = {(e.kind, e.ex_date): e for e in events}
    assert (KIND_BONUS, date(2020, 1, 1)) in kinds  # k!=1 kept
    assert (KIND_DIVIDEND, date(2021, 1, 1)) not in kinds  # ordinary dividend (k=1) dropped
    assert not any(e.ex_date == date(2019, 1, 1) for e in events)  # OTHER symbol filtered out
    demerger = kinds[(KIND_DEMERGER, date(2022, 1, 1))]
    assert demerger.our_price_factor is None  # a demerger has no ours factor
    pending_rights = kinds[(KIND_RIGHTS, date(2018, 6, 1))]
    assert pending_rights.our_price_factor is None  # a Q-6-pending rights has no ours factor


# --- the RELIANCE-shaped era-flip symbol -----------------------------------------------

# ACME mirrors RELIANCE: bonuses (ours == vendor), a rights the vendor scaled by its OWN factor
# (price 0.97, volume 0.98) that differs from our TERP (0.95), and a demerger the vendor BAKED
# into the recent pre-ex era (0.90) but LEFT OUT of the old eras. The intervening rights gives
# the old and recent eras different in-window keys, so both are representable.
_B0 = date(2016, 1, 15)
_R = date(2019, 1, 15)
_D = date(2022, 1, 15)
_B1 = date(2024, 1, 15)
_F = date(2026, 6, 1)

_V_B = Decimal("0.5")  # a 1:1 bonus: vendor == ours for price and volume
_V_R_PRICE = Decimal("0.97")  # the vendor's rights PRICE factor (ours is 0.95)
_V_R_VOL = Decimal("0.98")  # the vendor's rights VOLUME factor (independent, != price)
_V_D = Decimal("0.90")  # the demerger factor the vendor baked into the RECENT pre-ex era


def _acme_events() -> list[va.EventSpec]:
    return [
        va.EventSpec(KIND_BONUS, _B0, Decimal("0.5"), True),
        va.EventSpec(KIND_RIGHTS, _R, Decimal("0.95"), False),  # our TERP, != the vendor's 0.97
        va.EventSpec(KIND_DEMERGER, _D, None, False),
        va.EventSpec(KIND_BONUS, _B1, Decimal("0.5"), True),
    ]


def _acme_eras() -> list[va.EraMeasurement]:
    # raw prices vary per day so rounding is exercised; volumes vary too.
    def days(base: date, n: int):
        return [base + timedelta(days=i) for i in range(n)]

    identity = [
        _probe(d, 100000 + 7 * i, 98000 + 5 * i, 500000 + i, Decimal(1), Decimal(1))
        for i, d in enumerate(days(date(2025, 3, 3), 3))
    ]
    era_b1 = [  # in-window {B1}: only the 2024 bonus
        _probe(d, 100003 + 11 * i, 97007 + 9 * i, 700000 + i, _V_B, _V_B)
        for i, d in enumerate(days(date(2023, 6, 1), 3))
    ]
    era_d_b1 = [  # in-window {D, B1}: demerger PRESENT (0.90) x bonus (0.5)
        _probe(d, 100001 + 13 * i, 96003 + 7 * i, 900000 + i, _V_D * _V_B, _V_D * _V_B)
        for i, d in enumerate(days(date(2020, 6, 1), 3))
    ]
    era_r_d_b1 = [  # in-window {R, D, B1}: rights measured, demerger ABSENT, bonus
        _probe(d, 100002 + 3 * i, 95009 + 5 * i, 1000000 + i, _V_R_PRICE * _V_B, _V_R_VOL * _V_B)
        for i, d in enumerate(days(date(2017, 6, 1), 3))
    ]
    era_all = [  # in-window {B0, R, D, B1}: bonus0, rights measured, demerger ABSENT, bonus1
        _probe(d, 100004 + 5 * i, 94001 + 3 * i, 1200000 + i,
               Decimal("0.5") * _V_R_PRICE * _V_B, Decimal("0.5") * _V_R_VOL * _V_B)
        for i, d in enumerate(days(date(2015, 6, 1), 3))
    ]
    return [
        va.measure_era((), "identity", identity),
        va.measure_era((_B1,), "B1", era_b1),
        va.measure_era((_D, _B1), "D+B1", era_d_b1),
        va.measure_era((_R, _D, _B1), "R+D+B1", era_r_d_b1),
        va.measure_era((_B0, _R, _D, _B1), "all", era_all),
    ]


def _acme_map() -> va.AdjustmentMap:
    return va.build_map("ACME", _F, _acme_events(), _acme_eras(), tick_paise=5)


def _choice(era: va.EraResolution, ex: date) -> va.EventChoice:
    return next(c for c in era.choices if c.ex_date == ex)


def test_era_flip_demerger_resolved_present_recent_absent_old() -> None:
    amap = _acme_map()
    by_key = {era.ex_dates: era for era in amap.eras}
    assert all(era.provable for era in amap.eras)

    # RECENT pre-ex era {D, B1}: the vendor BAKED the demerger in -> measured ~0.90.
    recent = by_key[(_D, _B1)]
    dem_recent = _choice(recent, _D)
    assert dem_recent.price_source == va.SOURCE_MEASURED
    assert dem_recent.price_factor == pytest.approx(Decimal("0.90"), abs=Decimal("0.001"))

    # OLD eras {R, D, B1} and {B0, R, D, B1}: the demerger is ABSENT (the vendor did not apply it).
    for key in ((_R, _D, _B1), (_B0, _R, _D, _B1)):
        dem_old = _choice(by_key[key], _D)
        assert dem_old.price_source == va.SOURCE_ABSENT
        assert dem_old.price_factor == Decimal(1)

    # bonuses are OURS (ours == vendor) everywhere they appear.
    assert _choice(by_key[(_B1,)], _B1).price_source == va.SOURCE_OURS
    assert _choice(by_key[(_B0, _R, _D, _B1)], _B0).price_source == va.SOURCE_OURS


def test_vendor_volume_scaled_rights_measured_independently_for_price_and_volume() -> None:
    amap = _acme_map()
    by_key = {era.ex_dates: era for era in amap.eras}
    rights = _choice(by_key[(_R, _D, _B1)], _R)
    # our TERP (0.95) does NOT fit -> the rights resolves to the vendor's MEASURED factor, and the
    # PRICE (0.97) and VOLUME (0.98) factors are measured INDEPENDENTLY (they genuinely differ).
    assert rights.price_source == va.SOURCE_MEASURED
    assert rights.volume_source == va.SOURCE_MEASURED
    assert rights.price_factor == pytest.approx(Decimal("0.97"), abs=Decimal("0.0005"))
    assert rights.volume_factor == pytest.approx(Decimal("0.98"), abs=Decimal("0.0005"))
    assert rights.price_factor != rights.volume_factor
    # and it is measured as ONE scalar across BOTH eras it appears in (2015 + 2017 windows).
    rights_all = _choice(by_key[(_B0, _R, _D, _B1)], _R)
    assert rights_all.price_factor == rights.price_factor


def test_every_acme_era_is_contained_and_reconciled() -> None:
    amap = _acme_map()
    for era in amap.eras:
        # price containment within 2 paise on the CA eras (identity era is exempt -- no CA).
        if era.ex_dates:
            assert era.price_containment_paise <= 2, era.label
        # gate-1 median gap inside the band (the -0.1% floor is NOT widened).
        assert era.volume_gap_pct is not None
        assert qg.VOLUME_GAP_MIN_PCT <= era.volume_gap_pct <= qg.VOLUME_GAP_MAX_PCT, era.label


# --- identity era ----------------------------------------------------------------------


def test_identity_era_is_provable_with_unit_factors() -> None:
    amap = _acme_map()
    identity = next(era for era in amap.eras if not era.ex_dates)
    assert identity.provable is True
    assert identity.k_price == Decimal(1) and identity.k_volume == Decimal(1)


# --- no-fit span -> un-provable + counted ----------------------------------------------


def test_no_fit_span_is_unprovable_and_excluded() -> None:
    """A demerger whose vendor treatment FLIPS within one era key (the vendor's re-adjustment
    floor falls inside the span, with no intervening event to split the key): half the probe days
    carry the demerger (~0.90), half do not (~1.0). No single factor -- measured 0.95, or absent --
    reconciles either half, so the era is UN-PROVABLE and its days are excluded and counted."""
    ex = date(2020, 1, 15)
    F = date(2026, 6, 1)
    events = [va.EventSpec(KIND_DEMERGER, ex, None, False)]
    baked = [  # the vendor DID demerger-adjust these (ratio 0.90)
        _probe(date(2018, 6, 1) + timedelta(days=i), 100000 + i, 98000 + i, 500000, Decimal("0.90"), Decimal("0.90"))
        for i in range(3)
    ]
    raw = [  # the vendor did NOT (ratio 1.00) -- same era key {ex}
        _probe(date(2019, 6, 1) + timedelta(days=i), 100000 + i, 98000 + i, 500000, Decimal(1), Decimal(1))
        for i in range(3)
    ]
    era = va.measure_era((ex,), "bimodal", baked + raw)
    amap = va.build_map("GHOST", F, events, [era], tick_paise=5)
    only = amap.eras[0]
    assert only.provable is False
    assert only.price_containment_paise == -1
    # a day in that era cannot be un-adjusted, and consumption marks it un-provable.
    a_day = date(2018, 6, 1)
    assert amap.factors_for_day(a_day) is None
    bar = OneMinuteBar(datetime.combine(a_day, time(9, 15)), 90000, 90000, 88200, 89000, 555555)
    res = va.unadjust_with_map([bar], amap, symbol="GHOST", tick_paise=5)
    assert res.days[0].provable is False
    assert res.unprovable_days == (a_day,)


# --- consumption -----------------------------------------------------------------------


def test_unadjust_with_map_recovers_raw_and_flags_unprobed_days() -> None:
    amap = _acme_map()
    # a day in the {D, B1} era: k_price ~ 0.45, so a fetched price divides back to raw.
    day = date(2020, 6, 2)
    kp, kv = amap.factors_for_day(day)
    fetched_high = _r(Decimal(100000) * _V_D * _V_B)  # what the vendor served
    bar = OneMinuteBar(datetime.combine(day, time(9, 15)), fetched_high, fetched_high, fetched_high, fetched_high, 2000)
    res = va.unadjust_with_map([bar], amap, symbol="ACME", tick_paise=5)
    assert res.days[0].provable is True
    assert abs(res.raw_bars[0].high_paise - 100000) <= 2  # recovered raw within containment
    # a day whose era was never probed (a 2021 day: in-window {D, B1} IS probed; use a gap the map
    # has no era for by removing it) -- here use an out-of-range future day with events still ahead.
    unprobed_day = date(2012, 1, 1)  # in-window would be {B0,R,D,B1} -> that IS probed; craft a miss instead
    # Build a map missing the {B1} era, then a 2023 day (in-window {B1}) is unprovable.
    partial = va.build_map("ACME", _F, _acme_events(),
                           [e for e in _acme_eras() if e.ex_dates != (_B1,)], tick_paise=5)
    assert partial.factors_for_day(date(2023, 6, 2)) is None
    b2 = OneMinuteBar(datetime.combine(date(2023, 6, 2), time(9, 15)), 50000, 50000, 48500, 49000, 3000)
    r2 = va.unadjust_with_map([b2], partial, symbol="ACME", tick_paise=5)
    assert r2.days[0].provable is False


def test_identity_day_stored_byte_for_byte() -> None:
    amap = _acme_map()
    day = date(2025, 3, 4)  # identity era
    bar = OneMinuteBar(datetime.combine(day, time(9, 15)), 123457, 123999, 122001, 123000, 4242)
    res = va.unadjust_with_map([bar], amap, symbol="ACME", tick_paise=5)
    assert res.days[0].identity is True
    out = res.raw_bars[0]
    assert (out.open_paise, out.high_paise, out.low_paise, out.close_paise, out.volume) == (
        123457, 123999, 122001, 123000, 4242
    )


# --- persistence + determinism ---------------------------------------------------------


def test_json_round_trip_is_lossless() -> None:
    amap = _acme_map()
    back = va.from_dict(va.to_dict(amap))
    assert va.to_dict(back) == va.to_dict(amap)
    # factors survive the round-trip exactly (Decimals via string).
    for day in (date(2016, 6, 2), date(2020, 6, 2), date(2023, 6, 2)):
        assert back.factors_for_day(day) == amap.factors_for_day(day)


def test_build_is_deterministic() -> None:
    assert va.to_dict(_acme_map()) == va.to_dict(_acme_map())


def test_persist_and_load_from_disk(tmp_path) -> None:
    amap = _acme_map()
    path = va.persist_map(amap, data_dir=tmp_path)
    assert path == tmp_path / "adjustment_maps" / "ACME.json"
    loaded = va.load_map("ACME", data_dir=tmp_path)
    assert va.to_dict(loaded) == va.to_dict(amap)
    with pytest.raises(va.VendorAdjustmentError):
        va.load_map("NOSUCH", data_dir=tmp_path)


# --- TCS regression (bonus-only): map is exactly {2018 bonus, ours, 0.5} ----------------


def test_tcs_bonus_only_map_is_ours_half_everywhere() -> None:
    """A bonus-only symbol (TCS's shape: one 1:1 bonus, no rights/demerger) resolves to exactly
    {bonus, ours, 0.5} for price and volume, with the post-bonus era identity."""
    bonus_ex = date(2018, 5, 31)
    F = date(2026, 7, 25)
    events = [va.EventSpec(KIND_BONUS, bonus_ex, Decimal("0.5"), True)]
    pre = [  # pre-bonus: vendor halved price, doubled volume
        _probe(date(2016, 10, 3) + timedelta(days=i), 240000 + 100 * i, 238000 + 90 * i, 900000, Decimal("0.5"), Decimal("0.5"))
        for i in range(3)
    ]
    post = [  # post-bonus: identity
        _probe(date(2020, 1, 2) + timedelta(days=i), 200000 + 50 * i, 198000 + 40 * i, 1000000, Decimal(1), Decimal(1))
        for i in range(3)
    ]
    eras = [va.measure_era((bonus_ex,), "pre", pre), va.measure_era((), "post", post)]
    amap = va.build_map("TCS", F, events, eras, tick_paise=5)
    by_key = {era.ex_dates: era for era in amap.eras}
    bonus = _choice(by_key[(bonus_ex,)], bonus_ex)
    assert bonus.price_source == va.SOURCE_OURS and bonus.price_factor == Decimal("0.5")
    assert bonus.volume_source == va.SOURCE_OURS and bonus.volume_factor == Decimal("0.5")
    assert by_key[()].k_price == Decimal(1)  # post-bonus identity era
    assert all(era.provable for era in amap.eras)


# --- ingest-path consumption: backfill + rebuild THROUGH the map ------------------------

import pandas as pd  # noqa: E402
from acumen import minute_backfill as mb  # noqa: E402
from acumen.minute_store import MinuteStore, WINDOW_PRESENT, WindowOutcome  # noqa: E402


class _FakeClient:
    def __init__(self, bars):
        self._bars = tuple(bars)

    def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):
        return self._bars


class _FakeMaster:
    def token(self, symbol):
        return "11536"


class _FakeDaily:
    def __init__(self, rows):
        self._rows = rows

    def daily(self, symbol, d0, d1, *, series=None):
        cols = ["trade_date", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]
        rows = [r for r in self._rows.get(symbol.upper(), []) if d0 <= r["trade_date"] <= d1]
        return pd.DataFrame(rows, columns=cols)


def _bonus_map(bonus_ex: date, F: date) -> va.AdjustmentMap:
    events = [va.EventSpec(KIND_BONUS, bonus_ex, Decimal("0.5"), True)]
    pre = [_probe(date(2016, 10, 3) + timedelta(days=i), 240000, 238000, 900000, Decimal("0.5"), Decimal("0.5")) for i in range(3)]
    post = [_probe(date(2020, 1, 2) + timedelta(days=i), 200000, 198000, 1000000, Decimal(1), Decimal(1)) for i in range(3)]
    eras = [va.measure_era((bonus_ex,), "pre", pre), va.measure_era((), "post", post)]
    return va.build_map("TCS", F, events, eras, tick_paise=5)


def test_backfill_symbol_unadjusts_via_map(tmp_path) -> None:
    """The ingest path consumes the map: a fetched (adjusted) pre-bonus bar is divided back to RAW
    (price / 0.5) and its volume recovered (x 0.5) before storage."""
    store = MinuteStore.at(tmp_path / "m")
    F = date(2026, 7, 25)
    amap = _bonus_map(date(2018, 5, 31), F)
    day = date(2016, 10, 3)
    adjusted = [OneMinuteBar(datetime.combine(day, time(9, 15)), 120000, 120100, 119900, 120050, 2000)]
    sf = mb.SymbolFactors("TCS", tick_paise=5)
    result = mb.backfill_symbol(
        _FakeClient(adjusted), _FakeMaster(), store, "TCS", date(2016, 10, 1), date(2016, 10, 28),
        symbol_factors=sf, adjustment_map=amap, now=lambda: datetime(2026, 7, 25, 12, 0),
    )
    stored = store.minutes("TCS", day)
    assert stored[0].open_paise == 240000  # 120000 / 0.5 (RAW recovered via the map)
    assert stored[0].volume == 1000        # 2000 x 0.5
    assert result.unprovable_days == []


def test_rebuild_via_map_is_noop_on_an_already_raw_store(tmp_path) -> None:
    """The identity guard: a store already holding RAW volumes (gate 1 passes) is a NO-OP rebuild --
    the exact TCS regression. No day is rewritten even though the map's pre-bonus k_price is 0.5."""
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 3)
    raw_vol = 1000
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(day, time(9, 15)), 240000, 240100, 239900, 240050, raw_vol)])
    daily = _FakeDaily({"TCS": [{"trade_date": day, "open_paise": 240000, "high_paise": 240200,
                                 "low_paise": 239800, "close_paise": 240100, "volume": raw_vol}]})
    amap = _bonus_map(date(2018, 5, 31), date(2026, 7, 25))
    res = mb.rebuild_symbol_raw_with_map(store, daily, "TCS", amap, tick_paise=5)
    assert res.days_rewritten == 0 and res.identity_days == 1  # already-raw -> skipped
    assert store.minutes("TCS", day)[0].volume == raw_vol  # untouched


def test_rebuild_via_map_unadjusts_an_adjusted_store(tmp_path) -> None:
    """The other half of the guard: an ADJUSTED store (volume ~2x raw, gate 1 FAILS) is un-adjusted
    through the map to RAW."""
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 3)
    raw_vol = 1000
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(day, time(9, 15)), 120000, 120100, 119900, 120050, 2 * raw_vol)])
    daily = _FakeDaily({"TCS": [{"trade_date": day, "open_paise": 240000, "high_paise": 240200,
                                 "low_paise": 239800, "close_paise": 240100, "volume": raw_vol}]})
    amap = _bonus_map(date(2018, 5, 31), date(2026, 7, 25))
    res = mb.rebuild_symbol_raw_with_map(store, daily, "TCS", amap, tick_paise=5)
    assert res.days_rewritten == 1 and res.unadjusted_days == 1
    assert store.minutes("TCS", day)[0].open_paise == 240000  # 120000 / 0.5
    assert store.minutes("TCS", day)[0].volume == raw_vol     # 2000 x 0.5


# --- regressions for the FIX-4 adversarial-review findings -----------------------------


def test_probe_gap_marks_era_unprovable_not_fabricated() -> None:
    """A probe GAP (an inter-event era not measured) makes an older era introduce >1 new event ->
    per-event attribution is under-determined. The era MUST be un-provable, never a fabricated
    decomposition (rights labelled 'ours' with the residual dumped onto the demerger as 'measured').
    """
    B0, R, D, B1, F = _B0, _R, _D, _B1, _F
    events = _acme_events()
    # OMIT the {B1} and {D,B1} eras -> {R,D,B1} adds R and D at once (a gap).
    gapped = [e for e in _acme_eras() if e.ex_dates not in ((B1,), (D, B1))]
    amap = va.build_map("ACME", F, events, gapped, tick_paise=5)
    by_key = {era.ex_dates: era for era in amap.eras}
    assert by_key[(R, D, B1)].provable is False  # gap -> un-provable, not fabricated
    assert "probe gap" in by_key[(R, D, B1)].note
    assert by_key[(B0, R, D, B1)].provable is False  # the gap propagates to older eras
    # a day in the gapped era is un-provable at consumption -> gate 1 excludes it.
    assert amap.factors_for_day(date(2017, 6, 1)) is None


def test_bimodal_majority_era_is_unprovable_per_day_not_median() -> None:
    """The vendor's floor falling INSIDE one era key: a MAJORITY of days carry the demerger (0.90),
    a minority do not (1.0). A median oracle would pass on the majority and silently commit an 11%
    price error on the minority (gate-1 volume cannot see it). Per-day containment must reject it."""
    ex = date(2020, 1, 15)
    F = date(2026, 6, 1)
    events = [va.EventSpec(KIND_DEMERGER, ex, None, False)]
    baked = [_probe(date(2018, 6, 1) + timedelta(days=i), 100000 + i, 98000 + i, 500000, Decimal("0.90"), Decimal(1)) for i in range(5)]
    raw = [_probe(date(2019, 6, 1) + timedelta(days=i), 100000 + i, 98000 + i, 500000, Decimal(1), Decimal(1)) for i in range(3)]
    era = va.measure_era((ex,), "bimodal-majority", baked + raw)
    amap = va.build_map("GHOST", F, events, [era], tick_paise=5)
    assert amap.eras[0].provable is False


def _special_div_map(div_ex: date, F: date) -> va.AdjustmentMap:
    events = [va.EventSpec(KIND_DIVIDEND, div_ex, Decimal("0.98"), False)]  # price x0.98, volume untouched
    pre = [_probe(date(2016, 10, 3) + timedelta(days=i), 200000, 198000, 1000, Decimal("0.98"), Decimal(1)) for i in range(3)]
    post = [_probe(date(2021, 1, 4) + timedelta(days=i), 300000, 298000, 1000, Decimal(1), Decimal(1)) for i in range(3)]
    return va.build_map("DIVCO", F, events, [va.measure_era((div_ex,), "pre", pre), va.measure_era((), "post", post)], tick_paise=5)


def test_rebuild_unadjusts_a_price_only_special_dividend_day() -> None:
    """The blocker: a special dividend leaves VOLUME reconciled (k_volume=1) but PRICE adjusted
    (k_price=0.98). A volume-only guard would skip the day with its price still adjusted. The
    price+volume guard un-adjusts it."""
    import tempfile, pathlib
    store = MinuteStore.at(pathlib.Path(tempfile.mkdtemp()) / "m")
    F = date(2026, 7, 25)
    amap = _special_div_map(date(2019, 5, 1), F)
    day = date(2016, 10, 3)
    # ADJUSTED store day: price x0.98, volume UNCHANGED (a dividend does not scale volume).
    store.write_bars("DIVCO", [OneMinuteBar(datetime.combine(day, time(9, 15)), 196000, 196100, 195900, 196050, 1000)])
    daily = _FakeDaily({"DIVCO": [{"trade_date": day, "open_paise": 200000, "high_paise": 200200,
                                   "low_paise": 199800, "close_paise": 200100, "volume": 1000}]})
    res = mb.rebuild_symbol_raw_with_map(store, daily, "DIVCO", amap, tick_paise=5)
    assert res.days_rewritten == 1  # NOT skipped despite volume already reconciling
    assert store.minutes("DIVCO", day)[0].open_paise == 200000  # 196000 / 0.98 -> RAW price recovered


def test_rebuild_skips_already_raw_special_dividend_day() -> None:
    import tempfile, pathlib
    store = MinuteStore.at(pathlib.Path(tempfile.mkdtemp()) / "m")
    amap = _special_div_map(date(2019, 5, 1), date(2026, 7, 25))
    day = date(2016, 10, 3)
    store.write_bars("DIVCO", [OneMinuteBar(datetime.combine(day, time(9, 15)), 200000, 200200, 199800, 200100, 1000)])
    daily = _FakeDaily({"DIVCO": [{"trade_date": day, "open_paise": 200000, "high_paise": 200200,
                                   "low_paise": 199800, "close_paise": 200100, "volume": 1000}]})
    res = mb.rebuild_symbol_raw_with_map(store, daily, "DIVCO", amap, tick_paise=5)
    assert res.days_rewritten == 0 and res.identity_days == 1  # already raw on price AND volume


def test_rebuild_skips_a_day_with_no_daily_row() -> None:
    """No raw daily row -> cannot verify raw-vs-adjusted -> leave the day as-is (never blindly
    un-adjust, which would corrupt an already-raw day)."""
    import tempfile, pathlib
    store = MinuteStore.at(pathlib.Path(tempfile.mkdtemp()) / "m")
    amap = _bonus_map(date(2018, 5, 31), date(2026, 7, 25))
    day = date(2016, 10, 3)
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(day, time(9, 15)), 240000, 240100, 239900, 240050, 1000)])
    daily = _FakeDaily({"TCS": []})  # no row for this day
    res = mb.rebuild_symbol_raw_with_map(store, daily, "TCS", amap, tick_paise=5)
    assert res.days_rewritten == 0  # untouched
    assert store.minutes("TCS", day)[0].open_paise == 240000


def test_measure_era_drops_zero_volume_probe_days() -> None:
    good = _probe(date(2020, 3, 24), 100000, 98000, 500000, Decimal("0.5"), Decimal("0.5"))
    zero = va.ProbeDay(date(2020, 3, 25), 100000, 98000, 99000, 0, 100000, 98000, 99000, 500000)
    era = va.measure_era((date(2021, 1, 1),), "probe", [good, zero])  # must not divide by zero
    assert era.probe_days == (good,)  # the zero-volume day is dropped
    with pytest.raises(va.VendorAdjustmentError):
        va.measure_era((date(2021, 1, 1),), "all-degenerate", [zero])


def test_two_events_sharing_an_ex_date_are_refused() -> None:
    ex = date(2020, 1, 1)
    events = [va.EventSpec(KIND_BONUS, ex, Decimal("0.5"), True),
              va.EventSpec(KIND_DIVIDEND, ex, Decimal("0.98"), False)]
    with pytest.raises(va.VendorAdjustmentError):
        va.build_map("DUP", date(2026, 1, 1), events, [], tick_paise=5)


def test_recent_day_is_identity_even_without_a_probed_identity_era() -> None:
    """A post-last-CA day (empty in-window set) is identity (1,1) by definition -- so a recent RAW
    day is never wrongly excluded just because no identity window was probed."""
    bonus_ex = date(2018, 5, 31)
    F = date(2026, 7, 25)
    events = [va.EventSpec(KIND_BONUS, bonus_ex, Decimal("0.5"), True)]
    pre = [_probe(date(2016, 10, 3) + timedelta(days=i), 240000, 238000, 900000, Decimal("0.5"), Decimal("0.5")) for i in range(2)]
    amap = va.build_map("TCS", F, events, [va.measure_era((bonus_ex,), "pre", pre)], tick_paise=5)  # NO identity era
    assert amap.factors_for_day(date(2020, 1, 2)) == (Decimal(1), Decimal(1))  # recent -> identity, not None
