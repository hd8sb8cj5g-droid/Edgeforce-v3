import sqlite3
from datetime import datetime, timezone,timedelta
from unittest.mock import patch
import pytest
from edgeforce import db,providers,models,ledger,parlays


def quote(hours=24,price=-110,market='h2h',point=None,selection='Minnesota Vikings',book='Book One'):
    future=(datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat(timespec='seconds')
    return dict(event_id='evt123',sport='NFL',home_team='Minnesota Vikings',
        away_team='Green Bay Packers',commence_time=future,bookmaker=book,
        market=market,selection=selection,point=point,
        american_odds=price,source='The Odds API')


@pytest.fixture
def store(tmp_path):
    path=tmp_path/'ledger.db';db.init_db(path)
    return path


def test_odds_math_and_spreads():
    assert models.american_decimal(150)==2.5
    assert models.american_decimal(-200)==1.5
    assert models.implied(150)==pytest.approx(.4)
    assert models.ev_per_dollar(.44,150)==pytest.approx(.1)
    assert models.fair_american(.4)==150
    game={'hs':24,'as':20}
    q=quote(market='spreads',point=-3.5)
    assert models.resolve_score(q,game)=='WIN'
    q['point']=-4.0
    assert models.resolve_score(q,game)=='PUSH'
    q['selection']='Green Bay Packers';q['point']=3.5
    assert models.resolve_score(q,game)=='LOSS'
    q['market']='totals';q['selection']='Over';q['point']=44.
    assert models.resolve_score(q,game)=='PUSH'


def test_ledger_immutable_and_correct_entry_price(store):
    ids=db.insert_snapshots([quote(price=140)],store)
    db.insert_snapshots([quote(price=155)],store)
    prediction=db.log_prediction(ids[0],.47,grade='C',stake=20,path=store)
    history=ledger.performance_rows(store)
    assert history[0]['american_odds']==140  # original, NOT later improved quote
    assert history[0]['snapshot_id']==ids[0]
    with db.connect(store) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute('UPDATE odds_snapshots SET american_odds=999 WHERE id=?',(ids[0],))
    with db.connect(store) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute('DELETE FROM predictions WHERE id=?',(prediction,))


def test_closing_missing_and_correct_line(store):
    q=quote(hours=4)
    ids=db.insert_snapshots([q],store)
    snap=db.latest_quotes(path=store)[0]
    assert db.closing_quote(snap,path=store) is None  # 4h before kickoff is NOT closing
    near=(datetime.fromisoformat(q['commence_time'])-timedelta(minutes=10)).isoformat()
    q2=dict(q,american_odds=-125,observed_at=near)
    db.insert_snapshots([q2],store)
    close=db.closing_quote(snap,path=store)
    assert close['american_odds']==-125
    q3=dict(q2,american_odds=-130,observed_at=(datetime.fromisoformat(q['commence_time'])+timedelta(minutes=2)).isoformat())
    db.insert_snapshots([q3],store)
    assert db.closing_quote(snap,path=store)['american_odds']==-125
    spread=dict(q2,market='spreads',point=-3.5)
    sid=db.insert_snapshots([spread],store)[0]
    altered=dict(spread,point=-4.0,american_odds=120)
    db.insert_snapshots([altered],store)
    spreads=[r for r in db.latest_quotes(path=store) if r['id']==sid]
    assert db.closing_quote(spreads[0],path=store)['point']==-3.5


def test_settlement_append_corrections_and_metrics(store):
    sid=db.insert_snapshots([quote(price=120)],store)[0]
    pred=db.log_prediction(sid,.51,stake=25,path=store)
    db.settle(pred,'LOSS',source='test',home_score=17,away_score=24,path=store)
    assert ledger.metrics(ledger.performance_rows(store))['pnl']==-25
    db.settle(pred,'WIN',source='corrected result',home_score=24,away_score=17,path=store)
    hist=ledger.performance_rows(store)
    assert hist[0]['outcome']=='WIN'
    assert hist[0]['realized_pnl']==pytest.approx(30)
    with db.connect(store) as d:
        assert d.execute('SELECT COUNT(*) FROM settlements').fetchone()[0]==2


def test_parlay_locked_prices(store):
    one=db.insert_snapshots([quote(price=-110)],store)[0]
    two=db.insert_snapshots([dict(quote(),event_id='evt456',home_team='Chicago Bears',away_team='Detroit Lions',selection='Chicago Bears',american_odds=150)],store)[0]
    tid=db.log_ticket([one,two],10,.3,.05,'Core',path=store)
    db.insert_snapshots([dict(quote(),american_odds=-200)],store)
    hist=db.ticket_history(store)
    assert hist[0]['id']==tid
    assert hist[0]['combined_decimal']==pytest.approx(models.american_decimal(-110)*2.5)
    db.settle_ticket(tid,'WIN',path=store,note='test final')
    assert db.ticket_history(store)[0]['outcome']=='WIN'


def test_joint_simulation_same_game_dependency():
    proj={'home':28,'away':21,'margin':7,'total':49,'margin_sd':12.5,'total_sd':13.}
    q1=quote(market='h2h',selection='Minnesota Vikings',price=-130)
    q2=quote(market='totals',selection='Over',point=47.5,price=-110)
    sims=parlays.joint_ticket([q1,q2],{'evt123':proj},n=10000)
    assert 0<sims['win_prob']<1
    assert sims['n']==10000
    assert sims['decimal_payout']>1


def test_odds_api_normalizer_is_not_demo():
    raw=[{'id':'event','commence_time':'2030-11-01T17:00:00Z','home_team':'A','away_team':'B',
      'bookmakers':[{'key':'book','title':'Bestbook','last_update':'2030-10-31T00:00:00Z',
      'markets':[{'key':'h2h','outcomes':[{'name':'A','price':-120},{'name':'B','price':110}]}]}]}]
    with patch('edgeforce.providers.get_json',return_value=raw) as getter:
        q=providers.odds_api('NFL',key='key')
    assert len(q)==2
    assert q[0]['source']=='The Odds API'
    assert q[0]['source_updated_at']=='2030-10-31T00:00:00Z'
    assert q[0]['american_odds']==-120


def test_auto_settle_only_unique_matched_final(store):
    sid=db.insert_snapshots([quote(hours=4,market='totals',point=45.5,selection='Over')],store)[0]
    pred=db.log_prediction(sid,.5,path=store)
    q=db.latest_quotes(path=store)[0]
    games=[dict(home='MIN',away='GB',hs=31,**{'as':21},
                date=q['commence_time'],sport='NFL')]
    res=ledger.auto_settle(games,store)
    assert res['settled']==1
    assert db.prediction_history(store)[0]['outcome']=='WIN'


def test_auto_parlay_full_outcome(store):
    a=quote(hours=4)
    b=dict(quote(hours=4),event_id='evt777',home_team='Chicago Bears',
           away_team='Detroit Lions',selection='Chicago Bears',american_odds=-115)
    ids=db.insert_snapshots([a,b],store)
    tid=db.log_ticket(ids,15,.3,.01,path=store)
    games=[dict(home='MIN',away='GB',hs=21,**{'as':17},date=a['commence_time'],sport='NFL'),
           dict(home='CHI',away='DET',hs=10,**{'as':14},date=b['commence_time'],sport='NFL')]
    settled=ledger.auto_settle_tickets(games,store)
    assert settled['settled']==1
    assert db.ticket_history(store)[0]['outcome']=='LOSS'


def test_wal_safe_backup_includes_prices_and_history(store,tmp_path):
    sid=db.insert_snapshots([quote()],store)[0]
    db.log_prediction(sid,.56,path=store)
    backup=tmp_path/'restore.sqlite3'
    backup.write_bytes(db.backup_bytes(store))
    assert db.snapshot_counts(backup)==(1,1,0)
    assert len(db.prediction_history(backup))==1
