# ADR-0016: Headless rendering and perception (D16)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D16](../04-ai-ready-architecture.md#d16--headless-rendering-and-perception)

## Decision

- `render.describe_view` is the primary, exact perception channel; SVG/PNG are rendered server-side from the same ViewState.
- A renderer-independent scene description with projection parity between Python and the browser.

## Verified by

Visual parity tests (M2).
