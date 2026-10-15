"""Pre-registered prediction accuracy; never uses future data to construct a pick.

Only settled WIN/LOSS contribute Brier and calibration; ROI uses settled stakes;
PUSH/VOID do not count as wins. These are paper/research records, not proof of
actual placed bets or income. Historical estimates must be time stamped.
"""
from __future__ import annotations
import math
from collections import defaultdict
from .injury_intelligence import historical_tag
from . import models

BINS=((0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.001))

def _bucket_market(m):
    m=str(m or '')
    return 'Player props' if m.startswith('player_') else {'h2h':'Moneyline','spreads':'Spread','totals':'Total'}.get(m,'Other')

def _kind(p):
    if p is None:return None
    try:
        f=float(p)
    except (TypeError,ValueError):return None
    return f if math.isfinite(f) and 0<f<1 else None

def summarize(rows, min_sample=30):
    decisive=[r for r in rows if r.get('outcome') in ('WIN','LOSS')]
    pending=sum(r.get('outcome') is None for r in rows)
    settled=[r for r in rows if r.get('outcome') in ('WIN','LOSS','PUSH')]
    risk=sum(max(0,float(r.get('stake') or 0)) for r in settled)
    profit=0.
    groups=defaultdict(list)
    injury_groups=defaultdict(list)
    calibration=[[] for _ in BINS]
    calibration_count=0
    for r in decisive:
        y=int(r['outcome']=='WIN')
        p=_kind(r.get('model_probability'))
        groups[_bucket_market(r.get('market'))].append(r)
        injury_groups[historical_tag(r.get('tags'))['injury_status']].append(r)
        if p is not None:
            calibration_count+=1
            for i,(a,b) in enumerate(BINS):
                if a<=p<b:
                    calibration[i].append((p,y));break
    for r in settled:
        if r.get('realized_pnl') is not None:
            profit+=float(r['realized_pnl'])
        else:
            price=r.get('american_odds')
            if price and r['outcome']=='WIN': profit+=float(r.get('stake') or 0)*(models.american_decimal(int(price))-1)
            elif r['outcome']=='LOSS':profit-=float(r.get('stake') or 0)
    def group_summary(group):
        probs=[(_kind(r.get('model_probability')),int(r['outcome']=='WIN')) for r in group]
        probs=[(p,y) for p,y in probs if p is not None]
        return {'n':len(group),'wins':sum(r['outcome']=='WIN' for r in group),
            'observed_win_rate':sum(r['outcome']=='WIN' for r in group)/len(group) if group else None,
            'mean_predicted':sum(p for p,_ in probs)/len(probs) if probs else None,
            'brier':sum((p-y)**2 for p,y in probs)/len(probs) if probs else None,
            'calibration_n':len(probs),'mature':len(probs)>=min_sample}
    cohorts={k:group_summary(v) for k,v in sorted(groups.items())}
    injury={k:group_summary(v) for k,v in sorted(injury_groups.items())}
    bins=[]
    for (a,b),vals in zip(BINS,calibration):
        if vals:bins.append({'range':f'{int(a*100)}–{int(min(b,1)*100)}%',
                             'n':len(vals),'forecast_pct':round(100*sum(p for p,y in vals)/len(vals),1),
                             'actual_pct':round(100*sum(y for p,y in vals)/len(vals),1)})
    overall=group_summary(decisive)
    overall.update({'predictions':len(rows),'pending':pending,'settled':len(settled),
                    'research_pnl':round(profit,2),'research_roi':profit/risk if risk else None,
                    'calibrated_rows':calibration_count,'minimum_sample':min_sample,
                    'note':('Too few settled predictions to assess calibration reliably.' if calibration_count<min_sample else
                            'Calibration diagnostics are descriptive, not validation of an edge.')})
    return {'overall':overall,'by_market':cohorts,'by_injury_status':injury,'calibration_bins':bins}
