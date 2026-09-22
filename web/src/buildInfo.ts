// Build-time facts written by web/scripts/build_py_archive.py: the Python
// archive's name and hash, the pinned Pyodide URL, the preset table (exported
// by spectral.maxwell.presets) and the build-time quadrature validation.
import raw from "./generated/build-info.json";
import type { BuildInfo } from "./types";

export const buildInfo = raw as unknown as BuildInfo;

/** URL of a file under web/public, honouring the deployment base path. */
export function assetUrl(path: string): string {
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
}
