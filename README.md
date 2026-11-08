# Dipolar Studio

**Rescuing a 1998 graduation thesis with a new, AI-assisted implementation.**

In 1998 **Gino Llerena and Marco Idrogo** wrote *Proyecto* as their joint graduation thesis,
advised by **Dr. Jaime Avalos**. It is a Windows (MFC/C++) application that determines the
**conformation** and **orientational order** (the Saupe order matrix) of molecules dissolved
in **liquid crystals** from their **NMR dipolar couplings**. The original code is preserved,
unchanged, at [GinoLlerena/NMRApllication](https://github.com/GinoLlerena/NMRApllication).

Dipolar Studio is a **new implementation** of the same scientific idea, built with current
open-source tools and developed **with AI assistance**. AI has been used throughout: to audit
the old code, to convene a panel of expert perspectives (UX, UI, NMR physics and numerics,
software architecture), to cross-validate every conclusion with an independent model, and to
write the new software. It is designed from the start so that an **AI agent** can later use the
same tools as a human to run calculations and drive the interface.

> Status: **Phase 1, milestone M0 (foundations).** The workspace, CI, decision records, frozen
> test answers and legacy goldens are in place; the end-to-end vertical slice is next.

## Why a new implementation

An audit of the 1998 code (verified by an independent AI reviewer, and with the numerical bugs
reproduced by compiling the original solvers) found **56 defects**. The physical model at its
core, the dipolar tensor contraction with correct coupling constants, is sound. But the
numerics, bookkeeping and file handling were not:

- the eigenvalue routine prints `Szz = 99` for D2 symmetry;
- the linear solver returns wrong results on one of its paths;
- the default fit tolerance accepts 1000% errors;
- there are geometry sign errors and buffer overflows.

Details: [docs/legacy/02-bug-report.md](docs/legacy/02-bug-report.md).

## What the new design does differently

- **Statistics instead of pass/fail:** weighted least squares over *all* couplings, with honest
  uncertainty, identifiability diagnostics and explicitly labelled estimands.
- **A headless engine:** every calculation and every view action is a typed operation in one
  registry, used equally by the browser UI, Python, the CLI, test robots and, later, an AI agent
  (via MCP).
- **Reproducible by construction:** stable IDs, an event log with an actor per change, immutable
  fit runs with provenance, and plain-text project files.
- **Real benchmark data:** biphenyl, synthetic with a known answer and experimental in the
  liquid crystal 8CB ([datasets/](datasets/)).

## Roadmap

| Phase | Scope |
|---|---|
| **Phase 1: foundation + scientific beta** | Python scientific core, application layer (operation registry, session, event log, view state), browser UI, biphenyl workflow: users load their own couplings (CSV) and geometry (template or XYZ). No AI code; AI readiness is proven with a scripted "robot user". |
| **Phase 2: verification** | Extends the engine beyond biphenyl to any rigid molecule from XYZ (the 1998 single phenyl ring, benzene, substituted benzenes), multi-torsion fragments (the 1998 three-ring fragment, terphenyls), further symmetry models and the ρ ring-distortion model, ²H/¹³C/¹⁹F measurement types, and conformational distributions. Implemented extensions receive known-answer verification and, where suitable data exist, experimental evaluation; the public verification report states the evidence and limitations for each. The first release is bounded (rigid molecules from XYZ); the rest are conditional extensions. |
| **Phase 3: AI integration** | An MCP adapter generated from the registry, an in-app assistant whose actions arrive as proposals for the user to approve, grounded explanations, evaluations and safety red-teaming. |

## Development

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 with pnpm.

```bash
uv sync                      # Python workspace: packages/dipolar-core, packages/dipolar-app
uv run pytest                # frozen-fixture guards and architecture boundaries
uv run ruff check . && uv run mypy
cd web && pnpm install && pnpm run build   # browser UI (strict TypeScript)
```

| Path | Contents |
|---|---|
| `packages/dipolar-core/` | Pure scientific core (no I/O, no UI) |
| `packages/dipolar-app/` | Headless application layer: registry, session, event log, view state |
| `web/` | Browser UI, a thin client of the registry |
| `datasets/*/expected/` | Frozen expected answers the engine is tested against |
| `tools/reference/` | Independent NumPy/SciPy reference that produced them |
| `tools/legacy-harness/` | The 1998 solvers compiled and compared with frozen "golden failures" |

## Documents

| Document | Purpose |
|---|---|
| [docs/03-redesign-plan.md](docs/03-redesign-plan.md) | The consolidated plan: decisions D1–D20, scope, roadmap, risks |
| [docs/04-ai-ready-architecture.md](docs/04-ai-ready-architecture.md) | The headless engine and the AI-ready architecture |
| [docs/adr/](docs/adr/) | Architecture decision records ADR-0001 to ADR-0020 (one per decision D1–D20) |
| [docs/STATUS.md](docs/STATUS.md) | Current stopping point, where to resume, and open owner items |
| [docs/legacy/](docs/legacy/) | Analysis of the 1998 application, and the bug report |
| [docs/panel/](docs/panel/) | Expert-panel inputs: UX research, UI design with an [HTML mockup](docs/panel/mockup-workspace.html), science and numerics, architecture |
| [docs/validation/](docs/validation/) | Independent validation rounds (GPT-6.1-Sol) |
| [datasets/](datasets/) | Biphenyl benchmark datasets and reference fits |
| [tools/legacy-harness/](tools/legacy-harness/) | Compiles the original 1998 solvers to reproduce their bugs |

## Credits

- **Original work (1998):** Gino Llerena and Marco Idrogo, authors of the graduation thesis
  and of the *Proyecto* application.
- **Thesis advisor:** Dr. Jaime Avalos.
- **New implementation (2026):** Gino Llerena, with AI assistance.

## License

[BSD-3-Clause](LICENSE). Experimental data in `datasets/` remain the work of their cited authors;
see each dataset's README.
