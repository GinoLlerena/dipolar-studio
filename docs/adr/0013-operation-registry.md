# ADR-0013: One operation registry, every operation a typed tool (D13)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D13](../04-ai-ready-architecture.md#d13--one-operation-registry-every-operation-a-typed-tool)

## Decision

- Every calculation and every view action is a typed command or query declared once (name, kind, effect, summary, tier, idempotent, cost, examples).
- Python, CLI, HTTP/OpenAPI, the TypeScript client and (Phase 3) MCP are generated from it; there is no private UI API.
- Typed quantities and IDs; structured errors with code, message, offending field and hint; committed registry snapshot.

## M0 spike 2 (2026-11-08)

- The dispatcher validates every adapter's input in strict JSON mode: no type coercion, finite
  numbers only. The HTTP adapter parses strict RFC 8259 JSON (no NaN/Infinity, no duplicate keys,
  UTF-8 only).
- Wire integers stay within 2⁵³ − 1.
- The snapshot publishes the success and error envelopes, including every error code.

## Verified by

Registry snapshot and contract tests (M0 slice onward); `spikes/test_spike_json_serialization.py`
checks every schema, example, result and error code with the independent `jsonschema` validator.
