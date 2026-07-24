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
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "poc" / "data"

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
