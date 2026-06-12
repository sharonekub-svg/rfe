"""Rank politicians by an approximate trailing-12-month return.

Methodology (and its limits):
  * Disclosures report a dollar *range* and lag the actual trade by up to ~45
    days, so this is an estimate, not a P&L statement.
  * For each disclosed BUY in the window we take the entry price on the
    transaction date and an exit price at either the first subsequent SELL of
    the same ticker (a "closed" leg) or the latest price (an "open" leg).
  * Each leg's return is weighted by the midpoint of its disclosed amount, and
    a politician's score is the amount-weighted average return across legs.
  * Legs whose prices cannot be resolved are skipped. A politician with no
    priced legs is excluded from the ranking.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol

from .capitaltrades import Politician, Trade


class Pricer(Protocol):
    def daily_close(self, symbol: str, on: dt.date) -> float | None: ...
    def latest_price(self, symbol: str) -> float | None: ...


@dataclass
class Leg:
    ticker: str
    entry_date: dt.date
    exit_date: dt.date | None  # None => still open
    weight: float
    ret: float  # fractional return, e.g. 0.12 == +12%


@dataclass
class RankedPolitician:
    politician: Politician
    score: float  # weighted average return
    n_legs: int
    total_weight: float
    legs: list[Leg]


def _first_sell_after(trades: list[Trade], ticker: str, after: dt.date) -> dt.date | None:
    sells = sorted(
        t.txn_date for t in trades if t.ticker == ticker and t.is_sell and t.txn_date >= after
    )
    return sells[0] if sells else None


def compute_legs(trades: list[Trade], pricer: Pricer, today: dt.date | None = None) -> list[Leg]:
    """Build priced return legs from one politician's trades."""
    today = today or dt.date.today()
    legs: list[Leg] = []
    for t in trades:
        if not t.is_buy:
            continue
        entry = pricer.daily_close(t.ticker, t.txn_date)
        if not entry:
            continue
        exit_date = _first_sell_after(trades, t.ticker, t.txn_date)
        if exit_date and exit_date > t.txn_date:
            exit_price = pricer.daily_close(t.ticker, exit_date)
        else:
            exit_date = None
            exit_price = pricer.latest_price(t.ticker)
        if not exit_price:
            continue
        legs.append(
            Leg(
                ticker=t.ticker,
                entry_date=t.txn_date,
                exit_date=exit_date,
                weight=t.amount_usd,
                ret=(exit_price / entry) - 1.0,
            )
        )
    return legs


def score_politician(
    politician: Politician, trades: list[Trade], pricer: Pricer, today: dt.date | None = None
) -> RankedPolitician | None:
    legs = compute_legs(trades, pricer, today=today)
    total_w = sum(l.weight for l in legs)
    if not legs or total_w <= 0:
        return None
    weighted = sum(l.weight * l.ret for l in legs) / total_w
    return RankedPolitician(
        politician=politician,
        score=weighted,
        n_legs=len(legs),
        total_weight=total_w,
        legs=legs,
    )


def rank_politicians(
    trades_by_politician: dict[Politician, list[Trade]],
    pricer: Pricer,
    min_trades: int = 8,
    today: dt.date | None = None,
) -> list[RankedPolitician]:
    """Rank the *active* politicians (>= min_trades) by weighted return, desc."""
    ranked: list[RankedPolitician] = []
    for pol, trades in trades_by_politician.items():
        if len(trades) < min_trades:
            continue
        scored = score_politician(pol, trades, pricer, today=today)
        if scored is not None:
            ranked.append(scored)
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked
