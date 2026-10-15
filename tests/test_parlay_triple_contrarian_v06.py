"""v0.6 three-leg and contrarian suite: synthetic bookmaker quotes only."""
from datetime import timedelta
from pathlib import Path

from edgeforce import opportunities
from test_opportunity_engine_v05 import NOW, mocked_nfl_slate


def test_five_three_leg_and_five_five_leg_tickets_from_same_slate():
    data=mocked_nfl_slate(14)
    for number,method in ((3,opportunities.build_three_leg_tickets),(5,opportunities.build_five_leg_tickets)):
        result=method(data,'DiscountBook',NOW)
        assert len(result['tickets'])==5, result
        assert result['eligible_games']>=number
        signatures=set()
        for ticket in result['tickets']:
            assert len(ticket['legs'])==number
            assert len({x['quote']['event_id'] for x in ticket['legs']})==number
            assert len({x['quote']['bookmaker'] for x in ticket['legs']})==1
            assert ticket['stress_ev_pct']>0
            assert ticket['nominal_probability']>ticket['conservative_probability']>0
            assert ticket['signature'] not in signatures
            signatures.add(ticket['signature'])
            assert all(x['ev_pct']>=1 for x in ticket['legs'])


def test_three_leg_has_higher_hit_proxy_than_five_leg_from_same_market():
    offers=mocked_nfl_slate(14)
    three=opportunities.build_three_leg_tickets(offers,'DiscountBook',NOW)['tickets'][0]
    five=opportunities.build_five_leg_tickets(offers,'DiscountBook',NOW)['tickets'][0]
    assert three['conservative_probability']>five['conservative_probability']
    assert three['decimal_price']<five['decimal_price']


def test_six_ranked_contrarians_from_distinct_games_and_corroborated_prices():
    data=mocked_nfl_slate(14)
    report=opportunities.rank_price_contrarians(data,NOW)
    assert len(report['picks'])==6, report
    assert report['reason'] is None
    assert len({x['quote']['event_id'] for x in report['picks']})==6
    assert all(x['offered_odds']>=100 for x in report['picks'])
    assert all(.30<=x['fair_probability']<.5 for x in report['picks'])
    assert all(x['reference_count']>=2 and x['stress_ev_pct']>0 for x in report['picks'])
    scores=[x['contrarian_score'] for x in report['picks']]
    assert scores==sorted(scores,reverse=True)
    assert all('public betting' in x['contrarian_reason'] for x in report['picks'])


def test_only_three_games_can_generate_three_leg_but_no_five_leg():
    offers=mocked_nfl_slate(3)
    assert len(opportunities.build_three_leg_tickets(offers,'DiscountBook',NOW)['tickets'])>=1
    assert opportunities.build_five_leg_tickets(offers,'DiscountBook',NOW)['tickets']==[]


def test_insufficient_distinct_contrarians_reports_truth_not_synthetic_picks():
    report=opportunities.rank_price_contrarians(mocked_nfl_slate(7),NOW)
    assert len(report['picks'])<6
    assert 'Only' in report['reason']


def test_stale_and_postkickoff_contrarian_market_returns_empty():
    offers=mocked_nfl_slate(14)
    for q in offers:q['observed_at']=(NOW-timedelta(hours=2)).isoformat()
    assert not opportunities.rank_price_contrarians(offers,NOW)['picks']
    offers=mocked_nfl_slate(14)
    for q in offers:q['commence_time']=(NOW-timedelta(hours=1)).isoformat()
    assert not opportunities.rank_price_contrarians(offers,NOW)['picks']


def test_no_corrupted_or_missing_bookmaker_coerced_into_three_leg():
    result=opportunities.build_three_leg_tickets(mocked_nfl_slate(14),'NonexistentBook',NOW)
    assert result['tickets']==[]


def test_ui_has_all_requested_sections_and_tracking():
    app=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert 'portfolio.optimize_portfolio' in app
    assert 'portfolio.optimize_portfolio' in app
    assert 'opportunities.rank_price_contrarians' in app
    assert 'Log #{i} {number}-leg research ticket' in app
    assert 'Price-contrarian only; public split not verified' in app


def test_three_leg_tickets_are_loggable_and_immutable(tmp_path):
    """Timestamped snapshots and a 3-leg ticket survive a ledger round-trip."""
    from datetime import datetime, timezone
    from edgeforce import db
    current=datetime.now(timezone.utc)
    offers=mocked_nfl_slate(9)
    for q in offers:
        q['observed_at']=(current-timedelta(minutes=1)).isoformat()
        q['source_updated_at']=(current-timedelta(minutes=1)).isoformat()
        q['commence_time']=(current+timedelta(days=3)).isoformat()
    file=tmp_path/'three-leg-audit.sqlite3'
    db.init_db(file)
    db.insert_snapshots(offers,path=file)
    stored=db.latest_quotes('NFL',path=file)
    ticket=opportunities.build_three_leg_tickets(stored,'DiscountBook',current)['tickets'][0]
    saved=db.log_ticket([r['snapshot_id'] for r in ticket['legs']],10.,
        ticket['nominal_probability'],ticket['theoretical_ev_pct']/100,
        label='v0.6 three-leg test',path=file)
    history=db.ticket_history(path=file)
    row=next(x for x in history if x['id']==saved)
    assert len(row['legs'])==3
    assert len({x['event_id'] for x in row['legs']})==3
    assert all(x['bookmaker']=='DiscountBook' for x in row['legs'])
    assert sorted(x['id'] for x in row['legs'])==sorted(r['snapshot_id'] for r in ticket['legs'])
