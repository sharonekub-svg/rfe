"""Minimal Alpaca REST client (paper trading only) using the public HTTP API.

We talk to the REST endpoints directly with `requests` to keep dependencies
small and the behaviour transparent. The client refuses to operate against a
non-paper endpoint as a hard safety guard.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

from .config import Settings, settings


class NotPaperError(RuntimeError):
    """Raised if the configured endpoint is not an Alpaca paper endpoint."""


@dataclass
class Order:
    symbol: str
    notional: float
    side: str
    status: str
    id: str = ""


class AlpacaClient:
    def __init__(self, cfg: Settings | None = None, session: requests.Session | None = None):
        self.cfg = cfg or settings
        self.cfg.require_alpaca()
        if not self.cfg.is_paper:
            raise NotPaperError(
                f"Refusing to run against non-paper endpoint: {self.cfg.alpaca_base_url}. "
                "This tool only trades paper accounts."
            )
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": self.cfg.alpaca_key_id,
                "APCA-API-SECRET-KEY": self.cfg.alpaca_secret,
            }
        )

    # --- trading API ------------------------------------------------------
    def _t(self, path: str) -> str:
        return f"{self.cfg.alpaca_base_url.rstrip('/')}/{path.lstrip('/')}"

    def get_account(self) -> dict:
        r = self.session.get(self._t("account"), timeout=20)
        r.raise_for_status()
        return r.json()

    def equity(self) -> float:
        return float(self.get_account().get("equity", 0.0))

    def list_positions(self) -> list[dict]:
        r = self.session.get(self._t("positions"), timeout=20)
        r.raise_for_status()
        return r.json()

    def is_tradable(self, symbol: str) -> bool:
        r = self.session.get(self._t(f"assets/{symbol}"), timeout=20)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        asset = r.json()
        return bool(asset.get("tradable")) and asset.get("status") == "active"

    def submit_notional_order(self, symbol: str, notional: float, side: str = "buy") -> Order:
        """Place a fractional market order for a dollar amount (day order)."""
        payload = {
            "symbol": symbol,
            "notional": round(float(notional), 2),
            "side": side,
            "type": "market",
            "time_in_force": "day",
        }
        r = self.session.post(self._t("orders"), json=payload, timeout=20)
        r.raise_for_status()
        d = r.json()
        return Order(
            symbol=symbol,
            notional=float(notional),
            side=side,
            status=d.get("status", "submitted"),
            id=d.get("id", ""),
        )

    def close_position(self, symbol: str) -> None:
        r = self.session.delete(self._t(f"positions/{symbol}"), timeout=20)
        if r.status_code not in (200, 207, 404):
            r.raise_for_status()

    # --- market data (pricing for return calc) ----------------------------
    def _d(self, path: str) -> str:
        return f"{self.cfg.alpaca_data_url.rstrip('/')}/{path.lstrip('/')}"

    def daily_close(self, symbol: str, on: dt.date) -> float | None:
        """Closing price on/near a date (uses a small forward window)."""
        start = on.isoformat()
        end = (on + dt.timedelta(days=6)).isoformat()
        r = self.session.get(
            self._d(f"stocks/{symbol}/bars"),
            params={"timeframe": "1Day", "start": start, "end": end, "limit": 5},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        bars = r.json().get("bars") or []
        if not bars:
            return None
        return float(bars[0]["c"])

    def latest_price(self, symbol: str) -> float | None:
        r = self.session.get(self._d(f"stocks/{symbol}/trades/latest"), timeout=20)
        if r.status_code != 200:
            return None
        trade = r.json().get("trade") or {}
        return float(trade["p"]) if "p" in trade else None
