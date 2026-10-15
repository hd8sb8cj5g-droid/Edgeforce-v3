"""Prop feed regression: provider->normalization->auditable ledger->renderable data."""
from datetime import datetime, timedelta, timezone
import copy
import pytest
from edgeforce import providers, db, prop_market, value

NOW=datetime.now(timezone.utc).replace(microsecond=0)
KICKOFF=(NOW+timedelta(days=2)).isoformat()
UPDATED=(NOW-timedelta(seconds=45)).isoformat()
EVENT='evt_VALID_2026_A'


def fake_event(book_names=('DraftKings','FanDuel','BetMGM')):
    prices=[(-110,-110),(-115,-105),(-125,105)]
    return {'id':EVENT,'sport_key':'americanfootball_nfl',
        'commence_time':KICKOFF,'home_team':'Chicago Bears','away_team':'Green Bay Packers',
        'bookmakers':[{'key':name.lower(),'title':name,'markets':[
            {'key':'player_reception_yds','last_update':UPDATED,'outcomes':[
              {'name':'Over','description':'Receiver A','point':54.5,'price':price[0]},
              {'name':'Under','description':'Receiver A','point':54.5,'price':price[1]}
            ]}]}
            for name,price in zip(book_names,prices)]}


def test_discover_available_event_markets_one_market_credit(monkeypatch):
    calls=[]
    def mock_get(url,params=None,**kwargs):
        calls.append((url,params,kwargs))
        return ({'bookmakers':[
            {'title':'FanDuel','markets':[{'key':'player_reception_yds'},{'key':'h2h'}]},
            {'title':'DraftKings','markets':[{'key':'player_reception_yds'}]}]},
            {'x-requests-last':'1','x-requests-remaining':'109'})
    monkeypatch.setattr(providers,'get_json',mock_get)
    available=providers.odds_event_markets('NFL',EVENT,key='dummy-safe-key')
    assert available['player_reception_yds']==['DraftKings','FanDuel']
    assert providers.odds_usage()['last']=='1'
    assert len(calls)==1 and calls[0][0].endswith('/events/'+EVENT+'/markets')
    assert calls[0][1]['regions']=='us'


def test_fetch_event_props_and_show_market_diagnostics(monkeypatch,tmp_path):
    def mock_get(url,params=None,**kwargs):
        assert url.endswith('/events/'+EVENT+'/odds')
        assert params['markets']=='player_reception_yds'
        return (fake_event(),{'x-requests-last':'1','x-requests-remaining':'108'})
    monkeypatch.setattr(providers,'get_json',mock_get)
    result=providers.odds_event_props('NFL',EVENT,key='dummy-safe-key',
        markets=['player_reception_yds'],return_report=True)
    assert len(result['quotes'])==6
    assert result['report']['book_count']==3
    assert not result['report']['missing_markets']
    assert result['report']['last_request_cost']=='1'
    assert result['quotes'][0]['participant']=='Receiver A'
    assert result['quotes'][0]['point']==54.5
    datafile=tmp_path/'prop_quotes.sqlite3'
    db.init_db(datafile)
    assert len(db.insert_snapshots(result['quotes'],path=datafile))==6
    saved=db.latest_quotes('NFL',path=datafile)
    diag=prop_market.summarize(saved,now=datetime.now(timezone.utc))
    assert diag['raw_quotes']==6 and diag['players']==1 and diag['bookmakers']==3
    assert diag['reference_qualified_groups']==1
    rendered=prop_market.display_rows(saved)
    assert len(rendered)==6 and all('Source updated UTC' in r for r in rendered)
    # No obligation to have +EV: good prop quote can fail positive value filter.
    assert value.scan(saved,NOW,min_ev_pct=500)==[]


def test_provider_returns_zero_props_not_false_success(monkeypatch):
    def mock_get(url,params=None,**kwargs):
        return ({**fake_event(), 'bookmakers':[]}, {'x-requests-remaining':'105','x-requests-last':'0'})
    monkeypatch.setattr(providers,'get_json',mock_get)
    result=providers.odds_event_props('NFL',EVENT,key='dummy-safe-key',
        markets=['player_pass_yds','player_reception_yds'],return_report=True)
    assert result['quotes']==[]
    assert result['report']['quote_count']==0 and result['report']['book_count']==0
    assert set(result['report']['missing_markets'])=={'player_pass_yds','player_reception_yds'}
    assert 'No player-prop offers' in prop_market.summarize([],now=NOW)['reason']


def test_one_sided_or_different_lines_show_raw_but_no_ev():
    raw=fake_event()
    raw['bookmakers'][2]['markets'][0]['outcomes'][1]['point']=55.5
    q=providers.normalize_odds_event(raw,'NFL')
    for x in q:x['observed_at']=NOW.isoformat()
    diag=prop_market.summarize(q,now=NOW)
    assert diag['raw_quotes']==6
    assert diag['two_sided_groups']==1
    assert diag['reference_qualified_groups']==0
    assert value.scan(q,NOW)==[]


def test_stale_prices_visible_as_historical_not_current_ev():
    q=providers.normalize_odds_event(fake_event(),'NFL')
    for x in q:x['observed_at']=(NOW-timedelta(hours=5)).isoformat()
    diag=prop_market.summarize(q,now=NOW)
    assert diag['raw_quotes']==6 and diag['fresh_quotes']==0
    assert prop_market.display_rows(q)
    assert value.scan(q,NOW)==[]


def test_refuses_mismatched_event_id(monkeypatch):
    monkeypatch.setattr(providers,'get_json',lambda *a,**kw:
        ({**fake_event(),'id':'wrong_event_id'},{}))
    with pytest.raises(providers.ProviderError,match='does not match'):
        providers.odds_event_props('NFL',EVENT,key='dummy-safe-key',return_report=True)


def test_rejects_invalid_event_without_spending_credits(monkeypatch):
    monkeypatch.setattr(providers,'get_json',lambda *a,**kw:pytest.fail('should not issue request'))
    with pytest.raises(providers.ProviderError,match='Invalid event'):
        providers.odds_event_markets('NFL','bad/event',key='dummy-safe-key')


def test_v041_return_contract_still_list(monkeypatch):
    monkeypatch.setattr(providers,'get_json',lambda *a,**kw:(fake_event(),{}))
    q=providers.odds_event_props('NFL',EVENT,key='dummy-safe-key',markets=['player_reception_yds'])
    assert isinstance(q,list) and len(q)==6


def test_ui_uses_market_discovery_and_shows_all_raw_props():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert 'providers.odds_event_markets' in app
    assert 'return_report=True' in app
    assert "raw_props=[q for q in db.latest_quotes(sport)" in app
    assert 'prop_market.display_rows(raw_props)' in app
    assert "st.session_state.setdefault('prop_fetch_reports'" in app


def test_positive_ev_survives_provider_to_db_pipeline(tmp_path):
    payload=fake_event()
    payload['bookmakers'][0]['markets'][0]['outcomes'][0]['price']=+120
    payload['bookmakers'][0]['markets'][0]['outcomes'][1]['price']=-150
    payload['bookmakers'][1]['markets'][0]['outcomes'][0]['price']=-110
    payload['bookmakers'][1]['markets'][0]['outcomes'][1]['price']=-110
    payload['bookmakers'][2]['markets'][0]['outcomes'][0]['price']=-110
    payload['bookmakers'][2]['markets'][0]['outcomes'][1]['price']=-110
    q=providers.normalize_odds_event(payload,'NFL')
    for x in q:x['observed_at']=NOW.isoformat()
    path=tmp_path/'example.sqlite3'
    db.init_db(path)
    db.insert_snapshots(q,path=path)
    candidates=value.scan(db.latest_quotes('NFL',path=path),NOW,min_ev_pct=1)
    assert len(candidates)==1
    assert candidates[0]['quote']['participant']=='Receiver A'
    assert abs(candidates[0]['ev_pct']-10)<1e-9
    assert set(candidates[0]['reference_books'])=={'BetMGM','FanDuel'}
