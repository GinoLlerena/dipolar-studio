# Round 1 — independent verification of the legacy bug report

Reviewed 2026-11-07 against [GinoLlerena/NMRApllication](https://github.com/GinoLlerena/NMRApllication) at `34a0bff`, including the analysis in `docs/legacy/01-legacy-analysis.md` and all 45 claims in `docs/legacy/02-bug-report.md`. Source references below use the original files' line numbers; Latin-1 decoding and CRLF removal for scratch compilation do not change those numbers.

**Method and limits.** Read the cited implementations and relevant constructors, UI handlers, serializers, and callers. Rebuilt the supplied harness from fresh, otherwise unmodified `Matriz.cpp`/`SistEcuac.cpp`; independently compared with NumPy. Also compiled the original point, spherical-coordinate, angle, trigonometric, perpendicular-point, and calculated-interaction implementations using small MFC stubs; exercised verbatim extracted fragment-rotation and cylinder-orientation methods. Archive stubs do not validate actual MFC archive behavior, and no Windows GUI build was run. Scratch work was kept outside the repository; no legacy repository file was modified.

**Verdicts.** CONFIRMED means the substantive defect holds, even if a minor reference or qualification needs correction. PARTIALLY CORRECT means a material part of the mechanism, scope, consequence, or claimed intent is unsupported or wrong. REFUTED means the alleged failure does not follow on the inspected normal path. CANNOT DETERMINE would require missing evidence. Severities retain the report's definitions: S1 wrong science/crash, S2 behavior/data loss, S3 robustness/portability.

## Per-ID findings

| ID | Verdict | Justification | Corrections |
|---|---|---|---|
| B01 | CONFIRMED | `Matriz.cpp:261–264` changes N to 2 and puts the retained z eigenvalue in `EI[2][3]`; `:233` replaces exactly that cell with 99. The original harness reproduces `(-0.22071, -0.07929, 99)` for a D2-form tensor with nonzero xy. | S1 and references stand. The all-diagonal fast path returns earlier, so the nonzero-xy qualification matters. |
| B02 | CONFIRMED | At `Matriz.cpp:271–272`, the original yy value is already lost when `dValor` is assigned, and `:281` reconstructs yy from the largest xz-block eigenvalue and the original xx diagonal, rather than retaining yy. For the supplied tensor, yy becomes −0.2061538 instead of −0.2. | S1; use `:270–281`. The correct eigenvalue multiset is `{-0.2, -0.1061552813, 0.3061552813}`; eigenvalue ordering is a separate convention. |
| B03 | CONFIRMED | With xy=xz=0 and yz nonzero, neither reduction branch applies; the Householder first column has S=H=0. Divisions at `Matriz.cpp:188,194` produce NaNs, reproduced with the original source. | S1; cite `:149–194` as the complete cause, not only the H assignment at `:162`. |
| B04 | CONFIRMED | The ±99 sentinels, unguarded interpolation, absolute cutoffs, and silent iteration limit are real; the supplied general tensor has maximum eigenvalue-set error `1.573804986e-4`. Additional tests found much larger errors for ordinary order-sized matrices and for small matrices. | S1; add `Matriz.cpp:102–117,202–203,222–233`. ±99 are assumed outer bounds, not enforced bounds: regula falsi can extrapolate outside them. The error cannot be attributed exclusively to zeroing; see the numerical evidence below. |
| B05 | CONFIRMED | `ExaminaMatriz` tests `m_bEcuacion[j]` at `SistEcuac.cpp:198`, although `:209` marks solved equation row i, causing unrelated variable columns to disappear from later row scans. A full-rank example with exact solution `(1,2,3)` returns `(0,3,4)` without entering the reduced-dimension branch. | S1, independently reproduced; use `:198–214`. Solved-equation and solved-variable state need distinct meanings. |
| B06 | CONFIRMED | The original partial-path example returns `(1,2,14)` and leaves `DevuelveCantVariab()` equal to 2. The shifts, zero-as-unknown convention, and missing restoration at `SistEcuac.cpp:261–278` all occur in the source. | S1; include `:75–77,323–326` for the wrong output column. A zero known value also breaks the reduction: the same matrix with exact solution `(0,2,3)` returns `(5.5,-1.5,4)`. |
| B07 | CONFIRMED | Both singular-pivot exits return no failure status, and the caller still reads the augmented column as a solution. For `A=[[1,1],[2,2]], b=[3,6]`, the original solver reports `(6,0)`. | S1; the returned values can be **partly eliminated RHS values**, rather than necessarily the unchanged input. References `SistEcuac.cpp:131–134,161–176` and `RealizadorCalculo.cpp:416–428`. |
| B08 | PARTIALLY CORRECT | The default is exactly 10 and the acceptance threshold is exactly `10*abs(Dobs)`, with no division by 100 in the UI-to-calculation path. However, neither `Proyecto.rc:211` nor the help text explicitly calls the field a percentage, so the intended 10% interpretation is an inference from `m_dPorcentaje` and context. | The factual 1000% relative-error allowance is confirmed; the missing-percent-conversion diagnosis is not proven. Zero observations still require exact agreement, and arbitrary bad/singular predictions are not automatically accepted; remove “almost every grid point.” |
| B09 | PARTIALLY CORRECT | Zero increments can hang `ProcesoIteractivoDeVariacion` when another parameter makes the product exceed one, and ordinary positive decimal steps can miss an endpoint. Negative increments can hang **earlier**, in the total-counting loop, before reaching the cited recursive loop. | Keep hang severity; add `ParametroVariable.cpp:103–116` and `RealizadorCalculo.cpp:219–240`. A nonpositive step only hangs when the relevant initial≤final loop condition is entered; negative-step failure does not require a second parameter. |
| B10 | CONFIRMED | `RealizadorCalculo.cpp:270,284–299` averages by an unchecked matching-component count, so an observation with no matching components generates 0/0 coefficients. The usual observation-creation handler adds a default component, which reduces normal-path reachability but does not make this routine safe. | S1 conditional on missing/mismatched components, not a claim that every newly created observation has none. `InteraccObservadaPageOne.cpp:293–299` supplies the normal default. |
| B11 | CONFIRMED | `CPunto` defaults to zero and `ProyectoDoc.cpp:231–244` returns it on lookup failure; downstream geometry therefore silently substitutes the origin. If the other point is also the origin, `CoordEsf.cpp:45` and the r³ divisions encounter zero denominators. | S1; missing labels also leave the type empty, so K can become zero: the result may be zero or NaN rather than necessarily an infinite coupling. |
| B12 | CONFIRMED | In the independent-coefficient path, the wrong quadrant reverses the nonzero yz and zx Cartesian cross terms for x<0 while leaving zz, xx−yy, and xy unchanged. Compiled-source tests also show that `(0,-2,3)` incorrectly has the same yz coefficient as `(0,2,3)`. | S1; the sign statement applies to **nonzero** cross terms. At x=0, zx should be zero, so it is yz that changes sign; an identically zero term has no sign to reverse. See the derivation below. |
| B13 | PARTIALLY CORRECT | `ParteRigida.cpp:615–617` translates about P1 but rotates about vector P1 from the global origin; that is generally different from the intended P1−P0 axis. A translated test gives P2=`(1.5,0.70710678,1.5)` where rotation about the actual bond gives `(1,1,1)`. | S1, but “every non-root biphenyl” is false. Non-root placements can still have the same directed axis, zero rotation masks the defect, and reversed collinear axes reverse the rotation angle; arbitrary root placements can fail too. |
| B14 | PARTIALLY CORRECT | The trifenil branch really ignores incoming `cPtoC` and first supplies `(0,0,0)` as its reference point. The four-argument perpendicular routine normalizes a zero cross product for a collinear **general-axis** input, but its axis/coordinate-plane special cases bypass that normalization and can remain finite. | S1 for the NaN case; qualify the blanket origin-axis claim. Cite `ParteRigida.cpp:313,397–398` and `PtoPerpendicular.cpp:50–58,104–157`; the default z-axis placement is not itself proof of a NaN. |
| B15 | PARTIALLY CORRECT | The mismatch is real: biphenyl rendering uses spins 0/2 at P0/P2, while the bond editor stores labels in spins 0/1 and calculation maps those to bond finals P1/P2. Thus the ordinary first terminal label uses P1 instead of P0, but the ordinary second label is in spin 1 and calculates at P2, not at unused bond 2. | S1 for the first-site coordinate error; `m_cLado[2]` is initialized storage with default-origin endpoints, not an undefined array element, and spin-2 labeling is not the ordinary editor path. References `ParteRigida.cpp:88–90,249–265,486–497`, `EnlacePageOne.cpp:219`; trifenil's fourth terminal has a related P3/P4 mismatch. |
| B16 | CONFIRMED | `Fichero.cpp:59` copies an arbitrarily long `CString` into the 60-TCHAR local array declared at `:57`. A path of 60 characters requires 61 elements including the terminator and overflows it. | S1; the actual unsafe copy is `:59`, with a maximum safe path length of 59 TCHARs. This is independent of Windows' much larger normal path capacity. |
| B17 | CONFIRMED | Removing every fragment deletes the object but leaves `pObjParteRigida` dangling, and the storing branch subsequently archives that pointer. When some fragments remain, `ListaPartesDlg.cpp:145–150,169–172` normally reassigns the active pointer, so the strongest concrete trigger is deleting all parts or clearing the document. | S1; pointer allocation is at `ConstructorMolecula.cpp:119–121`, deletion at `:220–222`, and archive access at `ProyectoDoc.cpp:138`. Do not imply that every deletion leaves the active pointer dangling after the dialog handler finishes. |
| B18 | CONFIRMED | `Distorcion.cpp:150,155,161` performs all three divisions without domain checks or a failure return. Zero/default observations and K=0 can produce NaNs, and ρ=1/3 is a pole in the last expression. | S1; `ProyectoView.cpp:692–710` checks only empty label strings, while distortion labels initially contain a space (`Distorcion.cpp:26–28`), so those checks do not reliably reject unconfigured distortion inputs. |
| B19 | CONFIRMED | `CLado::Serialize` saves the state/type and geometry but never `m_strEtiqueta`. Reloading constructs bonds with the default blank label, so parameter matching at `RealizadorCalculo.cpp:109–112` is lost. | The reference is `Lado.cpp:179–195`. Under the report's definition, silent loss of a geometry sweep binding merits **S1** for wrong scientific results, as well as S2 persistence loss. |
| B20 | PARTIALLY CORRECT | Spherical coordinates are indeed omitted from the archive, and a newly loaded component has default coordinates until recomputed. However, the coefficient array is serialized and every normal calculation calls `CalculaCoeficientes`, which refreshes coordinates before using them. | Downgrade to S3 cache/persistence consistency unless a consumer of the unrefreshed cache is demonstrated; this is not established as a wrong-results-after-reload bug. Reference `InteraccCalculada.cpp:111–126`, `RealizadorCalculo.cpp:202,328–346`. |
| B21 | PARTIALLY CORRECT | The MFC runtime-class chains really skip the C++ intermediate bases, so intermediate-base `IsKindOf`/typed archive checks can fail. Schema 0 is nevertheless legal, and it does not by itself make migration impossible or prevent the explicit base serializers from running. | Separate the runtime ancestry defect from versioning policy; S3 on the demonstrated evidence, not an established S2 failure in the current CObject-based lists. The immediate bases should follow the headers; see the MFC reference below. |
| B22 | CONFIRMED | The only assignment of the distortion distance is in the settings dialog's `OnOK`; the sweep repeatedly calls `RealizaCalculos` on that retained value. Since both distortion order expressions scale with r₁₂³, an actual change of that distance is omitted. | Promote to S1 for affected sweeps. `CalculoTensoresPageDos.cpp:117–118`, `Distorcion.cpp:155,160`, `ProyectoDoc.cpp:736–742`; it is conditional on r₁₂ really depending on the swept geometry. |
| B23 | PARTIALLY CORRECT | `DevuelveDistanciaRij` does return −1 on parsing failure, and `OnOK` stores it without validation. However, the normal dropdown supplies formatted observed-pair labels, and an invalid selection often also produces zero D/K, so a clean sign-flipped finite tensor is not demonstrated by the parse failure alone. | Retain as an unchecked invalid-distance path, S3 for the specific malformed-selection claim; wrong/nonfinite science is S1 if that state is used. References `CalculoTensoresPageDos.cpp:117–120,154–158,176,180–204`. |
| B24 | CONFIRMED | `DevuelveEtiquetasDij("A,B")` returns first label `A` and second label `,B`, because the substring length includes the comma. This can fail lookup and invoke the origin fallback. | S2 parsing defect with possible S1 downstream consequences. Reference `Rutinas.cpp:273–281`; normal generated `"A, B"` strings take the other branch. |
| B25 | REFUTED | No A/B canonical ordering is imposed when the selection choices are populated: `CalculoTensoresPageUno.cpp:88–107` and `CalculoTensoresPageDos.cpp:73–87` copy the observation's own order. An observation entered as `"B, A"` produces the same `"B, A"` selection and calculated-row label, so reversing its original entry alone does not make the row vanish. | Exact-string matching is real at `ProyectoDoc.cpp:669–682`, but the alleged normal trigger is false. Editing/renaming/deleting an already selected observation creates a different, real stale-selection bug, listed below. |
| B26 | CONFIRMED | The comparison includes access time and absolute stored names, and a mismatch suppresses reopening with the warning commented out. Even a successful comparison returns only `GetFileName`, so subsequent reads depend on the working directory. | S2; reading **can** change access time depending on filesystem settings/timing, not necessarily on every read. Cite `Rutinas.cpp:201–244`, `RealizadorReporte.cpp:138–161`; metadata comparison is not a content-integrity check. |
| B27 | PARTIALLY CORRECT | The helper does discard the selected directory by passing `GetFileName()` to `Abre`. But no caller of `AbreConDlg` exists in this tree, and a Windows file dialog can itself change the working directory, so the asserted wrong-folder result is not established for a live application flow. | Downgrade to S3 latent helper defect. The main calculation path uses `GetPathName()` correctly at `ProyectoView.cpp:738`; avoid presenting the unused helper as a reproduced user-visible S2 bug. |
| B28 | CONFIRMED | The application registers `CSingleDocTemplate`; `OnNewDocument` only calls the base, and `DeleteContents` clears lists/counters while leaving the reported scalar and configuration state intact. A new document therefore inherits those settings rather than restoring constructor defaults. | S2; correct the start reference to `ProyectoDoc.cpp:573`, plus `:99–104` and `Proyecto.cpp:102–107`. The active pointer is also not reset, overlapping B17. |
| B29 | PARTIALLY CORRECT | The UI really deletes the entire suffix of the fragment list and leaves interaction references intact, rather than checking graph descendants. However, decrementing per-type counters while deleting a suffix preserves the sequential numbering of all surviving automatically named parts; duplicate names do not follow from this deletion path. | S2 data-loss/dependency defect, but remove the duplicate-name example absent another trigger. `ErrorMsg.h:49` warns about linked descendants, while `ListaPartesDlg.cpp:136–142` removes all later entries; constructor deletion itself removes only one item. |
| B30 | CONFIRMED | Searches of all sources show these preferences are assigned, displayed, and archived, but never supplied to the solver or selector. The solver uses `1e-5`, and the selector stores a maximum index of 24, i.e. capacity 25. | S2; correct the literal at `Seleccionadora.cpp:21` to **24**, with the inclusive indexing explanation. Also `:93` resets that hard-coded limit. |
| B31 | CONFIRMED | Parameter units are hard-coded as degrees in both printed and interactive results, regardless of what geometry is being varied. The document's default `mHz` conflicts with the kHz-scale constants and with result displays that explicitly say KHz. | S2; add `ResultadosOnePageTwo.cpp:142–143`. `ProyectoDoc.cpp:76` is a spelling issue only; the wrong coupling unit is at `:78`, while printed couplings already use KHz (`RealizadorReporte.cpp:239`). |
| B32 | CONFIRMED | Only the six H/D/F pair combinations return a nonzero constant; everything else silently returns zero at `InteraccCalculada.cpp:104`. For finite nonzero r this yields a zero interaction regardless of tensor values. | S2 for silently accepting an unsupported pair, potentially S1 science. Distinguish explicitly offered Cl/Br types from hypothetical ¹³C support; no isotope-specific ¹³C implementation is present. |
| B33 | CONFIRMED | If A=B, none of the classification conditions assigns n before it is returned. For nondegenerate inputs, the four-argument routine ignores C in special positions but uses the ABC-plane normal in position 7, so its chosen perpendicular direction changes discontinuously. | `PtoPerpendicular.cpp:104–127,132–157`; A=B is the UB case. Both constructions are perpendicular to AB—the distinction is arbitrary perpendicular versus a reference-plane normal, not perpendicular versus nonperpendicular. S1/S2 for geometry contamination; S3 if only rejecting degenerate inputs. |
| B34 | PARTIALLY CORRECT | Raw native struct persistence and unchecked 40-TCHAR label copies are real. Taking the address of the returned temporary is rejected by standard C++ but, when accepted as the legacy MSVC extension, the temporary survives the full synchronous `Escribe` call; it is not itself a dangling-pointer write. | Actual overflow sites: `Parametro.cpp:79`, `ValorDual.cpp:92–93`, with sizes at `Structures.h:43,49–50`; labels of length ≥40 overflow. Classify the overflow as S1 crash/corruption risk, and separate it from S3 portability/language-extension issues at `ProyectoDoc.cpp:302,324`. |
| B35 | CONFIRMED | The type-change handler enables labels for Deuterio, while the initialization/enabling handler accepts only Fluor/Proton. Reopening or changing the selected bond can disable a previously editable deuterium label. | S2; the first predicate is at `EnlacePageOne.cpp:201`, not `:198`; the second is correctly at `:377`. Reselecting the type can reenable it, so “cannot be edited” is not absolute. |
| B36 | CONFIRMED | The `else` binds to the inner decimal-fraction test, so all negative inputs fall through to truncation; for example, the legacy function returns −1 for −1.7. Its conflicting return type against modern `round(double)` is a compile issue, while redefining M_PI is a separate hygiene issue. | S3; use `Mathemat.cpp:42–57`. The declaration in `Mathemat.h:41` is commented out, and current callers may resolve the standard round; do not assume this broken implementation is used by the actual grid-count calculation. |
| B37 | CONFIRMED | `(iPaso != 2) \|\| (iPaso != 5)` is a tautology, so both intended exclusions are ignored. For a valid nonzero rotation axis, P2 is the translated origin and P5 is on the axis, so their mathematical positions are unchanged. | S3; `ParteRigida.cpp:599–606`. Floating-point roundoff and a degenerate zero axis qualify the “harmless” statement. |
| B38 | CONFIRMED | The local `CPen` is selected into the DC without retaining/restoring its predecessor before the function returns. Its destructor then tries to delete a selected GDI object, which can fail and leak the handle. | S3 initially, potentially resource-exhaustion failure during extended use. Reference `ParteRigida.cpp:537–539` and function exit `:558`; creating a pen per paint is not by itself the bug. |
| B39 | CONFIRMED | Every visible spin creates a quadric and calls `ss_InitMaterials()` for its sphere on each draw; the fragment adds another material initialization. This is unnecessary recurring work in the render path. | S3 performance issue, **not a proven memory leak**: `Spin.cpp:154` deletes the quadric, and `Lado.cpp:242` does likewise. Include the per-sphere initialization at `Spin.cpp:147`. |
| B40 | REFUTED | The textual dereference precedes its nearby null test, but an earlier `FindIndex`/non-null POSITION guard already verifies that the same list index exists. The getter retrieves that same entry synchronously, and inspected list-creation paths add constructed non-null objects, so no null trigger is established. | Remove as a demonstrated bug; `InteraccObservadaPageOne.cpp:328–338` and `ProyectoDoc.cpp:410–426`. A list corrupted to contain null pointers would be a different precondition, not evidence for this claimed flow. |
| B41 | CONFIRMED | On a platform with RAND_MAX=INT_MAX, `RAND_MAX+1` overflows in integer arithmetic before the float cast. MSVC's smaller RAND_MAX avoids this particular overflow. | S3 portability; `Material.cpp:131`. Qualify “non-MSVC platforms” to those whose RAND_MAX equals INT_MAX. |
| B42 | CONFIRMED | `ulPosicion` is unsigned, so zero wraps in the one-based record offset calculation; file-operation exceptions are suppressed outside Debug and the function has no success return. It can continue to read after a failed seek. | S3 for the invalid-zero-index path; unchecked short reads are a separate active S1/S2 problem below. Reference `Fichero.cpp:70–95`, and write-error swallowing at `:106–112`. |
| B43 | CONFIRMED | `iPaso` is introduced inside the first for initializer and then reused by the second loop outside its standard scope. Standard-conforming compilation rejects that use. | S3 portability/build issue; `ParteRigida.cpp:646,653`. MSVC's legacy `/Zc:forScope-` behavior is the relevant historical escape, not a guarantee of compatibility on other compilers. |
| B44 | CONFIRMED | The D4 coefficient contains `tan(dihedral)` and looks up the angle through the exact parameter label `Dihedral`, defaulting to zero when absent. Near 90° the formula is singular/ill-conditioned; a floating implementation typically returns a huge finite number at 90°, not literal infinity. | Restrict to **D4**, `InteraccCalculada.cpp:212–239`, `ProyectoDoc.cpp:215–228`. Potential S1 scientific failure near the pole; whether the reduction is valid away from it needs the model derivation, not just a guard. |
| B45 | CONFIRMED | `git ls-files` confirms the listed generated artifacts are tracked, including Debug objects, the SDF, NCB, APS, OPT, SUO and IPCH files. The SDF size is 81,723,392 bytes. | S3 repository hygiene; “81 MB” is a fair decimal approximation, about 77.94 MiB. No scientific/runtime failure follows merely from tracking these files. |

## Physics checks

### Dipolar prefactors: right scale and sign, overstated precision

For angular-frequency magnetogyric ratios, the stated convention gives

`Kij = −(μ0 / 4π) γi γj ħ / (2π)`,

with a factor `10^27` converting Hz·m³ to kHz·Å³. This is the same expression as `−μ0 γi γj ħ/(8π²)` in the analysis. Using γH=`2.67522128e8`, γD=`4.10662791e7`, γF=`2.518148e8` rad·s⁻¹·T⁻¹ from the [IUPAC nuclear-spin tables](https://www.princeton.edu/~nmr/IUPAC_NMR.pdf), ħ=`1.054571817e−34` J·s and μ0/(4π)≈`1e−7` gives:

| Pair | Legacy K (kHz·Å³) | Independent K | Relative magnitude error |
|---|---:|---:|---:|
| H–H | −120.120 | −120.120108 | −0.000090% |
| D–D | −2.830 | −2.830525 | −0.01855% |
| F–F | −106.302 | −106.428709 | −0.11906% |
| H–D | −18.439 | −18.439170 | −0.000919% |
| H–F | −113.000 | −113.067361 | −0.05958% |
| F–D | −17.346 | −17.356530 | −0.06067% |

Thus there is no orders-of-magnitude or overall-sign mistake, and kHz/Å is the correct scale. However, calling **all** constants correct to 3–4 significant figures overstates their accuracy, particularly the fluorine constants. These small errors are not explained by confusing MHz/T with angular-frequency units; they also exceed the tiny modern update to the proton ratio. Fundamental quantities can be checked against the [NIST constants listing](https://physics.nist.gov/cuu/Constants/Table/allascii.txt). This checks the prefactor convention written in the analysis; assigning an experimentally quoted splitting to D versus 2D still requires the experiment/thesis convention.

### Angular tensor coefficients: algebra passes; coordinate conversion does not

For a symmetric traceless tensor T, write Δ=Txx−Tyy and `u=(x,y,z)/r`. Then

`uᵀTu = Tzz*(3z²/r²−1)/2 + Δ*(x²−y²)/(2r²) + Tyz*2yz/r² + Tzx*2zx/r² + Txy*2xy/r²`.

With θ=`acos(z/r)` and φ=`atan2(y,x)`, these are precisely the five expressions in `InteraccCalculada.cpp:157–179`. The code calls the polar angle Phi and the azimuth Teta; the analysis renames them conventionally, which is fine. `Trigonom.cpp:20–87` and `Angulo.cpp:51–60,78–85` consistently convert degrees/radians.

B12 is nevertheless real. For x<0, `atan(y/x)` replaces the transverse direction `(x,y)` by `(-x,-y)` without reversing z. The terms 2yz and 2zx reverse sign, whereas z², x²−y², and 2xy do not. This is not the harmless full reversal `u→−u` under which a dipolar interaction is invariant.

Compiled-source H–H coefficients for vector `(-1,2,3)` are:

`[-1.06465424725, 0.245689441672, +1.96551553338, −0.982757766689, +0.655171844460]`.

The correct Cartesian coefficients have yz=`−1.96551553338` and zx=`+0.982757766689`; the other three agree. For `(0,−2,3)`, the correct yz coefficient is `+2.36558299067`, while the code produces `−2.36558299067`. The squared/2φ expressions in D2 and D4 avoid this particular quadrant sign error, but that does not validate the full symmetry reductions.

The report also should not imply that the **D4** coefficient is simply the standard five-term formula with three terms dropped. At `InteraccCalculada.cpp:225–226`, it contains an additional `tan(dihedral)*sin(2φ)` contribution. Its scientific derivation needs the thesis; a separate inconsistency with the saved/reported tensor is described as M10 below.

### Rodrigues rotation: confirmed for a nonzero axis

The actual multiplication order at `Punto3D.cpp:138–140` makes the seemingly transposed temporary factors exactly the right-handed active Rodrigues matrix `R(v)=v cos α+(u×v)sin α+u(u·v)(1−cos α)`. Do not flag the sine signs merely by reading the intermediate variable names.

Against an independent cross-product/dot-product implementation, 1,000 deterministic random vectors/axes/angles agreed to maximum absolute component error `4.4408920985e−16`. The test `Rz(90°)*(1,0,0)` gives `(0,1,0)`, and rotation preserves a vector along its own axis. **The nonzero-axis precondition is unchecked:** a zero axis yields NaNs even for a zero angle at `:124–126`; this is distinct from an incorrect Rodrigues matrix.

### Traceless reconstruction: confirmed

`RealizadorReporte.cpp:322–323` correctly computes `Txx=(Δ−Tzz)/2` and `Tyy=Txx−Δ=(−Δ−Tzz)/2`. That correctness does not rescue the eigenvalue routine or establish a consistent principal-axis labeling/order convention.

### Cylinder orientation: the reported pass is false

Verbatim `CLado::Construye`, `DeterminaPosicion` and `SituaEnEspacio` were executed with CPU stubs implementing OpenGL's postmultiplication order; all 124 nonzero vectors on the component grid `{−2,−1,0,1,2}³` were checked. The xy-plane branch fails: `Lado.cpp:221–223` classifies temporary vector `(x,0,y)` but passes the **original** `(x,y,0)` into the angle routine, whose denominator is then zero.

For the bond vector `(1,2,0)`, the transformed cylinder axis is approximately `(1,0,0)` instead of `(1/√5,2/√5,0)`. This is a reproducible rendering defect, not merely fragile but correct code. It does not itself alter the stored bond endpoints or coupling calculation.

## Numerical reproduction details

The supplied baseline was rebuilt with `clang++ -std=c++17 -w -Isrc test.cpp src/Matriz.cpp src/SistEcuac.cpp`. The original four numerical source/header files were copied through Latin-1 decoding, with CR removed; their algorithms were not edited. Baseline outputs match the README, including the full-Gauss control `(1,2,3)`.

Additional tests used a scratch `probe.cpp` accepting full matrices and returning the original class results:

- **B05 independent of B06:** `A=[[0,0,1],[1,1,0],[1,0,1]]`, `b=[3,3,4]`, determinant −1, expected `(1,2,3)`, returned `(0,3,4)` with the original dimension still 3.
- **B06 dimension loss:** `A=[[2,0,0],[1,3,1],[1,1,4]]`, `b=[2,10,15]`, expected `(1,2,3)`, returned `(1,2,14)`, final dimension 2. With `b=[0,9,14]`, expected `(0,2,3)`, returned `(5.5,−1.5,4)`.
- **B07 singular result:** `A=[[1,1],[2,2]], b=[3,6]` returned `(6,0)` without a failure signal.
- **B04 ordinary-scale severe error:** matrix `[[−0.105982318644915,−0.050385516736134,0.023611507918127],[−0.050385516736134,0.009709435283626,0.074291702508708],[0.023611507918127,0.074291702508708,0.096272883361289]]` has NumPy eigenvalues approximately `[-0.13592934,−0.00313645,0.13906579]`; legacy returns `[-0.13590525,−0.00313645,0.01821437]`. The maximum error is about 0.12085, and the returned trace is substantially wrong.
- **B04 scale failure:** the baseline general matrix scaled by `10^−6` should have eigenvalues about `[-2.21492e−7,−8.16234e−8,3.03115e−7]`; legacy returns `[0,45.15279703,82.41330865]`. These are physically small, valid order values, so the problem is not limited to unphysical eigenvalues outside ±99.
- A bounded check of 100 random symmetric traceless matrices, using NumPy `default_rng(12345)`, independent N(0,0.1²) entries, symmetrization `(A+Aᵀ)/2`, and trace removal, found 99 with eigenvalue-set maximum error above `1e−5`; the worst is the ordinary-scale example above. This sample is evidence of a broad numerical problem, not a population-wide failure-rate estimate.

The finite-output tests do not depend on uninitialized matrix contents: caller-used matrix entries are assigned in full. No repaired solver or substituted NumPy solver was used to generate a legacy result.

## Important missed bugs

These findings are separate from the 45-ID verdict counts. “Confirmed by reading” identifies deterministic source/data-flow evidence rather than pretending a Windows GUI reproduction occurred.

### M01 — stale observed values and selections used for solving (S1)

**Where:** `CalculoTensoresPageUno.cpp:146–153`, `CalculoTensoresPageDos.cpp:115–140`, `InteraccObservadaPageOne.cpp:251–261`, `RealizadorCalculo.cpp:394–401`; stale-label validation at `ProyectoView.cpp:673–688`.

The settings dialog copies selected observed coupling values into `m_cInteraccSelecc`; later solves read those copies, not the current observed list. Editing an observation's numeric value updates the list but neither selected copies nor the distortion model's cached observations. A subsequent calculation therefore fits the **old** observations while acceptance compares with the **new** ones; the loose default tolerance can let the wrong scientific result through. Renaming/deleting a selected observation likewise leaves a nonempty stale label, which passes validation but can produce a missing/zero equation. This is the concrete stale-state failure that B25 should have reported. Confirmed by reading the complete update and use paths.

### M02 — selected equations ignore the per-observation tensor-use flags (S1)

**Where:** `RealizadorCalculo.cpp:390–410` versus `:55–58`, `ProyectoDoc.cpp:696–721`; user flags at `InteraccObservadaPageOne.cpp:254–258`.

The solve inserts all symmetry-appropriate coefficients for a selected observation; it never applies that observation's `UsoTzz/UsoTxxMinusTyy/UsoTyz/UsoTzx/UsoTxy` flags. Prediction/acceptance does apply those flags, so the system fitted is not the forward model evaluated. For example, a selected D2 coupling with xy disabled and nonzero geometric xy coefficient still constrains the solver's Txy. This is not a least-squares-versus-exact-fit policy choice; the two code paths disagree about the same equation. Confirmed by reading.

### M03 — single-combination calculations apply parameters without rebuilding coordinates (S1)

**Where:** `RealizadorCalculo.cpp:192–205`; compare the sweep's explicit rebuild at `:162`; current-value editing at `ParametroPageOne.cpp:110–115`.

`RealizaCombinacionParametro` updates angles/lengths through `InicializaParametros`, then immediately computes coefficients from the already stored endpoints without calling `ReconstruyeMolecula`. A newly chosen current parameter value can therefore be saved beside couplings computed for the previous geometry. A later repaint can rebuild the drawing, but there is no repaint/rebuild between the parameter assignments and the immediate numerical calls that would make this calculation consistent. The sweep path does explicitly rebuild. Confirmed by reading.

### M04 — result pagination mixes records and selects the wrong configurations (S1/S2)

**Where:** `ResultadosOnePageThree.cpp:130,212–235`.

Every configuration occupies seven tensor/statistics records. On a full page 2, the first displayed configuration should read record 141, but the expression at `:234–235` reads record 21: it multiplies the page offset by 20 rows without also multiplying by seven records per row. The displayed tensor columns can therefore mix values from unrelated configurations and even display a MAD as Tzz.

There is a second independent offset error on the final short page: the display and selection expressions use the **current** page's row count as the page stride. With 25 configurations, page 2 contains five rows but its first configuration is labeled/selected as 6 instead of 21; interaction and parameter tabs then fetch that wrong configuration as well. Evidence is direct offset arithmetic on the one-based record reader; no MFC assumptions are required.

### M05 — xy-plane bond cylinders point in the wrong direction (S2)

**Where:** `Lado.cpp:221–223`, angle evaluation at `:319–335`.

As reproduced in the physics section, classification uses `(x,0,y)` but angle calculation receives `(x,y,0)`. The cylinder for `(1,2,0)` points along +X instead of its endpoint direction. This directly refutes the report's cylinder-orientation “pass”; the stored scientific geometry remains separate from this rendering error.

### M06 — EOF read is treated as a real fit, compounded by selector count/index confusion (S1/S2)

**Where:** `RealizadorReporte.cpp:95–105`, `Fichero.cpp:85–95`, `Seleccionadora.cpp:44–46,56–59,85–86`, `RealizadorReporte.cpp:71`, `TempView.cpp:57–58`.

`BuscaMejorAjuste` loops through `iIndex <= iTotal` even though iTotal is the number of saved configurations. The final iteration reads one configuration beyond EOF; `Read`'s byte count is ignored, and the old/uninitialized record is inserted with an out-of-range configuration index. Later consumers can print nonexistent data, and a file with zero accepted fits still enters this read path.

Separately, `m_iCantidadDatos` starts at −1 and is the **last occupied index**, but callers use `DevuelveCantidadDatos()` as a count. A single inserted fit returns 0 and fails `iIndex < ...` for page 0; a full selector returns 24 for 25 entries, suppressing a real final page. The two off-by-one defects can partially mask each other when an EOF duplicate happens to be inserted, which is not a valid correction. Confirmed by reading and one-based record arithmetic.

### M07 — an offered variable bond is never applied (S1/S2)

**Where:** `EnlacePageOne.cpp:322–325`, `RealizadorCalculo.cpp:94–114`.

The bond UI enables variable state for phenyl bonds 8 **and 11**, and stores their parameter labels. The sweep initializer matches only bond 8; it never checks bond 11, so that parameter can change in the output without its bond length changing in the geometry. This exists before any save/reload and is independent of B19. The same routine's narrow fragment-specific parameter coverage should be explicit in any rewrite specification. Confirmed by reading.

### M08 — shorter UI stack buffers overflow before the reported 40-character boundary (S1)

**Where:** `ParametroVariablePageTwo.cpp:112,134`, `ParametroPageTwo.cpp:141`, `InteraccObservadaPageTwo.cpp:125`, `ResultadosOnePageOne.cpp:129,138,149`, `ResultadosOnePageTwo.cpp:127,147`, `ResultadosOnePageThree.cpp:245–250`.

Several list views copy unrestricted label strings or `%f` output into `TCHAR palabra[25]`. A 25-character parameter label is enough to overflow the list view even though it still fits the 40-TCHAR binary record. A combined pair label can overflow even when each individual spin label is much shorter than 40 characters. Parameter-entry validation checks empty/duplicate names but supplies no length limit (`ParametroVariablePageOne.cpp:163–214`). These are additional concrete overflow sites, not covered by B16's path buffer or B34's binary-record buffers.

### M09 — important project state is not serialized (S2, possible S1 consequence)

**Where:** `ProyectoDoc.cpp:110–168`, especially `:122–123`; default plane point at `:87` and geometric use at `ConstructorMolecula.cpp:167–168`.

The document saves only the two symmetry-axis endpoints, not `m_cPtoPlano`, even though that point defines the root fragment's construction plane. The shown UI does not expose that plane point, so changed-plane persistence is latent unless it has been changed programmatically; it should not be claimed as an ordinary demonstrated UI data-loss path. More immediately, **`m_dPorcentaje` is also absent from serialization** although the other calculation preferences are written: a nondefault tolerance reverts to 10 in a fresh process or inherits another document's value in an SDI session, changing which scientific fits are accepted. This tolerance persistence defect is independent of whether the intended unit in B08 was a percentage.

### M10 — D4 predictions do not reconstruct the tensor written to the report (S1 model-consistency issue; intended convention needs the thesis)

**Where:** `InteraccCalculada.cpp:225–239`, `RealizadorCalculo.cpp:419–424`, `ProyectoDoc.cpp:192`, `RealizadorReporte.cpp:322–333`.

The D4 forward coefficient for Δ includes `0.5*tan(dihedral)*sin²θ*sin(2φ)`, algebraically equivalent in the documented coordinate frame to `Txy=0.5*Δ*tan(dihedral)`. But the D4 solve leaves stored Txy at its initialized zero, and reporting diagonalizes that stored tensor. For `(x,y,z)=(1,1,0)`, dihedral=45°, Tzz=0.3 and Δ=0.1, the compiled D4 model predicts approximately 4.2468833 kHz, whereas direct contraction of the tensor reconstructed in the report predicts 6.3703250 kHz.

This is a definite discrepancy under the tensor meanings stated in the analysis. A thesis derivation might define a transformed tensor/frame or a reduced parameter convention; without that derivation it is premature to prescribe the physical correction or declare the entire D4 model wrong. The report should flag the mismatch and withhold a blanket D4 physics pass.

### Other high-impact extensions

- **Zero rotation axis (S1 for reachable geometry):** `Punto3D.cpp:121–126` divides by the axis norm without checking it; even rotation by 0° returns NaNs for a zero axis. Besides B14, collinear A/B/C inputs give a zero normal through `PtoPerpendicular.cpp:70–75`, then phenyl/biphenyl construction passes it to `GirarLado`/`Rota3D`. Repeated symmetry-axis endpoints also cause earlier distance divisions. A correct rotation matrix is not equivalent to validated geometry inputs.
- **Nontransactional result writes and swallowed write failures (S2):** `ProyectoDoc.cpp:293–388` appends parameter, interaction and tensor records separately, while `Fichero.cpp:104–112` suppresses write exceptions without returning failure. Failure partway through can leave the three streams out of alignment and still increment the saved-result count; there is no rollback or record-length verification.
- **Cached-selection singularities (S1):** the selection validation at `ProyectoView.cpp:668–713` checks only emptiness, not distinct observations, membership, or matrix rank. Selecting the same observation twice/three times is allowed by the dropdowns and creates a singular fit; this is an ordinary UI trigger for B07, not merely a pathological numerical matrix.

## Overall assessment

**32 CONFIRMED, 11 PARTIALLY CORRECT, 2 REFUTED, 0 CANNOT DETERMINE (45 total).** That is about **71% fully upheld**, and **96% contain at least a valid underlying concern**. A rough claim-accuracy score giving partials half credit is **83%**; neither percentage measures completeness or independent bug count, because several IDs overlap.

The report is useful and correctly identifies the major original-solver failures. It is less reliable about normal-path reachability, intended tolerance units, biphenyl labeling, schema/migration implications, and universal geometry statements. Two alleged failures disappear when their callers are read (B25, B40). Conversely, it substantially understates general eigenvalue errors, falsely passes xy-plane cylinder orientation, and misses routine wrong-science paths involving stale selected observations, ignored tensor flags, single-combination geometry, and mismatched result pages.

For the analysis document, retain the broad workflow but qualify “correct physical model and constants,” do not infer component/range validation that is absent, and do not treat the symmetry names as an independently verified group-theoretic derivation. Prioritize the solver, the equation/geometry state used for fitting, and trustworthy result indexing before reproducing the legacy scientific outputs as reference truth.

MFC interpretation was checked against Microsoft's [run-time object model and IMPLEMENT_SERIAL documentation](https://learn.microsoft.com/en-us/cpp/mfc/reference/run-time-object-model-services?view=msvc-170): schema 0 is a valid version value, and the macro's base-class argument defines runtime ancestry. This supports B21's ancestry finding, not its absolute assertion that migration is impossible.
