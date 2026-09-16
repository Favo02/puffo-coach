# health-context

CLI tool that builds LLM-friendly Markdown context files from personal health, nutrition, and fitness data.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in values
```

### TimeTagger

1. Open your self-hosted TimeTagger instance.
2. Go to **Settings → API Tokens** and generate a token.
3. Set in `.env`:
   ```
   TIMETAGGER_URL=https://your-timetagger.example.com
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

Set in `.env`:
```
ZEPP_DB_PATH=<path-to-zeppbridge-zepp.db>
```

The database is opened in read-only mode.

## Usage

```bash
python health_context.py --from-date 2026-09-01 --to-date 2026-09-07 \
  --meals --activities --health \
  --detail-level medium \
  -o ./output/
```

| Argument | Description |
|---|---|
| `--from-date` | Start date, YYYY-MM-DD (required) |
| `--to-date` | End date, YYYY-MM-DD (required) |
| `--meals` | Fetch meals from TimeTagger |
| `--activities` | Fetch workouts from Strava |
| `--health` | Fetch sleep, HR, HRV, readiness from ZeppBridge |
| `--detail-level` | `high`, `medium` (default), or `low` |
| `-o` | Output file or directory (default: CWD) |

At least one of `--meals`, `--activities`, `--health` must be specified.

## Design Choices

- **Output format**: XML tags inside Markdown. Token-efficient, unambiguous for LLMs, and human-readable.
- **Meals are never compressed** regardless of detail level — volume is inherently low.
- **Vitals compression**: HR is 1440 samples/day; even at `high` we aggregate to hourly. At `low`, range averages.
- **Strava for workouts**: ZeppBridge workout data is not used. Strava's processing is trusted and its API natively provides per-km splits.
- **Curated health metrics**: Only actionable daily metrics are included (13 at high, 6 at medium). Stress is excluded (unreliable watch estimate).
- **Lazy validation**: Env vars for unused data sources are not required. `--meals` without Strava credentials is fine.
