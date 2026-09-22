// 4. Playback and plots: play/pause, restart, scrubbing (slider + keyboard),
// speed, redraw on resize while paused, heatmap time alignment (the cursor for
// frame i is drawn at t_i, the centre of image row i), potential-site markers.
import { test, expect, type Page } from "@playwright/test";
import { MARGINS } from "../src/plots";
import {
  appState, canvasPixels, computeViaUi, linspace, openApp, rgba, selectPreset, type App, type CanvasPixels,
} from "./support";

test.describe.configure({ mode: "serial" });

const N_T = 600;
let app: App;

test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
  await selectPreset(app.page, "single-barrier"); // potential at site 0, sites -100..100
  await app.page.getByTestId("input-n_t").fill(String(N_T));
  await computeViaUi(app.page);
  const s = await appState(app.page);
  expect(s.meta?.ok).toBe(true);
  expect(s.nFrames).toBe(N_T);
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

async function frameOf(page: Page): Promise<number> {
  return (await appState(page)).frameIndex;
}

async function pause(page: Page): Promise<void> {
  if ((await appState(page)).playing) await page.getByTestId("play-button").click();
  expect((await appState(page)).playing).toBe(false);
}

function tFmt(x: number): string {
  // readout-time uses fmt(x, 5) in main.ts: toPrecision(5), exponent form outside [1e-3, 1e4)
  if (x === 0) return "0";
  const a = Math.abs(x);
  return a >= 1e4 || a < 1e-3 ? x.toExponential(4) : x.toPrecision(5);
}

test("playback: play / pause / restart", async () => {
  const page = app.page;
  const play = page.getByTestId("play-button");
  // Compute auto-plays.
  expect((await appState(page)).playing).toBe(true);
  await expect(play).toHaveText("Pause");
  await play.click();
  await expect(play).toHaveText("Play");
  const f0 = await frameOf(page);
  await page.waitForTimeout(400);
  expect(await frameOf(page), "paused: frame does not move").toBe(f0);
  await play.click();
  await expect(play).toHaveText("Pause");
  await expect.poll(() => frameOf(page), { timeout: 5_000 }).toBeGreaterThan(f0);
  await page.waitForTimeout(300);
  await page.getByTestId("restart-button").click();
  const afterRestart = await appState(page);
  expect(afterRestart.playing).toBe(true);
  expect(afterRestart.frameIndex, "restart goes back to the first frame").toBeLessThan(15);
  await pause(page);
});

test("playback: scrub with the slider and the keyboard", async () => {
  const page = app.page;
  await pause(page);
  const times = linspace(0, 55, N_T);
  const scrub = page.getByTestId("scrubber");
  await scrub.fill("250");
  let s = await appState(page);
  expect(s.frameIndex).toBe(250);
  expect(s.playing).toBe(false);
  await expect(page.getByTestId("frame-label")).toHaveText(`frame 251 / ${N_T}`);
  await expect(page.getByTestId("readout-time")).toHaveText(tFmt(times[250]));
  await expect(page.getByTestId("readout-mass")).toHaveText(s.meta.mass_in_frame[250].toFixed(6));

  // Slider keys (native range behaviour).
  await scrub.focus();
  await page.keyboard.press("ArrowRight");
  expect(await frameOf(page)).toBe(251);
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  expect(await frameOf(page)).toBe(249);
  await page.keyboard.press("End");
  expect(await frameOf(page)).toBe(N_T - 1);
  await page.keyboard.press("Home");
  expect(await frameOf(page)).toBe(0);

  // Page-level shortcuts when focus is not in a field.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.keyboard.press("End");
  expect(await frameOf(page)).toBe(N_T - 1);
  await page.keyboard.press("ArrowLeft");
  expect(await frameOf(page)).toBe(N_T - 2);
  await page.keyboard.press("Home");
  await page.keyboard.press("ArrowRight");
  expect(await frameOf(page)).toBe(1);
  await page.keyboard.press(" ");
  expect((await appState(page)).playing, "space toggles play").toBe(true);
  await page.keyboard.press(" ");
  s = await appState(page);
  expect(s.playing).toBe(false);
  await expect(page.getByTestId("frame-label")).toHaveText(`frame ${s.frameIndex + 1} / ${N_T}`);
});

test("playback: speed changes the frame rate", async ({}, testInfo) => {
  const page = app.page;
  const rates: Record<string, number> = {};
  for (const speed of ["1", "4", "0.25"]) {
    await pause(page);
    await page.getByTestId("speed-select").selectOption(speed);
    expect((await appState(page)).speed).toBe(Number(speed));
    await page.getByTestId("scrubber").fill("0");
    await page.getByTestId("play-button").click();
    // Measure inside the page: frames advanced per second of wall time.
    rates[speed] = await page.evaluate(async () => {
      const st = () => (window as any).__spectralWave.state();
      await new Promise((r) => setTimeout(r, 200));
      const f0 = st().frameIndex;
      const t0 = performance.now();
      await new Promise((r) => setTimeout(r, 1500));
      return (st().frameIndex - f0) / ((performance.now() - t0) / 1000);
    });
  }
  await pause(page);
  await page.getByTestId("speed-select").selectOption("1");
  await testInfo.attach("frame-rates.json", { body: JSON.stringify(rates, null, 1), contentType: "application/json" });
  console.log(`  [${testInfo.project.name}] frames/s by speed: ${JSON.stringify(rates)}`);
  expect(rates["1"], "1x ~ 30 frames/s").toBeGreaterThan(20);
  expect(rates["1"]).toBeLessThan(40);
  expect(rates["4"] / rates["1"], "4x vs 1x").toBeGreaterThan(3);
  expect(rates["4"] / rates["1"]).toBeLessThan(5);
  expect(rates["0.25"] / rates["1"], "0.25x vs 1x").toBeGreaterThan(0.15);
  expect(rates["0.25"] / rates["1"]).toBeLessThan(0.35);
});

function countPixels(p: CanvasPixels, pred: (r: number, g: number, b: number) => boolean): number {
  const d = rgba(p);
  let n = 0;
  for (let i = 0; i < d.length; i += 4) if (pred(d[i], d[i + 1], d[i + 2])) n++;
  return n;
}
const isCurve = (r: number, g: number, b: number) => Math.abs(r - 0x1c) < 40 && Math.abs(g - 0x5d) < 40 && Math.abs(b - 0x99) < 40;
// Viridis runs from (68,1,84) to (253,231,37): never grey/white, blue channel never above ~160.
const isViridis = (r: number, g: number, b: number) => b < 170 && Math.max(r, g, b) - Math.min(r, g, b) > 30;
const isOrange = (r: number, g: number, b: number) => r > 150 && g < 120 && b < 70;

test("plots: resize while paused redraws both canvases", async ({}, testInfo) => {
  const page = app.page;
  await pause(page);
  await page.getByTestId("scrubber").fill("200");
  const before = { d: await canvasPixels(page, "plot-density"), h: await canvasPixels(page, "plot-heatmap") };

  await page.setViewportSize({ width: 1000, height: 900 });
  await expect.poll(async () => (await canvasPixels(page, "plot-density")).width, { timeout: 10_000 }).not.toBe(before.d.width);
  await page.waitForTimeout(300);
  const small = { d: await canvasPixels(page, "plot-density"), h: await canvasPixels(page, "plot-heatmap") };
  for (const [name, p, q] of [["density", small.d, before.d], ["heatmap", small.h, before.h]] as const) {
    expect(p.width, `${name}: backing store follows the CSS box`).toBe(Math.round(Math.floor(p.cssWidth) * p.dpr));
    expect(p.height).toBe(Math.round(Math.floor(p.cssHeight) * p.dpr));
    expect(p.width, `${name}: size changed`).not.toBe(q.width);
  }
  expect(countPixels(small.d, isCurve), "density curve drawn after resize").toBeGreaterThan(200);
  expect(countPixels(small.h, isViridis), "heatmap image drawn after resize").toBeGreaterThan(small.h.width * small.h.height * 0.3);
  expect((await appState(page)).playing, "still paused").toBe(false);
  expect(await frameOf(page)).toBe(200);

  // Back to the original size: the redraw reproduces the original pixels exactly.
  await page.setViewportSize({ width: 1400, height: 1000 });
  await expect.poll(async () => (await canvasPixels(page, "plot-density")).width, { timeout: 10_000 }).toBe(before.d.width);
  await page.waitForTimeout(300);
  const again = { d: await canvasPixels(page, "plot-density"), h: await canvasPixels(page, "plot-heatmap") };
  const same = (a: CanvasPixels, b: CanvasPixels) => a.width === b.width && a.height === b.height && rgba(a).equals(rgba(b));
  const diffCount = (a: CanvasPixels, b: CanvasPixels) => {
    const x = rgba(a), y = rgba(b);
    let n = 0;
    for (let i = 0; i < Math.min(x.length, y.length); i += 4) if (x[i] !== y[i] || x[i + 1] !== y[i + 1] || x[i + 2] !== y[i + 2]) n++;
    return n;
  };
  await testInfo.attach("resize.json", {
    body: JSON.stringify({
      before: [before.d.width, before.d.height, before.h.width, before.h.height],
      small: [small.d.width, small.d.height, small.h.width, small.h.height],
      diffPixelsAfterRestore: { density: diffCount(again.d, before.d), heatmap: diffCount(again.h, before.h) },
    }, null, 1),
    contentType: "application/json",
  });
  expect(same(again.d, before.d), "density identical after restoring the size").toBe(true);
  expect(same(again.h, before.h), "heatmap identical after restoring the size").toBe(true);
});

test("plots: heatmap cursor for frame i sits at t_i; potential markers drawn", async ({}, testInfo) => {
  const page = app.page;
  // Few frames -> tall image rows, so a half-row misalignment is ~10 px.
  const nT = 20;
  await selectPreset(page, "single-barrier");
  await page.getByTestId("input-n_t").fill(String(nT));
  await computeViaUi(page);
  const s = await appState(page);
  expect(s.nFrames).toBe(nT);
  await pause(page);
  const { t_min, t_max } = s.meta.times;
  const times = linspace(t_min, t_max, nT);
  const { N, M } = s.meta.sites;
  const rows: any[] = [];
  for (const i of [0, 1, 7, 13, nT - 1]) {
    await page.getByTestId("scrubber").fill(String(i));
    expect(await frameOf(page)).toBe(i);
    const p = await canvasPixels(page, "plot-heatmap");
    const d = rgba(p);
    const w = Math.floor(p.cssWidth), h = Math.floor(p.cssHeight), dpr = p.dpr;
    const r = { x: MARGINS.left, y: MARGINS.top, w: w - MARGINS.left - MARGINS.right, h: h - MARGINS.top - MARGINS.bottom };
    const dt = (times[nT - 1] - times[0]) / (nT - 1);
    const tLo = times[0] - dt / 2, tHi = times[nT - 1] + dt / 2;
    const yAxis = r.y + r.h - ((times[i] - tLo) / (tHi - tLo)) * r.h; // axis mapping at t_i
    const yRow = r.y + r.h - (i + 0.5) * (r.h / nT); // centre of image row i (row i = [t_i - dt/2, t_i + dt/2])
    // Scan a column at site n = N + 25% of the frame (away from the potential at 0).
    const x = Math.round((r.x + 0.25 * r.w) * dpr);
    let sum = 0, wsum = 0;
    for (let y = Math.floor(r.y * dpr); y < Math.ceil((r.y + r.h) * dpr); y++) {
      const o = (y * p.width + x) * 4;
      const white = Math.min(d[o], d[o + 1], d[o + 2]);
      if (white > 180) { sum += (y + 0.5) * white; wsum += white; }
    }
    const yCursor = wsum ? sum / wsum / dpr : NaN;
    rows.push({ frame: i, t: times[i], yCursor, yAxis, yRow, rowHeight: r.h / nT });
    expect(Math.abs(yAxis - yRow), "axis mapping and image row agree").toBeLessThan(1e-6);
    expect(Math.abs(yCursor - yAxis), `frame ${i}: cursor row vs t_i on the axis (px)`).toBeLessThan(1.0);
  }
  await testInfo.attach("heatmap-cursor.json", { body: JSON.stringify(rows, null, 1), contentType: "application/json" });

  // Potential markers at site 0 on both plots, and none at a control column.
  const dens = await canvasPixels(page, "plot-density");
  const heat = await canvasPixels(page, "plot-heatmap");
  const colScan = (p: CanvasPixels, xCss: number, y0: number, y1: number) => {
    const d = rgba(p);
    let n = 0;
    for (let y = Math.floor(y0 * p.dpr); y < Math.ceil(y1 * p.dpr); y++) {
      for (const dx of [-1, 0, 1]) {
        const o = (y * p.width + Math.round(xCss * p.dpr) + dx) * 4;
        if (isOrange(d[o], d[o + 1], d[o + 2])) { n++; break; }
      }
    }
    return n;
  };
  const geo = (p: CanvasPixels) => {
    const w = Math.floor(p.cssWidth), h = Math.floor(p.cssHeight);
    const r = { x: MARGINS.left, y: MARGINS.top, w: w - MARGINS.left - MARGINS.right, h: h - MARGINS.top - MARGINS.bottom };
    const sx = (n: number) => r.x + ((n - (N - 0.5)) / (M - N + 1)) * r.w;
    return { r, sx };
  };
  const gd = geo(dens);
  const onSite = colScan(dens, Math.round(gd.sx(0)) + 0.5, gd.r.y, gd.r.y + gd.r.h);
  const control = colScan(dens, Math.round(gd.sx(-60)) + 0.5, gd.r.y, gd.r.y + gd.r.h);
  const gh = geo(heat);
  const triangle = colScan(heat, gh.sx(0), gh.r.y - 9, gh.r.y - 1);
  const triControl = colScan(heat, gh.sx(-60), gh.r.y - 9, gh.r.y - 1);
  await testInfo.attach("potential-markers.json", { body: JSON.stringify({ onSite, control, triangle, triControl, plotHeight: gd.r.h }, null, 1), contentType: "application/json" });
  expect(onSite, "dashed potential line at site 0 on the density plot").toBeGreaterThan(gd.r.h * 0.3);
  expect(control).toBe(0);
  expect(triangle, "potential marker above the heatmap at site 0").toBeGreaterThan(3);
  expect(triControl).toBe(0);
});
