// 7. What the page says about the result on screen, and what happens when the
// Python worker cannot be loaded at all.
//
// - Stale banner: after an edit or a preset switch the plots no longer describe
//   the form. The page must say so (stale-banner naming the preset that was last
//   computed, dimmed plots, neutral status) and must stop saying so as soon as
//   the form matches the result again, either by reverting the edit, switching
//   back, or pressing Compute.
// - Failed worker: if the worker script cannot be fetched (site updated under an
//   open tab, offline), Cancel's fresh worker fails. The page must end in a
//   plain "failed" state with no restart loop, keep the previous result, and
//   retry exactly once per Compute click. Runs last: it breaks the worker on
//   purpose and restores it at the end.
import { test, expect, type Page } from "@playwright/test";
import {
  appState, computeViaUi, openApp, presets, selectPreset, settleForm, takeHealthProblems, testLog, waitIdle, type App,
} from "./support";

test.describe.configure({ mode: "serial" });

let app: App;
const NAME: Record<string, string> = {};
test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
  for (const p of await presets(app.page)) NAME[p.id] = p.name;
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

/** Everything the page shows about "is the plot the current form?" in one read. */
async function staleView(page: Page) {
  const s = await appState(page);
  const banner = page.getByTestId("stale-banner");
  return {
    matches: s.resultMatchesForm as boolean,
    staleShown: s.staleShown as boolean,
    bannerVisible: await banner.isVisible(),
    bannerText: (await banner.textContent()) ?? "",
    plotsDimmed: await page.getByTestId("plots").evaluate((e) => e.classList.contains("stale")),
    statusKind: await page.getByTestId("status").getAttribute("data-kind"),
    status: await page.getByTestId("status").innerText(),
    caption: await page.getByTestId("result-caption").innerText(),
    configKey: s.meta?.config_key as string | undefined,
  };
}

async function expectFresh(page: Page, presetName: string, modified: boolean): Promise<void> {
  await expect.poll(async () => (await appState(page)).resultMatchesForm, { message: "resultMatchesForm" }).toBe(true);
  const v = await staleView(page);
  expect(v.staleShown, "state().staleShown").toBe(false);
  expect(v.bannerVisible, "stale banner hidden").toBe(false);
  expect(v.plotsDimmed, "plots not dimmed").toBe(false);
  expect(v.statusKind, `status kind (${v.status})`).toBe("ok");
  expect(v.status).toMatch(/^Done:/);
  expect(v.caption).toContain(`“${presetName}”`);
  expect(v.caption.includes("(modified)"), `caption "${v.caption}" says (modified)`).toBe(modified);
  expect(v.caption).not.toContain("not the current form");
}

async function expectStale(page: Page, lastComputed: string): Promise<void> {
  await expect.poll(async () => (await appState(page)).resultMatchesForm, { message: "resultMatchesForm" }).toBe(false);
  const v = await staleView(page);
  expect(v.staleShown, "state().staleShown").toBe(true);
  expect(v.bannerVisible, "stale banner visible").toBe(true);
  expect(v.bannerText).toContain(lastComputed);
  expect(v.bannerText).toContain("press Compute to update");
  expect(v.plotsDimmed, "plots dimmed").toBe(true);
  expect(v.statusKind, `status kind (${v.status})`).toBe("info");
  expect(v.status).not.toMatch(/^Done:/);
  expect(v.caption).toContain("not the current form");
}

test("stale banner: an edit marks the plots stale; reverting it clears the banner and restores Done", async () => {
  const page = app.page;
  await selectPreset(page, "free-gaussian");
  await computeViaUi(page);
  expect((await appState(page)).meta?.ok).toBe(true);
  await expectFresh(page, NAME["free-gaussian"], false);
  const key = (await appState(page)).meta.config_key;
  const nT = String((await appState(page)).params.times.n_t);

  await page.getByTestId("input-n_t").fill(String(Number(nT) + 1));
  await expectStale(page, `“${NAME["free-gaussian"]}”`);
  // Nothing was recomputed: the displayed result is still the old one.
  expect((await appState(page)).meta.config_key).toBe(key);

  await page.getByTestId("input-n_t").fill(nT);
  await expectFresh(page, NAME["free-gaussian"], false);
  await settleForm(page);
  await expectFresh(page, NAME["free-gaussian"], false);
});

test("stale banner: pressing Compute after an edit clears it and the caption says (modified)", async () => {
  const page = app.page;
  const before = (await appState(page)).meta.config_key;
  await page.getByTestId("input-n_t").fill("97");
  await expectStale(page, `“${NAME["free-gaussian"]}”`);
  await computeViaUi(page);
  const s = await appState(page);
  expect(s.meta.ok).toBe(true);
  expect(s.meta.config_key, "a new result").not.toBe(before);
  expect(s.params.times.n_t).toBe(97);
  await expectFresh(page, NAME["free-gaussian"], true);
});

test("stale banner: switching preset names the last computed preset; switching back matches again", async () => {
  const page = app.page;
  await selectPreset(page, "strong-wall");
  await computeViaUi(page);
  await expectFresh(page, NAME["strong-wall"], false);

  await selectPreset(page, "single-well");
  await expectStale(page, `“${NAME["strong-wall"]}”`);
  const v = await staleView(page);
  expect(v.bannerText, "banner names the result, not the form's preset").not.toContain(NAME["single-well"]);

  await selectPreset(page, "strong-wall");
  await expectFresh(page, NAME["strong-wall"], false);

  // A modified result stays stale against its own unmodified preset.
  await page.getByTestId("input-t_max").fill(String((await appState(page)).params.times.t_max + 1));
  await computeViaUi(page);
  await expectFresh(page, NAME["strong-wall"], true);
  await selectPreset(page, "strong-wall");
  await expectStale(page, `“${NAME["strong-wall"]}” (modified)`);
});

test("failed worker: missing worker script after Cancel ends in a plain failed state, no restart loop, one retry per click", async ({}, testInfo) => {
  const page = app.page;
  await waitIdle(page);
  await selectPreset(page, "single-barrier");
  await computeViaUi(page);
  const prev = await appState(page);
  expect(prev.meta.ok).toBe(true);

  // A long job to cancel.
  await selectPreset(page, "free-gaussian");
  await page.getByTestId("input-N").fill("-400");
  await page.getByTestId("input-M").fill("400");
  await page.getByTestId("input-n_quad").fill("512");
  await page.getByTestId("input-n_t").fill("1509");
  await settleForm(page);
  await page.getByTestId("compute-button").click();
  await page.waitForFunction(() => {
    const s = (window as any).__spectralWave.state();
    return s.busy && /computing|checking/.test(s.stage);
  }, undefined, { timeout: 120_000, polling: 20 });

  // From now on the worker script is gone (as after a redeploy with new hashes).
  const WORKER_SCRIPT = /\/assets\/pyworker-[^/?#]*\.js/;
  let scriptHits = 0;
  await app.context.route(WORKER_SCRIPT, (route) => {
    scriptHits++;
    return route.fulfill({ status: 404, contentType: "text/plain", body: "not found" });
  });
  // Expected noise while the script is missing: the 404 itself and the browser's report of it.
  const allowed = [
    { pattern: WORKER_SCRIPT, reason: "worker script routed to 404 by this test" },
    { pattern: /Failed to load resource: the server responded with a status of 404/, reason: "the routed 404 (Chromium)" },
  ];
  app.health.allowed.push(...allowed);
  try {
    const workers0 = (await testLog(page)).workers.length;
    const tCancel = Date.now();
    await page.getByTestId("cancel-button").click();
    await page.waitForFunction(() => (window as any).__spectralWave.state().workerState === "failed", undefined, { timeout: 30_000 });
    const failedAfterMs = Date.now() - tCancel;
    // Any restart loop would show up within this window.
    await page.waitForTimeout(Math.max(0, 5000 - (Date.now() - tCancel)));
    const log5 = await testLog(page);
    const created5 = log5.workers.length - workers0;
    const hits5 = scriptHits;
    await page.waitForTimeout(1500);
    const createdLater = (await testLog(page)).workers.length - workers0 - created5;

    const s = await appState(page);
    const status = page.getByTestId("status");
    const statusText = await status.innerText();
    await testInfo.attach("worker-failed.json", {
      body: JSON.stringify({ failedAfterMs, created5, hits5, createdLater, statusText, workerState: s.workerState, workers: log5.workers }, null, 1),
      contentType: "application/json",
    });
    expect(s.workerState).toBe("failed");
    expect(created5, "workers created in the 5 s after Cancel").toBeLessThanOrEqual(3);
    expect(created5, "Cancel made a fresh worker").toBeGreaterThanOrEqual(1);
    expect(hits5, "worker script requests in the 5 s after Cancel").toBeLessThanOrEqual(3);
    expect(createdLater, "no further workers once failed").toBe(0);
    await expect(status).toHaveAttribute("data-kind", "error");
    expect(statusText).toMatch(/could not be loaded/);
    expect(statusText.match(/could not be loaded/g)!.length, "message not doubled").toBe(1);
    expect(statusText, "plain text, no stack or raw event").not.toMatch(/\bat \S+:\d+|\[object |undefined|Error:/);
    expect(await status.evaluate((el) => el.children.length), "status is plain text").toBe(0);
    expect(s.busy).toBe(false);
    expect(s.meta.config_key, "previous result kept").toBe(prev.meta.config_key);
    await expect(page.getByTestId("compute-button")).toBeEnabled();
    await expect(page.getByTestId("cancel-button")).toBeDisabled();
    await expect(page.getByTestId("play-button")).toBeEnabled();
    const ready = await page.evaluate(() => (window as any).__spectralWave.ready.then(() => "resolved", (e: any) => `rejected: ${e?.message}`));
    expect(ready, "ready rejects while failed").toMatch(/^rejected/);

    // One Compute click = exactly one more attempt, and the page settles back to failed.
    const w1 = (await testLog(page)).workers.length;
    const h1 = scriptHits;
    await page.getByTestId("compute-button").click();
    await page.waitForTimeout(4000);
    const s2 = await appState(page);
    expect((await testLog(page)).workers.length - w1, "workers created by one Compute click").toBe(1);
    expect(scriptHits - h1, "script requests from one Compute click").toBe(1);
    expect(s2.workerState).toBe("failed");
    expect(s2.busy).toBe(false);
    expect(s2.meta.config_key, "previous result still kept").toBe(prev.meta.config_key);
    await expect(status).toHaveText(/could not be loaded/);
    await expect(page.getByTestId("compute-button")).toBeEnabled();

    // Leftover noise is only what the 404 explains.
    const problems = takeHealthProblems(app.health);
    expect(problems, "unexpected console errors / requests while the script was missing").toEqual([]);
  } finally {
    await app.context.unroute(WORKER_SCRIPT);
    app.health.allowed.splice(app.health.allowed.length - allowed.length, allowed.length);
  }

  // Script back: the next Compute recovers and computes.
  await selectPreset(page, "single-barrier");
  await settleForm(page);
  await page.getByTestId("compute-button").click();
  await waitIdle(page);
  const s3 = await appState(page);
  expect(s3.workerState).toBe("ready");
  expect(s3.meta.ok).toBe(true);
  expect(s3.resultPreset).toContain("Single Barrier");
  expect(s3.resultMatchesForm).toBe(true);
  await expect(page.getByTestId("status")).toHaveText(/^Done:/);
  expect((await testLog(page)).workers.filter((w) => w.alive).length, "one live worker").toBe(1);
});
