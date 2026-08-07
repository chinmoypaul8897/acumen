"""The per-stock POINTS view (Round 4, the trader's own request) -- hand-computed first.

The trader superseded his Q43 capital question and asked instead for a view in POINTS: the
per-share move each trade made, so that what he reads does not move with the size the machine
happened to take. Everything asserted here was worked out by hand in the docstrings below BEFORE
the module was written, which is the only way a golden means anything.

Two properties matter more than any single figure and are asserted as properties, not as
examples:

* **size-independence** -- two identical trades taken in 1 share and in 10,000 shares produce the
  same points, and the rupee PnL that separates them is not consulted anywhere;
* **the drawdown is a WALK, not a difference** -- a symbol that ends level after a fall shows the
  fall, and a symbol whose first trade loses shows a drawdown from a peak of zero.

Offline and pure: this file reads no store and no committed artefact.
"""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction

import pytest

from acumen import points_view as pv
from acumen import signals as sig
from acumen.backtest import LedgerRow


def row(symbol: str, day: int, side: str, entry: int, exit_: int, *, qty: int = 100) -> LedgerRow:
    """One executed ledger row, priced in whole paise. Only the fields points reads matter."""
    stamp = datetime(2026, 4, day, 11, 30)
    move = (exit_ - entry) if side == sig.LONG else (entry - exit_)
    return LedgerRow(
        symbol=symbol,
        day=date(2026, 4, day),
        status="evaluated",
        reason="",
        side=side,
        executed=True,
        entry_paise=entry,
        exit_paise=exit_,
        entry_close_stamp=stamp,
        exit_close_stamp=stamp,
        qty=qty,
        gross_pnl_paise=move * qty,
        net_pnl_paise=move * qty - 10_000,
    )


#: THE HAND-COMPUTED LEDGER -- six trades on two symbols, every figure derived below.
#:
#:   AAA  1  long   entry 10,000  exit 10,250  -> +250          cumulative  +250
#:   AAA  2  long   entry 10,300  exit 10,200  -> -100          cumulative  +150
#:   AAA  3  short  entry 10,500  exit 10,400  -> +100          cumulative  +250
#:   BBB  4  short  entry  5,000  exit  5,200  -> -200          cumulative  -200
#:   BBB  5  long   entry  5,100  exit  5,100  ->    0          cumulative  -200
#:   BBB  6  long   entry  5,000  exit  5,350  -> +350          cumulative  +150
FIXTURE = (
    row("AAA", 1, sig.LONG, 10_000, 10_250),
    row("AAA", 2, sig.LONG, 10_300, 10_200),
    row("AAA", 3, sig.SHORT, 10_500, 10_400),
    row("BBB", 4, sig.SHORT, 5_000, 5_200),
    row("BBB", 5, sig.LONG, 5_100, 5_100),
    row("BBB", 6, sig.LONG, 5_000, 5_350),
)


def test_one_trades_points_are_the_signed_per_share_move_on_both_sides() -> None:
    """A long makes what the price rose; a short makes what it fell. Nothing else is consulted.

    HAND-COMPUTED: long 10,000 -> 10,250 is +250 paise per share; the same prices SHORT are
    -250. Short 10,500 -> 10,400 is +100; the same prices long are -100.
    """
    assert pv.points_paise(row("AAA", 1, sig.LONG, 10_000, 10_250)) == 250
    assert pv.points_paise(row("AAA", 1, sig.SHORT, 10_000, 10_250)) == -250
    assert pv.points_paise(row("AAA", 1, sig.SHORT, 10_500, 10_400)) == 100
    assert pv.points_paise(row("AAA", 1, sig.LONG, 10_500, 10_400)) == -100


def test_points_do_not_move_with_SIZE_which_is_the_whole_reason_the_view_exists() -> None:
    """The same trade in 1 share and in 10,000 gives the same points and different rupees."""
    small = row("AAA", 1, sig.LONG, 10_000, 10_250, qty=1)
    large = row("AAA", 1, sig.LONG, 10_000, 10_250, qty=10_000)
    assert pv.points_paise(small) == pv.points_paise(large) == 250
    assert small.gross_pnl_paise != large.gross_pnl_paise
    assert pv.per_symbol((small,))[0].points_paise == pv.per_symbol((large,))[0].points_paise


def test_the_per_symbol_table_is_hand_computed_row_by_row() -> None:
    """Every field of both rows, derived above.

    **AAA** -- three trades (+250, -100, +100).

    * points gross = 250 - 100 + 100 = **+250**;
    * winners = 2 of 3, so the win rate is **2/3**; no flat trade;
    * average = 250 / 3 points;
    * cumulative walk 250, 150, 250 against a running peak of 0, 250, 250 -> the deepest fall is
      250 - 150 = **100**;
    * best **+250**, worst **-100**.

    **BBB** -- three trades (-200, 0, +350).

    * points gross = -200 + 0 + 350 = **+150**;
    * winners = 1, losers = 1, flat = 1, so the win rate is **1/3** over all three trades;
    * average = 150 / 3 = **50**;
    * cumulative walk -200, -200, +150 against a running peak that STARTS AT ZERO -> the deepest
      fall is 0 - (-200) = **200**, which is the point of seeding the peak at the start rather
      than at the first trade;
    * best **+350**, worst **-200**.

    Order: by points gross, biggest first, so AAA (250) precedes BBB (150).
    """
    table = pv.per_symbol(FIXTURE)
    assert [one.symbol for one in table] == ["AAA", "BBB"]

    aaa, bbb = table
    assert (aaa.trades, aaa.winners, aaa.losers, aaa.flat) == (3, 2, 1, 0)
    assert aaa.points_paise == 250
    assert aaa.win_rate == Fraction(2, 3)
    assert aaa.avg_points_paise == Fraction(250, 3)
    assert aaa.max_drawdown_paise == 100
    assert (aaa.best_paise, aaa.worst_paise) == (250, -100)
    assert (aaa.best_day, aaa.worst_day) == (date(2026, 4, 1), date(2026, 4, 2))

    assert (bbb.trades, bbb.winners, bbb.losers, bbb.flat) == (3, 1, 1, 1)
    assert bbb.points_paise == 150
    assert bbb.win_rate == Fraction(1, 3)
    assert bbb.avg_points_paise == Fraction(50)
    assert bbb.max_drawdown_paise == 200
    assert (bbb.best_paise, bbb.worst_paise) == (350, -200)


def test_the_drawdown_is_a_walk_and_a_recovered_fall_is_still_shown() -> None:
    """A symbol that ends exactly level after falling 300 shows 300, not 0.

    HAND-COMPUTED: +100, -300, +200 -> cumulative 100, -200, 0; peak 100 -> deepest fall
    100 - (-200) = **300**; gross 0; and a symbol that only ever rises has a drawdown of 0.
    """
    rocky = (row("CCC", 1, sig.LONG, 10_000, 10_100),
             row("CCC", 2, sig.LONG, 10_000, 9_700),
             row("CCC", 3, sig.LONG, 10_000, 10_200))
    only_up = (row("DDD", 1, sig.LONG, 10_000, 10_100),
               row("DDD", 2, sig.LONG, 10_000, 10_050))
    (ccc,) = pv.per_symbol(rocky)
    (ddd,) = pv.per_symbol(only_up)
    assert ccc.points_paise == 0 and ccc.max_drawdown_paise == 300
    assert ddd.points_paise == 150 and ddd.max_drawdown_paise == 0


def test_the_walk_is_in_TIME_order_however_the_rows_arrive() -> None:
    """The ledger is per-symbol-shard ordered; a drawdown read out of order is a fiction."""
    forwards = pv.per_symbol(FIXTURE)
    backwards = pv.per_symbol(tuple(reversed(FIXTURE)))
    assert forwards == backwards


def test_non_executed_rows_are_not_trades_and_a_priceless_trade_is_REFUSED() -> None:
    """A refused day has no move to contribute; an executed row with no exit is a data fault
    and is raised rather than silently skipped or counted as zero."""
    refused = LedgerRow(symbol="AAA", day=date(2026, 4, 7), status="refused", reason="no-data")
    assert pv.per_symbol((refused,)) == ()
    assert pv.per_symbol(FIXTURE + (refused,)) == pv.per_symbol(FIXTURE)

    broken = row("AAA", 8, sig.LONG, 10_000, 10_100)
    broken = LedgerRow(**{**broken.__dict__, "exit_paise": None})
    with pytest.raises(pv.PointsError):
        pv.per_symbol((broken,))


def test_the_totals_are_the_sum_of_the_symbols_and_the_ledgers_own_trades() -> None:
    """HAND-COMPUTED: 250 + 150 = **400** points over **6** trades on **2** symbols, 3 winners."""
    total = pv.totals(pv.per_symbol(FIXTURE))
    assert total.symbols == 2 and total.trades == 6
    assert total.points_paise == 400
    assert total.winners == 3
    assert total.win_rate == Fraction(1, 2)


def test_points_are_formatted_as_points_and_never_as_rupees() -> None:
    """A point is a rupee of price on ONE share -- printing it with a rupee sign is exactly the
    confusion the view exists to remove, so the formatter carries no currency at all."""
    assert pv.format_points(250) == "+2.50"
    assert pv.format_points(-100) == "-1.00"
    assert pv.format_points(0) == "0.00"
    assert pv.format_points(123_456_789) == "+1,234,567.89"
    assert pv.format_points(Fraction(250, 3)) == "+0.83"
    assert "Rs" not in pv.format_points(250)
    # a MAGNITUDE -- a cost, a drawdown -- carries no leading plus, which would read as a gain
    assert pv.format_points(10_000, signed=False) == "100.00"
    assert pv.format_points(-100, signed=False) == "-1.00"


def test_the_mandatory_caveat_computes_its_own_two_numbers() -> None:
    """The architect made the multiple-comparisons caveat mandatory on any ranking. It is a
    TEMPLATE: a table of a different size cannot inherit this one's arithmetic.

    HAND-COMPUTED at the conventional one-in-twenty rate: 204 stocks -> 204/20 = 10.2 -> **10**
    that look good on no edge at all; 40 -> 2; 19 -> 0.
    """
    assert pv.by_chance(204) == 10
    assert pv.by_chance(40) == 2 and pv.by_chance(19) == 0
    sentence = pv.MULTIPLE_COMPARISONS_CAVEAT.format(symbols=204, by_chance=pv.by_chance(204))
    assert sentence.startswith("204 stocks ranked: even a no-edge system shows about 10 ")
    assert "never as proof." in sentence


def test_the_ends_of_the_ranking_never_print_the_same_stock_twice() -> None:
    """A short table would otherwise appear in both halves and read as more evidence."""
    table = pv.per_symbol(FIXTURE)
    top, bottom = pv.ends(table, each_end=20)
    assert [one.symbol for one in top] == ["AAA"]
    assert [one.symbol for one in bottom] == ["BBB"]
    assert not {one.symbol for one in top} & {one.symbol for one in bottom}
    wide = pv.per_symbol(FIXTURE)
    assert pv.ends(wide, each_end=1) == ((wide[0],), (wide[-1],))


def test_the_cost_in_points_is_the_cost_divided_by_ONE_share() -> None:
    """The honesty line on the page: at one share the flat cost IS its own number of points.

    HAND-COMPUTED: a 100-rupee round trip is 10,000 paise, and one share of it is 10,000 paise
    of price -- 100 points. At 350 shares the same cost is 100/350 of a point per share, which
    is why this view says out loud that it ignores size.
    """
    assert pv.cost_in_points_paise(10_000, shares=1) == Fraction(10_000)
    assert pv.cost_in_points_paise(10_000, shares=350) == Fraction(10_000, 350)
    with pytest.raises(pv.PointsError):
        pv.cost_in_points_paise(10_000, shares=0)


# --- REVIEW_12_2 findings C7 and C8 --------------------------------------------------------------


def test_a_move_too_small_to_survive_rounding_STILL_SHOWS_ITS_DIRECTION() -> None:
    """REVIEW_12_2 finding C7. The sign is taken from the value handed in, not from the
    quantized one, so a column whose convention is "a sign is always there" keeps it.

    HAND-COMPUTED. Half a paisa either way is the boundary: `Fraction(1, 2)` paise is
    0.005 rupees, which quantizes to nothing at two places but is not nothing. Seven rows of the
    204-row companion sat exactly here -- an average move under half a paisa beside a *Points*
    column carrying thousands of rupees, printed without a sign.
    """
    tiny_gain, tiny_loss = Fraction(1, 2), Fraction(-1, 2)
    assert pv.format_points(tiny_gain).startswith("+"), "a gain too small to print is a gain"
    assert pv.format_points(tiny_loss).startswith("-"), "and a loss too small to print is a loss"
    assert pv.format_points(tiny_gain).endswith("0.00") and pv.format_points(
        tiny_loss).endswith("0.00"), "the magnitude still rounds away; only the sign survives"

    # an EXACT zero is genuinely neither, and still prints neither
    assert pv.format_points(0) == "0.00" and pv.format_points(Fraction(0)) == "0.00"
    # ...and nothing that does not round to nothing has moved
    assert pv.format_points(250) == "+2.50" and pv.format_points(-100) == "-1.00"
    # a MAGNITUDE still refuses the leading plus, and still shows a minus if one ever arrives
    assert pv.format_points(tiny_gain, signed=False).endswith("0.00")
    assert not pv.format_points(tiny_gain, signed=False).startswith("+")


def test_the_totals_carry_the_flat_trades_page_7_has_to_state() -> None:
    """REVIEW_12_2 finding Q3. The win rate's denominator is EVERY trade (E13), so the trades
    that ended exactly level are inside it and in neither named side of it -- a page that prints
    the rate has to say how many there are.

    HAND-COMPUTED from the fixture above: BBB day 5 entered and exited at 5,100, so it is the
    one flat trade, on one of the two symbols. The rate is 3 winners over all 6 trades.
    """
    table = pv.per_symbol(FIXTURE)
    totals = pv.totals(table)
    assert totals.flat == 1 and totals.symbols_with_a_flat == 1
    assert totals.trades == 6 and totals.winners == 3
    assert totals.win_rate == Fraction(3, 6), "flats are in the denominator, not removed from it"
    assert totals.flat == sum(one.flat for one in table)
    assert totals.winners + totals.flat + sum(one.losers for one in table) == totals.trades


def test_the_trade_ORDER_is_safe_only_because_one_stock_trades_once_a_day() -> None:
    """REVIEW_12_2 finding C8, PINNED rather than fixed -- it is latent, not live.

    `_ordered` sorts on `(day, entry_close_stamp or day, symbol)`. The second element mixes a
    `datetime` with a `date`, which Python refuses to compare, so it would raise `TypeError` the
    moment two rows of the same symbol tied on `day` with one of them carrying no stamp. That
    cannot happen under CONTEXT 3.4 (R1-Q16: at most one trade per stock per day), so the second
    element is never reached and the ledger holds zero executed rows without a stamp.

    Both halves are asserted here: the safe case, which is every real case, and the unreachable
    one, so that a future change making a second same-day trade legal turns this red with an
    explanation attached instead of raising in a report generator.
    """
    stamped = row("AAA", 1, sig.LONG, 10_000, 10_250)
    unstamped = LedgerRow(
        symbol="AAA", day=date(2026, 4, 1), status="evaluated", reason="", side=sig.LONG,
        executed=True, entry_paise=10_000, exit_paise=10_100, entry_close_stamp=None,
    )

    # SAFE: distinct days, so the stamp is never compared against a date
    later = row("AAA", 2, sig.LONG, 10_000, 10_100)
    assert [one.day for one in pv._ordered([later, unstamped])] == [
        date(2026, 4, 1), date(2026, 4, 2),
    ]
    # SAFE: same day, DIFFERENT symbols -- ties break on `day` alone only when both stamps exist,
    # and here the missing stamp is compared against another date, not a datetime
    other = LedgerRow(
        symbol="BBB", day=date(2026, 4, 1), status="evaluated", reason="", side=sig.LONG,
        executed=True, entry_paise=1, exit_paise=2, entry_close_stamp=None,
    )
    assert [one.symbol for one in pv._ordered([other, unstamped])] == ["AAA", "BBB"]

    # LATENT: same day, same symbol, one stamped and one not -- CONTEXT 3.4 forbids it, and if
    # it ever became legal this is what would happen.
    with pytest.raises(TypeError):
        pv._ordered([stamped, unstamped])
