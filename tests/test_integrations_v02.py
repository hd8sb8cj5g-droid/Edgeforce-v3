"""Contract tests use mocked provider responses; they do not expend API credits."""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import sqlite3
import requests
import pytest
from edgeforce import db, models, providers


def source_event():
    return {'id':'abcdef1234567890','commence_time':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),
      'home_team':'Minnesota Golden Gophers','away_team':'Wisconsin Badgers',
      'bookmakers':[{'key':'example','title':'Example Sportsbook','last_update':datetime.now(timezone.utc).isoformat(),
        'markets':[{'key':'player_pass_yds','outcomes':[
          {'name':'Over','description':'QB One','point':245.5,'price':-110},
          {'name':'Under','description':'QB One','point':245.5,'price':-115},
          {'name':'Over','description':'QB Two','point':245.5,'price':120},
          {'name':'Under','description':'QB Two','point':245.5,'price':-130}
        ]}]}]}


def test_player_props_have_distinct_player_ids(tmp_path):
    quotes=providers.normalize_odds_event(source_event(),'CFB',{'player_pass_yds'})
    assert len(quotes)==4
    store=tmp_path/'edgeforce.sqlite3'
    db.init_db(store)
    db.insert_snapshots(quotes,path=store)
    latest=db.latest_quotes('CFB',path=store)
    assert len(latest)==4
    assert len({(q['participant'],q['selection'],q['point']) for q in latest})==4
    choice=next(q for q in latest if q['participant']=='QB One' and q['selection']=='Over')
    assert models.no_vig_probability(latest,choice)==pytest.approx(
        models.implied(-110)/(models.implied(-110)+models.implied(-115)))


def test_event_prop_api_sends_only_selected_markets_and_tracks_quota():
    with patch('edgeforce.providers.get_json',return_value=(source_event(),{
        'X-Requests-Remaining':'103','X-Requests-Used':'7','X-Requests-Last':'2'})) as req:
        qs=providers.odds_event_props('CFB','abcdef1234567890',key='not-real-secret',markets=['player_pass_yds'])
    assert len(qs)==4
    assert providers.odds_usage()=={'remaining':'103','used':'7','last':'2'}
    assert '/events/abcdef1234567890/odds' in req.call_args.args[0]
    assert req.call_args.args[1]['markets']=='player_pass_yds'
    assert 'not-real-secret' not in str(qs)


def test_market_quote_ingestion_and_quota_headers():
    event=source_event()
    event['bookmakers'][0]['markets']=[{'key':'h2h','outcomes':[
        {'name':event['home_team'],'price':-120},{'name':event['away_team'],'price':105}]}]
    with patch('edgeforce.providers.get_json',return_value=([event],{
        'X-Requests-Remaining':'998','X-Requests-Last':'3'})):
        qs=providers.odds_api('CFB',key='test-credential')
    assert len(qs)==2
    assert providers.odds_usage()['remaining']=='998'
    assert all(q['participant']=='' for q in qs)


def test_cfbd_mascot_aliases_resolve_model_team_matching():
    n=models.register_cfb_teams([{'school':'Minnesota','mascot':'Golden Gophers','abbreviation':'MINN',
       'alternateNames':['Minnesota U']},
      {'school':'Wisconsin','mascot':'Badgers','abbreviation':'WISC'}])
    try:
        assert n>=4
        assert models.team_key('Minnesota Golden Gophers','CFB')==models.team_key('Minnesota','CFB')
        assert models.team_key('Wisconsin Badgers','CFB')==models.team_key('Wisconsin','CFB')
        samples=[{'home':'Minnesota','away':'Wisconsin','hs':31,'as':24,'date':f'2026-09-0{x}','sport':'CFB'} for x in range(1,6)]
        summary=models.team_summary(samples,'CFB')
        assert models.project_scores('Minnesota Golden Gophers','Wisconsin Badgers','CFB',summary) is not None
    finally:
        models.CFB_ALIASES.clear()


def test_provider_error_never_exposes_url_api_key():
    key='do-not-display-this-credential'
    response=requests.Response()
    response.status_code=401
    response.url='https://api.the-odds-api.com/v4/sports?apiKey='+key
    with patch.object(providers.SESSION,'get',return_value=response):
        with pytest.raises(providers.ProviderError) as err:
            providers.get_json('https://api.the-odds-api.com/v4/sports',params={'apiKey':key})
    assert key not in str(err.value)
    assert '401' in str(err.value)
    with patch.object(providers.SESSION,'get',side_effect=requests.ConnectionError('key='+key)):
        with pytest.raises(providers.ProviderError) as err2:
            providers.get_json('https://api.the-odds-api.com/v4/sports',params={'apiKey':key})
    assert key not in str(err2.value)


def test_existing_db_migrates_participant_without_losing_quotes(tmp_path):
    store=tmp_path/'old.sqlite3'
    with sqlite3.connect(store) as conn:
        conn.execute('''CREATE TABLE odds_snapshots (id TEXT PRIMARY KEY,observed_at TEXT NOT NULL,
            source_updated_at TEXT,event_id TEXT NOT NULL,sport TEXT NOT NULL,
            commence_time TEXT NOT NULL,home_team TEXT NOT NULL,away_team TEXT NOT NULL,
            bookmaker TEXT NOT NULL,market TEXT NOT NULL,selection TEXT NOT NULL,point REAL,
            american_odds INTEGER NOT NULL,source TEXT NOT NULL,raw_json TEXT NOT NULL DEFAULT '{}')''')
        conn.execute('''INSERT INTO odds_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('original','2026-01-01T00:00:00+00:00',None,'event','NFL','2026-10-30T00:00:00Z',
             'Minnesota Vikings','Green Bay Packers','Book','h2h','Minnesota Vikings',None,110,'The Odds API','{}'))
    db.init_db(store)
    original=db.latest_quotes('NFL',path=store)
    assert len(original)==1 and original[0]['id']=='original' and original[0]['participant']==''
    assert db.snapshot_counts(store)[0]==1
    with db.connect(store) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('UPDATE odds_snapshots SET american_odds=999')
