"""Unit tests for CLI argument parsing and config building."""

import unittest
from datetime import date

from puffo_coach.cli import build_category_configs, parse_args
from puffo_coach.pipeline import HEALTH_METRICS_CORE, HEALTH_METRICS_HIGH


class TestCli(unittest.TestCase):
    def test_parse_args_valid_full(self) -> None:
        args = parse_args([
            "--from-date", "2026-09-01",
            "--to-date", "2026-09-07",
            "--meals", "colazione,cena",
            "--activities", "ride",
            "--activities-detail", "high",
            "--health",
            "--detail-level", "medium",
        ])
        self.assertEqual(args.from_date, date(2026, 9, 1))
        self.assertEqual(args.to_date, date(2026, 9, 7))
        self.assertEqual(args.meals, "colazione,cena")
        self.assertEqual(args.activities, "ride")
        self.assertEqual(args.activities_detail, "high")
        self.assertEqual(args.health, "all")

        cfgs = build_category_configs(args)
        self.assertTrue(cfgs["meals"].enabled)
        self.assertEqual(cfgs["meals"].filter, ["colazione", "cena"])
        self.assertEqual(cfgs["meals"].detail_level, "medium")

        self.assertTrue(cfgs["activities"].enabled)
        self.assertEqual(cfgs["activities"].filter, ["ride"])
        self.assertEqual(cfgs["activities"].detail_level, "high")

        self.assertTrue(cfgs["health"].enabled)
        self.assertEqual(cfgs["health"].detail_level, "medium")
        self.assertEqual(cfgs["health"].filter, list(HEALTH_METRICS_CORE))

    def test_parse_args_health_high_default_metrics(self) -> None:
        args = parse_args([
            "--from-date", "2026-09-01",
            "--to-date", "2026-09-07",
            "--health",
            "--health-detail", "high",
        ])
        cfgs = build_category_configs(args)
        self.assertEqual(cfgs["health"].filter, list(HEALTH_METRICS_HIGH))

    def test_parse_args_tui_flag(self) -> None:
        args = parse_args(["--tui"])
        self.assertTrue(args.tui)

    def test_parse_args_date_order_error(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--from-date", "2026-09-10", "--to-date", "2026-09-01", "--meals"])

    def test_parse_args_missing_categories_error(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--from-date", "2026-09-01", "--to-date", "2026-09-07"])


if __name__ == "__main__":
    unittest.main()
