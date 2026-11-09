# Status

**Phase 1, milestone M0: all five steps are done.** The spikes (step 4) pass with evidence, and
the re-baseline (step 5) is a proposal awaiting the owner. Validation round 10 (GPT-6.1-Sol) returned
NOT READY with one major and six minor findings, all fixed
([docs/validation/round10-m0-spikes.md](validation/round10-m0-spikes.md)). Round 11 confirmed
those fixes but returned NOT READY on a new major problem in the redirect-page cleanup (a symlinked
directory) and three minor ones, all fixed; a round-12 confirmation follows.

Earlier stopping points: `m0-step2`, `m0-step3`.

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
  | Numerical context (part of the science hash, D11) | `packages/dipolar-core/src/dipolar_core/context.py` |
  | Tests | `packages/*/tests/`, `tests/test_boundaries.py` (83 tests at step 3) |

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
  - Each accepted command is one checksummed, fsynced JSON Lines record, written in full before
    the command is acknowledged.
  - **Fail-stop:** after any journal failure, every later command returns `JOURNAL_FAILED`
    until a restart replays the journal. Queries keep working.
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
  - the old preview was marked stale after the robot reopened the project;
  - a superseded preview that arrived late was discarded. This check is manual; automated browser
    tests arrive with M3.
- **Validation** (GPT-6.1-Sol), recorded in
  [docs/validation/round8-m0-slice.md](validation/round8-m0-slice.md):
  - **Round 8: NOT READY.** Seven findings, all fixed. Six of the fixes have automated regression
    tests; the frontend fix was checked by hand in a browser.
  - **Round 9: READY WITH MINOR CHANGES.** Both minor fixes are applied.

### Deliberate limits of the slice (each is planned work)

- **Three supporting operations.** `project.open_example`, `project.describe` and
  `render.describe_view` exist so the slice can run end to end. Each is in the registry like any
  other operation.
- **What `fit.preview` is.** It is the profile objective at a fixed φ: the order parameters are
  re-solved, and it is not a fit. The full D3 stack (grid, then refinement, intervals, full
  Jacobian) is M1.
- **Browser token hand-off.** Decided in step 4: a launch code exchanged for a tab token.
- **Deferred to M2, as the plan says:** idempotency keys, dry run, proposals, undo and the event
  stream. The page polls `render.describe_view` every 2 s until the event stream exists.
- **Damaged journals.** Settled in step 4: a torn tail is recovered, any other damage is refused,
  and a fail-stopped session needs a restart.
- **The TypeScript client.** Its types are hand-written. M2 generates them from the registry.

- **Step 4, the spikes.** Evidence, findings and decisions:
  [docs/spikes/m0-spikes.md](spikes/m0-spikes.md). Every spike is an executable module in
  `spikes/`, and CI runs them.
  1. **D3 numerical controls: pass.** M1 refines on the residual vector.
  2. **JSON serialization: pass after fixes.** Validation is strict (no type coercion), the HTTP
     JSON parser is strict, and the envelopes are published.
  3. **D10 localhost security: pass after fixes, on the installed wheel.**
     - The browser hand-off is decided: a single-use launch code, passed through a private
       redirect page (never on a command line), is exchanged for a tab token.
     - Instance lock, instance handshake, page bundled in the wheel.
     - A new `packaged` CI job.
  4. **Journal crash recovery: pass.** A torn tail is quarantined and discarded; damage is refused.
     200 SIGKILLs lost 0 acknowledged commands.
- **Step 5, re-baseline: a proposal.** [docs/rebaseline-after-m0.md](rebaseline-after-m0.md) gives
  the measured velocity, proposes the shape of M1–M3 in slice-sized steps, and sets no dates.

## Resume here: M1, after the owner approves the re-baseline

M1 step 1 is the D3 stack in dipolar-core. It grows from `spikes/test_spike_d3_numerics.py`:
- grid/Sobol multistart;
- bounded TRF refinement on the residual vector;
- full-Jacobian covariance;
- profiles versus slices;
- validity flags.

See the re-baseline for the remaining steps.

Check the baseline before resuming:

```sh
uv sync --locked && uv run pytest -q -m "not slow"     # 184 passed
uv run ruff check . && uv run ruff format --check . && uv run mypy
(cd web && pnpm install --frozen-lockfile && pnpm build)
LEGACY=path/to/NMRApllication tools/legacy-harness/run.sh
tools/package/build.sh && uv venv /tmp/pkg && uv pip install --python /tmp/pkg/bin/python dist/packages/*.whl \
  && DIPOLAR_BIN=/tmp/pkg/bin/dipolar uv run pytest spikes/test_spike_d10_localhost.py   # 32 passed
```

## Open items for the owner

- Approve or adjust the M0 re-baseline ([docs/rebaseline-after-m0.md](rebaseline-after-m0.md)),
  including logging owner hours per step from M1 onwards.
- Approve plan v0.6 formally (the "go" started M0).
- Supply the thesis PDF. It is needed for B55/D4, the ρ formula and Phase 2 V3/V6.
- Get Di Pietro's permission to redistribute the 8CB couplings.
- Decide whether Marco Idrogo should be listed as a co-author of the new software in
  `CITATION.cff`.

## Known minor issue

- GitHub Actions warns that `actions/checkout@v4` and the setup actions run on the deprecated
  Node 20. Bump them in a small CI commit.
