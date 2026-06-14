#!/bin/bash
set -e
TOKEN=$(grep '^RENDER_API_TOKEN=' /home/dario/.openclaw/workspace/leadsignal/.env.render | cut -d= -f2)
SRV=srv-d8n8df6rnols73dea2sg
curl -s --max-time 30 -X POST "https://api.render.com/v1/services/$SRV/deploys" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' | python3 -m json.tool | head -n 40
