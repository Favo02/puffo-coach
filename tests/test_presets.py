"""Unit tests for date presets and pipeline utilities."""

import unittest
from datetime import date

from puffo_coach.pipeline import DATE_PRESETS, get_date_preset


class TestDatePresets(unittest.TestCase):
    def setUp(self) -> None:
        # Thursday 2026-09-17
        self.ref_date = date(2026, 9, 17)

    def test_preset_today(self) -> None:
        start, end = get_date_preset("today", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 17))
        self.assertEqual(end, date(2026, 9, 17))

    def test_preset_yesterday(self) -> None:
        start, end = get_date_preset("yesterday", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 16))
        self.assertEqual(end, date(2026, 9, 16))

    def test_preset_last_7d(self) -> None:
        start, end = get_date_preset("last_7d", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 11))
        self.assertEqual(end, date(2026, 9, 17))
        self.assertEqual((end - start).days + 1, 7)

    def test_preset_this_week(self) -> None:
        # 2026-09-17 is Thursday (weekday 3). Monday was 2026-09-14.
        start, end = get_date_preset("this_week", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 14))
        self.assertEqual(end, date(2026, 9, 17))

    def test_preset_last_week(self) -> None:
        # Last week Monday to Sunday: 2026-09-07 to 2026-09-13
        start, end = get_date_preset("last_week", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 7))
        self.assertEqual(end, date(2026, 9, 13))

    def test_preset_this_month(self) -> None:
        start, end = get_date_preset("this_month", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 9, 1))
        self.assertEqual(end, date(2026, 9, 17))

    def test_preset_last_30d(self) -> None:
        start, end = get_date_preset("last_30d", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 8, 19))
        self.assertEqual(end, date(2026, 9, 17))
        self.assertEqual((end - start).days + 1, 30)

    def test_preset_last_month(self) -> None:
        start, end = get_date_preset("last_month", reference_date=self.ref_date)
        self.assertEqual(start, date(2026, 8, 1))
        self.assertEqual(end, date(2026, 8, 31))

    def test_all_defined_presets_supported(self) -> None:
        for key, _ in DATE_PRESETS:
            start, end = get_date_preset(key, reference_date=self.ref_date)
            self.assertLessEqual(start, end)

    def test_invalid_preset_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_date_preset("non_existent_preset", reference_date=self.ref_date)


if __name__ == "__main__":
    unittest.main()
