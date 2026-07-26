"""Which un-adjustment path a symbol's 1-minute ingest must take (the Q-11 routing rule). PURE.

Chunk 5A left two ways to recover RAW same-day 1-minute prices from the vendor's
back-adjusted feed, and no rule for choosing between them:

* the **factor-table path** (QUESTIONS.md Q-10, :mod:`acumen.minute_unadjust`) -- divide by the
  product of OUR CONTEXT 4.2 factors in ``(D, F]``. Exact when every event in the window is a
  clean share-count change whose factor we know, and volume (gate 1) is then a genuine per-day
  proof of the price division, because a bonus/split scales price and volume by the SAME factor.
* the **map path** (QUESTIONS.md Q-11, :mod:`acumen.vendor_adjustment`) -- per-event MEASURED
  reconstruction, arbitrated by per-day PRICE containment against the raw daily store as well as
  gate-1 volume.

REVIEW_5A F2 measured the hole between them: for a **non-share-count** event the factor-table
path scales the price but not the volume (a special dividend has ``k_price < 1`` and
``k_shares == 1``), so if the vendor did not apply that price adjustment to its minute feed the
store keeps a ~2%-wrong price and gate-1 volume still PASSES. The fallback has no price oracle.
The architect's routing rule closes it (recorded verbatim in QUESTIONS.md, Q-11 addendum):

    "ARCHITECT'S RULING (routing): a symbol whose CA history contains ANY non-share-count event
    (rights, special dividend, demerger) is MAP-REQUIRED -- its eras must be probed and its
    ingest must run through the adjustment map's per-day price containment. Bonus/split-only
    symbols may use the factor-table path (their map would be identical: ours/ours). The
    classifier runs off the chunk-3 CA table; unknown-parse events force MAP-REQUIRED
    conservatively."

"Non-share-count" is read as the ruling's own enumeration -- rights, special dividend, demerger
-- i.e. the events that MOVE a price without moving the share count. An ordinary dividend and a
buyback carry ``k = 1`` (CONTEXT 4.2), move no price, and fragment no era, so they do not force
the map; reading them in would make every symbol map-required and contradict the ruling's own
"bonus/split-only symbols may use the factor-table path".

Everything here is PURE: it takes an already-built chunk-3 factor table and returns a decision.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from .corp_actions import (
    KIND_DEMERGER,
    KIND_DIVIDEND,
    KIND_RIGHTS,
    SHARE_COUNT_KINDS,
    Factor,
    ParseException,
    PendingFactor,
    Suppression,
)

#: The symbol's minutes may be un-adjusted with our own CONTEXT 4.2 factor table: every
#: price-moving event in its history is a share-count change (bonus / split / consolidation),
#: for which our factor and the vendor's are the same number and gate-1 volume proves the price.
ROUTE_TABLE_PATH: str = "table-path"

#: The symbol MUST go through a measured :class:`acumen.vendor_adjustment.AdjustmentMap`:
#: its history carries at least one non-share-count price-moving event (or something we could
#: not parse), so only the map's per-day price containment can prove the un-adjustment.
ROUTE_MAP_REQUIRED: str = "map-required"

_ONE: Decimal = Decimal(1)


@dataclass(frozen=True)
class RouteDecision:
    """Which path a symbol's ingest takes, and exactly why."""

    symbol: str
    route: str
    reasons: tuple[str, ...] = ()

    @property
    def map_required(self) -> bool:
        return self.route == ROUTE_MAP_REQUIRED

    def describe(self) -> str:
        if not self.reasons:
            return f"{self.symbol}: {self.route}"
        return f"{self.symbol}: {self.route} ({'; '.join(self.reasons)})"


def classify_route(
    symbol: str,
    *,
    factors: Sequence[Factor] = (),
    suppressions: Sequence[Suppression] = (),
    pending: Sequence[PendingFactor] = (),
    parse_exceptions: Iterable[ParseException] = (),
    since: date | None = None,
) -> RouteDecision:
    """Route one symbol per the Q-11 addendum routing rule. PURE.

    Args:
        symbol: the ticker.
        factors: the symbol's built CONTEXT 4.2 factors (chunk 3).
        suppressions: its suppressions -- a demerger, or a Q-6 tier-2 rights whose issue price
            could not be recovered. Both are non-share-count by definition.
        pending: events whose factor could not be built for want of a price. We cannot tell what
            they are, so they force the map (the ruling's conservative clause).
        parse_exceptions: subjects no CONTEXT 4.2 row explains, on THIS symbol. Same reasoning.
        since: ignore events with an ex-date strictly before this. Pass the symbol's minute
            clamp: an event older than every minute bar the ingest will store can never appear
            in any ``(D, F]`` window, so it cannot affect one stored price. ``None`` considers
            the whole history.

    Returns:
        A :class:`RouteDecision` whose ``reasons`` name every event that forced the map, so the
        operator's report can show WHY a symbol is on the expensive path.
    """
    sym = symbol.strip().upper()
    reasons: list[str] = []

    def in_scope(ex_date: date) -> bool:
        return since is None or ex_date >= since

    for factor in factors:
        if factor.symbol != sym or not in_scope(factor.ex_date):
            continue
        if factor.k == _ONE:
            continue  # an ordinary dividend / buyback: no price move, no era, no map needed
        if factor.kind in SHARE_COUNT_KINDS:
            continue  # bonus / split / consolidation: ours == the vendor's, gate 1 proves it
        what = "special dividend" if factor.kind == KIND_DIVIDEND else factor.kind
        reasons.append(f"{what} ex {factor.ex_date.isoformat()} (k={factor.k}, non-share-count)")

    for suppression in suppressions:
        if suppression.symbol != sym or not in_scope(suppression.ex_date):
            continue
        what = "demerger" if suppression.kind == KIND_DEMERGER else f"{suppression.kind} (no factor)"
        reasons.append(f"{what} ex {suppression.ex_date.isoformat()}")

    for item in pending:
        event = item.event
        if event.symbol != sym or not in_scope(event.ex_date):
            continue
        reasons.append(
            f"unresolved {event.kind} ex {event.ex_date.isoformat()} (needs {item.needs}) "
            "-- kind of price move unknown"
        )

    for exception in parse_exceptions:
        action = exception.action
        if action.symbol != sym or not in_scope(action.ex_date):
            continue
        reasons.append(
            f"unparsed subject ex {action.ex_date.isoformat()} ({exception.reason}) "
            "-- conservative per the ruling"
        )

    route = ROUTE_MAP_REQUIRED if reasons else ROUTE_TABLE_PATH
    return RouteDecision(symbol=sym, route=route, reasons=tuple(reasons))


def map_covers_route(
    decision: RouteDecision, adjustment_map_present: bool
) -> tuple[bool, str]:
    """May this symbol be ingested? ``(allowed, why_not)``. PURE.

    The refusal the routing rule requires: a MAP-REQUIRED symbol without a persisted map has no
    price oracle, and the factor-table fallback would store a price gate 1 cannot check. Better
    to refuse than to write a plausible wrong price (CLAUDE.md rule 1).
    """
    if not decision.map_required or adjustment_map_present:
        return True, ""
    return False, (
        f"{decision.symbol} is {ROUTE_MAP_REQUIRED} and no adjustment map is present. "
        f"Reason(s): {'; '.join(decision.reasons)}. The Q-10 factor-table fallback has no PRICE "
        "oracle -- for a non-share-count event it scales price but not volume, so a wrong price "
        "passes gate-1 volume unnoticed (REVIEW_5A F2). Build the map first:\n"
        f"    acumen-build-adjustment-map --symbol {decision.symbol} --allow-network "
        "--window <label>:<START>:<END> [--window ...]\n"
        "(or run the universe backfill, which probes each map-required symbol's eras itself)."
    )
