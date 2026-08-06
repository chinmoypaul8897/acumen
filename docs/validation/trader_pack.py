"""Generator for `docs/validation/trader_pack.md` -- the chunk-12 trader validation pack.

Committed HERE, beside its own output, under the same rule the report and the evidence packs
follow (CLAUDE.md git rules, REVIEW_7 finding C3): a session making claims from real store data
commits the generating script and its output. A later session can re-run this and diff -- and it
must come back byte-identical, in BOTH files (REVIEW_8 finding C2).

    python docs/validation/trader_pack.py

Read-only over the stores: it opens the completed run ledger and its manifest, the per-symbol
shards for the six days it replays, the 1-minute lake and the daily store, and writes exactly two
files inside the repo (the pack and its JSON companion). The implementation lives in the package
at `src/acumen/trader_pack.py`; this file is the launcher, with the same bare-clone bootstrap the
other launchers use (REVIEW_2 F12).

It takes a while -- the ledger is streamed twice, the six days are replayed through the very
engines the run walked (each one needs that symbol's whole ten-year bias series, because the
carry is path dependent), and the rounding probe rebuilds a year of volume profiles two ways.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_main() -> Callable[..., int]:
    try:
        from acumen.trader_pack import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from acumen.trader_pack import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
