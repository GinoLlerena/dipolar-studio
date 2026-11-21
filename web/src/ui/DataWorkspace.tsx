import { useEffect, useMemo, useState } from "react";
import { callOperation, type DescribeProjectOut, type ModelSetIn, type SymmetryIn } from "../api";
import { angstrom, hz, scientific } from "../format";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { download, FileButton, Panel, selectableRow, Spacer, useRowWindow } from "./common";
import { ImportCouplings } from "./ImportCouplings";

type Props = { studio: Studio; state: StudioState };

/** The Data workspace: the project, its geometry and model, its spins and couplings. */
export function DataWorkspace({ studio, state }: Props) {
  const { view, project } = state;
  return (
    <div className="workspace" id="panel-data" role="tabpanel" aria-labelledby="tab-data">
      <div className="column side">
        <ProjectPane studio={studio} state={state} />
        {project && view?.project_open && (
          <>
            <GeometryPane studio={studio} state={state} project={project} />
            {project.geometry.kind === "imported" && <SymmetryPane studio={studio} state={state} project={project} />}
            <ModelPane studio={studio} state={state} project={project} model={project.model} />
          </>
        )}
      </div>
      <div className="column main">
        {project && view?.project_open ? (
          <>
            <CouplingsPane studio={studio} state={state} project={project} />
            <ImportCouplings studio={studio} state={state} project={project} />
            <SpinsPane studio={studio} state={state} project={project} />
          </>
        ) : (
          <p className="empty">{strings.noProjectYet}</p>
        )}
      </div>
    </div>
  );
}

function ProjectPane({ studio, state }: Props) {
  const { view, project, busy } = state;
  const revision = view?.science_revision ?? 0;
  const disabled = busy !== null || !view;
  const open = view?.project_open && project;
  return (
    <Panel title={strings.project} id="pane-project">
      <div className="stack">
        <button
          type="button"
          className="primary"
          disabled={disabled}
          onClick={() =>
            void studio.command("project.open_example", (t) =>
              callOperation("project.open_example", { name: "biphenyl-synthetic", expected_science_revision: revision }, t),
            )
          }
        >
          {strings.openExample}
        </button>
        <div className="row">
          <FileButton
            label={strings.loadProject}
            accept=".json,application/json"
            disabled={disabled}
            onText={(text) =>
              void studio.command("project.load", (t) =>
                callOperation("project.load", { text, expected_science_revision: revision }, t),
              )
            }
          />
          <FileButton
            label={strings.importXyz}
            accept=".xyz,chemical/x-xyz,text/plain"
            disabled={disabled}
            onText={(xyz, file) =>
              void studio.command("project.import_xyz", (t) =>
                callOperation(
                  "project.import_xyz",
                  { xyz, name: strings.xyzName(file).slice(0, 200), expected_science_revision: revision },
                  t,
                ),
              )
            }
          />
          <button
            type="button"
            disabled={disabled || !open}
            onClick={async () => {
              const out = await studio.command("project.export", (t) => callOperation("project.export", {}, t));
              if (out) download(out.filename, out.text, "application/json");
            }}
          >
            {strings.exportProject}
          </button>
        </div>
        <p className="help">{strings.replaceWarning}</p>
        {open && (
          <>
            <p className={project.ready_to_fit ? "ready" : "not-ready"} role="note">
              {project.ready_to_fit ? `✓ ${strings.ready}` : `! ${strings.notReady(project.not_ready_reason ?? "")}`}
            </p>
            <dl className="facts">
              <dt>{strings.source}</dt>
              <dd>{project.source}</dd>
              <dt>{strings.estimand}</dt>
              <dd>{project.estimand}</dd>
            </dl>
            {project.equivalences.length > 0 && (
              <details>
                <summary>{strings.equivalences}</summary>
                <ul className="plain">
                  {project.equivalences.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}

function GeometryPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const geometry = project.geometry;
  return (
    <Panel title={strings.geometry} id="pane-geometry">
      {geometry.kind === "template" ? (
        <dl className="facts">
          <dt>{strings.template(geometry.template)}</dt>
          <dd />
          <dt>{strings.bond.r_cc}</dt>
          <dd className="num">{angstrom(geometry.r_cc.value)} Å</dd>
          <dt>{strings.bond.r_ch}</dt>
          <dd className="num">{angstrom(geometry.r_ch.value)} Å</dd>
          <dt>{strings.bond.r_inter}</dt>
          <dd className="num">{angstrom(geometry.r_inter.value)} Å</dd>
        </dl>
      ) : (
        <ImportedGeometry studio={studio} state={state} project={project} />
      )}
    </Panel>
  );
}

function ImportedGeometry({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const geometry = project.geometry;
  const atoms = geometry.kind === "imported" ? geometry.atoms : [];
  const declared = geometry.kind === "imported" ? geometry.torsion : null;
  const [draft, setDraft] = useState<string[]>(() => (declared ?? ["", "", "", ""]).map(String));
  // The fields follow the declared torsion and the geometry: when either changes (Set torsion
  // here or by another client; another geometry imported or loaded), typed indices could name
  // other atoms, so they are reset (round 52). Other science changes keep what was typed: one can
  // arrive while the user types (a couplings import, another client's edit; CI, M3 step 4b).
  const atomsKey = useMemo(() => JSON.stringify(atoms), [atoms]);
  const declaredKey = `${declared ? declared.join(",") : ""}|${atomsKey}`;
  useEffect(() => setDraft((declared ?? ["", "", "", ""]).map(String)), [declaredKey]);
  if (geometry.kind !== "imported") return null;
  // Non-default isotopes (molecule.declarations): shown, not edited here (V1.4, E-4).
  const mass = new Map((state.declarations?.declared.isotopes ?? []).map((i) => [i.atom, i.mass_number]));
  const indices = draft.map((d) => Number(d));
  const valid = draft.every((d) => /^\d+$/.test(d.trim())) && indices.every((i) => i < atoms.length);
  return (
    <>
      <p>{strings.imported(geometry.source_format, atoms.length)}</p>
      <fieldset className="torsion">
        <legend>{strings.torsion}</legend>
        <p className="muted">{declared ? declared.join(" – ") : strings.torsionNone}</p>
        <div className="row">
          {draft.map((value, k) => (
            <input
              key={k}
              aria-label={`${["a", "i", "j", "b"][k]}`}
              inputMode="numeric"
              className="index"
              value={value}
              onChange={(e) => setDraft(draft.map((d, j) => (j === k ? e.target.value : d)))}
            />
          ))}
          <button
            type="button"
            disabled={!valid || state.busy !== null}
            onClick={() => {
              const [a = 0, i = 0, j = 0, b = 0] = indices;
              void studio.command("molecule.set_torsion", (t) =>
                callOperation(
                  "molecule.set_torsion",
                  { torsion: [a, i, j, b], expected_science_revision: project.science_revision },
                  t,
                ),
              );
            }}
          >
            {strings.setTorsion}
          </button>
        </div>
        <p className="help">{strings.torsionHelp}</p>
      </fieldset>
      <details>
        <summary>
          {strings.colAtom} ({atoms.length})
        </summary>
        <table className="grid compact">
          <thead>
            <tr>
              <th>#</th>
              <th>El.</th>
              <th className="num">x (Å)</th>
              <th className="num">y (Å)</th>
              <th className="num">z (Å)</th>
              <th className="num">{strings.colMass}</th>
            </tr>
          </thead>
          <tbody>
            {atoms.map((a) => (
              <tr key={a.index}>
                <td className="num">{a.index}</td>
                <td>{a.element}</td>
                <td className="num">{angstrom(a.x)}</td>
                <td className="num">{angstrom(a.y)}</td>
                <td className="num">{angstrom(a.z)}</td>
                <td className="num">{mass.get(a.index) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

type ModelDraft = { kind: ModelSetIn["kind"]; order: ModelSetIn["order"]; frame: ModelSetIn["frame"]; from: string; to: string };

function toDraft(model: DescribeProjectOut["model"]): ModelDraft {
  if (model.kind === "fixed") return { kind: "fixed", order: "point-group", frame: "symmetry", from: "", to: "" };
  return {
    kind: model.kind,
    order: model.order,
    frame: model.frame,
    from: String(model.phi_domain[0].value),
    to: String(model.phi_domain[1].value),
  };
}

const KINDS: readonly ModelDraft["kind"][] = ["rigid", "jump4", "fixed"];
const ORDERS: readonly ModelDraft["order"][] = ["bisector-diagonal", "c2z", "c1"];
const FRAMES: readonly ModelDraft["frame"][] = ["bisector", "ring-a", "input"];

/** A new kind in the draft: the fixed-geometry fit has one order and one frame and no φ domain;
 * leaving it starts from the imported-geometry defaults (C₁, input frame) and an empty domain. */
function withKind(draft: ModelDraft, kind: ModelDraft["kind"]): ModelDraft {
  if (kind === "fixed") return { ...draft, kind, order: "point-group", frame: "symmetry" };
  if (draft.kind === "fixed") return { kind, order: "c1", frame: "input", from: "", to: "" };
  return { ...draft, kind };
}

/** The model inspector (an inspector, not a dialog: ui-design §3). The server validates every
 * combination; an invalid one comes back as an error naming the field. */
function ModelPane({ studio, state, project, model }: Props & { project: DescribeProjectOut; model: DescribeProjectOut["model"] }) {
  const [draft, setDraft] = useState(() => toDraft(model));
  // The draft follows the model when it changes (here or by another client), not every science
  // change: one that arrives while the user edits (the couplings import's new description, another
  // client's edit) must not wipe the edit (CI Firefox, beta step B4; as for the torsion, M3 step 4b).
  const modelKey = JSON.stringify(model);
  useEffect(() => setDraft(toDraft(model)), [modelKey]);
  const saved = toDraft(model);
  const changed = (Object.keys(draft) as (keyof ModelDraft)[]).some((k) => draft[k] !== saved[k]);
  const fixedFit = draft.kind === "fixed";
  const from = Number(draft.from);
  const to = Number(draft.to);
  const numbers = fixedFit || (draft.from.trim() !== "" && draft.to.trim() !== "" && Number.isFinite(from) && Number.isFinite(to));
  // After Apply, the inspector stays closed until the page shows the model it applied (round 79: a
  // late description erased an edit made meanwhile).
  const [pending, setPending] = useState<number | null>(null);
  // It also waits while the project shown is older than the newest revision the page shows (the
  // view's): Apply acts at the project's revision (round 79).
  const behind = state.view !== null && project.science_revision !== state.view.science_revision;
  const waiting = (pending !== null && project.science_revision < pending) || behind;
  const apply = async () => {
    const args: ModelSetIn = fixedFit
      ? { kind: "fixed", order: "point-group", frame: "symmetry", expected_science_revision: project.science_revision }
      : {
          kind: draft.kind,
          order: draft.order,
          frame: draft.frame,
          phi_domain: [
            { value: from, unit: "deg" },
            { value: to, unit: "deg" },
          ],
          expected_science_revision: project.science_revision,
        };
    const out = await studio.command("model.set", (t) => callOperation("model.set", args, t));
    if (out) setPending(out.science_revision);
  };
  const orders = fixedFit ? (["point-group"] as const) : ORDERS;
  const frames = fixedFit ? (["symmetry"] as const) : FRAMES;
  return (
    <Panel title={strings.model} id="pane-model">
      <div className="form">
        <label htmlFor="model-kind">{strings.modelKind}</label>
        <select
          id="model-kind"
          value={draft.kind}
          disabled={waiting}
          onChange={(e) => setDraft(withKind(draft, e.target.value as ModelDraft["kind"]))}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {strings.kindName[k]}
            </option>
          ))}
        </select>
        <label htmlFor="model-order">{strings.modelOrder}</label>
        <select
          id="model-order"
          value={draft.order}
          disabled={fixedFit || waiting}
          onChange={(e) => setDraft({ ...draft, order: e.target.value as ModelDraft["order"] })}
        >
          {orders.map((k) => (
            <option key={k} value={k}>
              {strings.orderModelName[k]}
            </option>
          ))}
        </select>
        <label htmlFor="model-frame">{strings.modelFrame}</label>
        <select
          id="model-frame"
          value={draft.frame}
          disabled={fixedFit || waiting}
          onChange={(e) => setDraft({ ...draft, frame: e.target.value as ModelDraft["frame"] })}
        >
          {frames.map((k) => (
            <option key={k} value={k}>
              {strings.frameName[k]}
            </option>
          ))}
        </select>
        {!fixedFit && (
          <>
            <span className="label">{strings.phiDomain}</span>
            <span className="row">
              <input
                aria-label={`${strings.phiDomain} ${strings.phiFrom}`}
                inputMode="decimal"
                className="short"
                disabled={waiting}
                value={draft.from}
                onChange={(e) => setDraft({ ...draft, from: e.target.value })}
              />
              <span className="muted">–</span>
              <input
                aria-label={`${strings.phiDomain} ${strings.phiTo}`}
                inputMode="decimal"
                className="short"
                disabled={waiting}
                value={draft.to}
                onChange={(e) => setDraft({ ...draft, to: e.target.value })}
              />
            </span>
          </>
        )}
      </div>
      <div className="row end">
        <button type="button" disabled={!changed || waiting} onClick={() => setDraft(saved)}>
          {strings.resetModel}
        </button>
        <button
          type="button"
          className="primary"
          disabled={!changed || !numbers || waiting || state.busy !== null}
          onClick={() => void apply()}
        >
          {strings.applyModel}
        </button>
      </div>
      <p className="help">{fixedFit ? strings.fixedModelHelp : project.frame}</p>
    </Panel>
  );
}

const GROUPS = ["C1", "Cs", "C2v", "D2h", "D3h", "D6h"] as const;
const IDENTITY: string[][] = [
  ["1", "0", "0"],
  ["0", "1", "0"],
  ["0", "0", "1"],
];
type SymmetryDraft = { group: string; axes: string[][]; tolerance: string };

function symmetryDraft(
  declared: { point_group: string; axes?: readonly (readonly number[])[]; tolerance?: { value: number } } | null | undefined,
): SymmetryDraft {
  if (!declared) return { group: "C1", axes: IDENTITY.map((r) => [...r]), tolerance: "0.01" };
  return {
    group: declared.point_group,
    axes: declared.axes ? declared.axes.map((r) => r.map(String)) : IDENTITY.map((r) => [...r]),
    tolerance: String(declared.tolerance?.value ?? 0.01),
  };
}

/** The symmetry form (V1.4, E-4): the declared point group, its axes and tolerance, with the
 * server's Cs suggestion for planar spins (E-5). Every check is the server's. */
function SymmetryPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const declarations = state.declarations;
  // The suggestion is shown only for the science state on screen; the declaration is the latest
  // read, so a science change that leaves it alone (a couplings import) never resets the form.
  const newest = state.view?.science_revision ?? -1;
  const current =
    declarations &&
    declarations.declared.science_revision === project.science_revision &&
    project.science_revision === newest
      ? declarations
      : null;
  const declared = declarations?.declared.symmetry ?? null;
  const [draft, setDraft] = useState<SymmetryDraft>(() => symmetryDraft(declared));
  // The form follows the declaration (and the geometry) when they change, not every science change.
  const atomsKey = project.geometry.kind === "imported" ? JSON.stringify(project.geometry.atoms) : "";
  const declaredKey = `${JSON.stringify(declared)}|${atomsKey}`;
  useEffect(() => setDraft(symmetryDraft(declared)), [declaredKey]);
  const numbers = [...draft.axes.flat(), draft.tolerance].every((v) => v.trim() !== "" && Number.isFinite(Number(v)));
  const suggestion = current?.suggested.suggestion ?? null;
  // Declare and Clear act on the declaration the form shows, at its revision, and wait while it is
  // older than the project (round 79: Clear removed a declaration the page had not shown yet), and,
  // after a declaration, until the page shows it.
  const [pending, setPending] = useState<number | null>(null);
  const shownRevision = declarations?.declared.science_revision ?? -1;
  const waiting = current === null || (pending !== null && shownRevision < pending);
  const declare = async (symmetry: SymmetryIn | null) => {
    if (!current) return;
    const out = await studio.command("molecule.set_symmetry", (t) =>
      callOperation("molecule.set_symmetry", { symmetry, expected_science_revision: current.declared.science_revision }, t),
    );
    if (out) setPending(out.science_revision);
  };
  const row = (k: number) => {
    const [x = 0, y = 0, z = 0] = (draft.axes[k] ?? []).map(Number);
    return [x, y, z] as [number, number, number];
  };
  return (
    <Panel title={strings.symmetry} id="pane-symmetry">
      <p className={declared ? undefined : "muted"}>
        {declared
          ? strings.declared(declared.point_group, String(declared.tolerance.value), scientific(declared.max_displacement.value, 2))
          : strings.notDeclared}
      </p>
      {suggestion && current && (
        <div className="suggestion">
          <p role="note">{current.suggested.reason}</p>
          <button type="button" className="quiet" onClick={() => setDraft(symmetryDraft(suggestion))}>
            {strings.useSuggestion}
          </button>
          <p className="help">{strings.suggestionHelp}</p>
        </div>
      )}
      <div className="form">
        <label htmlFor="symmetry-group">{strings.pointGroup}</label>
        <select id="symmetry-group" value={draft.group} onChange={(e) => setDraft({ ...draft, group: e.target.value })}>
          {GROUPS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        <span className="label">{strings.symmetryAxes}</span>
        <span className="axes">
          {(["x", "y", "z"] as const).map((axis, k) => (
            <span key={axis} className="row">
              <span className="muted">{strings.axisRow(axis)}</span>
              {(["x", "y", "z"] as const).map((component, j) => (
                <input
                  key={component}
                  id={`axis-${k}-${j}`}
                  aria-label={strings.axisInput(axis, component)}
                  inputMode="decimal"
                  className="index"
                  value={draft.axes[k]?.[j] ?? ""}
                  onChange={(e) => setDraft({ ...draft, axes: draft.axes.map((r, i) => (i === k ? r.map((v, c) => (c === j ? e.target.value : v)) : r)) })}
                />
              ))}
            </span>
          ))}
        </span>
        <label htmlFor="symmetry-tolerance">{strings.symmetryTolerance}</label>
        <input
          id="symmetry-tolerance"
          inputMode="decimal"
          className="short"
          value={draft.tolerance}
          onChange={(e) => setDraft({ ...draft, tolerance: e.target.value })}
        />
        <span className="label">{strings.medium}</span>
        <span className="muted">{strings.mediumName}</span>
      </div>
      <div className="row end">
        <button type="button" disabled={!declared || waiting || state.busy !== null} onClick={() => void declare(null)}>
          {strings.clearSymmetry}
        </button>
        <button
          type="button"
          className="primary"
          disabled={!numbers || waiting || state.busy !== null}
          onClick={() =>
            void declare({
              point_group: draft.group,
              axes: [row(0), row(1), row(2)],
              tolerance: { value: Number(draft.tolerance), unit: "Å" },
              medium: "achiral-uniaxial",
            })
          }
        >
          {strings.declareSymmetry}
        </button>
      </div>
      <p className="help">{strings.symmetryHelp}</p>
    </Panel>
  );
}

function CouplingsPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const selected = new Set(state.view?.selection.map((s) => s.id) ?? []);
  const spin = new Map(project.spins.map((s) => [s.id, s.label]));
  const rows = useRowWindow(project.couplings.length);
  return (
    <Panel title={strings.couplings} id="pane-couplings" actions={<span className="muted">{strings.couplingsCount(project.couplings.length)}</span>}>
      <p className="help">{strings.selectHint}</p>
      <div className={rows.windowed ? "scroll windowed" : "scroll"} ref={rows.ref}>
        <table className="grid">
          <thead>
            <tr>
              <th>{strings.colCoupling}</th>
              <th>{strings.colSpins}</th>
              <th>{strings.colObservable}</th>
              <th className="num">{strings.colObserved}</th>
              <th className="num">{strings.colSigma}</th>
              <th className="num">{strings.colMultiplicity}</th>
              <th>{strings.colSigmaSource}</th>
            </tr>
          </thead>
          <tbody>
            <Spacer height={rows.before} columns={7} />
            {project.couplings.slice(rows.start, rows.end).map((c) => (
              <tr key={c.id} {...selectableRow(studio, c.id, selected)}>
                <td>{c.label}</td>
                <td>
                  {spin.get(c.spin_a) ?? c.spin_a} – {spin.get(c.spin_b) ?? c.spin_b}
                </td>
                <td>{c.observable}</td>
                <td className="num">{hz(c.value.value)}</td>
                <td className="num">{hz(c.sigma.value)}</td>
                <td className="num" title={c.equivalent_pairs.join(", ")}>
                  ×{c.multiplicity}
                </td>
                <td className="clip" title={c.sigma_source}>
                  {c.sigma_source}
                </td>
              </tr>
            ))}
            <Spacer height={rows.after} columns={7} />
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function SpinsPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const selected = new Set(state.view?.selection.map((s) => s.id) ?? []);
  return (
    <Panel title={strings.spins} id="pane-spins" actions={<span className="muted">{project.spins.length}</span>}>
      <table className="grid compact">
        <thead>
          <tr>
            <th>{strings.colLabel}</th>
            <th>{strings.colIsotope}</th>
            <th className="num">{strings.colAtom}</th>
          </tr>
        </thead>
        <tbody>
          {project.spins.map((s) => (
            <tr key={s.id} {...selectableRow(studio, s.id, selected)}>
              <td>{s.label}</td>
              <td>{s.isotope}</td>
              <td className="num">{s.atom ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
