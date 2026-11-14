import { useEffect, useRef, useState } from "react";
import { callOperation, type DryRunReport, type ErrorBody, type ProposalDetailOut, type ProposalOut } from "../api";
import {
  acceptBlocker,
  activeJobs,
  allSteps,
  argsText,
  type ChangeLine,
  changeLines,
  decidable,
  dryRunKey,
  expired,
  ordered,
  withDependencies,
  withoutDependents,
} from "../inbox";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { Chip, Panel, type Tone } from "./common";

// The proposal inbox (M3 step 3). Agents propose; a human decides here. Every decision is a
// registry command (proposal.accept, proposal.reject) and the server re-checks everything; before
// accepting, the page shows a dry run of exactly the acceptance the button would send.

type Props = { studio: Studio; state: StudioState };

/** The page's clock, ticking every `ms` (expiry is time-based: no feed line announces it). */
export function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(timer);
  }, [ms]);
  return now;
}

/** The newest science revision the page has seen (a response or a feed line). */
function revisionOf(studio: Studio, state: StudioState): number {
  return Math.max(state.view?.science_revision ?? 0, studio.newestScienceRevision);
}

export function InboxWorkspace({ studio, state }: Props) {
  const now = useNow(15_000);
  const list = ordered(state.proposals, now);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const shown = list.find((p) => p.id === chosenId) ?? list.find((p) => decidable(p, now)) ?? list[0] ?? null;
  const revision = revisionOf(studio, state);
  // The proposal shown stays shown once decided (the outcome stays on screen), even though a
  // decided proposal is no longer the first waiting one.
  useEffect(() => {
    if (shown && chosenId !== shown.id && !list.some((p) => p.id === chosenId)) setChosenId(shown.id);
  }, [shown?.id]);

  return (
    <div className="workspace" id="panel-proposals" role="tabpanel" aria-labelledby="tab-proposals">
      <div className="column side">
        <Panel title={strings.proposals} id="pane-proposals">
          <p className="help">{strings.proposalsHelp}</p>
          {list.length === 0 ? (
            <p className="empty">{strings.noProposals}</p>
          ) : (
            <table className="grid compact" aria-labelledby="pane-proposals">
              <thead>
                <tr>
                  <th>{strings.colProposal}</th>
                  <th>{strings.colProposer}</th>
                  <th>{strings.colStatus}</th>
                </tr>
              </thead>
              <tbody>
                {list.map((p) => {
                  const isShown = p.id === shown?.id;
                  const choose = () => setChosenId(p.id);
                  return (
                    <tr
                      key={p.id}
                      className={isShown ? "selected" : undefined}
                      aria-selected={isShown}
                      tabIndex={0}
                      onClick={choose}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          choose();
                        }
                      }}
                    >
                      <td>
                        <code>{p.id}</code>
                        <div className="help">{strings.stepsCount(p.steps.length)}</div>
                      </td>
                      <td>{p.proposer}</td>
                      <td>
                        <StatusChip proposal={p} now={now} revision={revision} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
      <div className="column main">
        {shown ? (
          <ProposalDetail key={shown.id} studio={studio} state={state} proposal={shown} now={now} revision={revision} />
        ) : (
          <p className="empty">{strings.noProposalChosen}</p>
        )}
      </div>
    </div>
  );
}

function statusOf(p: ProposalOut, now: number, revision: number): { tone: Tone; label: string } {
  if (expired(p, now)) return { tone: "neutral", label: strings.proposalStatus.expired };
  if (p.status === "accepted") return { tone: "good", label: strings.proposalStatus.accepted };
  if (p.status === "rejected") return { tone: "neutral", label: strings.proposalStatus.rejected };
  if (p.stale || p.base_science_revision !== revision) return { tone: "warn", label: strings.proposalStatus.stale };
  return { tone: "neutral", label: strings.proposalStatus.pending };
}

function StatusChip({ proposal, now, revision }: { proposal: ProposalOut; now: number; revision: number }) {
  const { tone, label } = statusOf(proposal, now, revision);
  return <Chip tone={tone}>{label}</Chip>;
}

function when(iso: string): string {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toLocaleString() : iso;
}

type DryRun = {
  key: string;
  report: DryRunReport | null;
  /** The workspace revision the dry run was planned at; the acceptance expects it (round 47). */
  workspace: number | null;
  error: ErrorBody | null;
};

function ProposalDetail({
  studio,
  state,
  proposal: p,
  now,
  revision,
}: Props & { proposal: ProposalOut; now: number; revision: number }) {
  const [detail, setDetail] = useState<ProposalDetailOut | null>(null);
  const [chosen, setChosen] = useState<number[]>(() => allSteps(p.steps));
  const [dry, setDry] = useState<DryRun | null>(null);
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<string | null>(null);
  const open = decidable(p, now);
  const blocker = acceptBlocker(p, chosen, revision, now);

  // The steps' arguments never change: read them once per proposal.
  useEffect(() => {
    let live = true;
    void studio.run((t) => callOperation("proposal.get", { proposal_id: p.id }, t)).then((d) => {
      if (live && d) setDetail(d);
    });
    return () => {
      live = false;
    };
  }, [studio, p.id]);

  // A dry run of exactly the acceptance the button would send, again whenever the choice, the
  // science or the proposal changes; only the latest answer is shown.
  // The workspace is part of it: a selection change alters what an acceptance does to the view
  // without changing the science (round 47).
  const workspace = Math.max(state.view?.workspace_revision ?? 0, studio.newestWorkspaceRevision);
  const [attempt, setAttempt] = useState(0);
  const key = dryRunKey({ proposal: p, chosen, science: revision, workspace, jobs: activeJobs(state.jobs), attempt });
  const latest = useRef(key);
  latest.current = key;
  useEffect(() => {
    if (!open || blocker !== null) {
      setDry(null);
      return;
    }
    void studio
      .dryRun((t) => callOperation("proposal.accept", { proposal_id: p.id, steps: chosen }, t, { dry_run: true }))
      .then((r) => {
        if (latest.current === key) {
          setDry({ key, report: r.report, workspace: r.revisions?.workspace ?? null, error: r.error });
        }
      });
  }, [key]); // the key names everything the dry run depends on

  const labels: Record<string, string> = Object.fromEntries([
    ...(state.project?.couplings ?? []).map((c) => [c.id, c.label] as const),
    ...(state.project?.spins ?? []).map((s) => [s.id, s.label] as const),
  ]);
  const checked = dry !== null && dry.key === key;
  const wouldFail = checked && dry.error !== null;

  const accept = async () => {
    if (!checked || dry.workspace === null) return;
    // Exactly what the dry run showed: these steps, at the science the proposal was made for (the
    // server requires it) and at the workspace revision the dry run saw.
    const expected = dry.workspace;
    const done = await studio.command("proposal.accept", (t) =>
      callOperation("proposal.accept", { proposal_id: p.id, steps: chosen, expected_workspace_revision: expected }, t),
    );
    if (done) {
      const jobs = done.results.filter((r) => r.operation === "fit.run").length;
      setOutcome(strings.acceptedOutcome(done.results.length, done.science_revision, jobs));
    }
  };
  const reject = async () => {
    const done = await studio.command("proposal.reject", (t) =>
      callOperation("proposal.reject", { proposal_id: p.id, reason }, t),
    );
    if (done) setOutcome(strings.rejectedOutcome);
  };

  return (
    <>
      <Panel
        title={
          <>
            {strings.proposal} <code>{p.id}</code>
          </>
        }
        id="pane-proposal"
        actions={<StatusChip proposal={p} now={now} revision={revision} />}
      >
        <dl className="facts">
          <dt>{strings.colProposer}</dt>
          <dd>{p.proposer}</dd>
          <dt>{strings.proposedAt}</dt>
          <dd>{when(p.created_at)}</dd>
          <dt>{strings.baseRevision}</dt>
          <dd>
            {strings.baseRevisionValue(p.base_science_revision, revision)}
          </dd>
          {p.status === "pending" && (
            <>
              <dt>{strings.expiresAt}</dt>
              <dd>{when(p.expires_at)}</dd>
            </>
          )}
          {p.decided_at && (
            <>
              <dt>{strings.decided}</dt>
              <dd>{strings.decidedBy(p.decided_by ?? "", when(p.decided_at))}</dd>
            </>
          )}
          {p.status === "accepted" && (
            <>
              <dt>{strings.acceptedSteps}</dt>
              <dd>{p.accepted_steps.join(", ")}</dd>
            </>
          )}
          {p.reason && (
            <>
              <dt>{strings.reason}</dt>
              <dd className="untrusted">{p.reason}</dd>
            </>
          )}
        </dl>
        {p.note && (
          <figure className="note">
            <figcaption>{strings.noteFrom(p.proposer)}</figcaption>
            <blockquote className="untrusted">{p.note}</blockquote>
          </figure>
        )}
        {outcome && (
          <p className="ok-text" role="status">
            {outcome}
          </p>
        )}
      </Panel>

      <Panel title={strings.steps} id="pane-proposal-steps">
        {open && <p className="help">{strings.stepsHelp}</p>}
        <table className="grid compact">
          <thead>
            <tr>
              {open && <th>{strings.colAccept}</th>}
              <th className="num">#</th>
              <th>{strings.colOperation}</th>
              <th>{strings.colDependsOn}</th>
              <th>{strings.colArguments}</th>
            </tr>
          </thead>
          <tbody>
            {p.steps.map((s) => {
              const args = detail?.steps[s.index]?.args;
              const shown = args === undefined ? null : argsText(args);
              const id = `step-${p.id}-${s.index}`;
              return (
                <tr key={s.index}>
                  {open && (
                    <td>
                      <input
                        id={id}
                        type="checkbox"
                        checked={chosen.includes(s.index)}
                        aria-label={strings.acceptStep(s.index)}
                        onChange={(e) =>
                          setChosen(
                            e.target.checked
                              ? withDependencies(p.steps, chosen, s.index)
                              : withoutDependents(p.steps, chosen, s.index),
                          )
                        }
                      />
                    </td>
                  )}
                  <td className="num">{s.index}</td>
                  <td>
                    <code>{s.operation}</code>
                  </td>
                  <td>{s.depends_on.length === 0 ? strings.none : s.depends_on.join(", ")}</td>
                  <td>
                    {shown === null ? (
                      <span className="muted">{strings.loading}</span>
                    ) : (
                      <details>
                        <summary>{strings.showArguments}</summary>
                        <pre className="args untrusted">{shown.text}</pre>
                        {shown.cut > 0 && <p className="muted">{strings.argsCut(shown.cut)}</p>}
                      </details>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>

      {p.status === "pending" && (
        <Panel title={strings.decision} id="pane-proposal-decision">
          {open && blocker === null && (
            <div aria-live="polite">
              <h3>{strings.wouldChange(chosen.length, p.steps.length)}</h3>
              {!checked ? (
                <p className="muted">{strings.checking}</p>
              ) : dry.error ? (
                <div className="row">
                  <p className="warn-text" role="alert">
                    <strong>{dry.error.code}</strong>: {dry.error.message}
                    {dry.error.hint && <span className="help"> {dry.error.hint}</span>}
                  </p>
                  <button type="button" className="quiet" onClick={() => setAttempt((n) => n + 1)}>
                    {strings.checkAgain}
                  </button>
                </div>
              ) : (
                dry.report && (
                  <Changes
                    report={dry.report}
                    labels={labels}
                    revision={revision}
                    operations={chosen.map((i) => p.steps[i]?.operation ?? "")}
                  />
                )
              )}
            </div>
          )}
          {blocker !== null && blocker !== "none-chosen" && <p className="warn-text">{strings.acceptBlocked[blocker]}</p>}
          <div className="row">
            <button
              type="button"
              className="primary"
              disabled={blocker !== null || !checked || wouldFail || dry?.workspace === null || state.busy !== null}
              onClick={() => void accept()}
            >
              {strings.acceptButton(chosen.length, p.steps.length)}
            </button>
            {blocker === "none-chosen" && <span className="muted">{strings.acceptBlocked["none-chosen"]}</span>}
          </div>
          {!expired(p, now) && (
            <div className="row">
              <label htmlFor={`reason-${p.id}`}>{strings.rejectReason}</label>
              <input
                id={`reason-${p.id}`}
                value={reason}
                maxLength={2000}
                onChange={(e) => setReason(e.target.value)}
              />
              <button type="button" disabled={state.busy !== null} onClick={() => void reject()}>
                {strings.rejectButton}
              </button>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

function Changes({
  report,
  labels,
  revision,
  operations,
}: {
  report: DryRunReport;
  labels: Record<string, string>;
  revision: number;
  operations: string[];
}) {
  const lines = changeLines(report, labels, operations);
  return (
    <>
      <ul className="changes">
        {lines.map((line, i) => (
          <li key={i}>{describe(line)}</li>
        ))}
      </ul>
      <p className="muted">{strings.wouldRevision(revision, report.would_revisions.science)}</p>
    </>
  );
}

function describe(line: ChangeLine): string {
  switch (line.kind) {
    case "opened":
    case "name":
    case "geometry":
    case "model":
    case "nothing":
      return strings.change[line.kind];
    case "selection":
      return strings.changeSelection(line.names);
    case "jobs":
      return strings.changeJobs(line.count);
    case "spins":
    case "couplings":
      return strings.changeIds(line.kind, line.change, line.count, line.names, line.truncated);
  }
}
