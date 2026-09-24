"""Pipeline execution and date helper utilities for Puffo Coach."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from puffo_coach.formatter import MarkdownFormatter
from puffo_coach.models import Activity, CategoryConfig, HealthBundle, Meal

VALID_HEALTH_HOURS = (1, 2, 3, 4, 6, 8, 12, 24)
DEFAULT_HEALTH_HOURS = 6

PRIMARY_SPORT_TYPES = (
    "Soccer",
    "Volleyball",
    "Beach Volleyball",
    "Workout",
    "Hike",
    "Run",
    "Ride",
)

DATE_PRESETS: list[tuple[str, str]] = [
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("last_7d", "Last 7 days"),
    ("this_week", "This week to date"),
    ("last_week", "Last week"),
    ("this_month", "This month to date"),
    ("last_30d", "Last 30 days"),
    ("last_month", "Last month"),
]


def get_date_preset(preset_key: str, reference_date: date | None = None) -> tuple[date, date]:
    """Calculate (from_date, to_date) for a preset key."""
    today = reference_date or date.today()

    if preset_key == "today":
        return today, today
    elif preset_key == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    elif preset_key == "last_7d":
        return today - timedelta(days=6), today
    elif preset_key == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif preset_key == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        end = today - timedelta(days=today.weekday() + 1)
        return start, end
    elif preset_key == "this_month":
        return today.replace(day=1), today
    elif preset_key == "last_30d":
        return today - timedelta(days=29), today
    elif preset_key == "last_month":
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        return first_of_prev_month, last_of_prev_month
    else:
        raise ValueError(f"Unknown date preset: '{preset_key}'")


@dataclass
class PipelineStats:
    """Summary counts from a pipeline run."""
    meals_count: int = 0
    activities_count: int = 0
    sleep_sessions_count: int = 0
    daily_metrics_count: int = 0
    hr_buckets_count: int = 0


@dataclass
class PipelineResult:
    """Complete result returned by the pipeline."""
    markdown: str
    stats: PipelineStats
    meals: list[Meal]
    activities: list[Activity]
    health: HealthBundle | None


def run_pipeline(
    from_date: date,
    to_date: date,
    configs: dict[str, CategoryConfig],
    progress_callback: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Execute data fetching and formatting for configured sources."""
    def notify(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    meals: list[Meal] = []
    activities: list[Activity] = []
    health: HealthBundle | None = None
    stats = PipelineStats()

    # ── Fetch meals from TimeTagger ───────────────────────────────────
    if configs.get("meals") and configs["meals"].enabled:
        from puffo_coach.fetchers.timetagger import TimeTaggerFetcher

        notify(f"Fetching meals from TimeTagger ({from_date} → {to_date})…")
        meals = TimeTaggerFetcher().fetch(from_date, to_date)
        stats.meals_count = len(meals)
        notify(f"✓ {len(meals)} meal(s) found.")

    # ── Fetch activities from Strava ──────────────────────────────────
    if configs.get("activities") and configs["activities"].enabled:
        from puffo_coach.fetchers.strava import StravaFetcher

        cfg = configs["activities"]
        notify(f"Fetching activities from Strava ({from_date} → {to_date})…")
        activities = StravaFetcher().fetch(
            from_date,
            to_date,
            sport_types=cfg.filter,
        )
        stats.activities_count = len(activities)
        notify(f"✓ {len(activities)} activity/ies found.")

    # ── Fetch health vitals from ZeppBridge ───────────────────────────
    if configs.get("health") and configs["health"].enabled:
        from puffo_coach.fetchers.zepp_sqlite import ZeppSqliteReader

        cfg = configs["health"]
        bucket_hours = cfg.detail_level if isinstance(cfg.detail_level, int) else DEFAULT_HEALTH_HOURS
        notify(f"Fetching health data from ZeppBridge ({from_date} → {to_date})…")
        health = ZeppSqliteReader().fetch(
            from_date,
            to_date,
            bucket_hours=bucket_hours,
        )
        stats.sleep_sessions_count = len(health.sleep)
        stats.daily_metrics_count = len(health.daily)
        stats.hr_buckets_count = len(health.hr_buckets)
        notify(
            f"✓ {len(health.sleep)} sleep session(s), "
            f"{len(health.daily)} daily metric row(s), "
            f"{len(health.hr_buckets)} HR bucket(s)."
        )

    # ── Format ────────────────────────────────────────────────────────
    notify("Formatting context into Markdown…")
    md = MarkdownFormatter(configs).render(
        meals=meals,
        activities=activities,
        health=health,
        from_date=from_date,
        to_date=to_date,
    )

    return PipelineResult(
        markdown=md,
        stats=stats,
        meals=meals,
        activities=activities,
        health=health,
    )
