#!/usr/bin/env python3
"""Puffo Coach: Build LLM-friendly Markdown context from personal data.

Fetches meals (TimeTagger), activities (Strava), and health vitals
(ZeppBridge SQLite) for a date range and formats them into a single
Markdown file with XML-structured sections optimised for LLM consumption.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from puffo_coach.models import CategoryConfig
from puffo_coach.pipeline import (
    ALL_MEAL_TYPES,
    DETAIL_LEVELS,
    HEALTH_METRICS_CORE,
    HEALTH_METRICS_HIGH,
    run_pipeline,
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
        prog="puffo-coach",
        description="Puffo Coach: Build LLM-friendly Markdown context from personal data.",
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

    result = run_pipeline(from_date, to_date, configs, progress_callback=print)
    md = result.markdown


    # ── Write output ──────────────────────────────────────────────────
    default_name = f"context_from_{from_date}_to_{to_date}.md"
    if args.output:
        out_path = Path(args.output)
        if str(args.output).endswith(("/", "\\")) or out_path.is_dir() or (out_path.suffix == "" and not out_path.exists()):
            out_path.mkdir(parents=True, exist_ok=True)
            out = out_path / default_name
        else:
            out = out_path
    else:
        out = Path.cwd() / default_name

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\n✅ Written to {out}")
    print(f"   ({len(md)} characters)")


if __name__ == "__main__":
    main()
