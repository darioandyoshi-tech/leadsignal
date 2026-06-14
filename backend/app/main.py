from fastapi import FastAPI

app = FastAPI(title="LeadSignal Minimal", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "LeadSignal API is running"}
