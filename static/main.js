/* EDH Tools • Shared helpers
   Exposes a tiny helper bundle on window.EDH
*/
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const escapeHtml = (s) => s?.replace?.(/[&<>]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;" }[c])) ?? s;

  const haptic = (type = "light") => {
    try {
      if (navigator?.vibrate) {
        if (type === "success") navigator.vibrate([10, 30, 10]);
        else navigator.vibrate(10);
      }
    } catch {}
  };

  const toastHost = (() => {
    let host = document.querySelector(".toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "toasts";
      document.body.appendChild(host);
    }
    return host;
  })();

  const toast = (msg, ms = 2400) => {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    toastHost.appendChild(el);
    setTimeout(() => el.remove(), ms);
  };

  // Make a canvas match its CSS size (sharp on high-DPI)
  function fitCanvasToParent(canvas, cssHeight = 180) {
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.style.width = "100%";
    canvas.style.height = cssHeight + "px";
    const w = Math.floor(canvas.clientWidth * dpr);
    const h = Math.floor(cssHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  window.EDH = { $, $$, toast, haptic, escapeHtml, fitCanvasToParent };
})();
