"""Turn a top performer's disclosed positions into a paper-account portfolio."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .alpaca_client import AlpacaClient, Order
from .capitaltrades import Trade
from .config import Settings, settings


@dataclass
class TargetPosition:
    symbol: str
    weight: float       # fraction of deployed capital (0-1)
    target_notional: float


def net_open_positions(trades: list[Trade]) -> dict[str, float]:
    """Net disclosed exposure per ticker = sum(buys) - sum(sells), buys only kept.

    Returns {ticker: net_usd} for tickers with positive net exposure.
    """
    net: dict[str, float] = {}
    for t in trades:
        if t.is_buy:
            net[t.ticker] = net.get(t.ticker, 0.0) + t.amount_usd
        elif t.is_sell:
            net[t.ticker] = net.get(t.ticker, 0.0) - t.amount_usd
    return {sym: amt for sym, amt in net.items() if amt > 0}


def _finalize_plan(raw: dict[str, float], cap: float) -> list[TargetPosition]:
    """Apply the per-name cap (redistributing the excess) and build the plan."""
    # Apply per-name cap, then redistribute the trimmed excess to uncapped names.
    capped: dict[str, float] = {s: min(notional, cap) for s, notional in raw.items()}
    # Single redistribution pass keeps things simple and bounded.
    excess = sum(raw.values()) - sum(capped.values())
    if excess > 0:
        room = {s: cap - capped[s] for s in capped if cap - capped[s] > 0}
        room_total = sum(room.values())
        if room_total > 0:
            for s, r in room.items():
                capped[s] += excess * (r / room_total)

    plan_total = sum(capped.values()) or 1.0
    return [
        TargetPosition(symbol=s, weight=capped[s] / plan_total, target_notional=round(capped[s], 2))
        for s in sorted(capped, key=lambda k: capped[k], reverse=True)
        if capped[s] >= 1.0  # Alpaca minimum notional is $1
    ]


def build_plan(
    trades: list[Trade],
    equity: float,
    cfg: Settings | None = None,
    tradable: set[str] | None = None,
) -> list[TargetPosition]:
    """Allocate `deploy_fraction` of equity across net open positions.

    Weights are proportional to net disclosed exposure, then each name is capped
    at `max_position_fraction` of equity and weights are renormalised.
    """
    cfg = cfg or settings
    net = net_open_positions(trades)
    if tradable is not None:
        net = {s: a for s, a in net.items() if s in tradable}
    total = sum(net.values())
    if total <= 0 or equity <= 0:
        return []

    deploy = cfg.deploy_fraction * equity
    cap = cfg.max_position_fraction * equity
    raw = {s: (a / total) * deploy for s, a in net.items()}
    return _finalize_plan(raw, cap)


def build_multi_leader_plan(
    trades_by_leader: list[list[Trade]],
    equity: float,
    cfg: Settings | None = None,
    tradable: set[str] | None = None,
) -> list[TargetPosition]:
    """Diversify deployed capital *equally* across several leaders.

    Each leader receives an equal slice of the deploy budget, allocated across
    that leader's own net open positions (proportional to disclosed exposure).
    Slices are then merged per ticker, so a name held by several leaders adds
    up. The per-name cap (relative to total equity) is applied to the merge, so
    single-name risk stays bounded regardless of how many leaders we follow.
    """
    cfg = cfg or settings
    nets: list[dict[str, float]] = []
    for trades in trades_by_leader:
        net = net_open_positions(trades)
        if tradable is not None:
            net = {s: a for s, a in net.items() if s in tradable}
        if sum(net.values()) > 0:
            nets.append(net)
    if not nets or equity <= 0:
        return []

    deploy = cfg.deploy_fraction * equity
    budget_each = deploy / len(nets)
    cap = cfg.max_position_fraction * equity

    raw: dict[str, float] = {}
    for net in nets:
        total = sum(net.values())
        for s, a in net.items():
            raw[s] = raw.get(s, 0.0) + budget_each * (a / total)
    return _finalize_plan(raw, cap)


@dataclass
class MirrorResult:
    equity: float
    plan: list[TargetPosition]
    orders: list[Order]
    skipped: list[str]
    dry_run: bool


def _orders_for_plan(
    client: AlpacaClient, plan: list[TargetPosition], cfg: Settings
) -> tuple[list[Order], list[str]]:
    """Top up each planned name to its target; never sells existing holdings."""
    held = {p["symbol"]: float(p.get("market_value", 0.0)) for p in client.list_positions()}
    orders: list[Order] = []
    skipped: list[str] = []
    for tp in plan:
        already = held.get(tp.symbol, 0.0)
        delta = tp.target_notional - already
        if delta < 1.0:  # close enough / below Alpaca min
            skipped.append(tp.symbol)
            continue
        if cfg.dry_run:
            orders.append(Order(symbol=tp.symbol, notional=delta, side="buy", status="dry_run"))
        else:
            orders.append(client.submit_notional_order(tp.symbol, delta, side="buy"))
    return orders, skipped


def execute_mirror(
    client: AlpacaClient,
    trades: list[Trade],
    cfg: Settings | None = None,
    today: dt.date | None = None,
) -> MirrorResult:
    """Build a plan and (unless DRY_RUN) place notional buy orders to reach it.

    Only names not already held at/above target are topped up. Existing holdings
    are never sold here — `daily` handles rotation when the top performer rotates.
    """
    cfg = cfg or settings
    equity = client.equity()

    candidates = {t.ticker for t in trades if t.is_buy}
    tradable = {s for s in candidates if client.is_tradable(s)}
    plan = build_plan(trades, equity, cfg=cfg, tradable=tradable)
    orders, skipped = _orders_for_plan(client, plan, cfg)

    return MirrorResult(
        equity=equity, plan=plan, orders=orders, skipped=skipped, dry_run=cfg.dry_run
    )


def execute_multi_mirror(
    client: AlpacaClient,
    trades_by_leader: list[list[Trade]],
    cfg: Settings | None = None,
    today: dt.date | None = None,
) -> MirrorResult:
    """Mirror several leaders at once, diversifying capital equally across them.

    Same top-up semantics as `execute_mirror`: positions are only added to, never
    sold; rotation between runs is handled by `daily`.
    """
    cfg = cfg or settings
    equity = client.equity()

    candidates = {t.ticker for trades in trades_by_leader for t in trades if t.is_buy}
    tradable = {s for s in candidates if client.is_tradable(s)}
    plan = build_multi_leader_plan(trades_by_leader, equity, cfg=cfg, tradable=tradable)
    orders, skipped = _orders_for_plan(client, plan, cfg)

    return MirrorResult(
        equity=equity, plan=plan, orders=orders, skipped=skipped, dry_run=cfg.dry_run
    )
