"""Tests deliberately fix the October 15, 2026 Week 6 view and prevent regressions."""
from datetime import datetime, timedelta, timezone
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
import pytest
from edgeforce import nfl_schedule, providers, models

ASOF=datetime(2026,10,15,17,0,tzinfo=timezone.utc)
# 14 fixtures cross-checked against NFL.com Week 6 schedule, October 15-19.
W6=[('SEA','DEN','2026-10-15','20:15'),
    ('HOU','JAX','2026-10-18','09:30'),
    ('TEN','IND','2026-10-18','13:00'),
    ('CAR','PHI','2026-10-18','13:00'),
    ('PIT','TB','2026-10-18','13:00'),
    ('BAL','CLE','2026-10-18','13:00'),
    ('NO','NYG','2026-10-18','13:00'),
    ('CHI','ATL','2026-10-18','13:00'),
    ('NYJ','NE','2026-10-18','13:00'),
    ('ARI','LA','2026-10-18','16:05'),
    ('LAC','KC','2026-10-18','16:25'),
    ('BUF','LV','2026-10-18','16:25'),
    ('DAL','GB','2026-10-18','20:20'),
    ('WAS','SF','2026-10-19','20:15')]


def make_schedule(full=True):
    rows=[]
    if full:
        counts={w:15 for w in range(1,19)}
        counts.update({1:16,2:16,3:16,6:14})  # 272 games spread across 18 weeks
        assert sum(counts.values())==272
    else:counts={6:14,17:15,18:15}
    base=datetime(2026,9,10)
    for week,n in counts.items():
        for i in range(n):
            if week==6:
                away,home,day,tm=W6[i]
            else:
                day=(base+timedelta(weeks=week-1,days=3+i%2)).strftime('%Y-%m-%d')
                tm='13:00'; away=f'T{i}';home=f'H{i}'
            played=week<6
            rows.append({'season':2026,'game_type':'REG','week':week,
                         'game_id':f'2026_{week:02}_{i:02}',
                         'gameday':day,'gametime':tm,
                         'away_team':away,'home_team':home,
                         'away_score':17+i%4 if played else None,
                         'home_score':20+i%3 if played else None})
    return pd.DataFrame(rows)


def test_full_season_not_truncated_and_week6_by_default():
    prepared=nfl_schedule.prepare_schedule(make_schedule(),2026,asof=ASOF)
    assert len(prepared)==272
    assert nfl_schedule.coverage(prepared)['warnings']==[]
    assert nfl_schedule.active_week(prepared,ASOF)==6
    visible=nfl_schedule.select_games(prepared,'Current week',ASOF)
    assert len(visible)==14 and set(visible.week)=={6}
    assert {('SEA','DEN'),('HOU','JAX'),('WAS','SF')}<=set(zip(visible.away_team,visible.home_team))
    assert not ({17,18}&set(visible.week))
    view=nfl_schedule.table(visible)
    assert len(view)==14 and view.iloc[0]['Kickoff (ET)']=='Thu Oct 15, 08:15 PM'
    assert set(view['Status'])=={'Scheduled'}


def test_all_weeks_browse_and_filters_not_last_30():
    prepared=nfl_schedule.prepare_schedule(make_schedule(),2026,ASOF)
    assert len(nfl_schedule.select_games(prepared,'All regular season',ASOF))==272
    assert len(nfl_schedule.select_games(prepared,'Specific week',ASOF,week=17))==15
    completed=nfl_schedule.select_games(prepared,'Completed',ASOF)
    upcoming=nfl_schedule.select_games(prepared,'Upcoming',ASOF)
    assert len(completed)==16+16+16+15+15  # Weeks 1 to 5
    assert len(upcoming)==272-len(completed)
    seven=nfl_schedule.select_games(prepared,'Next 7 days',ASOF)
    assert len(seven)==14
    assert not set(completed.game_id)&set(upcoming.game_id)
    assert nfl_schedule.table(prepared.iloc[12:30])['Result'].iloc[0]!='—'


def test_timezone_and_espn_real_week6_matchup_crosscheck():
    prepared=nfl_schedule.prepare_schedule(make_schedule(),2026,ASOF)
    wk=nfl_schedule.select_games(prepared,'Current week',ASOF)
    espn=[]
    for row in wk.itertuples(index=False):
        home='LAR' if row.home_team=='LA' else ('WSH' if row.home_team=='WAS' else row.home_team)
        away='LAR' if row.away_team=='LA' else ('WSH' if row.away_team=='WAS' else row.away_team)
        espn.append({'home_team':home,'away_team':away,'kickoff_utc':row.kickoff_utc.isoformat()})
    report=nfl_schedule.compare_espn(prepared,espn,6)
    assert report['consistent'] and report['matches']==14
    espn[0]['kickoff_utc']='2026-10-22T00:15:00+00:00'
    report=nfl_schedule.compare_espn(prepared,espn,6)
    assert not report['consistent'] and report['date_disagreements']
    report=nfl_schedule.compare_espn(prepared,espn[:-1],6)
    assert not report['consistent'] and report['missing_in_espn']


def test_result_not_leaked_before_real_kickoff_even_with_scores():
    bad=make_schedule(full=False)
    bad.loc[bad.game_id=='2026_06_00',['home_score','away_score']]=[24,20]
    out=nfl_schedule.prepare_schedule(bad,2026,ASOF)
    thurs=out[out.game_id=='2026_06_00'].iloc[0]
    assert thurs.status=='Scheduled'  # it's 1 pm Eastern, 8:15 kickoff
    assert all(g['week']<6 for g in models.scores_from_schedule(out[out.status=='Final'],ASOF))
    later=datetime(2026,10,16,10,tzinfo=timezone.utc)
    out=nfl_schedule.prepare_schedule(bad,2026,later)
    assert out[out.game_id=='2026_06_00'].iloc[0].status=='Final'


def test_missing_time_date_only_and_no_premature_final():
    data=make_schedule(full=False)
    data.loc[data.game_id=='2026_06_00','gametime']=None
    data.loc[data.game_id=='2026_06_00',['home_score','away_score']]=[24,20]
    out=nfl_schedule.prepare_schedule(data,2026,ASOF)
    row=out[out.game_id=='2026_06_00'].iloc[0]
    assert row.status=='Scheduled'
    assert 'time unavailable' in nfl_schedule.table(out[out.game_id=='2026_06_00']).iloc[0]['Kickoff (ET)']
    assert nfl_schedule.coverage(out)['warnings']


def test_empty_wrong_season_and_duplicate_ids_rejected():
    with pytest.raises(ValueError,match='no schedule'):nfl_schedule.prepare_schedule(pd.DataFrame(),2026,ASOF)
    with pytest.raises(ValueError,match='no 2027'):nfl_schedule.prepare_schedule(make_schedule(False),2027,ASOF)
    dup=make_schedule(False)
    dup.loc[dup.index[1],'game_id']=dup.loc[dup.index[0],'game_id']
    with pytest.raises(ValueError,match='duplicate'):nfl_schedule.prepare_schedule(dup,2026,ASOF)


def test_provider_api_unofficial_espn_week_parse_and_failure():
    payload={'events':[{'date':'2026-10-16T00:15:00Z','competitions':[{'competitors':[
        {'homeAway':'home','team':{'abbreviation':'DEN'}},
        {'homeAway':'away','team':{'abbreviation':'SEA'}}]}]}]}
    with patch('edgeforce.providers.get_json',return_value=payload) as req:
        rows=providers.espn_nfl_week(2026,6)
        assert len(rows)==1 and rows[0]['away_team']=='SEA'
        assert req.call_args.args[1]['week']==6
    with patch('edgeforce.providers.get_json',return_value={'events':[]}):
        with pytest.raises(providers.ProviderError,match='No ESPN games'):
            providers.espn_nfl_week(2026,6)


def test_provider_loads_season_without_last_30_truncation():
    src=make_schedule()
    fake=SimpleNamespace(load_schedules=lambda year: SimpleNamespace(to_pandas=lambda:src.copy()))
    with patch.dict(sys.modules,{'nflreadpy':fake}):
        full=providers.nfl_games(2026)
        assert len(full)==272 and sorted(set(full.week))==list(range(1,19))


def test_2020_old_17_week_format_coverage_does_not_warn_272():
    frames=make_schedule(False)
    frames['season']=2020
    frames=frames[frames.week<=17]
    normalized=nfl_schedule.prepare_schedule(frames,2020,datetime(2020,10,15,tzinfo=timezone.utc))
    report=nfl_schedule.coverage(normalized)
    assert '256' in report['warnings'][0]  # Old expected total, not 272


def test_manual_sync_attempts_schedule_only_cache_clear():
    calls=[]
    fake=SimpleNamespace(
        clear_cache=lambda pattern:calls.append(pattern),
        load_schedules=lambda year:SimpleNamespace(to_pandas=lambda:make_schedule()))
    with patch.dict(sys.modules,{'nflreadpy':fake}):
        assert len(providers.nfl_games(2026))==272
    assert calls==['schedules/games']


def test_app_no_last_30_records_and_sportsbook_logic_unchanged():
    from pathlib import Path
    app=Path(__file__).resolve().parents[1].joinpath('app.py').read_text()
    assert "nfl_schedule.select_games(df,view" in app
    assert "nfl_schedule.table(selected)" in app
    assert "nfl_schedule_df']" in app
    assert 'df[[x for x in (\'week\',\'gameday\'' not in app
