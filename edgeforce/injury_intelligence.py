"""NFL injury availability evidence and conservative, explicitly hypothetical odds stress.

Nothing in this module proves a player will start, manufactures a new fair price,
or upgrades an underdog because an opponent is injured. Injury reports are weekly
snapshots, not a live inactive roster. Never treat a missing report as 'healthy'.
"""
from __future__ import annotations
import json
import math
import re
import unicodedata
from datetime import datetime, timezone, timedelta
import pandas as pd
from . import nfl_schedule, models

SOURCE = 'NFLverse injury report (game-status/practice participation)'
BLOCKED = {'OUT', 'INACTIVE', 'INJURED RESERVE', 'IR', 'RESERVE/INJURED', 'SUSPENDED'}
UNCERTAIN = {'QUESTIONABLE', 'DOUBTFUL'}

def utc(value):
    if isinstance(value, datetime):
        if value.tzinfo is None: raise ValueError('Date must be timezone-aware')
        return value.astimezone(timezone.utc)
    stamp = pd.to_datetime(value, errors='coerce', utc=True)
    if pd.isna(stamp): raise ValueError('Unknown timestamp')
    return stamp.to_pydatetime()

def norm_name(s):
    s=unicodedata.normalize('NFKD',str(s or '').casefold())
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', s)
    return re.sub(r'[^a-z0-9]', '', s)

def norm_status(s):
    x=' '.join(str(s or '').upper().replace('-', ' ').replace('_',' ').split())
    if x in {'DNP','DID NOT PARTICIPATE'}:return 'DNP'
    if x in {'LIMITED PARTICIPATION','LIMITED PARTICIPANT','LP'}:return 'LIMITED'
    if x in {'FULL PARTICIPATION','FULL PARTICIPANT','FP'}:return 'FULL'
    return x

def prepare_reports(raw, season, week, asof=None, max_source_age_hours=120):
    """Current-week records only. Do not borrow a past week's OUT status.

    Include report rows only if the provider-reported modification time is not
    in the future, and mark the entire report stale if those timestamps are old.
    """
    asof=utc(asof or datetime.now(timezone.utc))
    empty={'season':season,'week':week,'fetched_at':asof.isoformat(),
           'source':SOURCE,'status':'MISSING','players':[], 'latest_modified':None,
           'warning':'No current-week official game-status evidence; do not infer that players are healthy.'}
    if raw is None or not isinstance(raw,pd.DataFrame) or raw.empty:return empty
    required={'season','week','team','full_name'}
    if required-set(raw.columns):return dict(empty,warning='Injury provider returned unexpected fields; no player status has been inferred.')
    df=raw.copy()
    df['season']=pd.to_numeric(df.season,errors='coerce')
    df['week']=pd.to_numeric(df.week,errors='coerce')
    df=df[(df.season==int(season))&(df.week==int(week))].copy()
    if 'season_type' in df:
        df=df[df.season_type.astype(str).str.upper().isin(['REG','REGULAR','2'])]
    if df.empty:return empty
    rows=[]
    for r in df.to_dict('records'):
        try:
            modified=utc(r['date_modified']) if r.get('date_modified') else None
            if modified and modified>asof+timedelta(minutes=2):continue
        except (ValueError,TypeError,OverflowError):
            modified=None
        game_status=norm_status(r.get('report_status'))
        practice_status=norm_status(r.get('practice_status'))
        team=nfl_schedule.normalize_team(r.get('team'))
        name=str(r.get('full_name') or '').strip()
        if not team or not name:continue
        rows.append({'team':team,'player':name,'name_key':norm_name(name),
                     'position':str(r.get('position') or '').upper().strip(),
                     'status':game_status, 'practice':practice_status,
                     'injury':str(r.get('report_primary_injury') or r.get('practice_primary_injury') or '').strip(),
                     'modified_at':modified.isoformat() if modified else None,
                     'is_current':bool(modified and timedelta(minutes=-2)<=asof-modified<=timedelta(hours=max_source_age_hours))})
    if not rows:return empty
    # A current-week report can contain multiple updates for a player; latest wins.
    unique={}
    for row in sorted(rows,key=lambda r:r['modified_at'] or ''):
        unique[(row['team'],row['name_key'])]=row
    rows=list(unique.values())
    timestamps=[utc(p['modified_at']) for p in rows if p['modified_at']]
    latest=max(timestamps) if timestamps else None
    fresh=bool(latest and timedelta(minutes=-2)<=asof-latest<=timedelta(hours=max_source_age_hours))
    return {'season':int(season),'week':int(week),'fetched_at':asof.isoformat(),
            'source':SOURCE,'status':'FRESH' if fresh else 'STALE','players':rows,
            'latest_modified':latest.isoformat() if latest else None,
            'warning':('Weekly report is partial and NOT a verified game-day inactive list.' if fresh else
                       'Weekly source update is stale or lacks a source timestamp. Verify the current injury report.')}

def injury_player(report, name, team=None):
    if not report or report.get('status')!='FRESH':return None
    key=norm_name(name)
    found=[p for p in report.get('players',[]) if p['name_key']==key and p.get('is_current') and (team is None or p['team']==team)]
    return found[0] if len(found)==1 else None

def assess_offer(offer, report):
    """Availability gate: suppress impossible picks and hold uncertain ones.

    Injury scenario is a hypothetical downside stress ONLY, never a new calibrated
    injury-adjusted fair probability. Team-wide missing QB status requires review.
    """
    quote=offer.get('quote',offer)
    result={'status':'UNVERIFIED','reason':'Current-week injury data unavailable or stale.',
            'matched_player':None,'source_status':(report or {}).get('status','MISSING'),
            'stress_probability':None,'stress_ev_pct':None,'scenario':'No injury stress computed.'}
    if quote.get('sport')!='NFL':
        return dict(result,status='NOT_SUPPORTED',reason='College injury feed is not integrated.')
    if not report or report.get('status')!='FRESH':return result
    participant=str(quote.get('participant') or '').strip()
    if not participant and str(quote.get('market'))=='player_anytime_td':
        participant=str(quote.get('selection') or '').strip()
    teamcodes={nfl_schedule.normalize_team(models.team_key(quote.get(x),'NFL')) for x in ('home_team','away_team')}
    relevant=[p for p in report.get('players',[]) if p['team'] in teamcodes]
    if participant:
        matched=[p for p in relevant if p['name_key']==norm_name(participant)]
        if len(matched)>1:
            result.update(status='HOLD',reason='Ambiguous same-name athlete across teams; confirm player identity.')
        elif matched:
            player=matched[0];s=player['status'];pr=player['practice']
            result['matched_player']=player
            if not player.get('is_current'):
                result.update(status='UNVERIFIED',reason='This player’s status record is stale or missing a valid update timestamp.')
            elif s in BLOCKED:result.update(status='BLOCK',reason=f"{player['player']} listed {s} on this weekly report; exclude until updated.")
            elif s in UNCERTAIN:result.update(status='HOLD',reason=f"{player['player']} listed {s}; hold pending active-status verification.")
            elif pr=='DNP':result.update(status='REVIEW',reason=f"{player['player']} did not practice; game-day status remains unconfirmed.")
            elif pr=='LIMITED':result.update(status='REVIEW',reason=f"{player['player']} was limited in practice; check participation before acting.")
            else:result.update(status='REVIEW',reason=f"{player['player']} appears on the report ({s or pr or 'status not listed'}); report does not confirm active status.")
        else:
            result.update(status='UNVERIFIED',reason='Athlete not listed in this injury report; not equivalent to cleared or confirmed active.')
    else:
        result.update(status='REVIEW',reason='Team/game market: check listed quarterback, skill-position and defensive injuries; no calibrated team-level injury adjustment exists.')
    # Give a visible, strictly hypothetical downside scenario for uncertain player markets.
    if offer.get('fair_probability') is not None and result['status'] in ('HOLD','REVIEW') and participant:
        prob=float(offer['fair_probability'])
        if 0<prob<1:
            stress=max(.001,prob-(.04 if result['status']=='HOLD' else .02))
            price=offer.get('offered_odds',quote.get('american_odds'))
            if price is not None:
                result['stress_probability']=stress
                result['stress_ev_pct']=round(100*(stress*models.american_decimal(int(price))-1),2)
                result['scenario']='Illustrative -4pp' if result['status']=='HOLD' else 'Illustrative -2pp'
    return result

def prediction_tags(assessment, report):
    """One immutable pregame snapshot of what was known at prediction time."""
    d={'type':'market_consensus_injury_research','version':1,
       'injury_status':assessment.get('status','UNVERIFIED'),
       'injury_reason':assessment.get('reason',''),
       'injury_source':(report or {}).get('source',''),
       'injury_week':(report or {}).get('week'),
       'injury_source_modified_at':(report or {}).get('latest_modified'),
       'injury_retrieved_at':(report or {}).get('fetched_at'),
       'injury_scenario_ev_pct':assessment.get('stress_ev_pct')}
    return json.dumps(d,sort_keys=True)

def historical_tag(tags):
    try:
        value=json.loads(tags)
        if isinstance(value,dict) and value.get('type')=='market_consensus_injury_research':
            return value
    except (ValueError,TypeError):pass
    return {'injury_status':'NOT_RECORDED'}
