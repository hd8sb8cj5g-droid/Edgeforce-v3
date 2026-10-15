"""Free NFLverse final-score settlement runner for GitHub Actions.

Uses durable EDGEFORCE_POSTGRES_URL. Does not use sportsbook credits, does not
create forecasts, and does not invent box-score player-prop settlements.
"""
from datetime import datetime, timezone
import os
from edgeforce import db, ledger, providers, nfl_schedule, models, game_hub


def run(asof=None, seasons=None):
    if not os.getenv('EDGEFORCE_POSTGRES_URL'):
        raise RuntimeError('Durable PostgreSQL connection not configured; refusing ephemeral scheduled settlement')
    now=asof or datetime.now(timezone.utc)
    db.init_db()
    if seasons is None:
        active=game_hub.nfl_season_for_date(now)
        # Resolve pending prior-season picks after the turn of the year.
        pending=[r for r in db.prediction_history() if r['sport']=='NFL' and not r.get('outcome')]
        years={game_hub.nfl_season_for_date(db.parse_utc(r['commence_time'])) for r in pending}
        seasons=sorted(y for y in years if active-1<=y<=active)
    total=0
    for year in seasons:
        raw=providers.nfl_games(int(year))
        schedule=nfl_schedule.prepare_schedule(raw,int(year),asof=now)
        if schedule.empty:
            raise RuntimeError(f'No NFLverse games for {year}; settlement withheld')
        finals=schedule[schedule.status=='Final']
        if finals.empty:
            print(f'{year}: no verified final scores; no settlement changes')
            continue
        records=models.scores_from_schedule(finals,asof=now)
        result=ledger.auto_settle(records)
        total+=result['settled']
        print(f'{year}: {len(records)} final games, {result["settled"]} predictions settled, {result["skipped"]} skipped')
    return total


if __name__=='__main__':
    print('Completed automatic verified NFL score reconciliation:',run())
