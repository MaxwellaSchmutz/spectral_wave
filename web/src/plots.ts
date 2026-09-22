// Canvas plots of stored results. Nothing here computes physics: every value
// drawn is read straight from psi(n, t) as Python returned it.

export interface PlotData {
  /** Row-major (n_t, n_sites) float64 density from Python. */
  psi: Float64Array;
  nT: number;
  nSites: number;
  N: number;
  M: number;
  /** The time sample of each row (np.linspace grid, see times.ts). */
  times: Float64Array;
  /** Maximum of psi over all frames and sites. */
  globalMax: number;
  /** Lattice sites carrying a potential. */
  jSites: number[];
}

export const COLORS = {
  bg: "#0d1826",
  frame: "#38516b",
  grid: "#203045",
  text: "#eef5fc",
  faint: "#afbed0",
  curve: "#63e3db",
  fill: "rgba(99, 227, 219, 0.14)",
  potential: "#f8b56d",
  cursor: "#ffffff",
  cursorEdge: "#111111",
};

const FONT = '12px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const FONT_LABEL = '13px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

export interface Margins {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** Same margins on both plots so their x-axes line up exactly. */
export const MARGINS: Margins = { left: 70, right: 104, top: 14, bottom: 46 };

// ---- ticks ----------------------------------------------------------------

export function niceTicks(lo: number, hi: number, target: number): number[] {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const out: number[] = [];
  const first = Math.ceil(lo / step - 1e-9) * step;
  for (let v = first; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}

export function fmtTick(v: number, step: number): string {
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(1).replace("e+", "e");
  const decimals = Math.max(0, Math.min(6, -Math.floor(Math.log10(step) + 1e-9)));
  return v.toFixed(decimals);
}

// ---- colour map -----------------------------------------------------------

// Viridis, 16 stops (perceptually uniform, readable in greyscale).
const VIRIDIS = [
  "#440154", "#481a6c", "#472f7d", "#414487", "#39568c", "#31688e", "#2a788e", "#23888e",
  "#1f988b", "#22a884", "#35b779", "#54c568", "#7ad151", "#a5db36", "#d2e21b", "#fde725",
];

export const LUT: Uint8ClampedArray = (() => {
  const stops = VIRIDIS.map((h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)));
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * (stops.length - 1);
    const k = Math.min(stops.length - 2, Math.floor(x));
    const f = x - k;
    for (let c = 0; c < 3; c++) lut[i * 3 + c] = Math.round(stops[k][c] * (1 - f) + stops[k + 1][c] * f);
  }
  return lut;
})();

function lutCss(i: number): string {
  return `rgb(${LUT[i * 3]}, ${LUT[i * 3 + 1]}, ${LUT[i * 3 + 2]})`;
}

// Canvases wider than this are unsafe in some browsers; wider lattices are
// max-pooled into this many columns for the heatmap image only.
const MAX_IMAGE_COLS = 8192;

/**
 * Heatmap image: one pixel row per stored time sample, drawn later so that
 * row i covers exactly [t_i - dt/2, t_i + dt/2]. Linear scale 0..globalMax.
 */
export function buildHeatImage(d: PlotData): HTMLCanvasElement {
  const cols = Math.min(d.nSites, MAX_IMAGE_COLS);
  const pool = d.nSites / cols;
  const img = document.createElement("canvas");
  img.width = cols;
  img.height = d.nT;
  const ctx = img.getContext("2d")!;
  const data = ctx.createImageData(cols, d.nT);
  const scale = d.globalMax > 0 ? 255 / d.globalMax : 0;
  for (let i = 0; i < d.nT; i++) {
    const rowOut = d.nT - 1 - i; // time increases upward
    const base = i * d.nSites;
    for (let c = 0; c < cols; c++) {
      let v: number;
      if (pool === 1) v = d.psi[base + c];
      else {
        const k0 = Math.floor(c * pool);
        const k1 = Math.max(k0 + 1, Math.floor((c + 1) * pool));
        v = 0;
        for (let k = k0; k < k1; k++) v = Math.max(v, d.psi[base + k]);
      }
      const li = Math.max(0, Math.min(255, Math.round(v * scale)));
      const o = (rowOut * cols + c) * 4;
      data.data[o] = LUT[li * 3];
      data.data[o + 1] = LUT[li * 3 + 1];
      data.data[o + 2] = LUT[li * 3 + 2];
      data.data[o + 3] = 255;
    }
  }
  ctx.putImageData(data, 0, 0);
  return img;
}

// ---- shared geometry ------------------------------------------------------

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** x-range shared by both plots: every site n covers [n - 1/2, n + 1/2]. */
export function xDomain(d: PlotData): [number, number] {
  return [d.N - 0.5, d.M + 0.5];
}

function xScale(d: PlotData, r: Rect): (n: number) => number {
  const [lo, hi] = xDomain(d);
  return (n) => r.x + ((n - lo) / (hi - lo)) * r.w;
}

function dtOf(d: PlotData): number {
  return d.nT > 1 ? (d.times[d.nT - 1] - d.times[0]) / (d.nT - 1) : 1;
}

function drawXAxis(ctx: CanvasRenderingContext2D, d: PlotData, r: Rect, label: string): void {
  const [lo, hi] = xDomain(d);
  const ticks = niceTicks(d.N, d.M, Math.max(3, Math.floor(r.w / 80))).filter((t) => Number.isInteger(t));
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1;
  const sx = xScale(d, r);
  ctx.font = FONT;
  ctx.fillStyle = COLORS.faint;
  ctx.strokeStyle = COLORS.frame;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const t of ticks) {
    if (t < lo || t > hi) continue;
    const x = Math.round(sx(t)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, r.y + r.h);
    ctx.lineTo(x, r.y + r.h + 5);
    ctx.stroke();
    ctx.fillText(fmtTick(t, step), x, r.y + r.h + 7);
  }
  ctx.font = FONT_LABEL;
  ctx.fillStyle = COLORS.text;
  ctx.fillText(label, r.x + r.w / 2, r.y + r.h + 25);
}

function drawYAxis(
  ctx: CanvasRenderingContext2D,
  r: Rect,
  lo: number,
  hi: number,
  label: string,
  grid: boolean,
): void {
  const ticks = niceTicks(lo, hi, Math.max(2, Math.floor(r.h / 45)));
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : Math.abs(hi - lo) || 1;
  ctx.font = FONT;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const t of ticks) {
    const y = Math.round(r.y + r.h - ((t - lo) / (hi - lo)) * r.h) + 0.5;
    if (grid) {
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath();
      ctx.moveTo(r.x, y);
      ctx.lineTo(r.x + r.w, y);
      ctx.stroke();
    }
    ctx.strokeStyle = COLORS.frame;
    ctx.beginPath();
    ctx.moveTo(r.x - 5, y);
    ctx.lineTo(r.x, y);
    ctx.stroke();
    ctx.fillStyle = COLORS.faint;
    ctx.fillText(fmtTick(t, step), r.x - 8, y);
  }
  ctx.save();
  ctx.translate(r.x - 56, r.y + r.h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = FONT_LABEL;
  ctx.fillStyle = COLORS.text;
  ctx.fillText(label, 0, 0);
  ctx.restore();
}

function frameRect(ctx: CanvasRenderingContext2D, r: Rect): void {
  ctx.strokeStyle = COLORS.frame;
  ctx.lineWidth = 1;
  ctx.strokeRect(Math.round(r.x) + 0.5, Math.round(r.y) + 0.5, Math.round(r.w), Math.round(r.h));
}

export function plotRect(width: number, height: number, m: Margins = MARGINS): Rect {
  return { x: m.left, y: m.top, w: Math.max(10, width - m.left - m.right), h: Math.max(10, height - m.top - m.bottom) };
}

// ---- plot 1: density at the current frame ---------------------------------

export function drawDensity(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  d: PlotData,
  frame: number,
): void {
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, width, height);
  const r = plotRect(width, height);
  const yMax = d.globalMax > 0 ? d.globalMax * 1.05 : 1;
  drawYAxis(ctx, r, 0, yMax, "density ψ(n, t)", true);
  const sx = xScale(d, r);
  const sy = (v: number) => r.y + r.h - (v / yMax) * r.h;

  // potential sites
  ctx.save();
  ctx.strokeStyle = COLORS.potential;
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1;
  for (const j of d.jSites) {
    if (j < d.N || j > d.M) continue;
    const x = Math.round(sx(j)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, r.y);
    ctx.lineTo(x, r.y + r.h);
    ctx.stroke();
  }
  ctx.restore();

  const base = frame * d.nSites;
  ctx.save();
  ctx.beginPath();
  ctx.rect(r.x, r.y, r.w, r.h);
  ctx.clip();
  // Sub-pixel lattices: draw the envelope column by column (max over sites).
  const pxPerSite = r.w / d.nSites;
  ctx.beginPath();
  if (pxPerSite >= 1) {
    for (let k = 0; k < d.nSites; k++) {
      const x = sx(d.N + k);
      const y = sy(d.psi[base + k]);
      if (k === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
  } else {
    const cols = Math.ceil(r.w);
    for (let c = 0; c < cols; c++) {
      const k0 = Math.floor((c / cols) * d.nSites);
      const k1 = Math.max(k0 + 1, Math.floor(((c + 1) / cols) * d.nSites));
      let v = 0;
      for (let k = k0; k < k1; k++) v = Math.max(v, d.psi[base + k]);
      const x = r.x + c + 0.5;
      if (c === 0) ctx.moveTo(x, sy(v));
      else ctx.lineTo(x, sy(v));
    }
  }
  const lastX = pxPerSite >= 1 ? sx(d.M) : r.x + Math.ceil(r.w) - 0.5;
  const firstX = pxPerSite >= 1 ? sx(d.N) : r.x + 0.5;
  ctx.strokeStyle = COLORS.curve;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();
  ctx.lineTo(lastX, sy(0));
  ctx.lineTo(firstX, sy(0));
  ctx.closePath();
  const fill = ctx.createLinearGradient(0, r.y, 0, r.y + r.h);
  fill.addColorStop(0, "rgba(99, 227, 219, 0.30)");
  fill.addColorStop(1, "rgba(99, 227, 219, 0.02)");
  ctx.fillStyle = fill;
  ctx.fill();
  // Individual site markers when there is room to see them.
  if (pxPerSite >= 5) {
    ctx.fillStyle = COLORS.curve;
    for (let k = 0; k < d.nSites; k++) {
      ctx.beginPath();
      ctx.arc(sx(d.N + k), sy(d.psi[base + k]), 1.6, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
  ctx.restore();

  frameRect(ctx, r);
  drawXAxis(ctx, d, r, "site n");
}

// ---- plot 2: time / site heatmap ------------------------------------------

export function drawHeatmap(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  d: PlotData,
  frame: number,
  image: HTMLCanvasElement,
): void {
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, width, height);
  const r = plotRect(width, height);
  const dt = dtOf(d);
  const tLo = d.times[0] - dt / 2;
  const tHi = d.times[d.nT - 1] + dt / 2;
  const sy = (t: number) => r.y + r.h - ((t - tLo) / (tHi - tLo)) * r.h;

  ctx.save();
  ctx.imageSmoothingEnabled = false;
  // The image spans exactly [N-1/2, M+1/2] x [t_0 - dt/2, t_last + dt/2].
  ctx.drawImage(image, r.x, r.y, r.w, r.h);
  ctx.restore();

  drawYAxis(ctx, r, tLo, tHi, "time t", false);

  const sx = xScale(d, r);
  // potential-site markers: dashed lines plus a tick above the plot
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
  ctx.setLineDash([3, 5]);
  for (const j of d.jSites) {
    if (j < d.N || j > d.M) continue;
    const x = Math.round(sx(j)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, r.y);
    ctx.lineTo(x, r.y + r.h);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.fillStyle = COLORS.potential;
  for (const j of d.jSites) {
    if (j < d.N || j > d.M) continue;
    const x = sx(j);
    ctx.beginPath();
    ctx.moveTo(x - 5, r.y - 9);
    ctx.lineTo(x + 5, r.y - 9);
    ctx.lineTo(x, r.y - 1);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();

  // time cursor exactly at t_i
  const yc = sy(d.times[frame]);
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
  ctx.beginPath();
  ctx.moveTo(r.x, yc);
  ctx.lineTo(r.x + r.w, yc);
  ctx.stroke();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = COLORS.cursor;
  ctx.beginPath();
  ctx.moveTo(r.x, yc);
  ctx.lineTo(r.x + r.w, yc);
  ctx.stroke();
  ctx.restore();

  frameRect(ctx, r);
  drawXAxis(ctx, d, r, "site n");
  drawColorbar(ctx, r, d.globalMax);
}

function drawColorbar(ctx: CanvasRenderingContext2D, r: Rect, max: number): void {
  const bar: Rect = { x: r.x + r.w + 14, y: r.y, w: 14, h: r.h };
  for (let i = 0; i < 256; i++) {
    const y0 = bar.y + bar.h - ((i + 1) / 256) * bar.h;
    ctx.fillStyle = lutCss(i);
    ctx.fillRect(bar.x, Math.floor(y0), bar.w, Math.ceil(bar.h / 256) + 1);
  }
  frameRect(ctx, bar);
  const top = max > 0 ? max : 1;
  const ticks = niceTicks(0, top, Math.max(2, Math.floor(r.h / 50)));
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : top;
  ctx.font = FONT;
  ctx.fillStyle = COLORS.faint;
  ctx.strokeStyle = COLORS.frame;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  for (const t of ticks) {
    const y = Math.round(bar.y + bar.h - (t / top) * bar.h) + 0.5;
    ctx.beginPath();
    ctx.moveTo(bar.x + bar.w, y);
    ctx.lineTo(bar.x + bar.w + 4, y);
    ctx.stroke();
    ctx.fillText(fmtTick(t, step), bar.x + bar.w + 6, y);
  }
  ctx.save();
  ctx.translate(bar.x + bar.w + 54, bar.y + bar.h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.font = FONT_LABEL;
  ctx.fillStyle = COLORS.text;
  ctx.fillText("ψ(n, t)", 0, 0);
  ctx.restore();
}

// ---- HiDPI canvas helper --------------------------------------------------

/**
 * Size a canvas's backing store to its CSS box times devicePixelRatio and
 * return a context scaled to CSS pixels.
 */
export function prepareCanvas(canvas: HTMLCanvasElement): { ctx: CanvasRenderingContext2D; w: number; h: number } | null {
  const rect = canvas.getBoundingClientRect();
  const w = Math.floor(rect.width);
  const h = Math.floor(rect.height);
  if (w < 2 || h < 2) return null;
  const dpr = window.devicePixelRatio || 1;
  const bw = Math.round(w * dpr);
  const bh = Math.round(h * dpr);
  if (canvas.width !== bw) canvas.width = bw;
  if (canvas.height !== bh) canvas.height = bh;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

/** Placeholder text for an empty plot. */
export function drawEmpty(canvas: HTMLCanvasElement, message: string): void {
  const p = prepareCanvas(canvas);
  if (!p) return;
  const { ctx, w, h } = p;
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, w, h);
  const r = plotRect(w, h);
  ctx.strokeStyle = COLORS.grid;
  ctx.strokeRect(r.x + 0.5, r.y + 0.5, r.w, r.h);
  ctx.fillStyle = COLORS.faint;
  ctx.font = FONT_LABEL;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(message, r.x + r.w / 2, r.y + r.h / 2);
}

