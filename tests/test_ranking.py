import datetime as dt

from congress_mirror.ranking import compute_legs, rank_politicians, score_politician
from tests.conftest import FakePricer, make_trade


def test_open_leg_uses_latest_price():
    buy_day = dt.date(2025, 6, 1)
    trades = [make_trade("AAA", "buy", buy_day, amount=10000)]
    pricer = FakePricer(closes={("AAA", buy_day): 100.0}, now={"AAA": 150.0})
    legs = compute_legs(trades, pricer, today=dt.date(2026, 1, 15))
    assert len(legs) == 1
    assert legs[0].exit_date is None
    assert abs(legs[0].ret - 0.5) < 1e-9  # 100 -> 150 == +50%


def test_closed_leg_uses_sell_price():
    buy_day = dt.date(2025, 6, 1)
    sell_day = dt.date(2025, 9, 1)
    trades = [
        make_trade("BBB", "buy", buy_day, amount=10000),
        make_trade("BBB", "sell", sell_day, amount=10000),
    ]
    pricer = FakePricer(
        closes={("BBB", buy_day): 100.0, ("BBB", sell_day): 80.0},
        now={"BBB": 999.0},  # must be ignored for a closed leg
    )
    legs = compute_legs(trades, pricer)
    assert legs[0].exit_date == sell_day
    assert abs(legs[0].ret + 0.2) < 1e-9  # 100 -> 80 == -20%


def test_weighted_score_and_skip_unpriced(politician):
    buy_day = dt.date(2025, 6, 1)
    trades = [
        make_trade("AAA", "buy", buy_day, amount=30000),  # +50%, weight 30k
        make_trade("BBB", "buy", buy_day, amount=10000),  # -20%, weight 10k
        make_trade("CCC", "buy", buy_day, amount=99999),  # unpriced -> skipped
    ]
    pricer = FakePricer(
        closes={("AAA", buy_day): 100.0, ("BBB", buy_day): 100.0},
        now={"AAA": 150.0, "BBB": 80.0},
    )
    scored = score_politician(politician, trades, pricer)
    # (30000*0.5 + 10000*-0.2) / 40000 = (15000 - 2000)/40000 = 0.325
    assert abs(scored.score - 0.325) < 1e-9
    assert scored.n_legs == 2


def test_rank_filters_inactive(politician):
    from congress_mirror.capitaltrades import Politician

    buy_day = dt.date(2025, 6, 1)
    active = politician
    inactive = Politician(id="P2", name="Few Trades", trade_count=2)
    pricer = FakePricer(closes={("AAA", buy_day): 100.0}, now={"AAA": 200.0})
    trades_by = {
        active: [make_trade("AAA", "buy", buy_day) for _ in range(8)],
        inactive: [make_trade("AAA", "buy", buy_day) for _ in range(2)],
    }
    ranked = rank_politicians(trades_by, pricer, min_trades=8)
    assert [r.politician.id for r in ranked] == ["P1"]
