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

from models import CategoryConfig

# ── Constants ─────────────────────────────────────────────────────────

DETAIL_LEVELS = ("high", "medium", "low")

ALL_MEAL_TYPES = ("colazione", "pranzo", "cena", "merenda")

# Default health metrics per detail level (used when --health has no value).
HEALTH_METRICS_HIGH = (
    "resting_hr", "sleep_hrv", "sleep_rhr", "readiness", "steps",
    "calories", "active_calories", "spo2_night_score", "vo2max",
    "respiratory_rate", "training_load", "physical_readiness", "mental_readiness",
)
HEALTH_METRICS_CORE = (
    "resting_hr", "sleep_hrv", "readiness", "steps", "calories", "spo2_night_score",
)


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: '{s}'. Use YYYY-MM-DD.")


def _parse_filter(raw: str | None) -> list[str]:
    """Parse a comma-separated filter string into a list.

    Returns an empty list for 'all' (meaning no filter / include everything).
    """
    if raw is None or raw == "all":
        return []
    return [v.strip().lower() for v in raw.split(",") if v.strip()]


def _resolve_detail(category_detail: str | None, global_detail: str) -> str:
    """Return the per-category detail level, falling back to global."""
    return category_detail if category_detail is not None else global_detail


# ── Argument Parsing ──────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="health_context",
        description="Build LLM-friendly Markdown context from personal data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # Everything, medium detail
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 --meals --activities --health

  # Only breakfast and dinner, rides at high detail, core health metrics
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 \\
    --meals colazione,cena \\
    --activities ride --activities-detail high \\
    --health resting_hr,sleep_hrv,readiness --health-detail low

  # Only runs and hikes
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 \\
    --activities run,hike --activities-detail high""",
    )

    # ── Date range ────────────────────────────────────────────────────
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

    # ── Category flags (optional comma-separated filter) ──────────────
    parser.add_argument(
        "--meals",
        nargs="?",
        const="all",
        default=None,
        metavar="TYPES",
        help=(
            "Fetch meals from TimeTagger. Optionally filter by type: "
            "colazione,pranzo,cena,merenda. Default: all."
        ),
    )
    parser.add_argument(
        "--activities",
        nargs="?",
        const="all",
        default=None,
        metavar="TYPES",
        help=(
            "Fetch activities from Strava. Optionally filter by sport type: "
            "ride,run,hike,soccer,... (case-insensitive substring match). Default: all."
        ),
    )
    parser.add_argument(
        "--health",
        nargs="?",
        const="all",
        default=None,
        metavar="METRICS",
        help=(
            "Fetch health vitals from ZeppBridge. Optionally list specific metrics: "
            "resting_hr,sleep_hrv,readiness,steps,... Default: curated set."
        ),
    )

    # ── Detail levels ─────────────────────────────────────────────────
    parser.add_argument(
        "--detail-level",
        choices=DETAIL_LEVELS,
        default="medium",
        help="Global compression level (default: medium).",
    )
    parser.add_argument(
        "--meals-detail",
        choices=DETAIL_LEVELS,
        default=None,
        help="Override detail level for meals.",
    )
    parser.add_argument(
        "--activities-detail",
        choices=DETAIL_LEVELS,
        default=None,
        help="Override detail level for activities.",
    )
    parser.add_argument(
        "--health-detail",
        choices=DETAIL_LEVELS,
        default=None,
        help="Override detail level for health vitals.",
    )

    # ── Output ────────────────────────────────────────────────────────
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PATH",
        help="Output file path or directory (default: CWD).",
    )

    args = parser.parse_args(argv)

    # ── Validation ────────────────────────────────────────────────────
    if args.from_date > args.to_date:
        parser.error("--from-date must be before or equal to --to-date.")

    if args.meals is None and args.activities is None and args.health is None:
        parser.error("Specify at least one of --meals, --activities, --health.")

    return args


def build_category_configs(args: argparse.Namespace) -> dict[str, CategoryConfig]:
    """Build CategoryConfig objects from parsed CLI arguments."""
    global_detail = args.detail_level

    # ── Meals ─────────────────────────────────────────────────────────
    meals_cfg = CategoryConfig(
        enabled=args.meals is not None,
        filter=_parse_filter(args.meals),
        detail_level=_resolve_detail(args.meals_detail, global_detail),
    )

    # ── Activities ────────────────────────────────────────────────────
    activities_cfg = CategoryConfig(
        enabled=args.activities is not None,
        filter=_parse_filter(args.activities),
        detail_level=_resolve_detail(args.activities_detail, global_detail),
    )

    # ── Health ────────────────────────────────────────────────────────
    health_detail = _resolve_detail(args.health_detail, global_detail)
    if args.health is not None:
        explicit_metrics = _parse_filter(args.health)
        if not explicit_metrics:
            # No explicit list → use curated defaults based on detail level.
            explicit_metrics = list(
                HEALTH_METRICS_HIGH if health_detail == "high" else HEALTH_METRICS_CORE
            )
    else:
        explicit_metrics = []

    health_cfg = CategoryConfig(
        enabled=args.health is not None,
        filter=explicit_metrics,
        detail_level=health_detail,
    )

    return {
        "meals": meals_cfg,
        "activities": activities_cfg,
        "health": health_cfg,
    }


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: parse args, fetch data, format, write output."""
    args = parse_args()
    from_date: date = args.from_date
    to_date: date = args.to_date
    configs = build_category_configs(args)

    meals: list = []
    activities: list = []
    health = None

    # ── Fetch meals from TimeTagger ───────────────────────────────────
    if configs["meals"].enabled:
        from fetchers.timetagger import TimeTaggerFetcher

        cfg = configs["meals"]
        print(f"⏳ Fetching meals from TimeTagger ({from_date} → {to_date})…")
        meals = TimeTaggerFetcher().fetch(from_date, to_date, meal_types=cfg.filter)
        print(f"   ✓ {len(meals)} meal(s) found.")

    # ── Fetch activities from Strava ──────────────────────────────────
    if configs["activities"].enabled:
        from fetchers.strava import StravaFetcher

        cfg = configs["activities"]
        print(f"⏳ Fetching activities from Strava ({from_date} → {to_date})…")
        activities = StravaFetcher().fetch(
            from_date, to_date,
            detail_level=cfg.detail_level,
            sport_types=cfg.filter,
        )
        print(f"   ✓ {len(activities)} activity/ies found.")

    # ── Fetch health vitals from ZeppBridge ───────────────────────────
    if configs["health"].enabled:
        from fetchers.zepp_sqlite import ZeppSqliteReader

        cfg = configs["health"]
        print(f"⏳ Fetching health data from ZeppBridge ({from_date} → {to_date})…")
        health = ZeppSqliteReader().fetch(
            from_date, to_date,
            detail_level=cfg.detail_level,
            metrics=cfg.filter,
        )
        print(
            f"   ✓ {len(health.sleep)} sleep session(s), "
            f"{len(health.daily)} daily metric row(s), "
            f"{len(health.hr_hourly)} hourly HR record(s)."
        )

    # ── Format ────────────────────────────────────────────────────────
    from formatter import MarkdownFormatter

    md = MarkdownFormatter(configs).render(
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
