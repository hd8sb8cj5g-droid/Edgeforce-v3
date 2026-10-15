"""No-network regressions for game-centric research and quote explanations."""
from datetime import datetime,timedelta,timezone
import pandas as pd
from edgeforce import game_hub,nfl_schedule
from test_value_scanner import T,h2h_market,quote


def schedule():
    return nfl_schedule.prepare_schedule(pd.DataFrame([
        {'season':2026,'week':6,'gameday':'2026-10-17','gametime':'15:00',
         'home_team':'KC','away_team':'BUF','game_type':'REG',
         'home_score':None,'away_score':None,'game_id':'2026_06_BUF_KC'},
        {'season':2026,'week':6,'gameday':'2026-10-18','gametime':'13:00',
         'home_team':'SEA','away_team':'DEN','game_type':'REG',
         'home_score':None,'away_score':None,'game_id':'2026_06_DEN_SEA'},
        {'season':2026,'week':5,'gameday':'2026-10-10','gametime':'13:00',
         'home_team':'GB','away_team':'CHI','game_type':'REG',
         'home_score':22,'away_score':14,'game_id':'2026_05_CHI_GB'}
    ]),2026,asof=T)


def test_nflverse_schedule_visible_without_odds_and_past_excluded():
    games=game_hub.game_catalog(schedule(),[],T)
    assert len(games)==2
    assert {g['away_code'] for g in games}=={'BUF','DEN'}
    assert all(g['event_id'] is None for g in games)
    assert game_hub.game_health(games[0],[],T)['status']=='MISSING'
    assert game_hub.qualifying_game_bets(games[0],[],T)==[]


def test_matches_real_odds_event_id_not_schedule_game_id():
    qs=h2h_market()
    games=game_hub.game_catalog(schedule(),qs,T)
    assert len(games)==2
    buffalo=next(g for g in games if g['away_code']=='BUF')
    assert buffalo['event_id']=='GAME123'
    assert buffalo['source']=='NFLverse'
    assert len(game_hub.game_quotes(buffalo,qs))==6
    assert len(game_hub.qualifying_game_bets(buffalo,qs,T))==1
    assert game_hub.game_health(buffalo,qs,T)['status']=='FRESH'


def test_unrelated_same_day_opponent_and_faraway_kickoffs_do_not_join():
    qs=h2h_market()
    for q in qs:q['commence_time']=(T+timedelta(days=13)).isoformat()
    games=game_hub.game_catalog(schedule(),qs,T)
    assert len(games)==3
    assert len([g for g in games if g['event_id']=='GAME123'])==1
    assert len([g for g in games if g['source']=='NFLverse'])==2


def test_source_synthetic_excluded_cfb_game_with_real_odds_supported():
    qs=h2h_market()
    for q in qs:
        q['sport']='CFB';q['home_team']='Ohio State';q['away_team']='Michigan'
    games=game_hub.game_catalog(None,qs,T)
    assert len(games)==1 and games[0]['sport']=='CFB'
    for q in qs:q['source']='SYNTHETIC DEMO'
    assert game_hub.game_catalog(None,qs,T)==[]


def test_explanation_math_provenance_stress_and_invalidation():
    qs=h2h_market()
    game=game_hub.game_catalog(schedule(),qs,T)[0]
    # Sorting by kickoff places KC matchup first in this fixture.
    ranked=game_hub.qualifying_game_bets(game,qs,T)
    assert len(ranked)==1
    explain=game_hub.explain_offer(ranked[0],T)
    assert explain['offered']=='+120'
    assert explain['fair']=='+100'
    assert explain['ev_pct']==10.0
    assert explain['fair_pct']==50.0 and explain['implied_pct']==45.5
    assert abs(explain['stress_ev_pct']-5.6)<.01
    assert set(explain['references'])=={'Pinnacle','Circa'}
    assert explain['fresh'] and explain['quote_age_minutes']==2
    late=game_hub.explain_offer(ranked[0],T+timedelta(hours=1))
    assert not late['fresh']
    assert any('no longer current' in w.lower() for w in late['warnings'])


def test_prop_quotes_visible_without_ev_for_one_sided_anytime_td():
    qs=[quote('SoftBook','Yes',+145,market='player_anytime_td',player='Josh Allen')]
    g=game_hub.game_catalog(None,qs,T)[0]
    assert len(game_hub.raw_game_props(g,qs,T))==1
    assert game_hub.qualifying_game_bets(g,qs,T)==[]
    for q in qs:q['observed_at']=(T-timedelta(hours=1)).isoformat()
    assert game_hub.raw_game_props(g,qs,T)==[]
    assert game_hub.game_health(g,qs,T)['status']=='STALE'


def test_tickets_match_only_exact_event_id():
    game=game_hub.game_catalog(None,h2h_market(),T)[0]
    bet=game_hub.qualifying_game_bets(game,h2h_market(),T)[0]
    bundle={'three':{'tickets':[{'legs':[bet], 'bookmaker':'SoftBook'}]},'five':{'tickets':[]}}
    matches=game_hub.tickets_containing_game(bundle,game)
    assert len(matches)==1 and matches[0]['type']=='three'
    other=dict(game,event_id='NOT_THE_EVENT')
    assert game_hub.tickets_containing_game(bundle,other)==[]


def test_no_naive_clock_and_schedule_overflow():
    import pytest
    with pytest.raises(ValueError):game_hub.utc(datetime(2026,10,15))
    assert game_hub.game_catalog(None,[],T)==[]


def test_game_hub_really_navigation_includes_instructions_and_cross_links():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert "'🏟 Game Hub'" in app and 'st.session_state[\'hub_selection\']=game_key' in app
    assert 'explain_ev_candidate(candidate)' in app
    assert 'explain_ev_candidate(offer)' in app
    assert 'with st.popover(f"ℹ️ Why this bet?' in app
    assert "'Overview','⭐ Best Bets','Player Props','TD Scorers','Matchup','Parlays'" in app
    assert "providers.odds_event_props(chosen_game['sport'],chosen_game['event_id']" in app


def test_january_week_18_uses_previous_nfl_season():
    from datetime import datetime,timezone
    january=datetime(2027,1,3,19,tzinfo=timezone.utc)
    assert game_hub.nfl_season_for_date(january)==2026
    qs=[quote('Book','Yes',+145,eid='JANWEEK18')]
    for q in qs:
        q['commence_time']=(january+timedelta(days=2)).isoformat()
    games=game_hub.game_catalog(None,qs,january)
    assert games[0]['season']==2026
    assert game_hub.nfl_season_for_date(T)==2026


def test_catalog_suppresses_duplicate_same_game_provider_quotes():
    qs=h2h_market()*5
    games=game_hub.game_catalog(schedule(),qs,T)
    assert len(games)==2
    game=next(g for g in games if g['event_id']=='GAME123')
    assert game['price_count']==30
    assert game['book_count']==3
