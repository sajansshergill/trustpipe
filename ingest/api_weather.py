"""API ingest: NOAA hourly weather -> RAW.WEATHER (zone-hour grain).

NOAA exposes a single central-park-ish station for NYC; we fan the observation
out across all taxi zones for the join. In a real deployment you'd map stations
to zones spatially — that shortcut is documented in docs/gaps.md.

Usage:
    python -m ingest.api_weather --date 2024-01-15
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime

import pandas as pd
import requests

from ingest.contracts.validator import validate
from ingest.warehouse import load_dataframe

log = logging.getLogger(__name__)

NOAA_ENDPOINT = "https://api.weather.gov/stations/{station}/observations"
NYC_STATION = "KNYC"
N_ZONES = 265


def extract(date: str, station: str = NYC_STATION) -> list[dict]:
    start = f"{date}T00:00:00Z"
    end = f"{date}T23:59:59Z"
    url = NOAA_ENDPOINT.format(station=station)
    resp = requests.get(
        url,
        params={"start": start, "end": end},
        headers={"User-Agent": "trustpipe (portfolio project)"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("features", [])


def transform(features: list[dict]) -> pd.DataFrame:
    rows = []
    for f in features:
        p = f.get("properties", {})
        observed = p.get("timestamp")
        temp = (p.get("temperature") or {}).get("value")
        precip = (p.get("precipitationLastHour") or {}).get("value")
        wind = (p.get("windSpeed") or {}).get("value")
        for zone_id in range(1, N_ZONES + 1):
            rows.append(
                {
                    "zone_id": zone_id,
                    "observed_at": observed,
                    "temp_c": temp,
                    "precip_mm": precip,
                    "wind_kph": wind,
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["observed_at"] = pd.to_datetime(df["observed_at"], errors="coerce")
    df["zone_id"] = df["zone_id"].astype("Int64")
    return df


def run(date: str) -> int:
    df = transform(extract(date))
    if df.empty:
        log.warning("No weather observations returned for %s", date)
        return 0
    validate(df, "weather").raise_if_failed()
    return load_dataframe(df, "WEATHER")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = ap.parse_args()
    run(args.date)


if __name__ == "__main__":
    main()