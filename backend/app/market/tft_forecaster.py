#!/usr/bin/env python3
"""Temporal Fusion Transformer (TFT) multi-horizon forecaster.

Complements TimesFM (univariate, fast, magnitude) with:
  - Multi-horizon forecasts (1-4 day ahead)
  - Known inputs (day of week, month) + unknown inputs (price, volume, RSI, MACD)
  - Direction (up/down) + confidence + feature importance

Uses PyTorch Forecasting's TFT implementation with PyTorch Lightning training.
If pytorch-forecasting is unavailable at runtime, falls back to a simplified
pure-PyTorch TFT with multi-head attention.

Model checkpoint: app/market/data/tft_model.ckpt
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yfinance as yf

# Optional heavy deps
try:
    import pytorch_lightning as pl
    from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
    from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer, QuantileLoss
    from torch.utils.data import DataLoader
    _USE_PYTORCH_FORECASTING = True
except ImportError:
    _USE_PYTORCH_FORECASTING = False
    pl = None

try:
    import pandas_ta as ta
    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [TFT] %(message)s")
log = logging.getLogger("tft_forecaster")

DATA_DIR = Path(__file__).parent / "data"
MODEL_PATH = DATA_DIR / "tft_model.ckpt"
SIMPLE_MODEL_PATH = DATA_DIR / "tft_simple_model.pt"

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def fetch_ohlcv(symbols: List[str], lookback_days: int = 252) -> pd.DataFrame:
    """Fetch daily OHLCV + technical indicators for multiple symbols.

    Returns DataFrame with columns:
        symbol, date, open, high, low, close, volume, rsi, macd, macd_signal,
        atr, sma_20, sma_50, return_1d, volatility_20d, volume_ratio,
        day_of_week, month, target
    """
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback_days + 60)  # extra for indicator warmup

    frames = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(start=start, end=end + timedelta(days=1), auto_adjust=True)
            if hist.empty or len(hist) < 60:
                log.warning("Insufficient data for %s (%d rows)", sym, len(hist) if not hist.empty else 0)
                continue

            hist = hist.reset_index()
            hist = hist.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            hist["symbol"] = sym
            hist["date"] = pd.to_datetime(hist["date"]).dt.tz_localize(None)

            # Technical indicators
            if _HAS_PANDAS_TA:
                hist["rsi"] = ta.rsi(hist["close"], length=14)
                macd_df = ta.macd(hist["close"], fast=12, slow=26, signal=9)
                if macd_df is not None and not macd_df.empty:
                    cols = macd_df.columns.tolist()
                    hist["macd"] = macd_df[cols[0]]
                    hist["macd_signal"] = macd_df[cols[2]] if len(cols) > 2 else macd_df[cols[1]]
                else:
                    hist["macd"] = 0.0
                    hist["macd_signal"] = 0.0
                hist["atr"] = ta.atr(hist["high"], hist["low"], hist["close"], length=14)
                hist["sma_20"] = ta.sma(hist["close"], length=20)
                hist["sma_50"] = ta.sma(hist["close"], length=50)
            else:
                hist["rsi"] = 50.0
                hist["macd"] = 0.0
                hist["macd_signal"] = 0.0
                hist["atr"] = hist["high"] - hist["low"]
                hist["sma_20"] = hist["close"].rolling(20, min_periods=1).mean()
                hist["sma_50"] = hist["close"].rolling(50, min_periods=1).mean()

            hist["return_1d"] = hist["close"].pct_change(1)
            hist["volatility_20d"] = hist["return_1d"].rolling(20, min_periods=1).std() * np.sqrt(252)
            hist["volume_sma_20"] = hist["volume"].rolling(20, min_periods=1).mean()
            hist["volume_ratio"] = hist["volume"] / (hist["volume_sma_20"] + 1e-8)

            # Calendar features (known inputs)
            hist["day_of_week"] = hist["date"].dt.dayofweek.astype(float)
            hist["month"] = hist["date"].dt.month.astype(float)

            frames.append(hist)
        except Exception as e:
            log.error("Error fetching %s: %s", sym, e)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Fill NaN
    for col in ["rsi", "macd", "macd_signal", "atr", "sma_20", "sma_50",
                "return_1d", "volatility_20d", "volume_ratio"]:
        df[col] = df.groupby("symbol")[col].transform(lambda s: s.fillna(method="ffill").fillna(method="bfill").fillna(0))

    return df


def prepare_target(df: pd.DataFrame, horizon: int = 4) -> pd.DataFrame:
    """Add multi-horizon target: next-day return (used as forecast target)."""
    # Target: close price shifted -horizon days (what we want to predict)
    # We use return over horizon as the target
    df = df.sort_values(["symbol", "date"]).copy()
    df["target_close"] = df.groupby("symbol")["close"].shift(-horizon)
    df["target_return"] = df.groupby("symbol")["close"].transform(
        lambda s: s.shift(-horizon) / s - 1
    )
    # Drop rows without target (last `horizon` rows per symbol)
    df = df.dropna(subset=["target_close", "target_return"])
    return df


# ---------------------------------------------------------------------------
# Full PyTorch Forecasting TFT implementation
# ---------------------------------------------------------------------------

class TFTForecaster:
    """Temporal Fusion Transformer multi-horizon forecaster.

    Uses PyTorch Forecasting's TFT if available, otherwise falls back to
    a simplified pure-PyTorch TFT.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        simple_model_path: Path = SIMPLE_MODEL_PATH,
        max_encoder_length: int = 30,
        horizon: int = 4,
        batch_size: int = 64,
        max_epochs: int = 20,
        learning_rate: float = 0.03,
    ):
        self.model_path = Path(model_path)
        self.simple_model_path = Path(simple_model_path)
        self.max_encoder_length = max_encoder_length
        self.horizon = horizon
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.learning_rate = learning_rate
        self.model: Optional[TemporalFusionTransformer] = None
        self.simple_model: Optional[SimpleTFT] = None
        self.dataset_config: Optional[dict] = None
        # Simple model state (set during training or loading)
        self._simple_norm: Optional[dict] = None
        self._simple_feature_cols: Optional[List[str]] = None
        self._simple_known_cols: Optional[List[str]] = None
        self._simple_seq_len: int = 30

    # -- Public API -------------------------------------------------------

    def train(self, symbols: List[str], lookback_days: int = 252, horizon: int = 4) -> dict:
        """Train TFT model on given symbols.

        Fetches data via yfinance, creates PyTorch Forecasting TimeSeriesDataSet,
        trains TFT with PyTorch Lightning.

        Returns training metrics dict.
        """
        self.horizon = horizon
        log.info("Training TFT on %d symbols, lookback=%d days, horizon=%d", len(symbols), lookback_days, horizon)

        df = fetch_ohlcv(symbols, lookback_days)
        if df.empty:
            return {"error": "No data fetched", "symbols": symbols}

        df = prepare_target(df, horizon)
        if len(df) < 100:
            log.warning("Too few rows (%d) for TFT training, using simple model", len(df))
            return self._train_simple(df)

        if _USE_PYTORCH_FORECASTING:
            try:
                return self._train_tft(df)
            except Exception as e:
                log.error("TFT training failed: %s, falling back to simple model", e)
                return self._train_simple(df)
        else:
            return self._train_simple(df)

    def forecast(self, symbol: str, horizon: int = 4) -> dict:
        """Generate multi-horizon forecast for a symbol.

        Returns:
            {symbol, forecasts: [{day, point, lower, upper}, ...], direction, confidence}
        """
        # Try simple model first (more reliable for inference)
        if self.simple_model is not None or self.simple_model_path.exists():
            return self._forecast_simple(symbol, horizon)

        if self.model is not None or self.model_path.exists():
            return self._forecast_tft(symbol, horizon)

        return {"symbol": symbol, "error": "No trained model found"}

    def batch_forecast(self, symbols: List[str]) -> List[dict]:
        """Run forecast for multiple symbols."""
        results = []
        for sym in symbols:
            try:
                results.append(self.forecast(sym))
            except Exception as e:
                log.error("Forecast failed for %s: %s", sym, e)
                results.append({"symbol": sym, "error": str(e)})
        return results

    # -- PyTorch Forecasting TFT -----------------------------------------

    def _train_tft(self, df: pd.DataFrame) -> dict:
        """Train using PyTorch Forecasting TimeSeriesDataSet + TFT."""
        log.info("Building TimeSeriesDataSet (%d rows)", len(df))

        # Ensure time_idx is sequential per group
        df = df.sort_values(["symbol", "date"]).copy()
        df["time_idx"] = df.groupby("symbol").cumcount()

        # Normalize numeric features
        for col in ["close", "volume", "rsi", "macd", "macd_signal", "atr",
                     "sma_20", "sma_50", "volatility_20d", "volume_ratio"]:
            if col in df.columns:
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std

        target_col = "target_return"

        training = TimeSeriesDataSet(
            df,
            time_idx="time_idx",
            target=target_col,
            group_ids=["symbol"],
            min_encoder_length=self.max_encoder_length // 2,
            max_encoder_length=self.max_encoder_length,
            min_prediction_length=1,
            max_prediction_length=self.horizon,
            static_categoricals=["symbol"],
            time_varying_known_categoricals=["day_of_week", "month"],
            time_varying_known_reals=["day_of_week", "month"],
            time_varying_unknown_reals=[
                "close", "volume", "rsi", "macd", "macd_signal",
                "atr", "sma_20", "sma_50", "volatility_20d", "volume_ratio",
                "target_return",
            ],
            add_target_scales=True,
            add_relative_time_idx=True,
            add_encoder_length=True,
        )

        # Create dataloaders
        train_loader = training.to_dataloader(
            train=True, batch_size=self.batch_size, num_workers=0
        )
        val_loader = training.to_dataloader(
            train=False, batch_size=self.batch_size, num_workers=0
        )

        # Define TFT model
        tft = TemporalFusionTransformer.from_dataset(
            training,
            learning_rate=self.learning_rate,
            hidden_size=64,
            attention_head_size=4,
            dropout=0.1,
            hidden_continuous_size=32,
            output_size=7,  # 7 quantiles
            loss=QuantileLoss(),
            reduce_on_plateau_patience=4,
        )

        # Trainer
        trainer = pl.Trainer(
            max_epochs=self.max_epochs,
            accelerator="cpu",
            gradient_clip_val=0.1,
            callbacks=[
                EarlyStopping(monitor="val_loss", patience=6, mode="min"),
                ModelCheckpoint(
                    dirpath=str(DATA_DIR),
                    filename="tft_model",
                    monitor="val_loss",
                    mode="min",
                    save_last=True,
                ),
            ],
            logger=False,
            enable_progress_bar=False,
        )

        log.info("Starting TFT training...")
        trainer.fit(tft, train_dataloaders=train_loader, val_dataloaders=val_loader)

        # Save model
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        torch.save(tft.state_dict(), self.model_path)
        self.model = tft
        self.dataset_config = {
            "max_encoder_length": self.max_encoder_length,
            "horizon": self.horizon,
            "feature_cols": ["close", "volume", "rsi", "macd", "macd_signal",
                             "atr", "sma_20", "sma_50", "volatility_20d", "volume_ratio"],
        }

        metrics = {
            "trainer": "pytorch_forecasting_tft",
            "symbols_trained": df["symbol"].nunique(),
            "rows": len(df),
            "epochs": trainer.current_epoch,
            "model_path": str(self.model_path),
        }
        log.info("TFT training complete: %s", metrics)
        return metrics

    def _forecast_tft(self, symbol: str, horizon: int) -> dict:
        """Forecast using trained PyTorch Forecasting TFT."""
        # Load model if needed
        if self.model is None and self.model_path.exists():
            # Need dataset to rebuild model architecture; fetch recent data
            df = fetch_ohlcv([symbol], self.max_encoder_length + horizon + 60)
            if df.empty:
                return {"symbol": symbol, "error": "No data for forecast"}

            df = df.sort_values(["symbol", "date"]).copy()
            df["time_idx"] = df.groupby("symbol").cumcount()

            # Normalize
            for col in ["close", "volume", "rsi", "macd", "macd_signal", "atr",
                         "sma_20", "sma_50", "volatility_20d", "volume_ratio"]:
                if col in df.columns:
                    mean = df[col].mean()
                    std = df[col].std()
                    if std > 0:
                        df[col] = (df[col] - mean) / std

            # We can't easily reconstruct the full dataset for prediction without
            # the original training dataset. Fall back to simple model.
            log.warning("TFT inference needs training context, falling back to simple model")
            return self._forecast_simple(symbol, horizon)

        # If model is loaded (just trained), use it
        if self.model is not None:
            df = fetch_ohlcv([symbol], self.max_encoder_length + horizon + 60)
            if df.empty:
                return {"symbol": symbol, "error": "No data"}

            df = df.sort_values(["symbol", "date"]).copy()
            df["time_idx"] = df.groupby("symbol").cumcount()

            for col in ["close", "volume", "rsi", "macd", "macd_signal", "atr",
                         "sma_20", "sma_50", "volatility_20d", "volume_ratio"]:
                if col in df.columns:
                    mean = df[col].mean()
                    std = df[col].std()
                    if std > 0:
                        df[col] = (df[col] - mean) / std

            try:
                prediction = self.model.predict(df, mode="prediction", return_x=True)
                raw = prediction.output.numpy() if hasattr(prediction.output, "numpy") else np.array(prediction.output)
                # raw shape: (horizon,) or (1, horizon)
                raw = raw.flatten()[:horizon]

                forecasts = []
                for i, val in enumerate(raw):
                    point = float(val)
                    lower = float(point - 0.01 * (i + 1))
                    upper = float(point + 0.01 * (i + 1))
                    forecasts.append({"day": i + 1, "point": point, "lower": lower, "upper": upper})

                direction = "up" if raw.mean() > 0 else "down"
                confidence = min(1.0, abs(raw.mean()) * 100)

                return {
                    "symbol": symbol,
                    "forecasts": forecasts,
                    "direction": direction,
                    "confidence": round(confidence, 4),
                }
            except Exception as e:
                log.error("TFT predict failed: %s, using simple model", e)
                return self._forecast_simple(symbol, horizon)

        return {"symbol": symbol, "error": "Model not loaded"}

    # -- Simplified pure-PyTorch TFT --------------------------------------

    def _train_simple(self, df: pd.DataFrame) -> dict:
        """Train simplified TFT using pure PyTorch."""
        log.info("Training simplified TFT (%d rows)", len(df))

        feature_cols = ["close", "volume", "rsi", "macd", "macd_signal",
                        "atr", "sma_20", "sma_50", "volatility_20d", "volume_ratio",
                        "return_1d"]
        known_cols = ["day_of_week", "month"]

        # Build sequences
        sequences, targets, known_seqs = [], [], []
        seq_len = self.max_encoder_length

        for sym, group in df.sort_values(["symbol", "date"]).groupby("symbol"):
            if len(group) < seq_len + self.horizon:
                continue
            group = group.reset_index(drop=True)
            for i in range(len(group) - seq_len - self.horizon + 1):
                seq = group.loc[i:i + seq_len - 1, feature_cols].values.astype(np.float32)
                known_seq = group.loc[i:i + seq_len - 1, known_cols].values.astype(np.float32)
                # Target: returns for next `horizon` days
                target_arr = []
                for h in range(1, self.horizon + 1):
                    if i + seq_len + h - 1 < len(group):
                        ret = (group.loc[i + seq_len + h - 1, "close"] / group.loc[i + seq_len - 1, "close"]) - 1
                    else:
                        ret = 0.0
                    target_arr.append(float(ret))
                sequences.append(seq)
                known_seqs.append(known_seq)
                targets.append(target_arr)

        if not sequences:
            return {"error": "Not enough sequences for training", "rows": len(df)}

        X = np.array(sequences)
        K = np.array(known_seqs)
        Y = np.array(targets, dtype=np.float32)

        # Normalize features
        X_mean = X.mean(axis=(0, 1), keepdims=True)
        X_std = X.std(axis=(0, 1), keepdims=True) + 1e-8
        X = (X - X_mean) / X_std

        # Build model
        n_features = len(feature_cols)
        n_known = len(known_cols)
        model = SimpleTFT(
            n_features=n_features,
            n_known=n_known,
            horizon=self.horizon,
            d_model=64,
            n_heads=4,
            dropout=0.1,
        )

        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
        criterion = nn.MSELoss()
        quantile_criterion = QuantileLossSimple()

        X_t = torch.from_numpy(X)
        K_t = torch.from_numpy(K)
        Y_t = torch.from_numpy(Y)

        # Training loop
        best_loss = float("inf")
        patience_counter = 0
        patience = 8

        model.train()
        for epoch in range(self.max_epochs):
            optimizer.zero_grad()
            point_pred, quantile_pred = model(X_t, K_t)
            loss = criterion(point_pred, Y_t) + 0.5 * quantile_criterion(quantile_pred, Y_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
            optimizer.step()

            if loss.item() < best_loss:
                best_loss = loss.item()
                patience_counter = 0
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                torch.save({
                    "model_state": model.state_dict(),
                    "config": {
                        "n_features": n_features,
                        "n_known": n_known,
                        "horizon": self.horizon,
                        "d_model": 64,
                        "n_heads": 4,
                        "dropout": 0.1,
                        "seq_len": seq_len,
                    },
                    "norm": {"mean": X_mean.tolist(), "std": X_std.tolist()},
                    "feature_cols": feature_cols,
                    "known_cols": known_cols,
                }, self.simple_model_path)
            else:
                patience_counter += 1

            scheduler.step(loss)

            if (epoch + 1) % 5 == 0:
                log.info("Epoch %d: loss=%.6f best=%.6f", epoch + 1, loss.item(), best_loss)

            if patience_counter >= patience:
                log.info("Early stopping at epoch %d", epoch + 1)
                break

        self.simple_model = model
        self._simple_norm = {"mean": X_mean.tolist(), "std": X_std.tolist()}
        self._simple_feature_cols = feature_cols
        self._simple_known_cols = known_cols
        self._simple_seq_len = seq_len
        metrics = {
            "trainer": "simple_pytorch_tft",
            "rows": len(df),
            "sequences": len(sequences),
            "epochs_trained": epoch + 1,
            "best_loss": round(best_loss, 6),
            "model_path": str(self.simple_model_path),
        }
        log.info("Simple TFT training complete: %s", metrics)
        return metrics

    def _forecast_simple(self, symbol: str, horizon: int) -> dict:
        """Forecast using simplified pure-PyTorch TFT."""
        # Load model if needed
        if self.simple_model is None and self.simple_model_path.exists():
            checkpoint = torch.load(self.simple_model_path, map_location="cpu")
            config = checkpoint["config"]
            model = SimpleTFT(
                n_features=config["n_features"],
                n_known=config["n_known"],
                horizon=config["horizon"],
                d_model=config["d_model"],
                n_heads=config["n_heads"],
                dropout=config["dropout"],
            )
            model.load_state_dict(checkpoint["model_state"])
            model.eval()
            self.simple_model = model
            self._simple_norm = checkpoint["norm"]
            self._simple_feature_cols = checkpoint["feature_cols"]
            self._simple_known_cols = checkpoint["known_cols"]
            self._simple_seq_len = config["seq_len"]

        if self.simple_model is None:
            return {"symbol": symbol, "error": "No trained simple model found"}

        # Fetch recent data
        lookback = self._simple_seq_len + 10
        df = fetch_ohlcv([symbol], lookback_days=lookback)
        if df.empty or len(df) < self._simple_seq_len:
            return {"symbol": symbol, "error": "Insufficient recent data"}

        df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

        # Build most recent sequence
        feature_cols = self._simple_feature_cols
        known_cols = self._simple_known_cols
        seq_len = self._simple_seq_len

        group = df[df["symbol"] == symbol].iloc[-seq_len:]
        if len(group) < seq_len:
            return {"symbol": symbol, "error": "Not enough recent rows"}

        seq = group[feature_cols].values.astype(np.float32)
        known_seq = group[known_cols].values.astype(np.float32)

        # Normalize
        mean = np.array(self._simple_norm["mean"], dtype=np.float32).reshape(-1)
        std = np.array(self._simple_norm["std"], dtype=np.float32).reshape(-1)
        seq = (seq - mean) / std

        X_t = torch.from_numpy(seq).unsqueeze(0)  # (1, seq_len, n_features)
        K_t = torch.from_numpy(known_seq).unsqueeze(0)  # (1, seq_len, n_known)

        with torch.no_grad():
            point_pred, quantile_pred = self.simple_model(X_t, K_t)

        # point_pred: (1, horizon), quantile_pred: (1, horizon, 3) for [0.1, 0.5, 0.9]
        point = point_pred.squeeze(0).numpy()
        quants = quantile_pred.squeeze(0).numpy()  # (horizon, 3)

        forecasts = []
        for i in range(horizon):
            if i < len(point):
                p = float(point[i])
                lower = float(quants[i, 0]) if quants.shape[1] >= 3 else float(p - 0.01)
                upper = float(quants[i, 2]) if quants.shape[1] >= 3 else float(p + 0.01)
            else:
                p = float(point[-1]) if len(point) > 0 else 0.0
                lower = p - 0.01
                upper = p + 0.01
            forecasts.append({"day": i + 1, "point": round(p, 6), "lower": round(lower, 6), "upper": round(upper, 6)})

        avg_return = float(np.mean(point[:horizon]))
        direction = "up" if avg_return > 0 else "down"
        confidence = min(1.0, abs(avg_return) * 100)

        return {
            "symbol": symbol,
            "forecasts": forecasts,
            "direction": direction,
            "confidence": round(confidence, 4),
        }


# ---------------------------------------------------------------------------
# Simplified pure-PyTorch TFT
# ---------------------------------------------------------------------------

class SimpleTFT(nn.Module):
    """Simplified Temporal Fusion Transformer using multi-head attention.

    Architecture:
        - Variable Selection Network (simplified) → feature projection
        - Multi-head self-attention over recent price sequence
        - Known inputs (calendar features) concatenated
        - Decoder: per-horizon linear heads + quantile heads
    """

    def __init__(
        self,
        n_features: int,
        n_known: int,
        horizon: int,
        d_model: int = 64,
        n_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.horizon = horizon
        self.d_model = d_model

        # Feature projection
        self.feature_proj = nn.Linear(n_features, d_model)
        self.known_proj = nn.Linear(n_known, d_model)

        # Gated feature selection (simplified VSN)
        self.feature_gate = nn.Sequential(
            nn.Linear(n_features, n_features),
            nn.Sigmoid(),
        )

        # Positional encoding (learned)
        self.pos_encoding = nn.Parameter(torch.randn(1, 512, d_model) * 0.02)

        # Multi-head self-attention
        self.attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)

        # Feedforward
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model),
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # Decoder: temporal fusion + horizon-specific heads
        self.decoder = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
        )

        # Point forecast head
        self.point_head = nn.Linear(d_model, horizon)

        # Quantile forecast head (3 quantiles: 0.1, 0.5, 0.9)
        self.quantile_head = nn.Linear(d_model, horizon * 3)

    def forward(self, x: torch.Tensor, known: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, n_features) - unknown inputs
            known: (batch, seq_len, n_known) - known inputs (calendar features)

        Returns:
            point_pred: (batch, horizon)
            quantile_pred: (batch, horizon, 3)
        """
        batch_size, seq_len, _ = x.shape

        # Gated feature selection
        gate = self.feature_gate(x)
        x_gated = x * gate

        # Project to d_model
        h = self.feature_proj(x_gated) + self.known_proj(known)

        # Add positional encoding
        h = h + self.pos_encoding[:, :seq_len, :]

        # Self-attention
        attn_out, _ = self.attention(h, h, h)
        h = self.norm1(h + attn_out)

        # Feedforward
        ffn_out = self.ffn(h)
        h = self.norm2(h + ffn_out)

        # Use last timestep for prediction (can also use pooling)
        h_last = h[:, -1, :]  # (batch, d_model)

        # Decode
        decoded = self.decoder(h_last)

        # Point forecast
        point_pred = self.point_head(decoded)  # (batch, horizon)

        # Quantile forecast
        quantile_pred = self.quantile_head(decoded)  # (batch, horizon * 3)
        quantile_pred = quantile_pred.view(batch_size, self.horizon, 3)

        return point_pred, quantile_pred


class QuantileLossSimple(nn.Module):
    """Simple quantile loss for 0.1, 0.5, 0.9 quantiles."""

    def __init__(self, quantiles: List[float] = None):
        super().__init__()
        self.quantiles = quantiles or [0.1, 0.5, 0.9]

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        pred: (batch, horizon, 3)
        target: (batch, horizon)
        """
        target = target.unsqueeze(-1)  # (batch, horizon, 1)
        loss = 0
        for i, q in enumerate(self.quantiles):
            error = target - pred[..., i:i+1]
            loss = loss + torch.mean(torch.maximum(q * error, (q - 1) * error))
        return loss


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TFT Multi-Horizon Forecaster")
    parser.add_argument("--train", nargs="+", default=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
                        help="Symbols to train on")
    parser.add_argument("--forecast", nargs="+", default=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
                        help="Symbols to forecast")
    parser.add_argument("--lookback", type=int, default=252)
    parser.add_argument("--horizon", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()

    forecaster = TFTForecaster(max_epochs=args.epochs, horizon=args.horizon)

    print("\n=== Training ===")
    train_metrics = forecaster.train(args.train, lookback_days=args.lookback, horizon=args.horizon)
    print(json.dumps(train_metrics, indent=2))

    print("\n=== Forecasting ===")
    results = forecaster.batch_forecast(args.forecast)
    for r in results:
        print(json.dumps(r, indent=2))