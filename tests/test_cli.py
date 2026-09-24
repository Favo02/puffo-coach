"""Unit tests for CLI argument parsing and config building."""

import unittest
from datetime import date

from puffo_coach.cli import build_category_configs, parse_args


class TestCli(unittest.TestCase):
    def test_parse_args_valid_full(self) -> None:
        args = parse_args([
            "--from-date", "2026-09-01",
            "--to-date", "2026-09-07",
            "--meals",
            "--activities", "ride,run",
            "--health",
            "--health-detail", "4",
        ])
        self.assertEqual(args.from_date, date(2026, 9, 1))
        self.assertEqual(args.to_date, date(2026, 9, 7))
        self.assertTrue(args.meals)
        self.assertEqual(args.activities, "ride,run")
        self.assertTrue(args.health)
        self.assertEqual(args.health_detail, 4)

        cfgs = build_category_configs(args)
        self.assertTrue(cfgs["meals"].enabled)
        self.assertTrue(cfgs["activities"].enabled)
        self.assertEqual(cfgs["activities"].filter, ["ride", "run"])
        self.assertTrue(cfgs["health"].enabled)
        self.assertEqual(cfgs["health"].detail_level, 4)

    def test_parse_args_default_health_detail(self) -> None:
        args = parse_args([
            "--from-date", "2026-09-01",
            "--to-date", "2026-09-07",
            "--health",
        ])
        cfgs = build_category_configs(args)
        self.assertEqual(cfgs["health"].detail_level, 6)

    def test_parse_args_invalid_health_detail(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args([
                "--from-date", "2026-09-01",
                "--to-date", "2026-09-07",
                "--health",
                "--health-detail", "5",
            ])

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
