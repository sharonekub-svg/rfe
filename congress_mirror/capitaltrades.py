"""Client + parser for CapitalTrades congressional disclosure data.

CapitalTrades exposes a JSON backend (the "bff" host) that powers their site.
Endpoints and field names can change, and the site sits behind Cloudflare, so
all network access is funnelled through one place and the parsing is defensive:
unknown shapes are skipped rather than crashing the run.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Iterable

import requests

from .config import settings

# STOCK Act disclosure amount ranges -> representative midpoint (USD).
# Members report a bracket, not an exact figure, so we use the midpoint.
AMOUNT_BUCKETS: list[tuple[float, float]] = [
    (1_001, 15_000),
    (15_001, 50_000),
    (50_001, 100_000),
    (100_001, 250_000),
    (250_001, 500_000),
    (500_001, 1_000_000),
    (1_000_001, 5_000_000),
    (5_000_001, 25_000_000),
    (25_000_001, 50_000_000),
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def amount_midpoint(low: float | None, high: float | None) -> float:
    """Midpoint of a disclosed amount range, with sensible fallbacks."""
    if low and high:
        return (float(low) + float(high)) / 2.0
    if low:
        return float(low)
    if high:
        return float(high)
    return AMOUNT_BUCKETS[0][1]  # smallest bracket's high end


@dataclass
class Trade:
    politician_id: str
    politician_name: str
    ticker: str
    txn_type: str  # "buy" | "sell" | "exchange"
    txn_date: dt.date
    pub_date: dt.date | None
    amount_usd: float  # midpoint of disclosed range
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_buy(self) -> bool:
        return self.txn_type == "buy"

    @property
    def is_sell(self) -> bool:
        return self.txn_type == "sell"


@dataclass(frozen=True)
class Politician:
    id: str
    name: str
    trade_count: int = 0


def _parse_date(value: Any) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    s = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return dt.datetime.strptime(s[: len(fmt) + 6], fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _norm_txn_type(value: Any) -> str:
    s = str(value or "").lower()
    if "buy" in s or s in {"p", "purchase"}:
        return "buy"
    if "sell" in s or s in {"s", "sale"}:
        return "sell"
    if "exchange" in s:
        return "exchange"
    return s or "unknown"


def _norm_ticker(value: Any) -> str:
    s = str(value or "").strip().upper()
    # CapitalTrades sometimes suffixes exchange, e.g. "AAPL:US".
    return s.split(":")[0].strip()


class CapitalTradesClient:
    """Thin HTTP client. All parsing is tolerant of missing fields."""

    def __init__(self, base_url: str | None = None, session: requests.Session | None = None):
        self.base_url = (base_url or settings.capitaltrades_base_url).rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(_HEADERS)

    def _get(self, path: str, **params) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # --- raw fetchers -----------------------------------------------------
    def fetch_politicians(self, page_size: int = 50, pages: int = 2) -> list[Politician]:
        out: list[Politician] = []
        for page in range(1, pages + 1):
            data = self._get("politicians", page=page, pageSize=page_size)
            out.extend(parse_politicians(data))
        return out

    def fetch_trades_for(
        self, politician_id: str, since: dt.date, page_size: int = 100, max_pages: int = 10
    ) -> list[Trade]:
        out: list[Trade] = []
        for page in range(1, max_pages + 1):
            data = self._get(
                "trades",
                politician=politician_id,
                page=page,
                pageSize=page_size,
                txDateFrom=since.isoformat(),
            )
            batch = parse_trades(data)
            if not batch:
                break
            out.extend(batch)
            if len(batch) < page_size:
                break
        return [t for t in out if t.txn_date >= since]


# --- standalone parsers (unit-tested without network) ---------------------
def _records(data: Any) -> Iterable[dict]:
    """CapitalTrades wraps lists under 'data'; be tolerant of either shape."""
    if isinstance(data, dict):
        for key in ("data", "items", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    if isinstance(data, list):
        return data
    return []


def parse_politicians(data: Any) -> list[Politician]:
    out: list[Politician] = []
    for rec in _records(data):
        if not isinstance(rec, dict):
            continue
        pid = str(
            rec.get("_politicianId")
            or rec.get("politicianId")
            or rec.get("id")
            or ""
        )
        name = (
            rec.get("politicianName")
            or rec.get("fullName")
            or " ".join(
                p for p in [rec.get("firstName"), rec.get("lastName")] if p
            )
            or rec.get("name")
            or ""
        ).strip()
        if not pid or not name:
            continue
        stats = rec.get("stats") or {}
        count = int(stats.get("countTrades") or rec.get("countTrades") or 0)
        out.append(Politician(id=pid, name=name, trade_count=count))
    return out


def parse_trades(data: Any) -> list[Trade]:
    out: list[Trade] = []
    for rec in _records(data):
        if not isinstance(rec, dict):
            continue
        ticker = _norm_ticker(
            rec.get("ticker")
            or (rec.get("asset") or {}).get("assetTicker")
            or (rec.get("issuer") or {}).get("issuerTicker")
        )
        if not ticker or ticker in {"N/A", "--", "-"}:
            continue
        txn_date = _parse_date(rec.get("txDate") or rec.get("transactionDate"))
        if not txn_date:
            continue
        low = rec.get("valueLow") or (rec.get("size") or {}).get("low")
        high = rec.get("valueHigh") or (rec.get("size") or {}).get("high")
        out.append(
            Trade(
                politician_id=str(
                    rec.get("_politicianId") or rec.get("politicianId") or ""
                ),
                politician_name=(rec.get("politicianName") or "").strip(),
                ticker=ticker,
                txn_type=_norm_txn_type(rec.get("txType") or rec.get("type")),
                txn_date=txn_date,
                pub_date=_parse_date(rec.get("pubDate") or rec.get("publishedDate")),
                amount_usd=amount_midpoint(low, high),
                raw=rec,
            )
        )
    return out
