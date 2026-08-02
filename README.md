# Acumen Intelligence

Private research tool: backtester + live screener for a discretionary trader's NSE F&O strategy.

> **PRIVATE & CONFIDENTIAL.** Single-owner research tool. Not open source, not for
> distribution, no license grant, zero collaborators. Real money depends on the correctness
> of the one frozen strategy it implements.

## What this is

A backtester and live screener built around a single, frozen intraday strategy over the NSE
F&O universe. The strategy is specified once, in `CONTEXT.md`, and is never changed by code.
This README covers only how the repository is organised and run — no strategy details.

## Repository map

| Path | Role |
|------|------|
| `CLAUDE.md`     | **Session constitution** — the rules every working session must follow. Read first. |
| `CONTEXT.md`    | **Master spec** — the frozen strategy and system requirements. Law; never edited. |
| `plan.md`       | **Build plan** — the chunked roadmap and per-chunk cards. |
| `PROGRESS.md`   | Ledger — one honest session entry, newest on top. |
| `STATUS.md`     | Ledger — chunk state (`todo` / `built` / `reviewed-PASS` / `gate-closed`). |
| `QUESTIONS.md`  | Ledger — anything `CONTEXT.md` does not answer (the STOP rule lives here). |
| `docs/reviews/` | Per-chunk review reports (`REVIEW_<N>.md`). |

## Quickstart

Requires Python 3.10+. Runtime dependencies are pinned exactly (`==`) in `pyproject.toml`.

```bash
pip install -e ".[dev]"   # pinned runtime deps + pytest
python -m pytest          # full suite must be green
```

`pytest` also runs from a bare clone with no editable install (the `src/` layout is placed on
the test path by `pyproject.toml`), as long as `pytest` itself is available.

## Operator commands

Market data lives **outside the repository tree**, at `paths.data_root` / `paths.cache_root`
in `config.yaml` — not merely git-ignored. Ignoring was not enough: on 31-Jul-2026 both stores
sat inside the repo and `git worktree remove --force` followed two junctions into them and
emptied them, with every ignore rule in force (QUESTIONS.md Q-18, CONTEXT §4.6). Outside the
tree no git command can reach them, and the config loader refuses a store root that is
relative or inside the repo, so it cannot quietly revert.

The **tick regime is pinned** the same way, for the same reason: `config.yaml`'s
`instrument_master` names ONE instrument-master snapshot and the backtest reads no other. The
vendor's daily dump moved `tick_size` on 11 walked symbols — in both directions — within two
days, and CONTEXT §3.3 sizes the volume-profile row grid by the tick, so "newest dump wins"
silently changed POCs and made a re-run non-reproducible (QUESTIONS.md Q-20). The run manifest
records the pin by filename and sha256, and a run refuses to resume under a different one.

Every command below defaults to those roots; `--store` is only for pointing at a copy.

```bash
# resume the daily backfill (skips settled dates; network is opt-in)
python scripts/backfill_daily.py --from 2000-01-01 --to 2026-07-30 --allow-network

# rebuild a truncated/corrupt ledger from the surviving monthly files (offline, no date range)
python scripts/backfill_daily.py --rebuild-ledger
```

After `pip install -e .` these are also available as the `acumen-backfill` and
`acumen-ca-report` console entry points.

## Discipline

This repo is governed by `CLAUDE.md` — read it before doing anything. In short: the strategy is
frozen, tests define done, trading APIs are read-only, secrets never enter history, and the
commit history stays clean. The GitHub remote is a private backup mirror only.
