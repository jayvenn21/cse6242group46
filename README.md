# Ignition Insights Preprocessing

This is Team 46’s CSE 6242 project pipeline: we take raw fire incidents, match them to daily weather, put everything on a fixed city grid, and end up with a table you can hand to baselines and models.

## Dataset assumptions

- **Fire data:** FEMA NFIRS (or similar) — `.gpkg`, `.csv`, or `.parquet` with locations.
- **Weather:** one row per day with date, plus temperature, humidity, precipitation, and wind. The build script tries to guess column names; you can override on the command line.
- NFIRS is huge national data, so you’ll almost always want to **filter to your city** before running the heavy steps.

## Install

```bash
python3 -m pip install -r requirements.txt
```

`requirements.txt` also lists **Playwright** and **Pillow** for the optional capture script that records the map GIF for this README. If you only care about the data pipeline, you can ignore them until you need to refresh screenshots. The first time you run captures, you’ll also run `python -m playwright install chromium` once.

## Run

What we actually used in this repo (Atlanta, 2024-style handoff):

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

A more generic example (your own paths and filters):

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

If the auto-detect step can’t find a column, name it yourself, for example:

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

By default this lands in `data/processed/`:

- `incidents_clean.parquet`
- `grid_cells.geojson`
- `cell_day_table.parquet`
- `model_table.parquet`

`model_table.parquet` is what we feed into RF, ARIMA, and the rest of the baselines.

## The map app (Leaflet + D3)

There’s a small static site under `frontend/` you can open after you’ve run the baselines and have `model_results.csv` (and the interpretability files if you want the explanation side panel). **Leaflet** shows the basemap and wires up the grid from GeoJSON. **D3** drives everything that feels like a chart: the colored cells and legend, the time scrubber, the histogram for “this day,” the per-cell time series, and the SHAP-style bars when that CSV is there.

The idea is **linked views**: one date and one “color by” choice drive the map, the small multiples, and the readouts together. Scrub the slider and the map updates; pick a cell and the line chart locks onto that `grid_id`; click the chart and the slider jumps. No bundler — plain ES modules, D3 7, Leaflet, from CDNs.

### Quick preview

This GIF was recorded with `scripts/capture_frontend_media.py` (headless Chrome via Playwright). It’s the choropleth stepping through a few model dates with the time slider.

<p align="center">
  <img src="./docs/images/map_timelapse.gif" width="600" height="350" alt="Fire risk map: choropleth updates as the date slider moves">
</p>

### Run it in a browser

From the **repo root** (so paths like `../data/...` resolve the same as in class):

```bash
python3 -m http.server 8000
```

Then open **http://localhost:8000/frontend/index.html** in a normal tab. Browsers won’t load the data off `file://`, so a tiny local server is the usual trick.

## Updating the GIF in this README

If you change the model output or the UI, you can re-record the clip:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python -m playwright install chromium
python3 scripts/capture_frontend_media.py
# writes outputs/frontend-captures/{map_overview.png,app_full.png,map_timelapse.gif}
```

Or, with a venv already set up, `make frontend-captures`. Handy flags: `--no-gif`, `--gif-frames 10`, `--gif-ms 500`, `--viewport 1600x1000`. When you’re happy with it, copy the new animation over the one GitHub shows:

`cp outputs/frontend-captures/map_timelapse.gif docs/images/map_timelapse.gif` and commit.

## Current data choices (locked in this repo)

- **Incidents:** 2024 NFIRS PDR Light, filtered to `STATE_ID='GA'`, `CITY='Atlanta'`, fire `INC_TYPE` 100–199, and `AID` in `1`, `2`, or `N` to reduce double-counting from aid records.
- **Weather:** Open-Meteo daily history for `33.749, -84.388` — mean temp, mean RH, daily precip, and max 10 m wind.

## Scope note

Right now the table is **only** NFIRS + citywide daily weather + time/history features. We are **not** folding in 911, census, or other neighborhood context unless another part of the project adds that — don’t claim those in the writeup if they aren’t in this branch.
