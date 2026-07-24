"""The corporate-action engine: events in, pairwise price adjustment out (CONTEXT 4.2).

CONTEXT 4.1 says the bhavcopy is UNADJUSTED, and CONTEXT 3.2 makes the bias engine read
adjusted daily candles, so every number this project produces depends on the table in
CONTEXT 4.2 being implemented exactly. Three sources, in the order CONTEXT 4.2 names them:

* **NSE** ``corporates-corporateActions`` JSON -- the primary. Free-text ``subject`` strings
  (" Bonus 1:2", " Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per
  Share", " Rights 2:7"), one window per request, verified back to 2005.
* **BSE** ``CorpactCSVDownload`` CSV -- the second source, for cross-checking. No ISIN, so
  the join is by security NAME and a name mismatch shows up as "not found", never as a
  disagreement.
* **Yahoo** per-ticker split events -- the third vote, and only ever a TIEBREAK. It carries
  splits and bonuses (as combined split ratios) and is blind to rights and demergers.

Three rules this module refuses to break.

**A factor is never guessed.** CONTEXT 4.2's rights and dividend rows need prices this
module does not hold (the cum close, the pre-announcement close, the rights issue price).
Those are INPUTS: :func:`factor_for` raises when one is missing and
:func:`build_factor_table` collects the event as *pending* with the reason. A missing price
must never quietly become ``k = 1``, which is what "no adjustment" looks like from the
outside (CLAUDE.md rule 1).

**A demerger has NO factor.** CONTEXT 4.2: "NO factor exists ... NSE itself terminated RIL
F&O contracts rather than adjust". Asking for one raises; the demerger goes into
:func:`demerger_table`, which chunk 4 uses to block the bias pair and trading across the
ex-date (CONTEXT 3.2).

**An unparseable subject is reported, never dropped.** :func:`parse_actions` returns the
typed events, the informational rows (a bare AGM moves no price), AND the exceptions with
the exact reason. A silent drop is an unadjusted split waiting to happen.

Prices are integer paise (CONTEXT 7-E11); factors are :class:`~decimal.Decimal` so a ratio
like 2/3 stays exact until the single rounding at the end of :func:`adjust_pair`.

The parse and factor halves are PURE. Only the ``fetch_*`` functions touch the network, and
they are opt-in and day-cached like every other endpoint in this repo (CONTEXT 4.1).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import calendar as _calendar
import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import requests

from . import nse_http
from .calendar import parse_nse_date
from .daily_store import INSTRUMENT_SERIES

# --- sources ------------------------------------------------------------------------------

SOURCE_NSE: str = "nse"
SOURCE_BSE: str = "bse"
SOURCE_YAHOO: str = "yahoo"

#: CONTEXT 4.2: "NSE `corporates-corporateActions` JSON API -- verified returning data back
#: to 2005 (year-per-request)". Dates are DD-MM-YYYY.
NSE_CA_URL_TEMPLATE: str = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&from_date={from_date}&to_date={to_date}"
)

#: CONTEXT 4.2: "BSE `CorpactCSVDownload` CSV (sanctioned download, >=2010 verified)".
BSE_CA_URL_TEMPLATE: str = (
    "https://api.bseindia.com/BseIndiaAPI/api/CorpactCSVDownload/w"
    "?scripcode=&Fdate={from_date}&TDate={to_date}"
    "&Purposecode=&strSearch=S&ddlindustrys=&ddlcategorys=E&segment=0"
)
BSE_HOME_URL: str = "https://www.bseindia.com/"

#: CONTEXT 4.2: "Yahoo per-ticker `splits` events ... bonuses appear as combined split
#: ratios; rights invisible there".
YAHOO_CHART_URL_TEMPLATE: str = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    "?period1={period1}&period2={period2}&interval=1d&events=split"
)
#: Yahoo's suffix for an NSE listing.
YAHOO_NSE_SUFFIX: str = ".NS"

#: CONTEXT 4.2's own test oracle, frozen at docs/nse_adjustment_calculator.xlsx.
NSE_ADJUSTMENT_CALCULATOR_URL: str = (
    "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/"
    "Adjustment%20of%20Futures%20and%20Options%20contracts%20Calculator.xlsx"
)

#: These are historical archives pulled rarely, not a live feed. Same pacing as the bhavcopy
#: downloader (chunk-2 card: <= 1 request / 2s), sharing nse_http's process-wide throttle.
MIN_SECONDS_BETWEEN_REQUESTS: float = 2.0

#: IST is UTC+05:30 and has no DST (CONTEXT 7-E8). Used only to read Yahoo's epoch stamps.
_IST_OFFSET: timedelta = timedelta(hours=5, minutes=30)


# --- event kinds (exactly CONTEXT 4.2's table, plus "nothing to adjust") -------------------

KIND_BONUS: str = "bonus"
KIND_SPLIT: str = "split"
KIND_RIGHTS: str = "rights"
KIND_DIVIDEND: str = "dividend"
KIND_BUYBACK: str = "buyback"
KIND_DEMERGER: str = "demerger"
#: A subject that declares no money and no ratio and is a recognized meeting notice. It is
#: still reported and counted -- it is simply not a row of CONTEXT 4.2's table.
KIND_INFORMATIONAL: str = "informational"

PRICED_KINDS: frozenset[str] = frozenset(
    {KIND_BONUS, KIND_SPLIT, KIND_RIGHTS, KIND_DIVIDEND, KIND_BUYBACK}
)
ALL_KINDS: frozenset[str] = PRICED_KINDS | {KIND_DEMERGER, KIND_INFORMATIONAL}

#: CONTEXT 4.2: "Ordinary cash dividend (<2% of pre-announcement close) -> 1"; at or above
#: the threshold it is a special dividend. Spec law, not a tunable.
SPECIAL_DIVIDEND_THRESHOLD: Decimal = Decimal("0.02")


class CorporateActionError(RuntimeError):
    """A corporate action cannot be read, parsed, or turned into a factor."""


# --- records --------------------------------------------------------------------------------


@dataclass(frozen=True)
class CorporateAction:
    """One announced corporate action, as a source published it. Prices are paise."""

    symbol: str
    ex_date: date
    subject: str
    source: str
    series: str | None = None
    isin: str | None = None
    company: str | None = None
    record_date: date | None = None
    face_value_paise: int | None = None
    security_code: str | None = None


@dataclass(frozen=True)
class SplitRatio:
    """One Yahoo split event: ``numerator:denominator`` (3:2 means 3 new shares for 2 old)."""

    symbol: str
    ex_date: date
    numerator: Decimal
    denominator: Decimal
    ratio_text: str
    source: str = SOURCE_YAHOO

    @property
    def k(self) -> Decimal:
        """The pre-ex price multiplier this split implies: ``denominator / numerator``."""
        return self.denominator / self.numerator


@dataclass(frozen=True)
class ParsedEvent:
    """A typed event: the source row plus whatever CONTEXT 4.2's table needs from it."""

    action: CorporateAction
    kind: str
    ratio_new: int | None = None
    ratio_held: int | None = None
    face_from_paise: int | None = None
    face_to_paise: int | None = None
    rights_premium_paise: int | None = None
    rights_price_paise: int | None = None
    dividend_paise: int | None = None
    components: tuple[str, ...] = ()

    @property
    def symbol(self) -> str:
        return self.action.symbol

    @property
    def ex_date(self) -> date:
        return self.action.ex_date

    @property
    def source(self) -> str:
        return self.action.source

    @property
    def subject(self) -> str:
        return self.action.subject


@dataclass(frozen=True)
class ParseException:
    """A subject that no CONTEXT 4.2 row explains. Collected, never dropped."""

    action: CorporateAction
    reason: str


@dataclass(frozen=True)
class ParseReport:
    """Everything :func:`parse_actions` saw, in three buckets that always add up."""

    events: tuple[ParsedEvent, ...] = ()
    informational: tuple[ParsedEvent, ...] = ()
    exceptions: tuple[ParseException, ...] = ()
    ignored_series: tuple[CorporateAction, ...] = ()

    @property
    def total(self) -> int:
        return (
            len(self.events)
            + len(self.informational)
            + len(self.exceptions)
            + len(self.ignored_series)
        )

    def exceptions_in(self, universe: Iterable[str]) -> tuple[ParseException, ...]:
        """The exceptions that land on an F&O-universe symbol -- the ones that matter."""
        wanted = {str(symbol).strip().upper() for symbol in universe}
        return tuple(item for item in self.exceptions if item.action.symbol in wanted)

    def of_kind(self, kind: str) -> tuple[ParsedEvent, ...]:
        return tuple(event for event in self.events if event.kind == kind)

    def summary(self) -> dict[str, int]:
        counts = {kind: len(self.of_kind(kind)) for kind in sorted(ALL_KINDS - {KIND_INFORMATIONAL})}
        counts[KIND_INFORMATIONAL] = len(self.informational)
        counts["exceptions"] = len(self.exceptions)
        counts["ignored_series"] = len(self.ignored_series)
        counts["total"] = self.total
        return counts


@dataclass(frozen=True)
class Factor:
    """A pre-ex price multiplier ``k`` for one symbol's ex-date (CONTEXT 4.2)."""

    symbol: str
    ex_date: date
    kind: str
    k: Decimal
    basis: str
    source: str = SOURCE_NSE

    def __post_init__(self) -> None:
        if not isinstance(self.k, Decimal):
            raise CorporateActionError(
                f"A factor must be a Decimal, got {type(self.k).__name__} -- a float k would "
                "put rounding error into every adjusted price (CONTEXT 7-E11)."
            )
        if self.k <= 0:
            raise CorporateActionError(
                f"{self.symbol} {self.ex_date.isoformat()}: k={self.k} is not positive. "
                "A non-positive multiplier would invert or annihilate a price."
            )


@dataclass(frozen=True)
class PendingFactor:
    """An event whose factor needs a price this module was not given."""

    event: ParsedEvent
    needs: str


@dataclass(frozen=True)
class FactorTable:
    """The factors that could be built, and the events still waiting on an input."""

    factors: tuple[Factor, ...] = ()
    pending: tuple[PendingFactor, ...] = ()
    demergers: tuple[ParsedEvent, ...] = ()

    def for_symbol(self, symbol: str) -> tuple[Factor, ...]:
        wanted = symbol.strip().upper()
        return tuple(f for f in self.factors if f.symbol == wanted)


# --- parsing (PURE) -------------------------------------------------------------------------

#: "Rs 5", "Re 1", "Rs.5", "Rs  2" -- and BSE's own "Rs. - 5.5000", where the dash is a
#: separator in its "<purpose> - Rs. - <amount>" template, never a minus sign (measured on
#: the three frozen BSE windows: without the dash form, every BSE dividend row becomes a
#: parse exception).
_AMOUNT = r"(?:rs|re)\.?\s*-?\s*([0-9]+(?:\.[0-9]+)?)"

_BONUS_RE = re.compile(r"bonus\D{0,20}?([0-9]+)\s*:\s*([0-9]+)", re.I)
_RIGHTS_RE = re.compile(r"rights\D{0,20}?([0-9]+)\s*:\s*([0-9]+)", re.I)
_RIGHTS_PREMIUM_RE = re.compile(r"@\s*(?:at\s+)?premium\s*(?:of\s*)?" + _AMOUNT, re.I)
_RIGHTS_PRICE_RE = re.compile(r"@\s*(?:price\s*)?" + _AMOUNT, re.I)
_SPLIT_FROM_TO_RE = re.compile(r"from\s*" + _AMOUNT + r".*?\bto\s*" + _AMOUNT, re.I | re.S)
_ANY_AMOUNT_RE = re.compile(_AMOUNT, re.I)
_ANY_RATIO_RE = re.compile(r"[0-9]+\s*:\s*[0-9]+")

#: A consolidation (reverse split) is the same event as a split in CONTEXT 4.2's terms -- a
#: face value change from A to B, k = B/A -- only with B > A. It is recognised here ONLY
#: through the same "From Rs X ... To Rs Y" values a split needs, so a bare "Consolidation of
#: Shares" with no values stays an exception rather than becoming a guess.
_SPLIT_KEYWORD_RE = re.compile(
    r"face\s*value\s*split|sub[\s-]*division|stock\s+split|consolidat|split", re.I
)
#: CONTEXT 4.2 / 3.2 call this event "Demerger/spin-off"; NSE also files it as a scheme of
#: arrangement, which is the wording the chunk-3 card names explicitly.
_DEMERGER_RE = re.compile(r"de[\s-]*merger|scheme\s+of\s+arrangement|spin[\s-]*off", re.I)
_BUYBACK_RE = re.compile(r"buy[\s-]*back", re.I)
_DIVIDEND_RE = re.compile(r"dividend", re.I)
_INFORMATIONAL_RE = re.compile(
    r"general\s+meeting|board\s+meeting|postal\s+ballot|court\s+convened|"
    r"annual\s+report|analyst\s+meet|\ba\.?g\.?m\.?\b|\be\.?g\.?m\.?\b",
    re.I,
)
#: Splits a subject into the pieces NSE and BSE glue together with "/" and "plus".
_COMPONENT_SPLIT_RE = re.compile(r"\s*/\s*|\bplus\b", re.I)


def parse_actions(
    actions: Iterable[CorporateAction], *, instrument_series_only: bool = True
) -> ParseReport:
    """Classify raw actions into typed events, informational rows and exceptions. PURE.

    Args:
        actions: rows from any source.
        instrument_series_only: drop rows whose NSE ``series`` is not one of the Q-4
            whitelist series. A corporate action on a listed DEBENTURE (series ``N*``) is not
            an action on the equity we trade, and the interest-payment rows it carries would
            otherwise flood the exception report. Rows with no series (BSE has none) are
            always kept.
    """
    events: list[ParsedEvent] = []
    informational: list[ParsedEvent] = []
    exceptions: list[ParseException] = []
    ignored: list[CorporateAction] = []

    for action in actions:
        if (
            instrument_series_only
            and action.series is not None
            and action.series.strip().upper() not in INSTRUMENT_SERIES
        ):
            ignored.append(action)
            continue
        try:
            event = parse_action(action)
        except CorporateActionError as exc:
            exceptions.append(ParseException(action=action, reason=str(exc)))
            continue
        if event.kind == KIND_INFORMATIONAL:
            informational.append(event)
        else:
            events.append(event)

    return ParseReport(
        events=tuple(events),
        informational=tuple(informational),
        exceptions=tuple(exceptions),
        ignored_series=tuple(ignored),
    )


def parse_action(action: CorporateAction) -> ParsedEvent:
    """Turn one raw action into a typed event. PURE.

    Precedence, and why: a **demerger** keyword wins over everything, because it is the one
    outcome that suppresses trading entirely (CONTEXT 3.2) and a missed one is the most
    expensive mistake this parser can make. Then the ratio events (bonus, split, rights),
    then buyback, then cash dividends, then a recognized meeting notice.

    Raises:
        CorporateActionError: nothing in CONTEXT 4.2's table explains this subject. The
            caller collects it -- see :func:`parse_actions`.
    """
    subject = (action.subject or "").strip()
    if not subject:
        raise CorporateActionError("empty subject")
    text = subject.replace("/-", " ")

    if _DEMERGER_RE.search(text):
        return ParsedEvent(action=action, kind=KIND_DEMERGER)

    bonus = _BONUS_RE.search(text)
    if bonus:
        new, held = int(bonus.group(1)), int(bonus.group(2))
        if new <= 0 or held <= 0:
            raise CorporateActionError(f"bonus ratio {new}:{held} has a non-positive side")
        return ParsedEvent(action=action, kind=KIND_BONUS, ratio_new=new, ratio_held=held)

    if _SPLIT_KEYWORD_RE.search(text):
        pair = _SPLIT_FROM_TO_RE.search(text)
        if not pair:
            raise CorporateActionError(
                "split subject carries no 'From Rs X ... To Rs Y' face values"
            )
        face_from = _paise(pair.group(1), "split face value (from)")
        face_to = _paise(pair.group(2), "split face value (to)")
        if face_from <= 0 or face_to <= 0:
            raise CorporateActionError("split face value is not positive")
        return ParsedEvent(
            action=action,
            kind=KIND_SPLIT,
            face_from_paise=face_from,
            face_to_paise=face_to,
        )

    rights = _RIGHTS_RE.search(text)
    if rights:
        new, held = int(rights.group(1)), int(rights.group(2))
        if new <= 0 or held <= 0:
            raise CorporateActionError(f"rights ratio {new}:{held} has a non-positive side")
        premium = _RIGHTS_PREMIUM_RE.search(text)
        price = None if premium else _RIGHTS_PRICE_RE.search(text)
        return ParsedEvent(
            action=action,
            kind=KIND_RIGHTS,
            ratio_new=new,
            ratio_held=held,
            rights_premium_paise=(
                _paise(premium.group(1), "rights premium") if premium else None
            ),
            rights_price_paise=(_paise(price.group(1), "rights price") if price else None),
        )

    if _BUYBACK_RE.search(text):
        return ParsedEvent(action=action, kind=KIND_BUYBACK)

    if _DIVIDEND_RE.search(text):
        total, components = _dividend_paise(text)
        return ParsedEvent(
            action=action, kind=KIND_DIVIDEND, dividend_paise=total, components=components
        )

    if _INFORMATIONAL_RE.search(text):
        if _ANY_AMOUNT_RE.search(text) or _ANY_RATIO_RE.search(text):
            raise CorporateActionError(
                "looks like a meeting notice but declares an amount or a ratio, so it may "
                "carry a price event this parser does not recognise"
            )
        return ParsedEvent(action=action, kind=KIND_INFORMATIONAL)

    raise CorporateActionError("no CONTEXT 4.2 event kind matches this subject")


def _dividend_paise(text: str) -> tuple[int, tuple[str, ...]]:
    """Total declared cash per share, plus the components it was summed from.

    A subject can declare several cash components on ONE ex-date ("Final Dividend Rs 6 Plus
    Special Dividend Rs 4 Per Share", "Annual General Meeting/Dividend - Rs 1.50 Per Share/
    Special Dividend - Re 1 Per Share"). CONTEXT 4.2 classifies by SIZE against a reference
    price, not by the word "special", so what the size test needs is the total cash leaving
    the company per share on that date.
    """
    components = [part.strip() for part in _COMPONENT_SPLIT_RE.split(text) if part.strip()]
    total = 0
    matched: list[str] = []
    for component in components:
        if not _DIVIDEND_RE.search(component):
            continue
        amount = _ANY_AMOUNT_RE.search(component)
        if not amount:
            raise CorporateActionError(
                f"dividend component {component!r} declares no amount, so its size cannot be "
                "tested against CONTEXT 4.2's 2% threshold"
            )
        total += _paise(amount.group(1), "dividend")
        matched.append(component)
    if not matched:
        raise CorporateActionError("subject mentions a dividend but no component carries one")
    return total, tuple(matched)


def _paise(text: str, what: str) -> int:
    """Rupees as printed -> integer paise, EXACTLY (CONTEXT 7-E11)."""
    try:
        scaled = Decimal(text) * 100
    except InvalidOperation as exc:
        raise CorporateActionError(f"{what} {text!r} is not a number") from exc
    if scaled != scaled.to_integral_value():
        raise CorporateActionError(
            f"{what} {text!r} is not a whole number of paise; refusing to round a price"
        )
    return int(scaled)


# --- factors (PURE) -------------------------------------------------------------------------


def factor_for(
    event: ParsedEvent,
    *,
    cum_close_paise: int | None = None,
    pre_announcement_close_paise: int | None = None,
    rights_issue_price_paise: int | None = None,
) -> Factor:
    """The pre-ex multiplier ``k`` for one typed event, per CONTEXT 4.2's table. PURE.

    Args:
        event: a typed event from :func:`parse_action`.
        cum_close_paise: the close on the last cum date -- ``P`` for rights, ``P_cum`` for a
            special dividend.
        pre_announcement_close_paise: the close before the announcement, which is what
            CONTEXT 4.2 tests the 2% dividend threshold against (a DIFFERENT reference price
            from ``P_cum``, deliberately, per NSE's own rule).
        rights_issue_price_paise: ``S``, the price the rights are offered at.

    Raises:
        CorporateActionError: for a demerger (no factor exists -- CONTEXT 4.2), or when a
            required price was not supplied. Never returns ``k = 1`` for a missing input:
            that is indistinguishable from "this event needs no adjustment".
    """
    if event.kind == KIND_DEMERGER:
        raise CorporateActionError(
            f"{event.symbol} {event.ex_date.isoformat()}: a demerger has NO valid factor "
            "(CONTEXT 4.2 -- NSE terminated the RIL contracts rather than adjust). Use the "
            "demerger table and suppress the bias pair and trading across the ex-date "
            "(CONTEXT 3.2)."
        )

    if event.kind == KIND_BONUS:
        new, held = _require_ratio(event)
        k = Decimal(held) / Decimal(new + held)
        return _factor(event, k, f"bonus {new}:{held} -> k = B/(A+B) = {held}/{new + held}")

    if event.kind == KIND_SPLIT:
        if event.face_from_paise is None or event.face_to_paise is None:
            raise CorporateActionError(f"{event.symbol}: split event carries no face values")
        k = Decimal(event.face_to_paise) / Decimal(event.face_from_paise)
        return _factor(
            event,
            k,
            f"face value {event.face_from_paise / 100:g} -> {event.face_to_paise / 100:g}, "
            "k = B/A",
        )

    if event.kind == KIND_RIGHTS:
        new, held = _require_ratio(event)
        price = rights_issue_price_paise
        if price is None:
            price = event.rights_price_paise
        if price is None:
            raise CorporateActionError(
                f"{event.symbol} {event.ex_date.isoformat()}: the rights ISSUE PRICE (S) is "
                "unknown. NSE's subject states a PREMIUM over face value, not S, and the "
                "row's faceVal is the face value as of the query rather than as of the event "
                "(QUESTIONS.md Q-6). Pass rights_issue_price_paise explicitly."
            )
        if cum_close_paise is None:
            raise CorporateActionError(
                f"{event.symbol} {event.ex_date.isoformat()}: the cum-date close (P) is "
                "needed for a rights factor. Pass cum_close_paise."
            )
        k = rights_factor(
            cum_close_paise=cum_close_paise,
            issue_price_paise=price,
            ratio_new=new,
            ratio_held=held,
        )
        return _factor(
            event,
            k,
            f"rights {new}:{held} at S={price / 100:g} on P={cum_close_paise / 100:g}, "
            "k = (P-E)/P",
        )

    if event.kind == KIND_DIVIDEND:
        if event.dividend_paise is None:
            raise CorporateActionError(f"{event.symbol}: dividend event carries no amount")
        if pre_announcement_close_paise is None:
            raise CorporateActionError(
                f"{event.symbol} {event.ex_date.isoformat()}: CONTEXT 4.2 tests the 2% "
                "threshold against the PRE-ANNOUNCEMENT close, and this source publishes no "
                "announcement date (QUESTIONS.md Q-7). Pass pre_announcement_close_paise."
            )
        if pre_announcement_close_paise <= 0:
            raise CorporateActionError("pre-announcement close must be positive")
        ratio = Decimal(event.dividend_paise) / Decimal(pre_announcement_close_paise)
        if ratio < SPECIAL_DIVIDEND_THRESHOLD:
            return _factor(
                event,
                Decimal(1),
                f"ordinary dividend {event.dividend_paise / 100:g} = {ratio:.4%} of the "
                "pre-announcement close (< 2%), k = 1",
            )
        if cum_close_paise is None:
            raise CorporateActionError(
                f"{event.symbol} {event.ex_date.isoformat()}: this dividend is {ratio:.4%} of "
                "the pre-announcement close, so it is SPECIAL and k = 1 - D/P_cum needs the "
                "cum-date close. Pass cum_close_paise."
            )
        if cum_close_paise <= 0:
            raise CorporateActionError("cum close must be positive")
        k = Decimal(1) - Decimal(event.dividend_paise) / Decimal(cum_close_paise)
        return _factor(
            event,
            k,
            f"special dividend {event.dividend_paise / 100:g} = {ratio:.4%} of the "
            f"pre-announcement close (>= 2%), k = 1 - D/P_cum",
        )

    if event.kind == KIND_BUYBACK:
        return _factor(event, Decimal(1), "buyback -> no adjustment (CONTEXT 4.2)")

    raise CorporateActionError(
        f"{event.kind!r} is not a CONTEXT 4.2 factor kind (informational rows carry none)"
    )


def rights_factor(
    *, cum_close_paise: int, issue_price_paise: int, ratio_new: int, ratio_held: int
) -> Decimal:
    """NSE's own rights formula, spelled out (CONTEXT 4.2). PURE.

    ``C = (P - S) * A`` (benefit per right entitlement), ``E = C / (A + B)`` (benefit per
    share), ``k = (P - E) / P`` -- which is TERP/P. A is the entitlement (new shares), B the
    existing holding.
    """
    if ratio_new <= 0 or ratio_held <= 0:
        raise CorporateActionError(f"rights ratio {ratio_new}:{ratio_held} is not positive")
    if cum_close_paise <= 0:
        raise CorporateActionError("the cum-date close must be positive")
    price = Decimal(cum_close_paise)
    benefit = (price - Decimal(issue_price_paise)) * Decimal(ratio_new)
    per_share = benefit / Decimal(ratio_new + ratio_held)
    k = (price - per_share) / price
    if k <= 0:
        raise CorporateActionError(
            f"rights {ratio_new}:{ratio_held} at S={issue_price_paise / 100:g} on "
            f"P={cum_close_paise / 100:g} gives k={k}, which cannot be a price multiplier."
        )
    return k


def _require_ratio(event: ParsedEvent) -> tuple[int, int]:
    if event.ratio_new is None or event.ratio_held is None:
        raise CorporateActionError(f"{event.symbol}: {event.kind} event carries no ratio")
    return event.ratio_new, event.ratio_held


def _factor(event: ParsedEvent, k: Decimal, basis: str) -> Factor:
    return Factor(
        symbol=event.symbol,
        ex_date=event.ex_date,
        kind=event.kind,
        k=k,
        basis=basis,
        source=event.source,
    )


PriceLookup = Callable[[str, date], int | None]


def build_factor_table(
    events: Iterable[ParsedEvent],
    *,
    cum_close: PriceLookup | None = None,
    pre_announcement_close: PriceLookup | None = None,
    rights_issue_price: PriceLookup | None = None,
) -> FactorTable:
    """Build every factor that CAN be built; collect the rest as pending, with the reason.

    The lookups are injected so this stays pure and so a missing price is visible in the
    output rather than absorbed into a plausible-looking ``k``.
    """
    factors: list[Factor] = []
    pending: list[PendingFactor] = []
    demergers: list[ParsedEvent] = []

    for event in events:
        if event.kind == KIND_DEMERGER:
            demergers.append(event)
            continue
        if event.kind == KIND_INFORMATIONAL:
            continue
        try:
            factors.append(
                factor_for(
                    event,
                    cum_close_paise=_lookup(cum_close, event),
                    pre_announcement_close_paise=_lookup(pre_announcement_close, event),
                    rights_issue_price_paise=_lookup(rights_issue_price, event),
                )
            )
        except CorporateActionError as exc:
            pending.append(PendingFactor(event=event, needs=str(exc)))

    factors.sort(key=lambda f: (f.symbol, f.ex_date, f.kind))
    return FactorTable(
        factors=tuple(factors), pending=tuple(pending), demergers=tuple(demergers)
    )


def _lookup(lookup: PriceLookup | None, event: ParsedEvent) -> int | None:
    return None if lookup is None else lookup(event.symbol, event.ex_date)


def demerger_table(events: Iterable[ParsedEvent]) -> tuple[ParsedEvent, ...]:
    """The demerger/spin-off events, oldest first (CONTEXT 3.2's blocking list)."""
    return tuple(
        sorted(
            (event for event in events if event.kind == KIND_DEMERGER),
            key=lambda event: (event.ex_date, event.symbol),
        )
    )


def factors_between(
    factors: Iterable[Factor], previous_day: date, current_day: date, *, symbol: str | None = None
) -> tuple[Factor, ...]:
    """The factors CONTEXT 3.2 applies to candle P of the pair (P, C). PURE.

    "P's prices are multiplied by the factors of events with ex-date AFTER P and ON OR BEFORE
    C" -- so the window is ``(previous_day, current_day]``, half-open at the left.
    """
    if current_day < previous_day:
        raise CorporateActionError(
            f"Empty pair window: {current_day.isoformat()} is before {previous_day.isoformat()}."
        )
    wanted = None if symbol is None else symbol.strip().upper()
    return tuple(
        sorted(
            (
                factor
                for factor in factors
                if previous_day < factor.ex_date <= current_day
                and (wanted is None or factor.symbol == wanted)
            ),
            key=lambda factor: (factor.ex_date, factor.kind),
        )
    )


def adjust_pair(price_paise: int, events_between: Sequence[Factor]) -> int:
    """Bring one of candle P's prices into candle C's scale (CONTEXT 3.2 / 4.2). PURE.

    Multiplies the chained factors at full :class:`~decimal.Decimal` precision and rounds
    ONCE, half-even, back to integer paise (CONTEXT 7-E11). Rounding once rather than per
    event is what keeps a chain of two events from drifting by a paisa; half-even is the
    unbiased rule, so a long history of adjustments does not creep upward.

    Args:
        price_paise: a RAW price from candle P, in integer paise.
        events_between: the factors from :func:`factors_between`. An empty sequence returns
            the price unchanged -- exactly, with no rounding applied at all.
    """
    if isinstance(price_paise, bool) or not isinstance(price_paise, int):
        raise CorporateActionError(
            f"Prices are integer paise (CONTEXT 7-E11); got {type(price_paise).__name__}."
        )
    if not events_between:
        return price_paise
    scaled = Decimal(price_paise)
    for factor in events_between:
        if not isinstance(factor, Factor):
            raise CorporateActionError(
                f"adjust_pair takes Factor objects, got {type(factor).__name__}."
            )
        scaled *= factor.k
    return int(scaled.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


# --- source parsing (PURE) ------------------------------------------------------------------


def parse_nse_payload(payload: Any) -> tuple[CorporateAction, ...]:
    """NSE ``corporates-corporateActions`` JSON -> raw actions. PURE."""
    if not isinstance(payload, list):
        raise CorporateActionError(
            f"NSE corporate-actions payload must be a JSON array, got "
            f"{type(payload).__name__}."
        )
    actions: list[CorporateAction] = []
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise CorporateActionError(f"row {index} is {type(row).__name__}, expected an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise CorporateActionError(f"row {index} has no symbol")
        actions.append(
            CorporateAction(
                symbol=symbol,
                ex_date=_nse_date(row.get("exDate"), index),
                subject=str(row.get("subject") or "").strip(),
                source=SOURCE_NSE,
                series=_text_or_none(row.get("series")),
                isin=_text_or_none(row.get("isin")),
                company=_text_or_none(row.get("comp")),
                record_date=_optional_nse_date(row.get("recDate")),
                face_value_paise=_optional_face_value(row.get("faceVal")),
            )
        )
    return tuple(actions)


def parse_bse_csv(text: str) -> tuple[CorporateAction, ...]:
    """BSE ``CorpactCSVDownload`` CSV -> raw actions. PURE.

    BSE publishes no ISIN (CONTEXT 4.2), so the symbol carried here is BSE's own security
    NAME. The cross-source join uses it as a name join and reports a miss as "not found",
    never as a disagreement.
    """
    reader = csv.DictReader(io.StringIO(text))
    header = [name.strip() for name in (reader.fieldnames or [])]
    for required in ("Security Name", "Ex Date", "Purpose"):
        if required not in header:
            raise CorporateActionError(
                f"BSE CSV is missing column {required!r}; columns present: "
                f"{', '.join(header) or '<none>'}"
            )
    actions: list[CorporateAction] = []
    for index, raw in enumerate(reader, start=2):
        row = {str(k).strip(): v for k, v in raw.items() if k is not None and str(k).strip()}
        symbol = str(row.get("Security Name") or "").strip().upper()
        ex_text = str(row.get("Ex Date") or "").strip()
        if not symbol or not ex_text or ex_text == "-":
            continue  # BSE pads its export with rows that carry no ex-date
        actions.append(
            CorporateAction(
                symbol=symbol,
                ex_date=parse_bse_date(ex_text, index),
                subject=str(row.get("Purpose") or "").strip(),
                source=SOURCE_BSE,
                company=_text_or_none(row.get("Company Name")),
                record_date=_optional_bse_date(row.get("Record Date"), index),
                security_code=_text_or_none(row.get("Security Code")),
            )
        )
    return tuple(actions)


def parse_bse_date(text: str, line: int) -> date:
    """BSE stamps ``05 Jan 2016``. Parsed with the same locale-independent month map."""
    parts = str(text).strip().split()
    if len(parts) != 3:
        raise CorporateActionError(f"line {line}: {text!r} is not a BSE date (DD Mon YYYY)")
    return parse_nse_date("-".join(parts))


def parse_yahoo_chart(payload: Any, symbol: str) -> tuple[SplitRatio, ...]:
    """Yahoo chart JSON -> split events for one ticker, oldest first. PURE.

    Yahoo stamps each event with the exchange's session-open epoch, so the IST date is what
    NSE would call the ex-date. A BONUS reaches Yahoo as a combined split ratio (a 1:2 bonus
    is a 3:2 split), which is exactly why CONTEXT 4.2 uses it as a tiebreak and not as a
    source of truth.
    """
    if not isinstance(payload, Mapping):
        raise CorporateActionError(
            f"Yahoo payload must be a JSON object, got {type(payload).__name__}."
        )
    chart = payload.get("chart")
    if not isinstance(chart, Mapping):
        raise CorporateActionError("Yahoo payload has no 'chart' object")
    if chart.get("error"):
        raise CorporateActionError(f"Yahoo returned an error: {chart['error']!r}")
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise CorporateActionError("Yahoo payload carries no result")
    events = results[0].get("events") if isinstance(results[0], Mapping) else None
    splits = (events or {}).get("splits") if isinstance(events, Mapping) else None
    if not splits:
        return ()

    parsed: list[SplitRatio] = []
    for key, split in sorted(splits.items()):
        numerator = _decimal(split.get("numerator"), f"Yahoo split {key} numerator")
        denominator = _decimal(split.get("denominator"), f"Yahoo split {key} denominator")
        if numerator <= 0 or denominator <= 0:
            raise CorporateActionError(f"Yahoo split {key} has a non-positive side")
        parsed.append(
            SplitRatio(
                symbol=symbol.strip().upper(),
                ex_date=ist_date_from_epoch(int(split.get("date", key))),
                numerator=numerator,
                denominator=denominator,
                ratio_text=str(split.get("splitRatio") or f"{numerator}:{denominator}"),
            )
        )
    parsed.sort(key=lambda item: item.ex_date)
    return tuple(parsed)


def ist_date_from_epoch(seconds: int) -> date:
    """Yahoo's UTC epoch stamp -> the naive IST calendar date (CONTEXT 7-E8). PURE."""
    return (datetime.fromtimestamp(int(seconds), tz=timezone.utc).replace(tzinfo=None)
            + _IST_OFFSET).date()


def epoch_from_date(day: date) -> int:
    """A calendar date -> the UTC epoch second Yahoo's window parameters expect. PURE."""
    return _calendar.timegm(day.timetuple())


def _decimal(value: Any, what: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise CorporateActionError(f"{what} is not a number: {value!r}") from exc


def _text_or_none(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or value.strip() == "-":
        return None
    return value.strip()


def _nse_date(value: Any, index: int) -> date:
    text = _text_or_none(value)
    if text is None:
        raise CorporateActionError(f"row {index} has no ex-date")
    try:
        return parse_nse_date(text)
    except Exception as exc:
        raise CorporateActionError(f"row {index}: {text!r} is not an NSE date") from exc


def _optional_nse_date(value: Any) -> date | None:
    text = _text_or_none(value)
    if text is None:
        return None
    try:
        return parse_nse_date(text)
    except Exception:
        return None


def _optional_bse_date(value: Any, line: int) -> date | None:
    text = _text_or_none(value)
    if text is None:
        return None
    try:
        return parse_bse_date(text, line)
    except CorporateActionError:
        return None


def _optional_face_value(value: Any) -> int | None:
    text = _text_or_none(value)
    if text is None:
        return None
    try:
        return _paise(text, "face value")
    except CorporateActionError:
        return None


# --- cross-source join ----------------------------------------------------------------------


@dataclass(frozen=True)
class SourceComparison:
    """One NSE event, and what the other two sources say about the same symbol-date."""

    symbol: str
    ex_date: date
    kind: str
    nse_subject: str
    bse_purpose: str | None
    bse_kind: str | None
    yahoo_ratio: str | None
    nse_k: Decimal | None
    bse_k: Decimal | None
    yahoo_k: Decimal | None
    verdict: str
    note: str


AGREE: str = "agree"
DISAGREE: str = "disagree"
NOT_FOUND: str = "not-found"
NO_FACTOR: str = "no-factor"


def cross_source_report(
    nse_events: Iterable[ParsedEvent],
    bse_events: Iterable[ParsedEvent],
    yahoo_splits: Iterable[SplitRatio],
) -> tuple[SourceComparison, ...]:
    """Compare the three sources on every NSE event of a priced kind (CONTEXT 4.2).

    The comparison is on the ex-date AND on the implied factor where both sources supply one,
    which is the only part that changes a price. A BSE row that cannot be found under the
    same name is ``not-found`` (BSE has no ISIN to join on -- CONTEXT 4.2), never a
    disagreement; Yahoo is only expected to carry bonuses and splits.
    """
    bse_index: dict[tuple[str, date], list[ParsedEvent]] = {}
    for event in bse_events:
        bse_index.setdefault((event.symbol, event.ex_date), []).append(event)
    yahoo_index: dict[tuple[str, date], SplitRatio] = {}
    for split in yahoo_splits:
        yahoo_index.setdefault((split.symbol, split.ex_date), split)

    rows: list[SourceComparison] = []
    for event in sorted(nse_events, key=lambda e: (e.ex_date, e.symbol)):
        key = (event.symbol, event.ex_date)
        # One symbol-date can carry SEVERAL actions -- ROTO declared a bonus AND a dividend
        # on 2023-07-07, MAANALU a bonus AND a split on 2023-07-27 -- so the join matches on
        # the KIND too. Matching on the symbol-date alone reported both as disagreements
        # when in fact all three sources agreed about every event on those days.
        candidates = bse_index.get(key, [])
        bse = next((row for row in candidates if row.kind == event.kind), None)
        yahoo = yahoo_index.get(key)
        nse_k = _ratio_only_factor(event)
        bse_k = _ratio_only_factor(bse) if bse is not None else None
        yahoo_k = yahoo.k if yahoo is not None else None

        notes: list[str] = []
        verdict = AGREE
        if bse is None and not candidates:
            notes.append("no BSE row under this security name")
            verdict = NOT_FOUND
        elif bse is None:
            notes.append(
                "BSE lists "
                + ", ".join(sorted({row.kind for row in candidates}))
                + f" on this date but no {event.kind}"
            )
            verdict = DISAGREE
        else:
            if nse_k is not None and bse_k is not None and nse_k != bse_k:
                notes.append(f"k differs: nse={nse_k} bse={bse_k}")
                verdict = DISAGREE
        if yahoo is None:
            notes.append(
                "not in Yahoo's split stream"
                + (" (expected: it carries no rights/dividends/demergers)"
                   if event.kind not in (KIND_BONUS, KIND_SPLIT) else "")
            )
        elif nse_k is not None and yahoo_k is not None and nse_k != yahoo_k:
            notes.append(f"k differs: nse={nse_k} yahoo={yahoo_k}")
            verdict = DISAGREE
        if nse_k is None and verdict == AGREE:
            verdict = NO_FACTOR if event.kind != KIND_BUYBACK else AGREE

        rows.append(
            SourceComparison(
                symbol=event.symbol,
                ex_date=event.ex_date,
                kind=event.kind,
                nse_subject=event.subject,
                bse_purpose=bse.subject if bse is not None else None,
                bse_kind=bse.kind if bse is not None else None,
                yahoo_ratio=yahoo.ratio_text if yahoo is not None else None,
                nse_k=nse_k,
                bse_k=bse_k,
                yahoo_k=yahoo_k,
                verdict=verdict,
                note="; ".join(notes) or "all sources agree",
            )
        )
    return tuple(rows)


def _ratio_only_factor(event: ParsedEvent | None) -> Decimal | None:
    """The factor an event implies WITHOUT any price input (bonus and split only)."""
    if event is None or event.kind not in (KIND_BONUS, KIND_SPLIT):
        return None
    try:
        return factor_for(event).k
    except CorporateActionError:
        return None


# --- fetching (I/O; opt-in, day-cached) -------------------------------------------------------


def new_bse_session() -> requests.Session:
    """A session with the headers BSE's API expects (its own Referer and Origin)."""
    session = nse_http.new_session()
    session.headers.update(
        {"Referer": BSE_HOME_URL, "Origin": BSE_HOME_URL.rstrip("/"), "Accept": "*/*"}
    )
    return session


def new_yahoo_session() -> requests.Session:
    session = nse_http.new_session()
    session.headers.update({"Referer": "https://finance.yahoo.com/", "Accept": "application/json"})
    session.headers.pop("Origin", None)
    return session


def nse_url(start: date, end: date) -> str:
    return NSE_CA_URL_TEMPLATE.format(
        from_date=start.strftime("%d-%m-%Y"), to_date=end.strftime("%d-%m-%Y")
    )


def bse_url(start: date, end: date) -> str:
    return BSE_CA_URL_TEMPLATE.format(
        from_date=start.strftime("%Y%m%d"), to_date=end.strftime("%Y%m%d")
    )


def yahoo_url(symbol: str, start: date, end: date) -> str:
    return YAHOO_CHART_URL_TEMPLATE.format(
        ticker=f"{symbol.strip().upper()}{YAHOO_NSE_SUFFIX}",
        period1=epoch_from_date(start),
        period2=epoch_from_date(end),
    )


def cache_path(cache_dir: Path, name: str) -> Path:
    """Where a day-cached CA payload lives. ``data/`` is gitignored (CLAUDE.md git rules)."""
    return Path(cache_dir) / "ca" / name


def default_cache_dir() -> Path:
    from .config import load_config  # local: parsing must not require a config file

    return load_config(include_env=False).path("data_dir") / "nse"


def fetch_nse_corporate_actions(
    start: date,
    end: date,
    *,
    allow_network: bool = False,
    cache_dir: Path | None = None,
    today: date | None = None,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
    min_interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
) -> tuple[CorporateAction, ...]:
    """NSE corporate actions over ``[start, end]``, pulled at most once per calendar day."""
    payload = _cached(
        url=nse_url(start, end),
        name=f"nse_ca_{start.isoformat()}_{end.isoformat()}.json",
        cache_dir=cache_dir,
        today=today,
        allow_network=allow_network,
        fetch=lambda url: nse_http.fetch_json(
            url,
            session=session,
            min_interval=min_interval,
            **({} if sleep is None else {"sleep": sleep}),
        ),
    )
    return parse_nse_payload(payload)


def fetch_bse_corporate_actions(
    start: date,
    end: date,
    *,
    allow_network: bool = False,
    cache_dir: Path | None = None,
    today: date | None = None,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
    min_interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
) -> tuple[CorporateAction, ...]:
    """BSE corporate actions over ``[start, end]`` -- the second source (CONTEXT 4.2)."""
    text = _cached(
        url=bse_url(start, end),
        name=f"bse_ca_{start.isoformat()}_{end.isoformat()}.json",
        cache_dir=cache_dir,
        today=today,
        allow_network=allow_network,
        fetch=lambda url: nse_http.fetch_binary(
            url,
            session=session if session is not None else new_bse_session(),
            min_interval=min_interval,
            **({} if sleep is None else {"sleep": sleep}),
        ).decode("utf-8"),
    )
    return parse_bse_csv(text)


def fetch_yahoo_splits(
    symbol: str,
    start: date,
    end: date,
    *,
    allow_network: bool = False,
    cache_dir: Path | None = None,
    today: date | None = None,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
    min_interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
) -> tuple[SplitRatio, ...]:
    """Yahoo's split stream for one NSE symbol -- the third vote, a TIEBREAK only."""
    payload = _cached(
        url=yahoo_url(symbol, start, end),
        name=f"yahoo_splits_{symbol.strip().upper()}_{start.isoformat()}_{end.isoformat()}.json",
        cache_dir=cache_dir,
        today=today,
        allow_network=allow_network,
        fetch=lambda url: nse_http.fetch_json(
            url,
            session=session if session is not None else new_yahoo_session(),
            min_interval=min_interval,
            **({} if sleep is None else {"sleep": sleep}),
        ),
    )
    return parse_yahoo_chart(payload, symbol)


def _cached(
    *,
    url: str,
    name: str,
    cache_dir: Path | None,
    today: date | None,
    allow_network: bool,
    fetch: Callable[[str], Any],
) -> Any:
    base = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    return nse_http.cached_json(
        url,
        cache_path(base, name),
        today=today if today is not None else date.today(),
        allow_network=allow_network,
        fetcher=fetch,
    )


def load_snapshot(path: Path) -> Any:
    """Read a frozen snapshot: JSON payloads decode, everything else comes back as text."""
    source = Path(path)
    if not source.is_file():
        raise CorporateActionError(f"Snapshot not found: {source}")
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        import json

        try:
            return json.loads(text)
        except ValueError as exc:
            raise CorporateActionError(f"Snapshot {source} is not valid JSON: {exc}") from exc
    return text
