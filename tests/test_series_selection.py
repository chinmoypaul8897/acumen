"""QUESTIONS.md Q-4, clause by clause: which series IS the instrument.

The architect's ruling, verbatim in QUESTIONS.md Q-4:

    "the instrument is the equity series. daily() selects per symbol-date by whitelist EQ,
    else BE, else BZ (same equity in trade-for-trade settlement -- matches the trader's
    TradingView chart). All other series (N* debt, P* partly-paid, BL block, and any other)
    are never the instrument: kept in store, ignored by queries. Two whitelist series on one
    symbol-date -> raise loudly. No whitelist series -> the equity did not exist/trade that
    day: empty result, not an error; a symbol's history starts at its first equity row
    (consistent with the per-symbol clamp). Unknown series encountered on F&O-universe
    symbols must be surfaced in the backfill/coverage report."

Every sentence of that paragraph has a test below, in order. Two of the cases do not exist in
any bhavcopy this repo holds -- a symbol carrying both EQ and BE, and a symbol carrying no
equity at all on a date inside the frozen window -- so they come from
`tests/fixtures/series_edge_cases_synthetic.csv`, which is labelled SYNTHETIC in
PROVENANCE.md and is emphatically not evidence about NSE. Everything else is measured on the
real DERIVED fixtures: NTPC's six series on 2018-01-01 and BIOCON's EQ+BL on 2026-07-14.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
    Download,
    parse_bhavcopy,
)
from acumen.daily_store import (
    INSTRUMENT_SERIES,
    SERIES_INSTRUMENT,
    SERIES_KNOWN_OTHER,
    SERIES_UNKNOWN,
    DailyStore,
    DailyStoreError,
    classify_series,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 7, 24, 21, 0, 0)


def _ingest(store: DailyStore, fixture: str, source_format: str) -> DailyStore:
    rows = parse_bhavcopy((FIXTURES / fixture).read_text(encoding="utf-8"), source_format)
    for day in sorted({row.trade_date for row in rows}):
        same_day = tuple(row for row in rows if row.trade_date == day)
        store.ingest(
            Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_PRESENT,
                    source_format=source_format,
                    http_status=200,
                    row_count=len(same_day),
                    attempted_at=NOW,
                ),
                same_day,
            )
        )
    return store


@pytest.fixture()
def real(tmp_path: Path) -> DailyStore:
    """The two DERIVED fixtures: real NSE bytes, both eras."""
    store = DailyStore.at(tmp_path / "real")
    _ingest(store, "bhavcopy_archive_sample.csv", FORMAT_ARCHIVE)
    _ingest(store, "bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
    return store


@pytest.fixture()
def synthetic(tmp_path: Path) -> DailyStore:
    """The SYNTHETIC edge cases no real bhavcopy in this repo carries."""
    return _ingest(
        DailyStore.at(tmp_path / "synthetic"), "series_edge_cases_synthetic.csv", FORMAT_UDIFF
    )


# --- "the instrument is the equity series" ------------------------------------------------


def test_the_whitelist_is_exactly_the_ruling_and_lives_in_one_place() -> None:
    assert INSTRUMENT_SERIES == ("EQ", "BE", "BZ")


def test_six_series_on_one_date_resolve_to_the_equity_row(real: DailyStore) -> None:
    """NTPC 2018-01-01: EQ plus five listed debt series (the case REVIEW_2 measured)."""
    stored = real.frame(["NTPC"], date(2018, 1, 1), date(2018, 1, 1))
    assert sorted(stored["series"]) == ["EQ", "N4", "N6", "N7", "NB", "NC"], "all six stored"

    frame = real.daily("NTPC", date(2018, 1, 1), date(2018, 1, 2))
    assert list(frame["trade_date"]) == [date(2018, 1, 1), date(2018, 1, 2)]
    assert set(frame["series"]) == {"EQ"}


def test_the_block_deal_series_is_ignored(real: DailyStore) -> None:
    """BIOCON 2026-07-14 carried a real block-deal print at 400.00 beside its equity."""
    frame = real.daily("BIOCON", date(2026, 7, 14), date(2026, 7, 14))
    assert len(frame) == 1 and frame.iloc[0].series == "EQ"
    assert int(frame.iloc[0].close_paise) != 40000, "the BL print must not be the candle"


def test_a_partly_paid_series_is_ignored(real: DailyStore) -> None:
    """JSWSTEEL 2018: EQ plus P2 partly-paid shares, which trade at a fraction of the price."""
    frame = real.daily("JSWSTEEL", date(2018, 1, 1), date(2018, 1, 2))
    assert set(frame["series"]) == {"EQ"}
    assert len(frame) == 2


def test_a_trade_for_trade_day_is_still_the_instrument(synthetic: DailyStore) -> None:
    """ODDSERIES trades EQ on the 14th and BE on the 15th -- one continuous candle series.

    This is the reason BE and BZ are on the whitelist at all: a stock moved to trade-for-trade
    settlement is the SAME equity and still appears on the trader's TradingView chart.
    """
    frame = synthetic.daily("ODDSERIES", date(2026, 7, 14), date(2026, 7, 15))
    assert list(frame["series"]) == ["EQ", "BE"]
    assert list(frame["trade_date"]) == [date(2026, 7, 14), date(2026, 7, 15)]


# --- "two whitelist series on one symbol-date -> raise loudly" ----------------------------


def test_two_whitelist_series_on_one_date_raise_loudly(synthetic: DailyStore) -> None:
    """SYNTHETIC by necessity: no real bhavcopy here carries EQ and BE on one symbol-date.

    If it ever happens the whitelist itself is wrong, so the ruling calls for a loud failure
    rather than a ranking -- and the message has to name what it found.
    """
    with pytest.raises(DailyStoreError) as excinfo:
        synthetic.daily("TWOWHITE", date(2026, 7, 14), date(2026, 7, 14))
    message = str(excinfo.value)
    assert "more than one WHITELIST series" in message
    assert "'EQ'" in message and "'BE'" in message
    assert "Q-4" in message

    other_day = synthetic.daily("TWOWHITE", date(2026, 7, 15), date(2026, 7, 15))
    assert len(other_day) == 1, "the clash is per date, and does not poison the rest"


# --- "no whitelist series -> empty result, not an error" ----------------------------------


def test_a_symbol_with_no_equity_row_answers_empty_not_error(synthetic: DailyStore) -> None:
    """DEBTONLY carries two NCD series and no equity -- the IRFC-in-2018 shape.

    "The equity did not exist/trade that day: empty result, not an error." A rule of the form
    "take the highest-volume row" would have returned a DEBENTURE's price series here, and
    nothing downstream would have noticed.
    """
    stored = synthetic.frame(["DEBTONLY"], date(2026, 7, 14), date(2026, 7, 15))
    assert sorted(set(stored["series"])) == ["N1", "N2"], "the rows are kept in the store"

    frame = synthetic.daily("DEBTONLY", date(2026, 7, 14), date(2026, 7, 15))
    assert frame.empty
    assert list(frame.columns) == list(stored.columns), "empty, but the full column set"


def test_a_symbols_history_starts_at_its_first_equity_row(synthetic: DailyStore) -> None:
    """ODDSERIES has an equity row on both dates; DEBTONLY on neither. The clamp follows."""
    assert len(synthetic.daily("ODDSERIES", date(2026, 7, 14), date(2026, 7, 15))) == 2
    assert synthetic.daily("DEBTONLY", date(2026, 7, 14), date(2026, 7, 15)).empty


def test_the_explicit_series_escape_still_reaches_the_ignored_rows(real: DailyStore) -> None:
    """Ignored is not deleted: an audit of the block-deal or debt rows is still one call away."""
    debt = real.daily("NTPC", date(2018, 1, 1), date(2018, 1, 1), series="N4")
    assert len(debt) == 1 and debt.iloc[0].series == "N4"
    block = real.daily("BIOCON", date(2026, 7, 14), date(2026, 7, 14), series="BL")
    assert len(block) == 1 and int(block.iloc[0].close_paise) == 40000


# --- "unknown series ... must be surfaced in the backfill/coverage report" ----------------


@pytest.mark.parametrize(
    ("series", "kind"),
    [
        ("EQ", SERIES_INSTRUMENT),
        ("BE", SERIES_INSTRUMENT),
        ("BZ", SERIES_INSTRUMENT),
        ("eq", SERIES_INSTRUMENT),
        ("BL", SERIES_KNOWN_OTHER),
        ("N1", SERIES_KNOWN_OTHER),
        ("NC", SERIES_KNOWN_OTHER),
        ("ND", SERIES_KNOWN_OTHER),
        ("P1", SERIES_KNOWN_OTHER),
        ("P2", SERIES_KNOWN_OTHER),
        ("Q1", SERIES_UNKNOWN),
        ("GB", SERIES_UNKNOWN),
        ("IV", SERIES_UNKNOWN),
        ("", SERIES_UNKNOWN),
    ],
)
def test_the_classifier_matches_the_families_the_ruling_names(series: str, kind: str) -> None:
    """The ruling names three families as never-the-instrument; everything else is UNKNOWN.

    Q1 is the interesting row: the chunk-2 session measured UPL carrying it on 2018-01-01
    (QUESTIONS.md Q-4's own evidence table) and the ruling does not name it, so it is
    reported rather than quietly folded into "partly paid".
    """
    assert classify_series(series) == kind


def test_the_series_report_classifies_every_series_it_finds(real: DailyStore) -> None:
    report = real.series_report(["NTPC", "JSWSTEEL", "BIOCON"], date(2018, 1, 1), date(2026, 7, 20))
    by_series = dict(zip(report["series"], report["kind"]))
    assert by_series["EQ"] == SERIES_INSTRUMENT
    assert by_series["N4"] == SERIES_KNOWN_OTHER
    assert by_series["P2"] == SERIES_KNOWN_OTHER
    assert by_series["BL"] == SERIES_KNOWN_OTHER
    assert set(report["kind"]) <= {SERIES_INSTRUMENT, SERIES_KNOWN_OTHER, SERIES_UNKNOWN}

    ntpc = report[report["symbol"] == "NTPC"]
    assert set(ntpc["series"]) == {"EQ", "N4", "N6", "N7", "NB", "NC", "ND"}
    assert int(ntpc[ntpc["series"] == "ND"].iloc[0].rows) == 1, "ND appears on 02-Jan only"


def test_an_unknown_series_is_surfaced_and_never_chosen(synthetic: DailyStore) -> None:
    """ODDSERIES carries Q1 -- not a family the ruling names -- on 2026-07-14."""
    unknown = synthetic.unknown_series(["ODDSERIES", "DEBTONLY"], date(2026, 7, 14), date(2026, 7, 15))
    assert list(unknown["symbol"]) == ["ODDSERIES"]
    assert list(unknown["series"]) == ["Q1"]
    assert list(unknown["kind"]) == [SERIES_UNKNOWN]
    assert list(unknown["first_date"]) == [date(2026, 7, 14)]

    frame = synthetic.daily("ODDSERIES", date(2026, 7, 14), date(2026, 7, 14))
    assert set(frame["series"]) == {"EQ"}, "surfaced, and still not the instrument"


def test_the_real_fixtures_carry_no_unknown_series(real: DailyStore) -> None:
    """Everything in the frozen windows is either the equity or a family the ruling names."""
    assert real.unknown_series(None, date(2018, 1, 1), date(2026, 7, 20)).empty


def test_the_report_is_empty_rather_than_broken_when_the_store_is(tmp_path: Path) -> None:
    empty = DailyStore.at(tmp_path / "nothing")
    assert empty.series_report(["TCS"], date(2026, 7, 1), date(2026, 7, 31)).empty
    assert empty.unknown_series(["TCS"], date(2026, 7, 1), date(2026, 7, 31)).empty


# --- the ruling must not have moved anything else -----------------------------------------


def test_frame_is_unchanged_and_still_returns_every_series(real: DailyStore) -> None:
    """`daily()` selects; `frame()` does not. Chunk 2's "store everything" is intact."""
    frame = real.frame(None, date(2018, 1, 1), date(2018, 1, 2))
    assert len(frame) == 20, "every row of both 2018 dates, all series"


def test_a_single_series_symbol_is_untouched(real: DailyStore) -> None:
    """TCS carries only EQ, so the ruling changes nothing for it -- including the golden."""
    frame = real.daily("TCS", date(2026, 7, 20), date(2026, 7, 20))
    assert len(frame) == 1
    assert int(frame.iloc[0].close_paise) == 225110
    assert int(frame.iloc[0].volume) == 2202693


def test_selection_happens_before_the_duplicate_check_not_instead_of_it(
    synthetic: DailyStore,
) -> None:
    """Two rows of the SAME whitelist series on one date is a damaged store, not a Q-4 case."""
    row = DailyRow(
        trade_date=date(2026, 7, 16),
        symbol="TWOWHITE",
        series="EQ",
        open_paise=1,
        high_paise=1,
        low_paise=1,
        close_paise=1,
        volume=1,
    )
    synthetic.write_rows(date(2026, 7, 16), [row, row])
    with pytest.raises(DailyStoreError, match="more than one"):
        synthetic.daily("TWOWHITE", date(2026, 7, 16), date(2026, 7, 16))
