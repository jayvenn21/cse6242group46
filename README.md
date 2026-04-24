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

## Current locked data choice

- Fire incidents: 2024 NFIRS PDR Light feature layer derived from the FEMA/USFA NFIRS Public Data Release, filtered to `STATE_ID='GA'`, `CITY='Atlanta'`, `INC_TYPE` in the fire range `100-199`, and `AID` in `('1','2','N')` to avoid aid-given double counts.
- Weather: Open-Meteo historical daily archive for Atlanta (`33.7490, -84.3880`) with daily mean temperature, mean relative humidity, precipitation sum, and max 10m wind speed.

## Scope note

This repo currently builds a model table from NFIRS fire incidents plus citywide daily weather and time/history features only. It does not currently add 911 incident data, census joins, or other neighborhood-context covariates, so downstream writeups should not claim those features were implemented here unless another team component adds them.
