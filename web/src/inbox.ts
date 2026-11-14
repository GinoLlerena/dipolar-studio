// The proposal inbox's logic (M3 step 3). Pure functions with type-only imports, so
// tests/inbox.test.ts runs them under Node.
//
// An agent (a propose-tier caller) cannot change the science; it submits a proposal: ordered
// steps, made against one science revision. A human accepts the whole proposal or a
// dependency-closed subset of its steps, or rejects it (dipolar_app.proposal_ops). The server
// decides everything; the page only shows what it said, what a dry run of the acceptance would
// change, and why a button is disabled. The proposer's note and the steps' arguments are data
// written by the proposer: they are shown as text, never interpreted.

import type { DryRunReport, IdChanges, JobOut, ProposalOut, StepOut } from "./generated/contract";

/** Pending proposals first, oldest first (the order they wait in); then the decided ones, the
 * most recent decision first. */
export function ordered(proposals: readonly ProposalOut[], now: number): ProposalOut[] {
  const open = proposals.filter((p) => decidable(p, now));
  const closed = proposals.filter((p) => !decidable(p, now));
  const time = (iso: string | null) => (iso === null ? 0 : Date.parse(iso));
  open.sort((a, b) => time(a.created_at) - time(b.created_at) || a.id.localeCompare(b.id));
  closed.sort(
    (a, b) => time(b.decided_at ?? b.expires_at) - time(a.decided_at ?? a.expires_at) || b.id.localeCompare(a.id),
  );
  return [...open, ...closed];
}

/** Past its expiry by this page's clock. The server decides with its own; the page only stops
 * offering a decision it would refuse. */
export function expired(p: ProposalOut, now: number): boolean {
  return p.status === "expired" || (p.status === "pending" && Date.parse(p.expires_at) <= now);
}

/** Still waiting for a decision. */
export function decidable(p: ProposalOut, now: number): boolean {
  return p.status === "pending" && !expired(p, now);
}

/** The number of proposals waiting for a decision (the tab's badge). */
export function waiting(proposals: readonly ProposalOut[], now: number): number {
  return proposals.filter((p) => decidable(p, now)).length;
}

export type Blocker = "closed" | "expired" | "stale" | "none-chosen";

/** Why the proposal cannot be accepted now, or null. `revision` is the newest science revision
 * the page has seen: a proposal made at an older one is stale even before the list is re-read.
 * A stale proposal can still be rejected. */
export function acceptBlocker(p: ProposalOut, chosen: readonly number[], revision: number, now: number): Blocker | null {
  if (expired(p, now)) return "expired";
  if (p.status !== "pending") return "closed";
  if (p.stale || p.base_science_revision !== revision) return "stale";
  if (chosen.length === 0) return "none-chosen";
  return null;
}

/** `chosen` with step `index` and every step it depends on, transitively. */
export function withDependencies(steps: readonly StepOut[], chosen: readonly number[], index: number): number[] {
  const out = new Set(chosen);
  const seen = new Set<number>();
  const todo = [index];
  for (let i = todo.pop(); i !== undefined; i = todo.pop()) {
    if (seen.has(i)) continue;
    seen.add(i);
    out.add(i);
    todo.push(...(steps[i]?.depends_on ?? []));
  }
  return [...out].sort((a, b) => a - b);
}

/** `chosen` without step `index` and every step that depends on it, transitively, so what is
 * left stays dependency-closed. */
export function withoutDependents(steps: readonly StepOut[], chosen: readonly number[], index: number): number[] {
  const out = new Set(chosen);
  const todo = [index];
  for (let i = todo.pop(); i !== undefined; i = todo.pop()) {
    out.delete(i);
    for (const s of steps) if (out.has(s.index) && s.depends_on.includes(i)) todo.push(s.index);
  }
  return [...out].sort((a, b) => a - b);
}

/** True when every chosen step's dependencies are chosen too (what the server requires). */
export function closed(steps: readonly StepOut[], chosen: readonly number[]): boolean {
  const set = new Set(chosen);
  return chosen.every((i) => (steps[i]?.depends_on ?? []).every((d) => set.has(d)));
}

/** All the steps (the default choice). */
export function allSteps(steps: readonly StepOut[]): number[] {
  return steps.map((s) => s.index);
}

/** The longest argument text shown before it is cut (a couplings CSV can be megabytes). */
export const MAX_ARGS_TEXT = 4000;

/** A step's arguments as indented JSON, cut at `max` characters. */
export function argsText(args: unknown, max = MAX_ARGS_TEXT): { text: string; cut: number } {
  const text = JSON.stringify(args, null, 2) ?? "";
  return text.length <= max ? { text, cut: 0 } : { text: text.slice(0, max), cut: text.length - max };
}

/** IDs named by their labels where the page knows them (an added coupling has no label yet). */
export function labelled(ids: readonly string[], labels: Readonly<Record<string, string>>): string[] {
  return ids.map((id) => (Object.hasOwn(labels, id) ? `${labels[id]} (${id})` : id));
}

export type ChangeLine =
  | { kind: "opened" | "name" | "geometry" | "model" }
  | { kind: "spins" | "couplings"; change: "added" | "removed" | "changed"; count: number; names: string[]; truncated: boolean }
  | { kind: "selection"; names: string[] }
  | { kind: "jobs"; count: number }
  | { kind: "nothing" };

/** What a dry run of the acceptance says would change, as lines for the page. A dry run reports
 * the science and the view, not jobs, so the fit jobs the chosen steps would start are counted
 * from their operations (`operations`: the chosen steps' operations). */
export function changeLines(
  report: DryRunReport,
  labels: Readonly<Record<string, string>>,
  operations: readonly string[] = [],
): ChangeLine[] {
  const lines: ChangeLine[] = [];
  const science = report.science;
  if (science) {
    if (science.project_opened) lines.push({ kind: "opened" });
    else {
      if (science.name_changed) lines.push({ kind: "name" });
      if (science.geometry_changed) lines.push({ kind: "geometry" });
      if (science.model_changed) lines.push({ kind: "model" });
    }
    for (const kind of ["couplings", "spins"] as const) {
      const ids: IdChanges = science[kind];
      for (const change of ["added", "removed", "changed"] as const) {
        const count = ids[`n_${change}`];
        if (count > 0) lines.push({ kind, change, count, names: labelled(ids[change], labels), truncated: ids.truncated });
      }
    }
  }
  if (report.selection_after !== null) lines.push({ kind: "selection", names: labelled(report.selection_after, labels) });
  const jobs = operations.filter((o) => o === "fit.run").length;
  if (jobs > 0) lines.push({ kind: "jobs", count: jobs });
  if (lines.length === 0) lines.push({ kind: "nothing" });
  return lines;
}

/** The queued and running jobs, as a signature: an acceptance that starts a fit depends on the
 * caller's job quota, which changes with no revision when a job ends or is cancelled (round 48). */
export function activeJobs(jobs: readonly JobOut[]): string {
  return jobs
    .filter((j) => j.status === "queued" || j.status === "running")
    .map((j) => j.id)
    .sort()
    .join(",");
}

/** Everything a dry run of an acceptance depends on. When any of it changes, the shown dry run no
 * longer describes what Accept would do, so it is run again. `attempt` is the user's "check
 * again". */
export function dryRunKey(o: {
  proposal: ProposalOut;
  chosen: readonly number[];
  science: number;
  workspace: number;
  jobs: string;
  attempt: number;
}): string {
  const p = o.proposal;
  return [p.id, o.chosen.join(","), o.science, o.workspace, p.status, p.stale, o.jobs, o.attempt].join("|");
}
