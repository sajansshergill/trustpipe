"""Statistical anomaly detection on trip volumes and fares.

Two complementary detectors:
  * ARIMA baseline for daily trip counts — flags days whose actual volume falls
    outside a forecast confidence band (catches silent volume drops a schema
    check would miss).
  * Isolation Forest over per-zone-hour fare features — flags outlier segments.

Both return structured findings the scorecard consumes. Thresholds are tuned on
historical TLC distributions; recalibration is documented in docs/gaps.md.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.arima.model import ARIMA

log = logging.getLogger(__name__)


@dataclass
class Finding:
    detector: str
    entity: str
    metric: str
    observed: float
    expected: float | None
    severity: str  # "warn" | "critical"


def volume_anomalies(daily_counts: pd.Series, z_critical: float = 3.0) -> list[Finding]:
    """ARIMA(1,1,1) one-step forecasts; residual z-scores flag anomalies."""
    if len(daily_counts) < 30:
        log.warning("Not enough history for ARIMA (need >=30 days)")
        return []

    model = ARIMA(daily_counts.astype(float), order=(1, 1, 1)).fit()
    resid = model.resid
    sigma = resid.std(ddof=1) or 1.0
    findings: list[Finding] = []
    for day, value in daily_counts.items():
        pred = value - resid.get(day, 0.0)
        z = abs(resid.get(day, 0.0)) / sigma
        if z >= z_critical:
            findings.append(
                Finding(
                    detector="arima_volume",
                    entity=str(day),
                    metric="daily_trip_count",
                    observed=float(value),
                    expected=float(pred),
                    severity="critical" if z >= z_critical + 1 else "warn",
                )
            )
    return findings


def fare_outliers(features: pd.DataFrame, contamination: float = 0.01) -> list[Finding]:
    """Isolation Forest over [avg_fare, avg_distance, trip_count] per zone-hour."""
    needed = {"zone_id", "avg_fare", "avg_distance", "trip_count"}
    if not needed.issubset(features.columns) or features.empty:
        return []

    X = features[["avg_fare", "avg_distance", "trip_count"]].fillna(0).values
    iso = IsolationForest(contamination=contamination, random_state=42)
    labels = iso.fit_predict(X)
    scores = iso.score_samples(X)

    findings: list[Finding] = []
    for idx, (label, score) in enumerate(zip(labels, scores)):
        if label == -1:  # outlier
            row = features.iloc[idx]
            findings.append(
                Finding(
                    detector="iforest_fare",
                    entity=f"zone_{int(row['zone_id'])}",
                    metric="avg_fare",
                    observed=float(row["avg_fare"]),
                    expected=None,
                    severity="critical" if score < np.percentile(scores, 1) else "warn",
                )
            )
    return findings