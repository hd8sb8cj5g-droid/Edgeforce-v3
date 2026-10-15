# START HERE — EdgeForce runs in your browser

**You do not need to install Python on your computer or phone.**

1. Download and unzip `EdgeForce_v0.3_GitHub_Cloud.zip`.
2. Upload the extracted **source files** (not the ZIP itself) into your GitHub `edgeforge-dashboard` repository. Keep their folder structure.
3. Create a free-tier eligible hosted Postgres project at https://neon.tech for durable prediction history.
4. Open https://share.streamlit.io → **Create app** → select your repository → set main file to **`app.py`**.
5. In **Advanced settings → Secrets**, enter `ODDS_API_KEY`, `CFBD_API_KEY`, `EDGEFORCE_POSTGRES_URL`, `APP_PASSWORD` as four quoted TOML strings.
6. Deploy. Open the resulting `https://...streamlit.app` link on your iPhone or Android phone and add it to your home screen.

**Complete walkthrough:** [DEPLOY_NO_PYTHON.md](DEPLOY_NO_PYTHON.md)

Your actual API keys and database password are excluded from the GitHub source archive. Do not upload `.env`, `secrets.toml`, or a private credentials file to GitHub.

**Status:** Tested with 16 offline unit tests. Real provider authentication, hosted PostgreSQL, and Streamlit rendering remain unverified until first deployment.
