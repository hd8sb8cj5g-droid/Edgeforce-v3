"""Runs against a disposable PostgreSQL service in GitHub Actions, never Neon.

Run manually with EDGEFORCE_TEST_POSTGRES_URL to verify real psycopg protocol,
transaction behavior, and schema persistence before production deployment.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest

if not os.getenv('EDGEFORCE_TEST_POSTGRES_URL'):
    pytest.skip('Disposable test PostgreSQL URL not configured', allow_module_level=True)

from edgeforce import cloud_db


def test_real_postgres_full_audit_cycle(monkeypatch):
    monkeypatch.setenv('EDGEFORCE_POSTGRES_URL',os.environ['EDGEFORCE_TEST_POSTGRES_URL'])
    monkeypatch.setattr(cloud_db,'_POOL',None)
    assert cloud_db.check_connection()
    cloud_db.init_db()
    eid='ci-'+str(uuid4())
    observed=datetime.now(timezone.utc)
    quote={'event_id':eid,'sport':'NFL','commence_time':(observed+timedelta(days=2)).isoformat(),
           'home_team':'Kansas City Chiefs','away_team':'Buffalo Bills',
           'bookmaker':'CI Test Book','market':'h2h','selection':'Kansas City Chiefs',
           'point':None,'american_odds':-115,'source':'CI SYNTHETIC TEST',
           'observed_at':observed.isoformat()}
    ids=cloud_db.insert_snapshots([quote])
    assert len(ids)==1
    saved=[x for x in cloud_db.upcoming_quotes('NFL') if x['event_id']==eid]
    assert len(saved)==1 and saved[0]['id']==ids[0]
    assert cloud_db.check_connection()
    pid=cloud_db.log_prediction(ids[0],0.52,stake=10,rationale='CI synthetic test')
    assert pid
    sid=cloud_db.settle(pid,'WIN',source='CI TEST',home_score=17,away_score=10)
    assert sid
    # Trigger must preserve audit history even if code accidentally attempts an update.
    with pytest.raises(Exception):
        with cloud_db.connect() as conn:
            conn.execute('UPDATE edgeforce.odds_snapshots SET american_odds=+500 WHERE id=%s',(ids[0],))
    assert any(x['id']==ids[0] and x['american_odds']==-115 for x in cloud_db.latest_quotes('NFL'))
