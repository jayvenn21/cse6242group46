import os
import sys
import time
import pandas as pd
import geopandas as gpd
import yaml

script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(script_dir, "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from hotspot import train_hotspot, predict_hotspot
from arima import train_and_predict_arima
from rf import train_random_forest, predict_random_forest
from eval import run_evaluation

output_dir = os.path.join(script_dir, config["paths"]["output_dir"])
plot_dir = os.path.join(script_dir, config["paths"]["plot_dir"])


def load_data():
    model_table_path = os.path.join(script_dir, config["paths"]["model_table"])
    grid_cells_path = os.path.join(script_dir, config["paths"]["grid_cells"])

    df = pd.read_parquet(model_table_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    grid_gdf = gpd.read_file(grid_cells_path)

    unique_dates = df["date"].unique()
    train_frac = config["temporal"]["train_fraction"]
    split_idx = int(len(unique_dates) * train_frac)
    
    train_dates = unique_dates[:split_idx]
    test_dates = unique_dates[split_idx:]
    
    train = df[df["date"].isin(train_dates)].copy()
    test = df[df["date"].isin(test_dates)].copy()

    return train, test, grid_gdf


def main():
    t0 = time.time()

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)

    print("Step 1/5: Loading Data")
    train, test, grid_gdf = load_data()
    print(f"Train samples: {len(train):,}, Test samples: {len(test):,}")

    print("Step 2/5: Historical Hotspot")
    cell_scores, threshold = train_hotspot(train, grid_gdf, config)
    test = predict_hotspot(test, cell_scores, threshold)

    print("Step 3/5: ARIMA")
    test = train_and_predict_arima(train, test, config)

    print("Step 4/5: Random Forest")
    rf_model, rf_grid_map, rf_features, rf_threshold = train_random_forest(train, config)
    test = predict_random_forest(test, rf_model, rf_grid_map, rf_threshold)

    print("Step 5/5: Evaluation")
    results_df = run_evaluation(test, config, rf_model=rf_model, rf_feature_names=rf_features)

    elapsed = time.time() - t0
    print(f"Pipeline complete in {elapsed:.1f}s. Outputs in {output_dir}/")

    return results_df


if __name__ == "__main__":
    main()
