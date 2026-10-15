"""Regression tests: never manufacture EV from bad, stale, or dependent markets."""
from datetime import datetime, timedelta, timezone
from edgeforce import value

T = datetime(2026,10,15,15,0,tzinfo=timezone.utc)


def quote(book, side, odds, market='h2h', line=None, player='', eid='GAME123', minutes_ago=2,
          home='Kansas City Chiefs', away='Buffalo Bills', source_age=None):
    return {'id':f'{eid}-{book}-{market}-{player}-{side}-{line}-{minutes_ago}',
            'event_id':eid,'sport':'NFL',
            'commence_time':(T+timedelta(days=2)).isoformat(),
            'home_team':home,'away_team':away,'participant':player,
            'market':market,'bookmaker':book,'selection':side,'point':line,
            'american_odds':odds,'observed_at':(T-timedelta(minutes=minutes_ago)).isoformat(),
            'source_updated_at':(T-timedelta(minutes=source_age)).isoformat() if source_age is not None else None,
            'source':'The Odds API'}


def h2h_market():
    return [quote('SoftBook','Kansas City Chiefs',+120),quote('SoftBook','Buffalo Bills',-150),
            quote('Pinnacle','Kansas City Chiefs',-110),quote('Pinnacle','Buffalo Bills',-110),
            quote('Circa','Kansas City Chiefs',-110),quote('Circa','Buffalo Bills',-110)]


def test_ev_consensus_excludes_softbook_and_computes_correct_value():
    bets=value.scan(h2h_market(),T,min_ev_pct=1)
    assert len(bets)==1
    offer=bets[0]
    assert offer['quote']['selection']=='Kansas City Chiefs'
    assert offer['quote']['bookmaker']=='SoftBook'
    assert abs(offer['fair_probability']-0.5)<1e-9
    assert abs(offer['ev_pct']-10.)<1e-9
    assert offer['fair_american']==100
    assert set(offer['reference_books'])=={'Pinnacle','Circa'}
    assert offer['reference_count']==2
    assert offer['snapshot_id']


def test_rejects_no_two_sided_quotes_and_reference_shortage():
    odds=h2h_market()[:4]
    assert value.scan(odds,T,min_references=2)==[]
    assert value.scan(odds,T,min_references=1)
    odds=h2h_market()[:]
    odds.pop(3) # Pinnacle has no Bills side; only Circa left
    assert value.scan(odds,T,min_references=2)==[]


def test_point_exactness_and_player_identity_required():
    sides=['Over','Under']
    quotes=[]
    for book,pr in [('SoftBook',(+120,-150)),('Pinnacle',(-110,-110)),('Circa',(-110,-110))]:
        for side,odd in zip(sides,pr):
            quotes.append(quote(book,side,odd,market='player_reception_yds',line=55.5,player='Josh Allen'))
    assert len(value.scan(quotes,T))==1
    # One ref book prices a DIFFERENT player, must not be used as consensus
    for q in quotes:
        if q['bookmaker']=='Circa':q['participant']='Other Player'
    assert value.scan(quotes,T)==[]
    # Another ref book offers a different line, must not be used as consensus
    quotes=[]
    for book,pr,line in [('SoftBook',(+120,-150),55.5),('Pinnacle',(-110,-110),55.5),('Circa',(-110,-110),56.5)]:
        for side,odd in zip(sides,pr):quotes.append(quote(book,side,odd,'player_reception_yds',line,'Josh Allen'))
    assert value.scan(quotes,T)==[]


def test_spreads_require_opposing_signed_points():
    qs=[]
    for book, home_odds,away_odds in [('SoftBook',+120,-150),('Pinnacle',-110,-110),('Circa',-110,-110)]:
        qs.append(quote(book,'Kansas City Chiefs',home_odds,market='spreads',line=-3.5))
        qs.append(quote(book,'Buffalo Bills',away_odds,market='spreads',line=+3.5))
    assert len(value.scan(qs,T))==1
    for q in qs:
        if q['bookmaker']=='Circa' and q['selection']=='Buffalo Bills':q['point']=-3.5
    assert value.scan(qs,T)==[]


def test_over_under_game_total_and_unpriced_anytime_td():
    qs=[]
    for book,over,under in [('SoftBook',+120,-150),('Pinnacle',-110,-110),('Circa',-110,-110)]:
        qs.extend([quote(book,'Over',over,'totals',43.5),quote(book,'Under',under,'totals',43.5)])
    assert value.scan(qs,T)[0]['quote']['selection']=='Over'
    anytime=[quote(book,'Yes',+150,'player_anytime_td',None,'Josh Allen') for book in ['SoftBook','Circa','Pinnacle']]
    assert value.scan(anytime,T)==[]


def test_no_live_or_stale_provider_data_means_no_ev():
    qs=h2h_market()
    for q in qs:q['observed_at']=(T-timedelta(minutes=45)).isoformat()
    assert value.scan(qs,T)==[]
    qs=h2h_market()
    for q in qs:q['source_updated_at']=(T-timedelta(minutes=100)).isoformat()
    assert value.scan(qs,T)==[]
    qs=h2h_market()
    for q in qs:q['commence_time']=(T-timedelta(minutes=1)).isoformat()
    assert value.scan(qs,T)==[]


def test_does_not_count_history_twice_or_cross_games():
    qs=h2h_market()
    qs.extend([quote('Circa','Kansas City Chiefs',-110,minutes_ago=29),quote('Circa','Buffalo Bills',-110,minutes_ago=29)])
    assert len(value.scan(qs,T))==1
    qs=h2h_market()
    for q in qs:
        if q['bookmaker']=='Circa':q['event_id']='DIFFERENT'
    assert value.scan(qs,T)==[]


def test_limits_and_disagreement_screen():
    qs=h2h_market()
    assert value.scan(qs,T,min_ev_pct=11)==[]
    assert value.scan(qs,T,max_reference_range_pp=0)==value.scan(qs,T)
    qs=h2h_market()
    for q in qs:
        if q['bookmaker']=='Circa' and q['selection']=='Kansas City Chiefs':q['american_odds']=-160
        if q['bookmaker']=='Circa' and q['selection']=='Buffalo Bills':q['american_odds']=+130
    assert value.scan(qs,T,max_reference_range_pp=2)==[]


def test_market_category_unsupported_does_not_produce_fake_ev():
    qs=h2h_market()
    for q in qs:q['market']='player_anytime_td'
    assert value.scan(qs,T)==[]
    assert value.scan([],T)==[]


def test_prevent_ev_when_only_one_sided_candidate_offered():
    qs=h2h_market()
    qs=[q for q in qs if not (q['bookmaker']=='SoftBook' and q['selection']=='Buffalo Bills')]
    assert value.scan(qs,T,min_ev_pct=1)==[]


def test_hit_rates_are_descriptive_only_and_exact_comparisons():
    q=quote('Pinnacle','Over',-110,'player_reception_yds',50.5,'John Doe')
    rates=value.historical_hit_rates(q,[{'receiving_yards':i} for i in (30,55,65,49,60,0)])
    assert rates[5]=={'hits':3,'games':5,'hit_rate':.6}
    assert rates[10]['games']==6
    assert not value.historical_hit_rates(quote('Pinnacle','Yes',120,'player_anytime_td',None,'John Doe'),[{}])
    under=dict(q,selection='Under')
    assert value.historical_hit_rates(under,[{'receiving_yards':50.5}])[5]['hit_rate']==0.


def test_app_wires_crossbook_ev_to_each_game_and_prop_lab():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert 'from edgeforce import db, providers, models, parlays, ledger, value' in app
    assert 'display_value_feed(ev_quotes,prefix=' in app
    assert 'display_value_feed(props,prefix=' in app
    assert "['⭐ +EV bet finder','Best available prices','Odds history','Kalshi comparison']" in app
    assert 'crossbook-market-proxy-v0.4-UNCALIBRATED' in app
    assert 'value.historical_hit_rates' in app
    assert 'db.log_prediction(selected_bet' in app
    assert "result=providers.odds_event_props(sport" in app


def test_unequal_quote_timestamps_do_not_create_fake_two_way_market():
    qs=h2h_market()
    for q in qs:
        if q['bookmaker']=='SoftBook' and q['selection']=='Buffalo Bills':
            q['observed_at']=(T-timedelta(minutes=14)).isoformat()
    assert value.scan(qs,T)==[]
    qs=h2h_market()
    for q in qs:
        if q['bookmaker']=='Pinnacle' and q['selection']=='Buffalo Bills':
            q['source_updated_at']=(T-timedelta(minutes=28)).isoformat()
        if q['bookmaker']=='Pinnacle' and q['selection']=='Kansas City Chiefs':
            q['source_updated_at']=(T-timedelta(minutes=2)).isoformat()
    assert value.scan(qs,T)==[]


def test_feed_input_can_be_normalized_odds_api_snapshots(tmp_path):
    from edgeforce import providers, db
    source={'id':'GAME123','commence_time':(T+timedelta(days=2)).isoformat(),
        'home_team':'Kansas City Chiefs','away_team':'Buffalo Bills','bookmakers':[]}
    for book,ho,ao in [('SoftBook',120,-150),('Pinnacle',-110,-110),('Circa',-110,-110)]:
        source['bookmakers'].append({'title':book,'key':book.casefold(),
            'last_update':(T-timedelta(minutes=2)).isoformat(),
            'markets':[{'key':'h2h','last_update':(T-timedelta(minutes=2)).isoformat(),
               'outcomes':[{'name':'Kansas City Chiefs','price':ho},{'name':'Buffalo Bills','price':ao}]}]})
    quotes=providers.normalize_odds_event(source,'NFL',{'h2h'})
    for q in quotes:q['observed_at']=(T-timedelta(minutes=1)).isoformat()
    datafile=tmp_path/'value.sqlite3'
    db.init_db(datafile)
    ids=db.insert_snapshots(quotes,path=datafile)
    assert len(ids)==6
    from_database=db.latest_quotes('NFL',path=datafile)
    matched=value.scan(from_database,T)
    assert len(matched)==1 and abs(matched[0]['ev_pct']-10)<1e-7
    assert matched[0]['snapshot_id'] in ids
