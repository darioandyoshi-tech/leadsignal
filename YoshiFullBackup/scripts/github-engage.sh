#!/bin/bash
# GitHub Auto-Engagement Script
# Usage: ./github-engage.sh <repo> <issue_number> <comment_text>
#    OR: ./github-engage.sh <repo> --create "<title>" "<body>"

LOG_FILE="/home/dario/.openclaw/workspace/logs/github-engagement.log"
SCRIPT_DIR="/home/dario/.openclaw/workspace/scripts"

mkdir -p "$(dirname "$LOG_FILE")"

REPO="$1"
TARGET="$2"
COMMENT="$3"

if [ -z "$REPO" ] || [ -z "$TARGET" ]; then
    echo "Usage: $0 <owner/repo> <issue_number|discussions> <comment>"
    echo "   OR: $0 <owner/repo> --create \"<title>\" \"<body>\""
    exit 1
fi

echo "[$(date)] Engaging on GitHub: $REPO #$TARGET" >> "$LOG_FILE"

# Check if creating new issue or commenting
if [ "$TARGET" = "--create" ]; then
    TITLE="$COMMENT"
    BODY="$4"
    gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY" >> "$LOG_FILE" 2>&1
    echo "[$(date)] Created issue in $REPO: $TITLE" >> "$LOG_FILE"
else
    # Comment on existing issue/discussion
    gh issue comment "$TARGET" --repo "$REPO" --body "$COMMENT" >> "$LOG_FILE" 2>&1
    echo "[$(date)] Commented on $REPO #$TARGET" >> "$LOG_FILE"
fi

echo "----------------------------------------" >> "$LOG_FILE"
