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
chunk 5B: built (run in progress)  # prep(F1/F2/F7/F3)+runner+fix(routing upper bound)+FIX-2(three architect rulings). 1021/0 offline. Daily store VERIFIED clean (319 months, 6606/6606 file-present dates carry rows, 10.53M rows, 0 anomalies). FIX-2 recorded + executed: Q-12 (volume estimator = MINIMUM over price-passing probe days, min 3, else no measured candidate; the chosen PRICE factor joins the volume candidate set; order ours > price-factor > measured > absent; band UNWIDENED) -- CLOSED; the CONTEXT 4.5/7-E4 completeness amendment (a missing minute on a gate-1-PASSING day is a no-trade minute, not missing data; negative values added as a trigger; E4's minute-count trigger retired; no liquidity filter invented) -- architect-owned, effective by its QUESTIONS.md record; and the Q-12 addendum (quarantine recovery reroute + failure-pattern analysis; the +5.0% ceiling FLAGGED with per-symbol evidence, NOT tuned). Applied to the already-fetched store with no stored candle re-downloaded. Recoveries: ABB 67.2->99.4%, ADANIENT 8.1->98.8%, AUBANK 45.9->99.8%, BEL 39.3->89.4%, APLAPOLLO 77.8->96.4%, BLUESTARCO 52.5->99.1%; quarantined 9 -> 3. Coverage over the first 20 symbols: gate 1 85.80% -> 96.63%. Run LIVE at hand-off (57/210), resumable with the same command.
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
