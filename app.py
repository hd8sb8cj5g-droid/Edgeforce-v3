"""EdgeForce v0.11 — resilient Neon and login-ready football data.
Run with: streamlit run app.py
"""
import os
import hmac
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
st.set_page_config(page_title='EdgeForce | Football Intelligence',page_icon='🏈',layout='wide',initial_sidebar_state='collapsed')

st.markdown('''<style>
/* EdgeForce Daylight: high-contrast, mobile-first light appearance. */
:root { color-scheme: light; }
.stApp, [data-testid="stAppViewContainer"] {
    background: #F7F9FC !important;
    color: #17263B !important;
}
[data-testid="stHeader"] { background: rgba(247,249,252,0.96) !important; }
[data-testid="stSidebar"] {
    background: #EDF3F8 !important;
    border-right: 1px solid #CBD8E5;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
    color: #334A5C;
}
h1,h2,h3,h4,[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,[data-testid="stMarkdownContainer"] h3 {
    color: #15263B !important;
    letter-spacing: -.025em;
}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: #24384E;
}
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {
    color: #42546B !important;
}
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #CBD8E5;
    border-left: 4px solid #0A667A;
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: 0 2px 8px rgba(20, 43, 70, .035);
}
[data-testid="stMetricValue"] { color: #15263B; }
[data-testid="stMetricLabel"] { color: #42546B; }
.stButton button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #086476 !important;
    color: #FFFFFF !important;
    border: 1px solid #086476 !important;
    font-weight: 650;
}
.stButton button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background: #064C60 !important;
    color: #FFFFFF !important;
    border-color: #064C60 !important;
}
.stButton button[kind="secondary"],
[data-testid="stBaseButton-secondary"] {
    background: #FFFFFF;
    color: #17344A;
    border: 1px solid #A9BED0;
}
.stButton button[kind="secondary"]:hover,
[data-testid="stBaseButton-secondary"]:hover {
    background: #EAF3F8;
    border-color: #086476;
    color: #064C60;
}
button:focus-visible, a:focus-visible,
input:focus-visible, textarea:focus-visible {
    outline: 3px solid #0B6D80 !important;
    outline-offset: 2px;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    color: #15263B !important;
    background: #FFFFFF !important;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: #FFFFFF;
    border: 1px solid #CBD8E5;
    border-radius: 10px;
    max-width: 100%;
}
[data-baseweb="tab-list"] {
    overflow-x: auto; overflow-y: hidden; scrollbar-width: thin;
    padding: 4px; gap: 4px; border-bottom: 2px solid #CBD8E5;
    background: #FFFFFF; border-radius: 10px 10px 0 0;
}
[data-baseweb="tab-list"] button[role="tab"] {
    min-height: 46px; min-width: fit-content; padding: 8px 14px;
    font-weight: 650; border-radius: 8px; flex-shrink: 0;
}
[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] {
    background: #E7F3F7; border-bottom: 3px solid #086476;
    color: #064C60 !important;
}
button[role="tab"] { white-space: nowrap; color: #42546B !important; }
button[role="tab"][aria-selected="true"] { color: #075D71 !important; }
.muted { color: #42546B; font-size: .88rem; }
.banner {
    border: 1px solid #B7D4DF;
    border-left: 4px solid #086476;
    padding: 14px 18px;
    border-radius: 10px;
    background: #E7F3F7;
    color: #163A4E;
    margin-bottom: 16px;
    line-height: 1.55;
}
@media (max-width: 700px) {
  .block-container {
    padding-top: 0.65rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
    padding-bottom: 2rem;
  }
  h1 { font-size: 1.65rem !important; line-height: 1.25; }
  h2 { font-size: 1.3rem !important; }
  div[data-testid="stMetric"] { padding: 9px 10px !important; min-width: 0; }
  [data-testid="stMetricValue"] { font-size: clamp(1.1rem, 4.5vw, 1.55rem); }
  .banner { padding: 11px 12px; font-size: .9rem; }
  .stButton button { min-height: 44px; }
  [data-testid="stDataFrame"] { max-width: 100%; overflow-x: auto; }
  button[role="tab"] { font-size: .9rem; padding-left: .65rem; padding-right: .65rem; }
  [data-baseweb="tab-list"] { scroll-snap-type: x proximity; }
  [data-baseweb="tab-list"] button[role="tab"] { scroll-snap-align: start; }

}
</style>''',unsafe_allow_html=True)

def secret(name):
    # Preserve boolean `false` from Streamlit TOML (do not mistake it for an
    # absent setting, which could accidentally enable paid odds syncing).
    try:
        val=st.secrets.get(name,None)
        if val is not None and val!='':
            return str(val)
    except Exception:
        pass
    return str(os.getenv(name,'') or '')

# Credentials and database URL are injected server-side only. No repo secrets.
for _name in ('ODDS_API_KEY', 'CFBD_API_KEY', 'EDGEFORCE_POSTGRES_URL'):
    if secret(_name):
        os.environ[_name] = secret(_name)

# Auth gate is required whenever a durable database is attached.
_access_password=secret('APP_PASSWORD')
if any(secret(k) for k in ('ODDS_API_KEY','CFBD_API_KEY','EDGEFORCE_POSTGRES_URL')) and not _access_password:
    st.error('Set APP_PASSWORD in Streamlit Cloud secrets before exposing API-connected EdgeForce to the internet.')
    st.stop()
if _access_password and not st.session_state.get('edgeforce_authenticated'):
    st.title('🏈 EdgeForce Private Access')
    with st.form('edgeforce_login'):
        entry=st.text_input('App password',type='password')
        go=st.form_submit_button('Unlock EdgeForce',type='primary',use_container_width=True)
    if go:
        if hmac.compare_digest(entry,_access_password):
            st.session_state['edgeforce_authenticated']=True
            st.rerun()
        else:
            st.error('Incorrect access password.')
    st.stop()

from edgeforce import db, providers, models, parlays, ledger, value, nfl_schedule, prop_market
from edgeforce import opportunities, portfolio, td_scorers, command_center, game_hub, injury_intelligence, accuracy_feedback, login_bootstrap

PAGES=['Market Scanner','Player Prop Lab','Matchup Intelligence','Touchdown Scorers','Parlay Builder','Performance Tracker']
TAB_LABELS=['🏠 Today','🏟 Game Hub','📈 Markets','🏈 Player Props','🧠 Matchups','🎯 TD Scorers','🎟 Parlays','📊 Performance']


def section_guide(title, steps, note):
    """Clear, consistent first-steps guide at the top of every workspace tab."""
    with st.container(border=True):
        st.markdown(f'### {title}')
        st.markdown('**How to use this section**')
        st.markdown('\n'.join(f'{i}. {step}' for i,step in enumerate(steps,1)))
        st.caption(note)

@st.cache_resource(show_spinner=False)
def boot_database(backend):
    db.init_db()
    return True

try:
    boot_database(db.backend_name())
except Exception as exc:
    st.error(f'Database temporarily unavailable ({type(exc).__name__}). Historical records have not been modified.')
    st.info('Neon may be waking up or the connection could be incorrect. Retry below. If it persists, check Streamlit Manage app → Logs and verify EDGEFORCE_POSTGRES_URL in Streamlit Secrets. Do not paste the URL into chat.')
    if st.button('↻ Retry database connection',type='primary'):
        boot_database.clear()
        st.rerun()
    st.stop()
now=datetime.now(timezone.utc)



@st.cache_data(ttl=900,show_spinner=False)
def cached_nfl_injury_raw(year):
    try:
        return providers.nfl_injury_reports(year), None
    except providers.ProviderError as exc:
        return None, f'Injury feed unavailable ({type(exc).__name__}). Check NFLverse or try again later.'


@st.cache_data(ttl=180,show_spinner=False)
def game_injury_report(season,week):
    if not (season and week):
        return {'season':season,'week':week,'status':'MISSING','players':[],
                'source':'NFLverse','warning':'Game week unknown; injury status cannot be verified.'}
    raw,error=cached_nfl_injury_raw(int(season))
    report=injury_intelligence.prepare_reports(raw,int(season),int(week),asof=datetime.now(timezone.utc))
    if error:report['warning']=error
    return report


def quote_week(q):
    if q.get('sport')!='NFL':return None,None
    kickoff=db.parse_utc(q.get('commence_time'))
    if kickoff is None:return None,None
    season=game_hub.nfl_season_for_date(kickoff)
    schedule=st.session_state.get('nfl_schedule_df')
    if schedule is None or getattr(schedule,'empty',True) or st.session_state.get('nfl_schedule_year')!=season:
        schedule=fetch_daily_schedule(season)
    if schedule is None or getattr(schedule,'empty',True):return season,None
    home=game_hub.team_code(q.get('home_team'),'NFL')
    away=game_hub.team_code(q.get('away_team'),'NFL')
    matches=[]
    for g in schedule.to_dict('records'):
        try:
            if int(g.get('season'))!=season:continue
            if game_hub.team_code(g.get('home_team'),'NFL')!=home:continue
            if game_hub.team_code(g.get('away_team'),'NFL')!=away:continue
            scheduled=db.parse_utc(g.get('kickoff_utc'))
            if scheduled and abs((scheduled-kickoff).total_seconds())<=24*3600:
                matches.append(int(g['week']))
        except (TypeError,ValueError,OverflowError,KeyError):continue
    return season,matches[0] if len(set(matches))==1 else None


def offer_injury_evidence(offer,game=None):
    q=offer.get('quote',offer)
    if q.get('sport')!='NFL':
        report={'status':'MISSING','source':'NFLverse','players':[]}
    elif game and game.get('week'):
        report=game_injury_report(game['season'],game['week'])
    else:
        season,week=quote_week(q)
        report=game_injury_report(season,week)
    return injury_intelligence.assess_offer(offer,report),report


def injury_notice(offer, game=None, show_healthy=False):
    assessment,_=offer_injury_evidence(offer,game)
    status=assessment['status']
    if status=='BLOCK':st.error('OUT · '+assessment['reason'])
    elif status=='HOLD':st.warning('HOLD · '+assessment['reason'])
    elif status=='REVIEW':st.caption('⚠️ INJURY REVIEW · '+assessment['reason'])
    elif status=='UNVERIFIED':st.caption('◯ STATUS UNVERIFIED · '+assessment['reason'])
    elif show_healthy:st.caption(assessment['reason'])
    if assessment['stress_ev_pct'] is not None:
        st.caption(f"{assessment['scenario']} probability stress → hypothetical EV {assessment['stress_ev_pct']:+.1f}% (not a validated injury model).")
    return assessment


def short_time(t):
    try:return pd.to_datetime(t,utc=True).strftime('%b %d %I:%M %p UTC')
    except Exception:return str(t)


def fmt_odds(v):return f'{int(v):+d}'


def safe_upcoming_quotes(sport=None):
    """Show a retryable database warning, never an unhandled mobile traceback."""
    try:
        return db.upcoming_quotes(sport)
    except Exception as exc:
        st.error(f'Live research temporarily unavailable: database connection failed ({type(exc).__name__}).')
        st.info('Your stored evidence is not deleted. Neon may be resuming from idle. Try again in a moment; if it persists, check Settings → Secrets and Manage app → Logs.')
        if st.button('↻ Reconnect to Neon',key='db_retry_now',type='primary'):
            st.rerun()
        st.stop()


def current_quotes(sport=None):
    """Latest observed offer for a side, including line changes, not every historic line."""
    from datetime import timedelta
    recent=[q for q in safe_upcoming_quotes(sport)
            if db.parse_utc(q['commence_time'])>now
            and db.parse_utc(q['observed_at'])>=now-timedelta(minutes=30)
            and q['source']!='SYNTHETIC DEMO']
    latest={}
    for q in recent:
        k=(q['event_id'],q['bookmaker'],q['market'],q['selection'],q.get('participant',''),q.get('point'))
        if k not in latest or db.parse_utc(q['observed_at'])>db.parse_utc(latest[k]['observed_at']):
            latest[k]=q
    # Avoid showing a previous line as if still offered when a book moves
    # the handicap or player-prop threshold in a subsequent API response.
    return opportunities.latest_active_batch(list(latest.values()))


def best_quotes(qs):
    best={}
    for q in qs:
        k=(q['event_id'],q['market'],q['selection'],q['point'],q.get('participant',''))
        if k not in best or q['american_odds']>best[k]['american_odds']:
            best[k]=q
    return list(best.values())


def projections_by_event(quotes):
    res={}
    summaries={}
    for sport in ('NFL','CFB'):
        games=st.session_state.get('nfl_games',[]) if sport=='NFL' else st.session_state.get('cfb_games',[])
        if games:summaries[sport]=models.team_summary(games,sport)
    for q in quotes:
        sport=q['sport']
        if sport not in summaries:continue
        summary=summaries[sport]
        projection=models.project_scores(q['home_team'],q['away_team'],sport,summary)
        if projection:res[q['event_id']]=projection
    return res


def quotes_frame(quotes,projs=None):
    projs=projs or {}; rows=[]
    for q in quotes:
        proj=projs.get(q['event_id']);p=models.probability(q,proj)
        rows.append({'Matchup':q['away_team']+' @ '+q['home_team'],
            'Kickoff (UTC)':short_time(q['commence_time']), 'Sport':q['sport'],
            'Book':q['bookmaker'],'Market':q['market'],'Selection':q['selection'],
            'Line':q['point'],'Participant':q.get('participant',''),'Price':fmt_odds(q['american_odds']),
            'Implied %':round(100*models.implied(q['american_odds']),1),
            'Model %':round(p*100,1) if p is not None else None,
            'Experimental EV %':round(100*models.ev_per_dollar(p,q['american_odds']),1) if p is not None else None,
            'Research grade':models.grade(q,proj,p),'Source':q['source'],
            'Observed (UTC)':short_time(q['observed_at']),
            'Book source updated':short_time(q.get('source_updated_at')) if q.get('source_updated_at') else 'Unknown'})
    return pd.DataFrame(rows)



def value_frame(opportunities):
    """Compact +EV feed built only from authentic, time-stamped market quotes."""
    result=[]
    for row in opportunities:
        q=row['quote']
        player_df=st.session_state.get('nfl_player_df') if q['sport']=='NFL' and q.get('participant') else None
        histories={}
        if player_df is not None and not player_df.empty and 'player_display_name' in player_df:
            player_rows=player_df[player_df['player_display_name'].str.casefold()==str(q.get('participant','')).casefold()]
            if 'game_date' in player_rows:
                player_rows=player_rows[pd.to_datetime(player_rows['game_date'],utc=True,errors='coerce')<now]
            elif 'season' in player_rows and 'week' in player_rows:
                # Current-season logs supplied by the public API contain played games.
                player_rows=player_rows.sort_values(['season','week'])
            histories=value.historical_hit_rates(q,player_rows.to_dict('records'))
        result.append({
            'Game':q['away_team']+' @ '+q['home_team'],
            'Bet':value.describe(row),
            'Sportsbook':q['bookmaker'],
            'Offered':fmt_odds(row['offered_odds']),
            'Fair odds*':fmt_odds(row['fair_american']),
            'Est. EV %*':round(row['ev_pct'],2),
            'Est. probability*':round(100*row['fair_probability'],2),
            'Ref. books':row['reference_count'],
            'Variation pp':round(row['variation_pp'],2),
            'Market':q['market'],
            'Updated UTC':short_time(q['observed_at']),
            'L5 hit rate¹':f"{histories[5]['hits']}/{histories[5]['games']}" if histories.get(5) else '—',
            'L10 hit rate¹':f"{histories[10]['hits']}/{histories[10]['games']}" if histories.get(10) else '—',
            'L20 hit rate¹':f"{histories[20]['hits']}/{histories[20]['games']}" if histories.get(20) else '—',
        })
    return pd.DataFrame(result)


def explain_ev_candidate(candidate, key_suffix=''):
    """One tap: quote provenance, fair-odds method, and downside scenario."""
    details=game_hub.explain_offer(candidate,now=datetime.now(timezone.utc))
    q=candidate['quote']
    with st.popover(f"ℹ️ Why this bet? · {value.describe(candidate)}"):
        # A popover can be opened within a collapsed game expander; nested expanders cannot.
        if not details['fresh']:
            st.warning('Quote no longer fresh. This is historical research, not a live opportunity.')
        st.markdown(f"**At {q['bookmaker']}: {details['offered']}** · Estimated fair {details['fair']} · EV **{details['ev_pct']:+.1f}%**")
        st.markdown(f"The offer breaks even at **{details['implied_pct']:.1f}%**, while independently sourced sportsbook prices imply **{details['fair_pct']:.1f}%** after removing margin (difference: {details['edge_pp']:+.1f} percentage points).")
        st.caption(f"**Why this ranked:** {details['reference_count']} independent reference books ({', '.join(details['references'])}); reference disagreement {details['variation_pp']:.1f} pp. Data quality: {details['quality']}.")
        st.markdown(f"**Sensitivity check:** If the estimated chance is 2 percentage points too high, theoretical EV becomes **{details['stress_ev_pct']:+.1f}%**. This is a scenario, not a confidence bound.")
        st.caption(f"Observed {details['quote_age_minutes']:.0f} minutes ago · {details['source']}")
        st.markdown('**What could invalidate this?**')
        for reason in details['warnings']:
            st.markdown('- '+reason)
        injury_notice(candidate)
        st.caption('Research only. These are market-derived price disagreements, not verified profitable bets. The available line may change.')


def display_value_feed(offers, prefix='main'):
    """Game-specific independent market-consensus candidate screening."""
    if not offers:
        st.info('No live sportsbook quotes to evaluate. Sync your league, then refresh player props for a particular game if supported by your API plan.')
        return
    with st.expander('⚙️ Advanced EV filters (optional)',expanded=False):
        c1,c2,c3=st.columns(3)
        with c1:min_ev=st.number_input('Minimum estimated EV %',min_value=0.,max_value=30.,value=1.,step=.5,key=prefix+'_ev')
        with c2:min_books=st.selectbox('Independent reference books',[2,3,1],index=0,key=prefix+'_refs',help='2+ is recommended. The candidate sportsbook never contributes to its own fair-price estimate.')
        with c3:max_variation=st.selectbox('Maximum reference disagreement',[2.,3.,5.,10.],index=2,key=prefix+'_var',format_func=lambda x:f'{x:g} percentage points')
    if min_books==1:
        st.warning('Only one independent reference book: more false positives are possible. Verify prices before acting.')
    candidates=value.scan(offers,now=now,min_references=min_books,min_ev_pct=min_ev,
                          max_reference_range_pp=max_variation)
    before=len(candidates)
    candidates=[c for c in candidates if offer_injury_evidence(c)[0]['status'] not in ('BLOCK','HOLD')]
    if before>len(candidates):
        st.warning(f'{before-len(candidates)} candidates held/excluded due to documented injury status. Check the Game Hub injury panel before using other plays.')
    # Games with zero qualifying opportunities remain visible rather than disappearing.
    all_games=sorted(set((q['event_id'],q['away_team']+' @ '+q['home_team']) for q in offers),key=lambda x:x[1])
    game_map={'All upcoming games':None}
    game_map.update({f'{name} · {eid[:6]}':eid for eid,name in all_games})
    c1,c2=st.columns([3,2])
    with c1:choice=st.selectbox('Find bets for each game',list(game_map),key=prefix+'_event')
    with c2:
        book_options=['All sportsbooks']+sorted(set(r['quote']['bookmaker'] for r in candidates))
        choose_book=st.selectbox('Betting sportsbook',book_options,key=prefix+'_book')
    bet_type_options=['Moneyline','Spread','Game total','Player prop']
    types=st.multiselect('Bet types to rank',bet_type_options,default=bet_type_options,key=prefix+'_types')
    def category(q):
        market=q['market']
        return 'Moneyline' if market=='h2h' else ('Spread' if market=='spreads' else ('Game total' if market=='totals' else 'Player prop'))
    selected=[r for r in candidates if (game_map[choice] is None or r['quote']['event_id']==game_map[choice])
              and (choose_book=='All sportsbooks' or r['quote']['bookmaker']==choose_book)
              and category(r['quote']) in types]
    if not selected:
        st.info('No qualifying positive-EV estimates for these settings. This is a legitimate result; it is better to show nothing than to invent an edge.')
        st.caption('Requires two-sided prices for the exact same player/line at the offered book AND independent reference books. One-sided anytime-TD markets are not currently scoreable.')
        with st.expander('Upcoming games checked'):
            for eid,name in all_games:st.write('— '+name)
        return
    a,b,c=st.columns(3)
    a.metric('Qualifying bet candidates',len(selected))
    b.metric('Games with candidates',len({r['quote']['event_id'] for r in selected}))
    c.metric('Highest estimated EV',f"{max(r['ev_pct'] for r in selected):+.1f}%")
    st.subheader('Best research candidates by game')
    st.caption('Positive EV means our market-based fair-price estimate is more favorable than the quoted offer—not that a wager is guaranteed to win.')
    st.caption('The game summaries show the strongest quote per distinct bet/side/line, instead of repeating the same wager at several sportsbooks.')
    grouped={}
    for r in selected:grouped.setdefault(r['quote']['event_id'],[]).append(r)
    absent=[name for eid,name in all_games if eid not in grouped and (game_map[choice] is None or game_map[choice]==eid)]
    if absent:
        with st.expander(f'No qualifying EV estimate: {len(absent)} other games'):
            for name in absent:st.write('— '+name)
    for eid,rows in grouped.items():
        q=rows[0]['quote']
        distinct={}
        for r in rows:
            offer=r['quote']
            k=(offer['market'],offer.get('participant',''),offer['selection'],offer.get('point'))
            if k not in distinct:distinct[k]=r
        distinct_rows=list(distinct.values())
        with st.expander(f"{q['away_team']} @ {q['home_team']} — {len(distinct_rows)} distinct bets ({len(rows)} book offers)",expanded=len(grouped)==1):
            for candidate in distinct_rows[:5]:
                q=candidate['quote']
                st.markdown(f"**{value.describe(candidate)}** — {q['bookmaker']} **{fmt_odds(candidate['offered_odds'])}** · Fair {fmt_odds(candidate['fair_american'])} · Est. EV **{candidate['ev_pct']:+.1f}%**")
                st.caption(f"Independent references: {', '.join(candidate['reference_books'])} · Disagreement: {candidate['variation_pp']:.1f} pp · Quote: {short_time(q['observed_at'])}")
                explain_ev_candidate(candidate)
            st.button('Open all analysis for this game →',key=f'game_from_{prefix}_{eid}',
                use_container_width=True,on_click=go_to_game_by_event,args=(eid,))
    with st.expander(f'View detailed +EV table ({len(selected)} offers)',expanded=False):
        st.dataframe(value_frame(selected).head(150),hide_index=True,use_container_width=True,
                     column_config={'Est. EV %*':st.column_config.NumberColumn(format='%.2f%%'),
                                    'Est. probability*':st.column_config.NumberColumn(format='%.2f%%')})
        st.caption('*Market-based estimated EV and fair odds are not calibrated forecasts. Historical L5/L10/L20 successes, where available, are descriptive only.')
    st.subheader('Save an auditable EV forecast')
    limit=selected[:100]
    labels={f"{i+1}. {r['quote']['away_team']} @ {r['quote']['home_team']} | {value.describe(r)} | {r['quote']['bookmaker']} {fmt_odds(r['offered_odds'])} | EV {r['ev_pct']:+.1f}%":r for i,r in enumerate(limit)}
    with st.expander('Log one candidate with its original offered odds and timestamp'):
        chosen=st.selectbox('Actual quoted offer',list(labels),key=prefix+'_choice')
        selected_bet=labels[chosen]
        st.write(f"Estimated fair win probability: **{selected_bet['fair_probability']:.1%}** from {selected_bet['reference_count']} independent books.")
        stake=st.number_input('Research stake ($)',min_value=1.,max_value=10000.,value=10.,step=1.,key=prefix+'_stake')
        note=st.text_input('Research notes (optional)',key=prefix+'_note',placeholder='Reason for monitoring this market')
        assessment,injury_record=offer_injury_evidence(selected_bet)
        injury_notice(selected_bet)
        if assessment['status'] in ('BLOCK','HOLD'):
            st.warning('Recording disabled for this injury-flagged recommendation. Refresh and confirm availability.')
        if st.button('Record immutable EV prediction',key=prefix+'_log',type='primary',
                     disabled=assessment['status'] in ('BLOCK','HOLD')):
            try:
                saved=db.log_prediction(selected_bet['snapshot_id'],selected_bet['fair_probability'],
                    selected_bet['quality'],'crossbook-market-proxy-v0.4-UNCALIBRATED',
                    f"Independent reference books: {', '.join(selected_bet['reference_books'])}; variation={selected_bet['variation_pp']:.3f} pp; quote offered={selected_bet['offered_odds']}; estimated EV={selected_bet['ev_pct']:.3f}%. {note}",
                    stake,tags=injury_intelligence.prediction_tags(assessment,injury_record))
                st.success('Auditable forecast saved: '+saved[:12]+'. See Performance Tracker for later closing price and outcome.')
            except (ValueError,KeyError) as e:st.error(str(e))
            except Exception as e:st.error('Could not save record ('+type(e).__name__+'). Verify database connection and quote freshness.')


def chart(player_df,metric,player_col='player_display_name',label='Player'):
    if player_df.empty or metric not in player_df:return
    d=player_df.copy()
    d[metric]=pd.to_numeric(d[metric],errors='coerce')
    d=d.sort_values(['season','week'] if 'season' in d and 'week' in d else list(d.columns)[:1])
    d['Game']=np.arange(1,len(d)+1)
    fig=px.bar(d,x='Game',y=metric,hover_data=[c for c in ('week','season','opponent_team') if c in d],
               title=f'{label} — {metric.replace("_"," ").title()} by game')
    fig.update_traces(marker_color='#086476', selector=dict(type='bar'))
    fig.update_layout(template='plotly_white',paper_bgcolor='#FFFFFF',plot_bgcolor='#FFFFFF',
                      font=dict(color='#24384E',size=13),title_font=dict(color='#15263B',size=17),
                      xaxis=dict(showgrid=False,linecolor='#CBD8E5'),
                      yaxis=dict(gridcolor='#DCE6F0',zerolinecolor='#CBD8E5'),
                      margin=dict(l=45,r=18,t=58,b=40),height=320)
    st.plotly_chart(fig,use_container_width=True)
    cols=st.columns(3)
    for col,n in zip(cols,(5,10,20)):
        data=d[metric].dropna().tail(n)
        col.metric(f'Last {n} games average', f'{data.mean():.1f}' if len(data) else '—',help=f'Observed {len(data)} games, not a projection')


with st.sidebar:
    st.markdown('## 🏈 EDGEFORCE')
    st.caption('FOOTBALL INTELLIGENCE • v0.11 AUTO-READY')
    st.caption('Storage: '+db.backend_name())
    st.divider()
    with st.expander('🔑 API credentials',expanded=False):
        st.caption('Server-side credentials stay hidden; enter a temporary override only if needed. Never paste keys into shared screenshots.')
        odds_override=st.text_input('The Odds API temporary override',value='',type='password',key='odds_key_input')
        cfbd_override=st.text_input('CollegeFootballData temporary override',value='',type='password',key='cfbd_key_input')
        odds_key=odds_override or secret('ODDS_API_KEY')
        cfbd_key=cfbd_override or secret('CFBD_API_KEY')
        st.link_button('Get CFBD key','https://collegefootballdata.com/')
        st.link_button('Get odds API key','https://the-odds-api.com/')
    usage=st.session_state.get('odds_usage',{})
    if usage and usage.get('remaining')!='not reported':
        st.caption(f"Odds API credits remaining: {usage['remaining']} · Last sync cost: {usage.get('last','?')}")
    with st.expander('🔬 Verify API connections',expanded=False):
        st.caption('Test keys through their actual providers. The Odds API sports-list test uses no market credits; CFBD makes a small game-data request.')
        if st.button('Test CFBD + Odds API credentials'):
            st.session_state['provider_checks']=providers.check_connections(cfbd_key,odds_key,year=now.year)
        for provider,entry in st.session_state.get('provider_checks',{}).items():
            st.write(('✅ ' if entry['connected'] else '❌ ')+provider+' — '+entry['detail'])
            if entry.get('credits_remaining') is not None:
                st.caption('Odds credits left: '+str(entry['credits_remaining']))
    with st.expander('📡 Data sources',expanded=False):
        for source,configured in [
            ('NFLverse','Public'),('CFBD','Key ready' if cfbd_key else 'Key required'),
            ('Kalshi','Public'),('Open-Meteo','Public'),
            ('The Odds API','Key ready' if odds_key else 'Key required')]:
            st.caption(f'**{source}:** {configured}')
        st.caption('Public ≠ recently checked. Use the sync buttons on each screen for a real request.')
    st.divider()
    with st.expander('✅ Login data status',expanded=False):
        if st.session_state.get('login_preload_results'):
            for item in st.session_state['login_preload_results']:
                st.caption(('✅ ' if item['status']=='Loaded' else '⚠️ ')+item['source']+': '+item['status']+' ('+item['detail']+')')
        else:
            st.caption('Sources load just after the first sign-in.')
        if st.button('↻ Reload dashboard sources',key='reload_all_sources'):
            st.session_state['login_preload_complete']=False
            st.session_state['login_manual_reload']=True
            st.rerun()
    st.caption('RESEARCH ONLY • EV IS MARKET-ESTIMATED, NOT VERIFIED PROFIT')
    st.caption('No wagers are placed through this application.')
    if st.session_state.get('cfb_team_records'):
        models.register_cfb_teams(st.session_state['cfb_team_records'])

st.title('🏈 EdgeForce v0.11')
st.caption('NFL + college football • Automatic login data prep • Resilient hosted storage • Swipe tabs on mobile')
if db.backend_name().startswith('SQLite'):
    st.warning('This deployment is using temporary SQLite storage. Cloud restarts may erase all logged odds and predictions. Add EDGEFORCE_POSTGRES_URL in Streamlit secrets for persistent tracking.')
st.markdown('<div class="banner"><strong>Start here:</strong> tap an upcoming game to see prices, player props, matchup context, touchdowns and parlays in one place. <strong>Check freshness before considering a bet.</strong></div>',unsafe_allow_html=True)


# Lazy top-level tabs: only the selected section executes. This avoids API calls,
# database work, and heavy table rendering in tabs the user has not opened.
workspace_tabs=st.tabs(TAB_LABELS,key='edgeforce_workspace_tab',on_change='rerun')


def open_workspace_tab(label):
    """Jump from the daily brief to an actual, tracked Streamlit tab."""
    st.session_state['edgeforce_workspace_tab']=label


def go_to_game(game_key):
    st.session_state['hub_selection']=game_key
    open_workspace_tab(TAB_LABELS[1])


def go_to_game_by_event(event_id):
    st.session_state['hub_focus_event']=event_id
    open_workspace_tab(TAB_LABELS[1])


@st.cache_data(ttl=3600,show_spinner=False)
def hub_player_logs(year):
    return providers.nfl_player_stats(year)


def fetch_daily_schedule(year, force=False):
    """Load NFLverse automatically once when needed, never at every rerun."""
    loaded=st.session_state.get('nfl_schedule_df')
    loaded_year=st.session_state.get('nfl_schedule_year')
    fetched_at=st.session_state.get('nfl_schedule_fetched_at')
    health=command_center.schedule_health(loaded,fetched_at,now)
    should_sync=force or loaded_year!=year or health['status'] in ('MISSING','STALE')
    # One auto attempt per session and season, even if provider is down.
    flag=f'daily_schedule_auto_{year}'
    if not force and (not should_sync or st.session_state.get(flag)):
        return loaded if loaded_year==year else None
    st.session_state[flag]=True
    try:
        raw=providers.nfl_games(year)
        normalized=nfl_schedule.prepare_schedule(raw,year,asof=now)
        st.session_state['nfl_schedule_df']=normalized
        st.session_state['nfl_schedule_year']=year
        st.session_state['nfl_schedule_fetched_at']=datetime.now(timezone.utc).isoformat()
        st.session_state['nfl_games']=models.scores_from_schedule(
            normalized[normalized.status=='Final'],asof=now)
        st.session_state.pop('daily_schedule_error',None)
        return normalized
    except (providers.ProviderError,ValueError,KeyError,TypeError) as exc:
        st.session_state['daily_schedule_error']=f'Schedule retrieval failed ({type(exc).__name__}). Refresh manually or try again later.'
        return loaded if loaded_year==year else None


# Prepare the dashboard once at authentication, not once for every Streamlit rerun.
# Cache large public statistics, and never preload all event-specific paid props.
@st.cache_data(ttl=3600,show_spinner=False)
def login_nfl_player_logs(season):
    return providers.nfl_player_stats(season)


@st.cache_data(ttl=3600,show_spinner=False)
def login_cfb_games(season):
    return providers.cfbd_games(season)


@st.cache_data(ttl=3600,show_spinner=False)
def login_cfb_teams(season):
    return providers.cfbd_teams(season)


@st.cache_data(ttl=600,show_spinner=False)
def login_kalshi_markets():
    return providers.kalshi_markets(pages=1,limit=100)


@st.cache_data(ttl=900,show_spinner=False)
def login_featured_quotes(sport):
    # Cache provider responses, not requests to the database. Manual refresh
    # buttons on the other tabs always remain available.
    return providers.odds_api(sport,key=secret('ODDS_API_KEY'),markets='h2h,spreads,totals')


def prepare_login_workspace():
    if st.session_state.get('login_preload_complete'):
        return
    year=game_hub.nfl_season_for_date(datetime.now(timezone.utc))
    cfb_year=datetime.now(timezone.utc).year
    force_reload=bool(st.session_state.pop('login_manual_reload',False))
    if force_reload:
        login_nfl_player_logs.clear()
        login_cfb_games.clear()
        login_cfb_teams.clear()
        login_kalshi_markets.clear()
        login_featured_quotes.clear()
        cached_nfl_injury_raw.clear()
        game_injury_report.clear()

    def load_schedule():
        schedule=fetch_daily_schedule(year,force=force_reload)
        if schedule is None or schedule.empty:
            raise RuntimeError('NFL schedule not available')
        return len(schedule)

    def load_players():
        players=login_nfl_player_logs(year)
        st.session_state['nfl_player_df']=players
        return len(players)

    def load_injuries():
        raw,error=cached_nfl_injury_raw(year)
        if error or raw is None:
            raise RuntimeError('NFL injury feed not available')
        schedule=st.session_state.get('nfl_schedule_df')
        week=nfl_schedule.active_week(schedule,asof=datetime.now(timezone.utc)) if schedule is not None and not schedule.empty else None
        if week:
            st.session_state['login_injury_report']=game_injury_report(year,week)
        return len(raw)

    def load_cfb():
        if not secret('CFBD_API_KEY'):
            raise RuntimeError('CFBD key not configured')
        games=login_cfb_games(cfb_year)
        st.session_state['cfb_raw']=games
        st.session_state['cfb_games']=models.scores_from_cfbd(games,asof=datetime.now(timezone.utc))
        return len(games)

    def load_cfb_directory():
        if not secret('CFBD_API_KEY'):
            raise RuntimeError('CFBD key not configured')
        teams=login_cfb_teams(cfb_year)
        st.session_state['cfb_team_records']=teams
        models.register_cfb_teams(teams)
        return len(teams)

    def load_saved_odds():
        quotes=db.upcoming_quotes()
        st.session_state['login_saved_quote_count']=len(quotes)
        return len(quotes)

    def load_featured(sport):
        if not secret('ODDS_API_KEY'):
            raise RuntimeError('Odds API key not configured')
        existing=db.upcoming_quotes(sport)
        if not login_bootstrap.should_sync_featured(existing,datetime.now(timezone.utc)):
            return len(existing)
        if str(secret('AUTO_SYNC_ODDS_ON_LOGIN') or 'true').lower() in ('false','no','off','0'):
            return len(existing)  # optional owner-controlled credit conservation
        quotes=login_featured_quotes(sport)
        if quotes:
            db.insert_snapshots(quotes)
            st.session_state['odds_usage']=providers.odds_usage()
        return len(quotes)

    def load_kalshi():
        markets=login_kalshi_markets()
        st.session_state['kalshi_data']=markets
        return len(markets)

    def load_history():
        history=db.prediction_history()
        st.session_state['login_prediction_count']=len(history)
        return len(history)

    tasks=[('NFL schedule',load_schedule),('NFL player statistics',load_players),
           ('NFL injury reports',load_injuries),('College football schedule',load_cfb),
           ('College football teams',load_cfb_directory),('Saved sportsbook markets',load_saved_odds),
           ('Featured NFL odds',lambda:load_featured('NFL')),
           ('Featured CFB odds',lambda:load_featured('CFB')),
           ('Kalshi football markets',load_kalshi),('Historical predictions',load_history)]
    st.markdown('### Preparing your football dashboard')
    st.caption('This runs once when you sign in. Paid game-specific player props and individual stadium weather remain on-demand to prevent excessive API usage.')
    bar=st.progress(0,text='Connecting data sources…')
    def on_progress(done,total,name):
        bar.progress(done/total,text=f'Checking {name} ({done}/{total})')
    report=login_bootstrap.load_once(st.session_state,tasks,progress=on_progress)
    bar.empty()
    if any(r['status']=='Unavailable' for r in report):
        st.warning('Some feeds could not be loaded. Available data is ready; see Login data status in the sidebar. No unverified picks will be generated.')
    else:
        st.success('Dashboard data loaded. Open any game to explore your research.')


# The first navigation render happens only after bounded login initialization.
prepare_login_workspace()


if workspace_tabs[0].open:
    with workspace_tabs[0]:
        section_guide('Your daily football briefing',
            ['Check the **Data readiness** panel before trusting any odds or statistics.',
             'Tap a game below to open its unified betting and matchup page.',
             'Tap **Open game breakdown** for all matchup research, or use the specialty tabs for a full-slate view.'],
            'Only verified upcoming-game sportsbook quotes are considered. EV is market-consensus research, not a calibrated profit forecast.')
        east_now=datetime.now(timezone.utc).astimezone(command_center.EASTERN)
        st.markdown(f"#### {east_now.strftime('%A, %B %d, %Y')} · NFL daily brief")
        st.caption('Times shown in Eastern Time. Featured odds are checked once at login when stale (unless disabled in Secrets); event-specific props remain on-demand and market requests spend API credits.')

        # Automatic public schedule lookup; never spend sportsbook credits on page load.
        schedule=fetch_daily_schedule(game_hub.nfl_season_for_date(now))
        st.markdown('### Data readiness')
        stored_quotes=safe_upcoming_quotes('NFL')
        price_status=command_center.sportsbook_health(stored_quotes,now)
        schedule_status=command_center.schedule_health(schedule,
            st.session_state.get('nfl_schedule_fetched_at') if schedule is not None else None,now)
        a,b,c=st.columns(3)
        a.metric('Upcoming NFL games',len(command_center.nfl_games_next_week(schedule,now,days=7,limit=32)))
        b.metric('NFL sportsbook odds',price_status['status'])
        c.metric('NFL schedule',schedule_status['status'])
        st.caption(f"**Odds:** {price_status['detail']}  **Schedule:** {schedule_status['detail']}")
        week_for_today=nfl_schedule.active_week(schedule,asof=now) if schedule is not None and not schedule.empty else None
        today_injury=game_injury_report(game_hub.nfl_season_for_date(now),week_for_today)
        st.caption(f"**Current-week injuries:** {today_injury['status']} · {len(today_injury.get('players',[]))} reported athletes · last source update {short_time(today_injury.get('latest_modified')) if today_injury.get('latest_modified') else 'unknown'}")
        if today_injury['status']!='FRESH':st.warning(today_injury['warning'])
        if st.button('↻ Refresh public injury report (no sportsbook credits)',key='today_refresh_injuries'):
            cached_nfl_injury_raw.clear()
            game_injury_report.clear()
            st.rerun()
        if price_status['status']=='LIMITED':
            st.info('Price coverage is limited: EdgeForce requires an offer plus two independent reference books to estimate EV.')
        if schedule is not None and not schedule.empty:
            try:
                issues=nfl_schedule.coverage(schedule)['warnings']
                if issues:
                    with st.expander('NFL schedule completeness warnings',expanded=False):
                        for issue in issues:st.warning(issue)
            except (KeyError,TypeError,ValueError):
                st.warning('NFL schedule structure could not be fully verified; review it in Matchups.')
        a,b=st.columns(2)
        with a:
            if st.button('↻ Refresh NFL schedule',key='home_reload_schedule',use_container_width=True):
                with st.spinner('Checking NFLverse schedule…'):
                    fetch_daily_schedule(game_hub.nfl_season_for_date(now),force=True)
                st.rerun()
        with b:
            if st.button('↻ Sync NFL odds',key='home_sync_nfl_odds',type='primary',use_container_width=True):
                if not odds_key:
                    st.warning('Odds API key missing. Add ODDS_API_KEY in Streamlit secrets.')
                else:
                    try:
                        with st.spinner('Downloading current NFL prices (uses API credits)…'):
                            saved=db.insert_snapshots(providers.odds_api('NFL',key=odds_key,markets='h2h,spreads,totals'))
                            st.session_state['odds_usage']=providers.odds_usage()
                        st.session_state['daily_sync_message']=f'Saved {len(saved)} NFL quote snapshots.'
                        st.rerun()
                    except (providers.ProviderError,ValueError,KeyError,TypeError) as exc:
                        st.error(f'NFL odds sync unavailable ({type(exc).__name__}). Check API coverage and remaining credits in the sidebar.')
        if st.session_state.pop('daily_sync_message',None):
            st.success('NFL odds synced. The latest available offers are now being screened.')
        if st.session_state.get('daily_schedule_error'):
            st.warning(st.session_state['daily_schedule_error'])


        with st.expander('Why is some data missing or stale?'):
            st.markdown('- **Sportsbook prices:** Expire after 30 minutes; expired prices are never shown as +EV opportunities. Sync NFL odds to obtain new quotes.\n'
                '- **Player props:** Must be requested for an individual game in Markets or Player Props; sportsbooks may not list every market.\n'
                '- **Schedule:** NFLverse is public but can be delayed. Refresh the NFLverse schedule with the button on this page.\n'
                '- **Injuries / starters:** NFLverse weekly reports refresh every 15 minutes while you use the app. This is not a confirmed inactive roster; check game-day actives.\n'
                '- **Historical tracker:** Requires PostgreSQL in Streamlit Cloud for durable records.')

        st.markdown('### Upcoming NFL games · next 7 days')
        games=command_center.nfl_games_next_week(schedule,now,days=7,limit=32)
        if games:
            st.caption('Tap a matchup to open its complete game page. Games are shown even when sportsbooks have no available odds.')
            home_catalog=game_hub.game_catalog(schedule,stored_quotes,now,days=7,sports=('NFL',))
            for g in home_catalog[:6]:
                st.button(f"🏈 {g['away']} @ {g['home']} · {g['kickoff_et']} →",key='home_match_'+g['key'],
                    use_container_width=True,on_click=go_to_game,args=(g['key'],))
            if len(home_catalog)>6:
                with st.expander(f'Show {len(home_catalog)-6} more upcoming games',expanded=False):
                    for g in home_catalog[6:]:
                        st.button(f"{g['away']} @ {g['home']} · {g['kickoff_et']} →",key='home_match_'+g['key'],
                            use_container_width=True,on_click=go_to_game,args=(g['key'],))
        else:
            st.info('No verified upcoming regular-season games in the next seven days, or the schedule is currently unavailable. Open Matchups for the full season.')

        st.markdown('### Top 3 +EV research opportunities')
        st.caption('Candidates are ranked by positive **market-consensus estimated EV**, using at least two independent reference sportsbooks. One opportunity per game; ranks do not imply proven profitability.')
        fresh_quotes=current_quotes('NFL')
        best=[r for r in command_center.rank_research_opportunities(fresh_quotes,now,limit=30)
              if offer_injury_evidence(r)[0]['status'] not in ('BLOCK','HOLD')][:3]
        if not price_status['fresh']:
            st.info('Live prices are missing or stale. Tap **Sync NFL odds** to screen the latest available markets.')
        elif not best:
            st.info('No qualifying EV opportunities in available NFL quotes. This can be normal—EdgeForce will not generate unsupported picks.')
        else:
            for ix,candidate in enumerate(best,1):
                q=candidate['quote']
                with st.container(border=True):
                    st.markdown(f"**#{ix} · {q['away_team']} @ {q['home_team']}**")
                    st.markdown(f"{value.describe(candidate)} · **{q['bookmaker']} {fmt_odds(candidate['offered_odds'])}**")
                    z1,z2,z3=st.columns(3)
                    z1.metric('Estimated EV*',f"{candidate['ev_pct']:+.1f}%")
                    z2.metric('Fair odds*',fmt_odds(candidate['fair_american']))
                    z3.metric('Reference books',candidate['reference_count'])
                    st.caption(f"Quote: {short_time(q['observed_at'])} · Fair win chance* {candidate['fair_probability']:.1%} · Other books disagree by {candidate['variation_pp']:.1f} pp")
                    explain_ev_candidate(candidate)
                    st.button('Open full game breakdown →',key=f'home_ev_game_{ix}',use_container_width=True,on_click=go_to_game_by_event,args=(q['event_id'],))
        st.caption('*Market-derived estimates, not calibrated predictions. Check the sportsbook for availability before wagering.')
        st.markdown('### Continue your research')
        a,b,c=st.columns(3)
        a.button('🏟 Game Hub',key='home_goto_markets',use_container_width=True,
                 on_click=open_workspace_tab,args=(TAB_LABELS[1],))
        b.button('🎯 TD Scorers',key='home_goto_td',use_container_width=True,
                 on_click=open_workspace_tab,args=(TAB_LABELS[5],))
        c.button('🎟 Parlays',key='home_goto_parlays',use_container_width=True,
                 on_click=open_workspace_tab,args=(TAB_LABELS[6],))

if workspace_tabs[1].open:
    with workspace_tabs[1]:
        section_guide('Everything about one game',
            ['Choose an NFL or CFB matchup; NFL games appear even before odds are posted.',
             'Review **Overview → Best Bets → Player Props → TD Scorers → Matchup → Parlays → Injuries**. Tap **Why this bet?** to see how any +EV estimate was derived.',
             'Use **Sync prices** or **Fetch player props** only when needed; both spend Odds API credits. Check freshness and injuries before using research.'],
            'Odds and projections are different sources. No game, quote, player or edge is fabricated when a provider has missing data.')
        load_now=datetime.now(timezone.utc)
        schedule=fetch_daily_schedule(game_hub.nfl_season_for_date(load_now))
        # Search both leagues: CFB events come from the odds provider; NFL
        # fixtures remain selectable even if no sportsbook prices are listed.
        hub_all_quotes=safe_upcoming_quotes()
        hub_games=game_hub.game_catalog(schedule,hub_all_quotes,load_now,days=14)
        if not hub_games:
            st.info('No upcoming NFLverse fixtures or saved NFL/CFB sportsbook events were found for the next 14 days. Refresh the NFL schedule on Today or sync the league in Markets.')
        else:
            hub_lookup={g['key']:g for g in hub_games}
            focus=st.session_state.pop('hub_focus_event',None)
            if focus:
                found=next((g for g in hub_games if g['event_id']==focus),None)
                if found:st.session_state['hub_selection']=found['key']
            selected=st.session_state.get('hub_selection')
            if selected not in hub_lookup:
                st.session_state['hub_selection']=hub_games[0]['key']
            def label_game(key):
                g=hub_lookup[key]
                return f"{g['sport']} · {g['away']} @ {g['home']} · {g['kickoff_et']}"
            game_key=st.selectbox('Open a game',list(hub_lookup),format_func=label_game,key='hub_selection')
            chosen_game=hub_lookup[game_key]
            filtered_quotes=game_hub.game_quotes(chosen_game,hub_all_quotes)
            health=game_hub.game_health(chosen_game,hub_all_quotes,now=load_now)
            ranked=game_hub.qualifying_game_bets(chosen_game,hub_all_quotes,now=load_now)
            prop_quotes=game_hub.raw_game_props(chosen_game,hub_all_quotes,now=load_now)
            hub_injuries=game_injury_report(chosen_game['season'],chosen_game.get('week')) if chosen_game['sport']=='NFL' else {'status':'MISSING','players':[],'warning':'CFB injury feed not yet supported.'}
            withheld=[offer for offer in ranked if offer_injury_evidence(offer,chosen_game)[0]['status'] in ('BLOCK','HOLD')]
            ranked=[offer for offer in ranked if offer_injury_evidence(offer,chosen_game)[0]['status'] not in ('BLOCK','HOLD')]
            st.markdown(f"### {chosen_game['away']} @ {chosen_game['home']}")
            st.caption(f"{chosen_game['sport']} · {chosen_game['kickoff_et']}"+
                       (f" · Week {chosen_game['week']}" if chosen_game['week'] else '')+
                       (' · kickoff time unverified' if not chosen_game['kickoff_verified'] else ''))
            c1,c2,c3=st.columns(3)
            c1.metric('Odds',health['status'])
            c2.metric('Qualified EV bets',len(ranked))
            c3.metric('Live prop quotes',len(prop_quotes))
            st.caption(f"Injury report: {hub_injuries['status']} · {len(hub_injuries.get('players',[]))} listed athletes · {len(withheld)} +EV candidates held or excluded. No injury-derived fair prices are fabricated.")
            if hub_injuries['status']!='FRESH':st.warning(hub_injuries.get('warning','Current injury status unavailable.'))
            if health['status'] in ('MISSING','STALE','LIMITED'):
                st.warning('This game has missing, old or limited sportsbook coverage. Quotes must be refreshed before treating them as currently available.')
            if st.button('↻ Sync game lines for this league',key='hub_sync_lines',use_container_width=True):
                if not odds_key:st.warning('Configure ODDS_API_KEY in Streamlit secrets.')
                else:
                    try:
                        with st.spinner('Refreshing league markets; uses API credits…'):
                            fetched=providers.odds_api(chosen_game['sport'],key=odds_key,markets='h2h,spreads,totals')
                            count=len(db.insert_snapshots(fetched))
                            st.session_state['odds_usage']=providers.odds_usage()
                        st.success(f'Saved {count} league quotes. This includes other games; reload to see the current matchup.')
                        st.rerun()
                    except providers.ProviderError as exc:
                        st.error('Sportsbook line sync failed: '+str(exc))
            hub_overview,hub_bets,hub_props,hub_td,hub_matchup,hub_parlays,hub_injury_tab=st.tabs([
                'Overview','⭐ Best Bets','Player Props','TD Scorers','Matchup','Parlays','🩹 Injuries'])
            with hub_injury_tab:
                st.markdown('#### Injury status and betting implications')
                st.caption('NFLverse weekly game statuses and practice reports; NOT a confirmed game-day inactive roster. No player is marked healthy because they are absent.')
                st.write(f"Report: **{hub_injuries['status']}** · Week {hub_injuries.get('week') or 'unknown'} · Source updated: {short_time(hub_injuries['latest_modified']) if hub_injuries.get('latest_modified') else 'Unavailable'}")
                if st.button('↻ Refresh injury reports',key='hub_refresh_injuries'):
                    cached_nfl_injury_raw.clear()
                    st.rerun()
                players_in_game=[p for p in hub_injuries.get('players',[])
                    if p['team'] in (chosen_game['away_code'],chosen_game['home_code'])]
                if players_in_game:
                    st.dataframe(pd.DataFrame([{'Team':p['team'],'Player':p['player'],'Position':p['position'],
                        'Game designation':p['status'] or 'Not specified', 'Practice':p['practice'] or 'Not specified',
                        'Injury':p['injury'],'Report updated':p['modified_at']} for p in players_in_game]),
                        hide_index=True,use_container_width=True)
                else:st.info('No available injury report entries for this matchup. This is not confirmation of healthy players.')
                if withheld:
                    st.markdown('##### Held or excluded market opportunities')
                    for offer in withheld[:12]:
                        st.write(value.describe(offer))
                        injury_notice(offer,chosen_game)
                st.caption('Player-specific OUT picks are suppressed; QUESTIONABLE/DOUBTFUL are held. No injury proxy is allowed to create a positive-EV price.')
            with hub_overview:
                st.markdown('#### Matchup at a glance')
                st.caption('The headline is evidence-first: fresh odds, qualifying price differences, and visible data gaps.')
                if ranked:
                    for i,offer in enumerate(ranked[:3],1):
                        q=offer['quote']
                        with st.container(border=True):
                            st.markdown(f"**#{i} · {value.describe(offer)}**")
                            st.markdown(f"{q['bookmaker']} **{fmt_odds(offer['offered_odds'])}** · Fair **{fmt_odds(offer['fair_american'])}** · Est. EV **{offer['ev_pct']:+.1f}%**")
                            explain_ev_candidate(offer)
                else:
                    st.info('No independently qualified positive-EV bets for this matchup right now. Open Best Bets to understand eligibility requirements.')
                st.caption(f"Data: {health['books']} fresh sportsbooks · {health['fresh_quotes']} fresh quotes · {len(prop_quotes)} fresh player prop prices. No prices are manufactured.")
                st.info('Touchdown opportunity scores, game projections, and sportsbook EV use different methods. A strong TD candidate is not automatically a +EV touchdown bet.')
                with st.expander('📋 My logged predictions for this matchup',expanded=False):
                    if not chosen_game['event_id']:
                        st.info('Historical predictions require a sportsbook event ID; sync sportsbook markets for this game first.')
                    else:
                        saved_game_picks=[r for r in ledger.performance_rows() if r.get('event_id')==chosen_game['event_id']
                            and r.get('sport')==chosen_game['sport']]
                        if not saved_game_picks:
                            st.info('No tracked predictions for this game yet. Log an eligible price in Markets to begin an auditable history.')
                        else:
                            st.dataframe(pd.DataFrame([{
                                'Placed at (UTC)':short_time(r['created_at']),
                                'Bet':f"{r['market']} · {r['selection']} {r.get('point') or ''}",
                                'Book':r['bookmaker'],'Locked odds':fmt_odds(r['american_odds']),
                                'Closing odds':fmt_odds(r['closing_american_odds']) if r.get('closing_american_odds') is not None else 'Not recorded',
                                'Outcome':r.get('outcome') or 'Pending'} for r in saved_game_picks[:40]]),
                                hide_index=True,use_container_width=True)
                            st.caption('Closing odds are shown only when a qualifying pre-kickoff snapshot was actually captured.')
            with hub_bets:
                st.markdown('#### Highest-ranked bets for this game')
                st.caption('Each bet must have a compatible two-sided market and at least two **independent** reference sportsbooks. Estimates reflect price consensus, not a proven win model.')
                if not ranked:
                    st.info('No qualifying EV prices found. Common causes: unlisted props, missing matching lines, too few independent books, stale prices, or a genuinely efficient market.')
                else:
                    for i,offer in enumerate(ranked[:20],1):
                        q=offer['quote']
                        with st.container(border=True):
                            st.markdown(f"**#{i} · {value.describe(offer)}**")
                            c1,c2,c3=st.columns(3)
                            c1.metric('Offered odds',fmt_odds(offer['offered_odds']))
                            c2.metric('Est. fair odds',fmt_odds(offer['fair_american']))
                            c3.metric('Est. EV',f"{offer['ev_pct']:+.1f}%")
                            st.caption(f"{q['bookmaker']} · {offer['reference_count']} reference books · observed {short_time(q['observed_at'])}")
                            explain_ev_candidate(offer)
                    with st.expander('Full filtered table',expanded=False):
                        st.dataframe(value_frame(ranked),use_container_width=True,hide_index=True)
                st.caption('Anytime-TD (one-sided) prices can be displayed in Props / Scorers, but do not receive a fabricated +EV estimate.')
            with hub_props:
                st.markdown('#### Compare actual player-prop lines')
                st.caption('Fetching a specific game costs provider credits and requires a sportsbook event ID. The raw quotes appear even if none qualifies for +EV.')
                if not chosen_game['event_id']:
                    st.info('No sportsbook event ID yet. Sync league lines above; a schedule-only NFL game cannot request player props until the Odds API lists it.')
                else:
                    prop_names=st.multiselect('Prop markets to fetch',list(providers.PROP_MARKETS),
                        default=['Passing yards','Rushing yards','Receiving yards','Receptions'],key='hub_prop_markets')
                    if st.button('Fetch player props for this game',key='hub_fetch_props',type='primary',use_container_width=True):
                        if not odds_key:st.warning('Configure ODDS_API_KEY in Streamlit secrets.')
                        elif not prop_names:st.warning('Select one or more prop types.')
                        else:
                            try:
                                with st.spinner('Requesting exact event props (costs API credits)…'):
                                    report=providers.odds_event_props(chosen_game['sport'],chosen_game['event_id'],
                                        key=odds_key,markets=[providers.PROP_MARKETS[name] for name in prop_names],return_report=True)
                                    saved=db.insert_snapshots(report['quotes'])
                                    st.session_state['odds_usage']=providers.odds_usage()
                                    st.session_state['hub_prop_report']={**report['report'],'saved_quotes':len(saved),
                                        'event_id':chosen_game['event_id']}
                                st.rerun()
                            except providers.ProviderError as exc:st.error('Player props unavailable: '+str(exc))
                    report=st.session_state.get('hub_prop_report')
                    if report and report.get('event_id')==chosen_game['event_id']:
                        st.caption(f"Most recent request: {report['quote_count']} returned · {report['saved_quotes']} saved · {report['book_count']} books · credits remaining {report.get('remaining_credits','unknown')}")
                        if report.get('missing_markets'):
                            st.warning('Markets without offers: '+', '.join(report['missing_markets']))
                    if prop_quotes:
                        compact=sorted(prop_quotes,key=lambda q:(str(q.get('participant','')),str(q['market']),str(q.get('selection',''))))
                        st.dataframe(pd.DataFrame([{'Player':q.get('participant') or q.get('selection'),
                            'Bet':q['market'].replace('player_','').replace('_',' ').title(),
                            'Side':q['selection'],'Line':q.get('point'),'Offered':fmt_odds(q['american_odds']),
                            'Book':q['bookmaker'],'Observed UTC':short_time(q['observed_at'])}
                            for q in compact[:300]]),use_container_width=True,hide_index=True)
                        st.caption('Prices are live-ish snapshots only while fresh. To see independently qualified EV prop bets, use Best Bets above.')
                    else:
                        st.info('No fresh player-prop prices stored for this event. Try a specific market nearer kickoff; provider subscriptions and book coverage vary.')
            with hub_td:
                st.markdown('#### Top offensive touchdown candidates · each team')
                if chosen_game['sport']!='NFL':
                    st.info('NFLverse touchdown-scorer research is currently NFL-only. We do not invent college player rankings.')
                elif not chosen_game.get('week') or schedule is None or schedule.empty:
                    st.info('This matchup lacks a verified NFLverse schedule week. Refresh the NFL schedule and try again.')
                else:
                    year=int(chosen_game['season'])
                    cached=st.session_state.get('hub_player_stats') if st.session_state.get('hub_player_year')==year else None
                    if cached is None:
                        st.info('Load this season’s NFLverse player logs once to see the top three for each team. This is a public source; no sportsbook credits are spent.')
                        if st.button('Load NFL player usage and touchdowns',key='hub_load_td_logs',use_container_width=True):
                            try:
                                with st.spinner('Loading historical NFLverse player stats…'):
                                    st.session_state['hub_player_stats']=hub_player_logs(year)
                                    st.session_state['hub_player_year']=year
                                st.rerun()
                            except Exception as exc:
                                st.error(f'NFLverse stats unavailable ({type(exc).__name__}). No rankings are fabricated.')
                    else:
                        with st.expander('Exclude players confirmed OUT (optional)',expanded=False):
                            excluded_text=st.text_input('Names separated by commas',key='hub_out_players',placeholder='Only players you independently confirmed OUT')
                        excluded=[name.strip() for name in excluded_text.split(',') if name.strip()]
                        excluded += [p['player'] for p in hub_injuries.get('players',[]) if p.get('is_current') and p['status'] in injury_intelligence.BLOCKED]
                        candidate_board=td_scorers.weekly_scorer_board(schedule,cached,year,int(chosen_game['week']),
                            pbp=st.session_state.get('td_scheme_df') if st.session_state.get('td_scheme_year')==year else None,
                            excluded_players=excluded)
                        entries=[g for g in candidate_board['games'] if g['home']==chosen_game['home_code']
                                 and g['away']==chosen_game['away_code']]
                        if not entries:
                            st.warning('Could not match this game to the NFLverse player board; check schedule and team names.')
                        else:
                            entry=entries[0]
                            for team in (entry['away'],entry['home']):
                                st.markdown(f"**{team} — Top three candidates**")
                                if not entry['picks'][team]:st.info('Insufficient historical player usage for this team.')
                                for i,player in enumerate(entry['picks'][team],1):
                                    st.markdown(f"{i}. **{player['player']}** ({player['position']}) · Opportunity index {player['opportunity_index']:.1f}/100")
                                    p_status=injury_intelligence.injury_player(hub_injuries,player['player'],team)
                                    if p_status and p_status['status'] in injury_intelligence.UNCERTAIN:
                                        st.warning(f"HOLD — {player['player']} listed {p_status['status']}; confirm active status.")
                                    elif p_status and p_status['practice'] in ('DNP','LIMITED'):
                                        st.caption(f"⚠️ Practice designation {p_status['practice']} — verify actives.")
                                    st.caption(f"Last {player['historical_games']} games: {player['recent_td']} rushing/receiving TDs, {player['avg_carries']} carries/game, {player['avg_targets']} targets/game")
                                    td_quote=td_scorers.best_anytime_td_quote(prop_quotes,player['player'],entry['home'],entry['away'])
                                    if td_quote:st.caption(f"Anytime TD listed: {fmt_odds(td_quote['american_odds'])} at {td_quote['bookmaker']} · quoted price, not confirmed +EV")
                            st.warning('These are heuristic opportunity rankings, not validated scoring probabilities. Injuries, starters, and specific man/zone coverages are not automatically checked.')
                            if not candidate_board['with_schemes']:st.caption('Historical play-by-play tendencies not loaded; the standalone TD Scorers tab can load the optional larger analysis.')
            with hub_matchup:
                st.markdown('#### Matchup and projected game flow')
                st.caption('Historical team scores and schedule context are descriptive. Game-score projections are simple, experimental baselines—not validated predictions.')
                if chosen_game['sport']=='NFL':
                    final_games=st.session_state.get('nfl_games') or []
                    team_history=models.team_summary(final_games,'NFL') if final_games else None
                else:
                    final_games=st.session_state.get('cfb_games') or []
                    team_history=models.team_summary(final_games,'CFB') if final_games else None
                projection=models.project_scores(chosen_game['home'],chosen_game['away'],chosen_game['sport'],team_history) if team_history else None
                if projection:
                    z1,z2=st.columns(2)
                    z1.metric(f"{chosen_game['away']} projected",f"{projection['away']:.1f}")
                    z2.metric(f"{chosen_game['home']} projected",f"{projection['home']:.1f}")
                    st.caption('Experimental scoring baseline only. Game flow, weather, injuries and defensive scheme evidence are not automatically included.')
                else:
                    st.info('No usable completed-game history for this team pairing. Load the historical NFL/CFB results in Matchups to see experimental projections.')
                epa=st.session_state.get('epa_table')
                if chosen_game['sport']=='NFL' and epa is not None and not getattr(epa,'empty',True) and 'posteam' in epa:
                    sample=epa[epa.posteam.isin([chosen_game['home_code'],chosen_game['away_code']])]
                    if not sample.empty:
                        st.caption('Optional previously loaded offense EPA/play from NFLverse:')
                        st.dataframe(sample,use_container_width=True,hide_index=True)
                st.caption('Detailed passing/rushing tendencies are available in TD Scorers. Never label a coverage scheme as observed without source evidence.')
            with hub_parlays:
                st.markdown('#### Parlays containing this game')
                st.caption('Shown from the latest already-generated portfolio, never generated using stale lines on opening a game.')
                cached_bundle=st.session_state.get('ev_v06_bundle')
                if cached_bundle and cached_bundle.get('created_at'):
                    try:
                        if (load_now-game_hub.utc(cached_bundle['created_at'])).total_seconds()>1800:
                            st.warning('The portfolio is over 30 minutes old; refresh game odds and regenerate in Parlays before treating listed legs as available.')
                    except (ValueError,TypeError):st.warning('Portfolio timestamp could not be verified. Regenerate in Parlays.')
                tickets=game_hub.tickets_containing_game(cached_bundle,chosen_game)
                if not tickets:
                    st.info('No saved portfolio containing this exact sportsbook game. Open Parlays to build five three-leg and five five-leg tickets from independently qualifying +EV bets.')
                for row in tickets:
                    ticket=row['ticket']
                    with st.container(border=True):
                        st.markdown(f"**{row['type']}-leg ticket #{row['index']} · {ticket['bookmaker']}**")
                        st.caption(f"Experimental hit-rate proxy {ticket['nominal_probability']:.1%} · theoretical price {ticket['decimal_price']:.2f}x")
                        for leg in row['legs']:
                            st.markdown(f"- **This game:** {value.describe(leg)} @ {fmt_odds(leg['offered_odds'])}")
                            explain_ev_candidate(leg)
                st.button('Open the full parlay optimizer →',on_click=open_workspace_tab,
                    args=(TAB_LABELS[6],),key='hub_open_parlays',use_container_width=True)


if workspace_tabs[2].open:
    with workspace_tabs[2]:
        section_guide('Find valuable market prices', ['Choose **NFL or CFB**, then tap **Sync sportsbook odds** to load current prices.', 'Open **Game-by-game +EV** to compare estimated fair odds with a sportsbook offer.', 'Select an upcoming matchup to fetch player props; check that quotes are fresh before logging a pick.'], 'Estimated EV relies on reference-book prices; it is not a proven advantage. Syncing markets uses Odds API credits.')

        a,b,c=st.columns([2,2,1])
        with a:sport=st.selectbox('League',['NFL','CFB'],key='scan_sport')
        with b:markets=st.multiselect('Markets',['h2h','spreads','totals'],default=['h2h','spreads','totals'])
        with c:
            st.write('')
            if st.button('↻ Sync sportsbook odds',type='primary',use_container_width=True):
                try:
                    with st.spinner('Fetching source quotes…'):
                        fetched=providers.odds_api(sport,key=odds_key,markets=','.join(markets))
                        count=len(db.insert_snapshots(fetched))
                        st.session_state['odds_usage']=providers.odds_usage()
                    st.session_state['last_odds_sync_status']=f'Stored {count} immutable quotes from The Odds API.'
                    st.rerun()
                except providers.ProviderError as e:st.error(str(e))
        if st.session_state.pop('last_odds_sync_status',None):
            st.success('Sportsbook odds synced. New prices have been added to the EV scanner.')
        if not st.session_state.get('nfl_games' if sport=='NFL' else 'cfb_games'):
            st.info('To activate matchup probabilities and experimental EV, load current-season results in Matchup Intelligence. Prices are available without model data.')
        all_sport_quotes=current_quotes(sport)
        quotes=[q for q in all_sport_quotes if q['market'] in markets]
        # A health banner is essential for unattended daily operation; old
        # snapshots remain for auditing, but are never presented as live EV.
        stored_for_sport=safe_upcoming_quotes(sport)
        if stored_for_sport:
            valid_ages=[]
            for record in stored_for_sport:
                try:valid_ages.append((now-db.parse_utc(record['observed_at'])).total_seconds()/60)
                except (TypeError,ValueError):pass
            age=min(valid_ages) if valid_ages else None
            if age is not None:
                if age<=30:
                    st.success(f'Data health: latest sportsbook collection {age:.0f} minutes ago · EV uses only recent pregame prices.')
                else:
                    st.warning(f'Data health: newest sportsbook quotes are {age:.0f} minutes old. Refresh odds to generate reliable EV opportunities. Older records remain in the historical tracker.')
        else:
            st.info('No archived sportsbook quotes. Use Sync sportsbook odds to initialize the scanner.')
        # Prop snapshots are included in EV research after an explicit event prop sync.
        ev_quotes=[q for q in all_sport_quotes if q['market'] in markets or q['market'].startswith('player_')]
        projections=projections_by_event(quotes)
        x,y,z=st.columns(3)
        x.metric('Unique upcoming games',len(set(q['event_id'] for q in quotes)))
        y.metric('Unique sportsbooks',len(set(q['bookmaker'] for q in quotes)))
        z.metric('Recorded quote snapshots',db.snapshot_counts()[0])
        tab0,tab1,tab2,tab3=st.tabs(['⭐ Game-by-game +EV','💰 Compare prices','📈 Odds history','🔄 Kalshi'])
        with tab0:
            st.caption('Scan each game for potentially mispriced offers. Excludes the offered book from the reference consensus and requires both sides at the same line.')
            if sport=='NFL':
                st.subheader('🏈 NFL game-by-game opportunity board')
                st.caption('Each matchup receives a transparent status. A game with no supported EV is not forced into a pick.')
                game_report=opportunities.group_game_opportunities(ev_quotes,now=now)
                if not game_report:
                    st.info('No fresh upcoming NFL market quotes. Sync NFL sportsbook odds to generate the game board.')
                else:
                    for game in game_report:
                        num=len(game['top'])
                        title=f"{game['away']} @ {game['home']} — {num} +EV candidates" if num else f"{game['away']} @ {game['home']} — No qualifying EV"
                        with st.expander(title,expanded=(len(game_report)==1)):
                            st.caption(f"Kickoff UTC: {short_time(game['kickoff'])} · {game['books']} sportsbooks · {game['prices']} priced selections")
                            if not num:
                                st.info('No eligible positive market-consensus EV. Possible reasons: price already efficient, fewer than 2 independent two-way reference sportsbooks, incompatible lines, or missing props.')
                            valid=[c for c in game['top'] if offer_injury_evidence(c)[0]['status'] not in ('BLOCK','HOLD')]
                            held=len(game['top'])-len(valid)
                            if held:st.warning(f'{held} nominal +EV candidates are held or excluded due to injury designations.')
                            for candidate in valid[:3]:
                                q=candidate['quote']
                                st.markdown(f"**{value.describe(candidate)}** · {q['bookmaker']} **{fmt_odds(candidate['offered_odds'])}** · Est. fair {fmt_odds(candidate['fair_american'])} · **EV {candidate['ev_pct']:+.1f}%**")
                                st.caption(f"Fair estimate {candidate['fair_probability']:.1%} · {candidate['reference_count']} independent references · recorded {short_time(q['observed_at'])}")
                                injury_notice(candidate)
            st.divider()
            st.caption('NFL/CFB main game lines are scanned automatically from stored snapshots; player props join the same game finder after explicit per-game retrieval.')
            upcoming={q['event_id']:q for q in quotes}
            if upcoming:
                with st.expander('🏈 Player props for a specific game — fetch, diagnose, compare',expanded=True):
                    game_labels={f"{q['away_team']} @ {q['home_team']} · {short_time(q['commence_time'])} · {eid[:6]}":eid for eid,q in upcoming.items()}
                    pick=st.selectbox('Choose matchup',list(game_labels),key='scan_props_event')
                    event_id=game_labels[pick]
                    status_key=f'{sport}:{event_id}'
                    if st.button('Check sportsbook-listed prop markets (costs 1 API credit)',key='scan_props_discover'):
                        try:
                            found=providers.odds_event_markets(sport,event_id,key=odds_key)
                            st.session_state.setdefault('prop_market_discovery',{})[status_key]=found
                            st.session_state['odds_usage']=providers.odds_usage()
                            if found:
                                st.success(f'Sportsbooks currently list {len(found)} market types for this game.')
                            else:
                                st.warning('No markets are currently listed by the provider for this event/region. This can happen before books post prices.')
                        except providers.ProviderError as e:st.error(str(e))
                    discovered=st.session_state.get('prop_market_discovery',{}).get(status_key)
                    if discovered is not None:
                        available={k:books for k,books in discovered.items() if k in providers.PROP_MARKETS.values()}
                        if available:
                            st.caption('Currently observed player-prop markets by sportsbook (availability is not guaranteed at fetch time):')
                            st.dataframe(pd.DataFrame([{'Market':next((name for name,key in providers.PROP_MARKETS.items() if key==code),code),
                                'Bookmakers':len(books),'Sportsbooks':', '.join(books)} for code,books in available.items()]),
                                hide_index=True,use_container_width=True)
                        else:
                            st.warning('The market-discovery response lists no supported player props for this game. It does not mean there will never be props; check closer to kickoff.')
                    default=['Passing yards','Rushing yards','Receiving yards','Receptions']
                    if discovered is not None:
                        names=[name for name,key in providers.PROP_MARKETS.items() if key in discovered]
                        if names:default=names[:4]
                    chosen_markets=st.multiselect('Prop markets to request',list(providers.PROP_MARKETS),
                        default=default,key='scan_props_markets')
                    st.caption('Fetch only the selected markets. Each event request can consume API credits; coverage depends on sportsbook and timing.')
                    if st.button('Fetch props for this game',key='scan_props_fetch',type='primary'):
                        if not chosen_markets:st.warning('Choose at least one market.')
                        else:
                            try:
                                result=providers.odds_event_props(sport,event_id,key=odds_key,
                                    markets=[providers.PROP_MARKETS[m] for m in chosen_markets],return_report=True)
                                saved=db.insert_snapshots(result['quotes'])
                                result['report']['saved_quotes']=len(saved)
                                st.session_state.setdefault('prop_fetch_reports',{})[status_key]=result['report']
                                st.session_state['odds_usage']=providers.odds_usage()
                                st.rerun()
                            except providers.ProviderError as e:st.error(str(e))
                    report=st.session_state.get('prop_fetch_reports',{}).get(status_key)
                    if report:
                        if report['quote_count']:
                            st.success(f"Retrieved {report['quote_count']} player-prop prices from {report['book_count']} sportsbooks; saved {report['saved_quotes']} audit snapshots.")
                        else:
                            st.warning('The provider returned zero offers for the selected prop markets. This is not a successful prop sync; check availability, event ID, and market coverage.')
                        missing=report.get('missing_markets',[])
                        if missing:
                            st.caption('Requested markets with no available prices: '+', '.join(missing))
                        st.caption(f"Last prop request cost: {report.get('last_request_cost', 'unknown')} credits · Remaining: {report.get('remaining_credits', 'unknown')}")
                    raw_props=[q for q in safe_upcoming_quotes(sport) if q['event_id']==event_id
                               and q['market'].startswith('player_')]
                    if raw_props:
                        detail=prop_market.summarize(raw_props,now)
                        c1,c2,c3=st.columns(3)
                        c1.metric('Saved prop prices',detail['raw_quotes'])
                        c2.metric('Players',detail['players'])
                        c3.metric('Sportsbooks',detail['bookmakers'])
                        st.caption('EV-screen diagnostics: '+detail['reason'])
                        st.caption('Raw prices include historical saved quotes. Only recent pregame quotes are eligible for EV analysis.')
                        st.dataframe(pd.DataFrame(prop_market.display_rows(raw_props)),
                            use_container_width=True,hide_index=True)
                    elif not report:
                        st.info('Select a matchup and fetch player props to see actual sportsbook offers; no prop prices are saved for this game.')
            else:
                st.info('Sync current sportsbook game lines first. The game selector uses the event IDs returned by The Odds API, not NFLverse schedule IDs.')
            display_value_feed(ev_quotes,prefix='scanner')
        with tab1:
            best=best_quotes(quotes)
            if best:
                st.caption('Provider odds are indicative snapshots and not confirmed accepted wagers; logging requires quotes observed within the last 30 minutes.')
                df=quotes_frame(best,projections)
                st.dataframe(df,hide_index=True,use_container_width=True)
                st.caption('Experimental EV derives from basic scoring averages and normal distributions. It is NOT a validated edge. Comparative prices can change rapidly.')
                labels={f"{q['away_team']} @ {q['home_team']} · {q['market']} {q['selection']} {q['point'] or ''} · {fmt_odds(q['american_odds'])} @ {q['bookmaker']} · {q['id'][:6]}":q for q in best}
                with st.expander('🧾 Log an immutable prediction from an actual quote'):
                    selected=st.selectbox('Locked quoted offer',list(labels))
                    q=labels[selected];p=models.probability(q,projections.get(q['event_id']))
                    st.caption(f"Source observed: {q['observed_at']}; quote: {fmt_odds(q['american_odds'])}; kickoff: {q['commence_time']}")
                    if p is None:
                        st.warning('No model projection loaded. Enter your own pre-event probability and it will be labeled user-supplied.')
                    chosen=st.number_input('Forecast probability (%)',min_value=1.0,max_value=99.0,
                                           value=float(round(p*100,1)) if p is not None else 50.0,step=.5)
                    stake=st.number_input('Hypothetical stake ($)',min_value=1.0,max_value=10000.,value=10.,step=1.)
                    note=st.text_input('Prediction rationale',placeholder='Scheme / injury / price thesis at time of forecast')
                    if st.button('Record locked prediction',type='primary'):
                        try:
                            model_tag='experimental-scoring-v0.1' if p is not None and abs(chosen/100-p)<.0006 else 'user-supplied-v0.1'
                            rec=db.log_prediction(q['id'],chosen/100,models.grade(q,projections.get(q['event_id']),p),
                                                  model_tag,note,stake)
                            st.success('Recorded prediction '+rec[:10]+' (offer and timestamp are locked).')
                        except Exception as e:st.error(str(e))
            else:st.info('No upcoming sportsbook prices stored for this league. Add your odds key and select “Sync sportsbook odds.”')
        with tab2:
            if quotes:
                st.dataframe(quotes_frame(quotes,projections),hide_index=True,use_container_width=True)
                event_options={f"{q['away_team']} @ {q['home_team']} ({q['event_id'][:7]})":q['event_id'] for q in quotes}
                chosen_event=st.selectbox('Inspect line history',list(event_options))
                event_rows=db.snapshots_for_event(event_options[chosen_event])
                if event_rows:
                    d=pd.DataFrame(event_rows)
                    d['quoted_decimal']=d['american_odds'].map(models.american_decimal)
                    d['line_id']=d['bookmaker']+' · '+d['market']+' · '+d['selection']+' '+d['point'].fillna('').astype(str)
                    fig=px.line(d,x='observed_at',y='quoted_decimal',color='line_id',markers=True,
                                color_discrete_sequence=['#086476','#B2512C','#563E9C','#2A6E46','#AB3759','#275EAA','#70510B'],
                                title='Recorded price history (identical selections / lines tracked separately)')
                    fig.update_layout(template='plotly_white',height=350,paper_bgcolor='#FFFFFF',plot_bgcolor='#FFFFFF',
                                      font=dict(color='#24384E',size=12),title_font=dict(color='#15263B',size=16),
                                      xaxis=dict(showgrid=True,gridcolor='#EDF2F7'),
                                      yaxis=dict(gridcolor='#DCE6F0',zerolinecolor='#CBD8E5'),
                                      legend=dict(font=dict(color='#24384E'),bgcolor='#FFFFFF'),
                                      margin=dict(l=45,r=18,t=58,b=45))
                    st.plotly_chart(fig,use_container_width=True)
            else:st.info('Snapshots will appear here after the first sportsbook sync.')
        with tab3:
            st.caption('Kalshi uses exchange contracts, which are not automatically equivalent to sportsbook moneylines or spreads. No naive cross-market arbitrage claims.')
            kalshi_series=st.text_input('Optional Kalshi series ticker (recommended)',placeholder='Enter an NFL/football series ticker')
            if st.button('Load public Kalshi market data'):
                try:
                    with st.spinner('Fetching read-only Kalshi quotes…'):
                        st.session_state['kalshi_data']=providers.kalshi_markets(kalshi_series or None,pages=3)
                    st.success(f"Found {len(st.session_state['kalshi_data'])} matching open markets; no Kalshi trading authorization requested.")
                except Exception as e:st.error(str(e))
            kdata=st.session_state.get('kalshi_data',[])
            if kdata:
                ks=pd.DataFrame(kdata)
                keep=[c for c in ('ticker','title','yes_bid_dollars','yes_ask_dollars','no_bid_dollars','volume_fp','close_time') if c in ks]
                st.dataframe(ks[keep],use_container_width=True,hide_index=True)
                t=st.selectbox('Inspect order book',[m['ticker'] for m in kdata])
                if st.button('Fetch order book'):
                    try:st.json(providers.kalshi_orderbook(t))
                    except Exception as e:st.error(str(e))
            elif 'kalshi_data' in st.session_state:st.info('No matching markets on sampled pages. Use the exact football series ticker for a targeted lookup.')


if workspace_tabs[3].open:
    with workspace_tabs[3]:
        section_guide('Research a player prop', ['Sync game lines first in **Markets**, then select a league and matchup here.', 'Choose available prop types and tap **Fetch actual player prop prices**.', 'Compare quoted lines and estimated EV; use NFL/CFB game-log sub-tabs for historical context.'], 'Not every sportsbook or subscription supplies player props. No quote means no recommended prop.')

        live,nfl,cfb=st.tabs(['Live player prop prices','NFL game logs','College football player logs'])
        with live:
            st.caption('Per-event requests consume The Odds API credits. Props require coverage on your API plan. These are actual quotes, not projections.')
            prop_sport=st.selectbox('League for player props',['NFL','CFB'],key='prop_sport')
            games={q['event_id']:q for q in current_quotes(prop_sport) if q['market'] in ('h2h','spreads','totals')}
            options={f"{q['away_team']} @ {q['home_team']} · {short_time(q['commence_time'])}":eid for eid,q in games.items()}
            if not games:
                st.info('First sync this league in Market Scanner to obtain live event identifiers.')
            else:
                selected_game=st.selectbox('Matchup',list(options),key='prop_game')
                prop_market_names=st.multiselect('Player prop markets',list(providers.PROP_MARKETS),
                    default=['Passing yards','Rushing yards','Receiving yards','Receptions'])
                if st.button('Fetch actual player prop prices',type='primary'):
                    if not prop_market_names:st.warning('Choose at least one prop market.')
                    else:
                        try:
                            result=providers.odds_event_props(prop_sport,options[selected_game],key=odds_key,
                                markets=[providers.PROP_MARKETS[x] for x in prop_market_names],return_report=True)
                            saved=db.insert_snapshots(result['quotes'])
                            st.session_state['odds_usage']=providers.odds_usage()
                            if saved:st.success(f'Recorded {len(saved)} real player prop quotes for the chosen event.')
                            else:st.warning('The sportsbook feed returned no prop quotes for those markets. Try checking currently listed markets in Market Scanner.')
                            st.caption(f"Odds API: {result['report']['book_count']} sportsbooks · missing requested markets: {', '.join(result['report']['missing_markets']) or 'none'}")
                        except providers.ProviderError as error:st.error(str(error))
                props=[q for q in current_quotes(prop_sport) if q['event_id']==options[selected_game]
                       and q['market'].startswith('player_')]
                if props:
                    if prop_sport=='NFL' and st.session_state.get('nfl_player_df') is None:
                        if st.button('Load NFLverse player game logs for L5/L10/L20 prop research',key='live_stats_load'):
                            try:
                                with st.spinner('Loading NFL player game logs…'):
                                    st.session_state['nfl_player_df']=providers.nfl_player_stats(now.year)
                                st.success('Loaded NFL player game logs. Historical results are context, not modeled probabilities.')
                            except providers.ProviderError as e:st.error(str(e))
                    st.subheader('Player prop +EV candidates — this game')
                    st.caption('Actual sportsbook odds only. Requires independent two-sided quotes for the exact player and prop line. No fabricated player projections.')
                    display_value_feed(props,prefix='prop_value')
                    st.subheader('Raw prop quotes and manual player research')
                    df=pd.DataFrame([{'Player':q.get('participant',''),'Market':q['market'],
                        'Side':q['selection'],'Line':q['point'],'American odds':q['american_odds'],
                        'Book':q['bookmaker'],'Observed UTC':q['observed_at'], 'Snapshot ID':q['id']}
                        for q in props])
                    st.dataframe(df.sort_values(['Player','Market','Line','Side','American odds'],
                        ascending=[True,True,True,True,False]),hide_index=True,use_container_width=True)
                    st.caption('The +EV candidates above are independent market-consensus estimates—not validated player-specific probabilities. Raw quotes below may include markets without adequate two-sided reference prices.')
                    with st.expander('Record player prop research prediction'):
                        labels={f"{q.get('participant','')} | {q['market']} | {q['selection']} {q['point'] or ''} | {q['bookmaker']} {fmt_odds(q['american_odds'])} · {q['id'][:6]}":q for q in props}
                        choice=st.selectbox('Exact quoted offer',list(labels))
                        user_p=st.number_input('Your forecast probability (%)',min_value=1.,max_value=99.,value=50.,step=.5,key='prop_p')
                        stake_prop=st.number_input('Tracked hypothetical stake ($)',min_value=1.,max_value=10000.,value=10.,step=1.,key='prop_stake')
                        reasoning=st.text_input('Reason and source of your probability',key='prop_reason')
                        if st.button('Log player prop forecast'):
                            if not reasoning.strip():st.error('Add the basis for the probability.')
                            else:
                                try:
                                    ident=db.log_prediction(labels[choice]['id'],user_p/100,'C','user-supplied-prop-v0.2',reasoning,stake_prop)
                                    st.success(f'Saved immutable player prop prediction {ident[:10]}. Settlement requires verified player stats or manual review.')
                                except ValueError as error:st.error(str(error))
        with nfl:
            y=int(st.number_input('Season',min_value=2010,max_value=now.year,value=now.year,step=1,key='player_year'))
            if st.button('↻ Load NFLverse player-game statistics'):
                try:
                    with st.spinner('Loading NFL player-game data…'):
                        st.session_state['nfl_player_df']=providers.nfl_player_stats(y)
                    st.success(f"Loaded {len(st.session_state['nfl_player_df'])} player-game rows.")
                except Exception as e:st.error(str(e))
            ps=st.session_state.get('nfl_player_df')
            if ps is not None and not ps.empty:
                names=sorted(ps['player_display_name'].dropna().unique())
                name=st.selectbox('Player',names,index=0)
                sub=ps[ps.player_display_name==name]
                numeric=[c for c in ('passing_yards','passing_tds','passing_interceptions','rushing_yards','rushing_tds',
                           'receiving_yards','receptions','receiving_tds','targets','carries') if c in sub]
                metric=st.selectbox('Player metric',numeric) if numeric else None
                if metric:
                    chart(sub,metric,label=name)
                    st.dataframe(sub[[c for c in ('week','opponent_team',metric,'season') if c in sub]].tail(20).sort_values('week',ascending=False),hide_index=True,use_container_width=True)
                    line=st.number_input('Explore a hypothetical prop line',min_value=0.,value=50.,step=5.)
                    vals=pd.to_numeric(sub[metric],errors='coerce').dropna().tail(20)
                    st.metric('Historical games above line (last 20 max)',f'{sum(vals>line)}/{len(vals)}')
                    st.caption('Historical frequencies are NOT probabilities, and are NOT current sportsbook offers. Props require event-odds access for price/EV comparisons.')
            else:st.info('Load the NFLverse player-game file to explore L5/L10/L20 charts. No key needed.')
        with cfb:
            st.caption('CFBD player game-log calls are scoped to one team to conserve the free API quota.')
            cy=int(st.number_input('CFB season',min_value=2000,max_value=now.year,value=now.year))
            team=st.text_input('Exact CFBD team name',value='Minnesota')
            if st.button('↻ Load CFBD player box scores'):
                try:
                    raw=providers.cfbd_player_stats(cy,team,cfbd_key)
                    records=[]
                    for game in raw:
                        for side in game.get('teams',[]):
                            for cat in side.get('categories',[]):
                                for typ in cat.get('types',[]):
                                    for player in typ.get('athletes',[]):
                                        records.append({'game_id':game.get('id'),'team':side.get('team'),
                                           'player':player.get('name'),'category':cat.get('name'),
                                           'metric':typ.get('name'),'value':player.get('stat')})
                    st.session_state['cfbd_player_df']=pd.DataFrame(records)
                    st.success(f'Parsed {len(records)} stat observations.')
                except Exception as e:st.error(str(e))
            cf=st.session_state.get('cfbd_player_df')
            if cf is not None and not cf.empty:
                who=st.selectbox('CFB player',sorted(cf['player'].dropna().unique()))
                part=cf[cf.player==who]
                name=st.selectbox('CFB metric',sorted(part['metric'].dropna().unique()))
                part=part[part.metric==name].copy()
                part['value']=pd.to_numeric(part.value.astype(str).str.replace(',','',regex=False),errors='coerce')
                part=part.dropna(subset=['value']).sort_values('game_id')
                if len(part):
                    part=part.reset_index(drop=True);part['Game']=np.arange(1,len(part)+1)
                    fig=px.bar(part,x='Game',y='value',title=who+' • '+name)
                    st.plotly_chart(fig,use_container_width=True)
                    cc=st.columns(3)
                    for c,n in zip(cc,(5,10,20)):c.metric(f'L{n} avg',f'{part.value.tail(n).mean():.1f}')
                    st.dataframe(part[['game_id','team','value']],hide_index=True)
                else:st.warning('This stat is not numeric; see raw observations.')
            else:st.info('Add a CFBD API key to load college player-game statistics.')


if workspace_tabs[4].open:
    with workspace_tabs[4]:
        section_guide('Compare team matchups', ['Choose **NFL or CFB**, then load the season schedule and results.', 'Review offensive/defensive indicators and available matchup projections.', 'Check weather and roster availability separately before making decisions.'], 'Projections are experimental and are not verified against current injury or starting-lineup reports.')

        col1,col2=st.columns(2)
        with col1:
            st.subheader('NFLverse schedule and results')
            yr=int(st.number_input('NFL season',2020,now.year,now.year,key='nfl_y'))
            if st.session_state.get('nfl_schedule_year')!=yr and not st.session_state.get('nfl_auto_attempted_'+str(yr)):
                st.session_state['nfl_auto_attempted_'+str(yr)]=True
                try:
                    with st.spinner('Automatically checking the current NFL schedule…'):
                        auto_raw=providers.nfl_games(yr)
                        auto_prepared=nfl_schedule.prepare_schedule(auto_raw,yr,asof=now)
                        st.session_state['nfl_schedule_df']=auto_prepared
                        st.session_state['nfl_schedule_year']=yr
                        st.session_state['nfl_games']=models.scores_from_schedule(
                            auto_prepared[auto_prepared.status=='Final'],asof=now)
                        st.session_state['nfl_schedule_fetched_at']=now.isoformat()
                    st.caption('NFL schedule loaded automatically. Use manual Sync to force an update.')
                except Exception as exc:
                    st.warning(f'Automatic NFL schedule unavailable ({type(exc).__name__}). You can retry with Sync NFLverse games.')
            if st.button('↻ Sync NFLverse games'):
                try:
                    with st.spinner('Loading full NFLverse schedule (all 18 weeks)…'):
                        raw=providers.nfl_games(yr)
                        prepared=nfl_schedule.prepare_schedule(raw,yr,asof=now)
                        summary=nfl_schedule.coverage(prepared)
                        st.session_state['nfl_schedule_df']=prepared
                        st.session_state['nfl_schedule_year']=yr
                        # Crucially, use ONLY final results; preserve honest training cutoff.
                        st.session_state['nfl_games']=models.scores_from_schedule(
                            prepared[prepared.status=='Final'],asof=now)
                        st.session_state['nfl_schedule_fetched_at']=now.isoformat()
                        st.session_state.pop('nfl_espn_check',None)
                    st.success(f"NFLverse {yr}: {summary['regular_games']} regular-season games across "
                               f"{len(summary['weeks'])} weeks; {len(st.session_state['nfl_games'])} finals available for analysis.")
                except Exception as e:st.error(str(e))
            with st.expander('NFL advanced EPA play-by-play'):
                if st.button('Load EPA play-by-play data (large download)'):
                    try:
                        with st.spinner('Downloading NFLverse play-by-play…'):
                            pbp=providers.nfl_playbyplay(yr)
                            pbp=pbp.dropna(subset=['posteam','epa'])
                            st.session_state['epa_table']=pbp.groupby('posteam',as_index=False).agg(epa_per_play=('epa','mean'),plays=('epa','size')).sort_values('epa_per_play',ascending=False)
                        st.success(f'Loaded {len(pbp):,} plays.')
                    except Exception as e:st.error(str(e))
                if st.session_state.get('epa_table') is not None:
                    st.dataframe(st.session_state['epa_table'],use_container_width=True,hide_index=True)
            if st.session_state.get('nfl_schedule_df') is not None and st.session_state.get('nfl_schedule_year')==yr:
                df=st.session_state['nfl_schedule_df']
                stats=nfl_schedule.coverage(df)
                active=nfl_schedule.active_week(df,asof=now)
                st.caption(f"Source: NFLverse · Last retrieved: {short_time(st.session_state.get('nfl_schedule_fetched_at'))} · "
                           f"Current/next week: {active if active is not None else 'N/A'}")
                a,b,c=st.columns(3)
                a.metric('Regular games',stats['regular_games'])
                b.metric('Final results',stats['finals'])
                c.metric('Scheduled games',stats['upcoming'])
                for warning in stats['warnings']:st.warning(warning)
                views=['Current week','Next 7 days','Upcoming','Completed','Specific week','All regular season','All games (incl. postseason)']
                view=st.selectbox('NFL schedule view',views,key='nfl_schedule_view')
                week=None
                if view=='Specific week':
                    weeks=stats['weeks']
                    if weeks:
                        week=st.selectbox('Week',weeks,index=weeks.index(active) if active in weeks else 0,
                                          key='nfl_week_choice')
                selected=nfl_schedule.select_games(df,view,asof=now,week=week)
                if selected.empty:st.info('No games match this view. Choose another week or update the season.')
                else:
                    st.caption(f'Showing all {len(selected)} matching games, chronologically. Scores shown only for final results.')
                    st.dataframe(nfl_schedule.table(selected),hide_index=True,use_container_width=True,
                                 height=min(520,75+len(selected)*35))
                if active is not None and 1<=active<=18:
                    if st.button(f'Cross-check Week {active} vs ESPN (public, unofficial)',key='nfl_crosscheck'):
                        try:
                            remote=providers.espn_nfl_week(yr,active)
                            st.session_state['nfl_espn_check']=(yr,active,nfl_schedule.compare_espn(df,remote,active))
                        except providers.ProviderError as exc:st.warning(f'Unable to cross-check ESPN: {exc}')
                    result=st.session_state.get('nfl_espn_check')
                    if result and result[0]==yr and result[1]==active:
                        report=result[2]
                        if report['consistent']:
                            st.success(f"Current week verified: {report['matches']} matchups/dates match ESPN public scoreboard.")
                        else:
                            st.warning(f"Schedule disagreement. NFLverse: {report['nfl_total']} games; "
                                       f"ESPN: {report['espn_total']}; matched: {report['matches']}.")
                            with st.expander('Inspect unmatched games / kickoff-date disagreements'):
                                st.json({k:v for k,v in report.items() if k.startswith('missing_') or k=='date_disagreements'})
                    st.caption('ESPN is an unofficial public cross-check, not an authoritative replacement for NFLverse. '
                               'Kickoff changes and completed scores should be verified before placing wagers.')
            elif st.session_state.get('nfl_schedule_df') is not None:
                st.info('Selected season differs from loaded data. Click Sync NFLverse games to load this season.')
        with col2:
            st.subheader('CollegeFootballData schedule and results')
            yr=int(st.number_input('CFB season',2020,now.year,now.year,key='cfb_y'))
            if st.button('↻ Sync CFBD games'):
                try:
                    with st.spinner('Fetching CFBD games…'):
                        games=providers.cfbd_games(yr,key=cfbd_key)
                        team_records=providers.cfbd_teams(yr,key=cfbd_key)
                        st.session_state['cfb_team_records']=team_records
                        models.register_cfb_teams(team_records)
                        st.session_state['cfb_raw']=games
                        st.session_state['cfb_games']=models.scores_from_cfbd(games,asof=now)
                    st.success(f"{len(st.session_state['cfb_games'])} completed games available; {len(models.CFB_ALIASES)} college team-name aliases registered.")
                except Exception as e:st.error(str(e))
            if st.session_state.get('cfb_raw') is not None:
                df=pd.DataFrame(st.session_state['cfb_raw'])
                st.dataframe(df[[x for x in ('week','start_date','away_team','away_points','home_team','home_points') if x in df]].tail(30),hide_index=True,use_container_width=True)
        st.divider()
        st.subheader('Projected upcoming matchups')
        quotes=best_quotes(current_quotes())
        projs=projections_by_event(quotes)
        seen={q['event_id']:q for q in quotes}
        data=[]
        for eid,q in seen.items():
            pr=projs.get(eid)
            if not pr:continue
            data.append({'Sport':q['sport'],'Matchup':q['away_team']+' @ '+q['home_team'],
                         'Kickoff':short_time(q['commence_time']),
                         'Projected home pts':round(pr['home'],1),'Projected away pts':round(pr['away'],1),
                         'Margin':round(pr['margin'],1),'Total':round(pr['total'],1),
                         'Sample size min':min(pr['home_games'],pr['away_games']),
                         'Model status':'Experimental — uncalibrated'})
        if data:st.dataframe(pd.DataFrame(data),use_container_width=True,hide_index=True)
        else:st.info('Load schedules/results above AND sync sportsbook odds in Market Scanner to see projected upcoming matchups.')
        st.caption('Scoring-based projections do not yet include injury availability, play-by-play EPA, or opponent-adjusted ratings in probability calculation. EPA is displayed separately for research.')
        with st.expander('🌦 Stadium forecast (manual coordinates)'):
            st.caption('Enter verified stadium coordinates. This avoids assigning weather to the wrong stadium or a domed venue.')
            co1,co2=st.columns(2)
            lat=co1.number_input('Latitude',-90.,90.,44.9778,format='%.4f')
            lon=co2.number_input('Longitude',-180.,180.,-93.2650,format='%.4f')
            if st.button('Fetch Open-Meteo forecast'):
                try:st.session_state['weather_result']=providers.weather_forecast(lat,lon)
                except Exception as e:st.error(str(e))
            if st.session_state.get('weather_result'):
                hourly=st.session_state['weather_result'].get('hourly',{})
                wd=pd.DataFrame(hourly)
                if not wd.empty:
                    st.dataframe(wd[['time','temperature_2m','precipitation_probability','wind_speed_10m','wind_gusts_10m']].head(36),use_container_width=True,hide_index=True)
                    st.caption('Hourly forecast is not automatically aligned with a specific game. Interpret venue roof status and kickoff local time before applying it.')


if workspace_tabs[5].open:
    with workspace_tabs[5]:
        section_guide('Find likely touchdown opportunities', ['Pick the NFL season and week; player statistics load automatically when available.', 'Open a matchup to view up to **three scorer candidates per team**.', 'Check official player status; optionally load play-calling trends or compare quoted anytime-TD odds.'], 'The scoring index is a heuristic—not a touchdown probability or confirmed betting edge.')

        st.subheader('🏈 NFL Touchdown Scorer Board')
        st.caption('All regular-season matchups by week · Three offensive touchdown candidates per team · Historical usage, opponent tendencies and game-flow context')
        st.warning('These are experimental **scoring-opportunity rankings**, not confirmed starters, injury-cleared players, or calibrated hit probabilities. Verify availability and prices before betting.')

        @st.cache_data(ttl=3600,show_spinner=False)
        def scorer_schedule(year):
            return providers.nfl_games(year)

        @st.cache_data(ttl=3600,show_spinner=False)
        def scorer_player_logs(year):
            return providers.nfl_player_stats(year)

        @st.cache_data(ttl=7200,show_spinner=False)
        def scorer_schemes(year):
            return providers.nfl_pbp_tendencies(year)

        left,right=st.columns([1,2])
        with left:
            scorer_year=int(st.number_input('Season',min_value=2020,max_value=now.year,value=now.year,step=1,key='td_scorer_year'))
        if st.button('↻ Refresh NFL schedule and player logs',key='td_refresh',use_container_width=True):
            scorer_schedule.clear()
            scorer_player_logs.clear()
            st.session_state.pop('td_scorer_error',None)
            st.rerun()
        schedule=None; players=None
        try:
            with st.spinner('Loading NFLverse schedules and player game logs…'):
                schedule=nfl_schedule.prepare_schedule(scorer_schedule(scorer_year),scorer_year,asof=now)
                players=scorer_player_logs(scorer_year)
        except Exception as exc:
            st.error(f'NFLverse unavailable ({type(exc).__name__}): Check network connectivity and retry. Predictions are withheld rather than invented.')
        if schedule is not None and players is not None:
            eligible=schedule[(schedule.game_type=='REG') & schedule.week.between(1,18)]
            weeks=sorted(int(x) for x in eligible.week.dropna().unique())
            if not weeks:
                st.info('No regular-season weeks available for this season.')
            else:
                active=nfl_schedule.active_week(schedule,asof=now)
                initial=weeks.index(active) if active in weeks else 0
                with right:
                    pick_week=int(st.selectbox('NFL Week',weeks,index=initial,key='td_scorer_week'))
                st.caption('The data cutoff is strictly before the selected game week. Future-week projections use available prior games only, not future results.')
                with st.expander('Advanced: load offensive / defensive scheme tendencies',expanded=False):
                    st.caption('Optional larger NFLverse play-by-play download, cached for two hours. Adds pass/run rates and red-zone passing usage. Coverage-specific schemes such as man/zone are not inferred.')
                    if st.button('Load/play-by-play tendencies',key='td_scheme_load'):
                        try:
                            with st.spinner('Downloading NFL play-by-play for pass/run tendencies…'):
                                st.session_state['td_scheme_df']=scorer_schemes(scorer_year)
                                st.session_state['td_scheme_year']=scorer_year
                            st.success('Pass/run and red-zone tendencies loaded.')
                        except Exception as exc:
                            st.warning(f'Could not retrieve scheme data ({type(exc).__name__}); player-usage rankings remain available.')
                    if st.session_state.get('td_scheme_year')==scorer_year:
                        st.caption('Historical play-calling data active for selected season.')
                pool=td_scorers.prepare_player_rows(players,scorer_year,pick_week)
                known=sorted(pool.player_display_name.dropna().unique().tolist()) if not pool.empty else []
                with st.expander('Player availability: manually exclude confirmed OUT players',expanded=False):
                    st.caption('NFLverse current-week injury reports automatically exclude confirmed OUT players when fresh. Confirm game-day actives; manually exclude any additional athletes.')
                    excluded=st.multiselect('Exclude players known to be OUT',known,key=f'td_excluded_{scorer_year}_{pick_week}',placeholder='Search player names')
                pts={}
                finals=eligible[(eligible.week<pick_week)&(eligible.status=='Final')]
                if not finals.empty:
                    history=models.scores_from_schedule(finals,asof=now)
                    forms=models.team_summary(history,'NFL')
                    selected_games=eligible[eligible.week==pick_week]
                    for _,game in selected_games.iterrows():
                        projection=models.project_scores(game.home_team,game.away_team,'NFL',forms)
                        if projection:
                            pts[nfl_schedule.normalize_team(game.home_team)]=projection['home']
                            pts[nfl_schedule.normalize_team(game.away_team)]=projection['away']
                scheme_df=st.session_state.get('td_scheme_df') if st.session_state.get('td_scheme_year')==scorer_year else None
                scorer_injury=game_injury_report(scorer_year,pick_week)
                confirmed_out=[p['player'] for p in scorer_injury.get('players',[]) if p.get('is_current') and p['status'] in injury_intelligence.BLOCKED]
                board=td_scorers.weekly_scorer_board(schedule,players,scorer_year,pick_week,
                    pbp=scheme_df,excluded_players=list(excluded)+confirmed_out,team_points=pts)
                st.caption(f"Injury report {scorer_injury['status']} · {len(confirmed_out)} named players excluded as OUT · questionable scorers still require manual verification.")
                if scorer_injury['status']!='FRESH':st.warning(scorer_injury['warning'])
                c1,c2,c3=st.columns(3)
                c1.metric('Matchups',len(board['games']))
                c2.metric('Player logs available',board['historical_rows'])
                c3.metric('Play-calling adjustment','Active' if board['with_schemes'] else 'Not loaded')
                for warning in board['warnings']:
                    st.info(warning)
                live_td_quotes=[q for q in current_quotes('NFL') if q['market']=='player_anytime_td']
                flat=[]
                for g in board['games']:
                    for side in ('away','home'):
                        team=g[side]
                        for position,who in enumerate(g['picks'][team],1):
                            td_quote=td_scorers.best_anytime_td_quote(live_td_quotes,who['player'],g['home'],g['away'])
                            who['offered_td_odds']=fmt_odds(td_quote['american_odds']) if td_quote else None
                            who['td_book']=td_quote['bookmaker'] if td_quote else None
                            flat.append({'Week':pick_week,'Matchup':g['matchup'],'Team':team,'Rank':position,
                                         'Player':who['player'],'Position':who['position'],
                                         'Scoring opportunity index¹':who['opportunity_index'],
                                         'Last games':who['historical_games'],'Recent TDs':who['recent_td'],
                                         'Targets/game':who['avg_targets'],'Carries/game':who['avg_carries'],
                                         'Available anytime-TD odds':who['offered_td_odds'],'Book':who['td_book']})
                for g in board['games']:
                    with st.expander(f"{g['matchup']} · {str(g['kickoff'])[:16]}",expanded=False):
                        away,home=st.columns(2)
                        for side,pane in (('away',away),('home',home)):
                            team=g[side]
                            with pane:
                                st.markdown(f'**{team} · Top scorers**')
                                if not g['picks'][team]:
                                    st.info('Insufficient pre-game player evidence.')
                                for rank,player in enumerate(g['picks'][team],1):
                                    st.markdown(f"**{rank}. {player['player']}** · {player['position']}")
                                    st.caption(f"Opportunity index¹ {player['opportunity_index']:.1f}/100 · L{player['historical_games']} TDs: {player['recent_td']} · Targets {player['avg_targets']}/gm · Carries {player['avg_carries']}/gm")
                                    record=injury_intelligence.injury_player(scorer_injury,player['player'],team)
                                    if record and record['status'] in injury_intelligence.UNCERTAIN:
                                        st.warning(f"HOLD — game designation {record['status']}.")
                                    elif record and record['practice'] in ('DNP','LIMITED'):
                                        st.caption(f"⚠️ Practice {record['practice']}: confirm game-day status.")
                                    if player.get('offered_td_odds'):
                                        st.caption(f"Listed anytime TD: {player['offered_td_odds']} at {player['td_book']} (quoted price only, NOT verified +EV)")
                if flat:
                    st.subheader('Full Week '+str(pick_week)+' scoring shortlist')
                    st.dataframe(pd.DataFrame(flat),use_container_width=True,hide_index=True)
                    st.download_button('Download ranked touchdown shortlist (CSV)',pd.DataFrame(flat).to_csv(index=False),
                        file_name=f'edgeforce_nfl_{scorer_year}_week_{pick_week}_td_shortlist.csv',mime='text/csv',use_container_width=True)
                else:
                    st.info('No eligible players for this week from the available historical logs. Rankings are intentionally blank.')
                st.caption('¹ Opportunity index uses a Poisson heuristic combining pre-week rushing/receiving TDs, carries, targets, limited opponent positional TD concession, optional observed pass/run and red-zone trends, and recent team scoring. It is NOT a validated betting probability and does not include confirmed injuries, snap counts or man/zone coverage. When available, separately synced anytime-TD sportsbook quotes are shown without claiming positive EV. QB passing TDs never count as QB scoring TDs.')


if workspace_tabs[6].open:
    with workspace_tabs[6]:
        section_guide('Build and diversify EV-qualified tickets', ['Sync NFL sportsbook odds in **Markets**, then choose one sportsbook.', 'Tap **Optimize** to request five 3-leg tickets, five 5-leg tickets, and six price-based contrarian picks.', 'Review **Portfolio exposure** for repeated legs; log research tickets to track their results.'], 'The engine can return fewer tickets if qualifying offers are insufficient. Estimated hit rates are uncalibrated.')

        st.subheader('🏈 EV Parlay Studio')
        st.caption('Five 3-leg lower-complexity tickets • Five 5-leg higher-payout tickets • Six ranked price-contrarian NFL picks')
        st.info('Every quoted leg must pass our independent-book +EV research filter. Market-derived probabilities are NOT validated forecasts; sportsbook confirmation is required.')
        pre_injury_quotes=current_quotes('NFL')
        all_quotes=[q for q in pre_injury_quotes if offer_injury_evidence(q)[0]['status'] not in ('BLOCK','HOLD')]
        restricted=len(pre_injury_quotes)-len(all_quotes)
        if restricted:st.warning(f'{restricted} quoted legs were held or excluded due to player availability reports. Research ticket counts may be lower.')
        st.caption('Unlisted players are not certified healthy; manually confirm actives, starters and team injuries before treating any ticket as executable.')
        live_books=sorted({q['bookmaker'] for q in all_quotes})
        live_opportunities=value.scan(all_quotes,now=now,min_references=2,min_ev_pct=1.)
        coverage={}
        for r in live_opportunities:
            bk=r['quote']['bookmaker']
            coverage.setdefault(bk,set()).add(r['quote']['event_id'])
        live_books.sort(key=lambda bk:(-len(coverage.get(bk,set())),bk))
        aa,bb=st.columns([2,1])
        with aa:
            chosen_book=st.selectbox('Sportsbook — all legs on each parlay must use this book',
                live_books,key='value_parlay_book',
                format_func=lambda b:f"{b} · {len(coverage.get(b,set()))} eligible games") if live_books else None
            if not chosen_book:st.warning('No recent NFL odds. Sync the sportsbook feed to find opportunities.')
        with bb:
            if st.button('↻ Refresh NFL game odds',use_container_width=True):
                try:
                    fetched=providers.odds_api('NFL',key=odds_key,markets='h2h,spreads,totals')
                    num=len(db.insert_snapshots(fetched))
                    st.session_state['odds_usage']=providers.odds_usage()
                    st.success(f'Recorded {num} immutable sportsbook quote snapshots.')
                    st.rerun()
                except providers.ProviderError as exc:st.error(str(exc))
        with st.expander('⚙️ Advanced EV and portfolio settings (optional)',expanded=False):
            fc1,fc2=st.columns(2)
            with fc1:ev_cutoff=st.selectbox('Minimum estimated EV per leg',[1.,2.,3.,0.],index=0,key='parlay_ev_cutoff',format_func=lambda x:f'{x:.0f}%')
            with fc2:ref_cutoff=st.selectbox('Independent reference books',[2,3,1],index=0,key='parlay_ref_cutoff')
            if ref_cutoff==1:st.warning('Single reference-book estimates are weak. Use at least two for better price confidence.')
            cc1,cc2=st.columns(2)
            leg_cap=cc1.slider('Preferred maximum appearances per exact bet',1,5,2,key='v07_leg_cap')
            game_cap=cc2.slider('Preferred appearances per game',2,10,5,key='v07_game_cap')
            diversification=st.slider('Diversification emphasis',0.,3.,1.,step=.25,key='v07_diversity',help='Higher values penalize repeated legs and games across all ten tickets; does not improve the underlying odds.')
            st.caption('Limits are preferences rather than hard caps. If the slate is too small, EdgeForce reports any unavoidable concentration.')
        st.caption('The ranking balances an experimental conservative hit-rate proxy with slate-wide concentration penalties. Odds must be fresh, independently priced, and valid at one book.')
        if st.button('Optimize 5 three-leg + 5 five-leg parlays + top 6 contrarian picks',type='primary',
                     use_container_width=True,key='ev_bundle_generate'):
            if not chosen_book:st.warning('Choose a sportsbook with fresh NFL prices first.')
            else:
                with st.spinner('Ranking EV-qualified markets and slate-wide contrarian opportunities…'):
                    optimized=portfolio.optimize_portfolio(all_quotes,chosen_book,now=now,
                        min_ev=ev_cutoff,min_references=ref_cutoff,target_leg_cap=leg_cap,
                        target_game_cap=game_cap,diversification=diversification)
                    three={'tickets':optimized['three'],'reason':None if len(optimized['three'])==5 else 'Fewer than five qualifying three-leg tickets survived all controls.'}
                    five={'tickets':optimized['five'],'reason':None if len(optimized['five'])==5 else 'Fewer than five qualifying five-leg tickets survived all controls.'}
                    underdogs=opportunities.rank_price_contrarians(all_quotes,now=now,
                        count=6,min_ev=ev_cutoff,min_references=ref_cutoff)
                st.session_state['ev_v06_bundle']={'three':three,'five':five,'underdogs':underdogs,
                    'portfolio':optimized,'leg_cap':leg_cap,'game_cap':game_cap,'diversification':diversification,
                    'book':chosen_book,'min_ev':ev_cutoff,'min_ref':ref_cutoff,'created_at':datetime.now(timezone.utc).isoformat()}
        result=st.session_state.get('ev_v06_bundle')
        if result and (result['book']!=chosen_book or result['min_ev']!=ev_cutoff or result['min_ref']!=ref_cutoff
                       or result.get('leg_cap')!=leg_cap or result.get('game_cap')!=game_cap
                       or result.get('diversification')!=diversification):
            st.info('Settings changed. Generate again to update the analysis.')
            result=None
        if result:
            if (datetime.now(timezone.utc)-db.parse_utc(result['created_at'])).total_seconds()>1800:
                st.warning('Shortlist is over 30 minutes old. Sync fresh odds and regenerate.')
            k1,k2,k3=st.columns(3)
            k1.metric('3-leg tickets',len(result['three']['tickets']))
            k2.metric('5-leg tickets',len(result['five']['tickets']))
            k3.metric('Price-contrarian picks',len(result['underdogs']['picks']))
            tab3,tab5,tabc,tabe=st.tabs(['3-leg • Higher hit proxy','5-leg • Higher potential payout','Top 6 • Contrarian prices','Portfolio exposure'])
            def render_tickets(report,number):
                st.caption(f'Tickets contain {number} different games at the same sportsbook. They were selected jointly using exposure penalties; overlap can remain.')
                if report['reason']:st.warning(report['reason'])
                for i,ticket in enumerate(report['tickets'],1):
                    with st.container(border=True):
                        st.markdown(f"#### #{i} · {ticket['label']}")
                        m1,m2=st.columns(2)
                        m1.metric('Est. hit-rate proxy¹',f"{ticket['nominal_probability']:.1%}")
                        m2.metric('Sensitivity scenario¹',f"{ticket['conservative_probability']:.1%}")
                        st.caption(f"{ticket['bookmaker']} · Theoretical decimal payout {ticket['decimal_price']:.2f}x · Unvalidated EV {ticket['theoretical_ev_pct']:+.1f}% · Stress EV {ticket['stress_ev_pct']:+.1f}%")
                        for leg in ticket['legs']:
                            q=leg['quote']
                            st.markdown(f"- **{q['away_team']} @ {q['home_team']}** — {value.describe(leg)} · **{fmt_odds(leg['offered_odds'])}** · est. EV {leg['ev_pct']:+.1f}%")
                            explain_ev_candidate(leg)
                        if st.button(f'Log #{i} {number}-leg research ticket',key=f'v06_log_{number}_{i}'):
                            try:
                                tid=db.log_ticket([x['snapshot_id'] for x in ticket['legs']],10.,
                                    ticket['nominal_probability'],ticket['theoretical_ev_pct']/100,
                                    f'{number}-leg EV consensus · '+ticket['label'],
                                    version='portfolio-consensus-v0.7-UNCALIBRATED')
                                st.success(f'Research ticket saved: {tid[:12]} — Performance Tracker')
                            except Exception as e:
                                st.error(f'Could not log ticket ({type(e).__name__}). Refresh odds and verify database connectivity.')
                if not report['tickets']:st.info('No qualifying tickets with the requested filters. EdgeForce will not fill empty legs with unsupported wagers.')
            with tab3:
                st.markdown('### Five three-leg EV parlays')
                render_tickets(result['three'],3)
            with tab5:
                st.markdown('### Five five-leg EV parlays')
                render_tickets(result['five'],5)
            with tabc:
                st.markdown('### Six ranked price-contrarian NFL picks')
                st.caption('These are +odds underdog prices that outperform independent sportsbook fair-price estimates. They are NOT verified public fades or sharp-money plays.')
                underdogs=result['underdogs']
                if underdogs['reason']:st.warning(underdogs['reason'])
                for i,r in enumerate(underdogs['picks'],1):
                    q=r['quote']
                    with st.container(border=True):
                        st.markdown(f"#### #{i} · {q['away_team']} @ {q['home_team']}")
                        st.markdown(f"**{value.describe(r)}** · {q['bookmaker']} · Offered **{fmt_odds(r['offered_odds'])}** · Estimated fair **{fmt_odds(r['fair_american'])}**")
                        c1,c2,c3=st.columns(3)
                        c1.metric('Estimated EV',f"{r['ev_pct']:+.1f}%")
                        c2.metric('Fair probability¹',f"{r['fair_probability']:.1%}")
                        c3.metric('Reference books',r['reference_count'])
                        st.caption(f"Sensitivity EV {r['stress_ev_pct']:+.1f}% · Reference spread {r['variation_pp']:.1f} pp · Price-contrarian only; public split not verified")
                        explain_ev_candidate(r)
                if not underdogs['picks']:st.info('No independently supported contrarian prices available. This is a valid outcome; no picks are fabricated.')
            with tabe:
                st.markdown('### Across-ticket risk concentration')
                exposure=result['portfolio']
                for warning in exposure['warnings']:st.warning(warning)
                q1,q2,q3=st.columns(3)
                q1.metric('Unique NFL games',len(exposure['game_exposure']))
                q2.metric('Most-shared legs between two tickets',exposure['max_shared_legs'])
                q3.metric('Maximum repeat of one bet',max(exposure['leg_exposure'].values(),default=0))
                if exposure['game_exposure']:
                    names={q['event_id']:q['away_team']+' @ '+q['home_team'] for q in all_quotes}
                    exposures=pd.DataFrame([{'Matchup':names.get(eid,eid),'Appearances across 10 tickets':n}
                                            for eid,n in exposure['game_exposure'].items()])
                    st.dataframe(exposures.sort_values('Appearances across 10 tickets',ascending=False),
                        use_container_width=True,hide_index=True)
                if exposure['team_exposure']:
                    st.caption('Team appearances include both opponents in each game; they measure concentrated game exposure, not bets directly on each team.')
                    st.dataframe(pd.DataFrame([{'Team':team,'Appearances':n} for team,n in sorted(
                        exposure['team_exposure'].items(),key=lambda kv:-kv[1])]),use_container_width=True,hide_index=True)
                st.caption('This allocation manages concentration but does not make wagers statistically independent, guarantee a profit, or adjust underlying estimated EV for inter-game dependence.')
            st.caption('¹ Hit rates and fair prices are market-consensus proxies, not calibrated predictions. The sensitivity haircut is hypothetical, not a confidence interval. Avoid treating a ten-ticket set as ten independent positions.')
        else:
            st.info('Select an NFL sportsbook and generate the analysis. Three-leg, five-leg and contrarian sections will appear here.')
        st.divider()
        with st.expander('Understanding +EV and research safeguards'):
            st.markdown('**+EV** means the quoted sportsbook price implies a lower break-even probability than the no-vig probability estimated from independent sportsbooks. It does not establish a genuine predictive advantage. **Contrarian** means a qualifying underdog price at odds of +100 or longer; actual public-betting sentiment is unknown. **Three-leg parlays** generally have a higher hit probability than comparable five-leg parlays but pay less. All picks require fresh odds, matching lines and independent reference books. Historical closing lines and settled outcomes are tracked separately, not used as post-event inputs to predictions.')


if workspace_tabs[7].open:
    with workspace_tabs[7]:
        section_guide('Audit predictions and results', ['Save a research pick in Markets or a ticket in Parlays.', 'Review the locked offered price, prediction time, closing price (if recorded), and outcome.', 'Use **Export and settlement tools** to reconcile results and download your evidence.'], 'Closing prices are only shown if EdgeForce actually collected an eligible quote before kickoff.')

        st.caption('Click the free NFL results update to reconcile eligible team-market picks. Settled predictions automatically update accuracy panels without editing original forecasts.')
        if st.button('↻ Refresh NFL final scores and update accuracy',key='accuracy_sync_nfl',use_container_width=True):
            try:
                season=game_hub.nfl_season_for_date(datetime.now(timezone.utc))
                schedule=fetch_daily_schedule(season,force=True)
                if schedule is None or schedule.empty:
                    st.warning('Could not retrieve NFLverse final scores. Historical accuracy unchanged.')
                else:
                    finals=models.scores_from_schedule(schedule[schedule.status=='Final'],asof=datetime.now(timezone.utc))
                    settled=ledger.auto_settle(finals)
                    st.success(f"Updated result ledger: {settled['settled']} newly settled eligible picks; {settled['skipped']} not settled. Unsupported player props remain pending.")
            except Exception as exc:
                st.error(f'Unable to update results ({type(exc).__name__}). Original prediction records were not modified.')
        rows=ledger.performance_rows()
        mm=ledger.metrics(rows)
        st.subheader('Auditable prediction performance')
        st.markdown('### 📐 Historical forecast accuracy & injury feedback')
        st.caption('Only immutable pregame forecasts with recorded WIN/LOSS settlements enter calibration. ROI reflects hypothetical tracked stakes; no actual bets are inferred.')
        report=accuracy_feedback.summarize(rows)
        overall=report['overall']
        r1,r2,r3=st.columns(3)
        r1.metric('Settled decisive picks',overall['n'])
        r2.metric('Brier error¹',f"{overall['brier']:.3f}" if overall['brier'] is not None else '—')
        r3.metric('Paper ROI²',f"{overall['research_roi']:.1%}" if overall['research_roi'] is not None else '—')
        if not overall['mature']:
            st.info(f"Only {overall['calibration_n']} decisive forecasts have usable recorded probabilities. At least {overall['minimum_sample']} are needed for a preliminary reliability view; this is not an evidence-backed win model.")
        with st.expander('Accuracy by betting market and pre-pick injury context',expanded=False):
            for heading,items in [('Markets',report['by_market']),('Injury evidence recorded at prediction time',report['by_injury_status'])]:
                st.markdown('**'+heading+'**')
                if items:
                    st.dataframe(pd.DataFrame([{'Cohort':k,'Settled picks':v['n'],
                        'Actual wins':v['wins'],'Observed win %':round(100*v['observed_win_rate'],1) if v['observed_win_rate'] is not None else None,
                        'Average predicted %':round(100*v['mean_predicted'],1) if v['mean_predicted'] is not None else None,
                        'Brier (lower better)':round(v['brier'],3) if v['brier'] is not None else None,
                        'Sample qualified?':v['mature']} for k,v in items.items()]),hide_index=True,use_container_width=True)
                else:st.info('No settled records for this group.')
            if report['calibration_bins']:
                st.markdown('**Predicted vs actual hit rates**')
                st.dataframe(pd.DataFrame(report['calibration_bins']),hide_index=True,use_container_width=True)
        st.caption('¹ Brier uses only settled WIN/LOSS with a time-locked probability. ² Hypothetical stake ROI includes settled WIN/LOSS/PUSH, never pending picks. Older picks without injury tags are labeled NOT_RECORDED.')
        st.caption('Player-prop bets cannot be auto-settled from team scores; record an independently verified box-score outcome before evaluating their accuracy.')
        a,b,c,d,e=st.columns(5)
        a.metric('Logged predictions',mm['predictions'])
        b.metric('Settled',mm['settled'])
        c.metric('Win rate',f"{mm['win_rate']:.1%}" if mm['win_rate'] is not None else '—')
        d.metric('Realized P/L',f"${mm['pnl']:+,.2f}")
        e.metric('ROI on settled stakes',f"{mm['roi']:.1%}" if mm['roi'] is not None else '—')
        with st.expander('📐 Advanced calibration and closing-line metrics',expanded=False):
            f,g,h=st.columns(3)
            f.metric('Brier score',f"{mm['brier']:.3f}" if mm['brier'] is not None else '—',help='Mean squared probability error across settled wins/losses; lower is better.')
            g.metric('Eligible closing prices',mm['clv_available'])
            h.metric('Average closing implied shift',f"{mm['clv_pp_mean']:+.2f} pp" if mm['clv_available'] else '—',help='Positive = closing implied probability rose relative to locked offer, SAME book/market/line, within 2h of kickoff. Not no-vig CLV.')
        st.caption('Closing price is defined narrowly: the final actually collected quote within 120 minutes of kickoff, from the same book at the same selection and exact line. If never collected, it is **missing**, not inferred.')
        individual, parlays_tab, evidence=st.tabs(['Individual prediction ledger','Parlay ticket ledger','Export and settlement tools'])
        with individual:
            if rows:
                df=pd.DataFrame(rows)
                columns={'created_at':'Prediction timestamp (UTC)','observed_at':'Odds observed (UTC)',
                 'sport':'Sport','home_team':'Home','away_team':'Away','market':'Market',
                 'selection':'Selection','point':'Line','participant':'Player','bookmaker':'Book','american_odds':'Actual offer',
                 'model_probability':'Forecast p','closing_american_odds':'Closing odds (same line)',
                 'closing_observed_at':'Closing observed (UTC)','outcome':'Final result',
                 'final_home_score':'Home final','final_away_score':'Away final',
                 'clv_implied_delta_pp':'CLV implied Δ (pp)','realized_pnl':'P/L ($)','model_version':'Model version',
                 'id':'Prediction ID','source':'Odds source','source_updated_at':'Provider quote time (UTC)','stake':'Tracked stake ($)',
                 'confidence_grade':'Research grade'}
                st.dataframe(df[[c for c in columns if c in df]].rename(columns=columns),hide_index=True,use_container_width=True)
                to_settle=[r for r in rows if not r['outcome']]
                if to_settle:
                    with st.expander('Manually record a final outcome (append-only)',expanded=False):
                        options={f"{r['away_team']} @ {r['home_team']} {r['selection']} {r['market']} · {r['id'][:8]}":r for r in to_settle}
                        pick=st.selectbox('Unsettled forecast',list(options))
                        result=st.selectbox('Result',['WIN','LOSS','PUSH','VOID'])
                        hs=st.number_input('Final home score',min_value=0.,step=1.,value=0.)
                        aw=st.number_input('Final away score',min_value=0.,step=1.,value=0.)
                        evidence_note=st.text_input('Result source/reference (required)')
                        if st.button('Append settlement'):
                            if len(evidence_note.strip())<4:st.error('Document the source of the final result.')
                            else:
                                db.settle(options[pick]['id'],result,'manual review',hs,aw,evidence_note)
                                st.success('Appended a timestamped settlement. Reload the page to view metrics.')
                with st.expander('Reconciliation / corrections'):
                    st.caption('Corrections append new settlement events rather than altering old records. This preserves the audit trail.')
                    picks={f"{r['id'][:8]} {r['selection']} {r['outcome'] or 'PENDING'}":r for r in rows}
                    p=st.selectbox('Recorded forecast',list(picks))
                    result=st.selectbox('Corrected result',['WIN','LOSS','PUSH','VOID'])
                    note=st.text_input('Correction reason and result source')
                    if st.button('Append correction'):
                        if len(note.strip())<4:st.error('A documented reason is required.')
                        else:
                            db.settle(picks[p]['id'],result,'manual correction',note=note)
                            st.success('Correction appended; no historical evidence overwritten.')
            else:st.info('Predictions logged in Market Scanner will appear here, including their original quoted odds and timestamp.')
        with parlays_tab:
            tickets=db.ticket_history()
            if tickets:
                display=[]
                for t in tickets:
                    # Exact decimal payout from the locked same-book individual quotes.
                    pnl=(t['combined_decimal']-1)*t['stake'] if t['outcome']=='WIN' else (-t['stake'] if t['outcome']=='LOSS' else (0 if t['outcome'] else None))
                    display.append({'Ticket':t['id'][:12],'Timestamp UTC':t['created_at'],'Label':t['label'],
                        'Legs':len(t['legs']),'Locked gross decimal':round(t['combined_decimal'],2),
                        'Sim hit p':t['estimated_probability'],'Expected ROI (heuristic)':t['estimated_ev'],
                        'Stake $':t['stake'],'Outcome':t['outcome'],'P/L $':pnl})
                st.dataframe(pd.DataFrame(display),hide_index=True,use_container_width=True)
                pick=st.selectbox('Review ticket',range(len(tickets)),format_func=lambda i:f"{tickets[i]['label']} · {tickets[i]['id'][:10]}")
                t=tickets[pick]
                st.dataframe(pd.DataFrame([{'Matchup':q['away_team']+' @ '+q['home_team'],'Selection':q['selection'],
                         'Market':q['market'],'Point':q['point'],'Quoted price':q['american_odds'],'Book':q['bookmaker'],
                         'Observed UTC':q['observed_at']} for q in t['legs']]),hide_index=True,use_container_width=True)
                res=st.selectbox('Settle ticket',['WIN','LOSS','PUSH','VOID'])
                note=st.text_input('Ticket settlement reference / reason')
                if st.button('Append ticket settlement'):
                    if len(note.strip())<4:st.error('Provide a result source or reason.')
                    else:
                        db.settle_ticket(t['id'],res,'manual review',note)
                        st.success('Ticket settlement appended. Reload to refresh.')
            else:st.info('Logged custom or generated research parlays will appear here.')
        with evidence:
            st.subheader('Automatic result ingestion')
            st.caption('Auto-grading is limited to completed NFL/CFB games whose exact teams and kickoff dates uniquely match an odds event. Player props require separate verified box scores.')
            if st.button('Auto-settle from loaded final score feeds'):
                games=st.session_state.get('nfl_games',[])+st.session_state.get('cfb_games',[])
                if not games:st.warning('First load NFLverse and/or CFBD schedules in Matchup Intelligence.')
                else:
                    outcome=ledger.auto_settle(games)
                    st.success(f"Automatically settled {outcome['settled']}; skipped {outcome['skipped']} without unique verified matches.")
                    for d in outcome['details']:st.write(d)
                    t_outcome=ledger.auto_settle_tickets(games)
                    st.info(f"Automatically settled {t_outcome['settled']} parlay tickets; skipped {t_outcome['skipped']} (including partial pushes).")
            if rows:
                df=ledger.export_dataframe()
                st.download_button('Download prediction audit CSV',data=df.to_csv(index=False),
                                   file_name='edgeforce_prediction_audit.csv',mime='text/csv')
            if db.snapshot_counts()[0]:
                st.download_button('Download full audit export',db.backup_bytes(),
                    file_name=('edgeforce_cloud_audit.zip' if db.backend_name().startswith('PostgreSQL') else 'edgeforce_audit_backup.sqlite3'),
                    mime=('application/zip' if db.backend_name().startswith('PostgreSQL') else 'application/vnd.sqlite3'))
                allq=db.latest_quotes()
                st.download_button('Export latest market quotes CSV',pd.DataFrame(allq).to_csv(index=False),
                                   file_name='edgeforce_odds.csv',mime='text/csv')
            if db.backend_name().startswith('PostgreSQL'):
                st.success('Hosted PostgreSQL audit storage active: snapshots and settlements persist across Streamlit restarts. Keep database backups and Streamlit secrets secure.')
            else:
                st.warning('SQLite on Streamlit Cloud is not durable; configure EDGEFORCE_POSTGRES_URL in app secrets to preserve longitudinal history. Do not commit keys or personal records to GitHub.')

