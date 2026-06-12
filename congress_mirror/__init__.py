"""Congress trade mirror — paper-trading helper.

Ranks active members of Congress by an approximate trailing-12-month return on
their disclosed trades, mirrors the top performer's open positions into an
Alpaca *paper* account, and emails a daily summary.

This is an educational tool. Congressional disclosures are delayed (up to ~45
days under the STOCK Act) and report dollar ranges, not exact sizes, so any
"return" computed here is an approximation, not investment advice.
"""

__version__ = "0.1.0"
