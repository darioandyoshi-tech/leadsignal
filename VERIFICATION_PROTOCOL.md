# VERIFICATION_PROTOCOL.md - Claim Verification & Integrity Gates

## Purpose
Extracted from Academic Research Skills (ARS) integrity gate pattern. Prevents hallucinated claims, fabricated citations, and unsupported assertions.

## Core Principles
- **Zero Hallucination** — Every claim must be traceable to a source.
- **Locator Anchors** — Every citation carries a three-layer anchor (source, section, quote).
- **Fail-Closed** — If provenance is missing or claim cannot be verified → block output.

## Locator Anchor Format
```
[CLAIM_ID: L3-2026-06-08-001]
Source: https://arxiv.org/abs/2605.07723
Section: "Results", paragraph 4
Quote: "146,932 hallucinated citations for 2025 alone"
```

## Integrity Gates

### Gate 2.5 (Pre-Write)
- Run before any substantial writing begins.
- Check: All planned claims have declared sources or "no source" flag.
- Fail if: >20% of claims are "planning to find source later".

### Gate 4.5 (Pre-Finalize)
- Mandatory audit pass before any deliverable is marked complete.
- Modes:
  - **Quick**: Spot-check 10% of claims
  - **Full**: Verify every claim against locator anchor
  - **Cross-Model**: Second model (different provider) re-validates top 20% of claims

## Claim Verification Classes
| Class | Meaning | Action |
|-------|---------|--------|
| `ALIGNED` | Claim accurately reflects source | Pass |
| `OVERSTATED` | Claim stronger than source supports | Rewrite or flag |
| `NOT_SUPPORTED` | Source does not contain the claim | Block + rewrite |
| `FABRICATED_REFERENCE` | Cited source does not exist | Hard fail |
| `ANCHORLESS` | Claim has no locator | Require anchor before proceeding |

## Implementation in HIVE
- Every Node must attach locator anchors to factual claims.
- Yoshi performs final Gate 4.5 before any external output (email, report, PR, etc.).
- Failed claims trigger LEV Capture: "Why did this claim lack provenance?"

---
*Protocol Version: 1.0 (ARS-adapted)*
*Status: Active*
*Verified: 2026-06-08*