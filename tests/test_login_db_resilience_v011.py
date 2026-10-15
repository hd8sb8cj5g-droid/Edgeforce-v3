"""Regression coverage for stale Neon pool and complete-but-bounded login preload."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
import sys
import pytest

from edgeforce import cloud_db, login_bootstrap, db


def quote(age_minutes, source='The Odds API', market='h2h'):
    now=datetime.now(timezone.utc)
    return {'event_id':'E1','sport':'NFL','observed_at':(now-timedelta(minutes=age_minutes)).isoformat(),
            'commence_time':(now+timedelta(days=2)).isoformat(),'source':source,
            'market':market}


def test_featured_odds_login_does_not_resync_fresh_quote():
    assert not login_bootstrap.should_sync_featured([quote(8)])
    assert login_bootstrap.should_sync_featured([quote(33)])
    assert login_bootstrap.should_sync_featured([quote(1,source='SYNTHETIC DEMO')])
    assert login_bootstrap.should_sync_featured([quote(1,market='player_rush_yds')])


def test_login_load_once_and_independent_failure_with_no_secret_leaks():
    called=[];state={};progress=[]
    def fail():
        called.append('broken')
        raise RuntimeError('postgresql://someuser:secret@example.com/db')
    steps=[('NFL schedule',lambda:called.append('schedule') or 272),('Neon odds',fail),('CFB',lambda:called.append('cfb') or 90)]
    one=login_bootstrap.load_once(state,steps,lambda d,n,name:progress.append(d))
    assert [x['status'] for x in one]==['Loaded','Unavailable','Loaded']
    assert 'secret' not in repr(one) and 'example.com' not in repr(one)
    assert progress==[1,2,3]
    assert login_bootstrap.load_once(state,steps)==one
    assert len(called)==3
    login_bootstrap.load_once(state,steps,force=True)
    assert len(called)==6


def test_sqlite_upcoming_quotes_keeps_audit_history(tmp_path):
    path=str(tmp_path/'audit.sqlite3')
    db.init_db(path)
    now=datetime.now(timezone.utc)
    snapshot=lambda eid,day:{'event_id':eid,'sport':'NFL','commence_time':(now+timedelta(days=day)).isoformat(),
                            'home_team':'KC','away_team':'BUF','bookmaker':'Example','market':'h2h','selection':'KC',
                            'american_odds':-110,'source':'The Odds API'}
    db.insert_snapshots([snapshot('future',2),snapshot('past',-11)],path)
    window=db.upcoming_quotes('NFL',path)
    assert [x['event_id'] for x in window]==['future']
    assert len(db.latest_quotes('NFL',path))==2


def test_pool_checks_recycled_connections_without_explicit_begin(monkeypatch):
    created=[]
    class FakeConnectionPool:
        @staticmethod
        def check_connection(c):
            return None
        def __init__(self,*args,**kwargs):
            created.append(kwargs)
            self.closed=False
        @contextmanager
        def connection(self):
            class Conn:
                def transaction(self):
                    raise AssertionError('redundant BEGIN must not occur')
                def execute(self,query):
                    return SimpleNamespace(fetchone=lambda: {'ready':1})
            yield Conn()
    pool=ModuleType('psycopg_pool')
    pool.ConnectionPool=FakeConnectionPool
    monkeypatch.setitem(sys.modules,'psycopg_pool',pool)
    rows=ModuleType('psycopg.rows');rows.dict_row=object()
    monkeypatch.setitem(sys.modules,'psycopg.rows',rows)
    monkeypatch.setenv('EDGEFORCE_POSTGRES_URL','postgresql://fake:pass@localhost/db')
    monkeypatch.setattr(cloud_db,'_POOL',None)
    assert cloud_db.check_connection() is True
    assert created[0]['check']==FakeConnectionPool.check_connection
    assert created[0]['max_idle'] <= 60
    assert cloud_db.check_connection() is True
    assert len(created)==1
    monkeypatch.setattr(cloud_db,'_POOL',None)


def test_cloud_select_retry_once_for_transient_disconnect(monkeypatch):
    class FakeOpError(Exception):pass
    class FakeInterfaceError(Exception):pass
    class FakePoolTimeout(Exception):pass
    psy=ModuleType('psycopg');psy.OperationalError=FakeOpError;psy.InterfaceError=FakeInterfaceError
    pool=ModuleType('psycopg_pool');pool.PoolTimeout=FakePoolTimeout
    monkeypatch.setitem(sys.modules,'psycopg',psy)
    monkeypatch.setitem(sys.modules,'psycopg_pool',pool)
    count=[]
    @contextmanager
    def maybe_broken(path=None):
        count.append(True)
        if len(count)==1:raise FakeOpError('connection slept')
        class C:
            def execute(self,sql,params):
                return SimpleNamespace(fetchall=lambda:[{'id':'1'}])
        yield C()
    monkeypatch.setattr(cloud_db,'connect',maybe_broken)
    monkeypatch.setattr(cloud_db.time,'sleep',lambda _:None)
    assert cloud_db._fetchall('SELECT 1')==[{'id':'1'}]
    assert len(count)==2


def test_cloud_writes_not_replayed_on_disconnect(monkeypatch):
    class FakeOpError(Exception):pass
    count=[]
    @contextmanager
    def broken(path=None):
        count.append(True)
        class C:
            def execute(self,*args):raise FakeOpError('lost after execute')
        yield C()
    monkeypatch.setattr(cloud_db,'connect',broken)
    with pytest.raises(FakeOpError):
        cloud_db.insert_snapshots([{
            'event_id':'t','sport':'NFL','commence_time':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            'home_team':'Home','away_team':'Away','bookmaker':'Book','market':'h2h',
            'selection':'Home','american_odds':-110,'source':'The Odds API'
        }])
    assert len(count)==1
