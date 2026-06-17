"""Unit tests for the TimesFM wrapper client."""

import unittest
import numpy as np
from timesfm_wrapper.timesfm_client import TimesFMClient


class TestTimesFMClient(unittest.TestCase):
    def test_singleton(self):
        a = TimesFMClient.get()
        b = TimesFMClient.get()
        self.assertIs(a, b)

    def test_forecast_shape(self):
        client = TimesFMClient.get()
        series = np.linspace(0, 1, 100)
        result = client.forecast_single(series, horizon=6)
        self.assertEqual(result.point.shape, (6,))
        self.assertEqual(result.quantiles.shape, (6, 10))
        self.assertEqual(result.horizon, 6)

    def test_batch_forecast_shape(self):
        client = TimesFMClient.get()
        results = client.forecast(
            [np.linspace(0, 1, 50), np.sin(np.linspace(0, 10, 80))],
            horizon=8,
        )
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.point.shape, (8,))


if __name__ == "__main__":
    unittest.main()
