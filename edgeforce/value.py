"""Independent sportsbook market-consensus EV research (not a validated winning model).

Do NOT mix odds from different points, players, or books' stale market quotes.
Only compute a fair price from independent books offering BOTH sides of the
identical market. Always exclude the target sportsbook from reference pricing.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Iterable

from .models import implied, american_decimal, fair_american, ev_per_dollar

SHARP_GAME = ('pinnacle', 'circa', 'bookmaker')
SHARP_PROPS = ('fanduel', 'pinnacle', 'bookmaker')


def utc(t):
    if isinstance(t, datetime):
        if t.tzinfo is None: raise ValueError('Naive datetime not allowed')
        return t.astimezone(timezone.utc)
    d=datetime.fromisoformat(str(t).replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Naive datetime not allowed')
    return d.astimezone(timezone.utc)


def book_weight(book, market):
    """Heuristic reference weighting, not an assertion that a book is sharp."""
    s=book.casefold()
    priorities=SHARP_PROPS if market.startswith('player_') else SHARP_GAME
    return 1.5 if any(x in s for x in priorities) else 1.0


def _number(x):
    try:
        n=float(x)
        return round(n, 5) if math.isfinite(n) else None
    except (TypeError,ValueError):return None


def _identity(q):
    """Identical market. For spreads, teams have opposite-signed points."""
    market=str(q.get('market',''))
    point=_number(q.get('point'))
    if market=='spreads':
        if point is None: return None
        # Canonical HOME handicap, not its magnitude. A home -3.5 and a home
        # +3.5 are different wagers even though abs(points) is identical.
        side=_side(q)
        if side not in ('home','away'): return None
        line=point if side=='home' else -point
    elif market in ('h2h',):line=None
    elif market=='totals' or market.startswith('player_'):
        if market=='player_anytime_td':return None  # generally one-sided
        if point is None:return None
        line=point
    else:return None
    return str(q.get('event_id','')),market,str(q.get('participant') or '').casefold().strip(),line


def _side(q):
    market=q.get('market')
    name=str(q.get('selection',''))
    if market in ('h2h','spreads'):
        if name==q.get('home_team'):return 'home'
        if name==q.get('away_team'):return 'away'
    elif market=='totals' or str(market).startswith('player_'):
        if name.casefold()=='over':return 'over'
        if name.casefold()=='under':return 'under'
    return None


def _valid_pair(offers,market):
    """Pair both sides from one bookmaker at strictly compatible prices/lines."""
    if len(offers)!=2:return False
    a,b=offers
    # A bookmaker's two opposing sides must belong to the same recent quote
    # window; otherwise we would create a fictitious two-way market.
    try:
        if abs((utc(a['observed_at'])-utc(b['observed_at'])).total_seconds())>120:return False
        if a.get('source_updated_at') and b.get('source_updated_at'):
            if abs((utc(a['source_updated_at'])-utc(b['source_updated_at'])).total_seconds())>120:return False
    except (TypeError,ValueError):return False
    if {_side(a),_side(b)}!=({'home','away'} if market in ('h2h','spreads') else {'over','under'}):return False
    if market=='spreads' and not math.isclose(float(a['point']),-float(b['point']),abs_tol=.00001):return False
    if market in ('totals',) or market.startswith('player_'):
        if _number(a.get('point'))!=_number(b.get('point')):return False
    try:
        for q in offers:
            if int(q['american_odds']) in (0,):return False
            if implied(q['american_odds'])<=0:return False
    except (TypeError,ValueError):return False
    return True


def _fresh_quotes(quotes, now, freshness_min=30, provider_stale_min=75):
    """Latest independent offer by book, event, market, participant and SIDE.

    Multiple old lines in database must not manufacture independent references.
    Source update timestamps are also bounded when supplied by provider.
    """
    latest={}
    for q in quotes:
        try:
            observed=utc(q['observed_at'])
            start=utc(q['commence_time'])
            source=utc(q['source_updated_at']) if q.get('source_updated_at') else None
            if not (observed <= now and now-observed<=timedelta(minutes=freshness_min)):continue
            if source and (source>now+timedelta(minutes=2) or now-source>timedelta(minutes=provider_stale_min)):continue
            if start<=now:continue
            ident=_identity(q);side=_side(q)
            if ident is None or side is None:continue
            k=(ident[0],str(q['bookmaker']).casefold(),ident[1],ident[2],ident[3],side)
            # Only retain most recently observed quoted side/line per market.
            if k not in latest or (observed, str(q.get('id','')))>(utc(latest[k]['observed_at']),str(latest[k].get('id',''))):
                latest[k]=q
        except (ValueError,TypeError,KeyError,OverflowError):continue
    return list(latest.values())


def _weighted_consensus(values):
    # Weighted average; disagreement is measured unweighted and used as a gate.
    weight_total=sum(w for p,w in values)
    return sum(p*w for p,w in values)/weight_total


def scan(quotes: Iterable[dict], now=None, min_references=2, min_ev_pct=1.0,
         max_reference_range_pp=5.0, freshness_min=30):
    """Rank offered bets on independent, non-validated market-consensus EV.

    Independent reference books are devigged separately and the candidate book
    is EXCLUDED. Exactly matching points + players required. Incomplete markets
    and stale quotes receive NO asserted EV. Returned results keep snapshot ID.
    """
    now=utc(now) if now is not None else datetime.now(timezone.utc)
    if min_references<1:raise ValueError('Reference count must be >=1')
    offers=_fresh_quotes(list(quotes),now,freshness_min=freshness_min)
    groups={}
    for q in offers:
        k=_identity(q)
        if k is None:continue
        groups.setdefault(k,{}).setdefault(str(q['bookmaker']).casefold(),[]).append(q)
    result=[]
    for key, books in groups.items():
        pairs={}
        for book, rows in books.items():
            if _valid_pair(rows,key[1]):
                sides={_side(q):q for q in rows}
                vig=sum(implied(q['american_odds']) for q in rows)-1
                if -0.001 <= vig <= .25: # exclude broken, aberrant markets
                    pairs[book]=(sides,vig)
        for candidate_book, (sides, vig) in pairs.items():
            for side,offer in sides.items():
                references=[]
                for ref_book,(ref_sides,ref_vig) in pairs.items():
                    if ref_book==candidate_book:continue
                    p_raw=implied(ref_sides[side]['american_odds'])
                    denom=sum(implied(r['american_odds']) for r in ref_sides.values())
                    p=p_raw/denom
                    references.append((p,book_weight(ref_sides[side]['bookmaker'],key[1]),
                                       ref_sides[side]['bookmaker']))
                if len(references)<min_references:continue
                probabilities=[x[0] for x in references]
                spread_pp=(max(probabilities)-min(probabilities))*100
                if spread_pp>max_reference_range_pp:continue
                consensus=_weighted_consensus([(p,w) for p,w,_ in references])
                ev=100*ev_per_dollar(consensus,offer['american_odds'])
                if ev<min_ev_pct:continue
                # Quarter Kelly is an upper bound on simulated stake fraction.
                b=american_decimal(offer['american_odds'])-1
                kelly=max(0.,(b*consensus-(1-consensus))/b) if b>0 else 0.
                result.append({
                    'quote':offer,'snapshot_id':offer.get('id'),
                    'fair_probability':consensus,'fair_american':fair_american(consensus),
                    'offered_odds':int(offer['american_odds']), 'ev_pct':ev,
                    'edge_pp':(consensus-implied(offer['american_odds']))*100,
                    'kelly_quarter_pct':min(kelly*.25, .025)*100,
                    'reference_books':[bname for _,_,bname in references],
                    'reference_count':len(references),'variation_pp':spread_pp,
                    'market_vig_pct':vig*100, 'method':'Independent cross-book multiplicative no-vig consensus v0.4',
                    'strength':'RESEARCH — MARKET PROXY',
                    'quality':'B' if len(references)>=3 and spread_pp<=2 else 'C',
                })
    result.sort(key=lambda row:(-row['ev_pct'],-row['reference_count'],row['variation_pp']))
    return result


def describe(row):
    q=row['quote']
    label=(str(q.get('participant'))+' — ') if q.get('participant') else ''
    side=str(q['selection'])
    if q['market'] in ('spreads','totals') or q['market'].startswith('player_'):
        point=q.get('point')
        side+=' '+(f'{float(point):+g}' if q['market']=='spreads' else f'{float(point):g}')
    return f"{label}{q['market'].replace('_',' ').title()}: {side}"

PLAYER_STAT_KEYS={
    'player_pass_yds':'passing_yards',
    'player_rush_yds':'rushing_yards',
    'player_reception_yds':'receiving_yards',
    'player_receptions':'receptions',
    'player_pass_tds':'passing_tds',
    'player_rush_tds':'rushing_tds',
    'player_reception_tds':'receiving_tds',
}


def historical_hit_rates(offer, history):
    """Descriptive L5/10/20 hit rates. NEVER treat frequencies as forecast p.

    history: pre-event game logs for one player, ordered oldest to newest.
    """
    market=offer.get('market')
    stat_key=PLAYER_STAT_KEYS.get(market)
    if stat_key is None or offer.get('point') is None:
        return {}
    side=str(offer.get('selection','')).casefold()
    if side not in ('over','under'):return {}
    line=_number(offer['point'])
    if line is None:return {}
    values=[]
    for game in history:
        try:
            v=float(game[stat_key])
            if math.isfinite(v):values.append(v)
        except (KeyError,TypeError,ValueError):continue
    def rate(n):
        recent=values[-n:]
        if not recent:return None
        count=sum(v>line if side=='over' else v<line for v in recent)
        return {'hits':count,'games':len(recent),'hit_rate':count/len(recent)}
    return {n:rate(n) for n in (5,10,20)}
