# Ignition Insights Preprocessing

Preprocessing pipeline for Team 46's CSE 6242 project: cleaning fire incidents, joining daily weather, building a fixed grid, aggregating to cell-day counts, and writing a model-ready table.

## Dataset assumptions

- Fire incidents: FEMA/USFA NFIRS annual public data release, ideally a geocoded export (`.gpkg`, `.csv`, or `.parquet`).
- Weather: daily citywide weather file with date plus temperature, humidity, precipitation, and wind columns.
- The script inspects the actual file schema and tries to infer the right columns. CLI overrides are available if the source names differ.
- Because annual NFIRS files are national and large, you should filter to the study area when running the pipeline.

## Install

```bash
python3 -m pip install -r requirements.txt
```

The same file includes **Playwright** and **Pillow** for `scripts/capture_frontend_media.py`. They are safe to install for the data pipeline; you only need `python -m playwright install chromium` the first time you want to regenerate the README demo GIF and screenshots.

## Run

Real handoff run used for this repo:

```bash
python3 scripts/fetch_nfirs_light.py \
  --state-id GA \
  --city Atlanta \
  --out data/raw/nfirs_2024_atlanta_fire.geojson

python3 scripts/fetch_weather_openmeteo.py \
  --latitude 33.7490 \
  --longitude -84.3880 \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --out data/raw/atlanta_weather_2024.csv

python3 scripts/build_model_table.py \
  --incidents data/raw/nfirs_2024_atlanta_fire.geojson \
  --weather data/raw/atlanta_weather_2024.csv \
  --grid-size-m 1000 \
  --horizon-days 1 \
  --outdir data/processed
```

Generic example:

```bash
python3 scripts/build_model_table.py \
  --incidents data/raw/nfirs_2024_all_incidents.gpkg \
  --weather data/raw/weather_daily.csv \
  --filter-field state \
  --filter-value GA \
  --filter-field city \
  --filter-value Atlanta \
  --grid-size-m 1000 \
  --horizon-days 1 \
  --outdir data/processed
```

If the script cannot infer a source column, override it explicitly:

```bash
python3 scripts/build_model_table.py \
  --incidents data/raw/incidents.gpkg \
  --weather data/raw/weather.csv \
  --date-col incident_date \
  --lat-col latitude \
  --lon-col longitude \
  --incident-type-col incident_type \
  --weather-date-col date \
  --temp-col temperature \
  --humidity-col humidity \
  --precip-col precipitation \
  --wind-col wind_speed
```

## Outputs

Written to `data/processed/` by default:

- `incidents_clean.parquet`
- `grid_cells.geojson`
- `cell_day_table.parquet`
- `model_table.parquet`

`model_table.parquet` is the main deliverable for RF/XGBoost/baseline modeling.

## Fire risk explorer: D3.js and Leaflet

The `frontend/` app is a static **linked-views** dashboard. **Leaflet** draws the Atlanta grid from GeoJSON, colors each cell (choropleth) from a column in `model_results.csv`, and handles pan/zoom. The basemap and grid use Leaflet; everything analytical on the page is **D3 v7**.

**D3’s role** is to bind the same underlying tables to several coordinated views, so a change in the global “time” or the selected metric updates every view in sync:

- **Choropleth and legend** — A sequential color scale (yellow–orange–red) is built from the extent of the chosen metric across all cells for the *currently selected day*. D3 re-styles GeoJSON features when you scrub the date, change “Color by,” or pick a new cell.
- **Time scrubber (range input)** — Moving the date re-filters the join between grid features and the model table; the readout, map, and the “distribution for this day” view all read the same `dateIndex` state.
- **Distribution (histogram)** — A bar chart of the current metric’s values over cells that have a model row on that day (D3 `scaleLinear` / bins).
- **Time series (selected cell)** — For one `grid_id`, three model outputs (RF, hotspot, ARIMA) are shown as lines across all dates. Hover for values; a click on the series jumps the time scrubber to the nearest day (cross-view linking).
- **Explanations + SHAP panel** — When `outputs/interpretability/explanations.csv` is present, narrative text and a horizontal bar chart of top SHAP drivers are built with D3 from the same row; otherwise those panels stay empty or hidden.

No bundler is required: modules under `frontend/js/` load in the browser; D3 and Leaflet are pulled from CDNs. Serve the app over HTTP (see below) so `fetch` can load the CSV and GeoJSON.

### Demo (time scrubber on the map)

The clip below is generated with `scripts/capture_frontend_media.py` (Chromium + Playwright). The choropleth updates as the time slider steps through the modeled dates.

![Animated demo: map choropleth while scrubbing the date slider](docs/images/map_timelapse.gif)

To **refresh** this file after a pipeline run, regenerate captures (see the next section) and replace `docs/images/map_timelapse.gif` with a copy of `outputs/frontend-captures/map_timelapse.gif`, then commit.

## Frontend (static snapshot)

The web UI under `frontend/` loads GeoJSON/CSV from `data/`, `baselines/outputs/`, and `outputs/interpretability/` using paths relative to `frontend/index.html`. To bundle **only what the app needs** for a folder upload or zip (e.g. Netlify, class submission):

```bash
python3 scripts/sync_frontend_data.py
# or:  make frontend-snapshot
```

This writes `outputs/frontend-snapshot/` with the same directory shape so `../data/...` still resolves. Test locally:

```bash
cd outputs/frontend-snapshot && python3 -m http.server 8000
# open http://localhost:8000/frontend/index.html
```

Optional zip: `python3 scripts/sync_frontend_data.py --zip` (or `make frontend-snapshot-zip`) creates `outputs/frontend-snapshot.zip`. For **Netlify** (or similar), set the **publish directory** to `outputs/frontend-snapshot` and open `/frontend/index.html`, or add a root redirect to that path. Regenerate the snapshot after you refresh `data/processed/`, `baselines/outputs/model_results.csv`, or `outputs/interpretability/`.

## Regenerating screenshots and the README GIF

The data sync **copies** files; it does not render the browser. To **regenerate** PNGs and the time-scrubber GIF (e.g. after the model or UI changes), install the full `requirements.txt` and Chromium for Playwright, then run the capture script:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python -m playwright install chromium
python3 scripts/capture_frontend_media.py
# → outputs/frontend-captures/map_overview.png, app_full.png, map_timelapse.gif
```

`make frontend-captures` is equivalent if you use a `.venv` in the project root. Options: `--no-gif`, `--gif-frames 10`, `--gif-ms 500`, `--viewport 1600x1000`. The script starts a local HTTP server from the **repo root** (same as `python3 -m http.server` there) so `fetch` to `data/` and `baselines/outputs/` works; `file://` is not used.

**README figure:** after capture, you can `cp outputs/frontend-captures/map_timelapse.gif docs/images/map_timelapse.gif` so the demo above stays current on GitHub.

## Current locked data choice

- Fire incidents: 2024 NFIRS PDR Light feature layer derived from the FEMA/USFA NFIRS Public Data Release, filtered to `STATE_ID='GA'`, `CITY='Atlanta'`, `INC_TYPE` in the fire range `100-199`, and `AID` in `('1','2','N')` to avoid aid-given double counts.
- Weather: Open-Meteo historical daily archive for Atlanta (`33.7490, -84.3880`) with daily mean temperature, mean relative humidity, precipitation sum, and max 10m wind speed.

## Scope note

This repo currently builds a model table from NFIRS fire incidents plus citywide daily weather and time/history features only. It does not currently add 911 incident data, census joins, or other neighborhood-context covariates, so downstream writeups should not claim those features were implemented here unless another team component adds them.
