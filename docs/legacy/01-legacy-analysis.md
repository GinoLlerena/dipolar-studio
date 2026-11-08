# Legacy analysis — "Proyecto" (NMR application, 1998)

Source: [GinoLlerena/NMRApllication](https://github.com/GinoLlerena/NMRApllication) (git `34a0bff`, imported 2015, written 1998).
Analyzed 2026-11-07.

## 1. What the application does (domain)

It estimates **molecular conformation and orientational order** for rigid aromatic
fragments (phenyl ring, biphenyl, "triphenyl"/branched fragment) dissolved in an
**anisotropic medium (liquid crystal)**, from **observed NMR dipolar couplings Dᵢⱼ**.

For each spin pair *i,j* (¹H, ²H, ¹⁹F) at distance *rᵢⱼ* with polar angle θ and azimuth φ
in the molecular frame, the code uses the standard expression (`InteraccCalculada.cpp:150-180`):

```
Dij = Kij / rij³ · [ Szz·P2(cosθ) + ½(Sxx−Syy)·sin²θ·cos2φ
                     + Syz·sin2θ·sinφ + Szx·sin2θ·cosφ + Sxy·sin²θ·sin2φ ]
```

with `Kij = −μ0 γi γj ħ / (8π²)` in **kHz·Å³** (`DevuelveConstante`):
H–H −120.120, F–F −106.302, H–F −113.000, D–D −2.830, H–D −18.439, F–D −17.346.
**These constants are physically correct** (checked against γF/γH = 0.9408, γD/γH = 0.1535).

Note: the code calls the order matrix "T" (Tzz, Txx−Tyy, …); the reports call its eigenvalues S.

### Workflow the user follows

1. **Build the molecule** from rigid parts (`Insertar → Anillo fenil / Bifenil / Trifenil`),
   chaining them through "Enlace" (link) bonds. Each part has 12 bonds (`CLado`),
   12 angles (`CAngulo`), 6 spin sites (`CSpin`) and one rotation angle about the link axis.
2. **Mark bonds/angles as "Variable"** and bind them to a named parameter.
3. **Define variable parameters** (`CParametroVariable`: initial, final, increment).
4. **Enter observed couplings** (`CInteraccObservada`) between labelled spins, plus which
   order-matrix elements apply to each one (flags UsoTzz, UsoTxx−Tyy, …).
5. **Define component interactions** (`CInteraccComponent`). The observed coupling is
   modelled as the *average* of several geometric pairs, which is how motional or
   symmetry averaging is represented.
6. **Choose symmetry**: D4 (2 unknowns: Szz, Sxx−Syy), D2 (3: + Sxy), or none (Szz and
   Sxx−Syy from a ring-*distortion* model with ρ, then 3 unknowns Syz, Szx, Sxy).
7. **Select 2–3 "calculation" couplings** that fix the order matrix exactly
   (an *exactly determined* linear system).
8. **Calculate**: either a single combination or a **full grid sweep** over all variable
   parameters (`Calcular → Barrido`). For every grid point the molecule is rebuilt, the
   order matrix is solved from the selected couplings, and *all* couplings are predicted.
   The point is **accepted** only if every |Dobs − Dcalc| ≤ tolerance·|Dobs|.
   Accepted points are appended to 3 binary files (`.par`, `.int`, `.ten`) plus a `.bin`
   index file.
9. **Results**: browse and print the best 25 by MAD (mean absolute deviation). The order
   matrix is diagonalized to report principal values (Sxx, Syy, Szz).

## 2. Architecture

| Layer | Classes (Spanish → meaning) | Notes |
|---|---|---|
| App/UI shell | `CProyectoApp`, `CMainFrame`, `CMainBar`, `C3DToolBar`, `CSplash` | MFC SDI, OLE automation stub, WinHelp `.hlp` |
| Views | `CProyectoView` (2D GDI "design mode", 6 projection planes), `COpenGLView` (3D, fixed-function GL 1.1 + GLU/GLAUX), `CTempView` | Views also host the calculation drivers (`m_cRealizadorCalculo`, `m_cConstructorMolecula`) |
| Dialogs (≈50) | `Enlace*` (bond), `Angulo*`, `EjeRotacion*`, `InteraccObservada*`, `InteraccComponentDlg`, `ParametroVariable*`, `CalculoTensores*`, `Resultados*`, `Preferencias*`, `Propiedades` | Property sheets; business rules live in dialog handlers |
| Document | `CProyectoDoc` | God object: model lists + unit strings + file names + calculation state + results; reached through a global `GetDoc()` friend |
| Geometry | `CPunto` (point), `CCoordEsf` (spherical coords), `CLado` (bond/cylinder), `CPtoPerpendicular`, `CParteRigida` (rigid fragment, 1324 lines), `CConstructorMolecula` (assembly) | Hand-coded rotations with special cases per axis/quadrant and exact `== 0.0` comparisons |
| Physics | `CInteraccCalculada` (coefficients), `CDistorcion` (ρ, ring distortion), `CTensor`, `CValorDual` | |
| Numerics | `CSistEcuac` (Gauss + ad-hoc partial elimination), `CMatriz` (Householder tridiagonalization + Sturm bisection/regula falsi eigenvalues), `CSeleccionadora` (top-25 insertion sort) | Fixed arrays `[10][11]`, 1-based indexing |
| Search | `CRealizadorCalculo` | Recursive nested-loop grid sweep |
| Persistence | MFC `CArchive` `.prj`, raw `struct` dumps to `.par/.int/.ten`, raw `CFileStatus` dumps to `.bin` | Not versioned, not portable, Windows-only |
| Reporting | `CRealizadorReporte`, `ResultadosOne*` | Text drawn via GDI `TextOut` at hard-coded coordinates |

Size: about 21.5k lines of C++ (≈190 files), with Spanish identifiers and Latin-1 encoding.
The repo also contains build artifacts (`Debug/*.obj`, the 81 MB `Proyecto.sdf`, `.ncb`,
`.aps`, `.opt`, `.suo`, `ipch/`). Build files exist for VC6 (`.dsp/.dsw/.mak`) and for
VS2013 (`.vcxproj`, `UpgradeLog.htm`).

## 3. Data flow of one grid point (`RealizadorCalculo.cpp`)

```
ProcesoIteractivoDeVariacion(i)   — recursive loop over parameter i (float accumulator)
  └─ InicializaParametros()      — push value into matching angle/bond by *string label*
  └─ ReconstruyeMolecula()       — rebuild coordinates part by part (list order = tree order)
  └─ CalculaCoeficientes()       — 5 geometric coefficients per component pair
  └─ IncluyeInteraccionesCalculadas() — average components → one equation per observed D
  └─ CalculaTensores()           — exact 2×2 / 3×3 solve from the 2–3 *selected* couplings
  └─ OptimizaInteraccionesCalculadas() — predict all D, accept if all within tolerance,
                                    then append binary records to 3 files (open/close per hit)
```

## 4. Strengths worth keeping

- Correct physical model and constants. A clean separation already exists between
  "observed", "component" (averaging) and "calculated" interactions.
- The fragment-based builder with parameter binding is a good *domain-specific* UX idea.
- Symmetry-aware reduction of unknowns (D4/D2/none) and the ring-distortion (ρ) model.
- A systematic grid scan gives a global view of the solution space, rather than a single
  local minimum.

## 5. Structural weaknesses (beyond individual bugs)

1. **Statistics**: the order matrix is solved *exactly* from 2–3 hand-picked couplings
   rather than by least squares over all couplings. Results depend on which couplings
   the user picks, carry no uncertainty, and the accept/reject rule is binary.
2. **Search**: a brute-force grid is O(∏ nᵢ), with no gradient refinement, no early
   pruning and no parallelism. Each accepted point performs 3 file open/close cycles.
3. **Coupling of concerns**: physics, UI and persistence are entangled through `GetDoc()`.
   Model entities are linked by display strings ("Bifenil 2", "H1, H2", "Dihedral").
4. **Geometry**: case-by-case rotation code (`Lado::SituaEnEspacio`, `PtoPerpendicular`)
   uses exact float comparisons and `atan` instead of `atan2`/quaternions.
5. **Fixed topology**: only three hard-coded fragment types. Molecules cannot be imported
   (no PDB, SDF or XYZ), and only H, D and F spins are supported (Cl and Br are listed but
   return K = 0).
6. **No tests, no logging, silent failures** (singular matrices, missing labels, corrupt
   files all fail quietly).
7. **Platform lock-in**: MFC, Win32, OpenGL 1.1, GLAUX, WinHelp, ANSI code page.
