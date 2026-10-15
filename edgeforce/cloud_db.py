"""Durable PostgreSQL audit ledger for cloud-hosted EdgeForce.

Uses an isolated `edgeforce` schema with insert-only evidence tables and
append-only settlements. Activated by EDGEFORCE_POSTGRES_URL at startup.
The fallback `edgeforce.db` module implements the same API on SQLite.
"""
import csv
import io
import json
import os
import zipfile
from contextlib import contextmanager
from datetime import timedelta, datetime, timezone
from uuid import uuid4

from . import db as sqlite_db


_POOL = None


def _get_pool():
    global _POOL
    if _POOL is None:
        from psycopg_pool import ConnectionPool
        from psycopg.rows import dict_row
        url=os.getenv('EDGEFORCE_POSTGRES_URL')
        if not url:
            raise RuntimeError('Cloud storage requires EDGEFORCE_POSTGRES_URL configured in Streamlit secrets')
        _POOL=ConnectionPool(url,min_size=0,max_size=4,timeout=15,
                             kwargs={'row_factory':dict_row,'connect_timeout':12})
    return _POOL


@contextmanager
def connect(path=None):
    # Connection pool is shared by reruns, avoiding a new TLS handshake for each query.
    with _get_pool().connection() as conn:
        with conn.transaction():
            yield conn


TABLES={
'odds_snapshots': '''(
 id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, source_updated_at TEXT,
 event_id TEXT NOT NULL, sport TEXT NOT NULL, commence_time TEXT NOT NULL,
 home_team TEXT NOT NULL, away_team TEXT NOT NULL, bookmaker TEXT NOT NULL,
 market TEXT NOT NULL, selection TEXT NOT NULL, point DOUBLE PRECISION,
 participant TEXT NOT NULL DEFAULT '', american_odds INTEGER NOT NULL,
 source TEXT NOT NULL, raw_json TEXT NOT NULL DEFAULT '{}')''',
'predictions': '''(
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, snapshot_id TEXT NOT NULL REFERENCES edgeforce.odds_snapshots(id),
 model_probability DOUBLE PRECISION, confidence_grade TEXT NOT NULL, model_version TEXT NOT NULL,
 rationale TEXT NOT NULL, stake DOUBLE PRECISION NOT NULL, tags TEXT NOT NULL)''',
'settlements': '''(
 id TEXT PRIMARY KEY, prediction_id TEXT NOT NULL REFERENCES edgeforce.predictions(id),
 recorded_at TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('WIN','LOSS','PUSH','VOID')),
 final_home_score DOUBLE PRECISION, final_away_score DOUBLE PRECISION, result_source TEXT NOT NULL, note TEXT NOT NULL)''',
'parlay_tickets': '''(
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, stake DOUBLE PRECISION NOT NULL,
 estimated_probability DOUBLE PRECISION, estimated_ev DOUBLE PRECISION, combined_decimal DOUBLE PRECISION NOT NULL,
 simulation_version TEXT NOT NULL, label TEXT NOT NULL, source_note TEXT NOT NULL)''',
'parlay_legs': '''(
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES edgeforce.parlay_tickets(id),
 snapshot_id TEXT NOT NULL REFERENCES edgeforce.odds_snapshots(id))''',
'ticket_settlements': '''(
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES edgeforce.parlay_tickets(id),
 recorded_at TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('WIN','LOSS','PUSH','VOID')),
 source TEXT NOT NULL, note TEXT NOT NULL)''',
'game_scores': '''(
 id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, sport TEXT NOT NULL,
 event_id TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
 home_score DOUBLE PRECISION NOT NULL, away_score DOUBLE PRECISION NOT NULL,
 source TEXT NOT NULL, final_at TEXT,
 UNIQUE(event_id,home_score,away_score,source))'''
}


def init_db(path=None):
    with connect() as conn:
        conn.execute('CREATE SCHEMA IF NOT EXISTS edgeforce')
        for name,schema in TABLES.items():
            conn.execute(f'CREATE TABLE IF NOT EXISTS edgeforce.{name} {schema}')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_odds_event ON edgeforce.odds_snapshots(event_id,observed_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_odds_close ON edgeforce.odds_snapshots(event_id,bookmaker,market,selection,point,observed_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_result_prediction ON edgeforce.settlements(prediction_id,recorded_at)')
        conn.execute('''CREATE OR REPLACE FUNCTION edgeforce.deny_audit_changes() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only audit table'; END $$''')
        for name in TABLES:
            # Cannot CREATE TRIGGER IF NOT EXISTS on all hosted Postgres versions.
            existing=conn.execute('''SELECT 1 FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid
              JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname='edgeforce' AND c.relname=%s AND t.tgname=%s''',
              (name,f'edgeforce_deny_{name}')).fetchone()
            if not existing:
                conn.execute(f'''CREATE TRIGGER edgeforce_deny_{name} BEFORE UPDATE OR DELETE
                     ON edgeforce.{name} FOR EACH ROW EXECUTE FUNCTION edgeforce.deny_audit_changes()''')


def _fetchall(sql,params=()):
    with connect() as conn:
        return [dict(x) for x in conn.execute(sql,params).fetchall()]


def insert_snapshots(quotes,path=None):
    ids=[]
    with connect() as conn:
        for q in quotes:
            p={'id':str(uuid4()),'observed_at':q.get('observed_at') or _utcnow(),
               'source_updated_at':q.get('source_updated_at'),'event_id':str(q['event_id']),
               'sport':q['sport'],'commence_time':q['commence_time'],
               'home_team':q['home_team'],'away_team':q['away_team'],
               'bookmaker':q['bookmaker'],'market':q['market'],'selection':q['selection'],
               'point':q.get('point'),'participant':q.get('participant',''),
               'american_odds':int(q['american_odds']),'source':q['source'],
               'raw_json':json.dumps(q.get('raw',{}),default=str)}
            if p['american_odds']==0:continue
            cols=list(p)
            conn.execute(f'''INSERT INTO edgeforce.odds_snapshots ({','.join(cols)})
              VALUES ({','.join('%s' for _ in cols)})''',tuple(p.values()))
            ids.append(p['id'])
    return ids


def latest_quotes(sport=None,path=None):
    where='WHERE sport=%s' if sport else ''
    qs=(sport,) if sport else ()
    return _fetchall(f'''SELECT DISTINCT ON (event_id,bookmaker,market,selection,point,participant) *
     FROM edgeforce.odds_snapshots {where}
     ORDER BY event_id,bookmaker,market,selection,point,participant,observed_at DESC,id DESC''',qs)


def snapshots_for_event(event_id,path=None):
    return _fetchall('SELECT * FROM edgeforce.odds_snapshots WHERE event_id=%s ORDER BY observed_at', (event_id,))


def log_prediction(snapshot_id,probability,grade='C',version='experimental-v0.1',rationale='',stake=10.,tags='',path=None):
    if probability is not None and not 0<float(probability)<1:raise ValueError('Probability must be in (0,1)')
    if not 0<float(stake)<=1_000_000:raise ValueError('Stake must be positive')
    with connect() as conn:
        q=conn.execute('SELECT * FROM edgeforce.odds_snapshots WHERE id=%s',(snapshot_id,)).fetchone()
        if q is None:raise ValueError('No quoted offer; refresh the feed first')
        start=sqlite_db.parse_utc(q['commence_time']); observed=sqlite_db.parse_utc(q['observed_at'])
        now=sqlite_db.parse_utc(_utcnow())
        if observed>=start or now>=start:raise ValueError('Cannot log a pregame prediction after kickoff')
        if now-observed>timedelta(minutes=30):raise ValueError('Quoted snapshot is over 30 minutes old')
        pid=str(uuid4())
        conn.execute('''INSERT INTO edgeforce.predictions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (pid,_utcnow(),snapshot_id,float(probability) if probability is not None else None,
             grade,version,rationale,float(stake),tags))
        return pid


def settle(prediction_id,outcome,source='manual',home_score=None,away_score=None,note='',path=None):
    if outcome not in ('WIN','LOSS','PUSH','VOID'):raise ValueError('Unsupported settlement')
    with connect() as conn:
        if not conn.execute('SELECT 1 FROM edgeforce.predictions WHERE id=%s',(prediction_id,)).fetchone():
            raise ValueError('Unknown prediction')
        prev=conn.execute('''SELECT final_home_score,final_away_score FROM edgeforce.settlements
          WHERE prediction_id=%s ORDER BY recorded_at DESC,id DESC LIMIT 1''',(prediction_id,)).fetchone()
        if prev:
            if home_score is None:home_score=prev['final_home_score']
            if away_score is None:away_score=prev['final_away_score']
        sid=str(uuid4())
        conn.execute('INSERT INTO edgeforce.settlements VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
          (sid,prediction_id,_utcnow(),outcome,home_score,away_score,source,note))
        return sid


def closing_quote(quote,path=None,max_age_minutes=120):
    start=sqlite_db.parse_utc(quote['commence_time'])
    low=(start-timedelta(minutes=max_age_minutes)).isoformat()
    with connect() as conn:
        r=conn.execute('''SELECT * FROM edgeforce.odds_snapshots
        WHERE event_id=%s AND bookmaker=%s AND market=%s AND selection=%s
          AND point IS NOT DISTINCT FROM %s AND participant=%s
          AND observed_at>=%s AND observed_at<=%s
        ORDER BY observed_at DESC,id DESC LIMIT 1''',
        (quote['event_id'],quote['bookmaker'],quote['market'],quote['selection'],
         quote['point'],quote.get('participant',''),low,start.isoformat())).fetchone()
        if not r:return None
        if r['source_updated_at']:
            t=sqlite_db.parse_utc(r['source_updated_at'])
            if t<start-timedelta(minutes=max_age_minutes) or t>start:return None
        return dict(r)


def prediction_history(path=None):
    return _fetchall('''SELECT p.*,q.event_id,q.sport,q.commence_time,q.home_team,q.away_team,
      q.bookmaker,q.market,q.selection,q.point,q.participant,q.american_odds,q.source,q.observed_at,q.source_updated_at,
      s.outcome,s.recorded_at AS settlement_recorded_at,s.result_source,s.final_home_score,s.final_away_score
      FROM edgeforce.predictions p
      JOIN edgeforce.odds_snapshots q ON q.id=p.snapshot_id
      LEFT JOIN LATERAL (SELECT * FROM edgeforce.settlements x WHERE x.prediction_id=p.id
        ORDER BY recorded_at DESC,id DESC LIMIT 1) s ON TRUE
      ORDER BY p.created_at DESC,p.id DESC''')


def snapshot_counts(path=None):
    with connect() as conn:
        return tuple(conn.execute(f'SELECT COUNT(*) AS n FROM edgeforce.{tbl}').fetchone()['n']
                     for tbl in ('odds_snapshots','predictions','settlements'))


def record_game_score(event_id,sport,home,away,hs,as_,source,final_at=None,path=None):
    with connect() as conn:
        conn.execute('''INSERT INTO edgeforce.game_scores VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (event_id,home_score,away_score,source) DO NOTHING''',
        (str(uuid4()),_utcnow(),sport,event_id,home,away,float(hs),float(as_),source,final_at))


def log_ticket(quote_ids,stake,joint_probability=None,estimated_ev=None,label='Research parlay',version='correlated-score-v0.1',path=None):
    from .models import american_decimal
    if len(quote_ids)<2 or len(set(quote_ids))!=len(quote_ids):
        raise ValueError('At least two different odds snapshots required')
    if not 0<float(stake)<=1_000_000:raise ValueError('Positive stake required')
    with connect() as conn:
        qs=[]
        for sid in quote_ids:
            q=conn.execute('SELECT * FROM edgeforce.odds_snapshots WHERE id=%s',(sid,)).fetchone()
            if not q:raise ValueError('Missing odds snapshot')
            now=sqlite_db.parse_utc(_utcnow())
            if now>=sqlite_db.parse_utc(q['commence_time']) or sqlite_db.parse_utc(q['observed_at'])>=sqlite_db.parse_utc(q['commence_time']):
                raise ValueError('Cannot log parlay after kickoff')
            if now-sqlite_db.parse_utc(q['observed_at'])>timedelta(minutes=30):
                raise ValueError('One or more odds snapshots are stale')
            qs.append(q)
        if len({q['bookmaker'] for q in qs})!=1:
            raise ValueError('Parlay quotes must come from the same sportsbook')
        if len({q['event_id'] for q in qs})!=len(qs):
            raise ValueError('Same-game parlay requires executable sportsbook SGP price')
        decimal=1.
        for q in qs:decimal*=american_decimal(q['american_odds'])
        tid=str(uuid4())
        conn.execute('INSERT INTO edgeforce.parlay_tickets VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
           (tid,_utcnow(),float(stake),joint_probability,estimated_ev,decimal,version,label,
           'research only; no placed wager'))
        for q in qs:
            conn.execute('INSERT INTO edgeforce.parlay_legs VALUES (%s,%s,%s)',(str(uuid4()),tid,q['id']))
        return tid


def ticket_history(path=None):
    rows=_fetchall('''SELECT t.*,s.outcome,s.recorded_at AS settlement_recorded_at
      FROM edgeforce.parlay_tickets t
      LEFT JOIN LATERAL (SELECT * FROM edgeforce.ticket_settlements x
         WHERE x.ticket_id=t.id ORDER BY recorded_at DESC,id DESC LIMIT 1) s ON TRUE
      ORDER BY t.created_at DESC,t.id DESC''')
    with connect() as conn:
        for row in rows:
            row['legs']=[dict(x) for x in conn.execute('''SELECT q.* FROM edgeforce.parlay_legs l
              JOIN edgeforce.odds_snapshots q ON l.snapshot_id=q.id WHERE l.ticket_id=%s''',
              (row['id'],)).fetchall()]
    return rows


def settle_ticket(ticket_id,outcome,source='manual',note='',path=None):
    if outcome not in ('WIN','LOSS','PUSH','VOID'):raise ValueError('Bad outcome')
    with connect() as conn:
        if not conn.execute('SELECT 1 FROM edgeforce.parlay_tickets WHERE id=%s',(ticket_id,)).fetchone():
            raise ValueError('Unknown ticket')
        sid=str(uuid4())
        conn.execute('INSERT INTO edgeforce.ticket_settlements VALUES (%s,%s,%s,%s,%s,%s)',
          (sid,ticket_id,_utcnow(),outcome,source,note))
        return sid


def backup_bytes(path=None):
    """Export all full audit tables. Hosted Postgres backup is a ZIP, NOT SQLite."""
    with io.BytesIO() as raw:
        with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as arch:
            for table in TABLES:
                entries=_fetchall(f'SELECT * FROM edgeforce.{table}')
                buf=io.StringIO()
                w=csv.DictWriter(buf,fieldnames=list(entries[0]) if entries else [],extrasaction='ignore')
                if entries:
                    w.writeheader();w.writerows(entries)
                arch.writestr(f'{table}.csv',buf.getvalue())
            arch.writestr('README.txt','EdgeForce append-only audit evidence export. Original timestamps are UTC ISO 8601 strings.\n')
        return raw.getvalue()
