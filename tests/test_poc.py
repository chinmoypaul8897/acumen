"""Chunk 6 -- the POC engine (CONTEXT 3.3), its goldens F6 / F7 and its boundaries.

Everything here is OFFLINE and frozen:

* **F6** is TradingView's own documented row example (CONTEXT 8 F6, CONTEXT 5) -- 100 ticks at
  N=30 and at N=25 -- asserted on the ROW EDGES and the remainder shape, not just the counts.
* **F7** is the 22-Jul-2026 calibration, driven from the frozen ``poc/data/*_1min.csv`` files
  (CONTEXT 8: "the CSVs are the authoritative input") with the per-symbol ticks from the frozen
  ``tests/fixtures/tick_sizes.json`` (QUESTIONS.md Q-2's architect ruling). Both halves of F7
  are asserted: (a) the recomputed prorata POC reproduces the frozen printout to +-0.01, and
  (b) on every calibration day prorata is the candidate NEAREST the trader's TradingView
  reading -- no alternative spreading method in the frozen summary is closer.
* the **property** -- the prorata spread conserves volume EXACTLY -- is asserted on all 25
  frozen symbol-days, under both windows.
* the **window validity** rule is the AMENDED one (QUESTIONS.md, 2026-07-26): a day yields a
  POC iff it passes gate 1. There is no minute count anywhere, and the test that used to be
  "6 missing minutes -> no POC" is inverted here on purpose, with the ruling quoted.

The 1-minute CSVs are read back through the REAL ingest parser
(:func:`acumen.smartapi_client.parse_candles`), so these tests exercise the same +05:30 ->
naive-IST normalization and the same Decimal-exact paise the store holds.
"""

from __future__ import annotations

import ast
import csv
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import poc
from acumen import smartapi_client as sac
from acumen.instrument_master import InstrumentMaster

REPO_ROOT = Path(__file__).resolve().parents[1]
POC_DATA = REPO_ROOT / "poc" / "data"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TICK_FIXTURE = FIXTURES / "tick_sizes.json"

#: The trader's Row Size (CONTEXT 3.3; config.yaml carries it, confirmed by his Q32 screenshot).
ROW_SIZE = 24

#: CONTEXT 8 F7: the five calibration anchors -- symbol, day, the frozen 2-dp printout, and the
#: trader's own TradingView reading. HDFCBANK's midpoint is 815.275, legally off-grid
#: (CONTEXT 3.3), and the printout carried it as 815.27.
F7_ANCHORS: tuple[tuple[str, str, str, str], ...] = (
    ("TCS", "2026-07-14", "2205.25", "2205.3"),
    ("RELIANCE", "2026-07-16", "1303.60", "1303.7"),
    ("HDFCBANK", "2026-07-14", "815.27", "815.3"),
    ("DIXON", "2026-07-16", "14263.50", "14267"),
    ("MANAPPURAM", "2026-07-15", "329.75", "329.75"),
)

#: CONTEXT 8 F7 (a): "matches the poc-run printout to +-0.01".
F7_TOLERANCE = Decimal("0.01")


# --- frozen-fixture loading -------------------------------------------------------------


def _ticks() -> dict[str, int]:
    """The frozen F7 tick sizes, in PAISE. Test input only -- src/ reads the instrument master."""
    raw = json.loads(TICK_FIXTURE.read_text(encoding="utf-8"))
    return {
        symbol: int(Decimal(str(rupees)) * 100)
        for symbol, rupees in raw.items()
        if not symbol.startswith("_")
    }


def _bars(symbol: str, day: str) -> tuple[sac.OneMinuteBar, ...]:
    """One frozen poc/data day, parsed through the real ingest path (naive IST, paise)."""
    path = POC_DATA / f"{symbol}_{day}_1min.csv"
    rows: list[list] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(
                [
                    record["ts"].strip(),
                    record["open"],
                    record["high"],
                    record["low"],
                    record["close"],
                    int(record["volume"]),
                ]
            )
    return sac.parse_candles(rows)


def _summary() -> list[dict[str, str]]:
    with (POC_DATA / "volume_poc_summary.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _profile(symbol: str, day: str, *, window: poc.ProfileWindow = poc.SPEC_WINDOW) -> poc.DayProfile:
    return poc.day_profile(
        _bars(symbol, day),
        date.fromisoformat(day),
        row_size=ROW_SIZE,
        tick_paise=_ticks()[symbol],
        volume_reconciled=True,  # every calibration day passes gate 1 (F10, chunk 5A)
        window=window,
    )


def _synthetic(day: date, minutes: list[tuple[str, int, int, int, int, int]]) -> list[sac.OneMinuteBar]:
    """Build bars from ``(HH:MM, open, high, low, close, volume)`` tuples in integer paise."""
    bars: list[sac.OneMinuteBar] = []
    for stamp, o, h, low, c, v in minutes:
        hour, minute = (int(part) for part in stamp.split(":"))
        bars.append(
            sac.OneMinuteBar(
                stamp=datetime.combine(day, poc.SESSION_OPEN).replace(hour=hour, minute=minute),
                open_paise=o,
                high_paise=h,
                low_paise=low,
                close_paise=c,
                volume=v,
            )
        )
    return bars


# --- the window (CONTEXT 3.3 / R1-Q11; QUESTIONS.md Q-8 keeps it a parameter) -----------


def test_the_spec_window_is_the_8_candle_0915_to_1114_window() -> None:
    """CONTEXT 3.3 / R1-Q11: stamps 09:15..11:14 inclusive = the first EIGHT 15-min candles."""
    assert poc.SPEC_WINDOW.candles == 8
    assert poc.SPEC_WINDOW.first_time.isoformat() == "09:15:00"
    assert poc.SPEC_WINDOW.last_time.isoformat() == "11:14:00"


def test_the_alternate_window_is_the_9_candle_evidence_window_and_is_never_a_default() -> None:
    """QUESTIONS.md Q-8 (Round-3 Q42): the 9-candle reading ends at the 11:29 stamp.

    It exists so the chunk-6 gate can print both answers; the DEFAULT of every entry point
    stays the spec window until Q42 returns.
    """
    assert poc.ALTERNATE_WINDOW.candles == 9
    assert poc.ALTERNATE_WINDOW.last_time.isoformat() == "11:29:00"
    import inspect

    for function in (poc.window_bars, poc.day_profile):
        default = inspect.signature(function).parameters["window"].default
        assert default is poc.SPEC_WINDOW, f"{function.__name__} must default to the spec window"


def test_the_window_slice_takes_0915_through_1114_and_drops_the_1115_stamp() -> None:
    day = date(2026, 7, 14)
    bars = _bars("TCS", "2026-07-14")
    selected = poc.window_bars(bars, day)
    assert len(selected) == 120  # eight complete 15-minute candles
    assert selected[0].stamp.time().isoformat() == "09:15:00"
    assert selected[-1].stamp.time().isoformat() == "11:14:00"
    assert all(bar.stamp.time().isoformat() != "11:15:00" for bar in selected)


def test_the_nine_candle_window_adds_exactly_the_1115_to_1129_stamps() -> None:
    day = date(2026, 7, 14)
    bars = _bars("TCS", "2026-07-14")
    spec = poc.window_bars(bars, day)
    wider = poc.window_bars(bars, day, window=poc.ALTERNATE_WINDOW)
    assert len(wider) == len(spec) + 15
    assert wider[-1].stamp.time().isoformat() == "11:29:00"


def test_the_window_refuses_a_tz_aware_stamp_and_a_foreign_trade_date() -> None:
    day = date(2026, 7, 14)
    bars = _bars("TCS", "2026-07-14")
    with pytest.raises(poc.PocError, match="one trade date at a time|another date|feed one trade"):
        poc.window_bars(bars, date(2026, 7, 15))
    aware = [bar for bar in bars[:1]]
    aware[0] = sac.OneMinuteBar(
        stamp=bars[0].stamp.replace(tzinfo=__import__("datetime").timezone.utc),
        open_paise=1,
        high_paise=1,
        low_paise=1,
        close_paise=1,
        volume=1,
    )
    with pytest.raises(poc.PocError, match="naive IST"):
        poc.window_bars(aware, day)


def test_a_duplicate_stamp_inside_the_window_is_refused_not_double_counted() -> None:
    day = date(2026, 7, 14)
    bars = list(_bars("TCS", "2026-07-14")[:3])
    bars.append(bars[0])
    with pytest.raises(poc.PocError, match="duplicate"):
        poc.window_bars(bars, day)


def test_a_window_running_past_the_session_close_is_refused() -> None:
    with pytest.raises(poc.PocError, match="session close"):
        poc.ProfileWindow(name="absurd", candles=26)


# --- F6: TradingView's documented row example (CONTEXT 8 F6, CONTEXT 5) -----------------


@pytest.mark.parametrize("tick_paise", sorted(set(_ticks().values())))
def test_f6_100_ticks_at_n30_gives_34_rows_of_3_plus_a_1_tick_remainder(tick_paise: int) -> None:
    """CONTEXT 8 F6 / CONTEXT 5: 100 ticks, N=30 -> tpr=3 -> 33 rows of 3 + 1 row of 1 = 34.

    Row EDGES and the remainder SHAPE are asserted, not merely the count -- a wrong stacking
    that happened to produce 34 rows would still be wrong. Parametrized over every tick in the
    frozen fixture: the row SHAPE is tick-independent, the row EDGES scale with the tick.
    """
    bottom = 100_000
    grid = poc.build_rows(
        top_paise=bottom + 100 * tick_paise,
        bottom_paise=bottom,
        row_size=30,
        tick_paise=tick_paise,
    )
    assert grid.total_ticks == 100
    assert grid.ticks_per_row == 3
    assert len(grid.rows) == 34

    assert [row.ticks for row in grid.rows] == [3] * 33 + [1]
    for index, row in enumerate(grid.rows[:33]):
        assert row.lo_paise == bottom + index * 3 * tick_paise
        assert row.hi_paise == bottom + (index + 1) * 3 * tick_paise
    remainder = grid.rows[-1]
    assert remainder.lo_paise == bottom + 99 * tick_paise
    assert remainder.hi_paise == bottom + 100 * tick_paise
    assert remainder.hi_paise == grid.top_paise  # the rows reach exactly the top

    # every row is contiguous with the next -- no gap, no overlap
    for lower, upper in zip(grid.rows, grid.rows[1:]):
        assert lower.hi_paise == upper.lo_paise


@pytest.mark.parametrize("tick_paise", sorted(set(_ticks().values())))
def test_f6_100_ticks_at_n25_gives_25_rows_of_4_with_no_remainder(tick_paise: int) -> None:
    """CONTEXT 8 F6: 100 ticks, N=25 -> tpr=4 -> 25 rows of 4, the last one FULL."""
    bottom = 100_000
    grid = poc.build_rows(
        top_paise=bottom + 100 * tick_paise,
        bottom_paise=bottom,
        row_size=25,
        tick_paise=tick_paise,
    )
    assert grid.ticks_per_row == 4
    assert len(grid.rows) == 25
    assert [row.ticks for row in grid.rows] == [4] * 25
    assert grid.rows[0].lo_paise == bottom
    assert grid.rows[-1].hi_paise == bottom + 100 * tick_paise


def test_the_tpr_direction_is_the_one_whose_row_count_lands_closest_to_n() -> None:
    """CONTEXT 3.3: "direction chosen so the realized row count is closest to requested N".

    100/30 = 3.33: rounding DOWN to 3 realizes 34 rows (4 away from 30); rounding UP to 4
    realizes 25 (5 away). TradingView's own example takes 3 -- so the rule is not "round the
    quotient", it is "count both and pick the closer".
    """
    assert poc.ticks_per_row(100, 30) == 3  # 34 rows beats 25 rows
    assert poc.ticks_per_row(100, 25) == 4  # exact
    # 121/24 = 5.04: down->5 realizes 25 rows (1 away), up->6 realizes 21 (3 away)
    assert poc.ticks_per_row(121, 24) == 5
    # 130/24 = 5.42: down->5 realizes 26 (2 away), up->6 realizes 22 (2 away) -- a tie keeps
    # the finer profile, the same direction TV's documented example takes
    assert poc.ticks_per_row(130, 24) == 5


def test_tpr_is_floored_at_one_so_a_narrow_range_is_never_zero_ticks_per_row() -> None:
    """CONTEXT 3.3: "rounded to a whole number (minimum 1)"."""
    assert poc.ticks_per_row(5, 24) == 1
    assert poc.ticks_per_row(1, 24) == 1


# --- boundaries (the card's four) --------------------------------------------------------


def test_a_price_exactly_on_a_row_edge_belongs_to_the_row_above_it() -> None:
    """CONTEXT 3.3: rows are half-open ``[lo, hi)`` -- an edge price is the LOWER bound of the
    row above, never the upper bound of the row below."""
    grid = poc.build_rows(top_paise=1000, bottom_paise=900, row_size=10, tick_paise=10)
    assert grid.ticks_per_row == 1
    edge = grid.rows[3].lo_paise
    assert grid.containing_index(edge) == 3
    assert grid.containing_index(edge - 1) == 2


def test_a_point_bar_closing_on_a_row_edge_puts_its_whole_volume_in_the_upper_row() -> None:
    """The containment rule, exercised through the allocator: a zero-range bar is a point and
    its FULL volume lands in the single row containing that price (CONTEXT 3.3)."""
    day = date(2026, 7, 14)
    grid = poc.build_rows(top_paise=1000, bottom_paise=900, row_size=10, tick_paise=10)
    edge = grid.rows[3].lo_paise
    bars = _synthetic(day, [("09:15", edge, edge, edge, edge, 500)])
    volumes = poc.spread_volume(bars, grid)
    assert volumes[3] == 500
    assert sum(volumes) == 500  # nothing lost -- the PoC script's prorata dropped point bars


def test_a_bar_touching_top_allocates_into_the_topmost_row_which_includes_top() -> None:
    """CONTEXT 3.3: "rows are half-open [lo, hi) EXCEPT the topmost row, which includes top"."""
    day = date(2026, 7, 14)
    grid = poc.build_rows(top_paise=1000, bottom_paise=900, row_size=10, tick_paise=10)
    top = grid.top_paise
    point_at_top = _synthetic(day, [("09:15", top, top, top, top, 700)])
    volumes = poc.spread_volume(point_at_top, grid)
    assert volumes[-1] == 700, "a trade exactly at top must not fall out of the profile"
    assert sum(volumes) == 700


def test_a_tie_on_row_volume_goes_to_the_higher_priced_row() -> None:
    """CONTEXT 3.3 / R1-Q9: "Tie -> the higher-priced row", side-independent."""
    assert poc.poc_row_index([Fraction(5), Fraction(5), Fraction(5)]) == 2
    assert poc.poc_row_index([Fraction(9), Fraction(9), Fraction(1)]) == 1
    assert poc.poc_row_index([Fraction(1), Fraction(9), Fraction(9)]) == 2
    assert poc.poc_row_index([Fraction(9), Fraction(1), Fraction(1)]) == 0


def test_a_frozen_stock_gets_one_single_tick_row_and_its_midpoint() -> None:
    """CONTEXT 3.3: "If top == bottom for the whole window (frozen stock), the profile is one
    single-tick row" -- the tpr floor and the totalTicks floor together."""
    day = date(2026, 7, 14)
    price = 50_000
    bars = _synthetic(
        day, [("09:15", price, price, price, price, 100), ("09:16", price, price, price, price, 250)]
    )
    result = poc.day_profile(
        bars, day, row_size=ROW_SIZE, tick_paise=5, volume_reconciled=True
    )
    assert result.grid is not None
    assert result.grid.total_ticks == 1
    assert result.grid.ticks_per_row == 1
    assert len(result.grid.rows) == 1
    assert result.grid.rows[0].lo_paise == price
    assert result.grid.rows[0].hi_paise == price + 5
    assert result.poc_paise == Fraction(2 * price + 5, 2)  # the row midpoint, a half-paise value
    assert sum(result.row_volumes) == 350


# --- prorata spreading (CONTEXT 3.3) -----------------------------------------------------


def test_prorata_splits_a_bar_across_rows_in_proportion_to_the_price_overlap() -> None:
    """CONTEXT 3.3: volume is split "proportionally to the price-overlap fraction"."""
    day = date(2026, 7, 14)
    grid = poc.build_rows(top_paise=1000, bottom_paise=900, row_size=10, tick_paise=10)
    # a bar covering rows 0..1 with 3/4 of its range in row 0 and 1/4 in row 1
    bars = _synthetic(day, [("09:15", 900, 915, 895 + 5, 910, 400)])
    volumes = poc.spread_volume(bars, grid)
    assert volumes[0] == Fraction(400 * 10, 15)
    assert volumes[1] == Fraction(400 * 5, 15)
    assert sum(volumes) == 400


def test_row_volumes_are_exact_fractions_so_the_tie_rule_never_rests_on_float_noise() -> None:
    """CONTEXT 7-E11 bans float equality; an exact Fraction makes "maximum row" and "tie" exact."""
    result = _profile("HDFCBANK", "2026-07-14")
    assert result.row_volumes
    assert all(isinstance(volume, Fraction) for volume in result.row_volumes)


def test_a_zero_volume_bar_contributes_nothing_but_still_sets_the_range() -> None:
    """The completeness ruling: a tradeless minute contributes zero volume to the profile."""
    day = date(2026, 7, 14)
    bars = _synthetic(
        day,
        [
            ("09:15", 10_000, 10_050, 10_000, 10_020, 1_000),
            ("09:16", 10_200, 10_300, 10_200, 10_250, 0),  # no trade: sets the top, adds nothing
        ],
    )
    result = poc.day_profile(bars, day, row_size=4, tick_paise=5, volume_reconciled=True)
    assert result.grid is not None
    assert result.grid.top_paise == 10_300
    assert sum(result.row_volumes) == 1_000
    assert result.window_volume == 1_000


# --- F7: the calibration goldens (CONTEXT 8 F7) ------------------------------------------


@pytest.mark.parametrize("symbol,day,printed,trader", F7_ANCHORS)
def test_f7a_the_recomputed_prorata_poc_reproduces_the_frozen_printout(
    symbol: str, day: str, printed: str, trader: str
) -> None:
    """CONTEXT 8 F7 (a): recomputed prorata POC == the poc-run printout, to +-0.01."""
    result = _profile(symbol, day)
    assert result.reason == poc.POC_OK
    assert result.poc_rupees is not None
    assert abs(result.poc_rupees - Decimal(printed)) <= F7_TOLERANCE, (
        f"{symbol} {day}: recomputed {result.poc_rupees} vs frozen printout {printed}"
    )


@pytest.mark.parametrize("symbol,day,printed,trader", F7_ANCHORS)
def test_f7a_the_recomputed_poc_also_matches_the_frozen_summary_column(
    symbol: str, day: str, printed: str, trader: str
) -> None:
    """The same assertion against the frozen artifact itself (``poc_prorata`` in
    ``poc/data/volume_poc_summary.csv``) rather than the value CONTEXT 8 quotes -- so the
    golden cannot pass by agreeing with a transcription."""
    row = next(r for r in _summary() if r["symbol"] == symbol and r["date"] == day)
    frozen = Decimal(row["poc_prorata"])
    result = _profile(symbol, day)
    assert result.poc_rupees is not None
    assert abs(result.poc_rupees - frozen) <= F7_TOLERANCE


@pytest.mark.parametrize("symbol,day,printed,trader", F7_ANCHORS)
def test_f7b_prorata_is_the_candidate_nearest_the_traders_tradingview_reading(
    symbol: str, day: str, printed: str, trader: str
) -> None:
    """CONTEXT 8 F7 (b): "on each day, prorata is the candidate nearest the trader's TV reading".

    The alternatives are the OTHER spreading methods the 22-Jul calibration printed and froze
    (``poc_close``, ``poc_uniform``); they are not spec behaviour and exist nowhere in ``src/``
    -- the comparison is what LOCKED prorata (CONTEXT 3.3 / CONTEXT 5). The assertion is that
    no alternative is STRICTLY nearer: on three of the five days a rival method lands on the
    same price as prorata, and an "is strictly nearest" test would fail on an agreement.
    """
    row = next(r for r in _summary() if r["symbol"] == symbol and r["date"] == day)
    reading = Decimal(trader)
    result = _profile(symbol, day)
    assert result.poc_rupees is not None

    ours = abs(result.poc_rupees - reading)
    for method in ("poc_close", "poc_uniform"):
        rival = abs(Decimal(row[method]) - reading)
        assert ours <= rival, (
            f"{symbol} {day}: {method} ({row[method]}) is nearer the trader's {trader} "
            f"than prorata ({result.poc_rupees})"
        )
    # and the residual stays inside one row -- CONTEXT 5's "residuals ... within one row"
    assert result.grid is not None
    row_height = Decimal(result.grid.ticks_per_row * result.grid.tick_paise) / Decimal(100)
    assert ours <= row_height


def test_f7_reproduces_all_25_frozen_prorata_values_not_only_the_five_anchors() -> None:
    """CONTEXT 8 F7 names five anchors, but the frozen printout carries 25 -- and the extra 20
    are free evidence the engine did not merely fit the five.

    They also PIN the one rounding choice CONTEXT 3.3 leaves open (QUESTIONS.md **Q-13**): six
    of the 25 days sit exactly on the ticks-per-row rounding TIE, where the spec's "direction
    chosen so the realized row count is closest to N" gives two equally-close answers. The
    interim keeps the FINER profile, which is what reproduces all 25 frozen values; the other
    direction would move six of them.
    """
    ticks = _ticks()
    checked = 0
    for row in _summary():
        symbol, day = row["symbol"], row["date"]
        result = poc.day_profile(
            _bars(symbol, day),
            date.fromisoformat(day),
            row_size=ROW_SIZE,
            tick_paise=ticks[symbol],
            volume_reconciled=True,
        )
        assert result.poc_rupees is not None
        assert abs(result.poc_rupees - Decimal(row["poc_prorata"])) <= F7_TOLERANCE, (
            f"{symbol} {day}: {result.poc_rupees} vs frozen {row['poc_prorata']}"
        )
        checked += 1
    assert checked == 25


def test_the_tpr_tie_keeps_the_finer_profile_the_direction_the_frozen_printout_was_built_with() -> None:
    """QUESTIONS.md Q-13's interim, pinned so a later session cannot flip it silently.

    A tie is real and common (measured: 6 of the 25 frozen days, and 11-20% of stored days per
    symbol), and the two directions produce different POC prices -- so this is not cosmetic.
    """
    for ticks, expected_lower in ((130, 5), (128, 5), (105, 4), (176, 7), (246, 10)):
        lower = max(1, ticks // ROW_SIZE)
        upper = max(1, -(-ticks // ROW_SIZE))
        assert abs(-(-ticks // lower) - ROW_SIZE) == abs(-(-ticks // upper) - ROW_SIZE), (
            f"{ticks} ticks is not actually a tie at N={ROW_SIZE}"
        )
        assert poc.ticks_per_row(ticks, ROW_SIZE) == expected_lower == lower


def test_f7_every_anchor_uses_its_own_symbols_tick_and_hardcoding_one_breaks_it() -> None:
    """QUESTIONS.md Q-2's measured hazard, kept as a tripwire: with 0.05 hardcoded the DIXON
    calibration silently returns a plausible but WRONG price (Q-2 measured rupees of error)."""
    correct = _profile("DIXON", "2026-07-16")
    assert correct.poc_rupees is not None
    wrong = poc.day_profile(
        _bars("DIXON", "2026-07-16"),
        date(2026, 7, 16),
        row_size=ROW_SIZE,
        tick_paise=5,  # the banned hardcoded 0.05
        volume_reconciled=True,
    )
    assert wrong.poc_rupees is not None
    assert wrong.poc_rupees != correct.poc_rupees
    assert abs(wrong.poc_rupees - correct.poc_rupees) > F7_TOLERANCE


def test_the_frozen_tick_fixture_agrees_with_the_chunk5a_instrument_master_loader() -> None:
    """The fixture is a TEST input (Q-2 ruling); production reads the master. This proves the
    two agree, so the goldens are not calibrated against a tick the real loader would not
    return."""
    master = InstrumentMaster.from_rows(
        json.loads((FIXTURES / "instrument_master_sample.json").read_text(encoding="utf-8"))
    )
    for symbol, tick_paise in _ticks().items():
        assert master.instrument(symbol).tick_size_paise == tick_paise
        assert master.tick_size(symbol) == Decimal(tick_paise) / Decimal(100)


# --- the property: prorata conserves volume ----------------------------------------------


@pytest.mark.parametrize("window", [poc.SPEC_WINDOW, poc.ALTERNATE_WINDOW], ids=lambda w: w.name)
def test_property_the_row_volumes_sum_to_the_window_volume_on_every_frozen_day(
    window: poc.ProfileWindow,
) -> None:
    """The chunk-6 property: ``sum(row volumes) == window volume`` (+-1e-6) on every fixture day.

    Asserted EXACTLY as well as within the tolerance -- the arithmetic is Fractions over integer
    paise, so "close enough" would be hiding a real leak. All 25 frozen symbol-days, both
    windows.
    """
    ticks = _ticks()
    days = 0
    for row in _summary():
        symbol, day = row["symbol"], row["date"]
        result = poc.day_profile(
            _bars(symbol, day),
            date.fromisoformat(day),
            row_size=ROW_SIZE,
            tick_paise=ticks[symbol],
            volume_reconciled=True,
            window=window,
        )
        assert result.reason == poc.POC_OK
        assert sum(result.row_volumes) == result.window_volume, f"{symbol} {day}: volume leaked"
        assert abs(float(sum(result.row_volumes)) - result.window_volume) < 1e-6
        days += 1
    assert days == 25


def test_property_holds_when_the_top_is_off_the_tick_grid_in_both_rounding_directions() -> None:
    """An off-grid top (only reachable via a flagged un-adjustment residual) must not leak
    volume in either direction: ``totalTicks`` can round the grid SHORT of top or PAST it, and
    CONTEXT 3.3's top-inclusive rule has to hold both ways."""
    day = date(2026, 7, 14)
    for high in (10_007, 10_008):  # 7 paise rounds DOWN to 1 tick, 8 rounds UP to 2 (tick = 5)
        bars = _synthetic(
            day,
            [
                ("09:15", 10_000, high, 10_000, high, 300),
                ("09:16", high, high, high, high, 120),  # a point bar exactly at top
            ],
        )
        result = poc.day_profile(bars, day, row_size=ROW_SIZE, tick_paise=5, volume_reconciled=True)
        assert sum(result.row_volumes) == 420, f"volume leaked with high={high}"


# --- window validity: the AMENDED completeness rule --------------------------------------


def test_a_day_that_fails_gate_1_gets_no_poc() -> None:
    """The amended rule (QUESTIONS.md, 2026-07-26): "the 09:15-11:14 profile window is valid
    when the DAY passes gate-1". A failing day is excluded and counted (CONTEXT 7-E3)."""
    result = poc.day_profile(
        _bars("TCS", "2026-07-14"),
        date(2026, 7, 14),
        row_size=ROW_SIZE,
        tick_paise=_ticks()["TCS"],
        volume_reconciled=False,
    )
    assert not result.has_poc
    assert result.poc_paise is None
    assert result.reason == poc.NO_POC_GATE_1_FAILED
    assert result.grid is None


def test_a_day_whose_gate_1_never_ran_gets_no_poc_either() -> None:
    """The ruling's licence is "gate-1 PASSES"; an unrun gate has not passed -- the same
    conservative reading :func:`acumen.quality_gates.integrity_gate` takes (decision B104)."""
    result = poc.day_profile(
        _bars("TCS", "2026-07-14"),
        date(2026, 7, 14),
        row_size=ROW_SIZE,
        tick_paise=_ticks()["TCS"],
        volume_reconciled=None,
    )
    assert not result.has_poc
    assert result.reason == poc.NO_POC_GATE_1_UNRUN


def test_a_window_missing_six_minutes_still_yields_a_poc_the_retired_e4_trigger_inverted() -> None:
    """plan.md's chunk-6 card asked for "a window with 6 missing minutes -> no POC". That
    fixture is INVERTED here on purpose, because the architect RETIRED the trigger it tested:

        "a missing 1-minute stamp on a day whose gate-1 volume reconciliation PASSES is a
        NO-TRADE minute, not missing data ... E4 is redefined the same way ... E4's
        minute-count trigger is retired."   -- QUESTIONS.md, 2026-07-26

    So six absent stamps on a gate-1-passing day must still produce a POC, and (because the
    absent minutes traded nothing) the SAME POC as the complete day.
    """
    day = date(2026, 7, 14)
    full = _bars("TCS", "2026-07-14")
    dropped = {datetime.combine(day, poc.SESSION_OPEN) + timedelta(minutes=n) for n in range(20, 26)}
    thinned = [bar for bar in full if bar.stamp not in dropped]
    assert len(thinned) == len(full) - 6

    complete = _profile("TCS", "2026-07-14")
    result = poc.day_profile(
        thinned, day, row_size=ROW_SIZE, tick_paise=_ticks()["TCS"], volume_reconciled=True
    )
    assert result.has_poc
    assert result.reason == poc.POC_OK
    assert result.bar_count == 114
    # the dropped minutes DID trade, so the profile legitimately moves; what must not happen is
    # the day being refused for the count
    assert result.poc_paise is not None
    assert complete.poc_paise is not None


def test_a_window_of_only_tradeless_minutes_is_the_same_profile_as_the_traded_ones_alone() -> None:
    """The ruling's arithmetic claim, tested: "a prorata row sum over 118 traded minutes and
    over the same 118 traded minutes plus 2 tradeless ones is the same number"."""
    day = date(2026, 7, 14)
    traded = _synthetic(
        day,
        [
            ("09:15", 10_000, 10_100, 10_000, 10_050, 900),
            ("09:16", 10_050, 10_150, 10_050, 10_100, 400),
        ],
    )
    with_tradeless = traded + _synthetic(
        day, [("09:17", 10_100, 10_100, 10_100, 10_100, 0), ("09:18", 10_050, 10_050, 10_050, 10_050, 0)]
    )
    a = poc.day_profile(traded, day, row_size=8, tick_paise=5, volume_reconciled=True)
    b = poc.day_profile(with_tradeless, day, row_size=8, tick_paise=5, volume_reconciled=True)
    assert a.poc_paise == b.poc_paise
    assert a.row_volumes == b.row_volumes


def test_a_window_with_no_candles_at_all_has_no_poc_and_says_so() -> None:
    """Not a count and not a threshold: ``max(high)`` over an empty window does not exist, so
    there is no profile to build. Distinct reason code, so chunk 9 counts it separately."""
    day = date(2026, 7, 14)
    afternoon = _synthetic(day, [("13:00", 10_000, 10_100, 10_000, 10_050, 900)])
    result = poc.day_profile(
        afternoon, day, row_size=ROW_SIZE, tick_paise=5, volume_reconciled=True
    )
    assert not result.has_poc
    assert result.reason == poc.NO_POC_EMPTY_WINDOW


def test_a_window_holding_bars_but_zero_volume_is_flagged_not_silently_trusted() -> None:
    """CONTEXT 3.3's tie rule is unconditional, so an all-zero profile resolves to the topmost
    row. The flag exists so such a day can be COUNTED rather than believed (chunk-6 FINDING in
    QUESTIONS.md)."""
    day = date(2026, 7, 14)
    bars = _synthetic(
        day,
        [("09:15", 10_000, 10_100, 10_000, 10_050, 0), ("09:16", 10_050, 10_150, 10_050, 10_100, 0)],
    )
    result = poc.day_profile(bars, day, row_size=8, tick_paise=5, volume_reconciled=True)
    assert result.has_poc
    assert result.zero_volume_profile is True
    assert result.poc_paise == result.grid.rows[-1].midpoint_paise  # type: ignore[union-attr]


def test_a_normal_calibration_day_is_not_flagged_zero_volume() -> None:
    assert _profile("TCS", "2026-07-14").zero_volume_profile is False


# --- discipline guards -------------------------------------------------------------------


def test_the_poc_engine_imports_nothing_that_does_io() -> None:
    """CONTEXT 6: ``bias``, ``poc``, ``signals``, ``simulate`` are PURE. An import of the store,
    the client, requests, or pathlib would be the first step away from that -- caught here
    rather than in review."""
    tree = ast.parse((REPO_ROOT / "src" / "acumen" / "poc.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level  # a relative import is an acumen module, not the stdlib
            imported.add(f"{prefix}{(node.module or '').split('.')[0]}")
    banned = {
        "pathlib", "os", "io", "requests", "pyarrow", "pandas", "json", "csv", "time",
        ".minute_store", ".daily_store", ".smartapi_client", ".config", ".instrument_master",
        ".minute_backfill", ".universe_backfill", ".atomic_io", ".nse_http",
    }
    assert not (imported & banned), f"acumen.poc imports I/O: {sorted(imported & banned)}"
    # the ONLY acumen import allowed is the pure calendar module (session times, CONTEXT 7-E2)
    assert imported <= {
        "__future__", "dataclasses", "datetime", "decimal", "fractions", "typing", ".calendar"
    }, f"acumen.poc grew an unexpected import: {sorted(imported)}"


def test_the_engine_has_no_tick_size_default_anywhere() -> None:
    """CONTEXT 3.3 / 4.3: "NEVER hardcode 0.05". Every entry point must REQUIRE the symbol's
    tick, so a caller cannot silently inherit one."""
    import inspect

    for function in (poc.build_rows, poc.day_profile):
        parameter = inspect.signature(function).parameters["tick_paise"]
        assert parameter.default is inspect.Parameter.empty, f"{function.__name__} defaults a tick"
    with pytest.raises(poc.PocError, match="tick_paise"):
        poc.total_ticks(1000, 900, 0)


def test_no_row_may_be_built_from_an_inverted_range_or_a_fractional_tick() -> None:
    with pytest.raises(poc.PocError, match="below bottom"):
        poc.total_ticks(900, 1000, 5)
    with pytest.raises(poc.PocError, match="tick_paise"):
        poc.total_ticks(1000, 900, -5)
    with pytest.raises(poc.PocError, match="positive whole number"):
        poc.ticks_per_row(0, 24)


def test_a_negative_volume_or_impossible_ohlc_bar_is_refused_by_the_spreader() -> None:
    """Both are CONTEXT 4.5 gate-2 exclusion triggers, so such a bar can only arrive if the
    gate was bypassed; the engine refuses rather than producing a number."""
    day = date(2026, 7, 14)
    grid = poc.build_rows(top_paise=1000, bottom_paise=900, row_size=10, tick_paise=10)
    with pytest.raises(poc.PocError, match="negative volume"):
        poc.spread_volume(_synthetic(day, [("09:15", 950, 960, 940, 950, -1)]), grid)
    with pytest.raises(poc.PocError, match="below low"):
        poc.spread_volume(_synthetic(day, [("09:15", 950, 940, 960, 950, 10)]), grid)


def test_the_poc_is_reported_at_full_precision_and_may_be_half_paise() -> None:
    """CONTEXT 3.3 / 7-E11: the midpoint may sit off the tick grid, and comparisons use full
    precision. HDFCBANK's 2026-07-14 anchor is exactly that case: 815.275."""
    result = _profile("HDFCBANK", "2026-07-14")
    assert result.poc_paise == Fraction(163055, 2)  # 81527.5 paise -- a half-paise midpoint
    assert result.poc_rupees == Decimal("815.275")
