"""Unit tests for newly added features and edge case fixes."""

import unittest
from datetime import date, time

from puffo_coach.fetchers.strava import StravaFetcher
from puffo_coach.fetchers.timetagger import _parse_meal_food
from puffo_coach.formatter import MarkdownFormatter
from puffo_coach.models import (
    Activity,
    ActivitySplit,
    CategoryConfig,
    DailyMetricRow,
    HealthBundle,
    HrBucket,
    HrChunk,
    Meal,
    SleepSession,
)


class TestMealParsing(unittest.TestCase):
    def test_meal_without_brackets_returns_unknown(self) -> None:
        ds = "#pranzo a casa"
        tag_end = len("#pranzo")
        self.assertEqual(_parse_meal_food(ds, tag_end), "UNKNOWN")

    def test_meal_with_intermediate_tag_returns_unknown(self) -> None:
        ds = "#pranzo #friends [Mario, Luigi]"
        tag_end = len("#pranzo")
        self.assertEqual(_parse_meal_food(ds, tag_end), "UNKNOWN")

    def test_meal_with_direct_brackets_returns_content(self) -> None:
        ds = "#colazione al bar [brioche, cappuccio]"
        tag_end = len("#colazione")
        self.assertEqual(_parse_meal_food(ds, tag_end), "brioche, cappuccio")


class TestFormatting(unittest.TestCase):
    def setUp(self) -> None:
        self.configs = {
            "meals": CategoryConfig(enabled=True),
            "activities": CategoryConfig(enabled=True),
            "health": CategoryConfig(enabled=True, detail_level=6),
        }
        self.formatter = MarkdownFormatter(self.configs)

    def test_sleep_single_row_with_vitals_no_stages(self) -> None:
        session = SleepSession(
            sleep_id="123",
            start_time="2026-09-01T23:30:00",
            end_time="2026-09-02T07:15:00",
            score=88,
            duration_min=465,
            deep_min=80,
            light_min=280,
            rem_min=75,
            awake_min=30,
            wake_count=2,
            resp_rate=14.5,
            sleep_hrv=52.0,
            sleep_rhr=48.0,
            spo2_night=97.0,
        )
        health = HealthBundle(sleep=[session], daily=[], hr_buckets=[])
        out = self.formatter.render(meals=[], activities=[], health=health, from_date="2026-09-01", to_date="2026-09-02")

        self.assertIn('<night date="2026-09-01"', out)
        self.assertIn('resp_rate="14.5"', out)
        self.assertIn('sleep_hrv="52"', out)
        self.assertIn('sleep_rhr="48"', out)
        self.assertIn('spo2_night="97"', out)
        self.assertNotIn('<stages>', out)

    def test_activity_no_calories_and_relative_effort(self) -> None:
        act = Activity(
            id=1,
            name="Evening Run",
            sport_type="Run",
            start_date_local="2026-09-01T18:00:00",
            distance_m=10000.0,
            moving_time_s=3000,
            elapsed_time_s=3000,
            total_elevation_gain=50.0,
            average_speed=3.33,
            max_speed=4.5,
            average_heartrate=155.0,
            max_heartrate=175.0,
            min_heartrate=None,
            average_cadence=160.0,
            relative_effort=65,
            description=None,
            gear_name=None,
            has_gps=True,
        )
        out = self.formatter.render(meals=[], activities=[act], health=None, from_date="2026-09-01", to_date="2026-09-01")

        self.assertIn('relative_effort="65"', out)
        self.assertNotIn('calories', out)
        self.assertNotIn('suffer_score', out)
        self.assertIn('elevation_m="50"', out)

    def test_activity_ball_sport_no_elevation(self) -> None:
        act = Activity(
            id=2,
            name="Volleyball match",
            sport_type="Volleyball",
            start_date_local="2026-09-01T20:00:00",
            distance_m=0.0,
            moving_time_s=3600,
            elapsed_time_s=3600,
            total_elevation_gain=120.0,
            average_speed=None,
            max_speed=None,
            average_heartrate=140.0,
            max_heartrate=170.0,
            min_heartrate=95.0,
            average_cadence=None,
            relative_effort=40,
            description=None,
            gear_name=None,
            has_gps=False,
            hr_chunks=[
                HrChunk(chunk=1, start_time="0:00", end_time="6:00", avg_hr=130, min_hr=95, max_hr=150)
            ],
        )
        out = self.formatter.render(meals=[], activities=[act], health=None, from_date="2026-09-01", to_date="2026-09-01")

        self.assertNotIn('elevation_m', out)
        self.assertNotIn('distance_km', out)
        self.assertIn('<hr_chunks>', out)
        self.assertIn('<chunk n="1" start="0:00" end="6:00" avg_hr="130" min_hr="95" max_hr="150"/>', out)

    def test_health_vitals_curated_metrics_only(self) -> None:
        daily = [
            DailyMetricRow(date="2026-09-01", metric="resting_hr", value=48.0, unit="bpm"),
            DailyMetricRow(date="2026-09-01", metric="steps", value=9200.0, unit="steps"),
            DailyMetricRow(date="2026-09-01", metric="active_minutes", value=45.0, unit="min"),
            DailyMetricRow(date="2026-09-01", metric="training_load", value=450.0, unit="score"),
            DailyMetricRow(date="2026-09-01", metric="vo2max", value=58.5, unit="ml/kg/min"),
            DailyMetricRow(date="2026-09-01", metric="pai_total", value=120.0, unit="score"),
            # Excluded metrics that should NOT be rendered in <day .../>
            DailyMetricRow(date="2026-09-01", metric="calories", value=2200.0, unit="kcal"),
            DailyMetricRow(date="2026-09-01", metric="readiness", value=85.0, unit="score"),
            DailyMetricRow(date="2026-09-01", metric="stress", value=30.0, unit="score"),
        ]
        buckets = [
            HrBucket(
                day="2026-09-01",
                start_hour=0,
                end_hour=6,
                avg_hr=55,
                min_hr=48,
                max_hr=68,
                avg_hrv=45.5,
                min_hrv=22.0,
                max_hrv=78.0,
            ),
        ]
        health = HealthBundle(sleep=[], daily=daily, hr_buckets=buckets)
        out = self.formatter.render(meals=[], activities=[], health=health, from_date="2026-09-01", to_date="2026-09-01")

        # Curated metrics MUST be included
        self.assertIn('resting_hr="48"', out)
        self.assertIn('steps="9200"', out)
        self.assertIn('active_minutes="45"', out)
        self.assertIn('training_load="450"', out)
        self.assertIn('vo2max="58.5"', out)
        self.assertIn('pai_total="120"', out)

        # Other metrics MUST be excluded
        self.assertNotIn('calories', out)
        self.assertNotIn('readiness', out)
        self.assertNotIn('stress', out)

        # HR/HRV bucket min/max/avg
        self.assertIn('<bucket start="00:00" end="06:00" avg_hr="55" min_hr="48" max_hr="68" avg_hrv="45.5" min_hrv="22" max_hrv="78"/>', out)


class TestStravaSplitMerging(unittest.TestCase):
    def test_over_50km_all_splits_grouped_in_5km(self) -> None:
        raw_splits = [
            ActivitySplit(split=i, distance=1000.0, moving_time=300, average_speed=3.33, average_heartrate=140.0, elevation_difference=5.0, pace_zone=None)
            for i in range(1, 56)  # 55 km
        ]
        merged = StravaFetcher._merge_splits(raw_splits, 5)
        # 55 km divided by 5 = 11 splits
        self.assertEqual(len(merged), 11)
        self.assertEqual(merged[0].distance, 5000.0)
        self.assertEqual(merged[0].moving_time, 1500)
        self.assertEqual(merged[0].split, 1)
        self.assertEqual(merged[10].split, 11)
        self.assertEqual(merged[10].distance, 5000.0)


if __name__ == "__main__":
    unittest.main()
