// The page's state: what the registry says, kept current by the change feed (M3 step 1).
//
// - Every value shown comes from a registry query (D13): describe_view, project.describe,
//   history.log, run.list and job.list. The feed only says which of them to read again.
// - Reads are coalesced per resource: at most one is in flight, and a request that arrives
//   meanwhile runs once more afterwards. So a response is never older than one shown before it
//   (D11 late-response rule) and a burst of commits costs two reads, not one per commit.
// - A command's result is not applied directly: its commit comes back on the feed, and the
//   command also asks for the reads its effect implies, so the page updates without the feed too.

import {
  callOperation,
  type DescribeProjectOut,
  type DescribeViewOut,
  type Envelope,
  type ErrorBody,
  type FitRunOut,
  type JobOut,
  type LogOut,
  type OperationName,
  type OperationOutput,
  type RunOut,
  streamEvents,
} from "./api";
import { OPERATIONS } from "./generated/contract";
import { backoffMs, LineBuffer, parseFeedLine, type Resource, RevisionMark, refreshFor } from "./feed";

export type Connection = "connecting" | "live" | "reconnecting" | "needs-launch";

export interface StudioState {
  connection: Connection;
  view: DescribeViewOut | null;
  /** null while unknown or when no project is open (`view.project_open` tells which). */
  project: DescribeProjectOut | null;
  history: LogOut | null;
  runs: RunOut[];
  jobs: JobOut[];
  /** Fit results by run ID. A run's result is immutable (stored by content hash). */
  results: Readonly<Record<string, FitRunOut>>;
  /** Runs whose result could not be read; retried on every (re)connection or on request. */
  failedResults: Readonly<Record<string, ErrorBody | null>>;
  error: ErrorBody | null;
  /** The operation a button started and that has not answered yet. */
  busy: OperationName | null;
}

/** Without a byte for this long (the server pings every 15 s), the stream is reopened. */
const WATCHDOG_MS = 40_000;

/** A read answered with an older revision is repeated at most this often in a row. */
const MAX_LATE_RETRIES = 5;

/** What a command's effect makes worth reading again, before its commit arrives on the feed. */
function readsAfter(name: OperationName): Resource[] {
  switch (OPERATIONS[name].effect) {
    case "model":
      return ["project", "history", "view", "runs", "jobs"];
    case "view":
      return ["view"];
    case "compute":
      return ["jobs", "runs", "view"];
    default:
      return [];
  }
}

export class Studio {
  private state: StudioState = {
    connection: "connecting",
    view: null,
    project: null,
    history: null,
    runs: [],
    jobs: [],
    results: {},
    failedResults: {},
    error: null,
    busy: null,
  };
  private readonly listeners = new Set<() => void>();
  private readonly reads = new Map<Resource, { running: boolean; again: boolean }>();
  private readonly fetchingRuns = new Set<string>();
  private feed: AbortController | null = null;
  /** Late responses are dropped and read again (feed.ts RevisionMark, round 39). */
  private readonly seen = new RevisionMark();

  constructor(
    private readonly token: string,
    private readonly onLostSession: (error: ErrorBody) => void,
  ) {}

  // ------------------------------------------------------------------ store protocol (React)
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): StudioState => this.state;

  private set(patch: Partial<StudioState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }

  /** Opens the change feed; every (re)connection reads everything. */
  start(): void {
    if (this.feed) return;
    this.feed = new AbortController();
    void this.follow(this.feed.signal);
  }

  stop(): void {
    this.feed?.abort();
    this.feed = null;
  }

  dismissError(): void {
    this.set({ error: null });
  }

  // ------------------------------------------------------------------ calls
  /** One registry call with this tab's token. Errors are shown, except the codes in `quiet`;
   * UNAUTHENTICATED ends the tab's session (a new launch link is needed). */
  async run<N extends OperationName>(
    call: (token: string) => Promise<Envelope<N>>,
    quiet: readonly string[] = [],
  ): Promise<OperationOutput<N> | null> {
    let envelope: Envelope<N>;
    try {
      envelope = await call(this.token);
    } catch {
      this.set({
        error: {
          code: "INTERNAL",
          message: "could not reach dipolar serve",
          offending_field: null,
          hint: "check that dipolar serve is still running",
          details: {},
        },
      });
      return null;
    }
    if (envelope.ok) return envelope.result;
    if (envelope.error.code === "UNAUTHENTICATED") {
      this.stop();
      this.set({ connection: "needs-launch", error: envelope.error });
      this.onLostSession(envelope.error);
    } else if (!quiet.includes(envelope.error.code)) {
      this.set({ error: envelope.error });
    }
    return null;
  }

  /** A command started by the user: marks it busy, clears the last error on success and reads
   * what its effect changed. */
  async command<N extends OperationName>(
    name: N,
    call: (token: string) => Promise<Envelope<N>>,
  ): Promise<OperationOutput<N> | null> {
    this.set({ busy: name });
    try {
      const result = await this.run(call);
      if (result !== null) {
        this.set({ error: null });
        this.refresh(readsAfter(name));
      }
      return result;
    } finally {
      this.set({ busy: null });
    }
  }

  /** Reads the given resources again (coalesced, see the module comment). */
  refresh(resources: readonly Resource[]): void {
    for (const resource of resources) void this.read(resource);
  }

  private async read(resource: Resource): Promise<void> {
    const slot = this.reads.get(resource) ?? { running: false, again: false };
    this.reads.set(resource, slot);
    if (slot.running) {
      slot.again = true;
      return;
    }
    slot.running = true;
    try {
      let late = 0;
      do {
        slot.again = false;
        if (!(await this.readOnce(resource)) && late++ < MAX_LATE_RETRIES) slot.again = true;
      } while (slot.again && this.state.connection !== "needs-launch");
    } finally {
      slot.running = false;
    }
  }

  /** One read. False when the response was late (older than state already seen) and dropped. */
  private async readOnce(resource: Resource): Promise<boolean> {
    switch (resource) {
      case "view": {
        const view = await this.run((t) => callOperation("render.describe_view", {}, t));
        if (!view) return true;
        if (!this.seen.accept(view.science_revision, view.workspace_revision)) return false;
        this.set({ view });
        return true;
      }
      case "project": {
        let noProject = false;
        const project = await this.run(async (t) => {
          const envelope = await callOperation("project.describe", {}, t);
          noProject = !envelope.ok && envelope.error.code === "NO_PROJECT";
          return envelope;
        }, ["NO_PROJECT"]);
        if (project && !this.seen.accept(project.science_revision)) return false;
        if (project || noProject) this.set({ project }); // any other failure keeps what is shown
        return true;
      }
      case "history": {
        const history = await this.run((t) => callOperation("history.log", {}, t));
        if (!history) return true;
        if (!this.seen.accept(history.science_revision)) return false;
        this.set({ history });
        return true;
      }
      case "runs": {
        const listed = await this.run((t) => callOperation("run.list", {}, t));
        if (!listed) return true;
        if (!this.seen.accept(listed.science_revision)) return false;
        this.set({ runs: listed.runs });
        return true;
      }
      case "jobs": {
        const listed = await this.run((t) => callOperation("job.list", {}, t));
        if (!listed) return true;
        if (!this.seen.accept(listed.science_revision)) return false;
        this.set({ jobs: listed.jobs });
        return true;
      }
    }
  }

  /** Fetches a run's result once; it never changes, so it is kept. A failed read is recorded
   * (the page says so instead of "loading" forever) and retried on reconnection or on request. */
  async loadResult(runId: string, retry = false): Promise<void> {
    if (this.state.results[runId] || this.fetchingRuns.has(runId)) return;
    if (runId in this.state.failedResults && !retry) return;
    this.fetchingRuns.add(runId);
    let failure: ErrorBody | null = null;
    try {
      const got = await this.run(async (t) => {
        const envelope = await callOperation("run.get", { run_id: runId }, t);
        if (!envelope.ok) failure = envelope.error;
        return envelope;
      });
      const { [runId]: _, ...failed } = this.state.failedResults;
      if (got) this.set({ results: { ...this.state.results, [runId]: got.result }, failedResults: failed });
      else this.set({ failedResults: { ...failed, [runId]: failure } });
    } finally {
      this.fetchingRuns.delete(runId);
    }
  }

  // ------------------------------------------------------------------ the change feed
  private async follow(signal: AbortSignal): Promise<void> {
    let cursor: number | null = null;
    let failures = 0;
    while (!signal.aborted) {
      const attempt = new AbortController();
      const abortAttempt = () => attempt.abort();
      signal.addEventListener("abort", abortAttempt);
      let watchdog = window.setTimeout(abortAttempt, WATCHDOG_MS);
      const lines = new LineBuffer();
      const end = await streamEvents(
        this.token,
        cursor,
        (text) => {
          window.clearTimeout(watchdog);
          watchdog = window.setTimeout(abortAttempt, WATCHDOG_MS);
          for (const line of lines.push(text)) {
            const item = parseFeedLine(line);
            if (item === null) continue;
            if (item.kind === "hello") {
              failures = 0;
              this.set({ connection: "live" });
              for (const runId of Object.keys(this.state.failedResults)) void this.loadResult(runId, true);
            }
            if (item.kind === "hello" || item.kind === "commit") {
              this.seen.observe(item.revisions.science, item.revisions.workspace);
            }
            cursor = item.cursor;
            this.refresh(refreshFor(item));
          }
        },
        attempt.signal,
      );
      window.clearTimeout(watchdog);
      signal.removeEventListener("abort", abortAttempt);
      if (signal.aborted) return;
      if (end.reason === "refused" && end.error?.code === "UNAUTHENTICATED") {
        this.stop();
        this.set({ connection: "needs-launch", error: end.error });
        this.onLostSession(end.error);
        return;
      }
      failures += 1;
      this.set({ connection: "reconnecting" });
      // Wait before reconnecting; the abort listener is removed either way (round 39: one
      // listener per reconnection used to stay attached for the store's lifetime).
      await new Promise<void>((resolve) => {
        const done = () => {
          window.clearTimeout(timer);
          signal.removeEventListener("abort", done);
          resolve();
        };
        const timer = window.setTimeout(done, backoffMs(failures));
        signal.addEventListener("abort", done, { once: true });
      });
    }
  }
}
