
# LeadSignal Backend

FastAPI + SQLAlchemy + Alembic + Stripe.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in DB, Stripe, API keys
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```
