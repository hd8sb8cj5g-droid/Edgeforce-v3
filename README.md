# EdgeForce — GitHub + Streamlit Cloud v0.3

**No Python installation required on your computer or phone.** GitHub hosts the source; Streamlit Community Cloud installs and executes Python for you. EdgeForce opens as a mobile-friendly HTTPS web app.

## Start here

**[DEPLOY_NO_PYTHON.md](DEPLOY_NO_PYTHON.md)** contains step-by-step browser-only instructions and a four-line Streamlit secrets template. Main file: `app.py`. Requirements: `requirements.txt` at project root.

### Screens

| Screen | What it offers |
| --- | --- |
| Market Scanner | Real NFL/CFB sportsbook moneylines, spreads, totals, price comparison and snapshot history; Kalshi markets |
| Player Prop Lab | Event player prop quotes where licensed, NFL/CFB game logs and L5/L10/L20 trends |
| Matchup Intelligence | NFLverse/CFBD completed-game summaries, basic score projections, EPA research and Open-Meteo |
| Parlay Builder | Five research candidates plus custom joint-score simulations from one sportsbook, with clear limits |
| Performance Tracker | Append-only predictions and settlements, exact snapshot price, prediction timestamp, closing quote if observed, score outcomes, CLV, ROI and exports |

### Required Streamlit secrets

Paste into **Streamlit Community Cloud → App → Advanced settings → Secrets**. Do not put live values into GitHub source or `secrets.toml.example`.

```toml
ODDS_API_KEY = "YOUR_ODDS_API_KEY"
CFBD_API_KEY = "YOUR_COLLEGE_FOOTBALL_DATA_API_KEY"
EDGEFORCE_POSTGRES_URL = "YOUR_NEON_POSTGRESQL_CONNECTION_STRING"
APP_PASSWORD = "YOUR_LONG_PRIVATE_APP_PASSWORD"
```

Use a cloud-hosted PostgreSQL connection (e.g., from [Neon](https://neon.tech)) to preserve all data across Streamlit restarts. The app initializes its own Postgres schema automatically. With no database URL, it falls back to local SQLite and displays a **data-loss warning** on Streamlit Cloud.

### Audit guarantees and limits

- Original bookmaker, market, selection, line, player, quote timestamp, prediction timestamp, model version, stake and eventual results are preserved as **append-only database records**.
- Closing quote is the last *actually observed* pregame quote from the same bookmaker/market/selection/line, observed no more than 120 minutes before kickoff. No source observation means no closing price is claimed.
- Settlements and corrections are separate events. Postgres rejects updates/deletes to the audit tables.
- Parlay payout is **the product of individually quoted prices for legs from one sportsbook and different games**. These are still research prices, not a guaranteed accepted parlay offer. Same-game parlays require sportsbook-issued combination pricing.
- A/B/C grades are research data-coverage indicators, not proven chances of profit. Score and EV models are experimental and uncalibrated.
- An included GitHub Actions collector can append odds snapshots to the **same Postgres ledger**; it is **manual-only by default** to protect paid API credits. See instructions.
- External provider access and the Streamlit Cloud UI have **not been live verified** in the build environment. Unit tests are offline.

### Safety and security

The app requires `APP_PASSWORD` when API keys or a database URL are configured. This is a basic app-level shared password, not enterprise SSO or per-user permissions. Keep the URL, app password and API keys private. Rotate any credentials that have been shared outside a secure secret manager.

Never upload `.env`, `.streamlit/secrets.toml`, SQLite backups or API-key export files to GitHub. The distributed source ZIP excludes all live credentials.

## Project structure

```
app.py
requirements.txt
edgeforce/
  db.py          # SQLite fallback and PostgreSQL adapter
  cloud_db.py    # PostgreSQL append-only evidence tables
  providers.py   # NFLverse, CFBD, The Odds API, Kalshi, Open-Meteo
  models.py      # scoring probabilities and historical game processing
  parlays.py     # correlated research simulations
  ledger.py      # settlement, CLV, ROI, backtesting measures
scripts/collect.py
.github/workflows/collect-odds.yml
.streamlit/config.toml
.streamlit/secrets.toml.example
DEPLOY_NO_PYTHON.md
```

## Test summary

16 existing offline unit tests pass on the package in this environment (not a live Streamlit or Postgres integration test). Browser rendering, live provider authentication, Postgres triggers and scheduled Cloud Actions must be verified after deployment.
