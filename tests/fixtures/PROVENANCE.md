# tests/fixtures — provenance

What each frozen file is, where it came from, and (for trimmed files) exactly how it was
trimmed. Byte digests are pinned in `tests/test_fixture_integrity.py`; this file is the
human-readable half. CLAUDE.md rule 3: nothing here is ever regenerated or edited — a change
to any expected value requires an architect-signed spec change.

Two kinds of fixture live here, and the difference matters when judging evidence:

- **VERBATIM** — the complete, unmodified response of a source. Evidence of what the source
  actually returns.
- **DERIVED** — a *subset of lines* copied byte-for-byte out of a real file, so the parser
  can be tested offline without committing a 190 KB ZIP per date. Every retained line is
  unmodified; only whole lines were dropped. A derived fixture proves the parser reads real
  bytes correctly; it is **not** evidence about the whole file.

---

## chunk 1 (2026-07-24)

| File | Kind | Source |
|---|---|---|
| `universe_snapshot.json` | VERBATIM | `https://www.nseindia.com/api/underlying-information`, single live pull 2026-07-24. 210 underlyings + 5 indexes. |
| `holidays_2026.json` | VERBATIM | `https://www.nseindia.com/api/holiday-master?type=trading`, single live pull 2026-07-24. All 12 segments; CM = 20 holidays, all in 2026. |
| `tick_sizes.json` | authored | The architect's QUESTIONS.md Q-2 ruling (option a). Five measured ticks in rupees, tests only. |

## chunk 2 (2026-07-24)

All three are **DERIVED**, from the bounded-window live ingest this session ran
(`scripts/backfill_daily.py`, 2026-07-13..2026-07-24 and 2018-01-01..2018-01-15). The source
files are NSE bhavcopy ZIPs published under CONTEXT 4.1; the SHA-256 below is of the CSV
*inside* each ZIP, as downloaded.

### `bhavcopy_udiff_sample.csv` — UDiFF format (CONTEXT 4.1, "since Jul-2024")

Header line verbatim (34 columns, identical across all five source files, asserted at
extraction time), plus every row whose `TckrSymb` is one of **TCS, RELIANCE, HDFCBANK,
DIXON, MANAPPURAM** (the five symbols `poc/data` holds frozen SmartAPI minutes for, so the
cross-source golden can run offline) or **BIOCON** (the only F&O underlying in the 2026
window that NSE published under two series on one date — real data for the ambiguity guard).
31 rows over 5 dates.

| Source file | URL | SHA-256 of the CSV | lines | rows kept |
|---|---|---|---|---|
| `BhavCopy_NSE_CM_0_0_0_20260714_F_0000.csv` | `nsearchives.nseindia.com/content/cm/…` | `af036a89d78d8ad5b112a449825c6458532b4270ab635e59954a4628c985b822` | 3419 | 7 |
| `…20260715…` | same pattern | `f073234ab734fbd679755c485cd607bec220bfe77fa2eebf4e605766386f5a19` | 3410 | 6 |
| `…20260716…` | same pattern | `8f9ee750381b764dfdebafce8164ea73a3385cbd1bfbba61ef9418e30969b7d1` | 3440 | 6 |
| `…20260717…` | same pattern | `978c5eb70a9a0dc852b5c97a93b583090fb3deea0cf0eef555a3f3d9a0eb339c` | 3427 | 6 |
| `…20260720…` | same pattern | `f52d8dfe50807d3303743434188831115eee268b4bb7539b00ed5c1cdb714ac5` | 3396 | 6 |

The TCS 2026-07-20 line in this file is the chunk-2 card's golden row: close `2251.10`,
volume `2,202,693` — independently verified in `docs/RESULTS.md` section A against a
SmartAPI `ONE_DAY` candle.

### `bhavcopy_archive_sample.csv` — old archive format (verified back to 2000)

Header line verbatim (13 columns + NSE's trailing comma), plus every row whose `SYMBOL` is
**TCS, RELIANCE, NTPC or JSWSTEEL**. NTPC and JSWSTEEL are there for their non-EQ series
(`N4`, `N6`, `P2`) — the same multi-series reality as BIOCON, in the old format. 20 rows over
2 dates.

| Source file | URL | SHA-256 of the CSV | lines | rows kept |
|---|---|---|---|---|
| `cm01JAN2018bhav.csv` | `nsearchives.nseindia.com/content/historical/EQUITIES/2018/JAN/…` | `f755fa3a8f6cd0b867dfb848e8daf1f460c6f586a983d60658aa816e2f50cf87` | 1873 | 10 |
| `cm02JAN2018bhav.csv` | same pattern | `3ed9eb8dab896dd39ffb16a0d5aa99f8fb4e0477cfe97ddda29494285cb36acc` | 1857 | 10 |

Note: the 2000-era header is SHORTER still — `SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,
PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,` with no `TOTALTRADES` and no `ISIN` (verified live
against `cm03JAN2000bhav.csv.zip` on 2026-07-24), which is why the parser treats both as
optional. That file is not committed; the shape is asserted by a synthetic test instead.
