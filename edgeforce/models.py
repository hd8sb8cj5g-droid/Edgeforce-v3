"""Explicitly experimental, uncalibrated football score projections."""
import math
import re
import numpy as np
import pandas as pd

NFL_FULL={
'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL',
'Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI',
'Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL',
'Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB',
'Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX',
'Kansas City Chiefs':'KC','Las Vegas Raiders':'LV','Los Angeles Chargers':'LAC',
'Los Angeles Rams':'LA','Miami Dolphins':'MIA','Minnesota Vikings':'MIN',
'New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG',
'New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT',
'San Francisco 49ers':'SF','Seattle Seahawks':'SEA','Tampa Bay Buccaneers':'TB',
'Tennessee Titans':'TEN','Washington Commanders':'WAS'}


CFB_ALIASES = {}


def build_cfb_aliases(teams):
    """Map CFBD schools, mascots and alternate names to the same canonical school."""
    aliases={}
    for record in teams:
        school=str(record.get('school') or '').strip()
        if not school:continue
        names=[school,school+' '+str(record.get('mascot') or '').strip(),
               record.get('abbreviation')]+list(record.get('alternateNames') or [])
        for name in names:
            if not name:continue
            key=re.sub(r'[^a-z0-9]','',str(name).lower())
            if key:aliases[key]=re.sub(r'[^a-z0-9]','',school.lower())
    return aliases


def register_cfb_teams(teams):
    CFB_ALIASES.clear()
    CFB_ALIASES.update(build_cfb_aliases(teams))
    return len(CFB_ALIASES)

def team_key(name,sport='NFL'):
    if sport=='NFL':return NFL_FULL.get(str(name),str(name))
    k=re.sub(r'[^a-z0-9]','',str(name).lower())
    return CFB_ALIASES.get(k,k)


def american_decimal(odds):
    a=int(odds)
    if a==0:raise ValueError('Zero odds invalid')
    return 1+a/100 if a>0 else 1+100/abs(a)


def implied(odds):return 1/american_decimal(odds)


def fair_american(p):
    if p is None or not 0<p<1:return None
    return int(round(100*(1-p)/p)) if p<=.5 else int(round(-100*p/(1-p)))


def ev_per_dollar(p,american):
    return p*(american_decimal(american)-1)-(1-p)


def odds_pnl(odds,stake,outcome):
    if outcome=='WIN':return (american_decimal(odds)-1)*stake
    if outcome=='LOSS':return -stake
    return 0.


def no_vig_probability(quotes, selected):
    """Devig only outcomes at the same bookmaker/market/line; otherwise unavailable."""
    relevant=[]
    for q in quotes:
        if (q['event_id'],q['bookmaker'],q['market'])!=(selected['event_id'],selected['bookmaker'],selected['market']):continue
        if q.get('participant','')!=selected.get('participant',''):continue
        if selected['market']=='totals' or selected['market'].startswith('player_'):
            if q.get('point')!=selected.get('point'):continue
        elif selected['market']=='spreads':
            if abs(float(q.get('point') or 0))!=abs(float(selected.get('point') or 0)):continue
        relevant.append(q)
    if len(relevant)!=2:return None
    denom=sum(implied(q['american_odds']) for q in relevant)
    return implied(selected['american_odds'])/denom if denom else None


def scores_from_schedule(nfl_df,asof=None):
    """Each row is played NFL game with team abbreviations. asof prevents historical leakage."""
    if nfl_df is None or nfl_df.empty:return []
    df=nfl_df.copy()
    df=df.dropna(subset=['home_score','away_score'])
    if asof is not None and 'gameday' in df.columns:
        df=df[pd.to_datetime(df.gameday,utc=True,errors='coerce')<pd.Timestamp(asof)]
    out=[]
    for _,r in df.iterrows():
        out.append({'home':str(r.home_team),'away':str(r.away_team),
                    'hs':float(r.home_score),'as':float(r.away_score),
                    'week':r.get('week'), 'date':str(r.get('gameday','')),
                    'event_id':str(r.get('game_id','')),'sport':'NFL'})
    return out


def scores_from_cfbd(games,asof=None):
    out=[]
    for g in games:
        if g.get('home_points') is None or g.get('away_points') is None:continue
        date=g.get('start_date','')
        if asof and date and pd.to_datetime(date,utc=True)>=pd.Timestamp(asof):continue
        out.append({'home':str(g['home_team']),'away':str(g['away_team']),
                    'hs':float(g['home_points']),'as':float(g['away_points']),
                    'week':g.get('week'),'date':date,
                    'event_id':str(g.get('id','')),'sport':'CFB'})
    return out


def team_summary(games,sport='NFL',trailing=10):
    """Shrink sparse historical performance to national scoring average. No future game data."""
    results={}
    for g in sorted(games,key=lambda g: str(g.get('date',''))):
        for team,points,against in ((g['home'],g['hs'],g['as']),(g['away'],g['as'],g['hs'])):
            key=team_key(team,sport)
            results.setdefault(key,[]).append((points,against))
    summary={}
    baseline=22.5 if sport=='NFL' else 28.0
    for k,rows in results.items():
        rows=rows[-trailing:]
        n=len(rows); weight=n/(n+5)
        summary[k]={'played':n,'pf':weight*np.mean([x[0] for x in rows])+(1-weight)*baseline,
                    'pa':weight*np.mean([x[1] for x in rows])+(1-weight)*baseline}
    return summary


def project_scores(home,away,sport,team_stats):
    h=team_stats.get(team_key(home,sport));a=team_stats.get(team_key(away,sport))
    if not h or not a or min(h['played'],a['played'])<3:return None
    baseline=22.5 if sport=='NFL' else 28
    home_advantage=1.6 if sport=='NFL' else 2.5
    hs=max(3.,(h['pf']+a['pa'])/2+home_advantage)
    ats=max(3.,(a['pf']+h['pa'])/2)
    return {'home':hs,'away':ats,'margin':hs-ats,'total':hs+ats,
            'margin_sd':13.5 if sport=='NFL' else 18,
            'total_sd':13.8 if sport=='NFL' else 20,
            'home_games':h['played'],'away_games':a['played'],
            'model':'scoring-form-v0.1','validated':False}


def norm_cdf(x):return .5*(1+math.erf(x/math.sqrt(2)))


def probability(quote,proj):
    if proj is None:return None
    hs=proj['home'];a=proj['away']; spread=proj['margin_sd'];sd_total=proj['total_sd']
    name=str(quote['selection']);market=quote['market'];p=quote.get('point')
    if market=='h2h':
        return norm_cdf((hs-a)/spread) if name==quote['home_team'] else (norm_cdf((a-hs)/spread) if name==quote['away_team'] else None)
    if market=='spreads' and p is not None:
        return norm_cdf((hs-a+float(p))/spread) if name==quote['home_team'] else (norm_cdf((a-hs+float(p))/spread) if name==quote['away_team'] else None)
    if market=='totals' and p is not None:
        return norm_cdf((hs+a-float(p))/sd_total) if name.lower()=='over' else (norm_cdf((float(p)-hs-a)/sd_total) if name.lower()=='under' else None)
    return None


def grade(quote,proj,p):
    """A/B/C research coverage (NOT validated confidence in a profitable edge)."""
    if p is None:return '—'
    n=min(proj['home_games'],proj['away_games'])
    if n>=8 and quote['market']=='h2h':return 'B'
    return 'C'


def resolve_score(quote,game):
    """Compute objective result from final score; player markets remain manual."""
    if quote['market'] not in ('h2h','spreads','totals'):return None
    hs,as_=float(game['hs']),float(game['as'])
    market=quote['market'];sel=quote['selection'];p=quote.get('point')
    if market=='totals':
        if p is None:return None
        diff=(hs+as_)-float(p)
        if sel.lower()=='under':diff=-diff
        elif sel.lower()!='over':return None
    else:
        if sel==quote['home_team']:d=hs-as_
        elif sel==quote['away_team']:d=as_-hs
        else:return None
        diff=d+(float(p) if market=='spreads' and p is not None else 0)
    return 'WIN' if diff>0 else ('LOSS' if diff<0 else 'PUSH')


def matching_game(quote,games):
    """Conservative: exact normalized team pairing and kickoff within 40 hours, unique match only."""
    sport=quote['sport'];home=team_key(quote['home_team'],sport);away=team_key(quote['away_team'],sport)
    start=pd.to_datetime(quote['commence_time'],utc=True)
    matches=[]
    for g in games:
        if g['sport']!=sport:continue
        if team_key(g['home'],sport)!=home or team_key(g['away'],sport)!=away:continue
        day=pd.to_datetime(g.get('date'),utc=True,errors='coerce')
        if pd.isna(day) or abs((start-day).total_seconds())>40*3600:continue
        matches.append(g)
    return matches[0] if len(matches)==1 else None
