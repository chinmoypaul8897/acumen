# chunk 14 -- THE PARITY REPORT

Run at 2026-08-14T05:06:28 from `docs/evidence/chunk14_parity.py`. READ-ONLY over the stores.

CONTEXT section 6: *"One engine, two modes ... same code path, guaranteed no
backtest/live drift"*, qualified by CONTEXT 4.7: *"Section 6 parity is judged on
oracle-passing days; a live-alerted day the oracle later refuses is the disclosed,
bounded difference (live cannot see tomorrow)."* Both halves are executed here.

## The verdict

* **15 symbol-days** in the sample, stratified by `bias_rule` and by the shapes CONTEXT 3.4 and 3.5 decide differently.
* **14 judged** (the full CONTEXT 4.6 battery accepts the day).
* **14 matched** -- every boundary, every field, every alert.
* **0 mismatched.**
* **1 disclosed** as CONTEXT 4.7's bounded difference rather than judged.

### ZERO mismatches

Not one field of one boundary of one day differs. What is compared per day: the
bias and the rule that produced it, the POC, the 11:15 reference, and then at
EVERY boundary the phase, entry, stop, target, quantity, exit kind and exit price,
plus the alert sequence and the whole CONTEXT 3.4 transition trail.

## The sample, day by day

| stratum | symbol | day | source | oracle | boundaries | verdict |
|---|---|---|---|---|---:|---|
| `bias_rule:inside-bar-carry` | 360ONE | 2026-01-01 | lake | pass | 18 | **MATCH** |
| `bias_rule:no-data` | FORCEMOT | 2024-02-14 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-1-breakout` | 360ONE | 2026-01-05 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-2-sweep` | 360ONE | 2026-01-06 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-3-no-1min-carry` | AMBER | 2021-01-27 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-3-no-break-carry` | ASIANPAINT | 2017-07-11 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-3-outside-bar` | 360ONE | 2026-04-22 | lake | pass | 18 | **MATCH** |
| `bias_rule:rule-3-tie` | BDL | 2026-03-04 | lake | pass | 18 | **MATCH** |
| `carried-witness` | ITC | 2026-06-10 | lake | pass | 18 | **MATCH** |
| `gap-entry` | ADANIENSOL | 2026-05-08 | lake | pass | 18 | **MATCH** |
| `oracle-refused` | ADANIPORTS | 2026-02-06 | live-posture | REFUSED | 18 | **DISCLOSED (4.7)** |
| `qty-zero:BOSCHLTD` | BOSCHLTD | 2021-05-20 | lake | pass | 18 | **MATCH** |
| `qty-zero:SHREECEM` | SHREECEM | 2020-03-19 | lake | pass | 18 | **MATCH** |
| `reference==POC` | 360ONE | 2026-07-06 | lake | pass | 18 | **MATCH** |
| `recording round trip` | HDFCBANK | 2026-06-10 | recording | pass | 18 | **MATCH** |

## What each judged day agreed on

### 360ONE 2026-01-01 -- `bias_rule:inside-bar-carry` (lake)

bias `bullish` by `inside-bar-carry`, side `long`, POC `117875` paise, reference `117780` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | triggered | 117910 | 117750 | 118390 | 625 | - |
| 11:45 | in-trade | 117910 | 117750 | 118390 | 625 | - |
| 12:00 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 12:15 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 12:30 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 12:45 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 13:00 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 13:15 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 13:30 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 13:45 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 14:00 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 14:15 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 14:30 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 14:45 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 15:00 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 15:15 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |
| 15:30 | exited | 117910 | 117750 | 118390 | 625 | stop-loss-hit @ 117750 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### FORCEMOT 2024-02-14 -- `bias_rule:no-data` (lake)

bias `bearish` by `no-data`, side `short`, POC `440250` paise, reference `439700` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | armed | - | - | - | - | - |
| 13:45 | armed | - | - | - | - | - |
| 14:00 | armed | - | - | - | - | - |
| 14:15 | armed | - | - | - | - | - |
| 14:30 | armed | - | - | - | - | - |
| 14:45 | armed | - | - | - | - | - |
| 15:00 | armed | - | - | - | - | - |
| 15:15 | armed | - | - | - | - | - |
| 15:30 | armed | - | - | - | - | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### 360ONE 2026-01-05 -- `bias_rule:rule-1-breakout` (lake)

bias `bullish` by `rule-1-breakout`, side `long`, POC `120435` paise, reference `120420` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | triggered | 120710 | 120260 | 122060 | 222 | - |
| 11:45 | in-trade | 120710 | 120260 | 122060 | 222 | - |
| 12:00 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 12:15 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 12:30 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 12:45 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 13:00 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 13:15 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 13:30 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 13:45 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 14:00 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 14:15 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 14:30 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 14:45 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 15:00 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 15:15 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |
| 15:30 | exited | 120710 | 120260 | 122060 | 222 | target-hit @ 122060 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### 360ONE 2026-01-06 -- `bias_rule:rule-2-sweep` (lake)

bias `bearish` by `rule-2-sweep`, side `short`, POC `120560` paise, reference `120510` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | waiting | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | triggered | 120540 | 120700 | 120060 | 625 | - |
| 12:45 | in-trade | 120540 | 120700 | 120060 | 625 | - |
| 13:00 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 13:15 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 13:30 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 13:45 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 14:00 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 14:15 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 14:30 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 14:45 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 15:00 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 15:15 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |
| 15:30 | exited | 120540 | 120700 | 120060 | 625 | target-hit @ 120060 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### AMBER 2021-01-27 -- `bias_rule:rule-3-no-1min-carry` (lake)

bias `bearish` by `rule-3-no-1min-carry`, side `short`, POC `253395` paise, reference `253215` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | waiting | - | - | - | - | - |
| 11:45 | waiting | - | - | - | - | - |
| 12:00 | waiting | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | armed | - | - | - | - | - |
| 13:45 | armed | - | - | - | - | - |
| 14:00 | armed | - | - | - | - | - |
| 14:15 | armed | - | - | - | - | - |
| 14:30 | armed | - | - | - | - | - |
| 14:45 | armed | - | - | - | - | - |
| 15:00 | armed | - | - | - | - | - |
| 15:15 | armed | - | - | - | - | - |
| 15:30 | armed | - | - | - | - | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### ASIANPAINT 2017-07-11 -- `bias_rule:rule-3-no-break-carry` (lake)

bias `bearish` by `rule-3-no-break-carry`, side `short`, POC `112535` paise, reference `113105` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | armed | - | - | - | - | - |
| 13:45 | armed | - | - | - | - | - |
| 14:00 | armed | - | - | - | - | - |
| 14:15 | armed | - | - | - | - | - |
| 14:30 | armed | - | - | - | - | - |
| 14:45 | armed | - | - | - | - | - |
| 15:00 | armed | - | - | - | - | - |
| 15:15 | armed | - | - | - | - | - |
| 15:30 | armed | - | - | - | - | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### 360ONE 2026-04-22 -- `bias_rule:rule-3-outside-bar` (lake)

bias `bullish` by `rule-3-outside-bar`, side `long`, POC `105075` paise, reference `105340` paise.

alerts: live `['armed', 'trigger', 'square-off']` == backtest `['armed', 'trigger', 'square-off']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | waiting | - | - | - | - | - |
| 11:45 | waiting | - | - | - | - | - |
| 12:00 | waiting | - | - | - | - | - |
| 12:15 | waiting | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | triggered | 105490 | 104800 | 107560 | 144 | - |
| 13:15 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 13:30 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 13:45 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 14:00 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 14:15 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 14:30 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 14:45 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 15:00 | in-trade | 105490 | 104800 | 107560 | 144 | - |
| 15:15 | exited | 105490 | 104800 | 107560 | 144 | square-off-at-the-15:15-close @ 105530 |
| 15:30 | exited | 105490 | 104800 | 107560 | 144 | square-off-at-the-15:15-close @ 105530 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### BDL 2026-03-04 -- `bias_rule:rule-3-tie` (lake)

bias `bullish` by `rule-3-tie`, side `long`, POC `126815` paise, reference `127560` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | waiting | - | - | - | - | - |
| 11:45 | waiting | - | - | - | - | - |
| 12:00 | waiting | - | - | - | - | - |
| 12:15 | waiting | - | - | - | - | - |
| 12:30 | waiting | - | - | - | - | - |
| 12:45 | waiting | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | triggered | 126890 | 126460 | 128180 | 232 | - |
| 13:30 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 13:45 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 14:00 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 14:15 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 14:30 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 14:45 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 15:00 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 15:15 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |
| 15:30 | exited | 126890 | 126460 | 128180 | 232 | stop-loss-hit @ 126460 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### ITC 2026-06-10 -- `carried-witness` (lake)

bias `bearish` by `inside-bar-carry`, side `short`, POC `56655/2` paise, reference `28440` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | armed | - | - | - | - | - |
| 13:45 | armed | - | - | - | - | - |
| 14:00 | armed | - | - | - | - | - |
| 14:15 | armed | - | - | - | - | - |
| 14:30 | armed | - | - | - | - | - |
| 14:45 | armed | - | - | - | - | - |
| 15:00 | armed | - | - | - | - | - |
| 15:15 | armed | - | - | - | - | - |
| 15:30 | armed | - | - | - | - | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### ADANIENSOL 2026-05-08 -- `gap-entry` (lake)

bias `bearish` by `rule-1-breakout`, side `short`, POC `138155` paise, reference `138020` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | triggered | 137790 | 138160 | 136680 | 270 | - |
| 12:00 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 12:15 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 12:30 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 12:45 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 13:00 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 13:15 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 13:30 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 13:45 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 14:00 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 14:15 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 14:30 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 14:45 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 15:00 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 15:15 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |
| 15:30 | exited | 137790 | 138160 | 136680 | 270 | stop-loss-hit @ 138160 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### BOSCHLTD 2021-05-20 -- `qty-zero:BOSCHLTD` (lake)

bias `bullish` by `rule-1-breakout`, side `long`, POC `1472680` paise, reference `1464520` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | refused | - | - | - | 0 | - |
| 13:45 | refused | - | - | - | 0 | - |
| 14:00 | refused | - | - | - | 0 | - |
| 14:15 | refused | - | - | - | 0 | - |
| 14:30 | refused | - | - | - | 0 | - |
| 14:45 | refused | - | - | - | 0 | - |
| 15:00 | refused | - | - | - | 0 | - |
| 15:15 | refused | - | - | - | 0 | - |
| 15:30 | refused | - | - | - | 0 | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### SHREECEM 2020-03-19 -- `qty-zero:SHREECEM` (lake)

bias `bearish` by `rule-1-breakout`, side `short`, POC `1777490` paise, reference `1902470` paise.

alerts: live `['armed']` == backtest `['armed']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | armed | - | - | - | - | - |
| 12:00 | armed | - | - | - | - | - |
| 12:15 | armed | - | - | - | - | - |
| 12:30 | armed | - | - | - | - | - |
| 12:45 | armed | - | - | - | - | - |
| 13:00 | armed | - | - | - | - | - |
| 13:15 | armed | - | - | - | - | - |
| 13:30 | armed | - | - | - | - | - |
| 13:45 | armed | - | - | - | - | - |
| 14:00 | armed | - | - | - | - | - |
| 14:15 | refused | - | - | - | 0 | - |
| 14:30 | refused | - | - | - | 0 | - |
| 14:45 | refused | - | - | - | 0 | - |
| 15:00 | refused | - | - | - | 0 | - |
| 15:15 | refused | - | - | - | 0 | - |
| 15:30 | refused | - | - | - | 0 | - |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### 360ONE 2026-07-06 -- `reference==POC` (lake)

bias `bullish` by `rule-1-breakout`, side `long`, POC `112990` paise, reference `112990` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | waiting | - | - | - | - | - |
| 11:30 | armed | - | - | - | - | - |
| 11:45 | triggered | 113000 | 112600 | 114200 | 250 | - |
| 12:00 | in-trade | 113000 | 112600 | 114200 | 250 | - |
| 12:15 | in-trade | 113000 | 112600 | 114200 | 250 | - |
| 12:30 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 12:45 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 13:00 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 13:15 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 13:30 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 13:45 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 14:00 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 14:15 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 14:30 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 14:45 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 15:00 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 15:15 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |
| 15:30 | exited | 113000 | 112600 | 114200 | 250 | stop-loss-hit @ 112600 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

### HDFCBANK 2026-06-10 -- `recording round trip` (recording)

bias `bullish` by `rule-3-outside-bar`, side `long`, POC `73980` paise, reference `73820` paise.

alerts: live `['armed', 'trigger', 'exit']` == backtest `['armed', 'trigger', 'exit']`; transition trail identical: `True`.

| boundary | phase | entry | stop | target | qty | exit |
|---|---|---:|---:|---:|---:|---|
| 11:15 | armed | - | - | - | - | - |
| 11:30 | triggered | 74095 | 73810 | 74950 | 350 | - |
| 11:45 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 12:00 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 12:15 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 12:30 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 12:45 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 13:00 | in-trade | 74095 | 73810 | 74950 | 350 | - |
| 13:15 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 13:30 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 13:45 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 14:00 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 14:15 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 14:30 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 14:45 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 15:00 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 15:15 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |
| 15:30 | exited | 74095 | 73810 | 74950 | 350 | target-hit @ 74950 |

Every row above is the LIVE screener's own state at that boundary, and every one of them equals the backtester's whole-day answer projected onto the same boundary.

## The disclosed difference (CONTEXT 4.7)

* **ADANIPORTS 2026-02-06** (`oracle-refused`, live-posture): the full battery REFUSES the day -- *gap 52.135% is above the band [-0.1, 5.0]* -- while the ORACLE-FREE battery a live morning runs accepts it. Live alerts delivered: `['armed', 'trigger', 'square-off']`. This is not a parity failure: it is the bounded difference the architect's 08-Aug-2026 ruling names, and the next pre-open's verification reports it loudly.
  * measured: ADANIPORTS 2026-02-06: live posture delivered ['armed', 'trigger', 'square-off']; ledger reason 'gate 1 (volume reconciliation)'

## The recording round trip

A LIVE-posture morning was recorded over the named golden day and then replayed from its OWN bytes through `RecordingBarSource`, with the backtest side reading the same recording through the backtester's battery. This is the path REVIEW_13 **M22** blocked -- the lake does not hold a live morning's day, so the whole-day battery did not exist and 15 of 17 boundaries were refused by a gate that never ran. The alerts that morning delivered, verbatim (a live posture, so each carries CONTEXT 4.7's disclosed line):

```
  [11:15] HDFCBANK ARMED  LONG  POC 739.80  reference 738.20   [live feed, not yet verified against the exchange's end-of-day record]
  [11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)   [live feed, not yet verified against the exchange's end-of-day record]
  [13:15] HDFCBANK EXIT target-hit  at 749.50   [live feed, not yet verified against the exchange's end-of-day record]
```

## The strata, over the whole ten-year ledger

| bias_rule | evaluated stock-days |
|---|---:|
| `rule-1-breakout` | 276,541 |
| `inside-bar-carry` | 62,680 |
| `rule-2-sweep` | 60,527 |
| `rule-3-outside-bar` | 6,664 |
| `rule-3-tie` | 62 |
| `rule-3-no-1min-carry` | 7 |
| `rule-3-no-break-carry` | 5 |
| `no-data` | 2 |

Machine-readable sample: `chunk14_parity_sample.json` (the suite re-runs it, so a regression fails the build rather than waiting for someone to re-run this script).
