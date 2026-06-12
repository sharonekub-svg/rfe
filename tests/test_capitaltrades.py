import datetime as dt

from congress_mirror.capitaltrades import (
    amount_midpoint,
    parse_politicians,
    parse_trades,
)


def test_amount_midpoint():
    assert amount_midpoint(1001, 15000) == (1001 + 15000) / 2
    assert amount_midpoint(50000, None) == 50000
    assert amount_midpoint(None, None) > 0


def test_parse_politicians_handles_nested_stats():
    data = {
        "data": [
            {"_politicianId": "P1", "politicianName": "Jane Doe", "stats": {"countTrades": 42}},
            {"id": "P2", "firstName": "John", "lastName": "Roe", "countTrades": 7},
            {"garbage": True},  # skipped
        ]
    }
    pols = parse_politicians(data)
    assert [p.id for p in pols] == ["P1", "P2"]
    assert pols[0].trade_count == 42
    assert pols[1].name == "John Roe"


def test_parse_trades_normalises_ticker_and_type():
    data = {
        "data": [
            {
                "_politicianId": "P1",
                "politicianName": "Jane Doe",
                "ticker": "AAPL:US",
                "txType": "buy",
                "txDate": "2026-01-02",
                "pubDate": "2026-01-20",
                "valueLow": 1001,
                "valueHigh": 15000,
            },
            {  # missing ticker -> skipped
                "txType": "sell",
                "txDate": "2026-01-03",
            },
        ]
    }
    trades = parse_trades(data)
    assert len(trades) == 1
    t = trades[0]
    assert t.ticker == "AAPL"
    assert t.is_buy
    assert t.txn_date == dt.date(2026, 1, 2)
    assert t.amount_usd == (1001 + 15000) / 2
