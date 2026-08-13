"""REVIEW_13B's KEPT PROBES -- the re-review of chunk 13's FIX-2.

Seven probes. Three held behaviour that re-review verified and wanted held; **four PINNED
DEFECTS it found and said so in their names**, so a later session had to flip each one
deliberately rather than discover it by accident. That is the convention
``tests/test_review13_probes.py`` established and this file follows it exactly.

**The chunk-14 session has flipped all four, and this docstring is the record of it:**

    Q1  the alert carries no staleness marker   FLIPPED -- test_the_live_alert_line_CARRIES_*
    Q2  the live calendar falls through a gap   FLIPPED -- test_the_live_calendar_REFUSES_*
    Q3  --config does not govern the CA cache   FLIPPED -- test_build_runner_PASSES_the_*
    Q4  two string idioms evade the tripwire    FLIPPED -- test_the_order_tripwire_CATCHES_*

Each flipped probe KEEPS the defect's own measurement in its docstring and asserts the opposite
of what it asserted, so the review's finding stays readable beside the fix that closed it. The
deeper tests -- the whole frozen morning, the ledger's two qty-zero days, the fence's decision
table, the byte-level store tripwire -- live in ``tests/test_chunk14_carried_defects.py``; what
is kept here is the review's own witness, flipped.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from acumen import backtest as bt
from acumen import calendar as cal
from acumen import live_dashboard as dash
from acumen import live_screener as ls
from acumen.config import load_config
from acumen.daily_store import DailyStore
from acumen.live_recording import LiveRecording
from acumen.live_source import StoredDayBarSource
from acumen.minute_store import MinuteStore

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"

SYMBOL = "HDFCBANK"
LIVE_DAY = date(2026, 6, 10)
#: A real day on which a five-minute-late window MOVES the POC: the complete 09:15-11:14 window
#: answers 738.90 and a window five minutes short answers 739.70. Measured over 216 real
#: symbol-days by this re-review: a 5-minute-late window moves the POC on 16.67% of them.
BITE_DAY = date(2026, 6, 8)


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


def _live(tmp_path: Path, source, *, day: date, label: str):
    """The SHIPPED construction path -- nothing hand-assembled, no field mutated."""
    config = load_config(include_env=False)
    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(tmp_path / "rec" / f"{day.isoformat()}-{label}")
    screener = ls.build_live_screener(
        day, (SYMBOL,),
        source=source,
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="live",
        data_dir=config.path("data_root"),
        cache_dir=_scratch_world(tmp_path, day),
        sinks=(sink,),
    )
    return screener, sink, recording


# --- DEFECT PIN 1 (REVIEW_13B Q1) --------------------------------------------------------------


@dataclass
class _FrozenFeed:
    """A vendor that keeps answering 200 with a prefix that never grows.

    Not the empty answer REVIEW_13 B10 named -- that one is fixed (B362: an empty reply is a
    not-answer, retried, deferred and banner-raised). This is the other shape: a stale cache
    served successfully, which every sweep counts as a complete fetch.
    """

    inner: object
    freeze_at: datetime
    calls: int = 0

    def fetch(self, symbol, day, upto):
        self.calls += 1
        if self.calls <= 2:
            return self.inner.fetch(symbol, day, upto)
        return self.inner.fetch(symbol, day, self.freeze_at)


def test_the_live_alert_line_CARRIES_the_staleness_marker_when_the_feed_freezes(
    tmp_path: Path,
) -> None:
    """REVIEW_13B **Q1**, FIXED and FLIPPED. The row said STALE and the alert said nothing.

    Measured here on HDFCBANK 2026-06-10. The feed freezes at 11:30 and keeps answering; the
    real day hit its target at 749.50 at 13:15. What the trader got instead was a SQUARE-OFF
    alert at 740.95 -- computed off bars that stopped four hours earlier -- with:

    * no failure banner (every sweep "completed": the feed answered),
    * nothing on the ALERT line to say the data is stale,
    * and the dashboard row correctly marked ``[STALE 241m BEHIND - NOT being watched]``.

    **FLIPPED.** The staleness marker travels on the alert exactly as ``poc_note`` does
    (:meth:`LiveScreener._alert`), from the same predicate the dashboard row uses -- which now
    lives in ``live_screener`` so there is one of it. The banner is still silent, which is
    honest: every sweep really did complete, and what is wrong is the DATA, which is what the
    marker says. The chunk-14 rule that makes it safe to forward is asserted separately:
    :func:`acumen.live_screener.unvouched_price` refuses any alert that names a price without a
    freshness stamp, and the Telegram sink runs it before it sends.
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
    assert screener.banner == "", (
        "the banner is still silent, and that is honest: every sweep DID complete -- the feed "
        "answered every time. What is wrong is the data, which is what the marker is for"
    )

    # The RENDERED row is marked -- B10's own fix, and it holds.
    text = dash.render_text(
        day=LIVE_DAY, now=reports[-1].boundary, grouped=screener.by_phase(),
        alerts=tuple(sink.alerts), banner=screener.banner, dry_run=True,
        disclosure=ls.LIVE_DISCLOSURE, verification=None,
    )
    row = [line for line in text.splitlines() if SYMBOL in line and "bars" in line]
    assert row and "STALE" in row[0], "the dashboard row IS marked stale (B10, fixed)"

    # ...and so is the ALERT, which is the surface chunk 14 forwards.
    exits = [a for a in sink.alerts if a.kind in (ls.ALERT_EXIT, ls.ALERT_SQUARE_OFF)]
    assert exits, "the frozen prefix still produces an exit-side alert"
    delivered = ls.format_alert(exits[-1])
    assert "SQUARE-OFF at 740.95" in delivered, "the review's own measured alert, unchanged"
    assert "STALE 226m BEHIND" in delivered, (
        "the marker is on the line the trader reads -- 15:15 minus the 11:29 prefix, measured "
        "at the alert's own boundary rather than at the dashboard's clock (241m at 15:30)"
    )
    payload = exits[-1].payload
    assert payload["stale"] is True and payload["data_behind_minutes"] == 226
    assert ls.MARKER_STALE in payload["alert_states"]
    assert ls.unvouched_price(exits[-1]) is None, (
        "and with the marker on it, the alert may be forwarded: its price is vouched for"
    )


# --- DEFECT PIN 2 (REVIEW_13B Q2) --------------------------------------------------------------


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


def test_the_live_calendar_REFUSES_a_GAP_inside_the_history(tmp_path: Path) -> None:
    """REVIEW_13B **Q2**, FIXED and FLIPPED: the merge's gap refusal now exists.

    Decision **B363** says *"a GAP inside the history is still refused rather than papered
    over"*, and :func:`acumen.calendar.live_trading_calendar`'s own docstring says an
    unattempted date inside the history *"is the incomplete-backfill case Q-3 safeguard 1
    refuses"*. Neither was implemented: ``settled_through`` walks forward only while the ledger
    is terminal, so the FIRST hole silently handed the whole remaining history to the published
    holiday master.

    The measured cost on this machine's store was zero moved trading days (the published master
    and the store agree over 2026) and a LOST Q-5 weekend-session disclosure -- the manifest's
    ``excluded_weekend_sessions`` block went empty. What it would have cost on a store whose
    history disagrees with the published master is a CONTEXT 3.2 bias pair judged from a
    different calendar than the backtester's, which is drift in the one place section 6 forbids.

    **FLIPPED.** The store's own ledger decides: terminal evidence AFTER the hole means an
    incomplete backfill and is refused; no evidence after it means the store has reached the end
    of what it has attempted, which is every ordinary live morning under Q-19's guard and must
    still start. Both halves are asserted here and again, over a real morning's span, in
    ``tests/test_chunk14_carried_defects.py``.
    """
    data_root = _stores_or_skip()
    store = DailyStore.at(data_root / "daily_store")
    cache = _scratch_world(tmp_path, LIVE_DAY)
    published = cal.fetch_calendar(cache_dir=cache, today=LIVE_DAY, allow_network=False)
    first, hole = date(2026, 1, 2), date(2026, 1, 5)
    gappy = _GappyStore(store, hole)

    with pytest.raises(cal.CalendarError) as refusal:
        cal.TradingCalendar.from_daily_store_range(gappy, first, date(2026, 6, 9))
    assert "never attempted" in str(refusal.value), (
        "Q-3 safeguard 1 still holds where it always held"
    )

    with pytest.raises(cal.CalendarError) as merged_refusal:
        cal.live_trading_calendar(published, store=gappy, first_day=first, day=LIVE_DAY)
    assert "GAP inside its own history" in str(merged_refusal.value)
    assert hole.isoformat() in str(merged_refusal.value)

    whole = cal.live_trading_calendar(published, store=store, first_day=first, day=LIVE_DAY)
    assert whole.trading_days, "the WHOLE store still builds"
    assert whole.excluded_weekend_sessions, (
        "and the Q-5 weekend-session disclosure the store alone can supply is kept"
    )


# --- DEFECT PIN 3 (REVIEW_13B Q4) --------------------------------------------------------------


def test_the_order_tripwire_CATCHES_percent_and_format_construction() -> None:
    """REVIEW_13B **Q4**, FIXED and FLIPPED: two ordinary idioms no longer evade the scan.

    M7's widening was real -- that re-review re-measured it at 31/31 on the shipped corpus, with
    five AST-only catches and one literal-only catch, over 170 files instead of 46. Then ten NEW
    shapes were put to it and seven were caught. The three misses were ``"place%s" % "Order"``,
    ``"place{}".format("Order")`` and a ``chr()`` reconstruction. The last is deliberate
    obfuscation and outside any static tripwire's remit; the first two are ordinary Python that
    a careless author could reach for, which is exactly the population it is for.

    **FLIPPED.** ``_folded_strings`` folds ``ast.Mod`` over a constant left-hand side (both the
    single-value and the tuple form) and ``str.format`` with constant positional arguments. Both
    remain LITERAL-half misses by construction -- the normaliser leaves ``%s%`` and
    ``{}.format(`` between the halves -- so each one is a catch the AST half adds and the line
    scan cannot make.
    """
    from tests.test_live_safety import EVASIONS, ast_offenders, literal_offenders, scan_source

    # The shapes are READ from the corpus rather than written here, and they have to be: now
    # that the AST half folds them, a file that spells one out is a file the repository-wide
    # scan refuses -- which is the whole point of the fix, and which is why the corpus lives in
    # the one self-exempt file (this probe used to be able to write them precisely because they
    # were invisible).
    corpus = dict(EVASIONS)
    for label in ("percent format", "str.format", "str.format across lines"):
        source = corpus[label]
        assert not literal_offenders(source, label), (
            f"{label}: the literal half still cannot see it, which is why the AST half matters"
        )
        assert ast_offenders(ast.parse(source), label), f"{label}: the AST half CATCHES it"

    # The tuple form is the one shape of the four the LITERAL half already saw: squashing a
    # two-placeholder template against a tuple of two constants leaves the endpoint's own
    # spelling on the line. It is folded by the AST half anyway, so the two halves agree rather
    # than one of them carrying it alone.
    tuple_form = corpus["percent format, tuple"]
    assert literal_offenders(tuple_form, "percent format, tuple")
    assert ast_offenders(ast.parse(tuple_form), "percent format, tuple")

    # ... and the corpus, now four shapes longer, is caught in full.
    assert not [label for label, src in EVASIONS if not scan_source(src, label)]
    assert len(EVASIONS) >= 35, "the four new shapes joined the permanent corpus"


# --- HOLD 1: CONTEXT 4.7 against the ONE recorded text that can judge it ------------------------


def test_CONTEXT_4_7_is_byte_verbatim_against_the_RECORDED_ruling_in_QUESTIONS() -> None:
    """The architect's 12-Aug-2026 ruling: QUESTIONS.md's recorded text is 4.7's authority.

    *"there is NO external section 4.7 template -- QUESTIONS.md's recorded ruling text is the
    authority for 4.7 and 4.7 is verified against it; the earlier 'architect's template'
    phrasing is retired."*

    So the check REVIEW_13 could not discharge is discharged here, and kept: the disclosed
    sentence is the ruling's own 68 characters in all three places it exists (the ruling, the
    law, the code), and the section-6 parity clause Q-31(1) raised is in the law.
    """
    questions = (REPO / "QUESTIONS.md").read_text(encoding="utf-8")
    context = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    section = context[context.index("## 4.7 LIVE-MODE VALIDITY"):]
    section = section[:section.index("\n## ")]

    ruling = re.search(
        r"carries the disclosed line '(.*?record)'", questions.replace("\n> ", " ")
    )
    assert ruling is not None, "the Q-28 ruling is recorded in QUESTIONS.md"
    sentence = ruling.group(1)
    assert len(sentence) == 68
    assert sentence == ls.LIVE_DISCLOSURE
    assert f'Every live alert carries: "{sentence}"' in section, (
        "REVIEW_13's one-byte finding: 4.7 used to carry a terminal full stop INSIDE the "
        "quotation marks, 69 characters where the ruling has 68"
    )
    assert (
        "Section 6 parity is judged on oracle-passing days; a live-alerted day the oracle "
        "later refuses is the disclosed, bounded difference (live cannot see tomorrow)."
    ) in section, "Q-31(1): the parity clause reaches the law"
    assert "A live morning screens the settled universe (204)" in section, "Q-30, in the law"
    assert "--" not in section.splitlines()[2], "no transliteration: the em dashes are kept"


# --- HOLD 2: the POC pin, on a day where a short window really moves it -------------------------


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


def test_the_POC_pinned_on_a_SHORT_window_is_the_one_that_GOVERNS_the_whole_day(
    tmp_path: Path,
) -> None:
    """CONTEXT 3.3 + the architect's 08-Aug-2026 B3 ruling, on a day where the pin BITES.

    The fix session's own late-window day is one where the five missing minutes happen not to
    move the POC. This probe uses 2026-06-08, where they do: the complete window answers 738.90
    and a five-minute-late one answers 739.70. The ruling is that the SHORT answer stands --
    *"the POC is fixed at 11:15 and immutable for the day; a window missing its late minutes is
    a completeness failure -- flag 'POC provisional / incomplete window' and never silently
    re-fix"* -- and that is what is asserted, including after a restart, which is exactly when
    the window IS more complete than it was at 11:15.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, BITE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    control, _sink, _rec = _live(tmp_path / "a", StoredDayBarSource(store),
                                 day=BITE_DAY, label="ctl")
    control.run_day()
    complete = control.profiles[SYMBOL].poc_paise

    late, _sink2, _rec2 = _live(tmp_path / "b", _LateWindow(StoredDayBarSource(store), BITE_DAY),
                                day=BITE_DAY, label="late")
    late.run_day()
    pinned = late.profiles[SYMBOL].poc_paise

    assert pinned != complete, (
        "the probe day is chosen so the five late minutes really do move the POC"
    )
    assert late.states[SYMBOL].poc_provisional
    assert late.states[SYMBOL].poc_missing_minutes == 5
    assert late.bars[SYMBOL] and len(late.bars[SYMBOL]) > 300, (
        "the whole session is in hand by the close -- the window was long since complete"
    )
    assert late.profiles[SYMBOL].poc_paise == pinned, "and the POC was never re-fixed"

    resumed, _s3, _r3 = _live(tmp_path / "b", StoredDayBarSource(store),
                              day=BITE_DAY, label="late")
    assert resumed.restore()
    assert resumed.profiles[SYMBOL].poc_paise == pinned, (
        "a restart rebuilds the SAME POC from the four persisted fields"
    )
    assert resumed.profiles[SYMBOL].missing_window_minutes == 5
    resumed.run_day()
    assert resumed.profiles[SYMBOL].poc_paise == pinned, (
        "and a whole second morning over the COMPLETE day does not move it either"
    )


# --- HOLD 3: B2's stated boundary -- a twin in one reply refuses, across sweeps is a revision ---


@dataclass
class _TwinAcrossSweeps:
    """A vendor whose second and later replies re-serve one stamp with different values."""

    inner: object
    stamp: datetime
    calls: int = 0

    def fetch(self, symbol, day, upto):
        from dataclasses import replace

        self.calls += 1
        bars = self.inner.fetch(symbol, day, upto)
        if self.calls <= 1:
            return tuple(bars)
        return tuple(
            replace(bar, close_paise=bar.close_paise * 10, high_paise=bar.high_paise * 10)
            if bar.stamp == self.stamp else bar
            for bar in bars
        )


def test_a_stamp_RE_SERVED_in_a_later_sweep_is_a_revision_and_not_a_gate_2_duplicate(
    tmp_path: Path,
) -> None:
    """Decision **B358**'s boundary, stated as a test rather than as a claim.

    CONTEXT 4.5 gate 2's first exclusion trigger is *"any duplicate stamp"* and B2's fix carries
    the twins of ONE REPLY to the gate. The deliberate limit is that the same stamp arriving in
    a LATER sweep is not a duplicate -- ``SmartApiBarSource`` re-pulls the whole session every
    sweep by design, so a day-wide count would refuse every symbol by 11:30. This probe holds
    that boundary in place AND holds the thing that makes it safe: the revision is recorded, it
    reaches the next morning's verification, and a changed answer is delivered as a CORRECTION
    rather than swallowed.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(SYMBOL, LIVE_DAY):
        pytest.skip("the local minute lake does not hold the probe day")

    stamp = datetime.combine(LIVE_DAY, datetime.min.time()).replace(hour=10, minute=20)
    screener, _sink, recording = _live(
        tmp_path, _TwinAcrossSweeps(StoredDayBarSource(store), stamp),
        day=LIVE_DAY, label="revision",
    )
    screener.run_day()

    assert not screener.duplicate_bars.get(SYMBOL), (
        "a stamp re-served in a LATER reply is not a gate-2 duplicate (B358)"
    )
    gates = screener._battery(SYMBOL, screener.bars[SYMBOL])
    assert gates.gate2.duplicates == 0 and gates.usable

    revisions = recording.revisions(SYMBOL)
    assert len(revisions) == 1, (
        "but it IS a revision, and B331's reporting half now has a caller"
    )


# --- HOLD 4: what --config does NOT govern, pinned at the source --------------------------------


def test_build_runner_PASSES_the_CORPORATE_ACTION_cache_and_FENCES_the_refresh() -> None:
    """REVIEW_13B **Q3**, FIXED and FLIPPED -- still pinned at the source, still writing nothing.

    ``build_runner`` called ``build_factor_tables(..., allow_network=allow_network)`` with NO
    ``cache_dir``, so the corporate-action cache resolved to
    :func:`acumen.corp_actions.default_cache_dir` = ``<data_root>/nse`` whatever ``--config``
    said. On a live morning started with ``--allow-network`` -- the invocation
    ``run_screener``'s own docstring recommends -- that re-fetched and REWROTE 22 year files
    inside the store the operator snapshots, before the first sweep. That re-review measured it:
    22 files, +46,262 bytes, 45 seconds of paced network, and 19 symbols gaining one
    ordinary-dividend factor each (every ex-date after the frozen run's end, so no walked row
    moved), with nothing in the preflight, the manifest or the recording to say so.

    **FLIPPED.** The cache is passed explicitly, resolved from the caller's own ``data_dir``, and
    :func:`acumen.backtest.fence_ca_cache` stands between the CLI flag and the fetch: a cache
    inside either store is refreshed only under a NAMED sanction, and otherwise the flag becomes
    a cache read with :data:`acumen.backtest.CA_REFRESH_FENCED` printed. The byte-level proof --
    a real ``build_runner(allow_network=True)`` against the real store, fingerprinted before and
    after -- is ``test_Q3_a_LIVE_REFRESH_writes_ZERO_bytes_under_the_stores``. This probe stays
    at the SOURCE, because the finding was that the code writes, so the probe must not.
    """
    source = (Path(bt.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "build_factor_tables"
    ]
    assert calls, "build_runner still builds the factor tables"
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        assert "cache_dir" in keywords, "--config governs the CA cache now"
        assert "sanctioned_write" in keywords, "and a store write needs a named sanction"
        assert "allow_network" in keywords

    from acumen import corp_actions as ca

    data_root = load_config(include_env=False).path("data_root")
    assert ca.default_cache_dir() == data_root / "nse", (
        "the DEFAULT location is unchanged -- the fence is about writing, not about moving the "
        "cache, so every historical run reads exactly the table it always read"
    )
    resolved, network, why = bt.fence_ca_cache(cache_dir=None, allow_network=True)
    assert resolved == data_root / "nse" and network is False and why == bt.CA_REFRESH_FENCED
