"""Human-readable text reports for the CLI and the email summary."""
from __future__ import annotations

import datetime as dt

from .capitaltrades import Politician, Trade
from .mirror import MirrorResult
from .ranking import RankedPolitician


def format_ranking(ranked: list[RankedPolitician], limit: int = 15) -> str:
    if not ranked:
        return "No politicians could be ranked (no priced legs)."
    lines = [f"{'#':>2}  {'Politician':28} {'Return':>8} {'Legs':>5}  {'Disclosed $':>14}"]
    lines.append("-" * 64)
    for i, r in enumerate(ranked[:limit], 1):
        lines.append(
            f"{i:>2}  {r.politician.name[:28]:28} {r.score*100:>7.1f}% "
            f"{r.n_legs:>5}  ${r.total_weight:>12,.0f}"
        )
    return "\n".join(lines)


def format_mirror(result: MirrorResult, leaders_label: str) -> str:
    mode = "DRY RUN — no orders placed" if result.dry_run else "LIVE (paper) — orders placed"
    lines = [
        f"Mirroring top performer(s): {leaders_label}",
        f"Account equity: ${result.equity:,.2f}   [{mode}]",
        "",
        f"{'Symbol':8} {'Weight':>7} {'Target $':>12}",
        "-" * 30,
    ]
    for tp in result.plan:
        lines.append(f"{tp.symbol:8} {tp.weight*100:>6.1f}% ${tp.target_notional:>10,.2f}")
    if result.orders:
        lines.append("")
        lines.append("Orders:")
        for o in result.orders:
            lines.append(f"  {o.side.upper():4} {o.symbol:8} ${o.notional:>10,.2f}  [{o.status}]")
    if result.skipped:
        lines.append("")
        lines.append("Skipped (already at target / untradable): " + ", ".join(result.skipped))
    return "\n".join(lines)


def format_new_disclosures(new: list[Trade]) -> str:
    if not new:
        return "No new disclosures since last run."
    lines = [f"New disclosures ({len(new)}):"]
    for t in sorted(new, key=lambda x: x.txn_date, reverse=True):
        lines.append(
            f"  {t.txn_date.isoformat()}  {t.politician_name[:20]:20} "
            f"{t.txn_type.upper():4} {t.ticker:6} ~${t.amount_usd:,.0f}"
        )
    return "\n".join(lines)


def daily_summary(
    ranked: list[RankedPolitician],
    mirror: MirrorResult,
    new: list[Trade],
    leaders: list[Politician],
    when: dt.date | None = None,
) -> tuple[str, str]:
    when = when or dt.date.today()
    label = ", ".join(p.name for p in leaders) if leaders else "—"
    subject = f"[Congress Mirror] {when.isoformat()} — top {len(leaders)}: {label}"
    body = "\n\n".join(
        [
            f"Daily Congress-mirror summary for {when.isoformat()}",
            f"Mirroring top {len(leaders)} performer(s): {label}",
            format_new_disclosures(new),
            format_ranking(ranked),
            format_mirror(mirror, label),
            "Educational use only. Disclosures are delayed and approximate; not investment advice.",
        ]
    )
    return subject, body
