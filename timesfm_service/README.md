# TimesFM Forecast Microservice

Standalone FastAPI service that keeps the TimesFM 2.5 model loaded and warm.

## Run

```bash
./timesfm_service/run.sh
```

Service listens on `http://127.0.0.1:8001` by default.

## Endpoints

- `GET /health` — model status
- `POST /forecast` — single series forecast
- `POST /forecast/batch` — batch series forecast
- `POST /forecast/signal-trends` — LeadSignal category volume forecast

## Systemd (24/7 on desktop)

Install:
```bash
sudo cp timesfm_service/timesfm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now timesfm
```

Check:
```bash
sudo systemctl status timesfm
journalctl -u timesfm -f
```
