
from fastapi import FastAPI
from app.routers import auth, billing, signals, alert_engine
from app.db import Base, engine

app = FastAPI(title="LeadSignal", version="0.1.0")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Use Alembic in production; create_all is fine for MVP local dev
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(signals.router)
app.include_router(alert_engine.router)
