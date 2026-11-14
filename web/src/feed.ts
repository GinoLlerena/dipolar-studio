// The change feed, client side (D14; M3 step 1). api.ts streams the text of GET /api/v1/events;
// this module splits it into lines, parses each into the contract's FeedItem, and says which
// parts of the page to read again. Feed lines carry revisions, never arguments or labels, so
// the page always re-reads through registry operations. No network access here, no runtime
// imports: tests/feed.test.ts runs it under Node.

import type { FeedItem } from "./generated/contract";

/** The longest line accepted; the server's lines are a few hundred bytes. */
export const MAX_LINE = 1 << 20;

/** Splits decoded stream text into complete lines and keeps the unfinished tail. */
export class LineBuffer {
  private tail = "";

  push(chunk: string): string[] {
    const parts = (this.tail + chunk).split("\n");
    this.tail = parts.pop() ?? "";
    if (this.tail.length > MAX_LINE) throw new Error("event stream line too long");
    return parts.filter((line) => line.trim() !== "");
  }
}

const KINDS = new Set(["hello", "commit", "job", "ping", "resync"]);

/** One feed line, or null when it is not a feed item this client understands. */
export function parseFeedLine(line: string): FeedItem | null {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const { kind, cursor } = value as { kind?: unknown; cursor?: unknown };
  if (typeof kind !== "string" || !KINDS.has(kind) || !Number.isSafeInteger(cursor)) return null;
  return value as FeedItem;
}

/** What the page shows, each read by one registry query. */
export type Resource = "view" | "project" | "history" | "runs" | "jobs" | "scene" | "proposals";
export const RESOURCES: readonly Resource[] = ["view", "project", "history", "runs", "jobs", "scene", "proposals"];

const BY_DOMAIN: Record<"science" | "workspace" | "proposal" | "job", readonly Resource[]> = {
  // A science change alters the project and its history, and makes runs, jobs and pending
  // proposals stale.
  science: ["project", "history", "view", "runs", "jobs", "scene", "proposals"],
  // The camera, layers, selection and highlights: the view and the Structure view's scene.
  workspace: ["view", "scene"],
  // A finished job adds a run, which the view describes and whose residuals the scene shows.
  job: ["jobs", "runs", "view", "scene"],
  // A proposal was created or decided (the inbox, M3 step 3).
  proposal: ["proposals"],
};

/** The resources to read again after a feed line. `hello` (every connection, including a
 * reconnection) and `resync` read everything: entries may have been missed. */
export function refreshFor(item: FeedItem): Resource[] {
  switch (item.kind) {
    case "hello":
    case "resync":
      return [...RESOURCES];
    case "ping":
      return [];
    case "job":
      return ["jobs"];
    case "commit": {
      const wanted = new Set(item.domains.flatMap((domain) => BY_DOMAIN[domain]));
      return RESOURCES.filter((r) => wanted.has(r));
    }
  }
}

/** Reconnection delay after `failures` consecutive failed attempts: 0.5 s doubling to 10 s. */
export function backoffMs(failures: number): number {
  return Math.min(500 * 2 ** Math.max(failures - 1, 0), 10_000);
}

/** The newest revisions seen in any response or feed line (round 39). A response describing an
 * older science revision — or, for the view, an older workspace revision — arrived late: the
 * caller drops it and reads again, so a run list from before a commit never clears a stale badge
 * that a newer view already shows. */
export class RevisionMark {
  science = 0;
  workspace = 0;

  /** Records revisions announced elsewhere (a feed line). */
  observe(science: number, workspace?: number): void {
    this.science = Math.max(this.science, science);
    if (workspace !== undefined) this.workspace = Math.max(this.workspace, workspace);
  }

  /** True when a response is not older than what was seen; it then raises the mark. */
  accept(science: number, workspace?: number): boolean {
    if (science < this.science) return false;
    if (workspace !== undefined && workspace < this.workspace) return false;
    this.observe(science, workspace);
    return true;
  }
}
