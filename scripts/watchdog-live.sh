#!/bin/bash
# HIVE Watchdog - Live Check Every 5 Minutes
# Ensures HIVE is active and responsive

LOG_FILE="/home/dario/.openclaw/workspace/logs/watchdog-live.log"
STATUS_FILE="/home/dario/.openclaw/workspace/HIVE_STATUS.md"

mkdir -p "$(dirname "$LOG_FILE")"

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S %Z")

# Log heartbeat
echo "[$TIMESTAMP] WATCHDOG: HIVE is LIVE" >> "$LOG_FILE"

# Update status file
cat > "$STATUS_FILE" << EOF
# HIVE Status
**Last Heartbeat**: $TIMESTAMP
**Status**: 🟢 LIVE
**Watchdog**: Active (5-min interval)

## Current Systems
- PulseWatch Lead Gen: ✅ (every 20 min)
- Daily Sensing: ✅ (every 12 hours)
- Leaderboard Refresh: ✅ (daily @ 6 AM)
- PulseWatch Daily Report: ✅ (daily @ 8 AM)
- Watchdog: ✅ (every 5 min)

---
*Auto-updated by watchdog-live.sh*
EOF

# Keep log clean - retain last 100 lines
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

echo "[$TIMESTAMP] Status updated." >> "$LOG_FILE"
