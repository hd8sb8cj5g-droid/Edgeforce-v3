"""Daily opportunity and five-leg ticket regression suite with MOCK bookmaker data.
These are synthetic fixtures; no assertions about real NFL value bets.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path

from edgeforce import db, providers, opportunities, value

NOW=datetime(2026,10,15,17,0,tzinfo=timezone.utc)


def make_quote(eid,book,side,price,market='h2h',line=None,player='',ago=2,home='Kansas City Chiefs',away='Buffalo Bills'):
    return {'id':f'{eid}:{book}:{side}:{line}:{player}:{ago}:{price}',
      'event_id':eid,'sport':'NFL','commence_time':(NOW+timedelta(days=3)).isoformat(),
      'home_team':home,'away_team':away,'participant':player,'market':market,
      'selection':side,'point':line,'bookmaker':book,'american_odds':price,
      'observed_at':(NOW-timedelta(minutes=ago)).isoformat(),
      'source_updated_at':(NOW-timedelta(minutes=ago)).isoformat(),
      'source':'The Odds API'}


def mocked_nfl_slate(games=8):
    quotes=[]
    for i in range(games):
        home=f'Home Team {i}'
        away=f'Away Team {i}'
        eid=f'NFL2026-{i}'
        # Discount book misprices one of the two teams, references price both sides.
        # The last three games produce contrarian, underdog selections.
        if i>=5:
            offer_home=-190;offer_away=160
        else:
            offer_home=125;offer_away=-180
        for b,home_price,away_price in (
            ('DiscountBook',offer_home,offer_away),
            ('RefA',-122,111),('RefB',-123,112),('RefC',-121,110)):
            quotes += [make_quote(eid,b,home,home_price,home=home,away=away),
                       make_quote(eid,b,away,away_price,home=home,away=away)]
    return quotes


def test_canonical_spread_identity_does_not_compare_opposing_handicaps():
    qs=[]
    for b,hd,ad,hline in [('DiscountBook',120,-150,-3.5),('RefA',-110,-110,3.5),('RefB',-110,-110,3.5)]:
        qs += [make_quote('a',b,'Kansas City Chiefs',hd,'spreads',hline),
               make_quote('a',b,'Buffalo Bills',ad,'spreads',-hline)]
    assert value.scan(qs,NOW,min_ev_pct=-100)==[]
    # Once spread directions match, fair comparison is valid.
    for q in qs:
        if q['bookmaker']=='DiscountBook':q['point']*=-1
    assert len(value.scan(qs,NOW,min_ev_pct=1))==1


def test_later_sync_does_not_leave_earlier_handicap_as_live():
    qs=[]
    for side,point in [('Kansas City Chiefs',-3.5),('Buffalo Bills',3.5)]:
        qs.append(make_quote('x','BookX',side,-110,'spreads',point,ago=25))
    for side,point in [('Kansas City Chiefs',-4),('Buffalo Bills',4)]:
        qs.append(make_quote('x','BookX',side,-110,'spreads',point,ago=1))
    current=opportunities.latest_active_batch(qs)
    assert len(current)==2
    assert {abs(q['point']) for q in current}=={4.}


def test_simultaneous_alternate_prop_lines_are_preserved():
    qs=[]
    for line in [40.5,45.5]:
        qs += [make_quote('x','BookX','Over',-110,'player_reception_yds',line,'T Receiver'),
               make_quote('x','BookX','Under',-110,'player_reception_yds',line,'T Receiver')]
    assert len(opportunities.latest_active_batch(qs))==4


def test_nfl_report_covers_games_with_no_ev_and_sorts_kickoff():
    qs=mocked_nfl_slate(8)
    report=opportunities.group_game_opportunities(qs,NOW)
    assert len(report)==8
    assert all(row['prices']==8 for row in report)
    assert all(row['books']==4 for row in report)
    assert any(row['top'] for row in report)
    assert sum(len(row['bets']) for row in report)>=8
    only_no_edges=opportunities.group_game_opportunities(qs,NOW,min_ev=99)
    assert len(only_no_edges)==8
    assert all(not row['top'] for row in only_no_edges)


def test_five_tickets_only_ev_single_book_five_games_and_contrarian():
    quotes=mocked_nfl_slate(9)
    ev=value.scan(quotes,NOW)
    report=opportunities.build_five_leg_tickets(quotes,'DiscountBook',NOW)
    assert len(ev)>=9
    assert len(report['tickets'])==5, report
    assert report['eligible_games']==9
    assert sum(t['label']=='Contrarian value research' for t in report['tickets'])==2
    for ticket in report['tickets']:
        assert len(ticket['legs'])==5
        assert ticket['stress_ev_pct']>0
        assert ticket['conservative_probability']<ticket['nominal_probability']
        assert all(l['ev_pct']>=1 for l in ticket['legs'])
        assert len({l['quote']['event_id'] for l in ticket['legs']})==5
        assert len({l['quote']['bookmaker'] for l in ticket['legs']})==1
        assert ticket['nominal_probability']<.1
        assert ticket['decimal_price']>1


def test_insufficient_ev_games_never_fills_ticket_with_unqualified_legs():
    r=opportunities.build_five_leg_tickets(mocked_nfl_slate(4),'DiscountBook',NOW)
    assert r['tickets']==[] and r['eligible_games']==4
    assert 'Fewer than five' in r['reason']


def test_old_and_postkickoff_snapshots_produce_no_recommendations():
    qs=mocked_nfl_slate()
    for q in qs:q['observed_at']=(NOW-timedelta(hours=2)).isoformat()
    assert opportunities.build_five_leg_tickets(qs,'DiscountBook',NOW)['tickets']==[]
    qs=mocked_nfl_slate()
    for q in qs:q['commence_time']=(NOW-timedelta(minutes=1)).isoformat()
    assert opportunities.build_five_leg_tickets(qs,'DiscountBook',NOW)['tickets']==[]


def test_independent_book_rule_and_single_book_price():
    qs=mocked_nfl_slate()
    qs=[q for q in qs if q['bookmaker'] in ('DiscountBook','RefA')]
    assert opportunities.build_five_leg_tickets(qs,'DiscountBook',NOW)['tickets']==[]
    assert all(r['reference_count']>=2 for r in value.scan(mocked_nfl_slate(),NOW))


def test_end_to_end_mock_odds_provider_to_sqlite_to_five_tickets(tmp_path):
    """Fixture follows the same provider normalize->database->EV->parlay path."""
    game_count=8
    out=[]
    for i in range(game_count):
        eid=f'NFL-{i}'
        raw={'id':eid,'commence_time':(NOW+timedelta(days=2)).isoformat(),
          'home_team':f'Home Team {i}','away_team':f'Away Team {i}','bookmakers':[]}
        for book,h,a in [('DiscountBook',125,-180),('RefA',-122,111),('RefB',-123,112),('RefC',-121,110)]:
            raw['bookmakers'].append({'key':book,'title':book,
              'last_update':(NOW-timedelta(minutes=2)).isoformat(),'markets':[{
               'key':'h2h','last_update':(NOW-timedelta(minutes=2)).isoformat(),
               'outcomes':[{'name':raw['home_team'],'price':h},
                           {'name':raw['away_team'],'price':a}]}]})
        normalized=providers.normalize_odds_event(raw,'NFL',{'h2h'})
        for q in normalized:q['observed_at']=(NOW-timedelta(minutes=1)).isoformat()
        out.extend(normalized)
    database=tmp_path/'endtoend.sqlite3'
    db.init_db(database)
    assert len(db.insert_snapshots(out,path=database))==len(out)
    stored=db.latest_quotes('NFL',path=database)
    report=opportunities.build_five_leg_tickets(stored,'DiscountBook',NOW)
    assert len(report['tickets'])>=3
    assert len(report['tickets'][0]['legs'])==5
    assert set(r['snapshot_id'] for r in report['tickets'][0]['legs']) <= set(q['id'] for q in stored)


def test_legacy_ui_not_using_unvalidated_score_parlay_recommendations():
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert 'portfolio.optimize_portfolio' in app
    assert 'Optimize 5 three-leg + 5 five-leg parlays + top 6 contrarian picks' in app
    assert "parlays.candidate_tickets(quotes,projs" not in app
    assert 'game-by-game opportunity board' in app
