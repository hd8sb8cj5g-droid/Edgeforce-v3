"""Evidence-first sportsbook EV research and no-SGP 3- and 5-leg tickets.

This module does not manufacture forecasts. Positive market-consensus EV is a
hypothesis, not a proven betting edge. No cross-book mixing in a ticket.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from math import prod

from . import value
from .models import american_decimal


def latest_active_batch(quotes, seconds=6):
    """Discard old market lines after a sportsbook reposts a different line.

    Preserve alternative lines within the same ingestion batch, but prevent an
    old -3.5 from masquerading as available after the sportsbook moves to -4.
    Bookmaker+market+participant is the market-level group here.
    """
    market_latest={}
    for q in quotes:
        try:
            k=(q['event_id'],q['bookmaker'].casefold(),q['market'],
               str(q.get('participant') or '').casefold())
            timestamp=value.utc(q['observed_at'])
            if k not in market_latest or timestamp>market_latest[k]:
                market_latest[k]=timestamp
        except (ValueError,KeyError,TypeError):continue
    current=[]
    for q in quotes:
        try:
            k=(q['event_id'],q['bookmaker'].casefold(),q['market'],
               str(q.get('participant') or '').casefold())
            age=(market_latest[k]-value.utc(q['observed_at'])).total_seconds()
            if 0<=age<=seconds:current.append(q)
        except (ValueError,KeyError,TypeError):pass
    return current


def group_game_opportunities(offers, now=None, min_ev=1., min_books=2, max_var=5.):
    """Includes zero-edge games so missing data cannot look like a recommendation."""
    now=now or datetime.now(timezone.utc)
    recent=latest_active_batch(list(offers))
    games={}
    for q in recent:
        if q.get('sport')!='NFL':continue
        try:
            if value.utc(q['commence_time'])<=now:continue
        except (ValueError,KeyError):continue
        games[q['event_id']]={'event_id':q['event_id'],'home':q['home_team'],
            'away':q['away_team'],'kickoff':q['commence_time'],
            'prices':0,'books':set(),'markets':set(),'bets':[]}
    for q in recent:
        if q.get('event_id') not in games:continue
        g=games[q['event_id']]
        g['prices']+=1;g['books'].add(q['bookmaker']);g['markets'].add(q['market'])
    eligible=value.scan(recent,now=now,min_references=min_books,
        min_ev_pct=min_ev,max_reference_range_pp=max_var)
    for row in eligible:
        if row['quote']['event_id'] in games:
            games[row['quote']['event_id']]['bets'].append(row)
    result=[]
    for g in sorted(games.values(),key=lambda x:(x['kickoff'],x['away'])):
        # Deduplicate the same offered side/point across sportsbooks. Only
        # display the most valuable actual quote for each distinct bet.
        by_bet={}
        for r in g['bets']:
            q=r['quote'];key=(q['market'],q['selection'],q.get('participant',''),q.get('point'))
            if key not in by_bet or r['ev_pct']>by_bet[key]['ev_pct']:
                by_bet[key]=r
        g['top']=sorted(by_bet.values(),key=lambda r:(-r['ev_pct'],-r['reference_count']))
        g['books']=len(g['books']);g['markets']=sorted(g['markets'])
        result.append(g)
    return result


def _conservative_probability(offer):
    """Sensitivity scenario, NOT calibrated error bounds / actual forecast."""
    p=float(offer['fair_probability'])
    # Research haircut: 1.5 pp base plus half disagreement, capped at 5 pp.
    penalty=min(.05,.015 + float(offer['variation_pp'])/200)
    return max(.01,p-penalty)


def _qualifying_book_pool(offers, bookmaker, now, min_ev, min_references, max_disagreement):
    """Use only independently priced, timestamped, available NFL quotes."""
    candidates=value.scan(latest_active_batch(offers),now=now,
        min_references=min_references,min_ev_pct=min_ev,
        max_reference_range_pp=max_disagreement)
    return [r for r in candidates
        if r['quote'].get('bookmaker','').casefold()==bookmaker.casefold()
        and r['quote'].get('sport')=='NFL' and r.get('snapshot_id')]


def _ticket_from_legs(chosen, bookmaker):
    nominal=prod(float(r['fair_probability']) for r in chosen)
    stressed=prod(_conservative_probability(r) for r in chosen)
    decimal=prod(american_decimal(r['offered_odds']) for r in chosen)
    return {'legs':list(chosen),'leg_count':len(chosen),
            'nominal_probability':nominal,'conservative_probability':stressed,
            'decimal_price':decimal,'theoretical_ev_pct':100*(nominal*decimal-1),
            'stress_ev_pct':100*(stressed*decimal-1),
            'contrarian_legs':sum(_is_price_contrarian(r) for r in chosen),
            'bookmaker':bookmaker,
            'signature':tuple(sorted(r['snapshot_id'] for r in chosen))}


def _is_price_contrarian(r):
    """Underdog at plus-money versus independent fair price; NOT public-fade."""
    return r['offered_odds']>=100 and .30<=float(r['fair_probability'])<.50


def build_ev_tickets(offers, bookmaker, now=None, count=5, legs=3,
                     min_ev=1., min_references=2, max_disagreement=5.):
    """Return up to count distinct-game, same-book, positive-stressed-EV tickets.

    Three legs prioritize the highest conservative hit-rate proxy. Five legs
    retain a core/contrarian split. Reference probabilities are UNCALIBRATED.
    Ticket portfolios overlap and are NOT independent recommendations.
    """
    if legs not in (3,5):raise ValueError('Only 3-leg and 5-leg tickets supported')
    if count<1 or count>10:raise ValueError('Ticket count must be 1–10')
    if not bookmaker:return {'tickets':[],'eligible_legs':0,'eligible_games':0,'reason':'Select a sportsbook.'}
    now=now or datetime.now(timezone.utc)
    candidates=_qualifying_book_pool(offers,bookmaker,now,min_ev,min_references,max_disagreement)
    by_event=defaultdict(list)
    for r in candidates:by_event[r['quote']['event_id']].append(r)
    pool=[]
    for rs in by_event.values():
        rs.sort(key=lambda r:(-_conservative_probability(r),-r['ev_pct']))
        pool.extend(rs[:2])
    # Cap pool at 30 to bound combination enumeration and keep responsiveness.
    pool=sorted(pool,key=lambda r:(-_conservative_probability(r),-r['ev_pct']))[:30]
    eligible_games=len({r['quote']['event_id'] for r in pool})
    if eligible_games<legs:
        return {'tickets':[],'eligible_legs':len(candidates),'eligible_games':eligible_games,
            'reason':f'Fewer than {"three" if legs==3 else "five"} different NFL games have qualifying EV quotes at this sportsbook.'}
    evaluated=[]
    for chosen in combinations(pool,legs):
        if len({r['quote']['event_id'] for r in chosen})!=legs:continue
        if any(float(r['fair_probability'])<.35 for r in chosen):continue
        t=_ticket_from_legs(chosen,bookmaker)
        if t['stress_ev_pct']<=0:continue
        evaluated.append(t)
    if not evaluated:
        return {'tickets':[],'eligible_legs':len(candidates),'eligible_games':eligible_games,
            'reason':f'No {legs}-leg combination survived conservative probability and EV checks.'}
    # Sorting puts plausible hit frequency ahead of theoretical payout.
    evaluated.sort(key=lambda t:(-t['conservative_probability'],-t['stress_ev_pct']))
    winners=[]
    def choose(items,limit,label,allow_overlap=False):
        for t in items:
            if sum(x['label']==label for x in winners)>=limit:break
            overlap_limit=legs-1 if not allow_overlap else legs
            if any(t['signature']==o['signature'] or len(set(t['signature'])&set(o['signature']))>=overlap_limit
                   for o in winners):continue
            winners.append(dict(t,label=label))
    if legs==5:
        choose((t for t in evaluated if t['contrarian_legs']==0),min(3,count),'Higher hit-rate research')
        choose((t for t in evaluated if t['contrarian_legs']==1),min(2,count),'Contrarian value research',allow_overlap=True)
        if len(winners)<count:
            choose(evaluated,count-len(winners),'Additional qualified research')
    else:
        choose((t for t in evaluated if t['contrarian_legs']==0),count,'Higher hit-rate research')
        if len(winners)<count:
            choose(evaluated,count-len(winners),'Additional qualified research')
    if len(winners)<count:
        # Sparse slates can only supply highly overlapping tickets. Include
        # distinct tickets, never duplicate a ticket, and warn about overlap.
        choose(evaluated,count-len(winners),'Limited-diversification research',allow_overlap=True)
    reason=None if len(winners)>=count else f'Only {len(winners)} distinct, qualifying {legs}-leg tickets are available.'
    return {'tickets':winners[:count],'eligible_legs':len(candidates),
            'eligible_games':eligible_games,'reason':reason}


def build_five_leg_tickets(offers,bookmaker,now=None,count=5,legs=5,
                           min_ev=1.,min_references=2,max_disagreement=5.):
    """Backwards-compatible five-leg entry point."""
    if legs!=5:raise ValueError('Five-leg entry point requires legs=5')
    return build_ev_tickets(offers,bookmaker,now,count,5,min_ev,min_references,max_disagreement)


def build_three_leg_tickets(offers,bookmaker,now=None,count=5,
                            min_ev=1.,min_references=2,max_disagreement=5.):
    """Higher-hit-rate research tickets with three independent-game legs."""
    return build_ev_tickets(offers,bookmaker,now,count,3,min_ev,min_references,max_disagreement)


def rank_price_contrarians(offers, now=None, count=6, bookmaker=None,
                            min_ev=1., min_references=2,max_disagreement=5.):
    """Rank price-based NFL underdogs with independent fair-price evidence.

    This is not a public-betting fade, sharp-money indicator, or standalone
    independent player model. No qualifying underdogs => empty shortlist.
    Uses at most one price-based underdog per game, to avoid slate duplication.
    """
    now=now or datetime.now(timezone.utc)
    found=value.scan(latest_active_batch(offers),now=now,
        min_references=min_references,min_ev_pct=min_ev,
        max_reference_range_pp=max_disagreement)
    ranked=[]
    for r in found:
        if r['quote'].get('sport')!='NFL' or not r.get('snapshot_id'):continue
        if bookmaker and r['quote'].get('bookmaker','').casefold()!=bookmaker.casefold():continue
        if not _is_price_contrarian(r):continue
        # A positive theoretical EV alone is insufficient: apply the same
        # uncalibrated downside-sensitivity scenario used for parlay screening.
        stress_ev=100*(_conservative_probability(r)*american_decimal(r['offered_odds'])-1)
        if stress_ev<=0:continue
        score=(min(float(r['ev_pct']),25)*.7
               +min(float(r['edge_pp']),10)*.5
               +min(int(r['reference_count']),5)*1.0
               -float(r['variation_pp'])*.8
               +float(r['fair_probability'])*8)
        ranked.append(dict(r,contrarian_score=score,stress_ev_pct=stress_ev,
            contrarian_reason='Plus-money underdog with independently estimated +EV; public betting data not available'))
    ranked.sort(key=lambda r:(-r['contrarian_score'],-r['stress_ev_pct'],
                             -r['reference_count'],r['variation_pp']))
    selected=[]; used=set()
    for r in ranked:
        eid=r['quote']['event_id']
        if eid in used:continue
        selected.append(r);used.add(eid)
        if len(selected)>=count:break
    return {'picks':selected,'qualifying_underdogs':len(ranked),
            'eligible_games':len(used),
            'reason':None if len(selected)>=count else
            f'Only {len(selected)} different NFL games currently have qualifying price-contrarian underdogs.'}
