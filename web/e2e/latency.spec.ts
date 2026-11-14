// The two latency targets (03 §"Live-preview contract", 04 §7 "Perception", §8.6):
// - live preview: p95 under 100 ms from a gesture to fresh residuals, on the beta fixture, warm;
// - perception: a robot-issued view.highlight is shown in the browser within 200 ms.
//
// Both are measured in every run. The targets are met on *named hardware*: run with
// DIPOLAR_RECORD_LATENCY=1 to check them strictly and record the samples, with the machine and
// browser, in docs/validation/data/m3-latency/<browser>.json. Without it (CI's shared runners) a
// looser bound only guards against regressions.

import { mkdirSync, writeFileSync } from "node:fs";
import { cpus, platform, release, totalmem } from "node:os";
import { join, resolve } from "node:path";
import type { TestInfo } from "@playwright/test";
import { expect, openExample, test } from "./harness";

const RECORD = process.env.DIPOLAR_RECORD_LATENCY === "1";
const PREVIEW_P95_MS = RECORD ? 100 : 400;
const PERCEPTION_MAX_MS = RECORD ? 200 : 800;
const OUT = resolve(import.meta.dirname, "../../docs/validation/data/m3-latency");

function percentile(samples: number[], q: number): number {
  const sorted = [...samples].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)] ?? Number.NaN;
}

const tenth = (ms: number) => Math.round(ms * 10) / 10;

function record(info: TestInfo, version: string, name: string, samples: number[], extra: object): void {
  const summary = {
    p50_ms: tenth(percentile(samples, 0.5)),
    p95_ms: tenth(percentile(samples, 0.95)),
    max_ms: tenth(Math.max(...samples)),
    n: samples.length,
  };
  info.annotations.push({ type: name, description: JSON.stringify(summary) });
  if (!RECORD) return;
  mkdirSync(OUT, { recursive: true });
  const file = join(OUT, `${info.project.name}-${name}.json`);
  const machine = { cpu: cpus()[0]?.model ?? "unknown", cores: cpus().length, memory_gib: totalmem() / 2 ** 30, os: `${platform()} ${release()}` };
  writeFileSync(
    file,
    `${JSON.stringify({ measurement: name, browser: info.project.name, browser_version: version, machine, ...extra, ...summary, samples_ms: samples.map(tenth) }, null, 2)}\n`,
  );
}

test("live preview: p95 from a slider gesture to fresh residuals", async ({ app, server, browser }, info) => {
  await openExample(server);
  await app.getByRole("tab", { name: "Fit" }).click();
  await expect(app.locator(".meta")).toContainText("φ = "); // started (warm: the first preview is done)
  const rows = (await server.ok("robot", "project.describe")).couplings.length as number;
  const samples = await app.evaluate(
    async ({ count, rows }) => {
      const slider = document.getElementById("phi-slider") as HTMLInputElement;
      const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set as (v: string) => void;
      // Fresh = the preview line and the preview's residual table both show the new φ, the table
      // with every coupling's row (round 49: the line alone could certify a stale or empty table).
      const fresh = (value: number, want: string) => {
        const meta = document.querySelector("#pane-preview")?.closest("section")?.querySelector(".meta");
        const table = document.querySelector("#pane-preview-residuals")?.closest("section")?.querySelector("table[data-phi]");
        return (
          (meta?.textContent ?? "").includes(want) &&
          table !== null &&
          table !== undefined &&
          Math.abs(Number(table.getAttribute("data-phi")) - value) < 1e-9 &&
          table.querySelectorAll("tbody tr").length === rows
        );
      };
      const out: number[] = [];
      for (let i = 0; i < count; i++) {
        const value = Number((30 + (i % 50) * 0.3 + (i % 2) * 0.1).toFixed(1)); // a new position every time
        const want = `φ = ${value.toFixed(2)}°`;
        const done = new Promise<number>((resolve) => {
          const observer = new MutationObserver(() => {
            if (fresh(value, want)) {
              observer.disconnect();
              resolve(performance.now());
            }
          });
          observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
        });
        const start = performance.now();
        setValue.call(slider, value.toFixed(1));
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        out.push((await done) - start);
        await new Promise((r) => setTimeout(r, 120)); // about 8 gestures a second
      }
      return out;
    },
    { count: 60, rows },
  );
  record(info, browser.version(), "preview", samples, { fixture: "biphenyl-synthetic", gesture: "slider input event to the preview line and the residual table (every row) rendered at the new φ" });
  expect(percentile(samples, 0.95)).toBeLessThan(PREVIEW_P95_MS);
});

test("perception: a robot's highlight reaches the browser", async ({ app, server, browser }, info) => {
  await openExample(server);
  await app.getByRole("tab", { name: "Structure" }).click();
  await expect(app.locator("path.arc")).not.toHaveCount(0); // the scene is drawn
  const samples: number[] = [];
  for (let i = 0; i < 20; i++) {
    const id = `cpl_00000${(i % 9) + 1}`;
    // Watch in the page; report the page's wall-clock time of the change.
    const shown = app.evaluate(
      (target) =>
        new Promise<number>((resolve) => {
          const done = () => document.querySelector(`path.arc.is-highlighted[data-id="${target}"]`) !== null;
          const observer = new MutationObserver(() => {
            if (done()) {
              observer.disconnect();
              resolve(Date.now());
            }
          });
          observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class"], childList: true });
        }),
      id,
    );
    await app.waitForTimeout(50); // the observer is attached
    const sent = Date.now();
    await server.ok("robot", "view.highlight", { ids: [id] });
    samples.push((await shown) - sent);
    await app.waitForTimeout(100);
  }
  record(info, browser.version(), "perception", samples, { fixture: "biphenyl-synthetic", from: "the robot sends view.highlight", to: "the arc is drawn highlighted" });
  expect(Math.max(...samples)).toBeLessThan(PERCEPTION_MAX_MS);
});
