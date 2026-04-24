# Ignition Insights: Explaining and Forecasting Urban Fire Risk

**Team 46:** Vishruth Anand, Vineeth Nareddy, Rian Rahman, James Reilly, Jayanth Vennamreddy

## 1 Introduction

Fire departments decide where to staff, what to inspect, and how ready to be, all without knowing where the next call comes from. Fire activity is not spread evenly across a city. Some neighborhoods see repeat incidents month after month; others go quiet for long stretches and then spike. Weather, day of week, and recent local history all seem to play a role, but the raw incident log does not make any of that easy to see. What remains is a table of past events, not a picture of where risk sits right now or why.

Ignition Insights is our attempt to close that gap. We take public fire incident data from Atlanta, join it with daily weather, lay a 1 km grid over the city, and build a daily modeling table where every row is one grid cell on one date. We train three models on that table (a kernel-density hotspot baseline, per-cell ARIMA, and a Random Forest classifier) and feed the outputs into a Leaflet/D3 dashboard where a user can scrub through dates, compare model layers, click a cell, and read a SHAP-backed explanation of why that cell scored the way it did.

We do not claim to predict individual fires. At a 0.5% positive rate in the test set, no model we tried comes close to a reliable binary alarm. What the system does well is *rank* cells by relative risk and *explain* the ranking, which is closer to what a fire department actually needs when deciding where to look.

## 2 Problem Definition

In plain terms: given Atlanta's recent fire history, today's weather, and what has been happening in each neighborhood lately, which 1 km patches of the city look most likely to have a fire incident tomorrow, and what is driving that estimate?

More precisely, we tile the study area into fixed grid cells $G = \{g_1, \ldots, g_n\}$ (in our case $n = 1{,}176$ cells, of which 364 have at least one modeled day with data) and index time as daily steps $T = \{t_1, \ldots, t_m\}$ covering the full year 2024. For each cell-day pair $(g_i, t_j)$ we build a feature vector $x_{i,j}$ with weather, calendar, and recent-history features. The target is

$$
y_{i,j} =
\begin{cases}
1 & \text{at least one fire in } g_i \text{ during the next day} \\
0 & \text{otherwise}
\end{cases}
$$

and we learn $f(x_{i,j}) \to p_{i,j}$, a risk score between 0 and 1. The visualization task is then to project those scores, alongside the baselines and the ground-truth labels, back onto the map so users can compare models, browse dates, and drill into individual cells.

Three things make this hard. First, the data is extremely imbalanced: out of 132,860 cell-day rows in the model table, only 1,415 are positive (~1.1%), and in the 73-day test window that drops to 138 out of 26,572 (0.5%). Second, risk has both a spatial component (some cells are historically busier) and a temporal component (recent activity, weather, weekends). Third, a score by itself is not very useful in a public-safety setting; the user needs to know *why* it is high.

## 3 Literature Survey

Urban fire activity clusters in space and time. Asgary et al. [4] showed strong geographic and temporal patterning in Toronto structural fires, and Xiao et al. [14] modeled urban fire occurrence with spatial hazard methods. Both support using fixed grid cells instead of treating events as isolated points.

On the modeling side, Wang et al. [1] (CityGuard) combined temporal features with grid-based spatial structure for citywide fire forecasting. Jin et al. [7] used deep sequence learning on a similar grid setup. Yuan and Wylie [5] directly compared ARIMA and Random Forest for Austin fire incidents, and their finding that performance varies by district motivated us to include both a time-series baseline and an ML model. Madaio et al. [6] built Firebird for Atlanta fire-inspection prioritization, which is the closest prior system to ours geographically, though their problem is building-level inspection ranking rather than short-horizon grid-cell forecasting.

On the feature and interpretability side, Ahn et al. [8] showed that stacking heterogeneous data sources improves prediction, Cui et al. [11] demonstrated SHAP-style explanation in fire-risk assessment, and Ku et al. [10] linked GIS features to fire drivers through interpretable dimensionality reduction. Liao et al. [12] and Jennings [15] argue that housing conditions and socioeconomic context matter for residential fire risk, which provides useful context for future extensions, though we do not incorporate census data in the current build. Coffield et al. [2], Lattimer et al. [3], and Kang et al. [13] round out the picture with environmental covariates, physics-based simulation, and GIS-ML integration respectively.

The main gap we see in this literature is that most systems do one or two of forecasting, explanation, and interactive exploration, but rarely all three in a single interface. That is what we tried to build.

## 4 Proposed Method

### Intuition

The idea is straightforward: if you give a model recent incident counts, weather, day-of-week, and which cell you are looking at, it should be able to rank cells by relative risk better than a static hotspot map. And if you pair that ranking with a SHAP breakdown and a dashboard that lets you scrub through time, the output becomes something interpretable rather than a raw table of probabilities.

### Data

**Incidents.** We pull 2024 NFIRS PDR Light data from the FEMA ArcGIS FeatureServer, filtered to Atlanta (`STATE_ID='GA'`, `CITY='Atlanta'`). We keep fire-type codes 100-199 and aid values 1, 2, or N (to drop mutual-aid duplicates). After cleaning and deduplication, we end up with 1,473 geocoded fire incidents spanning January 1 through December 30, 2024.

**Weather.** Daily observations from the Open-Meteo archive API at Atlanta's coordinates (33.749, -84.388): mean temperature, mean relative humidity, total precipitation, and max 10 m wind speed. One row per day, merged citywide (same weather for every cell on a given date).

**Sizes.** The raw incidents file is a GeoJSON; after processing, `incidents_clean.parquet` is ~0.1 MB, `grid_cells.geojson` is ~0.4 MB, and the full `model_table.parquet` is ~0.1 MB (132,860 rows x 18 columns). The model results CSV with all three models' predictions is 4.1 MB.

### Preprocessing pipeline

The pipeline (`scripts/build_model_table.py`) is format-agnostic: it reads CSV, parquet, GeoJSON, shapefile, or GeoPackage and tries to auto-detect column names for date, latitude, longitude, and incident type (with CLI overrides when that fails). After loading, it standardizes timestamps, coerces coordinates, drops rows outside valid lat/lon bounds, filters to fire-type codes, and deduplicates on incident-number keys when available.

Cleaned incidents are projected to UTM and overlaid with a 1,000 m square grid. Each incident gets a `grid_id` like `r20_c14` from its floor-divided UTM coordinates. The grid polygons are reprojected to WGS84 and exported as GeoJSON so the frontend and the models share the same cell definitions.

Next the pipeline builds a full cross-product of (grid_id, date) pairs, covering every cell for every day in the study range. For each cell-day it records `incident_count`, merges the daily weather, and adds calendar features: `day_of_week`, `month`, `season`, `is_weekend`, and `is_holiday` (US federal holidays via the `holidays` library). History features are `lag_1`, `lag_3`, `lag_7` (shifted incident counts) and `rolling_sum_7`, `rolling_sum_14` (shifted rolling window sums, so no leakage from the current day). The target `target_next_interval` is 1 if the cell sees any fire in the next `horizon_days` (default 1).

The result is a 133K-row cell-day table. Rows where the forward target is undefined (last day of the range) are dropped to produce the 132,860-row model table.

### Hotspot baseline

We fit a 2D Gaussian KDE over training-set cell centroids weighted by incident count and evaluate the density at every cell. The density is normalized into `hotspot_prob` and a threshold is picked to maximize F1 on the training data. This is the simplest possible spatial model: it asks whether historical density alone carries signal about future risk. It ignores weather, time, and recent trends entirely.

### ARIMA baseline

For cells with at least 5 nonzero training days (up to 50 cells), we run a grid search over ARIMA(p,d,q) with p in {0,1,2}, d in {0,1}, q in {0,1,2}, pick the best by AIC, and forecast on the test dates. Forecasts are clipped to [0, $\infty$) and normalized. Cells that did not qualify get a fallback based on their historical rate. ARIMA serves as a sanity check for whether per-cell temporal signal adds anything beyond spatial density, but in practice most cells are too sparse for a stable fit.

### Random Forest

This is the main model. Features: temperature, humidity, precipitation, wind, day_of_week, month, is_weekend, is_holiday, lag_1, lag_3, lag_7, rolling_sum_7, rolling_sum_14, and an integer-encoded grid_id (so the model can learn cell-level effects). Hyperparameters: 300 trees, max depth 15, min samples per leaf 10, balanced class weights, seed 42. The threshold for `rf_pred` is chosen on the training set by F1. The probability output `rf_prob` is what the frontend actually uses, as it is more informative than the binary prediction.

### Interpretability

We retrain the same RF on the same features and run SHAP TreeExplainer to get per-feature contributions for every row. The explanation pipeline picks the top 3 drivers for each cell-date, records their SHAP values, and writes a one-sentence narrative like *"Risk is elevated mainly because recent 14-period activity (increases risk), recent 7-period activity (increases risk), and month (decreases risk)."* These rows are saved to `explanations.csv` and loaded by the frontend.

### Frontend

The interface (`frontend/index.html`) is a single-page app using Leaflet for the basemap and D3 for the analytical views. It loads `grid_cells.geojson`, `model_results.csv`, and `explanations.csv` at startup.

The main view is a choropleth of the Atlanta grid. A **metric dropdown** lets users switch between RF probability, hotspot score, ARIMA score, raw incident count, and ground-truth target. A **date slider** with play/pause steps through the 73 test dates; when you move it, the map colors, the status bar, and the right-panel charts all update together.

The right panel activates when you click a cell. It shows: (1) a **histogram** of the current metric across all cells on that day, (2) a **time-series chart** of the three model probabilities for the selected cell across all test dates, (3) a **snapshot table** of that cell's feature values on the selected day, and (4) a **SHAP explanation panel** with a horizontal bar chart of top drivers and a narrative sentence, when an explanation row exists. Clicking a point on the time-series chart jumps the global date slider to that day, keeping everything in sync.

## 5 Evaluation

### Setup

The model table is split temporally: the first 80% of unique dates go to training, the last 20% to testing. This gives us 292 training dates (Jan 1 to Oct 18) and 73 test dates (Oct 19 to Dec 30). We do not shuffle rows because that would leak future information into training.

The test set has 26,572 cell-date rows. Of those, 138 are positive (0.52%). This extreme imbalance is the single most important fact about the evaluation: any classifier that always says "no fire" gets 99.5% accuracy.

We report accuracy, precision, recall, F1, ROC-AUC, and PR-AUC. Accuracy is included for completeness, but it is nearly meaningless here. The ranking metrics (ROC-AUC, PR-AUC) matter more because our real use case is risk ranking, not yes/no alarms.

### Results

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|
| Hotspot | 0.9818 | 0.0274 | 0.0725 | 0.0398 | 0.5295 | 0.0086 |
| ARIMA | 0.9920 | 0.0375 | 0.0217 | 0.0275 | 0.5910 | 0.0110 |
| Random Forest | 0.9947 | 0.0000 | 0.0000 | 0.0000 | 0.6508 | 0.0144 |

**Accuracy is misleading.** All three models exceed 98% because almost every row is negative. A trivial "always predict 0" classifier would get 99.5%.

**Hotspot** has the highest recall (7.25%) among the thresholded classifiers, meaning it does flag a few cells that actually have fires tomorrow. But precision is under 3%, so most of its alarms are false. This is consistent with a spatial prior: historically busy areas carry some signal, but density alone is not enough.

**ARIMA** slightly improves the ranking metrics (ROC-AUC 0.59, PR-AUC 0.011) over the hotspot, but recall is lower at 2.17%. Most cells simply do not have enough positive days for a stable time-series fit, so ARIMA mostly falls back to the historical rate.

**Random Forest** has the best ranking performance (ROC-AUC 0.65, PR-AUC 0.014) but its chosen threshold produces zero true positives on the test set, resulting in 0.0 precision/recall/F1. At first glance this appears poor, but it means the probability surface is more informative than the binary cutoff. In the frontend, we use `rf_prob` as a continuous color scale rather than a binary alarm, which better serves the risk-ranking use case.

To put PR-AUC in context: a random classifier on data with 0.5% positives would score PR-AUC $\approx$ 0.005. RF's 0.0144 is roughly 3x better than random, which is modest but real given how sparse fire events are.

### Observations from the dashboard

Looking at the interactive map, a few patterns stand out. Cells in midtown and southwest Atlanta consistently score higher across models; the hotspot baseline captures this but does not differentiate between days. RF probabilities vary meaningfully day to day in a way that hotspot scores do not, reflecting the influence of weather and recent activity. The SHAP explanations for high-risk cells almost always point to `rolling_sum_14` and `rolling_sum_7` as the top drivers, with `month` and `wind` as secondary factors. Recent local activity is the strongest short-term signal. On days with zero observed fires city-wide, RF probabilities drop across the board but the spatial ranking is still preserved: the same cells that are usually riskier still rank at the top.

## 6 Conclusions and Discussion

We built an end-to-end pipeline and dashboard for exploring fire risk in Atlanta: data fetch, cleaning, grid construction, feature engineering, three baselines, SHAP-based explanation, and a linked Leaflet/D3 interface. The main takeaway is that at this level of imbalance (0.5% positive rate in the test set), binary classification metrics are not the right way to judge the system. What matters is whether the model ranks risk in a way that is better than the baselines and whether the interface helps users understand and interrogate that ranking. On both counts, we believe the current system meets that bar.

**Limitations.** The feature set is limited to weather, calendar, and incident history. We originally discussed incorporating 911 dispatch records, census demographics, building age, and land-use data, but none of that made it into the final build. The RF threshold selection clearly needs improvement; a probability-calibrated approach or a cost-sensitive threshold would be better than the current F1-maximizing strategy. ARIMA is constrained by sparsity and only covers about 50 cells. We did not run a formal user study on the dashboard.

**Future work.** Adding neighborhood-level context (census, zoning, building stock) would give the model more to work with. Gradient boosting or a spatiotemporal neural network could improve ranking. On the visualization side, a task-based user study would tell us whether the linked-view design actually helps decision-making compared to a simpler static map.

**Effort distribution:** All team members contributed a similar amount of effort. Vishruth Anand: data sourcing, cleaning, preprocessing, feature engineering. Vineeth Nareddy: baseline models, RF, evaluation metrics. Jayanth Vennamreddy: spatial grid construction, temporal aggregation, map rendering and prediction overlays. James Reilly: interpretability, SHAP analysis, explanation panel. Rian Rahman: frontend integration, D3/Leaflet linked views, visual polish, report structure. Everyone contributed to final review, poster content, and presentation prep.

## References

[1] Q. Wang et al., "CityGuard: citywide fire risk forecasting using a machine learning approach," *Proc. ACM IMWUT*, 3(4), 1-21, 2019.

[2] S. R. Coffield et al., "Machine learning to predict final fire size at the time of ignition," *Int. J. Wildland Fire*, 28(11), 861-873, 2019.

[3] B. Y. Lattimer, J. L. Hodges, and A. M. Lattimer, "Using machine learning in physics-based simulation of fire," *Fire Safety J.*, 114, 102991, 2020.

[4] A. Asgary, A. Ghaffari, and J. Levy, "Spatial and temporal analyses of structural fire incidents and their causes: A case of Toronto, Canada," 2010.

[5] Y. Yuan and A. G. Wylie, "Comparing machine learning and time series approaches in predictive modeling of urban fire incidents: A case study of Austin, Texas," 2024.

[6] M. Madaio et al., "Firebird: Predicting fire risk and prioritizing fire inspections in Atlanta," 2016.

[7] G. Jin et al., "Urban fire situation forecasting using deep sequence learning," *Applied Soft Computing*, 2020.

[8] S. Ahn et al., "Comprehensive building fire risk prediction using machine learning and stacking ensemble methods," *Fire*, 2024.

[9] C. Zhang et al., "A historical data based method for predicting firefighters demand in urban fires," *Fire Safety J.*, 2024.

[10] C.-Y. Ku et al., "Characterizing human-caused fires using GIS-based dimensionality reduction techniques in Keelung City, Taiwan," 2024.

[11] S. Cui et al., "Assessing urban fire risk: An ensemble learning approach based on scenarios and cases," *Int. J. Disaster Risk Reduction*, 114, 104941, 2024.

[12] C. Liao et al., "Beyond individual factors: a critical ethnographic account of urban residential fire risks in single-room occupancy housing," 2024.

[13] Y. Kang, N. Cho, and S. Son, "Spatiotemporal prediction of urban fire risk using GIS and machine learning," *Sustainability*, 2018.

[14] Y. Xiao, P. Murray Tuite, and K. Ozbay, "Development of a spatial hazard model for urban fire occurrences," *Accident Analysis & Prevention*, 2018.

[15] C. R. Jennings, "Social and economic characteristics as determinants of residential fire risk," *Fire Safety J.*, 2013.
