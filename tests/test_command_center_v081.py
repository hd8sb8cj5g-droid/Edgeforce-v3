"""EdgeForce Daily Command Center regression checks (all odds/game fixtures synthetic)."""
from datetime import datetime,timedelta,timezone

import pandas as pd
from edgeforce import command_center, nfl_schedule
from test_opportunity_engine_v05 import NOW, mocked_nfl_slate


def test_quote_status_fresh_stale_and_future_kickoff():
    qs=mocked_nfl_slate(3)
    health=command_center.sportsbook_health(qs,NOW)
    assert health['status']=='FRESH'
    assert health['games']==3 and health['books']==4
    assert health['quote_count']==24
    for q in qs:q['observed_at']=(NOW-timedelta(minutes=50)).isoformat()
    old=command_center.sportsbook_health(qs,NOW)
    assert old['status']=='STALE' and old['quote_count']==24
    for q in qs:q['commence_time']=(NOW-timedelta(minutes=1)).isoformat()
    assert command_center.sportsbook_health(qs,NOW)['status']=='MISSING'


def test_quote_status_never_greenlights_synthetic_or_stale_provider():
    qs=mocked_nfl_slate(2)
    for q in qs:q['source']='SYNTHETIC DEMO'
    assert command_center.sportsbook_health(qs,NOW)['status']=='MISSING'
    for q in qs:
        q['source']='The Odds API'
        q['source_updated_at']=(NOW-timedelta(hours=2)).isoformat()
    assert command_center.sportsbook_health(qs,NOW)['status']=='MISSING'
    qs[0]['source_updated_at']=(NOW-timedelta(minutes=2)).isoformat()
    assert command_center.sportsbook_health(qs,NOW)['status']=='LIMITED'
    for q in qs:q['observed_at']=(NOW+timedelta(minutes=1)).isoformat()
    assert command_center.sportsbook_health(qs,NOW)['status']=='MISSING'


def test_top_ev_candidates_deduplicated_by_game_with_bona_fide_reference_books():
    qs=mocked_nfl_slate(10)
    best=command_center.rank_research_opportunities(qs,NOW)
    assert len(best)==3
    assert len({r['quote']['event_id'] for r in best})==3
    assert all(r['ev_pct']>=1 and r['reference_count']>=2 for r in best)
    assert all(r['quote']['source']=='The Odds API' for r in best)
    for q in qs:q['observed_at']=(NOW-timedelta(hours=2)).isoformat()
    assert command_center.rank_research_opportunities(qs,NOW)==[]
    assert command_center.rank_research_opportunities([],NOW)==[]


def test_top_ev_candidates_discard_games_with_only_one_independent_book():
    qs=[q for q in mocked_nfl_slate(2) if q['bookmaker'] in ('DiscountBook','RefA')]
    assert command_center.rank_research_opportunities(qs,NOW)==[]


def _full_game(week,day,home='KC',away='BUF',start='20:15',finished=False):
    return {'season':2026,'week':week,'gameday':day,'gametime':start,
      'home_team':home,'away_team':away,'home_score':17 if finished else None,
      'away_score':13 if finished else None,'game_type':'REG',
      'game_id':f'2026_{week}_{away}_{home}'}


def test_nfl_next_week_respects_start_time_timezones_and_no_finished_games():
    now=datetime(2026,10,15,17,0,tzinfo=timezone.utc)
    schedule=nfl_schedule.prepare_schedule(pd.DataFrame([
        _full_game(6,'2026-10-15',start='20:15'),
        _full_game(6,'2026-10-18',home='GB',away='CHI',start='13:00'),
        _full_game(5,'2026-10-11',home='PHI',away='NYG',finished=True),
        _full_game(16,'2026-12-20',home='LA',away='SF')
    ]),2026,asof=now)
    games=command_center.nfl_games_next_week(schedule,now)
    assert len(games)==2
    assert games[0]['matchup']=='BUF @ KC'
    assert games[0]['kickoff_et'].endswith('08:15 PM ET')
    assert all(g['kickoff_utc']>now for g in games)
    assert command_center.nfl_games_next_week(schedule,now,limit=1)[0]==games[0]


def test_no_schedule_and_outdated_schedule_are_reported_not_fabricated():
    assert command_center.nfl_games_next_week(None,NOW)==[]
    assert command_center.schedule_health(None,None,NOW)['status']=='MISSING'
    frame=pd.DataFrame([_full_game(6,'2026-10-18')])
    assert command_center.schedule_health(frame,None,NOW)['status']=='UNKNOWN'
    assert command_center.schedule_health(frame,NOW-timedelta(hours=3),NOW)['status']=='FRESH'
    assert command_center.schedule_health(frame,NOW-timedelta(hours=12),NOW)['status']=='STALE'


def test_all_active_tab_source_preserved_and_nav_buttons_real():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert 'from edgeforce import opportunities, portfolio, td_scorers, command_center' in app
    assert "TAB_LABELS=['🏠 Today','🏟 Game Hub','📈 Markets','🏈 Player Props','🧠 Matchups','🎯 TD Scorers','🎟 Parlays','📊 Performance']" in app
    assert "st.session_state['edgeforce_workspace_tab']=label" in app
    assert 'on_click=open_workspace_tab,args=(TAB_LABELS[1],)' in app
    assert 'on_click=open_workspace_tab,args=(TAB_LABELS[5],)' in app
    assert 'on_click=open_workspace_tab,args=(TAB_LABELS[6],)' in app
    assert "st.button('↻ Sync NFL odds'" in app
    assert 'providers.odds_api(\'NFL\',key=odds_key,markets=\'h2h,spreads,totals\')' in app


def test_fresh_but_one_book_is_limited_not_fully_ready():
    qs=[q for q in mocked_nfl_slate(1) if q['bookmaker']=='DiscountBook']
    health=command_center.sportsbook_health(qs,NOW)
    assert health['status']=='LIMITED' and health['fresh']
    assert 'More books' in health['detail']
