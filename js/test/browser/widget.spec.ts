// The widget's own module (src/widget.ts and widget.css) drawn in a page by the harness,
// which plays the kernel. The page's clock is Playwright's: time moves only when a test
// moves it, so what the widget says between two pictures can be checked to the second.

import { readFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";
import type { Bar } from "../../src/format";

// made by Python (tests/test_widget.py), as in test/format.test.ts
const cases: { name: string; bar: Bar; stats: string[] }[] = JSON.parse(
  readFileSync(new URL("../../../tests/fixtures/stats.json", import.meta.url), "utf8"),
);

const bar = (over: Partial<Bar> = {}): Bar => ({
  id: 1, desc: "Load", n: 10, total: 100, unit: "it", status: "running", elapsed: 10,
  rate: 1, remaining: 90, since_progress: 0, message: "", leave: true, metrics: {},
  children: [], ...over,
});

const show = (page: Page, tree: Bar | Record<string, never>) =>
  page.evaluate((t) => (window as any).apb.show(t), tree);
const send = (page: Page, tree: Bar) => page.evaluate((t) => (window as any).apb.send(t), tree);

interface Drawn {
  name: string;
  title: string;
  indent: string;
  percent: string;
  status: string;
  numbers: string;
  said: string; // the numbers' status: a stall is said in their colour
  width: number; // the fill's, in percent
  now: string | null;
  text: string | null;
}

/** The rows as drawn, in the document's order: four elements to a row. */
function drawn(page: Page): Promise<Drawn[]> {
  return page.evaluate(() => {
    const parts = [...document.querySelectorAll<HTMLElement>(".apb > *")];
    const out = [];
    for (let i = 0; i < parts.length; i += 4) {
      const [name, percent, track, numbers] = parts.slice(i, i + 4);
      out.push({
        name: name.textContent ?? "",
        title: name.title,
        indent: name.style.paddingLeft,
        percent: percent.textContent ?? "",
        status: track.dataset.status ?? "",
        numbers: numbers.textContent ?? "",
        said: numbers.dataset.status ?? "",
        width: parseFloat((track.firstElementChild as HTMLElement).style.width),
        now: track.getAttribute("aria-valuenow"),
        text: track.getAttribute("aria-valuetext"),
      });
    }
    return out;
  });
}

const numbers = async (page: Page) => (await drawn(page)).map((row) => row.numbers);

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: 0 });
  await page.goto("/test/browser/harness.html");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  await page.clock.pauseAt(10_000);
});

test("each bar is a row with the text Python makes for it", async ({ page }) => {
  for (const c of cases) {
    await show(page, c.bar);
    expect(await numbers(page), c.name).toEqual(c.stats);
  }
});

test("a row has the bar's name, percentage, fill and value for screen readers", async ({ page }) => {
  await show(page, bar({ desc: "Load files" }));
  const [row] = await drawn(page);
  expect(row).toMatchObject({
    name: "Load files", title: "Load files", percent: "10%", status: "running",
    width: 10, now: "10", text: "10/100, 00:10, about 2 min left, 1 it/s",
  });
  const track = page.getByRole("progressbar", { name: "Load files" });
  await expect(track).toHaveAttribute("aria-valuemin", "0");
  await expect(track).toHaveAttribute("aria-valuemax", "100");
  // the fill eases to its value, and takes that share of the track
  await expect
    .poll(() => track.evaluate((t) => (t.firstElementChild as HTMLElement).offsetWidth / (t as HTMLElement).offsetWidth))
    .toBeCloseTo(0.1, 2);
  // a bar without a name is still called something
  await show(page, bar({ desc: "" }));
  await expect(page.getByRole("progressbar", { name: "Progress" })).toHaveCount(1);
});

test("between pictures the clock ticks, the time left counts down, and a stall is said", async ({ page }) => {
  await show(page, bar());
  expect(await numbers(page)).toEqual(["10/100 · 00:10 · about 2 min left · 1 it/s"]);
  await page.clock.runFor(4_000);
  expect(await numbers(page)).toEqual(["10/100 · 00:14 · about 1 min left · 1 it/s"]);
  // the fill does not move without a value
  expect((await drawn(page))[0].width).toBe(10);
  await page.clock.runFor(41_000);
  const [stalled] = await drawn(page);
  expect(stalled.numbers).toBe("10/100 · 00:55 · no progress for 45 s");
  expect(stalled.said).toBe("stalled");
  await expect(page.locator(".apb-numbers")).toHaveCSS("color", "rgb(232, 147, 12)");
  // a picture counts from when it came
  await send(page, bar({ n: 11, elapsed: 56, remaining: 80 }));
  expect(await drawn(page)).toMatchObject([{ numbers: "11/100 · 00:56 · about 1 min left · 1 it/s", said: "running" }]);
  await page.clock.runFor(1_000);
  expect(await numbers(page)).toEqual(["11/100 · 00:57 · about 1 min left · 1 it/s"]);
});

test("a finished bar's clock stands still", async ({ page }) => {
  await show(page, bar({ n: 100, status: "done", elapsed: 50, rate: null, remaining: null }));
  await page.clock.runFor(60_000);
  expect(await numbers(page)).toEqual(["100/100 · done in 00:50 · 2 it/s"]);
});

test("without a total a block runs along the track and claims no value", async ({ page }) => {
  await show(page, bar({ total: null, n: 42, remaining: null }));
  const track = page.getByRole("progressbar");
  await expect(track).toHaveClass(/apb-moving/);
  expect(await track.getAttribute("aria-valuenow")).toBeNull();
  const [row] = await drawn(page);
  expect(row.percent).toBe("");
  expect(row.numbers).toBe("42 it · 00:10 · 1 it/s");
  await expect(track.locator(".apb-fill")).toHaveCSS("animation-name", "apb-ribs, apb-run");
  // finished, it is full and still
  await send(page, bar({ total: null, n: 50, status: "done", remaining: null }));
  await expect(track).not.toHaveClass(/apb-moving/);
  await expect(track).toHaveAttribute("aria-valuenow", "100");
  expect((await drawn(page))[0].width).toBe(100);
  await expect(track.locator(".apb-fill")).toHaveCSS("animation-name", "none");
});

test("each ending has its colour, and a failure and a stop say so in it", async ({ page }) => {
  const fill = page.locator(".apb-fill");
  const text = page.locator(".apb-numbers");
  await show(page, bar());
  await expect(fill).toHaveCSS("background-color", "rgb(28, 126, 214)");
  await expect(fill).toHaveCSS("animation-name", "apb-ribs");
  await send(page, bar({ n: 100, status: "done", elapsed: 50 }));
  await expect(fill).toHaveCSS("background-color", "rgb(47, 158, 68)");
  await expect(fill).toHaveCSS("animation-name", "none");
  await send(page, bar({ status: "failed", message: "ValueError: bad row" }));
  await expect(fill).toHaveCSS("background-color", "rgb(224, 49, 49)");
  await expect(text).toHaveText("10/100 · failed after 00:10: ValueError: bad row");
  await expect(text).toHaveCSS("color", "rgb(224, 49, 49)");
  await expect(text).toHaveCSS("font-weight", "600");
  await send(page, bar({ status: "stopped" }));
  await expect(fill).toHaveCSS("background-color", "rgb(232, 147, 12)");
  await expect(text).toHaveCSS("color", "rgb(232, 147, 12)");
});

test("children are indented rows under their parent, in the tree's order", async ({ page }) => {
  const child = (id: number, desc: string, over: Partial<Bar> = {}) =>
    bar({ id, desc, n: 1, total: 4, elapsed: 2, remaining: 6, ...over });
  const grand = child(4, "Rows", { status: "pending" });
  await show(page, bar({ desc: "Epochs", children: [child(2, "Batches 0", { children: [grand] }), child(3, "Batches 1", { status: "pending" })] }));
  // pending bars are not drawn
  expect((await drawn(page)).map((r) => [r.name, r.indent])).toEqual([["Epochs", "0px"], ["Batches 0", "16px"]]);
  // a row made later still goes in its place, not at the end
  await send(page, bar({ desc: "Epochs", children: [child(2, "Batches 0", { children: [{ ...grand, status: "running" }] }), child(3, "Batches 1")] }));
  expect((await drawn(page)).map((r) => [r.name, r.indent])).toEqual([["Epochs", "0px"], ["Batches 0", "16px"], ["Rows", "32px"], ["Batches 1", "16px"]]);
  await send(page, bar({ desc: "Epochs", children: [child(5, "Batches 2"), child(2, "Batches 0", { status: "done", n: 4 })] }));
  expect((await drawn(page)).map((r) => r.name)).toEqual(["Epochs", "Batches 2", "Batches 0"]);
  // a bar that is gone from the tree is gone from the page, all four parts of it
  await send(page, bar({ desc: "Epochs", children: [child(5, "Batches 2")] }));
  expect((await drawn(page)).map((r) => r.name)).toEqual(["Epochs", "Batches 2"]);
  await expect(page.locator(".apb > *")).toHaveCount(8);
  // each row's parts are on one line, and the columns line up
  const boxes = await page.locator(".apb > *").evaluateAll((parts) => parts.map((p) => p.getBoundingClientRect()));
  for (let i = 0; i < boxes.length; i += 4) {
    const middles = boxes.slice(i, i + 4).map((b) => b.top + b.height / 2);
    for (const m of middles) expect(Math.abs(m - middles[0])).toBeLessThan(2);
  }
  expect(boxes[2].left).toBe(boxes[6].left);
  expect(boxes[2].width).toBe(boxes[6].width);
});

test("an empty tree draws nothing, and the next picture draws it", async ({ page }) => {
  await show(page, {});
  await expect(page.locator(".apb > *")).toHaveCount(0);
  await send(page, bar());
  await expect(page.locator(".apb > *")).toHaveCount(4);
  await send(page, {} as Bar);
  await expect(page.locator(".apb > *")).toHaveCount(0);
});

test("it tells the kernel that it was drawn, once", async ({ page }) => {
  await show(page, bar());
  await send(page, bar({ n: 20 }));
  await page.clock.runFor(2_000);
  expect(await page.evaluate(() => (window as any).apb.sent)).toEqual([{ shown: true }]);
});

test("once its view is removed it stops listening and keeping time", async ({ page }) => {
  await show(page, bar());
  expect(await page.evaluate(() => (window as any).apb.listening())).toBe(1);
  await page.evaluate(() => (window as any).apb.close());
  expect(await page.evaluate(() => (window as any).apb.listening())).toBe(0);
  await page.clock.runFor(5_000);
  expect(await numbers(page)).toEqual(["10/100 · 00:10 · about 2 min left · 1 it/s"]);
});

test("a long name is cut short on screen and whole in its tooltip", async ({ page }) => {
  const long = "Reading every file in the archive of last year's measurements";
  await show(page, bar({ desc: long }));
  const name = page.locator(".apb-name");
  await expect(name).toHaveAttribute("title", long);
  await expect(name).toHaveCSS("text-overflow", "ellipsis");
  const width = await name.evaluate((n) => [n.clientWidth, n.scrollWidth]);
  expect(width[0]).toBeLessThanOrEqual(18 * 13);
  expect(width[1]).toBeGreaterThan(width[0]);
});

test("on a narrow page the bars fit without scrolling sideways", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 600 });
  await show(page, bar({ desc: "Epochs", metrics: { loss: "0.231", accuracy: "0.912" }, children: [bar({ id: 2, desc: "Batches" })] }));
  const fits = await page.evaluate(() => {
    const apb = document.querySelector(".apb")!;
    return [apb.scrollWidth <= apb.clientWidth, document.documentElement.scrollWidth <= 320];
  });
  expect(fits).toEqual([true, true]);
  // the track keeps its least width
  expect((await page.locator(".apb-track").first().boundingBox())!.width).toBeGreaterThan(59.9);
});

test("text takes the colour of the page it is on", async ({ page }) => {
  await page.evaluate(() => {
    document.body.style.background = "#111418";
    document.body.style.color = "rgb(230, 232, 235)";
  });
  await show(page, bar());
  await expect(page.locator(".apb-name")).toHaveCSS("color", "rgb(230, 232, 235)");
  await expect(page.locator(".apb-numbers")).toHaveCSS("color", "rgb(230, 232, 235)");
});

test("in VS Code the bars are on the editor's ground, in its text colour", async ({ page }) => {
  // VS Code's dark theme as its Jupyter extension leaves a widget's output: the editor's
  // colours as variables, and the widget on white, in black (ipywidgets' own colour)
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.textContent = `
      :root { --vscode-editor-foreground: rgb(204, 204, 204); }
      body { background: #1f1f1f; color: rgb(204, 204, 204); }
      .cell-output-ipywidget-background { background: #fff !important; }
      .jupyter-widgets { color: black; }`;
    document.head.appendChild(style);
    const cell = document.getElementById("cell")!;
    const output = document.createElement("div");
    output.className = "cell-output-ipywidget-background";
    cell.replaceWith(output);
    output.appendChild(cell);
    cell.className = "jupyter-widgets";
  });
  await show(page, bar());
  await expect(page.locator(".cell-output-ipywidget-background")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(page.locator(".apb-name")).toHaveCSS("color", "rgb(204, 204, 204)");
  await expect(page.locator(".apb-numbers")).toHaveCSS("color", "rgb(204, 204, 204)");
});

test("other widgets in VS Code keep the white ground it gives them", async ({ page }) => {
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.textContent = ".cell-output-ipywidget-background { background: #fff !important; }";
    document.head.appendChild(style);
    const other = document.createElement("div");
    other.className = "cell-output-ipywidget-background";
    other.id = "other";
    other.textContent = "another widget";
    document.body.appendChild(other);
  });
  await show(page, bar());
  await expect(page.locator("#other")).toHaveCSS("background-color", "rgb(255, 255, 255)");
});

test("with reduced motion asked for, nothing moves", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await show(page, bar());
  const fill = page.locator(".apb-fill");
  await expect(fill).toHaveCSS("animation-name", "none");
  await expect(fill).toHaveCSS("transition-duration", "0s");
  await send(page, bar({ total: null, remaining: null }));
  await expect(fill).toHaveCSS("animation-name", "none");
  const share = await page.locator(".apb-track").evaluate((t) => (t.firstElementChild as HTMLElement).offsetWidth / (t as HTMLElement).offsetWidth);
  expect(share).toBeCloseTo(1, 2);
});
