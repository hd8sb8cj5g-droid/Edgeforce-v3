"""EdgeForce MVP — five-source, five-screen sports analytics prototype.
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
[data-baseweb="tab-list"] { overflow-x: auto; overflow-y: hidden; }
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
  button[role="tab"] { font-size: .88rem; padding-left: .5rem; padding-right: .5rem; }
}
</style>''',unsafe_allow_html=True)

def secret(name):
    try:
        return str(st.secrets.get(name) or os.getenv(name, '') or '')
    except Exception:
        return os.getenv(name, '') or ''

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

from edgeforce import db, providers, models, parlays, ledger, value, nfl_schedule

PAGES=['Market Scanner','Player Prop Lab','Matchup Intelligence','Parlay Builder','Performance Tracker']
page=st.selectbox('📍 EdgeForce workspace',PAGES,key='edgeforce_screen',label_visibility='visible')
@st.cache_resource(show_spinner=False)
def boot_database(backend):
    db.init_db()
    return True

try:
    boot_database(db.backend_name())
except Exception as exc:
    st.error(f'Database unavailable ({type(exc).__name__}). Check the hosted PostgreSQL URL or use local demo mode.')
    st.stop()
now=datetime.now(timezone.utc)



def short_time(t):
    try:return pd.to_datetime(t,utc=True).strftime('%b %d %I:%M %p UTC')
    except Exception:return str(t)


def fmt_odds(v):return f'{int(v):+d}'


def current_quotes(sport=None):
    """Latest observed offer for a side, including line changes, not every historic line."""
    from datetime import timedelta
    recent=[q for q in db.latest_quotes(sport)
            if db.parse_utc(q['commence_time'])>now
            and db.parse_utc(q['observed_at'])>=now-timedelta(minutes=30)
            and q['source']!='SYNTHETIC DEMO']
    latest={}
    for q in recent:
        k=(q['event_id'],q['bookmaker'],q['market'],q['selection'],q.get('participant',''))
        if k not in latest or db.parse_utc(q['observed_at'])>db.parse_utc(latest[k]['observed_at']):
            latest[k]=q
    return list(latest.values())


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


def display_value_feed(offers, prefix='main'):
    """Game-specific independent market-consensus candidate screening."""
    if not offers:
        st.info('No live sportsbook quotes to evaluate. Sync your league, then refresh player props for a particular game if supported by your API plan.')
        return
    c1,c2,c3=st.columns(3)
    with c1:min_ev=st.number_input('Minimum estimated EV %',min_value=0.,max_value=30.,value=1.,step=.5,key=prefix+'_ev')
    with c2:min_books=st.selectbox('Independent reference books',[2,3,1],index=0,key=prefix+'_refs',help='2+ is recommended. The candidate sportsbook never contributes to its own fair-price estimate.')
    with c3:max_variation=st.selectbox('Maximum reference disagreement',[2.,3.,5.,10.],index=2,key=prefix+'_var',format_func=lambda x:f'{x:g} percentage points')
    if min_books==1:
        st.warning('Only one independent reference book: more false positives are possible. Verify prices before acting.')
    candidates=value.scan(offers,now=now,min_references=min_books,min_ev_pct=min_ev,
                          max_reference_range_pp=max_variation)
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
    st.dataframe(value_frame(selected).head(150),hide_index=True,use_container_width=True,
                 column_config={'Est. EV %*':st.column_config.NumberColumn(format='%.2f%%'),
                                'Est. probability*':st.column_config.NumberColumn(format='%.2f%%')})
    st.caption('*Fair odds, probabilities and EV are independently devigged market-consensus estimates, NOT a calibrated outcome model. ¹L5/L10/L20 (when loaded) are descriptive historical successes, not forecasts. Prices can move; estimates may be wrong.')
    st.subheader('Best research candidates by game')
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
    st.subheader('Save an auditable EV forecast')
    limit=selected[:100]
    labels={f"{i+1}. {r['quote']['away_team']} @ {r['quote']['home_team']} | {value.describe(r)} | {r['quote']['bookmaker']} {fmt_odds(r['offered_odds'])} | EV {r['ev_pct']:+.1f}%":r for i,r in enumerate(limit)}
    with st.expander('Log one candidate with its original offered odds and timestamp'):
        chosen=st.selectbox('Actual quoted offer',list(labels),key=prefix+'_choice')
        selected_bet=labels[chosen]
        st.write(f"Estimated fair win probability: **{selected_bet['fair_probability']:.1%}** from {selected_bet['reference_count']} independent books.")
        stake=st.number_input('Research stake ($)',min_value=1.,max_value=10000.,value=10.,step=1.,key=prefix+'_stake')
        note=st.text_input('Research notes (optional)',key=prefix+'_note',placeholder='Reason for monitoring this market')
        if st.button('Record immutable EV prediction',key=prefix+'_log',type='primary'):
            try:
                saved=db.log_prediction(selected_bet['snapshot_id'],selected_bet['fair_probability'],
                    selected_bet['quality'],'crossbook-market-proxy-v0.4-UNCALIBRATED',
                    f"Independent reference books: {', '.join(selected_bet['reference_books'])}; variation={selected_bet['variation_pp']:.3f} pp; quote offered={selected_bet['offered_odds']}; estimated EV={selected_bet['ev_pct']:.3f}%. {note}",
                    stake,tags='MARKET_CONSENSUS_NOT_VALIDATED')
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
    st.caption('FOOTBALL INTELLIGENCE • v0.4 VALUE SCANNER')
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
    st.caption('RESEARCH ONLY • EV IS MARKET-ESTIMATED, NOT VERIFIED PROFIT')
    st.caption('No wagers are placed through this application.')
    if st.session_state.get('cfb_team_records'):
        models.register_cfb_teams(st.session_state['cfb_team_records'])

st.markdown(f'# {page}')
if db.backend_name().startswith('SQLite'):
    st.warning('This deployment is using temporary SQLite storage. Cloud restarts may erase all logged odds and predictions. Add EDGEFORCE_POSTGRES_URL in Streamlit secrets for persistent tracking.')
st.markdown('<div class="banner">NFL + College Football | Actual market quotes only when a provider is connected | Models are experimental, not independently validated betting edges.</div>',unsafe_allow_html=True)

if page=='Market Scanner':
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
                st.success(f'Stored {count} immutable quotes from The Odds API.')
            except providers.ProviderError as e:st.error(str(e))
    if not st.session_state.get('nfl_games' if sport=='NFL' else 'cfb_games'):
        st.info('To activate matchup probabilities and experimental EV, load current-season results in Matchup Intelligence. Prices are available without model data.')
    all_sport_quotes=current_quotes(sport)
    quotes=[q for q in all_sport_quotes if q['market'] in markets]
    # Prop snapshots are included in EV research after an explicit event prop sync.
    ev_quotes=[q for q in all_sport_quotes if q['market'] in markets or q['market'].startswith('player_')]
    projections=projections_by_event(quotes)
    x,y,z=st.columns(3)
    x.metric('Unique upcoming games',len(set(q['event_id'] for q in quotes)))
    y.metric('Unique sportsbooks',len(set(q['bookmaker'] for q in quotes)))
    z.metric('Recorded quote snapshots',db.snapshot_counts()[0])
    tab0,tab1,tab2,tab3=st.tabs(['⭐ +EV bet finder','Best available prices','Odds history','Kalshi comparison'])
    with tab0:
        st.caption('Scan each game for potentially mispriced offers. Excludes the offered book from the reference consensus and requires both sides at the same line.')
        st.caption('NFL/CFB main game lines are scanned automatically from stored snapshots; player props join the same game finder after explicit per-game retrieval.')
        upcoming={q['event_id']:q for q in quotes}
        if upcoming:
            with st.expander('Fetch player props for a game (uses Odds API credits)'):
                game_labels={f"{q['away_team']} @ {q['home_team']} · {short_time(q['commence_time'])}":eid for eid,q in upcoming.items()}
                pick=st.selectbox('Choose matchup',list(game_labels),key='scan_props_event')
                chosen_markets=st.multiselect('Prop markets to fetch',list(providers.PROP_MARKETS),
                    default=['Passing yards','Rushing yards','Receiving yards','Receptions'],key='scan_props_markets')
                st.caption('Each event fetch consumes sportsbook API credits; NFL/CFB props also depend on your plan entitlement and actual listed markets.')
                if st.button('Fetch props for this game',key='scan_props_fetch',type='primary'):
                    if not chosen_markets:st.warning('Choose at least one market.')
                    else:
                        try:
                            new_quotes=providers.odds_event_props(sport,game_labels[pick],key=odds_key,
                                   markets=[providers.PROP_MARKETS[m] for m in chosen_markets])
                            added=db.insert_snapshots(new_quotes)
                            st.session_state['odds_usage']=providers.odds_usage()
                            st.success(f'Saved {len(added)} actual prop offers. Reloading updated game candidates.')
                            st.rerun()
                        except providers.ProviderError as e:st.error(str(e))
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

elif page=='Player Prop Lab':
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
                        qs=providers.odds_event_props(prop_sport,options[selected_game],key=odds_key,
                            markets=[providers.PROP_MARKETS[x] for x in prop_market_names])
                        db.insert_snapshots(qs)
                        st.session_state['odds_usage']=providers.odds_usage()
                        st.success(f'Recorded {len(qs)} real player prop quotes for the chosen event.')
                        if not qs:st.warning('No prop quotes returned. Check market coverage and your subscription entitlement.')
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

elif page=='Matchup Intelligence':
    col1,col2=st.columns(2)
    with col1:
        st.subheader('NFLverse schedule and results')
        yr=int(st.number_input('NFL season',2020,now.year,now.year,key='nfl_y'))
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

elif page=='Parlay Builder':
    all_quotes=current_quotes()
    books=sorted(set(q['bookmaker'] for q in all_quotes))
    chosen_book=st.selectbox('Sportsbook (all legs must be from the same book)',books) if books else None
    quotes=[q for q in all_quotes if q['bookmaker']==chosen_book] if chosen_book else []
    projs=projections_by_event(quotes)
    st.subheader('Candidate parlay simulations')
    left,right=st.columns([2,1])
    left.caption('Joint NFL/CFB score simulations preserve within-game correlation, but the score model is not backtested or calibrated.')
    stake=right.number_input('Tracking stake ($)',min_value=1.,max_value=10000.,value=10.,step=1.)
    if st.button('Generate five 5-leg research tickets',type='primary'):
        if len([q for q in quotes if q['event_id'] in projs])<5:
            st.warning('Insufficient priced, modelled outcomes. Load completed-game data on Matchup Intelligence and fresh actual odds in Market Scanner.')
        else:
            with st.spinner('Running game-score simulations…'):
                st.session_state['tickets']=parlays.candidate_tickets(quotes,projs,ticket_count=5,legs=5,sim_n=20000)
                st.session_state['ticket_book']=chosen_book
            if not st.session_state['tickets']:st.warning('No eligible diversified ticket combinations; this is preferable to fabricated picks.')
    for i,ticket in enumerate(st.session_state.get('tickets',[]) if st.session_state.get('ticket_book')==chosen_book else [],1):
        with st.expander(f"#{i} {ticket['type']} · {ticket['win_prob']:.1%} modelled hit rate · {ticket['decimal_payout']:.2f}x decimal · EV {ticket['approx_ev_per_dollar']:.1%}",expanded=i==1):
            for q in ticket['quotes']:
                st.markdown(f"- **{q['away_team']} @ {q['home_team']}** · {q['market']} {q['selection']} {q['point'] if q['point'] is not None else ''} · **{fmt_odds(q['american_odds'])}** at {q['bookmaker']}")
            st.caption(f"{ticket['n']:,} joint score draws · Experimental, not predictive certainty. Push EV is conservatively approximated; sportsbooks may disallow same-game combinations or modify payouts.")
            if st.button(f'Log research ticket #{i}',key=f'log_ticket_{i}'):
                try:
                    tid=db.log_ticket([q['id'] for q in ticket['quotes']],stake,ticket['win_prob'],
                                      ticket['approx_ev_per_dollar'],ticket['type'])
                    st.success('Ticket locked in local audit ledger: '+tid[:12])
                except Exception as e:st.error(str(e))
    st.divider()
    st.subheader('Custom parlay research')
    st.caption('A same-game multi-leg model can be simulated, but its multiplied individual prices are NOT an executable SGP offer. Saved tracking tickets require distinct games.')
    if quotes:
        opts={f"{i+1}. {q['away_team']} @ {q['home_team']} · {q['market']} {q['selection']} {q['point'] if q['point'] is not None else ''} · {fmt_odds(q['american_odds'])} ({q['bookmaker']})":q for i,q in enumerate(quotes)}
        chosen=st.multiselect('Choose priced legs (2–8)',list(opts))
        if st.button('Run joint simulation for selected legs'):
            picked=[opts[x] for x in chosen]
            if not 2<=len(picked)<=8:st.warning('Select 2–8 legs.')
            elif any(q['event_id'] not in projs for q in picked):st.warning('Model data is not available for every selected matchup.')
            elif len({(q['event_id'],q['market'],abs(float(q.get('point') or 0))) for q in picked})<len(picked):
                st.warning('Contradictory selections in one market/line cannot form a valid ticket.')
            else:
                sim=parlays.joint_ticket(picked,projs,n=30000)
                st.session_state['custom_ticket']=(picked,sim)
        if st.session_state.get('custom_ticket'):
            picked,sim=st.session_state['custom_ticket']
            st.metric('Correlated simulated win probability',f"{sim['win_prob']:.2%}")
            c1,c2=st.columns(2)
            c1.metric('Approximate gross decimal payout',f"{sim['decimal_payout']:.2f}x")
            c2.metric('Experimental EV / $1 staked',f"{sim['approx_ev_per_dollar']:+.2%}")
            if st.button('Save this research ticket'):
                try:
                    tid=db.log_ticket([q['id'] for q in picked],stake,sim['win_prob'],
                                      sim['approx_ev_per_dollar'],'Custom')
                    st.success('Saved ticket '+tid[:12])
                except Exception as e:st.error(str(e))
    else:st.info('Add a real sportsbook odds key and sync markets before building parlays.')

elif page=='Performance Tracker':
    rows=ledger.performance_rows()
    mm=ledger.metrics(rows)
    st.subheader('Auditable prediction performance')
    a,b,c,d,e=st.columns(5)
    a.metric('Logged predictions',mm['predictions'])
    b.metric('Settled',mm['settled'])
    c.metric('Win rate',f"{mm['win_rate']:.1%}" if mm['win_rate'] is not None else '—')
    d.metric('Realized P/L',f"${mm['pnl']:+,.2f}")
    e.metric('ROI on settled stakes',f"{mm['roi']:.1%}" if mm['roi'] is not None else '—')
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
