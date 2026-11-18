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
