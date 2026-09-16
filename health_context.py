#!/usr/bin/env python3
"""health-context: Build LLM-friendly Markdown context from personal data.

Fetches meals (TimeTagger), activities (Strava), and health vitals
(ZeppBridge SQLite) for a date range and formats them into a single
Markdown file with XML-structured sections optimised for LLM consumption.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path


def _parse_date(s: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: '{s}'. Use YYYY-MM-DD.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="health_context",
        description="Build LLM-friendly Markdown context from personal data.",
    )

    parser.add_argument(
        "--from-date",
        required=True,
        type=_parse_date,
        metavar="YYYY-MM-DD",
        help="Start of the date range (inclusive).",
    )
    parser.add_argument(
        "--to-date",
        required=True,
        type=_parse_date,
        metavar="YYYY-MM-DD",
        help="End of the date range (inclusive).",
    )
    parser.add_argument(
        "--meals",
        action="store_true",
        help="Fetch meal data from TimeTagger.",
    )
    parser.add_argument(
        "--activities",
        action="store_true",
        help="Fetch workout/activity data from Strava.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Fetch health vitals (sleep, HR, HRV, etc.) from ZeppBridge.",
    )
    parser.add_argument(
        "--detail-level",
        choices=("high", "medium", "low"),
        default="medium",
        help="Controls data compression (default: medium).",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PATH",
        help="Output file path or directory (default: CWD).",
    )

    args = parser.parse_args(argv)

    # Validate date range.
    if args.from_date > args.to_date:
        parser.error("--from-date must be before or equal to --to-date.")

    # Require at least one data source.
    if not (args.meals or args.activities or args.health):
        parser.error("Specify at least one of --meals, --activities, --health.")

    return args


def main() -> None:
    """Entry point: parse args, fetch data, format, write output."""
    args = parse_args()
    from_date: date = args.from_date
    to_date: date = args.to_date
    detail_level: str = args.detail_level

    meals: list = []
    activities: list = []
    health = None

    # ── Fetch meals from TimeTagger ───────────────────────────────────
    if args.meals:
        from fetchers.timetagger import TimeTaggerFetcher

        print(f"⏳ Fetching meals from TimeTagger ({from_date} → {to_date})…")
        meals = TimeTaggerFetcher().fetch(from_date, to_date)
        print(f"   ✓ {len(meals)} meal(s) found.")

    # ── Fetch activities from Strava ──────────────────────────────────
    if args.activities:
        from fetchers.strava import StravaFetcher

        print(f"⏳ Fetching activities from Strava ({from_date} → {to_date})…")
        activities = StravaFetcher().fetch(from_date, to_date, detail_level=detail_level)
        print(f"   ✓ {len(activities)} activity/ies found.")

    # ── Fetch health vitals from ZeppBridge ───────────────────────────
    if args.health:
        from fetchers.zepp_sqlite import ZeppSqliteReader

        print(f"⏳ Fetching health data from ZeppBridge ({from_date} → {to_date})…")
        health = ZeppSqliteReader().fetch(from_date, to_date, detail_level=detail_level)
        print(
            f"   ✓ {len(health.sleep)} sleep session(s), "
            f"{len(health.daily)} daily metric row(s), "
            f"{len(health.hr_hourly)} hourly HR record(s)."
        )

    # ── Format ────────────────────────────────────────────────────────
    from formatter import MarkdownFormatter

    md = MarkdownFormatter(detail_level).render(
        meals=meals,
        activities=activities,
        health=health,
        from_date=from_date,
        to_date=to_date,
    )

    # ── Write output ──────────────────────────────────────────────────
    default_name = f"context_from_{from_date}_to_{to_date}.md"
    if args.output:
        out = Path(args.output)
        if out.is_dir():
            out = out / default_name
    else:
        out = Path.cwd() / default_name

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\n✅ Written to {out}")
    print(f"   ({len(md)} characters)")


if __name__ == "__main__":
    main()
