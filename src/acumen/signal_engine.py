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
from .aggregate import Bar, aggregate_15min, in_session_bars
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

#: Which BATTERY governed a day's verdict (CONTEXT 4.7).
#:
#: ``settled`` -- the day is over and its bhavcopy exists, so CONTEXT 4.6's full battery ran:
#: gate 1 (volume reconciliation, with the auction-relief branch), gate 2 (integrity) and gate 1P
#: (per-day price containment). Every stored symbol-day in the ten-year ledger is this.
#:
#: ``live`` -- CONTEXT 4.7. The day has no bhavcopy oracle until evening, so the ORACLE-FREE
#: battery ran instead: gate 2 (with the Q-21(a) open test), the Q-17 candle-level drops and
#: candle validity. Gates 1 and 1P are not skipped -- they are structurally INAPPLICABLE to
#: same-day data, because what they detect is history being rewritten and today cannot be
#: rewritten during today. The measured price of that posture is in section 4.7 and in
#: docs/evidence/chunk13_q28_residual.md.
POSTURE_SETTLED: str = "settled"
POSTURE_LIVE: str = "live"


@dataclass(frozen=True)
class DayGates:
    """The battery for one symbol-day, every verdict side by side.

    ``volume_reconciled`` is what gate 2 and the POC engine consume: gate 1's verdict, True when
    it passed strictly OR by auction relief (decision B122, chunk 5B), ``None`` when it could not
    be run at all -- because the day has no raw daily row, or (CONTEXT 4.7) because the day is
    TODAY and its bhavcopy does not exist yet. Those two cases are told apart by ``posture``, and
    they must be: the first is a settled day that failed to prove itself and the second is a day
    that cannot yet be asked.

    ``gate1p`` is ``None`` for the same reason and only under :data:`POSTURE_LIVE`; on a settled
    day it is always present, because the Q-14 ruling runs gate 1P on EVERY stored day.
    """

    gate1: gates.VolumeGateResult | None
    relieved: bool
    volume_reconciled: bool | None
    gate2: gates.IntegrityGateResult
    gate1p: gates.PriceContainmentResult | None
    posture: str = POSTURE_SETTLED

    @property
    def usable(self) -> bool:
        """CONTEXT 4.6: all three gates are required for a SETTLED day to be usable.

        CONTEXT 4.7: on a LIVE day the oracle-free battery is the whole battery there is, so
        gate 2's verdict is the day's verdict.
        """
        if self.posture == POSTURE_LIVE:
            return self.gate2.passed
        return (
            bool(self.volume_reconciled)
            and self.gate2.passed
            and self.gate1p is not None
            and self.gate1p.passed
        )

    @property
    def poc_licence(self) -> bool | None:
        """What CONTEXT 3.3's window-validity test is for THIS day, from the battery that ran.

        The POC engine takes one validity verdict (:func:`acumen.poc.day_profile`). On a settled
        day that verdict is gate 1's and nothing has changed -- this property returns
        ``volume_reconciled`` unaltered, which the suite asserts over every settled construction
        so the backtest cannot move. On a LIVE day (CONTEXT 4.7) gate 1 is structurally
        inapplicable and the licence is the ORACLE-FREE battery's own verdict.
        """
        if self.posture == POSTURE_LIVE:
            return self.gate2.passed
        return self.volume_reconciled

    @property
    def refusal(self) -> str | None:
        """Which gate refused the day, in the battery's own order, or ``None`` if none did."""
        detail = self.refusal_detail
        return None if detail is None else detail[0]

    @property
    def refusal_detail(self) -> tuple[str, str] | None:
        """``(which gate refused, that gate's OWN reason)``, or ``None`` if none did.

        The battery's order, decided in exactly one place so the gate NAME and the gate's own
        words can never come from two different verdicts. :attr:`refusal` is the first half of
        this pair, which is what every chunk-9 refusal count keys on.

        A day with NO raw daily row is counted under gate 1P and never under gate 1: gate 1
        could not run at all (there is nothing to reconcile against), while gate 1P FAILS it
        outright -- the Q-14 ruling's own words, and the reason its denominator is every stored
        day. Folding such a day into gate 1's count is exactly what that ruling forbids.

        The REASON half is what QUESTIONS.md Q-21(b) puts in a refused ledger row: a Rule-3 scan
        that is denied a battery-failing D-1 must say which gate denied it and why, in that
        gate's own words rather than in a sentence written here.

        Under :data:`POSTURE_LIVE` the order has ONE gate in it. CONTEXT 4.7 makes gates 1 and 1P
        structurally inapplicable to same-day data, and an inapplicable gate refuses nothing --
        reading their absence as a failure is exactly the reading that left a live morning with
        no POC for any symbol on any day (QUESTIONS.md Q-28).
        """
        if self.posture == POSTURE_LIVE:
            if not self.gate2.passed:
                return (NOT_EVALUATED_GATE2, "; ".join(self.gate2.reasons))
            return None
        gate1p = self.gate1p
        if gate1p is None:
            # The constructor's contract, stated rather than assumed: a SETTLED day always
            # carries a gate-1P verdict (the Q-14 ruling runs it on every stored day, and a day
            # with no raw daily row FAILS it), and a live day never reaches this line.
            raise ValueError(
                "a settled DayGates must carry a gate-1P verdict; only CONTEXT 4.7's live "
                "posture may leave it unrun"
            )
        if self.gate1 is None:
            return (NOT_EVALUATED_GATE1P, gate1p.reason)
        if not self.volume_reconciled:
            return (NOT_EVALUATED_GATE1, self.gate1.reason)
        if not self.gate2.passed:
            return (NOT_EVALUATED_GATE2, "; ".join(self.gate2.reasons))
        if not gate1p.passed:
            return (NOT_EVALUATED_GATE1P, gate1p.reason)
        return None


def oracle_free_battery(day: date, minutes: Sequence[StoredBar]) -> DayGates:
    """CONTEXT 4.7's ORACLE-FREE battery for a LIVE window. PURE, and shared with nothing copied.

    The architect's ruling of 08-Aug-2026 (QUESTIONS.md, verbatim): *"gates 1/1P exist to catch
    history being rewritten, and today cannot be rewritten during today -- so a LIVE morning runs
    the ORACLE-FREE battery per sweep (gate 2 incl. the Q-21(a) open test, Q-17 candle-level
    drops, candle validity)"*.

    Every one of those three is the SAME code the backtester runs, called with the one argument
    that says the session is not over:

    * **gate 2** is :func:`acumen.quality_gates.integrity_gate` itself -- duplicates, impossible
      OHLC including the Q-21(a) open clause, and negative prices or volumes. Not a live copy of
      it, not a subset of it re-implemented here: the function, with
      ``completeness_measurable=False``, which is the one trigger that cannot be asked of a
      session in progress (and which is itself gate-1-derived, so it was never oracle-free);
    * **the Q-17 candle-level drops** are counted by that same call (``out_of_session``) and are
      DROPPED where every consumer drops them, in :meth:`SignalPipeline.evaluate` through
      :func:`acumen.aggregate.in_session_bars`;
    * **candle validity** is gate 2's OHLC and negative-value clauses, which is what that phrase
      names.

    Per SWEEP, not per day: a live window grows all morning, and unlike gate 1 (a whole-day fold
    against a whole-day total) every trigger here is a property of the bars in hand.

    Returns:
        A :class:`DayGates` under :data:`POSTURE_LIVE`, with ``gate1``, ``gate1p`` and
        ``volume_reconciled`` all ``None`` -- not "failed", ``None``: the gates did not run
        because they cannot be run, and the difference is the whole ruling.
    """
    gate2 = gates.integrity_gate(
        minutes, day, volume_reconciled=None, completeness_measurable=False
    )
    return DayGates(
        gate1=None,
        relieved=False,
        volume_reconciled=None,
        gate2=gate2,
        gate1p=None,
        posture=POSTURE_LIVE,
    )


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
    #: 1-minute bars stamped outside 09:15..15:29 that were DROPPED before the engines ran --
    #: CONTEXT 7-E2 at the candle level, which is the reading gate 2 already applies (chunk 5B).
    #: Zero on every day the vendor stamped cleanly; carried so a drop is never silent.
    out_of_session_dropped: int = 0

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
        return self.evaluate(symbol, day, bias=bias, minutes=minutes)

    def evaluate(
        self,
        symbol: str,
        day: date,
        *,
        bias: DailyBias,
        minutes: Sequence[StoredBar],
        gates: DayGates | None = None,
        profile: poc_engine.DayProfile | None = None,
    ) -> StockDay:
        """CONTEXT 3.4 over MINUTES THE CALLER HOLDS -- the one-engine seam (CONTEXT 6).

        :meth:`stock_day` is this method with the store in front of it. The live screener
        (chunk 13) holds its minutes in a recording rather than in the Parquet lake, so it calls
        THIS -- and therefore runs the identical battery, the identical POC engine, the identical
        aggregation and the identical :func:`acumen.signals.evaluate_day`, in the identical
        order. CONTEXT 6's *"same code path, guaranteed no backtest/live drift"* is a property of
        this split rather than a claim beside two implementations.

        ``minutes`` is a whole stock-day of stored bars, ungated and unfiltered -- exactly what
        :meth:`acumen.minute_store.MinuteStore.minutes` returns. The live screener passes the
        bars it has collected SO FAR; the pure engine reads a prefix perfectly well (an absent
        grid stamp is a no-trade quarter-hour, not an error) and the live layer is what knows
        that a square-off marked on the last bar of a prefix is not yet an exit.

        ``gates`` lets a caller that already computed the CONTEXT 4.6 battery for this day hand
        it in instead of paying for it again -- a live sweep evaluates the same day at every
        15-minute boundary and the battery is a whole-day measurement, so recomputing it per
        boundary would be both wasteful and, on a growing prefix, WRONG. ``None`` means
        "compute it here", which is what :meth:`stock_day` does.

        ``profile`` is the same door for CONTEXT 3.3's last sentence -- *"POC is fixed for the
        rest of the day once computed"* (REVIEW_13 B3, architect 08-Aug-2026: *"the POC is fixed
        at 11:15 and immutable for the day"*). A live sweep evaluates a GROWING prefix, so
        recomputing the profile at every boundary would republish the day's POC seventeen times
        and move the entry, stop, target and quantity underneath an alert already delivered. The
        live layer computes it ONCE, at the first sweep at or after 11:15, through
        :meth:`profile_day` -- this engine's own call, not a second implementation -- and hands
        the same object back at every later boundary. ``None`` means "compute it here", which is
        what the backtester does and what keeps the ten-year ledger byte-still.
        """
        day_gates = self.gate_day(symbol, day, minutes) if gates is None else gates
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

        # CONTEXT 7-E2 at the CANDLE level -- gate 2's own reading, applied where the engines
        # consume the day. Gate 1 and gate 1P above deliberately fold the WHOLE stored day
        # (chunk-5B semantics: the vendor's pre-open print is part of the volume the bhavcopy
        # reconciles against), so the filter starts here and nowhere earlier. Zero on almost
        # every day; when it is not zero the count reaches the ledger row (QUESTIONS.md Q-17).
        session, dropped = in_session_bars(minutes)
        if profile is None:
            profile = self.profile_day(symbol, day, minutes, licence=day_gates.poc_licence)
        if profile.poc_paise is None:
            return StockDay(
                symbol=symbol, day=day, evaluated=False,
                reason=f"{NOT_EVALUATED_NO_POC}: {profile.reason}",
                bias=bias, side=side, gates=day_gates, profile=profile,
                minute_count=len(minutes), out_of_session_dropped=dropped,
            )

        bars = aggregate_15min(session)
        signal = sig.evaluate_day(
            bars, day=day, side=side, poc_paise=profile.poc_paise, minute_bars=session
        )
        return StockDay(
            symbol=symbol, day=day, evaluated=True, reason=EVALUATED,
            bias=bias, side=side, gates=day_gates, profile=profile, bars=bars,
            minute_count=len(minutes), signal=signal, out_of_session_dropped=dropped,
        )

    def profile_day(
        self,
        symbol: str,
        day: date,
        minutes: Sequence[StoredBar],
        *,
        licence: bool | None,
    ) -> poc_engine.DayProfile:
        """CONTEXT 3.3's profile for one symbol-day. The ONE place the POC engine is called.

        Split out of :meth:`evaluate` for the same reason :meth:`evaluate` was split out of
        :meth:`stock_day` (decision B328): a caller that must compute the profile ONCE and reuse
        it -- which CONTEXT 3.3's *"POC is fixed for the rest of the day once computed"* makes a
        requirement rather than an optimisation for the live screener -- has to be able to do so
        through this engine's own call rather than by assembling
        :func:`acumen.poc.day_profile`'s arguments a second time somewhere else. The tick, the
        Row Size, the Q-17 session filter and the licence are resolved HERE and nowhere else, so
        a pinned profile and a recomputed one can never be built from different inputs.

        ``licence`` is the GOVERNING battery's verdict (:attr:`DayGates.poc_licence`) -- gate 1's
        on a settled day, the oracle-free battery's on a live one (CONTEXT 4.7).
        """
        session, _dropped = in_session_bars(minutes)
        return poc_engine.day_profile(
            session,
            day,
            row_size=self.row_size,
            tick_paise=self.master.instrument(symbol).tick_size_paise,
            # CONTEXT 4.7: the POC's licence is the GOVERNING battery's verdict -- gate 1 on a
            # settled day, where `poc_licence` IS `volume_reconciled` and nothing moves (the
            # suite asserts the identity), and the oracle-free battery on a live day, where
            # gate 1 is structurally inapplicable. The parameter keeps its historical name
            # because renaming it would edit 41 call sites including frozen-era tests; what it
            # has always meant is "the verdict that licenses this window".
            volume_reconciled=licence,
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
