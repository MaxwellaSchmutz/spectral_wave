// 3. Jobs: one active job per page. Extra Compute clicks / Enter / hook calls
// during a run do not stack; Cancel terminates the worker, keeps the previous
// result, starts a fresh worker, and the next run succeeds; after several
// cancels exactly one worker is alive.
import { test, expect, type Page } from "@playwright/test";
import { appState, computeViaUi, openApp, selectPreset, settleForm, testLog, waitIdle, type App } from "./support";

test.describe.configure({ mode: "serial" });

let app: App;
test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
  await selectPreset(app.page, "free-gaussian");
  await computeViaUi(app.page);
  expect((await appState(app.page)).meta?.ok).toBe(true);
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

/** A config that takes several seconds in Pyodide (801 sites, 512 + 1024 nodes, ~1500 frames). */
async function fillLongConfig(page: Page, nT: number): Promise<void> {
  await selectPreset(page, "free-gaussian");
  await page.getByTestId("input-N").fill("-400");
  await page.getByTestId("input-M").fill("400");
  await page.getByTestId("input-n_quad").fill("512");
  await page.getByTestId("input-n_t").fill(String(nT)); // distinct n_t -> distinct config key -> never cached
  // Commit the edit and let the cost estimate come back so it cannot interleave with the burst.
  await settleForm(page);
  await expect(page.getByTestId("estimate")).toHaveText(/Estimated working memory/);
}

async function waitStage(page: Page, stage: RegExp): Promise<void> {
  await page.waitForFunction((src) => {
    const s = (window as any).__spectralWave.state();
    return s.busy && new RegExp(src).test(s.stage);
  }, stage.source, { timeout: 120_000, polling: 20 });
}

test("jobs: Compute clicks, Enter and hook calls during a run do not stack", async ({}, testInfo) => {
  const page = app.page;
  await fillLongConfig(page, 1500);
  const log0 = await testLog(page);
  const sentBefore = log0.sent.length;
  const recvBefore = log0.received.length;

  const compute = page.getByTestId("compute-button");
  await compute.click();
  await waitStage(page, /validating|computing/);
  await expect(compute).toBeDisabled();
  const extra: string[] = [];
  for (let k = 0; k < 3; k++) {
    await page.getByTestId("input-N").press("Enter");
    await page.getByTestId("input-n_quad").press("Enter");
    await compute.click({ force: true }); // disabled: must be a no-op
    await compute.evaluate((b) => b.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    const hook = await page.evaluate(() => (window as any).__spectralWave.run({}).then(() => "resolved", (e: any) => `${e.kind}: ${e.message}`));
    extra.push(hook);
  }
  expect((await appState(page)).busy, "still running after the burst").toBe(true);
  await waitIdle(page);

  const log = await testLog(page);
  const sent = log.sent.slice(sentBefore).filter((s) => s.id !== undefined);
  const runs = sent.filter((s) => s.type === "run");
  const results = log.received.slice(recvBefore).filter((r) => r.type === "result");
  await testInfo.attach("jobs-burst.json", { body: JSON.stringify({ sent, results, hookDuringRun: extra }, null, 1), contentType: "application/json" });
  expect(extra.every((e) => e.startsWith("busy")), `hook calls during the run: ${extra.join(" | ")}`).toBe(true);
  expect(runs.length, "run requests sent").toBe(1);
  expect(results.length, "results received").toBe(1);
  expect(results[0].id).toBe(runs[0].id);
  // Request ids (runs and estimates share one counter) advance by exactly one: nothing hidden was queued.
  for (let k = 1; k < sent.length; k++) expect(sent[k].id, `request id after ${sent[k - 1].id}`).toBe(sent[k - 1].id! + 1);
  const s = await appState(page);
  expect(s.meta.ok).toBe(true);
  expect(s.meta.shape).toEqual([1500, 801]);
  await expect(page.getByTestId("status")).toHaveText(/^Done:/);
});

test("jobs: Cancel during a long compute keeps the previous result, recreates the worker, next run works", async ({}, testInfo) => {
  const page = app.page;
  const prev = await appState(page);
  expect(prev.meta?.ok).toBe(true);
  await fillLongConfig(page, 1501);
  const log0 = await testLog(page);
  const workersBefore = log0.workers.length;

  const t0 = Date.now();
  await page.getByTestId("compute-button").click();
  await waitStage(page, /computing|checking/);
  await page.waitForTimeout(Math.max(0, 2000 - (Date.now() - t0)));
  const mid = await appState(page);
  expect(mid.busy, "the config must still be computing after 2 s").toBe(true);
  await page.getByTestId("cancel-button").click();
  const cancelledAfterMs = Date.now() - t0;

  // Idle state immediately (the fresh worker loads in the background).
  await expect(page.getByTestId("cancel-button")).toBeDisabled();
  await expect(page.getByTestId("compute-button")).toBeEnabled();
  await expect(page.getByTestId("status")).toHaveText(/Cancelled\. The previous result is still shown/);
  const s = await appState(page);
  expect(s.busy).toBe(false);
  expect(s.lastError?.kind).toBe("cancelled");
  expect(s.meta.config_key, "previous result kept").toBe(prev.meta.config_key);
  await expect(page.getByTestId("play-button")).toBeEnabled();

  const log1 = await testLog(page);
  expect(log1.workers.length, "a fresh worker was created").toBe(workersBefore + 1);
  expect(log1.workers[workersBefore - 1].alive, "old worker terminated").toBe(false);
  expect(log1.workers.filter((w) => w.alive).length).toBe(1);

  await waitIdle(page);
  await expect(page.getByTestId("status")).toHaveText(/Python is ready again/);
  await selectPreset(page, "single-barrier");
  await computeViaUi(page);
  const after = await appState(page);
  expect(after.meta.ok).toBe(true);
  expect(after.resultPreset).toContain("Single Barrier");
  await expect(page.getByTestId("status")).toHaveText(/^Done:/);
  await testInfo.attach("cancel.json", { body: JSON.stringify({ cancelledAfterMs, workers: log1.workers }, null, 1), contentType: "application/json" });
});

test("jobs: after several cancels exactly one worker is alive", async ({}, testInfo) => {
  const page = app.page;
  const seen: string[] = [];
  page.on("worker", (w) => seen.push(w.url()));
  for (let k = 0; k < 3; k++) {
    await waitIdle(page);
    await fillLongConfig(page, 1502 + k);
    await page.getByTestId("compute-button").click();
    await waitStage(page, /computing|checking/);
    await page.getByTestId("cancel-button").click();
    await expect(page.getByTestId("compute-button")).toBeEnabled();
  }
  await waitIdle(page);
  const log = await testLog(page);
  expect(log.workers.filter((w) => w.alive).length, "instrumented workers alive").toBe(1);
  await expect.poll(() => page.workers().length, { message: "page.workers()", timeout: 30_000 }).toBe(1);
  expect(seen.length, "page 'worker' events during the loop").toBe(3);
  await selectPreset(page, "two-channel-free");
  await computeViaUi(page);
  expect((await appState(page)).meta.ok).toBe(true);
  await testInfo.attach("workers.json", {
    body: JSON.stringify({ created: log.workers.length, alive: log.workers.filter((w) => w.alive).length, playwrightWorkers: page.workers().map((w) => w.url()) }, null, 1),
    contentType: "application/json",
  });
});

/** The estimate line has been replaced by the reply to the latest edit (not the old, dimmed text). */
async function estimateSettled(page: Page): Promise<void> {
  await page.waitForTimeout(400); // past the 350 ms debounce, so a pending mark is already set
  await page.waitForFunction(() => (document.querySelector('[data-testid="estimate"]') as HTMLElement | null)?.dataset.pending !== "true",
    undefined, { timeout: 30_000 });
}

// Regression (was a product bug): editing a field and then clicking Compute fires "change" on
// blur at mousedown; the page used to clear the cost-estimate line, the bottom-sticky .actions box
// shrank and the Compute button dropped ~17 px before mouseup, so the click landed on the
// container and no run started. Clicking the upper part of the button makes this deterministic.
test("jobs: clicking Compute right after editing a field starts the run (no layout shift under the pointer)", async ({}, testInfo) => {
  const page = app.page;
  await waitIdle(page);
  await selectPreset(page, "free-gaussian");
  await settleForm(page);
  await page.getByTestId("input-n_t").fill("123");
  // The user pauses long enough for the new estimate to show, then clicks Compute (focus still in the field).
  await estimateSettled(page);
  await expect(page.getByTestId("estimate")).toHaveText(/Estimated working memory/, { timeout: 30_000 });
  await page.waitForTimeout(200);
  const btn = page.getByTestId("compute-button");
  const box0 = await btn.boundingBox();
  const runsBefore = (await testLog(page)).sent.filter((s) => s.type === "run").length;
  await btn.click({ position: { x: 20, y: 4 } });
  await page.waitForTimeout(300);
  const box1 = await btn.boundingBox();
  const runs = (await testLog(page)).sent.filter((s) => s.type === "run").length - runsBefore;
  await testInfo.attach("layout-shift.json", { body: JSON.stringify({ before: box0, after: box1, runsStarted: runs }, null, 1), contentType: "application/json" });
  await waitIdle(page);
  expect.soft(box1!.y, "Compute button did not move during the click").toBeCloseTo(box0!.y, 0);
  expect(runs, "one run started by the click").toBe(1);
});

// Same click, harder layout: the estimate line shows a multi-line error (interval outside the open
// band) and the user edits another field and clicks Compute within the estimate debounce, so the
// estimate is pending and a blur "change" fires at mousedown. Real mouse down / up on the button's
// top edge: the button must not move in between and exactly one run must start (Python then
// refuses the interval, which is the expected outcome of that run).
test("jobs: a real click on Compute right after an edit, while the estimate shows an error, starts one run", async ({}, testInfo) => {
  const page = app.page;
  await waitIdle(page);
  await selectPreset(page, "free-gaussian");
  await settleForm(page);
  const prevKey = (await appState(page)).meta.config_key;
  await page.getByTestId("input-interval_hi").fill("1.9999");
  await estimateSettled(page);
  const estimate = page.getByTestId("estimate");
  await expect(estimate).toHaveText(/interval|band/i);
  const estLines = await estimate.evaluate((e) => e.getBoundingClientRect().height / (parseFloat(getComputedStyle(e).lineHeight) || 17));

  await page.getByTestId("input-n_t").fill("142");
  await page.waitForTimeout(150); // inside the 350 ms debounce: the estimate is pending, focus still in n_t
  const btn = page.getByTestId("compute-button");
  const runsBefore = (await testLog(page)).sent.filter((s) => s.type === "run").length;
  const b0 = (await btn.boundingBox())!;
  await page.mouse.move(b0.x + 20, b0.y + 3);
  await page.mouse.down();
  const b1 = (await btn.boundingBox())!;
  await page.mouse.up();
  await page.waitForTimeout(300);
  const b2 = (await btn.boundingBox())!;
  const runs = (await testLog(page)).sent.filter((s) => s.type === "run").length - runsBefore;
  await waitIdle(page);
  const s = await appState(page);
  await testInfo.attach("click-error-estimate.json", {
    body: JSON.stringify({ estimateLines: estLines, mousedown: b0, beforeMouseup: b1, after: b2, runsStarted: runs, lastError: s.lastError }, null, 1),
    contentType: "application/json",
  });
  expect(estLines, "the estimate error wraps to more than one line").toBeGreaterThan(1.5);
  expect(b1.y, "Compute did not move between mousedown and mouseup").toBeCloseTo(b0.y, 0);
  expect(b1.x).toBeCloseTo(b0.x, 0);
  expect(runs, "one run started by the click").toBe(1);
  expect(s.lastError?.kind, "Python refused the interval").toBe("invalid_input");
  await expect(page.getByTestId("error-interval")).toHaveText(/common open band/);
  expect(s.meta.config_key, "previous result kept").toBe(prevKey);

  // And a valid edit followed by the same click computes the edited form.
  await selectPreset(page, "single-well");
  await settleForm(page);
  await page.getByTestId("input-n_t").fill("143");
  await page.waitForTimeout(150);
  const c0 = (await btn.boundingBox())!;
  await page.mouse.move(c0.x + 20, c0.y + 3);
  await page.mouse.down();
  const c1 = (await btn.boundingBox())!;
  await page.mouse.up();
  await waitIdle(page);
  const s2 = await appState(page);
  expect(c1.y, "Compute did not move (valid edit)").toBeCloseTo(c0.y, 0);
  expect(s2.meta.ok).toBe(true);
  expect(s2.params.times.n_t).toBe(143);
  expect(s2.resultMatchesForm).toBe(true);
});
