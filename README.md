# Puffo Coach

<img width="80" src="assets/icon.svg" align="right" alt="Puffo Coach logo">

CLI/TUI tool that builds clean, LLM-friendly Markdown context files from personal health ([Zepp](https://www.zepp.com/)), nutrition ([TimeTagger](https://timetagger.app/)), and fitness data ([Strava](https://www.strava.com/)).

> [!NOTE]
> The data sources and formats reflect a personalized tracking workflow (and are very opinionated):
>
> - **Meals**: Tracked in TimeTagger using custom tag and bracket formatting (`#colazione [food items]`).
> - **Workouts**: Recorded on-device and synced directly to Strava.
> - **Vitals & Sleep**: Recorded by a Zepp-compatible wearable and exported to a local SQLite database via ZeppBridge.

## Setup

```bash
uv sync
cp .env.example .env   # then fill in your credentials
```

### TimeTagger

1. Open your TimeTagger instance (self-hosted or hosted at [timetagger.app](https://timetagger.app/)).
2. Navigate to **Settings > API Tokens** and generate an API token.
3. Add to `.env`:
   ```env
   TIMETAGGER_URL=<your-timetagger-url>
   TIMETAGGER_TOKEN=<your-token>
   ```

Meals are parsed by searching for the tags `#colazione`, `#pranzo`, `#cena`, or `#merenda` followed by bracketed food items `[...]`. Any text between the tag and brackets is ignored.

_Example_: `#colazione al bar [brioche, cappuccio]` is extracted as meal type `colazione` with food items `brioche, cappuccio`.

### Strava

1. Navigate to [strava.com/settings/api](https://www.strava.com/settings/api) and create an application:
   - **Authorization Callback Domain**: `localhost`
   - **Website**: `http://localhost`
2. Add your credentials to `.env`:
   ```env
   STRAVA_CLIENT_ID=<your-client-id>
   STRAVA_CLIENT_SECRET=<your-client-secret>
   ```
3. On your first run with `--activities`, a browser window opens for OAuth authorization. A temporary local server on `localhost:5739` captures the callback code. Tokens are saved to `~/.puffo-coach/strava_tokens.json` and refresh automatically on subsequent runs.

### ZeppBridge

1. Install [ZeppBridge](https://zeppbridge.pages.dev/) to sync wearable data into a local SQLite database.
2. Locate your `zepp.db` path via **Settings > Advanced > Open data folder**.
3. Add the path to `.env`:
   ```env
   ZEPP_DB_PATH=<path-to-zeppbridge-data>/zepp.db
   ```

The database is accessed strictly in read-only mode (`?mode=ro`).

> [!WARNING]
> ZeppBridge is a third-party open-source tool that syncs data from Zepp via OAuth into a local SQLite database.
> All data remains on your local machine with no external telemetry, though it has not undergone an independent security audit.

## Usage

### Interactive TUI

Launch the interactive Terminal User Interface (TUI) by running `puffo-coach` without arguments, with `--tui`, or via `puffo-coach-tui`:

```bash
uv run puffo-coach
# or
uv run puffo-coach --tui
# or
uv run puffo-coach-tui
```

The TUI provides:

- **Date Range Presets**: Quick selection for _Today_, _Yesterday_, _Last 7 days_, _This week to date_, _Last week_, _This month to date_, _Last 30 days_, _Last month_, and custom ranges.
- **Source & Detail Controls**: Enable/disable Meals, Activities, and Health with global or per-category detail levels (`high`, `medium`, `low`).
- **Meals Customization**: Filter all meal types or select individual types (`colazione`, `pranzo`, `cena`, `merenda`).
- **Activities Customization**: Filter all sport types, select common presets (`ride`, `run`, `hike`, `walk`, `swim`, `workout`), or enter custom sport names.
- **Vitals Customization**: Default metrics paired with detail level, toggles to include/exclude each metric, and custom metric inputs.
- **Preview & Export**: Rendered Markdown viewer with syntax highlighting, clipboard copy (`c` or button), and file save (`s` or button).

### CLI Mode

```bash
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health \
  --detail-level medium \
  -o ./output/
```

Alternatively, invoke as a Python module:

```bash
uv run python -m puffo_coach --from-date 2026-09-01 --to-date 2026-09-07 --meals --activities --health
```

### Arguments

| Argument               | Description                                                          |
| ---------------------- | -------------------------------------------------------------------- |
| `--tui`                | Launch interactive terminal user interface (TUI)                     |
| `--from-date`          | Start date, YYYY-MM-DD (required in CLI mode)                        |
| `--to-date`            | End date, YYYY-MM-DD (required in CLI mode)                          |
| `--meals [TYPES]`      | Fetch meals. Optionally filter: `colazione,pranzo,cena,merenda`      |
| `--activities [TYPES]` | Fetch workouts. Optionally filter by sport type: `ride,run,hike,...` |
| `--health [METRICS]`   | Fetch vitals. Optionally list metrics: `resting_hr,sleep_hrv,...`    |
| `--detail-level`       | Global compression: `high`, `medium` (default), `low`                |
| `--meals-detail`       | Override detail level for meals                                      |
| `--activities-detail`  | Override detail level for activities                                 |
| `--health-detail`      | Override detail level for health vitals                              |
| `-o`                   | Output file or directory (default: CWD)                              |

In CLI mode, both `--from-date` and `--to-date` plus at least one of `--meals`, `--activities`, `--health` must be specified.

### Filtering Examples

```bash
# Everything, medium detail
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health

# Only breakfast and dinner
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals colazione,cena

# Only rides at high detail, health at low detail with 3 core metrics
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --activities ride --activities-detail high \
  --health resting_hr,sleep_hrv,readiness --health-detail low

# Runs and hikes only
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --activities run,hike --activities-detail high
```

### Available Health Metrics

Default set (used when `--health` is passed without a value):

| Detail     | Metrics                                                                                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high       | `resting_hr`, `sleep_hrv`, `sleep_rhr`, `readiness`, `steps`, `calories`, `active_calories`, `spo2_night_score`, `vo2max`, `respiratory_rate`, `training_load`, `physical_readiness`, `mental_readiness` |
| medium/low | `resting_hr`, `sleep_hrv`, `readiness`, `steps`, `calories`, `spo2_night_score`                                                                                                                          |

You can override with any metric available in ZeppBridge's `daily_metrics` table, e.g. `--health stress,pai_total,vo2max`.

Sleep data is always included when `--health` is active.

### Activity Type Matching

Activity types use **case-insensitive substring matching** against Strava's `sport_type`:

- `ride` matches `Ride`, `VirtualRide`
- `run` matches `Run`, `TrailRun`, `VirtualRun`
- `soccer` matches `Soccer`

## Design Choices

- **Output format**: XML tags inside Markdown. Token-efficient, unambiguous for LLMs, and easily readable by humans.
- **Meals are always fully listed**: Given the low daily volume of meals, full fidelity is preserved across all detail levels.
- **Vitals compression**: Heart rate produces 1,440 samples/day; even at `high` detail it is aggregated hourly, while `low` detail provides multi-day statistical summaries.
- **Strava for workouts**: Activity data is sourced exclusively from Strava to leverage its trusted processing algorithms and native per-kilometer split calculations.
- **Curated health metrics**: Only actionable, reliable metrics are included by default (unreliable estimates like watch stress are excluded by default, but can be explicitly requested).
- **Lazy validation**: Environment variables for unused data sources are not required; running `--meals` alone will not fail if Strava credentials are unset.
- **Per-category detail**: Each data category (meals, activities, health) can have its own compression level, falling back to the global `--detail-level`.
