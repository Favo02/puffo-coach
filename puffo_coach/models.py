"""Domain models for Puffo Coach.

Pure dataclasses with no logic. These define the contract between
fetchers (which produce them) and the formatter (which consumes them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


# ── Category Configuration ────────────────────────────────────────────

@dataclass
class CategoryConfig:
    """Per-category filter and detail level settings.

    Attributes:
        enabled: Whether this category is active.
        filter: Types to include. Empty list means all (no filter).
                Used by activities for sport type filtering.
        detail_level: For health: hours per HR/HRV bucket (1–24, must divide 24).
                      Ignored by meals and activities.
    """
    enabled: bool = False
    filter: list[str] = field(default_factory=list)
    detail_level: int = 6


# ── Meals (TimeTagger) ────────────────────────────────────────────────

@dataclass
class Meal:
    date: date
    time: time
    meal_type: str       # colazione | pranzo | cena | merenda
    food: str            # raw string from brackets, or UNKNOWN


# ── Sleep (ZeppBridge) ────────────────────────────────────────────────

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
    resp_rate: float | None = None
    sleep_hrv: float | None = None
    sleep_rhr: float | None = None
    spo2_night: float | None = None


# ── Health Vitals (ZeppBridge) ────────────────────────────────────────

@dataclass
class DailyMetricRow:
    """Single metric value for a single day (flat row from daily_metrics)."""
    date: str            # YYYY-MM-DD
    metric: str
    value: float
    unit: str


@dataclass
class HrBucket:
    """Heart-rate and HRV aggregate for a time bucket within a day."""
    day: str             # YYYY-MM-DD
    start_hour: int      # 0–23
    end_hour: int        # 1–24 (exclusive)
    avg_hr: int
    min_hr: int
    max_hr: int
    avg_hrv: float | None = None


@dataclass
class HealthBundle:
    """Container for all ZeppBridge health data."""
    sleep: list[SleepSession]
    daily: list[DailyMetricRow]
    hr_buckets: list[HrBucket]


# ── Activities (Strava) ──────────────────────────────────────────────

@dataclass
class HrChunk:
    """Heart rate stats for a time chunk of a non-GPS activity."""
    chunk: int           # 1-indexed
    start_time: str      # M:SS or MM:SS
    end_time: str        # M:SS or MM:SS
    avg_hr: int
    min_hr: int
    max_hr: int


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
    min_heartrate: float | None         # bpm (from stream, non-GPS only)
    average_cadence: float | None
    relative_effort: int | None         # Strava's suffer_score
    description: str | None
    gear_name: str | None
    has_gps: bool = False
    splits_metric: list[ActivitySplit] = field(default_factory=list)
    hr_chunks: list[HrChunk] = field(default_factory=list)
