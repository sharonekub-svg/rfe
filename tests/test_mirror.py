import datetime as dt

from congress_mirror.config import Settings
from congress_mirror.mirror import build_plan, net_open_positions
from tests.conftest import make_trade


def test_net_open_positions_nets_buys_and_sells():
    day = dt.date(2025, 6, 1)
    trades = [
        make_trade("AAA", "buy", day, amount=30000),
        make_trade("AAA", "sell", day, amount=10000),
        make_trade("BBB", "buy", day, amount=5000),
        make_trade("CCC", "buy", day, amount=4000),
        make_trade("CCC", "sell", day, amount=9000),  # net negative -> dropped
    ]
    net = net_open_positions(trades)
    assert net == {"AAA": 20000.0, "BBB": 5000.0}


def test_build_plan_respects_cap_and_deploy():
    day = dt.date(2025, 6, 1)
    # One huge name that would exceed the per-name cap.
    trades = [
        make_trade("BIG", "buy", day, amount=900000),
        make_trade("SM1", "buy", day, amount=50000),
        make_trade("SM2", "buy", day, amount=50000),
    ]
    cfg = Settings(deploy_fraction=1.0, max_position_fraction=0.15)
    equity = 100000.0
    plan = build_plan(trades, equity, cfg=cfg)
    by = {p.symbol: p for p in plan}

    # BIG capped at 15% of equity = $15,000.
    assert abs(by["BIG"].target_notional - 15000.0) < 1.0
    # Total deployed cannot exceed deploy_fraction * equity.
    assert sum(p.target_notional for p in plan) <= equity * cfg.deploy_fraction + 1.0
    # Weights sum to ~1.
    assert abs(sum(p.weight for p in plan) - 1.0) < 1e-6


def test_build_plan_filters_untradable():
    day = dt.date(2025, 6, 1)
    trades = [make_trade("AAA", "buy", day), make_trade("ZZZ", "buy", day)]
    cfg = Settings()
    plan = build_plan(trades, 100000.0, cfg=cfg, tradable={"AAA"})
    assert {p.symbol for p in plan} == {"AAA"}
