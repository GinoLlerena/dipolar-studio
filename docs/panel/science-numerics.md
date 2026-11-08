# Panel review: science and numerics

Reviewer role: NMR in anisotropic (liquid-crystal) solvents and numerical optimization.
Inputs: `docs/legacy/01-legacy-analysis.md` and `02-bug-report.md`, plus `InteraccCalculada.cpp`,
`Distorcion.cpp`, `RealizadorCalculo.cpp`, `CoordEsf.cpp`, `Trigonom.cpp` and `Mathemat.cpp`.
Checks were run as throw-away NumPy scripts. They are not in the repo.
Confidence tags: **[verified]** = derived or checked numerically here · **[plausible]** = consistent
with the code, but the thesis must confirm the intent · **[unsure]** = from memory, check before relying on it.

## 1. Physics and model

### 1.1 Coupling formula [verified]

The legacy expression is exactly `D_ij = (K_ij / r³) · uᵀ S u`, where `u` is the unit internuclear
vector and `S` is the traceless Saupe matrix, `S_ab = ½⟨3 cos θ_a cos θ_b − δ_ab⟩`. Expanding
`uᵀSu` with `Sxx + Syy = −Szz` gives the five legacy coefficients. This includes the factor 1 (not 2)
on `Syz·sin2θ·sinφ`, because `2 Syz u_y u_z = Syz sin2θ sinφ`. The new code should use the
`uᵀSu` form directly, with no spherical angles at all. That removes B12 (atan vs. atan2) by
construction. Two side notes:

- The legacy variable names are swapped: `AnguloPhi` holds the *polar* angle and `AnguloTeta` holds the
  azimuth. The math is right; only the names are confusing.
- The atan ambiguity (φ vs. φ+π) does not affect the `cos2φ` and `sin2φ` terms. It flips only
  `Syz` and `Szx`, so B12 is confined to the no-symmetry path. A corollary: the physics is invariant
  under i↔j (u → −u), but the legacy code is **not**. Swapping the labels flips sin2θ, while
  `atan(y/x)` stays unchanged. So in the legacy code the Syz and Szx coefficients depend on the order
  in which the labels were entered ("A, B" vs. "B, A"). Add this to the bug report as an extension of B12.

### 1.2 Constants [verified]

`K = −(μ0/4π)·γiγjħ/(2π)`, in kHz·Å³. Recomputed from CODATA ħ, γH and the IUPAC Ξ frequency ratios:

| Pair | Legacy | Recomputed | Pair | Recomputed |
|---|---|---|---|---|
| H–H | −120.120 | −120.120 | H–¹³C | −30.20 |
| H–D | −18.439 | −18.439 | ¹³C–¹³C | −7.595 |
| D–D | −2.830 | −2.831 | ¹³C–F | −28.42 |
| F–F | −106.302 | −106.35 | H–¹⁵N | **+12.18** (γN < 0) |
| H–F | −113.000 | −113.03 | H–³¹P | −48.63 |
| F–D | −17.346 | −17.35 | F–³¹P | −45.75 |

The legacy values agree to within 0.05%. Ξ ratios include reference-compound shielding, so they
differ from γ ratios at about the 1e-4 level. **Recommendation:** compute K from a single nuclide table
(γ values with their source cited) instead of hard-coding pairs. This makes 13C, 15N and 31P free to add,
and it handles the sign automatically. Cl and Br should raise "not an observable dipolar partner"
(they are quadrupolar and self-decoupled) instead of silently returning K = 0 (B32).

### 1.3 Symmetry reductions [plausible; names need fixing]

- **"D2"** (Szz, Sxx−Syy, Sxy; Syz = Szx = 0) is what you get from a **single C2 (or mirror) axis along z**,
  with x and y *not* on symmetry axes. In a true D2 frame aligned with the three C2 axes, S is diagonal.
  Rename this path to "z is a C2 axis" or similar.
- **"D4" with `tan(dihedral)`** [verified algebra, intent plausible]. The coefficient
  `½ sin²θ (cos2φ + tan δ · sin2φ)` multiplying `(Sxx−Syy)` is equivalent to imposing
  `Sxy = ½(Sxx−Syy)·tan δ`. Rotate a diagonal tensor by α about z: then
  `Sxy/(Sxx−Syy) = ½ tan 2α`. So the constraint says the **principal x and y axes lie at δ/2 from the
  frame x axis**, i.e. they bisect the two ring planes. That is the D2 symmetry of a twisted biphenyl,
  written in a frame fixed to ring 1. This is physically sensible. Its problems are numerical:
  (a) the parametrization blows up at δ → 90° (B44), even though the physics is smooth; (b) the sign
  of the tan term depends on the direction of rotation, which nothing in the code documents; (c) at
  δ = 90° the symmetry becomes D2d and the principal Sxx−Syy must be 0. **Replace it** with the
  principal-frame form `½ Δ′ sin²θ cos 2(φ − δ/2)`, which is regular for every δ, or simply fit in the
  bisector frame with S diagonal. The thesis should confirm whether "D4" was meant to mean "D2 of the
  biphenyl" or something else, such as averaging over ring flips.
- **Averaging of components** (the arithmetic mean of coefficient rows) is correct for *equally populated,
  symmetry-related* sites or conformers that share **one** S. It is not a model for torsional
  flexibility (see §3).

### 1.4 `Distorcion.cpp`: reconstruction [verified numerically, origin plausible]

The four ring protons of a para-disubstituted benzene form a rectangle. z is the para (C1–C4) axis
and x lies in the ring plane. The protons sit at (±a, 0, ±b). The labels are:
D12 = ortho (along z, r12 = 2b), D15 = meta across the axis (along x, r15 = 2a), and D14 = para
diagonal. Then:

- `Tzz = D12·r12³/K` is exact (θ = 0).
- From D15 (θ = 90°): `Sxx−Syy = Szz + 2·D15·r15³/K`. The legacy code writes this as
  `Szz + 6√3·D15·r12³ / (K(1−3ρ))`. That is exact if `(√3·r12/r15)³ = 1 − 3ρ`. For a regular
  hexagon (`r15 = √3·r12`), ρ = 0.
- The legacy formula `ρ = (4D12 − 128D14 + 36√3 D15)/(27D12 − 384D14 + 63√3 D15)` gives **exactly 0**
  for the regular geometry and is independent of S there. For distorted rectangles it is only
  **approximately** S-independent. In my tests, with r15/r12 = 1.70–1.76 (regular is 1.732), the error
  in Sxx−Syy was about 1e-3. With r15/r12 = 1.60 or 1.90, the error grew to 1–4e-2, and ρ varied with S.
  So ρ looks like a **first-order (linearized) distortion parameter**, probably taken from the
  literature or the thesis. **[check thesis]** whether the published formula is exact (in which case
  the code has a transcription error) or linearized by design.

**Recommendation:** drop the closed form. Treat r15/r12 (or a ring angle) as an ordinary geometric
parameter in the nonlinear fit of §2. Three couplings and three unknowns (Szz, Δ, shape) is then an
exactly determined case of the general method. Also fix B18 and B22, where r12 is stale.
Note: apparent "ring distortions" from LC-NMR are often partly **vibrational artefacts**, or come from
D_aniso / J_aniso contributions (see §3). Report a fitted distortion only together with that caveat.

### 1.5 Fundamental identifiability facts the UI must surface [verified]

- **Scale degeneracy:** `(r → λr, S → λ³S)` leaves every D unchanged. One distance must be fixed.
  The legacy code fixes r12; the new code must require a fixed distance explicitly.
- **Reflection degeneracy:** a mirror-image geometry with the mirrored S gives identical D. The *sign*
  of a dihedral is never determined, and δ, −δ, 180°±δ are equivalent for symmetric biphenyl.
  Restrict the fitting domain to one copy (e.g. δ ∈ [0°, 90°]) and report it that way.
- **Coplanar vectors** (a single rigid planar ring) determine only 3 of the 5 S elements. Collinear
  vectors determine only 1.

## 2. Fitting methodology (replaces the exact solve and the binary grid)

**Model.** For geometry parameters g and order parameters s (up to 5 elements, fewer under symmetry):
`D_calc(g, s) = A(g)·s`, where row k of A holds the K/r³-weighted, component-averaged coefficients.
The problem is **separable**: linear in s, nonlinear in g.

1. **Inner problem (s given g):** weighted linear least squares, `min ‖W^½(A s − D_obs)‖²`
   with `W = diag(1/σ_k²)`. Solve it with QR, or with SVD (better, because it gives diagnostics).
   This uses **all** couplings, not 2–3 hand-picked ones, so the result no longer depends on the user's
   choice. Symmetry enters as a constraint matrix `s = C·t`, never as hand-edited coefficients.
2. **Outer problem (g):** variable projection (Golub–Pereyra). Minimize
   `‖(I − P_A(g)) W^½ D_obs‖²` over g alone, with `scipy.optimize.least_squares` (trust-region
   reflective, with bounds) or Levenberg–Marquardt. The Jacobian can come from finite differences,
   Kaufman's VarPro approximation, or JAX autodiff through the linear solve. The usual size
   (≤ 5 + a few geometry parameters, ≤ 50 couplings) is tiny, so robustness matters more than speed.
3. **Global strategy:** keep the legacy idea of a scan, but turn it into a **profile**. On a coarse grid
   over one or two key parameters (e.g. the dihedral), minimize everything else, then plot
   χ²_min(δ). The profile shows multimodality and gives profile-likelihood confidence intervals
   (Δχ² = 1 for one parameter). For more than 2 nonlinear parameters, use a multistart (Sobol points)
   followed by local refinement, with duplicate minima merged. `differential_evolution` is a fallback
   only.
4. **Weighting:** σ_k comes from the spectral analysis (line width, fit error), plus a **model-error
   floor** (for example 1–2% of |D| or a few Hz) that covers vibrations and anisotropic J. Never use a
   relative tolerance as the acceptance rule (B08). It can never accept couplings near zero, and with
   the legacy default of 10 it accepts deviations of 1000%.
5. **Statistics to report:** χ², ν = N − n_s − n_g, χ²/ν, RMS(Hz), the per-coupling normalized
   residuals (D_obs − D_calc)/σ, and the **Q-factor** `Q = rms(D_obs − D_calc)/rms(D_obs)`
   (Cornilescu & Bax 1998). If ν ≤ 0, report "exactly determined, no goodness of fit", as the legacy
   code always silently was.
6. **Uncertainties:** (a) the covariance `(JᵀWJ)⁻¹`, scaled by χ²/ν when the σ values are not trusted.
   This gives the full correlation matrix of S and g. (b) A **parametric Monte Carlo** run: perturb
   D_obs by N(0, σ), refit about 1000×, and report the spread of principal values, η, axis directions
   and geometry. This is better than the covariance for eigen-quantities, which are nonlinear in S.
   (c) A leave-one-out **jackknife** to show how much each coupling influences the result. A
   nonparametric bootstrap over couplings is unreliable when N ≈ 6–15, because resamples are often
   rank-deficient.
7. **Identifiability diagnostics** (computed before and after each fit):
   - Singular values of the weighted, column-scaled `W^½A`. Report the rank and the condition number
     κ, and warn when κ > about 10³ (threshold to be tuned).
   - The null-space vectors, named in S-element terms (for example "Sxy and Syz undetermined: all
     vectors coplanar").
   - The rank of the full Jacobian [∂D/∂s, ∂D/∂g], and parameter correlations > 0.95.
   - A physical-admissibility check: `(2S + I)/3` must be positive semidefinite (equivalently, each
     principal value lies in [−½, 1] and the eigenvalues satisfy the joint constraint). An inadmissible S
     is a strong sign of a wrong geometry or wrong signs of D.
   - **Signs of D:** spectra often give only |D|, or relative signs. Support sign patterns as a discrete
     search dimension, and enumerate patterns by χ².

## 3. Physics extensions (prioritized)

| Pri. | Extension | Notes |
|---|---|---|
| P1 | **More nuclei, total couplings** | 13C satellites give non-coplanar C–H and C–C vectors, which improves conditioning. Observed `T = J + 2D`, so store J separately. Optional J_aniso for F pairs. |
| P1 | **²H quadrupolar splittings** | `Δν_Q = (3/2)·q_CD·S_CD`. Linear in S, so it uses the same design matrix. q_CD ≈ 165–185 kHz **[unsure; make it a user parameter]**. |
| P1 | **Discrete conformers (RIS)** | `D = Σ_c p_c A_c s_c`. One shared S is valid only for symmetry-related conformers (ring flips). |
| P2 | **Additive Potential (AP)** | Emsley, Luckhurst et al. `U(ω,δ) = −Σ ε_2m C_2m(ω)` summed over fragments, plus `V(δ) = Σ V_n cos nδ`. S(δ) and P(δ) come from quadrature. Fit ε and V_n. The standard approach for biphenyls **[citations to check]**. |
| P2 | **Maximum Entropy** | Catalano, Di Bari, Veracini, Shilstone, Zannoni (JCP, ca. 1991) **[unsure]**. The least-biased P(δ); pairs with AP. |
| P2 | **Vibrational corrections** | About 1–5% on D. Needs a QM harmonic force field. Reorientation–vibration coupling matters for small molecules **[citations to check]**. Optional ΔD_vib per coupling. |
| P2 | **Weak-alignment RDCs** | Same math, S ≈ 10⁻³–10⁻⁴, alignment tensor `A = (2/3)S`. Biggest gain in users for the least code. |
| P3 | **Anisotropic shifts (RCSA)** | `Δδ ∝ Σ S_ab σ_ab` (factor 2/3 in the common convention **[check]**). Needs an isotropic reference. |
| P3 | **Direct spectral fitting** | Hamiltonian (Zeeman + J + D), diagonalized in Mz blocks (N ≤ 12 spins is feasible). Fit with a global then local search, as in the LEQUOR/ARCANA lineage and evolutionary strategies (Meerts, Celebre et al.) **[unsure]**. Removes the correlated errors of the spectrum → couplings step. |

## 4. Libraries and reference tools

- **Core (confident):** NumPy and SciPy (`lstsq`, `svd`, `least_squares`, `qmc.Sobol`); **lmfit**
  (bounded parameters); **emcee** (posteriors); **JAX** (autodiff through the model);
  **Hypothesis** (property tests); **uncertainties** (error propagation). In the JAX ecosystem,
  **optimistix** exists, and I believe **jaxopt** is deprecated **[verify]**.
- **Structures:** **RDKit** (SDF/MOL, ETKDG conformers, dihedral setting) and **Open Babel** are both
  maintained. **ASE** reads XYZ. **CREST/xtb** generate ensembles. **cclib** reads QM geometries and
  Hessians.
- **Spectra:** **nmrglue** reads Bruker and Varian data. **Spinach** (MATLAB) handles general
  anisotropic spin dynamics. **nmrsim** handles isotropic spin systems only **[unsure whether it
  supports D]**.
- **Cross-check references, not dependencies:** REDCAT (SVD order-matrix analysis), PALES (steric
  alignment), MSpin (commercial RDC/RCSA), Xplor-NIH, and ConArch+ **[unsure of availability]**.
  I know of no maintained open-source tool for strongly-aligned LC-NMR conformational analysis with
  AP/MaxEnt. That gap is this project's niche **[moderately confident]**.

## 5. Validation strategy

1. **Analytical cases (exact to 1e-12):**
   - A single pair along z gives `D = K·Szz/r³`.
   - A regular-hexagon para-disubstituted ring recovers S exactly, with ρ = 0.
   - A synthetic molecule with known S and geometry, and noise-free couplings, recovers both
     (round trip).
   - A coplanar set gives rank 3, with the diagnostics naming Sxy and Syz.
   - The scale degeneracy is detected when no distance is fixed.
2. **Property-based tests (Hypothesis):**
   - Rotation invariance: rotate the molecule by a random R. The fitted S must transform as
     `R S Rᵀ`, while the principal values, η and χ² stay invariant.
   - Swapping i and j changes nothing.
   - Permuting the order of the couplings changes nothing.
   - Mirror geometry gives identical D.
   - Scaling σ by c leaves the best-fit parameters unchanged and scales χ² by 1/c².
   - The trace of the reconstructed S is 0.
   - MC error bars shrink as 1/√(data quality).
3. **Literature benchmarks** (exact numbers to be collected **[literature task]**):
   - Benzene in nematic phases: a single Szz. Its D_ortho : D_meta : D_para ratios test geometry and
     vibrational corrections.
   - Mono-, di- and tri-fluorobenzenes: H–F and F–F couplings, with J_aniso for F.
   - para-Disubstituted benzenes: the ring-distortion case.
   - **Biphenyl and 4,4′-disubstituted biphenyls in nematics:** reported inter-ring dihedrals are about
     30–37° in LC phases, versus about 44° in the gas phase (electron diffraction)
     **[values from memory: verify]**. Run the full RIS, AP and MaxEnt chain here.
   - Weak-alignment RDC test sets for small organics (e.g. strychnine or menthol in PBLG / stretched
     gels) **[unsure which public datasets exist]**.
4. **Golden tests against the legacy code.** Build the legacy numerics in `tools/legacy-harness`.
   For D4, D2 and no-symmetry projects, freeze the inputs and outputs. Each golden file records
   **which bugs it exhibits** (B01 Szz = 99, B02, B04 1.6e-4 eigenvalue error, B12 sign flips, B13
   biphenyl axis, B44 at 90°). The new code must match the legacy results where no bug applies, and
   must differ in the documented direction where one does. Golden files are regression evidence, not
   ground truth.

## 6. Units and conventions to standardize

- **Internal units:** Hz for couplings and splittings, Å for lengths, radians for angles,
  Hz·Å³ for K (H–H = −120 120 Hz·Å³). kHz and degrees are display-only. Fix the legacy "mHz" and
  "Amstrong" labels (B31).
- **K sign:** `K = −(μ0/4π)·γiγjħ/(2π)`. It is negative for like-sign γ and positive for pairs that
  include 15N (or 29Si). Do not take absolute values.
- **Hamiltonian convention:** like spins use `H_D = Σ D_ij(3I_ziI_zj − I_i·I_j)`, so the doublet
  splitting of an isolated pair is 3|D|. Unlike spins use `2D I_zI_z`, with total coupling `J + 2D`.
  Weak-alignment RDC papers often define the splitting as `J + D`. Store the convention per dataset
  and convert on import.
- **Order matrix vs. alignment tensor:** Saupe `S_ab = ½⟨3cosθ_a cosθ_b − δ_ab⟩`, and `A = (2/3)S`.
  Always label which one is meant.
- **Molecular frame:** defined by atoms (origin atom, z-axis atom pair, atom in the xz plane) and
  right-handed. Store it with the project so results are reproducible. Report S both in the
  molecular frame and in the principal frame.
- **Principal values:** order them `|Szz| ≥ |Syy| ≥ |Sxx|`, with asymmetry
  `η = (Sxx − Syy)/Szz ∈ [0, 1]`. Report the principal axes as direction cosines and as ZYZ Euler angles
  (active rotation, stated explicitly). Also report the generalized degree of order
  `GDO = √((2/3)·Σ S_ab²)`.
- **Angles:** the dihedral uses the IUPAC sign convention. Since its sign is undeterminable (§1.5),
  report |δ| together with its folding domain.
- **Uncertainty:** every observed value carries a σ, in the same units, with a recorded origin
  (spectral fit / estimated / default floor).
