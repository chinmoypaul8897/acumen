"""CONTEXT 4.7's NEXT PRE-OPEN: the full battery over yesterday's recording, and the loud case.

The architect's ruling of 08-Aug-2026, verbatim: *"the NEXT pre-open runs the FULL battery on
yesterday's recording against the published bhavcopy and reports the verdict, loudly naming any
live-alerted day the oracle refuses."*

That sentence is the closing half of the whole live design. A live morning accepts a measured
residual (0.5229% of settled symbol-days failed gate 1 alone over the ten-year ledger); what
makes accepting it honest rather than convenient is that the loop CLOSES the next morning, on
the day's own recorded bytes, against the exchange's own published record.

So the case that must never be quiet is driven by a test here rather than waited for: a day this
tool ALERTED on that the bhavcopy then refuses. It is the case that will be rare, that nobody
will have seen, and that carries real money -- exactly the combination that goes unnoticed for
years unless a test holds it.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen.calendar import TradingCalendar
from acumen.daily_store import DailyStore
from acumen.live_recording import LiveRecording
from acumen.minute_store import MinuteStore
from acumen.signal_engine import SignalPipeline

from test_backtest import (
    ROW_SIZE,
    SYMBOL,
    TICK_PAISE,
    TRADE_DAY,
    build_stores,
    lead_rows,
    row_for_minutes,
    synthetic_minutes,
    daily_row,
    R,
    SEED_A,
    SEED_B,
)
from test_live_screener import make_screener

MASTER_NAME = "OpenAPIScripMaster_2026-07-17.json"


def world_with(tmp_path: Path, *, volume_override: int | None = None):
    """The chunk-9A synthetic world, optionally with a bhavcopy volume the fold cannot match."""
    minutes = synthetic_minutes(TRADE_DAY)
    rows = dict(lead_rows())
    override = {} if volume_override is None else {"volume": volume_override}
    rows.update({
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
        TRADE_DAY: row_for_minutes(TRADE_DAY, minutes, **override),
    })
    return build_stores(tmp_path, minute_days={TRADE_DAY: minutes}, daily_rows=rows)


def a_recorded_live_morning(tmp_path: Path) -> LiveRecording:
    """Run the live screener over the synthetic day and hand back what it recorded."""
    screener, _sink, recording = make_screener(tmp_path, live=True)
    screener.run_day()
    return recording


def pipeline_over(stores) -> SignalPipeline:
    minute_store, daily_store, master, _cal = stores
    return SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )


# --- the ordinary morning: the oracle agrees -----------------------------------------------------


def test_the_next_pre_open_re_gates_the_recording_and_reports_BOTH_verdicts(
    tmp_path: Path,
) -> None:
    """Two batteries over ONE set of bytes -- not one battery and a memory of the other.

    The live column is recomputed from the recording rather than read out of yesterday's state
    file, on purpose: a verification that trusted the morning's own summary of itself could not
    detect the one thing worth detecting, which is a morning whose battery was wrong.
    """
    recording = a_recorded_live_morning(tmp_path / "day")
    verification = refresh.verify_prior_recording(
        recording, pipeline_over(world_with(tmp_path / "stores")), day=TRADE_DAY
    )

    assert [v.symbol for v in verification.verdicts] == [SYMBOL]
    verdict = verification.verdicts[0]
    assert verdict.live_passed and verdict.oracle_passed
    assert verdict.alerted == ("armed", "exit", "trigger"), "the morning really did alert"
    assert not verdict.refused_after_alert
    assert verification.refused_after_alert == ()
    assert "verified against the published bhavcopy" in verification.headline
    assert "1/1 symbol-day(s) pass the FULL battery" in verification.headline
    assert "0 alerted-then-refused" in verification.headline


def test_the_verdict_is_written_INTO_the_day_it_judges(tmp_path: Path) -> None:
    """The verdict belongs beside the day, not only in the log of the session that computed it.

    A recording is what chunk 14's parity harness and any later audit read; a day whose morning
    could not verify itself and whose verification lives somewhere else is a day that reads as
    unverified forever.
    """
    recording = a_recorded_live_morning(tmp_path / "day")
    verification = refresh.verify_prior_recording(
        recording, pipeline_over(world_with(tmp_path / "stores")), day=TRADE_DAY
    )
    recording.write_verification(verification.as_dict())

    stored = recording.read_verification()
    assert stored["trade_date"] == TRADE_DAY.isoformat()
    assert stored["refused_after_alert"] == []
    assert stored["verdicts"][0]["symbol"] == SYMBOL
    assert stored["headline"] == verification.headline
    assert recording.inventory()["has_verification"] is True


# --- THE LOUD CASE ------------------------------------------------------------------------------


def test_a_LIVE_ALERTED_day_the_ORACLE_REFUSES_is_named_LOUDLY(tmp_path: Path) -> None:
    """The case CONTEXT 4.7 exists to make impossible to miss, driven rather than awaited.

    The bhavcopy arrives in the evening carrying a volume the morning's fold cannot reconcile.
    The morning's own oracle-free battery was right about everything it could see -- the candles
    were valid, nothing was duplicated, nothing was impossible -- and it still alerted on a day
    the exchange's own record does not accept. That is the disclosed, bounded difference the
    ruling names, and this is the sentence it must produce.
    """
    recording = a_recorded_live_morning(tmp_path / "day")
    stores = world_with(tmp_path / "stores", volume_override=10_000_000)
    verification = refresh.verify_prior_recording(
        recording, pipeline_over(stores), day=TRADE_DAY
    )

    verdict = verification.verdicts[0]
    assert verdict.live_passed, "the live battery was right about everything it could see"
    assert not verdict.oracle_passed, "and the exchange's record refuses the day anyway"
    assert verdict.alerted, "and the morning had already alerted on it"
    assert verdict.refused_after_alert

    headline = verification.headline
    assert "THE EXCHANGE'S RECORD REFUSES" in headline
    assert SYMBOL in headline
    assert "treat them as withdrawn" in headline
    assert [v.symbol for v in verification.refused_after_alert] == [SYMBOL]

    rendered = verification.render()
    assert "REFUSED-AFTER-ALERT" in rendered
    assert "gap" in rendered, "the gate's OWN reason travels with the verdict, not a paraphrase"


def test_a_refused_day_NOBODY_ALERTED_ON_is_reported_but_not_shouted(tmp_path: Path) -> None:
    """The discrimination that keeps the loud case loud.

    A day the oracle refuses and the tool never alerted on is ordinary disclosed residual -- it
    cost the trader nothing and it belongs in the table, not in a banner. If everything shouted,
    the one that matters would not.
    """
    screener, _sink, recording = make_screener(tmp_path / "day", live=True)
    # sweep only the collecting boundary: bars are recorded, nothing is ever armed or triggered
    screener.sweep(screener.clock.now().replace(hour=11, minute=15))
    screener.alerted.clear()
    (recording.root / "alerts.jsonl").write_text("", encoding="utf-8")

    stores = world_with(tmp_path / "stores", volume_override=10_000_000)
    verification = refresh.verify_prior_recording(
        recording, pipeline_over(stores), day=TRADE_DAY
    )
    verdict = verification.verdicts[0]
    assert not verdict.oracle_passed and verdict.alerted == ()
    assert not verdict.refused_after_alert
    assert verification.refused_after_alert == ()
    assert "THE EXCHANGE'S RECORD REFUSES" not in verification.headline
    assert "0/1 symbol-day(s) pass the FULL battery" in verification.headline


def test_the_REFRESH_REPORT_shouts_it_too(tmp_path: Path) -> None:
    """The operator reads the pre-open report and often nothing else. It must carry the case.

    ``RefreshReport.render`` prints READY or NOT READY and then stops -- so the loud line is
    appended AFTER the verdict, where a reader who stops at "READY" still sees it.
    """
    recording = a_recorded_live_morning(tmp_path / "day")
    stores = world_with(tmp_path / "stores", volume_override=10_000_000)
    verification = refresh.verify_prior_recording(
        recording, pipeline_over(stores), day=TRADE_DAY
    )
    report = refresh.RefreshReport(
        day=date(2026, 7, 20),
        steps=(refresh.RefreshStep(name="calendar (published NSE)", ok=True, detail="fine"),),
        verifications=(verification,),
    )
    text = report.render()
    assert "READY" in text
    assert "!! " in text and "THE EXCHANGE'S RECORD REFUSES" in text
    assert text.index("READY") < text.index("THE EXCHANGE'S RECORD REFUSES"), (
        "the loud line is the LAST thing on the page, not buried above the verdict"
    )


# --- finding yesterday at all --------------------------------------------------------------------


def write_master(cache_dir: Path, name: str = MASTER_NAME) -> Path:
    path = cache_dir / "instrument_master" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{
            "exch_seg": "NSE", "symbol": f"{SYMBOL}-EQ", "token": "90000",
            "tick_size": f"{TICK_PAISE}.000000", "name": SYMBOL, "lotsize": "1",
        }]),
        encoding="utf-8",
    )
    return path


def test_the_step_finds_the_LIVE_recording_and_re_gates_it_under_ITS_OWN_master(
    tmp_path: Path,
) -> None:
    """The whole step, end to end -- and the Q-29 half of it.

    A day is re-judged under the ticks it RAN on, not under whatever the config pin has become:
    the recording names its master, this step loads that one, and a master it cannot load is a
    FAILED step rather than a silent substitution.
    """
    stores = world_with(tmp_path / "stores")
    recording_root = tmp_path / "live"
    recording = LiveRecording.at(recording_root / TRADE_DAY.isoformat())
    source = a_recorded_live_morning(tmp_path / "day")
    import shutil

    shutil.copytree(source.root, recording.root)
    manifest = recording.read_manifest()
    manifest.update({"mode": "live", "master_file": MASTER_NAME, "row_size": ROW_SIZE})
    recording.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_master(tmp_path / "cache")

    # The PUBLISHED calendar, which is what a live morning uses (the C5 duty): a store-derived
    # one refuses to answer for a day the store has never ingested, and "today" never has been.
    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    verifications, step = refresh.verify_prior_recordings(
        today=date(2026, 7, 20),  # the Monday after TRADE_DAY (a Friday)
        calendar=calendar,
        data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache",
        recording_root=recording_root,
    )
    assert step.ok and step.figures["verified"] is True
    assert len(verifications) == 1
    verification = verifications[0]
    assert verification.day == TRADE_DAY
    assert [v.symbol for v in verification.verdicts] == [SYMBOL]
    assert step.figures["refused_after_alert"] == []
    assert recording.read_verification()["trade_date"] == TRADE_DAY.isoformat(), (
        "the verdict was written back into the day it judges"
    )


def test_a_REPLAY_recording_is_NOT_verified_because_its_day_already_had_a_bhavcopy(
    tmp_path: Path,
) -> None:
    """Absence is not failure, and it says which absence it is.

    A replay's day was settled when it ran -- verifying it would re-derive the verdict it already
    used. The step reports that in one line and stays green, so a first live morning (or a
    Monday after a quiet week) does not read as a broken pre-open.
    """
    stores = world_with(tmp_path / "stores")
    recording_root = tmp_path / "live"
    recording = LiveRecording.at(recording_root / TRADE_DAY.isoformat())
    source = a_recorded_live_morning(tmp_path / "day")
    import shutil

    shutil.copytree(source.root, recording.root)
    manifest = recording.read_manifest()
    manifest["mode"] = "replay"
    recording.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # The PUBLISHED calendar, which is what a live morning uses (the C5 duty): a store-derived
    # one refuses to answer for a day the store has never ingested, and "today" never has been.
    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    verifications, step = refresh.verify_prior_recordings(
        today=date(2026, 7, 20), calendar=calendar, data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache", recording_root=recording_root,
    )
    assert verifications == ()
    assert step.ok and step.figures["verified"] is False
    assert "nothing unverified" in step.detail and "needs no verification" in step.detail


def test_a_recording_whose_master_is_GONE_is_a_FAILED_step_not_a_substitution(
    tmp_path: Path,
) -> None:
    """Q-29's other edge: a day cannot be re-judged under ticks it never ran on.

    Substituting the config pin here would produce a verdict that looks exactly like a real one
    and could differ on any of the symbols Q-20 measured moving between dumps.
    """
    world_with(tmp_path / "stores")
    recording_root = tmp_path / "live"
    recording = LiveRecording.at(recording_root / TRADE_DAY.isoformat())
    source = a_recorded_live_morning(tmp_path / "day")
    import shutil

    shutil.copytree(source.root, recording.root)
    manifest = recording.read_manifest()
    manifest.update({"mode": "live", "master_file": "OpenAPIScripMaster_1999-01-01.json"})
    recording.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # The PUBLISHED calendar, which is what a live morning uses (the C5 duty): a store-derived
    # one refuses to answer for a day the store has never ingested, and "today" never has been.
    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    verifications, step = refresh.verify_prior_recordings(
        today=date(2026, 7, 20), calendar=calendar, data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache", recording_root=recording_root,
    )
    assert verifications == ()
    assert not step.ok, (
        "the recording that cannot be judged IS the prior trading day's, which is the one "
        "CONTEXT 4.7 names -- so the morning stops (REVIEW_14 M13's other edge)"
    )
    assert "OpenAPIScripMaster_1999-01-01.json" in step.detail
    assert "re-judged under the ticks it ran on" in step.detail
    assert "NOT JUDGED and still queued" in step.detail, (
        "and it stays on the queue rather than vanishing from it"
    )
    assert not recording.read_verification(), "nothing was written for a day nobody judged"
