"""Abstract base class for all data fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class BaseFetcher(ABC):
    """Base class that all fetchers must implement.

    Each fetcher is responsible for:
    1. Connecting to its data source
    2. Querying data for the given date range
    3. Returning a list of domain model objects
    """

    @abstractmethod
    def fetch(self, from_date: date, to_date: date, **kwargs: Any) -> Any:
        """Fetch data for the given date range.

        Args:
            from_date: Start of range (inclusive).
            to_date: End of range (inclusive).
            **kwargs: Fetcher-specific options (e.g., detail_level).

        Returns:
            A list of domain model objects or a bundle dataclass.
        """
        ...
