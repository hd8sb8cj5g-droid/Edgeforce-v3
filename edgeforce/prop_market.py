"""Explain player-prop coverage without equating missing EV with missing odds."""
from collections import defaultdict
from datetime import datetime, timezone

from . import value


def summarize(quotes, now=None):
    """Pure diagnostics for stored, fresh, and independent two-sided prop quotes."""
    now=value.utc(now) if now is not None else datetime.now(timezone.utc)
    raw=[q for q in quotes if str(q.get('market','')).startswith('player_')]
    fresh=value._fresh_quotes(raw,now)
    grouped=defaultdict(lambda:defaultdict(list))
    for q in fresh:
        ident=value._identity(q)
        if ident is not None:
            grouped[ident][str(q['bookmaker']).casefold()].append(q)
    pair_groups={}
    for identity,books in grouped.items():
        two_sided=[name for name,rows in books.items() if value._valid_pair(rows,identity[1])]
        if two_sided:pair_groups[identity]=two_sided
    comparable=sum(len(books)>=3 for books in pair_groups.values())
    if not raw:
        reason='No player-prop offers have been returned or stored for this game.'
    elif not fresh:
        reason='Offers exist, but they are stale, started, or are one-sided markets that cannot be priced by the EV engine.'
    elif not pair_groups:
        reason='Prices exist, but not enough matching Over/Under sides are available at the same player and line.'
    elif not comparable:
        reason='Some sportsbooks quote both sides, but fewer than three books offer the same player and line (one offering book plus two independent reference books).'
    else:
        reason='Comparable quotes exist. If EV results are empty, none passed the minimum EV or market-disagreement filters.'
    return {'raw_quotes':len(raw),'fresh_quotes':len(fresh),
            'players':len({str(q.get('participant','')).strip() for q in raw if q.get('participant')}),
            'bookmakers':len({q.get('bookmaker') for q in raw}),
            'markets':len({q.get('market') for q in raw}),
            'two_sided_groups':len(pair_groups),
            'reference_qualified_groups':comparable,'reason':reason}


def display_rows(quotes):
    """Plain rows for Streamlit, with no artificial probability estimates."""
    return [{
        'Player':q.get('participant','') or '(not specified)',
        'Market':q['market'], 'Side':q['selection'], 'Line':q.get('point'),
        'Odds':q['american_odds'],'Book':q['bookmaker'],
        'Observed UTC':str(q.get('observed_at','')),
        'Source updated UTC':str(q.get('source_updated_at') or 'Unknown')
    } for q in quotes if str(q.get('market','')).startswith('player_')]
