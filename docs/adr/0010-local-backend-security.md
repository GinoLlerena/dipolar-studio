# ADR-0010: Security and lifecycle of the local backend (D10)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D10](../03-redesign-plan.md#3-key-decisions)

## Decision

- Loopback only, OS-assigned port, authenticated readiness handshake; per-launch secrets never in URLs, command lines or logs; on disk only in the owner-only (0600) ready file.
- Host and Origin validation, CSRF protection, side-effect-free GET, strict CSP served by the backend.
- Project-scoped file handles, bounded uploads, points, memory and jobs; supervised worker processes.

## Consequences

- M0 spike with negative tests (DNS rebinding, missing Origin, token leakage).

## Decided in M0 spike 3 (2026-11-08)

- **Browser hand-off.** `dipolar open` or `serve --open` mints a single-use launch code.
  - The code is valid for 60 s, and only the human *launch* token can mint it; tab tokens cannot.
  - The code goes into a private redirect page (mode 0600) in `browser-launch/` beside the ready
    file. That directory must be a real, user-owned directory with mode 0700, and never a symlink.
    The browser launcher receives only the page's path, so the code is never on a command line.
  - Graceful shutdown removes the instance's pages. After a SIGKILL, the next `dipolar open`
    removes expired ones.
  - The page strips the fragment and exchanges the code once, from an allowed Origin, for a tab
    token kept in `sessionStorage`.
  - Launch tokens never reach a URL.
  - Rejected: a token in the URL, an HttpOnly cookie (not port-isolated), pasting the token.
- **Threat model.** Processes of the same OS user are trusted: they can read the ready file. Other
  local users and other origins are not. A stolen code yields a tab token, revoked only by a
  restart. Keeping codes out of process arguments and other users' reach is what prevents this.
- **Instances.** An exclusive project lock makes a second `serve` exit with code 3. A stale ready
  file is removed under the lock. The authenticated `GET /api/v1/instance` handshake lets clients
  detect a stale ready file or a reused port.
- **Transport.** HTTP on loopback for the beta; stdio for the Phase 3 MCP adapter.
- **Packaging.** The page is bundled in the `dipolar-app` wheel (`tools/package/build.sh`).

## Verified by

`spikes/test_spike_d10_localhost.py`, run against the source tree and, in the `packaged` CI job,
against the installed wheel; `packages/dipolar-app/tests/test_app_auth.py`. Evidence:
[docs/spikes/m0-spikes.md](../spikes/m0-spikes.md#3-d10-localhost-security-on-a-packaged-build).
