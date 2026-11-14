// The browser suite's harness (M3 step 4). Each test gets its own `dipolar serve` on a fresh
// project directory, with the built page (web/dist), and these helpers:
// - `server.call` / `server.ok`: registry calls over HTTP as the robot, the agent or the user, as
//   another client would make them (the page sees their effects through the change feed);
// - `server.launchUrl()`: a single-use launch link, as `dipolar open` makes;
// - the `app` fixture: a page signed in through that link, with the feed live.

import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test as base, expect, type Page } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "../..");
const DIST = join(ROOT, "web", "dist");

type Ready = { base_url: string; instance_id: string; tokens: Record<"user" | "robot" | "viewer" | "agent", string> };
export type Who = keyof Ready["tokens"];
export type Envelope = { ok: true; result: any; revisions: { science: number; workspace: number }; dry_run: any } | {
  ok: false;
  error: { code: string; message: string; offending_field: string | null };
};

export class Server {
  readonly dir: string;
  readonly ready: Ready;
  private readonly process: ChildProcess;

  constructor(dir: string, ready: Ready, process: ChildProcess) {
    this.dir = dir;
    this.ready = ready;
    this.process = process;
  }

  get base(): string {
    return this.ready.base_url;
  }

  /** One registry call over HTTP. */
  async call(who: Who, operation: string, args: object = {}, options: object = {}): Promise<Envelope> {
    const response = await fetch(`${this.base}/api/v1/ops/${operation}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.ready.tokens[who]}` },
      body: JSON.stringify({ args, ...options }),
    });
    return (await response.json()) as Envelope;
  }

  /** A call that must succeed; its result. */
  async ok(who: Who, operation: string, args: object = {}): Promise<any> {
    const envelope = await this.call(who, operation, args);
    if (!envelope.ok) throw new Error(`${operation}: ${JSON.stringify(envelope.error)}`);
    return envelope.result;
  }

  /** The current science revision. */
  async revision(): Promise<number> {
    return (await this.ok("robot", "render.describe_view")).science_revision as number;
  }

  /** A single-use launch link for a browser tab (as `dipolar open --print-url`). */
  async launchUrl(): Promise<string> {
    const response = await fetch(`${this.base}/api/v1/auth/launch-code`, {
      method: "POST",
      headers: { Authorization: `Bearer ${this.ready.tokens.user}` },
    });
    const { code } = (await response.json()) as { code: string };
    return `${this.base}/#launch=${code}`;
  }

  async stop(): Promise<void> {
    if (this.process.exitCode === null) {
      const exited = new Promise((done) => this.process.once("exit", done));
      this.process.kill("SIGTERM");
      await Promise.race([exited, new Promise((done) => setTimeout(done, 5000))]);
      if (this.process.exitCode === null) this.process.kill("SIGKILL");
    }
    rmSync(this.dir, { recursive: true, force: true });
  }
}

export async function startServer(): Promise<Server> {
  if (!existsSync(join(DIST, "index.html"))) throw new Error("build the page first: pnpm run build");
  const dir = mkdtempSync(join(tmpdir(), "dipolar-e2e-"));
  const readyFile = join(dir, "ready.json");
  const child = spawn(
    "uv",
    ["run", "--no-sync", "dipolar", "serve", "--project-dir", dir, "--ready-file", readyFile, "--static-dir", DIST],
    { cwd: ROOT, stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk) => {
    stderr = (stderr + String(chunk)).slice(-4000);
  });
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`dipolar serve exited (${child.exitCode}): ${stderr}`);
    if (existsSync(readyFile)) {
      try {
        return new Server(dir, JSON.parse(readFileSync(readyFile, "utf-8")) as Ready, child);
      } catch {
        // written but not complete yet
      }
    }
    await new Promise((done) => setTimeout(done, 100));
  }
  child.kill("SIGKILL");
  throw new Error(`dipolar serve did not start: ${stderr}`);
}

/** Opens the page through a fresh launch link and waits for the change feed. */
export async function signIn(page: Page, server: Server): Promise<void> {
  await page.goto(await server.launchUrl());
  await expect(page.locator(".conn-live")).toBeVisible();
}

export const test = base.extend<{ server: Server; app: Page }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature
  server: async ({}, use) => {
    const server = await startServer();
    try {
      await use(server);
    } finally {
      await server.stop();
    }
  },
  app: async ({ page, server }, use) => {
    await signIn(page, server);
    await use(page);
  },
});

export { expect };

/** The example project, opened by another client (the robot). */
export async function openExample(server: Server): Promise<void> {
  await server.ok("robot", "project.open_example", { name: "biphenyl-synthetic", expected_science_revision: 0 });
}
