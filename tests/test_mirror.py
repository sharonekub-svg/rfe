import datetime as dt

from congress_mirror.config import Settings
from congress_mirror.mirror import (
    build_multi_leader_plan,
    build_plan,
    net_open_positions,
)
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


def test_multi_leader_splits_capital_equally_across_leaders():
    day = dt.date(2025, 6, 1)
    # Leader A trades a much larger dollar amount than leader B, but with equal
    # diversification each leader should command the same slice of capital.
    leader_a = [make_trade("AAA", "buy", day, amount=900000, pid="A")]
    leader_b = [make_trade("BBB", "buy", day, amount=10000, pid="B")]
    cfg = Settings(deploy_fraction=1.0, max_position_fraction=1.0)
    equity = 100000.0
    plan = build_multi_leader_plan([leader_a, leader_b], equity, cfg=cfg)
    by = {p.symbol: p for p in plan}

    # Despite A's far larger disclosed size, each single-name leader gets ~half.
    assert abs(by["AAA"].target_notional - 50000.0) < 1.0
    assert abs(by["BBB"].target_notional - 50000.0) < 1.0
    assert sum(p.target_notional for p in plan) <= equity * cfg.deploy_fraction + 1.0


def test_multi_leader_merges_shared_names_and_caps():
    day = dt.date(2025, 6, 1)
    # Both leaders hold MSFT; their slices should add up, then hit the cap.
    leader_a = [make_trade("MSFT", "buy", day, amount=10000, pid="A")]
    leader_b = [make_trade("MSFT", "buy", day, amount=10000, pid="B")]
    cfg = Settings(deploy_fraction=1.0, max_position_fraction=0.15)
    equity = 100000.0
    plan = build_multi_leader_plan([leader_a, leader_b], equity, cfg=cfg)
    by = {p.symbol: p for p in plan}

    # Merged slice (50% + 50% = 100% of deploy) is capped at 15% of equity.
    assert abs(by["MSFT"].target_notional - 15000.0) < 1.0


def test_multi_leader_skips_empty_leaders():
    day = dt.date(2025, 6, 1)
    leader_a = [make_trade("AAA", "buy", day, amount=20000, pid="A")]
    leader_empty = [make_trade("CCC", "sell", day, amount=5000, pid="C")]  # no open buys
    cfg = Settings(deploy_fraction=1.0, max_position_fraction=1.0)
    plan = build_multi_leader_plan([leader_a, leader_empty], 100000.0, cfg=cfg)
    by = {p.symbol: p for p in plan}
    # Only one contributing leader -> it gets the whole deploy budget.
    assert abs(by["AAA"].target_notional - 100000.0) < 1.0
