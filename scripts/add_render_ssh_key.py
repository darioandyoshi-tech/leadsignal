#!/usr/bin/env python3
import json
import urllib.request
import urllib.error

ENV_FILE = "/home/dario/.openclaw/workspace/leadsignal/.env.render"
KEY_FILE = "/home/dario/.ssh/id_ed25519_render.pub"
SRV = "srv-d8n8df6rnols73dea2sg"

with open(ENV_FILE) as f:
    for line in f:
        if line.startswith("RENDER_API_TOKEN="):
            TOKEN = line.strip().split("=", 1)[1]
            break
    else:
        raise RuntimeError("No RENDER_API_TOKEN found")

with open(KEY_FILE) as f:
    pubkey = f.read().strip()

payload = json.dumps({"key": pubkey}).encode()
url = f"https://api.render.com/v1/services/{SRV}/ssh-keys"
req = urllib.request.Request(url, data=payload, method="POST", headers={
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
})
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("OK", resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:500])
except Exception as e:
    print("ERR", str(e)[:500])
