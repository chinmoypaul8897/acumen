"""CHUNK 14, PART A: the defects REVIEW_13 and REVIEW_13B left standing, each with its test.

One file, one test (or two) per carried finding, named after the finding so a later reader can
walk the review and the suite side by side:

* **Q1** (MAJOR) -- a frozen-but-answering feed delivered a WRONG exit alert with nothing on the
  alert to say so. The staleness marker is now on the PAYLOAD, B357's provisional-POC flag is a
  first-class alert state on every kind, and no alert carrying a price may leave without a
  freshness stamp.
* **M21** (MAJOR, carried from REVIEW_13) -- a ``qty == 0`` day was alerted as a trade. CONTEXT
  3.5: *"qty == 0 -> no trade, consumed + logged"*. Proved on the ledger's own two days.
* **M22** (MAJOR, carried) -- a day with no whole-day battery silently gated a GROWING PREFIX
  and refused 15 of 17 boundaries.
* **Q2** (MEDIUM) -- ``live_trading_calendar`` fell through a gap INSIDE the history.
* **Q3** (MAJOR) -- the shipped live path WROTE to ``data_root`` on ``--refresh
  --allow-network``.

Q4 (the tripwire's two string idioms) lives where the tripwire lives, in
``tests/test_live_safety.py``, with the four new evasion shapes in its corpus.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import calendar as cal
from acumen import live_dashboard as dash
from acumen import live_screener as ls
from acumen import signals as sig
from acumen.config import load_config
from acumen.daily_store import DailyStore
from acumen.live_recording import LiveRecording, RecordedAlert
from acumen.live_source import RecordingBarSource, StoredDayBarSource
from acumen.minute_store import MinuteStore
from acumen.signal_engine import SignalPipeline

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"

SYMBOL = "HDFCBANK"
LIVE_DAY = date(2026, 6, 10)
#: A real day where a five-minute-late window MOVES the POC (REVIEW_13B's own probe day).
BITE_DAY = date(2026, 6, 8)

#: The ledger's ONLY two ``qty == 0`` days, of 495,312 walked symbol-days, with the per-share
#: risk the chunk-9B run recorded for each. REVIEW_13B measured this population; this session
#: re-measured it from the same ledger and got the same two rows and the same two figures.
QTY_ZERO_DAYS: tuple[tuple[str, date, int], ...] = (
    ("BOSCHLTD", date(2021, 5, 20), 101_970),
    ("SHREECEM", date(2020, 3, 19), 117_330),
)


def _stores_or_skip() -> Path:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    for relpath in ("daily_store", "minute_store"):
        if not (data_root / relpath).is_dir():
            pytest.skip(f"local {relpath} is absent (the stores are gitignored)")
    return data_root


def _scratch_world(tmp_path: Path, day: date) -> Path:
    """A scratch ``cache_root`` holding the day's own master and the published holiday master.

    A COPY, never a link (CLAUDE.md data-store safety). Returns the cache directory.
    """
    config = load_config(include_env=False)
    cache = tmp_path / "cache"
    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        config.path("cache_root") / "instrument_master" / config.instrument_master,
        cache / "instrument_master" / ls.day_master_filename(day),
    )
    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=day
    )
    return cache


def _live(tmp_path: Path, source, *, day: date, label: str, symbol: str = SYMBOL):
    """The SHIPPED construction path in LIVE posture -- nothing hand-assembled."""
    config = load_config(include_env=False)
    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec" / f"{day.isoformat()}-{label}")
    screener = ls.build_live_screener(
        day, (symbol,),
        source=source,
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="live",
        data_dir=config.path("data_root"),
        cache_dir=_scratch_world(tmp_path, day),
        sinks=(sink,),
    )
    return screener, sink, recording


def _replay(tmp_path: Path, source, *, day: date, symbol: str, label: str = "replay"):
    """The SHIPPED construction path in REPLAY posture."""
    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / f"{symbol}-{day.isoformat()}-{label}")
    screener = ls.build_live_screener(
        day, (symbol,), source=source, recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(sink,),
    )
    return screener, sink, recording


# --- Q1: the alert vouches for its own price ----------------------------------------------------


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


def test_Q1_a_frozen_feeds_exit_alert_CARRIES_the_staleness_marker(tmp_path: Path) -> None:
    """REVIEW_13B **Q1**, closed: the alert says what the dashboard row said.

    The measured case is the review's own: HDFCBANK 2026-06-10, the feed freezes at 11:30 and
    keeps answering 200, so every sweep "completes" and no banner rises. The real day hit its
    target at 749.50; what the screener can see stops at 11:29, so at 15:15 it squares off on
    740.95. That alert is now impossible to mistake for a fresh one -- the marker is on the LINE
    and the numbers behind it are on the PAYLOAD, which is what chunk 14 forwards.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    screener, sink, _rec = _live(
        tmp_path,
        _FrozenFeed(StoredDayBarSource(store),
                    freeze_at=datetime.combine(LIVE_DAY, datetime.min.time())
                    .replace(hour=11, minute=30)),
        day=LIVE_DAY, label="frozen",
    )
    reports = screener.run_day()

    state = screener.states[SYMBOL]
    assert state.last_stamp == datetime.combine(LIVE_DAY, datetime.min.time()).replace(
        hour=11, minute=29
    ), "the screener really is looking at a prefix that stopped at 11:29"

    exits = [a for a in sink.alerts if a.kind in (ls.ALERT_EXIT, ls.ALERT_SQUARE_OFF)]
    assert exits, "the frozen prefix still produces an exit-side alert"
    alert = exits[-1]

    # 1. the LINE the trader reads
    line = ls.format_alert(alert)
    assert "STALE" in line and "cannot vouch for" in line
    assert line.index("STALE") > line.index("SQUARE-OFF"), (
        "the numbers first, then what qualifies them -- the marker must not be what he reads "
        "before the price"
    )
    assert line.index("STALE") < line.index(ls.LIVE_DISCLOSURE), (
        "and the thing that is true only today prints before the sentence that is true daily"
    )

    # 2. the PAYLOAD chunk 14 forwards
    assert alert.payload["stale"] is True
    assert alert.payload["data_behind_minutes"] == 226, (
        "15:15 minus 11:29 -- measured at the ALERT's own boundary, not at the dashboard's clock"
    )
    assert alert.payload["last_bar_stamp"] == "2026-06-10T11:29:00"
    assert ls.MARKER_STALE in alert.payload["alert_states"]

    # 3. and the row still says it too (B10's fix, from the SAME predicate now)
    text = dash.render_text(
        day=LIVE_DAY, now=reports[-1].boundary, grouped=screener.by_phase(),
        alerts=tuple(sink.alerts), banner=screener.banner, dry_run=True,
        disclosure=ls.LIVE_DISCLOSURE, verification=None,
    )
    row = [line for line in text.splitlines() if SYMBOL in line and "bars" in line]
    assert row and "STALE" in row[0]


def test_Q1_NO_delivered_alert_carries_a_price_the_screener_cannot_vouch_for(
    tmp_path: Path,
) -> None:
    """The chunk-14 rule, over a WHOLE frozen morning: every alert vouches for its price.

    This is the assertion the architect asked for, made against the delivery seam rather than
    against one alert: the sink collects everything the screener delivered, and
    :func:`acumen.live_screener.unvouched_price` -- the same predicate the Telegram sink runs
    before it sends -- must find nothing to refuse.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    screener, sink, _rec = _live(
        tmp_path,
        _FrozenFeed(StoredDayBarSource(store),
                    freeze_at=datetime.combine(LIVE_DAY, datetime.min.time())
                    .replace(hour=11, minute=30)),
        day=LIVE_DAY, label="vouched",
    )
    screener.run_day()
    assert sink.alerts, "the morning delivered something to check"
    refused = [ls.unvouched_price(alert) for alert in sink.alerts]
    assert not [reason for reason in refused if reason], (
        "an alert carrying a price left the screener without a freshness stamp:\n"
        + "\n".join(reason for reason in refused if reason)
    )
    # ...and the predicate is not vacuous: both failure shapes are caught.
    naked = RecordedAlert(kind=ls.ALERT_TRIGGER, symbol="ACME", at=datetime(2026, 6, 10, 11, 30),
                          payload={"entry_paise": 100})
    assert "no freshness stamp" in (ls.unvouched_price(naked) or "")
    unmarked = RecordedAlert(
        kind=ls.ALERT_EXIT, symbol="ACME", at=datetime(2026, 6, 10, 15, 15),
        payload={"exit_paise": 100, "stale": True, "data_behind_minutes": 226},
    )
    assert "no staleness marker" in (ls.unvouched_price(unmarked) or "")
    fresh = RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol="ACME", at=datetime(2026, 6, 10, 11, 30),
        payload={"entry_paise": 100, "stale": False, "data_behind_minutes": 1},
    )
    assert ls.unvouched_price(fresh) is None
    assert ls.unvouched_price(RecordedAlert(
        kind=ls.ALERT_FAILURE, symbol="ACME", at=datetime(2026, 6, 10, 11, 30),
        payload={"detail": "the screener is not answering"},
    )) is None, "a failure alert names no price, so there is no price to vouch for"


@dataclass
class _LateWindow:
    """The last five window minutes do not arrive until after the POC boundary."""

    inner: object
    day: date
    calls: int = 0

    def fetch(self, symbol, day, upto):
        self.calls += 1
        bars = self.inner.fetch(symbol, day, upto)
        if self.calls > 1:
            return bars
        cut = (datetime.combine(self.day, datetime.min.time()).replace(hour=11, minute=14)
               - timedelta(minutes=4))
        return tuple(bar for bar in bars if bar.stamp < cut)


def test_Q1_the_PROVISIONAL_POC_is_a_first_class_state_on_EVERY_alert(tmp_path: Path) -> None:
    """B357's flag, in the architect's own words: *"on every alert the symbol produces"*.

    It used to reach ARMED and TRIGGER only, so the EXIT alert of a provisional-POC day carried
    a stop and a target descended from that POC with nothing on it to say so -- and the exit is
    the alert the trader acts on last and keeps longest.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    # The golden day, five window minutes late: it still arms, triggers and exits, so the flag
    # has all three alert kinds to travel on -- REVIEW_13B's own bite day (2026-06-08) proves
    # the PIN moves the POC but produces no alert at all to carry it.
    screener, sink, _rec = _live(
        tmp_path, _LateWindow(StoredDayBarSource(store), LIVE_DAY),
        day=LIVE_DAY, label="late",
    )
    screener.run_day()
    assert screener.states[SYMBOL].poc_provisional
    assert screener.states[SYMBOL].poc_missing_minutes == 5
    assert [a.kind for a in sink.alerts] == [
        ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT
    ], "arming, the trade and the exit -- the exit is the one that used to carry nothing"
    for alert in sink.alerts:
        assert alert.payload.get("poc_note") == ls.POC_PROVISIONAL, alert.kind
        assert alert.payload.get("poc_missing_minutes") == 5, alert.kind
        assert ls.MARKER_POC_PROVISIONAL in alert.payload["alert_states"], alert.kind
        assert ls.POC_PROVISIONAL in ls.format_alert(alert), alert.kind


# --- M21: a qty == 0 day is no trade, consumed and logged ---------------------------------------


@pytest.mark.parametrize("symbol,day,per_share_risk", QTY_ZERO_DAYS)
def test_M21_a_qty_zero_day_is_NO_TRADE_consumed_and_logged(
    tmp_path: Path, symbol: str, day: date, per_share_risk: int
) -> None:
    """CONTEXT 3.5, on the ledger's own two days: *"qty == 0 -> no trade, consumed + logged"*.

    The live path used to deliver a TRIGGER with ``qty 0`` printed on it, which is a trade the
    strategy does not have: ``simulate._unsizable_record`` writes no fill, no cost and no PnL
    for exactly this shape and flags the row ``qty_zero_unsizable``. What must happen instead is
    all three of the spec's words -- NO trade alert, the stock-day CONSUMED so nothing later
    trades it, and the event LOGGED where a later reader can find it.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(symbol, day):
        pytest.skip(f"the local minute lake does not hold {symbol} {day}")

    screener, sink, recording = _replay(
        tmp_path, StoredDayBarSource(store), day=day, symbol=symbol, label="m21"
    )
    screener.run_day()
    state = screener.states[symbol]

    # 1. NO trade alert -- and the arming, which was real, is untouched.
    kinds = [alert.kind for alert in sink.alerts]
    assert ls.ALERT_TRIGGER not in kinds and ls.ALERT_EXIT not in kinds, (
        f"a qty-0 day alerted a trade: {kinds}"
    )
    assert kinds == [ls.ALERT_ARMED], kinds

    # 2. CONSUMED: refused for the rest of the day, in CONTEXT 3.5's own terms, with the four
    #    numbers readable in the detail even though there is no position.
    assert state.phase == ls.PHASE_REFUSED
    assert state.refusal == ls.REFUSAL_QTY_ZERO
    assert state.qty == 0 and state.entry_paise is None
    assert ls.rupees(per_share_risk) in state.detail
    assert "CONSUMED" in state.detail and "CONTEXT 3.5" in state.detail

    # 3. LOGGED, once, with the numbers.
    logged = [row for row in recording.events() if row["kind"] == "qty-zero-unsizable"]
    assert len(logged) == 1, f"logged {len(logged)} time(s), expected exactly once"
    assert logged[0]["per_share_risk_paise"] == per_share_risk
    assert logged[0]["symbol"] == symbol

    # 4. and the BACKTESTER agrees, which is the parity half of the same finding.
    from acumen import simulate as sim

    stock_day = screener.pipeline.stock_day(
        symbol, day, bias=screener.biases[symbol]
    )
    record = sim.simulate_day(
        stock_day.signal, stock_day.bars, symbol=symbol,
        risk_per_trade_paise=screener.risk_per_trade_paise,
        cost_paise=screener.cost_paise,
    )
    assert record.qty == 0 and record.exit_paise is None
    assert sim.FLAG_QTY_ZERO_UNSIZABLE in record.flags
    assert record.per_share_risk_paise == per_share_risk


# --- M22: a day with no whole-day battery is refused BY NAME ------------------------------------


def test_M22_a_symbol_day_with_NO_whole_day_battery_is_refused_by_name(tmp_path: Path) -> None:
    """REVIEW_13 **M22**: 15 of 17 boundaries refused, and gate 1 was not really the reason.

    ``gates={}`` is what a replay of a day the lake does not hold produced, and ``gates=None``
    reaches ``evaluate`` as *"compute it here"* -- which on a GROWING PREFIX folds a partial
    session against a whole-day bhavcopy and refuses by gate 1 at every boundary but the last.
    A parity harness run over such a day would have found both halves agreeing, for reasons
    neither of them stated. The screener now refuses in its own words, once.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    screener, sink, recording = _replay(
        tmp_path, StoredDayBarSource(store), day=LIVE_DAY, symbol=SYMBOL, label="m22"
    )
    assert screener.gates.get(SYMBOL) is not None, "the lake DOES hold this day"
    screener.gates = {}  # exactly what a lake-less day produced before this fix
    reports = screener.run_day()

    state = screener.states[SYMBOL]
    assert state.phase == ls.PHASE_REFUSED
    assert state.refusal == ls.REFUSAL_NO_BATTERY
    assert "gate 1" not in state.refusal, (
        "the refusal must not name a gate that was never run against a whole day"
    )
    assert not sink.alerts, "and a day nothing can gate produces no alert at all"
    logged = [row for row in recording.events() if row["kind"] == "battery-unavailable"]
    assert len(logged) == 1, "recorded once, on the boundary that first met it"
    assert len(reports) == 18, "every boundary still ran; none of them invented a verdict"


def test_M22_a_RECORDING_supplies_the_whole_day_battery_the_lake_does_not_hold(
    tmp_path: Path,
) -> None:
    """The other half: the battery a replay needs is measurable from the RECORDING's own bars.

    CONTEXT 4.7's next-pre-open duty already runs the FULL battery over a recording against the
    published bhavcopy (:func:`acumen.live_refresh.verify_prior_recording`); this is the same
    construction, one step earlier, so that a recording of a live morning can be replayed at all.
    Proved against an EMPTY minute lake -- the recording is the only source of the day -- and
    the verdict it produces is the one the lake produces, gate for gate.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")
    config = load_config(include_env=False)

    # A real recording, written by the shipped screener over the real day.
    source_screener, _sink, recording = _replay(
        tmp_path, StoredDayBarSource(store), day=LIVE_DAY, symbol=SYMBOL, label="origin"
    )
    source_screener.run_day()
    from_lake = source_screener.gates[SYMBOL]

    empty_lake = MinuteStore.at(tmp_path / "empty-lake")
    pipeline = SignalPipeline(
        minute_store=empty_lake,
        daily_store=DailyStore.at(data_root / "daily_store"),
        master=source_screener.pipeline.master,
        row_size=config.row_size,
    )
    assert not pipeline.minute_store.minutes(SYMBOL, LIVE_DAY), "the lake really is empty"
    assert ls.full_day_gates(pipeline, (SYMBOL,), LIVE_DAY) == {}, (
        "which is precisely the state that produced M22"
    )

    from_recording = ls.full_day_gates(
        pipeline, (SYMBOL,), LIVE_DAY, source=RecordingBarSource(recording)
    )
    assert SYMBOL in from_recording
    assert from_recording[SYMBOL].usable
    assert from_recording[SYMBOL] == from_lake, (
        "the recording holds the same session the lake does, so the battery is the same battery"
    )

    # ...and a source that REFUSES to be used -- which is exactly what `--preflight-only` runs
    # on -- leaves the symbol without a battery rather than turning a preflight into a crash.
    from acumen.run_screener import PreflightOnlySource

    assert ls.full_day_gates(
        pipeline, (SYMBOL,), LIVE_DAY, source=PreflightOnlySource()
    ) == {}


# --- Q2: a gap INSIDE the history is refused ----------------------------------------------------


class _GappyStore:
    """The real daily store with ONE date's outcome removed -- a hole INSIDE the history."""

    def __init__(self, inner, hole: date) -> None:
        self.inner = inner
        self.hole = hole

    def coverage(self, from_date, to_date):
        frame = self.inner.coverage(from_date, to_date)
        return frame[frame["trade_date"] != self.hole]

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_Q2_the_live_calendar_REFUSES_a_gap_inside_the_history(tmp_path: Path) -> None:
    """REVIEW_13B **Q2**, closed -- and decision B363's promise is now implemented.

    ``settled_through`` still walks forward only while the ledger is terminal, which is right;
    what was missing is that everything after the first hole was handed silently to the
    published holiday master. The store's own ledger tells the two cases apart: evidence AFTER
    the hole means an incomplete backfill (refuse, Q-3 safeguard 1), no evidence after it means
    the store has simply reached the end of what it has attempted, which is every ordinary live
    morning because Q-19's guard stops the top-up strictly before today.
    """
    data_root = _stores_or_skip()
    store = DailyStore.at(data_root / "daily_store")
    cache = _scratch_world(tmp_path, LIVE_DAY)
    published = cal.fetch_calendar(cache_dir=cache, today=LIVE_DAY, allow_network=False)
    first, hole = date(2026, 1, 2), date(2026, 1, 5)
    gappy = _GappyStore(store, hole)

    with pytest.raises(cal.CalendarError) as derived_refusal:
        cal.TradingCalendar.from_daily_store_range(gappy, first, date(2026, 6, 9))
    assert "never attempted" in str(derived_refusal.value)

    with pytest.raises(cal.CalendarError) as live_refusal:
        cal.live_trading_calendar(published, store=gappy, first_day=first, day=LIVE_DAY)
    message = str(live_refusal.value)
    assert "GAP inside its own history" in message
    assert hole.isoformat() in message, "it names the date the ledger has nothing for"
    assert "section 6" in message, "and why it matters: the bias pair would drift"

    # ...and the WHOLE store still builds, with the Q-5 weekend-session disclosure intact.
    whole = cal.live_trading_calendar(
        published, store=store, first_day=first, day=LIVE_DAY
    )
    assert whole.trading_days and whole.excluded_weekend_sessions

    # An ordinary live morning -- a store that stops before today, with no evidence after the
    # stop -- is NOT a gap and must still start. This is the case Q-19's guard creates daily.
    today = date(2026, 8, 14)
    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    for stamp in (LIVE_DAY, today):
        built = cal.live_trading_calendar(
            cal.TradingCalendar.from_payload(payload), store=store,
            first_day=stamp - timedelta(days=210), day=stamp,
        )
        assert built.trading_days, stamp


# --- Q3: the corporate-action refresh cannot write inside the stores ----------------------------


def test_Q3_the_fence_decides_by_PATH_and_by_named_sanction(tmp_path: Path) -> None:
    """REVIEW_13B **Q3**: the whole decision table, on paths that touch no store.

    CLAUDE.md's rule is the one being executed -- *"sessions treat the stores as READ-ONLY unless
    the architect's prompt explicitly sanctions a named write"* -- so the fence turns on WHERE
    the cache is and whether a sanction was named, and on nothing else.
    """
    data_root, cache_root = tmp_path / "data", tmp_path / "cache"
    inside = data_root / "nse"
    outside = tmp_path / "scratch" / "nse"

    resolved, network, why = bt.fence_ca_cache(
        cache_dir=inside, allow_network=False, data_root=data_root, cache_root=cache_root
    )
    assert (resolved, network) == (inside, False) and "read at any age" in why

    resolved, network, why = bt.fence_ca_cache(
        cache_dir=inside, allow_network=True, data_root=data_root, cache_root=cache_root
    )
    assert (resolved, network) == (inside, False) and why == bt.CA_REFRESH_FENCED

    resolved, network, why = bt.fence_ca_cache(
        cache_dir=cache_root / "nse", allow_network=True,
        data_root=data_root, cache_root=cache_root,
    )
    assert network is False, "the OTHER store is fenced too, not only data_root"

    resolved, network, why = bt.fence_ca_cache(
        cache_dir=outside, allow_network=True, data_root=data_root, cache_root=cache_root
    )
    assert (resolved, network) == (outside, True) and "outside the stores" in why

    resolved, network, why = bt.fence_ca_cache(
        cache_dir=inside, allow_network=True, sanctioned_write="architect 14-Aug: refresh CA",
        data_root=data_root, cache_root=cache_root,
    )
    assert network is True and why.startswith("SANCTIONED STORE WRITE:")
    assert "architect 14-Aug" in why, "the sanction is echoed, so the record names who allowed it"


def test_Q3_a_LIVE_REFRESH_writes_ZERO_bytes_under_the_stores(tmp_path: Path) -> None:
    """The tripwire the finding asks for, against the real store, read-only.

    ``build_runner(..., allow_network=True)`` is what ``--mode live --refresh --allow-network``
    reaches, and it is what wrote 22 files and 46,262 bytes into ``data_root`` during REVIEW_13B.
    It is driven here for real, over the real corporate-action cache, with a fingerprint taken
    before and after -- and with the HTTP layer replaced by a fetcher that raises, so that a
    fence which failed could not write even by accident. Both halves are asserted: nothing was
    fetched, and not one byte under the stores moved.
    """
    data_root = _stores_or_skip()
    config = load_config(include_env=False)
    ca_cache = data_root / bt.CA_CACHE_SUBDIR
    if not ca_cache.is_dir():
        pytest.skip("this machine has no corporate-action cache to protect")

    def fingerprint(root: Path) -> tuple[int, int, tuple]:
        files = sorted(p for p in root.rglob("*") if p.is_file())
        rows = tuple(
            (p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in files
        )
        return len(files), sum(row[1] for row in rows), rows

    import acumen.nse_http as nse_http

    attempted: list[str] = []

    def refuse(url: str, *args, **kwargs):  # pragma: no cover -- ASSERTED BY NOT BEING CALLED
        attempted.append(url)
        raise AssertionError(f"the fence let a network fetch through to {url}")

    before = fingerprint(ca_cache)
    original = nse_http.fetch_json
    nse_http.fetch_json = refuse
    try:
        runner, _master, _ca = bt.build_runner(
            (SYMBOL,), LIVE_DAY, LIVE_DAY, seed_from=LIVE_DAY,
            label="chunk14-fence-tripwire", allow_network=True,
        )
    finally:
        nse_http.fetch_json = original
    after = fingerprint(ca_cache)

    assert not attempted, f"a networked fetch was attempted: {attempted}"
    assert before == after, "the corporate-action cache under data_root MOVED"
    assert runner.spec.factor_digest, "and the run still has its factor tables, from the cache"

    # The same run, pointed at a scratch cache OUTSIDE the stores, is NOT fenced -- so the fence
    # is a fence and not a blanket refusal to ever refresh.
    _resolved, network, _why = bt.fence_ca_cache(
        cache_dir=tmp_path / "outside" / "nse", allow_network=True,
        data_root=data_root, cache_root=config.path("cache_root"),
    )
    assert network is True


def test_Q3_build_runner_passes_the_CA_cache_EXPLICITLY_so_config_governs() -> None:
    """The source-level half, which is where REVIEW_13B pinned the defect.

    The pin was an AST assertion that ``build_factor_tables`` is called with NO ``cache_dir``.
    It is called with one now, resolved from the caller's own ``data_dir`` rather than from
    whatever ``config.yaml`` the process happened to load, and the fence stands between the CLI
    flag and the fetch.
    """
    import ast

    tree = ast.parse(Path(bt.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "build_factor_tables"
    ]
    assert calls, "build_runner still builds the factor tables"
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        assert "cache_dir" in keywords, "--config governs where the CA cache is read from"
        assert "sanctioned_write" in keywords, "and a store write needs a named sanction"

    fenced = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "fence_ca_cache"
    ]
    assert len(fenced) >= 2, (
        "the fence is applied at the call site AND inside build_factor_tables, so a caller "
        "written next year that forgets is fenced anyway"
    )
