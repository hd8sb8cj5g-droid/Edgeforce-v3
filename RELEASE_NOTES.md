# v0.3 GitHub + Streamlit Cloud readiness (October 15, 2026)

- Browser-only GitHub/Streamlit deployment; no installation on the user's computer.
- Responsive top-of-page navigation across five existing analytics screens; collapsible sidebar on mobile.
- API keys are loaded from Streamlit Cloud secrets, not checked into GitHub.
- An APP_PASSWORD access gate is required whenever provider credentials or hosted database are configured.
- Optional durable PostgreSQL backend with a small connection pool, isolated `edgeforce` schema, append-only table triggers, closing-quote calculations, prediction and parlay settlement ledgers, and ZIP/CSV audit export.
- Retained SQLite fallback for local proof-of-concept; prominent warning when used for hosted apps.
- Included opt-in GitHub Actions odds collector with API credit guard (manual dispatch by default).
- Fully documented no-Python deployment using existing/new GitHub repo and Streamlit Community Cloud, plus Neon for persistence.
- 16 offline unit tests pass; production Postgres and Streamlit launch are unverified pending user account setup.
