// The built documentation (site/, from `uv run python scripts/build_docs.py`): the home
// page plays a recorded run again through the widget's own module, and the pages' bars,
// which are the plain HTML a notebook stores, fit a phone's width.

import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";

const built = existsSync(new URL("../../../site/index.html", import.meta.url));
const SITE = "http://127.0.0.1:4194/";
// the pages with bars in them
const PAGES = ["", "tutorials/first-bar.html", "tutorials/functions.html", "how-to/values.html", "how-to/totals.html", "how-to/endings.html", "how-to/nested.html"];

test.describe("the documentation", () => {
  // CI builds the site before these run; a checkout need not have
  test.skip(!built && !process.env.CI, "build the site first: uv run python scripts/build_docs.py");

  test("the home page plays a run again through the widget", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(SITE);
    const replay = page.locator(".apb-replay");
    await replay.scrollIntoViewIfNeeded();
    // the widget takes the place of the finished picture, and its clock moves
    await expect(replay.locator(".apb")).toHaveCount(1, { timeout: 10_000 });
    const first = await replay.locator(".apb-numbers").first().innerText();
    await expect(replay.locator(".apb-numbers").first()).not.toHaveText(first, { timeout: 5_000 });
    // at the end of the recording it can be played again
    const again = replay.getByRole("button", { name: "Play again" });
    await expect(again).toBeVisible({ timeout: 15_000 });
    await expect(replay.getByRole("progressbar").first()).toHaveAttribute("aria-valuenow", "100");
    await again.click();
    await expect(again).toHaveCount(0);
    await expect(replay.locator(".apb")).toHaveCount(1);
    expect(errors).toEqual([]);
  });

  test("on a phone the bars in the pages fit without scrolling sideways", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    for (const path of PAGES) {
      await page.goto(SITE + path);
      const bars = page.getByRole("progressbar");
      expect(await bars.count(), path).toBeGreaterThan(0);
      // each grid of bars is no wider than the room it has
      const over = await bars.evaluateAll((tracks) =>
        [...new Set(tracks.map((t) => t.parentElement!))]
          .filter((grid) => grid.scrollWidth > grid.clientWidth + 1)
          .map((grid) => `${grid.scrollWidth} > ${grid.clientWidth}: ${grid.textContent!.slice(0, 60)}`),
      );
      expect(over, path).toEqual([]);
      for (const track of await bars.all()) {
        expect((await track.boundingBox())!.width, path).toBeGreaterThan(59);
      }
    }
  });
});
