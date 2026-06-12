"""Command-line entry point: rank / mirror / daily / status.

    python -m congress_mirror.cli rank
    python -m congress_mirror.cli mirror      # respects DRY_RUN
    python -m congress_mirror.cli daily        # rank + mirror + email
    python -m congress_mirror.cli status
"""
from __future__ import annotations

import argparse
import sys

from .alpaca_client import AlpacaClient
from .capitaltrades import CapitalTradesClient
from .config import settings
from .emailer import send_email
from .pipeline import gather_and_rank, run_daily
from .report import daily_summary, format_mirror, format_ranking
from .state import SeenStore


def _cmd_status(_: argparse.Namespace) -> int:
    settings.require_alpaca()
    client = AlpacaClient()
    acct = client.get_account()
    print(f"Endpoint : {settings.alpaca_base_url} (paper={settings.is_paper})")
    print(f"Status   : {acct.get('status')}")
    print(f"Equity   : ${float(acct.get('equity', 0)):,.2f}")
    print(f"Cash     : ${float(acct.get('cash', 0)):,.2f}")
    print(f"DRY_RUN  : {settings.dry_run}")
    positions = client.list_positions()
    print(f"Positions: {len(positions)}")
    for p in positions:
        print(f"  {p['symbol']:8} {p.get('qty')} @ ${float(p.get('avg_entry_price',0)):.2f}"
              f"  mv=${float(p.get('market_value',0)):,.2f}")
    return 0


def _cmd_rank(args: argparse.Namespace) -> int:
    ct = CapitalTradesClient()
    pricer = AlpacaClient()
    outcome = gather_and_rank(ct, pricer)
    print(format_ranking(outcome.ranked, limit=args.limit))
    return 0


def _cmd_mirror(_: argparse.Namespace) -> int:
    ct = CapitalTradesClient()
    alpaca = AlpacaClient()
    outcome = gather_and_rank(ct, alpaca)
    if not outcome.ranked:
        print("Nothing to mirror — no ranked politicians.")
        return 1
    from .mirror import execute_mirror

    leader = outcome.ranked[0].politician
    trades = outcome.trades_by_politician.get(leader, [])
    result = execute_mirror(alpaca, trades)
    print(format_mirror(result, leader.name))
    return 0


def _cmd_daily(args: argparse.Namespace) -> int:
    ct = CapitalTradesClient()
    alpaca = AlpacaClient()
    store = SeenStore()
    outcome = run_daily(ct, alpaca, store)
    if outcome is None:
        print("No ranked politicians today; nothing to do.")
        return 1
    subject, body = daily_summary(
        outcome.ranked, outcome.mirror, outcome.new_disclosures, outcome.leader.name
    )
    print(body)
    if not args.no_email:
        send_email(subject, body)
        print("\n(email sent)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="congress_mirror", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("rank", help="Rank active politicians by trailing-12m return")
    pr.add_argument("--limit", type=int, default=15)
    pr.set_defaults(func=_cmd_rank)

    pm = sub.add_parser("mirror", help="Mirror the top performer (respects DRY_RUN)")
    pm.set_defaults(func=_cmd_mirror)

    pd = sub.add_parser("daily", help="Rank + mirror + email summary")
    pd.add_argument("--no-email", action="store_true", help="Print summary, don't email")
    pd.set_defaults(func=_cmd_daily)

    ps = sub.add_parser("status", help="Show paper-account status")
    ps.set_defaults(func=_cmd_status)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # surface a clean message, non-zero exit
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
