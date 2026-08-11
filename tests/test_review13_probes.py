"""REVIEW_13's kept probes -- the chunk-13 QC review of THE LIVE SCREENER.

Every probe here is GREEN as committed and each one pins a REVIEW_13 finding at the place the
finding actually lives. Most of them pin DEFECTS, which is why their names say what is wrong
rather than what is right: a fix session must flip each one deliberately, and until it does the
suite states the defect out loud instead of implying the chunk is whole.

    F1  the LIVE mode cannot START on a real morning        -- test_the_LIVE_mode_CANNOT_START_*
    F2  the recording mislabels which calendar governed     -- test_the_recording_CLAIMS_*
    F3  the pre-open reports READY on a non-session day     -- test_the_pre_open_reports_READY_*
    F5  the live POC is not fixed after 11:15               -- test_the_live_POC_MOVES_*
    F6  the vendor SDK undoes the credential logging guard  -- test_the_vendor_SDK_constructor_*

The rest are ordinary green pins on behaviour this review verified and wants held -- including
the one credential check that PASSES, on the recording.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import re
import inspect
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import calendar as cal
from acumen import live_refresh as lr
from acumen import live_screener as ls
from acumen import quality_gates as qg
from acumen import signal_engine as se
from acumen.config import load_config
from acumen.daily_store import DailyStore

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "acumen"


def _stores_or_skip() -> Path:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    for relpath in ("daily_store", "minute_store"):
        if not (data_root / relpath).is_dir():
            pytest.skip(f"local {relpath} is absent (the stores are gitignored)")
    return data_root


# --- F0: THE SCREENER LOSES EVERY CARRIED BIAS ---------------------------------------------------


def test_the_screener_LOSES_a_CARRIED_bias_the_backtester_keeps(tmp_path: Path) -> None:
    """REVIEW_13 finding F0 (BLOCKING, money-bearing). CONTEXT 3.2 + CONTEXT 6.

    :func:`acumen.live_screener.build_live_screener` wires the runner with
    ``bt.build_runner(symbols, day, day, seed_from=day)`` -- the bias SERIES therefore begins on
    the trade day itself. CONTEXT 3.2 rule 1 (*"Inside bar ... bias unchanged (carry last known
    bias)"*) and rule 5 (*"No rule fires -> carry last known bias"*) both need an earlier bias to
    carry, and a series seeded at D has none. The engine correctly reports "not seeded" -- which
    CONTEXT 3.2's Seeding paragraph reserves for HISTORY START -- and the screener refuses the
    symbol for the whole day.

    The backtester, walking from 2016, carries the bias and trades. Measured over the chunk-9B
    ten-year ledger: 62,692 of 406,488 evaluated stock-days (15.42%) and **29,121 of 188,345
    executed trades (15.46%)** stand on a carried bias. One trade in six is invisible to the live
    half, silently, with no error and no banner.

    ITC 2026-06-10 is the witness, and it is not obscure: it is in the very universe the chunk's
    own dashboard renders, where it appears under `refused` while the ledger row for the same
    symbol-day reads ``bias=bearish, rule=inside-bar-carry, status=evaluated``.

    GREEN while the defect stands. Passing an earlier ``seed_from`` restores the bias, which is
    both the proof of the diagnosis and the shape of the fix.
    """
    data_root = _stores_or_skip()

    from acumen.live_recording import LiveRecording
    from acumen.live_source import StoredDayBarSource
    from acumen.minute_store import MinuteStore

    symbol, day = "ITC", date(2026, 6, 10)
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(symbol, day):
        pytest.skip(f"{symbol} {day} is not in the local lake")

    def build(seed):
        return ls.build_live_screener(
            day, (symbol,), source=StoredDayBarSource(store),
            recording=LiveRecording.at(tmp_path / f"r{seed}"),
            clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
            mode="replay", sinks=(ls.CollectingAlertSink(),), seed_from=seed,
        )

    shipped = build(None)
    bias = shipped.biases.get(symbol)
    assert bias is not None and bias.rule == "inside-bar-carry"
    assert bias.bias is None, "the shipped wiring resolves NO bias on a carry day"
    assert shipped.states[symbol].phase == ls.PHASE_REFUSED

    seeded = build(day - timedelta(days=30))
    carried = seeded.biases[symbol]
    assert carried.rule == "inside-bar-carry"
    assert carried.bias == "bearish", (
        "given history to carry from, the SAME engine reaches the backtester's own answer -- "
        "so the divergence is the seed, not the code path"
    )
    assert seeded.states[symbol].phase == ls.PHASE_WAITING

    body = inspect.getsource(ls.build_live_screener)
    assert "seed_from=seed_from if seed_from is not None else day" in body, (
        "the default seed IS the trade day; this is the line a fix session changes"
    )


# --- F1: THE LIVE MODE CANNOT START ON A REAL MORNING -------------------------------------------


def test_the_LIVE_mode_CANNOT_START_on_a_day_the_daily_store_has_not_ingested() -> None:
    """REVIEW_13 finding F1 (BLOCKING). CONTEXT 4.7 unblocked the live mode; this is what stops it.

    ``build_live_screener(mode="live", day=D)`` calls ``bt.build_runner(symbols, D, D, ...)``,
    which derives its trading calendar from the DAILY STORE over ``[D - 30, D]``. A derived
    calendar refuses a range holding a date it has never attempted (QUESTIONS.md Q-3 safeguard 1:
    a download error is never a holiday). On a real live morning D is TODAY, and today's bhavcopy
    cannot exist during today -- that is CONTEXT 4.7's own opening sentence -- so the calendar can
    never be derived and the screener never reaches its first sweep.

    The route is closed at both ends, which is what makes it structural rather than a setup gap:
    :func:`acumen.live_refresh.refresh_daily_store` stops at the LAST COMPLETED trading day by
    Q-19's guard, so a perfect pre-open refresh still leaves TODAY never-attempted; and
    ``build_runner`` takes no calendar argument, so nothing may hand it one.

    This probe is GREEN while the defect stands. A fix session flips it.
    """
    data_root = _stores_or_skip()
    store = DailyStore.at(data_root / "daily_store")
    coverage = store.coverage(date(2000, 1, 1), date.today() + timedelta(days=365))
    attempted = [
        day for day, outcome in zip(coverage["trade_date"], coverage["outcome"]) if str(outcome)
    ]
    assert attempted, "the daily store has some coverage to reason from"
    future = max(attempted) + timedelta(days=3)

    with pytest.raises(cal.CalendarError) as caught:
        bt.build_runner(("HDFCBANK",), future, future, seed_from=future, label="review13-probe")
    assert "never attempted" in str(caught.value)


def test_the_live_screener_hands_build_runner_the_LIVE_DAY_as_its_calendar_END() -> None:
    """F1's mechanism, pinned at the source so the diagnosis cannot drift from the symptom.

    Two facts make the refusal structural, and both are read out of the shipped source rather
    than asserted in prose: the screener passes the live day as BOTH ends of the runner's span,
    and ``build_runner`` derives the calendar through that end with no injection point.
    """
    body = inspect.getsource(ls.build_live_screener)
    assert "bt.build_runner(" in body
    assert "symbols, day, day," in body, "the live day is both start and end of the runner's span"

    runner_source = inspect.getsource(bt.build_runner)
    assert "TradingCalendar.from_daily_store_range(" in runner_source
    assert "calendar" not in inspect.signature(bt.build_runner).parameters, (
        "there is no way to hand build_runner a calendar, so a live day cannot supply one"
    )


def test_the_Q19_guard_leaves_TODAY_permanently_unattended_in_the_daily_store() -> None:
    """F1's other end: the pre-open top-up can never reach the day the screener needs.

    :func:`acumen.live_refresh.last_completed_trading_day` is ``prev_trading_day(today)``,
    strictly before today, always -- Q-19's own discipline. So after a perfect refresh the daily
    store still has no row for today, which is exactly the date the derived calendar refuses.
    """
    calendar = cal.TradingCalendar.from_holidays([date(2026, 1, 26)], covered_years=[2026])
    for today in (date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)):
        assert lr.last_completed_trading_day(calendar, today) < today


def test_NOTHING_in_the_repo_builds_a_live_mode_screener_except_to_watch_it_refuse() -> None:
    """F1's other half, and the reason 2,392 green tests did not catch it.

    The live POSTURE is exercised everywhere -- but always by constructing
    :class:`acumen.live_screener.LiveScreener` directly (``tests.test_live_screener.make_screener``
    with ``live=True``) or by mutating a replay screener's fields
    (``docs/evidence/chunk13_context47_walk.py``). The two places that call
    ``build_live_screener(mode="live")`` are both in ``tests/test_live_safety.py`` and both assert
    a REFUSAL. So no test, no evidence document and no artefact ever proves the shipped live path
    ASSEMBLES, which is exactly where finding F1 lives.

    GREEN while the defect stands. A fix session that makes a live morning startable adds the
    positive test and flips this.
    """
    callers: dict[str, int] = {}
    for path in sorted(REPO.glob("tests/*.py")) + sorted(REPO.glob("docs/evidence/*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
                node.func, "id", ""
            )
            if name != "build_live_screener":
                continue
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) \
                        and keyword.value.value == "live":
                    callers[path.name] = callers.get(path.name, 0) + 1
    assert callers == {"test_live_safety.py": 1}, (
        f"live-mode construction now happens in {sorted(callers)} -- check whether any of it "
        "asserts a successful start rather than a refusal, and flip this probe if so"
    )

    walk = (REPO / "docs" / "evidence" / "chunk13_context47_walk.py").read_text(encoding="utf-8")
    assert "live.posture = se.POSTURE_LIVE" in walk, (
        "the committed CONTEXT 4.7 walk reaches the live posture by MUTATING a replay screener"
    )


# --- F2: THE RECORDING MISLABELS WHICH CALENDAR GOVERNED ----------------------------------------


def test_the_recording_CLAIMS_the_published_calendar_governs_while_carrying_the_derived_one(
) -> None:
    """REVIEW_13 finding F2. The C5 duty is asserted in the manifest, never computed.

    ``build_live_screener`` takes ``calendar`` and ``calendar_source`` and forwards them to the
    manifest -- but NO shipped call site passes either, so every recording ever written stamps
    ``governing_source = "published-nse-holiday-master"`` (the parameter default) beside readings
    taken from ``runner.calendar``, which is the DERIVED store-scan calendar. The manifest's own
    ``calendar_source_field`` says ``"derived"`` in the same block, so the two halves of the pair
    the code comment calls a cross-check contradict each other.

    QUESTIONS.md C5: *"chunk 13 takes non-standard sessions from the published NSE calendar; the
    store scan stays the backtest cross-check."*

    GREEN while the defect stands.
    """
    assert ls.build_live_screener.__defaults__ is not None or True  # keyword-only; see below
    signature = inspect.signature(ls.build_live_screener)
    assert signature.parameters["calendar"].default is None
    assert signature.parameters["calendar_source"].default == "published-nse-holiday-master"

    call_sites = []
    for path in sorted(REPO.glob("src/acumen/*.py")) + sorted(REPO.glob("docs/evidence/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
                node.func, "id", ""
            )
            if name == "build_live_screener":
                call_sites.append((path.name, {kw.arg for kw in node.keywords}))
    assert call_sites, "the screener really is built somewhere"
    for filename, keywords in call_sites:
        assert "calendar" not in keywords and "calendar_source" not in keywords, (
            f"{filename} now passes a calendar -- flip this probe, the C5 duty may be discharged"
        )

    manifest_body = inspect.getsource(ls._manifest)
    assert '"governing_source": calendar_source' in manifest_body
    assert '"calendar_source_field": calendar.source' in manifest_body, (
        "the two fields come from different places, which is how they can disagree"
    )


# --- F3: THE PRE-OPEN REPORTS READY ON A DAY THAT IS NOT A SESSION ------------------------------


def test_the_pre_open_reports_READY_on_a_day_that_is_NOT_a_trading_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REVIEW_13 finding F3. CONTEXT 3.1 / 7-E2's exclusion is reported, never enforced.

    plan.md's chunk-13 card names an *"E2 calendar check"* in the live loop. There is none:
    :func:`acumen.live_refresh.refresh_calendar` returns ``ok=True`` unconditionally, so
    ``RefreshReport.ok`` is True on a holiday and on an NSE weekend special session alike, and
    :mod:`acumen.run_screener` sweeps all seventeen boundaries. Nothing alerts today only because
    a non-session day has no bias in the runner's derived calendar -- an incidental guard whose
    operator-facing reason is *"no bias computed for today"*, not the E2 one.

    GREEN while the defect stands.
    """
    holiday = date(2026, 1, 26)
    calendar = cal.TradingCalendar.from_holidays([holiday], covered_years=[2026])
    assert not calendar.is_trading_day(holiday) and not calendar.is_standard_session(holiday)

    monkeypatch.setattr(cal, "fetch_calendar", lambda **kwargs: calendar)
    _calendar, step = lr.refresh_calendar(
        cache_dir=None, today=holiday, allow_network=False, daily_store=None
    )
    assert step.figures["today_is_standard_session"] is False
    assert "today is NOT a session" in step.detail
    assert step.ok is True, (
        "the step that KNOWS today is not a session still reports ok -- so the report says READY"
    )


# --- F5: THE LIVE POC IS NOT FIXED AFTER 11:15 --------------------------------------------------


def test_the_live_POC_MOVES_when_the_11_15_window_was_incomplete(tmp_path: Path) -> None:
    """REVIEW_13 finding F5 (MAJOR, money-bearing). CONTEXT 3.3: *"POC is fixed for the rest of
    the day once computed."* The live layer recomputes it at every boundary.

    :meth:`acumen.live_screener.LiveScreener._evaluate` calls the pipeline over *the bars in
    hand* at each boundary, and nothing caches the profile -- only the settled BATTERY is cached
    (``self.gates``). So a symbol whose 11:15 answer was short by even one minute gets a
    PROVISIONAL POC at 11:15 and a different one at 11:30, after CONTEXT 4.4's own healing
    re-pull. The 11:14 bar closes AT 11:15:00 and CONTEXT 4.4 measures it arriving ~0.2s later,
    so a short 11:15 window is the expected case for the first symbols in sweep order, not an
    exotic one.

    Measured on the real lake over 290 symbol-days (20 symbols x 95 days for the arming flip):
    the POC moves on 2.76% of symbol-days if only the 11:14 bar is late and on 14.48% if the last
    five minutes are, and 53 real symbol-days were found where that flips the 11:15 ARMED
    decision -- in both directions. An ARMED alert already delivered cannot be retracted, because
    :meth:`~acumen.live_screener.LiveScreener._deliver` dedupes on ``(symbol, kind)``.

    Pinned on a REAL symbol-day, because the synthetic day's minutes are too uniform to move a
    POC and a probe that cannot fail proves nothing. GREEN while the defect stands.
    """
    data_root = _stores_or_skip()

    from acumen.live_recording import LiveRecording
    from acumen.live_source import StoredDayBarSource
    from acumen.minute_store import MinuteStore

    day, symbol, drop = date(2026, 6, 11), "RELIANCE", 20

    class ShortFirstAnswer:
        """The vendor's first answer is missing the tail of the window; the next one heals it."""

        def __init__(self, inner, missing: int) -> None:
            self.inner, self.missing, self.calls = inner, missing, 0

        def fetch(self, sym, on, upto):
            bars = self.inner.fetch(sym, on, upto)
            self.calls += 1
            short = self.calls == 1 and len(bars) > self.missing
            return bars[: -self.missing] if short else bars

    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(symbol, day):
        pytest.skip(f"{symbol} {day} is not in the local lake")

    screener = ls.build_live_screener(
        day, (symbol,),
        source=ShortFirstAnswer(StoredDayBarSource(store), drop),
        recording=LiveRecording.at(tmp_path / "recording"),
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    seen = []
    for boundary in ls.boundary_stamps(day)[:3]:
        screener.clock.set(boundary)
        screener.sweep(boundary)
        seen.append(screener.states[symbol].poc_paise)

    assert all(poc is not None for poc in seen)
    assert seen[0] != seen[1], (
        "the POC computed at 11:15 on a short window differs from the one at 11:30 -- "
        "CONTEXT 3.3 says it is fixed for the rest of the day once computed"
    )
    assert seen[1] == seen[2], "and it settles once the window is whole"

    body = inspect.getsource(ls.LiveScreener._evaluate)
    assert "self.pipeline.evaluate(" in body
    assert "profile" not in body, (
        "nothing caches the day's profile -- only the settled battery is cached, in _battery"
    )


def test_an_ARMED_alert_can_never_be_corrected_once_the_POC_moves(tmp_path: Path) -> None:
    """F5's consequence, at the alert. The dedup key is what makes it permanent.

    ``(symbol, kind)`` is the right key for the ordinary case CONTEXT 4.4 worries about -- the
    same trigger re-derived at seventeen boundaries must be sent once. It is the wrong key for a
    state the tool has since changed its mind about: an ARMED alert sent against a provisional
    POC cannot be re-sent, amended or withdrawn.
    """
    from test_backtest import SYMBOL  # noqa: E402 -- the suite's own synthetic world
    from test_live_screener import make_screener  # noqa: E402

    screener, sink, _rec = make_screener(tmp_path)
    first = screener._alert(ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 15), {"poc": 1})
    assert screener._deliver(first) is True
    corrected = screener._alert(ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 30), {"poc": 2})
    assert screener._deliver(corrected) is False, (
        "a corrected ARMED alert is silently dropped -- the trader keeps the first POC"
    )
    assert len(sink.alerts) == 1 and sink.alerts[0].payload["poc"] == 1


# --- F6: THE CREDENTIAL LOGGING GUARD IS UNDONE BY THE VENDOR SDK -------------------------------


def test_the_vendor_SDK_constructor_UNDOES_the_credential_logging_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW_13 finding F6 (BLOCKING). CLAUDE.md rule 4: never log ``.env`` contents.

    :func:`acumen.smartapi_client._quiet_library_logging` raises logzero to CRITICAL exactly as
    its docstring says -- and then ``_default_connect_factory`` constructs ``SmartConnect``,
    whose own setup calls back into logzero, RESETS the level to ERROR and installs a
    ``RotatingFileHandler`` writing ``logs/<date>/app.log``. The guard runs one line too early.
    The vendor then logs every request's headers, which carry ``X-PrivateKey: <api key>`` and
    ``Authorization: Bearer <session jwt>``.

    This probe never reads ``.env`` and never prints a secret -- it measures the LOGGER, which is
    the mechanism. GREEN while the defect stands.
    """
    logzero = pytest.importorskip("logzero")
    pytest.importorskip("SmartApi")
    import logging

    from acumen import smartapi_client as sac

    monkeypatch.chdir(tmp_path)  # any log file the SDK opens lands here, never in the repo

    sac._quiet_library_logging()
    assert logzero.logger.level == logging.CRITICAL, "the guard does raise the threshold"
    guarded = [type(h).__name__ for h in logzero.logger.handlers]
    assert "RotatingFileHandler" not in guarded

    from SmartApi import SmartConnect  # noqa: F401 -- constructing it is the point

    SmartConnect(api_key="DUMMY-KEY-NOT-REAL")

    assert logzero.logger.level == logging.ERROR, (
        "the vendor constructor puts the level BACK to ERROR -- the level at which it logs "
        "full request headers, including X-PrivateKey and the Bearer session token"
    )
    assert any(type(h).__name__ == "RotatingFileHandler" for h in logzero.logger.handlers), (
        "and it installs a file handler, so the spill goes to disk and not only to stderr"
    )


def test_the_repos_own_run_logs_carry_credential_shaped_headers() -> None:
    """F6's outcome, measured on the machine rather than argued. Never reads ``.env``.

    ``logs/`` is gitignored, so nothing reached git -- but CLAUDE.md rule 4 says *logged*, not
    *committed*, and :mod:`acumen.run_screener` opens a broker session on every live morning, so
    a dry-run week is five more days of this. Detection is by HEADER SHAPE, so this probe needs
    no secret and leaks none.

    GREEN while the defect stands; it goes red once the guard is fixed AND the operator has
    rotated the existing logs.
    """
    logs = REPO / "logs"
    if not logs.is_dir():
        pytest.skip("no local logs/ directory")
    private_key = bearer = 0
    files = 0
    for path in sorted(logs.rglob("*.log")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        here = len(re.findall(r"'X-PrivateKey':\s*'[^']{4,}'", text))
        there = len(re.findall(r"'Authorization':\s*'Bearer [A-Za-z0-9_\-.]{20,}'", text))
        if here or there:
            files += 1
        private_key += here
        bearer += there
    if not files:
        pytest.skip("this machine's logs/ has been rotated since the review -- nothing to pin")
    assert private_key > 0 and bearer > 0, (
        f"{files} log file(s) carry {private_key} X-PrivateKey line(s) and {bearer} Bearer "
        "token line(s) -- CLAUDE.md rule 4"
    )


def test_a_real_RECORDING_carries_no_credential_byte(tmp_path: Path) -> None:
    """The other half of the same check, and this one PASSES: the replay contract is clean.

    Scans every byte of a freshly written recording for each ``.env`` value, reporting only
    found/not-found by key NAME. Nothing is printed. Recordings are what chunk 14 forwards and
    what the operator keeps, so this is the artefact that matters most.
    """
    data_root = _stores_or_skip()

    from acumen.live_recording import LiveRecording
    from acumen.live_source import StoredDayBarSource
    from acumen.minute_store import MinuteStore

    day, symbol = date(2026, 6, 10), "HDFCBANK"
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(symbol, day):
        pytest.skip(f"{symbol} {day} is not in the local lake")

    recording = LiveRecording.at(tmp_path / "recording")
    screener = ls.build_live_screener(
        day, (symbol,), source=StoredDayBarSource(store), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    screener.run_day()

    env_path = REPO / ".env"
    if not env_path.is_file():
        pytest.skip("no .env on this machine")
    secrets = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if len(value) >= 6:  # shorter than this is indistinguishable from coincidence
                secrets[key.strip()] = value

    leaked, files, size = [], 0, 0
    for path in sorted(recording.root.rglob("*")):
        if not path.is_file():
            continue
        files += 1
        blob = path.read_bytes()
        size += len(blob)
        text = blob.decode("utf-8", "ignore")
        leaked += [name for name, value in secrets.items() if value in text]

    assert files and size, "the recording really was written"
    assert not leaked, f"credential(s) {sorted(set(leaked))} reached the recording"


# --- green pins on behaviour this review verified and wants held --------------------------------


def test_the_oracle_free_battery_still_refuses_every_bar_shape_the_settled_one_does() -> None:
    """CONTEXT 4.7's whole safety claim, at the battery, over the four surviving triggers.

    The live battery sets aside exactly ONE of gate 2's triggers -- missing minutes, which is
    itself gate-1-derived and was therefore never oracle-free. Every other refusal the settled
    battery makes on the BARS THEMSELVES must survive, because those are the ones a live morning
    would otherwise trade on.
    """
    day = date(2026, 7, 17)
    base = datetime.combine(day, datetime.min.time()).replace(hour=9, minute=15)

    def bar(minute: int, o: int, h: int, low: int, c: int, volume: int = 10):
        return se.StoredBar(
            symbol="SYNTH", stamp=base + timedelta(minutes=minute),
            open_paise=o, high_paise=h, low_paise=low, close_paise=c, volume=volume,
        )

    clean = [bar(i, 100, 110, 90, 105) for i in range(30)]
    shapes = {
        "open above high": clean[:-1] + [bar(29, 999, 110, 90, 105)],
        "open below low": clean[:-1] + [bar(29, 1, 110, 90, 105)],
        "close above high": clean[:-1] + [bar(29, 100, 110, 90, 999)],
        "close below low": clean[:-1] + [bar(29, 100, 110, 90, 1)],
        "high below low": clean[:-1] + [bar(29, 100, 80, 90, 85)],
        "negative price": clean[:-1] + [bar(29, -100, 110, -120, 105)],
        "negative volume": clean[:-1] + [bar(29, 100, 110, 90, 105, -1)],
        "duplicate stamp": clean + [bar(29, 100, 110, 90, 105)],
    }
    assert qg.integrity_gate(clean, day, completeness_measurable=False).passed, (
        "the clean prefix is accepted, so a refusal below is the corruption and not the prefix"
    )
    for label, bars in shapes.items():
        live = se.oracle_free_battery(day, bars)
        assert not live.gate2.passed, f"the live battery accepted {label}"
        assert not live.usable, f"the live battery called {label} usable"
        assert live.refusal == se.NOT_EVALUATED_GATE2


def test_poc_licence_IS_volume_reconciled_on_every_settled_posture_including_a_typo() -> None:
    """B340's identity, and the one way a posture string could break it.

    ``posture`` is a plain ``str``. Anything that is not :data:`POSTURE_LIVE` is treated as
    settled, so an unknown or misspelled posture falls to the SAFE side -- gate 1's verdict
    licenses the POC and a missing gate-1P verdict raises rather than reading as a pass.
    """
    gate2 = qg.integrity_gate((), date(2026, 7, 17), volume_reconciled=True)
    containment = qg.price_containment_gate(110, 90, 110, 90)
    for posture in (se.POSTURE_SETTLED, "settled", "SETTLED", "typo", ""):
        for reconciled in (True, False, None):
            gates = se.DayGates(
                gate1=None, relieved=False, volume_reconciled=reconciled,
                gate2=gate2, gate1p=containment, posture=posture,
            )
            assert gates.poc_licence is gates.volume_reconciled

    unknown_posture_without_gate1p = se.DayGates(
        gate1=None, relieved=False, volume_reconciled=True,
        gate2=gate2, gate1p=None, posture="typo",
    )
    with pytest.raises(ValueError, match="must carry a gate-1P verdict"):
        _ = unknown_posture_without_gate1p.refusal


def test_the_integrity_gate_default_reproduces_the_pre_ruling_settled_behaviour() -> None:
    """B338: ``completeness_measurable`` defaults to the settled reading, so no stored day moves.

    Asserted as behaviour rather than as a diff: over the three gate-1 verdicts and both sides of
    the missing-minutes threshold, the DEFAULT call and the explicit ``True`` call agree in every
    field, and ``False`` differs only in the missing-minutes trigger.
    """
    day = date(2026, 7, 17)
    base = datetime.combine(day, datetime.min.time()).replace(hour=9, minute=15)
    bars = [
        se.StoredBar(symbol="SYNTH", stamp=base + timedelta(minutes=i),
                     open_paise=100, high_paise=110, low_paise=90, close_paise=105, volume=10)
        for i in range(30)
    ]
    for reconciled in (True, False, None):
        default = qg.integrity_gate(bars, day, volume_reconciled=reconciled)
        explicit = qg.integrity_gate(
            bars, day, volume_reconciled=reconciled, completeness_measurable=True
        )
        assert default == explicit
        live = qg.integrity_gate(
            bars, day, volume_reconciled=reconciled, completeness_measurable=False
        )
        assert live.missing == default.missing == qg.EXPECTED_SESSION_MINUTES - 30
        assert live.passed is True and live.missing_excluded is False
        assert "NOT MEASURABLE" in live.liquidity_note, (
            "an accepted window missing 345 of its minutes must never read as a clean 375"
        )
        if reconciled is not True:
            assert default.passed is False and default.missing_excluded is True
