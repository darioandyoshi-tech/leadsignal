"""
FinRL Exit Agent — Reinforcement Learning for Position Exit Optimization.

Uses PPO (Proximal Policy Optimization) via stable-baselines3 to learn optimal
exit policies for long positions. The agent decides between HOLD and SELL given
the current market state (price, RSI, ATR, unrealized P/L, days held, etc.).

Usage:
    from app.market.finrl_agent import FinRLExitAgent

    agent = FinRLExitAgent()
    metrics = agent.train(symbols=["AAPL","MSFT","GOOGL","AMZN","NVDA"], lookback_days=504)
    decision = agent.predict_exit("AAPL", entry_price=150.0, current_price=155.0,
                                  days_held=3, unrealized_pl_pct=3.33,
                                  rsi=65.0, atr=2.1, stop_loss=145.0, take_profit=165.0)
    # → "HOLD" or "SELL"
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import io
import json
import zipfile

import numpy as np
import pandas as pd
import torch as th
import yfinance as yf
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Monkey-patch SB3 save_util to work around torch 2.6+ weights_only issue
# torch 2.6+ changed weights_only=True default which breaks loading from ZipExtFile
# https://github.com/DLR-RM/stable-baselines3/issues/2001
# ---------------------------------------------------------------------------

import zipfile as _zipfile

def _patched_load_from_zip_file(load_path, load_data=True, custom_objects=None,
                                  device="auto", verbose=0, print_system_info=False):
    """Patched version that reads .pth files into BytesIO before torch.load."""
    from stable_baselines3.common.save_util import open_path, get_device, json_to_data

    file = open_path(load_path, "r", verbose=verbose, suffix="zip")
    device = get_device(device=device)

    try:
        with _zipfile.ZipFile(file) as archive:
            namelist = archive.namelist()
            data = None
            pytorch_variables = None
            params = {}

            if print_system_info and "system_info.txt" in namelist:
                print("== SAVED MODEL SYSTEM INFO ==")
                print(archive.read("system_info.txt").decode())

            if "data" in namelist and load_data:
                json_data = archive.read("data").decode()
                data = json_to_data(json_data, custom_objects=custom_objects)

            pth_files = [f for f in namelist if os.path.splitext(f)[1] == ".pth"]
            for file_path in pth_files:
                # Read into BytesIO to avoid torch weights_only issues with ZipExtFile
                with archive.open(file_path, mode="r") as param_file:
                    buf = io.BytesIO(param_file.read())
                th_object = th.load(buf, map_location=device, weights_only=True)
                if file_path == "pytorch_variables.pth" or file_path == "tensors.pth":
                    pytorch_variables = th_object
                else:
                    params[os.path.splitext(file_path)[0]] = th_object
    except _zipfile.BadZipFile as e:
        raise ValueError(f"Error: the file {load_path} wasn't a zip-file") from e
    finally:
        if isinstance(load_path, (str, type(__import__('pathlib').Path()))):
            file.close()

    return data, params, pytorch_variables


import stable_baselines3.common.save_util as _sb3_save_util
import stable_baselines3.common.base_class as _sb3_base

_sb3_save_util.load_from_zip_file = _patched_load_from_zip_file
# Patch the already-imported reference in base_class
_sb3_base.load_from_zip_file = _patched_load_from_zip_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_PATH = Path(__file__).parent / "data" / "finrl_exit_model.zip"
DATA_DIR = Path(__file__).parent / "data"

# State features (8 dimensions)
# 0: normalized current price (relative to entry)
# 1: normalized entry price (always 1.0)
# 2: days held (normalized by max_hold)
# 3: unrealized P/L %
# 4: RSI (0-100, normalized to 0-1)
# 5: ATR (normalized by price)
# 6: stop loss distance (normalized by price)
# 7: take profit distance (normalized by price)

STATE_DIM = 8
MAX_HOLD_DAYS = 60  # max days before forced sell penalty kicks in
ACTION_HOLD = 0
ACTION_SELL = 1

# ---------------------------------------------------------------------------
# Technical indicators (computed inline to avoid pandas-ta dependency issues)
# ---------------------------------------------------------------------------

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI (Relative Strength Index)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Compute ATR (Average True Range)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    return atr


# ---------------------------------------------------------------------------
# Custom Gymnasium Environment for Exit Optimization
# ---------------------------------------------------------------------------

class ExitTradingEnv(gym.Env):
    """
    Custom Gymnasium environment for learning when to exit a long position.

    The environment simulates a single position from entry to exit. At each
    timestep the agent observes market state and decides HOLD or SELL.

    Reward design:
        - SELL: realized P/L (percent). Episode ends.
        - HOLD: small penalty (-0.01 * days_held / MAX_HOLD_DAYS) to discourage
          holding forever. If price hits stop loss, forced sell with large penalty.
        - If max hold days exceeded, forced sell at current price.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        df: pd.DataFrame,
        entry_idx: int,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15,
        max_hold_days: int = MAX_HOLD_DAYS,
    ) -> None:
        """
        Args:
            df: OHLCV DataFrame with columns: Open, High, Low, Close, Volume,
                plus precomputed RSI, ATR columns.
            entry_idx: Index in df where the position was opened (entry at Close).
            stop_loss_pct: Stop loss as fraction below entry (e.g. 0.05 = 5%).
            take_profit_pct: Take profit as fraction above entry (e.g. 0.15 = 15%).
            max_hold_days: Maximum days to hold before forced sell.
        """
        super().__init__()
        self.df = df.reset_index(drop=True)
        self.entry_idx = entry_idx
        self.entry_price = float(df.iloc[entry_idx]["Close"])
        self.stop_loss = self.entry_price * (1 - stop_loss_pct)
        self.take_profit = self.entry_price * (1 + take_profit_pct)
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_hold_days = max_hold_days

        # Action: 0=HOLD, 1=SELL
        self.action_space = spaces.Discrete(2)
        # Observation: 8 continuous features in [-inf, inf] roughly
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(STATE_DIM,), dtype=np.float32
        )

        self.current_step = entry_idx
        self.days_held = 0
        self._reset_state()

    def _reset_state(self) -> None:
        self.current_step = self.entry_idx
        self.days_held = 0

    def _get_obs(self) -> np.ndarray:
        row = self.df.iloc[self.current_step]
        current_price = float(row["Close"])
        rsi = float(row.get("RSI", 50.0))
        atr = float(row.get("ATR", current_price * 0.02))

        unrealized_pl_pct = ((current_price - self.entry_price) / self.entry_price) * 100.0
        sl_dist = (current_price - self.stop_loss) / current_price
        tp_dist = (self.take_profit - current_price) / current_price

        obs = np.array([
            current_price / self.entry_price,       # normalized current price
            1.0,                                     # entry price normalized
            self.days_held / self.max_hold_days,     # normalized days held
            unrealized_pl_pct,                       # P/L %
            rsi / 100.0,                             # RSI normalized
            atr / current_price,                     # ATR normalized
            sl_dist,                                 # stop loss distance
            tp_dist,                                 # take profit distance
        ], dtype=np.float32)
        return obs

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict] = None) -> tuple:
        super().reset(seed=seed)
        self._reset_state()
        return self._get_obs(), {}

    def step(self, action: int) -> tuple:
        row = self.df.iloc[self.current_step]
        current_price = float(row["Close"])

        # Check stop loss / take profit first
        hit_stop = current_price <= self.stop_loss
        hit_tp = current_price >= self.take_profit

        if action == ACTION_SELL or hit_stop or hit_tp or self.days_held >= self.max_hold_days:
            # Sell — compute realized P/L
            realized_pl_pct = ((current_price - self.entry_price) / self.entry_price) * 100.0

            # Reward shaping: base reward is realized P/L
            reward = realized_pl_pct

            # Penalty for hitting stop loss
            if hit_stop and action != ACTION_SELL:
                reward -= 2.0  # extra penalty for getting stopped out

            # Bonus for hitting take profit
            if hit_tp and action != ACTION_SELL:
                reward += 1.0  # bonus for reaching TP

            # Small penalty if held too long and didn't profit
            if self.days_held >= self.max_hold_days and realized_pl_pct <= 0:
                reward -= 1.0

            return self._get_obs(), float(reward), True, False, {
                "realized_pl_pct": realized_pl_pct,
                "days_held": self.days_held,
                "exit_reason": "sell" if action == ACTION_SELL else
                               ("stop_loss" if hit_stop else
                                "take_profit" if hit_tp else "max_hold"),
            }

        # HOLD
        reward = -0.01 * (self.days_held / self.max_hold_days)
        self.current_step = min(self.current_step + 1, len(self.df) - 1)
        self.days_held += 1
        return self._get_obs(), float(reward), False, False, {}


# ---------------------------------------------------------------------------
# Multi-symbol training environment wrapper
# ---------------------------------------------------------------------------

class MultiSymbolExitEnv(gym.Env):
    """
    Samples random entry points across multiple symbols for diverse training.
    Each reset picks a random symbol and a random entry point.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(self, data_dict: Dict[str, pd.DataFrame], **env_kwargs) -> None:
        super().__init__()
        self.data_dict = data_dict
        self.symbols = list(data_dict.keys())
        self.env_kwargs = env_kwargs

        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(STATE_DIM,), dtype=np.float32
        )
        self._current_env: Optional[ExitTradingEnv] = None

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict] = None) -> tuple:
        super().reset(seed=seed)
        sym = self.np_random.choice(self.symbols)
        df = self.data_dict[sym]
        # Pick entry point with enough room after (at least 30 bars)
        max_entry = len(df) - 31
        if max_entry < 10:
            entry_idx = 0
        else:
            entry_idx = int(self.np_random.integers(0, max_entry))
        self._current_env = ExitTradingEnv(df, entry_idx, **self.env_kwargs)
        obs, _ = self._current_env.reset(seed=seed)
        return obs, {}

    def step(self, action: int) -> tuple:
        return self._current_env.step(action)


# ---------------------------------------------------------------------------
# Training logger callback
# ---------------------------------------------------------------------------

class TrainingLoggerCallback(BaseCallback):
    """Logs training progress every N steps."""

    def __init__(self, log_interval: int = 1000, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.log_interval = log_interval

    def _on_step(self) -> bool:
        if self.n_calls % self.log_interval == 0:
            infos = self.locals.get("infos", [])
            rewards = self.locals.get("rewards", [])
            if rewards:
                logger.info(
                    f"Step {self.n_calls}: "
                    f"mean_reward={np.mean(rewards):.4f} "
                    f"n_envs={len(rewards)}"
                )
        return True


# ---------------------------------------------------------------------------
# FinRLExitAgent
# ---------------------------------------------------------------------------

class FinRLExitAgent:
    """
    Reinforcement Learning agent for optimizing position exits.

    Uses PPO to learn when to HOLD vs SELL an existing long position.
    Trains on historical S&P 500 data and produces a model that can be
    queried at runtime for exit decisions.
    """

    # Default S&P 500 symbols for training
    DEFAULT_SYMBOLS = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "JPM", "V", "PG",
        "UNH", "HD", "MA", "DIS", "BAC",
        "XOM", "PFE", "KO", "PEP", "CSCO",
    ]

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = model_path or MODEL_PATH
        self.model: Optional[PPO] = None
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Data fetching & preprocessing
    # ------------------------------------------------------------------

    def _fetch_data(self, symbols: List[str], lookback_days: int) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data via yfinance and compute RSI/ATR."""
        period_str = f"{lookback_days}d"
        data_dict: Dict[str, pd.DataFrame] = {}

        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period=period_str, auto_adjust=True)
                if df is None or len(df) < 50:
                    logger.warning(f"Insufficient data for {sym}, skipping")
                    continue

                # Normalize column names
                df = df.rename(columns=str.capitalize)
                # yfinance returns: Open, High, Low, Close, Volume
                if "Close" not in df.columns:
                    logger.warning(f"No Close column for {sym}, skipping")
                    continue

                # Compute technical indicators
                df["RSI"] = _compute_rsi(df["Close"], period=14)
                df["ATR"] = _compute_atr(df["High"], df["Low"], df["Close"], period=14)

                # Fill NaN
                df = df.ffill().bfill()
                df["RSI"] = df["RSI"].fillna(50.0)
                df["ATR"] = df["ATR"].fillna(df["Close"] * 0.02)

                data_dict[sym] = df
                logger.info(f"Fetched {len(df)} bars for {sym}")
            except Exception as e:
                logger.warning(f"Failed to fetch {sym}: {e}")

        if not data_dict:
            raise RuntimeError("No data fetched for any symbol")

        return data_dict

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        symbols: Optional[List[str]] = None,
        lookback_days: int = 504,
        total_timesteps: int = 50_000,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Train the PPO agent on historical data.

        Args:
            symbols: List of ticker symbols. Defaults to 20 S&P 500 stocks.
            lookback_days: Days of history to fetch (default 504 = ~2 years).
            total_timesteps: Total training timesteps.
            learning_rate: PPO learning rate.
            n_steps: PPO rollout buffer size per env.
            batch_size: PPO mini-batch size.
            n_epochs: PPO optimization epochs per update.
            gamma: Discount factor.
            stop_loss_pct: Stop loss percentage (fraction below entry).
            take_profit_pct: Take profit percentage (fraction above entry).

        Returns:
            Dict with training metrics: timesteps, symbols_used, model_path, etc.
        """
        if symbols is None:
            symbols = self.DEFAULT_SYMBOLS[:20]

        logger.info(f"Starting training: {len(symbols)} symbols, {lookback_days}d lookback")

        # Fetch data
        data_dict = self._fetch_data(symbols, lookback_days)
        symbols_used = list(data_dict.keys())
        logger.info(f"Training on {len(symbols_used)} symbols: {symbols_used}")

        # Create multi-symbol environment
        env = MultiSymbolExitEnv(
            data_dict,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        vec_env = DummyVecEnv([lambda: env])

        # Create PPO agent
        model = PPO(
            "MlpPolicy",
            vec_env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            verbose=0,
            policy_kwargs={
                "net_arch": {
                    "pi": [64, 64],
                    "vf": [64, 64],
                },
            },
        )

        # Train
        callback = TrainingLoggerCallback(log_interval=max(total_timesteps // 10, 500))
        model.learn(total_timesteps=total_timesteps, callback=callback)

        # Save
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(self.model_path))
        self.model = model
        logger.info(f"Model saved to {self.model_path}")

        return {
            "status": "success",
            "symbols_used": symbols_used,
            "n_symbols": len(symbols_used),
            "total_timesteps": total_timesteps,
            "model_path": str(self.model_path),
            "lookback_days": lookback_days,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def _load_model(self) -> PPO:
        """Load the trained PPO model."""
        if self.model is not None:
            return self.model
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found at {self.model_path}. Call train() first."
            )
        self.model = PPO.load(str(self.model_path))
        logger.info(f"Model loaded from {self.model_path}")
        return self.model

    def predict_exit(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        days_held: int,
        unrealized_pl_pct: float,
        rsi: float,
        atr: float,
        stop_loss: float,
        take_profit: float,
    ) -> str:
        """
        Predict whether to HOLD or SELL the position.

        Args:
            symbol: Ticker symbol (for context/logging).
            entry_price: Price at which the position was opened.
            current_price: Current market price.
            days_held: Number of days the position has been held.
            unrealized_pl_pct: Unrealized P/L as percentage.
            rsi: Current RSI value (0-100).
            atr: Current ATR value.
            stop_loss: Stop loss price level.
            take_profit: Take profit price level.

        Returns:
            "HOLD" or "SELL"
        """
        model = self._load_model()

        # Construct observation
        price_ratio = current_price / entry_price if entry_price > 0 else 1.0
        sl_dist = (current_price - stop_loss) / current_price if current_price > 0 else 0.0
        tp_dist = (take_profit - current_price) / current_price if current_price > 0 else 0.0

        obs = np.array([
            price_ratio,
            1.0,
            min(days_held, MAX_HOLD_DAYS) / MAX_HOLD_DAYS,
            unrealized_pl_pct,
            rsi / 100.0,
            atr / current_price if current_price > 0 else 0.0,
            sl_dist,
            tp_dist,
        ], dtype=np.float32)

        # Predict
        action, _ = model.predict(obs.reshape(1, -1), deterministic=True)
        action = int(action[0]) if hasattr(action, "__iter__") else int(action)

        decision = "SELL" if action == ACTION_SELL else "HOLD"
        logger.info(
            f"FinRL exit prediction for {symbol}: {decision} "
            f"(entry={entry_price}, current={current_price}, "
            f"days_held={days_held}, pl%={unrealized_pl_pct:.2f}, rsi={rsi:.1f})"
        )
        return decision

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------

    def backtest(
        self,
        symbols: Optional[List[str]] = None,
        lookback_days: int = 504,
        train_ratio: float = 0.7,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15,
        initial_capital: float = 100_000.0,
    ) -> Dict[str, Any]:
        """
        Backtest the trained agent on out-of-sample data.

        Splits data into train/test, runs the agent on the test portion,
        and computes Sharpe ratio, total return, and win rate.

        Args:
            symbols: Symbols to backtest on. Defaults to training symbols.
            lookback_days: Days of history.
            train_ratio: Fraction of data used for training (rest = test).
            stop_loss_pct: Stop loss fraction.
            take_profit_pct: Take profit fraction.
            initial_capital: Starting capital for simulated trades.

        Returns:
            Dict with backtest metrics:
            - sharpe_ratio: Annualized Sharpe ratio
            - total_return_pct: Total return percentage
            - win_rate: Fraction of profitable trades
            - n_trades: Number of trades
            - avg_pl_pct: Average P/L per trade
            - trades: List of trade results
        """
        if symbols is None:
            symbols = self.DEFAULT_SYMBOLS[:10]

        model = self._load_model()

        # Fetch data
        data_dict = self._fetch_data(symbols, lookback_days)

        trades: List[Dict[str, Any]] = []
        capital = initial_capital

        for sym, df in data_dict.items():
            if len(df) < 100:
                continue

            split_idx = int(len(df) * train_ratio)
            test_df = df.iloc[split_idx:].reset_index(drop=True)

            if len(test_df) < 30:
                continue

            # Simulate trades: enter every 20 bars, use agent to decide exit
            i = 0
            while i < len(test_df) - 5:
                entry_price = float(test_df.iloc[i]["Close"])
                entry_idx = i
                days_held = 0
                exit_price = entry_price
                exit_reason = "max_hold"

                # Simulate the position day by day
                for j in range(i + 1, min(i + MAX_HOLD_DAYS + 1, len(test_df))):
                    row = test_df.iloc[j]
                    current_price = float(row["Close"])
                    rsi = float(row.get("RSI", 50.0))
                    atr = float(row.get("ATR", current_price * 0.02))
                    days_held = j - entry_idx

                    sl = entry_price * (1 - stop_loss_pct)
                    tp = entry_price * (1 + take_profit_pct)
                    unrealized_pl_pct = ((current_price - entry_price) / entry_price) * 100.0

                    # Check stop loss / take profit
                    if current_price <= sl:
                        exit_price = current_price
                        exit_reason = "stop_loss"
                        break
                    if current_price >= tp:
                        exit_price = current_price
                        exit_reason = "take_profit"
                        break

                    # Ask agent
                    decision = self.predict_exit(
                        sym, entry_price, current_price, days_held,
                        unrealized_pl_pct, rsi, atr, sl, tp,
                    )
                    if decision == "SELL":
                        exit_price = current_price
                        exit_reason = "agent_sell"
                        break

                    exit_price = current_price
                    days_held = j - entry_idx

                pl_pct = ((exit_price - entry_price) / entry_price) * 100.0
                position_value = capital * 0.1  # 10% per trade
                pnl = position_value * (pl_pct / 100.0)
                capital += pnl

                trades.append({
                    "symbol": sym,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "days_held": days_held,
                    "pl_pct": pl_pct,
                    "exit_reason": exit_reason,
                    "pnl": pnl,
                })

                # Move to next entry (every 20 bars)
                i += 20

        if not trades:
            return {
                "sharpe_ratio": 0.0,
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "n_trades": 0,
                "avg_pl_pct": 0.0,
                "trades": [],
            }

        # Compute metrics
        pl_values = [t["pl_pct"] for t in trades]
        pnl_values = [t["pnl"] for t in trades]
        total_return_pct = ((capital - initial_capital) / initial_capital) * 100.0
        win_rate = sum(1 for p in pl_values if p > 0) / len(pl_values)
        avg_pl_pct = np.mean(pl_values)

        # Sharpe ratio (annualized, assuming daily entries)
        if len(pnl_values) > 1 and np.std(pnl_values) > 0:
            daily_returns = np.array(pnl_values) / initial_capital
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = 0.0

        return {
            "sharpe_ratio": float(sharpe),
            "total_return_pct": float(total_return_pct),
            "win_rate": float(win_rate),
            "n_trades": len(trades),
            "avg_pl_pct": float(avg_pl_pct),
            "trades": trades[:20],  # first 20 for inspection
            "final_capital": float(capital),
        }


# ---------------------------------------------------------------------------
# CLI entry point for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    agent = FinRLExitAgent()

    # Quick test mode: train on 5 symbols for a short run
    test_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        results = agent.backtest(symbols=test_symbols, lookback_days=252)
        print(json.dumps(results, indent=2, default=str))
    else:
        # Quick training
        metrics = agent.train(
            symbols=test_symbols,
            lookback_days=252,
            total_timesteps=10_000,
        )
        print("Training complete:")
        print(json.dumps(metrics, indent=2, default=str))

        # Test predict_exit
        decision = agent.predict_exit(
            "AAPL",
            entry_price=150.0,
            current_price=155.0,
            days_held=3,
            unrealized_pl_pct=3.33,
            rsi=65.0,
            atr=2.1,
            stop_loss=145.0,
            take_profit=165.0,
        )
        print(f"\npredict_exit result: {decision}")

        decision2 = agent.predict_exit(
            "AAPL",
            entry_price=150.0,
            current_price=142.0,
            days_held=30,
            unrealized_pl_pct=-5.33,
            rsi=25.0,
            atr=3.5,
            stop_loss=142.5,
            take_profit=172.5,
        )
        print(f"predict_exit result (losing position): {decision2}")