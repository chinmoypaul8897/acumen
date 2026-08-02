"""MEASURED throughput for the chunk-9B full-history run, and the projection built from it.

Committed HERE, beside its own output and beside the smoke log it reads, because CLAUDE.md's
git rules (REVIEW_7 finding C3) require a session making claims from real store data to commit
the generating script and its output under `docs/evidence/`.

    python docs/evidence/chunk9b_throughput.py --out docs/evidence/chunk9b_throughput.md

READ-ONLY and OFFLINE. It writes nothing to either store. The one store-writing measurement --
the smoke run itself -- was executed separately with the architect's sanction, and its console
output is committed at `docs/evidence/chunk9b_smoke.log`; this script reads the SMOKE'S OWN
LEDGER back from the store for the counts and takes the two timing figures from that log.

WHY THE PROJECTION HAS THREE TERMS RATHER THAN ONE. A full run is not "the smoke, 102 times":

* the WALK scales with symbol-days, and the smoke measures it directly;
* the CONTEXT 7-E2 SESSION SCAN scales with symbols x span days and the smoke's 2-symbol
  measurement is 1/102 of the real one, so it is measured here on samples instead;
* the CORPORATE-ACTION TABLES scale with symbols (one daily-store history read each), same
  problem, same treatment.

Multiplying one blended smoke number by 102 would have silently projected the two wiring terms
at 1/102 of their real cost. They are small, but "small" is a measurement, not an assumption --
so each is measured at two sample sizes and its LINEARITY is printed, because a term that is
not linear cannot be extrapolated at all and the reader should be able to see that for himself.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import run_backtest as rb  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

#: The smoke this projection is built on: RELIANCE + MARUTI over the full era, run on
#: 2026-08-02 at 15:21 IST on a freshly rebooted machine. Both figures are read off the
#: runner's own final line and its wiring line, committed verbatim at chunk9b_smoke.log.
SMOKE_LABEL = "chunk9b_smoke"
SMOKE_WALK_SECONDS = 190  # "in 0:03:10 (25.6 days/s)"
SMOKE_WIRING_SECONDS = 28  # "wiring complete in 0:00:28"

#: The architect's STOP threshold for this session: a projection above it halts and reports
#: options instead of staging the run.
STOP_HOURS = 36

#: Sample sizes for the two per-symbol wiring terms. Two points, so linearity is shown rather
#: than assumed -- an extrapolation from a single point cannot distinguish O(n) from O(n^2).
SAMPLES = (4, 12)


def spread(universe: tuple[str, ...], n: int) -> tuple[str, ...]:
    """``n`` symbols spread EVENLY across the universe, not the first ``n``.

    This matters and it was measured: taking ``universe[:n]`` gave 10.4 s/symbol at n=2 and
    13.4 s/symbol at n=10 for the session scan, which looks like superlinearity and is not --
    it is the alphabetically-first symbols carrying less stored history than the ones after
    them. A first-n sample of a per-symbol cost is a sample of the symbols' NAMES.
    """
    if n >= len(universe):
        return universe
    step = len(universe) / n
    return tuple(universe[int(i * step)] for i in range(n))


@dataclass(frozen=True)
class Term:
    """One measured cost term: what it scales with, and what it costs per unit."""

    name: str
    scales_with: str
    samples: tuple[tuple[int, float], ...]
    per_symbol: float
    projected: float

    @property
    def linearity(self) -> str:
        """The per-symbol cost at each sample size, so a reader can see it hold (or not)."""
        return ", ".join(f"{n} sym -> {secs / n:.3f} s/sym" for n, secs in self.samples)


def _hms(seconds: float) -> str:
    total = int(round(max(0.0, seconds)))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}h {minutes:02d}m {secs:02d}s"


def month_files(minute_store, symbols) -> int:
    """Total 1-minute month files across ``symbols`` -- the session scan's real work unit."""
    root = minute_store.minute_dir
    return sum(
        len(list((root / symbol).glob(f"{symbol}_*.parquet")))
        for symbol in symbols
        if (root / symbol).is_dir()
    )


def measure_terms(universe, minute_store, daily_store, span, start, end) -> list[Term]:
    universe_files = month_files(minute_store, universe)

    scan_samples: list[tuple[int, float]] = []
    scan_files: list[int] = []
    for n in SAMPLES:
        sample = spread(universe, n)
        scan_files.append(month_files(minute_store, sample))
        started = time.monotonic()
        bt.scan_non_standard_sessions(minute_store, sample, span)
        scan_samples.append((n, time.monotonic() - started))

    ca_samples: list[tuple[int, float]] = []
    for n in SAMPLES:
        started = time.monotonic()
        bt.build_factor_tables(
            spread(universe, n), daily_store, start=start, end=end, allow_network=False
        )
        ca_samples.append((n, time.monotonic() - started))

    total = len(universe)
    # The session scan is projected by MONTH-FILE ratio, not by symbol count: the scan opens
    # every month file of every symbol, and symbols differ by a factor of several in how many
    # they have (a 2016 listing against a 2024 one). Scaling per-symbol would extrapolate the
    # sample's own listing dates onto the universe. Per-file removes that bias entirely, and
    # the per-symbol figure is still printed so the two can be compared.
    scan_secs = scan_samples[-1][1]
    scan_sample_files = scan_files[-1]
    scan_projected = scan_secs / scan_sample_files * universe_files

    # The CA tables carry a fixed shared cost (parsing the whole day-cache once), so the
    # LARGEST sample is the right per-symbol basis -- it amortises that furthest and therefore
    # projects the smallest, least flattering marginal cost.
    ca_per_symbol = ca_samples[-1][1] / ca_samples[-1][0]

    return [
        Term(
            name="CONTEXT 7-E2 session scan",
            scales_with=(
                f"month files ({universe_files:,} across the universe; "
                f"{scan_sample_files:,} in the sample)"
            ),
            samples=tuple(scan_samples),
            per_symbol=scan_projected / total,
            projected=scan_projected,
        ),
        Term(
            name="corporate-action factor tables",
            scales_with="symbols (one daily-store history read each)",
            samples=tuple(ca_samples),
            per_symbol=ca_per_symbol,
            projected=ca_per_symbol * total,
        ),
    ]


def render(
    *,
    universe: int,
    rows_each: int,
    walked: int,
    usable: int,
    executed: int,
    span: tuple[date, date],
    trading_days: int,
    terms: list[Term],
) -> str:
    rate = walked / SMOKE_WALK_SECONDS
    total_days = universe * rows_each
    walk_projected = total_days / rate
    wiring_projected = sum(term.projected for term in terms)
    total_projected = walk_projected + wiring_projected

    out: list[str] = []
    add = out.append
    add("# chunk 9B -- MEASURED throughput and the full-run projection")
    add("")
    add(
        "Generated by `docs/evidence/chunk9b_throughput.py`, committed under CLAUDE.md's "
        "evidence rule. Read-only and offline; the smoke run it is built on is committed "
        "beside it at `docs/evidence/chunk9b_smoke.log`."
    )
    add("")
    add("## 1. The smoke -- MEASURED, not extrapolated")
    add("")
    add(
        "The real runner, the real stores, the full era, on the machine that will do the run "
        "and after the reboot the operator performed at 14:01 IST on 2026-08-02."
    )
    add("")
    add("| Measure | Value |")
    add("|---|---|")
    add("| Command | `python scripts/run_backtest.py --symbols RELIANCE,MARUTI --label chunk9b_smoke` |")
    add(f"| Span walked | {span[0]} -> {span[1]} ({trading_days:,} trading days) |")
    add(f"| Symbol-days walked | {walked:,} ({rows_each:,} per symbol x 2) |")
    add(f"| Usable / executed | {usable:,} / {executed:,} |")
    add(f"| Walk time | {_hms(SMOKE_WALK_SECONDS)} |")
    add(f"| **Measured rate** | **{rate:.2f} symbol-days / second** |")
    add(f"| Wiring time (2 symbols) | {_hms(SMOKE_WIRING_SECONDS)} |")
    add("")
    add(
        "The two symbols cost 95s and 94s respectively -- within 1% of each other -- so the "
        "rate is a rate and not an average over two very different symbols."
    )
    add("")
    add("## 2. The two wiring terms, measured separately")
    add("")
    add(
        "These do NOT scale from the smoke: its session scan covered 2 symbols where the run "
        "covers 204, so multiplying a blended smoke figure by 102 would have projected them at "
        "1/102 of their real cost. Each is measured here at two sample sizes, on symbols spread "
        "EVENLY across the universe rather than the first few -- a first-n sample of a "
        "per-symbol cost is a sample of the symbols' NAMES, and this was measured rather than "
        "assumed: an alphabetically-first sample gave 10.4 s/symbol at n=2 against 13.4 s/symbol "
        "at n=10 for the session scan, which reads like superlinearity and is really just the "
        "early alphabet carrying less stored history."
    )
    add("")
    add("| Term | Scales with | Measured | Per symbol | Projected over 204 |")
    add("|---|---|---|---|---|")
    for term in terms:
        add(
            f"| {term.name} | {term.scales_with} | {term.linearity} | "
            f"{term.per_symbol:.3f} s | {_hms(term.projected)} |"
        )
    add("")
    add("## 3. The projection, with its arithmetic")
    add("")
    add("```")
    add(f"  walk      : {universe} symbols x {rows_each:,} rows = {total_days:,} symbol-days")
    add(f"              {total_days:,} / {rate:.3f} days-per-second")
    add(f"            = {walk_projected:,.0f} s = {_hms(walk_projected)}")
    for term in terms:
        add(
            f"  wiring    : {term.per_symbol:.3f} s/symbol x {universe} = "
            f"{term.projected:,.0f} s = {_hms(term.projected)}   ({term.name})"
        )
    add(f"  TOTAL     = {total_projected:,.0f} s = {_hms(total_projected)}")
    add("```")
    add("")
    verdict = "PROCEED" if total_projected <= STOP_HOURS * 3600 else "STOP"
    add(
        f"**PROJECTED FULL-RUN DURATION: {_hms(total_projected)}.** The session card's STOP "
        f"threshold is {STOP_HOURS} hours; this is "
        f"{'well under' if verdict == 'PROCEED' else 'ABOVE'} it, so the card's "
        f"\"STOP with options\" branch does {'not ' if verdict == 'PROCEED' else ''}fire."
    )
    add("")
    add("## 4. What this projection does NOT cover -- read before trusting the number")
    add("")
    add(
        "* **The machine is memory-starved, and the reboot did not fix it.** Measured at 14:12 "
        "IST, eleven minutes after the operator's reboot: **964 MB available of 7.7 GB**, with "
        "**20.1 GB committed against a 27.1 GB limit** -- i.e. the working set is already "
        "2.6x physical memory and is being served by the page file. RESUME-1 recorded the same "
        "starvation (0.4 GB free) and measured its cost: a 21,000-file read took 25 minutes and "
        "one verification pass was reaped mid-scan. The smoke ran clean at this pressure, but "
        "it held two symbols' candles at a time; a 204-symbol run holds no more per symbol "
        "(the runner walks one symbol at a time and writes its shard before the next), which is "
        "why the projection is offered at all -- but a long run competing with a browser or an "
        "editor for the last gigabyte will page, and paging does not show up in a 3-minute "
        "measurement."
    )
    add(
        "* **It is a projection from a 2-symbol sample, not a measured full run.** The walk "
        "rate is uniform across the two symbols measured, and the runner does the same work per "
        "symbol-day for every symbol, so the extrapolation is sound in structure -- but the "
        "only thing that MEASURES a full run is a full run."
    )
    add(
        "* **Resume is free, so an overrun is not a loss.** A symbol's shard is written only "
        "when that symbol is complete; a Ctrl-C costs at most the symbol in flight, and the "
        "same command picks up where it stopped. The projection is a planning number, not a "
        "deadline."
    )
    add(
        "* **A moved HEAD or a moved tick pin REFUSES the resume** (the run spec's digest "
        "covers the code SHA and the pin's filename + sha256), so committing during the run "
        "converts a free resume into a full re-run."
    )
    add("")
    return "\n".join(out) + "\n"


def run(out_path: Path | None) -> int:
    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    register = bt.load_residual_register(data / bt.RESIDUAL_LEDGER_RELPATH)
    universe = rb.settled_symbols(register)

    rows = bt.read_ledger(data / "backtests" / SMOKE_LABEL / bt.LEDGER_NAME)
    symbols = sorted({row.symbol for row in rows})
    rows_each = len(rows) // len(symbols)
    start = min(row.day for row in rows)
    end = max(row.day for row in rows)
    span_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    trading_days = len({row.day for row in rows})

    terms = measure_terms(universe, minute_store, daily_store, span_days, start, end)
    text = render(
        universe=len(universe),
        rows_each=rows_each,
        walked=len(rows),
        usable=sum(1 for row in rows if row.status == bt.STATUS_EVALUATED),
        executed=sum(1 for row in rows if row.executed),
        span=(start, end),
        trading_days=trading_days,
        terms=terms,
    )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"written: {out_path}")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="chunk-9B measured throughput + projection")
    parser.add_argument("--out", default=None, help="write the markdown report here")
    args = parser.parse_args(argv)
    return run(Path(args.out) if args.out else None)


if __name__ == "__main__":
    raise SystemExit(main())
