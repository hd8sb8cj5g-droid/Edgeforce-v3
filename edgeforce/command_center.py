"""Evidence-first home screen helpers, intentionally separate from Streamlit.

No scheduler, network requests, quote mutation, or synthetic recommendations.
All times use aware UTC internally; NFL schedule displays ET.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from . import value, opportunities

EASTERN=ZoneInfo('America/New_York')


def as_utc(moment=None):
    if moment is None:
        return datetime.now(timezone.utc)
    result=pd.Timestamp(moment)
    if pd.isna(result):raise ValueError('Invalid timestamp')
    return result.tz_localize('UTC').to_pydatetime() if result.tzinfo is None else result.tz_convert('UTC').to_pydatetime()


def sportsbook_health(quotes, now=None, freshness_minutes=30, max_source_minutes=75):
    """Status reflects newest *eligible, future-event* authentic sportsbook quote.

    Never declare a feed fresh merely because an old line is in the database,
    a kickoff has passed, or a synthetic record was created recently.
    """
    now=as_utc(now)
    valid=[]
    for q in quotes or []:
        if q.get('source')=='SYNTHETIC DEMO':continue
        try:
            observed=as_utc(q['observed_at'])
            kickoff=as_utc(q['commence_time'])
            if not (observed<=now<kickoff):continue
            age=(now-observed).total_seconds()/60
            src=q.get('source_updated_at')
            if src:
                age_source=(now-as_utc(src)).total_seconds()/60
                if age_source < -2 or age_source>max_source_minutes:continue
            valid.append((q,age))
        except (KeyError,TypeError,ValueError,OverflowError):continue
    if not valid:
        return {'status':'MISSING','fresh':False,'latest':None,'age_minutes':None,
                'games':0,'books':0,'quote_count':0,'detail':'No eligible upcoming-game sportsbook prices. Sync NFL odds.'}
    latest_age=min(age for _,age in valid)
    fresh=[q for q,age in valid if 0<=age<=freshness_minutes]
    status=('LIMITED' if len({q['bookmaker'] for q in fresh})<3 else 'FRESH') if fresh else 'STALE'
    source=fresh if fresh else [q for q,_ in valid]
    newest=max(as_utc(q['observed_at']) for q in source)
    return {'status':status,'fresh':bool(fresh),'latest':newest,'age_minutes':latest_age,
            'games':len({q['event_id'] for q in source}),
            'books':len({q['bookmaker'] for q in source}),
            'quote_count':len(source),'detail':
            (f'{len(fresh)} fresh quotes across {len({q["event_id"] for q in fresh})} upcoming games and {len({q["bookmaker"] for q in fresh})} books. '+('More books are needed for independent 2-book EV comparisons.' if status=='LIMITED' else '') if fresh
             else f'Newest valid quote was {latest_age:.0f} minutes ago. Refresh before EV research.')}


def nfl_games_next_week(schedule, now=None, days=7, limit=20):
    """True upcoming NFL regular season; never include started/completed fixtures."""
    now=as_utc(now)
    if schedule is None or getattr(schedule,'empty',True):return []
    required={'kickoff_utc','away_team','home_team','status','week','game_type'}
    if not required.issubset(schedule.columns):return []
    selected=[]
    for row in schedule.to_dict('records'):
        try:
            kickoff=as_utc(row['kickoff_utc'])
            if kickoff<=now or kickoff>now+timedelta(days=days):continue
            if str(row['game_type']).upper()!='REG':continue
            if str(row['status'])!='Scheduled':continue
            local=kickoff.astimezone(EASTERN)
            selected.append({'away':str(row['away_team']),'home':str(row['home_team']),
                'matchup':f"{row['away_team']} @ {row['home_team']}",
                'week':int(row['week']),'kickoff_utc':kickoff,
                'kickoff_et':local.strftime('%a %b %d, %I:%M %p ET'),
                'kickoff_verified':bool(row.get('kickoff_verified',True))})
        except (KeyError,TypeError,ValueError,OverflowError):continue
    return sorted(selected,key=lambda r:(r['kickoff_utc'],r['away']))[:limit]


def rank_research_opportunities(quotes, now=None, limit=3, min_references=2,
                                min_ev_pct=1.0, max_disagreement=5.0):
    """Rank non-duplicate upcoming NFL opportunities with independent fair prices.

    Return no recommendation if there is no eligible evidence. Diversify by
    event so the landing screen does not show three versions of the same game.
    """
    now=as_utc(now)
    nfl=[q for q in quotes or [] if q.get('sport')=='NFL' and q.get('source')!='SYNTHETIC DEMO']
    eligible=value.scan(opportunities.latest_active_batch(nfl),now=now,
                        min_references=min_references,min_ev_pct=min_ev_pct,
                        max_reference_range_pp=max_disagreement)
    used_events=set();result=[]
    for item in sorted(eligible,key=lambda r:(-float(r['ev_pct']),
                          -int(r['reference_count']),float(r['variation_pp']))):
        game=item['quote']['event_id']
        if game in used_events:continue
        used_events.add(game)
        result.append(item)
        if len(result)>=limit:break
    return result


def schedule_health(schedule, fetched_at, now=None):
    now=as_utc(now)
    if schedule is None or getattr(schedule,'empty',True):
        return {'status':'MISSING','detail':'NFL schedule not loaded yet.'}
    if not fetched_at:
        return {'status':'UNKNOWN','detail':'Schedule present without a verified retrieval timestamp.'}
    try:age=(now-as_utc(fetched_at)).total_seconds()/3600
    except (TypeError,ValueError):return {'status':'UNKNOWN','detail':'Schedule retrieval time is invalid.'}
    if age<0:return {'status':'UNKNOWN','detail':'Schedule retrieval time is ahead of the current clock.'}
    return {'status':'FRESH' if age<=6 else 'STALE',
            'detail':f'NFLverse schedule retrieved {age:.1f} hours ago.'}
