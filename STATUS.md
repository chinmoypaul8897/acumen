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
chunk 5B: built (FIX-4 complete, unreviewed)  # prep(F1/F2/F7/F3)+runner+fix(routing upper bound)+FIX-2(three rulings)+FIX-3(three rulings)+FIX-4(Q-11 ADDENDUM 4 -- floors in UN-PROVABLE eras, the FINAL data ruling). 1253/0 offline. FIX-4 recorded + executed the ruling's four guards: (i) SIGNATURE-GATED hunting -- an event enters an un-provable era only by the gate-3 raw-gap-near-zero signature (|raw gap| < |k-1|/2, which admits EXACTLY the eleven rows the architect named and rejects the six that are a different defect) or a >=95% era failure-rate cliff over >=20 gated days; (ii) one fresh unknown -- the era's chain is built from PREVIOUSLY COMMITTED sources plus the floored event's own factor, and a second uncommitted event REFUSES the era rather than assuming `ours`; (iii) acceptance unchanged -- measured floors go back through the MAP BUILDER (floor-aware `build_map`), so an era stands only under the same 2-paise containment + unwidened gate-1 band, and a floored event stops consuming the probe-gap guard's degree of freedom (which is what unwinds a cascade); (iv) full provenance in the map. New outcome: a floor AT the ex-date ("absent from every chain in our history"), requiring three event-out probes, not one. Also: the Q-5 ruling reached the MEASUREMENT days -- a weekend-dated session is no longer probed OR folded into an era (NSE's Saturday 2024-05-18 sat inside BDL's and INOXWIND's probe windows at 0.259/0.196 volume recovery vs 0.500/0.246 beside it, and gate-1 must hold on EVERY probe day, so one excluded session made the only correct chain un-provable). 10 floors over 108 probes; 16 eras PROMOTED; 26 symbols hunted, 38 events admitted across 20. Recoveries: VEDL 26.3->87.2% (13 eras promoted), INOXWIND 24.2->99.2%, BDL 51.6->99.7%, HINDPETRO 72.7->82.1%, CANBK 95.5->99.4%; quarantined 10 -> 6 (ASTRAL, IEX, NESTLEIND, NTPC, UPL, VBL). Gate 3: 118 ex-dates, 17 -> 15 failures, each in the disclosed-residual register with its numbers. **Coverage 93.48% -> 95.24%; the >= 95% DoD is MET** (413,914 of 434,591 symbol-days). Residuals are DISCLOSED, not chased, per the ruling. REVIEW (type C) still owed.
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
