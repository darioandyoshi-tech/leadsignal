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

Result: endpoint returns a list of trend forecasts, one per signal category (`hiring_spike`, `business_license`, `parcel_change`, etc.), each with `point_forecast` and `quantiles` arrays.

With the resident microservice (`TIMESFM_URL=http://127.0.0.1:8001`), the endpoint responds in ~1.5 s. Without it, the subprocess fallback takes ~5 s on first call.

Also tested the cron script:
```bash
python3 run_timesfm.py leadsignal/backend/scripts/daily_forecast.py --horizon 7 --bucket-days 1
```
Produced a JSON report with 7-day point + quantile forecasts for all categories.

## Dashboard UI

A new **Forecasts** tab was added to the LeadSignal dashboard (`app/page.tsx`):
- Grid of per-category trend charts
- 14-day forecast horizon with uncertainty bands
- `ForecastChart` component (`components/ForecastChart.tsx`) renders history + forecast with a vertical "Forecast" marker
- Calls `GET /forecast/signal-trends` via `getSignalTrends()` in `lib/api.ts`

Frontend builds cleanly (`npm run build`).

## Systemd service (24/7 desktop)

Installed and enabled:
```bash
sudo cp timesfm_service/timesfm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now timesfm
```

Status: `sudo systemctl status timesfm`
Logs: `journalctl -u timesfm -f`

Service runs on `http://127.0.0.1:8001`, auto-restarts on crash, uses ~1 GB RAM at idle.

## Verification

- Sanity test: passed (CUDA, correct shapes).
- Unit tests: 3 passed.
- Sample forecasts (generic, LeadSignal, OEW): all produced expected JSON output.
- CLI health check: reports `cuda_available: true`.
- TimesFM microservice: systemd service active and responding to `/health`.
- LeadSignal `GET /forecast/signal-trends`: live-tested locally via microservice in ~1.5 s.
- LeadSignal dashboard: builds with new Forecasts tab.

## Production / Render notes

- The TimesFM 200M model needs ~1 GB RAM. Render free web services (512 MB) are not suitable.
- Options for production:
  1. Keep the microservice on this desktop/GPU box and set `TIMESFM_URL` in Render env vars (requires publicly reachable URL + auth).
  2. Deploy to a GPU-capable host (RunPod, Vast.ai, AWS g4dn, etc.).
  3. Use the subprocess fallback on Render (slow but works).
- The LeadSignal backend `.env` now sets `TIMESFM_URL=http://127.0.0.1:8001` for local dev.

## Next steps (optional)

1. Secure the microservice with an API key before exposing publicly.
2. Cache daily forecasts in Redis/DB.
3. Add email/Slack alerts when a category is forecasted to spike.
4. Fine-tune on Dario-specific domain series if labeled data is collected.
