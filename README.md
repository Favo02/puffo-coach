# Health Context

<img width="80" src="icon.svg" align="right">

CLI tool that builds LLM-friendly Markdown context files from personal health ([Zepp](https://www.zepp.com/)), nutrition ([TimeTagger](https://timetagger.app/)), and fitness data ([Strava](https://www.strava.com/)).

> [!INFO]
> The sources of the data are very opinionated.
>
> - I track all my meals with a personal format in my TimeTagger instance.
> - I upload all my workouts/activities to Strava.
> - I own a device that transmits vital metrics to Zepp. These data are "fetched" by ZeppBridge (more on that below).

## Setup

```bash
uv sync
cp .env.example .env   # then fill in values
```

### TimeTagger

1. Open your TimeTagger (self-hosted or official) instance.
2. Go to **Settings > API Tokens** and generate a token.
3. Set in `.env`:
   ```
   TIMETAGGER_URL=<your-timetagger-url>
   TIMETAGGER_TOKEN=<token>
   ```

Meals are identified by tags `#colazione`, `#pranzo`, `#cena`, `#merenda` followed by `[food items]` in the description. Anything between the tag and brackets is ignored.

### Strava

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api) and create an app:
   - **Authorization Callback Domain**: `localhost`
   - **Website**: `http://localhost`
2. Set in `.env`:
   ```
   STRAVA_CLIENT_ID=<your client id>
   STRAVA_CLIENT_SECRET=<your client secret>
   ```
3. On first run with `--activities`, a browser window opens for OAuth authorization. A local server on `localhost:5739` captures the callback. Tokens are saved to `~/.health-context/strava_tokens.json` and auto-refresh on subsequent runs.

### ZeppBridge

1. Install [ZeppBridge](https://zeppbridge.pages.dev/) and let it sync the data into a local database.
2. Find the local database `zepp.db` path from **Settings > Advanced > Open data folder**
3. Set in `.env`:
   ```
   ZEPP_DB_PATH=<path-to-zeppbridge-data>/zepp.db
   ```

The database is opened in read-only mode.

> [!WARNING]
> ZeppBridge is an open-source third-party tool that _somehow_ extracts data from Zepp.
> It uses OAuth to access your Zepp profile, then saves all data to a local database.
> There should be no calls-home or third-party servers involved, but I have not done a security audit.

## Usage

```bash
uv run health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health \
  --detail-level medium \
  -o ./output/
```

### Arguments

| Argument               | Description                                                          |
| ---------------------- | -------------------------------------------------------------------- |
| `--from-date`          | Start date, YYYY-MM-DD (required)                                    |
| `--to-date`            | End date, YYYY-MM-DD (required)                                      |
| `--meals [TYPES]`      | Fetch meals. Optionally filter: `colazione,pranzo,cena,merenda`      |
| `--activities [TYPES]` | Fetch workouts. Optionally filter by sport type: `ride,run,hike,...` |
| `--health [METRICS]`   | Fetch vitals. Optionally list metrics: `resting_hr,sleep_hrv,...`    |
| `--detail-level`       | Global compression: `high`, `medium` (default), `low`                |
| `--meals-detail`       | Override detail level for meals                                      |
| `--activities-detail`  | Override detail level for activities                                 |
| `--health-detail`      | Override detail level for health vitals                              |
| `-o`                   | Output file or directory (default: CWD)                              |

At least one of `--meals`, `--activities`, `--health` must be specified.

### Filtering Examples

```bash
# Everything, medium detail
uv run health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health

# Only breakfast and dinner
uv run health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals colazione,cena

# Only rides at high detail, health at low detail with 3 metrics
uv run health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
  --activities ride --activities-detail high \
  --health resting_hr,sleep_hrv,readiness --health-detail low

# Runs and hikes only
uv run health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
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

- **Output format**: XML tags inside Markdown. Token-efficient, unambiguous for LLMs, and human-readable.
- **Meals are always fully listed** regardless of detail level. Volume is inherently low.
- **Vitals compression**: HR is 1440 samples/day; even at `high` we aggregate to hourly. At `low`, range averages.
- **Strava for workouts**: ZeppBridge workout data is not used. Strava's processing is trusted and its API natively provides per-km splits.
- **Curated health metrics**: Only actionable daily metrics are included by default. Stress is excluded (unreliable estimate) but can be opted in.
- **Lazy validation**: Env vars for unused data sources are not required. `--meals` without Strava credentials is fine.
- **Per-category detail**: Each category (meals, activities, health) can have its own compression level, falling back to the global `--detail-level`.
