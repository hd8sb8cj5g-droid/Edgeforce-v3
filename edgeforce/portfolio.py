"""Across-ticket concentration controls for EV-qualified research parlays.

Each ticket is same-book, includes different games, and has positive stressed EV.
Exposure caps are preferences, NOT guarantees or estimates of profitability.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from math import log
from datetime import datetime, timezone

from . import opportunities


def candidate_tickets(offers, bookmaker, legs, now=None, min_ev=1., min_references=2,
                      max_disagreement=5., pool_limit=22):
    """Build a bounded slate-wide candidate set; never combine different books."""
    if legs not in (3, 5):
        raise ValueError('Parlays require three or five legs')
    now = now or datetime.now(timezone.utc)
    qualified = opportunities._qualifying_book_pool(offers, bookmaker, now, min_ev,
                                                    min_references, max_disagreement)
    events = defaultdict(list)
    for row in qualified:
        events[row['quote']['event_id']].append(row)
    if len(events) < legs:
        return []
    for event in events:
        events[event].sort(key=lambda r: (-opportunities._conservative_probability(r), -r['ev_pct']))
    # Represent all games before adding alternatives, preserving slate coverage.
    first = [vals[0] for vals in events.values()]
    first.sort(key=lambda r: (-opportunities._conservative_probability(r), -r['ev_pct']))
    primary = first[:pool_limit]
    secondary = sorted([r for vals in events.values() for r in vals[1:3]],
                       key=lambda r: (-opportunities._conservative_probability(r), -r['ev_pct']))
    pool = primary + secondary[:max(0, pool_limit-len(primary))]
    results = []
    for chosen in combinations(pool, legs):
        if len({r['quote']['event_id'] for r in chosen}) != legs:
            continue
        if any(float(r['fair_probability']) < .35 for r in chosen):
            continue
        ticket = opportunities._ticket_from_legs(chosen, bookmaker)
        if ticket['stress_ev_pct'] <= 0:
            continue
        results.append(ticket)
    results.sort(key=lambda t: (-t['conservative_probability'], -t['stress_ev_pct']))
    return results


def _team_key(q, side):
    from .models import team_key
    return team_key(q[side], 'NFL')


def _ticketscore(ticket, picked, legs_used, events_used, teams_used, target_leg_cap,
                 target_game_cap, diversification):
    # Per-leg log probability is comparable across 3- and 5-leg tickets.
    base = log(max(1e-8, ticket['conservative_probability'])) / ticket['leg_count']
    base += .06 * min(.35, max(0, ticket['stress_ev_pct'])/100)
    legids = set(ticket['signature'])
    events = {r['quote']['event_id'] for r in ticket['legs']}
    teams = [_team_key(r['quote'], side) for r in ticket['legs'] for side in ('home_team','away_team')]
    leg_reuse = sum(max(0, legs_used[k] - target_leg_cap + 1) for k in legids)
    game_reuse = sum(max(0, events_used[k] - target_game_cap + 1) for k in events)
    max_overlap = max((len(legids & set(t['signature'])) for t in picked), default=0)
    team_reuse = sum(max(0, teams_used[k]-target_game_cap*2+1) for k in teams)
    # Penalize concentration even before a soft cap is crossed.
    # Convex reuse cost reduces worst-case common-leg knockouts.
    progressive = sum(legs_used[k]**2 for k in legids)
    penalty = (diversification * (0.32*leg_reuse + 0.09*game_reuse +
                                  0.05*progressive + 0.06*max_overlap + 0.008*team_reuse))
    return base-penalty


def _exposure(selected):
    leg_c, game_c, team_c = Counter(), Counter(), Counter()
    for ticket in selected:
        for r in ticket['legs']:
            leg_c[r['snapshot_id']] += 1
            game_c[r['quote']['event_id']] += 1
            team_c[_team_key(r['quote'], 'home_team')] += 1
            team_c[_team_key(r['quote'], 'away_team')] += 1
    return leg_c, game_c, team_c


def optimize_portfolio(offers, bookmaker, now=None, min_ev=1., min_references=2,
                       target_leg_cap=2, target_game_cap=5, diversification=1.0,
                       count_per_length=5):
    """Choose two groups jointly, penalizing shared legs and team/game exposure.

    Does not claim reduced overlap creates winning picks. Data may not support all
    requested tickets; never fill with negative EV or fake quotes.
    """
    if not bookmaker:
        return {'three': [], 'five': [], 'warnings': ['No sportsbook selected.'],
                'leg_exposure': {}, 'game_exposure': {}, 'team_exposure': {}, 'max_shared_legs': 0,
                'available_candidates': {3: 0, 5: 0}}
    if target_leg_cap < 1 or target_game_cap < 1 or not 0 <= diversification <= 3:
        raise ValueError('Invalid portfolio concentration settings')
    pools = {n: candidate_tickets(offers, bookmaker, n, now, min_ev, min_references) for n in (3, 5)}
    selected = []
    counts = Counter()
    warnings = []
    # Interleave lengths to control concentration across all ten tickets.
    for round_index in range(count_per_length):
        for length in (3, 5):
            if counts[length] >= count_per_length:
                continue
            candidates = [c for c in pools[length] if c['signature'] not in
                          {o['signature'] for o in selected}]
            if length == 5 and round_index >= max(0, count_per_length-2):
                contrarians = [c for c in candidates if c['contrarian_legs'] == 1]
                if contrarians:
                    candidates = contrarians
            if not candidates:
                continue
            le, ge, te = _exposure(selected)
            winner = max(candidates, key=lambda c: _ticketscore(
                c, selected, le, ge, te, target_leg_cap, target_game_cap, diversification))
            chosen = dict(winner, label='Portfolio-diversified EV research')
            selected.append(chosen)
            counts[length] += 1
    leg_exp, game_exp, team_exp = _exposure(selected)
    shared = max((len(set(a['signature']) & set(b['signature']))
                  for i,a in enumerate(selected) for b in selected[i+1:]),default=0)
    if counts[3] < count_per_length or counts[5] < count_per_length:
        warnings.append('Insufficient qualifying distinct-game combinations for the requested number of tickets.')
    if any(n > target_leg_cap for n in leg_exp.values()):
        warnings.append('Some legs exceed the preferred repeat limit; caps are soft because slate coverage is limited.')
    if any(n > target_game_cap for n in game_exp.values()):
        warnings.append('Some games exceed the preferred exposure limit; fewer qualifying games may be available.')
    if counts[5] >= 2 and sum(t['contrarian_legs']==1 for t in selected if t['leg_count']==5) < 2:
        warnings.append('Two qualifying single-contrarian five-leg tickets could not be supported by this slate.')
    return {'three': [t for t in selected if t['leg_count']==3],
            'five': [t for t in selected if t['leg_count']==5],
            'warnings': warnings,
            'leg_exposure': dict(leg_exp), 'game_exposure': dict(game_exp),
            'team_exposure': dict(team_exp), 'max_shared_legs': shared,
            'available_candidates': {k: len(v) for k,v in pools.items()}}
