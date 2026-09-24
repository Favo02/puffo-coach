"""Markdown formatter with XML-structured output for LLM consumption."""

from __future__ import annotations

import collections
from datetime import date, time
from typing import Any

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


class MarkdownFormatter:
    """Renders domain objects into XML-in-Markdown."""

    def __init__(self, configs: dict[str, CategoryConfig]) -> None:
        """Initialize with category configuration.

        Args:
            configs: Dict mapping category name ('meals', 'activities', 'health')
                     to its CategoryConfig.
        """
        self._configs = configs

    def render(
        self,
        meals: list[Meal],
        activities: list[Activity],
        health: HealthBundle | None,
        from_date: date | str,
        to_date: date | str,
    ) -> str:
        parts = [f"# Personal Context: {from_date} → {to_date}\n"]

        if meals:
            parts.append(self._render_meals(meals))

        if health:
            parts.append(self._render_health(health))

        if activities:
            parts.append(self._render_activities(activities))

        return "\n".join(parts)

    # ── Meals ─────────────────────────────────────────────────────────

    def _render_meals(self, meals: list[Meal]) -> str:
        parts = ["<meals>"]
        by_date: dict[date, list[Meal]] = collections.defaultdict(list)
        for meal in meals:
            by_date[meal.date].append(meal)

        for d in sorted(by_date.keys()):
            parts.append(f'<day date="{d.isoformat()}">')
            for m in sorted(by_date[d], key=lambda x: x.time):
                parts.append(f'  <meal time="{m.time.strftime("%H:%M")}" type="{m.meal_type}">{m.food}</meal>')
            parts.append("</day>")

        parts.append("</meals>")
        return "\n".join(parts)

    # ── Health (vitals + sleep) ───────────────────────────────────────

    def _render_health(self, health: HealthBundle) -> str:
        parts = []
        if health.daily or health.hr_buckets:
            parts.append(self._render_vitals(health))
        if health.sleep:
            parts.append(self._render_sleep(health.sleep))
        return "\n".join(parts)

    def _render_vitals(self, health: HealthBundle) -> str:
        daily_map = self._pivot_daily_metrics(health.daily)
        parts = ["<vitals>"]

        hr_by_day: dict[str, list[HrBucket]] = collections.defaultdict(list)
        if health.hr_buckets:
            for b in health.hr_buckets:
                hr_by_day[b.day].append(b)

        all_days = sorted(set(list(daily_map.keys()) + list(hr_by_day.keys())))

        for day in all_days:
            attrs = [f'date="{day}"']
            metrics = daily_map.get(day, {})
            for k, v in sorted(metrics.items()):
                attrs.append(f'{k}="{self._fmt_val(v)}"')

            attr_str = " ".join(attrs)

            if day in hr_by_day and hr_by_day[day]:
                parts.append(f"<day {attr_str}>")
                parts.append("  <hr_buckets>")
                for b in sorted(hr_by_day[day], key=lambda x: x.start_hour):
                    start_str = f"{b.start_hour:02d}:00"
                    end_str = f"{b.end_hour:02d}:00" if b.end_hour < 24 else "24:00"
                    b_attrs = [
                        f'start="{start_str}"',
                        f'end="{end_str}"',
                        f'avg_hr="{b.avg_hr}"',
                        f'min_hr="{b.min_hr}"',
                        f'max_hr="{b.max_hr}"',
                    ]
                    if b.avg_hrv is not None:
                        b_attrs.append(f'avg_hrv="{self._fmt_val(b.avg_hrv)}"')
                    parts.append(f"    <bucket {' '.join(b_attrs)}/>")
                parts.append("  </hr_buckets>")
                parts.append("</day>")
            else:
                parts.append(f"<day {attr_str}/>")

        parts.append("</vitals>")
        return "\n".join(parts)

    def _render_sleep(self, sessions: list[SleepSession]) -> str:
        parts = ["<sleep>"]

        for s in sorted(sessions, key=lambda x: x.start_time):
            attrs = [
                f'date="{s.start_time[:10]}"',
                f'score="{s.score if s.score is not None else 0}"',
                f'total_min="{s.duration_min}"',
                f'deep="{s.deep_min}"',
                f'light="{s.light_min}"',
                f'rem="{s.rem_min}"',
                f'awake="{s.awake_min}"',
                f'wakes="{s.wake_count if s.wake_count is not None else 0}"',
                f'start="{self._format_time(s.start_time)}"',
                f'end="{self._format_time(s.end_time)}"',
            ]
            if s.resp_rate is not None:
                attrs.append(f'resp_rate="{self._fmt_val(s.resp_rate)}"')
            if s.sleep_hrv is not None:
                attrs.append(f'sleep_hrv="{self._fmt_val(s.sleep_hrv)}"')
            if s.sleep_rhr is not None:
                attrs.append(f'sleep_rhr="{self._fmt_val(s.sleep_rhr)}"')
            if s.spo2_night is not None:
                attrs.append(f'spo2_night="{self._fmt_val(s.spo2_night)}"')

            parts.append(f"<night {' '.join(attrs)}/>")

        parts.append("</sleep>")
        return "\n".join(parts)

    # ── Activities ────────────────────────────────────────────────────

    @staticmethod
    def _classify_sport(sport_type: str) -> str:
        s = sport_type.lower()
        if "beach" in s and "volley" in s:
            return "beach_volleyball"
        if "volley" in s:
            return "volleyball"
        if "soccer" in s or "football" in s:
            return "soccer"
        if "workout" in s or "weight" in s or "crossfit" in s:
            return "workout"
        if "hike" in s:
            return "hike"
        if "run" in s:
            return "run"
        if "ride" in s:
            return "ride"
        return "other"

    def _render_activities(self, activities: list[Activity]) -> str:
        parts = ["<activities>"]

        for act in sorted(activities, key=lambda x: x.start_date_local):
            date_str = act.start_date_local[:10]
            dur_str = self._format_duration(act.moving_time_s)
            dist_km = round(act.distance_m / 1000, 1)
            sport = self._classify_sport(act.sport_type)

            attrs = [
                f'date="{date_str}"',
                f'type="{act.sport_type}"',
                f'name="{act.name}"',
                f'duration="{dur_str}"',
            ]

            if sport in ("ride", "run", "hike"):
                attrs.append(f'distance_km="{dist_km}"')
                if act.total_elevation_gain is not None:
                    attrs.append(f'elevation_m="{int(act.total_elevation_gain)}"')
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.average_cadence is not None:
                    attrs.append(f'avg_cadence="{int(act.average_cadence)}"')
                if act.relative_effort is not None:
                    attrs.append(f'relative_effort="{act.relative_effort}"')

            elif sport == "soccer":
                if act.has_gps and act.distance_m > 0:
                    attrs.append(f'distance_km="{dist_km}"')
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.min_heartrate is not None:
                    attrs.append(f'min_hr="{int(act.min_heartrate)}"')
                if act.relative_effort is not None:
                    attrs.append(f'relative_effort="{act.relative_effort}"')

            elif sport in ("volleyball", "beach_volleyball"):
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.min_heartrate is not None:
                    attrs.append(f'min_hr="{int(act.min_heartrate)}"')
                if act.relative_effort is not None:
                    attrs.append(f'relative_effort="{act.relative_effort}"')

            elif sport == "workout":
                if act.has_gps and act.distance_m > 0:
                    attrs.append(f'distance_km="{dist_km}"')
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.min_heartrate is not None:
                    attrs.append(f'min_hr="{int(act.min_heartrate)}"')
                if act.relative_effort is not None:
                    attrs.append(f'relative_effort="{act.relative_effort}"')

            else:  # other
                if act.distance_m > 0:
                    attrs.append(f'distance_km="{dist_km}"')
                if act.total_elevation_gain is not None and act.total_elevation_gain > 0:
                    attrs.append(f'elevation_m="{int(act.total_elevation_gain)}"')
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.min_heartrate is not None:
                    attrs.append(f'min_hr="{int(act.min_heartrate)}"')
                if act.relative_effort is not None:
                    attrs.append(f'relative_effort="{act.relative_effort}"')

            has_children = bool(act.hr_chunks or act.splits_metric)
            if not has_children:
                parts.append(f"<activity {' '.join(attrs)}/>")
            else:
                parts.append(f"<activity {' '.join(attrs)}>")
                if act.hr_chunks:
                    parts.append("  <hr_chunks>")
                    for c in act.hr_chunks:
                        chunk_attrs = [
                            f'n="{c.chunk}"',
                            f'start="{c.start_time}"',
                            f'end="{c.end_time}"',
                            f'avg_hr="{c.avg_hr}"',
                            f'min_hr="{c.min_hr}"',
                            f'max_hr="{c.max_hr}"',
                        ]
                        parts.append(f"    <chunk {' '.join(chunk_attrs)}/>")
                    parts.append("  </hr_chunks>")

                if act.splits_metric:
                    parts.append("  <splits>")
                    for s in act.splits_metric:
                        split_attrs = [f'n="{s.split}"', f'time="{self._format_pace(s.moving_time)}"']
                        if s.distance > 1500:
                            split_attrs.append(f'dist_km="{round(s.distance / 1000, 1)}"')
                        if s.average_heartrate is not None:
                            split_attrs.append(f'avg_hr="{int(s.average_heartrate)}"')
                        if s.elevation_difference is not None:
                            sign = "+" if s.elevation_difference > 0 else ""
                            split_attrs.append(f'elev_diff="{sign}{s.elevation_difference:.1f}"')
                        parts.append(f"    <km {' '.join(split_attrs)}/>")
                    parts.append("  </splits>")
                parts.append("</activity>")

        parts.append("</activities>")
        return "\n".join(parts)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _fmt_val(v: float) -> str:
        """Format a numeric value: integers stay clean, floats get 1 decimal."""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if isinstance(v, float):
            return f"{v:.1f}"
        return str(v)

    @staticmethod
    def _format_duration(seconds: int) -> str:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @staticmethod
    def _format_time(iso_str: str) -> str:
        if "T" in iso_str:
            return iso_str.split("T")[1][:5]
        return iso_str[11:16]

    @staticmethod
    def _format_pace(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"

    @staticmethod
    def _pivot_daily_metrics(rows: list[DailyMetricRow]) -> dict[str, dict[str, float]]:
        metric_map = {
            "resting_hr": "resting_hr",
            "readiness": "readiness",
            "steps": "steps",
            "calories": "calories",
            "active_calories": "active_cal",
            "vo2max": "vo2max",
            "training_load": "training_load",
            "physical_readiness": "physical_readiness",
            "mental_readiness": "mental_readiness",
            "stress": "stress",
            "pai_total": "pai_total",
            "hrv_readiness": "hrv_readiness",
            "rhr_readiness": "rhr_readiness",
        }

        result: dict[str, dict[str, float]] = collections.defaultdict(dict)
        for r in rows:
            mapped = metric_map.get(r.metric, r.metric)
            result[r.date][mapped] = r.value
        return dict(result)
