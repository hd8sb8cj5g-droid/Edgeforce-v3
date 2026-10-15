"""Cost-controlled, timestamped odds collector; schedule at a plan-appropriate rate."""
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
from edgeforce import db, providers


def run(sports,markets='h2h,spreads,totals',minimum_credits=15):
    load_dotenv()
    db.init_db()
    errors=0
    try:
        remaining=providers.odds_free_quota()
        if remaining is not None and remaining<minimum_credits:
            print('SKIPPED: odds API quota guard active; remaining credits below configured threshold.')
            return 0
    except providers.ProviderError as error:
        print('ERROR checking available API credits:',error)
        return 1
    for sport in sports:
        try:
            quotes=providers.odds_api(sport,markets=markets)
            ids=db.insert_snapshots(quotes)
            usage=providers.odds_usage()
            print(f'{datetime.now(timezone.utc).isoformat()} {sport}: '
                  f'saved {len(ids)} provider quotes across {len({q["event_id"] for q in quotes})} events; '
                  f'credits remaining: {usage.get("remaining","not reported")}')
            remaining=usage.get('remaining')
            if remaining is not None and str(remaining).isdigit() and int(remaining)<minimum_credits:
                print('STOP: configured quota guard reached after last market request.')
                break
        except providers.ProviderError as error:
            errors+=1
            print(f'{sport}: ERROR {error}')
    return errors


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sport',action='append',choices=['NFL','CFB'],required=True)
    parser.add_argument('--markets',default='h2h,spreads,totals',
                        help='One or more of h2h,spreads,totals; choose fewer to conserve credits')
    parser.add_argument('--min-remaining',type=int,default=15,
                        help='Stop collecting when API credits fall below this threshold (default 15)')
    options=parser.parse_args()
    raise SystemExit(1 if run(options.sport,options.markets,options.min_remaining) else 0)
