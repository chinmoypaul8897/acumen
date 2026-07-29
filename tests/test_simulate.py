"""The trade simulator (CONTEXT 3.5): sizing, exit PRICING, and the money.

CONTEXT 8's F1-F4 live in `tests/test_signals.py` at SIGNAL level (entry / stop / target as
exact paise). Here they are asserted again at **PnL level**, on the same candles, with every
rupee figure HAND-COMPUTED in the docstring BEFORE the code was written -- so a reader can
check any number in this file without running it, and a reviewer can check it against
CONTEXT 3.5 alone.

The money inputs are CONTEXT 3.5's, and they reach the simulator from `config.yaml` through
the loader -- never from a literal inside `src/acumen/simulate.py`
(``test_the_simulator_hardcodes_no_money_amount`` is the tripwire):

* risk per trade = 1,000 rupees = **100,000 paise** (Round-3 Q29, OPEN-1 resolved);
* cost per EXECUTED round trip = 100 rupees = **10,000 paise** (R1-Q23).

The five properties CONTEXT 3.5 implies, each asserted as its own test AND over a swept grid:

1. ``qty x per-share risk <= 100,000`` -- a trade never risks more than the trader's amount;
2. ``(qty + 1) x per-share risk > 100,000`` -- and the floor is tight;
3. a target exit's gross is exactly ``qty x 3 x per-share risk`` (CONTEXT 3.4-4's 3R);
4. a stop exit's gross is exactly ``-qty x per-share risk`` -- one R, by construction;
5. ``net == gross - 10,000`` if and only if ``qty > 0``.

Every long fixture has a hand-computed SHORT mirror, because CONTEXT 3.4/3.5's short side is
written out explicitly and must never be inferred.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, time
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import simulate as sim
from acumen import signals as sig
from acumen.aggregate import Bar
from acumen.config import load_config

#: An ordinary Monday. Nothing here reads a calendar; the date only stamps bars.
DAY = date(2026, 7, 20)

#: CONTEXT 3.5's two money amounts in paise. `config.yaml` carries them in rupees and the
#: loader converts once; ``test_the_money_comes_from_config_yaml_through_the_loader`` pins
#: that these literals ARE what the repo's own config resolves to.
RISK_PAISE = 100_000
COST_PAISE = 10_000


def R(rupees: float) -> int:
    """Rupees -> integer paise (CONTEXT 7-E11)."""
    return int(round(rupees * 100))


def POC(rupees: float) -> Fraction:
    """A POC in paise as the exact Fraction the POC engine hands over (CONTEXT 3.3)."""
    return Fraction(R(rupees))


def bar(ordinal: int, o: float, h: float, l: float, c: float, *, day: date = DAY) -> Bar:
    """The ``ordinal``-th 15-minute candle of ``day`` (1-based; the 8th closes at 11:15)."""
    return Bar(
        stamp=sig.bar_open_stamp(day, ordinal),
        open_paise=R(o),
        high_paise=R(h),
        low_paise=R(l),
        close_paise=R(c),
        volume=1_000,
    )


class Minute:
    """A 1-minute bar, for the E10 reference fallback only (it reads stamp + close)."""

    def __init__(self, at: time, close: float, day: date = DAY) -> None:
        self.stamp = datetime.combine(day, at)
        self.close_paise = R(close)


def priced(
    bars,
    *,
    side: str,
    poc: Fraction,
    symbol: str = "TCS",
    minutes=(),
    risk_paise: int = RISK_PAISE,
    cost_paise: int = COST_PAISE,
    bias: str | None = None,
    tie_case: bool = False,
) -> sim.TradeRecord:
    """Run one day through chunk 7 and then chunk 8 -- the whole path the backtest uses."""
    signal = sig.evaluate_day(
        bars, day=DAY, side=side, poc_paise=poc, minute_bars=minutes
    )
    return sim.simulate_day(
        signal,
        bars,
        symbol=symbol,
        risk_per_trade_paise=risk_paise,
        cost_paise=cost_paise,
        bias=bias,
        tie_case=tie_case,
    )


# ==============================================================================================
# THE GOLDEN MONEY TABLE -- CONTEXT 8's F1-F4 and every mirror, at PnL level
# ==============================================================================================
#
#  case              side  entry   stop    target  risk   qty  exit         gross      net
#  F1                long  2037    2032    2052     5.00  200  target     +3,000.00 +2,900.00
#  F2                long  2037    2032    2052     5.00  200  target     +3,000.00 +2,900.00
#  F3                short 1980    1988    1956     8.00  125  target     +3,000.00 +2,900.00
#  F4 (gap)          long  2042    2028    2084    14.00   71  target     +2,982.00 +2,882.00
#  F4 stop variant   long  2042    2028    2084    14.00   71  stop         -994.00 -1,094.00
#  F4 short mirror   short 1973    1987    1931    14.00   71  target     +2,982.00 +2,882.00
#  F4 short, stopped short 1973    1987    1931    14.00   71  stop         -994.00 -1,094.00

F1_BARS = (
    bar(8, 2028, 2029, 2024, 2025),
    bar(9, 2033, 2038, 2032, 2037),
    bar(10, 2037, 2041, 2035, 2040),
    bar(11, 2040, 2055, 2039, 2053),
)

F2_BARS = (
    bar(8, 2030, 2036, 2029, 2034),
    bar(9, 2034, 2039, 2033, 2038),
    bar(10, 2038, 2038, 2026, 2027),
    bar(11, 2033, 2038, 2032, 2037),
    bar(12, 2037, 2043, 2036, 2042),
    bar(13, 2042, 2056, 2041, 2054),
)

F3_BARS = (
    bar(8, 1992, 1994, 1988, 1990),
    bar(9, 1987, 1988, 1979, 1980),
    bar(10, 1980, 1984, 1975, 1977),
    bar(11, 1977, 1979, 1954, 1958),
)

#: F4's first three candles: the ARMED reference, the prior close 2028, and the gap candle.
F4_HEAD = (
    bar(8, 2031, 2032, 2027, 2029),
    bar(9, 2029, 2030, 2026, 2028),
    bar(10, 2035, 2044, 2034, 2042),
)
F4_BARS = F4_HEAD + (
    bar(11, 2042, 2050, 2040, 2048),
    bar(12, 2048, 2086, 2047, 2085),
)

F4_SHORT_HEAD = (
    bar(8, 1988, 1992, 1986, 1990),
    bar(9, 1990, 1991, 1986, 1987),
    bar(10, 1980, 1981, 1971, 1973),
)
F4_SHORT_BARS = F4_SHORT_HEAD + (
    bar(11, 1973, 1975, 1965, 1968),
    bar(12, 1968, 1970, 1929, 1932),
)


def test_f1_golden_money_target_hit_pays_three_r_minus_the_cost() -> None:
    """**F1 at PnL level.** CONTEXT 8 F1 (v1.4, POC 2032): entry 2037, SL 2032, TP 2052.

    HAND-COMPUTED from CONTEXT 3.5:

    * per-share risk = 2037 - 2032 = **5.00 rupees = 500 paise**;
    * ``qty = floor(100,000 / 500)`` = **200** shares. Check both directions:
      200 x 500 = 100,000 <= 100,000, and 201 x 500 = 100,500 > 100,000;
    * the exit event is a TARGET hit, so the fill is the target LEVEL, 2052 -- exactly, even
      though the 12:00 candle's high ran to 2055 (CONTEXT 7-E9: idealized fills);
    * gross = 200 x (205,200 - 203,700) = 200 x 1,500 = **300,000 paise = +Rs 3,000.00**,
      which is exactly ``qty x 3 x risk`` = 200 x 1,500;
    * net = 300,000 - 10,000 = **290,000 paise = +Rs 2,900.00**.
    """
    record = priced(F1_BARS, side=sig.LONG, poc=POC(2032))

    assert record.per_share_risk_paise == R(5)
    assert record.qty == 200
    assert record.exit_kind == sig.EXIT_TARGET
    assert record.exit_paise == R(2052)
    assert record.gross_pnl_paise == R(3_000)
    assert record.cost_paise == COST_PAISE
    assert record.net_pnl_paise == R(2_900)
    assert record.executed and record.signalled and record.consumed
    assert record.flags == ()
    assert not record.gap_entry


def test_f2_golden_money_is_the_same_trade_reached_by_the_entry_2_path() -> None:
    """**F2 at PnL level.** Same four numbers as F1 (entry 2037 / SL 2032 / TP 2052), reached
    through WAIT-BELOW -> the 2027 close arms -> the re-cross at 2037.

    HAND-COMPUTED: risk 5.00 -> qty ``floor(100,000 / 500)`` = **200**; TARGET fill at 2052;
    gross 200 x 1,500 = **+Rs 3,000.00**; net **+Rs 2,900.00**. The money does not care which
    path armed the day -- and that is the point of asserting it separately.
    """
    record = priced(F2_BARS, side=sig.LONG, poc=POC(2032))

    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(2037),
        R(2032),
        R(2052),
    )
    assert record.per_share_risk_paise == R(5) and record.qty == 200
    assert record.exit_kind == sig.EXIT_TARGET and record.exit_paise == R(2052)
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (R(3_000), R(2_900))


def test_f3_golden_money_short_sign_discipline() -> None:
    """**F3 at PnL level** -- the SHORT, where the sign discipline is the whole test.

    CONTEXT 8 F3: entry 1980, SL 1988 (the candle HIGH, R1-Q2), TP 1956 (R1-Q1's correction).
    HAND-COMPUTED:

    * per-share risk = 1988 - 1980 = **8.00 rupees = 800 paise** (``SL - entry`` on a short);
    * ``qty = floor(100,000 / 800)`` = **125**. Check: 125 x 800 = 100,000 <= 100,000;
      126 x 800 = 100,800 > 100,000;
    * TARGET fill at 1956, and a short that exits BELOW its entry MADE money:
      gross = 125 x (198,000 - 195,600) = 125 x 2,400 = **300,000 paise = +Rs 3,000.00**;
    * net = **+Rs 2,900.00**.

    A long-shaped formula would return -Rs 3,000 here, which is why this is a golden.
    """
    record = priced(F3_BARS, side=sig.SHORT, poc=POC(1985))

    assert record.side == sig.SHORT
    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(1980),
        R(1988),
        R(1956),
    )
    assert record.per_share_risk_paise == R(8) and record.qty == 125
    assert record.exit_kind == sig.EXIT_TARGET and record.exit_paise == R(1956)
    assert record.gross_pnl_paise == R(3_000)
    assert record.net_pnl_paise == R(2_900)


def test_f4_golden_money_gap_entry_target() -> None:
    """**F4 at PnL level** -- the gap entry, and the first case where the floor bites.

    CONTEXT 8 F4: prior close 2028, gap candle low 2034 close 2042 -> entry 2042, SL **2028**,
    TP 2084. HAND-COMPUTED:

    * per-share risk = 2042 - 2028 = **14.00 rupees = 1,400 paise**;
    * ``qty = floor(100,000 / 1,400)`` = **71** (the card's number). Check:
      71 x 1,400 = 99,400 <= 100,000, and 72 x 1,400 = 100,800 > 100,000. The 600 paise
      left over are NOT rounded up -- that is the floor;
    * TARGET fill at 2084: gross = 71 x (208,400 - 204,200) = 71 x 4,200 = **298,200 paise
      = +Rs 2,982.00** = ``qty x 3 x risk`` = 71 x 4,200;
    * net = 298,200 - 10,000 = **288,200 paise = +Rs 2,882.00**.
    """
    record = priced(F4_BARS, side=sig.LONG, poc=POC(2030))

    assert record.gap_entry
    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(2042),
        R(2028),
        R(2084),
    )
    assert record.per_share_risk_paise == R(14) and record.qty == 71
    assert record.exit_kind == sig.EXIT_TARGET and record.exit_paise == R(2084)
    assert record.gross_pnl_paise == R(2_982)
    assert record.net_pnl_paise == R(2_882)


def test_f4_variant_the_same_trade_stopped_out_pays_exactly_one_r() -> None:
    """**F4's stop branch** -- same entry, same size, the other outcome.

    Same three candles as F4 (entry 2042, SL 2028, risk 14.00, qty **71**), then a candle
    that trades down to 2026. HAND-COMPUTED:

    * the 12:00 candle's low 2026 <= the stop 2028 -> STOP hit, and the fill is the stop
      LEVEL **2028**, not the candle's low -- a stop fills where it was placed;
    * gross = 71 x (202,800 - 204,200) = 71 x (-1,400) = **-99,400 paise = -Rs 994.00**,
      which is exactly ``-qty x risk``: the trade lost less than the full Rs 1,000 budget
      because 71 shares is the floor, not the exact quotient;
    * net = -99,400 - 10,000 = **-109,400 paise = -Rs 1,094.00**. The cost is charged on a
      loser exactly as on a winner.
    """
    bars = F4_HEAD + (bar(11, 2042, 2043, 2026, 2030),)
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.qty == 71 and record.per_share_risk_paise == R(14)
    assert record.exit_kind == sig.EXIT_STOP
    assert record.exit_paise == R(2028)
    assert record.gross_pnl_paise == R(-994)
    assert record.net_pnl_paise == R(-1_094)
    assert record.gross_pnl_paise == -record.qty * record.per_share_risk_paise


def test_f4_short_mirror_golden_money_target() -> None:
    """**F4's SHORT mirror at PnL level** (CONTEXT 3.4's own mirror paragraph).

    HAND-COMPUTED at POC 1985: prior close 1987, the gap candle never trades at or above the
    POC (high 1981) and closes 1973 -> entry 1973, SL = the previous close **1987**, TP 1931.

    * per-share risk = 1987 - 1973 = **14.00 rupees = 1,400 paise** -> ``qty`` = **71**,
      the same floor as the long mirror;
    * TARGET fill at 1931: gross = 71 x (197,300 - 193,100) = 71 x 4,200 = **+Rs 2,982.00**;
    * net = **+Rs 2,882.00**. Identical money to the long, which is what "mirrored" means.
    """
    record = priced(F4_SHORT_BARS, side=sig.SHORT, poc=POC(1985))

    assert record.gap_entry and record.side == sig.SHORT
    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(1973),
        R(1987),
        R(1931),
    )
    assert record.per_share_risk_paise == R(14) and record.qty == 71
    assert record.exit_kind == sig.EXIT_TARGET and record.exit_paise == R(1931)
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (R(2_982), R(2_882))


def test_f4_short_mirror_stopped_out_pays_exactly_one_r() -> None:
    """**F4's SHORT mirror, stopped.** HAND-COMPUTED: entry 1973, SL 1987, qty 71; the 12:00
    candle's high 1988 >= the stop 1987 -> STOP, filled at the LEVEL 1987;
    gross = 71 x (197,300 - 198,700) = 71 x (-1,400) = **-Rs 994.00**; net **-Rs 1,094.00**.
    """
    bars = F4_SHORT_HEAD + (bar(11, 1973, 1988, 1972, 1985),)
    record = priced(bars, side=sig.SHORT, poc=POC(1985))

    assert record.exit_kind == sig.EXIT_STOP and record.exit_paise == R(1987)
    assert record.qty == 71
    assert record.gross_pnl_paise == R(-994)
    assert record.net_pnl_paise == R(-1_094)


# ==============================================================================================
# SQUARE-OFF: priced at the CLOSE of the 15:00-stamped candle (R1-Q18, CONTEXT 7-E12)
# ==============================================================================================

SQUARE_OFF_LONG_BARS = (
    bar(8, 2028, 2029, 2024, 2025),  # reference 2025 < POC 2030 -> ARMED
    bar(9, 2031, 2036, 2029, 2035),  # closes above the POC -> TRIGGER, entry 2035, SL 2029
    bar(10, 2035, 2040, 2033, 2038),
    bar(23, 2038, 2044, 2036, 2041),
    bar(24, 2041, 2046, 2038, 2044),  # the 15:00-stamped candle: closes at 15:15
    bar(25, 2044, 2060, 2040, 2058),  # 15:15-stamped: NEVER looked at, though it hits the TP
)

SQUARE_OFF_SHORT_BARS = (
    bar(8, 1972, 1976, 1971, 1975),  # reference 1975 > POC 1970 -> ARMED (bearish)
    bar(9, 1969, 1971, 1963, 1965),  # closes below the POC -> TRIGGER, entry 1965, SL 1971
    bar(10, 1965, 1968, 1960, 1962),
    bar(23, 1962, 1966, 1955, 1958),
    bar(24, 1958, 1962, 1950, 1956),  # the 15:00-stamped candle
    bar(25, 1956, 1958, 1940, 1942),  # 15:15-stamped: would have hit the TP; never looked at
)


def test_a_square_off_is_priced_at_the_close_of_the_15_00_stamped_candle() -> None:
    """**The square-off golden, LONG.** CONTEXT 3.4-5: "Neither by 15:15 -> square off at the
    15:00-15:15 candle's close" (R1-Q18). HAND-COMPUTED at POC 2030:

    * reference 2025 -> ARMED; the 11:30 close 2035 triggers; entry **2035**; the entry
      candle's low 2029 is not above the POC, so the stop is that low, **2029**;
    * per-share risk = 2035 - 2029 = **6.00 rupees = 600 paise**; target 2035 + 18 = 2053;
    * ``qty = floor(100,000 / 600)`` = **166** (166 x 600 = 99,600; 167 x 600 = 100,200);
    * no candle up to and including the 15:00-stamped one touches 2029 or 2053, so the day
      squares off at THAT candle's close, **2044** -- the 15:15-stamped candle's high of 2060
      would have paid the target and is never looked at (CONTEXT 3.4-5 stops at 15:15);
    * gross = 166 x (204,400 - 203,500) = 166 x 900 = **149,400 paise = +Rs 1,494.00**;
    * net = 149,400 - 10,000 = **139,400 paise = +Rs 1,394.00**.
    """
    record = priced(SQUARE_OFF_LONG_BARS, side=sig.LONG, poc=POC(2030))

    assert record.exit_kind == sig.EXIT_SQUARE_OFF
    assert record.exit_stamp == sig.bar_open_stamp(DAY, sig.SQUARE_OFF_BAR)
    assert record.exit_close_stamp == sig.bar_close_stamp(DAY, sig.SQUARE_OFF_BAR)
    assert record.exit_close_stamp.time() == time(15, 15)
    assert record.exit_paise == R(2044)
    assert record.per_share_risk_paise == R(6) and record.qty == 166
    assert record.gross_pnl_paise == R(1_494)
    assert record.net_pnl_paise == R(1_394)


def test_the_short_mirror_of_the_square_off_price() -> None:
    """**The square-off golden, SHORT.** HAND-COMPUTED at POC 1970: reference 1975 -> ARMED;
    the 11:30 close 1965 triggers; entry **1965**; the entry candle's high 1971 is not below
    the POC, so the stop is that high, **1971**; risk **6.00 rupees**, target 1947;
    ``qty`` = **166**; nothing touches either level by 15:15, so the fill is the 15:00-stamped
    candle's close **1956**; gross = 166 x (196,500 - 195,600) = 166 x 900 =
    **+Rs 1,494.00**; net **+Rs 1,394.00**. The 15:15-stamped candle's low of 1940 would have
    paid the target and is never looked at.
    """
    record = priced(SQUARE_OFF_SHORT_BARS, side=sig.SHORT, poc=POC(1970))

    assert record.exit_kind == sig.EXIT_SQUARE_OFF
    assert record.exit_paise == R(1956)
    assert record.exit_close_stamp is not None
    assert record.exit_close_stamp.time() == time(15, 15)
    assert record.qty == 166
    assert record.gross_pnl_paise == R(1_494)
    assert record.net_pnl_paise == R(1_394)


def test_a_square_off_with_nothing_trading_after_the_entry_prices_the_entry_close() -> None:
    """Chunk-7 decision B159 (REVIEW_7-approved), priced: when no 15-minute candle traded
    after the entry candle, the marker names the ENTRY candle, whose close IS the day's last
    traded 15-minute price -- so the trade is flat and the flag says why.

    HAND-COMPUTED at POC 2030: entry 2035, stop 2029, risk 6.00, qty 166. Nothing trades
    after 11:30, so the fill is the entry candle's own close 2035: gross = 166 x 0 = **0**,
    net = 0 - 10,000 = **-Rs 100.00** -- the round trip still happened and still cost.
    """
    bars = (bar(8, 2028, 2029, 2024, 2025), bar(9, 2031, 2036, 2029, 2035))
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.exit_kind == sig.EXIT_SQUARE_OFF
    assert record.exit_stamp == record.entry_stamp
    assert record.exit_paise == R(2035)
    assert record.qty == 166
    assert record.gross_pnl_paise == 0
    assert record.net_pnl_paise == -COST_PAISE
    assert sim.FLAG_SQUARE_OFF_AT_ENTRY_CANDLE in record.flags


# ==============================================================================================
# qty == 0: the per-share risk exceeds the whole trade risk (CONTEXT 3.5)
# ==============================================================================================


def test_a_day_whose_per_share_risk_exceeds_the_trade_risk_is_a_recorded_no_trade() -> None:
    """**The qty-zero golden.** CONTEXT 3.5: ``qty == 0`` -> no trade, consumed + logged. Real
    on a high-priced stock with a wide entry candle -- this one is shaped like DIXON.

    HAND-COMPUTED at POC 14,000:

    * reference 13,980 < POC -> ARMED; the 11:30 candle closes 14,250 -> TRIGGER,
      entry **14,250**; its low 12,950 is not above the POC, so the stop is that low;
    * per-share risk = 14,250 - 12,950 = **1,300.00 rupees = 130,000 paise**, which is MORE
      than the whole Rs 1,000 trade risk;
    * ``qty = floor(100,000 / 130,000)`` = **0**. One single share would already risk 1.3x
      the budget -- which is exactly property 2 at the boundary;
    * so nothing is bought: gross **0**, cost **0** (there is no round trip to charge), net
      **0**. The day is still CONSUMED (CONTEXT 3.4-2) and still COUNTED -- it carries the
      entry, stop and target for the replay pack, but no fill price, because nothing traded.
    """
    bars = (
        bar(8, 13_990, 14_005, 13_950, 13_980),
        bar(9, 13_990, 14_300, 12_950, 14_250),
        bar(10, 14_250, 14_400, 14_200, 14_350),
    )
    record = priced(bars, side=sig.LONG, poc=POC(14_000), symbol="DIXON")

    assert record.per_share_risk_paise == R(1_300)
    assert record.qty == 0
    assert not record.executed
    assert record.signalled and record.consumed
    assert (record.gross_pnl_paise, record.cost_paise, record.net_pnl_paise) == (0, 0, 0)
    assert record.exit_paise is None
    assert record.entry_paise == R(14_250) and record.stop_paise == R(12_950)
    assert record.flags == (sim.FLAG_QTY_ZERO_UNSIZABLE,)
    assert (record.qty + 1) * record.per_share_risk_paise > RISK_PAISE


def test_the_short_mirror_of_a_qty_zero_day() -> None:
    """The SHORT mirror. HAND-COMPUTED at POC 14,000: reference 14,020 > POC -> ARMED; the
    11:30 candle closes 13,750 -> entry **13,750**, and its high 15,050 is not below the POC,
    so the stop is that high -> per-share risk **1,300.00 rupees**, ``qty`` = **0**, no cost,
    no PnL, day consumed."""
    bars = (
        bar(8, 14_010, 14_050, 13_995, 14_020),
        bar(9, 14_010, 15_050, 13_700, 13_750),
        bar(10, 13_750, 13_800, 13_600, 13_650),
    )
    record = priced(bars, side=sig.SHORT, poc=POC(14_000), symbol="DIXON")

    assert record.per_share_risk_paise == R(1_300) and record.qty == 0
    assert (record.gross_pnl_paise, record.cost_paise, record.net_pnl_paise) == (0, 0, 0)
    assert record.consumed and record.flags == (sim.FLAG_QTY_ZERO_UNSIZABLE,)


def test_one_share_of_risk_exactly_equal_to_the_budget_still_sizes_one_share() -> None:
    """The boundary the qty-zero rule sits on, from the other side: a per-share risk of
    exactly Rs 1,000 sizes **1** share (``floor(100,000 / 100,000) = 1``), not zero.

    HAND-COMPUTED at POC 2030: entry 2035, stop 1035 -> risk 1,000.00 rupees; target
    2035 + 3,000 = 5035; the day squares off at the entry candle's close 2035, so gross 0 and
    net -Rs 100.00. What matters here is the share count at the boundary.
    """
    bars = (bar(8, 2028, 2029, 2024, 2025), bar(9, 2031, 2036, 1035, 2035))
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.per_share_risk_paise == RISK_PAISE
    assert record.qty == 1
    assert record.executed and record.cost_paise == COST_PAISE


# ==============================================================================================
# EXACT-TOUCH exits, priced at the LEVEL (REVIEW_7 finding Q2's probes, now with money)
# ==============================================================================================

TOUCH_LONG_HEAD = (
    bar(8, 2028, 2029, 2024, 2025),  # ARMED at POC 2030
    bar(9, 2031, 2036, 2029, 2035),  # entry 2035, stop 2029, risk 6.00, target 2053, qty 166
)
TOUCH_SHORT_HEAD = (
    bar(8, 1972, 1976, 1971, 1975),  # ARMED at POC 1970 (bearish)
    bar(9, 1969, 1971, 1963, 1965),  # entry 1965, stop 1971, risk 6.00, target 1947, qty 166
)


def test_a_candle_whose_high_exactly_equals_the_target_pays_the_target_level() -> None:
    """REVIEW_7 Q2's exact-touch target, priced. CONTEXT 3.4-5 is INCLUSIVE: "Candle high >=
    TP -> exit at TP".

    HAND-COMPUTED at POC 2030: entry 2035, stop 2029, risk 6.00, target **2053**, qty 166.
    The next candle's high is exactly 2053 -> TARGET, filled at 2053:
    gross = 166 x (205,300 - 203,500) = 166 x 1,800 = **298,800 paise = +Rs 2,988.00**
    (= ``qty x 3 x risk``); net = **+Rs 2,888.00**.
    """
    bars = TOUCH_LONG_HEAD + (bar(10, 2035, 2053, 2034, 2050),)
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.exit_kind == sig.EXIT_TARGET and record.exit_paise == R(2053)
    assert record.qty == 166
    assert record.gross_pnl_paise == R(2_988)
    assert record.net_pnl_paise == R(2_888)
    assert record.gross_pnl_paise == record.qty * 3 * record.per_share_risk_paise


def test_a_candle_whose_low_exactly_equals_the_stop_pays_the_stop_level() -> None:
    """REVIEW_7 Q2's exact-touch stop, priced ("Candle low <= SL -> exit at SL").

    HAND-COMPUTED at POC 2030: entry 2035, stop **2029**, qty 166. The next candle's low is
    exactly 2029 -> STOP, filled at 2029: gross = 166 x (-600) = **-99,600 paise =
    -Rs 996.00**; net = **-Rs 1,096.00**. A candle that merely touches the stop pays it.
    """
    bars = TOUCH_LONG_HEAD + (bar(10, 2035, 2040, 2029, 2033),)
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.exit_kind == sig.EXIT_STOP and record.exit_paise == R(2029)
    assert record.gross_pnl_paise == R(-996)
    assert record.net_pnl_paise == R(-1_096)


def test_the_short_mirrors_of_both_exact_touches() -> None:
    """The SHORT mirrors, HAND-COMPUTED at POC 1970 (entry 1965, stop 1971, target 1947,
    risk 6.00, qty 166):

    * a candle whose HIGH is exactly 1971 -> STOP at 1971: gross 166 x (196,500 - 197,100) =
      **-Rs 996.00**, net **-Rs 1,096.00**;
    * a candle whose LOW is exactly 1947 -> TARGET at 1947: gross 166 x 1,800 =
      **+Rs 2,988.00**, net **+Rs 2,888.00**.
    """
    stopped = priced(
        TOUCH_SHORT_HEAD + (bar(10, 1965, 1971, 1962, 1968),), side=sig.SHORT, poc=POC(1970)
    )
    assert stopped.exit_kind == sig.EXIT_STOP and stopped.exit_paise == R(1971)
    assert (stopped.gross_pnl_paise, stopped.net_pnl_paise) == (R(-996), R(-1_096))

    targeted = priced(
        TOUCH_SHORT_HEAD + (bar(10, 1965, 1968, 1947, 1950),), side=sig.SHORT, poc=POC(1970)
    )
    assert targeted.exit_kind == sig.EXIT_TARGET and targeted.exit_paise == R(1947)
    assert (targeted.gross_pnl_paise, targeted.net_pnl_paise) == (R(2_988), R(2_888))


def test_a_candle_that_touches_both_levels_is_priced_at_the_stop() -> None:
    """R1-Q20 priced: "Both touched in the same candle -> SL wins". Chunk 7 already MARKED it
    as a stop; chunk 8 must price the stop LEVEL and not re-decide anything.

    HAND-COMPUTED at POC 2030: entry 2035, stop 2029, target 2053, qty 166. The next candle
    runs 2028..2055, touching both. Fill = **2029**: gross = **-Rs 996.00**, net
    **-Rs 1,096.00** -- the pessimistic resolution, flagged so the report can disclose how
    often it happened.
    """
    bars = TOUCH_LONG_HEAD + (bar(10, 2035, 2055, 2028, 2050),)
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.exit_kind == sig.EXIT_STOP and record.exit_paise == R(2029)
    assert sim.FLAG_BOTH_TOUCHED_STOP_WINS in record.flags
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (R(-996), R(-1_096))


def test_the_short_mirror_of_a_both_touched_candle() -> None:
    """The SHORT mirror of R1-Q20. HAND-COMPUTED at POC 1970: entry 1965, stop 1971, target
    1947, qty 166; the next candle runs 1946..1972 and touches both -> filled at the stop
    **1971**: gross **-Rs 996.00**, net **-Rs 1,096.00**."""
    bars = TOUCH_SHORT_HEAD + (bar(10, 1965, 1972, 1946, 1950),)
    record = priced(bars, side=sig.SHORT, poc=POC(1970))

    assert record.exit_kind == sig.EXIT_STOP and record.exit_paise == R(1971)
    assert sim.FLAG_BOTH_TOUCHED_STOP_WINS in record.flags
    assert (record.gross_pnl_paise, record.net_pnl_paise) == (R(-996), R(-1_096))


# ==============================================================================================
# Days that produce no trade -- all recorded, none dropped
# ==============================================================================================


def test_a_degenerate_entry_equal_to_the_stop_is_recorded_consumed_with_no_money() -> None:
    """CONTEXT 3.4-3's degenerate ``entry == SL``, priced: chunk 7 refuses it before an Entry
    exists, so chunk 8 records a consumed NO-TRADE with no money at all.

    The candles are `tests/test_signals.py`'s unsizable fixture: no 11:00-11:15 candle, so
    E10 takes the 10:59 one-minute close 2025 as the reference (ARMED at POC 2030); the 11:30
    candle never trades at or below the POC and closes 2037 -> a GAP entry whose stop is the
    10:45 candle's close, also **2037**. Risk 0 -> unsizable, day CONSUMED.
    """
    bars = (
        bar(7, 2030, 2038, 2029, 2037),
        bar(9, 2038, 2040, 2036, 2037),
        bar(10, 2037, 2046, 2036, 2045),
    )
    record = priced(
        bars, side=sig.LONG, poc=POC(2030), minutes=(Minute(time(10, 59), 2025),)
    )

    assert record.outcome == sig.OUTCOME_UNSIZABLE
    assert record.consumed and not record.signalled and not record.executed
    assert record.qty == 0
    assert (record.gross_pnl_paise, record.cost_paise, record.net_pnl_paise) == (0, 0, 0)
    assert record.entry_paise is None and record.exit_paise is None
    assert set(record.flags) == {sim.FLAG_NO_ENTRY, sim.FLAG_SIGNAL_UNSIZABLE}


def test_a_day_that_never_crossed_is_recorded_and_consumes_nothing() -> None:
    """A no-cross day is a RECORD, not a gap in the data: chunk 9 counts records.

    HAND-COMPUTED at POC 2030: reference 2025 -> ARMED, and no later close ever gets above
    the POC, so there is no entry, nothing is consumed, and no money moves.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2025, 2029, 2020, 2022),
        bar(10, 2022, 2028, 2018, 2026),
    )
    record = priced(bars, side=sig.LONG, poc=POC(2030))

    assert record.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert not record.consumed and not record.signalled and not record.executed
    assert (record.qty, record.gross_pnl_paise, record.cost_paise, record.net_pnl_paise) == (
        0,
        0,
        0,
        0,
    )
    assert record.flags == (sim.FLAG_NO_ENTRY,)


def test_every_record_carries_its_signal_day_provenance() -> None:
    """CONTEXT 3.5's report and chunk 12's replay pack are built off these fields, so the
    record has to carry them: the gap flag, the tie-case flag, consumption, the outcome, the
    POC (exact, unrounded) and the reference close."""
    record = priced(
        F4_BARS, side=sig.LONG, poc=POC(2030), symbol="TCS", bias="bullish", tie_case=True
    )

    assert record.symbol == "TCS" and record.day == DAY and record.side == sig.LONG
    assert record.bias == "bullish"
    assert record.tie_case is True
    assert record.gap_entry is True
    assert record.consumed is True
    assert record.outcome == sig.OUTCOME_ENTERED
    assert record.poc_paise == POC(2030) and isinstance(record.poc_paise, Fraction)
    assert record.reference_paise == R(2029)
    assert record.entry_stamp == sig.bar_open_stamp(DAY, 10)
    assert record.entry_close_stamp == sig.bar_close_stamp(DAY, 10)
    assert record.exit_close_stamp == sig.bar_close_stamp(DAY, 12)
    assert record.risk_per_trade_paise == RISK_PAISE


def test_a_half_paise_poc_survives_into_the_record_unrounded() -> None:
    """CONTEXT 3.3: a row midpoint may sit half a paisa off the tick grid, and CONTEXT 7-E11
    forbids rounding it. The simulator carries the exact Fraction through to the record."""
    poc = Fraction(R(2030) * 2 + 1, 2)  # 203,030.5 paise
    record = priced(F1_BARS, side=sig.LONG, poc=poc)

    assert record.poc_paise == poc
    assert record.poc_paise.denominator == 2


# ==============================================================================================
# THE FIVE PROPERTIES (CONTEXT 3.5), each on its own and over a swept grid
# ==============================================================================================

#: A deterministic grid of per-share risks in paise, from one paisa to well past the budget.
RISK_GRID = (
    1,
    2,
    3,
    7,
    99,
    100,
    285,  # HDFCBANK 2026-06-10's real risk
    499,
    500,
    501,
    999,
    1_000,
    1_400,
    3_333,
    9_999,
    33_333,
    50_000,
    99_999,
    100_000,  # exactly the budget -> one share
    100_001,  # one paisa past it -> zero shares
    130_000,
    1_000_000,
)


@pytest.mark.parametrize("per_share_risk", RISK_GRID)
def test_property_1_a_trade_never_risks_more_than_the_budget(per_share_risk: int) -> None:
    """PROPERTY 1 (CONTEXT 3.5): ``qty x per-share risk <= risk_per_trade``, ALWAYS. This is
    the trader's whole risk rule and it must hold on every day the machine ever sizes."""
    qty = sim.position_size(RISK_PAISE, per_share_risk)
    assert qty * per_share_risk <= RISK_PAISE


@pytest.mark.parametrize("per_share_risk", RISK_GRID)
def test_property_2_the_floor_is_tight(per_share_risk: int) -> None:
    """PROPERTY 2: ``(qty + 1) x per-share risk > risk_per_trade`` -- the size is the largest
    one that fits, never smaller. At ``qty == 0`` this IS the unsizable condition: a single
    share already risks more than the whole budget."""
    qty = sim.position_size(RISK_PAISE, per_share_risk)
    assert (qty + 1) * per_share_risk > RISK_PAISE


@pytest.mark.parametrize("per_share_risk", RISK_GRID)
def test_the_two_sizing_properties_bracket_the_answer_uniquely(per_share_risk: int) -> None:
    """Together the two properties determine ``qty`` uniquely -- so any implementation that
    satisfies both computes the same share count as this one."""
    qty = sim.position_size(RISK_PAISE, per_share_risk)
    assert qty == RISK_PAISE // per_share_risk
    assert qty * per_share_risk <= RISK_PAISE < (qty + 1) * per_share_risk


@pytest.mark.parametrize("risk_rupees,expected_qty", [(5, 200), (8, 125), (14, 71), (6, 166)])
def test_property_3_a_target_exit_pays_exactly_three_r(
    risk_rupees: int, expected_qty: int
) -> None:
    """PROPERTY 3: a target exit's gross is ``qty x 3 x per-share risk`` exactly, because
    CONTEXT 3.4-4 puts the target exactly 3R away and the fill is the LEVEL.

    Built long at POC 2030 with entry 2035 and the stop placed ``risk`` below it; the
    hand-computed quantities are the four the goldens above use (risk 5 -> 200, 8 -> 125,
    14 -> 71, 6 -> 166).
    """
    entry, poc = 2035, POC(2030)
    stop = entry - risk_rupees
    target = entry + 3 * risk_rupees
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2031, 2036, stop, entry),
        bar(10, entry, target, entry - 1, entry),
    )
    record = priced(bars, side=sig.LONG, poc=poc)

    assert record.qty == expected_qty
    assert record.exit_kind == sig.EXIT_TARGET
    assert record.gross_pnl_paise == record.qty * 3 * record.per_share_risk_paise


@pytest.mark.parametrize("risk_rupees,expected_qty", [(5, 200), (8, 125), (14, 71), (6, 166)])
def test_property_4_a_stop_exit_pays_exactly_minus_one_r(
    risk_rupees: int, expected_qty: int
) -> None:
    """PROPERTY 4: a stop exit's gross is ``-qty x per-share risk`` exactly -- one R, never
    more, because the fill is the stop LEVEL however far the candle ran past it."""
    entry, poc = 2035, POC(2030)
    stop = entry - risk_rupees
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2031, 2036, stop, entry),
        bar(10, entry, entry + 1, stop - 5, stop - 4),  # runs well past the stop
    )
    record = priced(bars, side=sig.LONG, poc=poc)

    assert record.qty == expected_qty
    assert record.exit_kind == sig.EXIT_STOP
    assert record.exit_paise == R(stop)
    assert record.gross_pnl_paise == -record.qty * record.per_share_risk_paise


def test_property_5_the_cost_is_charged_if_and_only_if_something_executed() -> None:
    """PROPERTY 5: ``net == gross - 10,000`` exactly when ``qty > 0``, and a day that
    executed nothing pays nothing. Checked across every shape this file builds."""
    executed = [
        priced(F1_BARS, side=sig.LONG, poc=POC(2032)),
        priced(F3_BARS, side=sig.SHORT, poc=POC(1985)),
        priced(F4_BARS, side=sig.LONG, poc=POC(2030)),
        priced(SQUARE_OFF_LONG_BARS, side=sig.LONG, poc=POC(2030)),
    ]
    for record in executed:
        assert record.qty > 0
        assert record.cost_paise == COST_PAISE
        assert record.net_pnl_paise == record.gross_pnl_paise - COST_PAISE

    not_executed = [
        priced(
            (
                bar(8, 13_990, 14_005, 13_950, 13_980),
                bar(9, 13_990, 14_300, 12_950, 14_250),
                bar(10, 14_250, 14_400, 14_200, 14_350),
            ),
            side=sig.LONG,
            poc=POC(14_000),
        ),
        priced(
            (
                bar(8, 2028, 2029, 2024, 2025),
                bar(9, 2025, 2029, 2020, 2022),
            ),
            side=sig.LONG,
            poc=POC(2030),
        ),
    ]
    for record in not_executed:
        assert record.qty == 0
        assert (record.cost_paise, record.gross_pnl_paise, record.net_pnl_paise) == (0, 0, 0)


def test_the_gross_formula_is_mirrored_not_repeated() -> None:
    """The sign rule alone, isolated: the same price move pays a long and a short opposite
    amounts. 100 shares moving 10 rupees is 1,000 rupees either way -- with the sign the side
    decides (CONTEXT 3.5's "mirrored short")."""
    assert sim.gross_pnl_paise(sig.LONG, 100, R(2000), R(2010)) == R(1_000)
    assert sim.gross_pnl_paise(sig.SHORT, 100, R(2000), R(2010)) == R(-1_000)
    assert sim.gross_pnl_paise(sig.LONG, 100, R(2000), R(1990)) == R(-1_000)
    assert sim.gross_pnl_paise(sig.SHORT, 100, R(2000), R(1990)) == R(1_000)


# ==============================================================================================
# The money comes from config.yaml, never from a literal in the engine
# ==============================================================================================


def test_the_money_comes_from_config_yaml_through_the_loader() -> None:
    """CONTEXT 3.5's two amounts reach the simulator from the committed config only. This
    pins the paise values every golden in this file is hand-computed against."""
    config = load_config(include_env=False)
    assert config.require_risk_per_trade_paise() == RISK_PAISE
    assert config.cost_per_trade_paise() == COST_PAISE

    record = priced(
        F1_BARS,
        side=sig.LONG,
        poc=POC(2032),
        risk_paise=config.require_risk_per_trade_paise(),
        cost_paise=config.cost_per_trade_paise(),
    )
    assert (record.qty, record.gross_pnl_paise, record.net_pnl_paise) == (
        200,
        R(3_000),
        R(2_900),
    )


def test_the_simulator_hardcodes_no_money_amount() -> None:
    """The card's own defect definition: "a hardcoded 100000 in simulate.py is a defect".

    Asserted structurally over the module's numeric literals rather than by reading its text,
    so a comment mentioning an amount cannot trip it and a constant carrying one cannot hide.
    The only literal above 2 in the whole module is the 100 that splits paise into rupees for
    display.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sim))
    numbers = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    }
    assert RISK_PAISE not in numbers and COST_PAISE not in numbers
    assert 1_000 not in numbers and 100_000 not in numbers
    assert {n for n in numbers if n > 2} == {100}


# ==============================================================================================
# Refusals -- a bad input must never become a share count
# ==============================================================================================


@pytest.mark.parametrize("risk", [0, -1, -100_000, 100_000.0, "100000", True, None])
def test_a_risk_amount_that_is_not_positive_whole_paise_is_refused(risk) -> None:
    """A float rupee amount, a string from a mis-parsed config, or a non-positive number must
    raise rather than size anything (CONTEXT 7-E11 bans floats in price arithmetic)."""
    with pytest.raises(sim.SimulateError):
        sim.position_size(risk, 500)


@pytest.mark.parametrize("per_share", [0, -500, 12.5, None])
def test_a_per_share_risk_that_is_not_positive_whole_paise_is_refused(per_share) -> None:
    """Zero or negative per-share risk never reaches here (chunk 7 refuses the day first),
    and a division by it would be a crash or a negative share count."""
    with pytest.raises(sim.SimulateError):
        sim.position_size(RISK_PAISE, per_share)


def test_simulate_day_refuses_a_bad_money_input() -> None:
    signal = sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))
    with pytest.raises(sim.SimulateError, match="risk_per_trade_paise"):
        sim.simulate_day(
            signal, F1_BARS, symbol="TCS", risk_per_trade_paise=0, cost_paise=COST_PAISE
        )
    with pytest.raises(sim.SimulateError, match="cost_paise"):
        sim.simulate_day(
            signal, F1_BARS, symbol="TCS", risk_per_trade_paise=RISK_PAISE, cost_paise=-1
        )


def test_an_unknown_exit_kind_is_refused_rather_than_priced_at_a_guess() -> None:
    """If chunk 7 ever marks an exit this module does not know how to price, it must raise --
    a default price would be an invented fill."""
    signal = sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))
    assert signal.entry is not None and signal.exit_event is not None
    broken = sig.ExitEvent(
        kind="teleported-out",
        stamp=signal.exit_event.stamp,
        close_stamp=signal.exit_event.close_stamp,
        both_touched=False,
        detail="not a CONTEXT 3.4-5 exit",
    )
    with pytest.raises(sim.SimulateError, match="unknown exit kind"):
        sim.exit_price_paise(signal.entry, broken, F1_BARS)


def test_a_square_off_naming_a_candle_that_is_not_there_is_refused() -> None:
    """The square-off price IS a candle's close; if that candle is missing from the bars the
    caller passed, there is nothing honest to price and the run must stop."""
    signal = sig.evaluate_day(
        SQUARE_OFF_LONG_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2030)
    )
    assert signal.entry is not None and signal.exit_event is not None
    assert signal.exit_event.kind == sig.EXIT_SQUARE_OFF
    with pytest.raises(sim.SimulateError, match="not among the"):
        sim.exit_price_paise(signal.entry, signal.exit_event, SQUARE_OFF_LONG_BARS[:2])


def test_a_target_or_stop_exit_needs_no_candles_at_all() -> None:
    """Pricing a level does not read the tape: only a square-off needs the bars. Pinned so a
    future refactor cannot start reading candle extremes into a level fill."""
    signal = sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))
    record = sim.simulate_day(
        signal, symbol="TCS", risk_per_trade_paise=RISK_PAISE, cost_paise=COST_PAISE
    )
    assert record.exit_paise == R(2052) and record.net_pnl_paise == R(2_900)


def test_an_unknown_side_is_refused() -> None:
    with pytest.raises(sim.SimulateError):
        sim.gross_pnl_paise("sideways", 10, R(2000), R(2010))


def test_the_rupee_formatter_is_exact_on_both_signs_and_the_half_rupee() -> None:
    """The report's own numbers go through this, so it is asserted rather than eyeballed."""
    assert sim.format_paise(299_250) == "Rs 2,992.50"
    assert sim.format_paise(-109_400) == "-Rs 1,094.00"
    assert sim.format_paise(0) == "Rs 0.00"
    assert sim.format_paise(5) == "Rs 0.05"
    assert sim.format_paise(-5) == "-Rs 0.05"


# ==============================================================================================
# Purity (CONTEXT 6)
# ==============================================================================================


def test_the_simulator_is_pure() -> None:
    """CONTEXT 6: the engines are pure functions over candles. No I/O, no network, no clock
    read -- and CONTEXT 7-E11 -- no float anywhere in the arithmetic, and no true division
    that could produce one."""
    import ast
    import inspect

    source = inspect.getsource(sim)
    tree = ast.parse(source)

    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {"__future__", "dataclasses", "datetime", "fractions", "typing", "signals"}, imported

    banned = {"now", "today", "utcnow", "fromtimestamp", "read_text", "write_text", "open", "round"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } | {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & banned), sorted(called & banned)

    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ], "no float literal may appear in the simulator (CONTEXT 7-E11)"
    assert not [
        node for node in ast.walk(tree) if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
    ], "no true division may appear in the simulator -- it would produce a float"


# ==============================================================================================
# The named REAL golden, read from the store (CLAUDE.md evidence rule; REVIEW_7 finding C3)
# ==============================================================================================

GOLDEN_SYMBOL = "HDFCBANK"
GOLDEN_DAY = date(2026, 6, 10)


def _store_context():
    """Build the evidence context, or skip when the local stores are not present.

    ``data/`` is gitignored (CONTEXT 6), so a bare clone genuinely cannot run this assertion;
    on the operator's machine -- where the numbers below were produced -- it runs. The skip
    names exactly what is missing so it can never be mistaken for a pass.
    """
    from acumen import trade_evidence as evidence

    config = load_config(include_env=False)
    data_dir = Path(config.path("data_dir"))
    for required in (data_dir / "minute_store", data_dir / "daily_store"):
        if not required.exists():
            pytest.skip(f"local store {required} is absent (data/ is gitignored)")
    return evidence.build_context()


def test_the_hdfcbank_2026_06_10_golden_prices_from_the_store() -> None:
    """**THE NAMED REAL GOLDEN** -- chunk 8's money on a real stored stock-day.

    HDFCBANK 2026-06-10 is the first real Rule-3 outside-bar bias day in this repo: chunk 7
    walked it candle by candle and REVIEW_7 re-derived every number from the parquet stores
    with its own arithmetic (bias BULLISH, all three CONTEXT 4.6 gates pass, POC **739.80**,
    ARMED at 738.20, trigger **740.95**, not a gap, stop **738.10**, target **749.50**, target
    hit on the candle closing 13:15).

    Chunk 8's arithmetic on top of that, HAND-COMPUTED:

    * per-share risk = 740.95 - 738.10 = **2.85 rupees = 285 paise**;
    * ``qty = floor(100,000 / 285)`` = **350** (350 x 285 = 99,750 <= 100,000;
      351 x 285 = 100,035 > 100,000);
    * TARGET fill at the level 749.50: gross = 350 x (74,950 - 74,095) = 350 x 855 =
      **299,250 paise = +Rs 2,992.50**;
    * net = 299,250 - 10,000 = **289,250 paise = +Rs 2,892.50**.

    Read from the store through the same path the evidence pack uses, so the pack's named
    line and this assertion cannot drift apart.
    """
    from acumen import trade_evidence as evidence

    context = _store_context()
    day = evidence.price_one(context, GOLDEN_SYMBOL, GOLDEN_DAY)
    record = day.record

    assert record is not None, day.stock_day.reason
    assert record.symbol == GOLDEN_SYMBOL and record.day == GOLDEN_DAY
    assert record.side == sig.LONG and record.bias == "bullish"
    assert record.poc_paise == Fraction(R(739.80))
    assert record.entry_paise == R(740.95)
    assert record.stop_paise == R(738.10)
    assert record.target_paise == R(749.50)
    assert record.per_share_risk_paise == R(2.85) == 285
    assert record.qty == 350
    assert record.exit_kind == sig.EXIT_TARGET
    assert record.exit_paise == R(749.50)
    assert record.gross_pnl_paise == 299_250
    assert record.net_pnl_paise == 289_250
    assert sim.format_paise(record.gross_pnl_paise) == "Rs 2,992.50"
    assert sim.format_paise(record.net_pnl_paise) == "Rs 2,892.50"


def test_the_committed_evidence_pack_states_the_same_named_golden() -> None:
    """The pack under `docs/evidence/` is committed BECAUSE a later session must be able to
    re-check a claim without redoing the work (CLAUDE.md's evidence rule, REVIEW_7 C3). If
    the code's answer ever moves, the committed line must move with it -- so the two are
    pinned to each other here, and this one test needs no store at all."""
    pack = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "chunk8_sweep.md"
    text = pack.read_text(encoding="utf-8")

    assert "HDFCBANK 2026-06-10" in text
    assert "qty floor(100,000 / 285) = 350" in text
    assert "gross Rs 2,992.50" in text
    assert "net Rs 2,892.50" in text
