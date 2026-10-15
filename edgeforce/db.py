"""SQLite append-only market evidence, forecast, and settlement ledger."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def parse_utc(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def db_path():
    return os.getenv('EDGEFORCE_DB', str(Path(__file__).resolve().parent.parent / 'edgeforce.sqlite3'))


@contextmanager
def connect(path=None):
    db = sqlite3.connect(path or db_path(), timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS odds_snapshots (
 id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, source_updated_at TEXT,
 event_id TEXT NOT NULL, sport TEXT NOT NULL, commence_time TEXT NOT NULL,
 home_team TEXT NOT NULL, away_team TEXT NOT NULL, bookmaker TEXT NOT NULL,
 market TEXT NOT NULL, selection TEXT NOT NULL, point REAL, participant TEXT NOT NULL DEFAULT '',
 american_odds INTEGER NOT NULL, source TEXT NOT NULL, raw_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_odds_event ON odds_snapshots(event_id,observed_at);
CREATE INDEX IF NOT EXISTS idx_odds_close ON odds_snapshots(event_id,bookmaker,market,selection,point,observed_at);
CREATE TABLE IF NOT EXISTS predictions (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, snapshot_id TEXT NOT NULL,
 model_probability REAL, confidence_grade TEXT NOT NULL, model_version TEXT NOT NULL,
 rationale TEXT NOT NULL, stake REAL NOT NULL, tags TEXT NOT NULL,
 FOREIGN KEY(snapshot_id) REFERENCES odds_snapshots(id)
);
CREATE TABLE IF NOT EXISTS settlements (
 id TEXT PRIMARY KEY, prediction_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN ('WIN','LOSS','PUSH','VOID')),
 final_home_score REAL, final_away_score REAL, result_source TEXT NOT NULL,
 note TEXT NOT NULL, FOREIGN KEY(prediction_id) REFERENCES predictions(id)
);
CREATE INDEX IF NOT EXISTS idx_result_prediction ON settlements(prediction_id, recorded_at);
CREATE TABLE IF NOT EXISTS parlay_tickets (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, stake REAL NOT NULL,
 estimated_probability REAL, estimated_ev REAL, combined_decimal REAL NOT NULL,
 simulation_version TEXT NOT NULL, label TEXT NOT NULL, source_note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parlay_legs (
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, snapshot_id TEXT NOT NULL,
 FOREIGN KEY(ticket_id) REFERENCES parlay_tickets(id),
 FOREIGN KEY(snapshot_id) REFERENCES odds_snapshots(id)
);
CREATE TABLE IF NOT EXISTS ticket_settlements (
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN ('WIN','LOSS','PUSH','VOID')),
 source TEXT NOT NULL, note TEXT NOT NULL,
 FOREIGN KEY(ticket_id) REFERENCES parlay_tickets(id)
);
CREATE TABLE IF NOT EXISTS game_scores (
 id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, sport TEXT NOT NULL,
 event_id TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
 home_score REAL NOT NULL, away_score REAL NOT NULL, source TEXT NOT NULL,
 final_at TEXT, UNIQUE(event_id,home_score,away_score,source)
);
'''
IMMUTABLE = ('odds_snapshots','predictions','settlements','game_scores','parlay_tickets','parlay_legs','ticket_settlements')


def init_db(path=None):
    with connect(path) as db:
        db.executescript(SCHEMA)
        if 'participant' not in [c[1] for c in db.execute('PRAGMA table_info(odds_snapshots)')]:
            db.execute("ALTER TABLE odds_snapshots ADD COLUMN participant TEXT NOT NULL DEFAULT ''")
        for table in IMMUTABLE:
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS no_update_{table}
                BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'append-only audit table'); END''')
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS no_delete_{table}
                BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'append-only audit table'); END''')


def insert_snapshots(quotes, path=None):
    """Never mutate market evidence. quoted source timestamp and observation time are separate."""
    ids=[]
    with connect(path) as db:
        for q in quotes:
            row = {
                'id':str(uuid4()), 'observed_at':q.get('observed_at') or utcnow(),
                'source_updated_at':q.get('source_updated_at'),
                'event_id':str(q['event_id']), 'sport':q['sport'],
                'commence_time':q['commence_time'], 'home_team':q['home_team'],
                'away_team':q['away_team'], 'bookmaker':q['bookmaker'],
                'market':q['market'], 'selection':q['selection'],
                'point':q.get('point'),'participant':q.get('participant',''), 'american_odds':int(q['american_odds']),
                'source':q['source'], 'raw_json':json.dumps(q.get('raw',{}),default=str)
            }
            if row['american_odds']==0:
                continue
            db.execute('INSERT INTO odds_snapshots VALUES ('+','.join('?' for _ in row)+')',list(row.values()))
            ids.append(row['id'])
    return ids


def latest_quotes(sport=None, path=None):
    """Return the most recently OBSERVED price per sportsbook/market/line."""
    query='''SELECT s.* FROM odds_snapshots s WHERE s.rowid = (
      SELECT MAX(t.rowid) FROM odds_snapshots t WHERE
      t.event_id=s.event_id AND t.bookmaker=s.bookmaker AND t.market=s.market
      AND t.selection=s.selection AND t.point IS s.point
      AND t.participant=s.participant)'''
    params=[]
    if sport:
        query+=' AND s.sport=?'; params.append(sport)
    query+=' ORDER BY s.commence_time,s.home_team,s.market,s.bookmaker'
    with connect(path) as db:
        return [dict(r) for r in db.execute(query,params).fetchall()]


def snapshots_for_event(event_id,path=None):
    with connect(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM odds_snapshots WHERE event_id=? ORDER BY observed_at', (event_id,))]


def log_prediction(snapshot_id, probability, grade='C', version='experimental-v0.1', rationale='', stake=10., tags='', path=None):
    """Capture the price first; the prediction points to exactly that immutable quote."""
    if probability is not None and not 0 < float(probability) < 1:
        raise ValueError('Probability must be in (0,1)')
    if not 0 < float(stake) <= 1_000_000:
        raise ValueError('Stake must be positive')
    with connect(path) as db:
        quote=db.execute('SELECT * FROM odds_snapshots WHERE id=?',(snapshot_id,)).fetchone()
        if quote is None:
            raise ValueError('No quoted offer; refresh the feed first')
        observed=parse_utc(quote['observed_at']); start=parse_utc(quote['commence_time'])
        if observed >= start:
            raise ValueError('Cannot claim a pregame prediction using an odds snapshot observed after kickoff')
        if parse_utc(utcnow())-observed > timedelta(minutes=30):
            raise ValueError('Provider snapshot is over 30 minutes old: refresh odds before logging')
        if parse_utc(utcnow()) >= start:
            raise ValueError('Event has already started; do not backdate forecasts')
        created=utcnow()
        row=(str(uuid4()),created,snapshot_id,float(probability) if probability is not None else None,
             grade,version,rationale,float(stake),tags)
        db.execute('INSERT INTO predictions VALUES(?,?,?,?,?,?,?,?,?)',row)
        return row[0]


def settle(prediction_id,outcome,source='manual',home_score=None,away_score=None,note='',path=None):
    if outcome not in ('WIN','LOSS','PUSH','VOID'):
        raise ValueError('Unsupported settlement')
    with connect(path) as db:
        if not db.execute('SELECT 1 FROM predictions WHERE id=?',(prediction_id,)).fetchone():
            raise ValueError('Unknown prediction')
        previous=db.execute('''SELECT final_home_score,final_away_score FROM settlements
                   WHERE prediction_id=? ORDER BY rowid DESC LIMIT 1''',(prediction_id,)).fetchone()
        if previous is not None:
            if home_score is None:home_score=previous['final_home_score']
            if away_score is None:away_score=previous['final_away_score']
        row=(str(uuid4()),utcnow(),prediction_id,outcome,home_score,away_score,source,note)
        db.execute('''INSERT INTO settlements (id,recorded_at,prediction_id,outcome,
                   final_home_score,final_away_score,result_source,note) VALUES(?,?,?,?,?,?,?,?)''',row)
        return row[0]


def closing_quote(quote, path=None, max_age_minutes=120):
    """Closing = last snap from SAME book AND exact selection/line before kickoff, within freshness cutoff."""
    start=parse_utc(quote['commence_time'])
    low=(start-timedelta(minutes=max_age_minutes)).isoformat()
    with connect(path) as db:
        sql='''SELECT * FROM odds_snapshots WHERE event_id=? AND bookmaker=? AND market=?
          AND selection=? AND point IS ? AND participant=? AND observed_at>=? AND observed_at<=?
          ORDER BY observed_at DESC,rowid DESC LIMIT 1'''
        r=db.execute(sql,(quote['event_id'],quote['bookmaker'],quote['market'],
                          quote['selection'],quote['point'],quote.get('participant',''),low,start.isoformat())).fetchone()
        if not r: return None
        if r['source_updated_at']:
            provider_time=parse_utc(r['source_updated_at'])
            if provider_time < start-timedelta(minutes=max_age_minutes) or provider_time>start:
                return None
        return dict(r)


def prediction_history(path=None):
    with connect(path) as db:
        query='''SELECT p.*, q.event_id,q.sport,q.commence_time,q.home_team,q.away_team,
         q.bookmaker,q.market,q.selection,q.point,q.participant,q.american_odds,q.source,q.observed_at,q.source_updated_at,
         r.outcome,r.recorded_at AS settlement_recorded_at,r.result_source,
         r.final_home_score,r.final_away_score
         FROM predictions p JOIN odds_snapshots q ON q.id=p.snapshot_id
         LEFT JOIN settlements r ON r.rowid=(SELECT MAX(r2.rowid) FROM settlements r2 WHERE r2.prediction_id=p.id)
         ORDER BY p.created_at DESC,p.rowid DESC'''
        return [dict(x) for x in db.execute(query)]


def snapshot_counts(path=None):
    with connect(path) as db:
        a=db.execute('SELECT COUNT(*) FROM odds_snapshots').fetchone()[0]
        b=db.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]
        c=db.execute('SELECT COUNT(*) FROM settlements').fetchone()[0]
    return a,b,c


def record_game_score(event_id,sport,home,away,hs,as_,source,final_at=None,path=None):
    with connect(path) as db:
        db.execute('''INSERT OR IGNORE INTO game_scores VALUES(?,?,?,?,?,?,?,?,?,?)''',
                   (str(uuid4()),utcnow(),sport,event_id,home,away,float(hs),float(as_),source,final_at))

def log_ticket(quote_ids, stake, joint_probability=None, estimated_ev=None,
               label='Research parlay',version='correlated-score-v0.1',path=None):
    """Lock each leg to its offered price, as observed before its event begins."""
    if len(quote_ids)<2 or len(set(quote_ids))!=len(quote_ids):
        raise ValueError('At least two different odds snapshots required')
    if not 0<float(stake)<=1_000_000:raise ValueError('Positive stake required')
    from .models import american_decimal
    with connect(path) as conn:
        qs=[]
        for sid in quote_ids:
            q=conn.execute('SELECT * FROM odds_snapshots WHERE id=?',(sid,)).fetchone()
            if not q:raise ValueError('Odds snapshot missing')
            if parse_utc(utcnow())>=parse_utc(q['commence_time']) or parse_utc(q['observed_at'])>=parse_utc(q['commence_time']):
                raise ValueError('Started-event odds cannot be used in a pregame parlay')
            if parse_utc(utcnow())-parse_utc(q['observed_at'])>timedelta(minutes=30):
                raise ValueError('A quoted leg is more than 30 minutes old: refresh odds')
            qs.append(q)
        if len({q['bookmaker'] for q in qs})!=1:
            raise ValueError('Multi-book odds cannot form an executable single-sportsbook parlay')
        if len({q['event_id'] for q in qs})!=len(qs):
            raise ValueError('Same-game parlay payout requires a quoted SGP offer from the sportsbook')
        dec=1.
        for q in qs:dec*=american_decimal(q['american_odds'])
        ticket=str(uuid4())
        conn.execute('INSERT INTO parlay_tickets VALUES (?,?,?,?,?,?,?,?,?)',
           (ticket,utcnow(),float(stake),joint_probability,estimated_ev,dec,version,label,'research only; no placed wager'))
        for q in qs:
            conn.execute('INSERT INTO parlay_legs VALUES (?,?,?)',(str(uuid4()),ticket,q['id']))
        return ticket


def ticket_history(path=None):
    with connect(path) as conn:
        rows=[dict(r) for r in conn.execute('''SELECT t.*,
          s.outcome,s.recorded_at AS settlement_recorded_at
          FROM parlay_tickets t
          LEFT JOIN ticket_settlements s ON s.rowid=(SELECT MAX(s2.rowid) FROM ticket_settlements s2 WHERE s2.ticket_id=t.id)
          ORDER BY t.created_at DESC''')]
        for row in rows:
            row['legs']=[dict(x) for x in conn.execute('''SELECT q.* FROM parlay_legs l
               JOIN odds_snapshots q ON l.snapshot_id=q.id WHERE l.ticket_id=?''',(row['id'],))]
        return rows


def settle_ticket(ticket_id,outcome,source='manual',note='',path=None):
    if outcome not in ('WIN','LOSS','PUSH','VOID'):raise ValueError('Bad outcome')
    with connect(path) as conn:
        if not conn.execute('SELECT 1 FROM parlay_tickets WHERE id=?',(ticket_id,)).fetchone():
            raise ValueError('Unknown ticket')
        sid=str(uuid4())
        conn.execute('INSERT INTO ticket_settlements VALUES(?,?,?,?,?,?)',
                     (sid,ticket_id,utcnow(),outcome,source,note))
        return sid


def backup_bytes(path=None):
    """Consistent SQLite backup even with write-ahead logging enabled."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        dest=Path(directory)/'edgeforce-backup.sqlite3'
        with connect(path) as src:
            target=sqlite3.connect(dest)
            try:src.backup(target)
            finally:target.close()
        return dest.read_bytes()


def backend_name():
    return 'SQLite (local/ephemeral)'


# The hosted app sets EDGEFORCE_POSTGRES_URL before importing this module.
# All public ledger operations dispatch to Postgres in the cloud.
if os.getenv('EDGEFORCE_POSTGRES_URL'):
    from . import cloud_db as _cloud
    for _func in ('init_db', 'connect', 'insert_snapshots', 'latest_quotes',
                  'snapshots_for_event', 'log_prediction', 'settle', 'closing_quote',
                  'prediction_history', 'snapshot_counts', 'record_game_score',
                  'log_ticket', 'ticket_history', 'settle_ticket', 'backup_bytes'):
        globals()[_func] = getattr(_cloud, _func)
    backend_name = lambda: 'PostgreSQL (durable hosted storage)'
