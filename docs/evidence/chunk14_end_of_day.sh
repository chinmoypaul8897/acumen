#!/bin/sh
# chunk14_end_of_day.sh -- the end-of-day summary, exercised through the SHIPPED CLI.
#
# The architect's 14-Aug-2026 ruling: "the END-OF-DAY SUMMARY is a card line item and lands in
# chunk 14 -- routed to the phone via the sink at close, not only the terminal." The unit tests
# in tests/test_telegram_sink.py pin the message byte for byte on synthetic alerts; this is the
# other half of the evidence -- the same code reached through `python -m acumen.run_screener` on
# a REAL symbol-day out of the minute lake, so the alert list in the message is one the engine
# produced rather than one a test wrote.
#
# STORE SAFETY (CLAUDE.md). Read-only: the lake is READ in place, never linked or copied, and
# --recording-root sends every byte this run writes to a temp directory OUTSIDE both stores and
# outside the repository. Nothing under data_root or cache_root is created, changed or deleted.
#
# CREDENTIALS. There are none on this path. --live-alerts is NOT passed, so the sink is in DRY
# RUN: it prints the message it would have sent and reaches no transport, reads no .env key and
# opens no socket. That is why this script is safe to re-run by anyone.
#
# Usage:  sh docs/evidence/chunk14_end_of_day.sh <recording-root>
set -eu

ROOT="${1:-${TMPDIR:-/tmp}/acumen-chunk14-eod}"

PYTHONPATH=src python -m acumen.run_screener \
    --mode replay \
    --day 2026-06-10 \
    --symbols HDFCBANK,ICICIBANK \
    --telegram \
    --recording-root "$ROOT"
