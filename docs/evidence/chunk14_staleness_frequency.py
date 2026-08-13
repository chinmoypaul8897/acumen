"""Chunk 14 evidence: how often a HEALTHY feed looks stale at a boundary.

    python docs/evidence/chunk14_staleness_frequency.py [--day 2026-06-10]

**Why this number is needed.** REVIEW_13B **Q1** is closed by putting the staleness marker on
the alert. The obvious next step -- raise the loud FAILURE BANNER whenever a watched symbol's
window is stale -- was considered and NOT taken, and this measures the reason rather than
asserting it: a 1-minute bar exists only if the stock TRADED in that minute, so on a real,
healthy morning a perfectly good symbol can be several minutes behind the boundary simply
because nobody dealt in it. A banner that fires on that is a banner the operator learns to
ignore, which would cost him the one that matters.

The predicate measured is exactly the shipped one, :func:`acumen.live_screener.data_age` with
:data:`acumen.live_screener.STALE_AFTER_MINUTES` -- no second definition of "stale" is invented
here. The population is every settled symbol the lake holds for the day, at each of CONTEXT
4.4's seventeen boundaries, taking the bars a poll at that boundary would legally have seen
(:func:`acumen.live_source._clamp`, CONTEXT 7-E12).

**READ-ONLY over the stores**: it opens the minute lake for reading and writes only its own
markdown under ``docs/evidence/``.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import live_screener as ls  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_source import _clamp  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk14_staleness_frequency.md"
RESIDUAL_RELPATH = Path("universe_backfill") / "ledger.json"


def settled_symbols(data_root: Path) -> tuple[str, ...]:
    """The 204 the screener alerts on (CONTEXT 4.7 / Q-30), from the chunk-5B register."""
    from acumen.backtest import load_residual_register

    register = load_residual_register(data_root / RESIDUAL_RELPATH)
    return tuple(sorted(
        symbol for symbol, entry in register.items()
        if str(entry.status).strip().lower() == "settled"
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day", default="2026-06-10")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.day)

    config = load_config(include_env=False)
    data_root = config.path("data_root")
    store = MinuteStore.at(data_root / "minute_store")
    symbols = settled_symbols(data_root)

    boundaries = ls.boundary_stamps(day)
    behind_counts: Counter = Counter()
    stale_rows = 0
    rows = 0
    stale_by_symbol: Counter = Counter()
    covered = 0
    for symbol in symbols:
        minutes = store.minutes(symbol, day)
        if not minutes:
            continue
        covered += 1
        for boundary in boundaries:
            last = _clamp(day, boundary)
            seen = [bar for bar in minutes if bar.stamp <= last]
            if not seen:
                continue
            state = ls.SymbolState(
                symbol=symbol, phase=ls.PHASE_WAITING,
                minute_count=len(seen), last_stamp=seen[-1].stamp,
            )
            stale, behind = ls.data_age(state, boundary)
            rows += 1
            behind_counts[behind] += 1
            if stale:
                stale_rows += 1
                stale_by_symbol[symbol] += 1

    share = (stale_rows / rows) if rows else 0.0
    worst = behind_counts.most_common()
    lines = [
        "# chunk 14 -- how often a HEALTHY feed looks stale at a boundary",
        "",
        f"Run at {datetime.now().replace(microsecond=0).isoformat()} from "
        "`docs/evidence/chunk14_staleness_frequency.py`. READ-ONLY over the stores.",
        "",
        f"Day measured: **{day.isoformat()}**, over **{covered} settled symbols** the lake "
        f"holds, at each of the {len(boundaries)} boundaries CONTEXT 4.4 sweeps.",
        "",
        "## The measurement",
        "",
        f"* symbol-boundary readings: **{rows:,}**",
        f"* readings the shipped predicate calls STALE (last bar more than "
        f"{ls.STALE_AFTER_MINUTES} minute behind the boundary): **{stale_rows:,} = "
        f"{share:.2%}**",
        f"* symbols with at least one stale reading: **{len(stale_by_symbol)}** of {covered}",
        "",
        "| minutes behind the boundary | readings |",
        "|---:|---:|",
    ]
    for behind, count in sorted(worst)[:12]:
        lines.append(f"| {behind} | {count:,} |")
    lines += [
        "",
        "## What it does and does not decide",
        "",
        "**The number is SMALL, and it is reported as measured rather than as the answer it",
        "would have been convenient for it to be.** A 1-minute bar exists only if the stock",
        f"TRADED in that minute, so a healthy feed does produce stale readings -- {stale_rows} of",
        f"{rows:,} here, across {len(stale_by_symbol)} symbols -- but at {share:.2%} they would",
        "not drown a banner. So this measurement does NOT settle the banner question on volume,",
        "and it is not used to.",
        "",
        "What settles it, in this session's judgment and subject to the architect's, is what the",
        "banner MEANS. The full-width banner says *the screener could not read part of the",
        "market*: it is the one element DESIGN.md PART II lets cover the width, and its whole",
        "value is that it is never wrong. On a quiet stock the screener read the market",
        "perfectly and the market said nothing, so the banner's own sentence would be false --",
        "while the ALERT-level and ROW-level markers say exactly the true thing, that this price",
        "stands on a window N minutes old.",
        "",
        "REVIEW_13B's Q1 case -- a feed answering 200 with a prefix that never grows -- is",
        "therefore caught by the marker on every alert it produces and by the row on the",
        "dashboard, which is the fix the finding itself prescribed (*\"carrying the row's",
        "staleness onto the alert exactly as poc_note is carried\"*), and not by a banner it did",
        "not ask for.",
        "",
        "Recorded in PROGRESS.md as a Class-B choice with this number beside it, and put to the",
        "architect as QUESTIONS.md **Q-32** rather than settled here: at 0.26% a banner is",
        "affordable, and whether a stale window should ALSO be loud is his call, not this",
        "session's.",
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(json.dumps({"rows": rows, "stale": stale_rows, "share": round(share, 6)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
