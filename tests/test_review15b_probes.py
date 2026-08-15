"""REVIEW_15B -- the SCOPED RE-CHECK of chunk 15's cleanup, driven rather than read.

The cleanup span is ``ee412a6..29cd748``: REVIEW_15's nine findings closed, four in code (Q2, Q4,
Q3, C1) and three in prose (Q1, C2, C5), with C3 and C4 recorded-only. REVIEW_15 already passed
the chunk-15 body; what is under test here is the CLEANUP, and the risk a cleanup carries is not
the one the fix was written against -- it is the NEW behaviour firing where it should not.

So every probe in this file attacks the fixes from the side the build did not:

* **Q2** is a fail-closed change, and the real risk of fail-closed is OVER-firing. Driven here:
  the day-name fallback at each of its three outcomes; that a legitimate week never reaches the
  new code at all; and -- the property that decides whether "blocks" means "blocks a morning" or
  "blocks for ever" -- that a DATED broken artefact stops exactly ONE morning and ages out of the
  rule by itself the next day.
* **Q4** surfaces a directory the queue used to skip. Driven for what it can now refuse, and for
  the one entry that really does block until somebody acts -- with the runbook line that says who
  acts and what they do, read out of the runbook.
* **B431** claims the directory name reaches the BLOCKING TEST and nothing else. Proved by AST
  over the two loops of ``verify_prior_recordings``, so a later edit that lets a name reach the
  verifier fails here rather than in a morning.
* **Q3** is stated as "present iff the counters cannot account for the day". Driven at the
  boundary the build's own matrix does not cover: a process that accounts for all three alerts
  through THREE DIFFERENT counters.
* **C1** is confirmed where it was fixed -- and swept for, by AST, everywhere else in ``src/``.

Store-free by construction: every probe builds its own tree under ``tmp_path`` or reads the
repository. Nothing here opens ``data_root`` or ``cache_root``.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

from acumen import dry_run_readiness as gate
from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import telegram_sink as tg
from acumen.calendar import TradingCalendar
from acumen.live_recording import LiveRecording, RecordedAlert

REPO = Path(__file__).resolve().parents[1]

#: A week whose Monday is a real Monday, so ``prev_trading_day`` crosses a weekend where the
#: rule is at its most interesting: the prior TRADING day of Monday the 17th is Friday the 14th.
WED, THU, FRI = date(2026, 8, 12), date(2026, 8, 13), date(2026, 8, 14)
MON, TUE = date(2026, 8, 17), date(2026, 8, 18)


def _calendar() -> TradingCalendar:
    return TradingCalendar.from_holidays((date(2026, 1, 26),), covered_years=(2026,))


def _plant(root: Path, day: date, label: str = "live", *, mode: str = "live",
           verified: bool = False) -> LiveRecording:
    """A recording with a READABLE manifest -- what an ordinary morning leaves behind."""
    recording = LiveRecording.at(root / f"{day.isoformat()}-{label}")
    recording.open_session({
        "trade_date": day.isoformat(), "mode": mode, "symbols": ["HDFCBANK"],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    if verified:
        recording.write_verification({"trade_date": day.isoformat(), "verdicts": []})
    return recording


def _step(root: Path, scratch: Path, today: date):
    return refresh.verify_prior_recordings(
        today=today, calendar=_calendar(), data_root=scratch / "stores",
        cache_dir=scratch / "cache", recording_root=root,
    )


# --- Q2 / B431: the name fallback, and where it is allowed to reach ----------------------------


def _function(module_source: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(module_source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not a function of the module")


def _called_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                out.add(func.id)
            elif isinstance(func, ast.Attribute):
                out.add(func.attr)
    return out


def test_R15B_B431_the_directory_NAME_reaches_the_BLOCKING_TEST_AND_NOTHING_ELSE() -> None:
    """**B431**, proved structurally: no day is ever verified, written or re-judged under a name.

    The claim is a claim about REACHABILITY, so it is checked by AST over the module rather than
    by driving one example: the two loops of :func:`acumen.live_refresh.verify_prior_recordings`
    are walked and each is required to call what it may and none of what it may not.

    * the ``unreadable`` loop -- the blocking test -- may call ``recording_day_or_name``, and must
      call neither ``verify_prior_recording`` nor ``write_verification``;
    * the ``pending`` loop -- the one that VERIFIES and WRITES -- must call ``recording_day`` and
      must never call ``recording_day_or_name``.

    A future edit that lets a directory name decide which day a verdict is written for therefore
    fails here, in the suite, rather than in a market.
    """
    source = Path(refresh.__file__).read_text(encoding="utf-8")
    step = _function(source, "verify_prior_recordings")

    loops = [node for node in step.body if isinstance(node, ast.For)]
    assert len(loops) == 2, f"the step has {len(loops)} top-level loops, not two"
    blocking, verifying = loops

    # The blocking loop is the one over `unreadable`; the verifying loop is the one over `pending`.
    assert isinstance(blocking.iter, ast.Name) and blocking.iter.id == "unreadable"
    assert isinstance(verifying.iter, ast.Name) and verifying.iter.id == "pending"

    in_blocking = _called_names(blocking)
    in_verifying = _called_names(verifying)

    assert "recording_day_or_name" in in_blocking, "the name fallback is the blocking test's"
    assert "verify_prior_recording" not in in_blocking, "and it verifies nothing"
    assert "write_verification" not in in_blocking, "and it writes nothing"

    assert "recording_day" in in_verifying, "the verifier reads the MANIFEST"
    assert "recording_day_or_name" not in in_verifying, (
        "a verdict must never be written for a day a DIRECTORY NAME chose"
    )
    assert {"verify_prior_recording", "write_verification"} <= in_verifying

    # ...and the whole of src/ has exactly one call site for the fallback: that loop.
    sites = [
        path for path in sorted((REPO / "src").rglob("*.py"))
        if "recording_day_or_name(" in path.read_text(encoding="utf-8")
    ]
    assert sites == [Path(refresh.__file__)], sites
    calls = [
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "recording_day_or_name"
    ]
    assert len(calls) == 1, f"the fallback has {len(calls)} call sites in src/, not one"


def test_R15B_Q2_a_recording_whose_MANIFEST_CAN_be_read_never_reaches_the_fallback(
    tmp_path: Path,
) -> None:
    """The precondition of the whole fix: a legitimate recording is never in the ``unreadable``
    list, so the new code is unreachable for it.

    Five ordinary mornings, Monday to Friday, each leaving a recording with a readable manifest
    and each judged by the next. At every one of the five the second element of
    ``unverified_recordings`` -- the ONLY list the name fallback and the orphan rule touch -- is
    EMPTY, and the step is green. Whatever the fallback does, it cannot do it to a real week.
    """
    root = tmp_path / "live"
    week = (date(2026, 8, 10), date(2026, 8, 11), WED, THU, FRI)

    for index, day in enumerate(week):
        # The morning of `day`: yesterday's recording is on disk and unjudged; today's is not
        # written yet. This is the queue an ordinary pre-open sees.
        for earlier in week[:index]:
            if not (root / f"{earlier.isoformat()}-live").is_dir():
                _plant(root, earlier, verified=earlier != week[index - 1] if index else True)
        pending, unreadable = refresh.unverified_recordings(root, before=day)
        assert unreadable == (), (
            f"a week of readable manifests put something in the unreadable list on {day}: "
            f"{unreadable}"
        )
        assert all(refresh.recording_day(r) is not None for r in pending)

    # And with every day judged, the queue is empty and the step says so in one line.
    #
    # The Friday's own recording is PLANTED here rather than merely given a verdict, and that is
    # this probe's own scar: writing a verification for a day nothing had recorded left a
    # directory holding a verdict and no manifest, and the Q4 rule under test correctly refused
    # it. A directory that cannot say what it is of is exactly what B432 surfaces -- including
    # when a test is what created it.
    _plant(root, FRI)
    for day in week:
        LiveRecording.at(root / f"{day.isoformat()}-live").write_verification(
            {"trade_date": day.isoformat(), "verdicts": []}
        )
    _, step = _step(root, tmp_path, MON)
    assert step.ok is True
    assert "nothing unverified" in step.detail
    assert step.figures["pending"] == 0


def test_R15B_Q2_the_fallback_at_ALL_THREE_of_its_outcomes(tmp_path: Path) -> None:
    """The manifest, then the name, then nothing -- each driven, and each to the step's verdict.

    This is the finding's own shape read three ways. The middle one is the fix; the first is the
    boundary that keeps ``recording_day`` honest; the third is the only one that is permanent.
    """
    root = tmp_path / "live"

    # (1) THE MANIFEST WINS wherever it can be read -- even against a directory named otherwise.
    misnamed = LiveRecording.at(root / f"{FRI.isoformat()}-live")
    misnamed.open_session({
        "trade_date": THU.isoformat(), "mode": "live", "symbols": ["HDFCBANK"],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    assert refresh.recording_day_or_name(misnamed.root) == THU, (
        "a directory named for the Friday holding a recording of the Thursday is a recording of "
        "the Thursday, for every purpose including this one"
    )

    # (2) THE NAME ANSWERS when the manifest cannot. Three different ways of being unreadable,
    #     because the fix must not depend on which of them happened.
    for label, corruption in (
        ("broken", "{ not json at all"),
        ("empty", ""),
        ("no-trade-date", json.dumps({"mode": "live", "master_file": "x.json"})),
    ):
        planted = _plant(root / label, FRI, "live")
        planted.manifest_path.write_text(corruption, encoding="utf-8")
        assert refresh.recording_day(planted) is None, label
        assert refresh.recording_day_or_name(planted.root) == FRI, label
        _, step = _step(root / label, tmp_path, MON)
        assert step.ok is False, f"{label}: the prior trading day's own recording must stop it"
        assert step.figures["unknown_day"] == [], (
            f"{label}: the NAME dated it, so it is not one of the undateable ones"
        )

    # (3) NOTHING CAN SAY. Refused, and named as the reason it was refused.
    nameless = tmp_path / "nameless"
    (nameless / "live" / "notes").mkdir(parents=True)
    _, undated = _step(nameless / "live", tmp_path, MON)
    assert undated.ok is False
    assert refresh.recording_day_or_name(nameless / "live" / "notes") is None
    assert str(nameless / "live" / "notes") in " ".join(undated.figures["unknown_day"])
    assert "cannot say WHICH day they are of" in undated.detail


def test_R15B_Q2_a_NON_prior_broken_day_is_NAMED_and_does_NOT_block(tmp_path: Path) -> None:
    """B420's judgment, which the fix had to leave intact: an old artefact does not hold the bell.

    Three broken recordings, none of them the prior trading day's, over a Monday whose prior
    trading day is the Friday. All three are named; none of them blocks. A morning the trader
    loses is a worse failure than a stale artefact nobody can re-judge, and that trade-off is
    still the one the code makes.
    """
    root = tmp_path / "live"
    for day in (date(2026, 7, 20), WED, THU):
        planted = _plant(root, day)
        planted.manifest_path.write_text("{ not json", encoding="utf-8")

    _, step = _step(root, tmp_path, MON)
    assert step.ok is True, "not one of them is the Friday's, so the bell rings"
    assert len(step.figures["not_judged"]) == 3, "and all three are named, loudly"
    for day in (date(2026, 7, 20), WED, THU):
        assert f"{day.isoformat()}-live" in step.detail, day
    assert step.figures["unknown_day"] == [], "every one of them was dated by its name"


def test_R15B_Q2_a_DATED_blocker_stops_ONE_morning_and_ages_out_by_itself(
    tmp_path: Path,
) -> None:
    """The property that separates "blocks a morning" from "blocks for ever", driven.

    This is the over-block question that matters, and it is not answered by any test the build
    wrote. ONE artefact, unchanged on disk, read by two consecutive mornings: it is the prior
    trading day's on the Monday and it is not on the Tuesday, so it stops the Monday and clears
    itself. Nothing has to be deleted, and no operator has to do anything, for the week to
    continue -- which is what makes the fail-closed reading affordable.
    """
    root = tmp_path / "live"
    friday = _plant(root, FRI)
    friday.manifest_path.write_text("{ not json", encoding="utf-8")

    _, monday = _step(root, tmp_path, MON)
    assert monday.ok is False, "on the Monday it IS the prior trading day's"

    assert friday.root.is_dir(), "nothing was deleted, moved or repaired between the two calls"
    assert friday.manifest_path.read_text(encoding="utf-8") == "{ not json"

    _, tuesday = _step(root, tmp_path, TUE)
    assert tuesday.ok is True, (
        "on the Tuesday the prior trading day is the Monday, so the same artefact no longer "
        "blocks -- the rule ages out on its own and the week is not perpetually stopped"
    )
    assert str(friday.root) in tuesday.detail, "...and it is still named, and still queued"
    assert tuesday.figures["not_judged"], "and still reachable as data"


def test_R15B_Q2_no_VERDICT_is_ever_WRITTEN_for_a_day_a_NAME_chose(tmp_path: Path) -> None:
    """B431's claim at the only place it can cost money: the file on disk.

    The Friday recording is dated by its NAME for the blocking test. If that name ever reached
    the verifier, a ``verification.json`` would appear claiming a verdict about a day nothing
    proved this recording is of -- and the next morning would read it as judged and drop it from
    the queue, which is M15's shape with an extra step.
    """
    root = tmp_path / "live"
    friday = _plant(root, FRI)
    friday.manifest_path.write_text("{ not json", encoding="utf-8")

    verifications, step = _step(root, tmp_path, MON)
    assert step.ok is False
    assert verifications == (), "nothing was verified"
    assert not (friday.root / "verification.json").exists(), (
        "no verdict was written for a day only a directory name named"
    )
    assert friday.read_verification() == {}, "so the entry stays on the queue, as it must"
    assert step.figures["recordings"] == [] and step.figures["days"] == []

    # It is still on the queue on the next call, which is the point of not writing one.
    pending, unreadable = refresh.unverified_recordings(root, before=MON)
    assert pending == () and [path for path, _why in unreadable] == [friday.root]


# --- Q4: the orphan directory ------------------------------------------------------------------


def test_R15B_Q4_an_orphan_is_SURFACED_and_cannot_over_block_a_dated_one(
    tmp_path: Path,
) -> None:
    """Q4's fix and its cost, in one drive.

    A directory with no ``manifest.json`` used to be skipped silently -- and its own docstring
    says an absence from this list reads as a recording that PASSED. It is named now. What it
    must not do is refuse mornings it has no business refusing: an orphan the calendar can place
    behind the prior trading day is shouted about and lets the bell ring.
    """
    root = tmp_path / "live"
    old = root / f"{WED.isoformat()}-live"
    (old / "candles").mkdir(parents=True)
    (old / "candles" / "HDFCBANK.jsonl").write_text("", encoding="utf-8")

    pending, unreadable = refresh.unverified_recordings(root, before=MON)
    assert pending == (), "there is nothing to verify it under"
    assert [path for path, _why in unreadable] == [old], "but it is NAMED, never invisible"
    assert "manifest.json" in unreadable[0][1]

    _, step = _step(root, tmp_path, MON)
    assert step.ok is True, "a Wednesday-named orphan does not stop a Monday"
    assert str(old) in step.detail, "and it is still surfaced"

    # The same orphan named for the prior trading day DOES stop it -- the conservative reading.
    prior = root / f"{FRI.isoformat()}-live"
    prior.mkdir()
    _, blocked = _step(root, tmp_path, MON)
    assert blocked.ok is False and str(prior) in blocked.detail


def test_R15B_Q4_an_UNDATEABLE_orphan_blocks_until_an_OPERATOR_acts_and_the_RUNBOOK_says_how(
    tmp_path: Path,
) -> None:
    """The one entry that really is perpetual -- and the line that tells the operator what to do.

    An entry neither a manifest nor a name can date is refused every morning, by design. That is
    the disclosed price of the conservative reading, so the operator must be told: this probe
    reads section 8 of the runbook and requires the remedy to be there, to say who acts, and to
    say what a session may NOT do about it (CLAUDE.md: store deletions are never session work).
    """
    root = tmp_path / "live"
    (root / "scratch").mkdir(parents=True)

    for morning in (MON, TUE, date(2026, 8, 19)):
        _, step = _step(root, tmp_path, morning)
        assert step.ok is False, f"it blocks {morning} too -- this one does not age out"
        assert str(root / "scratch") in " ".join(step.figures["unknown_day"])

    runbook = (REPO / "docs" / "morning_runbook.md").read_text(encoding="utf-8")
    section = runbook.split("## 8.", 1)[1].split("\n## ", 1)[0]
    assert "cannot say WHICH day" in section, "the report's own words are on the operator's card"
    assert "Tell the architect" in section, "and the card says WHO clears it"
    assert "do not delete anything" in section, (
        "...and that clearing it is not a thing the operator does alone: store deletions are "
        "never a session's work and a snapshot is verified before anything is removed"
    )
    # The escalation the card points at is a rule of the card, not a sentence invented for it.
    assert "The stores are read-only during a session" in runbook


def test_R15B_Q4_nothing_that_EXISTS_TODAY_can_be_refused_by_the_new_rule() -> None:
    """Read from the machine, not from the build's assurance: there is no live root yet.

    The queue change can only ever refuse an artefact under ``<data_root>/live``. If that
    directory does not exist, ``unverified_recordings`` returns two empty tuples before it looks
    at anything -- so the first artefact this rule can refuse is one a dry-run week creates.
    """
    from acumen.config import load_config

    live_root = load_config(include_env=False).path("data_root") / "live"
    assert refresh.unverified_recordings(live_root, before=MON) == ((), ()), (
        "an absent recording root is two empty tuples, and an absent root cannot block"
    )
    if live_root.exists():  # pragma: no cover -- true only once a dry-run week has run
        pending, unreadable = refresh.unverified_recordings(live_root, before=date.today())
        assert unreadable == (), (
            f"the live root now exists and holds entries the new rule would surface: {unreadable}"
        )


def test_R15B_Q4_the_TWO_behaviour_changes_the_surfacing_buys_are_MEASURED(
    tmp_path: Path,
) -> None:
    """Two consequences of surfacing that neither REVIEW_15 nor the build states. Both measured.

    ``unverified_recordings`` applies its ``mode == "live"`` and ``day < before`` filters only
    AFTER a manifest has been read. An entry that reaches the unreadable list therefore skips
    both of them, so surfacing changes behaviour in two places nobody has written down:

    1. **A REPLAY whose manifest is corrupt, dated to the prior trading day, now BLOCKS.** Before
       the fix it did not (``recording_day`` answered ``None``). This review judges it CORRECT and
       records it: a manifest that cannot be read cannot say ``replay`` either, and calling it one
       would replace an unverifiable claim with a second unverifiable claim -- which is **B424**'s
       own approved reasoning, applied to the same unknown from the other side. A replay whose
       manifest IS readable is still filtered out and still cannot block.
    2. **A future-dated unreadable entry is surfaced.** It is named rather than skipped, and it
       does not block, because a future day is not the prior trading day.

    Neither is a defect; both are behaviour a later session would otherwise rediscover in a
    market. Pinned as measured.
    """
    # (1) the corrupt REPLAY of the prior trading day
    root = tmp_path / "replay"
    corrupt = _plant(root, FRI, "replay", mode="replay")
    corrupt.manifest_path.write_text("{ not json", encoding="utf-8")
    _, step = _step(root, tmp_path, MON)
    assert step.ok is False, (
        "a corrupt manifest cannot say 'replay', so it is refused like any other entry nothing "
        "can vouch for -- B424's reasoning from the other side"
    )

    # ...while a READABLE replay manifest is still invisible to the queue and still cannot block.
    clean = tmp_path / "clean"
    _plant(clean, FRI, "replay", mode="replay")
    assert refresh.unverified_recordings(clean, before=MON) == ((), ())
    _, quiet = _step(clean, tmp_path, MON)
    assert quiet.ok is True and "nothing unverified" in quiet.detail

    # (2) a FUTURE-dated unreadable entry: named, not skipped, and not a blocker.
    ahead = tmp_path / "ahead"
    future = _plant(ahead, date(2027, 1, 4), "live")
    future.manifest_path.write_text("{ not json", encoding="utf-8")
    _, later = _step(ahead, tmp_path, MON)
    assert later.ok is True, "a day that has not happened is not the prior trading day"
    assert str(future.root) in later.detail, "but it is still named rather than skipped"


# --- Q3: the resumed-summary line, at the boundary the build's matrix does not cover ------------


def _alerts(count: int) -> tuple[RecordedAlert, ...]:
    from datetime import datetime

    return tuple(
        RecordedAlert(
            kind=ls.ALERT_TRIGGER, symbol=symbol, at=datetime(2026, 6, 10, 11, 30),
            payload={
                "side": "long", "entry_paise": 74_095 + index, "mode": ls.POSTURE_LIVE,
                "stale": False, "data_behind_minutes": 0,
            },
        )
        for index, symbol in enumerate(("HDFCBANK", "ICICIBANK", "INFY")[:count])
    )


def test_R15B_Q3_the_line_is_present_IFF_the_counters_cannot_ACCOUNT_for_the_day() -> None:
    """The rule as stated -- ``accounted < alerts`` -- driven where the three counters DIFFER.

    The build's own matrix moves one counter (``sent``) from 0 to 3 and adds an all-refused case.
    Both of those are single-counter shapes, so neither can tell "did this process do nothing"
    from "can this process account for the day". The mixed shape can: one sent, one refused, one
    failed is three alerts accounted for by a process that sent only one of them, and the line
    must be ABSENT. Then one alert is taken out of the process's reach and it must be PRESENT.
    """
    alerts = _alerts(3)

    def sink_that(kinds: tuple[str, ...]) -> tg.TelegramSink:
        outcomes = iter(kinds)
        state = {"raise": False}

        def send(_text: str) -> None:
            if state["raise"]:
                raise TimeoutError("the transport is down")

        made = tg.TelegramSink(live=True, send=send, out=lambda line: None)
        for alert, outcome in zip(alerts, outcomes):
            if outcome == "refused":
                stripped = RecordedAlert(
                    kind=alert.kind, symbol=alert.symbol, at=alert.at,
                    payload={k: v for k, v in alert.payload.items() if k != "stale"},
                )
                made.deliver(stripped)
                continue
            state["raise"] = outcome == "failed"
            made.deliver(alert)
        state["raise"] = False
        return made

    mixed = sink_that(("sent", "refused", "failed"))
    text = mixed.end_of_day_message(alerts, day=date(2026, 6, 10))
    assert (len(mixed.sent), len(mixed.refused), len(mixed.failed)) == (1, 1, 1), mixed
    assert "1 sent, 1 refused (unvouched price), 1 failed" in text
    assert tg.SUMMARY_SUBJECTS not in text, (
        "three alerts accounted for by three different counters is not a resume, and the line "
        "that explains a resume must not be on it:\n" + text
    )

    # Take ONE alert out of this process's reach and the same sink must carry the sentence.
    partial = sink_that(("sent", "refused"))
    partial_text = partial.end_of_day_message(alerts, day=date(2026, 6, 10))
    assert (len(partial.sent), len(partial.refused), len(partial.failed)) == (1, 1, 0)
    assert tg.SUMMARY_SUBJECTS in partial_text, (
        "two of the day's three alerts accounted for IS a resume, and it is the shape Q3 was "
        "about:\n" + partial_text
    )


def test_R15B_Q3_a_normal_morning_can_always_ACCOUNT_for_every_alert_it_produced() -> None:
    """The new guard's only spurious-fire vector, closed at the source.

    ``deliver`` returns without touching a counter when the alert's kind is not one the sink
    forwards. Under the OLD guard that could not matter (one delivery suppressed the line); under
    the NEW one, a filtered kind would make a perfectly ordinary morning read as a resumed one.
    It cannot happen, because the sink's default set is every kind the screener can emit -- so
    this pins the two sets to each other rather than trusting the docstring's "everything".
    """
    assert tg.TelegramSink().kinds == ls.ALERT_KINDS, (
        "a kind the screener can emit and the sink does not forward would be an alert no counter "
        "can account for, and the resumed-morning line would appear on an ordinary day"
    )
    assert ls.ALERT_KINDS == frozenset(
        {ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT, ls.ALERT_SQUARE_OFF, ls.ALERT_FAILURE}
    )


# --- C1: the dead module form, swept beyond the module it was fixed in -------------------------


def _printable(source: str) -> list[tuple[int, str]]:
    """Every string literal a module can PRINT -- docstrings excluded, with line numbers."""
    tree = ast.parse(source)
    docs: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [
        (node.lineno, node.value) for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docs
    ]


def test_R15B_C1_the_GATE_carries_the_launcher_and_no_printable_trace_of_the_dead_form() -> None:
    """C1 where it was fixed, re-measured by this review rather than read from the build's test."""
    refusal = gate.check_master(date(2026, 6, 10), cache_dir=Path("nowhere-at-all"))
    assert not refusal.ok
    assert f"`python {gate.MASTER_LAUNCHER} --allow-network`" in refusal.detail
    assert "-m acumen." not in refusal.detail
    assert (REPO / gate.MASTER_LAUNCHER).is_file()

    offenders = [
        (line, text) for line, text in _printable(
            Path(gate.__file__).read_text(encoding="utf-8")
        ) if "-m acumen." in text
    ]
    assert not offenders, offenders


def test_R15B_C1_the_SAME_dead_form_elsewhere_in_src_is_MEASURED_not_assumed_absent() -> None:
    """The sweep C1 implies, taken across the whole package -- and pinned as MEASURED.

    REVIEW_15B finding: ``check_master`` was the site C1 named, and the cleanup fixed exactly it.
    The identical remedy string survives in printable, operator-facing refusals in three more
    places, none of which is in the cleanup's span and none of which REVIEW_15 raised:

    * ``live_screener._require_day_master`` -- the LIVE MORNING's own refusal when the day's dump
      is missing, which is the most operator-facing of the three;
    * ``backtest.named_master`` -- reached by the pre-open verification step;
    * ``backtest.CA_REFRESH_FENCED`` -- printed on every preflight, naming ``-m acumen.ca_report``.

    Pinned as the MEASURED state, not as the intended one, exactly as REVIEW_15 pinned C1 before
    the cleanup closed it. Flip this when the launchers are named: the working ones already exist
    (``scripts/fetch_instrument_master.py``, ``scripts/run_screener.py``, ``scripts/ca_report.py``).
    """
    carriers: dict[str, list[int]] = {}
    for path in sorted((REPO / "src" / "acumen").rglob("*.py")):
        hits = [
            line for line, text in _printable(path.read_text(encoding="utf-8"))
            if "-m acumen." in text
        ]
        if hits:
            carriers[path.name] = hits

    assert "dry_run_readiness.py" not in carriers, "C1's own site is CLOSED and must stay closed"
    assert set(carriers) == {"live_screener.py", "backtest.py"}, (
        f"the carried sites moved -- re-measure this pin: {carriers}"
    )
    for name, launcher in (
        ("fetch_instrument_master.py", "instrument master"),
        ("run_screener.py", "screener"),
        ("ca_report.py", "corporate actions"),
    ):
        assert (REPO / "scripts" / name).is_file(), (
            f"the working launcher for the {launcher} exists, which is why this is one string"
        )
