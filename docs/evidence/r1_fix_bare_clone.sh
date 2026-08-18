#!/usr/bin/env bash
# REVIEW_15B R1 -- the verification that matters, run as the OPERATOR and not as pytest.
#
# The defect R1 names is invisible to a green suite: pyproject.toml's `pythonpath = ["src"]` is
# PYTEST's path, so every in-process test imports `acumen` happily while the command the operator
# actually types answers "No module named 'acumen'". The only way to see it is to leave pytest,
# clear PYTHONPATH and run the printed command from a bare clone -- which is what this does.
#
# It runs NOTHING that fetches or writes. The two commands whose real flags would touch the
# network or the stores (`run_screener --refresh --allow-network`, the `ca_report` ingest) are
# resolved with `--help`, which argparse answers before any body executes; the instrument-master
# fetch is run WITHOUT its `--allow-network` opt-in against a brand-new empty temp directory.
# Nothing here names data_root or cache_root. Flag-for-flag equivalence between the dead form and
# the launcher is proved separately, per site, in tests/test_review15b_fix.py, which parses every
# printed flag through that launcher's OWN parser.
#
# Usage:  bash docs/evidence/r1_fix_bare_clone.sh <path-for-the-clone> <path-for-a-temp-cache>
set -u

CLONE="${1:?a path for the bare clone}"
TMPCACHE="${2:?a path for a brand-new empty temp cache}"

git clone --quiet "$(git rev-parse --show-toplevel)" "$CLONE"
cd "$CLONE" || exit 1
mkdir -p "$TMPCACHE"
unset PYTHONPATH

echo "HEAD          : $(git log --oneline -1)"
echo "PYTHONPATH is : [${PYTHONPATH:-UNSET}]"
echo

echo "=== the three strings, read from the clone's own source ==="
PYTHONPATH=src python - <<'PY'
import re
from datetime import date
from pathlib import Path

from acumen import backtest as bt
from acumen import live_screener as ls

messages = []
try:
    ls._require_day_master(ls.day_master_filename(date(2026, 8, 18)), cache_dir=Path("nowhere"))
except ls.ScreenerError as exc:
    messages.append(("live_screener._require_day_master", str(exc)))
try:
    bt.named_master(Path("nowhere"), "OpenAPIScripMaster_2026-08-18.json")
except bt.BacktestError as exc:
    messages.append(("backtest.named_master", str(exc)))
messages.append(("backtest.CA_REFRESH_FENCED", bt.CA_REFRESH_FENCED))

for name, message in messages:
    for command in [q for q in re.findall(r"`([^`]+)`", message) if q.startswith("python ")]:
        print(f"{name}  ->  {command}")
PY
echo

echo "=== (a) the shell is a real operator shell: import acumen MUST fail ==="
python -c "import acumen" 2>&1 | tail -1
echo

echo "=== (b) the NEW command forms, same shell ==="
echo "-- site 1a: the pre-open refresh launcher --"
python scripts/run_screener.py --help 2>&1 | head -3
echo "-- site 1b / site 2: the master fetch, WITHOUT --allow-network, on an empty temp cache --"
python scripts/fetch_instrument_master.py --cache-dir "$TMPCACHE"
echo "   exit=$?  (1 on an empty cache is REVIEW_15B R4's disclosed conditional, not a failure)"
echo "-- site 3: the corporate-action ingest launcher --"
python scripts/ca_report.py --help 2>&1 | head -3
echo

echo "=== every flag the printed commands name, as each launcher's own --help lists it ==="
python scripts/fetch_instrument_master.py --help 2>&1 | sed -n '1p'
python scripts/run_screener.py --help 2>&1 | grep -oE "\-\-(mode|day|refresh|allow-network)" | sort -u | tr '\n' ' '; echo
python scripts/ca_report.py --help 2>&1 | grep -oE "\-\-(from|to|allow-network)" | sort -u | tr '\n' ' '; echo
echo

echo "=== control: the DEAD forms, same shell ==="
for module in acumen.run_screener acumen.instrument_master acumen.ca_report; do
    printf '%-34s -> ' "python -m $module"
    python -m "$module" --help 2>&1 | tail -1
done
