"""NFLverse schedule normalization and honest, timezone-aware display controls.

NFLverse is the source of record for this page. ESPN is used only to signal
inconsistencies in the current week, never to invent outcomes or change scores.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd

EASTERN = ZoneInfo('America/New_York')
# ESPN / nflverse occasionally use different short names for the same franchise.
ALIASES = {'LAR':'LA','JAX':'JAX','WSH':'WAS','AZ':'ARI','ARZ':'ARI',
           'LVR':'LV','OAK':'LV','SD':'LAC','STL':'LA','JAC':'JAX'}
REQUIRED = {'season','week','gameday','home_team','away_team','home_score','away_score'}


def normalize_team(team):
    v = str(team or '').strip().upper()
    return ALIASES.get(v, v)


def _asof(asof=None):
    dt = pd.Timestamp(asof if asof is not None else datetime.now(timezone.utc))
    return dt.tz_localize('UTC') if dt.tzinfo is None else dt.tz_convert('UTC')


def _kickoff(day, time):
    """Parse nflverse gameday + ET gametime into real UTC kickoff.

    If the source omits gametime, retain date with a deliberately coarse noon
    value for ordering; it MUST NOT be treated as an authoritative kickoff.
    """
    d = pd.to_datetime(day, errors='coerce')
    if pd.isna(d):return pd.NaT, False
    day_str=d.strftime('%Y-%m-%d')
    if time is not None and not pd.isna(time):
        text=str(time).strip()
        if text and text.lower() not in ('nan','nat','none','tbd'):
            for fmt in ('%Y-%m-%d %H:%M','%Y-%m-%d %H:%M:%S','%Y-%m-%d %I:%M %p'):
                try:
                    parsed=datetime.strptime(day_str+' '+text,fmt)
                    return pd.Timestamp(parsed.replace(tzinfo=EASTERN).astimezone(timezone.utc)), True
                except ValueError:pass
    return pd.Timestamp(datetime.combine(d.date(),datetime.min.time()).replace(hour=12,tzinfo=EASTERN).astimezone(timezone.utc)), False


def prepare_schedule(source,season,asof=None):
    """Return all available games (no implicit tail/head truncation) with status.

    Reject wrong-season or malformed records rather than silently claiming
    an accurate schedule. Never interpret blank future scores as final results.
    """
    if source is None or source.empty:
        raise ValueError(f'NFLverse returned no schedule games for the {season} season.')
    missing=REQUIRED-set(source.columns)
    if missing:raise ValueError('NFLverse schedule missing fields: '+', '.join(sorted(missing)))
    asof=_asof(asof)
    df=source.copy()
    df['season']=pd.to_numeric(df['season'],errors='coerce')
    df=df[df.season==int(season)].copy()
    if df.empty:raise ValueError(f'NFLverse had no {season} games. Verify season and provider freshness.')
    df['week']=pd.to_numeric(df['week'],errors='coerce')
    df['game_type']=df['game_type'].fillna('REG').astype(str).str.upper() if 'game_type' in df else 'REG'
    df['home_score']=pd.to_numeric(df['home_score'],errors='coerce')
    df['away_score']=pd.to_numeric(df['away_score'],errors='coerce')
    starts=[_kickoff(d,t) for d,t in zip(df['gameday'],df['gametime'] if 'gametime' in df else [None]*len(df))]
    df['kickoff_utc']=pd.to_datetime([s[0] for s in starts],utc=True)
    df['kickoff_verified']=[s[1] for s in starts]
    df['game_day']=pd.to_datetime(df['gameday'],errors='coerce').dt.date
    if df['game_day'].isna().any():
        raise ValueError('NFLverse contains games without valid game dates; cannot reliably display current week.')
    if 'game_id' not in df:
        df['game_id']=(df['season'].astype(str)+'_'+df['week'].astype(str)+'_'+
                       df['away_team'].astype(str)+'_'+df['home_team'].astype(str))
    if df['game_id'].duplicated().any():
        raise ValueError('NFLverse schedule contains duplicate game IDs; verify upstream data before sync.')
    finished=df['home_score'].notna() & df['away_score'].notna() &              ((df['home_score']!=0)|(df['away_score']!=0))
    # If the source omitted kickoff time, never infer finality until the local date is past.
    began=((df['kickoff_verified'] & (df['kickoff_utc']<=asof)) |
           (~df['kickoff_verified'] & (df['game_day']<asof.tz_convert(EASTERN).date())))
    df['status']='Scheduled'
    df.loc[began & ~finished,'status']='Awaiting final'
    df.loc[began & finished,'status']='Final'
    df=df.sort_values(['kickoff_utc','week','game_id'],kind='stable').reset_index(drop=True)
    return df


def active_week(schedule,asof=None):
    """Identify the ongoing week or the *next* upcoming week (not Week 18)."""
    asof=_asof(asof)
    today=asof.tz_convert(EASTERN).date()
    df=schedule[schedule.game_type=='REG'].dropna(subset=['week'])
    if df.empty:return None
    bounds=df.groupby('week')['game_day'].agg(['min','max']).sort_index()
    within=[int(w) for w,r in bounds.iterrows() if r['min']<=today<=r['max']]
    if within:return min(within)
    upcoming=[(r['min'],int(w)) for w,r in bounds.iterrows() if r['min']>today]
    if upcoming:return min(upcoming)[1]
    return int(bounds.index.max())


def select_games(schedule,view='Current week',asof=None,week=None):
    asof=_asof(asof)
    regular=schedule[schedule.game_type=='REG'].copy()
    if view=='Current week':
        chosen=active_week(schedule,asof)
        return regular[regular.week==chosen].copy() if chosen is not None else regular.iloc[:0].copy()
    if view=='Specific week':
        return regular[regular.week==int(week)].copy() if week is not None else regular.iloc[:0].copy()
    if view=='Next 7 days':
        return schedule[(schedule.kickoff_utc>=asof)&(schedule.kickoff_utc<=asof+timedelta(days=7))].copy()
    if view=='Upcoming':return schedule[schedule.status=='Scheduled'].copy()
    if view=='Completed':return schedule[schedule.status=='Final'].copy()
    if view=='All regular season':return regular.copy()
    if view=='All games (incl. postseason)':return schedule.copy()
    raise ValueError(f'Unknown NFL schedule view: {view}')


def coverage(schedule):
    regular=schedule[schedule.game_type=='REG']
    weeks=sorted({int(w) for w in regular.week.dropna()})
    n=len(regular)
    season=int(schedule['season'].iloc[0])
    expected=272 if season>=2021 else 256
    week_count=18 if season>=2021 else 17
    warnings=[]
    if n<expected:
        warnings.append(f'Only {n}/{expected} regular-season games supplied; NFLverse schedule may be incomplete.')
    if n>expected:
        warnings.append(f'{n} regular-season games supplied (expected {expected}); investigate duplicates or changes.')
    absent=sorted(set(range(1,week_count+1))-set(weeks))
    if absent:warnings.append('Missing regular-season weeks: '+', '.join(map(str,absent))+'.')
    if (~schedule.kickoff_verified).any():
        warnings.append('Some game times were missing/invalid; kickoff ordering uses noon ET placeholders for those records.')
    return {'regular_games':n,'weeks':weeks,'finals':int((schedule.status=='Final').sum()),
            'upcoming':int((schedule.status=='Scheduled').sum()),'warnings':warnings}


def compare_espn(schedule,espn_games,week):
    """Cross-check game identities and date, never substitute an unverified score."""
    nfl=schedule[(schedule.game_type=='REG')&(schedule.week==int(week))]
    lookup={(normalize_team(r.away_team),normalize_team(r.home_team)):r
            for r in nfl.itertuples(index=False)}
    remote={}
    for g in espn_games:
        key=(normalize_team(g.get('away_team')),normalize_team(g.get('home_team')))
        if all(key):remote[key]=g
    missing_nfl=sorted(set(remote)-set(lookup))
    missing_espn=sorted(set(lookup)-set(remote))
    date_diffs=[]
    for key in set(remote)&set(lookup):
        nfl_date=lookup[key].game_day
        espn_date=pd.to_datetime(remote[key].get('kickoff_utc'),utc=True,errors='coerce')
        if not pd.isna(espn_date) and nfl_date!=espn_date.tz_convert(EASTERN).date():
            date_diffs.append(key)
    return {'matches':len(set(remote)&set(lookup)),'nfl_total':len(lookup),
            'espn_total':len(remote),'missing_in_nflverse':missing_nfl,
            'missing_in_espn':missing_espn,'date_disagreements':date_diffs,
            'consistent':not(missing_nfl or missing_espn or date_diffs)}


def table(schedule):
    """Mobile-friendly time/score/status columns, sorted chronologically."""
    schedule=schedule.reset_index(drop=True)
    out=pd.DataFrame({
        'Week':schedule['week'].astype('Int64'),
        'Kickoff (ET)':schedule['kickoff_utc'].dt.tz_convert(EASTERN).dt.strftime('%a %b %d, %I:%M %p'),
        'Away':schedule['away_team'].astype(str),
        'Home':schedule['home_team'].astype(str),
        'Status':schedule['status']})
    out['Result']=schedule.apply(lambda r: (f"{int(r.away_score)}–{int(r.home_score)}"
        if r.status=='Final' else '—'),axis=1)
    if not schedule['kickoff_verified'].all():
        mask=~schedule['kickoff_verified']
        out.loc[mask,'Kickoff (ET)']=schedule.loc[mask,'game_day'].astype(str)+' (time unavailable)'
    return out
