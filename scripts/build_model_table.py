#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
from pathlib import Path

import geopandas as gpd
import holidays
import numpy as np
import pandas as pd
from shapely.geometry import box


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a minimal cell-day fire incident model table."
    )
    parser.add_argument("--incidents", required=True, help="Path to raw incident file.")
    parser.add_argument("--weather", required=True, help="Path to daily weather file.")
    parser.add_argument("--outdir", default="data/processed", help="Output directory.")
    parser.add_argument("--grid-size-m", type=float, default=1000.0, help="Grid size in meters.")
    parser.add_argument("--horizon-days", type=int, default=1, help="Prediction horizon in days.")
    parser.add_argument("--country", default="US", help="Holiday calendar country code.")
    parser.add_argument("--date-col", help="Incident timestamp/date column.")
    parser.add_argument("--lat-col", help="Latitude column.")
    parser.add_argument("--lon-col", help="Longitude column.")
    parser.add_argument("--incident-type-col", help="Incident type column.")
    parser.add_argument("--weather-date-col", help="Weather date column.")
    parser.add_argument("--temp-col", help="Weather temperature column.")
    parser.add_argument("--humidity-col", help="Weather humidity column.")
    parser.add_argument("--precip-col", help="Weather precipitation column.")
    parser.add_argument("--wind-col", help="Weather wind column.")
    parser.add_argument(
        "--filter-field",
        action="append",
        default=[],
        help="Incident field to filter on. Repeat with --filter-value.",
    )
    parser.add_argument(
        "--filter-value",
        action="append",
        default=[],
        help="Incident filter value. Repeat with --filter-field.",
    )
    return parser.parse_args()


def read_table(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, low_memory=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".gpkg", ".geojson", ".json", ".shp"}:
        return gpd.read_file(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def normalize_name(name: str) -> str:
    return "".join(ch.lower() for ch in str(name) if ch.isalnum())


def infer_column(columns, candidates, contains=()):
    normalized = {col: normalize_name(col) for col in columns}
    for candidate in candidates:
        target = normalize_name(candidate)
        for col, norm in normalized.items():
            if norm == target:
                return col
    for needle in contains:
        needle_norm = normalize_name(needle)
        for col, norm in normalized.items():
            if needle_norm in norm:
                return col
    return None


def print_schema(label: str, df) -> None:
    print(f"{label} columns:")
    for col in df.columns:
        print(f"  - {col}")


def apply_filters(df: pd.DataFrame, fields: list[str], values: list[str]) -> pd.DataFrame:
    if len(fields) != len(values):
        raise ValueError("--filter-field and --filter-value must be supplied the same number of times.")
    for field, value in zip(fields, values):
        if field not in df.columns:
            raise ValueError(f"Filter field not found: {field}")
        df = df[df[field].astype(str).str.strip().str.lower() == str(value).strip().lower()]
    return df


def choose_incident_columns(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, str | None]:
    columns = list(df.columns)
    chosen = {
        "date_col": args.date_col
        or infer_column(
            columns,
            candidates=[
                "incident_date",
                "inc_date",
                "incident_datetime",
                "alarm_datetime",
                "alarm_time",
                "date",
                "datetime",
                "incident_dt",
                "dispatch_date",
            ],
            contains=["incidentdate", "alarmdate", "datetime"],
        ),
        "lat_col": args.lat_col
        or infer_column(
            columns,
            candidates=["latitude", "lat", "y", "ycoord", "incident_latitude"],
            contains=["latitude", "lat"],
        ),
        "lon_col": args.lon_col
        or infer_column(
            columns,
            candidates=["longitude", "lon", "lng", "x", "xcoord", "incident_longitude"],
            contains=["longitude", "long", "lon", "lng"],
        ),
        "incident_type_col": args.incident_type_col
        or infer_column(
            columns,
            candidates=["incident_type", "inc_type", "type", "incidenttype"],
            contains=["incidenttype", "inctype", "basicmoduleactiontaken"],
        ),
        "location_fields": [
            col
            for col in columns
            if normalize_name(col)
            in {
                "city",
                "state",
                "state_id",
                "county",
                "jurisdiction",
                "zipcode",
                "zip",
                "fdid",
                "departmentid",
            }
        ],
    }
    return chosen


def choose_weather_columns(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, str]:
    columns = list(df.columns)
    chosen = {
        "date": args.weather_date_col
        or infer_column(columns, ["date", "weather_date", "observation_date"], ["date"]),
        "temperature": args.temp_col
        or infer_column(columns, ["temperature", "temp", "tavg", "tmean"], ["temp"]),
        "humidity": args.humidity_col
        or infer_column(columns, ["humidity", "relative_humidity"], ["humidity"]),
        "precipitation": args.precip_col
        or infer_column(columns, ["precipitation", "precip", "prcp", "rain"], ["precip", "prcp", "rain"]),
        "wind": args.wind_col
        or infer_column(columns, ["wind", "wind_speed", "avg_wind_speed", "awnd"], ["wind"]),
    }
    missing = [name for name, col in chosen.items() if not col]
    if missing:
        raise ValueError(f"Could not infer weather columns: {missing}")
    return chosen


def coerce_incident_coordinates(df: pd.DataFrame, lat_col: str | None, lon_col: str | None) -> pd.DataFrame:
    if lat_col and lon_col:
        df["latitude"] = pd.to_numeric(df[lat_col], errors="coerce")
        df["longitude"] = pd.to_numeric(df[lon_col], errors="coerce")
        return df
    if isinstance(df, gpd.GeoDataFrame) and df.geometry is not None:
        geo = df.to_crs(4326) if df.crs else df.set_crs(4326, allow_override=True)
        df["longitude"] = geo.geometry.x
        df["latitude"] = geo.geometry.y
        return df
    raise ValueError("Could not determine coordinates. Provide lat/lon columns or a geocoded file.")


def filter_fire_incidents(df: pd.DataFrame, incident_type_col: str | None) -> pd.DataFrame:
    if not incident_type_col:
        print("No incident type column found; keeping all incidents.")
        return df

    raw = df[incident_type_col].astype(str).str.strip()
    numeric_code = pd.to_numeric(raw.str.extract(r"(\d{3})", expand=False), errors="coerce")
    fire_mask = numeric_code.between(100, 199, inclusive="both")
    text_mask = raw.str.lower().str.contains("fire", na=False)
    filtered = df[fire_mask.fillna(False) | text_mask]
    print(f"Filtered to {len(filtered):,} fire incidents from {len(df):,} rows.")
    return filtered


def dedupe_incidents(df: pd.DataFrame) -> pd.DataFrame:
    priority_keys = [
        "state",
        "state_id",
        "fdid",
        "incident_number",
        "incidentno",
        "inc_no",
        "exposure_number",
        "exp_no",
        "date",
        "latitude",
        "longitude",
    ]
    dedupe_keys = [col for col in df.columns if normalize_name(col) in {normalize_name(k) for k in priority_keys}]
    if not dedupe_keys:
        dedupe_keys = ["date", "latitude", "longitude"]
    before = len(df)
    df = df.drop_duplicates(subset=dedupe_keys)
    print(f"Removed {before - len(df):,} duplicate rows.")
    return df


def season_from_month(month: int) -> str:
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    return "fall"


def build_grid(incidents_gdf: gpd.GeoDataFrame, grid_size_m: float) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    projected = incidents_gdf.to_crs(incidents_gdf.estimate_utm_crs())
    minx, miny, maxx, maxy = projected.total_bounds
    n_cols = max(1, math.ceil((maxx - minx) / grid_size_m))
    n_rows = max(1, math.ceil((maxy - miny) / grid_size_m))

    projected["cell_col"] = np.floor((projected.geometry.x - minx) / grid_size_m).astype(int).clip(0, n_cols - 1)
    projected["cell_row"] = np.floor((projected.geometry.y - miny) / grid_size_m).astype(int).clip(0, n_rows - 1)
    projected["grid_id"] = projected.apply(lambda row: f"r{int(row.cell_row)}_c{int(row.cell_col)}", axis=1)

    cells = []
    for row in range(n_rows):
        for col in range(n_cols):
            x0 = minx + col * grid_size_m
            y0 = miny + row * grid_size_m
            cells.append(
                {
                    "grid_id": f"r{row}_c{col}",
                    "cell_row": row,
                    "cell_col": col,
                    "geometry": box(x0, y0, x0 + grid_size_m, y0 + grid_size_m),
                }
            )
    grid = gpd.GeoDataFrame(cells, geometry="geometry", crs=projected.crs).to_crs(4326)
    return projected.to_crs(4326), grid


def build_cell_day_table(incidents: pd.DataFrame, weather: pd.DataFrame, country: str, horizon_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    date_range = pd.date_range(incidents["date"].min(), incidents["date"].max(), freq="D")
    grid_ids = sorted(incidents["grid_id"].unique())
    full_index = pd.MultiIndex.from_product([grid_ids, date_range], names=["grid_id", "date"])

    counts = (
        incidents.groupby(["grid_id", "date"])
        .size()
        .rename("incident_count")
        .reindex(full_index, fill_value=0)
        .reset_index()
    )
    counts["date"] = pd.to_datetime(counts["date"])

    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()
    cell_day = counts.merge(weather, on="date", how="left", validate="many_to_one")

    holiday_calendar = holidays.country_holidays(country)
    cell_day["day_of_week"] = cell_day["date"].dt.dayofweek
    cell_day["month"] = cell_day["date"].dt.month
    cell_day["season"] = cell_day["month"].map(season_from_month)
    cell_day["is_weekend"] = cell_day["day_of_week"].isin([5, 6]).astype(int)
    cell_day["is_holiday"] = cell_day["date"].dt.date.map(lambda d: int(d in holiday_calendar))

    cell_day = cell_day.sort_values(["grid_id", "date"]).reset_index(drop=True)
    grouped = cell_day.groupby("grid_id")["incident_count"]
    cell_day["lag_1"] = grouped.shift(1)
    cell_day["lag_3"] = grouped.shift(3)
    cell_day["lag_7"] = grouped.shift(7)
    cell_day["rolling_sum_7"] = cell_day.groupby("grid_id")["incident_count"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).sum()
    )
    cell_day["rolling_sum_14"] = cell_day.groupby("grid_id")["incident_count"].transform(
        lambda s: s.shift(1).rolling(14, min_periods=1).sum()
    )

    for feature in ["lag_1", "lag_3", "lag_7", "rolling_sum_7", "rolling_sum_14"]:
        cell_day[feature] = cell_day[feature].fillna(0)

    future_sum = sum(grouped.shift(-step) for step in range(1, horizon_days + 1))
    cell_day["target_next_interval"] = (future_sum.fillna(0) > 0).astype(int)
    cell_day["target_available"] = grouped.shift(-horizon_days).notna().astype(int)

    model_table = cell_day[cell_day["target_available"] == 1].drop(columns=["target_available"]).copy()
    return cell_day, model_table


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    incidents_path = Path(args.incidents)
    weather_path = Path(args.weather)

    incidents_raw = read_table(incidents_path)
    print_schema("Incident", incidents_raw)
    incidents_raw = apply_filters(incidents_raw, args.filter_field, args.filter_value)
    print(f"Incident rows after filters: {len(incidents_raw):,}")

    incident_cols = choose_incident_columns(incidents_raw, args)
    print("Selected incident columns:")
    for key, value in incident_cols.items():
        if key != "location_fields":
            print(f"  - {key}: {value}")
    print(f"  - location_fields: {incident_cols['location_fields']}")

    if not incident_cols["date_col"]:
        raise ValueError("Could not infer incident date column. Use --date-col.")

    incidents = incidents_raw.copy()
    incidents = coerce_incident_coordinates(incidents, incident_cols["lat_col"], incident_cols["lon_col"])
    incidents["date"] = pd.to_datetime(incidents[incident_cols["date_col"]], errors="coerce").dt.normalize()
    incidents = incidents.dropna(subset=["date", "latitude", "longitude"]).copy()
    incidents = incidents[
        incidents["latitude"].between(-90, 90) & incidents["longitude"].between(-180, 180)
    ].copy()
    incidents = filter_fire_incidents(incidents, incident_cols["incident_type_col"])
    incidents = dedupe_incidents(incidents)

    incidents_gdf = gpd.GeoDataFrame(
        incidents,
        geometry=gpd.points_from_xy(incidents["longitude"], incidents["latitude"]),
        crs="EPSG:4326",
    )
    incidents_gdf, grid = build_grid(incidents_gdf, args.grid_size_m)
    incidents_clean = pd.DataFrame(incidents_gdf.drop(columns="geometry"))

    incidents_clean.to_parquet(outdir / "incidents_clean.parquet", index=False)
    grid.to_file(outdir / "grid_cells.geojson", driver="GeoJSON")

    weather_raw = read_table(weather_path)
    print_schema("Weather", weather_raw)
    weather_cols = choose_weather_columns(weather_raw, args)
    print("Selected weather columns:")
    for key, value in weather_cols.items():
        print(f"  - {key}: {value}")

    weather = weather_raw.rename(
        columns={
            weather_cols["date"]: "date",
            weather_cols["temperature"]: "temperature",
            weather_cols["humidity"]: "humidity",
            weather_cols["precipitation"]: "precipitation",
            weather_cols["wind"]: "wind",
        }
    )[["date", "temperature", "humidity", "precipitation", "wind"]].copy()
    for feature in ["temperature", "humidity", "precipitation", "wind"]:
        weather[feature] = pd.to_numeric(weather[feature], errors="coerce")
    weather["date"] = pd.to_datetime(weather["date"], errors="coerce").dt.normalize()
    weather = weather.dropna(subset=["date"]).groupby("date", as_index=False).mean(numeric_only=True)

    cell_day, model_table = build_cell_day_table(
        incidents_clean,
        weather,
        country=args.country,
        horizon_days=args.horizon_days,
    )
    cell_day.to_parquet(outdir / "cell_day_table.parquet", index=False)
    model_table.to_parquet(outdir / "model_table.parquet", index=False)

    print(f"Wrote cleaned incidents to {outdir / 'incidents_clean.parquet'}")
    print(f"Wrote grid mapping to {outdir / 'grid_cells.geojson'}")
    print(f"Wrote cell-day table to {outdir / 'cell_day_table.parquet'}")
    print(f"Wrote model table to {outdir / 'model_table.parquet'}")


if __name__ == "__main__":
    main()
