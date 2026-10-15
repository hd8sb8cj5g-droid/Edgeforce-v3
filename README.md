# EdgeForce v0.10 — injury-aware football research dashboard

Mobile-friendly Streamlit app deployed through GitHub and Streamlit Community Cloud. **No Python installation required on your own computer or phone.** Research-only: no wagering placement, guarantee of outcomes or calibrated profit prediction.

## Start here

- **Today:** upcoming NFL games, odds/schedule freshness, up to three independently qualified EV research candidates, and direct buttons into each game.
- **Game Hub:** choose a matchup and see **Overview**, **Best Bets**, **Player Props**, **TD Scorers**, **Matchup**, **Parlays**, and **Injuries** in one place. Expand **Why this bet?** for fair-price methodology, exact source quotes, data quality, and a two-percentage-point sensitivity check. The overview includes optional predictions and closing-odds history for the selected game.
- **Markets:** league-wide NFL/CFB moneyline, spread, totals and prop research with per-offer independent sportsbook no-vig EV calculations.
- **Player Props:** fetch player markets for an Odds API event, compare raw prices and game logs; absence of EV qualification does not hide raw prices.
- **Matchups:** NFLverse and CFBD games, schedule and experimental scoring projections.
- **TD Scorers:** up to three historic-usage-based offensive touchdown candidates per team, by NFL week, with optional play tendencies and fresh current-week OUT exclusions. Scoring index is **not** a calibrated TD probability.
- **Parlays:** up to five three-leg and five five-leg research tickets, plus six ranked price-contrarian picks and overlap concentration controls when enough qualifying legs exist.
- **Performance:** append-only recorded prices, forecast times, injury-status evidence known when forecasts were saved, actual captured closing prices if available, outcomes, calibration by market/injury designation, and exports.

## Deploy / upgrade

Read [UPGRADE_v0.10.md](UPGRADE_v0.10.md). For someone currently using v0.7, install the **v0.10 FROM_v0.7 patch** (includes v0.8/v0.9), not the older patches. `app.py` and `requirements.txt` must remain at repository root. Streamlit secrets stay in Streamlit private settings; never commit `.env` or real `secrets.toml` files.

## Sources

NFLverse schedules, player logs and optionally play-by-play; CollegeFootballData; The Odds API, Kalshi public markets, and Open-Meteo. Player-prop availability and sportsbook comparisons depend on the odds-provider subscription and current market coverage. Only authenticated, observed quotes qualify for EV analysis.

## Accuracy notes

- 'Estimated +EV' uses an independent-book no-vig **market consensus** price estimate, not a validated probability model; quoted prices are snapshots, not guaranteed accepted bets.
- For identical player, handicap and market type only. One-sided TD props are shown as raw prices, not assigned synthetic +EV.
- NFLverse current-week injury reports are retrieved automatically on relevant tabs; missing/old reports never certify health. OUT props are blocked, questionable/doubtful held, and downside EV scenarios are hypothetical rather than independently calibrated. Confirm active/inactive lists separately.
- Parlay hit rates and exposures are experimental. Tickets may overlap, and bookmaker same-game correlation/pricing rules may differ.
- Closing prices are present only if collected from the exact bookmaker/selection/line before kickoff. Neon is recommended to preserve history across cloud restarts.

## Tests

`python -m pytest -q` in GitHub Actions. See [QA_REPORT_v0.10.md](QA_REPORT_v0.10.md) for results and untested live environment constraints.
