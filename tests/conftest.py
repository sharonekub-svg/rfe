import datetime as dt

import pytest

from congress_mirror.capitaltrades import Politician, Trade


class FakePricer:
    """Deterministic pricer for offline tests.

    daily_close returns a price seeded per (symbol, date); latest_price returns
    a fixed "now" price per symbol so returns are predictable.
    """

    def __init__(self, closes: dict[tuple[str, dt.date], float], now: dict[str, float]):
        self._closes = closes
        self._now = now

    def daily_close(self, symbol: str, on: dt.date):
        return self._closes.get((symbol, on))

    def latest_price(self, symbol: str):
        return self._now.get(symbol)


@pytest.fixture
def d():
    return dt.date(2026, 1, 15)


@pytest.fixture
def politician():
    return Politician(id="P1", name="Jane Doe", trade_count=12)


def make_trade(ticker, ttype, day, amount=10000.0, pid="P1", name="Jane Doe"):
    return Trade(
        politician_id=pid,
        politician_name=name,
        ticker=ticker,
        txn_type=ttype,
        txn_date=day,
        pub_date=day,
        amount_usd=amount,
    )
