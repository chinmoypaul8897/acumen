"""REVIEW_14's FIX session -- one test per finding, each driving the REAL path.

REVIEW_14 failed chunk 14 on its edges: a fence that was never asked (B1), a certifying test
that asserted its own name (B2), a documented morning command that mutated the stores and then
refused to start (B3), a three-act Telegram gate with two acts in code (H1), a summary that
reports an empty day after a resume (H2), a ``qty == 0`` transition that walks BACKWARDS along
``PHASE_RANK`` (H3), a freshness stamp that can be FALSE (H4), a parity harness that cannot
judge the live posture (H5), and three carried majors that block the dry-run week (M19, M15,
M16).

Every test here drives the shipped code -- the CLI, ``morning_refresh``, ``LiveScreener.sweep``,
``TelegramSink`` -- rather than a helper beside it, because the finding that generated
CLAUDE.md's newest rule is exactly the other kind.

**The scratch world.** The tests that need stores build a COPY (never a link -- CLAUDE.md
data-store safety) of the slices of ``data_root`` and ``cache_root`` one symbol-day needs, and
point a scratch ``config.yaml`` at it. Every mutation any test here can cause lands inside that
copy: *a review or any session may NEVER run a mutating CLI against the real
data_root/cache_root* (CLAUDE.md, REVIEW_14 store incident).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from acumen import calendar as cal
from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import parity
from acumen import run_screener
from acumen import signals as sig
from acumen import telegram_sink as tg
from acumen.config import load_config
from acumen.daily_store import DailyStore
from acumen.live_recording import LiveRecording, RecordedAlert
from acumen.live_source import StoredDayBarSource
from acumen.minute_store import MinuteStore, StoredBar

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"

SYMBOL = "HDFCBANK"
DAY = date(2026, 6, 10)


def _stores_or_skip() -> Path:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    for relpath in ("daily_store", "minute_store"):
        if not (data_root / relpath).is_dir():
            pytest.skip(f"local {relpath} is absent (the stores are gitignored)")
    return data_root


def build_scratch_world(root: Path, *, day: date = DAY, symbol: str = SYMBOL) -> Path:
    """COPY the slices of both stores one symbol-day needs, and return a config that names them.

    A copy, never a junction or a symlink (CLAUDE.md data-store safety, the Q-18 incident). What
    is copied is exactly what a live morning for ``day`` reads: the daily ledger and the two
    calendar years CONTEXT 3.2's 180-day bias seed reaches back through, the symbol's own minute
    partition and the minute ledger, the corporate-action cache the factor tables are built from,
    the disclosed-residual register, the instrument masters (the Q-20 pin, and a copy of it under
    the day's own name so CONTEXT 4.7 / Q-29's prerequisite is on disk), a published holiday
    day-cache stamped for the day, and a corporate-action day-cache for the refresh's own window.
    """
    config = load_config(include_env=False)
    real_data, real_cache = config.path("data_root"), config.path("cache_root")
    data, cache = root / "data", root / "cache"

    (data / "daily_store").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "daily_store" / "ledger.parquet",
                    data / "daily_store" / "ledger.parquet")
    for year in {day.year, (day - timedelta(days=ls.SEED_LOOKBACK_DAYS + 40)).year}:
        shutil.copytree(real_data / "daily_store" / "daily" / str(year),
                        data / "daily_store" / "daily" / str(year), dirs_exist_ok=True)
    shutil.copytree(real_data / "minute_store" / "ledger", data / "minute_store" / "ledger")
    shutil.copytree(real_data / "minute_store" / "minute" / symbol,
                    data / "minute_store" / "minute" / symbol)
    shutil.copytree(real_data / "nse", data / "nse")
    (data / "universe_backfill").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_data / "universe_backfill" / "ledger.json",
                    data / "universe_backfill" / "ledger.json")

    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    pin = real_cache / "instrument_master" / config.instrument_master
    shutil.copyfile(pin, cache / "instrument_master" / config.instrument_master)
    shutil.copyfile(pin, cache / "instrument_master" / ls.day_master_filename(day))

    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=day
    )
    window_start = day - timedelta(days=refresh.DEFAULT_LOOKBACK_DAYS)
    ca_file = cache / "ca" / f"nse_ca_{window_start.isoformat()}_{day.isoformat()}.json"
    ca_file.parent.mkdir(parents=True, exist_ok=True)
    ca_file.write_text(
        json.dumps({"fetched_on": day.isoformat(), "payload": []}), encoding="utf-8"
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


@pytest.fixture(scope="module")
def scratch_world(tmp_path_factory) -> Path:
    """One copied world per module run -- the copy is ~65 MB and the tests only read it."""
    _stores_or_skip()
    root = tmp_path_factory.mktemp("review14-world")
    return build_scratch_world(root)


def _fingerprint(root: Path) -> tuple:
    return tuple(
        (p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*")) if p.is_file()
    )


# --- B3: the documented morning command must START the screener ---------------------------------


def test_B3_the_runbooks_own_0845_command_STARTS_the_screener(
    scratch_world: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """REVIEW_14 **B3**, closed -- through ``run_screener.main``, which nothing else drives.

    ``docs/morning_runbook_stub.md`` section 1 tells the operator to run

        python -m acumen.run_screener --mode live --day <TODAY> --refresh --allow-network
        --preflight-only

    and REVIEW_14 measured what that did: ``morning_refresh`` handed ``build_live_screener`` the
    PUBLISHED holiday calendar, whose ``trading_days`` is None; ``build_live_screener`` composed
    a live calendar only when the caller supplied NONE, so it was skipped; and ``build_runner``
    refuses any supplied calendar without an explicit trading-day set. The morning mutated the
    stores and then printed *"the screener cannot start"*, exit 1. **No test in the repository
    drove ``--refresh`` through the CLI**, which is why a whole pre-open-to-screener seam was
    unexercised -- so this is that test, and it is the one that would have caught it.

    It runs against the COPIED world, so the ``--refresh`` inside it can write all it likes and
    nothing under the real roots can move (CLAUDE.md, REVIEW_14 store incident).
    """
    code = run_screener.main([
        "--mode", "live", "--day", DAY.isoformat(), "--symbols", SYMBOL,
        "--refresh", "--allow-network", "--preflight-only",
        "--config", str(scratch_world), "--recording-root", str(tmp_path / "rec"),
    ])
    out = capsys.readouterr().out

    assert code == 0, out[-2000:]
    assert "the screener cannot start" not in out, "B3, verbatim"
    assert "READY" in out and "NOT READY" not in out
    assert "ACUMEN SCREENER PREFLIGHT" in out, "the screener really started"
    assert f"mode=live" in out and "biases resolved      1" in out
    # ...and the calendar the session RECORDS is the published master the refresh cross-checked
    # (REVIEW_13 M17), now composed rather than passed on raw.
    manifest = json.loads(
        (tmp_path / "rec" / f"{DAY.isoformat()}-live" / "manifest.json").read_text("utf-8")
    )
    assert manifest["calendar"]["governing_source"] == "published-nse-holiday-master"
    assert manifest["calendar"]["is_trading_day"] is True


def test_B3_a_published_calendar_reaches_build_runner_COMPOSED(scratch_world: Path) -> None:
    """The mechanism, isolated: a trading-day-less calendar in, a usable calendar out.

    ``TradingCalendar.from_holidays`` is what ``refresh_calendar`` returns, and it carries no
    explicit trading-day set by construction. ``build_live_screener`` must compose it through
    ``calendar.live_trading_calendar`` -- published for today, the store's own scan for the
    history behind it, which is the C5 division of labour -- rather than hand it to a runner that
    refuses it.
    """
    config = load_config(scratch_world, include_env=False)
    published = cal.fetch_calendar(cache_dir=config.path("cache_root"), today=DAY)
    assert published.trading_days is None, "the shape --refresh really supplies"

    composed = ls._live_calendar(
        day=DAY, first_day=DAY - timedelta(days=ls.SEED_LOOKBACK_DAYS + 30),
        data_dir=config.path("data_root"), cache_dir=config.path("cache_root"),
        allow_network=False, published=published,
    )
    assert composed.trading_days is not None, "which is what build_runner requires"
    assert DAY in composed.trading_days
    assert set(published.holidays) <= set(composed.holidays), (
        "the published master still governs the holidays it knows; the store scan supplies the "
        "history behind it, which is the C5 division of labour"
    )
    for holiday in published.holidays:
        assert holiday not in composed.trading_days, holiday


def test_B3_the_daily_topup_names_the_store_it_was_HANDED(tmp_path: Path) -> None:
    """The neighbour B3's CLI test uncovered: ``--config`` must govern what gets written.

    ``refresh_daily_store`` invoked the backfill with no ``--store``, so it resolved
    ``default_store_root()`` -- the data_root of whatever ``config.yaml`` the PROCESS had loaded
    -- and topped up THAT store however the caller had been pointed. Measured through the CLI on
    a scratch world: the top-up printed the REAL store's path. A session running against a copy
    would have written into the original, which is the write CLAUDE.md's newest rule forbids.
    """
    seen: list[list[str]] = []
    store = DailyStore.at(tmp_path / "scratch-store")

    step = refresh.refresh_daily_store(
        store=store,
        calendar=cal.TradingCalendar.from_holidays([date(2026, 1, 26)], covered_years=[2026]),
        today=date(2026, 8, 7), runner=lambda argv: (seen.append(list(argv)), 0)[1],
    )
    assert seen == [[
        "--from", "2026-07-27", "--to", "2026-08-06", "--store", str(tmp_path / "scratch-store"),
    ]]
    assert step.figures["store"] == str(tmp_path / "scratch-store")


def test_the_morning_refresh_survives_a_calendar_it_cannot_read(tmp_path: Path) -> None:
    """The pre-open's one unguarded step, guarded -- and NOT RUN stated rather than implied.

    Every other step of ``morning_refresh`` was wrapped; the calendar was not, so an unreadable
    published master left ``run_screener.main`` with a traceback from four layers down instead of
    REVIEW_12C C2's one sentence and exit 1. The steps that cannot run without a calendar now say
    so by name, because a step that is silently absent from a report reads as a step that passed
    -- which is M15's shape, refused before it can be made.
    """
    calendar, universe, report = refresh.morning_refresh(
        today=date(2026, 8, 7), store=DailyStore.at(tmp_path / "daily_store"),
        cache_dir=tmp_path / "no-cache-here", allow_network=False, symbols=("AAA",),
        daily_runner=lambda argv: 0, recording_root=tmp_path / "rec",
    )
    steps = {step.name: step for step in report.steps}

    assert calendar is None and not report.ok
    assert not steps["calendar (published NSE)"].ok
    assert "QUESTIONS.md C5" in steps["calendar (published NSE)"].detail
    for name in ("daily store (bhavcopy top-up)", refresh.VERIFY_STEP):
        assert steps[name].detail.startswith("NOT RUN:"), name
        assert not steps[name].ok, name
    assert len(report.steps) == 6, "every step is still reported, none silently dropped"
    assert universe == ("AAA",)


# --- H1: the Telegram gate is three acts, and a replay can never reach the phone ----------------


def _alert(kind: str = ls.ALERT_TRIGGER, **payload) -> RecordedAlert:
    body = {"side": "long", "entry_paise": 74095, "stop_paise": 73810, "target_paise": 74950,
            "qty": 350, "poc_paise": 73980, "bias": "bullish", "stale": False,
            "data_behind_minutes": 0}
    body.update(payload)
    return RecordedAlert(kind=kind, symbol="SHREECEM", at=datetime(2020, 3, 19, 11, 30),
                         payload=body)


def test_H1_a_REPLAY_with_telegram_and_live_alerts_sends_NOTHING(
    scratch_world: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """REVIEW_14 **H1**, closed, through ``main()`` -- the exact command the review measured.

    ``--day 2020-03-19 --symbols SHREECEM --telegram --live-alerts`` with the mode DEFAULTED
    (replay) put two real messages on the transport, and the first of them read

        [11:30] SHREECEM LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, ...)

    -- no date, no mode, no replay marker, and no CONTEXT 4.7 disclosure to distinguish it,
    because a replay carries none. Not one byte on that phone said it was about a day in 2020.

    The gate now names the mode. This drives the whole CLI over a real day and asserts the
    transport was never touched -- not that the sink is configured a certain way.
    """
    transport: list[str] = []
    original = tg.post_message
    tg.post_message = lambda text, **kwargs: transport.append(text)   # never reached
    try:
        code = run_screener.main([
            "--day", DAY.isoformat(), "--symbols", SYMBOL,          # mode DEFAULTS to replay
            "--telegram", "--live-alerts",
            "--config", str(scratch_world), "--recording-root", str(tmp_path / "rec"),
        ])
    finally:
        tg.post_message = original
    out = capsys.readouterr().out

    assert code == 0, out[-2000:]
    assert transport == [], (
        "a replayed day reached the trader's phone with --telegram --live-alerts:\n"
        + "\n---\n".join(transport)
    )
    assert "DRY RUN -- nothing was sent" in out
    # ...and the alerts really were produced, so this is not a test of an empty morning.
    alerts = list(LiveRecording.at(tmp_path / "rec" / f"{DAY.isoformat()}-replay").alerts())
    assert alerts, "the replay delivered alerts; only the forwarding was gated"


def test_H1_the_gate_is_MODE_and_telegram_and_live_alerts(scratch_world: Path) -> None:
    """The truth table, over the gate the CLI really computes. Three acts, all three required."""
    cases = {
        ("live", True, True): True,
        ("live", True, False): False,
        ("live", False, True): False,
        ("replay", True, True): False,
        ("replay", True, False): False,
    }
    for (mode, telegram, live_alerts), expected in cases.items():
        argv = ["--mode", mode, "--day", DAY.isoformat(), "--symbols", SYMBOL,
                "--config", str(scratch_world)]
        argv += ["--telegram"] if telegram else []
        argv += ["--live-alerts"] if live_alerts else []
        args = run_screener.parse_args(argv)
        assert run_screener.telegram_is_live(args) is expected, (mode, telegram, live_alerts)


def test_H1_a_replay_or_dry_message_can_never_be_read_as_a_live_one() -> None:
    """The second half of H1: what a message that is NOT about today has to carry.

    A live alert is separated from a replayed one by CONTEXT 4.7's disclosed line, which a replay
    has no reason to carry -- so on the phone the two were byte-identical apart from a price. The
    message now carries its DATE and, when it is not a live morning's own alert, a marker that
    says which posture produced it. The disclosure still travels whenever there is one.
    """
    dry = tg.message_for(_alert(dry_run=True))
    assert "2020-03-19" in dry, "the trade date, on the message, always"
    assert tg.DRY_RUN_MARKER in dry

    replayed = tg.message_for(_alert(dry_run=False, mode="replay"))
    assert "2020-03-19" in replayed
    assert tg.REPLAY_MARKER in replayed, "a replayed day names itself as one"

    live = tg.message_for(_alert(dry_run=False, mode="live", disclosure=ls.LIVE_DISCLOSURE))
    assert ls.LIVE_DISCLOSURE in live and tg.REPLAY_MARKER not in live
    assert "2026" not in live and "2020-03-19" in live

    summary = tg.TelegramSink(live=True).end_of_day_message(
        (_alert(mode="replay"),), day=date(2020, 3, 19)
    )
    assert tg.REPLAY_MARKER in summary, "and so does the one message that ends the morning"


# The prose half of H1 -- the five places that claim three acts -- is asserted by the FLIPPED
# census probe in tests/test_review14_probes.py, where the review put it.


# --- M19: one poisoned symbol must not cost the morning -----------------------------------------


def test_M19_one_poisoned_symbol_loses_ITS_boundary_and_not_the_morning(
    scratch_world: Path, tmp_path: Path,
) -> None:
    """REVIEW_14 PART 4, **M19** -- the finding that disqualifies the dry-run week, closed.

    Measured by the review: a 10-symbol live morning with ONE poisoned symbol raised ``PocError``
    at the FIRST boundary and **the exception escaped ``run_screener.main`` entirely** -- 0 of 18
    sweeps, ``sweeps_done == []``, six symbols never evaluated once, no banner, and
    ``dashboard.html`` never written. A restart could not recover it: the poison is deterministic
    and ``restore()`` resumes into the same raise. One symbol did not lose one boundary; it lost
    the morning.

    CONTEXT 4.4's discipline is already implemented on the FETCH side (*"on failure SKIP the
    symbol and re-poll at sweep end"*); this is the same discipline on the EVALUATION side. The
    other nine symbols complete every sweep, the banner NAMES the one that did not, and the
    recording carries the reason.
    """
    config = load_config(scratch_world, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    if not store.minutes(SYMBOL, DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    # Ten REAL F&O names, so the instrument master can price all ten -- the day's bars are one
    # real session fanned out, which is what makes the nine healthy symbols genuinely evaluable.
    symbols = ("HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
               "RELIANCE", "AXISBANK", "ITC", "LT", "WIPRO")
    poisoned = symbols[3]
    real = tuple(store.minutes(SYMBOL, DAY))

    class _Fanout:
        """One real day, served under ten names, with one of them poisoned."""

        def fetch(self, symbol: str, day: date, upto: datetime):
            bars = tuple(bar for bar in real if bar.stamp <= upto)
            if symbol == poisoned and bars:
                stray = replace(bars[0], stamp=bars[0].stamp - timedelta(days=1))
                return (stray,) + bars
            return bars

    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec-m19")
    screener = ls.LiveScreener(
        day=DAY, symbols=symbols,
        pipeline=_pipeline(config), biases={s: _bias(config, DAY) for s in symbols},
        gates={}, source=_Fanout(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    recording.open_session({"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(symbols)})

    def after(report: ls.SweepReport) -> None:
        """The CLI's own on_sweep hook -- ``dashboard.html`` is written after every sweep."""
        from acumen import live_dashboard as dash

        dash.write_dashboard(
            recording.root, day=DAY, now=report.boundary, grouped=screener.by_phase(),
            alerts=tuple(sink.alerts), banner=screener.banner, dry_run=screener.dry_run,
            disclosure=screener.disclosure, verification=None,
        )

    reports = screener.run_day(on_sweep=after)

    # 1. THE MORNING SURVIVED: every boundary swept, the day closed, the screen written.
    assert len(reports) == 18, "18 boundaries including close_day's 15:30 poll"
    assert len(screener.sweeps_done) == 18
    assert (recording.root / "dashboard.html").is_file(), (
        "the trader's screen was never written at all before this fix"
    )
    assert all(report.unevaluated == (poisoned,) for report in reports), (
        "one symbol failed at every boundary -- the poison is deterministic, as the review said"
    )
    assert all(report.evaluated == 9 for report in reports), (
        "nine symbols evaluated at every one of the eighteen sweeps"
    )

    # 2. THE OTHER NINE completed every sweep, and produced their alerts.
    healthy = [s for s in symbols if s != poisoned]
    for symbol in healthy:
        assert screener.states[symbol].phase != ls.PHASE_SKIPPED, symbol
    assert {a.symbol for a in sink.alerts} >= set(healthy), "nine symbols alerted"

    # 3. THE POISONED ONE is skipped-and-continued, NAMED, and recorded -- never silent.
    assert screener.states[poisoned].phase == ls.PHASE_SKIPPED
    assert poisoned in screener.banner and "NOT being watched" in screener.banner
    failures = [row for row in recording.events() if row["kind"] == ls.EVENT_EVALUATION_FAILED]
    assert failures, "the reason is on disk, per symbol, per boundary"
    assert failures[0]["symbol"] == poisoned
    assert "PocError" in failures[0]["detail"] or "Error" in failures[0]["detail"]

    # 4. ...and a RESTART recovers, which the review measured it could not.
    resumed = ls.LiveScreener(
        day=DAY, symbols=symbols, pipeline=screener.pipeline, biases=screener.biases,
        gates={}, source=_Fanout(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(ls.CollectingAlertSink(),), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    assert resumed.restore()
    assert len(resumed.run_day()) == 18


def test_M19_a_sink_that_raises_costs_its_own_delivery_and_nothing_else(tmp_path: Path) -> None:
    """The second half of M19's surface: the sink loop, which chunk 14 added a fourth member to.

    ``_deliver`` fires every sink in a bare loop, and chunk 14 attached the only one that does
    network I/O. ``TelegramSink.deliver`` never raises by design -- but the loop must not depend
    on every future sink being that careful, because an exception there ends the SWEEP and costs
    the other 203 symbols their boundary.
    """
    class _Exploding:
        def deliver(self, alert):
            raise RuntimeError("this sink is broken")

    collected = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec-sinks")
    recording.open_session({"trade_date": DAY.isoformat(), "mode": "replay", "symbols": []})
    screener = ls.LiveScreener(
        day=DAY, symbols=(), pipeline=None, biases={}, gates={}, source=None,
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(_Exploding(), collected), risk_per_trade_paise=100_000, cost_paise=10_000,
    )
    alert = _alert(ls.ALERT_FAILURE, detail="the screener is not answering")

    assert screener._deliver(alert) is True, "the delivery completed"
    assert [a.kind for a in collected.alerts] == [ls.ALERT_FAILURE], (
        "the sink AFTER the broken one still received the alert"
    )
    failures = [row for row in recording.events() if row["kind"] == ls.EVENT_SINK_FAILED]
    assert failures and "RuntimeError" in failures[0]["detail"]


# --- H3: the M21 fix's phase-regression hole ----------------------------------------------------


BOSCH, BOSCH_DAY = "BOSCHLTD", date(2021, 5, 20)


def test_H3_two_LATE_candles_cannot_walk_a_delivered_trade_into_a_numberless_row(
    tmp_path: Path,
) -> None:
    """REVIEW_14 **H3**, closed on the review's own day and its own numbers.

    ``_consumed_unsizable`` returned its state DIRECTLY instead of through ``_monotonic``, which
    made it the only transition in the screener that could walk BACKWARDS along ``PHASE_RANK``.
    Measured on BOSCHLTD 2021-05-20 with two ordinary late candles -- CONTEXT 4.4's normal case,
    no vendor revision, no duplicate stamp:

    * at 13:30 the entry candle's low is 14,580.00 (the two bars carrying 14,550.20 and 14,566.20
      have not arrived), so risk is 989.90 and ``qty == 1``: the trader is SENT
      ``[13:30] BOSCHLTD LONG entry 15,569.90 SL 14,580.00 TP 18,539.60 qty 1``;
    * at 13:45 the late bars land, the true stop is 14,550.20, risk is 1,019.70 -- past the
      Rs 1,000 budget -- and ``qty`` goes to 0.

    Before the fix the state became a numberless ``refused`` row: no alert, no ``ALERT_FAILURE``,
    no ``phase-regression-refused`` record, 0 of each. The position was unmanaged and 15:15 would
    not have squared it off -- verbatim the sentence ``_alerts_for`` exists to shout for
    REVIEW_13 M5. CONTEXT 3.4-2 consumes the stock-day at the first cross, so the earlier state
    stands and the feed's disagreement is recorded.

    The stores are read, never written: this is a replay over the real lake into a tmp recording.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    bars = tuple(store.minutes(BOSCH, BOSCH_DAY))
    if not bars:
        pytest.skip("the local minute lake does not hold BOSCHLTD 2021-05-20")

    entry_at = datetime.combine(BOSCH_DAY, time(13, 30))
    window = [bar for bar in bars if entry_at - timedelta(minutes=15) <= bar.stamp < entry_at]
    late = {bar.stamp for bar in sorted(window, key=lambda bar: bar.low_paise)[:2]}
    assert len(late) == 2, "the two 1-minute bars carrying the entry candle's true low"

    class _TwoLateCandles:
        """CONTEXT 4.4's ordinary case: two bars arrive one sweep after the rest."""

        def fetch(self, symbol: str, day: date, upto: datetime):
            served = [bar for bar in bars if bar.stamp <= upto]
            if upto <= entry_at:
                served = [bar for bar in served if bar.stamp not in late]
            return tuple(served)

    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec-h3")
    screener = ls.build_live_screener(
        BOSCH_DAY, (BOSCH,), source=_TwoLateCandles(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(BOSCH_DAY, datetime.min.time())),
        mode="replay", sinks=(sink,),
    )
    screener.run_day()

    # 1. The trade REALLY was delivered, with a real quantity, at 13:30.
    trigger = [alert for alert in sink.alerts if alert.kind == ls.ALERT_TRIGGER]
    assert len(trigger) == 1
    assert trigger[0].at == entry_at
    assert trigger[0].payload["qty"] == 1
    assert (trigger[0].payload["entry_paise"], trigger[0].payload["stop_paise"]) == (
        1_556_990, 1_458_000
    ), "the review's own numbers: entry 15,569.90, SL 14,580.00"

    # 2. ...and the late bars did NOT take it away.
    state = screener.states[BOSCH]
    assert state.phase == ls.PHASE_TRIGGERED
    assert state.entry_paise == 1_556_990 and state.qty == 1, (
        "a delivered trade walked backwards into a numberless row -- H3, unfixed"
    )

    # 3. The disagreement is RECORDED rather than absorbed, at every later boundary.
    regressions = [
        row for row in recording.events() if row["kind"] == "phase-regression-refused"
    ]
    assert len(regressions) == 8, len(regressions)
    assert regressions[0]["was"] == ls.PHASE_TRIGGERED
    assert regressions[0]["proposed"] == ls.PHASE_REFUSED

    # 4. And the ordinary qty-0 day -- the same code path with no late candle -- is UNCHANGED:
    #    CONTEXT 3.5's "no trade, consumed + logged", which is REVIEW_13 M21 and must not move.
    plain_sink = ls.CollectingAlertSink()
    plain = ls.build_live_screener(
        BOSCH_DAY, (BOSCH,), source=StoredDayBarSource(store),
        recording=LiveRecording.at(tmp_path / "rec-h3-plain"),
        clock=ls.VirtualClock(stamp=datetime.combine(BOSCH_DAY, datetime.min.time())),
        mode="replay", sinks=(plain_sink,),
    )
    plain.run_day()
    assert plain.states[BOSCH].phase == ls.PHASE_REFUSED
    assert plain.states[BOSCH].refusal == ls.REFUSAL_QTY_ZERO
    assert [alert.kind for alert in plain_sink.alerts] == [ls.ALERT_ARMED]


# --- H4: a freshness stamp that can be FALSE ----------------------------------------------------


def test_H4_a_refused_state_reports_its_REAL_age(tmp_path: Path) -> None:
    """REVIEW_14 **H4**: ``data_age`` short-circuited ``PHASE_REFUSED`` to ``(False, 0)``.

    So the one alert kind that names prices out of a refused state -- the *"the battery now
    REFUSES this day while a position is open"* FAILURE alert, which carries entry, stop, target
    and qty precisely so the trader can manage a position this tool has stopped watching -- was
    stamped ``stale=False, data_behind_minutes=0`` however old its last bar was. Measured: a feed
    frozen at 11:29 produced, at 15:00, a failure alert over a true gap of **211 minutes**, and
    ``unvouched_price`` accepted it.
    """
    frozen = ls.SymbolState(
        symbol=BOSCH, phase=ls.PHASE_REFUSED, refusal="gate 2 (integrity)",
        entry_paise=1_556_990, stop_paise=1_458_000, qty=1, minute_count=120,
        last_stamp=datetime(2026, 6, 10, 11, 29),
    )
    stale, behind = ls.data_age(frozen, datetime(2026, 6, 10, 15, 0))
    assert (stale, behind) == (True, 211), "15:00 minus 11:29 -- the review's own 211 minutes"

    fresh = replace(frozen, last_stamp=datetime(2026, 6, 10, 14, 59))
    assert ls.data_age(fresh, datetime(2026, 6, 10, 15, 0)) == (False, 1)


def test_H4_unvouched_price_rejects_a_FALSE_stamp_not_only_a_missing_one() -> None:
    """The predicate's third failure shape (REVIEW_14 **H4**).

    *"A missing stamp is caught by the predicate; a false one is not."* Both numbers are on the
    payload and they have to agree: a payload claiming FRESH while its own recorded age is past
    the clamp vouches for nothing, and the sink must refuse it exactly as it refuses a stale
    price that lost its marker.
    """
    lying = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol=BOSCH, at=datetime(2026, 6, 10, 15, 0),
        payload={"entry_paise": 1_556_990, "stop_paise": 1_458_000, "qty": 1,
                 "stale": False, "data_behind_minutes": 211},
    )
    refusal = ls.unvouched_price(lying)
    assert refusal is not None and "contradicts itself" in refusal
    assert "211" in refusal

    # ...and the sink really refuses it, rather than merely being able to.
    sent: list[str] = []
    sink = tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None)
    sink.deliver(lying)
    assert sent == [] and len(sink.refused) == 1

    honest = RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol=BOSCH, at=datetime(2026, 6, 10, 15, 0),
        payload={"entry_paise": 1_556_990, "stale": True, "data_behind_minutes": 211,
                 "alert_states": [ls.MARKER_STALE], "stale_note": ls.stale_note(211)},
    )
    assert ls.unvouched_price(honest) is None, "a stale price WITH its marker still travels"


# --- H2: the end-of-day summary after a resume --------------------------------------------------


def test_H2_a_RESUMED_morning_reports_the_days_REAL_alerts(tmp_path: Path) -> None:
    """REVIEW_14 **H2**: the summary said "nothing fired" over a recording holding three alerts.

    ``run_screener`` built the message from ``collected.alerts`` -- what THIS process delivered.
    A resumed morning delivers nothing, because ``restore()`` correctly re-reads a dedup set that
    already holds the day's alerts, so the one summary of a crashed-and-resumed day asserted the
    opposite of the truth. That defeats B402's stated purpose exactly: the message exists so a
    silent phone is never ambiguous between "no signal" and "the tool has stopped".

    Driven the way the CLI drives it: the alerts are written into the recording by a first
    process and the summary is built by a second one that delivered nothing.
    """
    from acumen.live_screener import ALERT_ARMED, ALERT_EXIT, ALERT_TRIGGER

    recording = LiveRecording.at(tmp_path / "rec" / f"{DAY.isoformat()}-live")
    for kind, minute in ((ALERT_ARMED, 15), (ALERT_TRIGGER, 30), (ALERT_EXIT, 45)):
        recording.record_alert(RecordedAlert(
            kind=kind, symbol=SYMBOL, at=datetime.combine(DAY, time(11, minute)),
            payload={"side": "long", "entry_paise": 74095, "qty": 350, "stale": False,
                     "data_behind_minutes": 0, "mode": "live"},
        ))

    sent: list[str] = []
    resumed_sink = tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None)
    assert run_screener._end_of_day_summary(
        resumed_sink, recording, day=DAY, disclosure=ls.LIVE_DISCLOSURE
    ) is True

    assert len(sent) == 1
    message = sent[0]
    assert tg.SUMMARY_NO_ALERTS not in message, (
        "the resumed morning reported an empty day over a recording holding three alerts"
    )
    assert "1 symbol(s) alerted:" in message
    assert f"{SYMBOL}" in message
    for kind, stamp in (("armed", "11:15"), ("trigger", "11:30"), ("exit", "11:45")):
        assert f"{kind} {stamp}" in message, kind
    assert ls.LIVE_DISCLOSURE in message

    # ...and a morning that really fired nothing still says so, in words (B402's own purpose).
    quiet = LiveRecording.at(tmp_path / "rec" / "2026-06-11-live")
    quiet_sent: list[str] = []
    assert run_screener._end_of_day_summary(
        tg.TelegramSink(send=quiet_sent.append, live=True, out=lambda _line: None),
        quiet, day=date(2026, 6, 11),
    ) is True
    assert tg.SUMMARY_NO_ALERTS in quiet_sent[0]


# --- M15 / M16: what "verified" is allowed to mean ----------------------------------------------


def test_M15_a_symbol_that_ALERTED_with_no_candles_is_not_counted_as_zero_alerted(
    tmp_path: Path,
) -> None:
    """REVIEW_14 **M15**: a false GREEN over a morning nothing verified.

    ``verify_prior_recording`` skipped a symbol whose candle file is absent, so it left the
    verdict list entirely -- and the headline then asserted it had alerted zero times:
    ``0/0 symbol-day(s) pass the FULL battery, 0 alerted, 0 alerted-then-refused`` while
    ``alerts.jsonl`` held three alerts. The dry-run week's debrief reads that as *"yesterday
    checked out"*.
    """
    recording = LiveRecording.at(tmp_path / "rec" / f"{DAY.isoformat()}-live")
    recording.open_session({"trade_date": DAY.isoformat(), "mode": "live",
                            "symbols": [SYMBOL], "master_file": "x", "row_size": 24})
    for kind in ("armed", "trigger", "exit"):
        recording.record_alert(RecordedAlert(
            kind=kind, symbol=SYMBOL, at=datetime.combine(DAY, time(11, 30)), payload={},
        ))
    assert recording.bars(SYMBOL, DAY) == (), "the candle file really is absent"

    verification = refresh.verify_prior_recording(recording, _no_pipeline(), day=DAY)

    assert [v.symbol for v in verification.verdicts] == [SYMBOL], (
        "the symbol is in the verdict list, not dropped out of the arithmetic"
    )
    verdict = verification.verdicts[0]
    assert verdict.verified is False and verdict.alerted == ("armed", "exit", "trigger")
    assert verdict.refused_after_alert is False, "nothing has refused it -- nothing has judged it"
    assert verdict.alerted_but_unverified is True
    headline = verification.headline
    assert "NOT VERIFIED" in headline and "0 alerted" not in headline
    assert SYMBOL in headline and "could NOT be judged" in headline
    assert "NOT withdrawn" in headline
    assert refresh.NOT_VERIFIED_MARK in verification.render()


def test_M16_the_oracle_that_has_NOT_SPOKEN_is_not_the_oracle_REFUSING(
    scratch_world: Path, tmp_path: Path,
) -> None:
    """REVIEW_14 **M16**: correct alerts, loudly withdrawn.

    An absent bhavcopy row fails gate 1P with ``no-raw-daily-row`` -- *"the stored prices can be
    compared with nothing"* -- and every alerted symbol was then named in a **"treat them as
    withdrawn"** headline, while ``oracle_available`` and the NOT-VERIFIED branch that exist for
    exactly this case were dead code. Over five dry-run days that withdraws real, correct alerts
    and trains the trader to ignore the one line that must never be ignored.

    Driven over a real recording with a real battery, against a daily store that holds no row for
    the day -- which is exactly what a bhavcopy the exchange has not published yet looks like.
    """
    from acumen.signal_engine import SignalPipeline

    config = load_config(scratch_world, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    if not store.minutes(SYMBOL, DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    # A real recording of a real morning, written by the shipped screener.
    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec-m16")
    screener = ls.build_live_screener(
        DAY, (SYMBOL,), source=StoredDayBarSource(store), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        mode="replay", sinks=(sink,),
        data_dir=config.path("data_root"), cache_dir=config.path("cache_root"),
    )
    screener.run_day()
    assert sink.alerts, "the morning really alerted"

    silent_oracle = SignalPipeline(
        minute_store=store,
        daily_store=DailyStore.at(tmp_path / "no-bhavcopy-here"),
        master=screener.pipeline.master, row_size=config.row_size,
    )
    verification = refresh.verify_prior_recording(recording, silent_oracle, day=DAY)
    verdict = verification.verdicts[0]

    assert verdict.verified is False, "the oracle has not spoken for this day"
    assert refresh.NO_ORACLE_ROW in verdict.oracle_reason
    assert verdict.refused_after_alert is False, (
        "a silent oracle refuses nothing -- M16, unfixed, called this a withdrawal"
    )
    assert "treat them as withdrawn" not in verification.headline
    assert "NOT VERIFIED" in verification.headline

    # ...and a REAL refusal still reads as one, so the loud line has not been softened.
    real_oracle = SignalPipeline(
        minute_store=store,
        daily_store=DailyStore.at(config.path("data_root") / "daily_store"),
        master=screener.pipeline.master, row_size=config.row_size,
    )
    honest = refresh.verify_prior_recording(recording, real_oracle, day=DAY)
    assert honest.verdicts[0].verified is True
    assert refresh.oracle_spoke(
        real_oracle.gate_day(SYMBOL, DAY, tuple(recording.bars(SYMBOL, DAY)))
    ) is True


def _no_pipeline():
    """A pipeline object the M15 path must never reach -- the symbol has no bars to gate."""

    class _Refuses:
        def gate_day(self, *args, **kwargs):  # pragma: no cover -- ASSERTED BY NOT BEING CALLED
            raise AssertionError("a symbol with no candles must not be gated")

    return _Refuses()


# --- H5: the harness can judge the LIVE posture -------------------------------------------------


def test_H5_the_parity_harness_judges_a_LIVE_POSTURE_day(
    scratch_world: Path, tmp_path: Path,
) -> None:
    """REVIEW_14 **H5**: ``transitions_equal`` was structurally False in CONTEXT 4.7 posture.

    ``build_live_screener`` sets ``gates = {} if live else full_day_gates(...)`` -- correctly: a
    live morning has no oracle. ``parity.run_live`` then computed the live half's own whole-day
    ``StockDay`` only when a settled battery existed, so ``live_final`` stayed None and the trail
    comparison was False for every day the backtester has a signal. Measured on 8 oracle-passing
    live-posture days: judged 8, matched 0, mismatched 8, each with exactly one named mismatch --
    the trail line -- while the live half's own trail is byte-identical.

    It fails SAFE, which is why the review rates it HIGH; a harness that cannot judge the posture
    the tool actually runs in still judges nothing that matters, and chunk 15's acceptance test is
    decision-level.
    """
    config = load_config(scratch_world, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    if not store.minutes(SYMBOL, DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    screener = ls.build_live_screener(
        DAY, (SYMBOL,), source=StoredDayBarSource(store),
        recording=LiveRecording.at(tmp_path / "rec-h5"),
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        mode="live", sinks=(ls.CollectingAlertSink(),),
        data_dir=config.path("data_root"), cache_dir=config.path("cache_root"),
    )
    assert screener.gates == {}, "CONTEXT 4.7: a live morning computes no settled battery"

    result = parity.parity_for_screener(screener, SYMBOL, source="lake")

    assert result.judged, result.oracle_reason
    assert result.transitions_equal, "the trail comparison is real again, not structurally False"
    assert result.matched, result.mismatches


def _pipeline(config):
    from acumen import backtest as bt
    from acumen.signal_engine import SignalPipeline

    master, _path, _sha = bt.pinned_master(config.path("cache_root"), config.instrument_master)
    return SignalPipeline(
        minute_store=MinuteStore.at(config.path("data_root") / "minute_store"),
        daily_store=DailyStore.at(config.path("data_root") / "daily_store"),
        master=master, row_size=config.row_size,
    )


def _bias(config, day: date):
    from acumen.bias_engine import DailyBias

    return DailyBias(
        trade_date=day, bias="bullish", tradeable=True, rule="rule-1-breakout",
        detail="fixed for this probe",
        current_date=day - timedelta(days=1), previous_date=day - timedelta(days=2),
    )
