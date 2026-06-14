# REASONING_BANK.md - HIVE Self-Evolving Memory System

## Purpose
Implement **ReasoningBank** (Google Research, ICLR 2026) as the core self-improving memory layer for the HIVE.

## Core Principle
The HIVE does not just store successful trajectories. It **distills generalizable reasoning strategies** from both successes and failures.

## Memory Item Structure

Each ReasoningBank entry contains:

- **Title**: Concise name of the reasoning pattern
- **Description**: High-level summary of the strategy
- **Reasoning Steps**: Key decision logic and rationale
- **Pitfalls to Avoid**: Common failure modes identified
- **Source Task**: Reference to the original mission (with locator anchor)
- **Outcome**: Success / Partial / Failure + key metrics
- **Tags**: Domain, Node, Complexity level

## Workflow

1. **Retrieve** relevant memories before starting a task
2. **Execute** the task using retrieved patterns
3. **Reflect** (LLM-as-judge) on what worked and what didn’t
4. **Distill** new reasoning items from the experience
5. **Append** distilled items back to the ReasoningBank

## Integration Points

- **HIVE_OPERATING_SYSTEM.md** — LEV Capture Protocol now uses ReasoningBank
- **HIVE_ORCHESTRATION.md** — All Nodes contribute to and query the ReasoningBank
- **Verification Gates** — Gate 4.5 requires ReasoningBank reflection before final output

## Implementation Status

- [x] ReasoningBank structure defined
- [ ] Core retrieval + distillation skill implemented
- [ ] Integration with existing LEV Capture
- [ ] Cross-Node shared ReasoningBank established

---
*Source*: ReasoningBank (arXiv:2509.25140)
*Adopted*: 2026-06-08
*Status*: Active