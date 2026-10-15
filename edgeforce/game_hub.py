"""Matchup-first UI support, pure/testable and strictly evidence-limited.

This module never calls a sportsbook, writes to the database, or claims a
market-consensus proxy is a validated edge. Schedule and sportsbook event IDs
are different; join by normalized teams AND nearby verified kickoff only.
"""
from __future__ import annotations

from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import models, nfl_schedule, opportunities, value

ET = ZoneInfo('America/New_York')


def utc(when):
    if isinstance(when, datetime):
        if when.tzinfo is None:
            raise ValueError('Naive timestamp')
        return when.astimezone(timezone.utc)
    return value.utc(when)


def team_code(team, sport):
    if sport == 'NFL':
        return nfl_schedule.normalize_team(models.team_key(team, 'NFL'))
    return models.team_key(team, 'CFB')


def nfl_season_for_date(moment):
    local=utc(moment).astimezone(ET)
    return local.year-1 if local.month<=2 else local.year


def identity(sport, away, home, kickoff):
    """Human-stable identity; don't pretend an NFLverse ID is a sportsbook ID."""
    d = utc(kickoff).astimezone(ET).strftime('%Y-%m-%d')
    return f'{sport}:{team_code(away,sport)}:{team_code(home,sport)}:{d}'


def _game(sport, away, home, kickoff, week=None, verified=True, source='Odds provider', season=None):
    kickoff = utc(kickoff)
    return {'key': identity(sport,away,home,kickoff), 'sport':sport,
            'away':str(away), 'home':str(home), 'away_code':team_code(away,sport),
            'home_code':team_code(home,sport), 'kickoff':kickoff,
            'kickoff_et':kickoff.astimezone(ET).strftime('%a %b %d, %I:%M %p ET'),
            'week':week, 'season':season if season is not None else (nfl_season_for_date(kickoff) if sport=='NFL' else kickoff.astimezone(ET).year), 'kickoff_verified':bool(verified), 'source':source,
            'event_id':None, 'price_count':0, 'book_count':0}


def game_catalog(schedule, quotes, now=None, days=14, sports=('NFL','CFB')):
    """Browse upcoming games even if odds are not available.

    Odds merge with schedule ONLY when both teams match and kickoffs are within
    24 hours; otherwise show a separate feed fixture, not a silently wrong join.
    No future scores, expired games, nor synthetic demo quotes.
    """
    now = utc(now) if now is not None else datetime.now(timezone.utc)
    deadline = now + timedelta(days=days)
    games=[]
    if 'NFL' in sports and schedule is not None and not getattr(schedule, 'empty', True):
        required={'home_team','away_team','kickoff_utc','status','game_type','week'}
        if required.issubset(schedule.columns):
            for row in schedule.to_dict('records'):
                if str(row['game_type']).upper() != 'REG' or str(row['status']) != 'Scheduled':
                    continue
                try:
                    kickoff=utc(row['kickoff_utc'])
                    if not now < kickoff <= deadline:continue
                    week=int(row['week'])
                except (ValueError, TypeError, KeyError, OverflowError):continue
                games.append(_game('NFL',row['away_team'],row['home_team'],kickoff,
                                   week, row.get('kickoff_verified',True), 'NFLverse', row.get('season')))
    books=defaultdict(set)
    quote_counts=Counter()
    candidates={}
    for q in quotes or []:
        try:
            sport=str(q['sport'])
            if sport not in sports or q.get('source')=='SYNTHETIC DEMO':continue
            kickoff=utc(q['commence_time'])
            if not now<kickoff<=deadline:continue
            eid=str(q['event_id'])
            away,home=str(q['away_team']),str(q['home_team'])
            if not eid or not away or not home:continue
            key=(sport,eid)
            candidates[key]=(away,home,kickoff)
            books[key].add(str(q['bookmaker']))
            quote_counts[key]+=1
        except (KeyError,TypeError,ValueError,OverflowError):continue
    for (sport,eid),(away,home,kickoff) in candidates.items():
        away_key=team_code(away,sport)
        home_key=team_code(home,sport)
        matches=[g for g in games if g['sport']==sport and g['event_id'] is None
                 and g['away_code']==away_key and g['home_code']==home_key
                 and abs((g['kickoff']-kickoff).total_seconds())<=24*3600]
        if matches:
            # If dates differ too much, err on the side of not merging.
            g=min(matches,key=lambda row:abs((row['kickoff']-kickoff).total_seconds()))
        else:
            g=_game(sport,away,home,kickoff,source='Odds provider')
            games.append(g)
        g['event_id']=eid
        g['book_count']=len(books[(sport,eid)])
        g['price_count']=quote_counts[(sport,eid)]
    # Keep a single entry for each distinct real fixture, not duplicate source rows.
    unique={}
    for g in games:
        k=g['key']
        if k not in unique or (g['event_id'] and not unique[k]['event_id']):unique[k]=g
    return sorted(unique.values(),key=lambda x:(x['kickoff'],x['sport'],x['away_code']))


def game_quotes(game, quotes):
    """No cross-matchup join on names alone; prices use the exact provider ID."""
    eid=game.get('event_id')
    if not eid:return []
    return [q for q in quotes or [] if q.get('event_id')==eid
            and q.get('sport')==game['sport'] and q.get('source')!='SYNTHETIC DEMO']


def qualifying_game_bets(game, quotes, now=None, min_ev_pct=1., min_references=2):
    """Deduplicate by actual bet and preserve the best documented bookmaker."""
    now=utc(now) if now is not None else datetime.now(timezone.utc)
    eligible=value.scan(opportunities.latest_active_batch(game_quotes(game,quotes)),
                        now=now,min_references=min_references,min_ev_pct=min_ev_pct)
    best={}
    for row in eligible:
        q=row['quote']
        k=(q['market'],q.get('participant',''),q['selection'],q.get('point'))
        if k not in best or (row['ev_pct'],row['reference_count']) > (best[k]['ev_pct'],best[k]['reference_count']):
            best[k]=row
    return sorted(best.values(),key=lambda x:(-x['ev_pct'],-x['reference_count'],x['variation_pp']))


def raw_game_props(game, quotes, now=None, freshness_minutes=30):
    """Display raw event props, even if no EV-qualified wager exists."""
    now=utc(now) if now is not None else datetime.now(timezone.utc)
    candidates=[]
    for q in game_quotes(game,quotes):
        try:
            if not str(q.get('market','')).startswith('player_'):continue
            seen=utc(q['observed_at'])
            if not seen<=now or now-seen>timedelta(minutes=freshness_minutes):continue
            if utc(q['commence_time'])<=now:continue
            candidates.append(q)
        except (KeyError,ValueError,TypeError):continue
    return opportunities.latest_active_batch(candidates)


def game_health(game, quotes, now=None):
    now=utc(now) if now is not None else datetime.now(timezone.utc)
    rows=game_quotes(game,quotes)
    current=[]
    for q in rows:
        try:
            age=(now-utc(q['observed_at'])).total_seconds()/60
            source=q.get('source_updated_at')
            if source and (now-utc(source)).total_seconds()/60>75:continue
            if 0<=age<=30 and utc(q['commence_time'])>now:current.append(q)
        except (KeyError,ValueError,TypeError):continue
    books=len({q['bookmaker'] for q in current})
    return {'status': 'MISSING' if not rows else 'STALE' if not current else 'LIMITED' if books<3 else 'FRESH',
            'books':books,'fresh_quotes':len(current),'raw_quotes':len(rows),
            'has_prop_data':any(q.get('market','').startswith('player_') for q in current)}


def explain_offer(row, now=None):
    """Plain-language explanation with source and price sensitivity, never hype."""
    now=utc(now) if now is not None else datetime.now(timezone.utc)
    q=row['quote']
    price=int(row['offered_odds'])
    probability=float(row['fair_probability'])
    implied=models.implied(price)
    odds=models.american_decimal(price)
    stress=max(0.,probability-0.02)
    age=(now-utc(q['observed_at'])).total_seconds()/60
    source_age=None
    if q.get('source_updated_at'):
        source_age=(now-utc(q['source_updated_at'])).total_seconds()/60
    fresh=0<=age<=30 and (source_age is None or -2<=source_age<=75) and utc(q['commence_time'])>now
    quality='Stronger reference coverage' if row['reference_count']>=3 and row['variation_pp']<=2 else 'Limited reference agreement'
    notes=[
        'The fair probability is inferred from other sportsbooks after removing their built-in margin; it is not an independently calibrated game forecast.',
        'This bet loses its estimated edge if the offered price worsens, other books move, or the supporting quotes become stale.',
    ]
    if q.get('market','').startswith('player_'):
        notes.append('Verify the player is active and their role is unchanged. Injury and starting status are not automatically certified.')
    else:
        notes.append('Weather, injuries, and matchup scheme changes are not independently included in this market-derived fair-price calculation.')
    if row['reference_count']<3:notes.append('Fewer than three reference books increases estimation uncertainty.')
    if not fresh:notes.append('This quote is no longer current. Refresh before using it.')
    return {'offered':f'{price:+d}','fair':f"{int(row['fair_american']):+d}",
            'implied_pct':round(100*implied,1),'fair_pct':round(100*probability,1),
            'edge_pp':round(100*(probability-implied),2),'ev_pct':round(float(row['ev_pct']),2),
            'stress_ev_pct':round(100*(stress*odds-1),2),
            'references':list(row['reference_books']),'reference_count':int(row['reference_count']),
            'variation_pp':float(row['variation_pp']), 'quote_age_minutes':round(age,1),
            'source_age_minutes':None if source_age is None else round(source_age,1),
            'fresh':fresh,'quality':quality,'warnings':notes,
            'source':'Independent cross-book, two-way no-vig consensus (not a verified profit edge)'}


def tickets_containing_game(bundle, game):
    """Match tickets to exact sportsbook event ID, not arbitrary shared teams."""
    eid=game.get('event_id')
    if not eid or not bundle:return []
    rows=[]
    for label in ('three','five'):
        data=bundle.get(label) or {}
        for index,ticket in enumerate(data.get('tickets',[]),1):
            related=[leg for leg in ticket.get('legs',[])
                     if leg.get('quote',{}).get('event_id')==eid]
            if related:rows.append({'type':label,'index':index,'ticket':ticket,'legs':related})
    return rows
