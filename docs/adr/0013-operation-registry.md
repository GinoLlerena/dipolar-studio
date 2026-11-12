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

## M2 step 1b (2026-11-11)

- The web client's types are generated from the committed snapshot by
  `tools/codegen/ts_contract.py` into `web/src/generated/`. The generator fails closed on any
  schema feature it cannot represent exactly. CI fails if the generated files are stale.
- `callOperation` is typed by operation name: the arguments and the result follow the registry.

## Verified by

Registry snapshot and contract tests (M0 slice onward); `spikes/test_spike_json_serialization.py`
checks every schema, example, result and error code with the independent `jsonschema` validator.
`tests/test_ts_contract.py` and `web/src/contract.typetest.ts` check the generated TypeScript.
