"""Official/public integrations. No private key is ever written to the database."""
import os
import re
from datetime import datetime, timezone
import requests

SPORTS={'NFL':'americanfootball_nfl','CFB':'americanfootball_ncaaf'}
KALSHI='https://external-api.kalshi.com/trade-api/v2'
CFBD='https://api.collegefootballdata.com'
ODDS='https://api.the-odds-api.com/v4'
WEATHER='https://api.open-meteo.com/v1/forecast'
SESSION=requests.Session()
SESSION.headers.update({'User-Agent':'EdgeForce-Research/0.2 (+local prototype)'})
LAST_ODDS_USAGE = {}


class ProviderError(Exception):
    pass


def get_json(url, params=None, headers=None, timeout=16, include_headers=False):
    """Never include HTTP exception URLs: The Odds API key travels in the query string."""
    try:
        response=SESSION.get(url,params=params,headers=headers,timeout=timeout)
        if response.status_code in (401,403):
            raise ProviderError(f'Access denied by {response.url.split("?")[0]} (HTTP {response.status_code}). Check API credentials and plan access.')
        if response.status_code==429:
            raise ProviderError('Provider rate limit or API credit quota reached (HTTP 429). Reduce sync frequency.')
        if not response.ok:
            raise ProviderError(f'Provider returned HTTP {response.status_code}; verify endpoint and market entitlement.')
        data=response.json()
        return (data, dict(response.headers)) if include_headers else data
    except requests.RequestException as error:
        raise ProviderError(f'Unable to reach provider ({type(error).__name__}); check network connectivity.') from None
    except ValueError:
        raise ProviderError('Provider response is not valid JSON') from None


def odds_usage():
    """Last response credit metadata (not user credentials)."""
    return LAST_ODDS_USAGE.copy()


def normalize_odds_event(event, sport, allowed_markets=None):
    """Preserve participant so two players with the same over/under do not collide."""
    quotes=[]
    for book in event.get('bookmakers',[]):
        for market in book.get('markets',[]):
            name=market.get('key','')
            if allowed_markets is not None and name not in allowed_markets:continue
            for outcome in market.get('outcomes',[]):
                price=outcome.get('price')
                if not isinstance(price,(int,float)) or price==0:continue
                participant=str(outcome.get('description') or '')
                quotes.append({
                    'event_id':str(event['id']),'sport':sport,
                    'commence_time':event['commence_time'],
                    'home_team':event['home_team'],'away_team':event['away_team'],
                    'bookmaker':book.get('title') or book.get('key','unknown'),
                    'market':name,'selection':outcome['name'],'participant':participant,
                    'point':outcome.get('point'),'american_odds':int(price),
                    'source_updated_at':market.get('last_update') or book.get('last_update'),
                    'source':'The Odds API','raw':{'book_key':book.get('key'),'market_key':name,
                                                 'participant':participant}
                })
    return quotes


def odds_api(sport='NFL',key=None,regions='us',markets='h2h,spreads,totals'):
    key=key or os.getenv('ODDS_API_KEY','')
    if not key: raise ProviderError('Set ODDS_API_KEY in .env or Streamlit secrets')
    if sport not in SPORTS: raise ProviderError('Unsupported sport')
    allowed=set(markets.split(',')) & {'h2h','spreads','totals'}
    if not allowed:raise ProviderError('No supported featured markets selected')
    response=get_json(f'{ODDS}/sports/{SPORTS[sport]}/odds',{
        'apiKey':key,'regions':regions,'markets':','.join(sorted(allowed)),
        'oddsFormat':'american','dateFormat':'iso'},include_headers=True)
    raw,headers=response if isinstance(response,tuple) else (response,{})
    headers={str(k).lower():v for k,v in headers.items()}
    LAST_ODDS_USAGE.clear()
    LAST_ODDS_USAGE.update({k:headers.get(v,'not reported') for k,v in {
        'remaining':'x-requests-remaining','used':'x-requests-used','last':'x-requests-last'}.items()})
    return [q for event in raw for q in normalize_odds_event(event,sport,allowed)]


PROP_MARKETS={
    'Passing yards':'player_pass_yds','Rushing yards':'player_rush_yds',
    'Receiving yards':'player_reception_yds','Receptions':'player_receptions',
    'Passing touchdowns':'player_pass_tds','Rushing touchdowns':'player_rush_tds',
    'Receiving touchdowns':'player_reception_tds','Anytime touchdown':'player_anytime_td'
}


def odds_event_props(sport,event_id,key=None,markets=None,regions='us'):
    """One event, one deliberate API request: prevents surprise credit exhaustion."""
    key=key or os.getenv('ODDS_API_KEY','')
    if not key:raise ProviderError('Missing Odds API credential')
    if sport not in SPORTS:raise ProviderError('Unsupported sport')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{5,100}',str(event_id)):
        raise ProviderError('Invalid event identifier')
    keys=list(markets or (PROP_MARKETS['Passing yards'],PROP_MARKETS['Rushing yards'],PROP_MARKETS['Receiving yards'],PROP_MARKETS['Receptions']))
    if not keys or any(m not in PROP_MARKETS.values() for m in keys):
        raise ProviderError('Unsupported prop market')
    raw,headers=get_json(f'{ODDS}/sports/{SPORTS[sport]}/events/{event_id}/odds',{
        'apiKey':key,'regions':regions,'markets':','.join(keys),
        'oddsFormat':'american','dateFormat':'iso'},include_headers=True)
    headers={str(k).lower():v for k,v in headers.items()}
    LAST_ODDS_USAGE.clear()
    LAST_ODDS_USAGE.update({k:headers.get(v,'not reported') for k,v in {
        'remaining':'x-requests-remaining','used':'x-requests-used','last':'x-requests-last'}.items()})
    return normalize_odds_event(raw,sport,set(keys))


def cfbd_teams(year,key=None):
    key=key or os.getenv('CFBD_API_KEY','')
    if not key:raise ProviderError('Missing CFBD credential')
    return get_json(CFBD+'/teams/fbs',{'year':int(year)},headers={'Authorization':'Bearer '+key})


def check_connections(cfbd_key, odds_key, year=2026):
    """Two deliberate lightweight auth checks; odds /sports doesn't consume credits."""
    status={}
    if odds_key:
        try:
            data,headers=get_json(ODDS+'/sports',{'apiKey':odds_key},include_headers=True)
            safe_headers={str(k).lower():v for k,v in headers.items()}
            status['The Odds API']={'connected':True,'detail':f"{len(data)} listed sports",
                'credits_remaining':safe_headers.get('x-requests-remaining','not reported')}
        except ProviderError as error:
            status['The Odds API']={'connected':False,'detail':str(error)}
    else:status['The Odds API']={'connected':False,'detail':'No key supplied'}
    if cfbd_key:
        try:
            sample=get_json(CFBD+'/games',{'year':int(year),'team':'Minnesota'},
                        headers={'Authorization':'Bearer '+cfbd_key})
            status['CollegeFootballData']={'connected':True,'detail':f'{len(sample)} Minnesota game records in {int(year)}'}
        except ProviderError as error:
            status['CollegeFootballData']={'connected':False,'detail':str(error)}
    else:status['CollegeFootballData']={'connected':False,'detail':'No key supplied'}
    return status


def odds_free_quota(key=None):
    key=key or os.getenv('ODDS_API_KEY','')
    if not key:raise ProviderError('No odds API credential available')
    data,headers=get_json(ODDS+'/sports',{'apiKey':key},include_headers=True)
    clean={str(k).lower():v for k,v in headers.items()}
    remaining=clean.get('x-requests-remaining')
    return int(remaining) if remaining is not None else None


def cfbd_games(year, key=None,week=None,season_type='regular'):
    key=key or os.getenv('CFBD_API_KEY','')
    if not key: raise ProviderError('Set CFBD_API_KEY in .env or Streamlit secrets')
    params={'year':int(year),'seasonType':season_type}
    if week:params['week']=int(week)
    return get_json(CFBD+'/games',params=params,headers={'Authorization':'Bearer '+key})


def cfbd_team_stats(year, key=None):
    key=key or os.getenv('CFBD_API_KEY','')
    if not key: raise ProviderError('Set CFBD_API_KEY in .env or Streamlit secrets')
    return get_json(CFBD+'/stats/season',{'year':int(year)},headers={'Authorization':'Bearer '+key})


def cfbd_player_stats(year,team,key=None):
    """Game-level player box-score data, one team to conserve CFBD quota."""
    key=key or os.getenv('CFBD_API_KEY','')
    if not key: raise ProviderError('Set CFBD_API_KEY in .env or Streamlit secrets')
    return get_json(CFBD+'/games/players',{'year':int(year),'team':team},headers={'Authorization':'Bearer '+key})


def nfl_games(year):
    """Fetch every week of the requested NFL season, not a partial week slice."""
    try:
        import nflreadpy as nfl
        # nflreadpy defaults to a 24-hour download cache, which is too old for
        # frequently updated game results. Keep a 15-minute ceiling; explicit
        # user sync attempts to invalidate only the schedules release asset.
        try:
            from nflreadpy.config import update_config
            update_config(cache_duration=900)
        except ImportError:
            pass  # Some older versions do not expose configurable caching.
        if hasattr(nfl, 'clear_cache'):
            nfl.clear_cache('schedules/games')
        data=nfl.load_schedules(int(year)).to_pandas()
        if data is None or data.empty:
            raise ProviderError(f'NFLverse returned no games for {year}. Check that season exists upstream.')
        return data
    except ProviderError:raise
    except Exception as e:
        raise ProviderError('NFLverse schedules unavailable: '+str(e)) from e


def espn_nfl_week(year,week):
    """Optional, unofficial public cross-check of current-week teams and dates.

    Does NOT replace NFLverse records; a provider failure is surfaced to the UI.
    """
    if not (2000<=int(year)<=2100 and 1<=int(week)<=18):
        raise ProviderError('Invalid NFL year/week for schedule cross-check.')
    raw=get_json('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard',
                 {'dates':int(year),'seasontype':2,'week':int(week),'limit':50},timeout=12)
    rows=[]
    for event in raw.get('events',[]):
        comp=(event.get('competitions') or [{}])[0]
        teams={c.get('homeAway'):c.get('team',{}).get('abbreviation')
               for c in comp.get('competitors',[])}
        if teams.get('home') and teams.get('away'):
            rows.append({'home_team':teams['home'],'away_team':teams['away'],
                         'kickoff_utc':event.get('date'),'source':'ESPN public scoreboard'})
    if not rows:raise ProviderError(f'No ESPN games returned for {year} Week {week}; cannot cross-check.')
    return rows


def nfl_player_stats(year):
    try:
        import nflreadpy as nfl
        return nfl.load_player_stats(int(year)).to_pandas()
    except Exception as e:
        raise ProviderError('NFLverse player stats unavailable: '+str(e)) from e


def nfl_playbyplay(year):
    try:
        import nflreadpy as nfl
        data=nfl.load_pbp(int(year))
        columns=['posteam','defteam','epa','success','week','game_id','season_type']
        return data.select([c for c in columns if c in data.columns]).to_pandas()
    except Exception as e:
        raise ProviderError('NFLverse play-by-play unavailable: '+str(e)) from e


def kalshi_markets(series_ticker=None, pages=2, limit=200, sport_filter=True):
    """Public non-trading read-only endpoint. Series ticker is best for targeted football watches."""
    cursor=None; markets=[]
    for _ in range(max(1,min(int(pages),5))):
        params={'status':'open','limit':min(limit,1000)}
        if series_ticker:params['series_ticker']=series_ticker.strip().upper()
        if cursor:params['cursor']=cursor
        data=get_json(KALSHI+'/markets',params=params)
        batch=data.get('markets',[])
        if not isinstance(batch,list): raise ProviderError('Unexpected Kalshi response')
        markets.extend(batch)
        cursor=data.get('cursor')
        if not cursor or not batch:break
    if sport_filter and not series_ticker:
        football=('nfl','football','super bowl','superbowl','quarterback','college football','ncaa','touchdown')
        markets=[m for m in markets if any(w in (str(m.get('title',''))+' '+str(m.get('ticker',''))+' '+str(m.get('subtitle',''))).lower() for w in football)]
    return markets


def kalshi_orderbook(ticker):
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{3,150}',ticker):
        raise ProviderError('Invalid market ticker')
    return get_json(f'{KALSHI}/markets/{ticker}/orderbook')


def weather_forecast(latitude,longitude,timezone_name='America/Chicago'):
    if not -90<=float(latitude)<=90 or not -180<=float(longitude)<=180:
        raise ProviderError('Invalid coordinates')
    result=get_json(WEATHER,{'latitude':latitude,'longitude':longitude,
        'hourly':'temperature_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m',
        'temperature_unit':'fahrenheit','wind_speed_unit':'mph','timezone':timezone_name,'forecast_days':7})
    return result


def get_current_status():
    return {
        'NFLverse':'No key required; pull on demand',
        'CollegeFootballData':'API key configured' if os.getenv('CFBD_API_KEY') else 'API key required',
        'Kalshi':'Public API; no key required for market reads',
        'Open-Meteo':'No key required for limited noncommercial use',
        'The Odds API':'API key configured' if os.getenv('ODDS_API_KEY') else 'API key required',
    }
