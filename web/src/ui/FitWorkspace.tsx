import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  callOperation,
  type ErrorBody,
  type FitRunOut,
  type FittedCoupling,
  type LandscapeOut,
  type NamedValue,
  type PreviewOut,
  type RunOut,
} from "../api";
import { boundsCurrent, inputText, LatestOnly, p95, parseAngle, snap, startAt } from "../preview";
import { atPlace, decimalsFor, fixed, hz, pValue, residualHz, scientific, signed, withUncertainty } from "../format";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { LandscapePlot, ObsCalcPlot, ResidualBar } from "./charts";
import { adequacyLabel, Chip, decimalsOf, Panel, Quantity, selectableRow, unitOf } from "./common";

type Props = { studio: Studio; state: StudioState };

/** The slider's resolution in degrees. */
const PHI_STEP = 0.1;

/** The Fit workspace: run the fit as a job, follow it, and read each run's diagnostics. */
export function FitWorkspace({ studio, state }: Props) {
  const { view, runs } = state;
  const [chosen, setChosen] = useState<string | null>(null);
  // The run shown: the one picked in the list, else the one the shared view reflects, else the newest.
  const runId = (chosen && runs.some((r) => r.id === chosen) ? chosen : null) ?? view?.run?.run_id ?? runs[0]?.id ?? null;
  useEffect(() => {
    if (runId) void studio.loadResult(runId);
  }, [studio, runId]);
  const run = runs.find((r) => r.id === runId) ?? null;

  return (
    <div className="workspace" id="panel-fit" role="tabpanel" aria-labelledby="tab-fit">
      <div className="column side">
        <RunControls studio={studio} state={state} onSubmitted={() => setChosen(null)} />
        <JobsPane state={state} studio={studio} />
        <RunsPane state={state} runId={runId} onChoose={setChosen} />
      </div>
      <div className="column main">
        {view?.project_open && view.warnings.length > 0 && (
          <ul className="warnings" aria-label={strings.viewWarnings}>
            {view.warnings.map((w) => (
              <li key={w}>! {w}</li>
            ))}
          </ul>
        )}
        {run ? (
          <RunDetail studio={studio} state={state} run={run} result={state.results[run.id]} />
        ) : (
          <p className="empty">{strings.noRuns}</p>
        )}
        {view?.project_open && <PreviewPane studio={studio} state={state} />}
      </div>
    </div>
  );
}

function RunControls({ studio, state, onSubmitted }: Props & { onSubmitted: () => void }) {
  const { view, project, busy, jobs } = state;
  const [intervals, setIntervals] = useState(false);
  const active = jobs.filter((j) => j.status === "queued" || j.status === "running");
  const ready = Boolean(view?.project_open && project?.ready_to_fit);
  return (
    <Panel title={strings.workspace.fit} id="pane-run">
      <div className="stack">
        <div className="row">
          <button
            type="button"
            className="primary"
            disabled={!ready || busy !== null || !view}
            title={ready ? undefined : (project?.not_ready_reason ?? strings.notReadyToFit)}
            onClick={async () => {
              if (!view) return;
              const submitted = await studio.command("fit.run", (t) =>
                callOperation("fit.run", { expected_science_revision: view.science_revision, intervals }, t),
              );
              if (submitted) onSubmitted();
            }}
          >
            {strings.runFit}
          </button>
          <label className="check">
            <input type="checkbox" checked={intervals} onChange={(e) => setIntervals(e.target.checked)} />
            {strings.intervals}
          </label>
        </div>
        {!ready && view?.project_open && <p className="help">{project?.not_ready_reason ?? strings.notReadyToFit}</p>}
        {active.map((job) => (
          <div key={job.id} className="row job-active">
            <span className="spinner" aria-hidden="true" />
            <span>
              {job.id} · {strings.jobStatus[job.status]}
            </span>
            <button
              type="button"
              onClick={() => void studio.command("job.cancel", (t) => callOperation("job.cancel", { job_id: job.id }, t))}
            >
              {strings.cancelJob}
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function JobsPane({ state }: Props) {
  const finished = state.jobs.filter((j) => j.status !== "queued" && j.status !== "running");
  if (finished.length === 0) return null;
  return (
    <Panel title={strings.jobs} id="pane-jobs">
      <ul className="plain jobs">
        {finished.map((job) => (
          <li key={job.id}>
            <Chip
              tone={job.status === "succeeded" ? "good" : job.status === "cancelled" ? "neutral" : "crit"}
              title={job.error ? `${job.error.code}: ${job.error.message}` : undefined}
            >
              {job.id} · {strings.jobStatus[job.status]}
            </Chip>
            {job.stale && <span className="badge badge-stale">{strings.stale}</span>}
            {job.error && <div className="help">{job.error.message}</div>}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

const timeOf = (iso: string) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString();
};

function RunsPane({ state, runId, onChoose }: { state: StudioState; runId: string | null; onChoose: (id: string) => void }) {
  const current = state.view?.run?.run_id;
  return (
    <Panel title={strings.runs} id="pane-runs" actions={<span className="muted">{state.runs.length}</span>}>
      {state.runs.length === 0 ? (
        <p className="muted">{strings.noRuns}</p>
      ) : (
        <table className="grid compact">
          <thead>
            <tr>
              <th>{strings.colRun}</th>
              <th>{strings.colCreated}</th>
              <th className="num">{strings.colRevision}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {state.runs.map((r) => (
              <tr
                key={r.id}
                className={r.id === runId ? "selected" : undefined}
                aria-selected={r.id === runId}
                tabIndex={0}
                onClick={() => onChoose(r.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onChoose(r.id);
                  }
                }}
              >
                <td>{r.id}</td>
                <td>{timeOf(r.created_at)}</td>
                <td className="num">{r.science_revision}</td>
                <td>
                  {r.stale ? (
                    <span className="badge badge-stale" title={strings.staleHelp}>
                      {strings.stale}
                    </span>
                  ) : r.id === current ? (
                    <span className="badge">{strings.current}</span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function valueOf(list: readonly NamedValue[] | null, name: string): number | null {
  return list?.find((v) => v.name === name)?.value ?? null;
}

function RunDetail({ studio, state, run, result }: Props & { run: RunOut; result: FitRunOut | undefined }) {
  if (!result && run.id in state.failedResults) {
    const failure = state.failedResults[run.id];
    return (
      <div className="empty" role="alert">
        <p>
          {strings.runUnavailable}
          {failure && ` ${failure.code}: ${failure.message}`}
        </p>
        <button type="button" onClick={() => void studio.loadResult(run.id, true)}>
          {strings.retry}
        </button>
      </div>
    );
  }
  if (!result) return <p className="muted">{strings.loadingRun}</p>;
  const selected = new Set(state.view?.selection.map((s) => s.id) ?? []);
  const flags = result.validity;
  const intervalOf = (name: string) => result.intervals.find((i) => i.parameter === name);

  const parameterRows = (values: readonly NamedValue[]) =>
    values.map((v) => {
      const sigma = valueOf(result.stderr, v.name);
      const interval = intervalOf(v.name);
      const places = decimalsFor(sigma ?? Number.NaN) ?? decimalsOf(v.name);
      return (
        <tr key={v.name}>
          <td>
            <Quantity name={v.name} />
          </td>
          <td className="num">
            {withUncertainty(v.value, sigma, decimalsOf(v.name))}
            {unitOf(v.name)}
          </td>
          <td className="num">
            {interval?.supported && interval.lower !== null && interval.upper !== null
              ? `[${atPlace(interval.lower, places + 1)}, ${atPlace(interval.upper, places + 1)}]${unitOf(v.name)}`
              : interval
                ? <span className="muted" title={interval.note}>{strings.intervalUnsupported}</span>
                : "—"}
          </td>
        </tr>
      );
    });

  return (
    <>
      <Panel
        title={`${run.id}`}
        id="pane-run-detail"
        actions={
          run.stale ? (
            <span className="badge badge-stale" title={strings.staleHelp}>
              {strings.staleBadge}
            </span>
          ) : undefined
        }
      >
        <p className="statement">{result.statement}</p>
        <div className="cards">
          <section>
            <h3>{strings.parameters}</h3>
            <table className="grid">
              <thead>
                <tr>
                  <th>{strings.colParameter}</th>
                  <th className="num">{strings.colEstimate}</th>
                  <th className="num">{result.intervals[0]?.label ?? strings.colInterval}</th>
                </tr>
              </thead>
              <tbody>{parameterRows(result.theta)}</tbody>
            </table>
            <h3>{strings.orderParameters}</h3>
            <table className="grid">
              <tbody>{parameterRows(result.order)}</tbody>
            </table>
          </section>
          <section>
            <h3>{strings.quality}</h3>
            <dl className="facts num-facts">
              <dt>{strings.chi2}</dt>
              <dd className="num">{fixed(result.chi2, 2)}</dd>
              <dt>{strings.nObs} / {strings.pFree} / {strings.nu}</dt>
              <dd className="num">
                {result.n_obs} / {result.p_free} / {result.nu ?? "—"}
              </dd>
              <dt>{strings.reducedChi2}</dt>
              <dd className="num">{result.nu ? fixed(result.chi2 / result.nu, 2) : "—"}</dd>
              <dt>{strings.pValue}</dt>
              <dd className="num">{pValue(result.p_value)}</dd>
              <dt>{strings.rms}</dt>
              <dd className="num">{fixed(result.rms_residual.value, 2)} Hz</dd>
            </dl>
            <div className="chips">
              <Chip tone={result.adequate === null ? "neutral" : result.adequate ? "good" : "warn"}>
                {adequacyLabel(result.adequate, result.p_value)}
              </Chip>
            </div>
          </section>
          <section>
            <h3>{strings.validity}</h3>
            <div className="chips">
              {(["converged", "search_resolved", "derivatives_resolved", "regular"] as const).map((flag) => (
                <Chip key={flag} tone={flags[flag] ? "good" : flag === "converged" ? "crit" : "warn"}>
                  {strings.flag[flag][flags[flag] ? 0 : 1]}
                </Chip>
              ))}
              <Chip tone={flags.physically_admissible === null ? "neutral" : flags.physically_admissible ? "good" : "crit"}>
                {strings.admissible(flags.physically_admissible)}
              </Chip>
            </div>
            <dl className="facts num-facts">
              <dt>{strings.innerRank}</dt>
              <dd>{strings.rank(flags.inner_rank, flags.inner_parameters)}</dd>
              <dt>{strings.jointRank}</dt>
              <dd>{strings.rank(flags.joint_rank, flags.joint_parameters)}</dd>
              <dt>{strings.condition}</dt>
              <dd className="num">{flags.inner_condition_number === null ? "∞" : scientific(flags.inner_condition_number)}</dd>
              <dt>{strings.atBound}</dt>
              <dd>{flags.at_bound.length ? flags.at_bound.join(", ") : strings.none}</dd>
            </dl>
            {result.unidentified.length > 0 && (
              <>
                <h4>{strings.unidentified}</h4>
                <ul className="plain">
                  {result.unidentified.map((direction, k) => (
                    <li key={k}>
                      {direction.map((d, j) => (
                        <span key={d.name}>
                          {j > 0 && " + "}
                          {signed(d.value, 3)}·<Quantity name={d.name} />
                        </span>
                      ))}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        </div>
        {result.basins.length > 1 && (
          <details>
            <summary>
              {strings.basins} ({result.basins.length - 1})
            </summary>
            <table className="grid compact">
              <thead>
                <tr>
                  <th>{strings.colBasin}</th>
                  <th className="num">{strings.chi2}</th>
                  <th className="num">{strings.colDeltaChi2}</th>
                </tr>
              </thead>
              <tbody>
                {result.basins.map((b, k) => (
                  <tr key={k}>
                    <td>
                      {b.theta.map((v) => (
                        <span key={v.name}>
                          <Quantity name={v.name} /> = {fixed(v.value, decimalsOf(v.name))}
                          {unitOf(v.name)}{" "}
                        </span>
                      ))}
                    </td>
                    <td className="num">{scientific(b.chi2, 4)}</td>
                    <td className="num">{scientific(b.delta_chi2, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
        {result.notes.length > 0 && (
          <>
            <h3>{strings.notes}</h3>
            <ul className="plain notes">
              {result.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </>
        )}
        <details>
          <summary>{strings.details}</summary>
          <dl className="facts">
            <dt>{strings.policy}</dt>
            <dd>{result.intervals_policy}</dd>
            <dt>{strings.fitVersion}</dt>
            <dd>
              <code>{result.fit_version}</code>
            </dd>
            {Object.entries(result.numerical_context).map(([k, v]) => (
              <div key={k} className="contents">
                <dt>{k}</dt>
                <dd>
                  <code>{String(v)}</code>
                </dd>
              </div>
            ))}
          </dl>
        </details>
      </Panel>
      <ResidualsPane studio={studio} couplings={result.couplings} selected={selected} rms={result.rms_residual.value} />
    </>
  );
}

/** Memoized: the live preview re-renders its pane at every slider step, and this table only
 * changes when a preview answers (M3 step 3). */
const ResidualsPane = memo(function ResidualsPane({
  studio,
  couplings,
  selected,
  rms,
  title = strings.residuals,
  stale = false,
}: {
  studio: Studio;
  couplings: readonly FittedCoupling[];
  selected: ReadonlySet<string>;
  rms: number;
  title?: string;
  stale?: boolean;
}) {
  const pick = (id: string) => selectableRow(studio, id, selected).onClick();
  return (
    <Panel title={title} id={`pane-${title === strings.residuals ? "residuals" : "preview-residuals"}`}>
      <div className={stale ? "residuals stale" : "residuals"}>
        <div className="scroll">
          <p className="help">
            {strings.selectHint} {strings.residualBarHelp}
          </p>
          <table className="grid">
            <thead>
              <tr>
                <th>{strings.colCoupling}</th>
                <th className="num">{strings.colObserved}</th>
                <th className="num">{strings.colSigma}</th>
                <th className="num">{strings.colCalculated}</th>
                <th className="num">{strings.colResidual}</th>
                <th className="num" colSpan={2}>
                  {strings.colNormalized}
                </th>
              </tr>
            </thead>
            <tbody>
              {couplings.map((c) => (
                <tr key={c.id} {...selectableRow(studio, c.id, selected)}>
                  <td>{c.label}</td>
                  <td className="num">{hz(c.observed.value)}</td>
                  <td className="num">{hz(c.sigma.value)}</td>
                  <td className="num">{hz(c.calculated.value)}</td>
                  <td className="num">{residualHz(c.residual.value)}</td>
                  <td className="num">{signed(c.normalized_residual, 2)}</td>
                  <td>
                    <ResidualBar normalized={c.normalized_residual} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3>{strings.obsCalc}</h3>
          <ObsCalcPlot couplings={couplings} selected={selected} rms={rms} onPick={pick} />
        </div>
      </div>
    </Panel>
  );
});

/** Answers that the preview shows in the pane instead of the page's error banner. */
const PREVIEW_QUIET = ["OUT_OF_DOMAIN", "PROJECT_NOT_READY", "NO_PROJECT", "INVALID_ARGUMENT"] as const;

type Previewed = { out: PreviewOut; error: null } | { out: null; error: ErrorBody };

/** The live preview (M3 step 3): drag φ and the order parameters, χ² and residuals follow
 * (fit.preview, a query: nothing is recorded), along the χ²(φ) landscape (fit.landscape). One
 * request is in flight at a time and only the newest position waits (preview.ts LatestOnly);
 * after any science change the preview and the landscape are read again. */
function PreviewPane({ studio, state }: Props) {
  const { view, project } = state;
  const lo = project?.model.phi_domain[0].value ?? 0;
  const hi = project?.model.phi_domain[1].value ?? 90;
  const run = view?.run && !view.run.stale ? state.results[view.run.run_id] : undefined;
  const fitted = run?.theta.find((t) => t.name === "phi_deg")?.value ?? null;

  const [phi, setPhi] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [shown, setShown] = useState<Previewed | null>(null);
  const [land, setLand] = useState<LandscapeOut | null>(null);
  const live = useMemo(
    () =>
      new LatestOnly<number, Previewed>(
        async (value) => {
          let error: ErrorBody | null = null;
          const out = await studio.run(async (t) => {
            const envelope = await callOperation("fit.preview", { phi: { value, unit: "deg" } }, t);
            if (!envelope.ok) error = envelope.error;
            return envelope;
          }, PREVIEW_QUIET);
          if (out) return { out, error: null };
          return error ? { out: null, error } : null;
        },
        (_value, result) => setShown(result),
        () => performance.now(),
      ),
    [studio],
  );
  useEffect(() => () => live.cancel(), [live]);

  const go = (value: number) => {
    const v = snap(value, lo, hi, PHI_STEP);
    setPhi(v);
    setText(inputText(v));
    live.ask(v);
  };

  // The landscape, read again after every science change (an older answer is dropped).
  const revision = view?.science_revision;
  useEffect(() => {
    let current = true;
    void studio.run((t) => callOperation("fit.landscape", {}, t), PREVIEW_QUIET).then((r) => {
      if (current && r) setLand(r);
    });
    return () => {
      current = false;
    };
  }, [studio, revision]);

  // Start where the fit is, else at the landscape's lowest sample, and clamp to the domain again
  // after a science change: both only once the domain shown is the current science's (round 48;
  // project.describe and the view can arrive in either order).
  const current = boundsCurrent(project?.science_revision ?? null, view?.science_revision ?? null);
  useEffect(() => {
    const start = startAt({
      current: phi,
      fitted,
      landscape: land,
      projectRevision: project?.science_revision ?? null,
      viewRevision: view?.science_revision ?? null,
    });
    if (start !== null) go(start);
  }, [fitted, land, current]);
  useEffect(() => {
    if (phi !== null && current) go(phi);
  }, [revision, lo, hi, current]);

  const preview = shown?.out ?? null;
  const stale = preview !== null && view !== null && preview.science_revision !== view.science_revision;
  const selection = view?.selection.map((s) => s.id).join(" ") ?? "";
  const selected = useMemo(() => new Set(selection === "" ? [] : selection.split(" ")), [selection]);
  const timing = p95(live.timings);
  const commitText = () => {
    const value = parseAngle(text);
    if (value !== null) go(value);
    else if (phi !== null) setText(inputText(phi));
  };

  return (
    <>
      <Panel title={strings.preview} id="pane-preview">
        <div className="row">
          <label htmlFor="phi-slider">{strings.phiLabel}</label>
          <input
            id="phi-slider"
            type="range"
            className="slider"
            min={lo}
            max={hi}
            step={PHI_STEP}
            value={phi ?? lo}
            aria-valuetext={phi === null ? undefined : `${fixed(phi, 1)}°`}
            onChange={(e) => go(Number(e.target.value))}
          />
          <input
            id="phi"
            aria-label={strings.phiExact}
            inputMode="decimal"
            className="short"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={commitText}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitText();
            }}
          />
          {fitted !== null && (
            <button type="button" className="quiet" onClick={() => go(fitted)}>
              {strings.toFitted(fixed(fitted, 2))}
            </button>
          )}
          {stale && (
            <span className="badge badge-stale" title={strings.staleHelp}>
              {strings.stale}
            </span>
          )}
        </div>
        <p className="help">
          {strings.previewHelp}
          {timing !== null && <span className="muted"> {strings.previewTiming(Math.round(timing), live.timings.length)}</span>}
        </p>
        {shown?.error && (
          <p className="warn-text" role="alert">
            <strong>{shown.error.code}</strong>: {shown.error.message}
          </p>
        )}
        {preview && (
          <p className={stale ? "meta stale" : "meta"} aria-live="polite">
            <Quantity name="phi_deg" /> = {fixed(preview.phi.value, 2)}° ·{" "}
            {preview.order.map((o) => (
              <span key={o.name}>
                <Quantity name={o.name} /> = {fixed(o.value, 4)}{" "}
              </span>
            ))}
            · χ² = {fixed(preview.chi2, 2)} (N = {preview.n_obs}) · RMS = {fixed(preview.rms_residual.value, 2)} Hz ·{" "}
            {strings.admissible(preview.validity.physically_admissible)}
          </p>
        )}
        {land && (
          <LandscapePlot
            landscape={land}
            phi={preview?.phi.value ?? phi}
            fitted={fitted}
            stale={view !== null && land.science_revision !== view.science_revision}
            onPick={go}
          />
        )}
      </Panel>
      {preview && (
        <ResidualsPane
          studio={studio}
          couplings={preview.couplings}
          selected={selected}
          rms={preview.rms_residual.value}
          title={`${strings.residuals}: ${strings.preview.toLowerCase()}`}
          stale={stale}
        />
      )}
    </>
  );
}
