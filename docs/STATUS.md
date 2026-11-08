# Status

**Phase 1, milestone M0: steps 1–3 of 5 are complete.** The next step is step 4, the spikes.

## Done

- **Step 1, foundations.**
  - The uv workspace and the web/ package.
  - CI with three jobs (Python, Web, Legacy goldens).
  - ADRs 0001–0020.
  - The legacy goldens in `tools/legacy-harness/`.
- **Step 2, frozen fixtures.** The expected answers in `datasets/*/expected/` were produced by the
  independent reference in `tools/reference/`. Stopping point: tag `m0-step2`.
- **Step 3, the vertical slice.** `fit.preview` and `view.select` run end to end:
  - through one typed dispatcher, then policy, then the session (separate science and workspace
    revisions), then the journal;
  - over the Python adapter (`LocalClient`) and the HTTP adapter (`dipolar serve`);
  - from a minimal browser page (`web/`) and from the robot (`tools/robot/robot.py`, which uses
    only the standard library and runs under `python -I`).

  | Piece | Where |
  |---|---|
  | Forward model, biphenyl template, whitened SVD inner solve, validity flags | `packages/dipolar-core/src/dipolar_core/` |
  | Registry and dispatcher, policy matrix, session, journal, operations | `packages/dipolar-app/src/dipolar_app/` |
  | Registry contract snapshot (version 0.1.0) | `packages/dipolar-app/registry.snapshot.json` |
  | Tests | `packages/*/tests/`, `tests/test_boundaries.py` (75 tests) |

### What the slice demonstrates

- **Science.** `fit.preview` at the frozen optimum reproduces the frozen fixture: Szz, Δ, χ² and
  all 14 predictions agree to about 10⁻¹³, far inside the frozen tolerances. The same values come
  back through Python, through HTTP and from the robot.
- **Contract.** The Python and HTTP adapters return identical envelopes for a 10-call sequence,
  including the error cases. The HTTP registry equals the committed snapshot.
- **Policy.** Identity and tier come only from the credential:
  - a `read` token cannot write the view;
  - a `propose` token gets `PROPOSAL_REQUIRED` for science changes;
  - `actor` or `tier` fields in a request change nothing.
- **Revisions.** A view change never moves the science revision or the science hash. A stale
  `expected_science_revision` returns `REVISION_CONFLICT` and nothing changes. Reopening a project
  clears the selection in the same transaction.
- **Journal.**
  - Each accepted command is one checksummed, fsynced JSON Lines record.
  - Replay reproduces the science hash and the revisions, and a new process resumes from the
    journal.
  - A tampered or torn journal is refused.
- **Localhost controls.**
  - Loopback only, on an OS-assigned port.
  - The tokens are in a mode-0600 ready file; they are never printed and never put in URLs the
    server sees.
  - Host and Origin allow-lists: a foreign Host gets 421, which is the DNS-rebinding defence.
  - A bearer token on every API call, JSON content type only, a 1 MiB body limit, no side effects
    on GET, and a strict CSP.
- **Browser.** Checked by hand in Chromium (Playwright):
  - open the example, preview, select a row;
  - the robot's selection then appeared on the page;
  - the old preview was marked stale after the robot reopened the project.

### Deliberate limits of the slice (each is planned work)

- **Three supporting operations.** `project.open_example`, `project.describe` and
  `render.describe_view` exist so the slice can run end to end. Each is in the registry like any
  other operation.
- **What `fit.preview` is.** It is the profile objective at a fixed φ: the order parameters are
  re-solved, and it is not a fit. The full D3 stack (grid, then refinement, intervals, full
  Jacobian) is M1.
- **Browser token hand-off.** It is provisional: the page asks for the token, or reads it from the
  URL fragment. **Deciding this is the D10 spike.**
- **Deferred to M2, as the plan says:** idempotency keys, dry run, proposals, undo and the event
  stream. The page polls `render.describe_view` every 2 s until the event stream exists.
- **Damaged journals.** A damaged journal is refused, never repaired. Recovery is the journal
  spike.
- **The TypeScript client.** Its types are hand-written. M2 generates them from the registry.

## Resume here: M0 step 4, the spikes

Each spike passes or fails with evidence (plan §8, M0).

1. **D3 numerical controls.** Rank-changing and planar controls, and the grid-then-refine
   optimum versus `noisy_fixture.json`.
2. **JSON serialization.** Units, IDs, errors and output schemas. Started in the slice: quantities
   are `{value, unit}`, IDs are typed patterns, errors are structured.
3. **D10 localhost security.**
   - The browser token hand-off.
   - CSRF and DNS-rebinding negative tests on a packaged build.
   - Multiple instances and port reuse.
4. **Journal crash recovery.** Kill the process mid-commit, then recover by discarding a torn
   final record.

Then step 5: re-baseline the schedule.

Check the baseline before resuming:

```sh
uv sync --locked && uv run pytest -q -m "not slow"     # 75 passed
uv run ruff check . && uv run ruff format --check . && uv run mypy
(cd web && pnpm install --frozen-lockfile && pnpm build)
LEGACY=path/to/NMRApllication tools/legacy-harness/run.sh
```

## Open items for the owner

- Approve plan v0.6 formally (the "go" started M0).
- Supply the thesis PDF. It is needed for B55/D4, the ρ formula and Phase 2 V3/V6.
- Get Di Pietro's permission to redistribute the 8CB couplings.
- Decide whether Marco Idrogo should be listed as a co-author of the new software in
  `CITATION.cff`.

## Known minor issue

- GitHub Actions warns that `actions/checkout@v4` and the setup actions run on the deprecated
  Node 20. Bump them in a small CI commit.
