"""Auditing, performance metrics, closing lines, and strictly guarded auto-settlement."""
from datetime import datetime,timezone
import pandas as pd
from . import db
from .models import odds_pnl,implied,ev_per_dollar,resolve_score,matching_game


def performance_rows(path=None):
    predictions=db.prediction_history(path)
    results=[]
    for r in predictions:
        close=db.closing_quote(r,path)
        row=dict(r)
        row['closing_american_odds']=close['american_odds'] if close else None
        row['closing_observed_at']=close['observed_at'] if close else None
        row['closing_same_price']=close is not None and close['id']==r['snapshot_id']
        row['clv_implied_delta_pp']=(100*(implied(close['american_odds'])-implied(r['american_odds']))) if close else None
        row['realized_pnl']=odds_pnl(r['american_odds'],r['stake'],r['outcome']) if r['outcome'] else None
        row['predicted_ev']=ev_per_dollar(r['model_probability'],r['american_odds']) if r['model_probability'] is not None else None
        results.append(row)
    return results


def metrics(rows):
    settled=[r for r in rows if r.get('outcome')]
    risk=sum(r['stake'] for r in settled if r['outcome']!='VOID')
    pnl=sum(r['realized_pnl'] or 0 for r in settled)
    decisive=[r for r in settled if r['outcome'] in ('WIN','LOSS')]
    calibrated=[r for r in decisive if r.get('model_probability') is not None]
    return {
        'predictions':len(rows),'settled':len(settled),'wins':sum(r['outcome']=='WIN' for r in decisive),
        'win_rate':sum(r['outcome']=='WIN' for r in decisive)/len(decisive) if decisive else None,
        'pnl':pnl,'roi':pnl/risk if risk else None,
        'brier':sum((r['model_probability']-(r['outcome']=='WIN'))**2 for r in calibrated)/len(calibrated) if calibrated else None,
        'clv_available':sum(r.get('clv_implied_delta_pp') is not None for r in rows),
        'clv_pp_mean':sum(r['clv_implied_delta_pp'] for r in rows if r.get('clv_implied_delta_pp') is not None)/max(1,sum(r.get('clv_implied_delta_pp') is not None for r in rows))
    }


def auto_settle(games,path=None):
    """Only completed games with unique matching matchup & kickoff can be auto-graded."""
    result={'settled':0,'skipped':0,'details':[]}
    for r in db.prediction_history(path):
        if r.get('outcome'):
            continue
        matching=matching_game(r,games)
        if not matching:
            result['skipped']+=1;continue
        outcome=resolve_score(r,matching)
        if outcome is None:
            result['skipped']+=1;continue
        src='nflverse schedule' if r['sport']=='NFL' else 'CollegeFootballData final score'
        db.record_game_score(r['event_id'],r['sport'],r['home_team'],r['away_team'],
            matching['hs'],matching['as'],src,matching.get('date'),path=path)
        db.settle(r['id'],outcome,source=src,home_score=matching['hs'],away_score=matching['as'],
                  note='Automated exact-team/date match; review for cancellations or revisions.',path=path)
        result['settled']+=1
        result['details'].append(f"{r['home_team']} vs {r['away_team']} {r['market']} {r['selection']}: {outcome}")
    return result


def export_dataframe(path=None):
    rows=performance_rows(path)
    return pd.DataFrame(rows)


def auto_settle_tickets(games,path=None):
    """Resolve only definite full wins/losses; pushed legs need quoted reduced ticket payout."""
    summary={'settled':0,'skipped':0,'details':[]}
    for t in db.ticket_history(path):
        if t.get('outcome'):
            continue
        results=[]
        for leg in t['legs']:
            g=matching_game(leg,games)
            if not g:break
            result=resolve_score(leg,g)
            if not result:break
            results.append(result)
        if len(results)!=len(t['legs']) or 'PUSH' in results:
            summary['skipped']+=1;continue
        outcome='WIN' if all(r=='WIN' for r in results) else 'LOSS'
        db.settle_ticket(t['id'],outcome,source='verified final game scores',
             note='Each leg matched to unique final NFLverse/CFBD result',path=path)
        summary['settled']+=1
        summary['details'].append(t['id'][:10]+': '+outcome)
    return summary
