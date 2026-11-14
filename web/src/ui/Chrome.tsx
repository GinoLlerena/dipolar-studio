import type { KeyboardEvent } from "react";
import { callOperation } from "../api";
import { fixed } from "../format";
import { waiting } from "../inbox";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { adequacyLabel, Chip } from "./common";

export type Workspace = "structure" | "data" | "fit" | "proposals";
export const WORKSPACES: readonly Workspace[] = ["structure", "data", "fit", "proposals"];

/** The title bar: project, revisions, undo/redo, the feed's state and the workspace tabs. */
export function TitleBar({
  studio,
  state,
  workspace,
  onWorkspace,
}: {
  studio: Studio;
  state: StudioState;
  workspace: Workspace;
  onWorkspace: (w: Workspace) => void;
}) {
  const { view, history, busy } = state;
  const pending = waiting(state.proposals, Date.now());
  const nextUndo = history?.undo[0];
  const nextRedo = history?.redo[0];
  const move = (name: "history.undo" | "history.redo") => {
    if (!view) return;
    const args = { expected_science_revision: view.science_revision };
    void (name === "history.undo"
      ? studio.command(name, (t) => callOperation("history.undo", args, t))
      : studio.command(name, (t) => callOperation("history.redo", args, t)));
  };
  const onTabKey = (e: KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const at = WORKSPACES.indexOf(workspace);
    const next = WORKSPACES[(at + (e.key === "ArrowRight" ? 1 : WORKSPACES.length - 1)) % WORKSPACES.length] ?? "data";
    onWorkspace(next);
    document.getElementById(`tab-${next}`)?.focus();
  };

  return (
    <header className="titlebar">
      <div className="brand">{strings.title}</div>
      <nav className="crumb" aria-label={strings.project}>
        <span className="crumb-name">{view?.project_open ? view.project_name : strings.noProject}</span>
        {view && (
          <span className="muted" title={strings.revisionsHelp}>
            {strings.revisions(view.science_revision, view.workspace_revision)}
          </span>
        )}
      </nav>
      <div role="tablist" aria-label={strings.workspaces} className="tabs" onKeyDown={onTabKey}>
        {WORKSPACES.map((w) => (
          <button
            key={w}
            id={`tab-${w}`}
            type="button"
            role="tab"
            aria-selected={w === workspace}
            aria-controls={`panel-${w}`}
            tabIndex={w === workspace ? 0 : -1}
            className={w === "proposals" && pending > 0 ? "tab tab-attention" : "tab"}
            title={w === "proposals" && pending > 0 ? strings.tabCountHelp(pending) : undefined}
            onClick={() => onWorkspace(w)}
          >
            {w === "proposals" ? strings.tabCount(strings.workspace[w], pending) : strings.workspace[w]}
          </button>
        ))}
      </div>
      <div className="titlebar-actions">
        <button
          type="button"
          disabled={!nextUndo || busy !== null}
          title={nextUndo ? strings.undoWhat(nextUndo.operation) : strings.nothingToUndo}
          onClick={() => move("history.undo")}
        >
          ↶ {strings.undo}
        </button>
        <button
          type="button"
          disabled={!nextRedo || busy !== null}
          title={nextRedo ? strings.redoWhat(nextRedo.operation) : strings.nothingToRedo}
          onClick={() => move("history.redo")}
        >
          ↷ {strings.redo}
        </button>
        <span className={`conn conn-${state.connection}`} title={strings.connectionHelp[state.connection]}>
          <span className="conn-dot" aria-hidden="true" />
          {strings.connection[state.connection]}
        </span>
      </div>
    </header>
  );
}

/** The status bar (plan §5): convergence, adequacy and identifiability are separate, with a
 * stale badge, so a run is never shown as good because it converged. Announced politely. */
export function StatusBar({ state }: { state: StudioState }) {
  const { view, jobs, results } = state;
  const active = jobs.find((j) => j.status === "queued" || j.status === "running");
  const run = view?.run ?? null;
  const fit = view?.fit ?? null;
  const result = run ? results[run.run_id] : undefined;
  return (
    <footer className="statusbar" role="status" aria-live="polite">
      {active && (
        <span className="status-job">
          <span className="spinner" aria-hidden="true" />
          {strings.statusFitting(strings.jobStatus[active.status])}
        </span>
      )}
      {!view?.project_open ? (
        <span className="muted">{strings.statusNoProject}</span>
      ) : !run ? (
        <span className="muted">{strings.statusNoFit}</span>
      ) : run.stale ? (
        // No fit summary for a stale run (describe_view): its numbers describe an earlier revision.
        <>
          <span className="muted">{run.run_id}</span>
          <span className="badge badge-stale" title={strings.staleHelp}>
            {strings.staleBadge}
          </span>
        </>
      ) : !run.available || !fit ? (
        <Chip tone="warn">{strings.unavailable}</Chip>
      ) : (
        <>
          <span className="muted">{run.run_id}</span>
          <Chip tone={fit.converged ? "good" : "crit"}>{strings.convergence[fit.converged ? "true" : "false"]}</Chip>
          <Chip tone={fit.adequate === null ? "neutral" : fit.adequate ? "good" : "warn"}>
            {adequacyLabel(fit.adequate, fit.p_value)}
          </Chip>
          <Chip tone={fit.identifiable ? "good" : "warn"}>{strings.identifiability(fit.identifiable)}</Chip>
          {!fit.regular && (
            <Chip tone="warn" title={strings.notRegularHelp}>
              {strings.flag.regular[1]}
            </Chip>
          )}
          <Chip tone={fit.physically_admissible === null ? "neutral" : fit.physically_admissible ? "good" : "crit"}>
            {strings.admissible(fit.physically_admissible)}
          </Chip>
          {result && (
            <span className="status-numbers">
              χ² {fixed(result.chi2, 2)}
              {result.nu !== null && result.nu > 0 && (
                <>
                  {" "}· ν {result.nu} · χ²ᵥ {fixed(result.chi2 / result.nu, 2)}
                </>
              )}{" "}
              · RMS {fixed(result.rms_residual.value, 2)} Hz
            </span>
          )}
        </>
      )}
    </footer>
  );
}
