// 2. Validation through the real UI: each bad input shows a plain-text message
// in the slot of the offending field, the previous result stays on screen, and
// a following valid run succeeds. Syntax problems (and anything that looks like
// code) are rejected in the page before any request reaches Python.
import { test, expect } from "@playwright/test";
import { appState, computeViaUi, hookRun, openApp, presets, selectPreset, testLog, waitIdle, type App } from "./support";

test.describe.configure({ mode: "serial" });

const BASE_PRESET = "single-barrier";

let app: App;
let baselineKey = "";

test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
  await selectPreset(app.page, BASE_PRESET);
  await computeViaUi(app.page);
  const s = await appState(app.page);
  expect(s.meta?.ok, "baseline preset run").toBe(true);
  baselineKey = s.meta.config_key;
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

interface Case {
  name: string;
  preset?: string;
  edits: Record<string, string>;
  slot: string;
  message: RegExp;
  /** true: must be rejected in the page, with no run request sent to the worker */
  clientSide: boolean;
  kind?: string;
}

const CASES: Case[] = [
  { name: "NaN typed into E0", edits: { E0: "NaN" }, slot: "E0", message: /E₀.*not a number/, clientSide: true },
  { name: "inf typed into t end", edits: { t_max: "inf" }, slot: "t_max", message: /t end.*not a number/, clientSide: true },
  { name: "1e400 (overflows to Infinity) in sigma_E", edits: { sigma_E: "1e400" }, slot: "sigma_E", message: /σ_E.*too large/, clientSide: true },
  { name: "fractional potential site", edits: { j_sites: "0.5" }, slot: "j_sites", message: /Potential sites.*whole number/, clientSide: true },
  { name: "fractional first site N", edits: { N: "-100.5" }, slot: "N", message: /First site N.*whole number/, clientSide: true },
  { name: "bad potential syntax (unclosed bracket)", edits: { V_sites: "[[[0.6]]" }, slot: "V_sites", message: /Potential matrices:.*(Unclosed|Expected)/, clientSide: true },
  { name: "code in the potential field", edits: { V_sites: "[[[__import__('os')]]]" }, slot: "V_sites", message: /Potential matrices:/, clientSide: true },
  // Deeper than sites / rows / entries: refused by the parser's depth limit, not by a stack overflow.
  {
    name: "potential nested 4 levels deep", edits: { V_sites: "[[[[0.6]]]]" }, slot: "V_sites",
    message: /^Potential matrices: Too many nested "\[" \(at most 3 levels: sites, rows, entries\) at character 4 \(found "\["\)\.$/, clientSide: true,
  },
  {
    name: "200000 nested brackets in the potential (parser depth bomb)", edits: { V_sites: "[".repeat(200_000) }, slot: "V_sites",
    message: /^Potential matrices: Too many nested "\[" \(at most 3 levels/, clientSide: true,
  },
  {
    name: "non-Hermitian V", preset: "two-channel-coupled",
    edits: { V_sites: "[[[0.4, 0.25j], [0.25j, -0.2]]]" },
    slot: "V_sites", message: /V_sites\[0\].*Hermitian/, clientSide: false, kind: "invalid_input",
  },
  { name: "interval outside the open band", edits: { interval_hi: "2.5" }, slot: "interval", message: /interval.*common open band/, clientSide: false, kind: "invalid_input" },
  {
    name: "amplitude essentially zero on the interval",
    edits: { interval_lo: "-1.5", interval_hi: "-1.0", E0: "1.4", sigma_E: "0.01" },
    slot: "E0", message: /amplitude is essentially zero.*E0/, clientSide: false, kind: "invalid_input",
  },
  {
    name: "over budget: memory (n_quad x sites)",
    edits: { N: "-2000", M: "2000", n_quad: "4000" },
    slot: "n_quad", message: /MB.*limit.*n_quad/, clientSide: false, kind: "over_budget",
  },
  {
    name: "over budget: result values",
    edits: { N: "-20000", M: "20000", n_t: "2000" },
    slot: "n_t", message: /values.*limit.*n_t/, clientSide: false, kind: "over_budget",
  },
];

for (const c of CASES) {
  test(`validation: ${c.name}`, async () => {
    const page = app.page;
    await selectPreset(page, c.preset ?? BASE_PRESET);
    for (const [key, value] of Object.entries(c.edits)) await page.getByTestId(`input-${key}`).fill(value);
    const before = await testLog(page);
    const runsBefore = before.sent.filter((s) => s.type === "run").length;
    const resultsBefore = before.received.filter((r) => r.type === "result").length;

    await computeViaUi(page);

    const err = page.getByTestId(`error-${c.slot}`);
    await expect(err).toHaveText(c.message);
    // Plain text: no markup inside the message element.
    expect(await err.evaluate((el) => el.children.length)).toBe(0);
    await expect(err.locator("xpath=ancestor::*[contains(@class,'field')][1]")).toHaveClass(/invalid/);
    await expect(page.getByTestId("status")).toHaveAttribute("data-kind", "error");

    const after = await testLog(page);
    const runsSent = after.sent.filter((s) => s.type === "run").length - runsBefore;
    const results = after.received.filter((r) => r.type === "result").slice(resultsBefore);
    const s = await appState(page);
    if (c.clientSide) {
      expect(runsSent, "rejected in the page: no run request reaches Python").toBe(0);
      await expect(page.getByTestId("status")).toHaveText(/Not computed: fix the highlighted field/);
    } else {
      expect(runsSent).toBe(1);
      expect(results.map((r) => r.ok)).toEqual([false]);
      expect(s.lastError?.kind).toBe(c.kind);
      await expect(page.getByTestId("status")).toContainText("The previous result is still shown");
    }

    // The previous result is untouched and still usable.
    expect(s.meta?.config_key, "previous result kept").toBe(baselineKey);
    await expect(page.getByTestId("play-button")).toBeEnabled();
    await expect(page.getByTestId("download-npz")).toBeEnabled();

    // The app stays usable: a valid run right after succeeds.
    await selectPreset(page, BASE_PRESET);
    await expect(err).toHaveText("");
    const r0 = (await testLog(page)).received.filter((r) => r.type === "result").length;
    await computeViaUi(page);
    const rs = (await testLog(page)).received.filter((r) => r.type === "result").slice(r0);
    expect(rs.map((r) => r.ok)).toEqual([true]);
    await expect(page.getByTestId("status")).toHaveAttribute("data-kind", "ok");
    await expect(page.getByTestId("status")).toHaveText(/^Done:/);
    expect((await appState(page)).meta.config_key).toBe(baselineKey);
  });
}

test("validation: over-budget config is flagged by the live estimate before Compute", async () => {
  const page = app.page;
  await selectPreset(page, BASE_PRESET);
  await page.getByTestId("input-N").fill("-2000");
  await page.getByTestId("input-M").fill("2000");
  await page.getByTestId("input-n_quad").fill("4000");
  await expect(page.getByTestId("estimate")).toHaveText(/limit is 700 MB/, { timeout: 30_000 });
  await expect(page.getByTestId("estimate")).toHaveAttribute("data-kind", "warn");
  await selectPreset(page, BASE_PRESET);
  await expect(page.getByTestId("estimate")).toHaveText(/Estimated working memory/, { timeout: 30_000 });
});

test("validation: Python rejects non-finite / non-integral JSON that bypasses the form (test hook)", async () => {
  const page = app.page;
  const base = (await presets(page)).find((p) => p.id === BASE_PRESET)!.params;
  const cases: [string, (p: any) => void, string][] = [
    // JSON.stringify turns NaN/Infinity into null, which must still be refused.
    ["sigma_E NaN", (p) => { p.amplitude.sigma_E = NaN; }, "amplitude.sigma_E"],
    ["t_max Infinity", (p) => { p.times.t_max = Infinity; }, "times.t_max"],
    ["fractional j_sites", (p) => { p.j_sites = [0.5]; }, "j_sites[0]"],
    ["string L", (p) => { p.L = "1"; }, "L"],
  ];
  for (const [name, mutate, field] of cases) {
    const p = structuredClone(base);
    mutate(p);
    const { meta } = await hookRun(page, p);
    expect(meta.ok, name).toBe(false);
    expect(meta.error.kind, name).toBe("invalid_input");
    expect(meta.error.field, name).toBe(field);
    expect(meta.error.message, name).toContain(field);
  }
  await waitIdle(page);
  expect((await appState(page)).meta.config_key, "previous result kept").toBe(baselineKey);
});
