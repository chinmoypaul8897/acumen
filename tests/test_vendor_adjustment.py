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


def test_vendor_volume_scaled_rights_price_measured_volume_takes_the_price_factor() -> None:
    """Q-12 clause (ii) applied to the ACME rights, and the consequence recorded honestly.

    Our TERP (0.95) does not fit, so the PRICE side still resolves to the vendor's MEASURED factor
    (0.97) -- the price oracle is 2-paise containment and forces it. On the VOLUME side the ruled
    candidate order is ``ours > chosen-price-factor > measured-minimum > absent``, and the rights has
    no volume ``ours`` at all. ACME's vendor used 0.98 for volume against 0.97 for price -- a 1%
    divergence -- and the chosen PRICE factor reconciles that within gate 1's band, so the ruled
    order commits the price factor and the ~1% residual rides inside the band.

    That is a deliberate, ruled consequence, not a defect: gate 1 (per-day, band UNWIDENED) is the
    acceptance criterion, and it is still satisfied on every probe day. The next test proves the
    oracle still GOVERNS -- a divergence the band cannot absorb forces ``measured`` back.
    """
    amap = _acme_map()
    by_key = {era.ex_dates: era for era in amap.eras}
    rights = _choice(by_key[(_R, _D, _B1)], _R)
    assert rights.price_source == va.SOURCE_MEASURED
    assert rights.price_factor == pytest.approx(Decimal("0.97"), abs=Decimal("0.0005"))
    assert rights.volume_source == va.SOURCE_PRICE_FACTOR
    assert rights.volume_factor == rights.price_factor  # the committed price factor, not a re-solve
    # and the price scalar is ONE number across BOTH eras it appears in (2015 + 2017 windows).
    rights_all = _choice(by_key[(_B0, _R, _D, _B1)], _R)
    assert rights_all.price_factor == rights.price_factor
    assert rights_all.volume_source == va.SOURCE_PRICE_FACTOR
    # the residual really is inside the band on every probe day, not merely on the median.
    era = next(m for m in _acme_eras() if m.ex_dates == (_R, _D, _B1))
    assert va._volume_reconciled(era, by_key[(_R, _D, _B1)].k_volume)


def test_a_volume_divergence_too_big_for_gate1_forces_measured_back() -> None:
    """The Q-12 preference is a TIE-BREAK among candidates that pass the oracle, never a bypass.

    Same shape as ACME's rights but with the vendor scaling volume by 0.80 against a price factor of
    0.97 -- a 21% divergence gate 1's ``[-0.1%, +5.0%]`` cannot absorb. The chosen-price-factor
    candidate FAILS the band, so the measured minimum is forced and the era is still provable.
    """
    ex = date(2019, 1, 15)
    fetch = date(2026, 6, 1)
    events = [va.EventSpec(KIND_RIGHTS, ex, Decimal("0.95"), False)]
    probes = [
        _probe(date(2018, 6, 1) + timedelta(days=i), 100002 + 3 * i, 95009 + 5 * i,
               1000000 + i, Decimal("0.97"), Decimal("0.80"))
        for i in range(4)
    ]
    amap = va.build_map("DIVERGE", fetch, events, [va.measure_era((ex,), "pre-ex", probes)])
    era = amap.eras[0]
    assert era.provable
    choice = _choice(era, ex)
    assert choice.price_source == va.SOURCE_MEASURED
    assert choice.price_factor == pytest.approx(Decimal("0.97"), abs=Decimal("0.0005"))
    assert choice.volume_source == va.SOURCE_MEASURED
    assert choice.volume_factor == pytest.approx(Decimal("0.80"), abs=Decimal("0.0005"))


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


# --- the NET-factor rebuild (the Q-12-addendum quarantine-recovery reroute) --------------


def test_net_map_factors_is_the_map_chain_when_nothing_was_applied_yet() -> None:
    """A map-required symbol's store holds the vendor's AS-FETCHED bars, so the net factors ARE the
    map's own -- the reroute arithmetic must not perturb the ordinary path."""
    amap = _bonus_map(date(2018, 5, 31), date(2026, 7, 25))
    assert mb.net_map_factors(amap, date(2016, 10, 3), None, None) == (Decimal("0.5"), Decimal("0.5"))


def test_net_map_factors_divides_out_what_the_factor_table_already_applied() -> None:
    """The reroute case. The store was un-adjusted once by our (WRONG) table factor 0.5, so it sits at
    ``fetched / 0.5``. The map measured the vendor's real 0.9. Reaching ``fetched / 0.9`` from there
    is ONE division by the net ``0.9 / 0.5 = 1.8`` -- never a second full division by 0.9, which would
    land at ``fetched / 0.45`` and be silently wrong by a factor of two.
    """
    ex = date(2018, 5, 31)
    F = date(2026, 7, 25)
    day = date(2016, 10, 3)
    events = [va.EventSpec(KIND_BONUS, ex, Decimal("0.5"), True)]
    # a map whose measured factor is 0.9, not our 0.5
    pre = [_probe(day + timedelta(days=i), 240000, 238000, 900000, Decimal("0.9"), Decimal("0.9"))
           for i in range(3)]
    amap = va.build_map("VAR", F, events, [va.measure_era((ex,), "pre", pre)], tick_paise=5)
    assert amap.eras[0].k_price == pytest.approx(Decimal("0.9"), abs=Decimal("0.0005"))

    applied = mb.SymbolFactors("VAR", factors=(
        Factor("VAR", ex, KIND_BONUS, Decimal("0.5"), "bonus 1:1"),
    ), tick_paise=5)
    net_price, net_volume = mb.net_map_factors(amap, day, applied, F)
    assert net_price == pytest.approx(Decimal("1.8"), abs=Decimal("0.001"))
    assert net_volume == pytest.approx(Decimal("1.8"), abs=Decimal("0.001"))
    # and the round trip really lands on raw: fetched = raw x 0.9, stored = fetched / 0.5
    raw_price = 240000
    fetched = int(Decimal(raw_price) * Decimal("0.9"))
    stored = int(Decimal(fetched) / Decimal("0.5"))
    from acumen.minute_unadjust import unadjust_price_paise

    recovered, _snap, _off = unadjust_price_paise(stored, net_price, tick_paise=None)
    assert abs(recovered - raw_price) <= 2


def test_a_day_the_map_cannot_resolve_is_left_exactly_as_it_was_and_counted(tmp_path) -> None:
    """The reroute's un-provable branch: the map has no answer, so NOTHING is applied.

    The day keeps whatever the factor table left on it, is counted in ``unprovable_days``, and gate 1
    excludes it (CONTEXT 7-E3). Leaving it alone is what makes a later pass safe too: the map returns
    no factors for this day, so no later pass can classify or correct it either -- there is no state
    in which it gets divided by a chain that was never proven for it.
    """
    ex = date(2018, 5, 31)
    F = date(2026, 7, 25)
    day = date(2016, 10, 3)
    store = MinuteStore.at(tmp_path / "m")
    raw_vol, raw_price = 1000, 240000
    fetched_price = int(Decimal(raw_price) * Decimal("0.9"))
    stored_price = int(Decimal(fetched_price) / Decimal("0.5"))     # what the table path stored
    stored_vol = int(Decimal(raw_vol) / Decimal("0.9") * Decimal("0.5"))
    store.write_bars("VAR", [OneMinuteBar(
        datetime.combine(day, time(9, 15)), stored_price, stored_price, stored_price, stored_price,
        stored_vol,
    )])
    store.record_window(WindowOutcome(
        symbol="VAR", window_start=day, window_end=day, outcome=WINDOW_PRESENT, candle_count=1,
        fetch_date=F, attempted_at=datetime(2026, 7, 25, 12, 0),
    ))
    daily = _FakeDaily({"VAR": [{"trade_date": day, "open_paise": raw_price, "high_paise": raw_price,
                                 "low_paise": raw_price, "close_paise": raw_price, "volume": raw_vol}]})
    # an UN-PROVABLE map: one probe day is adjusted by a different factor, so no chain contains it
    probes = [
        _probe(day + timedelta(days=i), 240000, 238000, 900000,
               Decimal("0.9") if i < 2 else Decimal("0.6"), Decimal("0.9"))
        for i in range(3)
    ]
    events = [va.EventSpec(KIND_BONUS, ex, Decimal("0.5"), True)]
    amap = va.build_map("VAR", F, events, [va.measure_era((ex,), "pre", probes)], tick_paise=5)
    assert not amap.eras[0].provable

    applied = mb.SymbolFactors("VAR", factors=(
        Factor("VAR", ex, KIND_BONUS, Decimal("0.5"), "bonus 1:1"),
    ), tick_paise=5)
    res = mb.rebuild_symbol_raw_with_map(
        store, daily, "VAR", amap, tick_paise=5, applied_factors=applied
    )
    assert res.unprovable_days == [day]
    assert res.days_rewritten == 0
    back = store.minutes("VAR", day)[0]
    assert back.open_paise == stored_price, "untouched -- no factor was proven for this day"
    assert back.volume == stored_vol
    assert fetched_price  # the fetched value is not what we claim to have recovered


def test_the_three_baselines_are_separable_and_a_fourth_is_refused() -> None:
    """:func:`stored_day_baseline`'s hypotheses, on the ASHOKLEY-shaped numbers that forced it.

    For a 1:1 bonus the ratios are 1 (raw), 0.5 (as-fetched) and 2.0 (divided one time too many) --
    an order of magnitude apart, so a 2% tolerance both absorbs the fold-vs-bhavcopy microstructure
    difference AND cannot confuse two hypotheses. A ratio near none of them is refused.
    """
    day = date(2016, 10, 3)
    raw_high, raw_low, raw_vol = 145000, 143000, 120958
    half, one, two = Decimal("0.5"), Decimal(1), Decimal(2)

    def bars(scale: Decimal, vol_scale: Decimal):
        return [OneMinuteBar(
            datetime.combine(day, time(9, 15)),
            int(Decimal(raw_low) * scale), int(Decimal(raw_high) * scale),
            int(Decimal(raw_low) * scale), int(Decimal(raw_high) * scale),
            int(Decimal(raw_vol) * vol_scale),
        )]

    row = {"trade_date": day, "high_paise": raw_high, "low_paise": raw_low,
           "close_paise": raw_high, "volume": raw_vol}
    assert mb.stored_day_baseline(bars(one, one), row, half, half) == mb.BASELINE_RAW
    assert mb.stored_day_baseline(bars(half, two), row, half, half) == mb.BASELINE_AS_FETCHED
    assert mb.stored_day_baseline(bars(two, half), row, half, half) == mb.BASELINE_OVER_DIVIDED
    assert mb.stored_day_baseline(bars(Decimal("0.75"), one), row, half, half) == mb.BASELINE_UNKNOWN

    # the measured ASHOKLEY case: a genuinely RAW day whose fold high sits 0.4% off the bhavcopy high
    # (a print the continuous 1-minute series never held). The old 0.1% one-way test called this "not
    # raw" and divided it a second time; it must read as RAW.
    off = [OneMinuteBar(datetime.combine(day, time(9, 15)),
                        raw_low, int(raw_high * Decimal("0.996")), raw_low,
                        int(raw_high * Decimal("0.996")), raw_vol)]
    assert mb.stored_day_baseline(off, row, half, half) == mb.BASELINE_RAW
    assert not mb._stored_day_is_raw(  # the old one-way test, kept for the Q-10 factor-table path
        [mb.StoredBar("X", b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise, b.volume)
         for b in off],
        row,
    ), "the tight one-way test really does reject it -- which is why it is not used to decide a divide"


def test_a_price_neutral_map_falls_back_to_the_volume_axis() -> None:
    """``k_price == 1`` carries no price information (both hypotheses coincide), so volume decides.
    With BOTH factors 1 there is nothing to correct and the day is raw by definition."""
    day = date(2020, 3, 24)
    row = {"trade_date": day, "high_paise": 100000, "low_paise": 99000,
           "close_paise": 99500, "volume": 1000}
    stamp = datetime.combine(day, time(9, 15))
    raw = [OneMinuteBar(stamp, 99000, 100000, 99000, 99500, 1000)]
    fetched = [OneMinuteBar(stamp, 99000, 100000, 99000, 99500, 2000)]  # volume 1/0.5
    assert mb.stored_day_baseline(raw, row, Decimal(1), Decimal("0.5")) == mb.BASELINE_RAW
    assert mb.stored_day_baseline(fetched, row, Decimal(1), Decimal("0.5")) == mb.BASELINE_AS_FETCHED
    assert mb.stored_day_baseline(fetched, row, Decimal(1), Decimal(1)) == mb.BASELINE_RAW


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


# --- Q-12: the volume estimator + the volume candidate set ------------------------------
#
# The architect's Q-12 ruling (QUESTIONS.md), in two clauses:
#   (i)  the measured VOLUME estimator becomes the MINIMUM over probe days, taken only across days
#        whose PRICE containment passes, minimum 3 such days, else no measured-volume candidate;
#   (ii) the event's CHOSEN PRICE factor joins the volume candidate set. Volume candidate order:
#        ours(share-count) > chosen-price-factor > measured-minimum > absent.
# The arbitration is unchanged: per-day price containment AND per-day gate 1, band UNWIDENED.

#: ABB's four live probe days (QUESTIONS.md Q-12's own measured table): the PRICE factor is a
#: rock-solid 0.8976 on all four, while the VOLUME recoveries scatter UPWARD from that same number
#: -- 2019-12-18 sits exactly on it and the others 0.04%..0.78% above. That upward scatter is the
#: pre-open auction shortfall, and it is what biases a median HIGH.
_ABB_EX = date(2019, 12, 20)
_ABB_PRICE = Decimal("0.8976")
_ABB_DAYS = [
    (date(2019, 12, 16), 124749, Decimal("0.897998")),
    (date(2019, 12, 17), 44311, Decimal("0.899205")),
    (date(2019, 12, 18), 120958, Decimal("0.897601")),
    (date(2019, 12, 19), 90154, Decimal("0.904588")),
]


def _abb_era() -> va.EraMeasurement:
    probes = [
        _probe(day, 145000 + 700 * i, 143000 + 500 * i, raw_vol, _ABB_PRICE, recovery)
        for i, (day, raw_vol, recovery) in enumerate(_ABB_DAYS)
    ]
    return va.measure_era((_ABB_EX,), "pre-2019-12-20", probes)


def test_q12_the_median_volume_estimator_is_biased_high_and_the_minimum_is_not() -> None:
    """The measured ABB flip, at the exact point it lives: a median that rejects a reconciling era
    versus the ruled minimum that accepts it. The band is NOT widened in either case."""
    era = _abb_era()
    biased_median = era.volume_cumulative                 # the SUPERSEDED estimator
    ruled_minimum = va.volume_estimator(era, _ABB_PRICE)  # the ruled estimator
    assert ruled_minimum is not None
    assert ruled_minimum < biased_median                  # the auction skews the median UP
    assert biased_median == pytest.approx(Decimal("0.8986"), abs=Decimal("0.0002"))
    assert ruled_minimum == pytest.approx(_ABB_PRICE, abs=Decimal("0.0001"))

    # ... and that difference is the whole story: the median fails a probe day on the -0.1% floor,
    # the minimum reconciles every one of them.
    assert not va._volume_reconciled(era, biased_median)
    assert va._volume_reconciled(era, ruled_minimum)
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")  # unwidened, as ruled


def test_q12_the_abb_era_is_provable_and_takes_the_chosen_price_factor_for_volume() -> None:
    """ABB end to end: a demerger with no ``ours`` factor at all. The price oracle pins 0.8976 as
    MEASURED, clause (ii) hands that same factor to the volume pass, every probe day reconciles, and
    the ~790 symbol-days the median cost are recovered."""
    events = [va.EventSpec(KIND_DEMERGER, _ABB_EX, None, False)]
    amap = va.build_map("ABB", date(2026, 7, 26), events, [_abb_era()], tick_paise=5)
    era = amap.eras[0]
    assert era.provable, era.note
    choice = _choice(era, _ABB_EX)
    assert choice.price_source == va.SOURCE_MEASURED
    assert choice.price_factor == pytest.approx(_ABB_PRICE, abs=Decimal("0.00005"))
    assert choice.volume_source == va.SOURCE_PRICE_FACTOR
    assert choice.volume_factor == choice.price_factor
    assert era.volume_gap_pct is not None
    assert qg.VOLUME_GAP_MIN_PCT <= era.volume_gap_pct <= qg.VOLUME_GAP_MAX_PCT
    # every stored day of the era is now un-adjustable, which is what coverage is made of.
    assert amap.factors_for_day(date(2017, 3, 15)) is not None


def test_q12_the_adanient_shape_our_terp_matches_the_vendor_and_carries_the_volume() -> None:
    """ADANIENT: a rights whose our-TERP (0.969485) matches the vendor to six decimals. The price
    side is therefore ``ours``; the volume side has no ``ours`` (a rights volume factor is not our
    TERP by construction), and clause (ii) lets the proven price factor carry it. Under the median it
    failed 2 of 4 days and cost 92% of the symbol's history."""
    ex = date(2025, 11, 17)
    terp = Decimal("0.969485")
    probes = [
        _probe(date(2025, 11, 10) + timedelta(days=i), 230000 + 900 * i, 227000 + 700 * i,
               1_000_000 + 5000 * i, terp, terp * (Decimal(1) + Decimal("0.0007") * i))
        for i in range(4)
    ]
    events = [va.EventSpec(KIND_RIGHTS, ex, terp, False)]
    amap = va.build_map("ADANIENT", date(2026, 7, 26), events,
                        [va.measure_era((ex,), "pre-2025-11-17", probes)], tick_paise=5)
    era = amap.eras[0]
    assert era.provable, era.note
    choice = _choice(era, ex)
    assert choice.price_source == va.SOURCE_OURS and choice.price_factor == terp
    assert choice.volume_source == va.SOURCE_PRICE_FACTOR and choice.volume_factor == terp


# --- clause (i) in isolation: the min-vs-median MUTATION --------------------------------


def _diverging_auction_era() -> va.EraMeasurement:
    """A rights the vendor scaled by 0.97 on price and 0.80 on volume, with a per-day auction
    shortfall of 0.00%/0.30%/0.60%/0.90% on top of the volume observable.

    The 21% price/volume divergence is far outside gate 1's band, so the chosen-price-factor
    candidate CANNOT serve and ``measured`` is forced -- which isolates clause (i): the committed
    volume factor is the estimator's own output and nothing else.
    """
    probes = [
        _probe(date(2018, 6, 1) + timedelta(days=i), 100002 + 300 * i, 95009 + 500 * i,
               1_000_000 + i, Decimal("0.97"),
               Decimal("0.80") * (Decimal(1) + Decimal("0.003") * i))
        for i in range(4)
    ]
    return va.measure_era((date(2019, 1, 15),), "pre-ex", probes)


def test_q12_mutation_swapping_the_minimum_back_to_the_median_breaks_the_era(monkeypatch) -> None:
    """A real mutation test of the flip the ruling turns on.

    HEAD (the ruled MINIMUM) resolves the era and commits ~0.80. Mutate ONLY the estimator back to
    the median -- the superseded Q-11 wording -- and the same inputs leave the era UN-PROVABLE,
    because the median sits above the true factor and the zero-auction probe day then lands below
    gate 1's -0.1% floor. Nothing else about the builder changes.
    """
    ex = date(2019, 1, 15)
    events = [va.EventSpec(KIND_RIGHTS, ex, Decimal("0.95"), False)]
    era = _diverging_auction_era()

    ruled = va.build_map("DIVERGE", date(2026, 6, 1), events, [era])
    assert ruled.eras[0].provable
    choice = _choice(ruled.eras[0], ex)
    assert choice.volume_source == va.SOURCE_MEASURED
    assert choice.volume_factor == pytest.approx(Decimal("0.80"), abs=Decimal("0.0005"))

    monkeypatch.setattr(
        va, "volume_estimator",
        lambda era_, k_price, **kw: va._median([p.volume_recovery() for p in era_.probe_days]),
    )
    mutant = va.build_map("DIVERGE", date(2026, 6, 1), events, [era])
    assert not mutant.eras[0].provable, "the min-vs-median flip is not load-bearing"


def test_q12_only_price_passing_days_may_set_the_volume_floor() -> None:
    """Clause (i)'s day filter, tested where it lives.

    A day whose un-adjusted price does NOT land inside containment carries a confounded ratio -- a
    vendor re-adjustment floor inside the era, a corrupt fold -- and must never set the volume floor.
    Here the fourth day was adjusted by a DIFFERENT price factor and also carries the lowest volume
    ratio; the estimator must ignore it and take the minimum of the three that pass.

    (At build level the price oracle rejects such an era outright -- ``_price_contained`` quantifies
    over every day -- so this filter is a GUARD on the estimator, and this is the level at which it
    can be observed.)
    """
    good = [
        _probe(date(2020, 3, 2) + timedelta(days=i), 100000 + 100 * i, 98000, 500000,
               Decimal("0.9"), Decimal("0.9") + Decimal("0.001") * (i + 1))
        for i in range(3)
    ]
    rogue = _probe(date(2020, 3, 6), 100000, 98000, 500000, Decimal("0.5"), Decimal("0.5"))
    era = va.measure_era((date(2021, 1, 1),), "mixed", [*good, rogue])

    passing = va.price_passing_probe_days(era, Decimal("0.9"))
    assert rogue not in passing and len(passing) == 3
    floor = va.volume_estimator(era, Decimal("0.9"))
    assert floor == min(p.volume_recovery() for p in good)  # the rogue 0.5 did NOT set the floor
    assert floor is not None and floor > Decimal("0.9")


def test_q12_fewer_than_three_price_passing_days_offers_no_measured_volume_candidate() -> None:
    """"minimum 3 such days, else no measured-volume candidate", literally. With 2 probe days the
    estimator refuses to answer, so ``build_map`` never SOLVEs a volume factor -- and an event with
    no ``ours`` and no usable price factor is left un-provable rather than fitted off two points."""
    ex = date(2019, 1, 15)
    probes = [
        _probe(date(2018, 6, 1) + timedelta(days=i), 100000, 98000, 500000,
               Decimal("0.97"), Decimal("0.80") * (Decimal(1) + Decimal("0.003") * i))
        for i in range(2)
    ]
    era = va.measure_era((ex,), "two-days", probes)
    assert va.volume_estimator(era, Decimal("0.97")) is None
    assert va.volume_estimator(era, Decimal("0.97"), min_days=2) is not None  # the knob, not magic

    events = [va.EventSpec(KIND_RIGHTS, ex, Decimal("0.95"), False)]
    amap = va.build_map("THIN", date(2026, 6, 1), events, [era])
    assert not amap.eras[0].provable
    assert amap.factors_for_day(date(2018, 6, 1)) is None  # excluded + counted, never guessed


def test_q12_the_volume_candidate_order_is_exactly_as_ruled() -> None:
    """ours(share-count) > chosen-price-factor > measured-minimum > absent, and the PRICE side is
    untouched (ours > absent > measured). ``absent`` moving to LAST is volume-only."""
    assert va._VOLUME_COST[va.SOURCE_OURS] < va._VOLUME_COST[va.SOURCE_PRICE_FACTOR]
    assert va._VOLUME_COST[va.SOURCE_PRICE_FACTOR] < va._VOLUME_COST[va.SOURCE_MEASURED]
    assert va._VOLUME_COST[va.SOURCE_MEASURED] < va._VOLUME_COST[va.SOURCE_ABSENT]
    assert va._COST == {va.SOURCE_OURS: 0, va.SOURCE_ABSENT: 1, va.SOURCE_MEASURED: 2}


def test_q12_a_share_count_event_and_a_dividend_keep_their_cost_zero_volume_ours() -> None:
    """The reordering can only ever decide an event with NO volume ``ours``. A bonus/split carries
    its price factor as its volume ``ours``; a cash dividend carries 1.0 (volume never scales for
    it). Both stay cost 0, so ``absent`` moving last cannot demote them."""
    bonus = va.EventSpec(KIND_BONUS, date(2020, 1, 1), Decimal("0.5"), True)
    dividend = va.EventSpec(KIND_DIVIDEND, date(2020, 1, 1), Decimal("0.98"), False)
    rights = va.EventSpec(KIND_RIGHTS, date(2020, 1, 1), Decimal("0.95"), False)
    demerger = va.EventSpec(KIND_DEMERGER, date(2020, 1, 1), None, False)
    assert bonus.our_volume_factor() == Decimal("0.5")
    assert dividend.our_volume_factor() == Decimal(1)
    assert rights.our_volume_factor() is None
    assert demerger.our_volume_factor() is None


def test_the_gate1_floor_is_not_widened_by_the_q12_ruling() -> None:
    """The ruling's closing clause. Pinned as literals here as well as in test_quality_gates.py,
    because this is the module that would be tempted to relax it."""
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")
    assert qg.VOLUME_GAP_MAX_PCT == Decimal("5.0")


# --- the estimator provenance marker ---------------------------------------------------


def test_a_map_built_under_the_superseded_median_estimator_is_detected_as_stale() -> None:
    """A persisted map records WHICH volume estimator built it. A map written before the Q-12 ruling
    carries no marker, so it reads back stale and must be rebuilt -- never consumed, because its
    committed volume factors came from the biased median and its un-provable eras may be provable."""
    amap = _acme_map()
    assert amap.volume_estimator_id == va.MAP_VOLUME_ESTIMATOR
    assert va.map_is_current(amap)

    payload = va.to_dict(amap)
    assert payload["volume_estimator"] == va.MAP_VOLUME_ESTIMATOR
    assert va.map_is_current(va.from_dict(payload))  # round-trips

    payload.pop("volume_estimator")  # exactly the shape a pre-ruling map file has on disk
    stale = va.from_dict(payload)
    assert stale.volume_estimator_id == ""
    assert not va.map_is_current(stale)
    assert stale.eras == amap.eras  # readable, just not trustworthy as a factor source
