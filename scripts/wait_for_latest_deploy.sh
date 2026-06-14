#!/bin/bash
set -e
TOKEN=$(grep '^RENDER_API_TOKEN=' /home/dario/.openclaw/workspace/leadsignal/.env.render | cut -d= -f2)
SRV=srv-d8n8df6rnols73dea2sg
for i in $(seq 1 40); do
    DEP=$(curl -s --max-time 15 "https://api.render.com/v1/services/$SRV/deploys" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['deploy']['id'])")
    STATUS=$(curl -s --max-time 15 "https://api.render.com/v1/services/$SRV/deploys/$DEP" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    echo "$(date) deploy $DEP status: $STATUS"
    if [ "$STATUS" != "build_in_progress" ] && [ "$STATUS" != "update_in_progress" ] && [ "$STATUS" != "queued" ]; then
        break
    fi
    sleep 15
done
