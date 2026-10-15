"""Login startup orchestration, independent of Streamlit and the data providers.

Use this only for bounded summary/featured feeds, not per-event player props or
full-season play-by-play downloads. A failure of one public source must not
invalidate successfully loaded data from other sources.
"""
from datetime import datetime, timezone


def should_sync_featured(quotes, now=None, cooldown_minutes=20):
    """Decide whether a live *featured-market* request is worth API credits."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('A timezone-aware UTC clock is required')
    for q in quotes or []:
        if q.get('source') == 'SYNTHETIC DEMO':
            continue
        try:
            from .db import parse_utc
            timestamp = parse_utc(q['observed_at'])
            kickoff = parse_utc(q['commence_time'])
            market = q['market']
            source_updated = parse_utc(q.get('source_updated_at')) if q.get('source_updated_at') else None
            if source_updated and (now-source_updated).total_seconds() > 75*60:
                continue
            if (timestamp is not None and kickoff is not None
                    and 0 <= (now-timestamp).total_seconds() < cooldown_minutes*60
                    and kickoff > now and market in ('h2h','spreads','totals')):
                return False
        except (KeyError, TypeError, ValueError):
            continue
    return True


def load_once(state, tasks, progress=None, force=False):
    """Run a bounded login preload; return per-source status without leaking URLs.

    `tasks` is an iterable of (display_name, loader) pairs. A loader may return
    a nonnegative count; unavailable sources raise and are shown as failures.
    Never caches credentials or error messages in the user's session state.
    """
    if state.get('login_preload_complete') and not force:
        return state['login_preload_results']
    results = []
    tasks = list(tasks)
    for number, (name, loader) in enumerate(tasks, 1):
        try:
            count = loader()
            status = 'Loaded'
            detail = str(count) if isinstance(count, int) and count >= 0 else 'Ready'
        except Exception as exc:
            # The exception can carry URLs containing API keys: NEVER show str(exc).
            status, detail = 'Unavailable', type(exc).__name__
        results.append({'source':name, 'status':status, 'detail':detail})
        if progress:
            progress(number, len(tasks), name)
    state['login_preload_results'] = results
    state['login_preload_complete'] = True
    state['login_preload_at'] = datetime.now(timezone.utc).isoformat()
    return results
