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

    def fetch(self, from_date: date, to_date: date, **kwargs: Any) -> list[Meal]:
        """Fetch meals from TimeTagger for the given date range.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            **kwargs: Additional options.

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

        data = response.json()
        meals: list[Meal] = []

        for record in data.get("records", []):
            ds = record.get("ds", "")
            match = MEAL_PATTERN.search(ds)
            if match:
                record_t1 = record.get("t1")
                if record_t1 is None:
                    continue
                
                dt = datetime.fromtimestamp(record_t1)
                meal = Meal(
                    date=dt.date(),
                    time=dt.time(),
                    meal_type=match.group(1).lower(),
                    food=match.group(2).strip(),
                )
                meals.append(meal)

        # Sort by date then time
        meals.sort(key=lambda m: (m.date, m.time))
        
        return meals
