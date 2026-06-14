#!/bin/bash
# Daily Cognitive Enhancement Schedule
# Automated routine for consistent brain training and memory utilization

echo "🧠 Starting Daily Cognitive Enhancement Routine - $(date)"
echo "========================================================"

# Start MCP servers if not already running
if [ ! -f /tmp/claude-flow-mcp.pid ] || ! kill -0 $(cat /tmp/claude-flow-mcp.pid) 2>/dev/null; then
    echo "🚀 Starting MCP servers..."
    ./start-mcp-servers.sh
else
    echo "✅ MCP servers already running"
fi

echo ""
echo "📋 DAILY ENHANCEMENT ROUTINE:"
echo "1. Cognitive Training Session"
echo "2. Memory Insight Storage"
echo "3. Progress Tracking"
echo ""

# 1. COGNITIVE TRAINING SESSION
echo "🏃‍♂️ Starting cognitive training..."
# Run a quick training session - you can extend this time as desired
timeout 60s node cognitive-training-system.js << 'EOF'
6
1
2
3
4
5
7
EOF

echo ""
echo "💾 STORING DAILY INSIGHTS..."
# Store today's cognitive session results
DAILY_INSIGHT="Daily cognitive enhancement completed on $(date). Session included all 5 training modules for baseline establishment and progressive improvement tracking."
echo "$DAILY_INSIGHT" | node enhanced-memory-system.js store daily-enhancement-$(date +%Y%m%d) -

echo ""
echo "📊 WEEKLY PROGRESS CHECK (if applicable)"
# Check if it's Sunday (day 0) for weekly review
if [ "$(date +%u)" = "7" ]; then
    echo "📅 Weekly enhancement review:"
    echo "   Retrieving weekly baseline..."
    node enhanced-memory-system.js retrieve weekly-baseline-$(date -d "last sunday" +%Y%m%d) 2>/dev/null || echo "   No previous weekly baseline found"
    echo "   Storing new weekly baseline..."
    WEEKLY_SUMMARY="Weekly cognitive enhancement summary for week ending $(date). Includes daily training sessions and incremental improvement tracking."
    echo "$WEEKLY_SUMMARY" | node enhanced-memory-system.js store weekly-baseline-$(date +%Y%m%d) -
else
    echo "📅 Daily progress tracking active"
fi

echo ""
echo "🎯 Enhancement routine complete for $(date)"
echo "💡 Tip: Consistency builds cognitive reserve over time!"
echo "========================================================"