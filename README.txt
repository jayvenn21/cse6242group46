DESCRIPTION
-----------
Ignition Insights is an end-to-end system for explaining and forecasting
short-horizon fire risk across an Atlanta grid. It ingests public NFIRS fire
incident records and Open-Meteo daily weather data, cleans and geocodes
incidents, lays a fixed 1 km spatial grid over the city, and builds a daily
cell-day modeling table with weather, calendar, and recent-history features.

Three models are trained on this table: a Gaussian KDE hotspot baseline that
captures static spatial density, a per-cell ARIMA baseline that tests temporal
signal, and a Random Forest classifier that combines all feature types. SHAP
TreeExplainer produces per-prediction feature contributions and short narrative
explanations for high-risk cells.

All outputs feed into an interactive browser-based dashboard built with Leaflet
and D3. Users can switch between model layers, scrub through dates with a time
slider, view score distributions, click individual grid cells for feature
snapshots, and read SHAP explanation panels. The goal is ranked risk awareness
and explanation, not binary fire alarms.


INSTALLATION
------------
Requirements: Python 3.9+, pip, and a modern web browser.

1. Clone the repository:

   git clone https://github.com/jayvenn21/cse6242group46.git
   cd cse6242group46

2. Install Python dependencies:

   python3 -m pip install -r requirements.txt

   This installs pandas, geopandas, scikit-learn, statsmodels, shap, folium,
   matplotlib, and other packages listed in requirements.txt.

3. (Optional) If you want to run the frontend capture script for screenshots:

   python3 -m pip install playwright pillow
   python -m playwright install chromium


EXECUTION
---------
The pipeline has four stages. Pre-built outputs are already included in the
repository, so you can skip to step 4 to just view the dashboard.

1. Fetch data (already done; raw data is in data/raw/):

   python3 scripts/fetch_nfirs_light.py \
     --state-id GA --city Atlanta \
     --out data/raw/nfirs_2024_atlanta_fire.geojson

   python3 scripts/fetch_weather_openmeteo.py \
     --latitude 33.7490 --longitude -84.3880 \
     --start-date 2024-01-01 --end-date 2024-12-31 \
     --out data/raw/atlanta_weather_2024.csv

2. Build the model table:

   python3 scripts/build_model_table.py \
     --incidents data/raw/nfirs_2024_atlanta_fire.geojson \
     --weather data/raw/atlanta_weather_2024.csv \
     --grid-size-m 1000 --horizon-days 1 \
     --outdir data/processed

   Outputs: data/processed/incidents_clean.parquet, grid_cells.geojson,
   cell_day_table.parquet, model_table.parquet

3. Run baselines and generate explanations:

   python3 baselines/run_baselines.py
   python3 scripts/build_explanations.py

   Outputs: baselines/outputs/model_results.csv,
   outputs/interpretability/explanations.csv, SHAP plots

4. Launch the interactive dashboard (local):

   python3 -m http.server 8000

   Then open http://localhost:8000/frontend/index.html in your browser.

   The dashboard loads grid_cells.geojson, model_results.csv, and
   explanations.csv. Use the metric dropdown to switch between RF probability,
   hotspot score, ARIMA score, incident count, and ground-truth target. Use
   the date slider to animate through test dates. Click any cell to see its
   time-series, feature snapshot, and SHAP explanation.

   Hosted version: https://jayvenn21.github.io/cse6242group46/frontend/index.html


DEMO VIDEO
----------
https://github.com/jayvenn21/cse6242group46/raw/main/demo6242.mp4
