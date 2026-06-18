"""Feature selection pipeline for LeadSignal opportunities.

Adapts the gradient-boosting feature selection approach from the multivariate
stock forecasting project (Geoffrey-42/n8zXS7BMxRChdvtm) to local-market signals.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Signal, Company


def build_signal_features(
    signals: List[Signal],
    bucket_days: int = 1,
    lookback_days: int = 90,
) -> pd.DataFrame:
    """Build a multivariate feature matrix from raw signals.

    Rows = days, columns = per-signal-type counts + severity stats.
    """
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback_days)
    date_range = pd.date_range(start=start, end=end, freq="D")

    # Aggregate counts and severity by date bucket
    counts: Dict[str, Dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    severity_sum: Dict[str, Dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    severity_max: Dict[str, Dict[datetime, float]] = defaultdict(lambda: defaultdict(float))

    for s in signals:
        if s.detected_at is None:
            continue
        bucket = s.detected_at.date()
        if bucket_days > 1:
            bucket = bucket - timedelta(days=bucket.day % bucket_days)
        st = s.signal_type.value
        counts[st][bucket] += 1
        severity_sum[st][bucket] += s.severity or 1
        severity_max[st][bucket] = max(severity_max[st][bucket], s.severity or 1)

    records = []
    for d in date_range:
        row = {"date": d}
        for st in counts:
            c = counts[st].get(d.date(), 0)
            row[f"{st}_count"] = c
            row[f"{st}_avg_severity"] = severity_sum[st].get(d.date(), 0) / max(1, c)
            row[f"{st}_max_severity"] = severity_max[st].get(d.date(), 0)
        records.append(row)

    df = pd.DataFrame(records).set_index("date")
    df = df.fillna(0)
    return df


def build_target(df: pd.DataFrame, horizon: int = 7) -> pd.Series:
    """Binary target: will total signal volume increase over the next horizon?"""
    total = df.filter(like="_count").sum(axis=1)
    future = total.shift(-horizon)
    target = (future > total).astype(int)
    return target


class SignalFeatureSelector:
    """Select the most predictive signal features using GradientBoosting."""

    def __init__(self, importance_threshold: float = 0.95):
        self.importance_threshold = importance_threshold
        self.selected_features: List[str] = []
        self.feature_importances: Dict[str, float] = {}
        self.scaler = StandardScaler()

    def fit(self, df: pd.DataFrame, horizon: int = 7) -> Tuple[List[str], Dict[str, float]]:
        """Fit feature selector and return selected feature names + importances."""
        target = build_target(df, horizon=horizon)
        # Drop rows with unknown target
        valid = target.notna()
        X = df[valid]
        y = target[valid]

        if len(X) < 20:
            # Not enough data; fall back to all count features
            self.selected_features = [c for c in df.columns if c.endswith("_count")]
            return self.selected_features, {}

        X_scaled = self.scaler.fit_transform(X)
        regressor = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=3,
            random_state=42,
        )
        regressor.fit(X_scaled, y)

        importances = pd.Series(regressor.feature_importances_, index=X.columns)
        importances = importances.sort_values(ascending=False)
        self.feature_importances = importances.to_dict()

        # Cumulative importance selection
        cumsum = importances.cumsum()
        n_features = (cumsum >= self.importance_threshold).idxmax()
        n_idx = importances.index.get_loc(n_features)
        self.selected_features = importances.index[: n_idx + 1].tolist()
        return self.selected_features, self.feature_importances

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return dataframe with only selected features."""
        if not self.selected_features:
            return df
        return df[self.selected_features]
