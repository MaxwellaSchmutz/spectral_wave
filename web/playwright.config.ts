// Browser harness for the spectral_wave web port.
//
//   Local:  npm run build  (web/)  and  python web/scripts/native_reference.py  (repo root), then
//           npx playwright test            -> serves the ALREADY BUILT web/dist on 127.0.0.1:4317
//   Live:   SW_BASE_URL=https://maxwellaschmutz.github.io/spectral_wave/ npx playwright test
//           (no local server; parity cases whose revision differs from the deployed build are skipped
//           and reported as such)
import { defineConfig, devices } from "@playwright/test";

const PORT = 4317;
const live = process.env.SW_BASE_URL;
const baseURL = live ? (live.endsWith("/") ? live : `${live}/`) : `http://127.0.0.1:${PORT}/spectral_wave/`;

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts$/,
  // Each spec file shares one page (a Pyodide cold start per test would dominate the run).
  fullyParallel: false,
  workers: process.env.CI ? 1 : 2,
  retries: 0,
  forbidOnly: !!process.env.CI,
  // Cold starts download Pyodide + NumPy from the CDN; parity runs 34 cases x (n + 2n).
  timeout: 15 * 60_000,
  expect: { timeout: 30_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
    actionTimeout: 60_000,
    navigationTimeout: 180_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1400, height: 1000 } } },
    { name: "firefox", use: { ...devices["Desktop Firefox"], viewport: { width: 1400, height: 1000 } } },
  ],
  webServer: live
    ? undefined
    : {
        // Serves web/dist as built by `npm run build`; the tests never rebuild.
        command: `npx vite preview --host 127.0.0.1 --port ${PORT} --strictPort`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
