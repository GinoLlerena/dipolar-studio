# ADR-0010: Security and lifecycle of the local backend (D10)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D10](../03-redesign-plan.md#3-key-decisions)

## Decision

- Loopback only, OS-assigned port, authenticated readiness handshake; per-launch secret never in URLs, logs or files.
- Host and Origin validation, CSRF protection, side-effect-free GET, strict CSP served by the backend.
- Project-scoped file handles, bounded uploads, points, memory and jobs; supervised worker processes.

## Consequences

- M0 spike with negative tests (DNS rebinding, missing Origin, token leakage).

## Decided in M0 spike 3 (2026-11-08)

- **Browser hand-off.** `dipolar open` or `serve --open` mints a single-use launch code (60 s, human
  launch credential only) and opens `/#launch=<code>`. The page strips the fragment and exchanges
  the code once, from an allowed Origin, for a tab token kept in `sessionStorage`. Launch tokens
  never reach a URL. Rejected: a token in the URL, an HttpOnly cookie (not port-isolated), paste.
- **Instances.** An exclusive project lock makes a second `serve` exit with code 3. A stale ready
  file is removed under the lock. The authenticated `GET /api/v1/instance` handshake lets clients
  detect a stale ready file or a reused port.
- **Transport.** HTTP on loopback for the beta; stdio for the Phase 3 MCP adapter.
- **Packaging.** The page is bundled in the `dipolar-app` wheel (`tools/package/build.sh`).

## Verified by

`spikes/test_spike_d10_localhost.py`, run against the source tree and, in the `packaged` CI job,
against the installed wheel; `packages/dipolar-app/tests/test_app_auth.py`. Evidence:
[docs/spikes/m0-spikes.md](../spikes/m0-spikes.md#3-d10-localhost-security-on-a-packaged-build).
