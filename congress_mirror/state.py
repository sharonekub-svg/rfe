"""Tiny JSON-file state store to detect *new* disclosures between runs."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .capitaltrades import Trade

STATE_DIR = os.getenv("STATE_DIR", "state")
STATE_FILE = os.path.join(STATE_DIR, "seen_trades.json")


def _trade_key(t: Trade) -> str:
    return f"{t.politician_id}|{t.ticker}|{t.txn_date.isoformat()}|{t.txn_type}|{int(t.amount_usd)}"


@dataclass
class SeenStore:
    path: str = STATE_FILE
    _seen: set[str] | None = None

    def load(self) -> set[str]:
        if self._seen is None:
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._seen = set(json.load(fh))
            except (FileNotFoundError, json.JSONDecodeError):
                self._seen = set()
        return self._seen

    def new_trades(self, trades: list[Trade]) -> list[Trade]:
        seen = self.load()
        return [t for t in trades if _trade_key(t) not in seen]

    def mark(self, trades: list[Trade]) -> None:
        seen = self.load()
        for t in trades:
            seen.add(_trade_key(t))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(sorted(seen), fh, indent=0)
