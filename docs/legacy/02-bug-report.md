# Legacy bug report

Paths are relative to the root of [GinoLlerena/NMRApllication](https://github.com/GinoLlerena/NMRApllication) (commit `34a0bff`). Line numbers refer to the
original files (Latin-1, CRLF).
Severity: **S1** produces wrong scientific results or crashes · **S2** wrong behaviour or
data loss in common flows · **S3** edge case, robustness or portability.
Status: **Reproduced** = executed in `tools/legacy-harness` · **Read** = found by code reading
· **Verify** = plausible, needs the thesis or a running Windows build to confirm.

## S1 — wrong science or crash

| ID | Where | Defect | Effect | Status |
|---|---|---|---|---|
| B01 | `Matriz.cpp:264` + `:233` | In `DiagonalizaMatriz`, when S13 = S23 = 0 (always the case under **D2** symmetry) the third eigenvalue is stored in `EI[2][3]`, then `CalculosFinales` overwrites `EI[L][L+1] = 99` (the bisection bracket). | The report prints **Szz = 99.000000** for every D2 result with Sxy ≠ 0. | **Reproduced** |
| B02 | `Matriz.cpp:268-282` | Branch "only S13 ≠ 0": `dValor` saves S22 *after* it has already been overwritten (and is then unused). The missing eigenvalue is computed as `−λ₂ − S11`, which is not the trace identity. | Wrong Sxx/Syy. Harness gives −0.20615 where the answer is −0.20000. | **Reproduced** |
| B03 | `Matriz.cpp:162` | Householder `H = S + abs(a)·√S` is 0 when column IR is already zero below the diagonal (only S23 ≠ 0, a case not special-cased). 0/0 follows. | Eigenvalues are **NaN**. | **Reproduced** |
| B04 | `Matriz.cpp:96,113,202,233` | The solver assumes ±99 sentinels as the bisection bracket, but its regula-falsi step is unguarded (it can divide by YH−YL = 0 or extrapolate past the bracket). The `1e-6` zeroing threshold is absolute, and the loop stops silently after 99 iterations. | **Severe on ordinary inputs:** λ₃ = 0.01821 where the answer is 0.13907; with a 10⁻⁶-scaled matrix it returns eigenvalues of 45 and 82; 99 of 100 random traceless matrices err by more than 1e-5 (round 1). | **Reproduced** |
| B05 | `SistEcuac.cpp:198` | `ExaminaMatriz` indexes `m_bEcuacion` by **column** `j` but sets it by **row** `i`. | Wrong "already solved" bookkeeping. | Read |
| B06 | `SistEcuac.cpp:259-276` | Partial-elimination path: removes rows/columns while iterating with shifting indices, treats "value == 0" as "unknown", and **never restores `m_iCantVariab`**, so `CopiaResultados`/`DevuelveResultado` read the wrong column. | Wrong solution, e.g. (1,2,**14**) instead of (1,2,3). | **Reproduced** |
| B07 | `SistEcuac.cpp:133,163` | A singular matrix returns silently, leaving *partly eliminated* right-hand-side values as the "result". For example, `[[1,1],[2,2]]·x=[3,6]` returns (6,0). | Garbage order parameters with no warning. | **Reproduced** (round 1) |
| B08 | `RealizadorCalculo.cpp:61`, `ProyectoDoc.cpp:59` | The tolerance "Máximo Error Permitido" defaults to **10** and is applied as `abs(Dobs−Dcalc) ≤ 10·abs(Dobs)`, with no conversion. A percentage reading is inferred from the name `m_dPorcentaje`; the UI does not say so. | Default relative allowance of 1000%. The actual acceptance rate depends on the data (Dobs = 0 still needs exact agreement), so it is not established that "almost every point fits". | Read |
| B09 | `RealizadorCalculo.cpp:145`, `ParametroVariable.cpp:103-116` | A **negative** step hangs already in the counting loop (`DevuelveTotalInteracciones`), with no second parameter needed, provided initial ≤ final, so that the loop is entered. A **zero** step hangs `ProcesoIteractivoDeVariacion` when another parameter makes the total exceed 1, again only if initial ≤ final. Positive decimal steps accumulate floating-point error and can miss the endpoint. | UI hang, or the last grid value is skipped. | Read |
| B10 | `RealizadorCalculo.cpp:299` | Coefficients are divided by `iCantIntrcComp`, which is 0 if an observed coupling has no components. A new observation normally gets a default component, so this needs component deletion or a corrupt file. | NaN propagates to all results. | Read |
| B11 | `ProyectoDoc.cpp:244` | `DevuelveParteRigidaListPunto` returns (0,0,0) and an empty type for a label that is not found (for example after deleting a fragment). The empty type gives K = 0, and r = 0 divides by zero. | Silent wrong or zero couplings, or inf/NaN. | Read |
| B12 | `Rutinas.cpp:306,322`, `CoordEsf.cpp:48-50,62-64` | The azimuth uses `atan(y/x)` instead of `atan2`, and sets 90° whenever x = 0. | Whenever x < 0, or x = 0 with y < 0, the **nonzero** Syz and Szx coefficients flip sign. The result also depends on the order the spin labels were entered (i↔j). This affects the no-symmetry path; D2 and D4 are immune. | **Reproduced** (round 1: vector (−1,2,3)) |
| B13 | `ParteRigida.cpp:615-617` | Biphenyl rotation translates about P1 but rotates about the vector P1 measured *from the global origin*, instead of P1 − P0. | Wrong geometry whenever P0 is off the line through the origin along the bond. In a translated test P2 lands at (1.5, 0.71, 1.5) instead of (1, 1, 1). It is masked only when the rotation is 0° or when P1 (from the origin) has the same *directed* axis as P1 − P0. For example, with P0 = (2,0,0) and P1 = (1,0,0) the old axis is +x while the intended axis is −x, so the rotation runs the other way. | **Reproduced** (round 1) |
| B14 | `ParteRigida.cpp:313,397-398`, `PtoPerpendicular.cpp:50-58,104-157` | Trifenil ignores the parent's plane point `cPtoC` and uses (0,0,0) as the first reference point. When the axis passes through the origin in the general (non-axis-aligned) case, the cross product is 0 and the normalization divides by 0. | The fragment's orientation is arbitrary, or NaN in the general case. The axis-aligned special cases stay finite. | Read |
| B15 | `ParteRigida.cpp:88-90,249-265,486-497`, `EnlacePageOne.cpp:219` | For biphenyl, the bond editor stores labels on spins 0 and 1, and the calculation maps spin *i* to `m_cLado[i].PtoFinal`. | The first terminal label is computed at **P1 instead of P0**; the second correctly uses P2. Rendering draws spins at P0 and P2. Trifenil has a related P3/P4 mismatch. The author left a note: *"Ver en BF y TF"*. | Read (round 1 confirmed) |
| B16 | `Fichero.cpp:57` | `TCHAR tFileName[60]` + `_tcscpy(full path)`. | **Stack buffer overflow** on any path longer than 59 characters (typical for a "My Documents" path). | Read |
| B17 | `ConstructorMolecula.cpp:56` + `:222`, `ListaPartesDlg.cpp:136-155`, `ProyectoDoc.cpp:138` | `pObjParteRigida` keeps pointing at deleted fragments. Deleting all parts and then saving runs `ar << pObjParteRigida` on a dangling pointer; dialogs that call `GetParteRigida()` also dereference it. | **Use-after-free** crash or corrupt `.prj` file. | Read |
| B18 | `Distorcion.cpp:150,155,161` | No guards on ρ's denominator, K = 0, or ρ = 1/3. | inf/NaN Szz and Sxx−Syy in the no-symmetry path. | Read |

## S2 — wrong behaviour or data loss

| ID | Where | Defect | Effect |
|---|---|---|---|
| B19 | `Lado.cpp:183-184` (`CLado::Serialize`) | `m_strEtiqueta`, the label that binds a bond length to a variable parameter, is not serialized. | **S1:** after save/reload, bond-length parameters are no longer swept, with no warning. |
| B20 | `InteraccCalculada.cpp:126` | **S3.** `m_cCoordEsf` is not serialized, but every calculation refreshes it first. | A stale cache only; no wrong result has been shown. |
| B21 | `InteraccCalculada.cpp:17`, `InteraccComponent.cpp:14`, `InteraccObservada.cpp:14`, `ParametroVariable.cpp:15` | **S3.** `IMPLEMENT_SERIAL(…, CObject, 0)` names the wrong base class. Schema 0 is legal and does not by itself block migration. | `IsKindOf` checks against intermediate base classes fail. |
| B22 | `CalculoTensoresPageDos.cpp:117` | **S1.** The distortion model takes r₁₂ from the geometry at the moment the dialog is closed, and it is not refreshed during the sweep. | Szz and Sxx−Syy (no-symmetry path) are wrong whenever r₁₂ depends on a swept parameter. |
| B23 | `CalculoTensoresPageDos.cpp:154-158` | **S3.** `DevuelveDistanciaRij` returns −1 on a parse error and the caller does not check it. The normal dropdown supplies well-formed labels. | Consequences are conditional; a clean sign flip has not been demonstrated. |
| B24 | `Rutinas.cpp:276-279` | `DevuelveEtiquetasDij`: when the label has no space, the second label keeps the comma (`Right(len − pos)` should be `len − pos − 1`). | Label lookup fails, which then triggers B11. |
| ~~B25~~ | `RealizadorCalculo.cpp:385` | **REFUTED (round 1).** The selection copies the observation's own label order, so entering "B, A" does not by itself lose the row. The real stale-label defect is **B46**. | — |
| B26 | `Rutinas.cpp:215` + `RealizadorReporte.cpp:145-152` | The result-file integrity check compares last-access time, which **can** change merely from reading the file, depending on filesystem settings. The warning is commented out, and the function returns a file name **without its path**, so a later open can depend on the working directory. | Results sometimes cannot be reopened, with no message. |
| B27 | `Fichero.cpp:44` | **S3, latent.** `AbreConDlg` would open `GetFileName()` (relative path), but no caller exists. The main path correctly uses `GetPathName()`. | None at present. |
| B28 | `ProyectoDoc.cpp:577` (`DeleteContents`) and `OnNewDocument` | SDI reuses the document object, but **New** does not reset the symmetry, the order-matrix values, the distortion model, the selected couplings, the units or the symmetry-axis points. | Settings leak from one project into the next. |
| B29 | `ListaPartesDlg.cpp:136-142` | Deleting a fragment deletes **every later fragment** in the list, related or not, and keeps couplings that reference deleted spins. (Round 1: this does *not* create duplicate names.) | Data loss, then B11. |
| B30 | `PreferenciasPageTwo.cpp:55-57` | "Ignorar valores menores a ±" and "Límite de datos a imprimir" are saved but **never used**. The solver hard-codes `1e-5` (`SistEcuac.cpp:29`), and the selector hard-codes a capacity of 25 (maximum index 24, `Seleccionadora.cpp:21`). | Settings have no effect. |
| B31 | `RealizadorReporte.cpp:199` | The unit column is hard-coded to "Grados" for every parameter, including bond lengths (Å). `ProyectoDoc.cpp:78` labels couplings **"mHz"** although the constants are in **kHz** (`:76` also misspells "Amstrong"). | Misleading reports. |
| B32 | `InteraccCalculada.cpp:104` | Unsupported spin pairs (Cl, Br, "Ninguno", ¹³C, …) return K = 0 silently. | The coupling is silently zero. |
| B33 | `PtoPerpendicular.cpp:104-150` | `n` is uninitialized when A = B. Axis-aligned cases return a point perpendicular to *AB*, while the general case returns the normal of plane *ABC*: two different meanings depending on the orientation. | Undefined behaviour, and a geometry discontinuity. |
| B34 | `Parametro.cpp:79`, `ValorDual.cpp:92-93` (sizes `Structures.h:43,49-50`) | **S1.** Labels of 40+ characters overflow the `TCHAR[40]` buffers in `_tcscpy` (the raw-struct, non-portable format is a separate S3 issue at `ProyectoDoc.cpp:302,324`). | Memory corruption or crash. |
| B35 | `EnlacePageOne.cpp:377` vs `:198` | The label edit box is enabled for Deuterio when the type is chosen, but disabled when the dialog is reopened. Reselecting the type re-enables it. | Minor inconsistency. |

## S3 — robustness, portability, hygiene

- B36 `Mathemat.cpp:44-54`: dangling `else` in `round()`, so negative numbers never round
  down. The function also collides with C99 `round`. `Mathemat.h:13` redefines `M_PI`.
- B37 `ParteRigida.cpp:601`: `(i != 2) || (i != 5)` is always true. Harmless only because
  points 2 and 5 lie on the axis.
- B38 `ParteRigida.cpp:538-539`: a pen is created on every paint and destroyed while still
  selected into the DC; the old pen is not restored (GDI leak).
- B39 `Spin.cpp:142`, `ParteRigida.cpp:479`: a new GLU quadric and a full material-table
  re-initialization for every sphere on every frame.
- ~~B40~~ **REFUTED (round 1).** An earlier `FindIndex` guard means the NULL dereference cannot occur.
- B41 `Material.cpp:131`: `RAND_MAX+1` is signed overflow on non-MSVC platforms.
- B42 `Fichero.cpp:74`: `(pos−1)` underflows for pos = 0. File exceptions are only logged in Debug builds.
- B43 `ParteRigida.cpp:653`: relies on pre-standard `for` scope, so it does not compile on
  modern compilers without `/Zc:forScope-`.
- B44 (**S1 near the pole**) `InteraccCalculada.cpp:226`: `tan(dihedral)` diverges at 90°, with no guard. The
  dihedral is found by the magic label `"Dihedral"` (`ProyectoDoc.cpp:223`) and defaults to 0.
- B45 Repo hygiene: `Debug/*.obj`, the 81 MB `Proyecto.sdf`, `.ncb`, `.aps`, `.opt`, `.suo`
  and `ipch/` are committed.

## Physics checks (revised after the GPT-6.1-Sol validation)

- Dipolar constants K: right sign and right scale (kHz·Å³). H–H, H–D and D–D agree with
  CODATA/IUPAC γ to better than 0.02%. **The fluorine constants are about 0.06–0.12% low**
  (F–F −106.302 vs −106.429). That is small, but larger than the "3–4 significant figures" first
  claimed. Constants should come from a γ registry, not literals.
- Angular coefficients for Szz, Sxx−Syy, Syz, Szx, Sxy: the algebra is correct, but the coordinate
  conversion is not (see B12). The **D4** coefficient adds a `tan(dihedral)·sin2φ` term that the
  reported tensor does not reproduce (B55).
- `CPunto::Rota3D`: correct right-handed Rodrigues rotation (1,000 random cases agree to 4e-16),
  but it does not check for a zero axis (B56).
- `Txx = (Δ − Tzz)/2`, `Tyy = Txx − Δ`: correct.
- ~~`Lado::Construye` cylinder orientation correct~~ **Wrong.** The xy-plane branch classifies
  `(x,0,y)` but passes `(x,y,0)` to the angle routine. A `(1,2,0)` bond is drawn along +X (B50).
  This is rendering only; the stored geometry is unaffected.

## Validation errata (GPT-6.1-Sol, round 1, `docs/validation/round1-bug-verification.md`)

Verdicts on B01–B45: **32 confirmed, 11 partially correct, 2 refuted**.

- **Refuted:** B25 (the selection copies the observation's own label order, so a reversed
  entry does not by itself lose the row; the real defect is B46) and B40 (an earlier
  `FindIndex` guard rules out the NULL case).
- **Downgraded to S3:** B20 (coordinates are refreshed before each calculation), B21 (schema 0 is
  legal; the defect is the wrong runtime-class ancestry), B23 (malformed input is unlikely through
  the dropdown), and B27 (`AbreConDlg` has no caller).
- **Narrowed:**
  - B08: 10·|Dobs| is a fact, but the "percentage" reading is inferred from the variable name.
  - B09: a negative step already hangs in the counting loop, `ParametroVariable.cpp:103–116`.
  - B13: not *every* non-root biphenyl is affected; in a translated test, P2 lands at
    (1.5, 0.71, 1.5) instead of (1, 1, 1).
  - B15: the first biphenyl label uses P1 instead of P0; the second correctly uses P2.
  - B29: the suffix delete does not create duplicate names.
  - B34: the real overflow sites are `Parametro.cpp:79` and `ValorDual.cpp:92–93`.
- **B04 is much worse than reported.** On an ordinary-scale traceless matrix the legacy solver
  returns λ₃ = **0.01821** where the answer is 0.13907. Scaled by 10⁻⁶, it returns eigenvalues
  of 45 and 82. 99 of 100 random traceless matrices were off by more than 1e-5.
  **No legacy principal value should be trusted.**

### Bugs missed in the first pass (found by GPT-6.1-Sol; numerical evidence exists for B50, B55 and B56, the rest were checked by reading)

| ID | Sev | Where | Defect |
|---|---|---|---|
| B46 | S1 | `CalculoTensoresPageUno.cpp:146-153`, `CalculoTensoresPageDos.cpp:115-140`, `RealizadorCalculo.cpp:394-401` | The selected couplings and distortion inputs are **copied** when the dialog closes. Editing an observed value later means the solve uses the *old* value while acceptance uses the *new* one. Renaming or deleting a selected observation leaves a non-empty stale label: validation passes, but the equation is missing or zero. |
| B47 | S1 | `RealizadorCalculo.cpp:390-410` vs `:55-58` | The solve ignores each coupling's Uso* flags, but prediction applies them, so the fitted equations are not the model that gets evaluated. |
| B48 | S1 | `RealizadorCalculo.cpp:192-205` | "Combinación dada" applies the parameter values but **does not rebuild the molecule** before computing coefficients, so it fits the previous geometry. |
| B49 | S1/S2 | `ResultadosOnePageThree.cpp:130,212-235` | Results paging forgets the 7-records-per-configuration stride, so page 2 shows tensors from unrelated configurations (even a MAD in the Tzz column). The last short page is also mis-indexed. |
| B50 | S2 | `Lado.cpp:221-223` | Bonds in the xy plane are drawn in the wrong direction (see the physics checks). |
| B51 | S1/S2 | `RealizadorReporte.cpp:95-105`, `Seleccionadora.cpp:44-86` | The best-fit scan reads one record past EOF (with `<=`) and inserts garbage. Also, `DevuelveCantidadDatos()` returns the *last index* but callers treat it as a *count*: one fit is hidden, and a full list drops its last page. |
| B52 | S1/S2 | `EnlacePageOne.cpp:322-325` vs `RealizadorCalculo.cpp:94-114` | Phenyl bond 11 can be marked Variable, but the sweep only applies bond 8. The parameter changes in the output while the geometry does not. |
| B53 | S1 | `ParametroVariablePageTwo.cpp:112,134`, `ResultadosOne*.cpp`, `InteraccObservadaPageTwo.cpp:125` | `TCHAR palabra[25]` list buffers overflow with labels of 25 or more characters. |
| B54 | S2 | `ProyectoDoc.cpp:110-168` | The error tolerance `m_dPorcentaje` (and `m_cPtoPlano`) is not saved. A fresh process reverts to the default of 10, and in an SDI session a new document can inherit another document's tolerance. `m_cPtoPlano` is also not saved, but the GUI never exposes it, so that part is latent. |
| B55 | S1 | `InteraccCalculada.cpp:225-239`, `RealizadorReporte.cpp:322-333` | D4 predictions imply Txy = ½Δ·tan(dihedral), but the stored and reported tensor keeps Txy = 0. For one test case the forward model gives 4.25 kHz and the reported tensor 6.37 kHz. **Needs the thesis derivation.** |
| B56 | S1 | `Punto3D.cpp:121-126`, `PtoPerpendicular.cpp:70-75` | Rotation about a zero axis gives NaN even for a 0° rotation. Collinear construction points can produce that zero axis. |
| B57 | S2 | `ProyectoDoc.cpp:293-388`, `Fichero.cpp:104-112` | The 3 result streams are not written as one transaction, and write failures are swallowed, so the streams can fall out of alignment. |
| B58 | S1 | `ProyectoView.cpp:668-713` | The same coupling can be selected 2–3 times, which gives a singular system (an ordinary UI path to B07). |

Revised total: **56 retained findings** (58 IDs minus the 2 refuted). Several IDs overlap, so this is not a count of 56 independent mechanisms. The rows above were reconciled in place after round 2 (`docs/validation/round2-plan-review.md` §1).
