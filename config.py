"""Configuration loader for health-context.

Reads secrets and paths from a .env file (via python-dotenv) and
exposes them as module-level constants. Fails fast with a clear error
message when a required variable is missing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (same directory as this file).
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)


def _require(var: str) -> str:
    """Return the value of an env var or exit with an error."""
    value = os.getenv(var)
    if not value:
        print(f"ERROR: Required environment variable '{var}' is not set.", file=sys.stderr)
        print(f"       Add it to {_ENV_PATH} or export it in your shell.", file=sys.stderr)
        sys.exit(1)
    return value


def _optional(var: str, default: str = "") -> str:
    """Return the value of an env var or a default."""
    return os.getenv(var, default)


# ── TimeTagger ────────────────────────────────────────────────────────
TIMETAGGER_URL: str = ""    # Lazy — only required when --meals is used
TIMETAGGER_TOKEN: str = ""

# ── Strava ────────────────────────────────────────────────────────────
STRAVA_CLIENT_ID: str = ""  # Lazy — only required when --activities is used
STRAVA_CLIENT_SECRET: str = ""

# ── ZeppBridge ────────────────────────────────────────────────────────
ZEPP_DB_PATH: str = ""      # Lazy — only required when --health is used


def require_timetagger() -> tuple[str, str]:
    """Validate and return TimeTagger config. Call only when --meals is used."""
    global TIMETAGGER_URL, TIMETAGGER_TOKEN
    TIMETAGGER_URL = _require("TIMETAGGER_URL").rstrip("/")
    TIMETAGGER_TOKEN = _require("TIMETAGGER_TOKEN")
    return TIMETAGGER_URL, TIMETAGGER_TOKEN


def require_strava() -> tuple[str, str]:
    """Validate and return Strava config. Call only when --activities is used."""
    global STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET
    STRAVA_CLIENT_ID = _require("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = _require("STRAVA_CLIENT_SECRET")
    return STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET


def require_zepp() -> str:
    """Validate and return ZeppBridge DB path. Call only when --health is used."""
    global ZEPP_DB_PATH
    ZEPP_DB_PATH = _require("ZEPP_DB_PATH")
    path = Path(ZEPP_DB_PATH)
    if not path.exists():
        print(f"ERROR: ZeppBridge database not found at '{path}'.", file=sys.stderr)
        sys.exit(1)
    return ZEPP_DB_PATH
