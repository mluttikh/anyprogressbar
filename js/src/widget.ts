// The anywidget front-end module: draws the tree of bars in the synced `tree` trait.
//
// The kernel sends a picture a few times a second at most. Between pictures this module
// keeps time itself: every quarter second it moves the running clocks on by the time since
// the last picture and re-makes the text, so a bar never looks frozen during one slow item,
// and a stall is said even when the kernel says nothing.

import { type Bar, finished, fraction, later, rows, stalled, stats } from "./format";

interface Model {
  get(key: "tree"): Bar | Record<string, never>;
  send(content: unknown): void;
  on(event: string, callback: () => void): void;
  off(event: string, callback: () => void): void;
}

interface Row {
  name: HTMLElement;
  percent: HTMLElement;
  track: HTMLElement;
  fill: HTMLElement;
  numbers: HTMLElement;
}

function makeRow(root: HTMLElement): Row {
  const make = (className: string, parent: HTMLElement = root) => {
    const el = document.createElement(className === "apb-name" ? "span" : "div");
    el.className = className;
    parent.appendChild(el);
    return el;
  };
  const name = make("apb-name");
  const percent = make("apb-percent");
  const track = make("apb-track");
  track.setAttribute("role", "progressbar");
  const fill = make("apb-fill", track);
  const numbers = make("apb-numbers");
  return { name, percent, track, fill, numbers };
}

function drawRow(row: Row, bar: Bar, depth: number): void {
  const share = fraction(bar);
  const moving = share === null && !finished(bar);
  const text = stats(bar);
  const name = bar.desc || "Progress";
  row.name.textContent = name;
  row.name.title = name;
  row.name.style.paddingLeft = `${16 * depth}px`;
  row.percent.textContent = share === null ? "" : `${Math.round(100 * share)}%`;
  row.track.dataset.status = bar.status;
  row.track.classList.toggle("apb-moving", moving);
  row.track.setAttribute("aria-label", name);
  row.track.setAttribute("aria-valuetext", text.replaceAll(" · ", ", "));
  if (moving) {
    row.track.removeAttribute("aria-valuenow");
    row.fill.style.width = "";
  } else {
    const percent = 100 * (share ?? 1);
    row.track.setAttribute("aria-valuemin", "0");
    row.track.setAttribute("aria-valuemax", "100");
    row.track.setAttribute("aria-valuenow", percent.toFixed(0));
    row.fill.style.width = `${percent.toFixed(2)}%`;
  }
  row.numbers.textContent = text;
  row.numbers.dataset.status = stalled(bar) ? "stalled" : bar.status;
}

function render({ model, el }: { model: Model; el: HTMLElement }): () => void {
  const root = document.createElement("div");
  root.className = "apb";
  el.appendChild(root);
  const made = new Map<number, Row>();
  let received = performance.now();

  const draw = () => {
    const tree = model.get("tree");
    if (!("id" in tree)) {
      root.replaceChildren();
      made.clear();
      return;
    }
    const now = later(tree as Bar, (performance.now() - received) / 1000);
    const seen = new Set<number>();
    for (const { bar, depth } of rows(now)) {
      seen.add(bar.id);
      let row = made.get(bar.id);
      if (!row) {
        row = makeRow(root);
        made.set(bar.id, row);
      }
      // keep the document's order the tree's order (a row made late goes to the end)
      for (const part of [row.name, row.percent, row.track, row.numbers]) root.appendChild(part);
      drawRow(row, bar, depth);
    }
    for (const [id, row] of made) {
      if (!seen.has(id)) {
        for (const part of [row.name, row.percent, row.track, row.numbers]) part.remove();
        made.delete(id);
      }
    }
  };

  const changed = () => {
    received = performance.now();
    draw();
  };
  model.on("change:tree", changed);
  const timer = setInterval(draw, 250);
  draw();
  // The kernel cannot see whether a page shows widgets; until it hears this it also keeps
  // the plain HTML moving (widget.py).
  model.send({ shown: true });
  return () => {
    clearInterval(timer);
    model.off("change:tree", changed);
  };
}

export default { render };
