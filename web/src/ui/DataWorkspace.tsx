import { useEffect, useState } from "react";
import { callOperation, type DescribeProjectOut, type ModelOut, type ModelSetIn } from "../api";
import { angstrom, hz } from "../format";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { download, FileButton, Panel, selectableRow } from "./common";

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
            <ModelPane studio={studio} state={state} project={project} />
          </>
        )}
      </div>
      <div className="column main">
        {project && view?.project_open ? (
          <>
            <CouplingsPane studio={studio} state={state} project={project} />
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
  useEffect(() => setDraft((declared ?? ["", "", "", ""]).map(String)), [project.science_hash]);
  if (geometry.kind !== "imported") return null;
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
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

type ModelDraft = { kind: ModelOut["kind"]; order: ModelOut["order"]; frame: ModelOut["frame"]; from: string; to: string };

function toDraft(model: ModelOut): ModelDraft {
  return {
    kind: model.kind,
    order: model.order,
    frame: model.frame,
    from: String(model.phi_domain[0].value),
    to: String(model.phi_domain[1].value),
  };
}

const KINDS: readonly ModelOut["kind"][] = ["rigid", "jump4"];
const ORDERS: readonly ModelOut["order"][] = ["bisector-diagonal", "c2z", "c1"];
const FRAMES: readonly ModelOut["frame"][] = ["bisector", "ring-a", "input"];

/** The model inspector (an inspector, not a dialog: ui-design §3). The server validates every
 * combination; an invalid one comes back as an error naming the field. */
function ModelPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const [draft, setDraft] = useState(() => toDraft(project.model));
  useEffect(() => setDraft(toDraft(project.model)), [project.science_hash]);
  const saved = toDraft(project.model);
  const changed = (Object.keys(draft) as (keyof ModelDraft)[]).some((k) => draft[k] !== saved[k]);
  const from = Number(draft.from);
  const to = Number(draft.to);
  const numbers = draft.from.trim() !== "" && draft.to.trim() !== "" && Number.isFinite(from) && Number.isFinite(to);
  const apply = () => {
    const args: ModelSetIn = {
      kind: draft.kind,
      order: draft.order,
      frame: draft.frame,
      phi_domain: [
        { value: from, unit: "deg" },
        { value: to, unit: "deg" },
      ],
      expected_science_revision: project.science_revision,
    };
    void studio.command("model.set", (t) => callOperation("model.set", args, t));
  };
  return (
    <Panel title={strings.model} id="pane-model">
      <div className="form">
        <label htmlFor="model-kind">{strings.modelKind}</label>
        <select id="model-kind" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as ModelDraft["kind"] })}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {strings.kindName[k]}
            </option>
          ))}
        </select>
        <label htmlFor="model-order">{strings.modelOrder}</label>
        <select id="model-order" value={draft.order} onChange={(e) => setDraft({ ...draft, order: e.target.value as ModelDraft["order"] })}>
          {ORDERS.map((k) => (
            <option key={k} value={k}>
              {strings.orderModelName[k]}
            </option>
          ))}
        </select>
        <label htmlFor="model-frame">{strings.modelFrame}</label>
        <select id="model-frame" value={draft.frame} onChange={(e) => setDraft({ ...draft, frame: e.target.value as ModelDraft["frame"] })}>
          {FRAMES.map((k) => (
            <option key={k} value={k}>
              {strings.frameName[k]}
            </option>
          ))}
        </select>
        <span className="label">{strings.phiDomain}</span>
        <span className="row">
          <input
            aria-label={`${strings.phiDomain} ${strings.phiFrom}`}
            inputMode="decimal"
            className="short"
            value={draft.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
          <span className="muted">–</span>
          <input
            aria-label={`${strings.phiDomain} ${strings.phiTo}`}
            inputMode="decimal"
            className="short"
            value={draft.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </span>
      </div>
      <div className="row end">
        <button type="button" disabled={!changed} onClick={() => setDraft(saved)}>
          {strings.resetModel}
        </button>
        <button type="button" className="primary" disabled={!changed || !numbers || state.busy !== null} onClick={apply}>
          {strings.applyModel}
        </button>
      </div>
      <p className="help">{project.frame}</p>
    </Panel>
  );
}

function CouplingsPane({ studio, state, project }: Props & { project: DescribeProjectOut }) {
  const selected = new Set(state.view?.selection.map((s) => s.id) ?? []);
  const spin = new Map(project.spins.map((s) => [s.id, s.label]));
  return (
    <Panel title={strings.couplings} id="pane-couplings" actions={<span className="muted">{strings.couplingsCount(project.couplings.length)}</span>}>
      <p className="help">{strings.selectHint}</p>
      <div className="scroll">
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
            {project.couplings.map((c) => (
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
