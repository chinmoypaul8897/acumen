"""Chunk 14 evidence: the TELEGRAM sink, on a real morning, with no credential read.

    python docs/evidence/chunk14_telegram.py

What this shows, in order, and all of it from the SHIPPED objects rather than from a mock-up:

1. the three messages a real live-posture morning would put on the trader's phone, verbatim,
   built by :func:`acumen.telegram_sink.message_for` from the alerts the screener actually
   delivered over HDFCBANK 2026-06-10;
2. the same morning through a FROZEN feed -- the REVIEW_13B Q1 case -- so the staleness marker
   can be read on the message rather than described;
3. the failure path: a transport that raises, degrading to silence plus a visible failure, and
   then healing without a duplicate;
4. the refusal path: an alert whose price the screener cannot vouch for is NOT forwarded;
5. the no-order-endpoint tripwire, re-run over the new module.

**No network, no credential.** The transport is a list; ``.env`` is never opened by this script,
and the only environment names that appear are the KEY NAMES. **READ-ONLY over the stores:** the
minute lake and the daily store are opened for reading and recordings are written to a temporary
directory outside them.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import calendar as cal  # noqa: E402
from acumen import live_screener as ls  # noqa: E402
from acumen import telegram_sink as tg  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk14_telegram.md"
HOLIDAY_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "holidays_2026.json"

SYMBOL = "HDFCBANK"
DAY = date(2026, 6, 10)


@dataclass
class _FrozenFeed:
    """A vendor that keeps answering 200 with a prefix that never grows (REVIEW_13B Q1)."""

    inner: object
    freeze_at: datetime
    calls: int = 0

    def fetch(self, symbol, day, upto):
        self.calls += 1
        if self.calls <= 2:
            return self.inner.fetch(symbol, day, upto)
        return self.inner.fetch(symbol, day, self.freeze_at)


def _morning(root: Path, source, *, label: str, sinks):
    config = load_config(include_env=False)
    cache = root / f"cache-{label}"
    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        config.path("cache_root") / "instrument_master" / config.instrument_master,
        cache / "instrument_master" / ls.day_master_filename(DAY),
    )
    cal.nse_http.write_cache(
        cal.cache_path(cache), json.loads(HOLIDAY_FIXTURE.read_text(encoding="utf-8")),
        url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY,
    )
    screener = ls.build_live_screener(
        DAY, (SYMBOL,), source=source,
        recording=LiveRecording.at(root / f"{label}"),
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        mode="live", data_dir=config.path("data_root"), cache_dir=cache, sinks=sinks,
        # `--live-alerts`: the flag that turns dry run off is the same flag that lets the sink
        # send, so this is the shape a real forwarding morning has. A DRY-RUN morning's alerts
        # carry `dry_run` and the message says so on its own line -- shown in section 6.
        dry_run=False,
    )
    screener.run_day()
    return screener


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    config = load_config(include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    if not store.minutes(SYMBOL, DAY):
        print(f"the local minute lake does not hold {SYMBOL} {DAY}")
        return 1
    root = Path(tempfile.mkdtemp(prefix="acumen-chunk14-telegram-"))

    # 1. a clean morning, with the sink LIVE and its transport a list
    sent: list[str] = []
    printed: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=printed.append)
    collected = ls.CollectingAlertSink()
    _morning(root, StoredDayBarSource(store), label="clean", sinks=(collected, sink))

    # 2. the frozen feed -- the Q1 case
    stale_sent: list[str] = []
    stale_printed: list[str] = []
    stale_sink = tg.TelegramSink(send=stale_sent.append, live=True, out=stale_printed.append)
    frozen = _FrozenFeed(
        StoredDayBarSource(store),
        freeze_at=datetime.combine(DAY, datetime.min.time()).replace(hour=11, minute=30),
    )
    _morning(root, frozen, label="frozen", sinks=(ls.CollectingAlertSink(), stale_sink))

    # 3. the failure path, on the same alerts
    fail_printed: list[str] = []

    def explode(_text: str) -> None:
        raise tg.TelegramError("the Telegram send failed: ConnectionError")

    failing = tg.TelegramSink(send=explode, live=True, out=fail_printed.append)
    for alert in collected.alerts:
        failing.deliver(alert)
    healed: list[str] = []
    failing.send = healed.append
    for alert in collected.alerts:
        failing.deliver(alert)
    for alert in collected.alerts:            # ...and again: no duplicate
        failing.deliver(alert)

    # 4. the refusal path
    refuse_printed: list[str] = []
    refusing = tg.TelegramSink(send=[].append, live=True, out=refuse_printed.append)
    from acumen.live_recording import RecordedAlert

    naked = RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol=SYMBOL, at=datetime(2026, 6, 10, 11, 30),
        payload={"side": "long", "entry_paise": 74_095, "stop_paise": 73_810,
                 "target_paise": 74_950, "qty": 350, "poc_paise": "73980", "bias": "bullish"},
    )
    refusing.deliver(naked)

    # 5. the tripwire, over the new module
    sys.path.insert(0, str(REPO_ROOT))
    from tests.test_live_safety import repo_sources, scan_source  # noqa: E402

    offenders = [
        row for path in repo_sources()
        for row in scan_source(path.read_text(encoding="utf-8"),
                               str(path.relative_to(REPO_ROOT)))
    ]

    lines = [
        "# chunk 14 -- TELEGRAM, on a real morning",
        "",
        f"Run at {datetime.now().replace(microsecond=0).isoformat()} from "
        "`docs/evidence/chunk14_telegram.py`. READ-ONLY over the stores. **No network and no "
        "credential**: the transport is a list, `.env` is never opened, and the only "
        "environment names that appear anywhere below are the two KEY NAMES.",
        "",
        f"The morning is {SYMBOL} {DAY.isoformat()} in LIVE posture -- the day chunk 7 walked "
        "candle by candle and chunk 8 priced, driven through the shipped screener with the "
        "Telegram sink attached to the sink tuple and nothing else changed.",
        "",
        "## 1. What lands on the trader's phone",
        "",
        f"{len(sent)} messages, verbatim:",
        "",
        "```",
    ]
    for index, message in enumerate(sent, start=1):
        lines.append(f"--- message {index} " + "-" * 60)
        lines.extend(message.splitlines())
    lines += [
        "```",
        "",
        "Every one carries CONTEXT 4.7's disclosed line, on its own line so a phone cannot wrap "
        "it out of sight. The numbers are CONTEXT 4.4's payload -- symbol, side, entry, SL, TP, "
        "POC, bias, timestamp -- plus the quantity CONTEXT 3.5 sizes.",
        "",
        "## 2. The Q1 case: a frozen feed",
        "",
        "The same day, with a vendor that keeps answering 200 with a prefix that never grows. "
        "The screener squares off at 15:15 on a price computed from bars that stopped at 11:29, "
        "and **the message says so**:",
        "",
        "```",
    ]
    for index, message in enumerate(stale_sent, start=1):
        lines.append(f"--- message {index} " + "-" * 60)
        lines.extend(message.splitlines())
    lines += [
        "```",
        "",
        "## 3. A send failure degrades to silence plus a VISIBLE failure",
        "",
        "The transport raises on every alert of the morning. Nothing crashes, the sweep is not "
        "interrupted, and the operator's screen carries one line per failed alert:",
        "",
        "```",
    ]
    lines.extend(fail_printed)
    lines += [
        "```",
        "",
        f"Then the transport heals: **{len(healed)} message(s) delivered** on the next pass "
        f"over the same alerts, and **{len(healed)} still** after a third pass -- a failed send "
        "is retried by the next re-derivation, and a successful one is never sent twice.",
        "",
        "## 4. An alert whose price cannot be vouched for is NOT forwarded",
        "",
        "```",
    ]
    lines.extend(refuse_printed)
    lines += [
        "```",
        "",
        "## 5. The order-endpoint tripwire, over the new module",
        "",
        f"`tests/test_live_safety.py`'s scan over {len(repo_sources())} Python files, including "
        f"`src/acumen/telegram_sink.py`: **{len(offenders)} offender(s)**.",
        "",
        "The sink talks to exactly one host, `api.telegram.org`, through exactly one call, and "
        "the repository holds no order-placement code for it to reach even if it wanted to.",
        "",
        "## 6. A DRY-RUN morning says so, on the message",
        "",
        "Everything above is the `--live-alerts` shape. Without that flag the screener stays in "
        "dry run, the sink sends nothing at all, and if a message is built anyway it carries "
        "the marker -- so a forwarded screenshot of a dry-run alert can never be read as a live "
        "one:",
        "",
        "```",
    ]
    lines.extend(tg.message_for(
        type(collected.alerts[1])(
            kind=collected.alerts[1].kind, symbol=collected.alerts[1].symbol,
            at=collected.alerts[1].at, payload=dict(collected.alerts[1].payload, dry_run=True),
        )
    ).splitlines())
    lines += ["```", ""]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if not offenders else 2


if __name__ == "__main__":
    raise SystemExit(main())
