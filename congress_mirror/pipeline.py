"""Orchestration shared by the CLI commands."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .alpaca_client import AlpacaClient
from .capitaltrades import CapitalTradesClient, Politician, Trade
from .config import Settings, settings
from .mirror import MirrorResult, execute_multi_mirror
from .ranking import RankedPolitician, rank_politicians


def twelve_months_ago(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return today - dt.timedelta(days=365)


@dataclass
class RankOutcome:
    ranked: list[RankedPolitician]
    trades_by_politician: dict[Politician, list[Trade]]


def gather_and_rank(
    ct: CapitalTradesClient,
    pricer,
    cfg: Settings | None = None,
    today: dt.date | None = None,
) -> RankOutcome:
    """Fetch the most-active politicians + their trailing-year trades and rank."""
    cfg = cfg or settings
    since = twelve_months_ago(today)

    politicians = ct.fetch_politicians(page_size=50, pages=3)
    politicians.sort(key=lambda p: p.trade_count, reverse=True)
    universe = politicians[: cfg.rank_universe_size]

    trades_by: dict[Politician, list[Trade]] = {}
    for pol in universe:
        trades_by[pol] = ct.fetch_trades_for(pol.id, since)

    ranked = rank_politicians(
        trades_by, pricer, min_trades=cfg.min_trades_12m, today=today
    )
    return RankOutcome(ranked=ranked, trades_by_politician=trades_by)


@dataclass
class DailyOutcome:
    ranked: list[RankedPolitician]
    leaders: list[Politician]
    leaders_trades: dict[Politician, list[Trade]]
    new_disclosures: list[Trade]
    mirror: MirrorResult


def run_daily(
    ct: CapitalTradesClient,
    alpaca: AlpacaClient,
    seen_store,
    cfg: Settings | None = None,
    today: dt.date | None = None,
) -> DailyOutcome | None:
    cfg = cfg or settings
    outcome = gather_and_rank(ct, alpaca, cfg=cfg, today=today)
    if not outcome.ranked:
        return None

    top = outcome.ranked[: max(1, cfg.top_n_leaders)]
    leaders = [r.politician for r in top]
    leaders_trades = {p: outcome.trades_by_politician.get(p, []) for p in leaders}
    all_trades = [t for trades in leaders_trades.values() for t in trades]

    new = seen_store.new_trades(all_trades)
    mirror = execute_multi_mirror(
        alpaca, list(leaders_trades.values()), cfg=cfg, today=today
    )
    seen_store.mark(all_trades)

    return DailyOutcome(
        ranked=outcome.ranked,
        leaders=leaders,
        leaders_trades=leaders_trades,
        new_disclosures=new,
        mirror=mirror,
    )
