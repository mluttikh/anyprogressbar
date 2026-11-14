// The widget's own module in a page, with this harness in the kernel's part: it hands the
// widget a model whose `tree` the test sets, and keeps what the widget sends back.
//
//   window.apb.show(tree)   draw a new widget for the tree (as a cell's output would)
//   window.apb.send(tree)   a new picture from the kernel
//   window.apb.close()      the widget's view is removed (its cleanup runs)

import widget from "../../src/widget";

type Tree = Record<string, unknown>;

const cell = document.getElementById("cell")!;
const listeners = new Set<() => void>();
const sent: unknown[] = [];
let tree: Tree = {};
let cleanup: (() => void) | null = null;

const model = {
  get: (_key: "tree") => tree as never,
  send: (content: unknown) => sent.push(content),
  on: (_event: string, callback: () => void) => listeners.add(callback),
  off: (_event: string, callback: () => void) => listeners.delete(callback),
};

const apb = {
  show(next: Tree): void {
    apb.close();
    tree = next;
    sent.length = 0;
    cell.replaceChildren();
    cleanup = widget.render({ model, el: cell });
  },
  send(next: Tree): void {
    tree = next;
    for (const callback of [...listeners]) callback();
  },
  close(): void {
    cleanup?.();
    cleanup = null;
  },
  sent,
  listening: () => listeners.size,
};

(window as unknown as { apb: typeof apb }).apb = apb;
document.body.dataset.ready = "1";
