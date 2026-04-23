import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from sklearn.metrics import f1_score
def train_hotspot(train_df, grid_gdf, config):
    random_seed = config["random_seed"]
    np.random.seed(random_seed)

    grid_gdf = grid_gdf.copy()
    grid_gdf["lon_center"] = grid_gdf.geometry.centroid.x
    grid_gdf["lat_center"] = grid_gdf.geometry.centroid.y
    centroids = grid_gdf.set_index("grid_id")[["lat_center", "lon_center"]]

    train_with_coords = train_df.merge(centroids, on="grid_id", how="left")

    cell_stats = (
        train_with_coords.groupby(["grid_id", "lat_center", "lon_center"])["incident_count"]
        .sum()
        .reset_index()
    )

    lats, lons = [], []
    for _, r in cell_stats.iterrows():
        count = max(int(r["incident_count"]), 0)
        if count > 0:
            lats.extend([r["lat_center"]] * count)
            lons.extend([r["lon_center"]] * count)

    if not lats:
        return {}, 0.5

    lats = np.array(lats)
    lons = np.array(lons)

    kde = gaussian_kde(np.vstack([lats, lons]), bw_method="scott")

    all_cells = centroids.reset_index()
    coords = np.vstack([all_cells["lat_center"].values, all_cells["lon_center"].values])
    scores = kde(coords)

    scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-12)
    cell_scores = dict(zip(all_cells["grid_id"], scores))

    train_df = train_df.copy()
    train_df["score"] = train_df["grid_id"].map(cell_scores).fillna(0)
    
    y_true = train_df["target_next_interval"].values
    best_thresh, best_f1 = 0.5, 0.0
    
    sample_size = min(len(train_df), 100000)
    sample_idx = np.random.choice(len(train_df), sample_size, replace=False)
    y_true_sample = y_true[sample_idx]
    score_sample = train_df["score"].values[sample_idx]

    for t in np.arange(0.01, 0.99, 0.01):
        preds = (score_sample >= t).astype(int)
        f = f1_score(y_true_sample, preds, zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_thresh = t

    return cell_scores, best_thresh


def predict_hotspot(test_df, cell_scores, threshold):
    test_df = test_df.copy()
    test_df["hotspot_prob"] = test_df["grid_id"].map(cell_scores).fillna(0)
    test_df["hotspot_pred"] = (test_df["hotspot_prob"] >= threshold).astype(int)
    return test_df
