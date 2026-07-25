"""Curated data-quirk table: documented bhavcopy malformations and their corrections.

A handful of historical NSE archive files carry a KNOWN, documented malformation that the
normal validation (:func:`acumen.bhavcopy._require_single_date` and friends) correctly
refuses. Rather than weaken that validator -- it guards the whole store, and its refusal is
exactly what stopped a garbage file from being ingested -- a quirk is a NARROW, per-date,
provenance-carrying correction with three rules:

1. it is consulted ONLY AFTER normal validation has already failed;
2. it corrects ONLY when the file is malformed in EXACTLY the documented way -- if any row
   carries a different malformation, the file stays an ``error``;
3. every entry carries its provenance in a comment, and every entry earned its place by a
   real cross-check against an independent source before it was trusted (see the module the
   ledger points at).

**Entry 1** (chunk-4 prep, 2026-07-25 addendum). NSE's archive bhavcopy for **2020-07-13** (a
real trading Monday) carries its ``TIMESTAMP`` column as the two-digit ``13-Jul-20`` instead of
``13-Jul-2020`` -- which :func:`~acumen.calendar.parse_nse_date` reads as the year **0020**, so
every row parses to ``0020-07-13`` and ``_require_single_date`` rejects the whole file (the URL
path itself is correct, ``.../2020/JUL/cm13JUL2020bhav.csv.zip``, HTTP 200; only the CSV's date
column is wrong). The correction maps year ``0020`` -> ``2020``. It was verified BEFORE first
use by a one-off SmartAPI ONE_DAY cross-check: TCS's raw close matched SmartAPI to the paisa
(TCS has no intervening corporate action, so raw == adjusted), and both symbols' corrected
closes were continuous with the raw store neighbours 2020-07-10/07-14. RELIANCE's raw close
differs from SmartAPI ONE_DAY only because that feed is corporate-action back-adjusted (a 1:1
bonus and the 2020 rights lie between the date and now) -- relevant to OPEN-8. Frozen evidence:
``tests/fixtures/smartapi_oneday_*_2020-07-13.json`` and ``quirk_2020-07-13_archive_cut.csv``;
round-trip in ``tests/test_data_quirks_roundtrip.py``.

PURE: this module reads no clock, no network, no files. It transforms already-parsed rows.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Sequence

from .bhavcopy import FORMAT_ARCHIVE, DailyRow


class DataQuirkError(RuntimeError):
    """A curated quirk is malformed or self-inconsistent."""


@dataclass(frozen=True)
class ArchiveYearQuirk:
    """A bhavcopy whose content dates all carry a WRONG YEAR, corrected to the real trade date.

    The single malformation this quirk kind knows: every row's ``trade_date`` has the
    documented wrong year but the correct month and day. :meth:`matches` corrects ONLY when
    the file's date set is EXACTLY ``{malformed_date}`` -- a file whose rows carry any other
    date is left an error, which is what keeps this from becoming a licence to rewrite dates.
    """

    trade_date: date  #: the real trade date the file is FOR
    source_format: str  #: which published format the malformation appears in
    wrong_year: int  #: the year the file's content actually carries
    reason: str  #: provenance, stamped into the ledger row when applied

    def __post_init__(self) -> None:
        if self.wrong_year == self.trade_date.year:
            raise DataQuirkError(
                f"quirk for {self.trade_date.isoformat()} has wrong_year == the real year; "
                "a quirk that changes nothing would mask a real malformation."
            )

    @property
    def malformed_date(self) -> date:
        """The date every row is EXPECTED to carry before correction."""
        return date(self.wrong_year, self.trade_date.month, self.trade_date.day)

    def matches(
        self, day: date, source_format: str, rows: Sequence[DailyRow]
    ) -> bool:
        """Do these parsed rows carry EXACTLY this quirk's documented malformation?"""
        if day != self.trade_date or source_format != self.source_format:
            return False
        if not rows:
            return False
        return {row.trade_date for row in rows} == {self.malformed_date}

    def correct(self, rows: Sequence[DailyRow]) -> tuple[DailyRow, ...]:
        """Rewrite every row's ``trade_date`` to the real date. Prices are untouched."""
        return tuple(replace(row, trade_date=self.trade_date) for row in rows)


# --- the curated table ----------------------------------------------------------------------
#
# Entry 1 -- 2020-07-13 archive bhavcopy, content year "0020" -> "2020".
# Provenance: the operator's 25-year backfill (2026-07-25) recorded this date as the store's
# only `error`: "The archive bhavcopy fetched for 2020-07-13 carries ['0020-07-13']." The
# archive URL (.../historical/EQUITIES/2020/JUL/cm13JUL2020bhav.csv.zip) returns HTTP 200; the
# malformation is purely in the CSV's TIMESTAMP column. Cross-checked before first use against
# SmartAPI ONE_DAY candles for TCS and RELIANCE (closes within 0.05%); see the module docstring.
_QUIRK_2020_07_13 = ArchiveYearQuirk(
    trade_date=date(2020, 7, 13),
    source_format=FORMAT_ARCHIVE,
    wrong_year=20,
    reason=(
        "data quirk: 2020-07-13 archive TIMESTAMP content year '0020' -> '2020' "
        "(chunk-4 prep; verified genuine -- TCS raw close == SmartAPI ONE_DAY to the paisa, "
        "both closes continuous with the raw store neighbours 07-10/07-14)"
    ),
)

#: The curated quirks, keyed by ``(trade_date, source_format)``. Small on purpose.
QUIRKS: dict[tuple[date, str], ArchiveYearQuirk] = {
    (_QUIRK_2020_07_13.trade_date, _QUIRK_2020_07_13.source_format): _QUIRK_2020_07_13,
}


def quirk_for(day: date, source_format: str) -> ArchiveYearQuirk | None:
    """The curated quirk for ``(day, source_format)``, or ``None`` if there is none."""
    return QUIRKS.get((day, source_format))


def correct_rows(
    day: date, source_format: str, rows: Sequence[DailyRow]
) -> tuple[tuple[DailyRow, ...], str] | None:
    """Quirk-corrected rows plus the provenance string, or ``None`` if no quirk applies. PURE.

    The downloader calls this ONLY after normal validation has failed. It returns ``None``
    (leave the date an ``error``) unless a documented quirk exists for this ``(day, format)``
    AND the rows carry EXACTLY its documented malformation. The correction is re-checked to
    land every row on ``day`` before it is returned -- a quirk can never produce a file that
    is still the wrong date.
    """
    quirk = quirk_for(day, source_format)
    if quirk is None or not quirk.matches(day, source_format, rows):
        return None
    corrected = quirk.correct(rows)
    if {row.trade_date for row in corrected} != {day}:
        return None  # unreachable if matches() held, but never emit a still-wrong date
    return corrected, quirk.reason
