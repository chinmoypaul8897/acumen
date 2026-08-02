"""Q-18 T4 -- write the SEALED universe (the 210) as a frozen snapshot the run can be pinned to.

The architect's T4 ruling (QUESTIONS.md, 01-Aug-2026, verbatim):

    "T4 UNIVERSE: a REBUILD uses the SEALED universe (the 210). Re-fetch EXIDEIND and NUVAMA
    (network sanctioned for exactly these two, --symbols), full pipeline, include them in the
    reconciliation. Today's-F&O-list applies only to a deliberate, architect-signed universe
    refresh (CONTEXT 7-E5 clarification, goes into v1.5)."

`acumen.universe_backfill.resolve_universe` already accepts `--universe-snapshot`, a frozen
endpoint payload, instead of today's live list. This script writes that payload from the ONE
place the sealed universe survives: the COMMITTED `docs/backfill_minute_report.md`, whose
section-3 depth table has a row per symbol of the era CONTEXT 4.6 sealed. No symbol is typed
here, and nothing is fetched.

Run:  python docs/recovery/q18_sealed_universe.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from acumen.recovery_reconcile import SEALED_REPORT_RELPATH, read_report  # noqa: E402
from acumen.universe import parse_universe                                # noqa: E402

DEFAULT_OUT = REPO / "docs" / "recovery" / "sealed_universe_210.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the sealed 210-symbol universe snapshot.")
    parser.add_argument("--sealed", default=str(REPO / SEALED_REPORT_RELPATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    symbols = sorted(read_report(args.sealed).symbols)
    payload = {
        "_note": (
            "The SEALED F&O universe, read from the committed docs/backfill_minute_report.md "
            "section 3 -- NOT from the live endpoint. Written by "
            "docs/recovery/q18_sealed_universe.py under the architect's T4 ruling "
            "(QUESTIONS.md, 01-Aug-2026): a REBUILD uses the SEALED universe. Shape matches "
            "NSE's underlying-information payload so acumen.universe.parse_universe reads it."
        ),
        "data": {"UnderlyingList": [{"symbol": symbol} for symbol in symbols]},
    }
    parsed = parse_universe(payload)  # refuse to write anything the loader cannot read back
    assert tuple(symbols) == parsed, "round-trip mismatch"

    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out} with {len(parsed)} symbols")
    print(f"  first/last: {parsed[0]} .. {parsed[-1]}")
    for symbol in ("EXIDEIND", "NUVAMA"):
        print(f"  {symbol} present: {symbol in parsed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
