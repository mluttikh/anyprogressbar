// Plays recorded runs again in the page through the widget's own module, as a notebook would
// show them: the pictures arrive at the times the kernel sent them, and between them the
// widget keeps time itself. Each `.apb-replay` element holds the run as JSON (made by
// scripts/docs_pictures.py) and, until this runs, the finished bar as plain HTML.
(function () {
  "use strict";
  const base = document.currentScript ? document.currentScript.src : location.href;
  let widget = null;
  const load = () =>
    widget ||
    (widget = import(new URL("anyprogressbar/widget.js", base).href).then((m) => m.default));

  function play(el, module) {
    const frames = JSON.parse(el.dataset.frames);
    if (!frames.length) return;
    const start = frames[0][0];
    let tree = frames[0][1];
    const listeners = new Set();
    const model = {
      get: () => tree,
      on: (_event, callback) => listeners.add(callback),
      off: (_event, callback) => listeners.delete(callback),
      send: () => {},
    };
    el.replaceChildren();
    const stage = document.createElement("div");
    el.appendChild(stage);
    const cleanup = module.render({ model, el: stage });
    const began = performance.now();
    let i = 0;
    const timer = setInterval(() => {
      const t = start + (performance.now() - began) / 1000;
      let changed = false;
      while (i + 1 < frames.length && frames[i + 1][0] <= t) {
        i += 1;
        tree = frames[i][1];
        changed = true;
      }
      if (changed) listeners.forEach((callback) => callback());
      if (i + 1 >= frames.length) {
        clearInterval(timer);
        const again = document.createElement("button");
        again.className = "apb-again";
        again.type = "button";
        again.textContent = "Play again";
        again.addEventListener("click", () => {
          cleanup();
          play(el, module);
        });
        el.appendChild(again);
      }
    }, 40);
  }

  function watch() {
    const items = document.querySelectorAll(".apb-replay:not([data-watched])");
    if (!items.length) return;
    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          seen.unobserve(entry.target);
          load().then((module) => play(entry.target, module));
        }
      },
      { threshold: 0.6 },
    );
    for (const item of items) {
      item.dataset.watched = "1";
      seen.observe(item);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
  else watch();
})();
