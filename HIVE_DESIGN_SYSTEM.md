# HIVE_DESIGN_SYSTEM.md - Frontend Design Quality Layer

## Purpose
Ensure all HIVE-generated frontend work avoids common AI design slop and follows professional, timeless design principles.

## Source
Adapted from **Impeccable** (pbakaus/impeccable) — a high-quality design skill for AI agents.

## Core Principles

### Anti-Patterns to Avoid
- Overused fonts (Arial, Inter, system defaults)
- Purple-to-blue gradients
- Gray text on colored backgrounds
- Nested cards inside cards
- Bounce/elastic easing (feels dated)
- Pure black/gray (always use tinted neutrals)
- Side-tab borders and dark glows

### Reference Domains
The HIVE maintains guidance across these areas:

| Domain              | Focus Areas                              |
|---------------------|------------------------------------------|
| Typography          | Type systems, modular scales, font pairing |
| Color & Contrast    | OKLCH, tinted neutrals, dark mode, a11y   |
| Spatial Design      | Spacing systems, grids, visual hierarchy  |
| Motion Design       | Easing curves, staggering, reduced motion |
| Interaction Design  | Forms, focus states, loading patterns     |
| Responsive Design   | Mobile-first, fluid design, container queries |
| UX Writing          | Button labels, error messages, empty states |

## Recommended Commands (when doing frontend work)

- `/impeccable audit` — Technical quality checks (a11y, performance, responsive)
- `/impeccable critique` — UX design review (hierarchy, clarity, emotional resonance)
- `/impeccable polish` — Final pass and design system alignment
- `/impeccable distill` — Strip to essence, remove complexity
- `/impeccable harden` — Error handling, edge cases, i18n
- `/impeccable shape` — Plan UX/UI before writing code

## HIVE Usage Rule

When any Node (especially AWM Dev or PulseWatch Growth) produces frontend output, it must run through the Impeccable quality layer before final delivery.

---
*Source*: Impeccable by Paul Bakaus
*Status*: Adopted as HIVE Design Quality Layer
*Verified*: 2026-06-08