import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


def save_feature_importance(model, feature_names, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1][:15]

    plt.figure(figsize=(8, 5))
    plt.barh([feature_names[i] for i in idx], importances[idx])
    plt.gca().invert_yaxis()
    plt.xlabel("Importance")
    plt.title("Random Forest Feature Importances")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "feature_importance.png"), dpi=150)
    plt.close()


def save_shap_outputs(model, X_test, output_dir):
    if shap is None:
        print("shap is not installed. Skipping SHAP plots.")
        return

    os.makedirs(output_dir, exist_ok=True)

    sample_n = min(500, len(X_test))
    X_sample = X_test.sample(sample_n, random_state=42)

    explainer = shap.TreeExplainer(model)

    shap_explanation = explainer(X_sample)
    shap_values = shap_explanation.values

    if shap_values.ndim == 3:
        shap_values = shap_values[:, :, 1]

    plt.figure()
    shap.summary_plot(
        shap_values,
        X_sample,
        show=False,
        plot_type="dot"
    )
    plt.savefig(
        os.path.join(output_dir, "shap_summary.png"),
        dpi=150,
        bbox_inches="tight"
    )
    plt.close()

    plt.figure()
    shap.summary_plot(
        shap_values,
        X_sample,
        show=False,
        plot_type="bar"
    )
    plt.savefig(
        os.path.join(output_dir, "shap_bar.png"),
        dpi=150,
        bbox_inches="tight"
    )
    plt.close()

    base_values = shap_explanation.base_values
    if np.array(base_values).ndim == 2:
        base_values = np.array(base_values)[:, 1]

    for i in range(min(3, len(X_sample))):
        plt.figure()
        shap.plots.waterfall(
            shap.Explanation(
                values=shap_values[i],
                base_values=base_values[i],
                data=X_sample.iloc[i].values,
                feature_names=X_sample.columns.tolist(),
            ),
            show=False
        )
        plt.savefig(
            os.path.join(output_dir, f"local_explanation_{i+1}.png"),
            dpi=150,
            bbox_inches="tight"
        )
        plt.close()


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "processed", "model_table.parquet")
    output_dir = os.path.join(base_dir, "outputs", "interpretability")

    df = pd.read_parquet(data_path)
    train_df, test_df = temporal_split(df)

    model, grid_map, feature_names = train_rf(train_df)
    X_test = prepare_test_features(test_df, grid_map)

    save_feature_importance(model, feature_names, output_dir)
    save_shap_outputs(model, X_test, output_dir)

    print(f"Saved interpretability outputs to {output_dir}")


if __name__ == "__main__":
    main()