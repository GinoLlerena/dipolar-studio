// The store's behaviour that needs a browser (round 39, fixes 3 and 4 of M3 step 1).
import type { Page } from "@playwright/test";
import { expect, openExample, openTab, type Server, test } from "./harness";

/** Counts the live "abort" listeners on AbortSignals that have not aborted (round 39, fix 3: each
 * reconnection used to leave one on the store's lifetime signal). Installed before the page runs. */
const COUNT_ABORT_LISTENERS = () => {
  const live = new Map<AbortSignal, Set<unknown>>();
  const add = AbortSignal.prototype.addEventListener;
  const remove = AbortSignal.prototype.removeEventListener;
  AbortSignal.prototype.addEventListener = function (this: AbortSignal, type: string, listener: unknown, options?: unknown) {
    if (type === "abort" && listener) {
      let set = live.get(this);
      if (!set) {
        set = new Set();
        live.set(this, set);
        add.call(this, "abort", () => live.delete(this), { once: true });
      }
      set.add(listener);
    }
    return add.call(this, type, listener as EventListener, options as AddEventListenerOptions);
  } as typeof AbortSignal.prototype.addEventListener;
  AbortSignal.prototype.removeEventListener = function (this: AbortSignal, type: string, listener: unknown, options?: unknown) {
    if (type === "abort") live.get(this)?.delete(listener);
    return remove.call(this, type, listener as EventListener, options as EventListenerOptions);
  } as typeof AbortSignal.prototype.removeEventListener;
  (window as unknown as { abortListeners: () => number }).abortListeners = () =>
    [...live.entries()].filter(([signal]) => !signal.aborted).reduce((n, [, set]) => n + set.size, 0);
};

async function listenersAfter(page: Page, server: Server, failures: number): Promise<number> {
  await page.addInitScript(COUNT_ABORT_LISTENERS);
  let left = failures;
  await page.route("**/api/v1/events*", (route) => (left-- > 0 ? route.abort() : route.continue()));
  await page.goto(await server.launchUrl());
  await expect(page.locator(".conn-live")).toBeVisible({ timeout: 30_000 });
  expect(left).toBeLessThan(0); // every forced failure happened, then a connection
  return page.evaluate(() => (window as unknown as { abortListeners: () => number }).abortListeners());
}

test("reconnections leave no abort listener behind (round 39, fix 3)", async ({ browser, server }) => {
  const steady = await listenersAfter(await browser.newPage(), server, 0);
  const reconnected = await listenersAfter(await browser.newPage(), server, 3); // backs off 0.5, 1, 2 s
  expect(reconnected).toBe(steady);
});

test("a result that could not be read says so, and Retry reads it (round 39, fix 4)", async ({ app, server }) => {
  await openExample(server);
  let fail = true;
  await app.route("**/api/v1/ops/run.get", (route) =>
    fail
      ? route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            ok: false,
            operation: "run.get",
            error: { code: "INTERNAL", message: "disk unavailable", offending_field: null, hint: null, details: {} },
          }),
        })
      : route.continue(),
  );
  await server.ok("robot", "fit.run", { expected_science_revision: await server.revision() });
  await openTab(app, "Fit");
  const failed = app.locator("#panel-fit").getByRole("alert").filter({ hasText: "disk unavailable" });
  await expect(failed).toBeVisible();
  await expect(app.getByText("Loading")).toHaveCount(0); // not "loading" for ever
  fail = false;
  await failed.getByRole("button", { name: "Retry" }).click();
  await expect(failed).toHaveCount(0);
  await expect(app.locator("#panel-fit")).toContainText("χ²");
});

test("a failed result read is retried by itself when the feed reconnects", async ({ page, server }) => {
  await openExample(server);
  let fail = true;
  await page.route("**/api/v1/ops/run.get", (route) =>
    // A malformed reply (a proxy's error page in JSON): the page must still record the failure.
    fail ? route.fulfill({ status: 503, contentType: "application/json", body: '{"ok":false}' }) : route.continue(),
  );
  // The page's own timers run on a controllable clock, so its feed watchdog can be made to fire.
  await page.clock.install();
  await page.goto(await server.launchUrl());
  await expect(page.locator(".conn-live")).toBeVisible();
  await server.ok("robot", "fit.run", { expected_science_revision: await server.revision() });
  await openTab(page, "Fit");
  await expect(page.locator("#panel-fit").getByRole("alert")).toContainText("not an operation envelope");
  fail = false;
  // 41 s without a byte: the watchdog reopens the feed; every (re)connection retries failed reads.
  await page.clock.fastForward(41_000);
  await page.clock.fastForward(1_000); // past the first back-off, if the reopening failed
  await expect(page.locator(".conn-live")).toBeVisible();
  await expect(page.locator("#panel-fit").getByRole("alert")).toHaveCount(0);
  await expect(page.locator("#panel-fit")).toContainText("χ²");
});

test("a reply that is not JSON is recorded as a failed read (round 49)", async ({ app, server }) => {
  await openExample(server);
  await app.route("**/api/v1/ops/run.get", (route) =>
    route.fulfill({ status: 502, contentType: "text/html", body: "<html><body>Bad gateway</body></html>" }),
  );
  await server.ok("robot", "fit.run", { expected_science_revision: await server.revision() });
  await openTab(app, "Fit");
  const failed = app.locator("#panel-fit").getByRole("alert");
  await expect(failed).toContainText("not an operation envelope (HTTP 502)");
  await expect(failed.getByRole("button", { name: "Retry" })).toBeVisible();
});
