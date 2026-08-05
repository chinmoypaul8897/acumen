"""Generator for `docs/reports/chunk9b_backtest_report.md` -- the chunk-9B backtest report.

Committed HERE, beside its own output, under the same rule the evidence packs follow
(CLAUDE.md git rules, REVIEW_7 finding C3): a session making claims from real store data commits
the generating script and its output. A later chunk can re-run this and diff -- and it must come
back byte-identical (REVIEW_8 finding C2).

    python docs/reports/chunk9b_backtest_report.py

Read-only over the stores: it opens the completed run ledger and its manifest, the chunk-9A pilot
ledger, the crashed run's retained shards, the disclosed-residual register, the 1-minute lake (for
the 15-minute equity path) and the daily store (for the benchmark's closes), and writes exactly
one markdown file inside the repo. The implementation lives in the package at
`src/acumen/report_9b.py`; this file is the launcher, with the same bare-clone bootstrap the other
launchers use (REVIEW_2 F12).

It takes a while -- the 15-minute path is assembled from every executed trade's own candles, which
is the one thing the ledger alone cannot supply.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_main() -> Callable[..., int]:
    try:
        from acumen.report_9b import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from acumen.report_9b import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
