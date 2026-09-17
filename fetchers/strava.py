"""Strava data fetcher."""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import Any

import requests

from auth.strava_oauth import StravaTokenManager
from fetchers.base import BaseFetcher
from models import Activity, ActivitySplit


class StravaFetcher(BaseFetcher):
    """Fetches activities from Strava."""
    
    BASE_URL = "https://www.strava.com"
    
    def __init__(self) -> None:
        self.token_manager = StravaTokenManager()
        self.session = requests.Session()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        detail_level: str = "medium",
        sport_types: list[str] | None = None,
        **kwargs: Any,
    ) -> list[Activity]:
        """Fetch Strava activities within the given date range.
        
        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            detail_level: 'low' (summary only), 'medium'/'high' (with detail call).
            sport_types: Activity types to include (e.g., ['ride', 'run']).
                         Case-insensitive substring match. Empty/None means all.
        """
        access_token = self.token_manager.get_access_token()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        
        dt_from = datetime.combine(from_date, datetime.min.time())
        dt_to = datetime.combine(to_date, datetime.max.time())
        after_epoch = int(dt_from.timestamp())
        before_epoch = int(dt_to.timestamp())
        
        activities_summary = self._list_activities(after_epoch, before_epoch)

        # Normalize filter for case-insensitive substring matching.
        type_filter = [t.lower() for t in sport_types] if sport_types else []
        
        activities = []
        for summary in activities_summary:
            # Apply sport type filter (case-insensitive substring match).
            if type_filter:
                sport = summary.get("sport_type", "").lower()
                if not any(f in sport for f in type_filter):
                    continue

            activity_id = summary["id"]
            
            if detail_level in ("medium", "high"):
                detail = self._get_detail(activity_id)
            else:
                detail = {}
                
            activity = self._build_activity(summary, detail)
            activities.append(activity)
            
        activities.sort(key=lambda a: a.start_date_local)
        return activities

    def _list_activities(self, after: int, before: int) -> list[dict]:
        activities = []
        page = 1
        while True:
            url = f"{self.BASE_URL}/api/v3/athlete/activities"
            params = {
                "after": after,
                "before": before,
                "per_page": 200,
                "page": page
            }
            resp = self.session.get(url, params=params)
            self._handle_response(resp)
            
            data = resp.json()
            if not data:
                break
                
            activities.extend(data)
            page += 1
            
        return activities
        
    def _get_detail(self, activity_id: int) -> dict:
        url = f"{self.BASE_URL}/api/v3/activities/{activity_id}"
        resp = self.session.get(url)
        self._handle_response(resp)
        return resp.json()

    def _build_activity(self, summary: dict, detail: dict) -> Activity:
        splits = []
        for s in detail.get("splits_metric", []):
            split = ActivitySplit(
                split=s.get("split", 0),
                distance=s.get("distance", 0.0),
                moving_time=s.get("moving_time", 0),
                average_speed=s.get("average_speed", 0.0),
                average_heartrate=s.get("average_heartrate"),
                elevation_difference=s.get("elevation_difference"),
                pace_zone=s.get("pace_zone")
            )
            splits.append(split)
            
        gear = detail.get("gear", {})
        gear_name = gear.get("name") if isinstance(gear, dict) else None

        return Activity(
            id=summary.get("id", 0),
            name=summary.get("name", ""),
            sport_type=summary.get("sport_type", ""),
            start_date_local=summary.get("start_date_local", ""),
            distance_m=summary.get("distance", 0.0),
            moving_time_s=summary.get("moving_time", 0),
            elapsed_time_s=summary.get("elapsed_time", 0),
            total_elevation_gain=summary.get("total_elevation_gain"),
            average_speed=summary.get("average_speed"),
            max_speed=summary.get("max_speed"),
            average_heartrate=summary.get("average_heartrate"),
            max_heartrate=summary.get("max_heartrate"),
            average_cadence=summary.get("average_cadence"),
            suffer_score=summary.get("suffer_score"),
            calories=detail.get("calories"),
            description=detail.get("description"),
            gear_name=gear_name,
            splits_metric=splits
        )

    def _handle_response(self, resp: requests.Response) -> None:
        usage = resp.headers.get("X-RateLimit-Usage")
        limit = resp.headers.get("X-RateLimit-Limit")
        if usage and limit:
            try:
                usages = [int(x) for x in usage.split(",")]
                limits = [int(x) for x in limit.split(",")]
                for u, l in zip(usages, limits):
                    if l > 0 and u / l > 0.8:
                        print(f"WARNING: Strava API rate limit close: {u}/{l} used.", file=sys.stderr)
                        break
            except Exception:
                pass
                
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"ERROR: Strava API call failed: {e}", file=sys.stderr)
            try:
                print(f"Details: {resp.json()}", file=sys.stderr)
            except Exception:
                print(f"Details: {resp.text}", file=sys.stderr)
            sys.exit(1)
