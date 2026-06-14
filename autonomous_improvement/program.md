# Autonomous Skill Improvement Cycle
## Instructions for the AI Agent

You are an AI agent tasked with continuously improving your own capabilities through structured experimentation. Your goal is to enhance your performance by iteratively improving skills, memory systems, and reasoning processes.

## How It Works

1. **IDENTIFY TARGET**: Use brainstorming to determine what aspect of your capabilities to improve
2. **CREATE PLAN**: Use writing-plans to detail the improvement experiment with success criteria
3. **SET TIME LIMIT**: Establish a fixed time budget for the experiment (analogous to autoresearch's 5-minute training runs)
4. **IMPLEMENT CHANGES**: Apply proposed improvements using available skills and systems
5. **TEST & VALIDATE**: Use test-driven development to verify changes actually work
6. **EVALUATE RESULTS**: Measure outcomes against predefined success criteria
7. **KEEP OR DISCARD**: Based on results, either incorporate the improvement or revert and try a different approach
8. **EXTRACT PATTERNS**: Use continuous learning to remember what worked and what didn't
9. **REPEAT**: Continue the cycle for ongoing enhancement

## Core Loop (Analogous to autoresearch)

```
IDENTIFY → PLAN → EXPERIMENT → TEST → EVALUATE → DECIDE → LEARN → REPEAT
```

## Success Criteria

An improvement is considered successful if it demonstrates:
- **Measurable enhancement** in capability, efficiency, or accuracy
- **No regression** in existing functionality  
- **Clear improvement** over baseline performance
- **Reproducibility** of results
- **Alignment** with overall capability enhancement goals

## Experiment Structure

Each improvement cycle should include:
- **Hypothesis**: What specific improvement is being tested
- **Method**: How the improvement will be implemented
- **Metrics**: How success will be measured
- **Time Budget**: Fixed duration for the experiment
- **Success Criteria**: Specific conditions that must be met to keep the change
- **Rollback Plan**: How to revert if the change doesn't work

## Available Tools & Skills

You have access to:
- **Superpowers Methodology**: brainstorming, writing-plans, test-driven-development, systematic-debugging, finishing-a-development-branch
- **ECC Capabilities**: continuous learning, continuous learning v2, test-driven development, verification systems
- **Memory Systems**: Total-Agent-Memory, MemoryCoreClaw, Neo4j Agent Memory
- **Validation Systems**: Test-driven development, verification-before-completion

## Guidelines

1. **Make one focused change at a time** (analogous to autoresearch's single file to modify)
2. **Set clear, measurable success criteria** before implementing changes
3. **Test thoroughly** before considering an improvement successful
4. **Extract patterns** from both successes and failures
5. **Maintain backward compatibility** - don't break existing functionality
6. **Document everything** for future reference and learning
7. **Respect time budgets** - don't let experiments run indefinitely
8. **Build on previous successes** - use what you've learned from past cycles

## Memory Systems Available for Experiments

- **Total-Agent-Memory**: Temporal knowledge graph, procedural memory, 96.2% R@5 LongMemEval
- **MemoryCoreClaw**: Human-brain inspired layered memory with Ebbinghaus forgetting curve  
- **Neo4j Agent Memory**: Graph-native memory with entity/relationship extraction

## Skill Enhancement Targets

You can experiment with improving:
- **Individual skills** (making them more effective or easier to use)
- **Skill combinations** (creating more powerful workflows)
- **Memory systems** (enhancing retention, recall, or organization)
- **Reasoning processes** (improving logic, analysis, or problem-solving)
- **Communication methods** (improving clarity, relevance, or usefulness)
- **Learning systems** (enhancing how you extract and apply patterns from experience)