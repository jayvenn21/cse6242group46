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

There’s a static site under `frontend/` that turns the model outputs into something you can **explore in time and space**—after you’ve run the baselines you get a live choropleth over Atlanta, not just another CSV.

### What you’re looking at

The main view is a **hex-style grid** (GeoJSON cells) laid on a light basemap. Each cell is a fixed neighborhood patch; color encodes whatever you pick in **“Color by”** for the **selected day**. The legend at the bottom of the map shows the scale (roughly yellow → deep red) and the min/max of that metric *across cells that have a model row on that day*, so the map is always comparable within the current day and metric.

You can color by several fields from `model_results.csv`, including **RF probability**, **hotspot / ARIMA model scores**, **ARIMA forecast**, **incident counts** in the interval, and the **next-interval target**—so the same grid can show “model belief” or raw outcome structure, depending on what you want to study.

The **time control** at the top is a date index (not a free calendar): it steps through the dates that actually appear in the model file. **Play** animates forward through those dates. When you move time, every view that depends on “today” updates together: the map fill, the status line under the map, the distribution plot, and (if you’ve selected a cell) the snapshot table for that day.

**Hover** a cell to see its id and the current metric value in the status strip; **click** a cell to “latch” it. The right-hand column then shows (1) a **histogram** of the chosen metric over all cells with data on that day, (2) a **small-multiple line chart** of the three model probability tracks for *that cell* across *all* dates in the CSV, and (3) a **read-only table** of key fields for that cell on the selected day. If you generated `explanations.csv`, you also get a short **narrative** and a **horizontal bar chart of top SHAP drivers** for that cell–date when a row exists. **Clicking a point** on the time-series chart jumps the global date scrubber to the nearest modeled day so the map and table stay in sync—that’s the main “linked view” gesture besides the slider.

Technically, **Leaflet** owns the map and tiles; **D3** builds the scales, paths, axes, brushes, and text for the charts and legend. No bundler—ES modules in `frontend/js/`, D3 7 and Leaflet from CDNs.

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

### Host the same app on Vercel (no GitHub “owner” on the org repo)

The app is all static files. This repo is set up for **[Vercel](https://vercel.com)**: on each deploy, `npm run build` runs `scripts/assemble-site.mjs` and copies `frontend/`, the grid GeoJSON, `model_results.csv`, and `outputs/interpretability/**` into `public/`, with the same folder layout the app already expects. You can deploy with **your own Vercel account**; you do **not** need admin access to the org repo’s GitHub Pages settings (useful when only a maintainer can enable Pages).

**Option A — Import from Git (dashboard)**  
1. [vercel.com](https://vercel.com) → **Add New Project** → import this GitHub repo.  
2. Vercel should pick up `vercel.json` (build: `npm run build`, output: `public`). Framework: **Other**.  
3. Deploy. Your site will look like `https://<project>.vercel.app/frontend/index.html` (or open `/` — the root `index.html` in `public/` redirects into the app).

**Option B — Vercel CLI (no org GitHub app install)**  
From a local clone, after `npx vercel` and logging in, deploy a production build. No special GitHub permission beyond being able to clone.  

If the org **blocks** third-party Git apps for the team repo, use the CLI, or deploy from a **personal fork** that has the same `vercel.json` and build.

**Relevant files:** `vercel.json`, `package.json` (`build` → `node scripts/assemble-site.mjs`), and `scripts/assemble-site.mjs`. The `public/` directory is **generated** and is gitignored.

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

The script also writes `map_overview.png` and `app_full.png` under `outputs/frontend-captures/`. That folder is **not** gitignored—you can add and commit those files if you want the latest PNGs in the repo for the team; otherwise they stay local. The only asset the README needs for the inline GIF is `docs/images/map_timelapse.gif`.

## Current data choices (locked in this repo)

- **Incidents:** 2024 NFIRS PDR Light, filtered to `STATE_ID='GA'`, `CITY='Atlanta'`, fire `INC_TYPE` 100–199, and `AID` in `1`, `2`, or `N` to reduce double-counting from aid records.
- **Weather:** Open-Meteo daily history for `33.749, -84.388` — mean temp, mean RH, daily precip, and max 10 m wind.

## Scope note

Right now the table is **only** NFIRS + citywide daily weather + time/history features. We are **not** folding in 911, census, or other neighborhood context unless another part of the project adds that — don’t claim those in the writeup if they aren’t in this branch.
