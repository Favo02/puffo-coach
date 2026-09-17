"""TimeTagger fetcher for extracting meal records."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

import requests

import config
from models import Meal
from fetchers.base import BaseFetcher

MEAL_TAGS = ('colazione', 'pranzo', 'cena', 'merenda')
MEAL_PATTERN = re.compile(
    r'#(' + '|'.join(MEAL_TAGS) + r')'
    r'.*?'
    r'\[([^\]]+)\]',
    re.IGNORECASE,
)


class TimeTaggerFetcher(BaseFetcher):
    """Fetches meal records from TimeTagger and parses them into Meal objects."""

    def __init__(self) -> None:
        """Initialize the fetcher and ensure TimeTagger configuration is present."""
        self.url, self.token = config.require_timetagger()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        meal_types: list[str] | None = None,
        **kwargs: Any,
    ) -> list[Meal]:
        """Fetch meals from TimeTagger for the given date range.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            meal_types: Meal types to include (e.g., ['colazione', 'pranzo']).
                        Empty list or None means all types.

        Returns:
            A list of Meal objects sorted by date and time.
        """
        t1 = int(datetime.combine(from_date, time.min).timestamp())
        t2 = int(datetime.combine(to_date, time.max).timestamp())

        url = f"{self.url}/api/v2/records?timerange={t1}-{t2}"
        headers = {"authtoken": self.token}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"TimeTagger fetch failed: {e}") from e

        # Normalize filter to a set for fast lookup (empty = all).
        type_filter: set[str] = {t.lower() for t in meal_types} if meal_types else set()

        data = response.json()
        meals: list[Meal] = []

        for record in data.get("records", []):
            ds = record.get("ds", "")
            match = MEAL_PATTERN.search(ds)
            if match:
                meal_type = match.group(1).lower()

                # Skip if a filter is active and this type isn't included.
                if type_filter and meal_type not in type_filter:
                    continue

                record_t1 = record.get("t1")
                if record_t1 is None:
                    continue

                dt = datetime.fromtimestamp(record_t1)
                meal = Meal(
                    date=dt.date(),
                    time=dt.time(),
                    meal_type=meal_type,
                    food=match.group(2).strip(),
                )
                meals.append(meal)

        meals.sort(key=lambda m: (m.date, m.time))
        return meals
