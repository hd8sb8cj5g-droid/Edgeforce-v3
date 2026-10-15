# EdgeForce v0.3 — GitHub + Streamlit Cloud (NO PYTHON ON YOUR DEVICE)

You do **not** have to install Python, terminal tools, or Streamlit. Your computer or phone is only used to upload the files and open the website.

## A. Create a GitHub project using your browser

1. Download `EdgeForce_v0.3_GitHub_Cloud.zip` and **extract/unzip it**. Do **not** upload only the ZIP: GitHub won't run a compressed archive as Streamlit source.
2. Open https://github.com/new and create a repository named `edgeforge-dashboard` (or use your existing EdgeForge repository). Private is preferred.
3. Open the repository and choose **Add file → Upload files**. Upload the **contents** of the extracted folder: `app.py`, `requirements.txt`, `edgeforce/` (all its `.py` files), `scripts/`, `.streamlit/config.toml`, and (optionally) `.github/workflows/collect-odds.yml`. Keep the same folder structure. GitHub browser upload supports drag-and-drop; if the mobile browser won't upload folders, use Desktop Site, a desktop browser, or GitHub's web editor to add the nested files.
4. Confirm `app.py` and `requirements.txt` are at the **repository root**, and `edgeforce/cloud_db.py` is present. Commit the files.

Never upload `.env`, `*.sqlite3`, `secrets.toml`, or `EdgeForce_private_keys.env`. The GitHub ZIP does not contain the API keys.

## B. Get a durable database (strongly recommended)

The tracker must survive Streamlit server restarts. SQLite files stored on Streamlit Community Cloud are **not** durable.

1. Open https://neon.tech and sign in; create a PostgreSQL project (e.g., `edgeforce`).
2. In its dashboard copy its **Postgres connection string** (pooled connection preferred), starting with `postgresql://` and containing `sslmode=require`.
3. EdgeForce will automatically create its tables in an isolated `edgeforce` Postgres schema the first time it launches. No database SQL editor is required.
4. Keep the connection string private, and make periodic Neon-managed backups or export the audit ledger from the app.

Neon account creation and pricing are independent of Streamlit. Confirm free-plan limits on their current website.

## C. Deploy the mobile-accessible website

1. Open https://share.streamlit.io, sign in with GitHub, choose **Create app → Yup, I have an app**.
2. Select `YOUR_GITHUB_USERNAME/edgeforge-dashboard`, branch `main`, **Main file** `app.py`.
3. Open **Advanced settings → Secrets** and paste this TOML template. Replace the placeholders with your existing keys, your new Neon Postgres connection string, and a long new password:

```toml
ODDS_API_KEY = "PASTE_ODDS_API_KEY"
CFBD_API_KEY = "PASTE_CFBD_API_KEY"
EDGEFORCE_POSTGRES_URL = "postgresql://user:password@your-neon-host.neon.tech/neondb?sslmode=require"
APP_PASSWORD = "YOUR_NEW_UNIQUE_LONG_APP_PASSWORD"
```

4. Choose Python 3.12 in Advanced settings when offered, then **Deploy**.
5. Streamlit installs Python and the packages **on its servers**, not on your device. It provides an HTTPS `.streamlit.app` URL that opens in Safari or Chrome on your phone.
6. Sign in with the `APP_PASSWORD` that you set. In the sidebar, click **Verify API Connections**, then sync **Market Scanner** odds and load stats on **Matchup Intelligence**.
7. On iPhone, use Safari **Share → Add to Home Screen**. On Android, use Chrome **⋮ → Add to Home screen**.

**No real-time requests were made to validate your API keys in the environment where this release was built.** If the Odds API prop endpoint rejects a market, check your provider's plan rather than posting keys publicly.

## D. Historical odds collection (important for genuine closing-line value)

Manual **Sync** saves a snapshot only when you open the app. That alone usually will not capture the true closing price.

A GitHub Actions workflow is included at `.github/workflows/collect-odds.yml`. It is **manual only by default**, so it cannot unexpectedly exhaust API credits. To enable it:

1. Go to your GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**.
2. Add `ODDS_API_KEY` and `EDGEFORCE_POSTGRES_URL` as separate **repository secrets** (not public variables).
3. Select **Actions → EdgeForce odds snapshot collector → Run workflow**. It saves snapshots to the **same Neon database** your Streamlit app reads.
4. Verify remaining Odds API credits in the app before enabling a time-based workflow schedule. Example scheduled cron is commented out in the workflow; uncomment only when your quota supports it.

Only a quote actually observed close to kickoff, for the same event, bookmaker, selection and exact line, qualifies as closing price in the tracker. We do **not** invent missing closing odds.

## What to expect

- Five screens are fully wired: Market Scanner, Player Prop Lab, Matchup Intelligence, Parlay Builder, Performance Tracker.
- The model is experimental and has not been independently calibrated. No EV claim constitutes a proven profitable edge.
- Cloud storage stays locked behind a password configured in Streamlit secrets. Do not share that password or Postgres URL.
- Manual settlements are append-only and revisions create additional ledger events.
- Automated browser deployment is not possible until GitHub hosts the project. This ZIP is **GitHub/Streamlit-ready**, not a live app URL.
- This package has passed its **offline Python unit tests**. A live Streamlit/Neon launch and external API authentication still require cloud deployment.
