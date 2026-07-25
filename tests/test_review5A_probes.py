"""Reviewer probes for chunk 5A (REVIEW_5A). Added by the fresh QC review, kept in the repo.

These close two gaps the builder's own suite (test_vendor_adjustment.py) left un-pinned, both
about the Q-11 measurement DISCIPLINE the architect's ruling turns on:

1. **The min-cost preference must never mask a MATERIAL vendor variant.** The arbitration prefers
   ``ours`` over ``measured`` (cost 0 vs 2). The ruling's safety net is that the price-containment
   oracle rejects ``ours`` when the vendor's real factor differs materially, forcing ``measured``.
   This pins exactly that boundary: a vendor bonus factor >0.1% off ours is caught (-> measured,
   recovering the true factor), while a sub-0.1% variant is (correctly, harmlessly) masked as
   ``ours`` -- below the 0.1% microstructure floor, i.e. immaterial. Without this test the
   preference could silently swallow a real, material variant and nothing would notice.

2. **The committed map factors are order-invariant** (determinism of the OBSERVABLE, not of the
   input order). ``build_map`` claims "the same fetched inputs produce the same map"; a stronger,
   safer property is that the COMMITTED factors do not depend on the order probe days arrive in
   (medians are order-free). Only the audit ``probe_days`` list tracks input order. This pins the
   factors invariant so a future refactor cannot make a k depend on fetch ordering.

Both are OFFLINE and pure -- they invert a KNOWN vendor exactly as test_vendor_adjustment.py does.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from acumen import vendor_adjustment as va
from acumen.corp_actions import KIND_BONUS


def _r(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _probe(day: date, raw_high: int, raw_low: int, raw_vol: int, price_cum: Decimal, vol_cum: Decimal) -> va.ProbeDay:
    """Invert a known vendor: fetched = raw x price_cum (price), fetched = raw / vol_cum (volume)."""
    raw_close = (raw_high + raw_low) // 2
    return va.ProbeDay(
        day=day,
        fetched_high=_r(Decimal(raw_high) * price_cum),
        fetched_low=_r(Decimal(raw_low) * price_cum),
        fetched_close=_r(Decimal(raw_close) * price_cum),
        fetched_volume=_r(Decimal(raw_vol) / vol_cum),
        raw_high=raw_high, raw_low=raw_low, raw_close=raw_close, raw_volume=raw_vol,
    )


def _one_bonus_map(vendor_price: Decimal, vendor_vol: Decimal, *, shuffle_seed: int | None = None) -> va.AdjustmentMap:
    """A single-1:1-bonus symbol whose vendor applied `vendor_price`/`vendor_vol` on pre-ex days.
    ours == 0.5 for the bonus; the pre-ex era measures whatever the vendor really did."""
    ex = date(2018, 5, 31)
    F = date(2026, 7, 25)
    events = [va.EventSpec(KIND_BONUS, ex, Decimal("0.5"), True)]
    pre = [
        _probe(date(2016, 10, 3) + timedelta(days=i), 240000 + 100 * i, 238000 + 90 * i, 900000 + i, vendor_price, vendor_vol)
        for i in range(6)
    ]
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(pre)
    post = [_probe(date(2020, 1, 2) + timedelta(days=i), 200000, 198000, 1000000, Decimal(1), Decimal(1)) for i in range(3)]
    eras = [va.measure_era((ex,), "pre", pre), va.measure_era((), "post", post)]
    return va.build_map("SYM", F, events, eras, tick_paise=5)


def _bonus_choice(amap: va.AdjustmentMap) -> va.EventChoice:
    era = next(e for e in amap.eras if e.ex_dates)  # the pre-bonus era
    return era.choices[0]


def test_min_cost_prefers_ours_only_within_containment_measures_a_material_variant() -> None:
    # exact ours -> resolves to ours (cost 0), 0-paise containment.
    exact = _bonus_choice(_one_bonus_map(Decimal("0.5"), Decimal("0.5")))
    assert exact.price_source == va.SOURCE_OURS and exact.price_factor == Decimal("0.5")

    # a sub-0.1% variant (+0.05%): ours still contains it -> masked as ours (immaterial, below the
    # microstructure floor the ruling accepts). This documents the exact masking boundary.
    tiny = _bonus_choice(_one_bonus_map(Decimal("0.50025"), Decimal("0.50025")))
    assert tiny.price_source == va.SOURCE_OURS

    # a MATERIAL variant (+0.2%, above the 0.1% floor): ours FAILS containment, so the oracle
    # forces MEASURED and recovers the vendor's true factor -- the preference cannot swallow it.
    material = _bonus_choice(_one_bonus_map(Decimal("0.5010"), Decimal("0.5010")))
    assert material.price_source == va.SOURCE_MEASURED
    assert material.price_factor == _approx(Decimal("0.5010"))

    # a large variant (+1%) is likewise measured, not silently kept as ours.
    big = _bonus_choice(_one_bonus_map(Decimal("0.505"), Decimal("0.505")))
    assert big.price_source == va.SOURCE_MEASURED
    assert big.price_factor == _approx(Decimal("0.505"))


def test_committed_map_factors_are_invariant_to_probe_day_order() -> None:
    base = _one_bonus_map(Decimal("0.5"), Decimal("0.5"))
    shuffled = _one_bonus_map(Decimal("0.5"), Decimal("0.5"), shuffle_seed=13)
    # the COMMITTED factors are identical regardless of probe-day arrival order (median-based);
    for day in (date(2016, 10, 4), date(2016, 10, 6), date(2020, 1, 3)):
        assert base.factors_for_day(day) == shuffled.factors_for_day(day)
    assert [e.k_price for e in base.eras] == [e.k_price for e in shuffled.eras]
    assert [e.k_volume for e in base.eras] == [e.k_volume for e in shuffled.eras]
    # and a straight rebuild from identical inputs is byte-identical (the ruling's determinism).
    assert va.to_dict(base) == va.to_dict(_one_bonus_map(Decimal("0.5"), Decimal("0.5")))


def _approx(target: Decimal, tol: Decimal = Decimal("0.0005")) -> object:
    class _A:
        def __eq__(self, other: object) -> bool:
            return isinstance(other, Decimal) and abs(other - target) <= tol

        def __repr__(self) -> str:
            return f"~{target}+/-{tol}"

    return _A()
