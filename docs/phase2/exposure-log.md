# Exposure log for experimental data (Phase 2 holdout rules)

**Custodian: the owner** (approved, decision 5, 2026-11-18).

This log records who or what has seen the **values** of each experimental source. A source seen
by anyone who builds or freezes the model, or its criteria, cannot be an independent holdout
(`docs/phase2-proposal.md`, holdout rules).

Each entry is appended and never edited. A correction is a new entry.

| Date | Viewer | Source | What was seen | Purpose |
|---|---|---|---|---|
| 2026-11-17 | the author agent (Claude) | Di Pietro (2013), Table 3.1, 8CB | all values (transcribed) | beta walkthrough; Phase 1 data, not a V1 candidate |
| 2026-11-18 | Codex retrieval task (GPT-6.2-Sol) | all files in `v0-sources.json` | downloaded; told not to analyse | V0.1 retrieval |
| 2026-11-18 | the author agent (Claude) | Taggar et al. (2006), SI file | **all values** (benzene, tfb, tcb, tbb) | V0.1 survey |
| 2026-11-18 | the author agent (Claude) | Taggar et al. (2006), Tables 1–2 (S_zz) | all values | V0.1 survey |
| 2026-11-18 | the author agent (Claude) | Chandrakumar & Burnell (1993), Tables I–II | **all values** | V0.1 survey |
| 2026-11-18 | the author agent (Claude) | Pizzirusso et al. (2012), Table 5 | benzene, tbb and acetylene rows | V0.1 survey |
| 2026-11-18 | round 68 reviewer (GPT-6.2-Sol) | Taggar SI; Chandrakumar & Burnell Tables I–II; Pizzirusso Table 5 | all values | review of V0.1 |
| 2026-11-18 | round 69 reviewer (GPT-6.2-Sol) | Taggar SI and paper Tables 1–2; Chandrakumar & Burnell Tables I–II and Figs. 2–3; the excluded sources' tables | all values | review of V0.1 |
| 2026-11-18 | transcription task B (Codex, GPT-6.2-Sol) and the author agent (transcription A) | Chandrakumar & Burnell (1993), Tables I–II | all values (transcribed) | V0.2, decision 4 |

**Kinds of access.**
- **Retrieval-only** access (downloading, not reading values) does not expose a source.
- **Phase 1 data** (8CB) is not a V1 candidate.
- The **selected V1 development sets** are Taggar et al.'s benzene and Chandrakumar & Burnell's
  ortho-dichlorobenzene.

**Consequence.** Every source whose values appear above is **development data** for V1.
- **A future holdout** is chosen and kept by the custodian, and appended here when it is opened,
  after V0.3 has frozen the model and the criteria.
- **Premature exposure** is appended as soon as it is discovered, and the affected group is
  retired from holdout use.
