"""Research-only correlated score simulations; no claims of guaranteed profit."""
import itertools
from collections import defaultdict
import numpy as np
from .models import american_decimal,implied,probability


def simulate_game_scores(proj, n=30000, seed=42):
    """Shared home/away outcomes create within-game dependence across legs."""
    rng=np.random.default_rng(seed)
    total=rng.normal(proj['total'],proj['total_sd'],n)
    margin=rng.normal(proj['margin'],proj['margin_sd'],n)
    # Heuristic Gaussian model; not yet calibrated to touchdown distributions.
    hs=np.clip(np.rint((total+margin)/2),0,None)
    away=np.clip(np.rint((total-margin)/2),0,None)
    return hs,away


def selection_outcomes(q, scores):
    hs,away=scores
    if q['market']=='h2h':
        margin=hs-away if q['selection']==q['home_team'] else away-hs
    elif q['market']=='spreads':
        margin=(hs-away if q['selection']==q['home_team'] else away-hs)+float(q['point'])
    elif q['market']=='totals':
        margin=(hs+away-float(q['point']))*(1 if q['selection'].lower()=='over' else -1)
    else:raise ValueError('Unsupported market')
    return margin>0,margin==0


def joint_ticket(quotes,projections,n=30000,seed=42):
    if not quotes:return None
    outcomes=[];pushes=[]
    game_scores={}
    for i,q in enumerate(quotes):
        if q['event_id'] not in projections:return None
        if q['event_id'] not in game_scores:
            game_scores[q['event_id']]=simulate_game_scores(projections[q['event_id']],n,seed+len(game_scores)*277)
        win,push=selection_outcomes(q,game_scores[q['event_id']])
        outcomes.append(win);pushes.append(push)
    all_win=np.logical_and.reduce(outcomes)
    any_push=np.logical_or.reduce(pushes)
    all_win_or_push=np.logical_and.reduce([w|p for w,p in zip(outcomes,pushes)])
    p_win=float(np.mean(all_win))
    # Individual push permutations require settlement-dependent payout; exclude from EV and report separately.
    p_push=float(np.mean(all_win_or_push & any_push))
    p_loss=max(0.,1-p_win-p_push)
    combined=1.
    for q in quotes:combined*=american_decimal(q['american_odds'])
    ev=p_win*(combined-1)-p_loss # push-modelled conservatively as 0 profit even if some legs win
    independent=1.
    for q in quotes:independent*=probability(q,projections[q['event_id']]) or 0
    return {'win_prob':p_win,'push_prob':p_push,'loss_prob':p_loss,
            'approx_ev_per_dollar':ev, 'decimal_payout':combined,'independent_prob':independent,
            'n':n,'simulation':'correlated-score-v0.1 (heuristic, not backtested)'}


def candidate_tickets(quotes,projections, ticket_count=5, legs=5, sim_n=15000):
    """Small, reproducible candidate search; 3 mainstream + 2 underdog/contrarian when feasible."""
    eligible=[]
    for q in quotes:
        proj=projections.get(q['event_id'])
        if not proj:continue
        p=probability(q,proj)
        if p is None:continue
        if q['market'] not in ('h2h','spreads','totals'):continue
        value=p-implied(q['american_odds'])
        # Restrict very unlikely legs that inflate payout but provide poor stability.
        if p<.25:continue
        eligible.append((q,p,value))
    if len(eligible)<legs:return []
    if len({q['bookmaker'] for q,_,_ in eligible})!=1:
        raise ValueError('Parlay candidates must use one sportsbook')
    # Diverse set of outcomes across games; no conflicting selections from same matchup.
    eligible.sort(key=lambda x:(x[2],x[1]),reverse=True)
    # Limit CPU, provide reproducible candidate search rather than claiming global optimum.
    pool=eligible[:min(42,len(eligible))]
    if len({q['event_id'] for q,_,_ in pool})<legs:return []
    rng=np.random.default_rng(17)
    candidates=[];seen=set()
    for _ in range(3500):
        chosen=rng.choice(len(pool),size=min(legs,len(pool)),replace=False)
        qs=[pool[i][0] for i in chosen]
        # One leg per event: standard multi-game parlays can use product prices;
        # same-game quoted legs need a separate sportsbook-approved SGP payout.
        event_count=defaultdict(int)
        for q in qs:event_count[q['event_id']]+=1
        if max(event_count.values())>1:continue
        cats=[(q['event_id'],q['market'],abs(float(q.get('point') or 0))) for q in qs]
        if len(set(cats))<len(cats):continue
        k=tuple(sorted(q['id'] for q in qs))
        if k in seen:continue
        seen.add(k)
        # contrarian: at least one underdog whose model p > posted implied, NOT just any longshot.
        contra=any(q['american_odds']>0 and pool[i][2]>0.025 and pool[i][1]<0.50 for i,q in zip(chosen,qs))
        avg_edge=np.mean([pool[i][2] for i in chosen])
        # Use coarse independent screen first; full Monte Carlo only top candidates.
        p_ind=np.prod([pool[i][1] for i in chosen])
        dec=np.prod([american_decimal(q['american_odds']) for q in qs])
        approx=p_ind*dec-1
        candidates.append((approx+avg_edge*.2,contra,qs))
    if not candidates:return []
    candidates.sort(key=lambda x:x[0],reverse=True)
    selected=[];used=set()
    for want_contrarian,slots in [(False,3),(True,2)]:
        gathered=0
        for _,contra,qs in candidates:
            if contra!=want_contrarian:continue
            sig=tuple(sorted(q['id'] for q in qs))
            if sig in used:continue
            # force at least two different groups of core bets to limit duplicate tickets.
            if any(len(set(sig)&set(old))>=legs-1 for old in used):continue
            used.add(sig)
            j=joint_ticket(qs,projections,n=sim_n,seed=42+len(selected))
            if j:
                selected.append({'type':'Contrarian' if want_contrarian else 'Core', 'quotes':qs,**j})
                gathered+=1
            if gathered>=slots:break
    return selected
