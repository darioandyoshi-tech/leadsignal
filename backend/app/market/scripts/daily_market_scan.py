#!/usr/bin/env python3
"""Daily NASDAQ-100 scan: fetch, score, and persist top picks.

Designed for 1-4 day swing holds. Run after market close via cron.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Ensure backend package imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.models import MarketSnapshot, StockPick, TradeAction
from app.market import NASDAQ100Fetcher, build_technical_features, StockScorer, StockRecommender


async def persist_snapshots(db: AsyncSession, df):
    """Upsert daily OHLCV + technical snapshots."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    for _, row in df.iterrows():
        date = pd.to_datetime(row["date"]).to_pydatetime().replace(tzinfo=None)
        stmt = (
            sqlite_insert(MarketSnapshot)
            .values(
                symbol=row["symbol"],
                date=date,
                open=float(row["open"]) if pd.notna(row["open"]) else None,
                high=float(row["high"]) if pd.notna(row["high"]) else None,
                low=float(row["low"]) if pd.notna(row["low"]) else None,
                close=float(row["close"]) if pd.notna(row["close"]) else None,
                volume=float(row["volume"]) if pd.notna(row["volume"]) else None,
                rsi_14=float(row["rsi_14"]) if pd.notna(row.get("rsi_14")) else None,
                macd=float(row["macd"]) if pd.notna(row.get("macd")) else None,
                macd_signal=float(row["macd_signal"]) if pd.notna(row.get("macd_signal")) else None,
                bb_upper=float(row["bb_upper"]) if pd.notna(row.get("bb_upper")) else None,
                bb_lower=float(row["bb_lower"]) if pd.notna(row.get("bb_lower")) else None,
                atr_14=float(row["atr_14"]) if pd.notna(row.get("atr_14")) else None,
                sma_20=float(row["sma_20"]) if pd.notna(row.get("sma_20")) else None,
                sma_50=float(row["sma_50"]) if pd.notna(row.get("sma_50")) else None,
            )
            .on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_={
                    "open": float(row["open"]) if pd.notna(row["open"]) else None,
                    "high": float(row["high"]) if pd.notna(row["high"]) else None,
                    "low": float(row["low"]) if pd.notna(row["low"]) else None,
                    "close": float(row["close"]) if pd.notna(row["close"]) else None,
                    "volume": float(row["volume"]) if pd.notna(row["volume"]) else None,
                },
            )
        )
        await db.execute(stmt)


async def main():
    print(f"[{datetime.now(timezone.utc)}] Starting daily S&P 500 scan...")

    fetcher = NASDAQ100Fetcher(lookback_days=120, universe="sp500")
    raw = fetcher.fetch()
    if raw.empty:
        print("No data fetched. Exiting.")
        return

    features_df = build_technical_features(raw)
    print(f"Fetched {len(features_df)} rows for {features_df['symbol'].nunique()} symbols")

    scorer = StockScorer()
    scores = scorer.score_all(features_df)
    print(f"Scored {len(scores)} symbols")

    # ── Vendor incident alpha filter (TimesFM-enhanced) ──────────────────
    # Check PulseWatch for active vendor incidents, then use TimesFM to
    # forecast which affected stocks will actually decline vs. recover.
    from app.market.vendor_alpha import VendorIncidentSignalGenerator, Severity
    from app.market.vendor_timesfm import forecast_vendor_impact, classify_signal

    try:
        import httpx
        r = httpx.get("https://api.pulsewatch.us/v1/incidents/open", timeout=15)
        incidents = r.json().get("incidents", []) if r.status_code == 200 else []
    except Exception:
        incidents = []

    avoid_symbols = set()
    strong_avoid_symbols = set()
    recovery_candidates = []

    if incidents:
        gen = VendorIncidentSignalGenerator()
        signals = gen.generate_signals(incidents, min_severity=Severity.MAJOR)

        if signals:
            print(f"[VENDOR ALPHA] {len(signals)} vendor incident signals generated")

            for signal in signals:
                affected = signal.affected_symbols
                vendor_name = signal.vendor_name
                print(f"[VENDOR ALPHA] {vendor_name}: forecasting {len(affected)} affected symbols...")

                forecasts = await forecast_vendor_impact(affected, vendor_name, signal.incident_title)

                for fc in forecasts:
                    classification = classify_signal(fc)
                    sym = fc["symbol"]
                    ret = fc["expected_return_pct"]
                    downside = fc.get("downside_pct")

                    if classification == "STRONG_AVOID":
                        strong_avoid_symbols.add(sym)
                        avoid_symbols.add(sym)
                        print(f"  {sym}: STRONG_AVOID (expected {ret:+.2f}%, downside {downside}%)")
                    elif classification == "AVOID":
                        avoid_symbols.add(sym)
                        print(f"  {sym}: AVOID (expected {ret:+.2f}%)")
                    elif classification == "RECOVERY":
                        recovery_candidates.append({"symbol": sym, "expected_return": ret, "vendor": vendor_name})
                        print(f"  {sym}: RECOVERY (expected {ret:+.2f}%) - incident priced in")

            # For symbols where TimesFM failed, fall back to AVOID
            for signal in signals:
                for sym in signal.affected_symbols:
                    if sym not in avoid_symbols and sym not in recovery_candidates:
                        avoid_symbols.add(sym)

    # Filter scores: remove strong avoid + avoid, keep neutral + recovery
    if avoid_symbols:
        before = len(scores)
        scores = [s for s in scores if s.symbol not in avoid_symbols]
        removed = before - len(scores)
        print(f"[VENDOR ALPHA] Filtered {removed} symbols ({len(strong_avoid_symbols)} strong avoid + {len(avoid_symbols - strong_avoid_symbols)} avoid)")
        print(f"[VENDOR ALPHA] {len(scores)} symbols remaining, {len(recovery_candidates)} recovery candidates")
    # ──────────────────────────────────────────────────────────────────


    recommender = StockRecommender(max_hold_days=4)
    top_picks = recommender.rank(scores, top_n=15)
    print(f"Top picks: {[(p.symbol, p.action, p.score) for p in top_picks[:5]]}")

    async with async_session_maker() as db:
        # Mark all previously active picks inactive so today replaces yesterday.
        result = await db.execute(
            select(StockPick).where(StockPick.is_active == True)
        )
        for old in result.scalars():
            old.is_active = False

        # Persist snapshots
        await persist_snapshots(db, features_df)

        # Persist picks
        for pick in top_picks:
            db.add(
                StockPick(
                    run_date=datetime.now(timezone.utc),
                    symbol=pick.symbol,
                    score=pick.score,
                    action=TradeAction(pick.action),
                    confidence=pick.confidence,
                    forecast_return_4d=pick.forecast_return_4d,
                    predicted_close_4d=pick.predicted_close_4d,
                    stop_loss=pick.stop_loss,
                    take_profit=pick.take_profit,
                    max_hold_days=pick.max_hold_days,
                    reasoning=pick.reasoning,
                    features={
                        "forecast_return_4d": pick.forecast_return_4d,
                        "stop_loss": pick.stop_loss,
                        "take_profit": pick.take_profit,
                    },
                )
            )

        await db.commit()

    print(f"[{datetime.now(timezone.utc)}] Done. Persisted {len(top_picks)} top picks.")

    # Sync actual Alpaca fills before making new trading decisions
    settings = get_settings()
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        print("[SCAN] Syncing Alpaca fills before trading...")
        from app.market.scripts.sync_alpaca_fills import main as sync_fills
        await sync_fills()
        print("[SCAN] Alpaca sync complete.")

    # Optionally execute paper trades with Alpaca
    if settings.alpaca_auto_trade:
        print("[SCAN] Auto-trade enabled; handing off to paper trade execution.")
        from app.market.scripts.execute_paper_trades import main as execute_trades
        await execute_trades()
        print("[SCAN] Paper trade execution complete.")


if __name__ == "__main__":
    asyncio.run(main())
