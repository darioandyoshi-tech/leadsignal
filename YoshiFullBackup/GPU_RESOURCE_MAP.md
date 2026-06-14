# GPU_RESOURCE_MAP.md - VRAM Allocation Strategy

## Hardware Inventory
- **GPU 0 (RTX 3060 Ti):** 8GB VRAM $\rightarrow$ "The Utility Engine"
- **GPU 1 (RTX 5080):** 16GB VRAM $\rightarrow$ "The Strategic Brain"

## Allocation Logic
To maximize throughput and eliminate communication lag, the following mapping is enforced:

### 1. The Strategic Brain (GPU 1 - 5080)
- **Primary Role:** Complex reasoning, business strategy, deep coding, and high-parameter LLMs.
- **Assigned Models:** `llama3.1:8b` (Standard Strategic), `qwen3.6:35b` (Deep Analyst - shared).
- **Constraint:** Reserved for tasks requiring high epistemic accuracy and complex logic.

### 2. The Utility Engine (GPU 0 - 3060 Ti)
- **Primary Role:** Fast summarization, embedding generation, vector database indexing, and system monitoring.
- **Assigned Models:** Small, fast models (e.g., Phi-3, Mistral-7B-quantized).
- **Constraint:** Handle all "pre-processing" tasks to keep the 5080's VRAM clear for the final output.

## Operational Rules
- **No Spillover:** Prevent small models from occupying 5080 VRAM unless the task explicitly requires high-parameter reasoning.
- **Persistence:** Both cards are in Persistence Mode to ensure 0ms warm-up.
- **Verification:** Every AI task must be routed via this map before execution.

---
*LEV: Learn Evolve Improve*
*Verified: 2026-06-07*
