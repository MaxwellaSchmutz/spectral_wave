// Runs a Python script for the web build with the right interpreter.
//
//   node scripts/run-python.mjs <script relative to web/> [args...]
//
// Interpreter: $PYTHON if set, else the repo's .venv (Windows or POSIX layout)
// if present, else "python" on PATH. The script runs from the repository root,
// which is how the Python build tooling expects to be invoked.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(webDir, "..");

function pickPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  for (const rel of [".venv/Scripts/python.exe", ".venv/bin/python"]) {
    const candidate = resolve(repoRoot, rel);
    if (existsSync(candidate)) return candidate;
  }
  return "python";
}

const [script, ...args] = process.argv.slice(2);
if (!script) {
  console.error("usage: node scripts/run-python.mjs <script> [args...]");
  process.exit(2);
}

const python = pickPython();
const result = spawnSync(python, [resolve(webDir, script), ...args], {
  cwd: repoRoot,
  stdio: "inherit",
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
});
if (result.error) {
  console.error(`could not start Python (${python}): ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
