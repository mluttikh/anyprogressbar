// The text beside a bar must be the same in the browser as in Python: the cases in
// tests/fixtures/stats.json are made by Python (tests/test_widget.py).
import { describe, expect, it } from "vitest";
import cases from "../../tests/fixtures/stats.json";
import { type Bar, later, rows, stalled, stats } from "../src/format";

describe("the text beside a bar", () => {
  for (const c of cases as { name: string; bar: Bar; stats: string[]; stalled: boolean[] }[]) {
    it(c.name, () => {
      const drawn = rows(c.bar);
      expect(drawn.map(({ bar }) => stats(bar))).toEqual(c.stats);
      expect(drawn.map(({ bar }) => stalled(bar))).toEqual(c.stalled);
    });
  }
});

describe("keeping time between pictures", () => {
  const bar: Bar = {
    id: 1, desc: "Load", n: 10, total: 100, unit: "it", status: "running", elapsed: 10,
    rate: 1, remaining: 90, since_progress: 0, message: "", leave: true, metrics: {},
    children: [{
      id: 2, desc: "inner", n: 5, total: 5, unit: "it", status: "done", elapsed: 3,
      rate: null, remaining: null, since_progress: 0, message: "", leave: true, metrics: {},
      children: [],
    }],
  };

  it("moves running clocks on and leaves finished bars alone", () => {
    const after = later(bar, 4);
    expect(stats(after)).toBe("10/100 · 00:14 · about 1 min left · 1 it/s");
    expect(after.remaining).toBe(86);
    expect(after.children[0]).toEqual(bar.children[0]);
    expect(stats(bar)).toBe("10/100 · 00:10 · about 2 min left · 1 it/s"); // not changed
  });

  it("says a stall once nothing has come for long enough", () => {
    expect(stalled(later(bar, 9))).toBe(false);
    expect(stats(later(bar, 45))).toBe("10/100 · 00:55 · no progress for 45 s");
  });

  it("never counts the time remaining below zero", () => {
    expect(later({ ...bar, remaining: 2 }, 5).remaining).toBe(0);
  });
});
