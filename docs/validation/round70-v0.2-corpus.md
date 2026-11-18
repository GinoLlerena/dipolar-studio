# Validation rounds 70–71: V0.2 transcription and verification

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step is recorded in [`docs/phase2/v0.2-corpus.md`](../phase2/v0.2-corpus.md).

## Round 70 (on 8ebb2e0): NOT READY, 3 A + 4 B

The reviewer verified a lot against the sources:
- the committed SI is byte for byte the publisher's file;
- all 45 benzene values and σ, and the four mixed compositions, match the sources;
- 28 ortho-dichlorobenzene cells, including both colon tokens and the 300/302 K rows, match
  freshly rendered pages;
- the built wheels hold no corpus values.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | **ortho-Dichlorobenzene values were tracked and exported:** three cells in a test fixture, one value in a tool docstring, the two colon tokens in the V0.2 record, and one uncertainty token in V0.1 (already on `main`). | The fixtures and examples are synthetic. Tracked docs refer to cells by table, temperature and coupling only; the exact discrepancy is in the local `FIRST-PASS.md`. The branch history was rewritten before merging. The token on `main` is flagged to the owner (v0.2-corpus.md §4). |
| 2 | A | **Benzene observations in exported files:** a parser docstring, a test string, and V0.1's worked example. | Synthetic token in the docstring. The test mutates a token read from the SI at run time. The worked example moved into the dataset README, which is excluded from archives. |
| 3 | A | **The guards could pass without checking.** `git check-ignore` exit status 1 was read as "not a git checkout" (a skip). An unrelated `*.csv` rule passed. A failed `git archive` left the release check green. | A separate check for a git checkout. The ignore rule must come from `.gitignore` itself, probed with a CSV and a Markdown path. The release step runs under `set -euo pipefail`, writes the archive and its listing to files, requires a non-empty listing, and also forbids `datasets-local/`. A repository-local exclude protects the owner's checkout across branches. Mutants checked: an ignore rule replaced by `*.csv` now fails the test. |
| 4 | B | The corpus tests missed coordinated errors: swapped columns, or a changed composition with the CSV regenerated. The comparator accepted empty files, truncated rows and surplus fields. | An independent reading of the SI keyed by run, sample and column, and assertions on the four footnote compositions; both mutants fail. The comparator refuses a missing header, missing key columns, wrong widths, duplicates and empty files, and takes `--expect N`. |
| 5 | B | `CITATION.cff` failed CFF 1.2.0 validation (`type: dataset`). The derived CSV's licence needed stating. | `type: data`. The README says the CSV carries the same CC BY-NC 4.0 terms. |
| 6 | B | Distinguish the first-pass evidence from the adjudicated result. | The first-pass output is kept locally (`FIRST-PASS.md`), and the 87/88 count is called a reported result. The spot-check sheet says "after adjudicating one token". |
| 7 | B | Carry the target availability into V0.3: Fig. 2's panels differ. Clarify the J provenance. | v0.2-corpus.md §3: availability per condition and per tensor component; benzene's missing J inputs are LEQUOR provenance; ortho-dichlorobenzene's J are printed. |
