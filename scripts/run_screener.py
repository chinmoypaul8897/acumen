"""Launcher for the live screener -- the operator's documented morning command (chunk 15).

The implementation lives in the package at ``src/acumen/run_screener.py``; this file only
forwards to it (the same bare-clone bootstrap every other launcher uses -- REVIEW_2 F12,
chunk-0 B2):

    acumen-screener                 --mode live --day <TODAY> --refresh --allow-network
    python -m acumen.run_screener   --mode live --day <TODAY> --refresh --allow-network
    python scripts/run_screener.py  --mode live --day <TODAY> --refresh --allow-network

The first two need the project installed (``pip install -e .``); the console script is declared
in pyproject.toml. **The third is the un-installed path, and it is the one the runbook gives**,
because a morning card whose first command depends on an editable install that nobody re-runs
after a fresh clone is a card that fails at 08:45 with ``No module named 'acumen'``. Chunk 14's
own stub printed the ``-m`` form and no test ever ran it as a shell command -- every test drove
``run_screener.main([...])`` in-process, where ``pyproject.toml``'s ``pythonpath = ["src"]``
had already put the package on the path. ``docs/morning_runbook.md`` fixes that, and
``tests/test_morning_runbook.py`` runs this file as a real subprocess so it cannot come back.

It opens no broker session unless the morning really starts one, places no order (nothing in
this repository can), and prints no credential.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    """Return the packaged ``main``, adding ``src/`` to the path only if it is not installed."""
    try:
        from acumen.run_screener import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.run_screener import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
