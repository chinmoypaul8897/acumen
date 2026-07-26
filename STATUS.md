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
chunk 6: built  # POC engine (CONTEXT 3.3) as PURE functions: window slice (8-candle spec window, 9-candle alternative reachable only by the gate-evidence generator -- Q-8/Q42), TV row math (tpr>=1, closest-count direction, remainder row), prorata spreading in exact Fractions, POC = row midpoint with tie -> higher row. Validity = the AMENDED completeness rule (gate 1 only; no minute count anywhere -- the ast probe stays green). 1093/0 offline; F6 (both N, row edges + remainder shape), F7 (a) 5/5 anchors to +-0.01 AND all 25 frozen poc_prorata values, (b) prorata nearest the trader's reading on 5/5; volume-conservation property exact on all 25 days x both windows. NEW Q-13 (class A, OPEN, non-blocking): CONTEXT 3.3 does not say which way the ticks-per-row rounding goes on an exact TIE -- hit on 10.7%-20.0% of stored days, POC differs on every one; interim = the finer profile (the direction that reproduces all 25 frozen values), pinned by tests. TRADER GATE PENDING -- docs/gate_chunk6_poc_evidence.md (7 days under both windows, each first proven raw by gate 1 + an exact daily high/low match; BHARTIARTL 2026-07-17 is the one day that separates the two windows). Review type QC.
chunk 7: todo
chunk 8: todo
chunk 9: todo
chunk 10: todo
chunk 11: todo
chunk 12: todo
chunk 13: todo
chunk 14: todo
chunk 15: todo
