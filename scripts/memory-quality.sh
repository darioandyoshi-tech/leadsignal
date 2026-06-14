#!/bin/bash
# Memory Quality Checker
# Usage: ./memory-quality.sh

MEMORY_FILE="/home/dario/.openclaw/workspace/MEMORY.md"

if [ ! -f "$MEMORY_FILE" ]; then
    echo "Error: MEMORY.md not found at $MEMORY_FILE"
    exit 1
fi

echo "=== MEMORY QUALITY CHECK ==="
echo ""
echo "File: $MEMORY_FILE"
echo "Last Modified: $(date -r "$MEMORY_FILE")"
echo ""
echo "Statistics:"
echo "- Lines: $(wc -l < "$MEMORY_FILE")"
echo "- Words: $(wc -w < "$MEMORY_FILE")"
echo "- Characters: $(wc -m < "$MEMORY_FILE")"
echo ""
echo "Sections Found:"
grep -n "^## " "$MEMORY_FILE"
echo ""
echo "Recent Activity (last modified files in memory/):"
ls -lt /home/dario/.openclaw/workspace/memory/*.md | head -5
echo ""
echo "Recommendations:"
echo "1. Review for outdated information (older than 6 months typically)"
echo "2. Check for duplicate or redundant entries"
echo "3. Verify technical details are still accurate"
echo "4. Consider reorganizing if sections have grown too large"
echo "5. Ensure all entries follow the format:"
echo "   ## [CATEGORY] - [DATE]"
echo "   - **Key Insight**: [Specific knowledge]"
echo "   - **Context**: [Situation]"
echo "   - **Application**: [How to use]"
echo "   - **Source**: [Reference to session/log]"
echo ""
echo "Quick Format Check:"
echo "Entries following recommended format:"
grep -A 3 "^## " "$MEMORY_FILE" | grep -E "(\*\*Key Insight\|\*\*Context\|\*\*Application\|\*\*Source)" | head -10
echo ""
echo "If the above shows good format coverage, your MEMORY.md is well-structured!"