# TimesFM Workspace Wrapper

A workspace-native wrapper around [Google Research TimesFM 2.5](https://github.com/google-research/timesfm) for Dario's OpenClaw environment.

## What was done

1. Cloned `google-research/timesfm` into `/home/dario/.openclaw/workspace/timesfm`.
2. Created a dedicated Python 3.14 virtual environment at `timesfm/venv`.
3. Installed PyTorch 2.12 (CUDA 12.6) + TimesFM 2.0.1 editable install.
4. Verified the official sanity test: model loads from Hugging Face, runs on the RTX 3070 Ti, and produces point + quantile forecasts.
5. Built `timesfm_wrapper/` — a reusable, singleton-backed client with adapters for LeadSignal and OEW/Phase4, plus a FastAPI router and CLI.

## Quick start

```bash
# From anywhere in the workspace, run via launcher
python run_timesfm.py timesfm_wrapper.examples.sample_forecast

# CLI forecast from CSV
python run_timesfm.py timesfm_wrapper.cli forecast data/prices.csv --horizon 12 --column close --output forecast.json

# Health check
python run_timesfm.py timesfm_wrapper.cli health
```

## Python API

```python
from timesfm_wrapper import TimesFMClient

client = TimesFMClient.get()
result = client.forecast_single([10, 12, 14, 13, 15, 18, 20], horizon=3)
print(result.point)      # array of 3 point forecasts
print(result.quantiles)  # (3, 10) mean + 10th-90th quantiles
```

## Project structure

```
timesfm_wrapper/
├── timesfm_client.py          # Singleton model wrapper
├── api.py                     # FastAPI /forecast + /forecast/batch + /health
├── cli.py                     # typer CLI: forecast / health / serve
├── adapters/
│   ├── generic.py             # CSV/JSON/NPY loader + forecaster
│   ├── leadsignal_adapter.py  # Aggregate Signal rows by category and forecast
│   └── oew_adapter.py         # Price/volume/event-rate forecasts for OEW
├── examples/                  # Sample usage scripts
├── tests/                     # Unit tests
└── requirements.txt           # Wrapper-level deps (fastapi, pandas, uvicorn, etc.)
```

## Integration ideas

- **LeadSignal backend**: mount `timesfm_wrapper.api.router` under the FastAPI app to expose `/timesfm/forecast` endpoints for dashboard trend charts.
- **OEW/Phase4**: use `OEWForecaster` in cron jobs to forecast incident rates, price series, or anomaly scores.
- **Heartbeat checks**: add a lightweight forecast health check that samples a saved series and confirms model inference completes in <N seconds.

## Hardware notes

- CUDA is available (RTX 2070 + RTX 3070 Ti); the model currently loads on the first available GPU.
- The 200M model uses ~1 GB VRAM at inference time and is fast enough for real-time cron usage.
