# The testers' path on the draft release v0.1.0b1 (2026-11-17)

Before the draft release is published, the testers' guide (`docs/beta/testers.md`) was followed
as written, on the release's own artefacts, outside the repository.

## What was used

- **The wheels attached to the draft release** (`gh release download v0.1.0b1`), installed with
  `pip` into a fresh `python3.12 -m venv`, on macOS. Not the repository's build.
- **The data from the publication.** Di Pietro's thesis came from its open copy
  (<http://hdl.handle.net/10955/1001>). Table 3.1 was read from the rendered pages 167–168 (PDF
  pages 179–180) and transcribed at T_red = 0.930 by the guide's label table. The repository's
  validation copy was used only afterwards, to compare: the transcription is identical to it.
- **Notebook 3 as a tester gets it**, downloaded from the tag
  (`raw.githubusercontent.com/.../v0.1.0b1/docs/notebooks/03-reproduce-8cb.ipynb`), executed in
  the same venv with `nbclient` and `ipykernel`.

## Results

| Check | Result |
|---|---|
| Release workflow (first run) | passed every step; a draft prerelease with both wheels and the notes |
| Source archives of the tag (`.tar.gz`, `.zip`) | no entry from `datasets/biphenyl-8CB-dipietro2013/` |
| `dipolar --version` | `dipolar 0.1.0b1 (dipolar-core 0.1.0b1, contract 0.10.0)` |
| Synthetic example, Fit → Run fit | φ = 36.985 ± 0.008°, adequate (p = 0.332) |
| Thesis labels and pages in the guide | match the thesis |
| 8CB in the app, by the guide's clicks (unweighted) | φ = 32.932 ± 0.012°, S_zz = 0.43075 ± 0.00012, Δ = 0.1852 ± 0.0004: the guide's values |
| Notebook 3 on the transcription | "reproduced: both fits agree with the reference" (unweighted φ 32.9321°, weighted φ 32.9746°, flagged inadequate) |

## Findings (all S3) and what was done

1. After the 8CB import the title bar still names the example ("Synthetic biphenyl (known
   answer)"), and there is no operation to rename a project. **The guide now says this is
   expected.** A rename is a candidate for after the beta.
2. The unweighted fit shows a yellow "inadequate" banner. The guide said its adequacy has no
   meaning, but not that the app flags it. **The guide now says so.**
3. With no project open, the page's first `project.describe` and `render.scene` calls answer 409,
   which the browser's console lists as errors. Nothing shows in the page. Recorded only.

No S1 or S2 problem was found. The guide changes are on `main`; the release notes link to the
guide there, so the draft release needs no rebuild.
