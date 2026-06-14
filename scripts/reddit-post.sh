#!/bin/bash
# Reddit Auto-Post via PRAW
# Usage: ./reddit-post.sh <subreddit> <title> <comment_text>

LOG_FILE="/home/dario/.openclaw/workspace/logs/reddit-posts.log"
SCRIPT_DIR="/home/dario/.openclaw/workspace/scripts"

mkdir -p "$(dirname "$LOG_FILE")"

SUBREDDIT="$1"
TITLE="$2"
COMMENT="$3"

if [ -z "$SUBREDDIT" ] || [ -z "$COMMENT" ]; then
    echo "Usage: $0 <subreddit> [title] <comment_text>"
    exit 1
fi

# Default title if not provided
if [ -z "$TITLE" ]; then
    TITLE="Re: Discussion"
fi

# Run Python script with PRAW
python3 "$SCRIPT_DIR/reddit-post.py" "$SUBREDDIT" "$TITLE" "$COMMENT" >> "$LOG_FILE" 2>&1

echo "[$(date)] Posted to r/$SUBREDDIT: $TITLE" >> "$LOG_FILE"
