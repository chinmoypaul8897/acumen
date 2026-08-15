"""REVIEW_14B reviewer probes -- the chunk-14 FIX-2 RE-REVIEW's own tests, kept in the repo.

Written by the RE-REVIEW session, not by a build or fix session. Each one pins a finding or a
verified property from ``docs/reviews/REVIEW_14B.md`` at the place it lives.

**A defect pin asserts the DEFECT** -- the convention REVIEW_13B set and REVIEW_14 followed, and
the reason five of REVIEW_14's pins could be flipped and counted. This file carried exactly one:
``test_DEFECT_R1_*``, which pinned the residual the re-review found by widening M19's own
question. **Chunk 15 flipped it** -- it is now ``test_FLIPPED_R1_*`` and asserts the property
instead of the defect. Every other probe here pins something CORRECT and must never flip.

Store-free by construction: nothing here reads ``data_root`` or ``cache_root``, so these run on a
bare clone. The measurements that DO need the stores are evidence scripts instead, committed
under ``docs/evidence/review14b_*.py`` with their outputs beside them (REVIEW_7 C3).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta
from pathlib import Path

from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import run_screener
from acumen import telegram_sink as tg
from acumen.daily_store import DailyStore
from acumen.live_recording import RecordedAlert

REPO = Path(__file__).resolve().parents[1]


# --- R1: the residual -- how far M19's isolation actually reaches --------------------------------


def test_FLIPPED_R1_the_poll_guard_covers_the_WHOLE_per_symbol_body() -> None:
    """REVIEW_14B **R1**, closed by chunk 15 -- the probe this file was written to flip.

    What it pinned, as the defect: ``_poll`` wrapped ONLY ``self.source.fetch(...)``, and the
    four statements after it in the same method stood outside every guard in the module, so a
    bar that survived the fetch and died in that block ended the sweep and the morning:

    * a tz-AWARE stamp raises ``TypeError`` in ``merge_bars``;
    * ``close_paise = None`` or ``volume = None`` raises ``TypeError`` in ``record_bars``.

    The architect's 15-Aug-2026 note assigns the completion to chunk 15 and calls the narrower
    remedy an under-prescription rather than a regression. This is the SOURCE-level half of the
    flip -- every one of the four statements is now inside the ``try``, and the ``except`` tells
    a feed that did not answer apart from a reply that could not be taken in. The BEHAVIOURAL
    half, all seven malformed shapes driven through ``run_day``, is in
    ``tests/test_chunk15_carried_defects.py``.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(ls.LiveScreener._poll)))
    guards = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
    assert len(guards) == 1, "one guard, covering the whole per-symbol body"
    guarded = "\n".join(ast.unparse(stmt) for stmt in guards[0].body)
    for statement in (
        "self.source.fetch",
        "merge_bars",
        "duplicate_stamps",
        "record_bars",
        "record_fetch",
    ):
        assert statement in guarded, (
            f"{statement} is outside the per-symbol guard again -- R1, reopened"
        )
    # ...and the guard tells the two failures apart, because they need different handling.
    source = inspect.getsource(ls.LiveScreener._poll)
    assert "if answered:" in source and "self._intake_failed(" in source
    assert "return POLL_UNREADABLE" in source

    # The evaluation site is still guarded, which is what REVIEW_14's own remedy bought.
    swept = inspect.getsource(ls.LiveScreener.sweep)
    assert "alerts.extend(self._evaluate(symbol, boundary))" in swept
    assert "self._evaluation_failed(symbol, boundary, exc)" in swept


# --- H1: the three acts, in code and in every place that claims them ----------------------------


def test_the_telegram_gate_is_MODE_and_telegram_and_live_alerts() -> None:
    """REVIEW_14 H1, closed -- the truth table, plus the case nobody wrote down."""
    cases = {
        ("live", True, True): True,
        ("live", True, False): False,
        ("live", False, True): False,
        ("replay", True, True): False,
        ("replay", True, False): False,
        ("replay", False, False): False,
    }
    for (mode, telegram, live_alerts), expected in cases.items():
        argv = ["--mode", mode, "--day", "2026-06-10"]
        argv += ["--telegram"] if telegram else []
        argv += ["--live-alerts"] if live_alerts else []
        args = run_screener.parse_args(argv)
        assert run_screener.telegram_is_live(args) is expected, (mode, telegram, live_alerts)


def test_every_place_that_claims_THREE_ACTS_names_the_same_three() -> None:
    """The prose half of H1, as a census this review can be held to.

    REVIEW_14 counted five places making a three-act claim the code did not keep. H1 was closed
    by adding the missing act rather than by softening the prose, so all five must now name the
    same three flags -- and none of them may still say "two".
    """
    places = {
        "src/acumen/telegram_sink.py": None,
        "src/acumen/run_screener.py": None,
        "docs/morning_runbook.md": None,
        "tests/test_telegram_sink.py": None,
        "PROGRESS.md": "**B393**",
    }
    for relpath, anchor in places.items():
        text = (REPO / relpath).read_text(encoding="utf-8", errors="replace")
        if anchor is not None:
            lines = text.splitlines()
            start = next(i for i, line in enumerate(lines) if anchor in line)
            text = "\n".join(lines[start:start + 2])   # the decision, and its correction
        assert "deliberate act" in text.lower() and "three" in text.lower(), relpath
        for flag in ("--mode live", "--telegram", "--live-alerts"):
            assert flag in text, f"{relpath} does not name {flag}"
        assert "Two separate deliberate acts" not in text, relpath


def test_a_message_that_is_not_a_live_mornings_own_says_so_on_the_phone() -> None:
    """REVIEW_14 H1's second half: the markers, and the date that was never there."""
    def alert(**payload) -> RecordedAlert:
        body = {"side": "long", "entry_paise": 74095, "stop_paise": 73810,
                "target_paise": 74950, "qty": 350, "poc_paise": 73980, "bias": "bullish",
                "stale": False, "data_behind_minutes": 0}
        body.update(payload)
        return RecordedAlert(kind=ls.ALERT_TRIGGER, symbol="SHREECEM",
                             at=datetime(2020, 3, 19, 11, 30), payload=body)

    replayed = tg.message_for(alert(dry_run=True, mode="replay"))
    assert replayed.splitlines()[0].startswith("[2020-03-19 11:30]"), replayed
    assert tg.DRY_RUN_MARKER in replayed and tg.REPLAY_MARKER in replayed

    live = tg.message_for(alert(dry_run=False, mode="live", disclosure=ls.LIVE_DISCLOSURE))
    assert tg.DRY_RUN_MARKER not in live and tg.REPLAY_MARKER not in live
    assert ls.LIVE_DISCLOSURE in live, "and a live alert still carries CONTEXT 4.7's line"
    assert "2020-03-19" in live, "the date travels on every posture"


# --- H4 / Q1: the vouch ---------------------------------------------------------------------------


def test_the_vouch_catches_a_stamp_that_contradicts_itself_and_lets_an_honest_one_through() -> None:
    """REVIEW_14 H4, closed -- and the boundary the fix must NOT over-reach."""
    def alert(**payload) -> RecordedAlert:
        return RecordedAlert(kind=ls.ALERT_FAILURE, symbol="BOSCHLTD",
                             at=datetime(2026, 6, 10, 15, 0),
                             payload={"entry_paise": 1_556_990, **payload})

    lying = alert(stale=False, data_behind_minutes=211)
    refusal = ls.unvouched_price(lying)
    assert refusal is not None and "contradicts itself" in refusal and "211" in refusal

    marked = alert(stale=True, data_behind_minutes=211,
                   alert_states=[ls.MARKER_STALE], stale_note=ls.stale_note(211))
    assert ls.unvouched_price(marked) is None, "a marked stale price still travels"

    at_the_clamp = alert(stale=False, data_behind_minutes=ls.STALE_AFTER_MINUTES)
    assert ls.unvouched_price(at_the_clamp) is None, "exactly at the clamp is not a lie"

    unstamped = alert()
    assert ls.unvouched_price(unstamped) is not None, "the original Q1 shape still fails"


def test_data_age_is_a_MEASUREMENT_for_every_phase_including_refused() -> None:
    """REVIEW_14 H4: the ``PHASE_REFUSED`` short-circuit to ``(False, 0)`` is gone."""
    frozen = ls.SymbolState(
        symbol="BOSCHLTD", phase=ls.PHASE_REFUSED, refusal="gate 2 (integrity)",
        entry_paise=1_556_990, qty=1, minute_count=120,
        last_stamp=datetime(2026, 6, 10, 11, 29),
    )
    assert ls.data_age(frozen, datetime(2026, 6, 10, 15, 0)) == (True, 211)
    for phase in (ls.PHASE_WAITING, ls.PHASE_ARMED, ls.PHASE_TRIGGERED, ls.PHASE_EXITED):
        moved = ls.SymbolState(
            symbol="BOSCHLTD", phase=phase, minute_count=120,
            last_stamp=datetime(2026, 6, 10, 11, 29),
        )
        assert ls.data_age(moved, datetime(2026, 6, 10, 15, 0)) == (True, 211), phase


# --- H3: the ladder -------------------------------------------------------------------------------


def test_a_qty_zero_day_stands_exactly_where_an_ARMED_day_stands() -> None:
    """REVIEW_14 H3 / decision B413, at the predicate rather than through a whole morning.

    The ladder measures how far a POSITION got. On an unsizable cross nothing was bought, so the
    day is consumed and terminal but is not further along than a day still waiting for one --
    which places ARMED -> consumed forward (CONTEXT 3.5) and TRIGGERED -> consumed backward.

    The state built by ``_consumed_unsizable`` deliberately carries NO ``entry_paise``: the four
    numbers stay in the detail line and out of the fields the alert machinery reads as "there is
    a position here". That is what lets the new branch be reached at all rather than
    short-circuited by the ``entry_paise`` test above it, so it is asserted here.
    """
    consumed = ls.SymbolState(
        symbol="BOSCHLTD", phase=ls.PHASE_REFUSED, refusal=ls.REFUSAL_QTY_ZERO, qty=0,
    )
    assert consumed.entry_paise is None and consumed.exit_kind is None

    armed = ls.SymbolState(symbol="BOSCHLTD", phase=ls.PHASE_ARMED)
    waiting = ls.SymbolState(symbol="BOSCHLTD", phase=ls.PHASE_WAITING)
    triggered = ls.SymbolState(symbol="BOSCHLTD", phase=ls.PHASE_TRIGGERED, entry_paise=1_556_990)

    assert ls._reached_rank(consumed) == ls._reached_rank(armed)
    assert ls._reached_rank(consumed) > ls._reached_rank(waiting)
    assert ls._reached_rank(consumed) < ls._reached_rank(triggered), (
        "TRIGGERED -> consumed is the regression H3 found, and it must stay a regression"
    )
    assert ls.PHASE_RANK[ls.PHASE_ARMED] < ls.PHASE_RANK[ls.PHASE_TRIGGERED], (
        "PHASE_RANK's own published values are unchanged"
    )


# --- B408: a pre-open that cannot read its calendar still reports ---------------------------------


def test_a_calendar_that_cannot_be_read_leaves_a_REPORT_not_a_traceback(tmp_path: Path) -> None:
    """REVIEW_14B PART 2.2 / decision B408, driven through ``morning_refresh`` on tmp paths.

    Every step that CAN run still runs; the two that need a calendar say NOT RUN by name, because
    a step silently absent from a report reads as a step that passed -- which is M15's shape.
    """
    calendar, universe, report = refresh.morning_refresh(
        today=date(2026, 8, 7), store=DailyStore.at(tmp_path / "daily_store"),
        cache_dir=tmp_path / "no-cache-here", allow_network=False, symbols=("AAA",),
        daily_runner=lambda argv: 0, recording_root=tmp_path / "rec",
    )
    assert calendar is None and not report.ok, (
        "the widened return type is only ever None on a report the caller must refuse"
    )
    assert len(report.steps) == 6, "every step reported, none silently dropped"
    steps = {step.name: step for step in report.steps}
    for name in ("daily store (bhavcopy top-up)", refresh.VERIFY_STEP):
        assert steps[name].detail.startswith("NOT RUN:") and not steps[name].ok, name
    assert universe == ("AAA",)


# --- M15 / M16: silence, refusal, and the difference ---------------------------------------------


def _verdict(**kwargs) -> refresh.SymbolVerdict:
    body = dict(
        symbol="HDFCBANK", live_passed=True, live_reason="ok",
        oracle_passed=True, oracle_reason="the FULL battery accepts this day",
        alerted=("armed", "trigger"), minutes=375,
    )
    body.update(kwargs)
    return refresh.SymbolVerdict(**body)


def _verification(verdict, tmp_path: Path) -> refresh.MorningVerification:
    return refresh.MorningVerification(
        day=date(2026, 6, 10), oracle_available=True, note="",
        recording_root=tmp_path, verdicts=(verdict,),
    )


def test_a_SILENT_oracle_and_a_REFUSING_one_are_never_the_same_sentence(tmp_path: Path) -> None:
    """REVIEW_14 M16: the exchange saying NOTHING is not the exchange refusing.

    Rendering the two the same way loudly withdrew real, correct alerts over five dry-run days,
    and withdrawing an alert the record has not refused trains the trader to ignore the one line
    that exists to stop him trading.
    """
    silent = _verification(_verdict(
        verified=False, oracle_passed=False,
        oracle_reason=f"{refresh.NO_ORACLE_ROW} -- the published bhavcopy has no row",
    ), tmp_path)
    refusing = _verification(_verdict(
        oracle_passed=False,
        oracle_reason="gate 1 (volume reconciliation): gap 52.135% is above the band",
    ), tmp_path)

    assert "NOT VERIFIED" in silent.headline
    assert "treat them as withdrawn" not in silent.headline
    assert silent.verdicts[0].refused_after_alert is False
    assert silent.verdicts[0].alerted_but_unverified is True

    assert "REFUSES" in refusing.headline and "treat them as withdrawn" in refusing.headline
    assert refusing.verdicts[0].refused_after_alert is True

    assert refresh.NOT_VERIFIED_MARK in silent.render()
    assert refresh.NOT_VERIFIED_MARK not in refusing.render()
    assert "REFUSED-AFTER-ALERT" in refusing.render()


def test_an_alerted_but_unjudged_symbol_is_never_counted_as_zero_alerted(tmp_path: Path) -> None:
    """REVIEW_14 M15: the false GREEN over a morning nothing verified."""
    blind = _verification(_verdict(
        verified=False, live_passed=False, oracle_passed=False,
        live_reason=refresh.NO_CANDLES_RECORDED, oracle_reason=refresh.NO_CANDLES_RECORDED,
        minutes=0,
    ), tmp_path)
    assert "0 alerted" not in blind.headline
    assert "HDFCBANK" in blind.headline and "could NOT be judged" in blind.headline
    assert "NOT withdrawn" in blind.headline
    assert blind.as_dict()["alerted_but_unverified"] == ["HDFCBANK"]


# --- the end-of-day summary -----------------------------------------------------------------------


def test_the_summary_of_a_REPLAYED_day_names_itself_one() -> None:
    """REVIEW_14 H1, at the one message that ends the morning."""
    replayed = RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol="SHREECEM", at=datetime(2020, 3, 19, 11, 30),
        payload={"entry_paise": 74095, "stale": False, "data_behind_minutes": 0,
                 "mode": "replay"},
    )
    message = tg.TelegramSink(live=True).end_of_day_message(
        (replayed,), day=date(2020, 3, 19)
    )
    assert tg.REPLAY_MARKER in message
    assert "2020-03-19" in message

    live = RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol="HDFCBANK", at=datetime(2026, 6, 10, 11, 30),
        payload={"entry_paise": 74095, "stale": False, "data_behind_minutes": 0,
                 "mode": "live"},
    )
    assert tg.REPLAY_MARKER not in tg.TelegramSink(live=True).end_of_day_message(
        (live,), day=date(2026, 6, 10)
    )


def test_the_summary_reads_the_RECORDING_and_not_this_process(tmp_path: Path) -> None:
    """REVIEW_14 H2, at the seam: ``_end_of_day_summary`` takes no alert list at all.

    The signature is the assertion. A caller that could pass this process's own sink is a caller
    that can reproduce the defect, and the CLI is the caller that did.
    """
    signature = inspect.signature(run_screener._end_of_day_summary)
    assert "alerts" not in signature.parameters, (
        "the summary's alerts must come from the recording, which is the only list that can be "
        "right after a resume"
    )
    assert "recording" in signature.parameters
    body = inspect.getsource(run_screener._end_of_day_summary)
    assert "alerts = recorded_alerts(recording)" in body

    from acumen.live_recording import LiveRecording

    recording = LiveRecording.at(tmp_path / "2026-06-10-live")
    for kind, minute in ((ls.ALERT_ARMED, 15), (ls.ALERT_TRIGGER, 30), (ls.ALERT_EXIT, 45)):
        recording.record_alert(RecordedAlert(
            kind=kind, symbol="HDFCBANK",
            at=datetime(2026, 6, 10, 11, minute),
            payload={"entry_paise": 74095, "stale": False, "data_behind_minutes": 0,
                     "mode": "live"},
        ))
    sent: list[str] = []
    assert run_screener._end_of_day_summary(
        tg.TelegramSink(send=sent.append, live=True, out=lambda _line: None),
        recording, day=date(2026, 6, 10), disclosure=ls.LIVE_DISCLOSURE,
    ) is True
    assert tg.SUMMARY_NO_ALERTS not in sent[0]
    for kind, stamp in (("armed", "11:15"), ("trigger", "11:30"), ("exit", "11:45")):
        assert f"{kind} {stamp}" in sent[0], kind

    empty = LiveRecording.at(tmp_path / "2026-06-11-live")
    quiet: list[str] = []
    assert run_screener._end_of_day_summary(
        tg.TelegramSink(send=quiet.append, live=True, out=lambda _line: None),
        empty, day=date(2026, 6, 11),
    ) is True
    assert tg.SUMMARY_NO_ALERTS in quiet[0], "B402's own purpose, still kept"


# --- the fence, at the call site ------------------------------------------------------------------


def test_the_fence_is_asked_INSIDE_the_live_refresh_and_with_the_jobs_own_roots() -> None:
    """REVIEW_14 B1 / decision B406, read out of the shipped source.

    The fence existed and worked from the day it was written; what it lacked was a caller on the
    path that mattered, and roots that describe the job rather than the process. Both are read
    here so a refactor that drops either is a red test rather than a silent regression.
    """
    source = inspect.getsource(refresh.refresh_corporate_actions)
    assert "bt.fence_ca_cache(" in source, "the fence is ASKED on this path"
    assert "allow_network=network" in source, (
        "and the fetch takes the fence's answer, not the CLI flag"
    )
    for root in ("data_root=data_root", "cache_root=cache_root"):
        assert root in source, root

    caller = inspect.getsource(refresh.morning_refresh)
    assert "data_root=data_root_for(store)" in caller and "cache_root=cache_dir" in caller, (
        "the roots handed to the fence are the roots THIS JOB runs under -- what makes a "
        "scratch-copy run fenced by its own scratch roots (CLAUDE.md's newest rule)"
    )
    preflight = inspect.getsource(run_screener._ca_note)
    assert "data_root=data_root" in preflight and "cache_root=cache_root" in preflight, (
        "the preflight asks the same question the run asked"
    )


def test_the_bhavcopy_topup_names_the_store_it_was_HANDED(tmp_path: Path) -> None:
    """Decision B409, at the argv. Store-free: the runner is captured, never run."""
    from acumen import calendar as cal

    seen: list[list[str]] = []
    step = refresh.refresh_daily_store(
        store=DailyStore.at(tmp_path / "scratch-store"),
        calendar=cal.TradingCalendar.from_holidays([date(2026, 1, 26)], covered_years=[2026]),
        today=date(2026, 8, 7),
        runner=lambda argv: (seen.append(list(argv)), 0)[1],
    )
    assert "--store" in seen[0]
    assert seen[0][seen[0].index("--store") + 1] == str(tmp_path / "scratch-store")
    assert step.figures["store"] == str(tmp_path / "scratch-store")
    assert date.fromisoformat(seen[0][seen[0].index("--to") + 1]) < date(2026, 8, 7), (
        "the Q-19 ceiling is the last COMPLETED trading day, never today"
    )
    assert timedelta(days=0) < (
        date.fromisoformat(seen[0][seen[0].index("--to") + 1])
        - date.fromisoformat(seen[0][seen[0].index("--from") + 1])
    )
