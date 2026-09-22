// File exports, all written in the browser from the stored result:
// parameters (.json), results (.npz and .csv) and a PNG of the two plots.
import { drawDensity, drawHeatmap, type PlotData } from "./plots";

// ---- generic download ------------------------------------------------------

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function slug(text: string): string {
  return (
    text
      .normalize("NFKD")
      .replace(/[^\w\s-]/g, "")
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, "-")
      .slice(0, 48) || "run"
  );
}

// ---- .npy / .npz -----------------------------------------------------------

type NpyDtype = "<f8" | "<i8";

/** Encode a C-ordered array as NPY format 1.0 (little-endian). */
export function encodeNpy(values: ArrayLike<number>, shape: number[], dtype: NpyDtype): Uint8Array {
  const count = shape.reduce((a, b) => a * b, 1);
  if (count !== values.length) throw new Error(`npy: shape ${shape} does not match ${values.length} values`);
  const shapeText = shape.length === 1 ? `(${shape[0]},)` : `(${shape.join(", ")})`;
  let header = `{'descr': '${dtype}', 'fortran_order': False, 'shape': ${shapeText}, }`;
  const preamble = 10; // magic (6) + version (2) + header length (2)
  const total = Math.ceil((preamble + header.length + 1) / 64) * 64;
  header = header.padEnd(total - preamble - 1, " ") + "\n";
  const out = new Uint8Array(total + count * 8);
  out.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 0x01, 0x00], 0); // \x93NUMPY v1.0
  const view = new DataView(out.buffer);
  view.setUint16(8, header.length, true);
  for (let i = 0; i < header.length; i++) out[preamble + i] = header.charCodeAt(i);
  if (dtype === "<f8") {
    for (let i = 0; i < count; i++) view.setFloat64(total + i * 8, values[i], true);
  } else {
    for (let i = 0; i < count; i++) view.setBigInt64(total + i * 8, BigInt(values[i]), true);
  }
  return out;
}

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(data: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i++) c = CRC_TABLE[(c ^ data[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function dosDateTime(d: Date): { time: number; date: number } {
  const time = (d.getHours() << 11) | (d.getMinutes() << 5) | Math.floor(d.getSeconds() / 2);
  const date = ((Math.max(1980, d.getFullYear()) - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
  return { time, date };
}

/** Minimal ZIP writer, STORED (no compression), as np.savez produces. */
export function zipStored(files: { name: string; data: Uint8Array }[], when = new Date()): Blob {
  const enc = new TextEncoder();
  const { time, date } = dosDateTime(when);
  const parts: BlobPart[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const f of files) {
    const name = enc.encode(f.name);
    const crc = crc32(f.data);
    const local = new Uint8Array(30 + name.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);
    lv.setUint16(6, 0, true);
    lv.setUint16(8, 0, true); // stored
    lv.setUint16(10, time, true);
    lv.setUint16(12, date, true);
    lv.setUint32(14, crc, true);
    lv.setUint32(18, f.data.length, true);
    lv.setUint32(22, f.data.length, true);
    lv.setUint16(26, name.length, true);
    lv.setUint16(28, 0, true);
    local.set(name, 30);

    const cd = new Uint8Array(46 + name.length);
    const cv = new DataView(cd.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true);
    cv.setUint16(8, 0, true);
    cv.setUint16(10, 0, true);
    cv.setUint16(12, time, true);
    cv.setUint16(14, date, true);
    cv.setUint32(16, crc, true);
    cv.setUint32(20, f.data.length, true);
    cv.setUint32(24, f.data.length, true);
    cv.setUint16(28, name.length, true);
    cv.setUint32(42, offset, true);
    cd.set(name, 46);

    parts.push(local as BlobPart, f.data as BlobPart);
    central.push(cd);
    offset += local.length + f.data.length;
  }
  const cdSize = central.reduce((a, c) => a + c.length, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true);
  ev.setUint32(16, offset, true);
  return new Blob([...parts, ...(central as BlobPart[]), end as BlobPart], { type: "application/zip" });
}

export interface ResultBundle {
  data: PlotData;
  massInFrame: number[];
  metadata: Record<string, unknown>;
}

export function buildNpz(b: ResultBundle): Blob {
  const { data } = b;
  const sites = Array.from({ length: data.nSites }, (_, k) => data.N + k);
  const enc = new TextEncoder();
  return zipStored([
    { name: "psi.npy", data: encodeNpy(data.psi, [data.nT, data.nSites], "<f8") },
    { name: "times.npy", data: encodeNpy(data.times, [data.nT], "<f8") },
    { name: "sites.npy", data: encodeNpy(sites, [data.nSites], "<i8") },
    { name: "mass_in_frame.npy", data: encodeNpy(b.massInFrame, [data.nT], "<f8") },
    { name: "metadata.json", data: enc.encode(JSON.stringify(b.metadata, null, 2) + "\n") },
  ]);
}

/** CSV: header row of site indices, then one row per stored time sample. */
export function buildCsv(data: PlotData): Blob {
  const parts: string[] = [];
  const header = ["t \\ n"];
  for (let k = 0; k < data.nSites; k++) header.push(String(data.N + k));
  parts.push(header.join(",") + "\n");
  for (let i = 0; i < data.nT; i++) {
    const row: string[] = [String(data.times[i])];
    const base = i * data.nSites;
    for (let k = 0; k < data.nSites; k++) row.push(String(data.psi[base + k]));
    parts.push(row.join(",") + "\n");
  }
  return new Blob(parts, { type: "text/csv" });
}

// ---- PNG -------------------------------------------------------------------

export function buildPng(
  data: PlotData,
  frame: number,
  heatImage: HTMLCanvasElement,
  title: string,
  subtitle: string,
): Promise<Blob> {
  const W = 1400;
  const topH = 80;
  const densH = 440;
  const heatH = 620;
  const H = topH + densH + heatH + 20;
  const scale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = W * scale;
  canvas.height = H * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#1f2933";
  ctx.font = '600 20px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  ctx.fillText(title, 24, 18);
  ctx.font = '14px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  ctx.fillStyle = "#52606d";
  ctx.fillText(subtitle, 24, 48);

  ctx.save();
  ctx.translate(0, topH);
  drawDensity(ctx, W, densH, data, frame);
  ctx.restore();
  ctx.save();
  ctx.translate(0, topH + densH + 10);
  drawHeatmap(ctx, W, heatH, data, frame, heatImage);
  ctx.restore();

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("PNG encoding failed"))), "image/png");
  });
}
