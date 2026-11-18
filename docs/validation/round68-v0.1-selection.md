# Validation rounds 68–69: V0.1 selection and access

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The document under review is [`docs/phase2/v0.1-selection.md`](../phase2/v0.1-selection.md).
Its source files are local, not committed; their manifest is
[`docs/phase2/v0-sources.json`](../phase2/v0-sources.json).

## Round 68 (on dcd7f58): NOT READY, 6 A + 3 B

The reviewer verified all eight SHA-256 checksums and the benzene arithmetic: an implied
2.477831 Å, and ratios 0.824 % and 1.275 % above the rigid values.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Wrong counts. Benzene has **15** conditions (45 values), with a single-solute range of 0.55–8.32 mol %. ortho-Dichlorobenzene's Table I has **9** rows (301–330 K) and Table II 13 (288–316 K): **22** conditions and **88** values, not 26 and 104. | Corrected, and used as V0.2's completeness checks. Checked against the rendered pages. |
| 2 | A | Observable and uncertainty provenance. Both sources fit D with isotropic J fixed, and Taggar says the values depend on J. The confidence level and covariance of the errors are unspecified. "The misfit is already known" was unsupported. | They are recorded as **published effective D under the source's spectral assumptions**, imported as printed. The uncertainties are "reported, definition unspecified", and independence is a stated working assumption. The claim is removed. |
| 3 | A | ortho-Dichlorobenzene: the geometry and J come from Diehl & Khetrapal (1968), ref. 14. Numbering and frame are in Fig. 1 (y the C2 axis, x ∥ H2–H3, z normal). The published targets are only Fig. 2's filled points. | Recorded: the label map, the classes (12 = 34, 23, 13 = 24, 14), the frame and the transform to V1's convention. The targets are to be digitized, or the comparison stays pending. |
| 4 | A | Benzene: the implied distance is a scale check, not a reproduction. SHAPE fits all the couplings, and \|D12/S_zz\| differs between rows beyond rounding. Vibration is one plausible cause of the ratios, not the only one. | Restated: the reproduction is pending the geometry and objective. Several causes are listed. The axial tensor's in-plane orientation is arbitrary. |
| 5 | A | ortho-Dichlorobenzene rights: the issue is **© 1993 ISMAR, all rights reserved**. The 8CB precedent does not transfer. The channels must be specified separately. | Corrected (§5, a table of channels). The ISMAR transcription stays local unless a basis is established. The CC BY-NC 4.0 obligations for Taggar's SI are listed. |
| 6 | A | The exposure log was not durable or verifiable. A group manifest is needed. | [`docs/phase2/exposure-log.md`](../phase2/exposure-log.md), which includes this review's access. The group manifest is in §4 (Run 1 tubes reused by sequential addition, Run 2 separate tubes, co-solutes by tube, two mixture series). |
| 7 | B | Sample conditions: the mixed-sample compositions; a nominal 300.9 K versus the calibration; ortho-dichlorobenzene's loading and co-solutes unresolved; the article spans pp. 199–204. | Added. |
| 8 | B | Exclusions: tcb's 0.85 mol % row has no uncertainty; tfb has one H–H class; Marjanska's Table 2 has three H–H values with no σ and ν = 0; Sinton's Table 4.7 is 5CB-d₁₁; the thesis is DOE-supported. | Corrected (§3, "Not selected"). |
| 9 | B | Pizzirusso's primary source is van der Est, Kok & Burnell (1987). Keep a durable manifest. List what was not obtained separately. | Added (`v0-sources.json`, §1). |

## Round 69 (on 91f2649, the final round under the cap): NOT READY, 4 A + 6 B; fixed without re-review

The reviewer confirmed every round 68 fix against the sources:
- the counts (15/45; 9 + 13 = 22/88), the mixed-sample compositions and the 300.9 K setting;
- the tube history;
- the J values, the numbering, the class map and the frame;
- the benzene arithmetic;
- the ISMAR and CC BY-NC records;
- all eight hashes and byte sizes.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | ortho-Dichlorobenzene broke the written rule (protocol 5): loading, tubes and co-solutes are incomplete. | Protocol 5 now allows a source with unresolved sample metadata **as development data only**, with each unknown marked. The 300 K Table II sample's trichlorobenzene peaks (Fig. 1) are recorded. |
| 2 | A | Fig. 2(a) has 7 filled markers for Table I's 9 temperatures and 8 for Table II's 13. Fig. 3 plots the same SHAPE results against T_r. | V0.3 digitizes both figures and cross-checks through T_NI = 333 and 317 K. It freezes a condition-by-condition target list with a declared precision; missing or ambiguous conditions stay pending. |
| 3 | A | The rights table was ambiguous on local use, external sharing and the CC BY-NC conditions in reports. | Local use and external sharing are separate rows. CC BY-NC conditions (non-commercial, attribution, licence, changes) apply wherever SI values are shared. ODCB transcriptions and digitized targets are not distributed until a basis is recorded. The ACS main paper is covered separately. |
| 4 | A | Unknown error definitions need an explicit inference rule. | The reported errors are kept as printed, and their use is preregistered in V0.3 as a stated error model. Residuals and agreement are descriptive or conditional; calibrated p-values or intervals need a justified model or a calibration. |
| 5 | B | SHAPE and LEQUOR provenance were missing from the checklist; the anisotropic-J statement was too broad. | Added to the README checklist and V0.2. Benzene's J inputs are LEQUOR provenance. The anisotropic-J treatment for benzene is "not stated". |
| 6 | B | The frame handoff. | The right-handed map (x, y, z)_V1 = (z, x, y)_paper is recorded and frozen before comparison. Benzene's S_xx = S_yy = −S_zz/2 is recorded, with the paper's apparent reversal noted. |
| 7 | B | The `±0:28` token at 311 K in Table II. | The token is preserved, and its reading (0.28 Hz) is documented after the independent check. |
| 8 | B | The exposure log. | Round 69 appended. Retrieval-only access, Phase 1 data and the V1 development sets are distinguished. Premature exposure is logged when discovered, and the group retired from holdout use. |
| 9 | B | The registry: pages and rights for ortho-dichlorobenzene; the fourth missing item. | pp. 199–204; the ISMAR notice (PDF page 2); the Yethiraj supplement marked unconfirmed. |
| 10 | B | The Burnell 1987 exclusion was too broad. | Narrowed: Table 1 has diatomics (H₂, HD, D₂); Table 3 has polyatomic order parameters, with no qualifying coupling table. |
