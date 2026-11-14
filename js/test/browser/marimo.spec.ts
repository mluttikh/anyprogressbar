// The widget in marimo's live page: an app (apps/bars.py) run headless, its kernel running
// this project's Python package. marimo draws the widget itself, inside the cell's output.

import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { expect, type Locator, type Page, test } from "@playwright/test";

const hasPython = spawnSync("uv", ["--version"]).status === 0;
// a marimo app with a kernel: one retry on a busy CI machine
test.describe.configure({ mode: "serial", retries: process.env.CI ? 1 : 0 });
let server: ChildProcess | null = null;
let url = "";
let page: Page;
const errors: string[] = [];

/** The text beside the bar called `name`, as drawn: the widget's, or the plain HTML's. */
const said = (name: string): Locator =>
  page.getByRole("progressbar", { name, exact: true }).locator("xpath=following-sibling::*[1]");

const colour = (text: Locator) =>
  text.evaluate((el) => getComputedStyle(el.firstElementChild ?? el).color);

test.describe("in marimo", () => {
  test.skip(!hasPython, "needs uv and Python");

  test.beforeAll(async ({ browser }, info) => {
    test.setTimeout(120_000);
    const port = 2960 + info.workerIndex;
    url = `http://127.0.0.1:${port}/`;
    server = spawn(
      "uv",
      ["run", "marimo", "run", "js/test/browser/apps/bars.py", "--headless", "--port", String(port), "--no-token"],
      { cwd: "..", stdio: "ignore" },
    );
    for (let i = 0; i < 240; i++) {
      try {
        if ((await fetch(url)).ok) break;
      } catch {
        // not yet
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    page = await browser.newPage({ viewport: { width: 1100, height: 800 } });
    page.on("pageerror", (e) => errors.push(String(e)));
  });

  test.afterAll(async () => {
    await page?.close();
    server?.kill();
  });

  test("while one slow item runs, the clock ticks in the page", async () => {
    test.setTimeout(120_000);
    await page.goto(url);
    await expect(page.locator(".apb")).toHaveCount(1, { timeout: 60_000 });
    await expect(said("Slow")).toHaveText(/^1\/4 · 00:0\d/);
    // the kernel is asleep: only the page moves the clock on
    await expect(said("Slow")).toHaveText(/^1\/4 · 00:0[3-5]/, { timeout: 8_000 });
    await page.screenshot({ path: "test-results/shots/marimo-running.png" });
  });

  test("when the work ends the widget gives way to plain HTML", async () => {
    test.setTimeout(60_000);
    await expect(said("Slow")).toHaveText(/^4\/4 · done in 00:0[67]/, { timeout: 20_000 });
    await expect(page.getByRole("progressbar", { name: "Slow", exact: true })).toHaveAttribute("aria-valuenow", "100");
  });

  test("a failure in nested loops ends both bars as failed, with the reason", async () => {
    // marimo puts a cell's error in place of its output, so the failed bars are not kept
    // (decision 0004, known limits); this fails until they are
    test.fail(true, "marimo replaces the output of a cell that raises");
    test.setTimeout(60_000);
    await expect(said("Epochs")).toHaveText(/^1\/2 · failed after 00:0\d: KeyError: 'id'$/, { timeout: 15_000 });
    await expect(said("Batches 1")).toHaveText(/^2\/5 · failed after 00:0\d: KeyError: 'id'$/);
    expect(await colour(said("Batches 1"))).toBe("rgb(224, 49, 49)");
    // no widget is left running
    await expect(page.locator(".apb")).toHaveCount(0);
    await page.screenshot({ path: "test-results/shots/marimo-ended.png", fullPage: true });
  });

  test("nothing went wrong in the page", () => {
    expect(errors).toEqual([]);
  });
});
