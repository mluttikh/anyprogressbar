// The widget in marimo's live pages: an app (apps/bars.py) run headless, as an app
// (`marimo run`) and in the editor (`marimo edit`), its kernel running this project's Python
// package. marimo draws the widget itself, inside the cell's output.

import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { expect, type Locator, type Page, test } from "@playwright/test";

const hasPython = spawnSync("uv", ["--version"]).status === 0;
// a marimo app with a kernel: one retry on a busy CI machine
test.describe.configure({ mode: "serial", retries: process.env.CI ? 1 : 0 });

for (const [mode, base] of [["run", 2960], ["edit", 2970]] as const) {
  test.describe(`in marimo (${mode})`, () => {
    test.skip(!hasPython, "needs uv and Python");
    let server: ChildProcess | null = null;
    let url = "";
    let page: Page;
    const errors: string[] = [];

    /** The text beside the bar called `name`, as drawn: the widget's, or the plain HTML's. */
    const said = (name: string): Locator =>
      page.getByRole("progressbar", { name, exact: true }).locator("xpath=following-sibling::*[1]");

    test.beforeAll(async ({ browser }, info) => {
      test.setTimeout(120_000);
      const port = base + info.workerIndex;
      url = `http://127.0.0.1:${port}/`;
      // the editor runs the cells when the page opens only where `auto_instantiate` is set,
      // which marimo 0.25 no longer sets by default: a user's own config decided it. Set
      // through marimo's (private) environment override, which comes after the user's config.
      const env = {
        ...process.env,
        MARIMO_SKIP_UPDATE_CHECK: "1",
        _MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE: process.env.APB_MARIMO_AUTORUN ?? "true",
      };
      server = spawn(
        "uv",
        ["run", "marimo", mode, "js/test/browser/apps/bars.py", "--headless", "--port", String(port), "--no-token"],
        { cwd: "..", stdio: "ignore", env },
      );
      for (let i = 0; i < 240; i++) {
        try {
          if ((await fetch(url)).ok) break;
        } catch {
          // not yet
        }
        await new Promise((r) => setTimeout(r, 250));
      }
      page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
      page.on("pageerror", (e) => errors.push(String(e)));
    });

    test.afterAll(async () => {
      await page?.close();
      server?.kill();
    });

    test("while one slow item runs, the clock ticks in the page", async () => {
      test.setTimeout(120_000);
      await page.goto(url); // the cells run when the page connects
      await expect(page.locator(".apb")).toHaveCount(1, { timeout: 60_000 });
      await expect(said("Slow")).toHaveText(/^1\/4 · 00:0\d/);
      // the kernel is asleep: only the page moves the clock on
      await expect(said("Slow")).toHaveText(/^1\/4 · 00:0[3-5]/, { timeout: 8_000 });
      await page.screenshot({ path: `test-results/shots/marimo-${mode}-running.png` });
    });

    test("when the work ends the widget gives way to plain HTML", async () => {
      test.setTimeout(60_000);
      await expect(said("Slow")).toHaveText(/^4\/4 · done in 00:0[67]/, { timeout: 20_000 });
      await expect(page.getByRole("progressbar", { name: "Slow", exact: true })).toHaveAttribute("aria-valuenow", "100");
    });

    test("bars that failed are not left running", async () => {
      test.setTimeout(60_000);
      // the nested loops run, and fail; marimo puts the error of a cell that raises in place
      // of its output, bars and all
      const epochs = page.getByRole("progressbar", { name: "Epochs", exact: true });
      await expect(epochs).toHaveCount(1, { timeout: 15_000 });
      await expect(epochs).toHaveCount(0, { timeout: 15_000 });
      await expect(page.locator(".apb")).toHaveCount(0, { timeout: 15_000 });
      if (mode === "edit") {
        // the cell's console stays, and the bars are written there, above the traceback
        const console = page.locator(".console-output-area", { hasText: "failed after" });
        await expect(console).toContainText(/Epochs .*1\/2 · failed after 00:0\d: KeyError: 'id'/, { timeout: 15_000 });
        await expect(console).toContainText(/Batches 1 .*2\/5 · failed after 00:0\d: KeyError: 'id'/);
        await console.scrollIntoViewIfNeeded();
      }
      await page.screenshot({ path: `test-results/shots/marimo-${mode}-ended.png`, fullPage: true });
    });

    test("loops one after another in a cell keep their bars", async () => {
      test.setTimeout(60_000);
      const first = page.getByRole("progressbar", { name: "First", exact: true });
      const second = page.getByRole("progressbar", { name: "Second", exact: true });
      // while the second runs, as the widget, the first's record stays above it
      await expect(said("Second")).toHaveText(/^[1-7]\/8 · /, { timeout: 30_000 });
      await expect(first).toHaveAttribute("aria-valuenow", "100");
      await expect(said("First")).toHaveText(/^4\/4 · done in/);
      expect((await first.boundingBox())!.y).toBeLessThan((await second.boundingBox())!.y);
      await expect(said("Second")).toHaveText(/^8\/8 · done in/, { timeout: 15_000 });
      await expect(first).toHaveCount(1);
    });

    test("nothing went wrong in the page", () => {
      expect(errors).toEqual([]);
    });
  });
}
