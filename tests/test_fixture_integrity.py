"""Frozen-fixture tripwire -- added by the chunk-0 REVIEW session (docs/reviews/REVIEW_0.md).

CLAUDE.md rule 3 makes `poc/data/` FROZEN: never regenerated, never edited. The chunk-0
build only asserted that the files EXIST (tests/test_smoke.py), so a later session could
have rewritten, re-downloaded or line-ending-normalized any of them and every test would
still have passed.

These digests are the bytes CONTEXT 8 F7/F10 were calibrated on, verified by the review
session two independent ways:

* every working-tree file hashes identically to its git HEAD blob (28/28), and
* an independent reimplementation of the CONTEXT 3.3 row math reproduces all 25
  `poc_prorata` values in volume_poc_summary.csv exactly, including all five F7 anchors.

A failure here is NOT a flaky test. It means a frozen fixture changed, which invalidates
F7/F10 and requires an architect-signed spec change (CONTEXT 8, CLAUDE.md rule 3) -- never
a digest update to make the suite green again.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "poc" / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]

#: SHA-256 of every frozen file under tests/fixtures/, extended as chunks add them.
#:
#: chunk 1 (2026-07-24): `tick_sizes.json` is the architect's ruling on QUESTIONS.md Q-2
#: (F7's tick inputs, frozen so the fixture stops depending on a daily live dump);
#: `universe_snapshot.json` and `holidays_2026.json` are verbatim single pulls of the two
#: CONTEXT 4.1 endpoints, taken once during the chunk-1 build so the whole calendar/universe
#: suite runs offline (CLAUDE.md rule 3: fixtures under tests/fixtures/ are FROZEN).
#:
#: chunk 2 (2026-07-24): three DERIVED fixtures -- whole lines lifted byte-for-byte out of
#: real bhavcopy files, plus the outcome ledger of this session's bounded-window ingest. Each
#: source file's own SHA-256, its URL and the trimming rule are recorded in
#: tests/fixtures/PROVENANCE.md; committing the full 190 KB ZIPs per date was the alternative.
#:
#: chunk 3 prep (2026-07-24): one SYNTHETIC fixture. It is authored, not measured -- the Q-4
#: ruling names two cases (two whitelist series on one date; a symbol with no equity row at
#: all) that no bhavcopy committed here contains. PROVENANCE.md says so in the file's own
#: entry, and nothing in it may be cited as a fact about NSE.
#:
#: Unlike poc/data there is no exact-set assertion here: later chunks legitimately add
#: fixtures. What may never happen is one of these files CHANGING.
FROZEN_FIXTURES_SHA256: dict[str, str] = {
    "bhavcopy_archive_sample.csv": "40d0281ab08a84c25d5ae27237ab3769875e97bc2d29a7f698652799645ed185",
    "bhavcopy_udiff_sample.csv": "bd477ba42278705a9cde9d7807d04891d076bca0fb974ec9ccc1b6632177c6cd",
    "daily_ledger_window.csv": "73b97a05760c0c6fccabb65aa9b3907ed83cdfe192cfa5f3db85b2e66067067b",
    "holidays_2026.json": "798c545acc5351eb9ed84f353c1fcc665a26967426e3761b7097e7f3c7042424",
    "series_edge_cases_synthetic.csv": (
        "fcedeb9c22f9682fdcd99de3fb51196cc0753842c9f14761b5d4ccfb1e8bac5e"
    ),
    "tick_sizes.json": "61488842568ee632b528dfa3c5f6be44a771520a2aa02cd63cb76b7c0ee146b0",
    "universe_snapshot.json": "3eaa84baf758421fa57754c28dc32dd0a5bb864f8e02ccbab237ed05ef13f912",
    # chunk 3 (2026-07-25): the corporate-action sources CONTEXT 4.2 names. Ten VERBATIM
    # snapshots (one per source per window) and two DERIVED bhavcopy cuts for the
    # adjustment-sanity golden. Provenance in tests/fixtures/PROVENANCE.md.
    "ca/bse_ca_2016-01.csv": (
        "982fc2a6cee3c0012ff5248948959482e8d252be7720561ee632fd6f9a77d49c"
    ),
    "ca/bse_ca_2023-07.csv": (
        "c819ee25c44a679f7665cedc1b3630b093bc09c3cd3b703039c25af309888a22"
    ),
    "ca/bse_ca_2024-10.csv": (
        "c8815e985538aeb20d399b8a7c540736fae8aa58b56610cc0e0f8d0ba8ca93cf"
    ),
    "ca/ca_adjust_archive.csv": (
        "4061f0e6fffe2a64f07be8f868aa30fbb0a033d55d1f2cdc93f26a6f1e657768"
    ),
    "ca/ca_adjust_udiff.csv": (
        "f4e9ccd14ccbd46f248a131b081859d0f5ecd0a52a15738bb9c357a7acb27c66"
    ),
    "ca/nse_ca_2016-01.json": (
        "6bb9787d830d8234a23403c1441abd9f7430ec05902c80b7b492400dfe1616bd"
    ),
    "ca/nse_ca_2023-07.json": (
        "8a2c5d348e3a94bc3d6ee31bc1a5fef789954eef3fec57235ad9b18a8f5ab67e"
    ),
    "ca/nse_ca_2024-10.json": (
        "d064cda3fa2fe7e358ec8aca68c9ca7c5c648a3b0584f21d320be558c1aa13e0"
    ),
    "ca/yahoo_splits_GREENPLY_2015-12.json": (
        "cc7fc8a3718ff72ea0e58b7406dd702c8b06666c8a8d957d9282e93d165dd976"
    ),
    "ca/yahoo_splits_KOTHARIPRO_2015-12.json": (
        "03a70ddebedab6ea18ce48be238b08a587ae5e2a91a4195e1367cc112a541740"
    ),
    "ca/yahoo_splits_RELIANCE_2023-07.json": (
        "b2bdeb52c6617f328e02a385b6fc42d1cc17335e81567dd9a3d50c6ae8212763"
    ),
    "ca/yahoo_splits_RELIANCE_2024-10.json": (
        "f3d3a78111bd0f004ea88aacede81778610a0db8e017f0ae07a8d97984fafc9a"
    ),
    # chunk 4 prep (2026-07-25): three DERIVED fixtures for the 2020-07-13 data-quirk
    # round-trip. The archive cut is TCS + RELIANCE rows lifted byte-for-byte out of NSE's
    # real (malformed, '13-Jul-20') archive bhavcopy; the two SmartAPI files are verbatim
    # ONE_DAY getCandleData responses, frozen once during the chunk-4 prep evidence step.
    # Provenance (source, verification, the raw:adjusted ratio) in tests/fixtures/PROVENANCE.md.
    "quirk_2020-07-13_archive_cut.csv": (
        "a363b028dd0b4f03c53f4c08db458719636c20461bcf13b054476b6a22e35f90"
    ),
    "smartapi_oneday_TCS_2020-07-13.json": (
        "aee8f2042f66fb2342ca9ccc3a9eccf75eeca5ba6e5fd014e63eac93d32d6a7a"
    ),
    "smartapi_oneday_RELIANCE_2020-07-13.json": (
        "6598c12d1e97dfc8f098a4015e778ba7e2b6d725d1b43ead2f3773c28401ebdb"
    ),
    # chunk 4 (2026-07-25): the F9 bias goldens and the synthetic Rule-3 1-minute fixtures.
    # f9_tcs_daily.csv is a DERIVED cut of REAL TCS daily candles from the settled store (a
    # contiguous window so every pair resolves); f9_tcs_expected.csv is the hand-computed bias
    # per selected day WITH its candle numbers and rule reasoning. The SYNTH_2099-* minute CSVs
    # are SYNTHETIC (far-future date, SYNTH symbol) -- real-day Rule-3 verification is chunk 12.
    "f9_tcs_daily.csv": (
        "1b5e31d4b065899ce2f0204f9fe6082044fd818bf3e8f5e7f6cec03cac0b5dd8"
    ),
    "f9_tcs_expected.csv": (
        "b87672490579fad04410c26fa95825686be579a9f07629291c6c423a40da827d"
    ),
    "minute/SYNTH_2099-01-05_1min.csv": (
        "d5cf134f13c9aa2721f40f54d5a1dbbd05164dfbeb606bf5820ed16453711d02"
    ),
    "minute/SYNTH_2099-01-06_1min.csv": (
        "d234acb10a959473e7c11671a57172263973c681945b683715a803d8c078ccc9"
    ),
}

#: CONTEXT 4.2's own test ORACLE, frozen at docs/ (not under tests/fixtures/, because it is a
#: published document rather than a captured payload). F8 reads its worked examples directly.
FROZEN_ORACLE_SHA256: dict[str, str] = {
    "nse_adjustment_calculator.xlsx": (
        "ac79276d12a7f72bc614fa9ea574c6ba12dd54fda811641de4835dadb4544062"
    ),
}

#: SHA-256 of every frozen CSV, measured 2026-07-24 by the chunk-0 review session.
FROZEN_SHA256: dict[str, str] = {
    "DIXON_2026-07-14_1min.csv": "1b824e393d3938c9cbb4a339be342969c6a9ae8d5d8d596f68d4b37db45d42bd",
    "DIXON_2026-07-15_1min.csv": "8b0aa9c827adae20e93c0586e567023a844495a70ace3a7654e98c9028432a79",
    "DIXON_2026-07-16_1min.csv": "e3b338d6766bd7be7810403736413858fb9f48d5a446eabc7a12f9f4acc7cafb",
    "DIXON_2026-07-17_1min.csv": "cc74ce0cf09254c364a7241b940f5433967e3391e38d6b7db18504cb2369cd1a",
    "DIXON_2026-07-20_1min.csv": "d9b2d636824f63ce8dadcec0cd179ed46eb6b857efafbc11f0b6b77e618d63a1",
    "HDFCBANK_2026-07-14_1min.csv": "fe85bea11c7f660006ad79c6935a7cd921a78cfb417432e71e1f73e2241b3300",
    "HDFCBANK_2026-07-15_1min.csv": "2a0fad42b89f051b522a763889c3376a748520947472e407d64b4478dac4f199",
    "HDFCBANK_2026-07-16_1min.csv": "468a5f0c53c692092091abfb5d6a42758b70e421ff4bd13df411c30606e19c60",
    "HDFCBANK_2026-07-17_1min.csv": "c21476bed90b9bc5c68ade89d9da0ba854a50dfbf8ed1691fd5aee8c6e6be314",
    "HDFCBANK_2026-07-20_1min.csv": "1c4710ce84d7bd3d97b32a50a5c6d133ef702366df9d41c2e572b5fe8ee9165d",
    "MANAPPURAM_2026-07-14_1min.csv": "7593078b2ce58fd6c89606059d3d49506978849cbec920fc80fe9ad4ef8cc2ce",
    "MANAPPURAM_2026-07-15_1min.csv": "4e12b8adef6b93c2c8f0d6510588ad8723001fd37b84e28e2a875f1b64fa4138",
    "MANAPPURAM_2026-07-16_1min.csv": "f84a6a5320a2eca66c8782e907d2fb3e72dad78e766f3edb056f57d572328624",
    "MANAPPURAM_2026-07-17_1min.csv": "11d3a5c6a9b8e65ff51693d5c0da583555a116369384b78048f7c27c50d4b52a",
    "MANAPPURAM_2026-07-20_1min.csv": "7478786b761472e8d8b52b46e0dafb0df9c9bcd44b6dd09f64b3ee9eb3f398b7",
    "RELIANCE_2026-07-14_1min.csv": "5880509f59962769a7e47d767ec623488a1cfa652d1f741a6727691626ab3db4",
    "RELIANCE_2026-07-15_1min.csv": "2a690d7f469ad1ed0c53b74abb88205b7cee63dc908a16cec84d45f32b44279a",
    "RELIANCE_2026-07-16_1min.csv": "0cdb705b8b9ad289d8e2d9e063ea0708faccaf77cff64cc4d59527c5bbae902b",
    "RELIANCE_2026-07-17_1min.csv": "a1a313fa09d2018ff3163849b971d549372963cb8399d327a49ceac1c254a4bb",
    "RELIANCE_2026-07-20_1min.csv": "11ac7d01048250a82b515d87e65058306b930abc45d6e543b47270f9f2f68d46",
    "TCS_2026-07-14_1min.csv": "7a71d1254d093773d2962d08b840619a0208505bd43aa88ccede3b2d2bb6cb0a",
    "TCS_2026-07-15_1min.csv": "49eb937a176809a9fd139b87029416503a8bfec6344ea7b962fdfc23332e4fc1",
    "TCS_2026-07-16_1min.csv": "5f44377f7fadf21c5cd6a82060c6936904adb758b2e7c01acd79dcfac36255a0",
    "TCS_2026-07-17_1min.csv": "1d9931b768cd4b143635272e41ed42bb7d13d001a752fedfa173a084b978a3c7",
    "TCS_2026-07-20_1min.csv": "484a7102098ec748b59f3e9c421d9d3e255070bce20ff6b825859426bc3c3e17",
    "depth_probe_results.csv": "09dace0154a3ab4733c02e5648bbd1b16c8f1f71167bc301d329367fed0c4abd",
    "quality_report.csv": "2a41cd81c6cb9a0aa834a657561c12fb3d1808aad5ca4d488b6ce4ced373df2d",
    "volume_poc_summary.csv": "105ac10264463bb008b28cbb4a9bec836166cfaa72ba54e2b90e33b4fd44f749",
}


@pytest.mark.parametrize("name", sorted(FROZEN_SHA256))
def test_frozen_fixture_bytes_are_unchanged(name: str) -> None:
    path = DATA_DIR / name
    assert path.is_file(), f"frozen fixture is MISSING: poc/data/{name}"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == FROZEN_SHA256[name], (
        f"poc/data/{name} CHANGED. Frozen fixtures may never be regenerated or edited "
        "(CLAUDE.md rule 3); F7/F10 were calibrated on these exact bytes. Restore the file "
        "from git -- do not update this digest without an architect-signed CONTEXT 8 change."
    )


def test_no_fixture_was_added_or_removed() -> None:
    """The directed count is EXACTLY 28 CSVs -- 25 one-minute symbol-days + 3 PoC outputs."""
    found = {p.name for p in DATA_DIR.glob("*.csv")}
    assert found == set(FROZEN_SHA256), (
        f"poc/data CSV set changed. Unexpected: {sorted(found - set(FROZEN_SHA256))}; "
        f"missing: {sorted(set(FROZEN_SHA256) - found)}"
    )
    assert len(found) == 28


def test_minute_fixtures_carry_a_full_session() -> None:
    """375 one-minute candles 09:15-15:29 per day (CONTEXT 4.5 gate 2), header included."""
    for name in sorted(n for n in FROZEN_SHA256 if n.endswith("_1min.csv")):
        lines = (DATA_DIR / name).read_bytes().splitlines()
        assert len(lines) == 376, f"{name}: expected 375 candles + header, got {len(lines) - 1}"


def test_minute_fixtures_kept_their_crlf_line_endings() -> None:
    """`.gitattributes` marks poc/data/** as -text so the committed bytes survive checkout.

    If that guard is ever dropped on a core.autocrlf machine the CSVs get normalized to LF,
    which silently changes the calibrated bytes -- caught here as well as by the digests.
    """
    raw = (DATA_DIR / "TCS_2026-07-14_1min.csv").read_bytes()
    assert raw.count(b"\r\n") == 376, "frozen CSV lost its CRLF line endings"


@pytest.mark.parametrize("name", sorted(FROZEN_FIXTURES_SHA256))
def test_frozen_tests_fixture_bytes_are_unchanged(name: str) -> None:
    path = FIXTURES_DIR / name
    assert path.is_file(), f"frozen fixture is MISSING: tests/fixtures/{name}"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == FROZEN_FIXTURES_SHA256[name], (
        f"tests/fixtures/{name} CHANGED. Fixtures under tests/fixtures/ are FROZEN "
        "(CLAUDE.md rule 3): the endpoint snapshots are the exact bytes the calendar and "
        "universe goldens were computed from, and tick_sizes.json is an architect ruling. "
        "Restore the file from git -- re-pulling the endpoint is NOT a fix."
    )


@pytest.mark.parametrize("name", sorted(FROZEN_ORACLE_SHA256))
def test_the_frozen_oracle_bytes_are_unchanged(name: str) -> None:
    """CONTEXT 4.2: "our factors must reproduce" NSE's calculator. An oracle that can be
    regenerated is not an oracle -- these bytes are the ones F8 was checked against."""
    path = REPO_ROOT / "docs" / name
    assert path.is_file(), f"frozen oracle is MISSING: docs/{name}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN_ORACLE_SHA256[name], (
        f"docs/{name} CHANGED. Restore it from git; re-downloading it from NSE is NOT a fix "
        "(CLAUDE.md rule 3)."
    )


def test_the_corporate_action_snapshots_are_verbatim_payloads() -> None:
    """The CA snapshots must stay raw source responses -- the same rule as chunk 1's two.

    A snapshot that has been prettified, trimmed or annotated is no longer evidence of what
    the source returns, which is the only reason to freeze one. The two `ca_adjust_*.csv`
    files are the exception and are DERIVED, not verbatim: whole lines lifted out of real
    bhavcopy CSVs, declared as such in PROVENANCE.md.
    """
    nse = json.loads((FIXTURES_DIR / "ca" / "nse_ca_2016-01.json").read_text(encoding="utf-8"))
    assert isinstance(nse, list) and len(nse) == 19
    assert set(nse[0]) == {
        "bcEndDate", "bcStartDate", "caBroadcastDate", "comp", "exDate", "faceVal", "ind",
        "isin", "ndEndDate", "ndStartDate", "recDate", "series", "subject", "symbol",
    }
    assert all(row["caBroadcastDate"] is None for row in nse), (
        "QUESTIONS.md Q-7 rests on this field being empty; if a future pull carries it, the "
        "special-dividend question may be answerable from the source itself."
    )

    bse = (FIXTURES_DIR / "ca" / "bse_ca_2016-01.csv").read_text(encoding="utf-8")
    assert bse.startswith("Security Code,Security Name,Company Name,Ex Date,Purpose")

    yahoo = json.loads(
        (FIXTURES_DIR / "ca" / "yahoo_splits_KOTHARIPRO_2015-12.json").read_text(encoding="utf-8")
    )
    assert set(yahoo) == {"chart"} and yahoo["chart"]["error"] is None


def test_the_endpoint_snapshots_are_verbatim_payloads() -> None:
    """They must stay raw API responses -- no wrapper, no hand-edit, no reformatting.

    A snapshot that has been prettified or annotated is no longer evidence of what the
    endpoint actually returns, which is the only reason to freeze one.
    """
    universe = json.loads((FIXTURES_DIR / "universe_snapshot.json").read_text(encoding="utf-8"))
    assert set(universe) == {"data"}
    assert set(universe["data"]) == {"IndexList", "UnderlyingList"}

    holidays = json.loads((FIXTURES_DIR / "holidays_2026.json").read_text(encoding="utf-8"))
    assert "CM" in holidays and "FO" in holidays
    assert set(holidays["CM"][0]) == {
        "tradingDate",
        "weekDay",
        "description",
        "morning_session",
        "evening_session",
        "Sr_no",
    }


def test_the_derived_bhavcopy_fixtures_kept_nses_own_header() -> None:
    """A DERIVED fixture is only evidence if the lines it kept were not touched.

    Whole rows were dropped and nothing else -- so the header must still be NSE's, verbatim,
    including the trailing comma the old archive format ends its header with. A prettified
    or renamed column would make the parser test prove something about us, not about NSE.
    """
    udiff = (FIXTURES_DIR / "bhavcopy_udiff_sample.csv").read_text(encoding="utf-8")
    assert udiff.splitlines()[0] == (
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
        "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,"
        "LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,"
        "TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4"
    )

    archive = (FIXTURES_DIR / "bhavcopy_archive_sample.csv").read_text(encoding="utf-8")
    assert archive.splitlines()[0] == (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,"
        "TOTALTRADES,ISIN,"
    )


def test_every_frozen_fixture_is_documented_in_provenance() -> None:
    """A frozen file whose origin nobody wrote down is not evidence, it is furniture."""
    provenance = (FIXTURES_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    for name in FROZEN_FIXTURES_SHA256:
        assert f"`{name}`" in provenance, f"{name} is pinned but not documented"
