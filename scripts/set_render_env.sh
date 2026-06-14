#!/bin/bash
set -e
TOKEN=$(grep '^RENDER_API_TOKEN=' /home/dario/.openclaw/workspace/leadsignal/.env.render | cut -d= -f2)
SRV=srv-d8n8df6rnols73dea2sg

# Required runtime env vars
for KEY in PYTHON_VERSION SECRET_KEY DATABASE_URL SYNC_DATABASE_URL; do
    case $KEY in
        PYTHON_VERSION) VAL="3.12.0" ;;
        DATABASE_URL) VAL="sqlite+aiosqlite:///./leadsignal.db" ;;
        SYNC_DATABASE_URL) VAL="sqlite:///./leadsignal.db" ;;
        SECRET_KEY) VAL="$(openssl rand -hex 32)" ;;
    esac
    curl -s --max-time 20 -X PUT "https://api.render.com/v1/services/$SRV/env-vars" \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"key\":\"$KEY\",\"value\":\"$VAL\"}" | python3 -m json.tool | head -n 20
    echo "--- set $KEY ---"
done
