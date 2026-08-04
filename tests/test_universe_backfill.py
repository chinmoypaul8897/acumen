"""Chunk-5B tests for the full-universe 1-minute run (:mod:`acumen.universe_backfill`).

The run itself is hours of live network, so what is testable offline is the DISCIPLINE around
it, and that is exactly what the card asks to be tested: the routing classifier's effect on a
real run, the map-required refusal, resume, the quarantine trigger and its halt ceiling, and
report generation. All of it runs against a synthetic VENDOR -- a fake client that serves
back-adjusted candles the way SmartAPI does -- plus a real Parquet daily store and a real
minute store in ``tmp_path``.

The end-to-end case is the one that matters most: a symbol with a demerger (no factor of ours)
whose vendor bakes a 0.9 factor into pre-ex minutes. Its map must be PROBED and BUILT before
its ingest, the measured 0.9 must come back out of the stored prices exactly, and gate 1 must
then pass on every day. That is the whole Q-11 chain, driven through the runner.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import corp_actions as ca
from acumen import minute_backfill as mb
from acumen import universe_backfill as ub
from acumen import vendor_adjustment as va
from acumen.adjustment_route import ROUTE_MAP_REQUIRED, ROUTE_TABLE_PATH
from acumen.bhavcopy import FORMAT_UDIFF, OUTCOME_PRESENT, DailyRow, DateOutcome, Download
from acumen.daily_store import DailyStore
from acumen.minute_store import MinuteStore
from acumen.smartapi_client import OneMinuteBar

NOW = datetime(2026, 7, 26, 8, 0, 0)

# A short synthetic history: one trading day a week keeps the fixture small while still
# spanning the eras a real symbol has. Prices are multiples of 10 paise and volumes multiples
# of 9 so the synthetic vendor's x0.9 / /0.9 stays exact -- the test measures the machinery,
# not rounding.
VENDOR_DEMERGER_FACTOR = Decimal("0.9")


def _trading_days(first: date, count: int, *, step: int = 7) -> list[date]:
    return [first + timedelta(days=step * i) for i in range(count)]


DAYS = _trading_days(date(2019, 1, 2), 40)  # 2019-01-02 .. 2019-10-02, ~10 fetch windows
START = date(2019, 1, 1)
END = DAYS[-1] + timedelta(days=3)
DEMERGER_EX = DAYS[20]


def _daily_row(day: date, symbol: str, base: int, volume: int) -> DailyRow:
    return DailyRow(
        trade_date=day, symbol=symbol, series="EQ",
        open_paise=base, high_paise=base + 100, low_paise=base - 100, close_paise=base + 50,
        volume=volume, last_paise=base + 50, prev_close_paise=base, turnover_paise=base * volume,
        trades=100, isin=None, instrument_type=None, source_format=FORMAT_UDIFF,
    )


def _make_daily_store(tmp_path: Path, symbols: dict[str, int]) -> DailyStore:
    """A real Parquet daily store carrying ``symbols`` (name -> base price) over DAYS.

    Written through ``write_rows`` + ONE ``record_outcomes`` rather than per-date ``ingest``:
    the ledger rewrite is O(n) per date (REVIEW_2 F8 measured it), which is fine for a real
    backfill and needlessly quadratic for a fixture.
    """
    store = DailyStore.at(tmp_path / "daily_store")
    outcomes = []
    for index, day in enumerate(DAYS):
        rows = tuple(
            _daily_row(day, symbol, base + 10 * index, 9000 + 9 * index)
            for symbol, base in symbols.items()
        )
        store.write_rows(day, rows)
        outcomes.append(
            DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, source_format=FORMAT_UDIFF,
                        url="https://example.invalid", http_status=200,
                        row_count=len(rows), attempted_at=NOW)
        )
    store.record_outcomes(outcomes)
    return store


class SyntheticVendor:
    """A SmartAPI double that serves CA-BACK-ADJUSTED 1-minute candles, as the real feed does.

    For a symbol in ``adjusted``, every day strictly before the ex-date comes back multiplied by
    the vendor's price factor and divided by it in volume -- the exact signature chunk 5A
    measured. Everything on or after the ex-date, and every other symbol, comes back raw. The
    daily fold of the three bars it emits reproduces the daily store's high/low/volume exactly,
    so an un-adjustment that is right lands on the raw daily values to the paisa.
    """

    def __init__(self, cache: ub.DailyCache, tokens: dict[str, str],
                 adjusted: dict[str, tuple[date, Decimal]] | None = None) -> None:
        self._cache = cache
        self._by_token = {token: symbol for symbol, token in tokens.items()}
        self._adjusted = adjusted or {}
        self.calls: list[tuple[str, date, date]] = []

    def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):  # type: ignore[no-untyped-def]
        symbol = self._by_token[token]
        self.calls.append((symbol, from_dt.date(), to_dt.date()))
        bars: list[OneMinuteBar] = []
        for day in self._cache.days(symbol):
            if not (from_dt.date() <= day <= to_dt.date()):
                continue
            row = self._cache.day(symbol, day)
            assert row is not None
            k = Decimal(1)
            if symbol in self._adjusted:
                ex_date, factor = self._adjusted[symbol]
                if day < ex_date:
                    k = factor
            high = int(Decimal(row.high_paise) * k)
            low = int(Decimal(row.low_paise) * k)
            close = int(Decimal(row.close_paise) * k)
            volume = int(Decimal(row.volume) / k)
            stamp = datetime.combine(day, time(9, 15))
            # three bars whose fold is exactly (high, low, close, volume)
            bars.extend([
                OneMinuteBar(stamp, low, high, low, close, volume - 2 * (volume // 3)),
                OneMinuteBar(stamp + timedelta(minutes=1), close, high, low, close, volume // 3),
                OneMinuteBar(stamp + timedelta(minutes=2), close, high, low, close, volume // 3),
            ])
        return tuple(bars)


class FakeMaster:
    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = tokens

    def token(self, symbol: str) -> str:
        try:
            return self._tokens[symbol.strip().upper()]
        except KeyError:
            from acumen.instrument_master import InstrumentMasterError

            raise InstrumentMasterError(f"no {symbol}") from None

    def tick_size(self, symbol: str) -> Decimal:
        self.token(symbol)
        return Decimal("0.05")

    def __len__(self) -> int:
        return len(self._tokens)


def _config(tmp_path: Path, daily_store: DailyStore, **kwargs) -> ub.RunConfig:
    defaults = dict(
        minute_store=MinuteStore.at(tmp_path / "minute_store"),
        daily_store=daily_store,
        ledger_path=tmp_path / "run" / "ledger.json",
        map_data_dir=tmp_path / "data",
        end=END,
        start=START,
        report_path=tmp_path / "report.md",
    )
    defaults.update(kwargs)
    return ub.RunConfig(**defaults)


def _action(symbol: str, ex: date, subject: str) -> ca.CorporateAction:
    return ca.CorporateAction(symbol=symbol, ex_date=ex, subject=subject, source="nse", series="EQ")


# --- era derivation (PURE) --------------------------------------------------------------


#: The real RELIANCE event shape (QUESTIONS.md Q-11), used for the pure era-derivation tests.
RELIANCE_EX = [date(2017, 9, 7), date(2020, 5, 13), date(2023, 7, 20), date(2024, 10, 28)]
RELIANCE_CLAMP = date(2016, 10, 1)
RELIANCE_F = date(2026, 7, 26)


def test_era_intervals_shrink_by_exactly_one_event_per_step() -> None:
    """The map builder can solve at most ONE fresh unknown per era; the intervals must match."""
    intervals = ub.era_intervals(RELIANCE_EX, RELIANCE_CLAMP, RELIANCE_F)

    assert [len(key) for key, _lo, _hi in intervals] == [1, 2, 3, 4], "newest (smallest) first"
    for (key, low, high), (older_key, _l, _h) in zip(intervals, intervals[1:]):
        assert set(key) < set(older_key)
        assert len(older_key) - len(key) == 1
        assert low > high or low <= high  # intervals are well formed
    assert intervals[0][1] == date(2023, 7, 20) and intervals[0][2] == date(2024, 10, 27)
    assert intervals[-1][1] == date(2016, 10, 1)


def test_an_event_at_or_before_the_clamp_creates_no_era() -> None:
    """For D >= clamp, an ex-date <= clamp can never satisfy D < ex, so it fragments nothing."""
    assert ub.era_intervals([date(2015, 1, 1)], RELIANCE_CLAMP, RELIANCE_F) == []


def test_the_identity_era_is_not_probed() -> None:
    intervals = ub.era_intervals([date(2020, 1, 1)], RELIANCE_CLAMP, RELIANCE_F)
    assert len(intervals) == 1  # only the pre-2020 era; [2020-01-01, END] is the identity
    assert intervals[0][0] == (date(2020, 1, 1),)


def test_probe_windows_take_the_last_pre_ex_days_of_each_era() -> None:
    events = (
        va.EventSpec(kind=ca.KIND_DEMERGER, ex_date=DEMERGER_EX,
                     our_price_factor=None, is_share_count=False),
    )
    windows, unprobeable = ub.era_probe_windows(events, DAYS, START, END, per_era=3)

    assert unprobeable == []
    assert len(windows) == 1
    picked = [d for d in DAYS if d < DEMERGER_EX][-3:]
    assert (windows[0].start, windows[0].end) == (picked[0], picked[-1])


def test_an_era_with_no_trading_day_is_reported_unprobeable_not_guessed() -> None:
    """Two ex-dates a day apart leave no probe day between them -- the probe-gap case."""
    first = DEMERGER_EX + timedelta(days=1)   # both land between two weekly trading days,
    second = DEMERGER_EX + timedelta(days=2)  # so the era BETWEEN them holds no probe day
    events = (
        va.EventSpec(kind=ca.KIND_RIGHTS, ex_date=first, our_price_factor=None,
                     is_share_count=False),
        va.EventSpec(kind=ca.KIND_DEMERGER, ex_date=second, our_price_factor=None,
                     is_share_count=False),
    )
    windows, unprobeable = ub.era_probe_windows(events, DAYS, START, END)
    assert unprobeable == [(second,)]
    assert [w.label for w in windows] == [f"pre-{first.isoformat()}"]


# --- the daily cache --------------------------------------------------------------------


def test_the_daily_cache_reads_the_universe_in_one_pass(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000, "BBB": 50000})
    cache = ub.build_daily_cache(store, ["AAA", "BBB"], DAYS[0], DAYS[-1])
    assert set(cache.by_symbol) == {"AAA", "BBB"}
    assert cache.days("AAA") == tuple(DAYS)
    assert cache.first_date("BBB") == DAYS[0]
    assert cache.day("AAA", DAYS[0]).close_paise == 100050
    assert cache.last_before("AAA", DAYS[5]) == DAYS[4]


def test_the_cached_store_adapter_answers_like_the_real_one(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    adapter = ub.CachedDailyStore(cache)
    frame = adapter.daily("AAA", DAYS[0], DAYS[2])
    assert list(frame["trade_date"]) == DAYS[:3]
    assert adapter.daily("AAA", date(1999, 1, 1), date(1999, 1, 2)).empty


# --- the run: routing, mapping, ingest, gates -------------------------------------------


def test_a_bonus_only_symbol_runs_on_the_factor_table_path(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    client = SyntheticVendor(cache, tokens)
    config = _config(tmp_path, store)

    ledger = ub.run_universe(client, FakeMaster(tokens), ["AAA"], (), cache, config, log=lambda m: None)

    record = ledger.records["AAA"]
    assert record.route == ROUTE_TABLE_PATH
    assert record.status == ub.STATUS_SETTLED
    assert record.map_eras == 0
    assert record.gate1_total == len(DAYS)
    assert record.gate1_pass == len(DAYS), "an unadjusted vendor reconciles on every day"
    assert not va.map_path("AAA", config.map_data_dir).is_file()


def test_a_demerger_symbol_is_mapped_before_ingest_and_the_measured_factor_comes_back_out(
    tmp_path: Path,
) -> None:
    """The whole Q-11 chain through the runner: probe -> measure -> build -> ingest -> gate."""
    store = _make_daily_store(tmp_path, {"CCC": 200000})
    cache = ub.build_daily_cache(store, ["CCC"], DAYS[0], DAYS[-1])
    tokens = {"CCC": "3"}
    client = SyntheticVendor(cache, tokens, adjusted={"CCC": (DEMERGER_EX, VENDOR_DEMERGER_FACTOR)})
    config = _config(tmp_path, store)
    actions = (_action("CCC", DEMERGER_EX, "Scheme of Arrangement"),)

    ledger = ub.run_universe(client, FakeMaster(tokens), ["CCC"], actions, cache, config,
                             log=lambda m: None)

    record = ledger.records["CCC"]
    assert record.route == ROUTE_MAP_REQUIRED
    assert record.status == ub.STATUS_SETTLED
    assert record.map_eras == 1 and record.map_eras_provable == 1
    assert [(e.kind, e.price_source) for e in record.map_events] == [
        (ca.KIND_DEMERGER, va.SOURCE_MEASURED)
    ], "a demerger has no factor of ours, so the vendor's must be MEASURED"

    # the map was probed BEFORE the first ingest window
    persisted = va.load_map("CCC", config.map_data_dir)
    assert abs(persisted.eras[0].k_price - VENDOR_DEMERGER_FACTOR) < Decimal("0.000001")
    probe_calls = [c for c in client.calls if c[2] < DEMERGER_EX]
    assert probe_calls and probe_calls[0] == client.calls[0]

    # and the stored minutes are RAW: a pre-ex day folds back onto the raw daily high/low
    pre_ex = [d for d in DAYS if d < DEMERGER_EX][-1]
    bars = config.minute_store.minutes("CCC", pre_ex)
    raw = cache.day("CCC", pre_ex)
    assert max(b.high_paise for b in bars) == raw.high_paise
    assert min(b.low_paise for b in bars) == raw.low_paise
    # Volume is un-adjusted PER BAR and rounded half-even per bar (CONTEXT 7-E11), so a day's
    # sum can sit a share or two off the daily total -- three bars here, so at most three
    # shares. Gate 1's band exists for exactly this; what matters is that it passes.
    assert abs(sum(b.volume for b in bars) - raw.volume) <= len(bars)
    from acumen.quality_gates import volume_gate

    assert volume_gate(raw.volume, sum(b.volume for b in bars)).passed
    assert record.gate1_pass == record.gate1_total == len(DAYS)


def test_a_map_required_symbol_whose_eras_cannot_be_probed_is_refused_not_fallen_back(
    tmp_path: Path,
) -> None:
    """REVIEW_5A F2's teeth: no probeable era means no price oracle, so no ingest at all."""
    store = _make_daily_store(tmp_path, {"DDD": 100000})
    cache = ub.build_daily_cache(store, ["DDD"], DAYS[0], DAYS[-1])
    tokens = {"DDD": "4"}
    client = SyntheticVendor(cache, tokens)
    config = _config(tmp_path, store)
    # the only era boundary sits before every trading day the symbol has
    actions = (_action("DDD", DAYS[0], "Scheme of Arrangement"),)

    ledger = ub.run_universe(client, FakeMaster(tokens), ["DDD"], actions, cache, config,
                             log=lambda m: None)

    record = ledger.records["DDD"]
    assert record.route == ROUTE_MAP_REQUIRED
    assert record.status == ub.STATUS_MAP_UNBUILDABLE
    assert "refusing the price-blind factor-table fallback" in record.note
    assert client.calls == [], "not one candle was fetched for it"
    assert config.minute_store.stored_days("DDD") == ()


def test_a_symbol_missing_from_the_instrument_master_is_recorded_not_crashed(
    tmp_path: Path,
) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)
    client = SyntheticVendor(cache, tokens)

    ledger = ub.run_universe(client, FakeMaster(tokens), ["AAA", "GONE"], (), cache, config,
                             log=lambda m: None)

    assert ledger.records["GONE"].status == ub.STATUS_NO_TOKEN
    assert ledger.records["AAA"].status == ub.STATUS_SETTLED


def test_a_symbol_with_no_daily_equity_history_is_recorded_not_gated(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA", "NEWCO"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1", "NEWCO": "9"}
    config = _config(tmp_path, store)
    client = SyntheticVendor(cache, tokens)

    ledger = ub.run_universe(client, FakeMaster(tokens), ["NEWCO"], (), cache, config,
                             log=lambda m: None)

    assert ledger.records["NEWCO"].status == ub.STATUS_NO_DAILY_HISTORY
    assert client.calls == []


# --- resume ------------------------------------------------------------------------------


def test_the_same_command_resumes_and_refetches_nothing(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)

    first = SyntheticVendor(cache, tokens)
    ub.run_universe(first, FakeMaster(tokens), ["AAA"], (), cache, config, log=lambda m: None)
    assert first.calls, "the first run fetched windows"

    second = SyntheticVendor(cache, tokens)
    ledger = ub.run_universe(second, FakeMaster(tokens), ["AAA"], (), cache, config,
                             log=lambda m: None)

    assert second.calls == [], "a settled symbol is skipped entirely on resume"
    assert ledger.records["AAA"].status == ub.STATUS_SETTLED


def test_an_interrupted_symbol_resumes_at_window_granularity(tmp_path: Path) -> None:
    """The minute store's own window ledger is what makes this true; the run ledger only
    skips whole symbols. A symbol left mid-way refetches only its UNSETTLED windows."""
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)
    master = FakeMaster(tokens)

    # settle the first three windows by hand, as an interrupted run would have left them
    windows = mb.plan_windows(START, END, first_data=DAYS[0])
    partial = SyntheticVendor(cache, tokens)
    mb.backfill_symbol(partial, master, config.minute_store, "AAA", DAYS[0], windows[2][1])
    settled = len(partial.calls)
    assert settled == 3, "three windows settled before the interrupt"

    resumed = SyntheticVendor(cache, tokens)
    ub.run_universe(resumed, master, ["AAA"], (), cache, config, log=lambda m: None)

    assert len(resumed.calls) == len(mb.plan_windows(DAYS[0], END)) - settled
    assert all(call[1] > windows[2][0] for call in resumed.calls)


def test_a_corrupt_run_ledger_names_the_recovery_instead_of_crashing(tmp_path: Path) -> None:
    path = tmp_path / "run" / "ledger.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ub.UniverseBackfillError, match="will not parse"):
        ub.RunLedger.load(path)


# --- quarantine and the halt ceiling ------------------------------------------------------


def _quarantine_config(tmp_path: Path, symbols: list[str]) -> tuple:
    """A universe whose vendor volume is wildly wrong, so gate 1 fails on every day."""
    store = _make_daily_store(tmp_path, {s: 100000 + 1000 * i for i, s in enumerate(symbols)})
    cache = ub.build_daily_cache(store, symbols, DAYS[0], DAYS[-1])
    tokens = {s: str(i + 1) for i, s in enumerate(symbols)}
    return store, cache, tokens


class BadVolumeVendor(SyntheticVendor):
    """Serves candles whose volume is half the daily total -- a permanent gate-1 failure."""

    def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):  # type: ignore[no-untyped-def]
        bars = super().get_candles(token, interval, from_dt, to_dt, exchange=exchange)
        return tuple(
            OneMinuteBar(b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise,
                         b.volume // 2)
            for b in bars
        )


def test_a_symbol_below_the_gate1_floor_is_quarantined_and_the_run_continues(
    tmp_path: Path,
) -> None:
    symbols = [f"S{i:02d}" for i in range(12)]
    store, cache, tokens = _quarantine_config(tmp_path, symbols)
    config = _config(tmp_path, store)

    class OneBadSymbol(SyntheticVendor):
        def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):  # type: ignore[no-untyped-def]
            bars = super().get_candles(token, interval, from_dt, to_dt, exchange=exchange)
            if self._by_token[token] != "S00":
                return bars
            return tuple(
                OneMinuteBar(b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise,
                             b.volume // 2)
                for b in bars
            )

    client = OneBadSymbol(cache, tokens)
    ledger = ub.run_universe(client, FakeMaster(tokens), symbols, (), cache, config,
                             log=lambda m: None)

    assert ledger.records["S00"].status == ub.STATUS_QUARANTINED
    assert ledger.records["S00"].gate1_rate < ub.QUARANTINE_GATE1_MIN_PASS_RATE
    assert "below 80%" in ledger.records["S00"].note
    assert all(ledger.records[s].status == ub.STATUS_SETTLED for s in symbols[1:])
    assert ledger.quarantined() == ["S00"]
    assert not ledger.halted


def test_more_than_ten_percent_quarantined_halts_the_run(tmp_path: Path) -> None:
    symbols = [f"S{i:02d}" for i in range(12)]  # ceiling = int(0.10 * 12) = 1
    store, cache, tokens = _quarantine_config(tmp_path, symbols)
    config = _config(tmp_path, store)
    client = BadVolumeVendor(cache, tokens)

    with pytest.raises(ub.RunHalted, match="systemic fault"):
        ub.run_universe(client, FakeMaster(tokens), symbols, (), cache, config, log=lambda m: None)

    ledger = ub.RunLedger.load(config.ledger_path)
    assert len(ledger.quarantined()) == 2, "halts the moment the ceiling of 1 is exceeded"
    assert ledger.halted
    assert all(s not in ledger.records for s in symbols[2:]), "nothing further was processed"


def test_a_resumed_run_halts_before_fetching_when_it_is_already_over_the_ceiling(
    tmp_path: Path,
) -> None:
    symbols = [f"S{i:02d}" for i in range(12)]
    store, cache, tokens = _quarantine_config(tmp_path, symbols)
    config = _config(tmp_path, store)
    with pytest.raises(ub.RunHalted):
        ub.run_universe(BadVolumeVendor(cache, tokens), FakeMaster(tokens), symbols, (), cache,
                        config, log=lambda m: None)

    resumed = BadVolumeVendor(cache, tokens)
    with pytest.raises(ub.RunHalted, match="ALREADY quarantined"):
        ub.run_universe(resumed, FakeMaster(tokens), symbols, (), cache, config, log=lambda m: None)
    assert resumed.calls == [], "not one request was made on the resumed run"


# --- the report ----------------------------------------------------------------------------


def test_the_report_carries_every_section_the_card_names(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000, "CCC": 200000})
    cache = ub.build_daily_cache(store, ["AAA", "CCC"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1", "CCC": "3"}
    client = SyntheticVendor(cache, tokens, adjusted={"CCC": (DEMERGER_EX, VENDOR_DEMERGER_FACTOR)})
    config = _config(tmp_path, store)
    actions = (_action("CCC", DEMERGER_EX, "Scheme of Arrangement"),)
    ledger = ub.run_universe(client, FakeMaster(tokens), ["AAA", "CCC"], actions, cache, config,
                             log=lambda m: None)

    unknown = ub.unknown_series_sweep(store, ["AAA", "CCC"], DAYS[0], END)
    path = ub.write_report(ledger, ["AAA", "CCC"], unknown, config, generated_at=NOW)
    text = path.read_text(encoding="utf-8")

    assert "# Minute backfill report" in text
    for heading in ("## 1. Headline", "## 2. Route classification", "### Map inventory",
                    "## 3. Depth found, per symbol", "## 4. Exclusions by reason",
                    "## 5. Gate 3", "## 6. Unknown series", "## 7. Disclosures"):
        assert heading in text, heading
    assert "TOTAL coverage" in text
    assert ROUTE_TABLE_PATH in text and ROUTE_MAP_REQUIRED in text
    # The synthetic vendor scaled price AND volume by the same demerger factor. The price side has no
    # ``ours`` for a demerger, so it is MEASURED; the volume side takes that same proven factor under
    # the Q-12 ruling's candidate order (ours > chosen-price-factor > measured-minimum > absent)
    # instead of re-measuring an observable the pre-open auction biases.
    assert f"demerger@{DEMERGER_EX.isoformat()}: measured/price-factor" in text
    assert "survivorship" in text.lower()
    assert str(len(DAYS)) in text


def test_the_report_is_regenerable_from_the_ledger_alone(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)
    ub.run_universe(SyntheticVendor(cache, tokens), FakeMaster(tokens), ["AAA"], (), cache,
                    config, log=lambda m: None)

    reloaded = ub.RunLedger.load(config.ledger_path)
    first = ub.build_report(reloaded, ["AAA"], None, generated_at=NOW, config=config)
    second = ub.build_report(reloaded, ["AAA"], None, generated_at=NOW, config=config)
    assert first == second, "the report is a pure function of the ledger and the sweep"
    assert "AAA" in first


def test_the_staleness_banner_hands_over_a_regate_command_that_actually_works(
    tmp_path: Path,
) -> None:
    """**REVIEW_9B_FIXES R4.** The banner is the only place the report tells an operator how to
    clear a stale marker, and it handed over the BARE `--regate`. Measured by the review: that
    command resolves the universe from the cached F&O endpoint (208 symbols against the
    register's sealed 210, missing EXIDEIND and NUVAMA) and overwrites the committed sealed
    report. It also told the reader the coverage was "understated", which was written for the
    Q-14 gate-1P bump and is the WRONG DIRECTION for the Q-21(a) completion now in force -- that
    one can only turn passing days into failures, so a stale row's printed coverage is
    OVERSTATED."""
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    config = _config(tmp_path, store)
    ub.run_universe(SyntheticVendor(cache, {"AAA": "1"}), FakeMaster({"AAA": "1"}), ["AAA"], (),
                    cache, config, log=lambda m: None)
    ledger = ub.RunLedger.load(config.ledger_path)

    current = ub.build_report(ledger, ["AAA"], None, generated_at=NOW, config=config)
    ledger.records["AAA"].gate_definition = "some-older-definition"
    stale = ub.build_report(ledger, ["AAA"], None, generated_at=NOW, config=config)

    assert "have NOT been re-gated" not in current  # a current row raises no banner at all
    assert "have NOT been re-gated" in stale
    # BOTH mandatory flags, and the snapshot named from the constant rather than typed in prose
    assert f"--universe-snapshot {ub.SEALED_UNIVERSE_SNAPSHOT}" in stale
    assert ub.SEALED_UNIVERSE_SNAPSHOT == "docs/recovery/sealed_universe_210.json"
    assert "--report-path" in stale and "NOT the committed report" in stale
    assert "EXIDEIND and NUVAMA" in stale  # what the bare command would silently leave behind
    # the DIRECTION, for the bump actually in force -- the old claim is gone, not merely hedged
    assert "OVERSTATED" in stale
    assert "coverage above is understated" not in stale


def test_the_ledger_round_trips_through_json(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger = ub.RunLedger(path=path, started="2026-07-26T08:00:00")
    ledger.record(
        ub.SymbolRecord(symbol="ZZZ", status=ub.STATUS_SETTLED, route=ROUTE_MAP_REQUIRED,
                        route_reasons=["demerger ex 2020-06-03"], gate1_pass=9, gate1_total=10,
                        map_events=[ub.MapEvent("demerger", "2020-06-03", "measured", "measured")])
    )
    reloaded = ub.RunLedger.load(path)
    record = reloaded.records["ZZZ"]
    assert record.route == ROUTE_MAP_REQUIRED
    assert record.route_reasons == ["demerger ex 2020-06-03"]  # noqa: E501
    assert record.map_events[0].price_source == "measured"
    assert record.gate1_rate == Decimal(9) / Decimal(10)
    assert json.loads(path.read_text(encoding="utf-8"))["symbols"]["ZZZ"]["status"] == "settled"


def test_an_older_ledger_missing_a_field_still_loads(tmp_path: Path) -> None:
    """A resumed run must not die because this session added a column."""
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({
        "started": "x", "halted": "",
        "symbols": {"ZZZ": {"symbol": "ZZZ", "status": "settled", "a_field_we_dropped": 1}},
    }), encoding="utf-8")
    assert ub.RunLedger.load(path).records["ZZZ"].status == "settled"


# --- the oracle gate ------------------------------------------------------------------------


def test_the_run_refuses_to_start_on_an_unverified_daily_store(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    store.month_path(DAYS[0]).unlink()  # the REVIEW_2 F7 damage
    with pytest.raises(ub.UniverseBackfillError, match="oracle"):
        ub.verify_the_oracle(store, log=lambda m: None, min_rows=0)


def test_a_clean_daily_store_passes_the_oracle_check(tmp_path: Path) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    # min_rows=0: this fixture publishes one synthetic symbol a day, not a full market. The
    # production run uses the real MIN_ROWS_PER_DATE floor (pinned in test_daily_store_verify).
    ub.verify_the_oracle(store, log=lambda m: None, min_rows=0)  # must not raise


# --- gate 3 must CHAIN events that share an ex-date (the measured 360ONE case) ------------


def _share_count_factor(kind: str, ex: date, k: str, symbol: str = "AAA") -> ca.Factor:
    return ca.Factor(symbol=symbol, ex_date=ex, kind=kind, k=Decimal(k), basis=f"{kind} {k}")


def test_two_events_on_one_ex_date_are_multiplied_not_tested_separately() -> None:
    """360ONE, measured live 2026-07-26: a 1:1 bonus AND a face-value split 2->1 BOTH ex
    2023-03-02, so the raw price falls to a QUARTER. Testing either 0.5 alone reports a bogus
    50% break on a series that is perfectly continuous (CONTEXT 4.2: "chain multiple events")."""
    factors = (
        _share_count_factor(ca.KIND_BONUS, date(2023, 3, 2), "0.5"),
        _share_count_factor(ca.KIND_SPLIT, date(2023, 3, 2), "0.5"),
    )
    grouped = ub.share_count_factors_by_ex_date("AAA", factors)
    assert grouped == {date(2023, 3, 2): (Decimal("0.25"), (ca.KIND_BONUS, ca.KIND_SPLIT))}

    tally = ub.GateTally(closes={date(2023, 3, 1): 400000, date(2023, 3, 2): 100000})
    ub.gate3_over_events(tally, "AAA", factors)

    assert tally.gate3_checked == 1, "one ex-date, one check -- not one per factor"
    assert tally.gate3_failed == 0, "0.5 x 0.5 = 0.25 makes the quartering continuous"


def test_gate3_still_catches_a_genuinely_broken_series() -> None:
    factors = (_share_count_factor(ca.KIND_BONUS, date(2023, 3, 2), "0.5"),)
    tally = ub.GateTally(closes={date(2023, 3, 1): 400000, date(2023, 3, 2): 100000})
    ub.gate3_over_events(tally, "AAA", factors)
    assert tally.gate3_checked == 1 and tally.gate3_failed == 1
    assert "never an ordinary market move" in tally.gate3_failures[0]


def test_gate3_ignores_ordinary_dividends_and_other_symbols() -> None:
    factors = (
        _share_count_factor(ca.KIND_BONUS, date(2023, 3, 2), "1"),          # k == 1: no step
        ca.Factor(symbol="AAA", ex_date=date(2023, 4, 1), kind=ca.KIND_DIVIDEND,
                  k=Decimal("0.97"), basis="special"),                       # not share-count
        _share_count_factor(ca.KIND_BONUS, date(2023, 3, 2), "0.5", symbol="OTHER"),
    )
    assert ub.share_count_factors_by_ex_date("AAA", factors) == {}


def test_gate3_skips_an_ex_date_outside_the_stored_span() -> None:
    factors = (_share_count_factor(ca.KIND_BONUS, date(2015, 1, 1), "0.5"),)
    tally = ub.GateTally(closes={date(2023, 3, 1): 400000, date(2023, 3, 2): 100000})
    ub.gate3_over_events(tally, "AAA", factors)
    assert tally.gate3_checked == 0


# --- the CONTEXT 4.5 gate-2 completeness redefinition, through the runner ------------------
#
# The synthetic vendor emits THREE bars per day whose fold reproduces the daily high/low/volume
# exactly. That is 372 of 375 session minutes absent on every single day -- the exact shape the
# architect's completeness ruling is about, and it was already in this fixture before the ruling
# existed. Pre-ruling, gate 2 excluded every one of those days. Now gate 1 reconciles them, so they
# are INCLUDED and the absent stamps are counted as liquidity.


def test_gate2_a_gate1_passing_day_with_tradeless_minutes_is_included_and_counted(
    tmp_path: Path,
) -> None:
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)
    ledger = ub.run_universe(SyntheticVendor(cache, tokens), FakeMaster(tokens), ["AAA"], (),
                             cache, config, log=lambda m: None)

    record = ledger.records["AAA"]
    assert record.status == ub.STATUS_SETTLED
    assert record.gate1_pass == record.gate1_total == len(DAYS)
    assert record.gate2_excluded == 0, "gate 1 reconciles every day, so nothing is data loss"
    assert record.liquidity_days == record.depth_days, "every day carries tradeless minutes"
    assert record.gate2_missing == 0
    assert record.median_minutes_per_day == 3 and record.min_minutes_per_day == 3
    assert record.gate_definition == ub.GATE_DEFINITION


def test_gate2_still_excludes_a_missing_minute_day_when_gate1_also_fails(tmp_path: Path) -> None:
    """The other half of the ruling: where gate 1 FAILS, absent stamps are indistinguishable from
    data loss and the day is still excluded. Same 372-missing-minute days as the test above -- only
    the gate-1 verdict differs. (12 symbols so one quarantine stays under the halt ceiling.)"""
    symbols = [f"S{i:02d}" for i in range(12)]
    store, cache, tokens = _quarantine_config(tmp_path, symbols)
    config = _config(tmp_path, store)

    class OneBadSymbol(SyntheticVendor):
        def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):  # type: ignore[no-untyped-def]
            bars = super().get_candles(token, interval, from_dt, to_dt, exchange=exchange)
            if self._by_token[token] != "S00":
                return bars
            return tuple(
                OneMinuteBar(b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise,
                             b.volume // 2)
                for b in bars
            )

    ledger = ub.run_universe(OneBadSymbol(cache, tokens), FakeMaster(tokens), symbols, (),
                             cache, config, log=lambda m: None)

    bad = ledger.records["S00"]
    assert bad.status == ub.STATUS_QUARANTINED
    assert bad.gate1_pass == 0
    assert bad.gate2_excluded == bad.depth_days
    assert bad.gate2_missing == bad.depth_days
    assert bad.liquidity_days == 0, "a day gate 1 rejects is never counted as liquidity"
    # ... while its 11 neighbours, with the SAME 3-bar days, are included and counted as liquidity.
    good = ledger.records["S01"]
    assert good.status == ub.STATUS_SETTLED
    assert good.gate2_excluded == 0 and good.liquidity_days == good.depth_days


# --- the Q-12-addendum quarantine-recovery reroute -----------------------------------------

#: A bonus whose SUBJECT says 1:1 (our CONTEXT 4.2 factor 0.5) while the vendor actually applied
#: 0.9 -- the ruling's "unrecorded or vendor-variant event". Routing sends a bonus-only symbol down
#: the cheap table path, which has no price oracle, so our wrong 0.5 divides every pre-ex price and
#: gate 1 fails the whole pre-ex span. Only the map's probes can see it.
VARIANT_EX = DAYS[20]
VENDOR_VARIANT_FACTOR = Decimal("0.9")


def _variant_setup(tmp_path: Path):
    store = _make_daily_store(tmp_path, {"TTT": 100000})
    cache = ub.build_daily_cache(store, ["TTT"], DAYS[0], DAYS[-1])
    tokens = {"TTT": "1"}
    client = SyntheticVendor(cache, tokens, adjusted={"TTT": (VARIANT_EX, VENDOR_VARIANT_FACTOR)})
    actions = (_action("TTT", VARIANT_EX, "Bonus 1:1"),)
    return store, cache, tokens, client, actions


def test_a_quarantined_table_path_symbol_is_rerouted_through_the_map_and_recovers(
    tmp_path: Path,
) -> None:
    """The Q-12 addendum ruling, end to end.

    TTT routes table-path (bonus only). Our factor 0.5 is not what the vendor used, so the ingest
    stores a 1.8x-wrong price and a 44%-short volume on every pre-ex day; gate 1 fails them all and
    the symbol quarantines at ~50%. The reroute then probes its eras, measures the vendor's real
    0.9, applies it to the ALREADY-STORED days by the NET factor 0.9/0.5 = 1.8 in one division, and
    gate 1 passes on every day -- so the symbol settles.

    (Gate 3 still reports a break across the ex-date and that is CORRECT: our CONTEXT 4.2 factor
    genuinely is wrong for this symbol. The reroute recovers the DATA; it does not pretend the
    factor table is right.)
    """
    store, cache, tokens, client, actions = _variant_setup(tmp_path)
    config = _config(tmp_path, store)
    ledger = ub.run_universe(client, FakeMaster(tokens), ["TTT"], actions, cache, config,
                             log=lambda m: None)

    record = ledger.records["TTT"]
    assert record.status == ub.STATUS_SETTLED, record.note
    assert record.reroute_attempted is True
    assert record.route == ROUTE_MAP_REQUIRED
    assert "quarantine-recovery (Q-12 addendum ruling)" in record.route_reasons
    # the BEFORE numbers are kept, so the recovery is auditable rather than merely different
    assert record.prior_status == ub.STATUS_QUARANTINED
    assert record.prior_gate1_pass < record.gate1_pass
    assert record.gate1_pass == record.gate1_total == len(DAYS)
    assert "gate 1" in record.reroute_note

    # the map that did it is on disk, with the vendor's real factor and its provenance
    amap = va.load_map("TTT", data_dir=config.map_data_dir)
    assert va.map_is_current(amap)
    choice = amap.eras[0].choices[0]
    assert choice.price_source == va.SOURCE_MEASURED
    assert choice.price_factor == pytest.approx(VENDOR_VARIANT_FACTOR, abs=Decimal("0.0005"))
    assert choice.volume_source == va.SOURCE_PRICE_FACTOR

    # and the stored prices really are RAW now, to the paisa, on a pre-ex day
    day = DAYS[0]
    row = cache.day("TTT", day)
    assert row is not None
    stored = config.minute_store.minutes("TTT", day)
    assert max(b.high_paise for b in stored) == row.high_paise
    assert min(b.low_paise for b in stored) == row.low_paise
    # Volume is recovered per BAR, so the day's sum can differ from the daily total by at most one
    # share per bar (three here) -- three orders of magnitude inside gate 1's own band, which is why
    # gate 1 passes on every day above.
    assert abs(sum(b.volume for b in stored) - row.volume) <= len(stored)


def test_the_reroute_runs_once_and_a_resume_neither_re_probes_nor_re_divides(
    tmp_path: Path,
) -> None:
    """Idempotence on the fetched store, which is what makes the reroute safe to leave in the run.

    After the recovery, a resumed run finds nothing owed (the gate definition, the map's estimator
    marker and its fetch date all match), so it processes NOTHING and makes no request. Forcing the
    symbol back through ``process_symbol`` is also a no-op: the identity guard sees a store that is
    already raw, the net factor is 1, and not one day is rewritten -- so the prices cannot be
    divided a second time.
    """
    store, cache, tokens, client, actions = _variant_setup(tmp_path)
    config = _config(tmp_path, store)
    ub.run_universe(client, FakeMaster(tokens), ["TTT"], actions, cache, config, log=lambda m: None)
    day = DAYS[0]
    after_first = [b.high_paise for b in config.minute_store.minutes("TTT", day)]

    resumed = SyntheticVendor(cache, tokens, adjusted={"TTT": (VARIANT_EX, VENDOR_VARIANT_FACTOR)})
    ledger = ub.RunLedger.load(config.ledger_path)
    assert ub.needs_reprocessing(ledger.records["TTT"], config) is None
    ub.run_universe(resumed, FakeMaster(tokens), ["TTT"], actions, cache, config,
                    log=lambda m: None)
    assert resumed.calls == [], "a settled, current symbol costs no request on a resume"

    forced = SyntheticVendor(cache, tokens, adjusted={"TTT": (VARIANT_EX, VENDOR_VARIANT_FACTOR)})
    amap = va.load_map("TTT", data_dir=config.map_data_dir)
    applied = mb.rebuild_symbol_raw_with_map(
        config.minute_store, store, "TTT", amap, tick_paise=5,
        applied_factors=mb.SymbolFactors.identity("TTT", tick_paise=5),
    )
    assert applied.days_rewritten == 0, "an already-raw store is never divided again"
    assert [b.high_paise for b in config.minute_store.minutes("TTT", day)] == after_first
    assert forced.calls == []


def test_a_map_built_under_the_superseded_estimator_is_rebuilt_not_consumed(
    tmp_path: Path,
) -> None:
    """The Q-12 staleness marker, through the runner. A map file written before the ruling carries
    no ``volume_estimator`` key; the run must rebuild it from probe windows rather than consume its
    median-derived factors -- and must say so, so the operator sees why a settled symbol re-ran."""
    store, cache, tokens, client, actions = _variant_setup(tmp_path)
    config = _config(tmp_path, store)
    ub.run_universe(client, FakeMaster(tokens), ["TTT"], actions, cache, config, log=lambda m: None)

    path = va.map_path("TTT", config.map_data_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("volume_estimator")  # exactly what a pre-ruling map file looks like
    path.write_text(json.dumps(payload), encoding="utf-8")

    ledger = ub.RunLedger.load(config.ledger_path)
    why = ub.needs_reprocessing(ledger.records["TTT"], config)
    assert why is not None and "superseded estimator" in why

    logged: list[str] = []
    resumed = SyntheticVendor(cache, tokens, adjusted={"TTT": (VARIANT_EX, VENDOR_VARIANT_FACTOR)})
    ledger = ub.run_universe(resumed, FakeMaster(tokens), ["TTT"], actions, cache, config,
                             log=logged.append)
    assert any("map is STALE" in line and va.MAP_VOLUME_ESTIMATOR in line for line in logged), (
        "the log must name BOTH markers -- a map can be stale on the model alone (Q-11 addendum 4)"
        " and the old message always blamed the estimator"
    )
    assert va.map_is_current(va.load_map("TTT", data_dir=config.map_data_dir))
    assert ledger.records["TTT"].status == ub.STATUS_SETTLED
    assert ledger.records["TTT"].gate1_pass == len(DAYS), "still raw after the rebuild"


def test_needs_reprocessing_flags_a_pre_ruling_row_and_clears_after_the_pass(
    tmp_path: Path,
) -> None:
    """A row written before the completeness ruling carries a different gate marker, so a resume
    RE-GATES it from the stored candles -- no window refetched -- and then stops flagging it."""
    store = _make_daily_store(tmp_path, {"AAA": 100000})
    cache = ub.build_daily_cache(store, ["AAA"], DAYS[0], DAYS[-1])
    tokens = {"AAA": "1"}
    config = _config(tmp_path, store)
    ub.run_universe(SyntheticVendor(cache, tokens), FakeMaster(tokens), ["AAA"], (), cache, config,
                    log=lambda m: None)

    ledger = ub.RunLedger.load(config.ledger_path)
    assert ub.needs_reprocessing(ledger.records["AAA"], config) is None
    # rewind the row to the pre-ruling state: the marker absent and gate 2 excluding every day
    ledger.records["AAA"].gate_definition = ""
    ledger.records["AAA"].gate2_excluded = len(DAYS)
    ledger.records["AAA"].liquidity_days = 0
    ledger.save()

    stale = ub.RunLedger.load(config.ledger_path)
    why = ub.needs_reprocessing(stale.records["AAA"], config)
    assert why is not None and "gate definition" in why

    resumed = SyntheticVendor(cache, tokens)
    reledger = ub.run_universe(resumed, FakeMaster(tokens), ["AAA"], (), cache, config,
                               log=lambda m: None)
    record = reledger.records["AAA"]
    assert resumed.calls == [], "re-gating reads the store; it never refetches a window"
    assert record.gate_definition == ub.GATE_DEFINITION
    assert record.gate2_excluded == 0 and record.liquidity_days == record.depth_days
    assert record.prior_gate2_excluded == len(DAYS), "the BEFORE number is kept for the report"
    assert ub.needs_reprocessing(record, config) is None, "self-clearing"


# --- the failure-pattern analysis (PURE) ---------------------------------------------------


def _tally_with(failing: set[date], gap: Decimal, volume: int = 9000) -> ub.GateTally:
    tally = ub.GateTally()
    for day in DAYS:
        tally.gate1_total += 1
        tally.gate1_days.append(day)
        tally.gate1_volumes.append(volume)
        tally.closes[day] = 100000
        if day in failing:
            tally.gate1_failures.append((day, gap, volume))
        else:
            tally.gate1_pass += 1
    return tally


def test_failure_profile_calls_a_whole_pre_ex_era_an_adjustment_problem() -> None:
    """Every day before the ex-date fails and every day after it passes -- one wrong factor applied
    to a whole span, which is what the ruling means by "clustered before a CA ex-date"."""
    profile = ub.gate1_failure_profile(
        _tally_with({d for d in DAYS if d < VARIANT_EX}, Decimal("44.4")), [VARIANT_EX]
    )
    assert profile.verdict == ub.PATTERN_CLUSTERED
    assert profile.above_ceiling == profile.failures  # all above +5.0%
    assert "whole span" in profile.detail


def test_failure_profile_calls_thin_scattered_days_an_auction_liquidity_shape() -> None:
    """A handful of failures spread across both eras, all above the +5.0% ceiling, on days whose raw
    daily volume is far below the symbol's own median: the auction share of a thin day."""
    tally = _tally_with(set(), Decimal("0"))
    thin = [DAYS[3], DAYS[9], DAYS[25], DAYS[33]]
    tally.gate1_failures = [(d, Decimal("7.5"), 300) for d in thin]
    tally.gate1_pass = tally.gate1_total - len(thin)
    profile = ub.gate1_failure_profile(tally, [VARIANT_EX])
    assert profile.verdict == ub.PATTERN_SCATTERED
    assert profile.above_ceiling == 4 and profile.below_floor == 0
    assert profile.median_volume_above_ceiling == 300 < profile.median_volume_all
    assert "auction share of a thin day" in profile.detail


def test_failure_profile_reports_no_failure_as_nothing_to_explain() -> None:
    profile = ub.gate1_failure_profile(_tally_with(set(), Decimal("0")), [VARIANT_EX])
    assert profile.verdict == ub.PATTERN_NONE and profile.failures == 0


def test_the_report_carries_the_before_after_table_and_the_deferred_ceiling_evidence(
    tmp_path: Path,
) -> None:
    """The two report sections the rulings owe the architect."""
    store, cache, tokens, client, actions = _variant_setup(tmp_path)
    config = _config(tmp_path, store)
    ledger = ub.run_universe(client, FakeMaster(tokens), ["TTT"], actions, cache, config,
                             log=lambda m: None)
    unknown = ub.unknown_series_sweep(store, ["TTT"], DAYS[0], END)
    text = ub.write_report(ledger, ["TTT"], unknown, config, generated_at=NOW).read_text(
        encoding="utf-8"
    )

    assert "### 3a. BEFORE / AFTER the 2026-07-26 rulings" in text
    assert "### 3b. Traded-minute statistics per symbol" in text
    assert "### Gate 2 redefined" in text
    assert "no minimum traded" in text.lower() or "NO liquidity filter" in text
    assert "quarantine-recovery" in text
    assert "the -0.1% floor is NOT widened" in text or "[-0.1%, 5.0%]" in text
    # the band is quoted from the constants, so a widened band would show up here
    assert "-0.1%" in text and "5.0%" in text
