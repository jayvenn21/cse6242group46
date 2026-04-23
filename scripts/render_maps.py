#!/usr/bin/env python3
"""
Spatial risk map rendering.
Takes grid geometry + model predictions -> choropleth overlays (HTML + PNG).
"""

import argparse
import json
import os

import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd


RISK_CMAP = LinearSegmentedColormap.from_list(
    "risk", ["#2ecc71", "#f9e652", "#e74c3c"]
)


def risk_hex(val):
    val = np.clip(val, 0.0, 1.0)
    r, g, b, _ = RISK_CMAP(val)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def grid_center(geojson):
    lats, lons = [], []
    for feat in geojson["features"]:
        for ring in feat["geometry"]["coordinates"]:
            for lon, lat in ring:
                lats.append(lat)
                lons.append(lon)
    return (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2


def per_cell_risk(results, prob_col, agg="mean"):
    return results.groupby("grid_id")[prob_col].agg(agg).to_dict()


def stamp_risk(geojson, scores):
    for feat in geojson["features"]:
        gid = feat["properties"]["grid_id"]
        feat["properties"]["risk"] = round(scores.get(gid, 0.0), 4)
    return geojson


def render_folium(geojson, center, title, zoom=11):
    m = folium.Map(location=list(center), zoom_start=zoom,
                   tiles="cartodbpositron")

    folium.GeoJson(
        geojson,
        style_function=lambda feat: {
            "fillColor": risk_hex(feat["properties"].get("risk", 0)),
            "color": "#444",
            "weight": 0.3,
            "fillOpacity": 0.6,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["grid_id", "risk"],
            aliases=["Cell", "Risk"],
        ),
    ).add_to(m)

    tag = f"""
    <div style="position:fixed; top:12px; left:55px; z-index:9999;
        background:#fff; padding:6px 14px; border-radius:5px;
        font:600 13px/1.4 sans-serif;
        box-shadow:0 1px 4px rgba(0,0,0,.25);">{title}</div>"""
    m.get_root().html.add_child(folium.Element(tag))

    return m


def render_static(geojson, outpath, title):
    fig, ax = plt.subplots(figsize=(10, 10))

    for feat in geojson["features"]:
        risk = feat["properties"].get("risk", 0)
        coords = feat["geometry"]["coordinates"][0]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        ax.fill(xs, ys, color=risk_hex(risk), alpha=0.7,
                edgecolor="#666", linewidth=0.15)

    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")

    sm = plt.cm.ScalarMappable(cmap=RISK_CMAP, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Predicted Risk")

    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)


def render_comparison(geojson, results, date, outpath):
    day = results[results["date"] == pd.Timestamp(date)]
    if day.empty:
        print(f"  [skip] no data for {date}")
        return

    actual = day.set_index("grid_id")["target_next_interval"].to_dict()
    predicted = day.set_index("grid_id")["rf_pred"].to_dict()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    for feat in geojson["features"]:
        gid = feat["properties"]["grid_id"]
        coords = feat["geometry"]["coordinates"][0]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        a_color = "#e74c3c" if actual.get(gid, 0) == 1 else "#ecf0f1"
        p_color = "#e74c3c" if predicted.get(gid, 0) == 1 else "#ecf0f1"
        ax1.fill(xs, ys, color=a_color, alpha=0.8,
                 edgecolor="#aaa", linewidth=0.12)
        ax2.fill(xs, ys, color=p_color, alpha=0.8,
                 edgecolor="#aaa", linewidth=0.12)

    date_str = pd.Timestamp(date).strftime("%b %d, %Y")
    ax1.set_title(f"Actual Fires — {date_str}", fontsize=12)
    ax2.set_title(f"RF Predicted Fires — {date_str}", fontsize=12)

    patches = [
        mpatches.Patch(color="#e74c3c", label="Fire"),
        mpatches.Patch(color="#ecf0f1", label="No Fire"),
    ]
    for ax in (ax1, ax2):
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")
        ax.legend(handles=patches, loc="lower right", fontsize=9)

    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)


def render_date_heatmap(geojson, results, date, prob_col, outpath):
    day = results[results["date"] == pd.Timestamp(date)]
    if day.empty:
        return
    scores = day.set_index("grid_id")[prob_col].to_dict()
    g = stamp_risk(_deep_copy_geojson(geojson), scores)
    date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
    render_static(g, outpath, title=f"Risk Heatmap — {date_str}")


def _deep_copy_geojson(geojson):
    return json.loads(json.dumps(geojson))


def parse_args():
    p = argparse.ArgumentParser(description="Render fire-risk prediction maps.")
    p.add_argument("--grid", default="data/processed/grid_cells.geojson",
                   help="Path to grid GeoJSON.")
    p.add_argument("--results", default="baselines/outputs/model_results.csv",
                   help="Path to model_results.csv from run_baselines.")
    p.add_argument("--outdir", default="outputs/maps",
                   help="Directory to save map outputs.")
    p.add_argument("--prob-col", default="rf_prob",
                   help="Column for risk probability overlay.")
    p.add_argument("--date", default=None,
                   help="Single date (YYYY-MM-DD) for per-day map. "
                        "Omit for aggregate over full test period.")
    p.add_argument("--sample-dates", type=int, default=3,
                   help="Number of evenly-spaced sample dates for "
                        "actual-vs-predicted comparison maps.")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    print("Loading grid and model results ...")
    with open(args.grid) as f:
        grid = json.load(f)
    results = pd.read_csv(args.results)
    results["date"] = pd.to_datetime(results["date"])

    center = grid_center(grid)
    print(f"  Grid center: {center[0]:.4f}, {center[1]:.4f}")
    print(f"  {len(grid['features'])} cells, "
          f"{results['date'].nunique()} test dates, "
          f"{len(results)} rows")

    if args.date:
        scores = results[results["date"] == pd.Timestamp(args.date)] \
                 .set_index("grid_id")[args.prob_col].to_dict()
        tag = args.date
    else:
        scores = per_cell_risk(results, args.prob_col, agg="mean")
        tag = "aggregate"

    grid_scored = stamp_risk(_deep_copy_geojson(grid), scores)

    html_out = os.path.join(args.outdir, f"risk_map_{tag}.html")
    fmap = render_folium(grid_scored, center, title=f"Fire Risk — {tag}")
    fmap.save(html_out)
    print(f"  -> {html_out}")

    png_out = os.path.join(args.outdir, f"risk_map_{tag}.png")
    render_static(grid_scored, png_out, title=f"Fire Risk — {tag}")
    print(f"  -> {png_out}")

    # sample a few dates for actual-vs-predicted comparison
    test_dates = sorted(results["date"].unique())
    n = min(args.sample_dates, len(test_dates))
    idxs = np.linspace(0, len(test_dates) - 1, n, dtype=int)
    sample = [test_dates[i] for i in idxs]

    for d in sample:
        dstr = pd.Timestamp(d).strftime("%Y-%m-%d")

        comp_path = os.path.join(args.outdir, f"actual_vs_pred_{dstr}.png")
        render_comparison(grid, results, d, comp_path)
        print(f"  -> {comp_path}")

        heat_path = os.path.join(args.outdir, f"risk_heatmap_{dstr}.png")
        render_date_heatmap(grid, results, d, args.prob_col, heat_path)
        print(f"  -> {heat_path}")

    print("Done.")


if __name__ == "__main__":
    main()
