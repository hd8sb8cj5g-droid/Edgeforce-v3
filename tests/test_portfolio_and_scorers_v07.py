"""v0.7 audited synthetic regression fixtures — NOT real sportsbook predictions."""
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from edgeforce import portfolio, td_scorers
from test_opportunity_engine_v05 import NOW, mocked_nfl_slate


def _weekly_fake():
    rows=[]
    for week in range(1,7):
        for team,other in [('KC','BUF'),('BUF','KC')]:
            rows += [dict(season=2026,week=week,season_type='REG',team=team,opponent_team=other,
                          player_id=f'{team}-rb',player_display_name=f'{team} Rusher',position='RB',
                          carries=18,targets=2,rushing_tds=1 if week%2 else 0,receiving_tds=0,passing_tds=0),
                     dict(season=2026,week=week,season_type='REG',team=team,opponent_team=other,
                          player_id=f'{team}-wr',player_display_name=f'{team} Catcher',position='WR',
                          carries=0,targets=12,rushing_tds=0,receiving_tds=1 if week%3==0 else 0,passing_tds=0),
                     dict(season=2026,week=week,season_type='REG',team=team,opponent_team=other,
                          player_id=f'{team}-te',player_display_name=f'{team} Tight End',position='TE',
                          carries=0,targets=7,rushing_tds=0,receiving_tds=1 if week%4==0 else 0,passing_tds=0),
                     dict(season=2026,week=week,season_type='REG',team=team,opponent_team=other,
                          player_id=f'{team}-qb',player_display_name=f'{team} Passer',position='QB',
                          carries=1,targets=0,rushing_tds=0,receiving_tds=0,passing_tds=4)]
    return pd.DataFrame(rows)


def _schedule():
    return pd.DataFrame([
        dict(season=2026,week=7,game_type='REG',home_team='KC',away_team='BUF',kickoff_utc='2026-10-18T17:00:00+00:00'),
        dict(season=2026,week=8,game_type='REG',home_team='BUF',away_team='KC',kickoff_utc='2026-10-25T17:00:00+00:00'),
    ])


def test_portfolio_delivers_five_each_and_respects_event_and_book():
    report=portfolio.optimize_portfolio(mocked_nfl_slate(14),'DiscountBook',NOW)
    assert len(report['three']) == 5 and len(report['five']) == 5
    for ticket in report['three']+report['five']:
        assert ticket['stress_ev_pct']>0
        assert len(ticket['legs'])==ticket['leg_count']
        assert len({leg['quote']['event_id'] for leg in ticket['legs']})==ticket['leg_count']
        assert {leg['quote']['bookmaker'] for leg in ticket['legs']}=={'DiscountBook'}
    assert len({ticket['signature'] for ticket in report['three']+report['five']})==10
    assert sum(report['leg_exposure'].values())==40
    assert sum(report['game_exposure'].values())==40
    assert max(report['leg_exposure'].values())>=1


def test_portfolio_diversification_does_not_worsen_peak_exposure():
    slate=mocked_nfl_slate(14)
    baseline=portfolio.optimize_portfolio(slate,'DiscountBook',NOW,diversification=0.)
    optimized=portfolio.optimize_portfolio(slate,'DiscountBook',NOW,diversification=2.5)
    assert max(optimized['leg_exposure'].values()) <= max(baseline['leg_exposure'].values())
    assert optimized['max_shared_legs'] <= baseline['max_shared_legs']


def test_no_artificial_tickets_if_only_four_events():
    r=portfolio.optimize_portfolio(mocked_nfl_slate(4),'DiscountBook',NOW)
    assert r['five']==[]
    assert len(r['three'])>0
    assert r['warnings']


def test_dont_cross_books_or_use_stale_quotes():
    from datetime import timedelta
    from copy import deepcopy
    offers=deepcopy(mocked_nfl_slate(14))
    assert not portfolio.optimize_portfolio(offers,'OtherBook',NOW)['three']
    for q in offers:q['observed_at']=(NOW-timedelta(hours=2)).isoformat()
    assert not portfolio.optimize_portfolio(offers,'DiscountBook',NOW)['five']


def test_weekly_board_both_teams_top_three_only_prior_weeks():
    board=td_scorers.weekly_scorer_board(_schedule(),_weekly_fake(),2026,7)
    assert len(board['games'])==1
    game=board['games'][0]
    assert len(game['picks']['KC'])==3 and len(game['picks']['BUF'])==3
    assert all(x['recent_td']>=0 and x['historical_games']==6 for picks in game['picks'].values() for x in picks)
    assert not any('Passer' in x['player'] for picks in game['picks'].values() for x in picks)
    assert game['picks']['KC'][0]['player']=='KC Rusher'


def test_no_future_leakage_and_exclude_out():
    logs=_weekly_fake()
    logs.loc[(logs.team=='KC')&(logs.week==6)&(logs.position=='WR'),'receiving_tds']=900
    week3=td_scorers.weekly_scorer_board(_schedule().assign(week=3),logs,2026,3)
    assert week3['games'][0]['picks']['KC'][0]['player']=='KC Rusher'
    result=td_scorers.weekly_scorer_board(_schedule(),logs,2026,7,excluded_players=['KC Rusher'])
    assert all(x['player']!='KC Rusher' for x in result['games'][0]['picks']['KC'])
    assert all(x['recent_td']<900 for x in week3['games'][0]['picks']['KC'])


def test_qb_passing_tds_never_count_as_scoring():
    logs=_weekly_fake()
    logs.loc[(logs.team=='KC')&(logs.position=='QB'),'carries']=10
    candidates=td_scorers.weekly_scorer_board(_schedule(),logs,2026,7)['games'][0]['picks']['KC']
    qbs=[x for x in candidates if x['position']=='QB']
    assert all(x['recent_td']==0 for x in qbs)


def test_missing_data_does_not_invent_players():
    board=td_scorers.weekly_scorer_board(_schedule(),pd.DataFrame(),2026,7)
    assert board['games'] and all(not picks for g in board['games'] for picks in g['picks'].values())
    assert board['warnings']


def test_scheme_tendencies_change_projections_without_future_leakage():
    pbp=pd.DataFrame([dict(season=2026,week=2,season_type='REG',posteam='KC',defteam='BUF',
                           pass_attempt=1 if k<80 else 0,rush_attempt=0 if k<80 else 1,
                           yardline_100=15 if k%2 else 60) for k in range(100)])
    base=td_scorers.weekly_scorer_board(_schedule(),_weekly_fake(),2026,7)
    after=td_scorers.weekly_scorer_board(_schedule(),_weekly_fake(),2026,7,pbp=pbp)
    assert after['with_schemes']
    assert base['games'][0]['picks']['KC'] != after['games'][0]['picks']['KC']
    before=td_scorers.summarize_schemes(pbp,2026,2)
    assert not before


def test_ui_has_portfolio_screen_and_tds():
    s=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    for token in ('portfolio.optimize_portfolio','Portfolio exposure','Touchdown Scorers',
                  'td_scorers.weekly_scorer_board','Exclude players known to be OUT'):
        assert token in s


def test_full_fourteen_game_slate_six_per_game_with_complete_history():
    from edgeforce.models import NFL_FULL
    teams=list(NFL_FULL.values())[:28]
    schedule=pd.DataFrame([{'season':2026,'week':6,'game_type':'REG',
                            'home_team':teams[2*i], 'away_team':teams[2*i+1],
                            'kickoff_utc':'2026-10-18T17:00:00Z'} for i in range(14)])
    rows=[]
    for team in teams:
        for week in range(1,6):
            for role,n,target,carry in [('RB',0,1,12),('WR',1,7,0),('TE',2,6,0)]:
                rows.append({'season':2026,'week':week,'season_type':'REG','recent_team':team,
                    'player_id':f'{team}-{role}', 'player_display_name':f'{team} {role}',
                    'position':role,'rushing_tds':int(role=='RB' and week==2),
                    'receiving_tds':int(role=='WR' and week==3),
                    'targets':target,'carries':carry})
    report=td_scorers.weekly_scorer_board(schedule,pd.DataFrame(rows),2026,6)
    assert len(report['games'])==14
    assert sum(len(g['picks'][team]) for g in report['games'] for team in (g['home'],g['away']))==84
    assert not any('fewer than three' in msg for msg in report['warnings'])


def test_game_flow_adjusts_rusher_and_receiver_indices():
    stats=_weekly_fake()
    balanced=td_scorers.weekly_scorer_board(_schedule(),stats,2026,7,team_points={'KC':22.5,'BUF':22.5})
    leading=td_scorers.weekly_scorer_board(_schedule(),stats,2026,7,team_points={'KC':34,'BUF':14})
    a={x['player']:x for x in balanced['games'][0]['picks']['KC']}
    b={x['player']:x for x in leading['games'][0]['picks']['KC']}
    assert b['KC Rusher']['opportunity_index']>a['KC Rusher']['opportunity_index']
    assert b['KC Catcher']['opportunity_index']<a['KC Catcher']['opportunity_index']*1.25


def test_anytime_td_price_requires_same_matchup_exact_player_and_yes():
    fixture={'sport':'NFL','market':'player_anytime_td','home_team':'Kansas City Chiefs',
             'away_team':'Buffalo Bills','participant':'KC Catcher','selection':'Yes',
             'american_odds':120,'bookmaker':'BookA'}
    candidates=[fixture, dict(fixture,bookmaker='BookB',american_odds=135),
                dict(fixture,bookmaker='BookC',american_odds=900,selection='No'),
                dict(fixture,bookmaker='BookD',american_odds=900,home_team='New York Giants')]
    row=td_scorers.best_anytime_td_quote(candidates,'KC Catcher','KC','BUF')
    assert row['bookmaker']=='BookB' and row['american_odds']==135
    assert td_scorers.best_anytime_td_quote(candidates,'KC Rusher','KC','BUF') is None
