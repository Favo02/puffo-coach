"""ZeppBridge SQLite database fetcher."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date
from typing import Any

from puffo_coach.config import require_zepp
from puffo_coach.fetchers.base import BaseFetcher
from puffo_coach.models import (
    DailyMetricRow,
    HealthBundle,
    HrBucket,
    SleepSession,
)

# Metrics attached to sleep sessions instead of daily vitals.
SLEEP_VITALS = ("respiratory_rate", "sleep_hrv", "sleep_rhr", "spo2_night_score")


class ZeppSqliteReader(BaseFetcher):
    """Fetches health data from a local ZeppBridge SQLite database."""

    def __init__(self) -> None:
        """Initialize the fetcher and require Zepp configuration."""
        self.db_path = require_zepp()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        bucket_hours: int = 6,
        **kwargs: Any,
    ) -> HealthBundle:
        """Fetch health data for the given date range.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            bucket_hours: Hours per HR/HRV aggregate bucket (must divide 24).

        Returns:
            HealthBundle containing sleep, daily metrics, and HR buckets.
        """
        uri = f"file:{self.db_path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row

            sleep = self._query_sleep(conn, from_date, to_date)
            daily = self._query_daily(conn, from_date, to_date)
            hr_buckets = self._query_hr_buckets(conn, from_date, to_date, bucket_hours)

            return HealthBundle(sleep=sleep, daily=daily, hr_buckets=hr_buckets)

    def _query_sleep(
        self, conn: sqlite3.Connection, from_date: date, to_date: date
    ) -> list[SleepSession]:
        """Query sleep sessions and attach sleep-related daily vitals."""
        query = """
            SELECT sleep_id, start_time, end_time, score, duration_minutes,
                   deep_minutes, light_minutes, rem_minutes, awake_minutes, wake_count
              FROM sleep_sessions
             WHERE date(start_time) BETWEEN ? AND ?
             ORDER BY start_time;
        """
        cur = conn.execute(query, (str(from_date), str(to_date)))
        sessions: list[SleepSession] = []
        for row in cur:
            sessions.append(SleepSession(
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
            ))

        # Attach sleep-related daily vitals to each session.
        if sessions:
            placeholders = ",".join(["?"] * len(SLEEP_VITALS))
            vitals_query = f"""
                SELECT date, metric, value FROM daily_metrics
                 WHERE date BETWEEN ? AND ? AND metric IN ({placeholders})
            """
            params: list[Any] = [str(from_date), str(to_date)] + list(SLEEP_VITALS)
            vitals_cur = conn.execute(vitals_query, params)

            vitals_by_date: dict[str, dict[str, float]] = defaultdict(dict)
            for row in vitals_cur:
                vitals_by_date[row["date"]][row["metric"]] = float(row["value"])

            for session in sessions:
                wake_date = session.end_time[:10]
                vitals = vitals_by_date.get(wake_date, {})
                session.resp_rate = vitals.get("respiratory_rate")
                session.sleep_hrv = vitals.get("sleep_hrv")
                session.sleep_rhr = vitals.get("sleep_rhr")
                session.spo2_night = vitals.get("spo2_night_score")

        return sessions

    def _query_daily(
        self, conn: sqlite3.Connection, from_date: date, to_date: date
    ) -> list[DailyMetricRow]:
        """Query all daily metrics, excluding sleep vitals (attached to sleep)."""
        placeholders = ",".join(["?"] * len(SLEEP_VITALS))
        query = f"""
            SELECT date, metric, value, unit
              FROM daily_metrics
             WHERE date BETWEEN ? AND ?
               AND metric NOT IN ({placeholders})
             GROUP BY date, metric
             ORDER BY date, metric;
        """
        params: list[Any] = [str(from_date), str(to_date)] + list(SLEEP_VITALS)
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

    def _query_hr_buckets(
        self, conn: sqlite3.Connection, from_date: date, to_date: date, bucket_hours: int
    ) -> list[HrBucket]:
        """Aggregate heart rate and HRV RMSSD into time buckets."""
        query = """
            SELECT date(timestamp) AS day,
                   (CAST(strftime('%H', timestamp) AS INTEGER) / ?) AS bucket_idx,
                   ROUND(AVG(CASE WHEN metric = 'heart_rate' THEN value END)) AS avg_hr,
                   MIN(CASE WHEN metric = 'heart_rate' THEN CAST(value AS INTEGER) END) AS min_hr,
                   MAX(CASE WHEN metric = 'heart_rate' THEN CAST(value AS INTEGER) END) AS max_hr,
                   ROUND(AVG(CASE WHEN metric = 'hrv_rmssd' THEN value END), 1) AS avg_hrv
              FROM metric_samples
             WHERE metric IN ('heart_rate', 'hrv_rmssd')
               AND date(timestamp) BETWEEN ? AND ?
             GROUP BY day, bucket_idx
             ORDER BY day, bucket_idx;
        """
        cur = conn.execute(query, (bucket_hours, str(from_date), str(to_date)))

        return [
            HrBucket(
                day=row["day"],
                start_hour=int(row["bucket_idx"]) * bucket_hours,
                end_hour=(int(row["bucket_idx"]) + 1) * bucket_hours,
                avg_hr=int(row["avg_hr"]) if row["avg_hr"] is not None else 0,
                min_hr=int(row["min_hr"]) if row["min_hr"] is not None else 0,
                max_hr=int(row["max_hr"]) if row["max_hr"] is not None else 0,
                avg_hrv=float(row["avg_hrv"]) if row["avg_hrv"] is not None else None,
            )
            for row in cur
        ]
