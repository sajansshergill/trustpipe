from __future__ import annotations

import pandas as pd

from quality.anomaly.detectors import fare_outliers, volume_anomalies


def test_volume_anomalies_requires_history() -> None:
    counts = pd.Series([100, 101, 99], index=pd.date_range("2024-01-01", periods=3))

    assert volume_anomalies(counts) == []


def test_fare_outliers_returns_structured_findings() -> None:
    features = pd.DataFrame(
        {
            "zone_id": list(range(1, 21)) + [99],
            "avg_fare": [20.0] * 20 + [500.0],
            "avg_distance": [3.0] * 20 + [0.5],
            "trip_count": [100] * 20 + [1],
        }
    )

    findings = fare_outliers(features, contamination=0.05)

    assert len(findings) == 1
    assert findings[0].detector == "iforest_fare"
    assert findings[0].entity == "zone_99"
    assert findings[0].metric == "avg_fare"
    assert findings[0].observed == 500.0


def test_fare_outliers_ignores_missing_columns() -> None:
    features = pd.DataFrame({"zone_id": [1], "avg_fare": [20.0]})

    assert fare_outliers(features) == []
