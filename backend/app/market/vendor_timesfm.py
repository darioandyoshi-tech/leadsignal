#!/usr/bin/env python3
"""TimesFM vendor incident impact forecaster.

When a vendor incident occurs, fetches recent price history for affected
S&P 500 stocks and uses TimesFM to forecast the 4-day impact trajectory.

This adds a forecast confidence layer: if TimesFM predicts continued decline,
the AVOID signal is strengthened. If TimesFM predicts quick recovery, the
signal is weakened (incident already priced in).
"""

import asyncio
import httpx
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


TIMESFM_URL = "http://127.0.0.1:8001"


async def fetch_price_history(symbol: str, days: int = 60) -> List[float]:
    """Fetch recent daily close prices for a symbol."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start, end=end + timedelta(days=1), auto_adjust=True)
        if hist.empty:
            return []
        return [float(x) for x in hist["Close"].dropna().tolist()]
    except Exception:
        return []


async def forecast_symbol(symbol: str, prices: List[float], horizon: int = 8) -> Optional[Dict]:
    """Get TimesFM forecast for a symbol given recent prices."""
    if len(prices) < 10:
        return None

    # Load API key from .env.timesfm
    import os
    from pathlib import Path
    key_file = Path(__file__).resolve().parents[2] / ".env.timesfm"
    api_key = ""
    if key_file.exists():
        api_key = key_file.read_text().strip().split("=", 1)[1].strip().strip("'\"")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    payload = {
        "series": prices[-128:],  # TimesFM max context
        "horizon": horizon,  # 8 steps = 4 trading days
        "return_quantiles": True,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{TIMESFM_URL}/forecast", json=payload, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None

    point_forecast = data.get("point", data.get("point_forecast", data.get("median", [])))
    quantiles_raw = data.get("quantiles", [])  # list[step][quantile_index]

    if not point_forecast:
        return None

    current_price = prices[-1]

    # Calculate expected return over forecast horizon
    forecast_end = float(point_forecast[-1])
    expected_return = (forecast_end / current_price - 1) * 100

    # Calculate downside risk (10th percentile = index 1 of quantile list)
    downside = None
    if quantiles_raw and len(quantiles_raw) == len(point_forecast):
        # quantiles_raw[step] = [q0, q1, ..., q9] - q1 is ~10th percentile
        if len(quantiles_raw[-1]) > 1:
            downside_end = float(quantiles_raw[-1][1])
            downside = (downside_end / current_price - 1) * 100

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "forecast_end": round(forecast_end, 2),
        "expected_return_pct": round(expected_return, 2),
        "downside_pct": round(downside, 2) if downside is not None else None,
        "horizon_steps": len(point_forecast),
        "point_forecast": [round(x, 2) for x in point_forecast],
    }


async def forecast_vendor_impact(
    affected_symbols: List[str],
    vendor_name: str,
    incident_title: str,
) -> List[Dict]:
    """Forecast price impact for all stocks affected by a vendor incident.

    Returns list of forecasts sorted by expected return (worst first).
    """
    print(f"[TIMESFM] Forecasting impact for {vendor_name}: {len(affected_symbols)} symbols")
    results = []

    for symbol in affected_symbols:
        prices = await fetch_price_history(symbol)
        if len(prices) < 10:
            print(f"  {symbol}: insufficient price history ({len(prices)} points)")
            continue

        forecast = await forecast_symbol(symbol, prices)
        if forecast:
            forecast["vendor"] = vendor_name
            forecast["incident"] = incident_title
            results.append(forecast)
            direction = "↓" if forecast["expected_return_pct"] < 0 else "↑"
            print(f"  {symbol}: {direction} {forecast['expected_return_pct']:+.2f}% (downside: {forecast['downside_pct']}%)")
        else:
            print(f"  {symbol}: forecast failed")

    # Sort worst first
    results.sort(key=lambda x: x["expected_return_pct"])
    return results


def classify_signal(forecast: Dict) -> str:
    """Classify the signal strength based on TimesFM forecast.

    STRONG_AVOID: forecast shows >2% decline over horizon
    AVOID: forecast shows 0-2% decline
    NEUTRAL: forecast shows 0-1% gain (incident may be priced in)
    RECOVERY: forecast shows >1% gain (buy opportunity post-incident)
    """
    ret = forecast["expected_return_pct"]
    downside = forecast.get("downside_pct")

    if ret < -2.0:
        return "STRONG_AVOID"
    elif ret < 0:
        return "AVOID"
    elif ret < 1.0:
        return "NEUTRAL"
    else:
        return "RECOVERY"


async def enhance_vendor_signals(signals: List[Dict]) -> List[Dict]:
    """Enhance vendor incident signals with TimesFM forecasts.

    Takes vendor_alpha signals and adds TimesFM forecast data to each
    affected symbol. Returns enhanced signals with forecast classifications.
    """
    enhanced = []

    for signal in signals:
        affected = signal.get("affected_symbols", [])
        vendor_name = signal.get("vendor_name", "Unknown")
        incident_title = signal.get("incident_title", "")

        # Only forecast for major/critical incidents
        if signal.get("incident_severity") not in ("major", "critical"):
            enhanced.append(signal)
            continue

        forecasts = await forecast_vendor_impact(affected, vendor_name, incident_title)

        # Build forecast lookup
        fc_by_symbol = {f["symbol"]: f for f in forecasts}

        # Enhance affected_companies with forecast data
        enhanced_companies = []
        strong_avoid = []
        avoid = []
        neutral = []
        recovery = []

        for sym in affected:
            fc = fc_by_symbol.get(sym)
            if fc:
                classification = classify_signal(fc)
                fc_entry = {
                    "symbol": sym,
                    "classification": classification,
                    "expected_return_pct": fc["expected_return_pct"],
                    "downside_pct": fc.get("downside_pct"),
                    "current_price": fc["current_price"],
                    "forecast_end": fc["forecast_end"],
                }
                enhanced_companies.append(fc_entry)

                if classification == "STRONG_AVOID":
                    strong_avoid.append(sym)
                elif classification == "AVOID":
                    avoid.append(sym)
                elif classification == "NEUTRAL":
                    neutral.append(sym)
                else:
                    recovery.append(sym)
            else:
                # No forecast available, keep as AVOID (default)
                enhanced_companies.append({"symbol": sym, "classification": "AVOID"})
                avoid.append(sym)

        enhanced_signal = signal.copy()
        enhanced_signal["timesfm_forecasts"] = enhanced_companies
        enhanced_signal["strong_avoid"] = strong_avoid
        enhanced_signal["avoid"] = avoid
        enhanced_signal["neutral"] = neutral
        enhanced_signal["recovery"] = recovery
        enhanced_signal["forecast_summary"] = (
            f"TimesFM: {len(strong_avoid)} strong avoid, {len(avoid)} avoid, "
            f"{len(neutral)} neutral, {len(recovery)} recovery"
        )
        enhanced.append(enhanced_signal)

    return enhanced


if __name__ == "__main__":
    # Quick test with a few symbols
    async def test():
        symbols = ["CRM", "WDAY", "ZM", "NFLX"]
        print("Testing TimesFM vendor impact forecast...\n")
        results = await forecast_vendor_impact(symbols, "Cloudflare", "Test incident")
        print(f"\nResults: {len(results)} forecasts")
        for r in results:
            classification = classify_signal(r)
            print(f"  {r['symbol']}: {classification} — expected {r['expected_return_pct']:+.2f}%")

    asyncio.run(test())