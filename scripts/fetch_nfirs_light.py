#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/NFIRS_PDR_Light_Service_2024/FeatureServer/0/query"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a filtered 2024 NFIRS Light GeoJSON extract.")
    parser.add_argument("--state-id", required=True, help="Two-letter incident state code, e.g. GA.")
    parser.add_argument("--city", required=True, help="Incident city name, e.g. Atlanta.")
    parser.add_argument("--out", required=True, help="Output GeoJSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    where = (
        f"STATE_ID = '{args.state_id}' "
        f"AND CITY = '{args.city}' "
        "AND AID IN ('1','2','N') "
        "AND INC_TYPE >= '100' AND INC_TYPE < '200'"
    )
    params = {
        "f": "geojson",
        "where": where,
        "outFields": ",".join(
            [
                "INCIDENT_KEY",
                "STATE",
                "FDID",
                "FD_NAME",
                "INC_DATE",
                "INC_NO",
                "EXP_NO",
                "CITY",
                "STATE_ID",
                "ZIP5",
                "INC_TYPE",
                "AID",
                "ALARM",
                "ARRIVAL",
                "LU_CLEAR",
                "PROP_USE",
                "FIRE_CAUSE",
                "Status",
                "Score",
                "Match_Addr",
                "Addr_type",
            ]
        ),
        "returnGeometry": "true",
        "orderByFields": "OBJECTID ASC",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    if data.get("type") != "FeatureCollection":
        raise RuntimeError(f"Unexpected response: {data}")

    out_path.write_text(json.dumps(data), encoding="utf-8")
    print(f"Fetched {len(data.get('features', [])):,} NFIRS features to {out_path}")


if __name__ == "__main__":
    main()
