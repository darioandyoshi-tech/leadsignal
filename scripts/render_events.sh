#!/bin/bash
set -e
TOKEN=$(grep '^RENDER_API_TOKEN=' /home/dario/.openclaw/workspace/leadsignal/.env.render | cut -d= -f2)
SRV=srv-d8n8df6rnols73dea2sg
curl -s --max-time 30 "https://api.render.com/v1/services/$SRV/events" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -n 200
