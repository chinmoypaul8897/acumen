"""GOLDEN FIXTURE F8 and the chunk-3 card's goldens (CONTEXT 8, CONTEXT 4.2).

Four things define "correct" for the corporate-action engine, and all four are here:

1. **F8, hand-derived** -- the three cases the chunk-3 card names, computed straight from
   CONTEXT 4.2's formulas: bonus 1:2 -> k = 2/3, split FV 10->2 -> k = 0.2,
   rights 1:4 @ 200 on P = 300 -> k = 280/300.
2. **F8, against NSE's own oracle** -- CONTEXT 4.2 says "our factors must reproduce" NSE's
   "Adjustment of Futures and Options contracts Calculator" XLSX. It is frozen at
   `docs/nse_adjustment_calculator.xlsx` (fetched once, 2026-07-25, digest pinned below) and
   these tests read its three worked examples OUT OF THE FILE, so the transcription below
   cannot drift from the oracle it claims to quote.
3. **Parser goldens** -- the five verified events, from the frozen source snapshots: the
   three Jan-2016 subjects, RELIANCE's Oct-2024 bonus, and RELIANCE's Jul-2023 demerger.
4. **Cross-source join** -- NSE vs BSE vs Yahoo over the three frozen windows.

NSE's calculator expresses BONUS and SPLIT as an adjustment factor that DIVIDES a strike,
and RIGHTS as one that MULTIPLIES it. CONTEXT 4.2 states all three as multipliers of the
pre-ex PRICE, so the bonus/split relation is `k = 1/AF` and the rights one is `k = AF`. Both
are asserted below against the file's own cells, because that relation is exactly the kind of
thing a later session could invert without any test noticing.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from acumen import corp_actions as ca
from acumen.corp_actions import (
    KIND_BONUS,
    KIND_DEMERGER,
    KIND_RIGHTS,
    KIND_SPLIT,
    CorporateAction,
    ParsedEvent,
    factor_for,
)

REPO = Path(__file__).resolve().parents[1]
CA_FIXTURES = REPO / "tests" / "fixtures" / "ca"
CALCULATOR = REPO / "docs" / "nse_adjustment_calculator.xlsx"

#: SHA-256 of the oracle as fetched from CONTEXT 4.2's URL on 2026-07-25. Pinned here rather
#: than in test_fixture_integrity.py because this file is the only thing that reads it.
CALCULATOR_SHA256 = "ac79276d12a7f72bc614fa9ea574c6ba12dd54fda811641de4835dadb4544062"

#: NSE quotes F&O strikes on a 5-paise grid and its calculator rounds with Excel's MROUND.
#: That is NSE's contract convention, NOT this project's price domain -- our own prices are
#: integer paise, rounded half-even (CONTEXT 7-E11). The grid is applied only where a cell of
#: the oracle is being reproduced.
STRIKE_GRID_PAISE = 5


def _synthetic(kind: str, **fields: object) -> ParsedEvent:
    """A typed event with no source row behind it -- for the formula-only F8 cases."""
    action = CorporateAction(
        symbol="F8", ex_date=date(2020, 1, 1), subject="hand-derived F8 case", source="golden"
    )
    return ParsedEvent(action=action, kind=kind, **fields)  # type: ignore[arg-type]


# =========================================================================================
# F8 part 1 -- hand-derived from CONTEXT 4.2's formulas
# =========================================================================================


def test_f8_bonus_one_for_two_is_two_thirds() -> None:
    """CONTEXT 4.2: "Bonus A:B (A new per B held -- INDIAN convention) -> k = B/(A+B)"."""
    factor = factor_for(_synthetic(KIND_BONUS, ratio_new=1, ratio_held=2))
    assert factor.k == Decimal(2) / Decimal(3)
    assert factor.k.quantize(Decimal("0.000001")) == Decimal("0.666667")


def test_f8_face_value_split_ten_to_two_is_point_two() -> None:
    """CONTEXT 4.2: "Split, face value A->B -> k = B/A. FV 10->2: k=0.2"."""
    factor = factor_for(_synthetic(KIND_SPLIT, face_from_paise=1000, face_to_paise=200))
    assert factor.k == Decimal("0.2")


def test_f8_rights_one_for_four_at_200_on_a_300_close() -> None:
    """CONTEXT 4.2's TERP formula, with the card's numbers: C=(P-S)A, E=C/(A+B), k=(P-E)/P.

    A=1, B=4, S=200, P=300 -> C = 100, E = 20, k = 280/300.
    """
    k = ca.rights_factor(
        cum_close_paise=30000, issue_price_paise=20000, ratio_new=1, ratio_held=4
    )
    assert k == Decimal(280) / Decimal(300)
    assert (Decimal(30000) * k).quantize(Decimal(1)) == Decimal(28000), "TERP is 280.00"


def test_f8_a_special_dividend_uses_the_two_reference_prices_it_is_meant_to() -> None:
    """The chunk-3 card's "one special-dividend case validated against the 4.2 formula".

    D = 25.00 on a pre-announcement close of 1000.00 is 2.5% -> SPECIAL. The factor then uses
    the CUM close (990.00), NOT the pre-announcement one: k = 1 - 25/990.
    """
    event = _synthetic("dividend", dividend_paise=2500)
    factor = factor_for(
        event, pre_announcement_close_paise=100000, cum_close_paise=99000
    )
    assert factor.k == Decimal(1) - Decimal(2500) / Decimal(99000)
    assert factor.k.quantize(Decimal("0.00000001")) == Decimal("0.97474747")

    ordinary = factor_for(
        _synthetic("dividend", dividend_paise=1900),
        pre_announcement_close_paise=100000,
        cum_close_paise=99000,
    )
    assert ordinary.k == Decimal(1), "1.9% of the pre-announcement close is ordinary"


# =========================================================================================
# F8 part 2 -- NSE's own calculator, read out of the frozen file
# =========================================================================================


def _cells(sheet_index: int) -> dict[str, str]:
    """Every non-empty cell of one sheet as {ref: text}. Stdlib only -- an xlsx is a zip."""
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(CALCULATOR) as archive:
        shared = [
            "".join(node.text or "" for node in si.iter(namespace + "t"))
            for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall(namespace + "si")
        ]
        root = ET.fromstring(archive.read(f"xl/worksheets/sheet{sheet_index}.xml"))
    values: dict[str, str] = {}
    for cell in root.iter(namespace + "c"):
        node = cell.find(namespace + "v")
        if node is None or node.text is None:
            continue
        text = node.text
        if cell.get("t") == "s":
            text = shared[int(text)]
        values[str(cell.get("r"))] = text
    return values


def _mround_to_grid(paise: Decimal) -> int:
    """Excel's MROUND(x, 0.05) in the paise domain: nearest 5 paise, halves away from zero."""
    steps = (paise / STRIKE_GRID_PAISE).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(steps * STRIKE_GRID_PAISE)


def test_the_oracle_is_the_file_nse_published() -> None:
    """CONTEXT 4.2 names this XLSX as the test oracle; this pins the bytes it was read from."""
    assert CALCULATOR.is_file(), "docs/nse_adjustment_calculator.xlsx is missing"
    digest = hashlib.sha256(CALCULATOR.read_bytes()).hexdigest()
    assert digest == CALCULATOR_SHA256, (
        "The frozen NSE calculator CHANGED. It is an oracle, not an input to regenerate "
        "(CLAUDE.md rule 3): restore it from git."
    )


def test_f8_oracle_bonus_sheet() -> None:
    """NSE: "Adjustment factor for Bonus issue of A:B is defined as (A+B)/B" -- a DIVISOR.

    Sheet BONUS, ratio 1:2 -> AF 1.5. Our k must be its reciprocal, and applying k to the
    sheet's own "before" values must reproduce its "after" values on NSE's 5-paise grid.
    """
    cells = _cells(1)
    assert cells["A2"].strip() == "Bonus issue ratio     : 1:2"
    adjustment_factor = Decimal(cells["B6"])
    assert adjustment_factor == Decimal("1.5")

    k = factor_for(_synthetic(KIND_BONUS, ratio_new=1, ratio_held=2)).k
    assert k == 1 / adjustment_factor

    for before_ref, after_ref in (("E9", "F9"), ("E11", "F11"), ("D16", "E16")):
        before = int(Decimal(cells[before_ref]) * 100)
        expected = _paise_2dp(cells[after_ref])
        assert _mround_to_grid(Decimal(before) * k) == expected, (before_ref, after_ref)

    assert _mround_to_grid(Decimal(11500) * k) == 7665, "strike 115.00 -> 76.65"
    assert _mround_to_grid(Decimal(11195) * k) == 7465, "futures 111.95 -> 74.65"


def test_f8_oracle_split_sheet() -> None:
    """Sheet SPLIT, ratio 10:1 -> AF 10 (a divisor). CONTEXT 4.2's k = B/A = 1/10."""
    cells = _cells(2)
    assert cells["A2"].strip() == "Stock split ratio : 10:1"
    adjustment_factor = Decimal(cells["B6"])
    assert adjustment_factor == Decimal(10)

    k = factor_for(_synthetic(KIND_SPLIT, face_from_paise=1000, face_to_paise=100)).k
    assert k == 1 / adjustment_factor == Decimal("0.1")

    for before_ref, after_ref in (("E9", "F9"), ("E11", "F11"), ("D16", "E16")):
        before = int(Decimal(cells[before_ref]) * 100)
        assert _mround_to_grid(Decimal(before) * k) == _paise_2dp(cells[after_ref])

    assert _mround_to_grid(Decimal(90000) * k) == 9000, "strike 900.00 -> 90.00"
    assert _mround_to_grid(Decimal(91330) * k) == 9135, "futures 913.30 -> 91.35"


def test_f8_oracle_rights_sheet() -> None:
    """Sheet RIGHTS: 17:74 at S=65 on P=107.10. Here NSE's AF is a MULTIPLIER, and it is
    CONTEXT 4.2's k exactly -- every intermediate (C, E) is checked against its own cell."""
    cells = _cells(3)
    assert cells["B2"].strip() == "17:74"
    cum_close = Decimal(cells["B4"])
    issue_price = Decimal(cells["B5"])
    ratio_new, ratio_held = int(Decimal(cells["B6"])), int(Decimal(cells["B7"]))
    assert (cum_close, issue_price, ratio_new, ratio_held) == (
        Decimal("107.1"),
        Decimal(65),
        17,
        74,
    )
    assert int(Decimal(cells["B8"])) == ratio_new + ratio_held == 91

    k = ca.rights_factor(
        cum_close_paise=int(cum_close * 100),
        issue_price_paise=int(issue_price * 100),
        ratio_new=ratio_new,
        ratio_held=ratio_held,
    )
    benefit = (cum_close - issue_price) * ratio_new
    per_share = benefit / (ratio_new + ratio_held)
    assert benefit.quantize(Decimal("0.01")) == Decimal(cells["B9"]).quantize(Decimal("0.01"))
    assert per_share.quantize(Decimal("0.0001")) == Decimal(cells["B10"]).quantize(
        Decimal("0.0001")
    )
    # NSE stores its AF as a double; ours is exact. Equal to the last digit the file holds.
    assert k.quantize(Decimal("0.0000000000000001")) == Decimal(cells["B11"]).quantize(
        Decimal("0.0000000000000001")
    )

    for before_ref, after_ref in (("E16", "F16"), ("E18", "F18"), ("D23", "E23")):
        before = int(Decimal(cells[before_ref]) * 100)
        assert _mround_to_grid(Decimal(before) * k) == _paise_2dp(cells[after_ref])

    assert _mround_to_grid(Decimal(10600) * k) == 9820, "strike 106.00 -> 98.20"
    assert _mround_to_grid(Decimal(10590) * k) == 9810, "futures 105.90 -> 98.10"


def _paise_2dp(text: str) -> int:
    """A cell holding a double like 76.650000000000006 -> 7665 paise."""
    return int((Decimal(text) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# =========================================================================================
# Parser goldens -- the five verified events, from the frozen snapshots
# =========================================================================================


@pytest.fixture(scope="module")
def nse_events() -> dict[tuple[str, date], ParsedEvent]:
    events: dict[tuple[str, date], ParsedEvent] = {}
    for tag in ("2016-01", "2023-07", "2024-10"):
        payload = ca.load_snapshot(CA_FIXTURES / f"nse_ca_{tag}.json")
        report = ca.parse_actions(ca.parse_nse_payload(payload))
        for event in report.events:
            events[(event.symbol, event.ex_date)] = event
    return events


def test_golden_kothari_bonus_parses_to_one_for_two(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """KOTHARIPRO, ex 2016-01-05, subject " Bonus 1:2" (chunk-3 card; verified Jan-2016)."""
    event = nse_events[("KOTHARIPRO", date(2016, 1, 5))]
    assert event.kind == KIND_BONUS
    assert (event.ratio_new, event.ratio_held) == (1, 2)
    assert event.subject == "Bonus 1:2"
    assert factor_for(event).k == Decimal(2) / Decimal(3)


def test_golden_greenply_split_parses_to_face_five_to_one(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """GREENPLY, ex 2016-01-06, "Face Value Split ... From Rs 5/- ... To Re 1/-"."""
    event = nse_events[("GREENPLY", date(2016, 1, 6))]
    assert event.kind == KIND_SPLIT
    assert (event.face_from_paise, event.face_to_paise) == (500, 100)
    assert factor_for(event).k == Decimal("0.2")


def test_golden_jmcproject_rights_parses_to_two_for_seven(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """JMCPROJECT, ex 2016-01-11, " Rights 2:7". The ratio is all the subject carries -- the
    issue price is not in it, which is QUESTIONS.md Q-6 and why no factor is built here."""
    event = nse_events[("JMCPROJECT", date(2016, 1, 11))]
    assert event.kind == KIND_RIGHTS
    assert (event.ratio_new, event.ratio_held) == (2, 7)
    assert event.rights_premium_paise is None and event.rights_price_paise is None
    with pytest.raises(ca.CorporateActionError, match="ISSUE PRICE"):
        factor_for(event, cum_close_paise=10000)


def test_golden_reliance_bonus_parses_to_one_for_one(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """RELIANCE, ex 2024-10-28, "Bonus 1:1" -> k = 1/2 (the card's Oct-2024 golden)."""
    event = nse_events[("RELIANCE", date(2024, 10, 28))]
    assert event.kind == KIND_BONUS
    assert (event.ratio_new, event.ratio_held) == (1, 1)
    assert factor_for(event).k == Decimal("0.5")


def test_golden_reliance_demerger_is_the_seed_of_the_demerger_table(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """RELIANCE -> Jio Financial, ex 2023-07-20: the seed CONTEXT 3.2 names, taken from the
    snapshot rather than hardcoded. No factor exists; the bias pair is suppressed instead."""
    event = nse_events[("RELIANCE", date(2023, 7, 20))]
    assert event.kind == KIND_DEMERGER
    assert event.subject == "Demerger"

    table = ca.demerger_table(nse_events.values())
    assert (event.symbol, event.ex_date) in [(d.symbol, d.ex_date) for d in table]
    with pytest.raises(ca.CorporateActionError, match="NO valid factor"):
        factor_for(event)


def test_golden_the_three_january_2016_subjects_are_the_only_priced_events_that_month(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """A completeness check on the window, so a parser that silently stopped early is seen."""
    payload = ca.load_snapshot(CA_FIXTURES / "nse_ca_2016-01.json")
    report = ca.parse_actions(ca.parse_nse_payload(payload))
    ratio_events = sorted(
        (event.symbol, event.ex_date.isoformat(), event.kind)
        for event in report.events
        if event.kind in (KIND_BONUS, KIND_SPLIT, KIND_RIGHTS)
    )
    assert ratio_events == [
        ("GREENPLY", "2016-01-06", KIND_SPLIT),
        ("JMCPROJECT", "2016-01-11", KIND_RIGHTS),
        ("KOTHARIPRO", "2016-01-05", KIND_BONUS),
    ]


def test_golden_no_frozen_window_produces_a_silent_drop() -> None:
    """The card's rule: an unparseable subject is COLLECTED, never dropped. Every row of
    every snapshot lands in exactly one bucket, and the buckets add up to the row count."""
    for tag in ("2016-01", "2023-07", "2024-10"):
        rows = ca.parse_nse_payload(ca.load_snapshot(CA_FIXTURES / f"nse_ca_{tag}.json"))
        report = ca.parse_actions(rows)
        assert report.total == len(rows), tag
        assert report.exceptions == (), f"NSE {tag} parsed with no exceptions"

        bse_rows = ca.parse_bse_csv(ca.load_snapshot(CA_FIXTURES / f"bse_ca_{tag}.csv"))
        bse_report = ca.parse_actions(bse_rows)
        assert bse_report.total == len(bse_rows), tag


def test_golden_every_bse_exception_is_a_genuine_one() -> None:
    """The exception report earns its keep on BSE, whose rows carry no series to filter on.

    These eight distinct subjects are the complete exception set over the three windows.
    Every one of them genuinely lacks what CONTEXT 4.2 needs -- a rights row with no ratio,
    a consolidation with no face values, a REIT/InvIT distribution, a sub-paisa dividend --
    so each is reported for a ruling rather than silently adjusted or silently ignored.
    """
    subjects: dict[str, int] = {}
    for tag in ("2016-01", "2023-07", "2024-10"):
        report = ca.parse_actions(
            ca.parse_bse_csv(ca.load_snapshot(CA_FIXTURES / f"bse_ca_{tag}.csv"))
        )
        for item in report.exceptions:
            subjects[item.action.subject.strip()] = subjects.get(item.action.subject.strip(), 0) + 1

    assert subjects == {
        "Right Issue of Equity Shares": 21,
        "Income Distribution (InvIT)": 6,
        "Resolution Plan -Suspension": 4,
        "Income Distribution REITs": 3,
        "Consolidation of Shares": 2,
        "Reduction of Capital": 1,
        "Final Dividend - Rs. - 0.0350": 1,
        "InvIT - Return of Capital": 1,
    }


# =========================================================================================
# Cross-source join (chunk-3 card part 6)
# =========================================================================================


@pytest.fixture(scope="module")
def comparisons() -> tuple[ca.SourceComparison, ...]:
    yahoo: list[ca.SplitRatio] = []
    for symbol, tag in (
        ("KOTHARIPRO", "2015-12"),
        ("GREENPLY", "2015-12"),
        ("RELIANCE", "2024-10"),
        ("RELIANCE", "2023-07"),
    ):
        yahoo.extend(
            ca.parse_yahoo_chart(
                ca.load_snapshot(CA_FIXTURES / f"yahoo_splits_{symbol}_{tag}.json"), symbol
            )
        )
    rows: list[ca.SourceComparison] = []
    for tag in ("2016-01", "2023-07", "2024-10"):
        nse = ca.parse_actions(
            ca.parse_nse_payload(ca.load_snapshot(CA_FIXTURES / f"nse_ca_{tag}.json"))
        )
        bse = ca.parse_actions(
            ca.parse_bse_csv(ca.load_snapshot(CA_FIXTURES / f"bse_ca_{tag}.csv"))
        )
        rows.extend(ca.cross_source_report(nse.events, bse.events, yahoo))
    return tuple(rows)


def test_golden_join_no_source_disagrees_anywhere_in_the_frozen_windows(
    comparisons: tuple[ca.SourceComparison, ...]
) -> None:
    """The card: "disagreements listed, none expected for these five events" -- and in fact
    none exists anywhere in the three windows, across 333 comparisons."""
    disagreements = [row for row in comparisons if row.verdict == ca.DISAGREE]
    assert disagreements == [], [(d.symbol, d.ex_date.isoformat(), d.note) for d in disagreements]
    assert len(comparisons) == 333


def test_golden_join_every_shared_ratio_is_identical(
    comparisons: tuple[ca.SourceComparison, ...]
) -> None:
    """Where two sources both imply a factor, the factors must be EQUAL -- no tolerance."""
    shared_bse = [row for row in comparisons if row.nse_k is not None and row.bse_k is not None]
    assert len(shared_bse) == 22
    assert all(row.nse_k == row.bse_k for row in shared_bse)

    shared_yahoo = [row for row in comparisons if row.yahoo_k is not None]
    assert len(shared_yahoo) == 3
    assert all(row.nse_k == row.yahoo_k for row in shared_yahoo)


def test_golden_join_the_five_verified_events(
    comparisons: tuple[ca.SourceComparison, ...]
) -> None:
    """The card's five events, source by source."""
    rows = {(row.symbol, row.ex_date): row for row in comparisons}

    kothari = rows[("KOTHARIPRO", date(2016, 1, 5))]
    assert (kothari.kind, kothari.verdict) == (KIND_BONUS, ca.AGREE)
    assert kothari.bse_purpose == "Bonus issue 1:2"
    assert kothari.yahoo_ratio == "3:2", "a 1:2 bonus reaches Yahoo as a 3:2 split"
    assert kothari.nse_k == kothari.bse_k == kothari.yahoo_k == Decimal(2) / Decimal(3)

    greenply = rows[("GREENPLY", date(2016, 1, 6))]
    assert (greenply.kind, greenply.verdict) == (KIND_SPLIT, ca.AGREE)
    assert greenply.bse_purpose == "Stock  Split From Rs.5/- to Rs.1/-"
    assert greenply.nse_k == greenply.bse_k == greenply.yahoo_k == Decimal("0.2")

    jmc = rows[("JMCPROJECT", date(2016, 1, 11))]
    assert (jmc.kind, jmc.verdict) == (KIND_RIGHTS, ca.NOT_FOUND)
    assert "no BSE row under this security name" in jmc.note
    assert jmc.yahoo_ratio is None, "CONTEXT 4.2: rights are invisible in Yahoo's stream"

    demerger = rows[("RELIANCE", date(2023, 7, 20))]
    assert (demerger.kind, demerger.verdict) == (KIND_DEMERGER, ca.NO_FACTOR)
    assert demerger.bse_purpose == "Spin Off"
    assert demerger.nse_k is None and demerger.yahoo_ratio is None

    reliance = rows[("RELIANCE", date(2024, 10, 28))]
    assert (reliance.kind, reliance.verdict) == (KIND_BONUS, ca.AGREE)
    assert reliance.bse_purpose == "Bonus issue 1:1"
    assert reliance.yahoo_ratio == "2:1"
    assert reliance.nse_k == reliance.bse_k == reliance.yahoo_k == Decimal("0.5")


def test_golden_adjustment_sanity_removes_the_fake_gap_at_every_verified_ex_date(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """CONTEXT 4.5 gate 3, applied to the daily store: "on every split/bonus ex-date in
    history, adjusted series must show |day-over-day gap| < 20% (unadjusted 1:10 split =
    -90% fake gap must disappear)".

    Real bhavcopy rows for the three verified events, DERIVED from the archived source CSVs
    (tests/fixtures/ca/ca_adjust_*.csv). The same check ran live over +/-10 trading days
    against the session's scratch store; the numbers are identical and are reported in
    PROGRESS.md. GREENPLY is the one the card calls out: a face-value 5->1 split prints a
    -79.63% drop that is entirely an artefact, and the factor removes all of it.
    """
    from acumen.bhavcopy import FORMAT_ARCHIVE, FORMAT_UDIFF

    store = _adjustment_store()
    cases = [
        ("KOTHARIPRO", date(2016, 1, 5), date(2016, 1, 4), 35540, 24010, Decimal("-32.44")),
        ("GREENPLY", date(2016, 1, 6), date(2016, 1, 5), 98525, 20070, Decimal("-79.63")),
        ("RELIANCE", date(2024, 10, 28), date(2024, 10, 25), 265570, 133435, Decimal("-49.76")),
    ]
    assert FORMAT_ARCHIVE and FORMAT_UDIFF  # both eras are represented above

    for symbol, ex_date, cum_date, cum_close, ex_close, expected_raw in cases:
        factor = factor_for(nse_events[(symbol, ex_date)])
        frame = store.daily(symbol, date(2015, 1, 1), date(2025, 1, 1))
        closes = {row.trade_date: int(row.close_paise) for row in frame.itertuples()}
        assert closes[cum_date] == cum_close and closes[ex_date] == ex_close

        raw_gap = _pct(closes[ex_date] - closes[cum_date], closes[cum_date])
        assert raw_gap.quantize(Decimal("0.01")) == expected_raw, symbol

        window = ca.factors_between([factor], cum_date, ex_date, symbol=symbol)
        assert len(window) == 1, "the ex-date factor lands in CONTEXT 3.2's half-open window"
        adjusted_cum = ca.adjust_pair(closes[cum_date], window)
        adjusted_gap = _pct(closes[ex_date] - adjusted_cum, adjusted_cum)
        assert abs(adjusted_gap) < 20, (symbol, str(adjusted_gap))

    greenply_raw = _pct(20070 - 98525, 98525)
    assert greenply_raw < -75, "the ~-80% fake drop the card names, before adjustment"
    assert abs(_pct(20070 - ca.adjust_pair(98525, [factor_for(nse_events[("GREENPLY", date(2016, 1, 6))])]),
                    ca.adjust_pair(98525, [factor_for(nse_events[("GREENPLY", date(2016, 1, 6))])]))) < 2


def test_golden_adjustment_sanity_holds_for_every_pair_in_the_window(
    nse_events: dict[tuple[str, date], ParsedEvent]
) -> None:
    """Not just the ex-date crossing: EVERY consecutive pair in the frozen window, adjusted
    pairwise as CONTEXT 3.2 does it, stays inside the 20% band."""
    store = _adjustment_store()
    factors = [
        factor_for(nse_events[key])
        for key in (
            ("KOTHARIPRO", date(2016, 1, 5)),
            ("GREENPLY", date(2016, 1, 6)),
            ("RELIANCE", date(2024, 10, 28)),
        )
    ]
    worst = Decimal(0)
    for symbol in ("KOTHARIPRO", "GREENPLY", "RELIANCE"):
        frame = store.daily(symbol, date(2015, 1, 1), date(2025, 1, 1))
        rows = [(row.trade_date, int(row.close_paise)) for row in frame.itertuples()]
        assert len(rows) >= 7, symbol
        for (previous, previous_close), (current, current_close) in zip(rows, rows[1:]):
            adjusted = ca.adjust_pair(
                previous_close, ca.factors_between(factors, previous, current, symbol=symbol)
            )
            gap = _pct(current_close - adjusted, adjusted)
            assert abs(gap) < 20, (symbol, previous, current, str(gap))
            worst = max(worst, abs(gap))
    assert worst > 0


def _adjustment_store():
    """Ingest the two DERIVED adjustment fixtures into an in-memory-ish temp store."""
    import tempfile

    from acumen.bhavcopy import (
        FORMAT_ARCHIVE,
        FORMAT_UDIFF,
        OUTCOME_PRESENT,
        DateOutcome,
        Download,
        parse_bhavcopy,
    )
    from acumen.daily_store import DailyStore

    root = Path(tempfile.mkdtemp(prefix="acumen_ca_")) / "store"
    store = DailyStore.at(root)
    for name, source_format in (
        ("ca_adjust_archive.csv", FORMAT_ARCHIVE),
        ("ca_adjust_udiff.csv", FORMAT_UDIFF),
    ):
        rows = parse_bhavcopy((CA_FIXTURES / name).read_text(encoding="utf-8"), source_format)
        for day in sorted({row.trade_date for row in rows}):
            same_day = tuple(row for row in rows if row.trade_date == day)
            store.ingest(
                Download(
                    DateOutcome(
                        trade_date=day,
                        outcome=OUTCOME_PRESENT,
                        source_format=source_format,
                        row_count=len(same_day),
                    ),
                    same_day,
                )
            )
    return store


def _pct(numerator: int, denominator: int) -> Decimal:
    return Decimal(numerator) / Decimal(denominator) * 100


def test_golden_join_matches_on_the_kind_because_one_date_can_carry_two_events(
    comparisons: tuple[ca.SourceComparison, ...]
) -> None:
    """ROTO declared a bonus AND a dividend on 2023-07-07; MAANALU a bonus AND a split on
    2023-07-27. Joining on the symbol-date alone reported both as disagreements when all
    three sources in fact agreed -- so the join matches the kind too."""
    roto = {
        row.kind: row
        for row in comparisons
        if row.symbol == "ROTO" and row.ex_date == date(2023, 7, 7)
    }
    assert sorted(roto) == ["bonus", "dividend"]
    assert roto["bonus"].verdict == ca.AGREE
    assert roto["bonus"].nse_k == roto["bonus"].bse_k == Decimal("0.5")
    # A dividend implies no price-free factor, so there is nothing to compare: the kinds
    # match on both sources and the row says so with NO_FACTOR rather than with AGREE.
    assert roto["dividend"].verdict == ca.NO_FACTOR
    assert roto["dividend"].bse_purpose == "Final Dividend - Rs. - 3.1500"

    maanalu = {
        row.kind: row
        for row in comparisons
        if row.symbol == "MAANALU" and row.ex_date == date(2023, 7, 27)
    }
    assert sorted(maanalu) == ["bonus", "split"]
    assert {row.verdict for row in maanalu.values()} == {ca.AGREE}
    assert maanalu["split"].nse_k == maanalu["split"].bse_k == Decimal("0.5")


# =========================================================================================
# The report entry point (chunk-3 card parts 2 and 6, as something a human can run)
# =========================================================================================


def test_the_report_runs_offline_over_the_frozen_windows(capsys) -> None:
    """It must reproduce exactly what the goldens above assert, and touch no network.

    conftest fails any test that opens a socket, so this also proves the default path reads
    the snapshots rather than the endpoints.
    """
    from acumen import ca_report

    assert ca_report.main([]) == 0
    out = capsys.readouterr().out
    counts_line = [line for line in out.splitlines() if "comparisons:" in line]
    assert counts_line and "agree=27" in counts_line[0]
    assert "DISAGREEMENTS: 0" in out
    assert "ON AN F&O-UNIVERSE SYMBOL: 0" in out
    assert "RELIANCE     2023-07-20  'Demerger'" in out
    assert "<-- F&O universe" in out


def test_the_report_counts_are_the_goldens(capsys) -> None:
    from acumen import ca_report

    nse, bse, yahoo = ca_report.load_frozen()
    counts = ca_report.print_report(nse, bse, yahoo, symbols=ca_report.universe_symbols())
    capsys.readouterr()
    assert counts["comparisons"] == 333
    assert counts["disagreements"] == 0
    assert counts["universe_exceptions"] == 0
    assert counts["demergers"] == 5
    assert counts["yahoo_splits"] == 3
    assert counts["pending"] == 296, "7 rights (Q-6) + 289 dividends (Q-7)"


def test_the_report_refuses_a_live_run_without_a_window(capsys) -> None:
    from acumen import ca_report

    assert ca_report.main(["--allow-network"]) == 2
    assert "needs --from and --to" in capsys.readouterr().out
