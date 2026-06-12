"""Configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


def _flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Alpaca
    alpaca_key_id: str = os.getenv("ALPACA_API_KEY_ID", "")
    alpaca_secret: str = os.getenv("ALPACA_API_SECRET_KEY", "")
    alpaca_base_url: str = os.getenv(
        "ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2"
    )
    alpaca_data_url: str = os.getenv(
        "ALPACA_DATA_URL", "https://data.alpaca.markets/v2"
    )

    # CapitalTrades
    capitaltrades_base_url: str = os.getenv(
        "CAPITALTRADES_BASE_URL", "https://bff.capitaltrades.com"
    )

    # Strategy
    rank_universe_size: int = _int("RANK_UNIVERSE_SIZE", 40)
    min_trades_12m: int = _int("MIN_TRADES_12M", 8)
    deploy_fraction: float = _float("DEPLOY_FRACTION", 0.80)
    max_position_fraction: float = _float("MAX_POSITION_FRACTION", 0.15)
    dry_run: bool = _flag("DRY_RUN", True)

    # Email
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: str = os.getenv("EMAIL_TO", "")

    @property
    def is_paper(self) -> bool:
        """True only when the configured endpoint is an Alpaca paper endpoint."""
        return "paper-api.alpaca.markets" in self.alpaca_base_url

    def require_alpaca(self) -> None:
        if not self.alpaca_key_id or not self.alpaca_secret:
            raise RuntimeError(
                "Missing ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY. "
                "Copy .env.example to .env and fill them in."
            )

    def require_email(self) -> None:
        missing = [
            n
            for n, v in {
                "SMTP_HOST": self.smtp_host,
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password,
                "EMAIL_TO": self.email_to,
            }.items()
            if not v
        ]
        if missing:
            raise RuntimeError(f"Missing email settings: {', '.join(missing)}")


settings = Settings()
