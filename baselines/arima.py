import warnings
import numpy as np
import pandas as pd
import yaml
import os
from statsmodels.tools.sm_exceptions import ConvergenceWarning

warnings.simplefilter('ignore', ConvergenceWarning)
warnings.filterwarnings("ignore")

def select_arima_cells(train_df, min_nonzero_days, max_cells):
    train_df = train_df.copy()
    train_df["has_fire"] = (train_df["incident_count"] > 0).astype(int)
    
    cell_activity = (
        train_df.groupby("grid_id")
        .agg(
            nonzero_days=("has_fire", "sum"),
            total_incidents=("incident_count", "sum"),
        )
        .reset_index()
    )
    eligible = cell_activity[
        cell_activity["nonzero_days"] >= min_nonzero_days
    ].sort_values("total_incidents", ascending=False)

    selected = eligible.head(max_cells)["grid_id"].tolist()
    return selected


def fit_single_arima(series, forecast_steps, order_p, order_d, order_q):
    from statsmodels.tsa.arima.model import ARIMA

    best_aic = np.inf
    best_result = None

    for p in order_p:
        for d in order_d:
            for q in order_q:
                if p == 0 and q == 0:
                    continue
                
                model = ARIMA(series, order=(p, d, q))
                result = model.fit()
                if result.aic < best_aic:
                    best_aic = result.aic
                    best_result = result

    if best_result is not None:
        forecast = best_result.forecast(steps=forecast_steps)
    else:
        model = ARIMA(series, order=(1, 0, 1))
        best_result = model.fit()
        forecast = best_result.forecast(steps=forecast_steps)
        
    return np.maximum(forecast.values, 0)


def train_and_predict_arima(train_df, test_df, config):
    random_seed = config["random_seed"]
    arima = config["arima"]
    min_nonzero_days = arima["min_nonzero_days"]
    max_cells = arima["max_cells"]
    order_p = arima["order_p"]
    order_d = arima["order_d"]
    order_q = arima["order_q"]

    np.random.seed(random_seed)
    selected_cells = select_arima_cells(train_df, min_nonzero_days, max_cells)

    test_dates = sorted(test_df["date"].unique())
    n_forecast = len(test_dates)

    n_train_days = len(train_df["date"].unique())
    cell_hist_rate = (
        train_df.groupby("grid_id")["incident_count"].sum() / n_train_days
    ).to_dict()

    forecasts = {}

    for i, cell_id in enumerate(selected_cells):
        cell_train = (
            train_df[train_df["grid_id"] == cell_id]
            .sort_values("date")
            .set_index("date")["incident_count"]
        )

        forecast_values = fit_single_arima(cell_train, n_forecast, order_p, order_d, order_q)
        forecasts[cell_id] = dict(zip(test_dates, forecast_values))

    test_df = test_df.copy()

    def get_arima_forecast(row):
        cell = row["grid_id"]
        d = row["date"]
        if cell in forecasts:
            return forecasts[cell].get(d, 0)
        return cell_hist_rate.get(cell, 0)

    test_df["arima_forecast"] = test_df.apply(get_arima_forecast, axis=1)

    fmax = test_df["arima_forecast"].max()
    test_df["arima_prob"] = test_df["arima_forecast"] / (fmax + 1e-12)
    test_df["arima_pred"] = (test_df["arima_forecast"] >= 0.1).astype(int)

    return test_df
