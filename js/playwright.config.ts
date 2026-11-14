import { defineConfig } from "@playwright/test";

// Browser tests (npm run test:browser): the widget's own module in a page, in Chromium,
// Firefox and WebKit; then the widget in a real JupyterLab and a real marimo, and the
// documentation's replays, in Chromium. esbuild bundles the harness and serves js/.

const HOSTS = ["**/jupyterlab.spec.ts", "**/marimo.spec.ts", "**/docs.spec.ts"];

export default defineConfig({
  testDir: "test/browser",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4193",
    viewport: { width: 900, height: 600 },
    // what a failure on CI looked like (uploaded with the test results)
    screenshot: process.env.CI ? "only-on-failure" : "off",
    trace: process.env.CI ? "retain-on-failure" : "off",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" }, testIgnore: HOSTS },
    { name: "firefox", use: { browserName: "firefox" }, testIgnore: HOSTS },
    { name: "webkit", use: { browserName: "webkit" }, testIgnore: HOSTS },
    // notebooks start servers and kernels: after the rest, which would slow them down
    {
      name: "notebooks",
      use: { browserName: "chromium" },
      testMatch: HOSTS,
      dependencies: ["chromium", "firefox", "webkit"],
    },
  ],
  webServer: [
    {
      command:
        "npx esbuild test/browser/harness.ts --bundle --format=esm --outdir=test/browser/dist --servedir=. --serve=127.0.0.1:4193",
      url: "http://127.0.0.1:4193/test/browser/harness.html",
      reuseExistingServer: !process.env.CI,
    },
    // the built documentation (docs.spec.ts), as it is published
    {
      command: "npx esbuild --servedir=../site --serve=127.0.0.1:4194",
      url: "http://127.0.0.1:4194/",
      reuseExistingServer: !process.env.CI,
      ignoreHTTPSErrors: true,
    },
  ],
});
