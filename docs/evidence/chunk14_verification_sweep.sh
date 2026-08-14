#!/usr/bin/env bash
# chunk 14 -- the end-of-chunk verification sweep, run from the machine.
#
# CLAUDE.md, data-store safety: "Operator-executed runbooks are relayed, not certified ... an
# independent verification sweep of every step's completion evidence read from the machine
# itself". The same standard is applied here to this chunk's OWN claims: the test count and the
# "zero store writes" property are re-derived rather than quoted from the build's transcript.
#
# Three steps, in this order, so that the store reading BRACKETS a full test run:
#   1. fingerprint data_root (the committed housekeeping script, unedited)
#   2. clone the repository to a scratch tree and run the whole suite there from clean
#   3. fingerprint data_root again and diff -- an empty diff is the read-only proof
#
# READ-ONLY over the stores by construction: step 1 and 3 open every file "rb"; step 2 runs the
# suite, which is the thing being proved not to write. The clone is a COPY of the repository and
# the stores are reached by their absolute config.yaml paths -- never linked, junctioned or
# symlinked into the disposable tree (CLAUDE.md, Q-18 incident).
#
# Usage:  bash docs/evidence/chunk14_verification_sweep.sh <scratch-dir>

set -u
S="${1:?usage: chunk14_verification_sweep.sh <scratch-dir>}"
REPO="C:/Users/chinm/acumen"
STORE="C:/Users/chinm/acumen-data"
CLONE="$S/clone14"

echo "=== step 1: store fingerprint BEFORE ==="
date
python "$REPO/docs/evidence/housekeeping_13aug_store_fingerprint.py" "$STORE" > "$S/fp_before.json" 2>&1
cat "$S/fp_before.json"

echo "=== step 2: clean clone at HEAD ==="
rm -rf "$CLONE"
git clone --quiet "$REPO" "$CLONE"
cd "$CLONE" || exit 1
git log --oneline -1
git status --short
echo "clone has .env?: $(test -f .env && echo YES || echo no)"
echo "clone has logs/?: $(test -d logs && echo YES || echo no)"

echo "=== step 3: pytest from clean ==="
date
python -m pytest -q -p no:cacheprovider > "$S/pytest_clone.txt" 2>&1
echo "pytest exit=$?"
tail -25 "$S/pytest_clone.txt"
date

echo "=== step 4: store fingerprint AFTER ==="
python "$REPO/docs/evidence/housekeeping_13aug_store_fingerprint.py" "$STORE" > "$S/fp_after.json" 2>&1
cat "$S/fp_after.json"

echo "=== step 5: before/after diff (empty == zero store writes) ==="
diff "$S/fp_before.json" "$S/fp_after.json" && echo "STORE UNCHANGED ACROSS THE RUN"
date
echo "=== sweep done ==="
