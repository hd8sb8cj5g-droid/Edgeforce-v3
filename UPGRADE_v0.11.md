# EdgeForce v0.11 — resilient Neon + login preload

**Upgrade target:** current EdgeForce v0.10 on GitHub/Streamlit. No local Python install is required. No existing audit records are deleted or modified by the upgrade.

## What was repaired

- `edgeforce/cloud_db.py` used a reusable `ConnectionPool` **without a checkout health check** and opened an additional explicit transaction. A cloud database that idles or suspends can close a pooled connection; the next `BEGIN` can raise `psycopg.OperationalError`.
- The new pool uses `ConnectionPool.check_connection`, low idle lifetime and bounded acquisition time. Its `connection()` context owns commit/rollback (no extra explicit `BEGIN`). Reads can retry once on temporary connection failures; **writes are never replayed automatically**, preventing uncertain commits from producing duplicate financial evidence.
- A failure still can occur from invalid credentials, a sleeping/unreachable Neon service, network problems, or permissions. The redacted traceback alone does not confirm the exact server-side message. The app presents a retryable status instead of dumping a trace.
- Upcoming-market screens use a bounded PostgreSQL query rather than reading historical game quotes on every rerun. All existing historical records remain intact. A matching index is added non-destructively.

## What now happens automatically on login

After successful password authentication, EdgeForce loads the **core research feeds** once per browser session (and shows progress):

1. NFLverse schedule and final-game results
2. NFL player game logs
3. NFL injury reports for the active week
4. CollegeFootballData current-season schedule/results and team directory
5. Recently saved sportsbook odds and — **if stale and enabled** — refreshed featured NFL + CFB prices
6. Kalshi public football markets
7. Stored historical predictions

Individual **paid player-prop markets**, full-season play-by-play/scheme downloads, and stadium-specific weather remain on-demand when opening a game. Fetching all of those for every NFL game on every login would be slow and might exhaust API credits. The existing Game Hub behavior is retained.

With an API key configured, featured sportsbook requests are enabled on login by default. Each request consumes your Odds API plan credits. EdgeForce checks for fresh upcoming quotes first and uses a 20-minute freshness threshold to avoid repeat requests from routine sessions. To disable, add to **Streamlit Secrets**:

```toml
AUTO_SYNC_ODDS_ON_LOGIN = false
```

This flag is optional. Current `ODDS_API_KEY`, `CFBD_API_KEY`, `EDGEFORCE_POSTGRES_URL`, and `APP_PASSWORD` secrets do not need to be changed to install this release.

## Apply using GitHub web/mobile, without Python

1. Download `EdgeForce_v0.11_FROM_v0.10_PATCH.zip` and extract it.
2. In `https://github.com/hd8sb8cj5g-droid/Edgeforce-v3` on the `main` branch, replace or add every extracted file at the corresponding path. Upload the **contents**, not the ZIP itself.
3. Commit your changes. Streamlit Community Cloud will redeploy the new code.
4. Open EdgeForce on your phone and sign in. Wait for "Preparing your football dashboard" and inspect the **Login data status** sidebar item.
5. Open **Today**, **Markets**, **Game Hub**, and **Performance**. Check that today's NFL schedule, available odds and historical records appear. If there are zero qualifying +EV plays, that is a valid result.
6. Open the repository's GitHub **Actions** tab. The `EdgeForce continuous integration` workflow now has a `postgres-integration` job using a disposable PostgreSQL 16 database. Check both jobs are green. It **does not** connect to your production Neon database.

## Troubleshooting Neon

If the app says database unavailable:

- Tap **Retry database connection** or **Reconnect to Neon**. A first request after Neon idle-suspension may need a few seconds.
- In Neon Console → Connect, consider using the **Pooled** connection string for app traffic (look for `-pooler` in the host). Set this only in Streamlit App → Settings → Secrets, under the existing `EDGEFORCE_POSTGRES_URL` name. Do not change production credentials until your backup is verified.
- Check `sslmode=require`, password validity, and the Neon database's active status.
- In Streamlit Cloud → Manage app → Logs, find the **final line** of the full psycopg exception; the source traceback may otherwise hide the actual SQLSTATE/network cause. Do not share passwords or complete connection URLs.
- You can export the SQLite/Postgres historical tracker backup through Performance if the current database is available.

## Testing completed

- `python -m pytest -q` — **136 passed, 2 skipped** in the available offline runtime.
- Compile — passed (`app.py`, `edgeforce/`, `scripts/`).
- Stale connection checkout, read-retry-only, no write replay, single-load state, provider failure redaction, full SQLite audit persistence and bounded upcoming odds — passed.
- GitHub Actions includes real PostgreSQL append-only smoke tests and Streamlit headless UI tests. These are **not yet verified** in this execution environment; its package installer cannot access Streamlit/Psycopg distributions. Do not interpret the offline pass count as verified live deployment.

## Rollback

If Streamlit fails to start, open the last working commit in GitHub → use **Revert** (or restore the previous `app.py` and `edgeforce/cloud_db.py`). The database tables remain backward-compatible. Do not delete your Neon project or production audit tables.
