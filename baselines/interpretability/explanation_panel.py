import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURE_COLS = [
    "temperature", "humidity", "precipitation", "wind",
    "day_of_week", "month", "is_weekend", "is_holiday",
    "lag_1", "lag_3", "lag_7", "rolling_sum_7", "rolling_sum_14"
]


def prepare_features(df):
    X = df[FEATURE_COLS].copy().fillna(0)
    unique_grids = sorted(df["grid_id"].unique())
    grid_map = {v: i for i, v in enumerate(unique_grids)}
    X["grid_id_enc"] = df["grid_id"].map(grid_map).fillna(-1).astype(int)
    y = df["target_next_interval"].values
    return X, y, grid_map


def prepare_test_features(df, grid_map):
    X = df[FEATURE_COLS].copy().fillna(0)
    X["grid_id_enc"] = df["grid_id"].map(grid_map).fillna(-1).astype(int)
    return X


def temporal_split(df, train_fraction=0.8):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    unique_dates = df["date"].unique()
    split_idx = int(len(unique_dates) * train_fraction)

    train_dates = unique_dates[:split_idx]
    test_dates = unique_dates[split_idx:]

    train_df = df[df["date"].isin(train_dates)].copy()
    test_df = df[df["date"].isin(test_dates)].copy()
    return train_df, test_df


def train_rf(train_df):
    X_train, y_train, grid_map = prepare_features(train_df)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=15,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model, grid_map, list(X_train.columns)


def build_rule_based_explanation(row):
    reasons = []

    if row.get("temperature", 0) > 75:
        reasons.append("higher temperature")
    if row.get("humidity", 100) < 40:
        reasons.append("lower humidity")
    if row.get("wind", 0) > 12:
        reasons.append("stronger wind")
    if row.get("rolling_sum_7", 0) > 0:
        reasons.append("recent fire activity in the last 7 periods")
    if row.get("rolling_sum_14", 0) > row.get("rolling_sum_7", 0):
        reasons.append("elevated recent activity over the last 14 periods")

    if not reasons:
        return "Risk appears lower because recent activity and weather indicators are not elevated."

    return "Risk is elevated mainly because of " + ", ".join(reasons[:3]) + "."


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "processed", "model_table.parquet")
    output_dir = os.path.join(base_dir, "outputs", "interpretability")
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_parquet(data_path)
    train_df, test_df = temporal_split(df)

    model, grid_map, feature_names = train_rf(train_df)
    X_test = prepare_test_features(test_df, grid_map)

    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)

    export_df = test_df[["grid_id", "date"] + FEATURE_COLS].copy()
    export_df["rf_prob"] = probs
    export_df["rf_pred"] = preds
    export_df["explanation_text"] = export_df.apply(build_rule_based_explanation, axis=1)

    export_df.to_csv(os.path.join(output_dir, "explanations.csv"), index=False)
    print(f"Saved explanations to {output_dir}")


if __name__ == "__main__":
    main()
