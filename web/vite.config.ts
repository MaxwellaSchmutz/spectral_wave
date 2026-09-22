import { defineConfig } from "vite";

// GitHub Pages serves the project at /spectral_wave/. BASE_PATH overrides it
// (e.g. BASE_PATH=/ for a root deployment). Every runtime URL in src/ is built
// from import.meta.env.BASE_URL, so the app works under any base.
function basePath(): string {
  const raw = process.env.BASE_PATH ?? "/spectral_wave/";
  const withLead = raw.startsWith("/") ? raw : `/${raw}`;
  return withLead.endsWith("/") ? withLead : `${withLead}/`;
}

export default defineConfig({
  base: basePath(),
  worker: {
    // Pyodide 314.x runs only in module workers.
    format: "es",
  },
  build: {
    target: "es2022",
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    strictPort: false,
  },
  preview: {
    port: 4173,
    strictPort: false,
  },
});
