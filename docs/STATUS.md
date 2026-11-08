# Status: stopping point

**Paused on 2026-11-07 at tag `m0-step2`.** Phase 1, milestone M0, steps 1–2 of 5 are complete,
and CI passes on all three jobs (Python, Web, Legacy goldens).

## Done

- **Step 1, foundations.**
  - The uv workspace with `packages/dipolar-core` (pure science) and `packages/dipolar-app`
    (application layer). An import-boundary test keeps the core free of I/O and web code.
  - `web/`: React 19 and strict TypeScript on Vite (a placeholder page for now).
  - CI in `.github/workflows/ci.yml`.
  - ADRs 0001–0020 in `docs/adr/`.
  - The legacy goldens in `tools/legacy-harness/`.
- **Step 2, frozen fixtures.**
  - `datasets/*/expected/` comes from the independent reference in `tools/reference/`, which never
    uses `dipolar-core`. Each directory has a checksum manifest.
  - The synthetic fit gives φ = 36.98503°, and the 68% coverage check passes.
  - The 8CB fits give φ = 32.932° at T_red 0.930 and 33.038° at T_red 0.980.
  - 24 tests pass.

## Resume here: M0 step 3, the vertical slice

Build `fit.preview` on the synthetic biphenyl and `view.select` on one coupling. Each must pass
through the full path the plan defines (`docs/03-redesign-plan.md` §8, M0; `docs/04-ai-ready-architecture.md`):

1. a typed operation registry and dispatcher;
2. the policy check;
3. the session, with science and workspace revisions;
4. the journal.

It is then driven four ways: from Python, over HTTP (localhost), from a minimal browser page, and
from the scripted robot. The results must match `datasets/biphenyl-synthetic/expected/` within
the frozen tolerances.

After that:

- **Step 4, spikes:** the D3 numerical controls, JSON serialization (units, IDs, errors), D10
  localhost security, and journal crash recovery.
- **Step 5:** re-baseline the schedule.

Check the baseline before resuming:

```sh
uv sync --locked && uv run pytest -q -m "not slow"     # 24 passed
uv run ruff check . && uv run mypy
tools/legacy-harness/run.sh                             # needs LEGACY=path/to/NMRApllication
(cd web && pnpm install --frozen-lockfile && pnpm build)
```

## Open items for the owner

- Approve plan v0.6 formally (the "go" started M0).
- Supply the thesis PDF (needed for B55/D4, the ρ formula and Phase 2 V3/V6).
- Get permission from Di Pietro to redistribute the 8CB couplings.
- Decide whether Marco Idrogo should be listed as a co-author of the new software in
  `CITATION.cff`.

## Known minor issue

- GitHub Actions warns that `actions/checkout@v4` and the setup actions run on the deprecated
  Node 20. Bump the versions in a small CI commit.
