from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, billing, signals, alert_engine, admin, forecast, screen
from app.db import Base, engine

app = FastAPI(title="LeadSignal", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"status": "ok", "service": "LeadSignal API"}


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(signals.router)
app.include_router(screen.router)
app.include_router(alert_engine.router)
app.include_router(admin.router)
app.include_router(forecast.router)
