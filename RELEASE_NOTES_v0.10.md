# EdgeForce v0.10 — NFL Injury Intelligence and Historical Accuracy

## Added

- Cached **15-minute NFLverse injury data** with season/week filtering, provider modification timestamps, stale-source detection, safe name normalization and no assumed healthy designations.
- **Injury status in Today and every NFL Game Hub**, including a dedicated `Injuries` tab and a refresh control.
- **Conservative recommendation gating:** confirmed OUT player props blocked; questionable/doubtful held; partial practice designations flagged; unknown/stale not silently cleared.
- **Scorer shortlists:** fresh current-week OUT players are automatically removed; flagged players display injury warnings.
- **Portfolio candidate gating:** verified injury blocks and holds excluded from suggested multi-game ticket candidates.
- **Why this bet?** one-tap explanation includes available injury flags, evidence age, and a clearly hypothetical downside scenario when applicable.
- **Immutable pre-prediction injury context** written to the prediction record's existing tags JSON; no database schema changes or historical record migration.
- **Performance accuracy by market and recorded injury status**, Brier error, calibration bins, sample-size disclaimers, hypothetical tracked ROI. No future results leak into forecast metadata.
- Free scheduled GitHub Actions **NFL final-score reconciliation**, optional Neon GitHub Actions secret; never uses Odds API credits.

## Limitations

Nflverse injury reports contain official weekly report status and practice participation but are **not** a verified game-day inactive list. Actual live-data availability varies. No injury effect is statistically calibrated; the market-consensus EV engine remains experimental. CFB injury feeds, independent player-prop settlement, live authenticated API tests, and real Streamlit rendering have not been verified for this build.
