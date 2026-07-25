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
chunk 5A: built  # + chunk5A-fix (Q-10 un-adjust) + chunk5A-fix2 (k_shares volume split; RELIANCE demerger probe), unreviewed -- joins the 5A review
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
