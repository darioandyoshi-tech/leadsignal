# TimesFM Integration — Implementation Notes

**Date:** 2026-06-17  
**Model:** TimesFM 2.5 200M (PyTorch)  
**Repo:** `https://github.com/google-research/timesfm` cloned to `./timesfm`

## What was installed

- Cloned `google-research/timesfm` into `/home/dario/.openclaw/workspace/timesfm`.
- Created a dedicated Python 3.14 virtual environment at `timesfm/venv`.
- Installed PyTorch 2.12 (CUDA 12.6) and `timesfm==2.0.1` editable install.
- Verified official inference on the RTX 3070 Ti: point + quantile forecasts shape `(B, H)` and `(B, H, 10)`.

## Wrapper: `timesfm_wrapper/`

A reusable workspace module was created:

| File | Purpose |
|------|---------|
| `timesfm_client.py` | Singleton TimesFM client, lazy load, handles numpy/torch outputs, input list mutation quirk, batch dimension normalizing |
| `adapters/generic.py` | Load CSV/JSON/NPY and forecast |
| `adapters/leadsignal_adapter.py` | Aggregate LeadSignal rows by category and forecast volumes |
| `adapters/oew_adapter.py` | Price / volume / event-rate forecasts for OEW |
| `api.py` | FastAPI router: `POST /forecast`, `POST /forecast/batch`, `GET /health` |
| `cli.py` | Typer CLI: `forecast`, `health`, `serve` |
| `examples/` | Sample usage for generic, LeadSignal, and OEW cases |
| `tests/test_client.py` | Unit tests (singleton, shape checks) |

## Integration points

### LeadSignal
- New backend router: `leadsignal/backend/app/routers/forecast.py`
  - `GET /forecast/signal-trends?horizon_days=7&bucket_days=1`
  - Delegates to the TimesFM wrapper subprocess via `run_timesfm.py` so the backend venv does not need the heavy torch stack.
- New cron script: `leadsignal/backend/scripts/daily_forecast.py`
  - Reads all signals from the configured DB and emits a JSON trend report.
- `leadsignal/backend/app/main.py` updated to include the forecast router.

### OEW / Phase4
- New adapter: `phase4-ssm-leap/integrations/timesfm_oew_adapter.py`
  - `forecast_incident_rate(timestamps, bucket_minutes, horizon)`
  - `forecast_price_trend(prices, horizon)`
  - `forecast_volume_trend(volumes, horizon)`
- Example: `timesfm_wrapper/examples/oew_forecast_example.py`

## Launcher

`run_timesfm.py` at workspace root activates `timesfm/venv` automatically:

```bash
python3 run_timesfm.py timesfm_wrapper.examples.sample_forecast
python3 run_timesfm.py timesfm_wrapper.cli health
python3 run_timesfm.py timesfm_wrapper.cli forecast data.csv --horizon 12 --column close
python3 run_timesfm.py leadsignal/backend/scripts/daily_forecast.py --horizon 7
```

## Known quirks

- TimesFM's `forecast()` mutates the `inputs` list in-place (appends metadata arrays). The wrapper passes a copy to avoid corrupting the caller's data.
- The model returns numpy arrays directly in this version, but the wrapper also handles torch tensors for compatibility.
- Python 3.14 + PyTorch 2.12 installed cleanly; no issues encountered.

## Deployment considerations

- For Render/Fly, the backend either needs the same `timesfm/venv` installed in the container, or the forecast endpoint should call a separate TimesFM microservice.
- The current `/forecast/signal-trends` endpoint spawns the wrapper via subprocess. This works locally but adds ~3–5 s cold-start for model load. Keeping the model resident in a microservice would be faster.

## Live endpoint test (local dev)

Tested on `http://127.0.0.1:8123` with seeded sample data:

```bash
curl -s 'http://127.0.0.1:8123/forecast/signal-trends?horizon_days=7&bucket_days=1' | python3 -m json.tool
```

Result: endpoint returns a list of trend forecasts, one per signal category (`hiring_spike`, `business_license`, `parcel_change`, etc.), each with `point_forecast` and `quantiles` arrays. First request took ~5 s because the TimesFM model loads; subsequent calls are faster.

Also tested the cron script:
```bash
python3 run_timesfm.py leadsignal/backend/scripts/daily_forecast.py --horizon 7 --bucket-days 1
```
Produced a JSON report with 7-day point + quantile forecasts for all categories.

## Verification

- Sanity test: passed (CUDA, correct shapes).
- Unit tests: 3 passed.
- Sample forecasts (generic, LeadSignal, OEW): all produced expected JSON output.
- CLI health check: reports `cuda_available: true`.
- LeadSignal `GET /forecast/signal-trends`: live-tested locally and working.

## Next steps (optional)

1. Add a dedicated TimesFM microservice with a persistent model worker.
2. Add dashboard UI trend charts consuming `/forecast/signal-trends`.
3. Cache daily forecast results in Redis/DB to avoid recomputation.
4. Fine-tune on Dario-specific domain series if labeled data is collected.
