# Dipolar Studio — UI / visual design

Panel role: UI and visual design. Companion mockup: [`mockup-workspace.html`](mockup-workspace.html)
(static, inline CSS + SVG, 1440×900; the moon icon switches theme, the ⌘K field opens the palette).
Mockup data: synthetic 4,4′-difluorobiphenyl in ZLI-1132 at 300 K, with 15 dipolar couplings and
D₂ symmetry. Its fit gives φ = 39.60 ± 0.03°, r(C1–C1′) = 1.482 ± 0.005 Å and S_zz = 0.3020(3).

## 1. Visual direction

**Calm, precise, data-first. Colour is data; chrome is greyscale.**

The legacy app spread the work across about 50 modal dialogs, six 2D projection planes and a
separate OpenGL mode, so the molecule, the couplings and the fit were never visible together.
The new design shows all three at once and keeps the interface quiet:

- **The chrome uses no hue.** Panels, buttons, selection and focus are neutral greys and one
  ink, so colour always means something: a spin type, a misfit size or a status.
- **The tool is an instrument, not a SaaS dashboard.** A dashboard is glanced at: KPI tiles,
  soft cards, empty space, a bright accent everywhere. Here a scientist spends hours asking
  "which coupling is pulling φ?" and "is this minimum unique?". So the layout is dense, numbers
  align on the decimal point, units and uncertainties sit next to every value, each number shows
  its provenance (fit, dataset), and charts are small multiples with hairline axes.
- **Typography makes the numbers trustworthy.** Numbers use tabular figures and the true minus
  sign (−). Physics symbols (φ, r, S) are set in serif italic, as in a paper.
- **Light and dark themes are designed separately.** Dark is not an inverted light theme: each
  theme has its own steps from the same ramps, checked against its own surface colour.

## 2. Workspace layout

The main window is a single window with docked panes. All panes can be resized and collapsed,
and the layout is saved per project. At 1440 px the default layout is:

| Zone | Width | Content |
|---|---|---|
| Title bar | 40 px | Breadcrumb (molecule › dataset › run), ⌘K field, undo/redo, EN/ES, theme, **Sweep…**, **Run fit** |
| Left: Model | 248 px | Fragment tree with spin chips; isotopes, symmetry, frame, data, runs; **History** |
| Centre top: Viewport | flexible | WebGL molecule with misfit, S-axis and label overlays; view presets; legend |
| Centre bottom: Dock | 392 px | **Couplings** (obs, σ, calc, residual, residual/σ) · Spins · Sweep results · Log |
| Right: Inspector | 436 px | Parameters (sliders, ranges) · Order matrix · Fit diagnostics (4 charts) |
| Status bar | 26 px | Fit state + icon, χ², ν, χ²ᵥ, RMS, worst coupling, sparkline, units, engine |

**Density.** The base text is 12.5 px, table rows are 20 px and panel headers 32–34 px. A
*Comfortable* setting (24 px rows, 13.5 px text) is available. Panes are separated by 1 px rules,
not by shadows. Shadows appear only on floating elements (toolbars, popovers, the palette).

**Docking.** Any dock tab can be dragged into a second window, for example to put the χ²
landscape on another monitor. The inspector follows the selection (a spin, bond, parameter,
coupling or run) and **never opens a modal dialog**.

## 3. Interaction patterns

- **Click two spins to create a coupling.** ⇧-click two spins. A draft row appears in the
  Couplings table with its D_obs cell focused. The app fills in the spin types, r, the class
  (ortho/meta/para, syn/anti) and the symmetry multiplicity (×n).
- **Direct manipulation of geometry.** Every free dihedral has a ring handle drawn around its
  rotation axis. Dragging the knob rotates the fragment live, and a pill shows
  `φ 39.60° · χ²ᵥ 1.56` because the engine re-solves the order matrix linearly on every frame.
  Releasing the knob records one undoable step.
- **Residuals mapped onto the molecule.** With *Misfit* switched on, each coupling is drawn as
  an arc between its two spins. The arc's colour **and** its width encode |res|/σ, so the
  encoding does not depend on colour alone. Selecting a table row highlights its arc in ink and
  shows a leader-line callout with obs, calc, residual, r and θ.
- **Inline editable tables with units.** Cells are edited in place. Units live in the column
  header and as a ghost suffix in the editor (`206.1 Hz`). Typing `0.2061 kHz` converts the
  value. Blocks can be pasted from a spreadsheet, and the add row accepts `H3 F4′ −51.4`.
- **Command palette (⌘K).** One search covers commands, spins, parameters, runs and help, in
  English and Spanish ("barrido" finds *Sweep*). Each command shows its shortcut.
- **Inspectors instead of dialogs.** The roughly 50 legacy dialogs (Enlace, Ángulo,
  ParámetroVariable, InteraccObservada, …) become inspector sections. Edits apply immediately
  and are validated in place. Nothing blocks the canvas.
- **Undo/redo for everything.** Edits, drags, lock/free toggles and fits share one command
  stack, shown in the History list (undone steps are struck through). Fits are never overwritten:
  every run is kept under **Runs**.

## 4. Results visualization

All four diagnostics are small multiples in the inspector. Each one opens full size in the dock.

1. **Residual bar chart.** This is built into the table: the *Residual / σ* column draws a
   diverging bar on a fixed ±3σ scale, with a shaded ±1σ band and a zero line. The bars use the
   same misfit ramp as the 3D arcs, so a long violet bar in the table is a dark, thick arc in the
   viewport.
2. **Observed vs calculated.** A scatter plot with a dashed 1:1 line, slope and RMS. The
   selected coupling is a hollow ring, and hover is linked to the table and the arcs.
3. **χ² landscape.** A 1D profile (χ²ᵥ against φ, log scale) with the swept grid points marked
   along the axis, plus a 2D map (φ × r₁) on a single-hue violet ramp with the best fit and the
   correlation ρ. A copy of the 1D profile is drawn behind each parameter slider.
4. **Order-matrix principal axes on the molecule.** The X, Y and Z principal axes are drawn
   through the molecular centre. Axis length is proportional to |S_ii|, axes with negative S
   are dashed, and each carries its value. The inspector shows the 3×3 matrix (symmetry-zero
   elements greyed), the principal values as diverging bars, η and S_xx−S_yy.
5. **Convergence trace.** χ² per iteration on a log scale, from the sweep seed to convergence,
   with the stopping rule. The status bar repeats it as a sparkline.

## 5. Design-system tokens

**Type scale (px):** 10.5 caption · 11.5 secondary · **12.5 body/table** · 14 palette · 18
heading. Weights 400/500/600, tabular figures everywhere.

**Spacing:** a 4 px grid (4 · 8 · 12 · 16 · 24). Corner radii are 4, 6 and 8 px.

**Colour.** Each colour has one job. The categorical palette was checked with the dataviz
skill's validator (`validate_palette.js`).

| Role | Light | Dark | Notes |
|---|---|---|---|
| ¹H | `#2a78d6` blue | `#3987e5` | Categorical slot 1 |
| ²H | `#eb6834` orange | `#d95926` | Slot 2 |
| ¹⁹F | `#1baf7a` aqua | `#199e70` | Slot 3. Also drawn as a ◆ diamond glyph, not a ● circle |
| C / silent nuclei | `#9a9993` grey | `#77766f` | Not observed, so drawn recessive |
| Misfit \|res\|/σ (sequential) | `#d9d7f0` → `#3a2b8c` | `#33304a` → `#cbc3fb` | Six violet steps. In dark mode the lightness runs the other way, so a small misfit always fades into the background |
| Status good / warn / critical | `#0ca30c` / `#fab219` / `#d03b3b` | same | Reserved. Always shown with an icon and a label |

The three spin slots pass every all-pairs check in both themes (worst CVD ΔE ≈ 9). Misfit is a
lightness ramp in a hue no spin uses, doubled by arc width. Spin identity is colour **plus**
glyph shape plus label. There is no red/green pair and no rainbow.

**Number formatting** (one formatter in the engine and the UI):

- Quote the uncertainty to 1–2 significant figures and round the value to the same decimal
  place: `39.60 ± 0.03°`, `1.482 ± 0.005 Å`. Where space is tight, use the compact form
  `0.3020(3)`, with the uncertainty in the last digit.
- Couplings to 0.1 Hz, residuals signed to 0.01 Hz (`+0.21`), distances to 0.001 Å, fitted
  angles to 0.01°, order parameters to 4 decimals.
- True minus sign, thin-space thousands (`−2 407.3`), units in headers or a muted suffix.
  Values are rounded only for display, never in the data.

## 6. Accessibility

- Contrast is at least 4.5:1 for body text and 3:1 for non-text UI. Colours below 3:1 (aqua)
  are always paired with a label.
- Full keyboard use: F6 cycles panes. In the viewport, Tab walks the spins, ⇧+Enter creates a
  coupling, and the arrow keys rotate the selected dihedral by 1° (⇧ for 10°).
- An accessible tree mirrors the 3D scene, every chart has a table view, and the status bar is
  an `aria-live` region ("Fit converged, reduced chi-square 1.56").
- The app follows *reduce motion* and *increase contrast*. In forced-colours mode, misfit falls
  back to texture plus width.

## 7. Internationalization

- Every string is externalized (ICU MessageFormat). The app ships with **English** and
  **Spanish** (the legacy app's language), switchable live from the title bar.
- The decimal separator follows the locale (es-ES `1,482`) unless a "scientific" override
  forces `.`. Pasted data is parsed using the separator it actually contains.
- Symbols (φ, S_zz, Dᵢⱼ, ¹⁹F) and spin labels are never translated.
- Layouts allow about 30 % text expansion. Labels truncate with an ellipsis and a tooltip, and
  no text is drawn into a bitmap.
