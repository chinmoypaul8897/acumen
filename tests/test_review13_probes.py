"""REVIEW_13's kept probes -- the chunk-13 QC review of THE LIVE SCREENER.

Every probe here was GREEN as committed and each one pins a REVIEW_13 finding at the place the
finding actually lives. Five of them pinned DEFECTS, with names that said what was wrong, so
that a fix session had to flip each one deliberately rather than let a passing suite imply the
chunk was whole. **The FIX-2 session has flipped all five, and this docstring is the record of
which way each one now points:**

    F0/B1  the carried bias                 FLIPPED -- test_the_screener_KEEPS_the_CARRIED_bias_*
    F1/B6  the LIVE mode cannot START       FLIPPED -- test_the_LIVE_mode_STARTS_*
    F2/M17 the mislabelled calendar         FLIPPED -- test_the_recording_NAMES_the_calendar_*
    F5/B3  the POC moves after 11:15        FLIPPED -- test_the_live_POC_IS_PINNED_*
    F6/B5  the credential guard is undone   FLIPPED -- test_the_credential_guard_SURVIVES_*

Each flipped probe KEEPS the defect's own measurement in its docstring and asserts the opposite
behaviour, so the record of what was wrong survives the fix rather than being deleted with it.

**F3 is NOT flipped and is not on the fix list.** The pre-open still reports READY on a day that
is not a session (the E2 calendar check named on the chunk card is reported and never enforced).
It is a MINOR in REVIEW_13's own list, it was not among the ten blocking findings the FIX-2
session was given, and it stays GREEN and stated out loud until it is fixed.

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


# --- F0/B1: THE CARRIED BIAS -- FLIPPED BY THE FIX-2 SESSION -------------------------------------


def test_the_screener_KEEPS_the_CARRIED_bias_the_backtester_keeps(tmp_path: Path) -> None:
    """REVIEW_13 finding F0 / **B1**, FIXED and FLIPPED. CONTEXT 3.2 + CONTEXT 6.

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
    own dashboard renders, where it appeared under `refused` while the ledger row for the same
    symbol-day reads ``bias=bearish, rule=inside-bar-carry, status=evaluated``.

    **FLIPPED.** ``build_live_screener`` now seeds the bias series at
    ``day - SEED_LOOKBACK_DAYS``, so every carried bias is present by construction and the
    SHIPPED wiring -- no ``seed_from`` argument at all -- reaches the backtester's own answer on
    the witness day. The old defect is still measured here, by seeding at the trade day
    explicitly and watching the engine correctly answer "not seeded": the diagnosis is preserved
    as a live measurement rather than as a claim in prose.
    """
    data_root = _stores_or_skip()

    from acumen.live_recording import LiveRecording
    from acumen.live_source import StoredDayBarSource
    from acumen.minute_store import MinuteStore

    symbol, day = "ITC", date(2026, 6, 10)
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(symbol, day):
        pytest.skip(f"{symbol} {day} is not in the local lake")

    def build(seed, tag):
        return ls.build_live_screener(
            day, (symbol,), source=StoredDayBarSource(store),
            recording=LiveRecording.at(tmp_path / f"r{tag}"),
            clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
            mode="replay", sinks=(ls.CollectingAlertSink(),), seed_from=seed,
        )

    shipped = build(None, "shipped")
    bias = shipped.biases.get(symbol)
    assert bias is not None and bias.rule == "inside-bar-carry"
    assert bias.bias == "bearish", (
        "the SHIPPED wiring now reaches the ledger's own answer on a carry day -- "
        "ledger row: bias=bearish, rule=inside-bar-carry, status=evaluated"
    )
    assert shipped.states[symbol].phase == ls.PHASE_WAITING
    assert shipped.states[symbol].side == "short", "and a bearish day is short-only (CONTEXT 3.4)"

    # The defect itself, still measurable: seed the series AT the trade day and the same engine
    # correctly reports "not seeded" -- CONTEXT 3.2's history-start state -- and the day is lost.
    at_the_day = build(day, "at-the-day")
    assert at_the_day.biases[symbol].bias is None
    assert at_the_day.states[symbol].phase == ls.PHASE_REFUSED

    body = inspect.getsource(ls.build_live_screener)
    assert "seed_from if seed_from is not None else day - timedelta(days=SEED_LOOKBACK_DAYS)" \
        in body, "the default seed is now a look-back, not the trade day itself"
    assert ls.SEED_LOOKBACK_DAYS >= 112, (
        "and the look-back covers the ledger's MEASURED worst carry reach (112 calendar days, "
        "docs/evidence/chunk13_fix2_bias_stratified.md)"
    )


# --- F1/B6: THE LIVE MODE ON A REAL MORNING -- FLIPPED BY THE FIX-2 SESSION ----------------------


def test_the_DERIVED_calendar_still_refuses_a_day_the_daily_store_has_not_ingested() -> None:
    """REVIEW_13 finding F1 / **B6**'s mechanism, which is CORRECT and must stay.

    ``build_live_screener(mode="live", day=D)`` called ``bt.build_runner(symbols, D, D, ...)``,
    which derives its trading calendar from the DAILY STORE over ``[D - 30, D]``. A derived
    calendar refuses a range holding a date it has never attempted (QUESTIONS.md Q-3 safeguard 1:
    a download error is never a holiday). On a real live morning D is TODAY, and today's bhavcopy
    cannot exist during today -- that is CONTEXT 4.7's own opening sentence -- so the calendar
    could never be derived and the screener never reached its first sweep. Reproduced by the
    review: ``--mode live --day 2026-08-10 --preflight-only`` with the day's own master present
    -> *"the screener cannot start: CalendarError ... 11 date(s) never attempted"*, exit 1.

    **The REFUSAL is right and is asserted here to stay right.** Q-3 safeguard 1 exists so an
    unfinished backfill cannot become a calendar full of invented holidays, and the fix does not
    weaken it by one date: what changed is that a LIVE morning no longer asks the derived
    calendar a question only the published master can answer (see the probe below).
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


def test_the_LIVE_mode_STARTS_on_a_day_the_daily_store_can_never_have_ingested() -> None:
    """REVIEW_13 **B6**, FIXED and FLIPPED: a live morning can be assembled on TODAY.

    Two facts made the old refusal structural, and both are read out of the shipped source rather
    than asserted in prose: the screener passes the live day as BOTH ends of the runner's span,
    and ``build_runner`` derived the calendar through that end with no injection point. The
    second is what changed. ``build_runner`` now takes a ``calendar`` -- CONTEXT 4.7's second
    door, closed to every historical caller by default -- and a live morning supplies the one
    :func:`acumen.calendar.live_trading_calendar` builds: the PUBLISHED NSE holiday master for
    the days the store cannot answer for, the store's own scan for the history behind it, which
    is the C5 division of labour exactly.

    Asserted on a date the store has NEVER attempted and structurally never will (Q-19 stops the
    top-up strictly before today), so this probe cannot pass by accident of coverage.
    """
    data_root = _stores_or_skip()
    store = DailyStore.at(data_root / "daily_store")
    coverage = store.coverage(date(2000, 1, 1), date.today() + timedelta(days=365))
    attempted = [
        day for day, outcome in zip(coverage["trade_date"], coverage["outcome"]) if str(outcome)
    ]
    beyond = max(attempted) + timedelta(days=3)
    while beyond.weekday() >= 5:  # a session, so the calendar has a bias pair to reach for
        beyond += timedelta(days=1)

    assert "calendar" in inspect.signature(bt.build_runner).parameters, (
        "build_runner has an injection point now, and it is CONTEXT 4.7's door"
    )
    runner_source = inspect.getsource(bt.build_runner)
    assert "TradingCalendar.from_daily_store_range(" in runner_source, (
        "and the DERIVED calendar is still what every historical caller gets"
    )

    published = cal.TradingCalendar.from_holidays(
        [date(beyond.year, 1, 26)], covered_years=[beyond.year, beyond.year - 1]
    )
    live = cal.live_trading_calendar(
        published, store=store, first_day=beyond - timedelta(days=70), day=beyond
    )
    assert live.is_trading_day(beyond), (
        "the published master answers for a date the store has never attempted -- which is the "
        "date every real live morning is"
    )
    assert live.trading_days is not None and live.covered_days is not None

    # The history behind it is still the STORE's own reading, so the live bias pair and the
    # backtester's bias pair are the same two days by construction (CONTEXT 6).
    derived = cal.TradingCalendar.from_daily_store_range(
        store, beyond - timedelta(days=70), max(attempted)
    )
    shared = sorted(day for day in derived.covered_days if day <= max(attempted))
    assert shared and all(
        live.is_trading_day(day) == derived.is_trading_day(day) for day in shared
    ), "and it agrees with the store on every day the store can answer for"


def test_the_Q19_guard_leaves_TODAY_permanently_unattended_in_the_daily_store() -> None:
    """F1's other end: the pre-open top-up can never reach the day the screener needs.

    :func:`acumen.live_refresh.last_completed_trading_day` is ``prev_trading_day(today)``,
    strictly before today, always -- Q-19's own discipline. So after a perfect refresh the daily
    store still has no row for today, which is exactly the date the derived calendar refuses.
    """
    calendar = cal.TradingCalendar.from_holidays([date(2026, 1, 26)], covered_years=[2026])
    for today in (date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)):
        assert lr.last_completed_trading_day(calendar, today) < today


def test_THE_LIVE_PATH_IS_NOW_BUILT_AND_RUN_somewhere_that_is_not_a_refusal() -> None:
    """F1's other half, and the reason 2,392 green tests did not catch it. FLIPPED.

    The live POSTURE was exercised everywhere -- but always by constructing
    :class:`acumen.live_screener.LiveScreener` directly (``tests.test_live_screener.make_screener``
    with ``live=True``) or by mutating a replay screener's fields
    (``docs/evidence/chunk13_context47_walk.py``). The two places that called
    ``build_live_screener(mode="live")`` were both in ``tests/test_live_safety.py`` and both
    asserted a REFUSAL. **No test, no evidence document and no artefact anywhere in the repo ever
    successfully constructed the shipped live path**, which is exactly the coverage gap finding
    F1 lived in and exactly why a green suite meant nothing about it.

    What this probe now requires is the thing whose absence caused the FAIL: at least one caller
    that builds ``mode="live"`` and asserts it WORKS, and it must not be a refusal test.
    """
    callers: dict[str, int] = {}
    for path in sorted(REPO.glob("tests/*.py")) + sorted(REPO.glob("docs/evidence/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
                node.func, "id", ""
            )
            # (a) build_live_screener(mode="live") directly ...
            if name == "build_live_screener":
                for keyword in node.keywords:
                    if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) \
                            and keyword.value.value == "live":
                        callers[path.name] = callers.get(path.name, 0) + 1
            # ... or (b) the SHIPPED CLI driven with --mode live, which is stronger: it proves
            # the whole entry point, which is the thing REVIEW_13 found reached none of the
            # class it drives.
            elif name == "main":
                literals = [
                    element.value
                    for argument in node.args if isinstance(argument, ast.List)
                    for element in argument.elts
                    if isinstance(element, ast.Constant)
                ]
                if "--mode" in literals and "live" in literals:
                    callers[path.name] = callers.get(path.name, 0) + 1

    assert "test_review13_fix.py" in callers, (
        "the FIX-2 session's own end-to-end live test drives the shipped live path; if it is "
        "gone, the coverage gap that caused REVIEW_13's FAIL is back"
    )
    positive = {name: count for name, count in callers.items() if name != "test_live_safety.py"}
    assert positive, (
        "every live-mode construction in the repo is a refusal test again -- that was the gap"
    )


# --- F2/M17: WHICH CALENDAR GOVERNED -- FLIPPED BY THE FIX-2 SESSION -----------------------------


def test_the_recording_NAMES_the_calendar_that_actually_governed(tmp_path: Path) -> None:
    """REVIEW_13 finding F2 / **M17**, FIXED and FLIPPED. The C5 duty is COMPUTED, not asserted.

    ``build_live_screener`` took ``calendar`` and ``calendar_source`` and forwarded them to the
    manifest -- and NO shipped call site passed either, so every recording ever written stamped
    ``governing_source = "published-nse-holiday-master"`` (the parameter DEFAULT) beside readings
    taken from ``runner.calendar``, which is the DERIVED store-scan calendar. The manifest's own
    ``calendar_source_field`` said ``"derived"`` in the same block, so the two halves of the pair
    the code comment calls a cross-check contradicted each other, and the preflight printed the
    false half. Demonstrated by the review on a real run (2026-02-01). C5's duty was executed in
    ``refresh_calendar`` and then thrown away one line later, by ``del calendar``.

    Both ends are closed. There is no default to fall back to (the parameter is ``None`` and the
    source is DERIVED from the mode when nothing is supplied), and ``run_screener.main`` now
    keeps the calendar the refresh cross-checked and hands it to the session that runs on it.
    """
    signature = inspect.signature(ls.build_live_screener)
    assert signature.parameters["calendar"].default is None
    assert signature.parameters["calendar_source"].default is None, (
        "there is no 'published' default left to be stamped on a derived reading"
    )

    body = inspect.getsource(ls.build_live_screener)
    assert "CALENDAR_PUBLISHED if live else CALENDAR_STORE_SCAN" in body, (
        "the source is decided by what governs, not by a parameter nobody passes"
    )

    cli = inspect.getsource(__import__("acumen.run_screener", fromlist=["main"]).main)
    deleted = {
        target.id
        for node in ast.walk(ast.parse(cli.lstrip()))
        if isinstance(node, ast.Delete)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "calendar" not in deleted, (
        "the C5 duty is no longer executed and then thrown away one line later"
    )
    assert "calendar=published_calendar" in cli, (
        "the calendar refresh_calendar fetched AND cross-checked is the calendar the session "
        "runs on and records"
    )

    manifest_body = inspect.getsource(ls._manifest)
    assert '"governing_source": calendar_source' in manifest_body
    assert '"calendar_source_field": calendar.source' in manifest_body, (
        "both readings are still recorded side by side -- what changed is that the first is now "
        "computed rather than defaulted, so they can no longer contradict each other"
    )
    del tmp_path


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


# --- F5/B3: THE POC AFTER 11:15 -- FLIPPED BY THE FIX-2 SESSION ---------------------------------


def test_the_live_POC_IS_PINNED_at_11_15_even_when_the_window_was_incomplete(
    tmp_path: Path,
) -> None:
    """REVIEW_13 finding F5 / **B3**, FIXED and FLIPPED. CONTEXT 3.3: *"POC is fixed for the rest
    of the day once computed."* The live layer recomputed it at every boundary.

    :meth:`acumen.live_screener.LiveScreener._evaluate` calls the pipeline over *the bars in
    hand* at each boundary, and nothing caches the profile -- only the settled BATTERY is cached
    (``self.gates``). So a symbol whose 11:15 answer was short by even one minute gets a
    PROVISIONAL POC at 11:15 and a different one at 11:30, after CONTEXT 4.4's own healing
    re-pull. The 11:14 bar closes AT 11:15:00 and CONTEXT 4.4 measures it arriving ~0.2s later,
    so a short 11:15 window is the expected case for the first symbols in sweep order, not an
    exotic one.

    Measured on the real lake over 290 symbol-days (20 symbols x 95 days for the arming flip):
    the POC moved on 2.76% of symbol-days if only the 11:14 bar was late and on 14.48% if the
    last five minutes were, and 53 real symbol-days were found where that flipped the 11:15
    ARMED decision -- in both directions.

    **FLIPPED.** The architect's 08-Aug-2026 ruling: *"the POC is fixed at 11:15 and immutable
    for the day; a window missing its late minutes is a completeness failure -- flag 'POC
    provisional / incomplete window' and never silently re-fix."* Both halves are asserted: the
    POC does not move when the window heals, and the day says out loud that it was pinned short.

    Run on a REAL symbol-day, because the synthetic day's minutes are too uniform to move a POC
    and a probe that cannot fail proves nothing -- this one FAILED here before the fix, on these
    exact inputs.
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

    def run(source):
        screener = ls.build_live_screener(
            day, (symbol,), source=source,
            recording=LiveRecording.at(tmp_path / f"rec{id(source)}"),
            clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
            mode="replay", sinks=(ls.CollectingAlertSink(),),
        )
        seen = []
        for boundary in ls.boundary_stamps(day)[:3]:
            screener.clock.set(boundary)
            screener.sweep(boundary)
            seen.append(screener.states[symbol].poc_paise)
        return screener, seen

    short, seen = run(ShortFirstAnswer(StoredDayBarSource(store), drop))
    assert all(poc is not None for poc in seen)
    assert seen[0] == seen[1] == seen[2], (
        "CONTEXT 3.3: the POC is fixed for the rest of the day once computed -- the healed "
        "window at 11:30 does NOT re-fix the 11:15 answer"
    )
    state = short.states[symbol]
    assert state.poc_provisional is True and state.poc_missing_minutes >= drop, (
        "and the incompleteness is FLAGGED rather than silently re-fixed (the architect's ruling)"
    )

    # The unmutilated day pins the same window whole, and says so.
    whole, whole_seen = run(StoredDayBarSource(store))
    assert whole.states[symbol].poc_provisional is False
    assert whole_seen[0] == whole_seen[1] == whole_seen[2]
    assert seen[0] != whole_seen[0], (
        "the two POCs really do differ -- so the pin is holding a DIFFERENT answer, which is "
        "what makes 'never silently re-fix' a decision rather than a no-op"
    )

    events = {row["kind"] for row in short.recording.events()}
    assert "poc-pinned" in events, "and the pinning is in the recording, with its window count"


def test_a_corrected_ARMED_alert_IS_DELIVERED_when_the_state_it_described_changes(
    tmp_path: Path,
) -> None:
    """F5's consequence at the alert, FLIPPED -- REVIEW_13 B334 / B9 / M6.

    ``(symbol, kind)`` is the right key for the ordinary case CONTEXT 4.4 worries about -- the
    same trigger re-derived at seventeen boundaries must be sent once. It was the wrong key for a
    state the tool had since changed its mind about: an ARMED alert sent against a provisional
    POC could not be re-sent, amended or withdrawn, and because the check sat ABOVE
    ``record_alert`` the suppressed alert left no trace anywhere either.

    The key is re-cut to ``(symbol, kind, identity)``. Both properties are asserted: the same
    answer is still sent ONCE, and a DIFFERENT answer is delivered as a correction that names
    what it supersedes.
    """
    from test_backtest import SYMBOL  # noqa: E402 -- the suite's own synthetic world
    from test_live_screener import make_screener  # noqa: E402

    screener, sink, rec = make_screener(tmp_path)
    first = screener._alert(
        ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 15),
        {"side": "long", "poc_paise": "1", "reference_paise": 10},
    )
    assert screener._deliver(first) is True
    again = screener._alert(
        ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 30),
        {"side": "long", "poc_paise": "1", "reference_paise": 10},
    )
    assert screener._deliver(again) is False, "the SAME answer is still sent exactly once"

    corrected = screener._alert(
        ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 45),
        {"side": "long", "poc_paise": "2", "reference_paise": 10},
    )
    assert screener._deliver(corrected) is True, (
        "a corrected ARMED alert reaches the trader instead of being swallowed"
    )
    assert len(sink.alerts) == 2
    assert sink.alerts[-1].payload["correction"] is True
    assert sink.alerts[-1].payload["supersedes"], "and it names the answer it replaces"
    # ... and it is in the RECORDING, which is where a superseded alert used to leave no trace.
    recorded = [row for row in rec.alerts() if row["kind"] == ls.ALERT_ARMED]
    assert len(recorded) == 2 and recorded[-1]["payload"].get("correction") is True


# --- F6/B5: THE CREDENTIAL LOGGING GUARD -- FLIPPED BY THE FIX-2 SESSION -------------------------


def test_the_credential_guard_SURVIVES_the_vendor_SDK_constructor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW_13 finding F6 / **B5**, FIXED and FLIPPED. CLAUDE.md rule 4: never LOG ``.env``.

    :func:`acumen.smartapi_client._quiet_library_logging` raised logzero to CRITICAL exactly as
    its docstring said -- and then ``_default_connect_factory`` constructed ``SmartConnect``,
    whose own setup calls back into logzero, RESET the level to ERROR and installed a
    ``RotatingFileHandler`` writing ``logs/<date>/app.log``. The guard ran one line too early.
    The vendor then logs every request's headers, which carry ``X-PrivateKey: <api key>`` and
    ``Authorization: Bearer <session jwt>``. Measured in isolation before the fix: level 10 ->
    **50 after the guard** -> **40 after the constructor**, with a ``RotatingFileHandler@40``
    attached; and on this machine's disk, 97 X-PrivateKey lines and 86 Bearer lines across six
    files.

    **FLIPPED.** The constructor still does exactly what it did -- the assertion in the middle
    of this probe proves it, so the diagnosis stays measured rather than remembered -- and the
    guard now runs on the FAR SIDE of it and detaches the file handler as well as raising the
    level. A level alone would not be enough: an attached file handler is a file that can still
    be written, and the artefact this rule is about is a file on disk.

    This probe never reads ``.env`` and never prints a secret -- it measures the LOGGER, which is
    the mechanism.
    """
    logzero = pytest.importorskip("logzero")
    pytest.importorskip("SmartApi")
    import logging

    from acumen import smartapi_client as sac

    monkeypatch.chdir(tmp_path)  # any log file the SDK opens lands here, never in the repo

    sac._quiet_library_logging()
    assert logzero.logger.level == logging.CRITICAL, "the guard does raise the threshold"
    assert not [h for h in logzero.logger.handlers if isinstance(h, logging.FileHandler)]

    from SmartApi import SmartConnect  # noqa: F401 -- constructing it is the point

    SmartConnect(api_key="DUMMY-KEY-NOT-REAL")

    # The vendor's behaviour is UNCHANGED, and that is the point: the fix does not depend on it.
    assert logzero.logger.level == logging.ERROR
    assert any(isinstance(h, logging.RotatingFileHandler if hasattr(logging, "RotatingFileHandler")
                          else logging.FileHandler) for h in logzero.logger.handlers), (
        "the constructor still installs a file handler at ERROR -- so the guard has to run after"
    )

    sac._quiet_library_logging()  # ... which is what _default_connect_factory now does
    assert logzero.logger.level == logging.CRITICAL, (
        "the guard, re-run on the far side of the constructor, takes the level back above ERROR"
    )
    assert not [h for h in logzero.logger.handlers if isinstance(h, logging.FileHandler)], (
        "and DETACHES the file handler: a level alone leaves a file that can still be written"
    )

    factory = inspect.getsource(sac._default_connect_factory)
    assert factory.count("_quiet_library_logging()") == 2, (
        "the factory guards on BOTH sides of the constructor -- that is the whole fix"
    )


def test_a_full_LIVE_POSTURE_session_writes_NO_credential_shaped_line_to_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B5's tripwire, at the ARTEFACT rather than at ``repr()``.

    REVIEW_13's instruction was explicit: *"call ``_quiet_library_logging()`` after the vendor
    constructor as well as before, and assert it at the artefact (``logs/``), not at
    ``repr()``."* So this drives the real vendor constructor through the real factory, inside a
    scratch working directory, then makes the vendor's own logger try to emit exactly the line
    that leaked -- full request headers with an ``X-PrivateKey`` and a ``Bearer`` token -- and
    walks every byte of every file under ``logs/`` afterwards.

    The credential shapes here are INVENTED constants. No secret is read, printed or written by
    this probe, and the strings it plants are what it then proves absent.
    """
    logzero = pytest.importorskip("logzero")
    pytest.importorskip("SmartApi")
    import logging

    from acumen import smartapi_client as sac

    monkeypatch.chdir(tmp_path)
    planted_key = "NOT-A-REAL-KEY-0000"
    planted_token = "Bearer " + "n0taRealSessionTokenAtAll_0123456789"

    sac._default_connect_factory("DUMMY-KEY-NOT-REAL")  # both guards, around the real SDK

    # The vendor logs at ERROR. Try it at ERROR *and* at CRITICAL, so the proof does not rest on
    # the level alone -- a detached handler is what makes even a CRITICAL line reach no file.
    for level in (logging.ERROR, logging.CRITICAL):
        logzero.logger.log(
            level, "request headers: {'X-PrivateKey': '%s', 'Authorization': '%s'}",
            planted_key, planted_token,
        )

    logs = tmp_path / "logs"
    written = sorted(logs.rglob("*")) if logs.is_dir() else []
    offenders = []
    for path in written:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if planted_key in text or planted_token in text or "X-PrivateKey" in text:
            offenders.append(str(path.relative_to(tmp_path)))
    assert not offenders, (
        f"a live-posture session wrote credential-shaped headers to {offenders} -- CLAUDE.md "
        "rule 4 says LOGGED, not only committed"
    )


def test_the_repos_own_run_logs_carry_NO_credential_shaped_headers() -> None:
    """F6's defect pin, **FLIPPED** (chunk 14): the logs are clean and this now holds them so.

    ``logs/`` is gitignored, so nothing reached git -- but CLAUDE.md rule 4 says *logged*, not
    *committed*, and :mod:`acumen.run_screener` opens a broker session on every live morning, so
    a dry-run week would have been five more days of this. Detection is by HEADER SHAPE, so this
    probe needs no secret and leaks none.

    **The skip-vs-red one-liner, and why it mattered.** As pinned, the probe was green while the
    defect stood and *skipped* -- ``"this machine's logs/ has been rotated since the review --
    nothing to pin"`` -- once it was fixed. So the receipt for closing B5's outstanding operator
    half was a SKIP, indistinguishable from "this machine has no logs directory", and REVIEW_13B
    (*"the operator rotates the six logs/ files ... which turns its probe red"*) would have been
    waiting for a red that could never arrive. This session made that branch ``pytest.fail``
    first and ran it, and it went red on the sentence above -- the operator HAS rotated the six
    files -- which is the receipt the flip is licensed by. Recorded because a pin that cannot go
    red is not a pin.

    Flipped, it is the standing guarantee: **no file under ``logs/`` carries a credential-shaped
    header**. An absent ``logs/`` is that guarantee trivially satisfied, not a skip -- there is
    nothing to leak in a directory that does not exist, and a clone deserves the same green.
    """
    logs = REPO / "logs"
    private_key = bearer = 0
    offenders: list[str] = []
    for path in sorted(logs.rglob("*.log")) if logs.is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="ignore")
        here = len(re.findall(r"'X-PrivateKey':\s*'[^']{4,}'", text))
        there = len(re.findall(r"'Authorization':\s*'Bearer [A-Za-z0-9_\-.]{20,}'", text))
        if here or there:
            offenders.append(f"{path.relative_to(REPO)}: {here} key line(s), {there} token(s)")
        private_key += here
        bearer += there
    assert not offenders, (
        f"{len(offenders)} log file(s) carry {private_key} X-PrivateKey line(s) and {bearer} "
        "Bearer token line(s) -- CLAUDE.md rule 4 says LOGGED, not only committed. The guard is "
        "`acumen.smartapi_client._quiet_library_logging`, called on BOTH sides of the vendor "
        "constructor; rotate the files it already wrote.\n" + "\n".join(offenders)
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
