# EdgeForce v0.10 Quality Report

- **Offline Python/fixture suite:** 130 passed, 1 skipped (Streamlit cannot be installed in this sandbox).
- **Checks included:** exact-season/week injury filtering, current and stale official report timestamps, two athletes sharing name, questionable vs OUT vs DNP practice, no confirmed-active inference from missing entries, odds stress scenario math, immutable snapshot and settlement integrity, historical Brier and ROI, market / injury-status cohorts, scheduled GitHub Actions source, current v0.7 cumulative merge, and Python compilation.
- **Historical honesty:** no modification of original odds, predicted probability, or injury context when final outcomes are recorded. Invalid or pending outcomes are excluded from probability calibration.
- **Confidence limitations:** zero current live sportsbook/injury API authentication tested here; no real Streamlit browser test; no external data guarantee. Running tests does not validate a profitable model or an estimated touchdown probability.
- **Live acceptance checklist:** Deploy to Streamlit, check Today, Game Hub Injuries, Markets, TD Scorers, Parlays, Performance; confirm NFLverse feeds, quotas, Postgres storage, scheduled GitHub workflow, and mobile legibility. No actual money wagering is performed by this application.
