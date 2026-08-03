"""Orchestration for the daily bias engine (chunk 4). I/O allowed here, unlike bias.py.

The pure rules live in :mod:`acumen.bias`; this module FEEDS them:

* it pulls the CONTEXT 3.2 pair (candle D-1 current, candle D-2 previous) from the calendar
  and the daily store, selecting the equity series (QUESTIONS.md Q-4);
* it applies the pairwise corporate-action adjustment (chunk-3 :func:`adjust_pair`), bringing
  the PREVIOUS candle into the CURRENT candle's price scale (CONTEXT 3.2 / 7-E11);
* it consumes the SUPPRESSION list -- demergers and Q-6 tier-2 rights (:func:`suppression_dates`)
  -- and for a day D where ``D-1`` or ``D-2`` is a suppression ex-date makes no bias update and
  marks the day no-trade (CONTEXT 3.2);
* it handles seeding -- walk forward from the first data, no bias (and no trading) until a rule
  first fires -- and carries the last bias across days that do not fire;
* it binds the (symbol, date) :data:`MinuteLoader` down to the zero-arg provider Rule 3 needs,
  falling back to carry when a Rule-3 day has no 1-minute data.

The one-minute loader is an INTERFACE here (``(symbol, date) -> candles or None``). Its real
implementation is chunk 5A; chunk-4 tests inject fixture CSVs via :func:`csv_minute_loader`.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import corp_actions as ca
from .bias import BULLISH, BEARISH, Candle, MinuteProvider, evaluate_pair
from .calendar import CalendarError, TradingCalendar
from .daily_store import DailyStore

#: The one-minute data interface Rule 3 needs. chunk 5A implements it for real; a test passes
#: a loader that reads fixture CSVs. Returning ``None`` means "no 1-minute data for that day"
#: (old dates) and triggers the documented carry fallback.
MinuteLoader = Callable[[str, date], Sequence[Candle] | None]


class BiasEngineError(RuntimeError):
    """The bias orchestration cannot assemble the inputs a pair needs."""


#: The rule a day carries when its Rule-3 minute evidence is MALFORMED (QUESTIONS.md Q-21,
#: architect 03-Aug-2026). It is neither a decision nor a carry-with-a-reason: the pair is
#: UNRESOLVABLE, and the orchestration above refuses the whole DAY under its own
#: ``REASON_BIAS_UNRESOLVED``.
RULE_MINUTES_MALFORMED: str = "minutes-malformed"

#: The rule a day carries when its Rule-3 minute evidence is INADMISSIBLE -- D-1 did not pass
#: the CONTEXT 4.5/4.6 gate battery (QUESTIONS.md Q-21(b), architect 03-Aug-2026). Same shape
#: and same machinery as :data:`RULE_MINUTES_MALFORMED`: the pair is UNRESOLVABLE and the whole
#: DAY is refused under ``REASON_BIAS_UNRESOLVED``.
RULE_MINUTES_UNGATED: str = "minutes-ungated"


class UnusableMinuteEvidence(BiasEngineError):
    """Rule-3 minute evidence that may not decide a bias -- for two different reasons.

    QUESTIONS.md Q-21 and its Q-21(b) addendum give the SAME answer to two different questions
    about day C's minutes: if they cannot be trusted, the bias for the pair is UNRESOLVABLE and
    the DAY is refused and counted -- never a crash, and never a scan quietly continued without
    them, because Rule 3 decides on which extreme broke FIRST and evidence that is missing or
    wrong can reverse that.

    Subclasses carry :attr:`rule` (the tag the refused day's ledger row prints) and
    :meth:`detail` (the refusal detail, which must name the specific thing that was wrong).

    It subclasses :class:`BiasEngineError` deliberately: :class:`BiasEngine` turns it into a
    refused DAY, and any escape past that is still a COUNTED no-trade for the symbol rather
    than a dead run.
    """

    #: The :class:`DailyBias` rule tag for this kind of refusal. Set by each subclass.
    rule: str = ""

    def detail(self) -> str:  # pragma: no cover -- every subclass overrides it
        raise NotImplementedError


class MalformedMinuteBar(UnusableMinuteEvidence):
    """A stored 1-minute bar a Rule-3 scan asked for is impossible: O or C outside [L, H].

    Raised by the RUN's minute loader (:func:`acumen.backtest.minute_loader`) at the LOAD
    BOUNDARY, which is the narrowest place that still holds the raw bar and therefore the only
    place that can name it. QUESTIONS.md Q-21 (architect, 03-Aug-2026): malformed minute
    evidence makes the bias unresolvable for that pair, so the DAY is refused and counted --
    never a crash, and never a scan with the corrupt bar quietly dropped, because a scan minus
    a bar could reverse a first-break and therefore the bias itself.
    """

    rule: str = RULE_MINUTES_MALFORMED

    def __init__(
        self,
        *,
        symbol: str,
        day: date,
        stamp: datetime | None,
        open_paise: int,
        high_paise: int,
        low_paise: int,
        close_paise: int,
        volume: int,
    ) -> None:
        self.symbol = symbol
        self.day = day
        self.stamp = stamp
        self.open_paise = open_paise
        self.high_paise = high_paise
        self.low_paise = low_paise
        self.close_paise = close_paise
        self.volume = volume
        super().__init__(self.detail())

    def detail(self) -> str:
        """The refusal detail Q-21 requires: the offending bar's stamp and its OHLCV."""
        stamp = "unstamped" if self.stamp is None else self.stamp.isoformat(sep=" ")
        return (
            f"malformed-minute-bar {self.symbol} {self.day.isoformat()} stamp {stamp} "
            f"O {self.open_paise} H {self.high_paise} L {self.low_paise} "
            f"C {self.close_paise} V {self.volume}"
        )


class UngatedMinuteDay(UnusableMinuteEvidence):
    """A Rule-3 scan asked for a day's minutes and that day FAILS the CONTEXT 4.6 battery.

    QUESTIONS.md **Q-21(b)** (architect, 03-Aug-2026): *"a day's minutes may serve a Rule-3
    first-break scan ONLY if that day passes the CONTEXT 4.5/4.6 gate battery ... a
    battery-failing D-1 makes the bias UNRESOLVABLE: fourth counted case (minutes-ungated),
    same machinery as Q-21's third, detail naming which gate failed."*

    The rationale is the ruling's own: a D-1 sitting in a wrong-price-domain era would have its
    minutes compared against correct-scale daily thresholds (``P.high`` / ``P.low``, brought
    into C's scale by the pairwise adjustment), so the first break the scan finds is arithmetic
    on two different price scales -- a garbage answer that then trades.

    Raised by :func:`acumen.backtest.gated_minute_loader`, which is the only place on the run
    path that holds the stored day AND can reach the battery. ``gate`` and ``gate_reason`` are
    the battery's OWN verdict (:attr:`acumen.signal_engine.DayGates.refusal_detail`), never a
    sentence composed here -- a refusal that paraphrased a gate could drift from it.
    """

    rule: str = RULE_MINUTES_UNGATED

    def __init__(self, *, symbol: str, day: date, gate: str, gate_reason: str) -> None:
        self.symbol = symbol
        self.day = day
        self.gate = gate
        self.gate_reason = gate_reason
        super().__init__(self.detail())

    def detail(self) -> str:
        """The refusal detail Q-21(b) requires: which gate failed, and its own reason."""
        return (
            f"minutes-ungated {self.symbol} {self.day.isoformat()} gate {self.gate} "
            f"reason {self.gate_reason}"
        )


@dataclass(frozen=True)
class DailyBias:
    """The bias in effect for one trading day, with everything the evidence pack needs."""

    trade_date: date
    bias: str | None
    tradeable: bool
    rule: str
    detail: str
    current_date: date | None = None  # candle(D-1)
    previous_date: date | None = None  # candle(D-2)
    previous_candle: Candle | None = None  # P, adjusted into C's scale
    current_candle: Candle | None = None  # C, raw
    suppressed: bool = False
    suppression_reason: str | None = None
    #: This day's bias came from the Rule-3 TIE (see :attr:`acumen.bias.BiasResult.tie_case`) --
    #: the case OPEN-4 was about, resolved by Round-3 Q38/Q39 and still worth flagging for the
    #: chunk-12 pack.
    tie_case: bool = False
    log: str | None = None
    #: Set ONLY when this day's bias could not be resolved at all -- QUESTIONS.md Q-21's third
    #: ``REASON_BIAS_UNRESOLVED`` case (malformed Rule-3 minute evidence) and Q-21(b)'s fourth
    #: (a D-1 that fails the CONTEXT 4.6 battery). It carries the offending bar, or the refusing
    #: gate and its reason, verbatim -- so the orchestration can log it in the refusal without
    #: ever re-reading the store. ``None`` on every other day, so no existing row's bytes move;
    #: :attr:`rule` says WHICH of the two it is.
    unresolved_detail: str | None = None


@dataclass(frozen=True)
class BiasEngine:
    """Turns stored daily candles into the CONTEXT 3.2 bias sequence for a symbol.

    Attributes:
        store: the daily store (raw candles; Q-4 equity-series selection on read).
        calendar: trading days, ``bias_pair``, ``prev_trading_day``.
        factors: the corporate-action factors for pairwise adjustment (empty = no adjustment,
            correct for a symbol/window with no split/bonus/special-dividend).
        suppressions: demerger + Q-6 tier-2 rights ex-dates to suppress across (CONTEXT 3.2).
        minute_loader: the (symbol, date) 1-minute loader for Rule 3; ``None`` means every
            Rule-3 day falls back to carry (documented, R1-Q6).
    """

    store: DailyStore
    calendar: TradingCalendar
    factors: tuple[ca.Factor, ...] = ()
    suppressions: tuple[ca.Suppression, ...] = ()
    minute_loader: MinuteLoader | None = None

    def bias_series(self, symbol: str, from_date: date, to_date: date) -> list[DailyBias]:
        """The bias for every trading day in ``[from_date, to_date]``, seeded at ``from_date``.

        Seeding starts at the first trading day of the range: ``last_bias`` begins ``None`` and
        stays ``None`` (no trading) until a rule first fires. Carries forward across days no
        rule decides, and across suppression windows (no bias update).

        This is a self-contained window -- the carry starts here rather than at the symbol's
        first-ever candle, which is exactly what the chunk-4 F9 "seed day" needs. A full-history
        production run would pass the symbol's first data as ``from_date``.
        """
        if to_date < from_date:
            raise BiasEngineError(f"Empty range: {to_date} before {from_date}.")
        trading_days = [
            day for day in _walk(from_date, to_date) if self._is_trading_day(day)
        ]
        suppress_dates = {s.ex_date: s for s in self.suppressions if s.symbol == symbol.upper()}

        results: list[DailyBias] = []
        last_bias: str | None = None
        for day in trading_days:
            result, last_bias = self._bias_for(symbol, day, last_bias, suppress_dates)
            results.append(result)
        return results

    def bias_for_day(self, symbol: str, day: date, *, seed_from: date | None = None) -> DailyBias:
        """The bias for a single day ``day`` (walking from ``seed_from`` to carry correctly).

        ``seed_from`` defaults to ``day`` itself, which is only right for a day a rule fires on;
        pass the window start to get a carry-correct answer. The bias engine's carry is path
        dependent, so a single day cannot be computed without a start point -- this is why the
        backtest (chunk 9) computes the whole series once.
        """
        start = seed_from if seed_from is not None else day
        series = self.bias_series(symbol, start, day)
        if not series or series[-1].trade_date != day:
            raise BiasEngineError(f"{symbol}: {day} is not a trading day in range.")
        return series[-1]

    # --- internals ----------------------------------------------------------------

    def _bias_for(
        self,
        symbol: str,
        day: date,
        last_bias: str | None,
        suppress_dates: dict[date, ca.Suppression],
    ) -> tuple[DailyBias, str | None]:
        try:
            pair = self.calendar.bias_pair(day)
        except CalendarError as exc:
            raise BiasEngineError(f"{symbol}: no bias pair for {day}: {exc}") from exc
        current_date, previous_date = pair.current, pair.previous

        # Suppression (CONTEXT 3.2): D-1 or D-2 is a demerger / tier-2 rights ex-date ->
        # no bias update AND no trade. The carried bias is kept unchanged.
        for ex_date in (current_date, previous_date):
            supp = suppress_dates.get(ex_date)
            if supp is not None:
                return (
                    DailyBias(
                        trade_date=day,
                        bias=last_bias,
                        tradeable=False,
                        rule="suppressed",
                        detail=(
                            f"suppressed: {supp.kind} ex-date {ex_date} is D-"
                            f"{'1' if ex_date == current_date else '2'} of the pair "
                            f"(CONTEXT 3.2); no bias update, no trade"
                        ),
                        current_date=current_date,
                        previous_date=previous_date,
                        suppressed=True,
                        suppression_reason=supp.reason,
                        log=f"{symbol} {day}: suppressed across {supp.kind} ex {ex_date}",
                    ),
                    last_bias,  # unchanged
                )

        current = self._candle(symbol, current_date)
        previous_raw = self._candle(symbol, previous_date)
        if current is None or previous_raw is None:
            # A candle is missing (the symbol had not listed yet): seeding has not started.
            return (
                DailyBias(
                    trade_date=day,
                    bias=last_bias,
                    tradeable=last_bias is not None,
                    rule="no-data",
                    detail=f"no equity candle for {'current ' + str(current_date) if current is None else 'previous ' + str(previous_date)}; not seeded",
                    current_date=current_date,
                    previous_date=previous_date,
                ),
                last_bias,
            )

        previous_adj = self._adjust_previous(symbol, previous_raw, current)
        provider: MinuteProvider = self._provider(symbol, current_date)
        try:
            outcome = evaluate_pair(previous_adj, current, provider, last_bias)
        except UnusableMinuteEvidence as exc:
            # QUESTIONS.md Q-21 (architect, 03-Aug-2026): "malformed minute evidence makes the
            # bias UNRESOLVABLE for that pair -- the day joins REASON_BIAS_UNRESOLVED as its
            # third case (minutes-malformed), counted, never a crash", and Q-21(b) adds the
            # FOURTH case in the same shape -- a D-1 that fails the CONTEXT 4.6 battery is not
            # admissible evidence either ("same machinery as Q-21's third"). The carried bias is
            # left UNCHANGED in both: a day whose evidence cannot be used decides nothing, in
            # either direction.
            return (
                DailyBias(
                    trade_date=day,
                    bias=last_bias,
                    tradeable=False,
                    rule=exc.rule,
                    detail=exc.detail(),
                    current_date=current_date,
                    previous_date=previous_date,
                    previous_candle=previous_adj,
                    current_candle=current,
                    unresolved_detail=exc.detail(),
                    log=(
                        f"{symbol} {day}: Rule-3 minute evidence unusable on {current_date} "
                        f"({exc.rule}) -> bias unresolvable, day refused (Q-21)"
                    ),
                ),
                last_bias,  # unchanged
            )

        new_bias = outcome.bias
        return (
            DailyBias(
                trade_date=day,
                bias=new_bias,
                tradeable=new_bias is not None,
                rule=outcome.rule,
                detail=outcome.detail,
                current_date=current_date,
                previous_date=previous_date,
                previous_candle=previous_adj,
                current_candle=current,
                tie_case=outcome.tie_case,
                log=outcome.log,
            ),
            new_bias,
        )

    def _adjust_previous(self, symbol: str, previous: Candle, current: Candle) -> Candle:
        """Bring the previous candle into the current candle's scale (CONTEXT 3.2 / 7-E11)."""
        between = ca.factors_between(
            self.factors, previous.day, current.day, symbol=symbol
        ) if previous.day is not None and current.day is not None else ()
        if not between:
            return previous
        return Candle(
            open=ca.adjust_pair(previous.open, between),
            high=ca.adjust_pair(previous.high, between),
            low=ca.adjust_pair(previous.low, between),
            close=ca.adjust_pair(previous.close, between),
            day=previous.day,
        )

    def _provider(self, symbol: str, current_date: date) -> MinuteProvider:
        loader = self.minute_loader
        if loader is None:
            return lambda: None
        return lambda: loader(symbol, current_date)

    def _candle(self, symbol: str, day: date) -> Candle | None:
        frame = self.store.daily(symbol, day, day)
        if frame.empty:
            return None
        row = frame.iloc[0]
        return Candle(
            open=int(row["open_paise"]),
            high=int(row["high_paise"]),
            low=int(row["low_paise"]),
            close=int(row["close_paise"]),
            day=day,
        )

    def _is_trading_day(self, day: date) -> bool:
        try:
            return self.calendar.is_trading_day(day)
        except CalendarError:
            return False


def _walk(start: date, end: date) -> Iterable[date]:
    from datetime import timedelta

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


# --- the fixture minute loader (test infrastructure; chunk 5A ships the real one) ----------


def csv_minute_loader(directory: Path | str) -> MinuteLoader:
    """A :data:`MinuteLoader` that reads ``<SYMBOL>_<YYYY-MM-DD>_1min.csv`` from a directory.

    Columns: ``stamp,open,high,low,close`` (prices in RUPEES, parsed to integer paise via
    ``Decimal`` exactly -- CONTEXT 7-E11). Rows are returned in file order (chronological).
    Missing file -> ``None`` (the "no 1-minute data" case). This is the shape chunk 5A's real
    loader will satisfy; here it lets the synthetic Rule-3 / tie fixtures drive the engine.
    """
    base = Path(directory)

    def load(symbol: str, day: date) -> Sequence[Candle] | None:
        path = base / f"{symbol.upper()}_{day.isoformat()}_1min.csv"
        if not path.is_file():
            return None
        return load_minutes_csv(path)

    return load


def load_minutes_csv(path: Path | str) -> tuple[Candle, ...]:
    """Parse one 1-minute fixture CSV into candles (rupees -> integer paise). PURE-ish (reads a file)."""
    source = Path(path)
    candles: list[Candle] = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for line, raw in enumerate(reader, start=2):
            row = {str(k).strip(): (v or "").strip() for k, v in raw.items() if k}
            stamp = _parse_stamp(row.get("stamp"))
            candles.append(
                Candle(
                    open=_paise(row.get("open"), "open", line),
                    high=_paise(row.get("high"), "high", line),
                    low=_paise(row.get("low"), "low", line),
                    close=_paise(row.get("close"), "close", line),
                    stamp=stamp,
                )
            )
    return tuple(candles)


def _parse_stamp(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _paise(text: str | None, field: str, line: int) -> int:
    if not text:
        raise BiasEngineError(f"line {line}: {field} is empty in the 1-minute fixture")
    try:
        scaled = Decimal(text) * 100
    except InvalidOperation as exc:
        raise BiasEngineError(f"line {line}: {field}={text!r} is not a number") from exc
    if scaled != scaled.to_integral_value():
        raise BiasEngineError(f"line {line}: {field}={text!r} is not a whole number of paise")
    return int(scaled)
