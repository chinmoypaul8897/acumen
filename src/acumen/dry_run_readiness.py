"""THE DRY-RUN-WEEK READINESS GATE (chunk 15): one command, seven checks, a named refusal.

    python -m acumen.run_screener --readiness --day <TODAY>
    python -m acumen.run_screener --readiness --day <TODAY> --send-test-message

plan.md's chunk-15 card is *"five live sessions in parallel with his manual trading ... zero
unhandled errors across 5 sessions"*. Everything that would break that week breaks it on the
FIRST morning, at 11:30, for a reason that was knowable at 08:00 the day before: a ``.env`` short
one key, a day's-own-master that never landed, a holiday cache nobody refreshed, a universe that
quietly grew back to 210, a fence that stopped fencing, a chat id that was typed wrong.

So this is the one command the operator runs ONCE, before the week, and it CERTIFIES rather than
reports. Every check is a fact about this machine read from this machine; none of them is a
promise. It answers :data:`READY_LINE` or it REFUSES with the name of what is missing and what to
do about it -- there is no partial pass, because a week that starts on six of seven is a week
that discovers the seventh on Wednesday.

**What it never does.** It places no order (nothing in this repository can -- see
``tests/test_live_safety.py``, which this gate RUNS rather than cites). It prints no credential
and returns none: :func:`check_credentials` learns whether two keys EXIST and nothing else, and
the only value that leaves this process is the one Telegram's own endpoint receives, from
:func:`acumen.telegram_sink.post_message`, which is the single place in the repo that reads
either key. It writes nothing under ``data_root`` or ``cache_root``. And it sends exactly one
message, only when the operator asks for it in a separate flag, and that message names no stock,
no price and no trade.

**Why the test message is opt-in AND required.** Opt-in, because a gate that messages somebody's
phone as a side effect of being run is a gate nobody runs twice. Required, because a chat this
tool has never reached is a chat nobody has evidence about: a wrong chat id, a bot the trader
never pressed Start on, and a token that was revoked all look exactly like a quiet morning. So
the check is present in every report, and until it has really been sent it reads NOT SENT and the
gate refuses. One flag, once, before the week.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Mapping

from . import backtest as bt
from . import calendar as cal
from . import live_screener as ls
from . import telegram_sink as tg
from .config import MASTER_CACHE_SUBDIR, Config, load_config

#: The repository root, for the tripwire suite. ``config.py``'s own anchor, reused rather than
#: re-derived, so a session cannot end up scanning a different tree from the one it imports.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: The tripwire module this gate RUNS. Named here because the runbook quotes it and a test pins
#: that the file exists -- a gate that cites a suite nobody runs is the shape REVIEW_14 B2 named.
TRIPWIRE_SUITE: str = "tests/test_live_safety.py"

#: How long the tripwire suite may take before the gate calls it unproven rather than green.
TRIPWIRE_TIMEOUT_SECONDS: float = 600.0

#: CONTEXT 4.6's sealed count, and QUESTIONS.md Q-30's ruling in one number: *"a live morning
#: screens the 204 SETTLED symbols only ... the 6 quarantined are never screened"*. It is a
#: figure of the LAW, not a tuning constant -- which is why the gate asserts it rather than
#: printing whatever it finds.
SETTLED_UNIVERSE_SIZE: int = 204

#: The six CONTEXT 4.6 quarantines, in the ruling's own order. Checked by name, not by count: a
#: register that had settled one of them and quarantined a different one would still count six.
QUARANTINED: tuple[str, ...] = ("APLAPOLLO", "ASTRAL", "IEX", "NTPC", "UPL", "VBL")

# --- the seven checks, named once so the runbook and the tests read the same words -------------

CHECK_CREDENTIALS: str = "telegram credentials in .env"
CHECK_MASTER: str = "the day's own instrument master"
CHECK_CALENDAR: str = "the published NSE calendar"
CHECK_UNIVERSE: str = "the settled universe"
CHECK_FENCE: str = "the store fence"
CHECK_TRIPWIRES: str = "the safety tripwires"
CHECK_TEST_MESSAGE: str = "a test message to the configured chat"

#: Every check, in the order the report prints them: the cheap local facts first, the suite next,
#: and the one act that leaves this machine last.
CHECKS: tuple[str, ...] = (
    CHECK_CREDENTIALS, CHECK_MASTER, CHECK_CALENDAR, CHECK_UNIVERSE,
    CHECK_FENCE, CHECK_TRIPWIRES, CHECK_TEST_MESSAGE,
)

READY_LINE: str = "READY for a live dry-run week"
NOT_READY_LINE: str = "NOT READY for a live dry-run week -- do not start it"

#: The test message's first line. A phone that receives this must not be able to read it as a
#: signal, so the heading says what it is before anything else does.
TEST_MESSAGE_HEADING: str = "ACUMEN -- TEST MESSAGE (not an alert)"

#: What the test message says when it has NOT been sent. The gate refuses on this sentence, and
#: the sentence carries its own remedy, because a refusal an operator cannot act on is a wall.
TEST_MESSAGE_NOT_SENT: str = (
    "NOT SENT. This gate cannot certify a chat it has never reached: a wrong chat id, a bot the "
    "trader never pressed Start on, and a revoked token all look exactly like a quiet morning. "
    "Re-run this command once with --send-test-message"
)


@dataclass(frozen=True)
class ReadinessCheck:
    """One certified fact about this machine: what was asked, the answer, and the evidence."""

    name: str
    ok: bool
    detail: str
    figures: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReadinessReport:
    """The whole gate. :attr:`ready` is the AND of every check AND of their completeness."""

    day: date
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return (
            tuple(check.name for check in self.checks) == CHECKS
            and all(check.ok for check in self.checks)
        )

    @property
    def refusals(self) -> tuple[str, ...]:
        """Every check that says no, by name. What the refusal line is built from."""
        missing = tuple(
            f"{name}: NOT CHECKED -- this report does not carry it at all"
            for name in CHECKS if name not in {check.name for check in self.checks}
        )
        return tuple(
            f"{check.name}: {check.detail}" for check in self.checks if not check.ok
        ) + missing

    def render(self) -> str:
        width = max(len(name) for name in CHECKS)
        lines = [
            "=" * 78,
            f"ACUMEN -- DRY-RUN-WEEK READINESS   {self.day.isoformat()}",
            "=" * 78,
        ]
        for check in self.checks:
            lines.append(
                f"[{'ok  ' if check.ok else 'FAIL'}] {check.name:<{width}}  {check.detail}"
            )
        lines.append("=" * 78)
        lines.append(READY_LINE if self.ready else NOT_READY_LINE)
        for refusal in self.refusals:
            # The REASON, by name, under the verdict -- a gate that refuses without saying what
            # is missing sends the operator to read code at 08:00.
            lines.append(f"  -> {refusal}")
        lines.append("=" * 78)
        return "\n".join(lines) + "\n"


# --- the seven checks ---------------------------------------------------------------------------


def check_credentials() -> ReadinessCheck:
    """Are BOTH Telegram keys in ``.env``? The key NAMES travel; no value is ever read out.

    CLAUDE.md rule 4 is absolute here: this function learns two booleans. It cannot return, log
    or render a value, and the names it prints are constants of this repository's own source
    (:data:`acumen.telegram_sink.ENV_BOT_TOKEN` and :data:`~acumen.telegram_sink.ENV_CHAT_ID`),
    which are not secrets and are what an operator needs in order to fix the file.
    """
    from .config import env_value

    present = {
        name: bool(env_value(name, required=False))
        for name in (tg.ENV_BOT_TOKEN, tg.ENV_CHAT_ID)
    }
    missing = sorted(name for name, found in present.items() if not found)
    return ReadinessCheck(
        name=CHECK_CREDENTIALS, ok=not missing,
        detail=(
            "both keys present (values never read, printed or logged)" if not missing
            else f"MISSING from .env: {', '.join(missing)}. Add them; the file is gitignored"
        ),
        figures={"present": sorted(present), "missing": missing},
    )


def check_master(day: date, *, cache_dir: Path) -> ReadinessCheck:
    """Does THE DAY'S OWN instrument master resolve, and is it on disk (CONTEXT 4.7 / Q-29)?

    Two facts, not one. The NAME is resolved through :func:`acumen.live_screener.
    day_master_filename` -- the same function the pre-open fetch, the screener and the
    verification all use -- so the gate proves the resolution as well as the file. A live morning
    REFUSES to start without this dump, by design, and finding that out at 09:14 is the failure
    this gate exists to move to the day before.
    """
    name = ls.day_master_filename(day)
    path = Path(cache_dir) / MASTER_CACHE_SUBDIR / name
    ok = path.is_file()
    return ReadinessCheck(
        name=CHECK_MASTER, ok=ok,
        detail=(
            f"{name} is on disk ({path.stat().st_size:,} bytes)" if ok else
            f"{name} is NOT at {path}. A live morning runs on the DAY'S OWN dump (CONTEXT 4.7 / "
            "Q-29) and refuses to start without it. Run the pre-open refresh first, or "
            "`python -m acumen.instrument_master --allow-network`"
        ),
        figures={"master_file": name, "path": str(path), "present": ok},
    )


def check_calendar(day: date, *, cache_dir: Path) -> ReadinessCheck:
    """Does the PUBLISHED NSE holiday master load, offline, and what does it say about ``day``?

    Offline on purpose: the day-cache is what a real 08:45 reads (CONTEXT 4.1's courtesy rule,
    and the 31-Jul-2026 offline ruling -- what is on disk is served at any age). A gate that
    pulled would certify a network rather than a machine.
    """
    try:
        calendar = cal.fetch_calendar(cache_dir=Path(cache_dir), today=day, allow_network=False)
    except Exception as exc:
        return ReadinessCheck(
            name=CHECK_CALENDAR, ok=False,
            detail=(
                f"{type(exc).__name__}: {str(exc).rstrip('.')}. The PUBLISHED master governs a "
                "live morning "
                "(QUESTIONS.md C5) and the store-derived calendar cannot answer for today by "
                "construction, so there is no fallback. Run the pre-open refresh with "
                "--allow-network once"
            ),
            figures={"loaded": False},
        )
    try:
        trading = calendar.is_trading_day(day)
        standard = calendar.is_standard_session(day)
    except Exception as exc:
        return ReadinessCheck(
            name=CHECK_CALENDAR, ok=False,
            detail=f"the calendar loaded but cannot answer for {day.isoformat()}: "
                   f"{type(exc).__name__}: {exc}",
            figures={"loaded": True},
        )
    return ReadinessCheck(
        name=CHECK_CALENDAR, ok=True,
        detail=(
            f"{len(calendar.holidays)} holiday(s) over {sorted(calendar.covered_years)}; "
            f"{day.isoformat()} trading={trading} standard={standard}"
        ),
        figures={
            "loaded": True, "holidays": len(calendar.holidays),
            "is_trading_day": trading, "is_standard_session": standard,
        },
    )


def check_universe(*, data_root: Path) -> ReadinessCheck:
    """Does the settled universe still filter to 204, through the SHIPPED filter?

    Not a count of the register: the register is handed to
    :func:`acumen.live_screener._screened_universe`, which is the function a live morning really
    uses, and the answer is what that function screens. REVIEW_13 **M2** measured the alternative
    -- a live morning sweeping the raw F&O list, all six quarantined symbols included, on which
    the backtester walked ZERO days of 495,312.
    """
    try:
        register = bt.load_residual_register(
            Path(data_root) / bt.RESIDUAL_LEDGER_RELPATH
        )
    except Exception as exc:
        return ReadinessCheck(
            name=CHECK_UNIVERSE, ok=False,
            detail=f"the chunk-5B disclosed-residual register cannot be read: "
                   f"{type(exc).__name__}: {exc}",
            figures={"settled": 0},
        )
    screened, excluded = ls._screened_universe(
        sorted(register), live=True, data_dir=None, residual=register,
    )
    quarantined = tuple(sorted(symbol for symbol, _why in excluded))
    ok = len(screened) == SETTLED_UNIVERSE_SIZE and quarantined == QUARANTINED
    return ReadinessCheck(
        name=CHECK_UNIVERSE, ok=ok,
        detail=(
            f"{len(screened)} settled symbol(s) screened, {len(excluded)} excluded by name "
            f"({', '.join(quarantined)})" if ok else
            f"the live filter screens {len(screened)} symbol(s), not "
            f"{SETTLED_UNIVERSE_SIZE} (CONTEXT 4.6 / Q-30); excluded: "
            f"{', '.join(quarantined) or 'none'}"
        ),
        figures={
            "settled": len(screened), "excluded": list(quarantined),
            "expected": SETTLED_UNIVERSE_SIZE,
        },
    )


def check_fence(*, data_root: Path, cache_root: Path) -> ReadinessCheck:
    """Is the corporate-action fence ACTIVE for both stores, asked as a real morning asks it?

    REVIEW_14 B1 measured what an unfenced morning did: 22 corporate-action year files rewritten
    inside the snapshot-protected tree, 45 seconds of paced network in the pre-open, and a
    ``factor_digest`` that stopped being stable for an unchanged span. The fence is pure and
    decides nothing here; it is asked the same question ``refresh_corporate_actions`` asks it,
    with the roots a real morning runs under, for both of them.
    """
    answers = {}
    for label, cache_dir in (
        ("data_root", Path(data_root) / bt.CA_CACHE_SUBDIR),
        ("cache_root", Path(cache_root) / "ca"),
    ):
        _resolved, may_network, reason = bt.fence_ca_cache(
            cache_dir=cache_dir, allow_network=True,
            data_root=Path(data_root), cache_root=Path(cache_root),
        )
        answers[label] = (may_network, reason)
    unfenced = [label for label, (may, _why) in answers.items() if may]
    fenced_reason = answers["data_root"][1]
    return ReadinessCheck(
        name=CHECK_FENCE, ok=not unfenced,
        detail=(
            "ACTIVE on both stores -- a refresh downgrades to the day-cache and writes nothing "
            f"({fenced_reason.split(':')[0]})" if not unfenced else
            f"NOT fenced for {', '.join(unfenced)}: a --refresh --allow-network morning would "
            "WRITE inside the stores (CLAUDE.md data-store safety, REVIEW_14 B1)"
        ),
        figures={
            "fenced": {label: not may for label, (may, _why) in answers.items()},
            "reason": fenced_reason,
        },
    )


def check_tripwires(
    *, repo_root: Path | None = None,
    runner: Callable[[list[str], Path], tuple[int, str]] | None = None,
) -> ReadinessCheck:
    """Are the safety tripwires GREEN -- by running them, not by citing them.

    ``tests/test_live_safety.py`` is the no-order-endpoint scan (source text AND AST, over
    ``src``, ``tests``, ``scripts`` and ``docs/evidence``), the allowed-broker-call list, the
    credential rules and the live mode's own refusals. Running it is the difference between
    *"there is a tripwire"* and *"the tripwire is green on this tree, right now"* -- and
    REVIEW_14 **B2** is the standing lesson about tests that assert their own name.

    A suite that cannot be run at all is NOT a pass. It is a refusal with the reason on it: the
    gate certifies, and there is nothing to certify from an exit code that never happened.
    """
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    suite = root / TRIPWIRE_SUITE
    if not suite.is_file():
        return ReadinessCheck(
            name=CHECK_TRIPWIRES, ok=False,
            detail=f"{TRIPWIRE_SUITE} is not at {suite}: this gate certifies a repository, and "
                   "an installed package without its tests is not one",
            figures={"ran": False},
        )
    argv = [
        sys.executable, "-m", "pytest", str(suite),
        "-q", "--no-header", "-p", "no:cacheprovider",
    ]
    try:
        code, output = (
            runner(argv, root) if runner is not None else _run(argv, root)
        )
    except Exception as exc:
        return ReadinessCheck(
            name=CHECK_TRIPWIRES, ok=False,
            detail=f"{TRIPWIRE_SUITE} could not be RUN ({type(exc).__name__}: {exc}), so "
                   "nothing about it is certified",
            figures={"ran": False},
        )
    summary = [line for line in output.splitlines() if line.strip()]
    tail = summary[-1].strip() if summary else "(no output)"
    return ReadinessCheck(
        name=CHECK_TRIPWIRES, ok=code == 0,
        detail=(
            f"{TRIPWIRE_SUITE} GREEN -- {tail}" if code == 0 else
            f"{TRIPWIRE_SUITE} FAILED (exit {code}) -- {tail}. Read it before anything else: "
            "these are the rules with real money behind them"
        ),
        figures={"ran": True, "exit": code, "summary": tail},
    )


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    """Run one subprocess and return ``(exit code, combined output)``. No shell, ever."""
    done = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True,
        timeout=TRIPWIRE_TIMEOUT_SECONDS,
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def test_message(day: date) -> str:
    """The ONE message this gate may send. It names no stock, no price and no trade.

    A phone is a small screen with no context on it, so the message says what it is on its first
    line and again on its last. It is deliberately boring: the trader's only job on receiving it
    is to confirm that he did.
    """
    return "\n".join((
        f"{TEST_MESSAGE_HEADING}   {day.isoformat()}",
        "The operator ran the dry-run-week readiness check on his own machine and asked it to "
        "send you one message.",
        "There is nothing to do and nothing to trade. No stock, no price, no signal.",
        "If you can read this, the alerts have somewhere to arrive.",
        "THIS TOOL PLACES NO ORDERS.",
    ))


def check_test_message(
    day: date, *, send: bool, transport: Callable[[str], None] | None = None
) -> ReadinessCheck:
    """Can a message actually reach the configured chat? Opt-in, one message, clearly a test.

    See the module docstring for why this is both opt-in and required. ``transport`` exists so a
    test can watch the bytes without a network; the default is
    :func:`acumen.telegram_sink.post_message`, which is the one place in this repository that
    reads a credential and the one place that makes a request.
    """
    if not send:
        return ReadinessCheck(
            name=CHECK_TEST_MESSAGE, ok=False, detail=TEST_MESSAGE_NOT_SENT,
            figures={"sent": False, "attempted": False},
        )
    text = test_message(day)
    post = transport if transport is not None else tg.post_message
    try:
        post(text)
    except Exception as exc:
        return ReadinessCheck(
            name=CHECK_TEST_MESSAGE, ok=False,
            detail=(
                f"the send FAILED: {type(exc).__name__}: {exc}. Nothing about the failure names "
                "a credential; check the two keys in .env and that the trader has pressed Start "
                "on the bot"
            ),
            figures={"sent": False, "attempted": True, "error": type(exc).__name__},
        )
    return ReadinessCheck(
        name=CHECK_TEST_MESSAGE, ok=True,
        detail=(
            "ONE message sent to the configured chat, headed "
            f"'{TEST_MESSAGE_HEADING}'. Ask the trader to confirm he saw it"
        ),
        figures={"sent": True, "attempted": True, "lines": len(text.splitlines())},
    )


# --- the gate ------------------------------------------------------------------------------------


def assess(
    *,
    day: date,
    config: Config | None = None,
    send_test_message: bool = False,
    transport: Callable[[str], None] | None = None,
    repo_root: Path | None = None,
    tripwire_runner: Callable[[list[str], Path], tuple[int, str]] | None = None,
) -> ReadinessReport:
    """Run every check, in order, and return the report. Never raises; refuses instead.

    Each check is independent by construction: one failure must not hide the next, because an
    operator fixing them one per run is an operator who does not start the week. A check that
    RAISES is reported as a refusal naming the exception, which is the same discipline
    :func:`acumen.live_refresh.morning_refresh` holds every step to.
    """
    settings = config if config is not None else load_config(include_env=False)
    data_root, cache_root = settings.path("data_root"), settings.path("cache_root")
    plan: tuple[tuple[str, Callable[[], ReadinessCheck]], ...] = (
        (CHECK_CREDENTIALS, check_credentials),
        (CHECK_MASTER, lambda: check_master(day, cache_dir=cache_root)),
        (CHECK_CALENDAR, lambda: check_calendar(day, cache_dir=cache_root)),
        (CHECK_UNIVERSE, lambda: check_universe(data_root=data_root)),
        (CHECK_FENCE, lambda: check_fence(data_root=data_root, cache_root=cache_root)),
        (CHECK_TRIPWIRES, lambda: check_tripwires(
            repo_root=repo_root, runner=tripwire_runner
        )),
        (CHECK_TEST_MESSAGE, lambda: check_test_message(
            day, send=send_test_message, transport=transport
        )),
    )
    checks: list[ReadinessCheck] = []
    for name, run in plan:
        try:
            checks.append(run())
        except Exception as exc:  # a check that raises is a refusal, never a traceback
            checks.append(ReadinessCheck(
                name=name, ok=False,
                detail=f"the check itself failed: {type(exc).__name__}: {exc}",
                figures={"raised": type(exc).__name__},
            ))
    return ReadinessReport(day=day, checks=tuple(checks))


__all__ = [
    "CHECKS",
    "CHECK_CALENDAR",
    "CHECK_CREDENTIALS",
    "CHECK_FENCE",
    "CHECK_MASTER",
    "CHECK_TEST_MESSAGE",
    "CHECK_TRIPWIRES",
    "CHECK_UNIVERSE",
    "NOT_READY_LINE",
    "QUARANTINED",
    "READY_LINE",
    "REPO_ROOT",
    "ReadinessCheck",
    "ReadinessReport",
    "SETTLED_UNIVERSE_SIZE",
    "TEST_MESSAGE_HEADING",
    "TEST_MESSAGE_NOT_SENT",
    "TRIPWIRE_SUITE",
    "TRIPWIRE_TIMEOUT_SECONDS",
    "assess",
    "check_calendar",
    "check_credentials",
    "check_fence",
    "check_master",
    "check_test_message",
    "check_tripwires",
    "check_universe",
    "test_message",
]
