# EdgeForce v0.11 QA report

- Existing suite + new 6 resilience/bootstrap tests: **136 passed, 2 skipped** (real PostgreSQL requires GitHub's test container; Streamlit requires installation).
- Pool uses checked checkout, shorter connection lifetimes and no redundant explicit `BEGIN`.
- Only read operations retry automatically; failed writes are returned as errors rather than silently replayed.
- Login source loaders are single-run per session, independently report failures without leaking connection strings, and prefetch NFL/CFB research and odds subject to freshness/quotas.
- Streamlit sections use `db.upcoming_quotes` for research; complete archive remains available in `db.latest_quotes` for tracking/export.
- Added GitHub PostgreSQL service test with actual transaction + audit-trigger checks. It will run **after** the source is pushed.
- Live Neon connection, real provider keys, Streamlit mobile render: **not verifiable locally**.

This release fixes code-level causes likely to produce the reported stack, but the supplied traceback did not include the final server error; verification of the specific production root cause needs Streamlit logs after deployment.
