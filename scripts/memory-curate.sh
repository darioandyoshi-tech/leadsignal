#!/bin/bash
# Memory Curation Assistant
# Usage: ./memory-curate.sh [days-back] [output-file]

# Defaults
DAYS_BACK=${1:-3}
OUTPUT_FILE=${2:-"/home/dario/.openclaw/workspace/MEMORY_TEMP_UPDATE.md"}
DATE=$(date +"%Y-%m-%d %H:%M CDT")

echo "# MEMORY CURATION SESSION - $DATE" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Review Period: Last $DAYS_BACK days" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Collect files to review
echo "## Files Reviewed:" >> "$OUTPUT_FILE"
for i in $(seq 0 $((DAYS_BACK-1))); do
    DATE_CHECK=$(date -d "-$i days" +"%Y-%m-%d")
    FILE="/home/dario/.openclaw/workspace/memory/${DATE_CHECK}.md"
    if [ -f "$FILE" ]; then
        echo "- $FILE" >> "$OUTPUT_FILE"
        # Show first few lines as preview
        head -3 "$FILE" | sed 's/^/  > /' >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    fi
done
echo "" >> "$OUTPUT_FILE"

# Prompt for manual curation
echo "## CURATION NEEDED:" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "Please review the files above and extract:" >> "$OUTPUT_FILE"
echo "- Significant decisions made" >> "$OUTPUT_FILE"
echo "- Important insights or learnings" >> "$OUTPUT_FILE" 
echo "- Problems solved and solutions"
echo "- Patterns or trends observed"
echo "- Preferences or configurations discovered"
echo "" >> "$OUTPUT_FILE"
echo "Add extracted knowledge to MEMORY.md using the format:" >> "$OUTPUT_FILE"
echo "## [CATEGORY] - [DATE]" >> "$OUTPUT_FILE"
echo "- **Key Insight**: [Specific, actionable knowledge]" >> "$OUTPUT_FILE"
echo "- **Context**: [Brief situation/problem]" >> "$OUTPUT_FILE"
echo "- **Application**: [How to use this knowledge]" >> "$OUTPUT_FILE"
echo "- **Source**: [Reference to session/log]" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "💡 TIP: Look for content that answers 'What should I remember about this period?'"