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
export type Resource = "view" | "project" | "history" | "runs" | "jobs";
export const RESOURCES: readonly Resource[] = ["view", "project", "history", "runs", "jobs"];

const BY_DOMAIN: Record<"science" | "workspace" | "proposal" | "job", readonly Resource[]> = {
  // A science change alters the project and its history, and makes runs and jobs stale.
  science: ["project", "history", "view", "runs", "jobs"],
  workspace: ["view"],
  // A finished job adds a run, which the view describes.
  job: ["jobs", "runs", "view"],
  // The beta page has no proposal inbox yet (a later M3 step).
  proposal: [],
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
