// The parameter form: controls, their plain-language help, reading the
// canonical params (syntax only; Python validates the meaning) and showing
// per-field messages.
import { h, setText } from "./dom";
import { LiteralError, formatPotential, parsePotential } from "./literal";
import type { Direction, GaussianFields, Params, Preset } from "./types";

export type Slot =
  | "L" | "a" | "N" | "M" | "j_sites" | "V_sites" | "interval" | "mode"
  | "E0" | "sigma_E" | "direction" | "n_init" | "t_min" | "t_max" | "n_t"
  | "n_quad" | "outer_sign" | "threshold_buffer";

const SLOTS: Slot[] = [
  "L", "a", "N", "M", "j_sites", "V_sites", "interval", "mode", "E0", "sigma_E",
  "direction", "n_init", "t_min", "t_max", "n_t", "n_quad", "outer_sign", "threshold_buffer",
];

type Input = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

export interface FormEls {
  root: HTMLElement;
  inputs: Record<string, Input>;
  errors: Record<Slot, HTMLElement>;
  gaussianBox: HTMLElement;
  windowNote: HTMLElement;
}

let uid = 0;

function field(
  slot: Slot,
  key: string,
  label: string,
  help: string,
  input: Input,
  errors: Partial<Record<Slot, HTMLElement>>,
  extraClass = "",
): HTMLElement {
  const id = `f-${key}-${++uid}`;
  input.id = id;
  input.dataset.testid = `input-${key}`;
  input.name = key;
  const helpEl = h("p", { class: "help", id: `${id}-help` }, help);
  let err = errors[slot];
  const wrap = h("div", { class: `field ${extraClass}`.trim(), "data-slot": slot },
    h("label", { for: id }, label), input, helpEl);
  if (!err) {
    err = h("p", { class: "field-error", id: `err-${slot}`, testid: `error-${slot}`, "aria-live": "polite" });
    errors[slot] = err;
    wrap.append(err);
  }
  input.setAttribute("aria-describedby", `${id}-help ${err.id}`);
  return wrap;
}

function text(inputmode: "decimal" | "numeric" | "text" = "decimal"): HTMLInputElement {
  return h("input", { type: "text", inputmode, autocomplete: "off", spellcheck: "false" });
}

function select(options: [string, string][]): HTMLSelectElement {
  const s = h("select", {});
  for (const [value, label] of options) s.append(h("option", { value }, label));
  return s;
}

export function buildForm(): FormEls {
  const errors: Partial<Record<Slot, HTMLElement>> = {};
  const inputs: Record<string, Input> = {};
  const mk = (slot: Slot, key: string, label: string, help: string, input: Input, cls = "") => {
    inputs[key] = input;
    return field(slot, key, label, help, input, errors, cls);
  };

  const vArea = h("textarea", { rows: 3, spellcheck: "false", autocomplete: "off", class: "mono" });

  // interval: two inputs sharing one message slot
  const lo = text();
  const hi = text();
  inputs.interval_lo = lo;
  inputs.interval_hi = hi;
  lo.id = `f-interval_lo-${++uid}`;
  hi.id = `f-interval_hi-${++uid}`;
  lo.dataset.testid = "input-interval_lo";
  hi.dataset.testid = "input-interval_hi";
  lo.name = "interval_lo";
  hi.name = "interval_hi";
  const intervalErr = h("p", { class: "field-error", id: "err-interval", testid: "error-interval", "aria-live": "polite" });
  errors.interval = intervalErr;
  const intervalHelp = h("p", { class: "help", id: "help-interval" },
    "Energies the packet is built from. Must lie inside the band shared by all channels, " +
    "|E| < 2·min(a) minus the threshold buffer.");
  for (const el of [lo, hi]) el.setAttribute("aria-describedby", "help-interval err-interval");
  const intervalField = h("div", { class: "field", "data-slot": "interval" },
    h("span", { class: "label", id: "label-interval" }, "Energy interval [E_lo, E_hi]"),
    h("div", { class: "pair" },
      h("label", { for: lo.id, class: "sub" }, "from"), lo,
      h("label", { for: hi.id, class: "sub" }, "to"), hi),
    intervalHelp, intervalErr);

  const modeSel = select([["gaussian", "Gaussian packet"], ["schober_window", "Schober window (fixed f)"]]);
  const dirSel = select([["right", "right-moving (1, 0)"], ["left", "left-moving (0, 1)"], ["balanced", "balanced (1, 1)"]]);
  const outerSel = select([["1", "+1  (retarded / outgoing)"], ["-1", "−1"]]);

  const windowNote = h("p", { class: "note", testid: "window-note", role: "note" },
    "Schober window: f is fixed. Channel 1 is 1 on [0.4, 0.6] for both directions, channel 2 is 1 on " +
    "[−0.7, −0.5] for σ = + only, and the energy integral runs window by window. The Gaussian settings " +
    "below do not apply in this mode. Requires L = 2.");

  const gaussianBox = h("div", { class: "subgroup", testid: "gaussian-settings" },
    mk("E0", "E0", "Centre energy E₀", "Energy at the middle of the Gaussian profile.", text()),
    mk("sigma_E", "sigma_E", "Energy width σ_E",
      "Narrow → long packet that keeps its shape; wide → short packet that spreads quickly. Must be > 0.", text()),
    mk("direction", "direction", "Direction",
      "Which way the packet moves. Balanced launches both, so it splits into two packets moving apart.", dirSel),
    mk("n_init", "n_init", "Start site n_init", "Lattice site where the packet is centred at t = 0.", text("numeric")),
  );

  const group = (title: string, testid: string, ...kids: HTMLElement[]) =>
    h("fieldset", { class: "group", testid }, h("legend", {}, title), ...kids);

  const root = h("div", { class: "form" },
    group("Lattice and channels", "group-lattice",
      h("div", { class: "row2" },
        mk("L", "L", "Channels L", "Number of parallel channels per site (1 to 6).", text("numeric")),
        mk("a", "a", "Hoppings a", "One per channel, comma-separated, largest first: a₁ ≥ a₂ ≥ … > 0.", text())),
      h("div", { class: "row2" },
        mk("N", "N", "First site N", "Leftmost site computed and shown.", text("numeric")),
        mk("M", "M", "Last site M", "Rightmost site. A packet that runs past N or M leaves the picture.", text("numeric")))),
    group("Potential", "group-potential",
      mk("j_sites", "j_sites", "Potential sites",
        "Sites that carry a potential, comma-separated, increasing. Leave empty for a free lattice.", text("text")),
      mk("V_sites", "V_sites", "Potential matrices V(j)",
        "One L×L Hermitian matrix per site, in the desktop syntax: [[[0.6]]] for one scalar site, " +
        "[[[0.40, 0.25j], [-0.25j, -0.20]]] for a complex 2×2. Use j for imaginary parts; [] for none. " +
        "Enter starts a new line here; Ctrl+Enter computes.", vArea)),
    group("Energy and packet", "group-energy",
      intervalField,
      mk("mode", "amplitude_mode", "Amplitude mode",
        "Gaussian: a bell-shaped energy profile set below. Schober window: his fixed step-function f.", modeSel),
      windowNote,
      gaussianBox),
    group("Time", "group-time",
      h("div", { class: "row3" },
        mk("t_min", "t_min", "t start", "May be negative.", text()),
        mk("t_max", "t_max", "t end", "Must exceed t start.", text()),
        mk("n_t", "n_t", "Frames", "Stored time samples, 2 to 2000.", text("numeric")))),
    group("Numerics", "group-numerics",
      mk("n_quad", "n_quad", "Quadrature nodes n_quad",
        "Energy nodes for the integral. Every result is re-checked at twice this number; if the two disagree " +
        "the node count is raised and reported, or the run is refused.", text("numeric")),
      mk("outer_sign", "outer_sign", "Outer branch",
        "Which of the two exact eigenbases the final sum uses. With a potential they give different, " +
        "equally correct pictures (they differ by the scattering matrix).", outerSel),
      mk("threshold_buffer", "threshold_buffer", "Threshold buffer",
        "How far the energy interval must stay inside the band edges ±2·min(a).", text())),
  );

  return { root, inputs, errors: errors as Record<Slot, HTMLElement>, gaussianBox, windowNote };
}

// ---- params <-> form ------------------------------------------------------

function num(x: number): string {
  return Object.is(x, -0) ? "0" : String(x);
}

/** The desktop's Gaussian field defaults, used when a window preset brings none. */
export const DESKTOP_GAUSSIAN: GaussianFields = { E0: 0.5, sigma_E: 0.1, direction: "balanced", n_init: 0 };

const DIRECTIONS: Direction[] = ["right", "left", "balanced"];

/**
 * Gaussian fields to show for a preset: its own amplitude when it is Gaussian,
 * else the preset's form_gaussian (per field, when well-formed), else the
 * desktop defaults. Never the previously viewed preset's values.
 */
export function gaussianFieldsFor(preset: Pick<Preset, "params" | "form_gaussian">): GaussianFields {
  const amp = preset.params.amplitude;
  if (amp.mode === "gaussian") {
    return { E0: amp.E0, sigma_E: amp.sigma_E, direction: amp.direction, n_init: amp.n_init };
  }
  const g = (preset.form_gaussian ?? {}) as Partial<Record<keyof GaussianFields, unknown>>;
  const finite = (x: unknown, fallback: number) => (typeof x === "number" && Number.isFinite(x) ? x : fallback);
  return {
    E0: finite(g.E0, DESKTOP_GAUSSIAN.E0),
    sigma_E: finite(g.sigma_E, DESKTOP_GAUSSIAN.sigma_E),
    direction: DIRECTIONS.includes(g.direction as Direction) ? (g.direction as Direction) : DESKTOP_GAUSSIAN.direction,
    n_init: Number.isInteger(g.n_init) ? (g.n_init as number) : DESKTOP_GAUSSIAN.n_init,
  };
}

export function fillForm(f: FormEls, p: Params, gaussian?: Preset["form_gaussian"]): void {
  const i = f.inputs;
  i.L.value = num(p.L);
  i.a.value = p.a.map(num).join(", ");
  i.N.value = num(p.N);
  i.M.value = num(p.M);
  i.j_sites.value = p.j_sites.map(num).join(", ");
  i.V_sites.value = formatPotential(p.V_sites);
  i.interval_lo.value = num(p.interval[0]);
  i.interval_hi.value = num(p.interval[1]);
  i.t_min.value = num(p.times.t_min);
  i.t_max.value = num(p.times.t_max);
  i.n_t.value = num(p.times.n_t);
  i.n_quad.value = num(p.n_quad);
  i.outer_sign.value = String(p.outer_sign);
  i.threshold_buffer.value = num(p.threshold_buffer);
  i.amplitude_mode.value = p.amplitude.mode;
  const g = gaussianFieldsFor({ params: p, form_gaussian: gaussian });
  i.E0.value = num(g.E0);
  i.sigma_E.value = num(g.sigma_E);
  i.direction.value = g.direction;
  i.n_init.value = num(g.n_init);
}

const NUMBER_RE = /^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/;

class FieldError extends Error {
  constructor(public slot: Slot, message: string) {
    super(message);
  }
}

function parseNum(slot: Slot, label: string, raw: string, integer = false): number {
  const t = raw.trim().replace(/^−/, "-");
  if (t === "") throw new FieldError(slot, `${label}: enter a number.`);
  if (!NUMBER_RE.test(t)) throw new FieldError(slot, `${label}: "${t.slice(0, 40)}" is not a number.`);
  const v = Number(t);
  if (!Number.isFinite(v)) throw new FieldError(slot, `${label}: ${t.slice(0, 40)} is too large.`);
  if (integer && !Number.isInteger(v)) throw new FieldError(slot, `${label}: must be a whole number.`);
  return v;
}

function parseList(slot: Slot, label: string, raw: string, integer: boolean): number[] {
  const t = raw.trim();
  if (t === "") return [];
  return t
    .split(/[,\s]+/)
    .filter((s) => s !== "")
    .map((s, k) => parseNum(slot, `${label}, entry ${k + 1}`, s, integer));
}

export interface ReadResult {
  params: Params | null;
  errors: Partial<Record<Slot, string>>;
}

/** Read the form into canonical params. Only syntax is checked here. */
export function readForm(f: FormEls): ReadResult {
  const i = f.inputs;
  const errors: Partial<Record<Slot, string>> = {};
  const attempt = <T>(fn: () => T): T | undefined => {
    try {
      return fn();
    } catch (e) {
      if (e instanceof FieldError) {
        if (!errors[e.slot]) errors[e.slot] = e.message;
        return undefined;
      }
      throw e;
    }
  };

  const L = attempt(() => parseNum("L", "Channels L", i.L.value, true));
  const a = attempt(() => parseList("a", "Hoppings a", i.a.value, false));
  const N = attempt(() => parseNum("N", "First site N", i.N.value, true));
  const M = attempt(() => parseNum("M", "Last site M", i.M.value, true));
  const j = attempt(() => parseList("j_sites", "Potential sites", i.j_sites.value, true));
  let V: Params["V_sites"] | undefined;
  try {
    V = parsePotential(i.V_sites.value);
  } catch (e) {
    if (e instanceof LiteralError) errors.V_sites = `Potential matrices: ${e.message}.`;
    else throw e;
  }
  if (V && j && V.length !== j.length && V.length > 0) {
    errors.V_sites = `Potential matrices: ${V.length} matri${V.length === 1 ? "x" : "ces"} given for ${j.length} potential site${j.length === 1 ? "" : "s"}.`;
  } else if (V && j && V.length === 0 && j.length > 0) {
    errors.V_sites = `Potential matrices: enter one matrix for each of the ${j.length} potential site${j.length === 1 ? "" : "s"}.`;
  }
  const lo = attempt(() => parseNum("interval", "Energy interval (from)", i.interval_lo.value));
  const hi = attempt(() => parseNum("interval", "Energy interval (to)", i.interval_hi.value));
  const tMin = attempt(() => parseNum("t_min", "t start", i.t_min.value));
  const tMax = attempt(() => parseNum("t_max", "t end", i.t_max.value));
  const nT = attempt(() => parseNum("n_t", "Frames", i.n_t.value, true));
  const nQuad = attempt(() => parseNum("n_quad", "Quadrature nodes", i.n_quad.value, true));
  const buffer = attempt(() => parseNum("threshold_buffer", "Threshold buffer", i.threshold_buffer.value));
  const outer = i.outer_sign.value === "-1" ? -1 : 1;

  let amplitude: Params["amplitude"] | undefined;
  if (i.amplitude_mode.value === "schober_window") {
    amplitude = { mode: "schober_window" };
  } else {
    const E0 = attempt(() => parseNum("E0", "Centre energy E₀", i.E0.value));
    const sigma = attempt(() => parseNum("sigma_E", "Energy width σ_E", i.sigma_E.value));
    const nInit = attempt(() => parseNum("n_init", "Start site", i.n_init.value, true));
    if (E0 !== undefined && sigma !== undefined && nInit !== undefined) {
      amplitude = { mode: "gaussian", E0, sigma_E: sigma, direction: i.direction.value as Direction, n_init: nInit };
    }
  }

  if (Object.keys(errors).length > 0) return { params: null, errors };
  const params: Params = {
    L: L!, a: a!, N: N!, M: M!, j_sites: j!, V_sites: V!,
    interval: [lo!, hi!],
    times: { t_min: tMin!, t_max: tMax!, n_t: nT! },
    n_quad: nQuad!,
    outer_sign: outer,
    threshold_buffer: buffer!,
    amplitude: amplitude!,
  };
  return { params, errors };
}

export function clearErrors(f: FormEls): void {
  for (const s of SLOTS) {
    setText(f.errors[s], "");
    f.errors[s].closest(".field")?.classList.remove("invalid");
  }
}

export function showErrors(f: FormEls, errors: Partial<Record<Slot, string>>): void {
  for (const [slot, msg] of Object.entries(errors) as [Slot, string][]) {
    setText(f.errors[slot], msg);
    f.errors[slot].closest(".field")?.classList.add("invalid");
  }
}

/**
 * Map a field name reported by Python (e.g. "V_sites[0][1][0]",
 * "times.n_t", "amplitude.sigma_E", "interval") to the form slot showing it.
 */
export function slotForPythonField(field: string | null | undefined): Slot | null {
  if (!field) return null;
  const clean = field.replace(/^params\./, "").replace(/\[[^\]]*\]/g, "");
  const parts = clean.split(".").filter(Boolean);
  const candidates = [clean, parts[parts.length - 1], parts[0]];
  const aliases: Record<string, Slot> = {
    amplitude: "mode", "amplitude.mode": "mode", times: "t_max", interval_lo: "interval", interval_hi: "interval",
    E_lo: "interval", E_hi: "interval", E_segments: "interval", sigma: "sigma_E", outer: "outer_sign",
  };
  for (const c of candidates) {
    if (!c) continue;
    if (aliases[c]) return aliases[c];
    if ((SLOTS as string[]).includes(c)) return c as Slot;
    if (c === "mode") return "mode";
  }
  return null;
}
