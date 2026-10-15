"""Offline fixtures; these are NOT verification of the current 2026 injury reports."""
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from edgeforce import injury_intelligence as ii, accuracy_feedback as af

NOW=datetime(2026,10,15,18,tzinfo=timezone.utc)

def injury_rows():
    return pd.DataFrame([
      {'season':2026,'week':6,'season_type':'REG','team':'BUF','full_name':'Josh Allen','position':'QB','report_status':'Questionable','practice_status':'Limited','date_modified':(NOW-timedelta(hours=2)).isoformat()},
      {'season':2026,'week':6,'season_type':'REG','team':'KC','full_name':'Travis Kelce','position':'TE','report_status':'Out','practice_status':'DNP','date_modified':(NOW-timedelta(hours=1)).isoformat()},
      {'season':2026,'week':5,'season_type':'REG','team':'KC','full_name':'Patrick Mahomes','position':'QB','report_status':'Out','practice_status':'DNP','date_modified':(NOW-timedelta(days=8)).isoformat()},
    ])

def fake_offer(player,market='player_pass_yds',team='BUF'):
    return {'quote':{'sport':'NFL','event_id':'E','home_team':'Kansas City Chiefs','away_team':'Buffalo Bills',
                'market':market,'participant':player,'selection':'Over','american_odds':+120},
            'fair_probability':.5,'offered_odds':120,'ev_pct':10.}

def test_current_week_only_and_preserves_provenance():
    report=ii.prepare_reports(injury_rows(),2026,6,NOW)
    assert report['status']=='FRESH' and len(report['players'])==2
    assert report['latest_modified'] and report['fetched_at']==NOW.isoformat()
    assert not ii.injury_player(report,'Patrick Mahomes')
    assert ii.injury_player(report,'TRAVIS KELCE','KC')['status']=='OUT'

def test_out_excluded_and_questionable_held():
    report=ii.prepare_reports(injury_rows(),2026,6,NOW)
    assert ii.assess_offer(fake_offer('Travis Kelce'),report)['status']=='BLOCK'
    a=ii.assess_offer(fake_offer('Josh Allen'),report)
    assert a['status']=='HOLD' and a['stress_ev_pct'] == pytest.approx(1.2)
    assert a['stress_probability']==pytest.approx(.46)
    assert ii.assess_offer(fake_offer('Stefon Diggs'),report)['status']=='UNVERIFIED'

def test_missing_and_old_never_assume_healthy():
    missing=ii.prepare_reports(injury_rows(),2026,7,NOW)
    assert missing['status']=='MISSING'
    assert ii.assess_offer(fake_offer('Josh Allen'),missing)['status']=='UNVERIFIED'
    stale=ii.prepare_reports(injury_rows(),2026,6,NOW+timedelta(days=8))
    assert stale['status']=='STALE' and ii.assess_offer(fake_offer('Travis Kelce'),stale)['status']=='UNVERIFIED'

def test_name_suffix_and_dnp_is_not_out():
    assert ii.norm_name('D.K. Metcalf Jr.')==ii.norm_name('DK Metcalf')
    rows=injury_rows();rows.loc[1,'report_status']=''; rows.loc[1,'practice_status']='DNP'
    report=ii.prepare_reports(rows,2026,6,NOW)
    assert ii.assess_offer(fake_offer('Travis Kelce'),report)['status']=='REVIEW'

def test_unknown_future_and_ambiguous_report_never_cleared():
    future=injury_rows();future.loc[1,'date_modified']=(NOW+timedelta(days=1)).isoformat()
    report=ii.prepare_reports(future,2026,6,NOW)
    assert ii.assess_offer(fake_offer('Travis Kelce'),report)['status']=='UNVERIFIED'
    future.loc[0,'full_name']='Travis Kelce';future.loc[0,'date_modified']=(NOW-timedelta(hours=1)).isoformat()
    report=ii.prepare_reports(future,2026,6,NOW)
    assert ii.assess_offer(fake_offer('Travis Kelce'),report)['status']=='HOLD'

def test_non_nfl_not_labeled_injury_adjusted():
    report=ii.prepare_reports(injury_rows(),2026,6,NOW)
    o=fake_offer('Josh Allen');o['quote']['sport']='CFB'
    assert ii.assess_offer(o,report)['status']=='NOT_SUPPORTED'

def test_immutable_injury_context_roundtrip_older_tags():
    report=ii.prepare_reports(injury_rows(),2026,6,NOW)
    tag=ii.prediction_tags(ii.assess_offer(fake_offer('Josh Allen'),report),report)
    parsed=ii.historical_tag(tag)
    assert parsed['injury_status']=='HOLD' and parsed['injury_week']==6
    assert parsed['injury_source_modified_at']==report['latest_modified']
    assert ii.historical_tag('MARKET_CONSENSUS_NOT_VALIDATED')['injury_status']=='NOT_RECORDED'

def pred(p,outcome='WIN',market='h2h',stake=10,tags=None,odds=-110):
    return {'model_probability':p,'outcome':outcome,'market':market,'stake':stake,
            'american_odds':odds,'tags':tags,'realized_pnl':None}

def test_calibration_math_roi_and_no_future_outcomes():
    rows=[pred(.8,'WIN'),pred(.7,'LOSS'),pred(.9,'PUSH'),pred(.6,None)]
    report=af.summarize(rows,min_sample=3)
    o=report['overall']
    assert o['predictions']==4 and o['pending']==1 and o['n']==2
    assert o['mean_predicted']==pytest.approx(.75)
    assert o['brier']==pytest.approx((.2**2+.7**2)/2)
    assert o['observed_win_rate']==.5 and not o['mature']
    assert o['research_pnl']==pytest.approx(round(10*100/110-10,2))
    assert sum(x['n'] for x in report['calibration_bins'])==2

def test_cohort_segmentation_old_context_not_fabricated():
    tag=json.dumps({'type':'market_consensus_injury_research','injury_status':'REVIEW'})
    rows=[pred(.55,'WIN',tags=tag),pred(.6,'LOSS',market='spreads',tags='oldtag'),pred(.7,'VOID')]
    report=af.summarize(rows)
    assert report['by_injury_status']['REVIEW']['n']==1
    assert report['by_injury_status']['NOT_RECORDED']['n']==1
    assert report['overall']['n']==2

def test_invalid_probability_no_nan_leakage():
    rows=[pred(float('nan'),'WIN'),pred(None,'LOSS')]
    report=af.summarize(rows)
    assert report['overall']['calibration_n']==0 and report['calibration_bins']==[]

def test_no_old_player_row_reused_when_other_player_fresh():
    raw=injury_rows()
    raw.loc[1,'date_modified']=(NOW-timedelta(days=12)).isoformat()
    report=ii.prepare_reports(raw,2026,6,NOW)
    assert report['status']=='FRESH'
    assert ii.assess_offer(fake_offer('Travis Kelce'),report)['status']=='UNVERIFIED'


def test_scheduled_result_reconciliation_requires_hosted_database(monkeypatch):
    from scripts.refresh_accuracy import run
    monkeypatch.delenv('EDGEFORCE_POSTGRES_URL',raising=False)
    with pytest.raises(RuntimeError,match='PostgreSQL'):run(NOW)


def test_github_actions_scheduled_settlement_does_not_need_odds_key():
    from pathlib import Path
    workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/accuracy-feedback.yml').read_text()
    assert 'EDGEFORCE_POSTGRES_URL' in workflow and 'ODDS_API_KEY' not in workflow
    assert 'scripts.refresh_accuracy' in workflow


def test_ui_contains_injury_gate_and_historical_feedback():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'app.py').read_text()
    assert "'🩹 Injuries'" in text
    assert 'accuracy_feedback.summarize(rows)' in text
    assert 'injury_intelligence.prediction_tags(assessment,injury_record)' in text
    assert 'confirmed_out' in text
    assert "all_quotes=[q for q in pre_injury_quotes" in text

def test_end_to_end_pregame_injury_snapshot_settlement_accuracy(tmp_path,monkeypatch):
    from edgeforce import db
    from datetime import timedelta
    monkeypatch.setattr(db,'utcnow',lambda:NOW.isoformat())
    path=str(tmp_path/'edgeforce.sqlite3')
    db.init_db(path)
    q={'event_id':'TEST1','sport':'NFL','commence_time':(NOW+timedelta(days=2)).isoformat(),
       'home_team':'Kansas City Chiefs','away_team':'Buffalo Bills','bookmaker':'SoftBook',
       'market':'player_reception_yds','participant':'Travis Kelce','selection':'Over','point':55.5,
       'american_odds':120,'observed_at':(NOW-timedelta(minutes=2)).isoformat(),
       'source':'The Odds API','raw':{}}
    ids=db.insert_snapshots([q],path=path)
    report=ii.prepare_reports(injury_rows(),2026,6,NOW)
    assessment=ii.assess_offer(fake_offer('Travis Kelce'),report)
    assert assessment['status']=='BLOCK'
    # A blocked pick can still be explicitly logged as HISTORICAL evidence via
    # API (not as a recommendation); tags preserve the contradictory source.
    tags=ii.prediction_tags(assessment,report)
    pred_id=db.log_prediction(ids[0],.45,'C','test-research',rationale='Injury evidence test',
                              stake=10,tags=tags,path=path)
    db.settle(pred_id,'LOSS',source='verified box score',note='fixture',path=path)
    history=db.prediction_history(path=path)
    feedback=af.summarize(history)
    assert feedback['by_injury_status']['BLOCK']['n']==1
    assert feedback['overall']['research_roi']==pytest.approx(-1.0)
    assert feedback['overall']['brier']==pytest.approx(.45**2)
    assert history[0]['tags']==tags
    # Immutable odds never changed when a result was recorded.
    assert db.snapshots_for_event('TEST1',path=path)[0]['american_odds']==120


def test_weekly_provider_loader_contract_mocked(monkeypatch):
    import sys,types
    from edgeforce import providers
    class Frame:
        def to_pandas(self):return injury_rows()
    monkeypatch.setitem(sys.modules,'nflreadpy',types.SimpleNamespace(load_injuries=lambda y:Frame()))
    frame=providers.nfl_injury_reports(2026)
    assert len(frame)==3

def test_background_refresh_only_uses_verified_finals(monkeypatch):
    from scripts import refresh_accuracy
    from edgeforce import db,providers,ledger,models,nfl_schedule
    monkeypatch.setenv('EDGEFORCE_POSTGRES_URL','postgresql://example-without-access')
    monkeypatch.setattr(db,'init_db',lambda:None)
    monkeypatch.setattr(db,'prediction_history',lambda:[{'sport':'NFL','outcome':None,
           'commence_time':(NOW-timedelta(days=2)).isoformat()}])
    raw=pd.DataFrame([{'season':2026,'week':5,'gameday':'2026-10-11','gametime':'13:00',
        'away_team':'BUF','home_team':'KC','home_score':28,'away_score':21,
        'game_type':'REG','game_id':'2026_05_BUF_KC'}])
    monkeypatch.setattr(providers,'nfl_games',lambda year:raw)
    received=[]
    monkeypatch.setattr(ledger,'auto_settle',lambda games: received.extend(games) or {'settled':1,'skipped':0})
    assert refresh_accuracy.run(NOW,seasons=[2026])==1
    assert len(received)==1
