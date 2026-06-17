"""Singleton TimesFM client with caching and batching helpers."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Container for a single forecast."""

    point: np.ndarray
    quantiles: np.ndarray
    horizon: int
    input_length: int
    model_name: str
    # Optional extra metadata
    metadata: dict = None

    def to_dict(self) -> dict:
        return {
            "point": self.point.tolist(),
            "quantiles": self.quantiles.tolist(),
            "horizon": self.horizon,
            "input_length": self.input_length,
            "model_name": self.model_name,
            "metadata": self.metadata or {},
        }

    def to_json(self, **kwargs) -> str:
        return json.dumps(self.to_dict(), **kwargs)


class TimesFMClient:
    """Lightweight singleton wrapper around the official TimesFM torch model.

    The model is loaded lazily on first forecast call and reused across calls.
    """

    _instance: Optional["TimesFMClient"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        model_name: str = "google/timesfm-2.5-200m-pytorch",
        max_context: int = 1024,
        max_horizon: int = 256,
        normalize_inputs: bool = True,
        use_continuous_quantile_head: bool = True,
        force_flip_invariance: bool = True,
        infer_is_positive: bool = True,
        fix_quantile_crossing: bool = True,
        device: Optional[str] = None,
    ):
        if self._initialized:
            return
        self.model_name = model_name
        self.max_context = max_context
        self.max_horizon = max_horizon
        self.normalize_inputs = normalize_inputs
        self.use_continuous_quantile_head = use_continuous_quantile_head
        self.force_flip_invariance = force_flip_invariance
        self.infer_is_positive = infer_is_positive
        self.fix_quantile_crossing = fix_quantile_crossing
        self.device = device or os.environ.get("TIMESFM_DEVICE", "cuda" if self._cuda_available() else "cpu")

        self._model = None
        self._initialized = True
        logger.info("TimesFMClient initialized (model not loaded yet)")

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    def _load_model(self):
        if self._model is not None:
            return
        try:
            import timesfm
            import torch
        except ImportError as exc:
            raise ImportError(
                "TimesFM dependencies not found. "
                "Activate the timesfm venv or install: pip install timesfm[torch]"
            ) from exc

        torch.set_float32_matmul_precision("high")
        logger.info("Loading TimesFM model: %s on device: %s", self.model_name, self.device)
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self.model_name)
        model.compile(
            timesfm.ForecastConfig(
                max_context=self.max_context,
                max_horizon=self.max_horizon,
                normalize_inputs=self.normalize_inputs,
                use_continuous_quantile_head=self.use_continuous_quantile_head,
                force_flip_invariance=self.force_flip_invariance,
                infer_is_positive=self.infer_is_positive,
                fix_quantile_crossing=self.fix_quantile_crossing,
            )
        )
        self._model = model
        logger.info("TimesFM model loaded and compiled.")

    def forecast(
        self,
        inputs: Iterable[np.ndarray | List[float]],
        horizon: int,
    ) -> List[ForecastResult]:
        """Run forecasting on one or more input series.

        Args:
            inputs: list of 1-D numeric arrays/sequences.
            horizon: number of future steps to predict.

        Returns:
            List of ForecastResult, one per input series.
        """
        self._load_model()
        import torch

        arrays = [np.asarray(ts, dtype=np.float32).ravel() for ts in inputs]
        if not arrays:
            raise ValueError("inputs must contain at least one time series")
        if horizon <= 0 or horizon > self.max_horizon:
            raise ValueError(f"horizon must be in [1, {self.max_horizon}], got {horizon}")

        # Context is limited by model max_context; truncate from the end if too long.
        trimmed = []
        for arr in arrays:
            if arr.ndim != 1:
                raise ValueError("Each input series must be 1-D")
            if len(arr) > self.max_context:
                arr = arr[-self.max_context :]
            trimmed.append(arr)

        # TimesFM mutates the inputs list in-place, so pass a copy.
        model_inputs = list(trimmed)
        with torch.inference_mode():
            point, quantiles = self._model.forecast(horizon=horizon, inputs=model_inputs)

        # TimesFM may return numpy directly or torch tensors depending on version.
        if hasattr(point, "detach"):
            point = point.detach().cpu().numpy()
        else:
            point = np.asarray(point)
        if hasattr(quantiles, "detach"):
            quantiles = quantiles.detach().cpu().numpy()
        else:
            quantiles = np.asarray(quantiles)

        # Ensure batch dimension exists and matches number of inputs.
        n_inputs = len(trimmed)
        if point.ndim == 1:
            point = point[np.newaxis, :]
        if quantiles.ndim == 2:
            quantiles = quantiles[np.newaxis, :, :]
        if point.shape[0] != n_inputs or quantiles.shape[0] != n_inputs:
            raise RuntimeError(
                f"Model output batch size mismatch: "
                f"inputs={n_inputs}, point.shape={point.shape}, quantiles.shape={quantiles.shape}"
            )

        results = []
        for i, arr in enumerate(trimmed):
            results.append(
                ForecastResult(
                    point=point[i],
                    quantiles=quantiles[i],
                    horizon=horizon,
                    input_length=len(arr),
                    model_name=self.model_name,
                    metadata={"device": self.device},
                )
            )
        return results

    def forecast_single(
        self,
        series: np.ndarray | List[float],
        horizon: int,
    ) -> ForecastResult:
        """Convenience wrapper for a single series."""
        return self.forecast([series], horizon)[0]

    @classmethod
    def get(cls, **kwargs) -> "TimesFMClient":
        """Return the shared singleton instance."""
        return cls(**kwargs)

    @classmethod
    def reset(cls):
        """Drop the singleton (useful in tests or for memory cleanup)."""
        cls._instance = None


# Default cached client accessor for use across adapters.
@lru_cache(maxsize=1)
def default_client() -> TimesFMClient:
    return TimesFMClient.get()
