# tests/fixtures — provenance

What each frozen file is, where it came from, and (for trimmed files) exactly how it was
trimmed. Byte digests are pinned in `tests/test_fixture_integrity.py`; this file is the
human-readable half. CLAUDE.md rule 3: nothing here is ever regenerated or edited — a change
to any expected value requires an architect-signed spec change.

Three kinds of fixture live here, and the difference matters when judging evidence:

- **VERBATIM** — the complete, unmodified response of a source. Evidence of what the source
  actually returns.
- **DERIVED** — a *subset of lines* copied byte-for-byte out of a real file, so the parser
  can be tested offline without committing a 190 KB ZIP per date. Every retained line is
  unmodified; only whole lines were dropped. A derived fixture proves the parser reads real
  bytes correctly; it is **not** evidence about the whole file.
- **SYNTHETIC** — authored here, in a real file's shape, for a case no committed real file
  contains. It is evidence about OUR code's behaviour and about nothing else: a synthetic row
  can never be cited as a fact about NSE.

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

### `daily_ledger_window.csv` — the Q-3 outcome ledger

One row per calendar date of the two ingested windows (27 dates), copied out of the live
store's `ledger.parquet` after the run: `trade_date,outcome,source_format,http_status`. This
is what makes the derived-calendar golden reproducible offline — including the card's named
cases, `2026-07-19` = `confirmed-404` (a Sunday) and `2026-07-20` = `file-present`.

Attempt timestamps and URLs are deliberately NOT copied: they are run metadata, not
behaviour, and pinning them would make the fixture look like evidence about a moment rather
than about the calendar.

## chunk 3 prep (2026-07-24)

### `series_edge_cases_synthetic.csv` — **SYNTHETIC**, the Q-4 cases NSE did not supply

Authored for `tests/test_series_selection.py`, in the UDiFF shape (header line copied
verbatim from `bhavcopy_udiff_sample.csv`, 34 columns). Four invented symbols, none of them
real, all with ISINs in the unassigned `INE000…` space so nobody can mistake a row here for
market data:

| symbol | series | why it exists |
|---|---|---|
| `TWOWHITE` | `EQ` + `BE` on 2026-07-14 | the Q-4 ruling's "two whitelist series on one symbol-date -> raise loudly". No real bhavcopy in this repo carries it, and it should never occur — which is exactly why the raise needs a test. |
| `DEBTONLY` | `N1`, `N2` only | "no whitelist series -> empty result, not an error" — the IRFC-in-2018 shape (IRFC itself is not in the DERIVED archive fixture). |
| `ODDSERIES` | `EQ` + `Q1`, then `BE` | an UNKNOWN series to surface (`Q1`, which the chunk-2 session measured on the real UPL and which the ruling's families do not cover), plus an EQ -> BE move across two days to prove trade-for-trade is the same instrument. |

Prices are round numbers chosen so a wrong pick is obvious in a failure message (the block /
debt / partly-paid rows sit nowhere near the equity's). **This file is not evidence about NSE
and must never be cited as such** — every real-data claim in the Q-4 work is measured on the
two DERIVED bhavcopy fixtures instead.

## chunk 3 (2026-07-25) — `ca/`, the corporate-action sources

CONTEXT §4.2 names three sources; there is one snapshot per source per window, which is the
minimum possible (all three APIs are window-scoped, so one file cannot cover three windows).
Every one is **VERBATIM** — the exact response bytes, no wrapper, no reformatting — taken in a
single pass on **2026-07-25 (IST)** at one request per 4 seconds. The pacing is deliberately
slower than this repo's usual 1-per-2s because the operator's 25-year bhavcopy backfill was
running against the same infrastructure in another process; the combined rate stayed at the
usual ~1 request / 2s.

The windows are the ones the chunk-3 card names, chosen for five independently verified
events: **Jan-2016** (KOTHARIPRO bonus ex 05-Jan, GREENPLY face-value split ex 06-Jan,
JMCPROJECT rights ex 11-Jan), **Jul-2023** (RELIANCE demerger ex 20-Jul) and **Oct-2024**
(RELIANCE 1:1 bonus ex 28-Oct).

| File | Kind | Source URL (parameters as sent) | bytes |
|---|---|---|---|
| `ca/nse_ca_2016-01.json` | VERBATIM | `nseindia.com/api/corporates-corporateActions?index=equities&from_date=01-01-2016&to_date=31-01-2016` | 5,849 |
| `ca/nse_ca_2023-07.json` | VERBATIM | same, `01-07-2023`..`31-07-2023` | 106,619 |
| `ca/nse_ca_2024-10.json` | VERBATIM | same, `01-10-2024`..`31-10-2024` | 23,717 |
| `ca/bse_ca_2016-01.csv` | VERBATIM | `api.bseindia.com/BseIndiaAPI/api/CorpactCSVDownload/w?scripcode=&Fdate=20160101&TDate=20160131&Purposecode=&strSearch=S&ddlindustrys=&ddlcategorys=E&segment=0` | 3,018 |
| `ca/bse_ca_2023-07.csv` | VERBATIM | same, `20230701`..`20230731` | 42,476 |
| `ca/bse_ca_2024-10.csv` | VERBATIM | same, `20241001`..`20241031` | 12,910 |
| `ca/yahoo_splits_KOTHARIPRO_2015-12.json` | VERBATIM | `query1.finance.yahoo.com/v8/finance/chart/KOTHARIPRO.NS?period1=1448928000&period2=1456704000&interval=1d&events=split` | 6,894 |
| `ca/yahoo_splits_GREENPLY_2015-12.json` | VERBATIM | same shape, `GREENPLY.NS`, same window | 7,955 |
| `ca/yahoo_splits_RELIANCE_2024-10.json` | VERBATIM | same shape, `RELIANCE.NS`, `2024-10-01`..`2024-11-30` | 5,203 |
| `ca/yahoo_splits_RELIANCE_2023-07.json` | VERBATIM | same shape, `RELIANCE.NS`, `2023-07-01`..`2023-08-31` | 5,326 |

The last Yahoo file is frozen precisely because it is **empty of splits**: it is the evidence
that Yahoo's stream cannot see the RELIANCE demerger (CONTEXT §4.2 says rights and demergers
are invisible there), and a source that is silent must never be read as one that disagrees.

### `ca/ca_adjust_archive.csv` and `ca/ca_adjust_udiff.csv` — **DERIVED**

The bhavcopy rows the adjustment-sanity golden runs on, so it needs no live store. Header line
verbatim, plus every row whose symbol is one of the three verified events' symbols. Cut from
the CSVs archived by `scripts/backfill_daily.py --raw-dir` during this session (one live
fetch per date, 1 request / 4s, the same pacing as above).

| File | Symbols | Dates | Rows |
|---|---|---|---|
| `ca/ca_adjust_archive.csv` | KOTHARIPRO, GREENPLY | 2015-12-30 .. 2016-01-11 (9 trading days) | 18 |
| `ca/ca_adjust_udiff.csv` | RELIANCE | 2024-10-23 .. 2024-10-31 (7 trading days) | 7 |

Source CSV digests (SHA-256 of the CSV inside each published ZIP, as downloaded):

| Date | Format | SHA-256 | lines | kept |
|---|---|---|---|---|
| 2015-12-30 | archive | `2f54c9a5fc6542cdc885eafce25e11868b5bc2df07d0ed972e4762b2224ec311` | 1625 | 2 |
| 2015-12-31 | archive | `60236335f32d8f565e1250131773437c5a2416122f6d011c408b1071d36b4035` | 1607 | 2 |
| 2016-01-01 | archive | `f7b2c885bf9411ac1ba564325f5347816b78de7b672ba943aa769debf6915cc7` | 1608 | 2 |
| 2016-01-04 | archive | `2f773eda6f1c187432548d6d554e0a29d42895f7f8997049cabd74c619194326` | 1624 | 2 |
| 2016-01-05 | archive | `135b3bb5c5c0c6d139302179ff43893bf36902f99cbe3420df40efcbb06a11b7` | 1628 | 2 |
| 2016-01-06 | archive | `4bee07284baa0c520f49d68e850cd708dbf89cb88f6ecad416e73df475493b84` | 1622 | 2 |
| 2016-01-07 | archive | `83a72da633b5d4695385282ef674b7a9ab56072bde2b7bed97d584ddeddea92a` | 1633 | 2 |
| 2016-01-08 | archive | `eed87349dd0f4c7109ef57b29f3bc832db15f18016f28b3a966e81c7525e646b` | 1623 | 2 |
| 2016-01-11 | archive | `339268cce785cda8411a89631a29d3bbcc6ac8006f3eb1d4194eb15304426e11` | 1634 | 2 |
| 2024-10-23 | udiff | `343fcf400d871842823967d94b9f5b81a70ea32de9e30996c4a48ec61bd2a4b3` | 2860 | 1 |
| 2024-10-24 | udiff | `114e7c49cf48971a1360c15a94fe340c20795c89e29b1730c68183bd0994f2df` | 2844 | 1 |
| 2024-10-25 | udiff | `fed0742836df91b672c987d3310f81997daef865d1ac831546b0415ef5654866` | 2903 | 1 |
| 2024-10-28 | udiff | `a09ec1262af5a79a3679008f94fc32ccbefa047c15f9325fabbc35e75856ae7e` | 2921 | 1 |
| 2024-10-29 | udiff | `ddc1ef14bb4d279870360b6df2d7b7653d5970660e53d517624dd8fa204b8ba1` | 2866 | 1 |
| 2024-10-30 | udiff | `8b1e79b624f3dcfff87add9224cd4db90b9324d1bae7eecf83520ded998b42e7` | 2851 | 1 |
| 2024-10-31 | udiff | `4d8e4bba60ca43252bee6f24aaa63ff126638296f599ceefbbf94961bf71334c` | 2851 | 1 |

### The F8 oracle — `docs/nse_adjustment_calculator.xlsx`

Not under `tests/fixtures/` because it is a published document, not a captured payload, but
frozen on the same terms (digest pinned in `tests/test_fixture_integrity.py`). CONTEXT §4.2:
"NSE's official 'Adjustment of F&O contracts Calculator' XLSX — our factors must reproduce
it." Fetched once on 2026-07-25 from
`nsearchives.nseindia.com/web/sites/default/files/inline-files/Adjustment%20of%20Futures%20and%20Options%20contracts%20Calculator.xlsx`
(20,114 bytes, SHA-256 `ac79276d12a7f72bc614fa9ea574c6ba12dd54fda811641de4835dadb4544062`).
CONTEXT §4.2 gives the URL only as `nsearchives.nseindia.com/.../` — four candidate paths were
tried and this is the one that answered 200; the other three answered 404. Its three sheets
(BONUS, SPLIT, RIGHTS) are read cell-by-cell by `tests/test_ca_goldens.py`, so the numbers in
that file cannot drift from the oracle they quote.

### The 2020-07-13 data-quirk round-trip (chunk 4 prep, 2026-07-25)

Three DERIVED fixtures for `tests/test_data_quirks_roundtrip.py`, frozen during the chunk-4
prep evidence step (a one-off, read-only network fetch). Provenance and verification:

- **`quirk_2020-07-13_archive_cut.csv`** — the `TCS-EQ` and `RELIANCE-EQ` rows lifted
  byte-for-byte (header + 2 data rows) out of NSE's real archive bhavcopy for 2020-07-13
  (`nsearchives.nseindia.com/content/historical/EQUITIES/2020/JUL/cm13JUL2020bhav.csv.zip`,
  HTTP 200). That file is malformed: its `TIMESTAMP` column reads the two-digit `13-Jul-20`
  instead of `13-Jul-2020`, so every row parses to the year 0020 and the store validator
  correctly refused it (the operator's 25-year backfill left it as the ledger's only `error`).
  The cut PRESERVES the malformation verbatim — it is the input the quirk mechanism corrects.
- **`smartapi_oneday_TCS_2020-07-13.json`** / **`smartapi_oneday_RELIANCE_2020-07-13.json`** —
  verbatim SmartAPI `getCandleData` ONE_DAY responses (exchange NSE, tokens 11536 / 2885,
  `2020-07-13 00:00`..`15:30`), fetched once with the operator's read-only `.env` credentials.

Verification (why the quirk was trusted before the date was ingested): the corrected **TCS**
close 2220.00 equals the SmartAPI ONE_DAY close **to the paisa** (TCS had no intervening
corporate action, so raw == adjusted). The corrected **RELIANCE** close 1935.00 differs from
its SmartAPI ONE_DAY close 878.36 — ratio 0.454 — because SmartAPI ONE_DAY is corporate-action
BACK-ADJUSTED (1:1 bonus ex 2024-10-28 x RELIANCE->Jio demerger ex 2023-07-20), while the
bhavcopy is raw; RELIANCE's raw close was instead verified against the raw store neighbours
2020-07-10 (1878.05) and 2020-07-14 (1917.00), and the file's own PREVCLOSE column chains to
2020-07-10. This is recorded as OPEN-8 evidence in QUESTIONS.md. NOTE: the SmartAPI files carry
market prices only, no credential of any kind.
