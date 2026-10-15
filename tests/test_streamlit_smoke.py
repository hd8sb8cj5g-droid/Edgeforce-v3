"""Real Streamlit headless UI smoke checks, run in GitHub CI.

If Streamlit is not installed in a restricted build environment this test is
skipped, not falsely recorded as a passing browser test.
"""
import os
from pathlib import Path
import pytest

streamlit=pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest


def test_all_eight_streamlit_screens_render_without_runtime_exceptions(tmp_path,monkeypatch):
    monkeypatch.setenv('EDGEFORCE_DB',str(tmp_path/'ui-smoke.sqlite3'))
    for name in ('ODDS_API_KEY','CFBD_API_KEY','EDGEFORCE_POSTGRES_URL','APP_PASSWORD'):
        monkeypatch.delenv(name,raising=False)
    from edgeforce import providers
    import pandas as pd
    from test_portfolio_and_scorers_v07 import _weekly_fake
    fake_schedule=pd.DataFrame([{'season':2026,'week':7,'gameday':'2026-10-18',
       'gametime':'13:00','home_team':'KC','away_team':'BUF','home_score':None,'away_score':None,
       'game_type':'REG','game_id':'2026_07_BUF_KC'}])
    monkeypatch.setattr(providers,'nfl_games',lambda year:fake_schedule)
    monkeypatch.setattr(providers,'nfl_player_stats',lambda year:_weekly_fake())
    monkeypatch.setattr(providers,'nfl_injury_reports',lambda year:pd.DataFrame())
    monkeypatch.setattr(providers,'kalshi_markets',lambda **kw:[])
    app=Path(__file__).resolve().parents[1]/'app.py'
    at=AppTest.from_file(str(app),default_timeout=30).run()
    assert not at.exception, str(at.exception)
    # st.tabs(on_change='rerun',key=...) exposes the active label in session state.
    # Selecting a tab should run only that workspace (lazy evaluation).
    for label in ['🏟 Game Hub','📈 Markets','🏈 Player Props','🧠 Matchups','🎯 TD Scorers','🎟 Parlays','📊 Performance']:
        at.session_state['edgeforce_workspace_tab'] = label
        at.run()
        assert not at.exception, f'{label}: {at.exception}'
