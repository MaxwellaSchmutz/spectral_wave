// Shared shapes for the page, the worker and the generated build info.
// They mirror the interface contract (canonical params, bridge meta, worker
// protocol). Python owns validation; these types only describe the JSON.

/** Complex number in structured form: [real, imaginary]. */
export type Complex = [number, number];

export type Direction = "right" | "left" | "balanced";

export interface GaussianAmplitude {
  mode: "gaussian";
  E0: number;
  sigma_E: number;
  direction: Direction;
  n_init: number;
}

export interface WindowAmplitude {
  mode: "schober_window";
}

export type Amplitude = GaussianAmplitude | WindowAmplitude;

/** Canonical params dict (contract section 2). */
export interface Params {
  L: number;
  a: number[];
  N: number;
  M: number;
  j_sites: number[];
  /** K x L x L complex entries. */
  V_sites: Complex[][][];
  interval: [number, number];
  times: { t_min: number; t_max: number; n_t: number };
  n_quad: number;
  outer_sign: 1 | -1;
  threshold_buffer: number;
  amplitude: Amplitude;
}

/** The Gaussian form fields (the amplitude minus its mode). */
export type GaussianFields = Omit<GaussianAmplitude, "mode">;

export interface Preset {
  id: string;
  name: string;
  description: string;
  params: Params;
  /**
   * Values for the (unused) Gaussian fields of a window-mode preset, so they
   * never carry over from the previously viewed preset. Optional: absent in
   * older build info, where the desktop defaults apply.
   */
  form_gaussian?: Partial<GaussianFields> | null;
}

export interface QuadratureRecord {
  source_revision: string;
  requested_n_quad: number;
  used_n_quad: number;
  check_n_quad: number | null;
  discrepancy_rel_peak: number | null;
  tolerance: number;
  status: string;
}

export interface BuildInfo {
  sourceRevision: string;
  archive: { file: string; sha256: string; bytes: number };
  pyodide: { version: string; indexURL: string };
  expected: { python: string; numpy: string };
  presets: Preset[];
  presetValidation: Record<string, QuadratureRecord>;
}

export type ErrorKind =
  | "invalid_input"
  | "over_budget"
  | "unresolved"
  | "nonfinite"
  | "internal"
  | "runtime";

export interface BridgeError {
  kind: ErrorKind;
  field: string | null;
  message: string;
}

export interface Quadrature {
  rule: string;
  requested_n_quad: number;
  used_n_quad: number;
  check_n_quad: number | null;
  discrepancy_rel_peak: number | null;
  tolerance: number;
  status: "verified" | "refined" | "cached" | string;
  segments: [number, number][] | null;
  interval_used: [number, number];
  threshold_buffer: number;
}

export interface SuccessMeta {
  ok: true;
  shape: [number, number];
  dtype: string;
  sites: { N: number; M: number };
  times: { t_min: number; t_max: number; n_t: number };
  mass_in_frame: number[];
  quadrature: Quadrature;
  timing_ms: Record<string, number>;
  memory_estimate_bytes: number;
  source_revision: string;
  runtime: { python: string; numpy: string; [k: string]: string };
  config_key: string;
  warnings: string[];
}

export interface FailureMeta {
  ok: false;
  error: BridgeError;
}

export type Meta = SuccessMeta | FailureMeta;

export interface Estimate {
  ok: boolean;
  bytes_peak?: number;
  bytes_result?: number;
  limits?: Record<string, number>;
  error?: BridgeError;
}

export interface RuntimeInfo {
  pyodide: string;
  python: string;
  numpy: string;
}

// ---- worker protocol (contract section 5) --------------------------------

export type ToWorker =
  | { type: "init" }
  | { type: "run"; id: number; params: Params; cachedValidation?: Record<string, QuadratureRecord> }
  | { type: "estimate"; id: number; params: Params };

export type FromWorker =
  | { type: "stage"; id?: number; stage: string; detail: string }
  | { type: "ready"; runtime: RuntimeInfo; sourceRevision: string }
  | { type: "result"; id: number; meta: Meta; psi: ArrayBuffer | null }
  | { type: "estimate"; id: number; result: Estimate }
  | { type: "error"; id?: number; kind: ErrorKind; field?: string | null; message: string };
