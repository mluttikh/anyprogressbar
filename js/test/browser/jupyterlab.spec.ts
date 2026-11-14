// The widget in a real JupyterLab with a Python kernel, both from this project's
// environment (so the widgets' browser side is installed where the kernel runs, and bars are
// widgets from the start). One page runs the notebook; the tests follow it in order.

import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type Browser, expect, type Locator, type Page, test } from "@playwright/test";

const hasPython = spawnSync("uv", ["--version"]).status === 0;
// a whole JupyterLab with a kernel: slow to start on a busy CI machine
const LIMIT = process.env.CI ? 300_000 : 120_000;
test.describe.configure({ mode: "serial", retries: process.env.CI ? 1 : 0 });

const cells = [
  "import time\nfrom anyprogressbar import progress",
  // one slow item: the kernel says nothing for twelve seconds
  `with progress(total=4, desc="Slow") as bar:
    time.sleep(0.6)
    bar.update()
    time.sleep(12)
    bar.update(3)`,
  `from anyprogressbar import widget
print("HEARD", widget._heard, widget._disproved)`,
  `for epoch in progress(range(2), "Epochs"):
    for i in progress(range(5), f"Batches {epoch}"):
        time.sleep(0.3)
        if epoch == 1 and i == 2:
            raise KeyError("id")`,
  `for _ in progress(range(1000), "Endless"):
    time.sleep(0.1)`,
  // the terminal renderer, chosen in a notebook, whose output is no terminal
  `from anyprogressbar import set_renderer
set_renderer("terminal")
for _ in progress(range(40), "As text"):
    time.sleep(0.05)
set_renderer(None)`,
];

let server: ChildProcess | null = null;
let url = "";
let dir = "";
let page: Page;
const errors: string[] = [];

function notebook(): string {
  return JSON.stringify({
    nbformat: 4,
    nbformat_minor: 5,
    metadata: { kernelspec: { name: "python3", display_name: "Python 3", language: "python" } },
    cells: cells.map((source, i) => ({ cell_type: "code", id: `c${i}`, metadata: {}, execution_count: null, outputs: [], source })),
  });
}

async function startLab(port: number): Promise<void> {
  dir = mkdtempSync(join(tmpdir(), "apb-lab-"));
  writeFileSync(join(dir, "bars.ipynb"), notebook());
  url = `http://127.0.0.1:${port}/`;
  server = spawn(
    "uv",
    [
      "run", "jupyter", "lab", "--no-browser", `--port=${port}`, "--ip=127.0.0.1",
      "--IdentityProvider.token=", "--ServerApp.password=", `--ServerApp.root_dir=${dir}`,
      "--LabApp.news_url=", "--LabApp.check_for_updates_class=jupyterlab.NeverCheckForUpdate",
    ],
    {
      cwd: "..",
      stdio: "ignore",
      // settings (the theme a test switches), workspaces, config and kernels of the test's
      // own, never the user's: only this environment's Python kernel. Started from a
      // terminal that takes tab progress, as a kernel can be (it has Jupyter's environment).
      env: {
        ...process.env,
        TERM_PROGRAM: "ghostty",
        JUPYTER_DATA_DIR: join(dir, ".data"),
        JUPYTERLAB_SETTINGS_DIR: join(dir, ".settings"),
        JUPYTERLAB_WORKSPACES_DIR: join(dir, ".workspaces"),
        JUPYTER_CONFIG_DIR: join(dir, ".config"),
      },
    },
  );
  for (let i = 0; i < 240; i++) {
    try {
      if ((await fetch(`${url}api/status`)).ok) return;
    } catch {
      // not yet
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("JupyterLab did not start");
}

async function openNotebook(): Promise<void> {
  await page.goto(`${url}lab/tree/bars.ipynb`);
  await page.locator(".jp-Notebook").waitFor({ timeout: LIMIT / 2 });
  await expect(page.locator(".jp-Notebook-ExecutionIndicator[data-status='idle']")).toHaveCount(1, { timeout: LIMIT / 2 });
}

const cell = (n: number): Locator => page.locator(".jp-Notebook .jp-Cell").nth(n);
const output = (n: number): Locator => cell(n).locator(".jp-OutputArea");

/** Run cell `n` on its own; resolves once it has started (its prompt says so). */
async function runCell(n: number): Promise<void> {
  await cell(n).locator(".jp-InputArea-editor").click();
  await page.keyboard.press("Shift+Enter");
  await expect(cell(n).locator(".jp-InputPrompt")).toHaveText(/\[[*\d]+\]/, { timeout: 30_000 });
}

/** The bar's text as drawn: the widget's, or the plain HTML's. */
const said = (n: number) => output(n).locator("[role=progressbar] + *");

/** The colour of that text (in the plain HTML it is on a span inside). */
const colour = (text: Locator) =>
  text.evaluate((el) => getComputedStyle(el.firstElementChild ?? el).color);

async function menu(name: string, command: string): Promise<void> {
  await page.getByRole("menuitem", { name, exact: true }).click();
  await page.locator(`[data-command="${command}"]`).click();
}

/** Switch JupyterLab's theme from its Settings menu. */
async function setTheme(name: string): Promise<void> {
  await page.getByRole("menuitem", { name: "Settings", exact: true }).click();
  await page.locator(".lm-Menu-item[data-type='submenu']", { hasText: "Theme" }).first().hover();
  await page.locator(".lm-Menu-item[data-command='apputils:change-theme']", { hasText: name }).first().click();
}

test.describe("in JupyterLab", () => {
  test.skip(!hasPython, "needs uv and Python");

  test.beforeAll(async ({ browser }: { browser: Browser }, info) => {
    test.setTimeout(LIMIT);
    await startLab(8960 + info.workerIndex);
    page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    page.on("pageerror", (e) => errors.push(String(e)));
    await openNotebook();
  });

  test.afterAll(async () => {
    await page?.close();
    server?.kill();
  });

  test("while one slow item runs, the clock ticks in the page and a stall is said", async () => {
    test.setTimeout(LIMIT);
    // Run All; again if the kernel did not take it (the status may say idle before the
    // kernel takes requests on a busy machine)
    for (let attempt = 0; ; attempt++) {
      await menu("Run", "runmenu:run-all");
      try {
        await expect(output(1).locator(".apb")).toHaveCount(1, { timeout: 25_000 });
        break;
      } catch (err) {
        if (attempt >= 2) throw err;
      }
    }
    await expect(said(1)).toHaveText(/^1\/4 · 00:0\d/);
    // the kernel is asleep: only the page moves the clock on
    await expect(said(1)).toHaveText(/^1\/4 · 00:0[4-9](?! · no progress)/, { timeout: 10_000 });
    await expect(said(1)).toHaveText(/^1\/4 · 00:1\d · no progress for 10 s$/, { timeout: 12_000 });
    expect(await colour(said(1))).toBe("rgb(232, 147, 12)");
    await page.screenshot({ path: "test-results/shots/jupyterlab-stalled.png" });
  });

  test("when the work ends the widget gives way to plain HTML", async () => {
    test.setTimeout(LIMIT);
    await expect(output(1).locator(".apb")).toHaveCount(0, { timeout: 20_000 });
    await expect(said(1)).toHaveText(/^4\/4 · done in 00:1[23] · \d+(\.\d+)? it\/min$/);
    await expect(output(1).locator("[role=progressbar]")).toHaveAttribute("aria-valuenow", "100");
  });

  test("a failure in nested loops ends both bars as failed, with the reason", async () => {
    test.setTimeout(LIMIT);
    await expect(output(3).locator(".jp-RenderedText[data-mime-type='application/vnd.jupyter.stderr']")).toContainText("KeyError", { timeout: 30_000 });
    await expect(output(3).locator(".apb")).toHaveCount(0);
    // the inner loop that finished has left the tree (decision 0002); the one that failed stays
    const rows = output(3).locator("[role=progressbar]");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toHaveAccessibleName("Epochs");
    await expect(rows.nth(1)).toHaveAccessibleName("Batches 1");
    await expect(said(3).nth(0)).toHaveText(/^1\/2 · failed after 00:0\d: KeyError: 'id'$/);
    await expect(said(3).nth(1)).toHaveText(/^2\/5 · failed after 00:0\d: KeyError: 'id'$/);
    expect(await colour(said(3).nth(1))).toBe("rgb(224, 49, 49)");
  });

  test("the page told the kernel that it draws widgets", async () => {
    test.setTimeout(LIMIT);
    // under Run All the answer is read once every queued cell has ended (decision 0004), so
    // ask again now (Run All stops at the cell that raises: the endless one has not run)
    await expect(cell(3).locator(".jp-InputPrompt")).toHaveText(/\[\d+\]/, { timeout: 30_000 });
    await expect(page.locator(".jp-Notebook-ExecutionIndicator[data-status='idle']")).toHaveCount(1, { timeout: 30_000 });
    await runCell(2);
    await expect(output(2)).toContainText("HEARD True False", { timeout: 30_000 });
  });

  test("an interrupted loop ends as stopped", async () => {
    test.setTimeout(LIMIT);
    await runCell(4);
    await expect(output(4).locator(".apb")).toHaveCount(1, { timeout: 30_000 });
    await expect(said(4)).toHaveText(/^\d+\/1000 · 00:0[1-9]/, { timeout: 10_000 });
    await menu("Kernel", "kernelmenu:interrupt");
    await expect(output(4).locator(".apb")).toHaveCount(0, { timeout: 30_000 });
    await expect(said(4)).toHaveText(/^\d+\/1000 · stopped after 00:\d\d: interrupted$/);
    expect(await colour(said(4))).toBe("rgb(232, 147, 12)");
  });

  test("the terminal renderer writes one line over itself, and nothing a terminal alone reads", async () => {
    test.setTimeout(LIMIT);
    await runCell(5);
    const text = output(5).locator(".jp-OutputArea-output");
    // the spaces that wrote over longer lines stay after it: unseen
    await expect(text).toHaveText(/^As text 100% ▕█+▏ 40\/40 · done in 00:0[23] · \d+(\.\d+)? it\/s\s*$/, { timeout: 30_000 });
    expect(await text.innerText()).not.toContain("]9;4");
  });

  test("the saved notebook holds plain HTML and text, and no widget", async () => {
    test.setTimeout(LIMIT);
    await page.locator(".jp-Notebook").click();
    await page.keyboard.press("ControlOrMeta+s");
    await expect(page.locator(".jp-mod-dirty")).toHaveCount(0, { timeout: 15_000 });
    const saved = JSON.parse(readFileSync(join(dir, "bars.ipynb"), "utf8"));
    const kinds = (n: number) =>
      saved.cells[n].outputs.filter((o: any) => o.output_type === "display_data").map((o: any) => Object.keys(o.data).sort());
    expect(kinds(1)).toEqual([["text/html", "text/plain"]]);
    expect(kinds(3)).toEqual([["text/html", "text/plain"]]);
    expect([saved.cells[1].outputs[0].data["text/plain"]].flat().join("")).toMatch(/Slow .*4\/4 · done in 00:1[23]/);
    expect(JSON.stringify(saved)).not.toContain("widget-view");
    // opened again, it shows how the work ended
    await page.reload();
    await openNotebook();
    await expect(said(1)).toHaveText(/^4\/4 · done in 00:1[23]/);
    await expect(said(3).nth(0)).toHaveText(/failed after .*KeyError: 'id'$/);
    await expect(page.locator(".jp-Notebook")).not.toContainText(/Loading widget|Error displaying widget|Model not found/);
  });

  test("in the dark theme the bars' text is light", async () => {
    test.setTimeout(LIMIT);
    const light = (color: string) => {
      const [r, g, b] = color.match(/\d+/g)!.map(Number);
      return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    };
    const name = output(1).locator("[role=progressbar]").locator("xpath=preceding-sibling::*[2]");
    expect(light(await name.evaluate((n) => getComputedStyle(n).color))).toBeLessThan(0.3);
    await setTheme("JupyterLab Dark");
    await expect(page.locator("body")).toHaveAttribute("data-jp-theme-light", "false", { timeout: 15_000 });
    await expect.poll(async () => light(await name.evaluate((n) => getComputedStyle(n).color))).toBeGreaterThan(0.7);
    await expect(page.locator("#jupyterlab-splash")).toHaveCount(0, { timeout: 15_000 });
    await output(3).scrollIntoViewIfNeeded();
    await page.screenshot({ path: "test-results/shots/jupyterlab-dark.png" });
    await setTheme("JupyterLab Light");
    await expect(page.locator("body")).toHaveAttribute("data-jp-theme-light", "true", { timeout: 15_000 });
  });

  test("nothing went wrong in the page", () => {
    expect(errors).toEqual([]);
  });
});
