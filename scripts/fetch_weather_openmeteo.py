#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


BASE_URL = "https://archive-api.open-meteo.com/v1/archive"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch daily citywide weather from Open-Meteo archive.")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--out", required=True, help="Output CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    params = {
        "latitude": args.latitude,
        "longitude": args.longitude,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "daily": ",".join(
            [
                "temperature_2m_mean",
                "relative_humidity_2m_mean",
                "precipitation_sum",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": "America/New_York",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    daily = data.get("daily")
    if not daily:
        raise RuntimeError(f"Unexpected weather response: {data}")

    weather = pd.DataFrame(
        {
            "date": daily["time"],
            "temperature": daily["temperature_2m_mean"],
            "humidity": daily["relative_humidity_2m_mean"],
            "precipitation": daily["precipitation_sum"],
            "wind": daily["wind_speed_10m_max"],
        }
    )
    weather.to_csv(out_path, index=False)
    print(f"Fetched {len(weather):,} weather rows to {out_path}")


if __name__ == "__main__":
    main()
