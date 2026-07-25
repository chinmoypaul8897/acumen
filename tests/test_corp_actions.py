"""The corporate-action engine: parser, factors, adjust_pair (CONTEXT 4.2, 3.2, 7-E11).

Everything here is offline and runs against the frozen snapshots in `tests/fixtures/ca/`,
which are VERBATIM responses of the three sources CONTEXT 4.2 names. The goldens that define
"correct" live in `tests/test_ca_goldens.py`; this module is the unit layer underneath them:
the regexes, the error paths, and the arithmetic.

What is deliberately NOT here: any test that lets a missing price become `k = 1`. CONTEXT 4.2
needs prices this module does not hold, and the whole design turns on those being INPUTS that
raise when absent -- so the error paths are tested as carefully as the happy ones.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import corp_actions as ca
from acumen.corp_actions import (
    KIND_BONUS,
    KIND_BUYBACK,
    KIND_DEMERGER,
    KIND_DIVIDEND,
    KIND_INFORMATIONAL,
    KIND_RIGHTS,
    KIND_SPLIT,
    CorporateAction,
    CorporateActionError,
    Factor,
    ParsedEvent,
    adjust_pair,
    factor_for,
    factors_between,
    parse_action,
    parse_actions,
    parse_bse_csv,
    parse_nse_payload,
    parse_yahoo_chart,
)

CA_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ca"
EX = date(2020, 1, 15)


def action(subject: str, *, symbol: str = "ACME", series: str | None = "EQ") -> CorporateAction:
    return CorporateAction(
        symbol=symbol, ex_date=EX, subject=subject, source=ca.SOURCE_NSE, series=series
    )


def event(kind: str, **fields: object) -> ParsedEvent:
    return ParsedEvent(action=action("synthetic"), kind=kind, **fields)  # type: ignore[arg-type]


# --- the subject parser -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("subject", "new", "held"),
    [
        (" Bonus 1:2", 1, 2),
        ("Bonus 1:1", 1, 1),
        ("Bonus issue 1:2", 1, 2),  # BSE's wording
        ("Bonus 4:1", 4, 1),
        ("BONUS 2 : 9", 2, 9),
    ],
)
def test_a_bonus_subject_parses_to_its_ratio(subject: str, new: int, held: int) -> None:
    parsed = parse_action(action(subject))
    assert (parsed.kind, parsed.ratio_new, parsed.ratio_held) == (KIND_BONUS, new, held)


@pytest.mark.parametrize(
    ("subject", "face_from", "face_to"),
    [
        (" Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per Share", 500, 100),
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", 1000, 200),
        ("Stock  Split From Rs.5/- to Rs.1/-", 500, 100),  # BSE's wording
        ("Face Value Consolidation From Re 1/- To Rs 10/-", 100, 1000),
    ],
)
def test_a_split_subject_parses_to_its_face_values(
    subject: str, face_from: int, face_to: int
) -> None:
    parsed = parse_action(action(subject))
    assert parsed.kind == KIND_SPLIT
    assert (parsed.face_from_paise, parsed.face_to_paise) == (face_from, face_to)


def test_a_split_subject_without_face_values_is_an_exception_not_a_guess() -> None:
    """BSE files 2 of these ("Consolidation of Shares"). A face-value change with no values
    cannot produce k = B/A, and inventing one would silently rescale a whole history."""
    with pytest.raises(CorporateActionError, match="no 'From Rs X"):
        parse_action(action("Consolidation of Shares"))


@pytest.mark.parametrize(
    ("subject", "new", "held", "premium"),
    [
        (" Rights 2:7", 2, 7, None),
        ("Rights 1:1 @ Premium Rs 1.30/-", 1, 1, 130),
        ("Rights 1:16 @ Premium Rs 65/-", 1, 16, 6500),
        ("Rights 119:758 @ Premium Rs 218/-", 119, 758, 21800),
        ("Rights 1:2 @ Premium Re 1.50/-", 1, 2, 150),
    ],
)
def test_a_rights_subject_parses_to_ratio_and_premium(
    subject: str, new: int, held: int, premium: int | None
) -> None:
    parsed = parse_action(action(subject))
    assert parsed.kind == KIND_RIGHTS
    assert (parsed.ratio_new, parsed.ratio_held) == (new, held)
    assert parsed.rights_premium_paise == premium
    assert parsed.rights_price_paise is None, "NSE states a PREMIUM, never the issue price"


def test_a_rights_subject_with_no_ratio_is_an_exception() -> None:
    """BSE's generic "Right Issue of Equity Shares" (21 rows across the frozen windows)."""
    with pytest.raises(CorporateActionError, match="no CONTEXT 4.2 event kind"):
        parse_action(action("Right Issue of Equity Shares"))


@pytest.mark.parametrize(
    ("subject", "paise"),
    [
        ("Dividend - Rs 1.50 Per Share", 150),
        ("Interim Dividend - Re 0.20/- Per Share", 20),
        ("Interim Dividend-Rs 8/- Per Share (Purposed Revised)", 800),
        ("Annual General Meeting/Dividend - Rs 10 Per Share", 1000),
        ("Interim Dividend - Rs. - 5.5000", 550),  # BSE's wording
        ("Final Dividend Rs 6/- Plus Special Dividend Rs 4/- Per Share", 1000),
        ("Annual General Meeting/Dividend - Rs 1.50 Per Share/ Special Dividend - Re 1 Per Share", 250),
    ],
)
def test_a_dividend_subject_totals_the_cash_it_declares(subject: str, paise: int) -> None:
    """One ex-date can declare several cash components; CONTEXT 4.2 classifies by SIZE, so
    what its threshold needs is the total cash per share leaving the company that day."""
    parsed = parse_action(action(subject))
    assert parsed.kind == KIND_DIVIDEND
    assert parsed.dividend_paise == paise


def test_a_sub_paisa_dividend_is_refused_rather_than_rounded() -> None:
    """Measured on the frozen BSE window: SANINFRA declared Rs 0.0350 on 2023-07-25."""
    with pytest.raises(CorporateActionError, match="not a whole number of paise"):
        parse_action(action("Final Dividend - Rs. - 0.0350"))


def test_a_dividend_with_no_amount_is_an_exception() -> None:
    with pytest.raises(CorporateActionError, match="declares no amount"):
        parse_action(action("Interim Dividend Declared"))


@pytest.mark.parametrize(
    "subject",
    ["Demerger", "Scheme Of Arrangement", "Spin Off ", "De-Merger", "scheme of arrangement"],
)
def test_every_demerger_wording_lands_in_the_demerger_kind(subject: str) -> None:
    """CONTEXT 3.2 blocks trading across these, so a missed one is the costliest miss here."""
    assert parse_action(action(subject)).kind == KIND_DEMERGER


def test_a_demerger_keyword_wins_over_any_other_kind() -> None:
    """Precedence, stated and tested: the suppressing outcome beats the adjusting one."""
    assert parse_action(action("Scheme Of Arrangement / Bonus 1:2")).kind == KIND_DEMERGER


@pytest.mark.parametrize("subject", ["Buyback Of Shares", "Buy Back", "Buy-back of equity"])
def test_a_buyback_parses_and_carries_no_adjustment(subject: str) -> None:
    parsed = parse_action(action(subject))
    assert parsed.kind == KIND_BUYBACK
    assert factor_for(parsed).k == Decimal(1)


@pytest.mark.parametrize(
    "subject",
    [
        "Annual General Meeting",
        "Extra Ordinary General Meeting",
        "Extra-Ordinary General Meeting",
        "E.G.M.",
        "Postal Ballot",
    ],
)
def test_a_bare_meeting_notice_is_informational(subject: str) -> None:
    assert parse_action(action(subject)).kind == KIND_INFORMATIONAL


def test_a_meeting_notice_that_declares_money_is_an_exception_not_informational() -> None:
    """The guard that keeps "informational" from becoming a dustbin: if a subject carries an
    amount or a ratio this parser did not understand, it must be REPORTED, not shrugged off.
    """
    with pytest.raises(CorporateActionError, match="declares an amount or a ratio"):
        parse_action(action("Annual General Meeting / Something Rs 5 Per Share"))
    with pytest.raises(CorporateActionError, match="declares an amount or a ratio"):
        parse_action(action("Extra Ordinary General Meeting 1:2"))


@pytest.mark.parametrize(
    "subject",
    ["Reduction of Capital", "Resolution Plan -Suspension", "Income Distribution (InvIT)", ""],
)
def test_an_unrecognised_subject_raises_so_the_caller_can_report_it(subject: str) -> None:
    with pytest.raises(CorporateActionError):
        parse_action(action(subject))


def test_parse_actions_buckets_everything_and_the_buckets_add_up() -> None:
    actions = [
        action(" Bonus 1:2"),
        action("Annual General Meeting"),
        action("Reduction of Capital"),
        action("Interest Payment", series="N4"),
    ]
    report = parse_actions(actions)
    assert len(report.events) == 1
    assert len(report.informational) == 1
    assert len(report.exceptions) == 1
    assert len(report.ignored_series) == 1
    assert report.total == len(actions)
    assert report.summary()["total"] == 4


def test_a_debt_series_action_is_ignored_rather_than_excepted() -> None:
    """QUESTIONS.md Q-4: a coupon on a listed NCD is not an action on the equity we trade.
    Keeping them would flood the exception report with rows that can never matter."""
    report = parse_actions([action("Interest Payment", series="N4")])
    assert report.exceptions == () and len(report.ignored_series) == 1

    kept = parse_actions([action("Interest Payment", series="N4")], instrument_series_only=False)
    assert len(kept.exceptions) == 1, "the filter is opt-out, and then nothing is hidden"


def test_exceptions_in_universe_filters_to_the_symbols_that_matter() -> None:
    report = parse_actions(
        [action("Reduction of Capital", symbol="TCS"), action("Reduction of Capital", symbol="XYZ")]
    )
    assert len(report.exceptions) == 2
    assert [item.action.symbol for item in report.exceptions_in(["TCS"])] == ["TCS"]


# --- factors, CONTEXT 4.2's table row by row ----------------------------------------------


def test_bonus_uses_the_indian_convention() -> None:
    """CONTEXT 4.2: "Bonus A:B (A new per B held -- INDIAN convention), k = B/(A+B)".
    A US-convention library would return 1/2 here and silently corrupt every 2016 price."""
    assert factor_for(event(KIND_BONUS, ratio_new=1, ratio_held=2)).k == Decimal(2) / Decimal(3)
    assert factor_for(event(KIND_BONUS, ratio_new=1, ratio_held=1)).k == Decimal("0.5")
    assert factor_for(event(KIND_BONUS, ratio_new=4, ratio_held=1)).k == Decimal(1) / Decimal(5)


def test_split_uses_the_face_value_ratio() -> None:
    """CONTEXT 4.2: "Split, face value A->B: k = B/A". FV 10->2 is the spec's own example."""
    assert factor_for(event(KIND_SPLIT, face_from_paise=1000, face_to_paise=200)).k == Decimal("0.2")
    assert factor_for(event(KIND_SPLIT, face_from_paise=500, face_to_paise=100)).k == Decimal("0.2")
    assert factor_for(event(KIND_SPLIT, face_from_paise=100, face_to_paise=1000)).k == Decimal(10)


def test_rights_follows_nses_own_terp_formula() -> None:
    """C = (P-S)*A, E = C/(A+B), k = (P-E)/P -- the chunk-3 card's hand-derived case."""
    k = ca.rights_factor(
        cum_close_paise=30000, issue_price_paise=20000, ratio_new=1, ratio_held=4
    )
    assert k == Decimal(280) / Decimal(300)


def _rights(
    *,
    ratio_new: int,
    ratio_held: int,
    premium_paise: int | None = None,
    price_paise: int | None = None,
    face_value_paise: int | None = None,
    symbol: str = "ACME",
    ex_date: date = EX,
) -> ParsedEvent:
    act = CorporateAction(
        symbol=symbol,
        ex_date=ex_date,
        subject="Rights",
        source=ca.SOURCE_NSE,
        series="EQ",
        face_value_paise=face_value_paise,
    )
    return ParsedEvent(
        action=act,
        kind=KIND_RIGHTS,
        ratio_new=ratio_new,
        ratio_held=ratio_held,
        rights_premium_paise=premium_paise,
        rights_price_paise=price_paise,
    )


def _split_event(ex_date: date, face_from: int, face_to: int, symbol: str = "ACME") -> ParsedEvent:
    act = CorporateAction(
        symbol=symbol, ex_date=ex_date, subject="split", source=ca.SOURCE_NSE, series="EQ"
    )
    return ParsedEvent(
        action=act, kind=KIND_SPLIT, face_from_paise=face_from, face_to_paise=face_to
    )


def test_a_rights_factor_refuses_to_run_without_the_issue_price() -> None:
    """factor_for is the arithmetic; S is recovered by build_factor_table, not guessed here."""
    rights = event(KIND_RIGHTS, ratio_new=2, ratio_held=7, rights_premium_paise=9000)
    with pytest.raises(CorporateActionError, match="ISSUE PRICE"):
        factor_for(rights, cum_close_paise=30000)
    with pytest.raises(CorporateActionError, match="cum-date close"):
        factor_for(rights, rights_issue_price_paise=20000)


def test_a_rights_issue_priced_at_or_above_the_cum_close_is_refused() -> None:
    """REVIEW_3 F3: rights are always at a discount, so S >= P (k >= 1) is impossible."""
    with pytest.raises(CorporateActionError, match="economically impossible"):
        ca.rights_factor(cum_close_paise=10000, issue_price_paise=10000, ratio_new=1, ratio_held=4)
    with pytest.raises(CorporateActionError, match="economically impossible"):
        ca.rights_factor(cum_close_paise=10000, issue_price_paise=15000, ratio_new=1, ratio_held=4)
    assert (
        ca.rights_factor(cum_close_paise=10000, issue_price_paise=9999, ratio_new=1, ratio_held=4)
        < Decimal(1)
    )


def test_a_dividend_is_classified_by_D_over_P_cum() -> None:
    """QUESTIONS.md Q-7: three bands against P_cum -- < 1% fast, 1-2% near, >= 2% special."""
    fast = factor_for(event(KIND_DIVIDEND, dividend_paise=100), cum_close_paise=20000)  # 0.5%
    assert fast.k == Decimal(1) and fast.classification == ca.DIVIDEND_ORDINARY

    near = factor_for(event(KIND_DIVIDEND, dividend_paise=150), cum_close_paise=10000)  # 1.5%
    assert near.k == Decimal(1) and near.classification == ca.DIVIDEND_NEAR_THRESHOLD

    special = factor_for(event(KIND_DIVIDEND, dividend_paise=200), cum_close_paise=9000)  # 2.22%
    assert special.k == Decimal(1) - Decimal(200) / Decimal(9000)
    assert special.classification == ca.DIVIDEND_SPECIAL and "P_cum" in special.basis


def test_the_two_percent_threshold_is_inclusive_at_the_boundary() -> None:
    """Q-7 keeps CONTEXT 4.2's "<2%" / ">=2%" wording, now against P_cum: exactly 2% is special."""
    exactly = factor_for(event(KIND_DIVIDEND, dividend_paise=200), cum_close_paise=10000)  # 2.0%
    assert exactly.classification == ca.DIVIDEND_SPECIAL
    assert exactly.k == Decimal(1) - Decimal(200) / Decimal(10000)
    just_under = factor_for(event(KIND_DIVIDEND, dividend_paise=199), cum_close_paise=10000)  # 1.99%
    assert just_under.k == Decimal(1) and just_under.classification == ca.DIVIDEND_NEAR_THRESHOLD


def test_the_one_percent_fast_path_boundary_is_inclusive() -> None:
    """Exactly 1% is NEAR-THRESHOLD (>= 1%); just under it is the fast-path ordinary."""
    at = factor_for(event(KIND_DIVIDEND, dividend_paise=100), cum_close_paise=10000)  # 1.0%
    assert at.classification == ca.DIVIDEND_NEAR_THRESHOLD
    under = factor_for(event(KIND_DIVIDEND, dividend_paise=99), cum_close_paise=10000)  # 0.99%
    assert under.classification == ca.DIVIDEND_ORDINARY


def test_a_dividend_factor_refuses_to_run_without_P_cum() -> None:
    """A missing price must never become k = 1: that is what "no adjustment" looks like."""
    with pytest.raises(CorporateActionError, match="cum-date close"):
        factor_for(event(KIND_DIVIDEND, dividend_paise=500))


def test_a_demerger_has_no_factor_at_all() -> None:
    """CONTEXT 4.2: "NO factor exists". CONTEXT 3.2 suppresses the pair instead."""
    with pytest.raises(CorporateActionError, match="NO valid factor"):
        factor_for(event(KIND_DEMERGER), cum_close_paise=10000)


def test_a_factor_must_be_a_positive_decimal() -> None:
    with pytest.raises(CorporateActionError, match="must be a Decimal"):
        Factor(symbol="X", ex_date=EX, kind=KIND_BONUS, k=0.5, basis="float")  # type: ignore[arg-type]
    with pytest.raises(CorporateActionError, match="not positive"):
        Factor(symbol="X", ex_date=EX, kind=KIND_BONUS, k=Decimal(0), basis="zero")


# --- Q-6: face reconstruction, tier-1 recovery, tier-2 suppression, tier-3 overrides -------


def test_reconstruct_face_value_prefers_split_history_over_a_stale_faceval() -> None:
    """The GREENPLY trap: a split in the parsed history overrides the as-of-query faceVal."""
    split = _split_event(date(2016, 1, 6), face_from=500, face_to=100)  # 5 -> 1
    assert ca.reconstruct_face_value_paise(date(2015, 1, 1), [split]) == 500  # before -> from
    assert ca.reconstruct_face_value_paise(date(2020, 1, 1), [split]) == 100  # after -> to
    assert ca.reconstruct_face_value_paise(date(2016, 1, 6), [split]) == 100  # on ex -> to (effected)
    assert ca.reconstruct_face_value_paise(date(2020, 1, 1), []) is None  # no split -> None


def test_build_factor_table_suppresses_a_rights_with_no_recoverable_price() -> None:
    """Q-6 tier 2: no price, no premium+face, no override -> SUPPRESSION (the demerger precedent)."""
    events = [
        event(KIND_BONUS, ratio_new=1, ratio_held=1),
        event(KIND_RIGHTS, ratio_new=2, ratio_held=7),  # bare ratio -> unrecoverable
        event(KIND_DEMERGER),
    ]
    table = ca.build_factor_table(events)
    assert [f.kind for f in table.factors] == [KIND_BONUS]
    assert table.pending == (), "an unrecoverable rights is suppressed, not left pending"
    assert {s.kind for s in table.suppressions} == {KIND_DEMERGER, KIND_RIGHTS}
    rights_supp = [s for s in table.suppressions if s.kind == KIND_RIGHTS]
    assert rights_supp and "tier 2" in rights_supp[0].reason


def test_build_factor_table_prices_a_rights_when_S_is_recoverable_and_P_given() -> None:
    """Q-6 tier 1: S = face + premium; k once the cum close is supplied. Face 100 + prem 100
    = S 200 on P 300 -> k = 280/300 (the F8 numbers)."""
    rights = _rights(ratio_new=1, ratio_held=4, premium_paise=10000, face_value_paise=10000)
    table = ca.build_factor_table([rights], cum_close=lambda symbol, day: 30000)
    assert table.pending == () and table.suppressions == ()
    assert table.factors[0].k == Decimal(280) / Decimal(300)


def test_a_recoverable_rights_stays_pending_until_the_cum_close_arrives() -> None:
    rights = _rights(ratio_new=1, ratio_held=4, premium_paise=10000, face_value_paise=10000)
    table = ca.build_factor_table([rights])  # no cum_close
    assert table.factors == () and table.suppressions == ()
    assert len(table.pending) == 1 and "needs the cum-date close" in table.pending[0].needs


def test_a_split_in_history_reprices_a_rights_that_the_stale_faceval_would_misprice() -> None:
    """A rights BEFORE a 5->1 split: face is 5 (from history), not the row's stale 1."""
    split = _split_event(date(2016, 1, 6), face_from=500, face_to=100)
    rights = _rights(
        ratio_new=1, ratio_held=1, premium_paise=0, face_value_paise=100, ex_date=date(2015, 6, 1)
    )
    table = ca.build_factor_table([split, rights], cum_close=lambda symbol, day: 100000)
    # S = face 5 + premium 0 = 5 (500 paise), NOT the stale faceVal 1 (100 paise)
    pending = table.pending
    factor = [f for f in table.factors if f.kind == KIND_RIGHTS][0]
    expected = ca.rights_factor(
        cum_close_paise=100000, issue_price_paise=500, ratio_new=1, ratio_held=1
    )
    assert pending == () and factor.k == expected


def test_a_rights_override_supplies_S_and_must_cite_a_circular(tmp_path) -> None:
    """Q-6 tier 3: the committed file is empty; an entry with no circular is refused."""
    assert ca.load_rights_overrides() == {}, "the committed overrides file is empty by design"

    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"overrides":[{"symbol":"ACME","ex_date":"2020-01-15","issue_price_paise":20000}]}',
        encoding="utf-8",
    )
    with pytest.raises(CorporateActionError, match="circular"):
        ca.load_rights_overrides(bad)

    good = tmp_path / "good.json"
    good.write_text(
        '{"overrides":[{"symbol":"ACME","ex_date":"2020-01-15",'
        '"issue_price_paise":20000,"nse_circular":"NSE/FAOP/123 15-Jan-2020"}]}',
        encoding="utf-8",
    )
    overrides = ca.load_rights_overrides(good)
    # a premium that would give a different S is overridden by the curated value
    rights = _rights(ratio_new=1, ratio_held=4, premium_paise=99999, face_value_paise=10000)
    recovered = ca.recover_rights_price(rights, overrides=overrides)
    assert recovered.recoverable and recovered.price_paise == 20000
    assert "circular" in recovered.basis.lower()


def test_suppression_dates_union_demergers_and_unrecoverable_rights() -> None:
    """The single list the bias engine consumes (CONTEXT 3.2 + Q-6 tier 2)."""
    table = ca.build_factor_table([event(KIND_DEMERGER), event(KIND_RIGHTS, ratio_new=2, ratio_held=7)])
    supp = ca.suppression_dates(table)
    assert len(supp) == 2 and {s.kind for s in supp} == {KIND_DEMERGER, KIND_RIGHTS}


def test_special_dividend_verification_list() -> None:
    """Q-7: every SPECIAL classification lands on the verification list; ordinary ones do not."""
    big = event(KIND_DIVIDEND, dividend_paise=300)  # 3% -> special
    small = event(KIND_DIVIDEND, dividend_paise=50)  # 0.5% -> ordinary
    table = ca.build_factor_table([big, small], cum_close=lambda symbol, day: 10000)
    verifications = ca.special_dividend_verifications(table)
    assert len(verifications) == 1 and verifications[0].classification == ca.DIVIDEND_SPECIAL


# --- adjust_pair (CONTEXT 3.2 + 7-E11) ----------------------------------------------------


def _factor(k: str, day: date = EX, symbol: str = "ACME") -> Factor:
    return Factor(symbol=symbol, ex_date=day, kind=KIND_BONUS, k=Decimal(k), basis="test")


def test_adjust_pair_multiplies_the_chain_and_rounds_once() -> None:
    """Rounding once, at the end, is what keeps two chained events from drifting a paisa."""
    two_thirds = _factor("0.6666666666666666666666666667")
    assert adjust_pair(30000, [_factor("0.5")]) == 15000
    assert adjust_pair(12345, [Factor(symbol="A", ex_date=EX, kind=KIND_BONUS,
                                      k=Decimal(2) / Decimal(3), basis="t")]) == 8230
    chained = adjust_pair(100000, [_factor("0.5"), _factor("0.2")])
    assert chained == 10000
    assert two_thirds.k > 0


def test_adjust_pair_rounds_half_to_even() -> None:
    """Half-even is unbiased, so a long history of adjustments does not creep upward."""
    half = Factor(symbol="A", ex_date=EX, kind=KIND_SPLIT, k=Decimal("0.5"), basis="t")
    assert adjust_pair(5, [half]) == 2, "2.5 -> 2 (even)"
    assert adjust_pair(7, [half]) == 4, "3.5 -> 4 (even)"


def test_adjust_pair_with_no_events_returns_the_price_untouched() -> None:
    assert adjust_pair(225110, []) == 225110


def test_adjust_pair_refuses_anything_that_is_not_integer_paise() -> None:
    with pytest.raises(CorporateActionError, match="integer paise"):
        adjust_pair(2251.10, [_factor("0.5")])  # type: ignore[arg-type]
    with pytest.raises(CorporateActionError, match="Factor objects"):
        adjust_pair(225110, [Decimal("0.5")])  # type: ignore[list-item]


def test_factors_between_uses_context_3_2s_half_open_window() -> None:
    """"events with ex-date AFTER P and ON OR BEFORE C" -- so the P-dated event is excluded
    and the C-dated one is included. Getting this backwards double-adjusts a candle."""
    previous, current = date(2016, 1, 4), date(2016, 1, 6)
    on_p = _factor("0.5", date(2016, 1, 4))
    between = _factor("0.5", date(2016, 1, 5))
    on_c = _factor("0.5", date(2016, 1, 6))
    after_c = _factor("0.5", date(2016, 1, 7))
    picked = factors_between([on_p, between, on_c, after_c], previous, current)
    assert [f.ex_date for f in picked] == [date(2016, 1, 5), date(2016, 1, 6)]


def test_factors_between_filters_by_symbol_when_asked() -> None:
    mine = _factor("0.5", date(2016, 1, 5), symbol="TCS")
    theirs = _factor("0.5", date(2016, 1, 5), symbol="INFY")
    assert factors_between([mine, theirs], date(2016, 1, 4), date(2016, 1, 6), symbol="tcs") == (
        mine,
    )


def test_factors_between_refuses_a_backwards_window() -> None:
    with pytest.raises(CorporateActionError, match="Empty pair window"):
        factors_between([], date(2016, 1, 6), date(2016, 1, 4))


# --- source payload parsing ---------------------------------------------------------------


def test_the_nse_payload_parses_to_actions_with_naive_dates() -> None:
    actions = parse_nse_payload(ca.load_snapshot(CA_FIXTURES / "nse_ca_2016-01.json"))
    assert len(actions) == 19
    first = next(a for a in actions if a.symbol == "KOTHARIPRO")
    assert first.ex_date == date(2016, 1, 5)
    assert first.record_date == date(2016, 1, 6)
    assert first.series == "EQ"
    assert first.isin == "INE823A01017"
    assert first.face_value_paise == 1000
    assert first.source == ca.SOURCE_NSE


def test_a_malformed_nse_payload_raises_rather_than_returning_nothing() -> None:
    with pytest.raises(CorporateActionError, match="must be a JSON array"):
        parse_nse_payload({"data": []})
    with pytest.raises(CorporateActionError, match="no symbol"):
        parse_nse_payload([{"exDate": "05-Jan-2016", "subject": "Bonus 1:2"}])
    with pytest.raises(CorporateActionError, match="not an NSE date"):
        parse_nse_payload([{"symbol": "X", "exDate": "2016-01-05", "subject": "Bonus 1:2"}])


def test_the_bse_csv_parses_and_skips_its_rows_without_an_ex_date() -> None:
    actions = parse_bse_csv(ca.load_snapshot(CA_FIXTURES / "bse_ca_2016-01.csv"))
    assert len(actions) == 24
    kothari = next(a for a in actions if a.symbol == "KOTHARIPRO")
    assert kothari.ex_date == date(2016, 1, 5)
    assert kothari.subject == "Bonus issue 1:2"
    assert kothari.security_code == "530299"
    assert kothari.source == ca.SOURCE_BSE
    assert all(a.isin is None for a in actions), "CONTEXT 4.2: BSE publishes no ISIN"


def test_a_bse_csv_without_its_columns_raises() -> None:
    with pytest.raises(CorporateActionError, match="missing column"):
        parse_bse_csv("A,B\n1,2\n")


def test_the_yahoo_stream_parses_to_ist_dated_splits() -> None:
    splits = parse_yahoo_chart(
        ca.load_snapshot(CA_FIXTURES / "yahoo_splits_KOTHARIPRO_2015-12.json"), "KOTHARIPRO"
    )
    assert len(splits) == 1
    assert splits[0].ex_date == date(2016, 1, 5), "epoch 1451965500 is 09:15 IST on 05-Jan"
    assert splits[0].ratio_text == "3:2"
    assert splits[0].k == Decimal(2) / Decimal(3)


def test_yahoo_carries_no_split_for_the_reliance_demerger() -> None:
    """CONTEXT 4.2: Yahoo is a TIEBREAK for splits and bonuses. It is blind to demergers, and
    a source that is silent must never be read as a source that disagrees."""
    splits = parse_yahoo_chart(
        ca.load_snapshot(CA_FIXTURES / "yahoo_splits_RELIANCE_2023-07.json"), "RELIANCE"
    )
    assert splits == ()


def test_a_yahoo_error_payload_raises_rather_than_returning_an_empty_stream() -> None:
    with pytest.raises(CorporateActionError, match="returned an error"):
        parse_yahoo_chart({"chart": {"error": {"code": "Not Found"}, "result": None}}, "X")
    with pytest.raises(CorporateActionError, match="carries no result"):
        parse_yahoo_chart({"chart": {"result": []}}, "X")


def test_the_epoch_conversions_are_inverses_at_ist_session_open() -> None:
    assert ca.ist_date_from_epoch(1451965500) == date(2016, 1, 5)
    assert ca.ist_date_from_epoch(1730087100) == date(2024, 10, 28)
    assert ca.epoch_from_date(date(2016, 1, 5)) == 1451952000


# --- URLs and the fetch discipline ---------------------------------------------------------


def test_the_urls_are_the_ones_context_4_2_names() -> None:
    assert ca.nse_url(date(2016, 1, 1), date(2016, 1, 31)).endswith(
        "from_date=01-01-2016&to_date=31-01-2016"
    )
    assert "corporates-corporateActions" in ca.nse_url(date(2016, 1, 1), date(2016, 1, 31))
    assert "Fdate=20160101&TDate=20160131" in ca.bse_url(date(2016, 1, 1), date(2016, 1, 31))
    assert "CorpactCSVDownload" in ca.bse_url(date(2016, 1, 1), date(2016, 1, 31))
    url = ca.yahoo_url("reliance", date(2024, 10, 1), date(2024, 11, 30))
    assert "/chart/RELIANCE.NS?" in url and "events=split" in url


def test_every_fetcher_is_offline_by_default(tmp_path: Path) -> None:
    """The same opt-in rule as every other endpoint in this repo (chunk-1 B2). conftest would
    fail these at the socket if they tried anyway."""
    for call in (
        lambda: ca.fetch_nse_corporate_actions(
            date(2016, 1, 1), date(2016, 1, 31), cache_dir=tmp_path
        ),
        lambda: ca.fetch_bse_corporate_actions(
            date(2016, 1, 1), date(2016, 1, 31), cache_dir=tmp_path
        ),
        lambda: ca.fetch_yahoo_splits(
            "RELIANCE", date(2024, 10, 1), date(2024, 11, 30), cache_dir=tmp_path
        ),
    ):
        with pytest.raises(Exception, match="allow_network is False"):
            call()


def test_a_cached_payload_is_served_without_the_network(tmp_path: Path) -> None:
    """Day-cached like the universe and holiday endpoints: one live pull per day, at most."""
    from acumen import nse_http

    payload = ca.load_snapshot(CA_FIXTURES / "nse_ca_2016-01.json")
    today = date(2026, 7, 25)
    nse_http.write_cache(
        ca.cache_path(tmp_path, "nse_ca_2016-01-01_2016-01-31.json"),
        payload,
        url=ca.nse_url(date(2016, 1, 1), date(2016, 1, 31)),
        fetched_on=today,
    )
    actions = ca.fetch_nse_corporate_actions(
        date(2016, 1, 1), date(2016, 1, 31), cache_dir=tmp_path, today=today
    )
    assert len(actions) == 19
    assert any(a.symbol == "GREENPLY" for a in actions)


def test_the_bse_and_yahoo_sessions_carry_their_own_headers() -> None:
    bse = ca.new_bse_session()
    assert bse.headers["Referer"] == ca.BSE_HOME_URL
    assert "bseindia" in bse.headers["Origin"]
    yahoo = ca.new_yahoo_session()
    assert "yahoo" in yahoo.headers["Referer"]
    assert "Origin" not in yahoo.headers


def test_the_module_holds_no_hardcoded_event_list() -> None:
    """CLAUDE.md: no hardcoded symbols or dates. The demerger seed comes from the SNAPSHOT,
    not from a list in `src/` -- a hardcoded table would rot the first time NSE files one."""
    import ast

    source = (Path(ca.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.upper() in {"RELIANCE", "KOTHARIPRO", "GREENPLY", "JMCPROJECT"}
    ]
    assert offenders == []
