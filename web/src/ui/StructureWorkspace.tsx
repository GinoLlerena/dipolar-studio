import { type KeyboardEvent, type PointerEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { callOperation, type DescribeProjectOut, type SceneOut } from "../api";
import { fixed, residualHz } from "../format";
import { autoCamera, type Camera, drawOrder, project, type Vec3 } from "../scene/projection";
import {
  arcPath,
  arcWidth,
  CameraCommits,
  cameraIn,
  cameraOf,
  DEGREES_PER_PIXEL,
  dolly,
  guarded,
  keyMove,
  misfitStep,
  orbit,
  radiusAbout,
  ZOOM_STEP,
} from "../scene/view";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { Panel, selectableRow } from "./common";

// The minimal Structure view (03 §5; M3 step 2): the molecule as the shared scene describes it,
// with couplings drawn as misfit arcs whose colour and width encode |residual|/σ. Every action
// here has a table alternative: the couplings table below (and in the Data and Fit workspaces)
// selects the same objects, and the selection is shared with every client.

type Props = { studio: Studio; state: StudioState };

export function StructureWorkspace({ studio, state }: Props) {
  const { scene, project, view } = state;
  const open = view?.project_open && scene && project;
  return (
    <div className="workspace" id="panel-structure" role="tabpanel" aria-labelledby="tab-structure">
      <div className="column side">
        {open && <LayersPane studio={studio} scene={scene} busy={state.busy !== null} />}
        {open && <SelectionPane studio={studio} scene={scene} project={project} />}
        {open && <Legend hasResiduals={scene.couplings.some((c) => c.residual !== null)} />}
      </div>
      <div className="column main">
        {open ? <ScenePane studio={studio} scene={scene} project={project} viewRevision={view?.workspace_revision ?? 0} /> : <p className="empty">{strings.noProjectYet}</p>}
        {open && <ResidualTable studio={studio} scene={scene} project={project} />}
      </div>
    </div>
  );
}

/** |residual|/σ for each coupling the scene shows with a residual. */
function normalizedResiduals(scene: SceneOut, project: DescribeProjectOut): Map<string, number> {
  const sigma = new Map(project.couplings.map((c) => [c.id, c.sigma.value]));
  const out = new Map<string, number>();
  for (const c of scene.couplings) {
    const s = sigma.get(c.id);
    if (c.residual !== null && s !== undefined && s > 0) out.set(c.id, c.residual.value / s);
  }
  return out;
}

const MIN_SIDE = 16;
const MAX_SIDE = 8192;
/** A drag starts after this many pixels; less is a click (a pick). */
const DRAG_THRESHOLD = 4;
/** Keys and the wheel commit the camera after this long without another move. */
const COMMIT_DELAY_MS = 400;

function useSize(): [RefObject<HTMLDivElement | null>, { width: number; height: number }] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 640, height: 420 });
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const clamp = (v: number) => Math.min(Math.max(Math.round(v), MIN_SIDE), MAX_SIDE);
      setSize({ width: clamp(entry.contentRect.width), height: clamp(entry.contentRect.height) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size];
}

function ScenePane({
  studio,
  scene,
  project: prj,
  viewRevision,
}: {
  studio: Studio;
  scene: SceneOut;
  project: DescribeProjectOut;
  viewRevision: number;
}) {
  const [box, { width, height }] = useSize();
  const svg = useRef<SVGSVGElement | null>(null);
  // A camera moved here and not yet echoed back by the server. It is shown only while the shared
  // view is at the revision it was moved from: a newer revision (ours, or another client's move,
  // which wins) replaces it.
  const [local, setLocal] = useState<{ camera: Camera; revision: number } | null>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean; id: number } | null>(null);
  const suppressClick = useRef(false);

  const points = useMemo(() => scene.atoms.map((a) => a.position.xyz as Vec3), [scene]);
  const shared = useMemo(
    () => (scene.camera.automatic ? autoCamera(points, width, height) : cameraOf(scene.camera)),
    [scene, points, width, height],
  );
  const camera = local !== null && local.revision === scene.workspace_revision ? local.camera : shared;
  const latest = useRef({ camera, width, height, revision: scene.workspace_revision, points });
  latest.current = { camera, width, height, revision: scene.workspace_revision, points };

  // One committer per pane: it drops a delayed commit that a newer revision or action supersedes,
  // and each commit names the revision its camera was moved from, so the server refuses a camera
  // that a newer one has replaced meanwhile (rounds 41–42).
  const [commits] = useState(
    () =>
      new CameraCommits(
        scene.workspace_revision,
        (next, revision) => {
          const { width: w, height: h } = latest.current;
          void studio
            .command(
              "view.set_camera",
              (t) =>
                callOperation(
                  "view.set_camera",
                  {
                    camera: next === null ? null : cameraIn(next),
                    viewport: { width: w, height: h },
                    expected_workspace_revision: revision,
                  },
                  t,
                ),
              ["REVISION_CONFLICT"], // superseded: the newer camera stays, quietly
            )
            .then((done) => {
              if (done === null) {
                setLocal(null); // refused: show the shared camera again
                studio.refresh(["view", "scene"]);
              }
            });
        },
        { set: (fn, ms) => window.setTimeout(fn, ms), clear: (handle) => window.clearTimeout(handle as number) },
      ),
  );
  // The newest workspace revision any response has shown: the scene's, or the view's when its
  // read answers first.
  commits.observe(Math.max(scene.workspace_revision, viewRevision));
  useEffect(() => () => commits.cancel(), [commits]);

  const move = (next: Camera, later: boolean) => {
    const revision = latest.current.revision;
    setLocal({ camera: next, revision });
    if (later) commits.later(next, revision, COMMIT_DELAY_MS);
  };
  const radius = () => radiusAbout(latest.current.points, latest.current.camera.target);
  const fitToView = () => {
    setLocal(null);
    commits.now(null, null);
  };

  // The wheel needs a non-passive listener to keep the page from scrolling.
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const current = latest.current.camera;
      move(guarded(current, dolly(current, e.deltaY > 0 ? ZOOM_STEP : 1 / ZOOM_STEP, radius())), true);
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  });

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    suppressClick.current = false; // a click is suppressed only right after a drag
    drag.current = { x: e.clientX, y: e.clientY, moved: false, id: e.pointerId };
  };
  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (!d.moved) {
      d.moved = true;
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    d.x = e.clientX;
    d.y = e.clientY;
    commits.cancel(); // a drag supersedes a key's or the wheel's pending commit
    const current = latest.current.camera;
    move(guarded(current, orbit(current, -dx * DEGREES_PER_PIXEL, -dy * DEGREES_PER_PIXEL)), false);
  };
  const onPointerUp = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    drag.current = null;
    if (d?.moved) {
      suppressClick.current = true; // the click that ends a drag is not a pick
      if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
      commits.now(latest.current.camera, latest.current.revision);
    }
  };
  const onKeyDown = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "0" || e.key === "Home") {
      e.preventDefault();
      fitToView();
      return;
    }
    const next = keyMove(latest.current.camera, e.key, radius());
    if (next) {
      e.preventDefault();
      move(next, true);
    }
  };

  const selected = new Set(scene.selection);
  const highlighted = new Set(scene.highlights);
  const pick = (id: string, additive: boolean) => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    let ids: string[];
    if (additive) ids = selected.has(id) ? scene.selection.filter((s) => s !== id) : [...scene.selection, id];
    else ids = selected.has(id) && selected.size === 1 ? [] : [id];
    void studio.command("view.select", (t) => callOperation("view.select", { ids }, t));
  };

  const projected = project(camera, width, height, points);
  const ids = scene.atoms.map((a) => a.id);
  const at = new Map(ids.map((id, k) => [id, projected[k]] as const));
  const order = drawOrder(ids, projected);
  const depths = projected.filter((p) => p.visible).map((p) => p.depth);
  const reference = depths.length ? depths.reduce((a, b) => a + b, 0) / depths.length : 1;
  const atoms = new Map(scene.atoms.map((a) => [a.id, a]));
  const normalized = normalizedResiduals(scene, prj);
  const labelOf = new Map(prj.couplings.map((c) => [c.id, c.label]));

  return (
    <Panel
      title={strings.structure}
      id="pane-structure"
      actions={
        <button type="button" className="quiet" onClick={fitToView}>
          {strings.fitView}
        </button>
      }
    >
      <div className="scene-box" ref={box}>
        <svg
          ref={svg}
          className="scene"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          tabIndex={0}
          role="group"
          aria-roledescription="3D structure view"
          aria-label={strings.structureLabel(
            scene.atoms.length,
            scene.couplings.length,
            fixed(scene.phi.value, 1),
            strings.phiSource[scene.phi_source],
          )}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            drag.current = null;
          }}
          onKeyDown={onKeyDown}
        >
          {scene.layers.bonds &&
            scene.bonds.map((b) => {
              const pa = at.get(b.a);
              const pb = at.get(b.b);
              if (!pa?.visible || !pb?.visible) return null;
              return <line key={`${b.a}-${b.b}`} className="scene-bond" x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} />;
            })}
          {scene.layers.couplings &&
            scene.couplings.map((c) => {
              const pa = at.get(c.spin_a);
              const pb = at.get(c.spin_b);
              if (!pa?.visible || !pb?.visible) return null;
              const z = normalized.get(c.id);
              const step = z === undefined ? null : misfitStep(z);
              const cls = [
                "arc",
                step === null ? "arc-none" : `m${step}`,
                selected.has(c.id) ? "is-selected" : "",
                highlighted.has(c.id) ? "is-highlighted" : "",
              ].join(" ");
              const label = labelOf.get(c.id) ?? c.id;
              return (
                <path
                  key={c.id}
                  data-id={c.id}
                  className={cls}
                  d={arcPath(pa, pb)}
                  strokeWidth={step === null ? 1 : arcWidth(step)}
                  onClick={(e) => pick(c.id, e.shiftKey)}
                >
                  <title>
                    {strings.arcTitle(
                      label,
                      c.residual === null ? null : residualHz(c.residual.value),
                      z === undefined ? null : fixed(z, 1),
                    )}
                  </title>
                </path>
              );
            })}
          {order.map((id) => {
            const p = at.get(id);
            const a = atoms.get(id);
            if (!p || !a) return null;
            const r = (7 * reference) / p.depth;
            const cls = [
              "atom",
              a.element === "H" ? "atom-h" : "atom-heavy",
              selected.has(id) ? "is-selected" : "",
              highlighted.has(id) ? "is-highlighted" : "",
            ].join(" ");
            const isSpin = id.startsWith("spn_");
            return (
              <g key={id} data-id={id}>
                <circle className={cls} cx={p.x} cy={p.y} r={r} onClick={isSpin ? (e) => pick(id, e.shiftKey) : undefined}>
                  <title>{a.label}</title>
                </circle>
                {scene.layers.labels && (
                  <text className="atom-label" x={p.x + r + 2} y={p.y - r - 2}>
                    {a.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="help">{strings.viewHelp}</p>
      {normalized.size === 0 && <p className="help">{strings.noResiduals}</p>}
    </Panel>
  );
}

function LayersPane({ studio, scene, busy }: { studio: Studio; scene: SceneOut; busy: boolean }) {
  const set = (key: keyof SceneOut["layers"], value: boolean) =>
    void studio.command("view.set_layers", (t) => callOperation("view.set_layers", { ...scene.layers, [key]: value }, t));
  return (
    <Panel title={strings.layers} id="pane-layers">
      <fieldset className="layers">
        <legend className="visually-hidden">{strings.layers}</legend>
        {(["couplings", "bonds", "labels"] as const).map((key) => (
          <label key={key} className="check">
            <input type="checkbox" checked={scene.layers[key]} disabled={busy} onChange={(e) => set(key, e.target.checked)} />
            {strings.layer[key]}
          </label>
        ))}
      </fieldset>
    </Panel>
  );
}

function SelectionPane({ studio, scene, project: prj }: { studio: Studio; scene: SceneOut; project: DescribeProjectOut }) {
  const couplings = new Map(prj.couplings.map((c) => [c.id, c]));
  const spins = new Map(prj.spins.map((s) => [s.id, s]));
  const residual = new Map(scene.couplings.map((c) => [c.id, c.residual]));
  return (
    <Panel
      title={strings.selection}
      id="pane-selection"
      actions={
        scene.selection.length > 0 && (
          <button
            type="button"
            className="quiet"
            onClick={() => void studio.command("view.select", (t) => callOperation("view.select", { ids: [] }, t))}
          >
            {strings.clearSelection}
          </button>
        )
      }
    >
      {scene.selection.length === 0 ? (
        <p className="help">{strings.nothingSelected}</p>
      ) : (
        <ul className="selection-list">
          {scene.selection.map((id) => {
            const c = couplings.get(id);
            if (c) {
              const r = residual.get(id);
              return (
                <li key={id}>
                  <strong>{strings.selectedCoupling(c.label)}</strong>: D = {fixed(c.value.value, 1)} ± {fixed(c.sigma.value, 1)} Hz
                  {r ? `, residual ${residualHz(r.value)} Hz` : ""}
                </li>
              );
            }
            const s = spins.get(id);
            return <li key={id}>{strings.selectedSpin(s?.label ?? id)}</li>;
          })}
        </ul>
      )}
      <p className="help">{strings.shiftHint}</p>
    </Panel>
  );
}

function Legend({ hasResiduals }: { hasResiduals: boolean }) {
  return (
    <Panel title={strings.misfitLegend} id="pane-legend">
      <ul className="legend">
        {strings.misfitSteps.map((label, step) => (
          <li key={label}>
            <svg width={36} height={12} aria-hidden="true">
              <path className={`arc m${step}`} d="M2,6 L34,6" strokeWidth={arcWidth(step)} />
            </svg>
            {label}
          </li>
        ))}
      </ul>
      {!hasResiduals && <p className="help">{strings.noResiduals}</p>}
    </Panel>
  );
}

/** The table alternative to the arcs: every coupling with its residual, selectable. */
function ResidualTable({ studio, scene, project: prj }: { studio: Studio; scene: SceneOut; project: DescribeProjectOut }) {
  const selected = new Set(scene.selection);
  const normalized = normalizedResiduals(scene, prj);
  const residual = new Map(scene.couplings.map((c) => [c.id, c.residual]));
  return (
    <Panel title={strings.couplings} id="pane-structure-couplings" actions={<span className="muted">{strings.couplingsCount(prj.couplings.length)}</span>}>
      <div className="scroll">
        <table className="grid">
          <thead>
            <tr>
              <th>{strings.colCoupling}</th>
              <th className="num">{strings.colObserved}</th>
              <th className="num">{strings.colSigma}</th>
              <th className="num">{strings.colResidual}</th>
              <th className="num">{strings.colNormalized}</th>
            </tr>
          </thead>
          <tbody>
            {prj.couplings.map((c) => {
              const r = residual.get(c.id);
              const z = normalized.get(c.id);
              return (
                <tr key={c.id} {...selectableRow(studio, c.id, selected)}>
                  <td>{c.label}</td>
                  <td className="num">{fixed(c.value.value, 1)}</td>
                  <td className="num">{fixed(c.sigma.value, 1)}</td>
                  <td className="num">{r ? residualHz(r.value) : "—"}</td>
                  <td className="num">
                    {z === undefined ? "—" : <span className={`misfit-chip m${misfitStep(z)}`}>{fixed(z, 1)}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
