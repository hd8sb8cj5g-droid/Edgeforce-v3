"""Historical NFL anytime-touchdown scorer *research* (not calibrated probabilities).

No passing touchdowns are credited to QB scorers. Only pre-week NFLverse player
logs are used; past-week reports do not leak future games. Per-game players may
be missing from the feed and injury/depth chart status is NOT verified.
"""
from __future__ import annotations
import math
import pandas as pd
from . import nfl_schedule

ROLE_PRIOR = {'RB': .32, 'FB': .16, 'WR': .23, 'TE': .18, 'QB': .10}
ROLE_MIN_OPPORTUNITY = {'RB': 1.0, 'FB': 1.0, 'WR': 1.0, 'TE': 1.0, 'QB': 1.0}


def prepare_player_rows(stats, season, before_week):
    """Filter to known history before requested week, dedupe player/week records."""
    if stats is None or not isinstance(stats, pd.DataFrame) or stats.empty:
        return pd.DataFrame()
    df = stats.copy()
    required = {'season', 'week', 'player_display_name', 'position', 'rushing_tds', 'receiving_tds'}
    if required - set(df.columns):
        return pd.DataFrame()
    team_col = 'team' if 'team' in df.columns else 'recent_team' if 'recent_team' in df.columns else None
    if not team_col:
        return pd.DataFrame()
    df['season'] = pd.to_numeric(df['season'], errors='coerce')
    df['week'] = pd.to_numeric(df['week'], errors='coerce')
    df = df[(df.season == int(season)) & (df.week < int(before_week)) & (df.week >= 1)].copy()
    if 'season_type' in df:
        df = df[df.season_type.astype(str).str.upper().isin(['REG','REGULAR'])]
    df['position'] = df.position.fillna('').astype(str).str.upper()
    df = df[df.position.isin(ROLE_PRIOR)].copy()
    df['team_key'] = df[team_col].apply(nfl_schedule.normalize_team)
    df['player_display_name'] = df.player_display_name.fillna('').astype(str).str.strip()
    df = df[(df.team_key != '') & (df.player_display_name != '')]
    if df.empty:
        return df
    df['player_key'] = df.player_id.astype(str) if 'player_id' in df else df.player_display_name.str.casefold()
    df = df.drop_duplicates(subset=['season','week','player_key','team_key'], keep='last')
    for c in ('rushing_tds','receiving_tds','carries','targets','rushing_yards','receiving_yards'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).clip(lower=0) if c in df else 0.
    return df.sort_values(['season','week'])


def summarize_schemes(pbp, season, before_week):
    """Compute observed pass/run and red-zone tendencies; NOT man/zone coverages."""
    if pbp is None or not isinstance(pbp, pd.DataFrame) or pbp.empty:
        return {}
    need = {'posteam','defteam','week','season'}
    if need - set(pbp.columns):
        return {}
    df = pbp.copy()
    df['week'] = pd.to_numeric(df.week,errors='coerce')
    df['season'] = pd.to_numeric(df.season,errors='coerce')
    df = df[(df.season == int(season)) & (df.week < int(before_week))]
    if 'season_type' in df:
        df=df[df.season_type.astype(str).str.upper() == 'REG']
    if 'pass_attempt' in df and 'rush_attempt' in df:
        pas = pd.to_numeric(df.pass_attempt, errors='coerce').fillna(0) > 0
        run = pd.to_numeric(df.rush_attempt, errors='coerce').fillna(0) > 0
    elif 'play_type' in df:
        pas = df.play_type.astype(str).eq('pass')
        run = df.play_type.astype(str).eq('run')
    else:
        return {}
    df['is_pass'] = pas
    df['is_run'] = run
    df = df[df.is_pass | df.is_run].copy()
    if df.empty:
        return {}
    df['red_zone'] = pd.to_numeric(df.get('yardline_100',pd.Series(index=df.index,dtype=float)),errors='coerce') <= 20
    result = {}
    for team, g in df.groupby('posteam'):
        team = nfl_schedule.normalize_team(team)
        rz = g[g.red_zone]
        result[team] = {
            'off_pass_rate': float(g.is_pass.mean()),
            'red_zone_pass_rate': float(rz.is_pass.mean()) if len(rz) >= 5 else None,
            'off_plays': int(len(g)),
        }
    for team, g in df.groupby('defteam'):
        team = nfl_schedule.normalize_team(team)
        v = result.setdefault(team, {})
        v['def_pass_rate_faced'] = float(g.is_pass.mean())
        v['def_plays'] = int(len(g))
    return result


def _defense_position_td_adjustment(hist, opponent, role):
    """Very small adjustment for positional TD allowed (historical, noisy)."""
    if 'opponent_team' not in hist or hist.empty:
        return 1.0
    data = hist[hist.opponent_team.astype(str).apply(nfl_schedule.normalize_team)==opponent]
    data = data[data.position==role]
    # Too small a sample to infer defensive positional weakness reliably.
    weeks = data.week.nunique()
    if weeks < 3:
        return 1.0
    allowed = (data.rushing_tds + data.receiving_tds).sum()/weeks
    baseline = {'RB': .65, 'WR': 1.0, 'TE': .38, 'QB': .15, 'FB': .05}[role]
    ratio = (allowed + 3*baseline)/(4*baseline)
    return min(1.12,max(.88,float(ratio)))


def _player_candidates(hist, team, opponent, summary, schemes, excluded):
    if hist.empty or 'team_key' not in hist.columns:
        return []
    team_rows=hist[hist.team_key==team]
    if team_rows.empty:
        return []
    result=[]
    for key, all_games in team_rows.groupby('player_key'):
        games=all_games.sort_values('week')
        recent=games.tail(6)
        last=games.iloc[-1]
        name=str(last.player_display_name)
        if name.casefold() in excluded or games.week.max() < hist.week.max()-3:
            continue
        role=str(last.position)
        n=len(recent)
        if n<2:
            continue
        # Athlete scoring equals rushing + receiving TDs, never passing TDs.
        scores=float((recent.rushing_tds+recent.receiving_tds).sum())
        td_rate=(scores+3*ROLE_PRIOR[role])/(n+3)
        carry=float(recent.carries.sum()/n)
        target=float(recent.targets.sum()/n)
        if carry+target<ROLE_MIN_OPPORTUNITY[role]:
            continue
        opportunity_rate=.040*carry+.055*target
        lambda_value=.55*td_rate+.45*opportunity_rate
        if summary:
            lambda_value*=min(1.2,max(.8,float(summary.get('projected_points',22.5))/22.5))
        off=schemes.get(team,{})
        de=schemes.get(opponent,{})
        pass_rate=off.get('red_zone_pass_rate')
        if pass_rate is None:pass_rate=off.get('off_pass_rate')
        # Historical play calling and game script, no unverified coverage claims.
        scheme_factor=1.0
        if pass_rate is not None:
            scheme_factor+= max(-.08,min(.08,(float(pass_rate)-.55)*.3))*(1 if role in ('WR','TE') else -1)
        faced=de.get('def_pass_rate_faced')
        if faced is not None:
            scheme_factor+=max(-.035,min(.035,(float(faced)-.55)*.15))*(1 if role in ('WR','TE') else -1)
        # Illustrative game-script tilt: a projected lead favors rushing
        # opportunities, while trailing scripts favor receiving usage.
        margin=max(-10.,min(10.,float(summary.get('expected_margin',0))))
        flow_multiplier=1.0 + (.006*margin if role in ('RB','FB') else
                               -.004*margin if role in ('WR','TE') else 0.)
        lambda_value*=scheme_factor*flow_multiplier*_defense_position_td_adjustment(hist,opponent,role)
        lambda_value=max(.001,min(1.5,lambda_value))
        score_prob=1-math.exp(-lambda_value)
        result.append({'player':name,'team':team,'position':role,'opponent':opponent,
                       'historical_games':n,'recent_td':int(scores),
                       'avg_targets':round(target,1),'avg_carries':round(carry,1),
                       'opportunity_index':round(score_prob*100,1),
                       'observed_scheme':bool(off or de),
                       'player_key':str(key)})
    return sorted(result,key=lambda x:(-x['opportunity_index'],-x['recent_td'],x['player']))


def weekly_scorer_board(schedule, stats, season, week, pbp=None, excluded_players=None,
                        team_points=None):
    """Top three observed offensive touchdown candidates per team for ALL week's games.

    Only historical games before selected week are used. No injury certification.
    Missing sources produce missing candidates rather than made-up player names.
    """
    if schedule is None or not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return {'games':[],'warnings':['Load a complete NFL schedule first.']}
    hist=prepare_player_rows(stats,season,week)
    df=schedule.copy()
    df['season']=pd.to_numeric(df.season,errors='coerce')
    df['week']=pd.to_numeric(df.week,errors='coerce')
    df=df[(df.season==season)&(df.week==week)&(df.game_type.astype(str).str.upper().isin(['REG','REGULAR']))] if 'game_type' in df else df[(df.season==season)&(df.week==week)]
    if 'kickoff_utc' in df:df=df.sort_values('kickoff_utc')
    schemes=summarize_schemes(pbp,season,week)
    excluded={str(name).casefold() for name in (excluded_players or [])}
    games=[]
    for _,row in df.iterrows():
        home=nfl_schedule.normalize_team(row.home_team)
        away=nfl_schedule.normalize_team(row.away_team)
        picks={}
        for team,other in ((away,home),(home,away)):
            pts=(team_points or {}).get(team,22.5)
            opposing_pts=(team_points or {}).get(other,22.5)
            picks[team]=_player_candidates(hist,team,other,
                {'projected_points':pts,'expected_margin':float(pts)-float(opposing_pts)},schemes,excluded)[:3]
        games.append({'matchup':f'{away} @ {home}', 'week':int(week),
                      'kickoff':str(row.get('kickoff_utc',row.get('gameday',''))),
                      'away':away,'home':home,'picks':picks})
    warnings=[]
    if hist.empty:
        warnings.append('No eligible pre-week NFLverse player game logs; players are not guessed. Load current-season player stats.')
    if not schemes:
        warnings.append('Play-by-play tendencies not loaded; scorer ranking uses historical TDs and touches only.')
    if games and any(len(g['picks'][team])<3 for g in games for team in (g['home'],g['away'])):
        warnings.append('Some teams have fewer than three qualifying recent participants; check injuries, roster moves and available logs.')
    warnings.append('Research-only opportunity index, not a calibrated touchdown probability or verified injury/starting-lineup report.')
    return {'games':games,'warnings':warnings,'season':season,'week':week,
            'with_schemes':bool(schemes),'historical_rows':len(hist)}


def best_anytime_td_quote(quotes, player_name, home, away):
    """Return actual same-matchup fresh YES anytime-TD quote if already synced.

    This is NOT EV: one-sided touchdown prices are not model-calibrated.
    """
    from .models import team_key
    found=[]
    for q in quotes or []:
        if q.get('sport')!='NFL' or q.get('market')!='player_anytime_td':
            continue
        if nfl_schedule.normalize_team(team_key(q.get('home_team'), 'NFL')) != home:
            continue
        if nfl_schedule.normalize_team(team_key(q.get('away_team'), 'NFL')) != away:
            continue
        participant=str(q.get('participant') or '').strip().casefold()
        outcome=str(q.get('selection') or '').strip().casefold()
        if participant and participant != player_name.strip().casefold():
            continue
        if participant and outcome not in ('yes','over',player_name.strip().casefold()):
            continue
        if not participant and outcome != player_name.strip().casefold():
            continue
        try:price=int(q['american_odds'])
        except (ValueError,KeyError,TypeError):continue
        found.append((price, q))
    return max(found,key=lambda x:x[0])[1] if found else None
