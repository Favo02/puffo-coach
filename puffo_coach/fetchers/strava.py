"""Strava data fetcher."""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import Any

import requests

from puffo_coach.auth.strava_oauth import StravaTokenManager
from puffo_coach.fetchers.base import BaseFetcher
from puffo_coach.models import Activity, ActivitySplit, HrChunk


class StravaFetcher(BaseFetcher):
    """Fetches activities from Strava with full detail."""

    BASE_URL = "https://www.strava.com"

    def __init__(self) -> None:
        self.token_manager = StravaTokenManager()
        self.session = requests.Session()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        sport_types: list[str] | None = None,
        **kwargs: Any,
    ) -> list[Activity]:
        """Fetch Strava activities within the given date range.

        Always fetches full detail for every activity. For non-GPS activities
        with heart-rate data, also fetches the HR stream and splits it into
        10 equal time chunks.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            sport_types: Activity types to include (e.g., ``['ride', 'run']``).
                         Case-insensitive substring match. Empty/None = all.
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

        activities: list[Activity] = []
        for summary in activities_summary:
            if type_filter:
                sport = summary.get("sport_type", "").lower()
                if not any(f in sport for f in type_filter):
                    continue

            activity_id = summary["id"]
            detail = self._get_detail(activity_id)

            has_gps = bool(summary.get("start_latlng"))

            # Fetch HR stream for non-GPS activities → 10 time-based HR chunks.
            hr_chunks: list[HrChunk] = []
            min_hr: float | None = None
            if not has_gps and summary.get("has_heartrate"):
                time_data, hr_data = self._fetch_hr_stream(activity_id)
                if time_data and hr_data:
                    hr_chunks = self._compute_hr_chunks(time_data, hr_data)
                    valid_hr = [h for h in hr_data if h > 0]
                    min_hr = min(valid_hr) if valid_hr else None

            activity = self._build_activity(summary, detail, has_gps, hr_chunks, min_hr)
            activities.append(activity)

        activities.sort(key=lambda a: a.start_date_local)
        return activities

    # ── API Calls ─────────────────────────────────────────────────────

    def _list_activities(self, after: int, before: int) -> list[dict]:
        activities: list[dict] = []
        page = 1
        while True:
            url = f"{self.BASE_URL}/api/v3/athlete/activities"
            params = {"after": after, "before": before, "per_page": 200, "page": page}
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

    def _fetch_hr_stream(self, activity_id: int) -> tuple[list[int], list[int]]:
        """Fetch time and heartrate streams. Returns empty lists on failure."""
        try:
            url = f"{self.BASE_URL}/api/v3/activities/{activity_id}/streams"
            params = {"keys": "time,heartrate", "key_by_type": "true"}
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            time_data = data.get("time", {}).get("data", [])
            hr_data = data.get("heartrate", {}).get("data", [])
            return time_data, hr_data
        except Exception:
            return [], []

    # ── Data Processing ───────────────────────────────────────────────

    @staticmethod
    def _compute_hr_chunks(
        time_data: list[int], hr_data: list[int], n_chunks: int = 10
    ) -> list[HrChunk]:
        """Split HR stream data into ``n_chunks`` equal time chunks with stats."""
        if not time_data or not hr_data or len(time_data) != len(hr_data):
            return []

        total_time = time_data[-1]
        if total_time <= 0:
            return []

        chunk_duration = total_time / n_chunks
        chunks: list[HrChunk] = []

        for i in range(n_chunks):
            start_t = i * chunk_duration
            end_t = (i + 1) * chunk_duration

            hr_in_chunk = [
                hr for t, hr in zip(time_data, hr_data)
                if start_t <= t < end_t and hr > 0
            ]
            if not hr_in_chunk:
                continue

            def _fmt(secs: float) -> str:
                m, s = divmod(int(secs), 60)
                return f"{m}:{s:02d}"

            chunks.append(HrChunk(
                chunk=i + 1,
                start_time=_fmt(start_t),
                end_time=_fmt(end_t),
                avg_hr=int(sum(hr_in_chunk) / len(hr_in_chunk)),
                min_hr=min(hr_in_chunk),
                max_hr=max(hr_in_chunk),
            ))

        return chunks

    @staticmethod
    def _merge_splits(splits: list[ActivitySplit], chunk_size: int) -> list[ActivitySplit]:
        """Merge consecutive 1 km splits into larger chunks."""
        if chunk_size <= 1:
            return splits

        merged: list[ActivitySplit] = []
        for i in range(0, len(splits), chunk_size):
            chunk = splits[i:i + chunk_size]
            total_dist = sum(s.distance for s in chunk)
            total_time = sum(s.moving_time for s in chunk)
            avg_speed = total_dist / total_time if total_time > 0 else 0

            hr_vals = [s.average_heartrate for s in chunk if s.average_heartrate is not None]
            avg_hr = sum(hr_vals) / len(hr_vals) if hr_vals else None

            elev_vals = [s.elevation_difference for s in chunk if s.elevation_difference is not None]
            total_elev = sum(elev_vals) if elev_vals else None

            merged.append(ActivitySplit(
                split=len(merged) + 1,
                distance=total_dist,
                moving_time=total_time,
                average_speed=avg_speed,
                average_heartrate=avg_hr,
                elevation_difference=total_elev,
                pace_zone=None,
            ))

        return merged

    def _build_activity(
        self,
        summary: dict,
        detail: dict,
        has_gps: bool,
        hr_chunks: list[HrChunk],
        min_hr: float | None,
    ) -> Activity:
        # Build native splits.
        raw_splits: list[ActivitySplit] = []
        for s in detail.get("splits_metric", []):
            raw_splits.append(ActivitySplit(
                split=s.get("split", 0),
                distance=s.get("distance", 0.0),
                moving_time=s.get("moving_time", 0),
                average_speed=s.get("average_speed", 0.0),
                average_heartrate=s.get("average_heartrate"),
                elevation_difference=s.get("elevation_difference"),
                pace_zone=s.get("pace_zone"),
            ))

        # Dynamic split merging: >51 km → merge the tail into 5 km chunks.
        total_dist_km = summary.get("distance", 0.0) / 1000
        if total_dist_km > 51 and raw_splits:
            head = raw_splits[:51]
            tail = raw_splits[51:]
            merged_tail = self._merge_splits(tail, 5) if tail else []
            for j, ms in enumerate(merged_tail):
                ms.split = 51 + j + 1
            raw_splits = head + merged_tail

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
            min_heartrate=min_hr,
            average_cadence=summary.get("average_cadence"),
            relative_effort=summary.get("suffer_score"),
            description=detail.get("description"),
            gear_name=gear_name,
            has_gps=has_gps,
            splits_metric=raw_splits,
            hr_chunks=hr_chunks,
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
