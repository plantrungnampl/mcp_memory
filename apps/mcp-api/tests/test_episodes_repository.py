from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from viberecall_mcp.repositories.episodes import create_episode, list_recent_raw_episodes, list_timeline_episodes


class _DummyMappings:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def all(self) -> list[dict]:
        return self._rows


class _DummyResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> _DummyMappings:
        return _DummyMappings(self._rows)


class _DummySession:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}
        self._rows = rows or []
        self.commits = 0

    async def execute(self, statement, params):  # noqa: ANN001
        self.statement = str(statement)
        self.params = dict(params)
        return _DummyResult(self._rows)

    async def commit(self) -> None:
        self.commits += 1


def test_create_episode_coerces_reference_time_to_utc_datetime() -> None:
    session = _DummySession()

    asyncio.run(
        create_episode(
            session,
            episode_id="ep_test",
            project_id="proj_test",
            content="episode",
            reference_time="2026-03-02T12:00:00Z",
            metadata_json="{}",
        )
    )

    assert session.params["reference_time"] == datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
    assert session.commits == 1


def test_timeline_query_omits_null_time_filters() -> None:
    session = _DummySession()
    rows = asyncio.run(
        list_timeline_episodes(
            session,
            project_id="proj_test",
            from_time=None,
            to_time=None,
            limit=20,
            offset=0,
        )
    )

    assert rows == []
    assert "cast(:from_time as timestamptz)" not in session.statement
    assert "cast(:to_time as timestamptz)" not in session.statement
    assert "from_time" not in session.params
    assert "to_time" not in session.params


def test_timeline_query_includes_time_filters_when_present() -> None:
    session = _DummySession()
    rows = asyncio.run(
        list_timeline_episodes(
            session,
            project_id="proj_test",
            from_time="2026-03-02T00:00:00Z",
            to_time="2026-03-02T23:59:59Z",
            limit=20,
            offset=0,
        )
    )

    assert rows == []
    assert "cast(:from_time as timestamptz)" in session.statement
    assert "cast(:to_time as timestamptz)" in session.statement
    assert session.params["from_time"] == datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
    assert session.params["to_time"] == datetime(2026, 3, 2, 23, 59, 59, tzinfo=timezone.utc)


def test_timeline_rows_serialize_datetimes_to_iso_strings() -> None:
    session = _DummySession(
        rows=[
            {
                "episode_id": "ep_1",
                "reference_time": datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
                "ingested_at": datetime(2026, 3, 2, 12, 30, tzinfo=timezone.utc),
                "summary": "summary",
                "metadata_json": {"source": "test"},
            }
        ]
    )

    rows = asyncio.run(
        list_timeline_episodes(
            session,
            project_id="proj_test",
            from_time=None,
            to_time=None,
            limit=20,
            offset=0,
        )
    )

    assert rows[0]["reference_time"] == "2026-03-02T12:00:00+00:00"
    assert rows[0]["ingested_at"] == "2026-03-02T12:30:00+00:00"


def test_recent_raw_episodes_query_uses_offset() -> None:
    session = _DummySession()

    rows = asyncio.run(
        list_recent_raw_episodes(
            session,
            project_id="proj_test",
            query="bug",
            window_seconds=300,
            limit=5,
            offset=2,
        )
    )

    assert rows == []
    assert "offset :offset" in session.statement
    assert session.params["offset"] == 2
