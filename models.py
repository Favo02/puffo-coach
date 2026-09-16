"""Domain models for health-context.

Pure dataclasses with no logic. These define the contract between
fetchers (which produce them) and the formatter (which consumes them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


# ── Meals (TimeTagger) ────────────────────────────────────────────────

@dataclass
class Meal:
    date: date
    time: time
    meal_type: str       # colazione | pranzo | cena | merenda
    food: str            # raw string from brackets, unparsed


# ── Sleep (ZeppBridge) ────────────────────────────────────────────────

@dataclass
class SleepStage:
    stage: str           # deep | light | rem | awake
    start_time: str      # ISO 8601
    end_time: str        # ISO 8601


@dataclass
class SleepSession:
    sleep_id: str
    start_time: str      # ISO 8601
    end_time: str        # ISO 8601
    score: int | None
    duration_min: int
    deep_min: int
    light_min: int
    rem_min: int
    awake_min: int
    wake_count: int | None
    stages: list[SleepStage] = field(default_factory=list)


# ── Health Vitals (ZeppBridge) ────────────────────────────────────────

@dataclass
class DailyMetricRow:
    """Single metric value for a single day (flat row from daily_metrics)."""
    date: str            # YYYY-MM-DD
    metric: str
    value: float
    unit: str


@dataclass
class HrHourly:
    """Hourly heart-rate aggregate for one hour of one day."""
    day: str             # YYYY-MM-DD
    hour: int            # 0–23
    avg_hr: int
    min_hr: int
    max_hr: int


@dataclass
class HealthBundle:
    """Container for all ZeppBridge health data."""
    sleep: list[SleepSession]
    daily: list[DailyMetricRow]
    hr_hourly: list[HrHourly]


# ── Activities (Strava) ──────────────────────────────────────────────

@dataclass
class ActivitySplit:
    """Per-km split from Strava's splits_metric."""
    split: int                          # 1-indexed km number
    distance: float                     # meters
    moving_time: int                    # seconds
    average_speed: float                # m/s
    average_heartrate: float | None
    elevation_difference: float | None
    pace_zone: int | None


@dataclass
class Activity:
    """A single workout/activity from Strava."""
    id: int
    name: str
    sport_type: str
    start_date_local: str               # ISO 8601 local time
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    total_elevation_gain: float | None
    average_speed: float | None         # m/s
    max_speed: float | None             # m/s
    average_heartrate: float | None     # bpm
    max_heartrate: float | None         # bpm
    average_cadence: float | None
    suffer_score: int | None
    calories: float | None
    description: str | None
    gear_name: str | None
    splits_metric: list[ActivitySplit] = field(default_factory=list)
