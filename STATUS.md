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
chunk 5B: todo
chunk 6: todo
chunk 7: todo
chunk 8: todo
chunk 9: todo
chunk 10: todo
chunk 11: todo
chunk 12: todo
chunk 13: todo
chunk 14: todo
chunk 15: todo
