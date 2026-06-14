#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== LeadSignal Installer ==="

# Backend
if [ ! -d backend/.venv ]; then
  echo "Creating backend venv..."
  python3 -m venv backend/.venv
fi
source backend/.venv/bin/activate
pip install -r backend/requirements.txt

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env — fill in API keys before running."
fi

# Scraper
if [ ! -d scraper/.venv ]; then
  echo "Creating scraper venv..."
  python3 -m venv scraper/.venv
fi
source scraper/.venv/bin/activate
pip install -r scraper/requirements.txt

# Frontend
cd frontend
npm install
cd ..

echo "=== Done ==="
echo "Next steps:"
echo "1. Edit backend/.env with database + Stripe + Google Places keys"
echo "2. Start Postgres + Redis"
echo "3. cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "4. cd frontend && npm run dev"
echo "5. cd scraper && source .venv/bin/activate && python run_all.py"
