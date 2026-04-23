import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

try:
    import shap
except ImportError:
    shap = None

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


def clean_feature_name(name):
    rename_map = {
        "grid_id_enc": "location history",
        "rolling_sum_14": "recent 14-period activity",
        "rolling_sum_7": "recent 7-period activity",
        "lag_1": "last-period incidents",
        "lag_3": "3-period lag activity",
        "lag_7": "7-period lag activity",
        "day_of_week": "day of week",
        "is_weekend": "weekend timing",
        "is_holiday": "holiday timing",
    }
    return rename_map.get(name, name.replace("_", " "))


def build_shap_explanation(row):
    drivers = []
    for i in range(1, 4):
        feat = row[f"top_driver_{i}"]
        val = row[f"top_driver_{i}_shap"]
        direction = "increases" if val > 0 else "decreases"
        drivers.append(f"{clean_feature_name(feat)} ({direction} risk)")

    if row["rf_prob"] >= 0.5:
        prefix = "Risk is elevated mainly because "
    else:
        prefix = "Risk remains lower mainly because "

    return prefix + ", ".join(drivers[:-1]) + f", and {drivers[-1]}."


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "processed", "model_table.parquet")
    output_dir = os.path.join(base_dir, "outputs", "interpretability")
    os.makedirs(output_dir, exist_ok=True)

    if shap is None:
        raise ImportError("shap must be installed to build SHAP-based explanations.")

    df = pd.read_parquet(data_path)
    train_df, test_df = temporal_split(df)

    model, grid_map, feature_names = train_rf(train_df)
    X_test = prepare_test_features(test_df, grid_map)

    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)

    full_df = test_df[["grid_id", "date"] + FEATURE_COLS].copy()
    full_df["grid_id_enc"] = X_test["grid_id_enc"].values
    full_df["rf_prob"] = probs
    full_df["rf_pred"] = preds

    high_idx = full_df.nlargest(50, "rf_prob").index

    medium_candidates = full_df[
        (full_df["rf_prob"] >= full_df["rf_prob"].quantile(0.40)) &
        (full_df["rf_prob"] <= full_df["rf_prob"].quantile(0.60))
    ]
    if len(medium_candidates) > 0:
        medium_idx = medium_candidates.sample(
            n=min(25, len(medium_candidates)),
            random_state=42
        ).index.tolist()
    else:
        medium_idx = []

    low_candidates = full_df.nsmallest(200, "rf_prob")
    if len(low_candidates) > 0:
        low_idx = low_candidates.sample(
            n=min(25, len(low_candidates)),
            random_state=42
        ).index.tolist()
    else:
        low_idx = []

    explain_idx = list(dict.fromkeys(list(high_idx) + medium_idx + low_idx))
    explain_df = full_df.loc[explain_idx].copy()
    X_explain = X_test.loc[explain_idx].copy()

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_explain)

    if isinstance(shap_values, list):
        shap_matrix = shap_values[1]
    elif len(np.array(shap_values).shape) == 3:
        shap_matrix = np.array(shap_values)[:, :, 1]
    else:
        shap_matrix = shap_values

    shap_df = pd.DataFrame(shap_matrix, columns=X_explain.columns, index=explain_df.index)

    for col in shap_df.columns:
        explain_df[f"{col}_shap"] = shap_df[col]

    abs_shap = shap_df.abs()
    top_idx = np.argsort(-abs_shap.values, axis=1)[:, :3]
    cols = shap_df.columns.tolist()

    explain_df["top_driver_1"] = [cols[idxs[0]] for idxs in top_idx]
    explain_df["top_driver_2"] = [cols[idxs[1]] for idxs in top_idx]
    explain_df["top_driver_3"] = [cols[idxs[2]] for idxs in top_idx]

    explain_df["top_driver_1_shap"] = [shap_df.iloc[i, idxs[0]] for i, idxs in enumerate(top_idx)]
    explain_df["top_driver_2_shap"] = [shap_df.iloc[i, idxs[1]] for i, idxs in enumerate(top_idx)]
    explain_df["top_driver_3_shap"] = [shap_df.iloc[i, idxs[2]] for i, idxs in enumerate(top_idx)]

    explain_df["explanation_text"] = explain_df.apply(build_shap_explanation, axis=1)

    explain_df.to_csv(os.path.join(output_dir, "explanations.csv"), index=False)
    full_df.to_csv(os.path.join(output_dir, "scored_test_rows.csv"), index=False)

    print(f"Saved explanations to {output_dir}")


if __name__ == "__main__":
    main()