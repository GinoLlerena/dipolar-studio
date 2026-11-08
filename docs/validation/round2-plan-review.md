# Round 2 — independent review of the redesign plan

Reviewed 2026-11-07. Primary target: `docs/03-redesign-plan.md`, version 0.1; supporting targets: the four panel reports, `panel/mockup-workspace.html`, the revised legacy bug report, and the round 1 verification.

**Verdict: NOT READY as a committed implementation and 6–8-month 1.0 plan.** The scientific direction is sound enough to start a narrower research prototype. The current document combines unresolved scientific assumptions, incompatible numerical prescriptions, unvalidated performance and import estimates, and a substantial desktop/editor/platform project. Resolve the scientific contract and cut the release boundary before treating the roadmap as an execution baseline. This is a review of the plan, not a finding that the proposed product is infeasible.

**Method and limits.** Compared the documents against each other and against round 1. Re-read relevant legacy physics, serialization, geometry and project-build code through `iconv -f latin1 -t utf-8`; the legacy checkout was read-only. Independently checked weighted-projection algebra, the rectangle distortion reconstruction, mockup residual statistics, memory arithmetic and roadmap totals with NumPy. Consulted primary scientific papers and official framework/format documentation, linked at the relevant findings below. No Windows/MFC execution, actual CArchive fixture import, new performance benchmark, user study, or full graphical/accessibility inspection was performed. Mockup findings concern its HTML content and stated behavior. No file other than this report was edited.

Severity here: **critical** can invalidate inferred science or expose local capabilities; **major** can invalidate a release commitment or core workflow; **moderate** is a material clarification or later-feature risk. Estimates below are reviewer judgments, not measured delivery forecasts.

## 1. Incorporation of round 1 into the bug report

**Assessment: substantially recorded, incompletely reconciled.** The revised physics section correctly incorporates the fluorine-prefactor correction, the D4 forward/report mismatch, the nonzero-axis condition for Rodrigues rotations, and the failed cylinder-orientation check. The verdict counts are faithfully repeated. B46–B58 account for all ten missed findings and the three additional high-impact extensions. No entire new high-impact finding was dropped.

However, the original tables remain contradictory to the errata. Readers and downstream panel authors have continued using the original claims. An appendix that retracts a claim does not make a table that still states it a reliable specification.

### 1.1 Corrections that remain wrong or incomplete in the authoritative rows

| IDs / location | Remaining problem | Required reconciliation |
|---|---|---|
| B04, row 17 | Still says eigenvalues are searched **only** inside a hard ±99 bracket and outside eigenvalues are silently lost. Round 1 explicitly found interpolation can extrapolate beyond the assumed bounds. | Replace with assumed sentinels, unguarded interpolation, absolute thresholds and silent iteration termination; retain both ordinary-scale and small-scale reproductions. |
| B07, row 20 | Still says singular exits leave the input values in place. | They can leave **partly eliminated RHS values**, e.g. `(6,0)`. Do not prescribe a test that expects unchanged input. |
| B08, row 21 | Still concludes “almost every grid point fits.” The errata only qualifies the inferred percentage interpretation. | Keep the factual `10*abs(Dobs)` threshold; remove the unsupported acceptance-rate claim. Zero observations still require exact agreement and other failures can reject points. The architecture performance estimate repeats this mistake. |
| B09, row 22 | Still groups zero and negative steps under the second-parameter precondition. | Negative steps can hang during counting without a second parameter; zero-step reachability and entered loop bounds need their own conditions. |
| B10–B14 | Important reachability/mechanism qualifications were not integrated. | A normal new observation gets a default component; a missing spin can also make K zero; only **nonzero** yz/zx terms can reverse sign; the perpendicular routine's coordinate-plane special cases can avoid the general-axis NaN. |
| B13, B15, rows 26–28 | Still says every non-root biphenyl fails; still describes bond 2 as undefined and the ordinary second label as using it. | Replace with round 1's translation/axis qualification and the normal editor mapping: first label uses P1 instead of P0, second label correctly uses P2. Bond 2 is initialized storage, not an undefined array element. |
| B20/B21/B23/B27 | Original S2 section still contradicts the S3 errata. B21 still says migration is impossible; B23 promises a finite sign flip; B27 presents an unused helper as an observed user flow. | Update the rows and their severity in place. Schema 0 is legal. The ancestry error is separate from migration policy. Malformed-distance consequences are conditional. |
| B25/B40 | Refuted entries remain written as live defects in the original lists. | Strike/mark them refuted at their rows and point B25 readers to B46. Do not leave consumers to discover the retraction later. |
| B26, row 44 | Still implies reading necessarily changes access time and invalidates a file. | Use “can, depending on filesystem settings/timing”; include absolute-path and working-directory failure modes. |
| B29, row 47 | Still alleges duplicate names from suffix deletion, despite the explicit retraction. | Remove that consequence. Keep unrelated-fragment deletion and orphan references. |
| B19/B22/B34/B44 | Recommended severity corrections were largely not applied. | B19's lost scientific sweep binding and B22's affected distance sweeps warrant S1; B34's overflow is S1 independently of portability; B44 can cause S1 science near its pole. Separate portability findings rather than burying the scientific consequences. |
| B30/B35 | Minor but misleading shorthand persists. | Selector literal is **24 as maximum index**, capacity 25; deuterium label editing can be reenabled by reselecting the type. |

Other small source-reference corrections from round 1 were not systematically applied. For example, B17 still includes the misleading constructor reference, B19 retains the abbreviated serializer reference, and B35 retains the earlier wrong handler line. These do not overturn the defects, but undermine the promise of a verified source map.

### 1.2 New IDs: faithful mapping, two material qualifications lost

- **B46** captures stale numeric values but omits the concrete **rename/delete → nonempty stale selected label → missing equation** path from M01. Restore it; it is the actual replacement for refuted B25.
- **B47–B53 and B55–B58** preserve the substantive mechanisms. B49's shortened wording should retain that the final-short-page bug also selects the wrong configuration across tabs, not just displays a wrong tensor.
- **B54** says reload silently reverts to the default. Round 1 distinguished a fresh process, which defaults to 10, from an SDI session, which can inherit another document's tolerance. It also identified changed-plane persistence as latent because the shown GUI does not expose that point. Restore both qualifications.
- The heading “checked by reading” covers B50/B55/B56 despite round 1 having executable numerical evidence for related paths. Preserve evidence categories per finding rather than implying a new Windows reproduction or erasing available reproduction evidence.

The **56** figure is correct as **58 tracked IDs minus two refuted IDs**. Call it “56 retained findings”; several IDs combine defects or overlap, so it is not an independently established count of 56 distinct failure mechanisms.

Finally, the plan's opening sentence that the legacy application “had a correct physical model” contradicts the final caution of round 1. Replace it with: “The standard dipolar tensor contraction is sound; geometry, symmetry/frame conventions, distortion assumptions and several solve/report paths remain qualified or unverified.”

## 2. Science and method

### 2.1 VarPro + weighted LSQ + multistart: retain, with a precise contract

**Yes, this is the right baseline for a rigid or explicitly parameterized geometry with known signed observables, a shared order tensor, and a stated Gaussian error model.** It exploits the actual separability and removes the arbitrary choice of defining couplings. SVD order-matrix fitting is established methodology, not a new scientific invention; see the original [order-matrix SVD paper](https://users.cs.duke.edu/~brd/Teaching/Bio/asmb/Papers/NMR/Residual-dipolar-coupling/SVDRdc.pdf). A scan plus bounded local refinement is appropriate for the small geometry dimension anticipated here. Sobol multistart is a sensible extension, not a proof of the global optimum.

The implementation contract needs these corrections before M1:

1. **Whiten both the data and the design matrix.** Science §2 currently writes `(I-P_A) W^(1/2)y`. That is wrong as written if `P_A` is the ordinary projector onto the unwhitened A; if a whitened projector was intended, define it explicitly. With `LᵀL=Σ⁻¹`, `B=L A(g) C(g)` and `b=L y`, solve `t*=argmin ||Bt-b||²` and return residual `Bt*-b`. The symmetry basis can depend on geometry. A simple check with `A=(1,1)ᵀ`, `y=(0,1)ᵀ`, `L=diag(1,2)` gives `t*=0.8`, χ²=0.8; applying the unwhitened projector to `Ly` gives χ²=2.0. Use the returned residual vector with `least_squares`, not the scalar squared norm. Constant-rank assumptions and projector derivatives matter in [the VarPro literature](https://lsec.cc.ac.cn/pub/home/yyx/papers/2008-jcm-26-3.pdf).
2. **Resolve the QR/SVD versus normal-equations contradiction.** Architecture §5 proposes `solve(AᵀWA, AᵀWy)`. This squares the condition number and compromises precisely the marginal geometries the product must diagnose. A condition check is not a substitute for a stable solve. Use float64 SVD or pivoted QR as the correctness baseline; only introduce a demonstrably equivalent fast path after measuring it. Handle rank changes explicitly; autodiff through an SVD/pseudoinverse near rank changes is not automatically reliable.
3. **Do not infer full covariance from the reduced optimizer Jacobian alone.** VarPro eliminates order parameters computationally, not statistically. Build the full prediction Jacobian in independent order and geometry coordinates, including frame motion, and recover covariance/cross-covariance by a stable factorization or block formula. Define whether J is raw or already whitened; otherwise `(JᵀWJ)⁻¹` can double-weight. Singular directions need named unidentifiability, not finite-looking pseudoinverse error bars.
4. **Use bounded trust-region fitting as the default.** The UX and mockup promise LM refinement while geometry has bounds. SciPy's `method='lm'` does not support bounds; use `trf`, or document and validate a parameter transformation. See [SciPy's solver contract](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).
5. **Treat rank-deficient grid points as a reported class of result.** A minimum-norm S can still predict some data meaningfully, but does not identify all tensor elements. Specify whether such points are displayed, excluded from physical solutions, or fitted under a reduced model. Never silently assign ordinary confidence intervals to them. At planar/orthogonal symmetry endpoints, changes in rank deserve dedicated checks.

### 2.2 The statistical promises currently exceed the stated model

**Major.** Weighted residuals do not by themselves create valid uncertainty estimates.

- Couplings extracted from one spin-Hamiltonian fit may have correlated errors. Support covariance whitening in the API, even if the first GUI accepts diagonal σ only. Report the independence assumption. Symmetry multiplicity/components are not additional independent measurements; duplicated equivalent rows must not inflate N.
- A linewidth is not automatically the standard error of a fitted coupling. Record the uncertainty source, distinguish missing/estimated errors, and make the assumed noise model visible.
- The suggested “1–2% or a few Hz” floor is an unsupported heuristic, not a calibrated model of vibrational or anisotropic-J bias. Systematic model discrepancy can be correlated and can move the inferred geometry. Record the floor separately, run sensitivity checks, and do not use it merely to obtain χ²/ν≈1.
- If variances depend on fitted parameters, the Gaussian likelihood includes a log-determinant term; minimizing only weighted residuals is then incomplete. Model comparisons must use the same observations and a properly specified likelihood.
- `ν=N-n_s-n_g` is valid for a regular, locally identifiable model with independent observations. State the applicable rank, nuisance parameters and active constraints. `ν=0` means exactly determined; `ν<0` is underdetermined, not another exactly determined case as science §2 currently says. A positive nominal ν does not guarantee identifiability.
- A grid slice at fixed nuisance geometry is **conditional**, whereas a profile minimizes the other free geometry parameters as well as S. Label these separately. VarPro alone profiles S, not every other geometric variable.
- Δχ²=1 is an approximate **68.3% one-parameter** interval under regular Gaussian conditions. A 95% one-parameter interval uses about 3.84; a joint two-parameter 68.3% contour uses about 2.30. Boundaries, unidentified signs and competing basins require further calibration. Show raw Δχ² for confidence thresholds, not unexplained reduced-χ² bands.
- Report mode-separated/asymmetric intervals when warranted. Parametric simulation must repeat the search across competing basins and report failed/rank-deficient refits. Local covariance or repeated fitting from one seed understates multimodal uncertainty. There is no universal “1/√(data quality)” law (science §5); under a regular fixed design, uncertainty scales linearly with σ and approximately as 1/√N for comparable independent observations.
- AIC/BIC for mixture models, parameter boundaries, selected sign patterns or rank-deficient fits cannot be promised as push-button definitive rankings. Count all fitted nuisance parameters and restrict initial support to regular models on identical datasets. Q-factor and χ²_red are diagnostics, not general model-selection rules.

### 2.3 Identifiability: the two absolute claims must be rewritten

**Scale.** The algebra is correct: if **all relevant distances can be scaled together**, `r→λr`, `S→λ³S` leaves D unchanged. The conclusion “one distance must be fixed” is overbroad.

A template or imported structure with fixed dimensions already supplies an absolute scale; users need not choose one special r12. External order information or known quadrupolar observables under the same tensor assumptions can also anchor scale. Physical bounds on S can restrict an otherwise continuous ambiguity without identifying a unique distance. Conversely, fixing an irrelevant distance does not cure every rank deficiency. Require a documented scale anchor only when the active model admits the scale mode; then test the full Jacobian for remaining degeneracies.

**Dihedral sign.** For a true whole-geometry reflection Q, `r' = Qr` and `S'=QSQᵀ` give the same quadratic contractions. Thus an unconstrained dipolar-only fit cannot distinguish an enantiomeric geometry/tensor pair. This does **not** mean the sign of every internal torsion is never measurable: changing one torsion in an asymmetric or otherwise stereochemically anchored structure need not produce the mirror of the entire molecule.

For the ideal identically substituted biphenyl under the intended achiral, equivalent-site assumptions, ±δ and the relevant 180° variants can indeed be redundant. Folding to `[0°,90°]` should be a validated property of that model and its assignment mapping, not a universal UI rule. Chiral media alone do not defeat the algebra when each candidate receives an entirely free tensor; claims of absolute stereochemistry need additional physical constraints. The [critical assessment of enantiomer assignment from RDCs](https://pubmed.ncbi.nlm.nih.gov/22782933/) is a useful guardrail against overselling this point.

**Planar data.** Coplanar vectors determine **at most** three combinations of the five unconstrained S components; collinear vectors at most one. Fewer independent directions give lower rank. Which entries are null depends on the plane/frame: in an xz plane, xy and yz are invisible; in an xy plane, xz and yz are invisible. The “regular ring recovers S exactly” test must specify the constrained identifiable tensor, not pretend a single planar ring recovers a general five-component tensor.

### 2.4 Symmetry renaming: good algebra, overconfident physical labeling

**Legacy D2 → C2(z): correct as a tensor constraint.** Invariance under `Rz(π)=diag(-1,-1,1)` forces xz=yz=0 and leaves zz, xx−yy, xy. A mirror **plane perpendicular to z** imposes the same restriction on this rank-two tensor; there is no “mirror axis” as science §1.3 says. A true D2 tensor in its symmetry frame is diagonal. The constraint does not uniquely identify the molecule's point group.

**Legacy D4 → two-parameter diagonal tensor in a moving bisector frame: plausible, not established by the name.** Source algebra gives

`Sxy = ½ Δ tan δ`, where `Δ=Sxx-Syy` in the legacy ring frame.

For an active z rotation by `α=δ/2` of a diagonal tensor with principal-frame anisotropy `Δ'`,

`Δ=Δ' cos δ`, `Sxy=½Δ' sin δ`.

This is the regular parameterization to use. Away from `cos δ=0`, it reproduces the legacy coefficient after reparameterization. It also makes clear that carrying the old numerical Δ unchanged into the new frame is wrong. The sign depends on the documented active/passive rotation, torsion direction and chosen ring axes; verify them against the actual geometry, not just trigonometric identities.

“D2h-type” is acceptable only as shorthand for the **same diagonal rank-two tensor form**, not as a claim that a twisted biphenyl has D2h molecular symmetry. Generic ideal twisted biphenyl has D2 symmetry; other substitution patterns need not. At 90°, the enhanced D2d symmetry of the appropriate identical-ring model forces transverse degeneracy `Δ'=0`. Simply replacing tan δ with a regular bisector expression while retaining two independent parameters at that endpoint does not enforce that symmetry. Distinguish an intentionally less constrained phenomenological tensor from a molecular-symmetry model.

The thesis/frame derivation is still needed for historical parity and B55. Molecular geometry alone is not a universally sufficient proof of alignment constraints; [Lorieau's symmetry analysis](https://pubmed.ncbi.nlm.nih.gov/31407205/) explicitly warns that some commonly simplified relationships have limited applicability. Store the constraint basis, frame definition, assumptions and legacy alias separately.

### 2.5 D7 conventions: mostly correct, insufficiently specified

The proposed Hz storage, signed K, explicit S/A convention, absolute-value principal ordering and η range are defensible. Use the following complete contract:

- With angular magnetogyric ratios, `K=-(μ0/4π)γiγjħ/(2π)`; conversion to Hz·Å³ multiplies the SI value by `10^30`. D is defined by `D=K r^-3 uᵀSu`. Record isotope, γ source, units and constants-table version. “CODATA γ” is not a sufficient source for every nucleus; use an explicit nuclide table such as [IUPAC's nuclear-spin recommendations](https://publications.iupac.org/pac/73/11/1795/index.html).
- `T=J+2D` is the heteronuclear secular convention used here, not a universal definition of every measured line separation. A common weak-alignment literature convention absorbs the factor two into its RDC D. Define observable type and conversion per dataset; preserve raw value/unit, signed versus magnitude-only status, isotropic J/reference, and uncertainty propagation. If `D=(T-J)/2`, uncertainty in J matters.
- The Hamiltonians in science §6 need an explicit `H/h` in Hz (dimensionless spin operators). The claimed isolated homonuclear pair splitting `3|D|` requires the relevant equivalent-pair limit; arbitrary inequivalent or strongly coupled pairs require the spin Hamiltonian. Do not map every apparent doublet directly to D.
- `A=(2/3)S` is correct **for the explicitly defined alignment tensor** `A=<ccᵀ>-I/3`. Literature symbols vary. Store the definition, not just the letter A.
- With trace zero and `|Szz|≥|Syy|≥|Sxx|`, `η=(Sxx-Syy)/Szz` lies in `[0,1]` for nonzero S. At S=0 it is undefined. Degenerate principal values make axes nonunique; axis signs and ordering near crossings also need a reproducible display convention. Keep the molecular/symmetry frame distinct from the sorted principal frame.
- Physical admissibility `(2S+I)/3 ⪰ 0` is correct. For a symmetric traceless tensor the stated eigenvalue bounds are sufficient; there is no additional unspecified joint eigenvalue test beyond them and trace zero. Distinguish an unconstrained numerical optimum from a physically admissible solution. If physical constraints are enforced in the inner fit, this is a constrained projection problem, not ordinary unconstrained linear LSQ.

### 2.6 ρ distortion and extensions

**ρ model: the proposed geometric fit is better justified, but it changes the model.** The rectangle reconstruction and the observation that the closed form is generally approximate are supported by the source equations. With `r12=1`, `q=r15/r12`, `Szz=0.30`, `Sxx=-0.13`, direct rectangle couplings inserted into the legacy expression give Δ errors of approximately 0 at `q=√3`, `0.000760` at 1.70, `0.000514` at 1.76, `0.01579` at 1.60 and `0.01428` at 1.90. This supports the panel's local-approximation diagnosis, not a proof of its historical derivation.

The expression is also not “exactly zero independent of S” without qualification: at regular geometry both numerator and denominator vanish when `Szz=Sxx`. A proposed nonlinear shape fit should specify the actual Cartesian deformation, fixed scale, valid domain and tensor constraints. “Three observations, three unknowns” does not establish uniqueness, conditioning or goodness of fit. Keep legacy ρ output separate from a new fitted aspect ratio or ring angle until the mapping is established. Do not interpret an effective rectangle distortion as a literal equilibrium bond distortion without addressing vibrations and anisotropic indirect interactions. Move it behind a validation gate rather than guaranteeing MVP support.

**²H: correct extension in principle, incomplete measurement model.** With an axially symmetric EFG along C–D and the stated q convention, the signed expression `(3/2)q_CD uᵀSu` is appropriate. A measured doublet separation is usually its magnitude; sign assignment is extra information. A quadrupolar datum is a **single-site EFG observable**, not a spin-pair D with a different γ. Add an observable schema for site/tensor, q, EFG orientation/asymmetry, sign knowledge and q uncertainty. A scalar 165–185 kHz value is a plausible C–D range, not a universal constant. A [primary liquid-crystal study](https://link.aps.org/pdf/10.1103/PhysRevE.108.024702) uses a specific 168.8 kHz value with nonzero asymmetry, illustrating the needed specificity. Multiple tensors/unknown q values can add identifiability issues.

**¹³C: adding the prefactor is easy; guaranteeing new information is wrong.** Science §3 says carbon satellites “give non-coplanar C–H and C–C vectors.” Vectors confined to an aromatic ring remain coplanar regardless of isotope. Additional sites, inter-ring pairs, or distinct directions can improve conditioning, but isotope substitution alone cannot lift a geometric null space. Heteronuclear total couplings require J and its uncertainty/reference; natural-abundance satellite sensitivity and equivalence are experimental constraints. Basic ¹³C dipolar prediction belongs in the registry, while a validated total-coupling workflow is a separate feature.

**Further panel physics corrections:**

- Science §1.2 repeats the obsolete fluorine values and says all legacy constants agree within 0.05%. Round 1 established F–F≈−106.428709, H–F≈−113.067361 and F–D≈−17.356530 kHz·Å³ with the stated γ table, and legacy errors up to 0.119%. Replace that table. Ξ frequency ratios include reference shielding and are not an interchangeable high-precision γ source.
- “Cl and Br are quadrupolar and self-decoupled, therefore not observable partners” is too absolute. Reject unsupported measurement models, not the physical existence of those dipolar interactions. Quadrupolar relaxation and experimental resolution depend on the system; the already supported deuteron is itself quadrupolar.
- Arithmetic/weighted coefficient averaging is valid under explicitly normalized populations/equivalence weights and an appropriate shared tensor. It can model internal motion under a justified shared-tensor approximation; it is not categorically restricted to symmetry-related conformers. Conversely, freely fitting `Σ p_c A_c s_c` with independent unknown populations and tensors creates confounding because the products `p_c s_c` are what the data constrain. The [single-tensor approximation is a recognized approximation for conformational analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC6849632/), not a theorem that all non-symmetry-related conformers must have different tensors.
- “Biphenyl dihedral” must distinguish a rigid effective angle, a distribution mean, and the maximum of P(φ). A primary LC study reports different AP and maximum-entropy distribution maxima and uncertainties from the same scientific problem; these are not interchangeable reference answers. See [Emsley et al., 1991](https://pubs.rsc.org/en/content/articlelanding/1991/ft/ft9918702623).
- AP/MaxEnt references, universal vibration magnitudes, and assumed literature datasets remain explicitly marked uncertain by the panel. Preserve that uncertainty in the plan; do not turn them into release-tested physics by synthesis.

## 3. Architecture, performance, legacy import and local security

### 3.1 Stack: reasonable choices, too many simultaneous commitments

**Python + NumPy/SciPy** is well suited to the problem. Establish one scalar/reference implementation and float64 numerical contract. **Numba** can be an optimization after profiling. **JAX** should remain a research extra: enable x64 explicitly, verify derivatives/rank behavior and measure compile overhead. JAX's [official dtype documentation](https://docs.jax.dev/en/latest/101/default_dtypes.html) confirms its default is 32-bit, incompatible with casually promised 1e-10/1e-12 comparisons.

**FastAPI/Pydantic + React/TypeScript + r3f** is a defensible architecture for a team already comfortable with both ecosystems. It is not browser/JupyterHub deployment “for free”: authentication, base paths, reverse-proxy/SSE behavior, filesystem access and multiuser isolation differ from a local desktop. Keep hosted multiuser execution out of the initial release.

**Tauri 2 + a Python sidecar** can work. It brings a Rust build/release toolchain now, despite the summary's “Rust if ever needed” aside. The sidecar still ships CPython and native dependencies; the claimed ~10× installer reduction cannot be inferred from an empty Tauri shell. Measure the frozen application with NumPy/SciPy, LLVM/Numba if included, Arrow, plotting and the chosen structure library. Electron is not a cost-free fallback: packaging, permissions, native file handling and tests change even if React is reused.

Choose and prototype a freezer/build strategy early. Test offline startup, writable JIT cache, supported CPU/OS targets, arm64 versus x86_64, BLAS libraries, signing/notarization of nested binaries and process-pool spawn. PyInstaller explicitly requires [special multiprocessing startup handling](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html); a development `ProcessPoolExecutor` test does not validate the frozen application. Avoid Dask in that same binary until proven.

**Graph + NeRF is not a general molecular editor.** A tree can place coordinates, but arbitrary edits in a molecular cycle do not preserve ring closure. Define the initial geometry model as rigid fragments connected by permitted acyclic torsions; import other structures as fixed geometry where necessary. Specify degeneracy checks for collinear reference atoms, ring closure, atom identity/hydrogens, connectivity inference for XYZ, and unsupported rotatable bonds. These are scientific correctness requirements, not polish.

**Parquet and versioned JSON are good defaults**, with important missing policies:

- Write each chunk to a temporary file, close it, validate its footer/count/hash, then atomically rename and publish it in an atomic manifest. Specify durable-save policy and disk-full recovery. Parquet does not itself provide a transaction; [its error-recovery documentation](https://parquet.apache.org/docs/file-format/data-pages/errorrecovery/) explains why a damaged footer can lose a file.
- Snapshot immutable input content per run, not only a hash and version labels. Include constants/model/template/plugin versions, raw observations, conversions, covariance and preprocessing, solver settings, seed, frame and parameter mapping. A hash verifies content one possesses; it does not reconstruct missing content.
- Define JSON canonicalization for hashes separately from pretty-printing: exclude UI-only state and timestamps, specify float/unit normalization, forbid nonfinite numbers, and preserve ID/reference semantics through migrations. JSON Schema validates shape, not all graph/physics constraints.
- A newer-schema project cannot safely be scientifically interpreted just because the UI opens it read-only. Offer metadata/raw inspection without executing unknown models or promise only compatible-version opening. Preserve the original on migration and validate the migrated graph.
- `.dipolarz` needs bounded decompression, path/symlink validation and no executable content. Never deserialize pickle or automatically install/import code named by a project.
- Entry-point plugins are trusted Python code. Dynamic schema forms do not automatically implement a new observable's plots, scene interaction, derivatives or reports. Stabilizing a broad third-party plugin ABI before the core model is exercised adds cost without improving the first fit.

### 3.2 Speedup: plausible ambition, not a defensible estimate yet

The **10²–10⁴×** range is possible for an I/O-bound legacy executable versus an optimized multicore implementation. No measured baseline here justifies it as a product claim. Architecture §5 compounds guessed legacy compute time, guessed accepted-point rate, guessed file cost, guessed new FLOPs and assumed eight-core scaling. It compares an exact selected-row solver with all-row WLS while calling it the same grid; the workload changes. Multiplying independent-looking speedup factors also risks double-counting gains.

Specific unsupported numbers and contracts:

- “The default accepts nearly every point” is the round 1 B08 overstatement again; accepted-point rate controls the proposed I/O advantage.
- `10^6 points/s/core` as a Rust-switch trigger is arbitrary. A measured end-to-end user latency target should drive optimization, after profiling Python/BLAS/serialization overhead; Rust does not automatically make small SVDs faster.
- A 5° versus 0.5° grid has roughly `10^k` fewer grid locations, but refinement, narrow/missed basins, boundary minima and uncertainty scans add work. It is not a guaranteed further 10–1000× acceleration at equal solution coverage.
- With float64, G=16,384, N=10, P=45 and C=15, the named X, A_pairs and A_obs arrays alone occupy **43.3 MB**. At N=200, X alone is **78.6 MB** and those three arrays total **118.0 MB**, before pair vectors, whitened arrays, SVD workspace and results. “About 30 MB” is not a general chunk budget. Per-worker duplication and process transport multiply the cost.
- Parquet output, full per-coupling residuals, rank diagnostics, optional eigendecomposition and JIT/process startup must be included or explicitly excluded from the ≤10 s sweep target. Limit nested BLAS/Numba/process thread pools to avoid oversubscription. Compute eigenframes only where needed if profiling supports that choice.
- Byte-identical resumed files can differ because of timestamps, metadata, ordering, compression/library versions or floating-point reductions. Require identical point coverage and numerically equivalent results; reserve byte identity for an explicitly pinned, deterministic artifact contract. Relative-only cross-platform tolerances fail near zero; specify absolute and relative tolerances per quantity.

**Concrete benchmark revision:** make M1 establish a published, pinned 10-spin/15-observation/3-parameter fixture with a fixed grid, all-point validation, observed acceptance rate for legacy runs, cold and warm timings, one-core and multicore timings, peak RSS, output bytes, and end-to-end versus kernel-only times. Use the same hardware and record the differing fit semantics. Add an ill-conditioned and a rank-changing case. Until that exists, label 100–10,000× a hypothesis and ≤10 s an engineering target, not an estimate confirmed by arithmetic.

### 3.3 CArchive importer: feasible research task; “one week, 400 lines, one format” is not established

The source serialization order described in architecture §4 is broadly correct, including the UI combo strings, directly serialized members and active-fragment object reference. A constrained Python reader is realistic. The schedule and compatibility guarantee are not.

1. **Schema 0 does not prove one historical format.** It records one schema value, including when authors changed serializers without incrementing it. MBCS/Unicode builds, archive implementation details, code-page choices and prior source revisions remain separate evidence questions. The inspected VS project uses v120; saying `windows-latest` will build VS2013 plus MFC is not a toolchain/setup plan.
2. **The parser description omits archive cases.** A CObList count is not unconditionally one WORD. Handle count extensions, null tags, the shared class/object PID map, large object/class tags, directly serialized members, CString length extensions and Unicode markers. Microsoft's [TN002](https://learn.microsoft.com/en-us/cpp/mfc/tn002-persistent-object-data-format?view=msvc-170) documents the extended PID encoding and identity behavior. The common short tags in the plan are a starting subset, not a complete grammar.
3. **“Drop the dangling pointer” is not a recovery algorithm.** The field's bytes must still be parsed to remain aligned. A valid repeated reference can be ignored semantically after parsing; a file damaged during a use-after-free save may be unrecoverable. Do not promise salvage of arbitrary corrupt archives.
4. **Missing state cannot be reconstructed with certainty.** Bond-label sweep bindings, tolerance and the construction-plane point were not all saved. Report unknown/defaulted values, require reviewed rebindings before a scientific run, preserve original bytes/hash, and keep parsed historical coordinates separate from regenerated/corrected geometry. Successful parsing is not scientific equivalence.
5. **Raw struct sizes do not uniquely identify all files.** 48/88-byte parameter and 88/168-byte dual records are plausible for the shown layout/character width. File-length divisibility alone is ambiguous, can fit multiple interpretations, and does not prove packing, provenance or stream alignment. Validate labels, numeric finiteness, record counts and companion-file relationships; return ambiguity rather than guess. `.bin` metadata needs its own definition.
6. **Fixtures must precede the commitment.** Build a tiny serializer using the real member serializers, a compatible Windows environment or recovered original binaries, rather than requiring the whole GUI to build first. Validate MBCS and Unicode, repeated/null references, empty/multiple lists, long strings, all model types, truncated data and malformed counts against known field dumps. Limit allocations/recursion and whitelist classes; this reader must parse data, never execute class constructors from an archive name.

Replace the fixed estimate with a time-boxed feasibility spike and a supported-variant matrix. A one-week parser prototype may be possible once fixtures exist; production migration and reviewable scientific mapping cannot be promised from source reading alone. If original datasets survive as tables but not `.prj`, enter and audit them directly rather than holding the core release hostage to archival recovery.

### 3.4 Local FastAPI sidecar: missing security and lifecycle requirements

**Critical before shipping a desktop build.** Architecture mentions “spawns, token” and loopback, which is a start. Tauri capabilities govern Tauri IPC; they do **not** automatically mediate an HTTP API that reads files and starts Python jobs. A malicious website, imported label/report content, another local process, or an orphan sidecar is part of the practical attack surface. Loopback is not authentication, and CORS is not a general authorization boundary. FastAPI's [CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) distinguishes simple requests from preflight checks.

Add an ADR with explicit controls and negative tests:

- Bind to explicit loopback only; use an OS-assigned port and authenticated readiness handshake. Handle multiple app instances and prevent attaching to an unrelated process on a reused port. Do not expose `0.0.0.0` or silently publish a cluster/server mode.
- Generate an unpredictable per-launch secret, pass it through private process IPC, and authorize sensitive endpoints including data/status/progress streams. Keep tokens out of URLs, persisted projects, process command lines and logs. Native `EventSource` cannot attach an arbitrary Authorization header; choose authenticated fetch streaming, a scoped same-origin session with CSRF protection, or a Tauri broker. Specify reconnection authorization too.
- Validate Host and allowed origins to resist rebinding/cross-origin misuse; reject unauthorized requests even when they omit Origin. Restrict methods/content types, keep GET free of side effects, and protect cookie-authenticated mutations against CSRF. Avoid broad localhost/port regex allowlists that trust other apps.
- Package UI assets locally, escape imported labels, sanitize report HTML, and set a restrictive CSP with only required backend connections. Limit file/shell Tauri capabilities to the main trusted window. Remote navigation/content must not inherit local privileges. Tauri's official [capability](https://tauri.app/security/capabilities/) and [CSP](https://tauri.app/security/csp/) guidance supports these separate boundaries.
- Give filesystem endpoints project-scoped handles/validated paths rather than arbitrary read/write APIs. Bound upload sizes, archive expansion, point counts, memory, concurrent jobs and runtime; do not allow a project to invoke shell commands, fetch arbitrary URLs or select an executable plugin.
- Supervise the sidecar and its process tree, terminate workers on app exit/crash, detect backend crashes and disk-full conditions, and recover only committed chunks. Test port collisions, two app instances, stalled SSE clients, cancelled jobs and restart. Keep CPU work outside the event loop so live preview cannot freeze behind a sweep; discard out-of-date preview responses by model revision.
- Treat browser/JupyterHub serving as a separate deployment profile with user isolation and authenticated storage, not merely the desktop server with a public bind address.

An authenticated stdio/IPC transport may reduce desktop exposure and credential plumbing. It does not eliminate the need to validate imported content and paths. Choose HTTP versus IPC after a minimal packaged spike, before building the full GUI around an assumed transport.

## 4. Product and UX: reduce the first-release boundary

**Major: over-scoped for an undifferentiated “1–2 developers, 6–8 months.”** The roadmap's phase sizes sum to **23–31 weeks**, including Phase T. That roughly accounts for the calendar promise while leaving little explicit buffer for unresolved physics, archive recovery, research/recruitment, packaging failures, documentation and beta support. One developer and two developers are materially different capacities, especially across scientific validation, interaction design and three-platform release engineering. Summing optimistic phases is not a capacity estimate.

### 4.1 A viable narrower MVP

Retain: one owner-prioritized rigid/template workflow (biphenyl is the clearest candidate), fixed imported coordinates, permitted inter-fragment torsions, isotope constants, explicitly signed dipolar observations with σ/provenance, assignment reconciliation, stable references, one supported symmetry/frame model plus the unconstrained reference model, float64 SVD/QR, bounded VarPro, a small grid/multistart search, rank/physical diagnostics, a correctly profiled one-parameter interval, residuals, immutable run snapshots, JSON/CSV, Python API/CLI and a single local UI path. Keep edits undoable and visibly mark stale results.

Do not cut mathematical diagnostics or provenance to preserve visual scope. For one or two geometry variables, a modest multibasin grid belongs in the first scientifically credible fit; the plan currently puts “global multistart” in v1 while promising uncertainty in MVP/D3.

Move out of the initial release: arbitrary molecular editing and cyclic geometry changes; branched-template generalization unless required by an actual dataset; unresolved ρ geometry fitting; symmetry auto-detection; broad fitter/model/I/O plugin APIs; Dask/SLURM; AP/MaxEnt/RIS; production JAX; multiple detached windows; elaborate docking; theme and EN/ES polish unless research proves it essential; custom report composition; automated spectrum import/simulation; and a simultaneous signed release across all desktop formats. Externalize strings early if Spanish is important, but separate that from a polished bilingual release commitment.

Keep `.prj` migration as a gated archival deliverable. Prioritize one installable desktop platform only if contextual inquiry demonstrates that Python plus a local browser is unacceptable. A useful deterministic HTML/CSV summary should precede a PDF report designer. Freeze third-party extension interfaces after a real second model exposes the needed boundary.

For planning, define a 6–8-month target for this narrowed, validated beta with named staffing and explicit reserve; estimate 1.0 only after the scientific and packaging spikes. No credible replacement date for the full original scope follows from the current evidence.

### 4.2 UX findings the synthesis misses

- **Valid IDs do not prove correct assignments.** Mapping a row to the wrong two existing spins is scientifically wrong but referentially valid. Reconciliation prevents missing/ambiguous references; it cannot promise zero wrong assignments. Include user-confirmed mapping, original labels and a reviewable import diff; avoid a false “validated assignment” badge.
- **Separate convergence, adequacy and identifiability.** A converged optimizer can have a poor, nonphysical, underdetermined or multimodal result. One green “converged” chip should not certify the science.
- **Keep results tied to their input revision.** The mockup's history edits a coupling at 14:32 after Fit 3 converged at 14:31, while the screen still presents Fit 3 as converged. Any edited dataset must mark that run stale and label current preview separately. This is the new UI's version of the stale-state failure the rewrite is supposed to remove.
- **Define an attainable live-preview contract.** Under 100 ms is 10 updates/s, not “re-solve on every frame” at 60 Hz. Specify supported fixture, cold/warm behavior, p95 from gesture to displayed fresh residuals, request coalescing/cancellation and out-of-order-response protection. Preserve the preview under active jobs; measure 3D draw time separately.
- **Dense expert layout needs a novice path.** The fixed 248+436 px side panes consume 684 px before the central table. Test laptop widths, zoom, keyboard-only reconciliation, focus and table alternatives for 3D operations. Colour-palette distance and an asserted contrast ratio do not establish WCAG behavior; low-contrast marks still need adequate graphical contrast where they convey information.
- **Locale parsing cannot simply detect whatever separator a paste contains.** `1,234` is ambiguous. Preview delimiter/decimal interpretation, let users choose it, and store a canonical numeric representation. Formatting precision should follow uncertainty and measurement scale rather than hard-coding every coupling to 0.1 Hz.

### 4.3 Success metrics: useful hypotheses, incomplete measurement definitions

| Proposed target | Concrete measurable replacement / qualification |
|---|---|
| First fit ≤15 min | Fix start/end events, installation/training assumptions, dataset and task, permitted help, invalid-fit/failure handling, and participant group. Report individual times, median and completion rate; a fast invalid fit is failure. |
| Zero seeded assignment errors reach a run | State number/type of seeds and denominator. Split malformed/ambiguous mapping errors the software must block from plausible wrong assignments users must identify. Report observed escapes, not a universal guarantee. |
| ≥80% novices report φ±σ | Define novice count and scoring rubric: confidence level, conditional assumptions, multiple minima, folding and when no identifiable interval exists. Use counts plus uncertainty; the mixed 10–12-person sample contains too few novices for a precise population claim. |
| SUS≥75 | Name version, language, eligible users, timing after a real task and analysis method; report individual/mean scores and uncertainty. Treat the small sample as formative. |
| Every published answer within its uncertainty | Reproduce the original forward model and conventions first; compare like estimands. Separate known-method reproduction, corrected discrepancies and deliberate new-model differences. Do not tune until all papers agree. |
| Bundle reruns to 1e-9 or 1e-10 relative | Pin environment and inputs; specify `atol + rtol*abs(reference)` by observable, objective and identifiable parameter. Compare invariant predictions/subspaces where axes or parameter labels are nonunique. |
| ≤10 s sweep / ≤1 s cancel | Name hardware, dataset, algorithm, JIT state, output policy and percentile; measure time to worker quiescence/commit-safe cancellation, not only UI acknowledgement. |
| Two beta groups / adoption / citation | Require independent setup and a complete dataset/report rerun. Count research adoption as an outcome, not a release-correctness substitute; citations are a lagging aspiration. |

Recruitment arithmetic also needs correction: UX §7's 4 spectroscopists + 4 trainees + 2–3 computational chemists + 1–2 PIs totals **11–13**, unless roles overlap. Define overlap and novice recruitment. Its “MVP benchmark at weeks 8–12” conflicts with M3 in the consolidated roadmap; align research checkpoints to an actually available prototype.

## 5. Section 7 — each idea judged

### 5.1 Thesis audit / Phase T

**Value high; feasibility conditional; novelty moderate as an application, low as a method.** This is the strongest early owner-specific deliverable if original inputs, assignments, conventions and the thesis are available. It can expose which conclusions survive the numerical repairs.

It is not necessarily a 1–2-week publishable note. Historical output may depend on build, flags, coordinates and lost state. A broadly “bug-compatible” rewrite would be expensive and dangerous as a public fit method. Keep the original harness or an isolated audit adapter with explicit bug switches and known scope. Distinguish original numerical behavior, corrected exact solving under the same physical assumptions, and a different weighted statistical model. Report parameter/output differences before attributing them to changed scientific conclusions. Publication requires an actual new result and documented datasets, not just a repaired solver. Make Phase T data-dependent and nonblocking for the core.

### 5.2 Bayesian mode

**Value moderate/high for multimodality; feasibility medium/low initially; methodological novelty low.** It is a useful later research mode, not a natural small plugin that automatically supplies trustworthy credible intervals. Bayesian RDC analysis already has substantial prior art, for example [Rieping et al.'s probabilistic framework](https://link.springer.com/article/10.1007/s10858-007-9215-1).

First remove scale gauges, specify sign ambiguities, physical tensor constraints, observation covariance and the prior over S. DFT gas-phase torsion energies are not automatically solution/nematic free-energy priors. If analytically eliminating S in a posterior, **profiling is not marginalization**: integrating a Gaussian linear nuisance block introduces a determinant/prior term; constrained/non-Gaussian priors complicate it further. Multimodal MCMC needs convergence and mixing diagnostics. Start with a notebook comparing posterior sensitivity against the frequentist profiles; defer product integration.

### 5.3 Experiment-design assistant

**Value high; feasibility medium for a local prototype; novelty unproven in this niche.** Potentially the best later differentiator. Keep it as a research hypothesis, not “no current tool does this well”; this review has not established competitive absence.

Raw `∂D/∂φ` is not enough because S and other geometry can absorb the change. Rank candidates by expected reduction in target-parameter uncertainty after accounting for nuisance parameters (full information matrix/Schur complement), assumed measurement errors and cost. Evaluate across competing minima, not only at one optimum; a locally insensitive candidate can still distinguish basins. Isotopic labeling feasibility, signal strength, correlated spectral extraction and perturbation of alignment also matter. Prototype on one audited dataset and ask whether it would change a spectroscopist's actual measurement choice.

### 5.4 Zero-install teaching edition

**Value moderate pending teacher demand; feasibility high for a tiny explorer, lower for the same production core; novelty low.** A Saupe/tensor explorer with fixed geometry and synthetic data could be an effective teaching artifact. It need not carry the full engine or desktop dependency graph.

Pyodide/JupyterLite compatibility is not automatic for Numba, JAX, native chemistry packages, process pools, file handling or large scientific wheels. Define a supported NumPy-only subset with lazy loading and browser-memory/first-load measurements; use static precomputed cases where sufficient. Defer recruitment and educational maintenance until an instructor commits to a concrete course use.

### 5.5 Open benchmark dataset

**Value very high; feasibility medium; novelty moderate as curated infrastructure.** Promote a **small initial corpus** into scientific validation, ahead of broad feature growth. Distinguish raw published observations, faithfully reproduced analyses and corrected/alternative analyses. There may be several defensible “reference answers” under different motional models.

Record source tables/errata, assignments, units, uncertainty/covariance, J subtraction, temperature/medium, geometry convention, model and reference implementation. Include negative/degenerate synthetic controls and at least one independently checked experimental case. Keep a holdout dataset beyond the cases used while developing the fit. “Each entry is CC-BY” is not something a curator can guarantee for all third-party material; record per-source rights and apply a collection license only to material the project is authorized to license, consistent with [Creative Commons guidance](https://creativecommons.org/share-your-work/cclicenses/?authuser=0).

### 5.6 Spectrum-in-the-loop / v1-lite

**Value potentially high for experienced users; feasibility low as a lite feature; novelty low.** Move this out of v1-lite. Reading a spectrum is not the main challenge. Even a stick spectrum needs the correct strong-coupling Hamiltonian, shifts in Hz at the stated field, isotropic and anisotropic interactions, equivalence, transition intensities and, where relevant, quadrupolar terms. “N≤12 feasible” depends on task and repeated fitting workload; it is not a universal interactive-performance guarantee.

Overlay also needs correct referencing, processing/line broadening and a comparison criterion. It may reveal assignment errors but cannot certify their absence. [nmrglue supports the proposed file families](https://nmrglue.readthedocs.io/en/stable/reference/), which validates the I/O option, not the simulator. Start later with exporting a full parameter set to an independently validated simulator; then consider importing an already processed 1D spectrum for a narrowly documented check.

### 5.7 Optional AI assistance

**Value low for MVP; feasibility medium; novelty low.** A deterministic Methods template from provenance is simpler, reproducible and sufficient initially. “Never touches numbers” does not prevent an LLM from inventing uncertainty interpretations, causal explanations or assumptions. A run-field link proves provenance of a value, not correctness of a sentence about it.

Defer. If introduced, use schema-bounded inputs, deterministic numeric insertion, clearly marked generated interpretation, explicit user review and a specified local/remote privacy policy. Imported labels and metadata are untrusted text, including prompt-injection input. Do not silently transmit unpublished data when local inference is unavailable. “Sxy and φ are correlated because…” should come from computed diagnostics with a bounded explanation, not an inferred physical story.

## 6. Consistency, gaps and unsupported numbers across documents

The plan should be the decision record. Panel proposals should remain historical inputs with an explicit resolution map; otherwise their errors continue to reenter implementation.

| Issue | Conflicting or unsupported statements | Required decision |
|---|---|---|
| Round 1 | UX §2 repeats refuted B25 and duplicate names from B29; architecture §3 says IDs remove B25; architecture §5 repeats near-universal tolerance acceptance. | Reconcile authoritative bug rows and annotate panel supersessions. |
| Numerical solver | Plan §2 says only `lstsq`/QR; science recommends QR/SVD; architecture §5 prescribes batched normal equations. | One float64 QR/SVD reference contract with rank policy. |
| Angle calculations | Science §1.1 explicitly says no spherical angles; plan §6 and architecture §5 still build coefficients via `atan2`. | Use Cartesian quadratic products in the dipolar kernel. Reserve angles/atan2 for geometry and display. |
| Symmetry naming | Plan C2/D2h-type; architecture C1/D2/D4; mockup D₂ with two parameters and bisector frame. | Canonical constraint/frame identifiers plus legacy aliases; avoid ambiguous display labels. |
| ρ placement | Plan describes fitted geometry; architecture treats `distortion-rho` as an order model. | Geometry/deformation model and order constraints are separate objects. |
| Search/uncertainty scope | D3 includes multistart, profiles and bootstrap; MVP lists covariance; v1 adds global multistart and MC; UX defers refinement to v1. | Specify exactly which search and intervals a first release validates. |
| Reports | MVP promises CSV/JSON; v1 promises PDF/HTML; M4/M5 imply Report workspace and publication exports before 1.0. | Put each export and report behavior in one release tier and one phase. |
| Motional models | “Correct for averaging,” “not torsional flexibility,” and “shared S only for symmetry-related conformers” coexist. | State shared-tensor and conformer-dependent alternatives and their identifiable parameters. |
| Observation schema | UX includes sign-known/unknown; plan CSV omits sign status/J/covariance; architecture only models spin-pair D/T. | Versioned observable schema; signed D first, quadrupolar and total-coupling extensions explicitly gated. |
| Geometry scope | “Product is a fit” versus arbitrary imports, length/angle editing, topology and multiple templates. | Fixed structures/rigid fragments plus a restricted torsion model for MVP. |
| Browser versus desktop tests | Tauri quirks supposedly covered by Playwright on every OS; architecture elsewhere admits narrower desktop tests. | Browser tests plus real packaged system-webview tests. Official [Tauri testing docs](https://tauri.app/develop/tests/webdriver/) now describe a WebdriverIO embedded-server route for macOS too; recheck the panel's blanket macOS limitation rather than freezing it as fact. |
| Figure identity | Architecture says Plotly + Matplotlib yields “one figure source” and identical exports. | Define a shared semantic figure specification/style, or promise consistent data rather than identical rendering. |
| Speed/install/memory | 100–10,000×, another 10–1000×, 10× smaller installer, 30 MB/chunk, 10⁶ points/s/core. | All unmeasured; benchmark or remove as factual rationale. |
| Resume/reproduction | Byte-identical runs, 1e-9 UX relative agreement, 1e-10 architecture relative agreement. | Separate deterministic input identity, same-environment resumption and cross-platform numerical equivalence. |
| Product evidence | Personas, “most frequent user,” scripting habits, competitive gap and teaching adoption read as findings. | Label them hypotheses pending contextual inquiry. |
| Legal/release claims | Source-reading rewrite called clean-room; BSD said compatible with every dependency; copyright risk given low likelihood without an ownership audit. | Describe independent reimplementation accurately; verify ownership and actual distributed dependency licenses before release. The wording alone is not evidence of clearance. |

**Mockup-specific observations:** the 15 displayed residuals give χ²≈17.1625 and RMS≈0.8044 Hz, consistent with its 17.18 and 0.80 after display rounding. With 2 geometry + 2 order parameters, ν=11 and reduced χ²≈1.56 are internally consistent **if** those 15 values are independent observations. This arithmetic is not evidence that the synthetic geometry/uncertainties were recovered by a real fit.

Fix the following content before using it as a scientific prototype: the H2–H2′ callout says r=2.311 Å while the table says 2.305 Å; the plan sketch shows RMS=0.41 Hz although the mockup shows 0.80; the sketch names the worst normalized residual, while the mockup status names the worst absolute residual without making the distinction in the plan. H2–H6 and H3–H5 are equivalent under the ideal symmetric template; establish whether these are independent experimental estimates or duplicated fitted spectral parameters before counting them twice. Label the very narrow φ±0.03° interval as synthetic and conditional on the model, fixed lengths and assumed errors. It is not a claim of achievable experimental accuracy. An honest multimodal/unidentifiable example would test the design better than another green converged example.

Missing acceptance cases across the plan: finite/positive input validation; unsigned observations; near-zero couplings; zero/degenerate S; ring closure and frame degeneracy; symmetry changes at endpoints; correlated or missing σ; invalid physical optimum; stale previews/runs; disk-full recovery; archive ambiguity; malicious project/bundle content; packaged worker crashes; and a published dataset whose new-model result intentionally differs from the old one. These are higher priority than adding a new plotting mode.

## 7. Top 10 recommended changes to the plan, ranked, with concrete edits

### 1. Add a binding scientific/inference contract before M1

**Edit D3 and M1:** “Use a float64 Cartesian forward model, whitened SVD or pivoted QR inner solve, and bounded trust-region variable projection. Support a documented diagonal-noise baseline and API covariance input. Define rank/physical validity, full-parameter covariance, profile versus slice, sign handling and confidence level. Show unidentified directions and competing basins; numerical convergence alone does not certify a fit.”

Add an M1 gate: analytical coefficient tests, weighted-projection control, rank-changing/planar controls, full versus reduced-fit agreement, and simulation-based interval coverage for the supported model. Remove the normal-equations prescription from the governing architecture ADR. This prevents a faster replacement from producing unjustified precision.

### 2. Replace the identifiability and symmetry absolutes with model-specific rules

**Replace the MVP identifiability parenthesis and revise D7:** “Detect scale freedom and require an anchor only when present in the active model. Enumerate model-specific reflection/torsion equivalences and report the chosen domain. Identify tensor constraints by frame and basis: C2(z), or a diagonal tensor in an explicitly defined moving frame. Retain D2/D4 as legacy aliases only. D4 equivalence, rotation sign and endpoint symmetry require a documented derivation.”

State `Δ=Δ'cosδ`, `Sxy=½Δ'sinδ`; gate the enhanced-symmetry endpoint and the new ρ model. Replace the blanket legacy-physics pass in §1. This closes the largest physics overclaims without discarding the useful algebra.

### 3. Rewrite §4 and §8 around a small, staffed scientific beta

**Replace “6–8 months to 1.0”:** “Target 6–8 months for a validated beta of one template/imported fixed-geometry workflow, restricted torsions, signed couplings, fitting/diagnostics, reproducible runs, API/CLI and one local UI path; confirm staffing, reserve and dates after M0 spikes.”

Move Dask, arbitrary editing/ring changes, unresolved ρ, stable external plugins, broad reports, automatic symmetry, ensemble models, spectrum overlay and simultaneous multi-format desktop release out of that boundary. Retain multibasin checking and an honest interval method in the first scientific release. Re-estimate 1.0 from measured delivery evidence.

### 4. Add a sidecar security/lifecycle ADR and early packaged spike

**Add D10 plus an M0 exit gate:** “A minimal packaged build authenticates every sensitive HTTP/stream request, binds only loopback with a verified ephemeral-port handshake, restricts Host/Origin/CSP/capabilities/filesystem access, validates untrusted files, supervises its process tree, and cancels/restarts safely. Choose authenticated SSE transport explicitly. Prototype the freezer, worker spawn, offline startup and JIT cache on the first supported platform before committing to three-platform installers.”

Name the HTTP-versus-IPC decision and keep public/multiuser serving outside desktop assumptions. This is both a security prerequisite and a delivery-risk reduction.

### 5. Make round 1 reconciliation a prerequisite, not an appendix readers must reinterpret

**Revise §2's source-of-truth statement:** “Rewrite each retained bug row to its validated mechanism/severity; mark B25/B40 refuted in place; restore B46 stale rename/delete and B54 process/session distinctions; carry round 1 provenance per finding. Panel statements superseded by validation are historical proposals.”

Correct the stale fluorine table, acceptance-rate claim, schema-0/migration claims and duplicate-name story wherever they influence decisions. Keep 56 as retained findings, not an audited independent defect count. This stops known refutations from becoming new requirements and benchmark assumptions.

### 6. Gate legacy import on fixtures and scientific mapping

**Replace D6/M4's unconditional importer promise:** “Time-box a CArchive feasibility spike; support only fixture-verified format variants. Preserve source bytes/hash and unknown state, report ambiguity/losses, and require review of missing bindings/conventions before running. Test counts/tags/string variants, identity references and malformed archives. Do not promise corrupt-file salvage or infer encoding solely from file length.”

Remove “one week/400 lines/exactly one format” from the rationale. Make archive recovery and Phase T contingent on data/toolchain evidence rather than blockers for the new engine.

### 7. Replace speedup arithmetic with a benchmark specification

**Replace the speedup paragraph in §6:** “A 100–10,000× end-to-end improvement is an unmeasured hypothesis. M1 establishes a fixed workload and correctness baseline; M2 records cold/warm kernel and persisted-run timing, single/multicore scaling, accepted-point fraction, peak memory, cancellation and numerical agreement on named hardware. The ≤10 s target is provisional until measured.”

Remove the arbitrary Rust-switch rate, guaranteed extra VarPro multiplier and blanket 30 MB chunk assumption. Budget chunks by bytes and retain the stable solver while optimizing.

### 8. Specify observable types and separate physical model extensions

**Revise D7 and the project/CSV schema commitment:** “Preserve raw observable, convention, sign status, isotope, uncertainty source, J/reference and conversion provenance. Start with signed dipolar D. Add total couplings and single-site quadrupolar/EFG observables only with dedicated schemas and validation datasets. Carbon labels do not themselves add out-of-plane information; conformer averaging states whether tensors are shared or conformation-dependent.”

Move broad ²H/¹³C measurement workflows and ρ interpretation behind scientific acceptance gates. Correct the stale constants and shared-tensor absolutes in the expert inputs used to implement them.

### 9. Define immutable-run, durable-save and stale-result behavior

**Expand D5/D6 and M2:** “Every run contains an immutable executable input snapshot plus canonical hash, model/constants/plugin versions, solver settings and seed. Commit completed Parquet chunks and manifests atomically; incomplete chunks are never results. Resume validates coverage and content. Cross-platform agreement uses quantity-specific absolute and relative tolerances; byte identity is limited to a pinned deterministic environment. Editing a model marks historical results stale; previews carry revision IDs.”

Add disk-full/crash, out-of-order preview and migration/reference-validation acceptance cases. A new storage format alone does not fix B46/B57-style scientific state corruption.

### 10. Make validation metrics operational and prioritize the benchmark corpus over speculative features

**Revise §5 targets and §7 priorities:** define task start/end/failure, participant denominators, assignment-error types, uncertainty-comprehension rubric, p95 preview/cancel latency and reproducibility tolerance. Separate numerical truth, original-method reproduction and new-model inference; include a held-out experimental dataset and coverage tests.

Promote a small cited, rights-reviewed benchmark corpus and conditional thesis audit. Keep the experiment-design assistant as the leading later research candidate; defer Bayesian product integration, teaching deployment, spectral overlay and AI until there is demonstrated user demand and a stable inference core.

## Final verdict

**NOT READY.** Approve a narrowed scientific prototype after the inference/symmetry contract and authoritative bug reconciliation are corrected. Do not approve the current full-scope 6–8-month 1.0 commitment, unmeasured speedup/installer claims, or unconditional legacy-import promise. Re-review the plan after ranked changes 1–5 are incorporated and the scientific, packaging and archive spikes have explicit pass/fail criteria; completion of the remaining changes should be scheduled before the corresponding features ship.
