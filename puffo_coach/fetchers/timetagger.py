"""TimeTagger fetcher for extracting meal records."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

import requests

from puffo_coach import config
from puffo_coach.models import Meal
from puffo_coach.fetchers.base import BaseFetcher

MEAL_TAGS = ('colazione', 'pranzo', 'cena', 'merenda')
_MEAL_TAG_RE = re.compile(
    r'#(' + '|'.join(MEAL_TAGS) + r')\b',
    re.IGNORECASE,
)


def _parse_meal_food(ds: str, tag_end: int) -> str:
    """Extract food description from brackets after a meal tag.

    The bracket content is only associated with the meal tag if no other
    ``#tag`` appears between the meal tag and the opening ``[``.

    Returns:
        Bracket contents if valid, otherwise ``'UNKNOWN'``.
    """
    after = ds[tag_end:]
    next_hash = after.find('#')
    bracket_start = after.find('[')

    if bracket_start != -1 and (next_hash == -1 or bracket_start < next_hash):
        bracket_end = after.find(']', bracket_start)
        if bracket_end != -1:
            return after[bracket_start + 1:bracket_end].strip()
    return "UNKNOWN"


class TimeTaggerFetcher(BaseFetcher):
    """Fetches meal records from TimeTagger and parses them into Meal objects."""

    def __init__(self) -> None:
        """Initialize the fetcher and ensure TimeTagger configuration is present."""
        self.url, self.token = config.require_timetagger()

    def fetch(
        self,
        from_date: date,
        to_date: date,
        **kwargs: Any,
    ) -> list[Meal]:
        """Fetch meals from TimeTagger for the given date range.

        All records containing a meal tag are returned. If a record has no
        bracketed food description (or another ``#tag`` appears before the
        bracket), the food is set to ``'UNKNOWN'``.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).

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
            match = _MEAL_TAG_RE.search(ds)
            if not match:
                continue

            meal_type = match.group(1).lower()
            food = _parse_meal_food(ds, match.end())

            record_t1 = record.get("t1")
            if record_t1 is None:
                continue

            dt = datetime.fromtimestamp(record_t1)
            meals.append(Meal(
                date=dt.date(),
                time=dt.time(),
                meal_type=meal_type,
                food=food,
            ))

        meals.sort(key=lambda m: (m.date, m.time))
        return meals
