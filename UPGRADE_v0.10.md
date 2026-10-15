# EdgeForce v0.10 — one cumulative upgrade from your current GitHub v0.7

**Important:** You have not yet published v0.8, v0.8.1, or v0.9. The recommended `EdgeForce_v0.10_FROM_v0.7_GITHUB_PATCH.zip` already includes their functionality. Do **not** apply the older patches first.

## Browser-only GitHub → Streamlit installation

1. Download and extract the v0.10 **FROM v0.7** patch. Its `app.py` and `requirements.txt` should remain directly at the repository root, with folders such as `edgeforce/`, `scripts/`, `tests/`, and `.github/workflows/` preserved.
2. Open [Edgeforce-v3](https://github.com/hd8sb8cj5g-droid/Edgeforce-v3), branch `main`. Upload **the contents of the extracted patch** (not the ZIP itself) and commit the changes. Existing files at the same paths must be replaced, while new files are added. You can use GitHub's web editor and file uploader. Do not include `.env`, `secrets.toml`, or private credentials.
3. Streamlit Community Cloud should pick up `main` automatically. Verify `app.py` is selected as the main script and the screen says **EdgeForce v0.10**.
4. Under **Today**, confirm `Current-week injuries` displays `FRESH`, `STALE`, or `MISSING`—not an unqualified healthy status. Use Refresh public injury report as needed.
5. Open **Game Hub → Injuries** for a selected NFL matchup. Check reported player names, primary injury, official game designation, practice status, and report-update timestamp. `OUT` players are excluded from scorer shortlist and their prop picks blocked; `QUESTIONABLE` and `DOUBTFUL` props are held. The source is **not** the confirmed game-day inactive list.
6. In **Parlays**, generate your five 3-leg and five 5-leg candidate tickets. Injury-held or excluded player props are screened from candidate quote inputs. Unknown availability is **not** represented as cleared or healthy.
7. In **Performance**, click **Refresh NFL final scores and update accuracy**. Check accuracy by market, by **injury status recorded when the prediction was made**, and calibration bins. Only recorded WIN/LOSS with original probabilities enter Brier scoring; live sources do not settle player props without verified box scores.
8. On your phone, test horizontal tabs, readable popovers, and the Injury tab. Use the GitHub Actions test workflow for the Streamlit headless smoke test.

## Automatic background performance settlement (optional, free of Odds API credits)

A new `.github/workflows/accuracy-feedback.yml` runs on a UTC schedule and can reconcile eligible NFL team-market outcomes while the app is closed. It needs `EDGEFORCE_POSTGRES_URL` added **separately** as a GitHub Actions repository secret, even if Streamlit already has it configured. Add under GitHub **Settings → Secrets and variables → Actions → New repository secret**. If this optional secret is absent, the new scheduled workflow simply skips settlement and reports how to enable it. GitHub cron runs can be delayed. It only records **unique NFL final-game matches**; player props require independently verified box scores.

Your existing `ODDS_API_KEY`, `CFBD_API_KEY`, `APP_PASSWORD`, and Neon connection string remain in Streamlit's **private** secrets. Do not publish them. The v0.10 patch includes no actual credentials and requires no local Python install.

## Important accuracy boundaries

- **Automated NFLverse injury refresh:** When relevant tabs are opened, public injury data is retrieved and cached up to 15 minutes. The source may update later; this does **not** certify players as active or up-to-the-minute inactive. When reports are stale, missing or mismatched to the exact week, EdgeForce says `UNVERIFIED` and cannot claim injury-adjusted fair odds.
- **Qualitative injury decisions:** Out-player prop candidates are blocked; doubtful/questionable are held; limited/DNP practice requires review. A -2 or -4 percentage-point **scenario** is shown for certain injury-sensitive props; it is not a statistically fitted win-probability adjustment or a claim of new +EV.
- **College football injury statuses** are not connected yet; the app never applies NFL injury reports to CFB.
- **Historical feedback:** Records predictions, source-modification date, observed odds and later settlements separately. Original pregame evidence is append-only. Market consensus probabilities have **not** been demonstrated to predict outcomes accurately. Paper ROI is not evidence of placed wagers.
- **No guaranteed ten tickets:** If eligible markets are scarce, portfolio output may include fewer than five 3-leg or five 5-leg research tickets. Games/markets with missing data must not be manufactured.
- **Production verification remains to be done:** The unit/integration tests are synthetic offline, and this build environment has no access to external provider endpoints or Streamlit runtime. Use GitHub Actions plus your Streamlit logs for runtime checks.
