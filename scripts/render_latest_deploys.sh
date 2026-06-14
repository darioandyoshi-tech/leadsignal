#!/bin/bash
set -e
TOKEN=$(grep '^RENDER_API_TOKEN=' /home/dario/.openclaw/workspace/leadsignal/.env.render | cut -d= -f2)
SRV=srv-d8n8df6rnols73dea2sg
curl -s --max-time 30 "https://api.render.com/v1/services/$SRV/deploys" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
d=json.load(sys.stdin)
for dep in d[:3]:
    x=dep['deploy']
    print(x['id'], x['status'], x['commit']['message'][:60], x['createdAt'])
"