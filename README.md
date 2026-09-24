# Puffo Coach

<img width="80" src="assets/icon.svg" align="right" alt="Puffo Coach logo">

CLI/TUI tool that builds clean, LLM-friendly Markdown context files from personal health ([Zepp](https://www.zepp.com/)), nutrition ([TimeTagger](https://timetagger.app/)), and fitness data ([Strava](https://www.strava.com/)).

> [!NOTE]
> Data sources and formatting reflect a personalized tracking workflow (and are very opinionated):
>
> - **Meals**: Tracked in TimeTagger using meal tags (`#colazione`, `#pranzo`, `#cena`, `#merenda`) and bracketed food descriptions (`[food items]`).
> - **Workouts**: Recorded on-device and synced directly to Strava.
> - **Vitals & Sleep**: Recorded by a Zepp-compatible wearable and exported to a local SQLite database via ZeppBridge.

## Setup

```bash
uv sync
cp .env.example .env   # fill in credentials
```

### TimeTagger

1. Open your TimeTagger instance (self-hosted or hosted at [timetagger.app](https://timetagger.app/)).
2. Navigate to **Settings > API Tokens** and generate an API token.
3. Add to `.env`:
   ```env
   TIMETAGGER_URL=<your-timetagger-url>
   TIMETAGGER_TOKEN=<your-token>
   ```

Meals are parsed by searching for the tags `#colazione`, `#pranzo`, `#cena`, or `#merenda`. If followed immediately by bracketed food items `[...]`, the bracket content is extracted. If no brackets exist or if another `#tag` appears before the bracket (e.g. `#pranzo #friends [Mario, Luigi]`), the food description is recorded as `UNKNOWN`.

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

- **High-Visibility Status Bar**: Prominent status indicator showing state, progress, and generation summaries.
- **Date Range Controls**: 3-column row with quick presets (_Today_, _Yesterday_, _Last 7 days_, _This week to date_, _Last week_, _This month to date_, _Last 30 days_, _Last month_, _Custom_) and editable From/To dates.
- **Meals Toggle**: Single checkbox to include all tracked meals.
- **Activities Selection**: Multi-select grid with the 7 primary sports (`Soccer`, `Volleyball`, `Beach Volleyball`, `Workout`, `Hike`, `Run`, `Ride`) and custom sport input.
- **Health Detail Selection**: Direct selection of heart rate / HRV aggregation window (`1h`, `2h`, `3h`, `4h`, `6h`, `8h`, `12h`, `24h` per bucket).
- **Keyboard Shortcuts**: `g` (Generate Context), `c` (Copy to Clipboard), `s` (Save to File), `d` (Toggle Dark Mode), `q` (Quit).

### CLI Mode

```bash
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health \
  --health-detail 6 \
  -o ./output/
```

### Arguments

| Argument                | Description                                                                        |
| ----------------------- | ---------------------------------------------------------------------------------- |
| `--tui`                 | Launch interactive terminal user interface (TUI)                                   |
| `--from-date`           | Start date, YYYY-MM-DD (required in CLI mode)                                      |
| `--to-date`             | End date, YYYY-MM-DD (required in CLI mode)                                        |
| `--meals`               | Fetch all tracked meals from TimeTagger                                            |
| `--activities [TYPES]`  | Fetch activities from Strava. Optionally filter: `ride,run,soccer,...`             |
| `--health`              | Fetch health vitals and sleep from ZeppBridge                                      |
| `--health-detail HOURS` | HR/HRV bucket aggregation window in hours: `1, 2, 3, 4, 6, 8, 12, 24` (default: 6) |
| `-o`, `--output`        | Output file path or directory (default: CWD)                                       |

In CLI mode, both `--from-date` and `--to-date` plus at least one of `--meals`, `--activities`, `--health` must be specified.

### CLI Examples

```bash
# Everything, default 6-hour health buckets
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health

# Meals and runs/hikes, hourly health buckets
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities run,hike --health --health-detail 1

# Only rides
uv run puffo-coach --from-date 2026-09-01 --to-date 2026-09-07 \
  --activities ride
```

## Data Handling & Formatting

### Meals

- All meals tagged with `#colazione`, `#pranzo`, `#cena`, or `#merenda` are included.
- Food descriptions in brackets following the tag are extracted (e.g. `#colazione [yogurt, caffè]` -> `yogurt, caffè`).
- If no brackets exist or an intermediate tag is present (e.g. `#pranzo #friends [Mario]`), description defaults to `UNKNOWN`.

### Activities

- **Always Full Detail**: Activities never use lossy compression levels.
- **No Calories**: Calorie estimates are omitted.
- **Relative Effort**: Strava's `suffer_score` is reported as `relative_effort`.
- **Primary Sport Curated Attributes**:
  - `Ride`, `Run`, `Hike`: `distance_km`, `elevation_m`, `avg_hr`, `max_hr`, `avg_cadence`, `relative_effort`, and `<splits>`. For activities >50 km, all kilometers are grouped into 5 km chunks.
  - `Soccer`: `distance_km` (if GPS tracked), `avg_hr`, `max_hr`, `min_hr`, `relative_effort`. No elevation.
  - `Volleyball`, `Beach Volleyball`: `avg_hr`, `max_hr`, `min_hr`, `relative_effort`. No elevation or distance.
  - `Workout`: `distance_km` (if GPS tracked), `avg_hr`, `max_hr`, `min_hr`, `relative_effort`. No elevation.
- **Heart Rate Chunks vs Splits**:
  - Activities **with** Strava API-native km splits: use native splits with heart rate data included (`avg_hr` per split, or 5 km grouped splits for >50 km).
  - Activities **without** Strava API-native km splits: split into 10 equal-duration time chunks with `start`, `end`, `avg_hr`, `min_hr`, and `max_hr`.

### Sleep

- Rendered as a single `<night .../>` row per sleep session.
- Sleep phase/stage transitions are omitted.
- Row attributes: `date`, `score`, `total_min`, `deep`, `light`, `rem`, `awake`, `wakes`, `start`, `end`.
- Sleep-specific vitals moved from daily vitals to the sleep row: `resp_rate`, `sleep_hrv`, `sleep_rhr`, `spo2_night`.

### Health Vitals & Compression

- **Only vitals have a detail level**: configured via `--health-detail N` (hours dividing 24: `1, 2, 3, 4, 6, 8, 12, 24`).
- **Curated Day Metrics**: `<day date="..." .../>` includes only `resting_hr`, `steps`, `active_minutes`, `training_load`, `vo2max`, and `pai_total`.
- **Day HR/HRV Chunks**: sub-daily samples are aggregated into `<hr_buckets>` with `<bucket start="..." end="..." avg_hr="..." min_hr="..." max_hr="..." avg_hrv="..." min_hrv="..." max_hrv="..."/>`.

---

## ZeppDB Metrics Reference

Full inventory of metrics present in the local ZeppBridge SQLite database (`zepp.db`):

### `metric_samples` Table (Sub-Daily / Timestamped Samples)

| Metric           | Granularity   | Average Frequency  | Description                                        |
| ---------------- | ------------- | ------------------ | -------------------------------------------------- |
| `heart_rate`     | ~1 minute     | ~1,420 samples/day | Continuous heart rate measurement (bpm)            |
| `hrv_rmssd`      | ~1 minute     | ~376 samples/day   | Root mean square of successive RR differences (ms) |
| `stress`         | ~5 minutes    | ~210 samples/day   | Stress score (0-100)                               |
| `spo2`           | ~5-15 minutes | ~143 samples/day   | Blood oxygen saturation percentage (%)             |
| `hrv`            | ~2-3x / night | ~3 samples/day     | Nightly HRV summary samples                        |
| `spo2_apnea_low` | ~1x / night   | ~3 samples/day     | Lowest SpO₂ recorded during sleep                  |
| `weight`         | manual input  | As recorded        | Body weight (kg)                                   |
| `height`         | manual input  | As recorded        | Body height (cm)                                   |
| `bmi`            | manual input  | As recorded        | Body mass index (kg/m²)                            |

### `daily_metrics` Table (Daily Aggregates)

All metrics in this table have **daily** granularity (one record per day):

| Metric                     | Category         | Description                                                         |
| -------------------------- | ---------------- | ------------------------------------------------------------------- |
| `sleep_hrv`                | Sleep / Recovery | Average HRV during sleep (ms) _(moved to sleep row)_                |
| `sleep_rhr`                | Sleep / Recovery | Resting heart rate during sleep (bpm) _(moved to sleep row)_        |
| `respiratory_rate`         | Sleep / Recovery | Average respiratory rate during sleep (brpm) _(moved to sleep row)_ |
| `respiratory_rate_min`     | Sleep / Recovery | Minimum respiratory rate during sleep                               |
| `respiratory_rate_max`     | Sleep / Recovery | Maximum respiratory rate during sleep                               |
| `spo2_night_score`         | Sleep / Recovery | SpO₂ night score _(moved to sleep row)_                             |
| `spo2_odi`                 | Sleep / Recovery | Oxygen desaturation index                                           |
| `spo2_odi_events`          | Sleep / Recovery | Total oxygen desaturation events                                    |
| `spo2_measured_minutes`    | Sleep / Recovery | Duration of nocturnal SpO₂ monitoring (min)                         |
| `resting_hr`               | Vitals           | Daily resting heart rate (bpm)                                      |
| `readiness`                | Readiness        | Overall readiness score (0-100)                                     |
| `physical_readiness`       | Readiness        | Physical readiness score                                            |
| `mental_readiness`         | Readiness        | Mental readiness score                                              |
| `hrv_readiness`            | Readiness        | HRV score contribution to readiness                                 |
| `rhr_readiness`            | Readiness        | RHR score contribution to readiness                                 |
| `ahi_readiness`            | Readiness        | Apnea-hypopnea index contribution to readiness                      |
| `skin_temp_readiness`      | Readiness        | Skin temperature deviation contribution to readiness                |
| `hybrid_charge`            | Body Battery     | Combined physical & mental charge                                   |
| `physical_charge`          | Body Battery     | Physical charge score                                               |
| `mental_charge`            | Body Battery     | Mental charge score                                                 |
| `hrv_baseline`             | Baselines        | Rolling HRV baseline                                                |
| `rhr_baseline`             | Baselines        | Rolling RHR baseline                                                |
| `ahi_baseline`             | Baselines        | Rolling AHI baseline                                                |
| `steps`                    | Activity         | Total daily step count                                              |
| `distance`                 | Activity         | Total daily distance (meters)                                       |
| `active_minutes`           | Activity         | Total active minutes                                                |
| `active_minutes_goal`      | Activity         | Active minutes target goal                                          |
| `calories`                 | Activity         | Total daily energy expenditure (kcal)                               |
| `active_calories`          | Activity         | Active energy expenditure (kcal)                                    |
| `calorie_goal`             | Activity         | Calorie expenditure goal                                            |
| `step_goal`                | Activity         | Step count goal                                                     |
| `running_distance`         | Activity         | Distance covered running (meters)                                   |
| `cycling_distance`         | Activity         | Distance covered cycling (meters)                                   |
| `training_load`            | Training         | 7-day rolling training load score                                   |
| `vo2max`                   | Training         | Estimated VO₂ max (ml/kg/min)                                       |
| `stress`                   | Stress           | Average daily stress score (0-100)                                  |
| `stress_min`               | Stress           | Minimum stress recorded                                             |
| `stress_max`               | Stress           | Maximum stress recorded                                             |
| `stress_relaxed_pct`       | Stress           | Percentage of time in relaxed state                                 |
| `stress_normal_pct`        | Stress           | Percentage of time in normal state                                  |
| `stress_medium_pct`        | Stress           | Percentage of time in medium stress                                 |
| `stress_high_pct`          | Stress           | Percentage of time in high stress                                   |
| `pai_daily`                | PAI              | PAI points earned today                                             |
| `pai_total`                | PAI              | Rolling 7-day PAI score total                                       |
| `pai_low_zone`             | PAI              | PAI points in low heart rate zone                                   |
| `pai_low_zone_lower_hr`    | PAI              | Lower HR threshold for low zone                                     |
| `pai_low_zone_minutes`     | PAI              | Time spent in low zone (minutes)                                    |
| `pai_medium_zone`          | PAI              | PAI points in medium heart rate zone                                |
| `pai_medium_zone_lower_hr` | PAI              | Lower HR threshold for medium zone                                  |
| `pai_medium_zone_minutes`  | PAI              | Time spent in medium zone (minutes)                                 |
| `pai_high_zone`            | PAI              | PAI points in high heart rate zone                                  |
| `pai_high_zone_lower_hr`   | PAI              | Lower HR threshold for high zone                                    |
| `pai_high_zone_minutes`    | PAI              | Time spent in high zone (minutes)                                   |
| `device_resting_hr`        | Device           | Device firmware reported resting HR                                 |
| `device_max_hr`            | Device           | Device firmware reported max HR                                     |

### `sleep_sessions` Table (Sleep Sessions)

| Field              | Type    | Description                                  |
| ------------------ | ------- | -------------------------------------------- |
| `score`            | integer | Sleep quality score (0-100)                  |
| `duration_minutes` | integer | Total duration of sleep session              |
| `deep_minutes`     | integer | Deep sleep duration (minutes)                |
| `light_minutes`    | integer | Light sleep duration (minutes)               |
| `rem_minutes`      | integer | REM sleep duration (minutes)                 |
| `awake_minutes`    | integer | Awake duration during sleep period (minutes) |
| `wake_count`       | integer | Number of awakenings                         |
