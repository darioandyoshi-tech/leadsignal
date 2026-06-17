"""Example: forecast a synthetic series and print results."""

import json
import numpy as np
from timesfm_wrapper import TimesFMClient

if __name__ == "__main__":
    client = TimesFMClient.get()

    # Synthetic seasonality + trend
    t = np.arange(200)
    series = 100 + 0.5 * t + 10 * np.sin(2 * np.pi * t / 30.0) + np.random.normal(0, 3, size=200)
    series = np.asarray(series, dtype=float).ravel()
    print("DEBUG series shape:", series.shape, "len:", len(series), file=__import__("sys").stderr)

    result = client.forecast_single(series, horizon=14)
    print(json.dumps(result.to_dict(), indent=2))
