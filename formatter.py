"""Markdown formatter with XML-structured output for LLM consumption."""

import collections
from datetime import date, time
from typing import Any

from models import (
    Activity, ActivitySplit, CategoryConfig, DailyMetricRow, HealthBundle,
    HrHourly, Meal, SleepSession, SleepStage,
)


class MarkdownFormatter:
    """Renders domain objects into XML-in-Markdown, respecting per-category detail levels."""

    def __init__(self, configs: dict[str, CategoryConfig]) -> None:
        """Initialize with per-category configuration.

        Args:
            configs: Dict mapping category name ('meals', 'activities', 'health')
                     to its CategoryConfig with detail_level.
        """
        self._configs = configs

    def _detail(self, category: str) -> str:
        """Get the detail level for a category."""
        return self._configs[category].detail_level

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
    # Meals are always rendered fully — compression has minimal benefit
    # given the low data volume (~3–5 entries/day).

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
        detail = self._detail("health")
        parts = []
        if health.daily:
            parts.append(self._render_vitals(health, detail))
        if health.sleep:
            parts.append(self._render_sleep(health.sleep, detail))
        return "\n".join(parts)

    def _render_vitals(self, health: HealthBundle, detail: str) -> str:
        daily_map = self._pivot_daily_metrics(health.daily)
        parts = ["<vitals>"]

        if detail == "high":
            hr_by_day: dict[str, list[HrHourly]] = collections.defaultdict(list)
            if health.hr_hourly:
                for h in health.hr_hourly:
                    hr_by_day[h.day].append(h)

            for day, metrics in sorted(daily_map.items()):
                attrs = [f'date="{day}"']
                for k, v in sorted(metrics.items()):
                    attrs.append(f'{k}="{self._fmt_val(v)}"')

                attr_str = " ".join(attrs)

                if day in hr_by_day:
                    parts.append(f"<day {attr_str}>")
                    parts.append("  <hr_hourly>")
                    for hr in sorted(hr_by_day[day], key=lambda x: x.hour):
                        parts.append(f'    <h hour="{hr.hour}" avg="{hr.avg_hr}" min="{hr.min_hr}" max="{hr.max_hr}"/>')
                    parts.append("  </hr_hourly>")
                    parts.append("</day>")
                else:
                    parts.append(f"<day {attr_str}/>")

        elif detail == "medium":
            for day, metrics in sorted(daily_map.items()):
                attrs = [f'date="{day}"']
                for k, v in sorted(metrics.items()):
                    attrs.append(f'{k}="{self._fmt_val(v)}"')
                parts.append(f"<day {' '.join(attrs)}/>")

        else:  # low
            metrics_acc: dict[str, list[float]] = collections.defaultdict(list)
            for metrics in daily_map.values():
                for k, v in metrics.items():
                    metrics_acc[k].append(v)

            days_count = len(daily_map)

            def get_stats(key: str) -> tuple[float, float, float] | None:
                if key not in metrics_acc or not metrics_acc[key]:
                    return None
                vals = metrics_acc[key]
                return sum(vals) / len(vals), min(vals), max(vals)

            summary_parts = [f"{days_count} days."]

            rhr = get_stats("resting_hr")
            if rhr:
                summary_parts.append(f"Resting HR: avg {int(rhr[0])} ({int(rhr[1])}–{int(rhr[2])}).")

            steps = get_stats("steps")
            if steps:
                summary_parts.append(f"Steps: avg {int(steps[0])}/day.")

            readiness = get_stats("readiness")
            if readiness:
                summary_parts.append(f"Readiness: avg {int(readiness[0])}.")

            hrv = get_stats("sleep_hrv")
            if hrv:
                summary_parts.append(f"Sleep HRV: avg {int(hrv[0])} ms.")

            spo2 = get_stats("spo2_night")
            if spo2:
                summary_parts.append(f"SpO₂ night: avg {int(spo2[0])}.")

            parts.append(" ".join(summary_parts))

        parts.append("</vitals>")
        return "\n".join(parts)

    def _render_sleep(self, sessions: list[SleepSession], detail: str) -> str:
        parts = ["<sleep>"]

        if detail == "high":
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
                parts.append(f"<night {' '.join(attrs)}>")
                if s.stages:
                    parts.append("  <stages>")
                    for stage in s.stages:
                        parts.append(
                            f'    <s stage="{stage.stage}" '
                            f'start="{self._format_time(stage.start_time)}" '
                            f'end="{self._format_time(stage.end_time)}"/>'
                        )
                    parts.append("  </stages>")
                parts.append("</night>")

        elif detail == "medium":
            for s in sorted(sessions, key=lambda x: x.start_time):
                total_hr = round(s.duration_min / 60, 1)
                attrs = [
                    f'date="{s.start_time[:10]}"',
                    f'score="{s.score if s.score is not None else 0}"',
                    f'total_hr="{total_hr}"',
                    f'deep="{s.deep_min}"',
                    f'rem="{s.rem_min}"',
                ]
                parts.append(f"<night {' '.join(attrs)}/>")

        else:  # low
            if sessions:
                count = len(sessions)
                scores = [s.score for s in sessions if s.score is not None]
                avg_score = int(sum(scores) / len(scores)) if scores else 0
                avg_dur = round(sum(s.duration_min for s in sessions) / (count * 60), 1)
                avg_deep = int(sum(s.deep_min for s in sessions) / count)
                avg_rem = int(sum(s.rem_min for s in sessions) / count)

                parts.append(
                    f"{count} nights. Avg score: {avg_score}. Avg duration: {avg_dur}h. "
                    f"Avg deep: {avg_deep} min. Avg REM: {avg_rem} min."
                )

        parts.append("</sleep>")
        return "\n".join(parts)

    # ── Activities ────────────────────────────────────────────────────

    def _render_activities(self, activities: list[Activity]) -> str:
        detail = self._detail("activities")
        parts = ["<activities>"]

        for act in sorted(activities, key=lambda x: x.start_date_local):
            date_str = act.start_date_local[:10]
            dur_str = self._format_duration(act.moving_time_s)
            dist_km = round(act.distance_m / 1000, 1)

            if detail == "high":
                attrs = [
                    f'date="{date_str}"',
                    f'type="{act.sport_type}"',
                    f'name="{act.name}"',
                    f'duration="{dur_str}"',
                    f'distance_km="{dist_km}"',
                ]
                if act.total_elevation_gain is not None:
                    attrs.append(f'elevation_m="{int(act.total_elevation_gain)}"')
                if act.calories is not None:
                    attrs.append(f'calories="{int(act.calories)}"')
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')
                if act.suffer_score is not None:
                    attrs.append(f'suffer_score="{act.suffer_score}"')

                parts.append(f"<activity {' '.join(attrs)}>")
                if act.splits_metric:
                    parts.append("  <splits>")
                    for s in act.splits_metric:
                        split_attrs = [f'n="{s.split}"', f'time="{self._format_pace(s.moving_time)}"']
                        if s.average_heartrate is not None:
                            split_attrs.append(f'avg_hr="{int(s.average_heartrate)}"')
                        if s.elevation_difference is not None:
                            sign = "+" if s.elevation_difference > 0 else ""
                            split_attrs.append(f'elev_diff="{sign}{s.elevation_difference:.1f}"')
                        parts.append(f"    <km {' '.join(split_attrs)}/>")
                    parts.append("  </splits>")
                parts.append("</activity>")

            elif detail == "medium":
                attrs = [
                    f'date="{date_str}"',
                    f'type="{act.sport_type}"',
                    f'name="{act.name}"',
                    f'duration="{dur_str}"',
                    f'distance_km="{dist_km}"',
                ]
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                if act.max_heartrate is not None:
                    attrs.append(f'max_hr="{int(act.max_heartrate)}"')

                parts.append(f"<activity {' '.join(attrs)}>")
                if act.splits_metric:
                    parts.append("  <splits>")
                    for s in act.splits_metric:
                        split_attrs = [f'n="{s.split}"', f'time="{self._format_pace(s.moving_time)}"']
                        if s.average_heartrate is not None:
                            split_attrs.append(f'avg_hr="{int(s.average_heartrate)}"')
                        parts.append(f"    <km {' '.join(split_attrs)}/>")
                    parts.append("  </splits>")
                parts.append("</activity>")

            else:  # low
                attrs = [
                    f'date="{date_str}"',
                    f'type="{act.sport_type}"',
                    f'distance_km="{dist_km}"',
                    f'duration="{dur_str}"',
                ]
                if act.average_heartrate is not None:
                    attrs.append(f'avg_hr="{int(act.average_heartrate)}"')
                parts.append(f"<activity {' '.join(attrs)}/>")

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
            "sleep_hrv": "sleep_hrv",
            "sleep_rhr": "sleep_rhr",
            "readiness": "readiness",
            "steps": "steps",
            "calories": "calories",
            "active_calories": "active_cal",
            "spo2_night_score": "spo2_night",
            "vo2max": "vo2max",
            "respiratory_rate": "resp_rate",
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
