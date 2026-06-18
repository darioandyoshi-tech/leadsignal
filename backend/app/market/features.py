"""Technical feature engineering for NASDAQ-100 snapshots."""

from __future__ import annotations

import pandas as pd
import numpy as np


def build_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical indicators per symbol.

    Expects columns: symbol, date, open, high, low, close, volume.
    """
    if df.empty:
        return df

    import pandas_ta as ta

    rows = []
    for symbol, group in df.sort_values("date").groupby("symbol"):
        group = group.copy()
        group["rsi_14"] = ta.rsi(group["close"], length=14)
        macd = ta.macd(group["close"], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            macd_cols = macd.columns.tolist()
            group["macd"] = macd[macd_cols[0]]
            group["macd_signal"] = macd[macd_cols[2]] if len(macd_cols) > 2 else macd[macd_cols[1]]
        bb = ta.bbands(group["close"], length=20, std=2)
        if bb is not None and not bb.empty:
            bb_cols = bb.columns.tolist()
            # pandas_ta returns middle, upper, lower order varies by version
            upper_col = next((c for c in bb_cols if "BBU" in c), None)
            lower_col = next((c for c in bb_cols if "BBL" in c), None)
            if upper_col:
                group["bb_upper"] = bb[upper_col]
            if lower_col:
                group["bb_lower"] = bb[lower_col]
        group["atr_14"] = ta.atr(group["high"], group["low"], group["close"], length=14)
        group["sma_20"] = ta.sma(group["close"], length=20)
        group["sma_50"] = ta.sma(group["close"], length=50)

        # Momentum features
        group["return_1d"] = group["close"].pct_change(1)
        group["return_4d"] = group["close"].pct_change(4)
        group["volatility_20d"] = group["return_1d"].rolling(20).std() * np.sqrt(252)
        group["volume_sma_20"] = group["volume"].rolling(20).mean()
        group["volume_ratio"] = group["volume"] / group["volume_sma_20"]

        # Position within Bollinger
        group["bb_position"] = (group["close"] - group["bb_lower"]) / (group["bb_upper"] - group["bb_lower"])

        rows.append(group)

    return pd.concat(rows, ignore_index=True)
