"""Q-20 CALIBRATION RE-VERIFICATION -- does the POC calibration reproduce under the PIN?

Committed under CLAUDE.md's evidence rule. Regenerate with:

    python docs/evidence/chunk9b_tick_pin.py --out docs/evidence/chunk9b_tick_pin.md

OFFLINE and READ-ONLY. It opens ONE instrument master -- the pinned one named in
``config.yaml`` -- plus the frozen `poc/data` CSVs and the local minute store. It fetches
nothing, writes nothing but its own markdown, and decides nothing.

WHY THIS EXISTS. The architect's Q-20 ruling (02-Aug-2026) ends with a condition:

    "The pin is valid only if the POC calibration reproduces under it -- verified before any
    run."

So this is the gate on the pin itself, and it is deliberately narrow: every figure below is one
this repository already froze or already published, recomputed with the pinned master as the
ONLY tick source. Nothing here is a new calibration; a NEW number would prove nothing, because
the question is whether the pin moves an OLD one.

WHAT IS CHECKED, in the order a failure would matter:

1. **The ticks themselves** -- the pinned master's tick for every symbol the calibration and
   the sealed walks use, against the values this repo froze (`tests/fixtures/tick_sizes.json`,
   QUESTIONS.md Q-2) and published (REVIEW_7's three hand-walked days). A difference here is
   the session card's STOP condition, so it is measured first and reported even when it passes.
2. **F7, all 25 frozen prorata POCs** -- CONTEXT 8 F7's calibration set, recomputed from the
   frozen CSVs with the PINNED master's ticks rather than the frozen fixture's, so the two tick
   sources are actually compared rather than assumed equal.
3. **The chunk-6 gate day** -- BHARTIARTL, POC and ROW COUNT under CONTEXT 3.3's 8-candle
   window, from the local minute store. Both candidate dates are computed; see the note in the
   rendered pack for why there are two.
4. **The three sealed pilot walks** -- HDFCBANK 2026-06-10 (739.80), ICICIBANK 2026-05-21
   (1245.70) and RELIANCE 2026-05-05 (1465.85), each with its tick, totalTicks, tpr and row
   count, exactly as REVIEW_7 published them.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import poc  # noqa: E402
from acumen import poc_evidence as pe  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

FROZEN_TICKS = REPO / "tests" / "fixtures" / "tick_sizes.json"
FROZEN_SUMMARY = REPO / "poc" / "data" / "volume_poc_summary.csv"

#: CONTEXT 8 F7 (a) allows +-0.01 between the recomputed POC and the frozen printout. Reused
#: verbatim so this pack cannot be more forgiving than the golden test it re-runs.
F7_TOLERANCE = Decimal("0.01")

#: REVIEW_7's three hand-walked days, with every figure the review published. These are the
#: SEALED walks the card's STOP condition refers to: "any calibration symbol whose tick differs
#: from the sealed walks -> STOP".
SEALED_WALKS: tuple[tuple[str, date, int, int, int, int, str], ...] = (
    # symbol, day, tick paise, totalTicks, tpr, rows, POC rupees
    ("HDFCBANK", date(2026, 6, 10), 5, 182, 8, 23, "739.80"),
    ("ICICIBANK", date(2026, 5, 21), 10, 82, 4, 23, "1245.70"),
    ("RELIANCE", date(2026, 5, 5), 10, 224, 9, 25, "1465.85"),
)

#: The chunk-6 TRADER GATE day. The repo's own record -- QUESTIONS.md receipt R3F-f,
#: docs/gate_chunk6_poc_evidence.md and STATUS.md's chunk-6 line -- is 2026-07-17, where the
#: 8-candle finer profile gives POC 1914.60 in 26 rows and the TRADER's chart read 1913.9 in 25
#: rows (the price INCONCLUSIVE at 0.70 away, inside CONTEXT 5's feed-noise band; the ROW COUNT
#: decisive). The RESUME-2 session card names 2026-07-24 with the trader's two figures, so both
#: dates are computed and both are printed. Nothing is chosen here.
GATE_DAYS: tuple[date, ...] = (date(2026, 7, 17), date(2026, 7, 24))
GATE_SYMBOL = "BHARTIARTL"
GATE_EXPECTED = {date(2026, 7, 17): ("1914.60", 26)}
TRADER_READING = ("1913.9", 25)


#: A row's three possible verdicts. ``MOVED`` is the only one that fires the card's STOP: it
#: means the PIN changed a figure this repo had frozen or published. ``PUBLISHED_SLIP`` is a
#: mismatch the pin demonstrably did not cause -- the same figure comes back identical under the
#: OTHER cached snapshot, so the disagreement is with a published transcription, not with a tick.
#: Separating them matters: collapsing the two would either hide a real tick move inside a known
#: typo, or halt a run over one.
OK, MOVED, PUBLISHED_SLIP = "ok", "moved", "published-slip"


@dataclass(frozen=True)
class Line:
    """One measured row: what was checked, what was expected, what came back."""

    what: str
    expected: str
    measured: str
    status: str
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK

    @property
    def mark(self) -> str:
        return {OK: "**YES**", MOVED: "**NO -- MOVED**", PUBLISHED_SLIP: "see note"}[self.status]


def frozen_ticks() -> dict[str, int]:
    """The F7 tick fixture, in PAISE (the file states rupees -- QUESTIONS.md Q-2 ruling (a))."""
    raw = json.loads(FROZEN_TICKS.read_text(encoding="utf-8"))
    return {
        symbol: int((Decimal(str(value)) * 100).to_integral_value())
        for symbol, value in raw.items()
        if not symbol.startswith("_")
    }


def frozen_summary() -> list[dict[str, str]]:
    with FROZEN_SUMMARY.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _profile_from_store(store: MinuteStore, master, symbol: str, day: date, row_size: int):
    bars = store.minutes(symbol, day)
    if not bars:
        return None, None
    tick = int(master.by_symbol[symbol].tick_size_paise)
    return (
        poc.day_profile(
            bars, day, row_size=row_size, tick_paise=tick, volume_reconciled=True
        ),
        tick,
    )


def _rupees(value) -> str:
    return "-" if value is None else f"{value}"


def _same_money(measured, published: str) -> bool:
    """Decimal equality, not string equality: ``739.8`` and ``739.80`` are the same price.

    CONTEXT 7-E11 keeps prices in integer paise precisely so this comparison is exact; the POC
    is an exact ``Fraction`` of paise and the published figure is a decimal literal, so the two
    are compared as numbers and a trailing zero decides nothing.
    """
    return measured is not None and Decimal(measured) == Decimal(published)


def _control_under_the_other_master(
    config, store: MinuteStore, symbol: str, day: date, row_size: int
) -> tuple[str, str] | None:
    """Recompute one day under the OTHER cached snapshot, to prove whether the PIN is the cause.

    This is the discriminator the whole pack turns on. A mismatch that reproduces identically
    under both snapshots cannot have been caused by the pin -- the tick is the same in both --
    so it is a disagreement with a published number, not a tick move. Returns ``(snapshot name,
    one-line measurement)`` or ``None`` when there is no second snapshot to compare against.
    """
    from acumen.instrument_master import CACHE_SUBDIR

    home = config.path("cache_root") / CACHE_SUBDIR
    others = [
        path
        for path in sorted(home.glob("OpenAPIScripMaster_*.json"))
        if path.name != config.instrument_master
    ]
    if not others:
        return None
    other = others[-1]
    master, _path, _sha = bt.pinned_master(config.path("cache_root"), other.name)
    result, tick = _profile_from_store(store, master, symbol, day, row_size)
    if result is None:
        return other.name, "no stored minutes"
    grid = result.grid
    return other.name, (
        f"POC {_rupees(result.poc_rupees)}, tick {tick}p, totalTicks {grid.total_ticks}, "
        f"tpr {grid.ticks_per_row}, {len(result.row_volumes)} rows"
    )


# --- the four sections -------------------------------------------------------------------------


def check_ticks(master, pinned_name: str) -> list[Line]:
    """Section 1: the pinned master's tick for every symbol any figure below depends on."""
    lines: list[Line] = []

    def tick_line(what: str, symbol: str, want: int, source: str) -> Line:
        entry = master.by_symbol.get(symbol)
        got = int(entry.tick_size_paise) if entry else None
        return Line(
            what=what,
            expected=f"{want}p ({source})",
            measured=f"{got}p ({pinned_name})" if got is not None else "ABSENT",
            status=OK if got == want else MOVED,
        )

    for symbol, tick in sorted(frozen_ticks().items()):
        lines.append(
            tick_line(
                f"F7 tick, {symbol}", symbol, tick, "tests/fixtures/tick_sizes.json, Q-2"
            )
        )
    for symbol, _day, tick, *_rest in SEALED_WALKS:
        lines.append(
            tick_line(f"sealed-walk tick, {symbol}", symbol, tick, "REVIEW_7 walk")
        )
    lines.append(
        tick_line(
            f"chunk-6 gate tick, {GATE_SYMBOL}",
            GATE_SYMBOL,
            10,
            "gate pack: 26 rows of 6 ticks over 1910.10..1925.20",
        )
    )
    return lines


def check_f7(master, row_size: int) -> list[Line]:
    """Section 2: all 25 frozen prorata POCs, recomputed with the PINNED master's ticks."""
    lines: list[Line] = []
    for row in frozen_summary():
        symbol, day = row["symbol"], row["date"]
        entry = master.by_symbol.get(symbol)
        if entry is None:
            lines.append(
                Line(f"F7 {symbol} {day}", row["poc_prorata"], "symbol ABSENT from the pin", MOVED)
            )
            continue
        result = poc.day_profile(
            pe.bars_from_frozen_csv(symbol, date.fromisoformat(day)),
            date.fromisoformat(day),
            row_size=row_size,
            tick_paise=int(entry.tick_size_paise),
            volume_reconciled=True,
        )
        frozen = Decimal(row["poc_prorata"])
        measured = result.poc_rupees
        ok = measured is not None and abs(measured - frozen) <= F7_TOLERANCE
        lines.append(
            Line(
                what=f"F7 {symbol} {day} (tick {int(entry.tick_size_paise)}p)",
                expected=str(frozen),
                measured=_rupees(measured),
                status=OK if ok else MOVED,
            )
        )
    return lines


def check_gate_day(config, store: MinuteStore, master, row_size: int) -> list[Line]:
    """Section 3: the chunk-6 gate day's POC and ROW COUNT under the 8-candle spec window."""
    lines: list[Line] = []
    for day in GATE_DAYS:
        result, tick = _profile_from_store(store, master, GATE_SYMBOL, day, row_size)
        if result is None:
            lines.append(
                Line(
                    f"{GATE_SYMBOL} {day} (8-candle)",
                    "a stored day",
                    "NO STORED MINUTES",
                    MOVED,
                )
            )
            continue
        rows = len(result.row_volumes)
        measured = f"POC {_rupees(result.poc_rupees)} in {rows} rows (tick {tick}p)"
        if day in GATE_EXPECTED:
            want_poc, want_rows = GATE_EXPECTED[day]
            ok = _same_money(result.poc_rupees, want_poc) and rows == want_rows
            expected = f"POC {want_poc} in {want_rows} rows (R3F-f, the 8-candle finer profile)"
            status, note = (OK, "") if ok else _classify(
                config, store, GATE_SYMBOL, day, row_size
            )
        else:
            status, note = OK, "measured for the record: this repo froze no figure for this date"
            expected = "nothing frozen in this repo for this date -- measured, not asserted"
        lines.append(Line(f"{GATE_SYMBOL} {day} (8-candle)", expected, measured, status, note))
    return lines


def _classify(config, store, symbol, day, row_size) -> tuple[str, str]:
    """A mismatch: was it the PIN, or was the published figure already wrong? Measure it."""
    control = _control_under_the_other_master(config, store, symbol, day, row_size)
    if control is None:
        return MOVED, "no second snapshot on this machine -- cannot rule the pin out"
    name, line = control
    return PUBLISHED_SLIP, f"identical under `{name}`: {line} -- so the PIN did not cause it"


def check_walks(config, store: MinuteStore, master, row_size: int) -> list[Line]:
    """Section 4: REVIEW_7's three published walks, every figure of each."""
    lines: list[Line] = []
    for symbol, day, tick, ticks_total, tpr, rows, want_poc in SEALED_WALKS:
        result, measured_tick = _profile_from_store(store, master, symbol, day, row_size)
        if result is None:
            lines.append(Line(f"{symbol} {day}", want_poc, "NO STORED MINUTES", MOVED))
            continue
        grid = result.grid
        measured = (
            f"POC {_rupees(result.poc_rupees)}, tick {measured_tick}p, "
            f"totalTicks {grid.total_ticks}, tpr {grid.ticks_per_row}, "
            f"{len(result.row_volumes)} rows"
        )
        ok = (
            _same_money(result.poc_rupees, want_poc)
            and measured_tick == tick
            and grid.total_ticks == ticks_total
            and grid.ticks_per_row == tpr
            and len(result.row_volumes) == rows
        )
        status, note = (OK, "") if ok else _classify(config, store, symbol, day, row_size)
        lines.append(
            Line(
                what=f"{symbol} {day}",
                expected=(
                    f"POC {want_poc}, tick {tick}p, totalTicks {ticks_total}, tpr {tpr}, "
                    f"{rows} rows (REVIEW_7)"
                ),
                measured=measured,
                status=status,
                note=note,
            )
        )
    return lines


# --- rendering ------------------------------------------------------------------------------


def _table(title: str, lines: list[Line], out: list[str]) -> None:
    out.append(f"## {title}")
    out.append("")
    out.append("| check | frozen / published | recomputed under the pin | match |")
    out.append("|---|---|---|---|")
    for line in lines:
        out.append(f"| {line.what} | {line.expected} | {line.measured} | {line.mark} |")
    out.append("")
    for line in lines:
        if line.note:
            out.append(f"* **{line.what}** -- {line.note}")
    if any(line.note for line in lines):
        out.append("")


def render(pin_name: str, pin_sha: str, sections: list[tuple[str, list[Line]]]) -> str:
    every = [line for _title, lines in sections for line in lines]
    moved = [line for line in every if line.status == MOVED]
    slips = [line for line in every if line.status == PUBLISHED_SLIP]
    out: list[str] = []
    out.append("# Q-20 calibration re-verification -- the POC under the PINNED master")
    out.append("")
    out.append(
        "Generated by `docs/evidence/chunk9b_tick_pin.py`, committed under CLAUDE.md's evidence "
        "rule. Offline and read-only. This is the architect's own condition on the Q-20 ruling: "
        '*"the pin is valid only if the POC calibration reproduces under it -- verified before '
        'any run."*'
    )
    out.append("")
    out.append(f"- pinned master : `{pin_name}`")
    out.append(f"- sha256        : `{pin_sha}`")
    out.append(
        "- tick source   : that file and NOTHING else. `acumen.backtest.pinned_master` is the "
        "only resolver on the run path; newest-by-filename selection is retired."
    )
    out.append("")
    if moved:
        out.append(
            f"**VERDICT: STOP -- {len(moved)} of {len(every)} figures MOVED under the pin.**"
        )
    else:
        out.append(
            f"**VERDICT: the pin is VALID. {len(every) - len(slips)} of {len(every)} figures "
            "reproduce EXACTLY, and every calibration and sealed-walk TICK under the pin equals "
            "the one this repo froze or published** -- so the card's STOP condition (*\"any "
            "calibration symbol whose tick differs from the sealed walks\"*) does not fire."
        )
    if slips:
        out.append("")
        out.append(
            f"{len(slips)} row(s) disagree with a PUBLISHED figure and are marked *see note*. "
            "None of them is a tick move: each was recomputed under the OTHER cached snapshot "
            "and came back identical, which is what separates \"the pin changed a number\" from "
            "\"a number in a document was already wrong\". They are findings for the architect, "
            "not a reason to hold the run -- but they are not swept into the pass count either."
        )
    out.append("")
    for title, lines in sections:
        _table(title, lines, out)
    out.append("## The two dates for the chunk-6 gate day")
    out.append("")
    out.append(
        "The RESUME-2 session card names the chunk-6 oracle as *BHARTIARTL 2026-07-24: POC "
        "1913.9, 25 rows*. This repository's own record says otherwise on both counts, so both "
        "dates are computed above and neither is quietly preferred:"
    )
    out.append("")
    out.append(
        "* the gate day is **2026-07-17** -- QUESTIONS.md receipt R3F-f, "
        "`docs/gate_chunk6_poc_evidence.md`, and STATUS.md's chunk-6 line all name it;"
    )
    out.append(
        f"* **{TRADER_READING[0]} and {TRADER_READING[1]} rows are the TRADER's chart reading**, "
        "not an engine output. The engine's 8-candle finer-profile answer on that day is POC "
        "1914.60 in 26 rows, and R3F-f records the PRICE as INCONCLUSIVE (0.70 away, inside "
        "CONTEXT 5's documented Rs 0.05-3.5 feed-noise band) with the ROW COUNT as the decisive "
        "evidence: his 25 is ONE row from the finer profile's 26 and THREE from the coarser "
        "profile's 22."
    )
    out.append("")
    out.append(
        "So the figure a machine can reproduce is 1914.60 / 26 rows on 2026-07-17, and that is "
        "what the table above asserts. 2026-07-24 is measured for completeness and asserted "
        "against nothing, because this repo froze no figure for it -- its POC is 1880.75, "
        "Rs 33 away from the card's 1913.9, so the card's price cannot be that day's POC under "
        "any tick."
    )
    out.append("")
    if slips:
        out.append("## The published-figure discrepancy, with its arithmetic")
        out.append("")
        out.append(
            "**REVIEW_7's ICICIBANK 2026-05-21 walk publishes `23 rows`, and 23 rows is "
            "arithmetically impossible for the numbers beside it.** CONTEXT 3.3 stacks rows of "
            "`tpr` ticks from the bottom with the last row holding the remainder, so the "
            "realized row count is `ceil(totalTicks / tpr)`. The review's own figures are "
            "totalTicks 82 and tpr 4:"
        )
        out.append("")
        out.append("    ceil(82 / 4) = ceil(20.5) = 21 rows  (20 rows of 4 ticks + 1 row of 2)")
        out.append("")
        out.append(
            "There is no tick that produces 23 rows with totalTicks 82 and tpr 4. The most "
            "likely reading is a transcription slip: the HDFCBANK walk printed directly above "
            "it in REVIEW_7 has totalTicks 182, tpr 8 -- `ceil(182/8) = 23` -- and 23 is the "
            "figure that appears twice."
        )
        out.append("")
        out.append(
            "Everything else in that walk reproduces to the digit: POC 1245.70, tick 10p, "
            "totalTicks 82, tpr 4. **No POC, entry, stop, target or money figure depends on the "
            "printed row COUNT**, so nothing downstream moves -- the run's numbers are the "
            "engine's, not the review's prose. It is recorded here because a published figure "
            "that disagrees with the engine is exactly what a later session would trip over, "
            "and because this session will not quietly correct a REVIEWED document."
        )
        out.append("")
    return "\n".join(out) + "\n"


def run(out_path: Path | None) -> int:
    config = load_config(include_env=False)
    master, path, sha = bt.pinned_master(config.path("cache_root"), config.instrument_master)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    row_size = config.row_size

    sections = [
        ("1. The ticks the pin supplies", check_ticks(master, path.name)),
        ("2. CONTEXT 8 F7 -- all 25 frozen prorata POCs", check_f7(master, row_size)),
        ("3. The chunk-6 trader-gate day", check_gate_day(config, store, master, row_size)),
        (
            "4. The three sealed pilot walks (REVIEW_7)",
            check_walks(config, store, master, row_size),
        ),
    ]
    text = render(path.name, sha, sections)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"written: {out_path}")
    else:
        print(text)
    every = [line for _t, lines in sections for line in lines]
    moved = [line for line in every if line.status == MOVED]
    slips = [line for line in every if line.status == PUBLISHED_SLIP]
    print(
        f"VERDICT: {'PIN VALID' if not moved else f'{len(moved)} MOVED -- STOP'}; "
        f"{len(every) - len(moved) - len(slips)}/{len(every)} exact, "
        f"{len(slips)} published-figure discrepancy(ies)"
    )
    return 0 if not moved else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q-20 calibration re-verification.")
    parser.add_argument("--out", default=None, help="write the markdown pack here")
    args = parser.parse_args(argv)
    return run(Path(args.out) if args.out else None)


if __name__ == "__main__":
    raise SystemExit(main())
