"""THE SAFETY RAILS (chunk 13), restated in tests because a rule nobody checks is a wish.

Three of them, and each is a rule someone wrote down before this chunk existed:

1. **NO ORDER PLACEMENT, ANYWHERE.** CONTEXT section 1 R4 (*"Read-only trading APIs. No
   order-placement code anywhere in this repo in v1"*) and CLAUDE.md rule 4. The screener alerts;
   the human trades. This is the rule with real money behind it and it is the one a live chunk is
   most likely to erode, one convenience at a time -- so it is enforced by a scan of the WHOLE
   package, at the source text AND through the AST, rather than by a promise in a docstring.
2. **Credentials are never printed, logged or committed.** Same rule, the other half.
3. **The screener degrades to SILENCE plus a visible failure banner, never to a wrong alert.**
   The per-symbol half is tested in ``tests/test_live_screener.py``; what is tested here is that
   the LIVE mode -- the one nobody may rely on until QUESTIONS.md **Q-28** is ruled -- refuses to
   start at all rather than starting and producing numbers.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

import pytest

from acumen import live_screener as ls
from acumen.live_recording import LiveRecording
from acumen.smartapi_client import Credentials, SmartApiClient

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "acumen"

#: Every SmartAPI entry point that PLACES, CHANGES or CANCELS anything at the exchange, in the
#: vendor's own spelling and in this repo's snake_case house style. Naming one of these in
#: ``src/acumen`` is a build failure, whether it is called, imported, or merely written down.
ORDER_ENDPOINTS: tuple[str, ...] = (
    "placeOrder", "place_order",
    "placeOrderFullResponse",
    "modifyOrder", "modify_order",
    "cancelOrder", "cancel_order",
    "gttCreateRule", "gttModifyRule", "gttCancelRule",
    "convertPosition", "convert_position",
    "createRule", "modifyRule", "cancelRule",
)

#: What the client is ALLOWED to call on the broker connection. Anything else is a finding.
ALLOWED_BROKER_CALLS: frozenset[str] = frozenset(
    {"generateSession", "terminateSession", "getCandleData"}
)


def package_sources() -> list[Path]:
    return sorted(path for path in PACKAGE.glob("*.py"))


def test_NO_ORDER_PLACEMENT_ENDPOINT_IS_NAMED_ANYWHERE_IN_THE_PACKAGE() -> None:
    """CONTEXT section 1 R4, enforced over every module in ``src/acumen``.

    A literal scan, because that is what catches the thing this rule is really about: a future
    session pasting a snippet from the vendor's documentation. It does not need to be reachable
    to be a breach -- an order call sitting behind a flag is an order call.
    """
    offenders: list[str] = []
    for path in package_sources():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#") and "ORDER_ENDPOINTS" in line:
                continue
            for endpoint in ORDER_ENDPOINTS:
                if endpoint in line:
                    offenders.append(f"{path.name}:{line_number} names {endpoint!r}")
    assert not offenders, (
        "CONTEXT section 1 R4: no order-placement code anywhere in this repo in v1. Found:\n"
        + "\n".join(offenders)
    )


def test_the_broker_connection_is_only_ever_asked_for_candles_or_a_session() -> None:
    """The AST half: what the package actually CALLS on the broker object.

    A literal scan can be walked around by ``getattr(connect, "place" + "Order")``. So every
    attribute access and every ``getattr`` string in the package is collected and checked against
    the three calls this repo is allowed to make -- login, logout, and the read-only
    ``getCandleData`` CONTEXT 4.3 and 4.4 both name as the one source of bars.
    """
    suspicious: list[str] = []
    for path in package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Attribute):
                name = node.attr
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr" and len(node.args) > 1
                  and isinstance(node.args[1], ast.Constant)
                  and isinstance(node.args[1].value, str)):
                name = node.args[1].value
            if name is None:
                continue
            lowered = name.lower()
            if ("order" in lowered or "gtt" in lowered) and name not in ALLOWED_BROKER_CALLS:
                # `ordered`, `order` as a local, `sort_order` etc. are English, not endpoints.
                if lowered in {"order", "ordered", "sort_order", "reorder", "ordering"}:
                    continue
                suspicious.append(f"{path.name}: .{name}")
    unexpected = [row for row in suspicious if any(e in row for e in ORDER_ENDPOINTS)]
    assert not unexpected, "an order endpoint is reachable by attribute:\n" + "\n".join(unexpected)

    # and the three calls the client really makes are exactly the allowed set
    client_text = (PACKAGE / "smartapi_client.py").read_text(encoding="utf-8")
    called = {
        node.func.attr
        for node in ast.walk(ast.parse(client_text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id in ("connect", "_connect")
    }
    called |= {
        node.func.attr
        for node in ast.walk(ast.parse(client_text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "_connect"
    }
    assert called <= ALLOWED_BROKER_CALLS, f"the client calls {sorted(called - ALLOWED_BROKER_CALLS)}"


def test_the_live_path_imports_no_broker_method_but_get_candles() -> None:
    """The screener's own source: one SmartAPI method is named on the whole live path."""
    live_modules = [PACKAGE / name for name in (
        "live_screener.py", "live_source.py", "live_recording.py",
        "live_dashboard.py", "live_refresh.py", "run_screener.py",
    )]
    for path in live_modules:
        text = path.read_text(encoding="utf-8")
        assert "placeOrder" not in text and "place_order" not in text
    source_text = (PACKAGE / "live_source.py").read_text(encoding="utf-8")
    assert "get_candles" in source_text
    assert source_text.count("self.client.") == 1, (
        "live_source touches the client exactly once, and it is the candle call"
    )


def test_a_credential_never_reaches_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAUDE.md rule 4. The repr is the accident waiting to happen -- a logged client object."""
    creds = Credentials(api_key="KEY-abc", client_code="C123", pin="4321", totp_secret="SECRET")
    for text in (repr(creds), str(creds)):
        for secret in ("KEY-abc", "4321", "SECRET"):
            assert secret not in text, f"{secret!r} leaked through the credential repr"

    client = SmartApiClient(credentials=creds)
    for secret in ("KEY-abc", "4321", "SECRET"):
        assert secret not in repr(client)


def test_the_LIVE_mode_REFUSES_TO_START_and_says_which_question_blocks_it(
    tmp_path: Path,
) -> None:
    """QUESTIONS.md Q-28, made structural.

    CONTEXT 3.3's POC needs CONTEXT 4.5 gate 1 to have PASSED, gate 1 needs TODAY's bhavcopy,
    and today's bhavcopy does not exist during today. This session did not decide what a live
    screener does about that -- so the live mode does not start, and it says so in the
    question's own words rather than failing with an obscure refusal from four layers down.

    This test is the STOP rule in executable form: it will go red the moment someone unblocks
    live without the ruling, which is exactly when someone should be stopped.
    """
    with pytest.raises(ls.BlockedByOpenQuestion) as caught:
        ls.build_live_screener(
            date(2026, 7, 17), ("SYNTH",),
            source=None, recording=LiveRecording.at(tmp_path / "r"),
            clock=ls.VirtualClock(stamp=datetime(2026, 7, 17, 9, 0)), mode="live",
        )
    message = str(caught.value)
    assert "Q-28" in message
    assert "gate 1" in message and "bhavcopy" in message
    assert "Replay of a past day is unaffected" in message
    assert ls.Q28_TEXT == message

    with pytest.raises(ls.ScreenerError, match="mode must be"):
        ls.build_live_screener(
            date(2026, 7, 17), ("SYNTH",), source=None,
            recording=LiveRecording.at(tmp_path / "r2"),
            clock=ls.VirtualClock(stamp=datetime(2026, 7, 17, 9, 0)), mode="paper",
        )


def test_the_screener_cli_reports_the_block_rather_than_crashing(tmp_path: Path) -> None:
    """The operator's experience of the block: exit 1 and the question, not a traceback.

    The same standard REVIEW_12C finding C2 set for the two document generators, applied to the
    newest runnable module in the repo before anyone has to find out the hard way.
    """
    from acumen import run_screener

    printed: list[str] = []
    import builtins

    real_print = builtins.print
    builtins.print = lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args))
    try:
        code = run_screener.main(["--mode", "live", "--day", "2026-07-17", "--symbols", "SYNTH"])
    finally:
        builtins.print = real_print
    assert code == 1
    joined = "\n".join(printed)
    assert "BLOCKED" in joined and "Q-28" in joined
    assert "Traceback" not in joined


def test_the_master_tick_divergence_detector_MEASURES_and_decides_nothing() -> None:
    """QUESTIONS.md Q-29, built as a measurement.

    Q-20 pins ONE instrument master for the backtest. CONTEXT section 6 forbids backtest/live
    drift, so the live path takes the same pin -- and the residual question (what happens when a
    newer vendor dump disagrees about a live symbol's tick) is NAMED rather than answered. The
    detector reports the symbols; the ruling is the architect's.
    """
    from acumen.instrument_master import InstrumentMaster

    def master(tick_a: str, tick_b: str) -> InstrumentMaster:
        return InstrumentMaster.from_rows([
            {"exch_seg": "NSE", "symbol": "AAA-EQ", "token": "1", "tick_size": tick_a,
             "name": "AAA", "lotsize": "1"},
            {"exch_seg": "NSE", "symbol": "BBB-EQ", "token": "2", "tick_size": tick_b,
             "name": "BBB", "lotsize": "1"},
        ])

    pinned = master("5.000000", "5.000000")
    newer = master("5.000000", "1.000000")
    assert ls.master_tick_divergence(pinned, pinned, ("AAA", "BBB")) == {}
    assert ls.master_tick_divergence(pinned, newer, ("AAA", "BBB")) == {"BBB": (5, 1)}
    # an unknown symbol is not a divergence and is not an exception
    assert ls.master_tick_divergence(pinned, newer, ("ZZZ",)) == {}
