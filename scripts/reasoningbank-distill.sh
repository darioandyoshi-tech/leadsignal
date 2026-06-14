#!/bin/bash
# ReasoningBank Distillation - Run after major tasks
# Usage: ./reasoningbank-distill.sh [task_name] [outcome] [lessons]

LOG_FILE="/home/dario/.openclaw/workspace/logs/reasoningbank-distill.log"
MEMORY_FILE="/home/dario/.openclaw/workspace/memory/$(date +%Y-%m-%d).md"
REASONING_BANK="/home/dario/.openclaw/workspace/REASONING_BANK.md"

mkdir -p "$(dirname "$LOG_FILE")"

TASK_NAME="${1:-unnamed_task}"
OUTCOME="${2:-completed}"
LESSONS="${3:-}"

echo "[$(date)] Distilling: $TASK_NAME ($OUTCOME)" >> "$LOG_FILE"

# Append to daily memory
if [ -n "$LESSONS" ]; then
    echo "- **$TASK_NAME**: $LESSONS" >> "$MEMORY_FILE"
    echo "[$(date)] Added to daily memory" >> "$LOG_FILE"
fi

# Trigger ReasoningBank update (placeholder for AI distillation)
echo "[$(date)] Distillation complete for: $TASK_NAME" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
