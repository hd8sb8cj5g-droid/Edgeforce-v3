"""Regression coverage for Streamlit Cloud sportsbook-odds sync.

Uses a fake PostgreSQL connection to avoid requiring a running Neon database.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from edgeforce import cloud_db


class InsertRecorder:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_cloud_sync_defaults_observed_at_to_utc_without_name_error():
    recorder = InsertRecorder()

    @contextmanager
    def fake_connect(path=None):
        yield recorder

    quote = {
        "event_id": "test-event-1",
        "sport": "NFL",
        "commence_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "home_team": "Minnesota Vikings",
        "away_team": "Green Bay Packers",
        "bookmaker": "Example Book",
        "market": "h2h",
        "selection": "Minnesota Vikings",
        "american_odds": -110,
        "source": "The Odds API",
    }
    with patch.object(cloud_db, "connect", fake_connect):
        snapshot_ids = cloud_db.insert_snapshots([quote])

    assert len(snapshot_ids) == 1
    assert len(recorder.calls) == 1
    sql, values = recorder.calls[0]
    assert "INSERT INTO edgeforce.odds_snapshots" in sql
    assert "observed_at" in sql
    assert values[0] == snapshot_ids[0]
    observed = datetime.fromisoformat(values[1].replace("Z", "+00:00"))
    assert observed.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - observed).total_seconds()) < 10


def test_cloud_clock_is_defined_and_utc():
    value = cloud_db._utcnow()
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset().total_seconds() == 0
