# STATUS.md — chunk state ledger

One line per chunk; this file is the ONLY place chunk state lives (plan.md §2).
Every session updates its own chunk's line before it ends (CLAUDE.md end-of-session duties).

States: `todo` | `built` | `reviewed-PASS` | `gate-closed(<evidence path>)`
No chunk may start while a dependency is not `reviewed-PASS` (plan.md §2).

chunk 0: reviewed-PASS
chunk 1: reviewed-PASS
chunk 2: reviewed-PASS
chunk 3: reviewed-PASS
chunk 4: reviewed-PASS
chunk 5A: reviewed-PASS  # QC (both personas) over 2d55919..9f06b6d: prep+build+fix(Q-10)+fix2(k_shares)+fix3(demerger-scope/Q-11 STOP)+fix4(Q-11 measured reconstruction). 911/0 offline; RELIANCE era-flip hand-verified; 9-mutant matrix (8 caught/1 equivalent); no secrets/AI-attribution/test-weakening. 2 LOW findings (map not yet wired to ingest CLI; factor-table fallback price-blind for special dividends) are chunk-5B-forward + gate-1-safe. tag chunk5A-pass
chunk 5B: built (FIX-3 complete, unreviewed)  # prep(F1/F2/F7/F3)+runner+fix(routing upper bound)+FIX-2(three rulings)+FIX-3(three rulings). 1200/0 offline. Daily store VERIFIED clean (319 months, 6606/6606 file-present dates carry rows, 10.53M rows, 0 anomalies). FIX-3 recorded + executed: Q-11 ADDENDUM 2 (vendor APPLICATION FLOORS -- one optional measured floor_date per event, binary-searched against the daily oracle, committed to the map with every probe and verdict; hunted only where failure is systematic), Q-11 ADDENDUM 3 (same-ex-date events compose into ONE compound node, k=product, share-count flags combined; an UNPARSED subject enters the map with candidates {measured, absent} only), and Q-12 ADDENDUM 2 (AUCTION RELIEF -- the deferred +5.0% ceiling answered: the ceiling STAYS, `volume_gate` and the band are byte-identical, and an above-ceiling failure with exactly-intact extremes, an exactly-matching opening print and a shortfall <= 20% is a separately-counted `auction-relief pass`). 6 floors MEASURED: CANBK split@2024-05-15 -> 2022-05-10, RELIANCE demerger@2023-07-20 -> 2022-01-05 (FIX-4's unpinned question), DIXON bonus@2021-03-18 -> 2018-10-01, NESTLEIND split@2024-01-05 -> 2021-12-31, JUBLFOOD split@2022-04-19 -> 2018-01-18, ASTRAL bonus@2023-03-14 -> 2021-03-08; 78 probes total, CANBK independently re-measured to the same date in the same 13 probes. Recoveries: CANBK 42.9->95.5%, MOTILALOFS 42.2->99.2%, PERSISTENT 44.6->99.3%, PNBHOUSING 69.0->99.3%, RELIANCE 82.2->99.1%, DIXON 87.8->99.0%, HAL 81.3->99.4%, PFC 94.5->99.5%, MOTHERSON 92.0->99.7%, ASTRAL 54.8->69.9%; quarantined 14 -> 10. BAJAJFINSV and COLPAL ingested for the FIRST time (2431/2429 days, both 99.4%). 432 auction-relief passes across 125 symbols. Gate 3: 118 ex-dates checked, 18 -> 17 failures, every one printed with its raw and adjusted gap. **Coverage 90.78% -> 93.48%; the >= 95% DoD is NOT MET** -- 5.20% of the shortfall is the 10 remaining quarantined symbols, 1.31% settled-symbol failures. Run COMPLETE and terminal for all 210 symbols at fetch date 2026-07-27. REVIEW (type C) still owed.
chunk 6: reviewed-PASS  # QC (both personas) over 8b053c2..6ed863c. 1099/0 from clean (1094 build + 5 reviewer probes). CONTEXT 3.3 REIMPLEMENTED from scratch by the reviewer: all 25 frozen poc_prorata values reproduced at worst 4.0e-13, the coarser tie direction moves exactly six; F6 rebuilt by hand at two ticks no fixture uses; 16-mutant matrix (14 caught, 3 survived -> all tripwired in tests/test_review6_probes.py); every number in the gate pack re-derived read-only from the frozen CSVs and the parquet stores incl. BHARTIARTL 2026-07-17's 1914.60 vs 1914.50; engine swept over 11,905 real stored symbol-days with 0 exceptions, EXACT volume conservation and the POC always inside [bottom, top]. B111-B121 all approved. 4 MEDIUM findings (2 spec silences for the architect: the gate's discriminating day is also a Q-13 tie day, and totalTicks' rounding MODE is a second unstated silence measured at 10 POC-moving days per 2,418; 2 coverage gaps, both CLOSED by kept reviewer tests) + 6 INFO/LOW; no CONTEXT deviation, no fix session needed. GATE STILL PENDING -- docs/gate_chunk6_poc_evidence.md, closed by Q42 (one BHARTIARTL reading with the rows countable answers Q42 and Q-13 together). tag chunk6-pass
chunk 7: todo
chunk 8: todo
chunk 9: todo
chunk 10: todo
chunk 11: todo
chunk 12: todo
chunk 13: todo
chunk 14: todo
chunk 15: todo
