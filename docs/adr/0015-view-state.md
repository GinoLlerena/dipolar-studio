# ADR-0015: View state is first-class and agent-controllable (D15)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D15](../04-ai-ready-architecture.md#d15--view-state-is-first-class-and-agent-controllable)

## Decision

- ViewState (selection, focus, camera, layers, highlights, annotations, panels, active run, display units) lives in the session.
- All view changes are `view.*` commands with their own undo stack; the beta has one shared view.

## Verified by

M0 slice (`view.select`).
