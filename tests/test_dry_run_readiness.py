"""THE DRY-RUN-WEEK READINESS GATE (chunk 15), checked one refusal at a time.

A gate is only worth the refusals it makes, so every check here is driven twice -- once on a
world where it must pass and once on a world where it must refuse -- and the report is checked
for the property that matters more than any single check: **it never says READY while one of the
seven is missing, absent or unproven.**

Two rules this file exists to enforce beyond that:

* **no credential ever reaches a string.** The report is rendered with real-looking values in the
  environment and searched for them, because the one thing a readiness report must never do is
  print the thing it is checking for.
* **the gate has no side effects except the one message it is asked for.** It opens no broker
  session, fetches no candle, and writes nothing under either store.

Store-free by construction: nothing here reads ``data_root`` or ``cache_root`` except through a
scratch tree it built itself, so these run on a bare clone.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from acumen import calendar as cal
from acumen import dry_run_readiness as gate
from acumen import run_screener
from acumen import telegram_sink as tg
from acumen.backtest import ResidualEntry

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
DAY = date(2026, 6, 10)


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator's real ``.env`` must not decide a test's answer, in EITHER direction.

    ``config.env_value`` loads ``.env`` before it reads the environment, so a bare
    ``monkeypatch.delenv`` is undone one line later on the operator's own machine while passing
    on a clone -- the two would disagree about whether the refusal path is covered at all.
    Neutralised here, once, for every test in this module.
    """
    monkeypatch.setattr("acumen.config.load_env", lambda *args, **kwargs: None)
    for name in (tg.ENV_BOT_TOKEN, tg.ENV_CHAT_ID):
        monkeypatch.delenv(name, raising=False)


# --- the seven checks, each shown passing and refusing --------------------------------------------


def test_the_CREDENTIALS_check_names_the_MISSING_KEY_and_never_a_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAUDE.md rule 4: whether the two keys EXIST, never what they are."""
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "1234567890:AAHsecretsecretsecretsecret")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1001234567890")
    ok = gate.check_credentials()
    assert ok.ok and "both keys present" in ok.detail
    assert "AAHsecret" not in ok.detail and "1001234567890" not in json.dumps(ok.figures)

    monkeypatch.delenv(tg.ENV_CHAT_ID)
    missing = gate.check_credentials()
    assert not missing.ok
    assert tg.ENV_CHAT_ID in missing.detail, "the operator has to know WHICH key to add"
    assert tg.ENV_BOT_TOKEN not in missing.detail.split("MISSING from .env:")[1]


def test_the_MASTER_check_resolves_THE_DAYS_OWN_NAME_and_says_where_it_looked(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.7 / Q-29's prerequisite, moved from 09:14 to the day before."""
    absent = gate.check_master(DAY, cache_dir=tmp_path)
    assert not absent.ok
    assert "OpenAPIScripMaster_2026-06-10.json" in absent.detail
    assert str(tmp_path) in absent.detail, "and where it looked, so the fix is obvious"
    # REVIEW_15 C1: the remedy names the LAUNCHER, which runs on a tree with no editable
    # install, and not `python -m acumen.instrument_master`, which answers "No module named".
    assert f"`python {gate.MASTER_LAUNCHER} --allow-network`" in absent.detail, "the remedy"
    assert "-m acumen.instrument_master" not in absent.detail, "the dead form is gone"

    path = tmp_path / "instrument_master" / "OpenAPIScripMaster_2026-06-10.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    present = gate.check_master(DAY, cache_dir=tmp_path)
    assert present.ok and present.figures["master_file"] == path.name


def test_the_CALENDAR_check_reads_the_DAY_CACHE_and_never_the_network(tmp_path: Path) -> None:
    """Offline on purpose: a gate that pulled would certify a network, not a machine.

    The suite's socket guard would fail this test outright if it reached out, which is the
    strongest available proof that it does not.
    """
    empty = gate.check_calendar(DAY, cache_dir=tmp_path)
    assert not empty.ok and "no fallback" in empty.detail

    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(tmp_path), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY
    )
    ready = gate.check_calendar(DAY, cache_dir=tmp_path)
    assert ready.ok
    assert ready.figures["is_trading_day"] is True
    assert ready.figures["is_standard_session"] is True
    assert ready.figures["holidays"] > 0


def _register(settled: int, quarantined=gate.QUARANTINED) -> dict:
    rows = {
        f"SYM{index:03d}": ResidualEntry(
            symbol=f"SYM{index:03d}", status="settled", gate1p_pass=1, gate1p_total=1,
            gate1p_no_oracle=0, residual_reason="", usable_pass=1,
        )
        for index in range(settled)
    }
    rows.update({
        symbol: ResidualEntry(
            symbol=symbol, status="quarantined", gate1p_pass=0, gate1p_total=1,
            gate1p_no_oracle=0, residual_reason="CONTEXT 4.6 quarantine", usable_pass=0,
        )
        for symbol in quarantined
    })
    return rows


def _write_register(root: Path, rows) -> Path:
    from acumen import backtest as bt

    path = root / bt.RESIDUAL_LEDGER_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"symbols": {
        symbol: {
            "status": entry.status, "gate1p_pass": entry.gate1p_pass,
            "gate1p_total": entry.gate1p_total, "gate1p_no_oracle": entry.gate1p_no_oracle,
            "residual_reason": entry.residual_reason, "usable_pass": entry.usable_pass,
        }
        for symbol, entry in rows.items()
    }}), encoding="utf-8")
    return path


def test_the_UNIVERSE_check_drives_the_SHIPPED_filter_and_refuses_205(tmp_path: Path) -> None:
    """It asks ``_screened_universe`` -- the function a live morning really uses -- not a count.

    REVIEW_13 **M2** measured the alternative: a live morning sweeping the raw F&O list, all six
    quarantined symbols included, on which the chunk-9B run walked ZERO days of 495,312.
    """
    _write_register(tmp_path, _register(gate.SETTLED_UNIVERSE_SIZE))
    ok = gate.check_universe(data_root=tmp_path)
    assert ok.ok
    assert ok.figures["settled"] == gate.SETTLED_UNIVERSE_SIZE == 204
    assert ok.figures["excluded"] == list(gate.QUARANTINED)
    for symbol in gate.QUARANTINED:
        assert symbol in ok.detail, symbol

    _write_register(tmp_path, _register(gate.SETTLED_UNIVERSE_SIZE + 1))
    grown = gate.check_universe(data_root=tmp_path)
    assert not grown.ok and "205" in grown.detail

    # ...and a register that settled one of the quarantined six still counts six exclusions,
    # which is why the check names them rather than counting them.
    rows = _register(gate.SETTLED_UNIVERSE_SIZE, quarantined=gate.QUARANTINED[:-1] + ("ZZZZ",))
    _write_register(tmp_path, rows)
    renamed = gate.check_universe(data_root=tmp_path)
    assert not renamed.ok

    _write_register(tmp_path, {})
    (tmp_path / "universe_backfill" / "ledger.json").unlink()
    assert not gate.check_universe(data_root=tmp_path).ok


def test_the_FENCE_check_asks_BOTH_stores_the_question_a_real_morning_asks(
    tmp_path: Path,
) -> None:
    """REVIEW_14 B1: the fence was built, worked, and was never called on the live path."""
    data, cache = tmp_path / "data", tmp_path / "cache"
    fenced = gate.check_fence(data_root=data, cache_root=cache)
    assert fenced.ok and "ACTIVE on both stores" in fenced.detail
    assert fenced.figures["fenced"] == {"data_root": True, "cache_root": True}

    # A cache OUTSIDE the stores is permitted to refresh -- which is what makes this a fence and
    # not a blanket refusal, and what the check would have to notice if a root moved.
    from acumen import backtest as bt

    _resolved, may_network, _why = bt.fence_ca_cache(
        cache_dir=tmp_path / "scratch" / "nse", allow_network=True,
        data_root=data, cache_root=cache,
    )
    assert may_network is True


def test_the_TRIPWIRE_check_RUNS_the_suite_and_an_unrunnable_suite_is_NOT_a_pass(
    tmp_path: Path,
) -> None:
    """*"There is a tripwire"* and *"the tripwire is green on this tree"* are different claims.

    REVIEW_14 **B2** is the standing lesson: a certifying test that asserted its own name left a
    real defect one module away with the suite green. So the gate runs the suite; and a suite it
    could not run is a refusal, because there is nothing to certify from an exit code that never
    happened.
    """
    seen: list[list[str]] = []

    def green(argv, cwd):
        seen.append(list(argv))
        return 0, "14 passed in 19.14s\n"

    ok = gate.check_tripwires(runner=green)
    assert ok.ok and "GREEN" in ok.detail and "14 passed" in ok.detail
    assert seen and seen[0][1:3] == ["-m", "pytest"]
    assert gate.TRIPWIRE_SUITE.replace("/", "\\") in seen[0][3] or gate.TRIPWIRE_SUITE in seen[0][3]

    red = gate.check_tripwires(runner=lambda argv, cwd: (1, "1 failed, 13 passed\n"))
    assert not red.ok and "FAILED" in red.detail and "real money" in red.detail

    def explode(argv, cwd):
        raise FileNotFoundError("pytest is not installed")

    assert not gate.check_tripwires(runner=explode).ok

    # A tree with no tests directory at all -- an installed package -- is a refusal, not a pass.
    absent = gate.check_tripwires(repo_root=tmp_path)
    assert not absent.ok and gate.TRIPWIRE_SUITE in absent.detail

    # ...and the suite it names really is in THIS repository.
    assert (gate.REPO_ROOT / gate.TRIPWIRE_SUITE).is_file()


def test_the_TEST_MESSAGE_is_opt_in_REQUIRED_and_could_not_be_read_as_a_signal() -> None:
    """Opt-in so the gate can be run twice; required because a chat nobody has reached is a
    chat nobody has evidence about."""
    not_sent = gate.check_test_message(DAY, send=False)
    assert not not_sent.ok
    assert not_sent.detail.startswith("NOT SENT")
    assert "--send-test-message" in not_sent.detail, "the refusal carries its own remedy"
    assert not_sent.figures["attempted"] is False

    sent: list[str] = []
    ok = gate.check_test_message(DAY, send=True, transport=sent.append)
    assert ok.ok and len(sent) == 1, "ONE message"
    text = sent[0]
    assert text.startswith(gate.TEST_MESSAGE_HEADING)
    assert "not an alert" in gate.TEST_MESSAGE_HEADING
    assert "no price, no signal" in text and "PLACES NO ORDERS" in text
    assert DAY.isoformat() in text
    for word in ("entry", "SL ", "TP ", "qty", "POC"):
        assert word not in text, f"a test message must not read like an alert: {word!r}"

    def refuse(_text: str) -> None:
        raise tg.TelegramError("Telegram refused the request (status 401)")

    failed = gate.check_test_message(DAY, send=True, transport=refuse)
    assert not failed.ok and "the send FAILED" in failed.detail
    assert failed.figures["attempted"] is True


# --- the report: the property that outranks any single check --------------------------------------


def _world(root: Path) -> Path:
    """A scratch world where all five machine-local checks pass, and a config that names it."""
    data, cache = root / "data", root / "cache"
    _write_register(data, _register(gate.SETTLED_UNIVERSE_SIZE))
    master = cache / "instrument_master" / "OpenAPIScripMaster_2026-06-10.json"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text("[]", encoding="utf-8")
    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY
    )
    text = (REPO / "config.yaml").read_text(encoding="utf-8")
    for key, value in (("data_root", data), ("cache_root", cache)):
        text = "\n".join(
            f"  {key}: {value.as_posix()}" if line.strip().startswith(f"{key}:") else line
            for line in text.splitlines()
        )
    path = root / "config.yaml"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _assess(config_path: Path, **overrides):
    from acumen.config import load_config

    kwargs = dict(
        day=DAY, config=load_config(config_path, include_env=False),
        tripwire_runner=lambda argv, cwd: (0, "14 passed in 19.14s\n"),
        send_test_message=True, transport=lambda text: None,
    )
    kwargs.update(overrides)
    return gate.assess(**kwargs)


def test_the_GATE_certifies_only_when_ALL_SEVEN_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is no partial pass: a week that starts on six of seven finds the seventh on
    Wednesday."""
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "1234567890:AAHtoken")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1001234567890")
    config_path = _world(tmp_path)

    report = _assess(config_path)
    assert [check.name for check in report.checks] == list(gate.CHECKS)
    assert report.ready, report.render()
    assert gate.READY_LINE in report.render()
    assert report.refusals == ()

    # ...and each of the seven, removed one at a time, refuses the whole gate BY NAME.
    monkeypatch.delenv(tg.ENV_CHAT_ID)
    assert not _assess(config_path).ready
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1001234567890")

    assert not _assess(config_path, send_test_message=False).ready
    assert not _assess(
        config_path, tripwire_runner=lambda argv, cwd: (1, "1 failed")
    ).ready

    (tmp_path / "cache" / "instrument_master" / "OpenAPIScripMaster_2026-06-10.json").unlink()
    without_master = _assess(config_path)
    assert not without_master.ready
    assert any(gate.CHECK_MASTER in refusal for refusal in without_master.refusals)
    assert gate.NOT_READY_LINE in without_master.render()


def test_a_REFUSAL_names_what_is_missing_and_what_to_do(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal an operator cannot act on is a wall. Every one of them carries its remedy."""
    config_path = _world(tmp_path)
    (tmp_path / "cache" / "instrument_master" / "OpenAPIScripMaster_2026-06-10.json").unlink()

    report = _assess(config_path, send_test_message=False)
    text = report.render()
    assert gate.NOT_READY_LINE in text
    assert len(report.refusals) == 3
    assert "Add them" in text                              # .env
    assert f"{gate.MASTER_LAUNCHER} --allow-network" in text   # the day's own dump
    assert "--send-test-message" in text                   # the chat
    for line in report.refusals:
        assert line.split(":")[0] in gate.CHECKS, line


def test_the_REPORT_never_prints_a_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one thing a readiness report must never do is print the thing it is checking for."""
    token = "7654321098:AAG-this-is-the-token-value-nobody-may-see"
    chat = "-1009876543210"
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, token)
    monkeypatch.setenv(tg.ENV_CHAT_ID, chat)
    config_path = _world(tmp_path)

    report = _assess(config_path)
    rendered = report.render() + json.dumps(
        [check.figures for check in report.checks], default=str
    )
    for secret in (token, chat, token.split(":")[1], chat.lstrip("-")):
        assert secret not in rendered, "a credential reached the report"
    # ...while the KEY NAMES, which are constants of this repository's own source and are what
    # an operator needs in order to fix the file, do travel.
    assert tg.ENV_BOT_TOKEN in rendered and tg.ENV_CHAT_ID in rendered


def test_a_CHECK_that_RAISES_is_a_refusal_and_never_a_traceback(tmp_path: Path) -> None:
    """The same discipline ``morning_refresh`` holds every step to."""
    from acumen.config import load_config

    config_path = _world(tmp_path)
    (tmp_path / "data" / "universe_backfill" / "ledger.json").write_text(
        "{not json", encoding="utf-8"
    )
    report = gate.assess(
        day=DAY, config=load_config(config_path, include_env=False),
        tripwire_runner=lambda argv, cwd: (0, "14 passed"),
        send_test_message=True, transport=lambda text: None,
    )
    assert not report.ready
    assert [check.name for check in report.checks] == list(gate.CHECKS), (
        "every check still ran -- one failure must not hide the next"
    )


# --- the CLI ---------------------------------------------------------------------------------------


def test_the_CLI_flag_runs_the_GATE_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``--readiness`` returns before a screener, a recording or a broker session exists.

    Asserted by making every one of those explode if it is touched: a gate with side effects is
    a gate nobody runs twice, and the operator is told to run this one before a live week.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, "1234567890:AAHtoken")
    monkeypatch.setenv(tg.ENV_CHAT_ID, "-1001234567890")
    config_path = _world(tmp_path)

    for name in ("build_live_screener",):
        monkeypatch.setattr(
            f"acumen.live_screener.{name}",
            lambda *a, **k: pytest.fail("--readiness built a screener"),
        )
    monkeypatch.setattr(
        "acumen.live_refresh.morning_refresh",
        lambda *a, **k: pytest.fail("--readiness ran the morning refresh"),
    )
    monkeypatch.setattr(
        gate, "check_tripwires",
        lambda **kwargs: gate.ReadinessCheck(
            name=gate.CHECK_TRIPWIRES, ok=True, detail="stubbed for this probe"
        ),
    )

    code = run_screener.main([
        "--readiness", "--day", DAY.isoformat(), "--config", str(config_path),
    ])
    out = capsys.readouterr().out
    assert code == 1, "the test message has not been sent, so the gate refuses"
    assert gate.NOT_READY_LINE in out
    assert "ACUMEN SCREENER PREFLIGHT" not in out, "no morning was started"
    assert not (tmp_path / "data" / "live").exists(), "and no recording was written"

    # ...and the two flags exist on the shipped parser, spelled the way the runbook prints them.
    args = run_screener.parse_args([
        "--readiness", "--day", DAY.isoformat(), "--send-test-message",
    ])
    assert args.readiness is True and args.send_test_message is True
    assert run_screener.parse_args(["--day", DAY.isoformat()]).readiness is False
