# Congress Trade Mirror (paper trading)

Ranks the most **active members of Congress** by an approximate trailing‑12‑month
return on their disclosed trades, **mirrors the top performer's open positions**
into an **Alpaca *paper* account**, checks for new disclosures each weekday at
market open, and **emails a summary**.

> ⚠️ **Educational use only — not investment advice.** Congressional STOCK Act
> disclosures are delayed (up to ~45 days) and report dollar *ranges*, not exact
> sizes, so the "returns" here are estimates. This tool only ever trades a
> **paper** account — it hard‑refuses any live Alpaca endpoint.

## What it does

| Command | Description |
| --- | --- |
| `rank`   | Fetch the most‑active politicians + their trailing‑year trades and rank them by amount‑weighted return. |
| `mirror` | Build a target portfolio from the **top `TOP_N_LEADERS` performers'** net open positions and place orders (respects `DRY_RUN`). |
| `daily`  | `rank` → `mirror` → detect new disclosures → email a summary. Intended for cron. |
| `status` | Show paper‑account equity, cash, and open positions. |

## Setup

```bash
git clone https://github.com/sharonekub-svg/rfe
cd rfe
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then edit .env with your real values
```

Fill in `.env`:

- **Alpaca** — your paper key id/secret. `ALPACA_BASE_URL` must stay the
  `paper-api.alpaca.markets` endpoint.
- **Email** — SMTP host/credentials. For Gmail, create an
  [App Password](https://support.google.com/accounts/answer/185833) and use that
  as `SMTP_PASSWORD`.
- **Strategy** — `DEPLOY_FRACTION`, `MAX_POSITION_FRACTION`, `MIN_TRADES_12M`,
  `TOP_N_LEADERS` (how many top‑ranked politicians to mirror; capital is split
  equally across them, then diversified across each one's positions — `1`
  follows only the leader), and `DRY_RUN` (defaults to `true` — flip to `false`
  only when you're ready to place paper orders).

`.env` is git‑ignored. **Never commit real keys.**

## Run

```bash
python -m congress_mirror.cli status        # sanity-check the connection
python -m congress_mirror.cli rank          # print the ranking
python -m congress_mirror.cli mirror        # build/place the mirror (DRY_RUN aware)
python -m congress_mirror.cli daily --no-email   # full run, print instead of email
python -m congress_mirror.cli daily         # full run + email
```

## Schedule it (weekdays at market open)

US markets are closed on weekends, so the recommended cadence is **Mon–Fri at
09:30 America/New_York**. Edit the paths in `scheduler/crontab.example`, then:

```bash
crontab scheduler/crontab.example
```

The cron line runs `scheduler/run_daily.py`, which calls `daily` and emails you.

## Run it automatically on GitHub Actions (no server of your own)

`.github/workflows/daily.yml` runs the bot on GitHub's infrastructure on US
trading days near market open — no always-on machine required. To enable it:

1. **Push this repo to GitHub** (the workflow file is already included).
2. In the repo, go to **Settings → Secrets and variables → Actions** and add
   these **repository secrets**:
   - `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`
3. (Optional) Under the **Variables** tab add `DRY_RUN` = `true` to test without
   placing orders; remove it (or set `false`) to place real paper orders.
4. Open the **Actions** tab → **daily-mirror** → **Run workflow** to test now,
   or just wait for the next weekday market open.

Notes:
- A market-open check (Alpaca's `/clock`) makes the job a no-op on weekends and
  holidays, and handles EDT/EST automatically.
- The job commits `state/seen_trades.json` back to the repo so "new disclosure"
  detection persists between runs.
- GitHub's scheduled runs can be delayed a few minutes and are paused after ~60
  days of repo inactivity — push occasionally (the state commits usually cover this).

## How ranking works (and its limits)

For each disclosed **buy** in the trailing 12 months we take the entry price on
the transaction date and an exit price at either the first subsequent **sell**
of the same ticker (a *closed* leg) or the latest price (an *open* leg). Each
leg's return is weighted by the midpoint of its disclosed amount bracket, and a
politician's score is the amount‑weighted average return across legs. Legs whose
prices can't be resolved are skipped; a politician with no priced legs is
excluded. Prices come from the Alpaca market‑data API.

The bot then mirrors the **top `TOP_N_LEADERS`** ranked politicians (not just
the single best). Deployed capital is split **equally** across those leaders,
and within each leader it's allocated proportionally to disclosed exposure;
slices are merged per ticker and each name is capped at `MAX_POSITION_FRACTION`
of equity. This diversifies across several top performers instead of betting on
one.

## Safety design

- **Paper‑only:** `AlpacaClient` raises if the endpoint isn't a paper endpoint.
- **`DRY_RUN`:** computes and emails but places **no** orders when `true`.
- **Position caps:** `MAX_POSITION_FRACTION` caps any single name; only
  `DEPLOY_FRACTION` of equity is deployed; non‑tradable tickers are dropped.
- **New‑disclosure tracking:** `state/seen_trades.json` records what's already
  been seen so the email highlights only genuinely new filings.

## Network access

The data sources are `paper-api.alpaca.markets`, `data.alpaca.markets`, and
`bff.capitaltrades.com` (Cloudflare‑protected). Run this where those hosts are
reachable. CapitalTrades' backend shape can change; `capitaltrades.py` parses
defensively and the parsers are unit‑tested with fixtures.

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

All tests are offline (no network, no keys) — they exercise parsing, the
return‑ranking math, portfolio sizing/caps, and new‑disclosure tracking.

## Layout

```
congress_mirror/
  config.py         # env/.env settings + paper guard
  capitaltrades.py  # disclosure fetch + defensive parsing
  alpaca_client.py  # paper REST client + market-data pricing
  ranking.py        # trailing-12m return ranking
  mirror.py         # net open positions -> capped target portfolio -> orders
  state.py          # seen-disclosure tracking
  emailer.py        # SMTP summary
  report.py         # text reports / email body
  pipeline.py       # orchestration
  cli.py            # rank / mirror / daily / status
scheduler/          # cron entry point + crontab.example
tests/              # offline unit tests
```
