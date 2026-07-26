"""Chunk-5B tests for the Q-11 addendum ROUTING rule (:mod:`acumen.adjustment_route`).

REVIEW_5A F1/F2 left chunk 5B two jobs: wire the measured adjustment map into the operator CLI,
and decide WHICH symbols must go through it. The architect's routing ruling (QUESTIONS.md, Q-11
addendum) answers the second: any non-share-count event (rights, special dividend, demerger)
makes a symbol MAP-REQUIRED; bonus/split-only symbols may use the factor-table path; unknown
parses force the map conservatively.

The property that matters for money is the asymmetry: a wrong route towards the map costs
probe requests, a wrong route away from it stores a price no gate can check (F2). So every
test below that expects ``table-path`` is a test that the cheap path stays available, and every
test that expects ``map-required`` is a test that the price oracle cannot be skipped.

All offline and PURE -- these build chunk-3 dataclasses directly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from acumen.adjustment_route import (
    ROUTE_MAP_REQUIRED,
    ROUTE_TABLE_PATH,
    classify_route,
    map_covers_route,
)
from acumen.corp_actions import (
    KIND_BONUS,
    KIND_DEMERGER,
    KIND_DIVIDEND,
    KIND_RIGHTS,
    KIND_SPLIT,
    CorporateAction,
    Factor,
    ParseException,
    ParsedEvent,
    PendingFactor,
    Suppression,
)

SYM = "ACME"


def _factor(kind: str, ex: date, k: str, *, symbol: str = SYM) -> Factor:
    return Factor(symbol=symbol, ex_date=ex, kind=kind, k=Decimal(k), basis=f"{kind} {k}")


def _action(ex: date, subject: str, *, symbol: str = SYM) -> CorporateAction:
    return CorporateAction(symbol=symbol, ex_date=ex, subject=subject, source="nse")


def _event(kind: str, ex: date, *, symbol: str = SYM) -> ParsedEvent:
    return ParsedEvent(action=_action(ex, f"{kind} something", symbol=symbol), kind=kind)


# --- the table path stays available ----------------------------------------------------


def test_a_symbol_with_no_corporate_actions_is_table_path() -> None:
    decision = classify_route(SYM)
    assert decision.route == ROUTE_TABLE_PATH
    assert decision.reasons == ()
    assert not decision.map_required


def test_bonus_and_split_only_is_table_path() -> None:
    """The ruling's own words: 'their map would be identical: ours/ours'."""
    decision = classify_route(
        SYM,
        factors=(
            _factor(KIND_BONUS, date(2018, 5, 31), "0.5"),
            _factor(KIND_SPLIT, date(2021, 7, 1), "0.2"),
        ),
    )
    assert decision.route == ROUTE_TABLE_PATH


def test_an_ordinary_dividend_does_not_force_the_map() -> None:
    """k == 1 (CONTEXT 4.2): no price move, no era. Reading these in would make EVERY symbol
    map-required and contradict the ruling's own bonus/split-only clause."""
    decision = classify_route(
        SYM,
        factors=(
            _factor(KIND_DIVIDEND, date(2022, 6, 1), "1"),
            _factor(KIND_BONUS, date(2023, 1, 5), "0.5"),
        ),
    )
    assert decision.route == ROUTE_TABLE_PATH


# --- the map is mandatory ---------------------------------------------------------------


def test_a_special_dividend_forces_the_map() -> None:
    """REVIEW_5A F2 exactly: k_price < 1 with k_shares == 1, so gate-1 volume is blind to it."""
    decision = classify_route(SYM, factors=(_factor(KIND_DIVIDEND, date(2022, 6, 1), "0.98"),))
    assert decision.route == ROUTE_MAP_REQUIRED
    assert "special dividend" in decision.reasons[0]


def test_a_rights_factor_forces_the_map() -> None:
    decision = classify_route(SYM, factors=(_factor(KIND_RIGHTS, date(2020, 5, 13), "0.99061"),))
    assert decision.route == ROUTE_MAP_REQUIRED
    assert KIND_RIGHTS in decision.reasons[0]


def test_a_demerger_suppression_forces_the_map() -> None:
    decision = classify_route(
        SYM,
        suppressions=(
            Suppression(symbol=SYM, ex_date=date(2023, 7, 20), kind=KIND_DEMERGER, reason="Jio"),
        ),
    )
    assert decision.route == ROUTE_MAP_REQUIRED
    assert "demerger" in decision.reasons[0]


def test_a_tier2_rights_suppression_forces_the_map() -> None:
    decision = classify_route(
        SYM,
        suppressions=(
            Suppression(symbol=SYM, ex_date=date(2016, 1, 11), kind=KIND_RIGHTS,
                        reason="issue price unrecoverable (Q-6 tier 2)"),
        ),
    )
    assert decision.route == ROUTE_MAP_REQUIRED


def test_a_pending_factor_forces_the_map_conservatively() -> None:
    decision = classify_route(
        SYM,
        pending=(PendingFactor(event=_event(KIND_DIVIDEND, date(2019, 3, 1)), needs="cum close"),),
    )
    assert decision.route == ROUTE_MAP_REQUIRED
    assert "unresolved" in decision.reasons[0]


def test_an_unparsed_subject_forces_the_map_conservatively() -> None:
    """The ruling's last clause: 'unknown-parse events force MAP-REQUIRED conservatively'."""
    decision = classify_route(
        SYM,
        parse_exceptions=(
            ParseException(action=_action(date(2017, 9, 1), "Some Unheard-Of Scheme"),
                           reason="no CONTEXT 4.2 row explains this subject"),
        ),
    )
    assert decision.route == ROUTE_MAP_REQUIRED
    assert "unparsed subject" in decision.reasons[0]


def test_every_forcing_event_is_named_in_the_reasons() -> None:
    decision = classify_route(
        SYM,
        factors=(
            _factor(KIND_BONUS, date(2017, 9, 7), "0.5"),
            _factor(KIND_RIGHTS, date(2020, 5, 13), "0.99061"),
            _factor(KIND_BONUS, date(2024, 10, 28), "0.5"),
        ),
        suppressions=(
            Suppression(symbol=SYM, ex_date=date(2023, 7, 20), kind=KIND_DEMERGER, reason="Jio"),
        ),
    )
    assert decision.route == ROUTE_MAP_REQUIRED
    assert len(decision.reasons) == 2, "the two bonuses are share-count and do not force it"
    assert any("2020-05-13" in r for r in decision.reasons)
    assert any("2023-07-20" in r for r in decision.reasons)


# --- scoping and the refusal ------------------------------------------------------------


def test_another_symbols_events_are_ignored() -> None:
    decision = classify_route(
        SYM,
        factors=(_factor(KIND_RIGHTS, date(2020, 5, 13), "0.99", symbol="OTHER"),),
        suppressions=(
            Suppression(symbol="OTHER", ex_date=date(2023, 7, 20), kind=KIND_DEMERGER, reason="x"),
        ),
    )
    assert decision.route == ROUTE_TABLE_PATH


def test_an_event_older_than_the_minute_clamp_does_not_force_the_map() -> None:
    """An ex-date before every minute bar we will ever store can appear in no (D, F] window."""
    clamp = date(2016, 10, 1)
    events = (_factor(KIND_RIGHTS, date(2011, 4, 1), "0.9"),)
    assert classify_route(SYM, factors=events).route == ROUTE_MAP_REQUIRED
    assert classify_route(SYM, factors=events, since=clamp).route == ROUTE_TABLE_PATH


def test_map_required_without_a_map_is_refused_with_the_command_to_fix_it() -> None:
    decision = classify_route(SYM, factors=(_factor(KIND_RIGHTS, date(2020, 5, 13), "0.99"),))
    allowed, why_not = map_covers_route(decision, adjustment_map_present=False)
    assert not allowed
    assert "acumen-build-adjustment-map" in why_not
    assert SYM in why_not


def test_map_required_with_a_map_is_allowed() -> None:
    decision = classify_route(SYM, factors=(_factor(KIND_RIGHTS, date(2020, 5, 13), "0.99"),))
    allowed, why_not = map_covers_route(decision, adjustment_map_present=True)
    assert allowed and why_not == ""


def test_table_path_never_needs_a_map() -> None:
    decision = classify_route(SYM, factors=(_factor(KIND_BONUS, date(2018, 5, 31), "0.5"),))
    assert map_covers_route(decision, adjustment_map_present=False) == (True, "")
