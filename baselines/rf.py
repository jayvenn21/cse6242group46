import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
feature_cols = [
    "temperature", "humidity", "precipitation", "wind",
    "day_of_week", "month", "is_weekend", "is_holiday",
    "lag_1", "lag_3", "lag_7", "rolling_sum_7", "rolling_sum_14"
]

def _prepare_features(df):
    X = df[feature_cols].copy()
    X = X.fillna(0)
    
    unique_grids = sorted(df["grid_id"].unique())
    grid_map = {v: i for i, v in enumerate(unique_grids)}
    X["grid_id_enc"] = df["grid_id"].map(grid_map).fillna(-1).astype(int)

    y = df["target_next_interval"].values
    return X, y, grid_map

def _prepare_test_features(df, grid_map):
    X = df[feature_cols].copy()
    X = X.fillna(0)
    X["grid_id_enc"] = df["grid_id"].map(grid_map).fillna(-1).astype(int)
    return X

def train_random_forest(train_df, config):
    rf = config["random_forest"]
    rf_n_estimators = rf["n_estimators"]
    rf_max_depth = rf["max_depth"]
    rf_min_samples_leaf = rf["min_samples_leaf"]
    random_seed = config["random_seed"]

    X_train, y_train, grid_map = _prepare_features(train_df)
    feature_names = list(X_train.columns)

    model = RandomForestClassifier(
        n_estimators=rf_n_estimators,
        max_depth=rf_max_depth,
        min_samples_leaf=rf_min_samples_leaf,
        class_weight="balanced",
        random_state=random_seed,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    train_probs = model.predict_proba(X_train)[:, 1]
    best_thresh, best_f1 = 0.5, 0.0

    sample_size = min(len(y_train), 100000)
    sample_idx = np.random.choice(len(y_train), sample_size, replace=False)
    y_true_sample = y_train[sample_idx]
    score_sample = train_probs[sample_idx]

    for t in np.arange(0.01, 0.99, 0.01):
        preds = (score_sample >= t).astype(int)
        f = f1_score(y_true_sample, preds, zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_thresh = t

    return model, grid_map, feature_names, best_thresh


def predict_random_forest(test_df, model, grid_map, threshold):
    X_test = _prepare_test_features(test_df, grid_map)

    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= threshold).astype(int)

    test_df = test_df.copy()
    test_df["rf_prob"] = probs
    test_df["rf_pred"] = preds

    return test_df
