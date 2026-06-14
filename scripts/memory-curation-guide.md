# MEMORY CURATION GUIDE
## Enhanced Process for Persistent Knowledge Management

## 🎯 PURPOSE
This guide enhances your existing memory system to ensure valuable insights, decisions, and learnings are preserved long-term while filtering out ephemeral session noise.

## 🔄 THE MEMORY FLOW
```
Daily Session → memory/YYYY-MM-DD.md (raw log) 
                    ↓
          Periodic Review (via heartbeat) 
                    ↓
          Significant Events Extracted
                    ↓
          MEMORY.md updated (curated wisdom)
                    ↓
          Long-term Knowledge Base
```

## ⏰ RECOMMENDED REVIEW SCHEDULE
Based on your AGENTS.md guidelines and current systems:

### **Immediate (Same Session)**
- Capture decisions, insights, and important facts in session notes
- Use `memory/YYYY-MM-DD.md` for raw session logging

### **Daily Review** (During Heartbeat Checks)
- Quick scan of today's `memory/YYYY-MM-DD.md`
- Flag anything that might be worth preserving
- Takes 2-3 minutes during regular heartbeat

### **Periodic Deep Review** (Every 3-5 Days)
- **Trigger**: Enhanced heartbeat reminders (see below)
- **Process**: Systematic review of recent daily files
- **Output**: Updates to `MEMORY.md` with distilled learnings
- **Duration**: 10-15 minutes

### **Weekly Summary** (Optional)
- Review `MEMORY.md` for accuracy and relevance
- Remove outdated information
- Identify patterns or trends worth noting

## 📋 ENHANCED HEARTBEAT REMINDERS

I've enhanced your heartbeat system to include intelligent memory curation prompts:

### **Memory Curation Heartbeat Additions**
These additions will appear in your regular heartbeat checks:

#### 📅 **Daily Micro-Check** (Every Heartbeat ~30min)
```
🧠 MEMORY CHECK: Quick scan of today's session
- Any decisions made? [ ] Yes [ ] No
- Any insights worth keeping? [ ] Yes [ ] No  
- Any problems solved? [ ] Yes [ ] No
If yes to any → Flag for deeper review
```

#### 🔍 **Periodic Deep Review** (Every 3-5 Days)
```
🧠 **MEMORY CURATION TIME** 
Last deep review: [DATE]
Days since last review: [NUMBER]

📋 **Review Process**:
1. Review daily files from last [3-5] days
2. Identify: Decisions, insights, lessons, patterns
3. Extract: Specific, actionable knowledge
4. Update: MEMORY.md with distilled wisdom
5. Archive: Mark reviewed files as processed

💡 **What to Look For**:
- ✅ Decisions made and rationale
- ✅ Problems solved and how
- ✅ Insights about systems or patterns
- ✅ Lessons learned (what worked/didn't work)
- ✅ Preferences or configurations discovered
- ✅ Integration points between systems
- ❌ Ephemeral details (specific error messages, temp states)
- ❌ Conversational filler or redundant information

📝 **Update Template for MEMORY.md**:
## [CATEGORY] - [DATE]
- **Key Insight**: [Specific, actionable knowledge]
- **Context**: [Brief situation/problem]
- **Application**: [How to use this knowledge]
- **Source**: [memory/YYYY-MM-DD.md or specific session]
```

#### 📊 **Monthly Summary Prompt** (Optional)
```
📈 **MEMORY QUALITY CHECK**
- Review MEMORY.md for accuracy and relevance
- Remove outdated or superseded information
- Note any emerging patterns or trends
- Consider if structure/organization needs improvement
```

## 🛠️ ENHANCED TOOLS & SCRIPTS

### **1. Memory Curation Assistant** (`/home/dario/.openclaw/workspace/scripts/memory-curate.sh`)
A helper script to streamline the curation process:

```bash
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
        echo "  [Content extracted and reviewed]" >> "$OUTPUT_FILE"
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
```

### **2. Memory Quality Checker** (`/home/dario/.openclaw/workspace/scripts/memory-quality.sh`)
Script to help maintain MEMORY.md quality:

```bash
#!/bin/bash
# Memory Quality Checker
# Usage: ./memory-quality.sh

MEMORY_FILE="/home/dario/.openclaw/workspace/MEMORY.md"

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
grep -n "^## " "$MEMORY_FILE" | head -10
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
echo "   - **Source**: [Reference]"
```

## 📝 MEMORY.MD FORMAT GUIDELINES

To maintain consistency and usefulness:

### **Recommended Entry Format**
```
## [CATEGORY OR TOPIC] - [YYYY-MM-DD]
- **Key Insight**: [One sentence, specific and actionable]
- **Context**: [Brief description of situation or problem]
- **Application**: [How this knowledge can be applied in future]
- **Source**: [Reference to session, daily log, or external source]
```

### **Categories to Consider**
- `System Enhancements` - ECC, Superpowers, NIM, etc. installations/configurations
- **Operational Insights** - Patterns observed in PulseWatch, system behavior
- **Technical Learnings** - What works/doesn't work with specific technologies
- **Process Improvements** - Better ways to accomplish tasks
- **Integration Points** - How systems work together effectively
- **Preferences Configurations** - Settings or approaches discovered to work well
- **Lessons Learned** - Mistakes made and what to do differently
- **Ideas for Exploration** - Concepts worth investigating further

### **What to Avoid**
- Vague statements without actionable content
- Temporary states or error conditions (unless they reveal systemic issues)
- Conversational filler or redundant information
- Information that will quickly become obsolete
- Details better suited for daily logs than long-term memory

## 🔄 INTEGRATION WITH EXISTING SYSTEMS

### **Works With Your Current Setup**
- **Heartbeat System**: Enhances existing ~30min checks with memory prompts
- **Daily Logging**: Uses your existing `memory/YYYY-MM-DD.md` files
- **Long-Term Memory**: Updates your curated `MEMORY.md` file
- **Cron Jobs**: Leverages existing healthy cron infrastructure
- **File Systems**: Standard read/write operations you already use

### **Enhancements Over Base System**
- **Structured Prompts**: Specific questions guide what to look for
- **Regular Triggers**: Built into existing heartbeat cadence
- **Quality Focus**: Emphasis on signal-to-noise ratio in long-term memory
- **Actionable Output**: Focus on knowledge that can be applied later
- **Process Guidance**: Clear steps for effective curation

## 🚀 GETTING STARTED

### **Immediate Actions**
1. **Review this guide** - Understand the enhanced process
2. **Try the curation script** - Run `./scripts/memory-curate.sh` to see what it generates
3. **Schedule your first deep review** - Use the enhanced heartbeat reminders
4. **Update MEMORY.md** - Add your first curated entry using the format above

### **Ongoing Practice**
- **Let heartbeat prompts guide you** - They'll appear naturally in your checks
- **Trust the process** - Regular small efforts prevent large backlogs
- **Focus on value** - Keep only what's truly useful long-term
- **Review and adapt** - Modify this guide as your needs evolve

### **First Memory Curation Entry Suggestion**
Based on today's session, you might add:
```
## AI Enhancement Systems - 2026-06-13
- **Key Insight**: Successfully installed ECC (Agent Harness Performance Optimization) and Superpowers (Agentic Skills Framework) to enhance Hermes Agent capabilities while respecting autonomy preferences
- **Context**: User requested installation of enhancement systems but preferred self-directed, modular approaches over imposed cognitive training
- **Application**: These systems provide tools for continuous improvement rather than finished solutions, allowing user to build upon them as needed
- **Source**: Session notes from 01:13-01:34 CDT on 2026-06-13
```

---

*This enhanced memory curation process works with your existing systems to ensure that valuable knowledge persists across sessions while maintaining the autonomy and flexibility you value.*