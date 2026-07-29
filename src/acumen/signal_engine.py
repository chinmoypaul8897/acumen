"""Orchestration for the signal engine (chunk 7). I/O allowed here, unlike signals.py.

The pure rules live in :mod:`acumen.signals`; this module FEEDS them one stock-day at a time,
and it is the only place the four engines meet:

* the day's stored 1-minute candles come out of the chunk-5A minute store (RAW prices -- the
  store holds raw only, CONTEXT 7-E11);
* the **gate battery of CONTEXT 4.6** is recomputed for that day -- gate 1 (volume
  reconciliation, with the auction-relief branch), gate 2 (integrity, under the completeness
  ruling) and **gate 1P** (per-day price containment, the Q-14 ruling). All three are required.
  A day that fails ANY of them yields NO signal evaluation at all and is counted under the gate
  that refused it (CONTEXT 7-E3);
* the 15-minute candles are AGGREGATED from those minutes by :mod:`acumen.aggregate`
  (CONTEXT 7-E1/E12) -- never fetched separately, so a bar the signal engine sees is identical
  in the backtest and in the live screener (CONTEXT 6);
* the POC comes from :mod:`acumen.poc` (CONTEXT 3.3), keyed on the symbol's own tick from the
  instrument master and the config's Row Size;
* the bias comes from :mod:`acumen.bias_engine` (CONTEXT 3.2) and decides the SIDE -- bullish
  day long only, bearish day short only, no bias (or a suppressed day) means no evaluation.

**Why gate 1P is recomputed here rather than looked up.** CONTEXT 4.6 makes it a duty:
"recompute gate 1P per day (pure function, both stores local -- there is no per-day exclusion
file)". The chunk-5B residual register is per SYMBOL and its ledger persists only sample dates,
so a per-day answer has to be derived, and it is cheap and exact to derive because both sides of
the comparison are local.

**Order of refusal.** A day can fail several ways at once; this module records the FIRST reason
in a fixed order -- no minutes, then the gate battery, then bias, then POC -- so the counts
chunk 9 prints partition the days instead of double-counting them. Each reason is its own
constant.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from . import poc as poc_engine
from . import quality_gates as gates
from . import signals as sig
from .aggregate import Bar, aggregate_15min
from .bias_engine import DailyBias
from .daily_store import DailyStore
from .instrument_master import InstrumentMaster
from .minute_store import MinuteStore, StoredBar

#: Why a stock-day was not evaluated. Exactly one is set when ``evaluated`` is False.
NOT_EVALUATED_NO_MINUTES: str = "no stored 1-minute candles for this symbol-day"
NOT_EVALUATED_GATE1: str = "gate 1 (volume reconciliation)"
NOT_EVALUATED_GATE2: str = "gate 2 (candle integrity)"
NOT_EVALUATED_GATE1P: str = gates.REASON_GATE1P
NOT_EVALUATED_NO_BIAS: str = "no bias yet (CONTEXT 3.2 seeding: not seeded)"
NOT_EVALUATED_SUPPRESSED: str = "bias suppressed across a demerger/rights ex-date (CONTEXT 3.2)"
NOT_EVALUATED_NO_POC: str = "no POC for the day (CONTEXT 3.3)"

#: The day was evaluated; ``signal`` carries the outcome (which may itself be "no trade").
EVALUATED: str = "evaluated"


@dataclass(frozen=True)
class DayGates:
    """The CONTEXT 4.6 battery for one stored symbol-day, all three verdicts side by side.

    ``volume_reconciled`` is what gate 2 and the POC engine consume: gate 1's verdict, True when
    it passed strictly OR by auction relief (decision B122, chunk 5B), ``None`` when it could not
    be run at all because the day has no raw daily row.
    """

    gate1: gates.VolumeGateResult | None
    relieved: bool
    volume_reconciled: bool | None
    gate2: gates.IntegrityGateResult
    gate1p: gates.PriceContainmentResult

    @property
    def usable(self) -> bool:
        """CONTEXT 4.6: all three are required for a day to be usable."""
        return bool(self.volume_reconciled) and self.gate2.passed and self.gate1p.passed

    @property
    def refusal(self) -> str | None:
        """Which gate refused the day, in the battery's own order, or ``None`` if none did.

        A day with NO raw daily row is counted under gate 1P and never under gate 1: gate 1
        could not run at all (there is nothing to reconcile against), while gate 1P FAILS it
        outright -- the Q-14 ruling's own words, and the reason its denominator is every stored
        day. Folding such a day into gate 1's count is exactly what that ruling forbids.
        """
        if self.gate1 is None:
            return NOT_EVALUATED_GATE1P
        if not self.volume_reconciled:
            return NOT_EVALUATED_GATE1
        if not self.gate2.passed:
            return NOT_EVALUATED_GATE2
        if not self.gate1p.passed:
            return NOT_EVALUATED_GATE1P
        return None


@dataclass(frozen=True)
class StockDay:
    """One stock-day through the whole pipeline: bias -> gates -> POC -> signal.

    Everything the chunk-12 replay pack needs to print a day in plain English is here, whether
    or not it produced a trade -- including the inputs that refused it.
    """

    symbol: str
    day: date
    evaluated: bool
    reason: str
    bias: DailyBias | None = None
    side: str | None = None
    gates: DayGates | None = None
    profile: poc_engine.DayProfile | None = None
    bars: tuple[Bar, ...] = ()
    minute_count: int = 0
    signal: sig.SignalDay | None = None

    @property
    def traded(self) -> bool:
        return self.signal is not None and self.signal.traded


@dataclass(frozen=True)
class SignalPipeline:
    """Wires the stores and the four engines together for one symbol-day at a time.

    Attributes:
        minute_store: the chunk-5A 1-minute store (RAW prices).
        daily_store: the chunk-2 daily store -- the RAW bhavcopy oracle both gate 1 and gate 1P
            measure against.
        master: the instrument master, for the symbol's own tick (CONTEXT 4.3: NEVER hardcode).
        row_size: N from ``config.yaml`` (CONTEXT 3.3; the trader-confirmed 24).
    """

    minute_store: MinuteStore
    daily_store: DailyStore
    master: InstrumentMaster
    row_size: int

    def stock_day(self, symbol: str, day: date, *, bias: DailyBias) -> StockDay:
        """Evaluate CONTEXT 3.4 for one symbol-day, or record why it was not evaluated.

        Args:
            symbol: the ticker.
            day: the trade date.
            bias: that day's bias, from :class:`acumen.bias_engine.BiasEngine`. Its ``bias`` and
                ``suppressed`` fields decide the side; this module never recomputes a bias, so
                the backtest's path-dependent carry (chunk 9 computes the series once) cannot
                diverge from what the signal engine used.
        """
        minutes = self.minute_store.minutes(symbol, day)
        if not minutes:
            return StockDay(
                symbol=symbol, day=day, evaluated=False, reason=NOT_EVALUATED_NO_MINUTES, bias=bias
            )

        day_gates = self.gate_day(symbol, day, minutes)
        refusal = day_gates.refusal
        if refusal is not None:
            return StockDay(
                symbol=symbol,
                day=day,
                evaluated=False,
                reason=refusal,
                bias=bias,
                gates=day_gates,
                minute_count=len(minutes),
            )

        if bias.suppressed:
            return StockDay(
                symbol=symbol, day=day, evaluated=False, reason=NOT_EVALUATED_SUPPRESSED,
                bias=bias, gates=day_gates, minute_count=len(minutes),
            )
        side = sig.side_for_bias(bias.bias)
        if side is None:
            return StockDay(
                symbol=symbol, day=day, evaluated=False, reason=NOT_EVALUATED_NO_BIAS,
                bias=bias, gates=day_gates, minute_count=len(minutes),
            )

        profile = poc_engine.day_profile(
            minutes,
            day,
            row_size=self.row_size,
            tick_paise=self.master.instrument(symbol).tick_size_paise,
            volume_reconciled=day_gates.volume_reconciled,
        )
        if profile.poc_paise is None:
            return StockDay(
                symbol=symbol, day=day, evaluated=False,
                reason=f"{NOT_EVALUATED_NO_POC}: {profile.reason}",
                bias=bias, side=side, gates=day_gates, profile=profile,
                minute_count=len(minutes),
            )

        bars = aggregate_15min(minutes)
        signal = sig.evaluate_day(
            bars, day=day, side=side, poc_paise=profile.poc_paise, minute_bars=minutes
        )
        return StockDay(
            symbol=symbol, day=day, evaluated=True, reason=EVALUATED,
            bias=bias, side=side, gates=day_gates, profile=profile, bars=bars,
            minute_count=len(minutes), signal=signal,
        )

    def gate_day(
        self, symbol: str, day: date, minutes: Sequence[StoredBar]
    ) -> DayGates:
        """The CONTEXT 4.6 battery for one stored symbol-day. Recomputed, never looked up.

        The composition is chunk 5B's, unchanged: gate 1 runs first because the completeness
        ruling makes its verdict gate 2's completeness oracle; an ABOVE-ceiling gate-1 failure is
        offered to the auction-relief branch; gate 1P runs on EVERY stored day from the same fold
        and a day with no raw daily row FAILS it (the Q-14 ruling's own words).
        """
        fold_high = max(int(bar.high_paise) for bar in minutes)
        fold_low = min(int(bar.low_paise) for bar in minutes)
        fold_volume = sum(int(bar.volume) for bar in minutes)
        first_open = min(minutes, key=lambda bar: bar.stamp).open_paise

        row = self._daily_row(symbol, day)
        gate1p = gates.price_containment_gate(
            fold_high,
            fold_low,
            None if row is None else int(row["high_paise"]),
            None if row is None else int(row["low_paise"]),
        )

        gate1: gates.VolumeGateResult | None = None
        relieved = False
        reconciled: bool | None = None
        if row is not None:
            gate1 = gates.volume_gate(int(row["volume"]), fold_volume)
            if not gate1.passed:
                relief = gates.auction_relief(
                    gate1,
                    minute_open_paise=int(first_open),
                    minute_high_paise=fold_high,
                    minute_low_paise=fold_low,
                    raw_open_paise=int(row["open_paise"]),
                    raw_high_paise=int(row["high_paise"]),
                    raw_low_paise=int(row["low_paise"]),
                )
                relieved = relief.relieved
            reconciled = gate1.passed or relieved

        gate2 = gates.integrity_gate(minutes, day, volume_reconciled=reconciled)
        return DayGates(
            gate1=gate1,
            relieved=relieved,
            volume_reconciled=reconciled,
            gate2=gate2,
            gate1p=gate1p,
        )

    def _daily_row(self, symbol: str, day: date):
        """The RAW bhavcopy row for one symbol-day, or ``None`` when the store has none."""
        frame = self.daily_store.daily(symbol, day, day)
        if frame.empty:
            return None
        return frame.iloc[0]
