"""ZeppBridge SQLite database fetcher."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from config import require_zepp
from fetchers.base import BaseFetcher
from models import (
    DailyMetricRow,
    HealthBundle,
    HrHourly,
    SleepSession,
    SleepStage,
)


class ZeppSqliteReader(BaseFetcher):
    """Fetches health data from a local ZeppBridge SQLite database."""

    def __init__(self) -> None:
        """Initialize the fetcher and require Zepp configuration."""
        self.db_path = require_zepp()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        detail_level: str = "medium",
        metrics: list[str] | None = None,
        **kwargs: Any,
    ) -> HealthBundle:
        """Fetch health data for the given date range.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            detail_level: 'low', 'medium', or 'high'. Controls sleep stages and hourly HR.
            metrics: Explicit list of daily metrics to query. When provided,
                     this overrides the detail-level-based defaults entirely.

        Returns:
            HealthBundle containing sleep, daily metrics, and hourly HR (if high detail).
        """
        uri = f"file:{self.db_path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row

            sleep = self._query_sleep(conn, from_date, to_date, detail_level)
            daily = self._query_daily(conn, from_date, to_date, metrics or [])

            hr_hourly: list[HrHourly] = []
            if detail_level == "high":
                hr_hourly = self._query_hr_hourly(conn, from_date, to_date)

            return HealthBundle(sleep=sleep, daily=daily, hr_hourly=hr_hourly)

    def _query_sleep(
        self, conn: sqlite3.Connection, from_date: date, to_date: date, detail_level: str
    ) -> list[SleepSession]:
        query = """
            SELECT sleep_id, start_time, end_time, score, duration_minutes,
                   deep_minutes, light_minutes, rem_minutes, awake_minutes, wake_count
              FROM sleep_sessions
             WHERE date(start_time) BETWEEN ? AND ?
             ORDER BY start_time;
        """
        cur = conn.execute(query, (str(from_date), str(to_date)))
        sessions = []
        for row in cur:
            session = SleepSession(
                sleep_id=row["sleep_id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                score=row["score"],
                duration_min=row["duration_minutes"],
                deep_min=row["deep_minutes"],
                light_min=row["light_minutes"],
                rem_min=row["rem_minutes"],
                awake_min=row["awake_minutes"],
                wake_count=row["wake_count"],
            )
            
            if detail_level == "high":
                stage_query = """
                    SELECT stage, start_time, end_time 
                      FROM sleep_stages 
                     WHERE sleep_id = ? 
                     ORDER BY start_time;
                """
                stage_cur = conn.execute(stage_query, (session.sleep_id,))
                session.stages = [
                    SleepStage(
                        stage=s_row["stage"],
                        start_time=s_row["start_time"],
                        end_time=s_row["end_time"],
                    )
                    for s_row in stage_cur
                ]
                
            sessions.append(session)
            
        return sessions

    def _query_daily(
        self, conn: sqlite3.Connection, from_date: date, to_date: date,
        metrics: list[str],
    ) -> list[DailyMetricRow]:
        """Query daily metrics for the given list.

        The caller (CLI) is responsible for choosing which metrics to include
        based on detail level and user overrides. This method just queries
        whatever it's told to.
        """
        if not metrics:
            return []

        placeholders = ",".join(["?"] * len(metrics))
        query = f"""
            SELECT date, metric, value, unit
              FROM daily_metrics
             WHERE date BETWEEN ? AND ?
               AND metric IN ({placeholders})
             GROUP BY date, metric
             ORDER BY date, metric;
        """
        params = [str(from_date), str(to_date)] + metrics
        cur = conn.execute(query, params)
        
        return [
            DailyMetricRow(
                date=row["date"],
                metric=row["metric"],
                value=float(row["value"]) if row["value"] is not None else 0.0,
                unit=row["unit"],
            )
            for row in cur
        ]

    def _query_hr_hourly(
        self, conn: sqlite3.Connection, from_date: date, to_date: date
    ) -> list[HrHourly]:
        query = """
            SELECT date(timestamp) AS day,
                   CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                   ROUND(AVG(value)) AS avg_hr,
                   MIN(CAST(value AS INTEGER)) AS min_hr,
                   MAX(CAST(value AS INTEGER)) AS max_hr
              FROM metric_samples
             WHERE metric = 'heart_rate'
               AND date(timestamp) BETWEEN ? AND ?
             GROUP BY day, hour
             ORDER BY day, hour;
        """
        cur = conn.execute(query, (str(from_date), str(to_date)))
        
        return [
            HrHourly(
                day=row["day"],
                hour=int(row["hour"]),
                avg_hr=int(row["avg_hr"]),
                min_hr=int(row["min_hr"]),
                max_hr=int(row["max_hr"]),
            )
            for row in cur
        ]
