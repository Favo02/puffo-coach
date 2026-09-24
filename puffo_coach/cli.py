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
    DEFAULT_HEALTH_HOURS,
    VALID_HEALTH_HOURS,
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


# ── Argument Parsing ──────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="puffo-coach",
        description="Puffo Coach: Build LLM-friendly Markdown context from personal data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # Everything with 6-hour health buckets
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 --meals --activities --health

  # Meals and specific activities, health with 1-hour (hourly) buckets
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 \\
    --meals --activities run,hike --health --health-detail 1

  # Only rides
  %(prog)s --from-date 2026-09-01 --to-date 2026-09-07 --activities ride""",
    )

    # ── Interactive TUI ───────────────────────────────────────────────
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch interactive terminal user interface (TUI).",
    )

    # ── Date range ────────────────────────────────────────────────────
    parser.add_argument(
        "--from-date",
        type=_parse_date,
        metavar="YYYY-MM-DD",
        help="Start of the date range (inclusive).",
    )
    parser.add_argument(
        "--to-date",
        type=_parse_date,
        metavar="YYYY-MM-DD",
        help="End of the date range (inclusive).",
    )

    # ── Category flags ────────────────────────────────────────────────
    parser.add_argument(
        "--meals",
        action="store_true",
        default=False,
        help="Fetch all meals from TimeTagger.",
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
        action="store_true",
        default=False,
        help="Fetch health vitals and sleep from ZeppBridge.",
    )

    # ── Health Detail Level ───────────────────────────────────────────
    parser.add_argument(
        "--health-detail",
        type=int,
        choices=VALID_HEALTH_HOURS,
        default=DEFAULT_HEALTH_HOURS,
        metavar="HOURS",
        help=(
            f"Hours per heart-rate/HRV bucket in daily vitals: "
            f"{', '.join(str(h) for h in VALID_HEALTH_HOURS)} (default: {DEFAULT_HEALTH_HOURS})."
        ),
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
    if args.tui:
        return args

    if not args.from_date or not args.to_date:
        parser.error("Both --from-date and --to-date are required for CLI mode (or run with --tui).")

    if args.from_date > args.to_date:
        parser.error("--from-date must be before or equal to --to-date.")

    if not args.meals and args.activities is None and not args.health:
        parser.error("Specify at least one of --meals, --activities, --health.")

    return args


def build_category_configs(args: argparse.Namespace) -> dict[str, CategoryConfig]:
    """Build CategoryConfig objects from parsed CLI arguments."""
    meals_cfg = CategoryConfig(
        enabled=bool(args.meals),
    )

    activities_cfg = CategoryConfig(
        enabled=args.activities is not None,
        filter=_parse_filter(args.activities),
    )

    health_cfg = CategoryConfig(
        enabled=bool(args.health),
        detail_level=args.health_detail,
    )

    return {
        "meals": meals_cfg,
        "activities": activities_cfg,
        "health": health_cfg,
    }


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: parse args, fetch data, format, write output."""
    if len(sys.argv) == 1:
        from puffo_coach.tui import main as tui_main
        tui_main()
        return

    args = parse_args()
    if args.tui:
        from puffo_coach.tui import main as tui_main
        tui_main()
        return

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
