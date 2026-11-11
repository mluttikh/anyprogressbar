// A bar as the kernel sends it (Snapshot.as_dict in state.py), and the text beside it.
// The text must read the same as Python's (format.py and terminal.py's stats): the widget
// re-makes it between updates, as its clock ticks. tests/fixtures/stats.json holds cases
// made by Python that test/format.test.ts checks this file against.

export type Status = "pending" | "running" | "done" | "failed" | "stopped";

export interface Bar {
  id: number;
  desc: string;
  n: number;
  total: number | null;
  unit: string;
  status: Status;
  elapsed: number;
  rate: number | null;
  remaining: number | null;
  since_progress: number;
  message: string;
  leave: boolean;
  metrics: Record<string, string>;
  children: Bar[];
}

export const finished = (bar: Bar): boolean =>
  bar.status === "done" || bar.status === "failed" || bar.status === "stopped";

// Python's round(): halves go to the even neighbour
function round(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff !== 0.5) return Math.round(x);
  return floor % 2 === 0 ? floor : floor + 1;
}

const short = (value: number): string => String(Number(value.toPrecision(3)));

export function count(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return Math.abs(value) >= 1000 ? String(round(value)) : short(value);
}

export function elapsed(seconds: number): string {
  const s = Math.max(0, Math.trunc(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const two = (v: number) => String(v).padStart(2, "0");
  return h ? `${h}:${two(m)}:${two(s % 60)}` : `${two(m)}:${two(s % 60)}`;
}

export function remaining(seconds: number): string {
  if (seconds < 20) return `${Math.max(1, round(seconds))} s`;
  if (seconds < 55) return `${5 * round(seconds / 5)} s`;
  if (seconds < 3570) return `${Math.max(1, round(seconds / 60))} min`;
  const quarters = round(seconds / 900);
  const h = Math.floor(quarters / 4);
  const q = quarters % 4;
  return q ? `${h} h ${String(15 * q).padStart(2, "0")} min` : `${h} h`;
}

export function rate(perSecond: number, unit: string): string {
  let value = perSecond;
  let per = "s";
  for (const [scale, name] of [[1, "s"], [60, "min"], [3600, "h"]] as const) {
    value = perSecond * scale;
    per = name;
    if (value >= 1) break;
  }
  const digits = value >= 100 ? String(round(value)) : short(value);
  return `${digits} ${unit}/${per}`;
}

export function fraction(bar: Bar): number | null {
  if (bar.total === null) return null;
  if (bar.total <= 0) return 1;
  return Math.min(1, Math.max(0, bar.n / bar.total));
}

// seconds since the bar, or anything running under it, last moved
function quiet(bar: Bar): number {
  let least = bar.since_progress;
  for (const child of bar.children) {
    if (child.status === "running") least = Math.min(least, quiet(child));
  }
  return least;
}

export function stalled(bar: Bar): boolean {
  if (bar.status !== "running") return false;
  const still = quiet(bar);
  if (bar.n <= 0) return still >= 30;
  const perUnit = (bar.elapsed - bar.since_progress) / bar.n;
  return still >= Math.max(10, 5 * perUnit);
}

export function stats(bar: Bar): string {
  const position =
    bar.total !== null ? `${count(bar.n)}/${count(bar.total)}` : `${count(bar.n)} ${bar.unit}`;
  const took = elapsed(bar.elapsed);
  let parts: string[];
  if (bar.status === "done") {
    parts = [position, `done in ${took}`];
    if (bar.elapsed > 0 && bar.n > 0) parts.push(rate(bar.n / bar.elapsed, bar.unit));
  } else if (finished(bar)) {
    const end = `${bar.status} after ${took}`;
    parts = [position, bar.message ? `${end}: ${bar.message}` : end];
  } else {
    parts = [position, took];
    if (stalled(bar)) {
      parts.push(`no progress for ${remaining(quiet(bar))}`);
    } else {
      if (bar.remaining !== null) parts.push(`about ${remaining(bar.remaining)} left`);
      if (bar.rate !== null) parts.push(rate(bar.rate, bar.unit));
    }
  }
  for (const [key, value] of Object.entries(bar.metrics)) parts.push(`${key}=${value}`);
  return parts.join(" · ");
}

// The bar as it is `dt` seconds after the kernel described it: running clocks have moved on.
export function later(bar: Bar, dt: number): Bar {
  const children = bar.children.map((child) => later(child, dt));
  if (bar.status !== "running") return { ...bar, children };
  return {
    ...bar,
    children,
    elapsed: bar.elapsed + dt,
    since_progress: bar.since_progress + dt,
    remaining: bar.remaining === null ? null : Math.max(0, bar.remaining - dt),
  };
}

// the bars to draw, parents before children, with their depth; pending ones are not drawn
export function rows(root: Bar): { bar: Bar; depth: number }[] {
  const out: { bar: Bar; depth: number }[] = [];
  const walk = (bar: Bar, depth: number) => {
    out.push({ bar, depth });
    for (const child of bar.children) if (child.status !== "pending") walk(child, depth + 1);
  };
  walk(root, 0);
  return out;
}
