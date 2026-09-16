import collections
from datetime import date, time
from typing import Any

from models import (
    Activity, ActivitySplit, DailyMetricRow, HealthBundle, 
    HrHourly, Meal, SleepSession, SleepStage
)


class MarkdownFormatter:
    def __init__(self, detail_level: str):
        self.detail_level = detail_level.lower()

    def render(self, meals: list[Meal], activities: list[Activity], health: HealthBundle | None, from_date: str, to_date: str) -> str:
        parts = [f"# Personal Context: {from_date} → {to_date}\n"]
        
        if meals:
            parts.append(self._render_meals(meals))
            
        if health:
            parts.append(self._render_health(health))
            
        if activities:
            parts.append(self._render_activities(activities))
            
        return "\n".join(parts)

    def _render_meals(self, meals: list[Meal]) -> str:
        parts = ["<meals>"]
        by_date = collections.defaultdict(list)
        for meal in meals:
            by_date[meal.date].append(meal)
            
        for d in sorted(by_date.keys()):
            parts.append(f'<day date="{d.isoformat()}">')
            for m in sorted(by_date[d], key=lambda x: x.time):
                parts.append(f'  <meal time="{m.time.strftime("%H:%M")}" type="{m.meal_type}">{m.food}</meal>')
            parts.append("</day>")
            
        parts.append("</meals>")
        return "\n".join(parts)

    def _render_health(self, health: HealthBundle) -> str:
        parts = []
        if health.daily:
            parts.append(self._render_vitals(health))
        if health.sleep:
            parts.append(self._render_sleep(health.sleep))
        return "\n".join(parts)

    def _render_vitals(self, health: HealthBundle) -> str:
        daily_map = self._pivot_daily_metrics(health.daily)
        parts = ["<vitals>"]
        
        if self.detail_level == "high":
            hr_by_day = collections.defaultdict(list)
            if health.hr_hourly:
                for h in health.hr_hourly:
                    hr_by_day[h.day].append(h)
                    
            for day, metrics in sorted(daily_map.items()):
                attrs = [f'date="{day}"']
                for k, v in sorted(metrics.items()):
                    if isinstance(v, float) and v.is_integer():
                        v_str = str(int(v))
                    elif isinstance(v, float):
                        v_str = f"{v:.1f}"
                    else:
                        v_str = str(v)
                    attrs.append(f'{k}="{v_str}"')
                    
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
                    
        elif self.detail_level == "medium":
            core_metrics = ["resting_hr", "sleep_hrv", "readiness", "steps", "calories", "spo2_night"]
            for day, metrics in sorted(daily_map.items()):
                attrs = [f'date="{day}"']
                for k in core_metrics:
                    if k in metrics:
                        v = metrics[k]
                        if isinstance(v, float) and v.is_integer():
                            v_str = str(int(v))
                        elif isinstance(v, float):
                            v_str = f"{v:.1f}"
                        else:
                            v_str = str(v)
                        attrs.append(f'{k}="{v_str}"')
                parts.append(f"<day {' '.join(attrs)}/>")
                
        else: # low
            metrics_acc = collections.defaultdict(list)
            for metrics in daily_map.values():
                for k, v in metrics.items():
                    metrics_acc[k].append(v)
                    
            days_count = len(daily_map)
            
            def get_stats(key):
                if key not in metrics_acc or not metrics_acc[key]:
                    return None
                vals = metrics_acc[key]
                return sum(vals)/len(vals), min(vals), max(vals)
                
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

    def _render_sleep(self, sessions: list[SleepSession]) -> str:
        parts = ["<sleep>"]
        
        if self.detail_level == "high":
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
                    f'end="{self._format_time(s.end_time)}"'
                ]
                parts.append(f"<night {' '.join(attrs)}>")
                if s.stages:
                    parts.append("  <stages>")
                    for stage in s.stages:
                        parts.append(f'    <s stage="{stage.stage}" start="{self._format_time(stage.start_time)}" end="{self._format_time(stage.end_time)}"/>')
                    parts.append("  </stages>")
                parts.append("</night>")
                
        elif self.detail_level == "medium":
            for s in sorted(sessions, key=lambda x: x.start_time):
                total_hr = round(s.duration_min / 60, 1)
                attrs = [
                    f'date="{s.start_time[:10]}"',
                    f'score="{s.score if s.score is not None else 0}"',
                    f'total_hr="{total_hr}"',
                    f'deep="{s.deep_min}"',
                    f'rem="{s.rem_min}"'
                ]
                parts.append(f"<night {' '.join(attrs)}/>")
                
        else: # low
            if sessions:
                days_count = len(sessions)
                scores = [s.score for s in sessions if s.score is not None]
                avg_score = int(sum(scores)/len(scores)) if scores else 0
                avg_dur = round(sum(s.duration_min for s in sessions) / (len(sessions) * 60), 1)
                avg_deep = int(sum(s.deep_min for s in sessions) / len(sessions))
                avg_rem = int(sum(s.rem_min for s in sessions) / len(sessions))
                
                parts.append(f"{days_count} nights. Avg score: {avg_score}. Avg duration: {avg_dur}h. Avg deep: {avg_deep} min. Avg REM: {avg_rem} min.")
            
        parts.append("</sleep>")
        return "\n".join(parts)

    def _render_activities(self, activities: list[Activity]) -> str:
        parts = ["<activities>"]
        
        for act in sorted(activities, key=lambda x: x.start_date_local):
            date_str = act.start_date_local[:10]
            dur_str = self._format_duration(act.moving_time_s)
            dist_km = round(act.distance_m / 1000, 1)
            
            if self.detail_level == "high":
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
                
            elif self.detail_level == "medium":
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
                
            else: # low
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

    def _format_duration(self, seconds: int) -> str:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _format_time(self, iso_str: str) -> str:
        if "T" in iso_str:
            return iso_str.split("T")[1][:5]
        return iso_str[11:16]

    def _format_pace(self, seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"

    def _pivot_daily_metrics(self, rows: list[DailyMetricRow]) -> dict[str, dict[str, float]]:
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
        }
        
        result = collections.defaultdict(dict)
        for r in rows:
            mapped = metric_map.get(r.metric, r.metric)
            result[r.date][mapped] = r.value
        return dict(result)
