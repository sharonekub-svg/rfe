#!/usr/bin/env python3
"""Cron entry point: run the daily pipeline once and email the summary.

Designed to be invoked by cron on weekdays at US market open. US markets are
closed on weekends, so the recommended schedule is Mon-Fri. See crontab.example.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a standalone script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from congress_mirror.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["daily"]))
