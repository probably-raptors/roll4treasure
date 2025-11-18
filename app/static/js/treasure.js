// app/static/js/treasure.js
//
// Treasure Cruise front-end:
// - Precache page polling
// - Session UI (roll / choose / pass / end)
// - Minimal, modern, no external dependencies

(function () {
  "use strict";

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $all(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const err = new Error("Request failed");
      err.status = res.status;
      err.body = text;
      throw err;
    }
    return res.json();
  }

  /* ------------------------------------------------------------------ */
  /*  PRECACHE PAGE                                                     */
  /* ------------------------------------------------------------------ */

  function initPrecache(root) {
    const sid = root.dataset.sid;
    if (!sid) return;

    const fill = $("#pc-fill", root);
    const doneEl = $("#pc-done", root);
    const totalEl = $("#pc-total", root);
    const statusEl = $("#pc-status", root);
    const actions = $("#pc-actions", root);
    const openBtn = $("#pc-open", root);

    if (!fill || !doneEl || !totalEl || !statusEl || !actions || !openBtn) {
      return;
    }

    async function poll() {
      try {
        const url = `/treasure/precache_status?sid=${encodeURIComponent(sid)}`;
        const data = await fetchJSON(url);

        const total = data.total || 0;
        const done = data.done || 0;
        const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;

        totalEl.textContent = total;
        doneEl.textContent = done;
        fill.style.width = pct + "%";

        if (data.is_ready) {
          statusEl.textContent = "Done.";
          actions.classList.add("show");
          openBtn.setAttribute("href", `/treasure/${sid}`);
          return; // stop polling
        } else {
          statusEl.textContent = "Fetching images…";
        }
      } catch (err) {
        console.error(err);
        statusEl.textContent = "Waiting…";
      }
      setTimeout(poll, 800);
    }

    poll();
  }

  /* ------------------------------------------------------------------ */
  /*  SESSION PAGE                                                      */
  /* ------------------------------------------------------------------ */

  function initSession(root) {
    const sid = root.dataset.sid;
    if (!sid) return;

    // Elements
    const sidCodeEl = $("#tc-sid", root);
    const sidCopyBtn = $("#tc-sid-copy", root);
    const playersEl = $("#tc-players", root);
    const turnLabelEl = $("#tc-turnlabel", root);
    const deckEl = $("#tc-deck", root);
    const handEl = "#tc-hand" ? $("#tc-hand", root) : null;
    const logBox = "#tc-logbox" ? $("#tc-logbox", root) : null;
    const logToggle = "#tc-log-toggle" ? $("#tc-log-toggle", root) : null;

    const rollBtn = $("#tc-roll");
    const passBtn = $("#tc-pass");
    const endBtn = $("#tc-end");

    let state = null;
    let lastReveal = [];
    let lastMode = null;
    let lastReceived = null;
    let choiceActive = false;
    let logExpanded = false;

    function setBusy(isBusy) {
      [rollBtn, passBtn, endBtn].forEach((btn) => {
        if (!btn) return;
        btn.disabled = isBusy;
      });
    }

    function setChoiceMode(on) {
      choiceActive = on;
      if (!deckEl) return;
      if (on) {
        deckEl.classList.add("tc-choice");
      } else {
        deckEl.classList.remove("tc-choice");
      }
    }

    function renderPlayers() {
      if (!state || !playersEl || !Array.isArray(state.players)) return;
      playersEl.innerHTML = "";

      const slider = document.createElement("div");
      slider.id = "tc-player-slider";
      playersEl.appendChild(slider);

      state.players.forEach((p, idx) => {
        const span = document.createElement("span");
        span.className = "chip";
        if (idx === state.turn_idx) {
          span.classList.add("chip--active");
        }
        span.textContent = p.name;
        span.dataset.playerId = p.id;
        playersEl.appendChild(span);
      });

      // Basic slider placement (optional, non-critical)
      requestAnimationFrame(() => {
        const active = playersEl.querySelector(".chip.chip--active");
        if (!active) {
          slider.style.opacity = "0";
          return;
        }
        const rect = active.getBoundingClientRect();
        const parentRect = playersEl.getBoundingClientRect();
        slider.style.opacity = "1";
        slider.style.left = rect.left - parentRect.left + "px";
        slider.style.top = rect.top - parentRect.top + "px";
        slider.style.width = rect.width + "px";
        slider.style.height = rect.height + "px";
      });
    }

    function renderTurnLabel() {
      if (!turnLabelEl || !state || !Array.isArray(state.players)) return;
      const idx = state.turn_idx ?? 0;
      const current = state.players[idx];
      const name = current ? current.name : "—";
      const turnNum = state.turn_num ?? "—";
      turnLabelEl.textContent = `Turn ${turnNum} — ${name}'s turn`;
    }

    function getCurrentPlayer() {
      if (!state || !Array.isArray(state.players)) return null;
      const idx = state.turn_idx ?? 0;
      return state.players[idx] || null;
    }

    function updateRollButtonLabel() {
      if (!rollBtn) return;
      const p = getCurrentPlayer();
      if (!p) {
        rollBtn.textContent = "Pay — • Roll d6";
        return;
      }
      const digs = typeof p.digs_this_game === "number" ? p.digs_this_game : 0;
      const cost = digs + 1;
      rollBtn.textContent = `Pay ${cost} • Roll d6`;
    }


    function createCardTile(card, { clickable = false, kept = false } = {}) {
      const wrapper = document.createElement("div");
      wrapper.className = "tc-card";
      if (clickable) wrapper.classList.add("clickable");
      if (kept) wrapper.classList.add("kept");
      wrapper.dataset.cardId = card.id || "";

      const inner = document.createElement("div");
      inner.className = "tc-card-inner";

      if (card.img) {
        const img = document.createElement("img");
        img.className = "card-img";
        img.src = card.img;
        img.alt = card.name || "Card";
        inner.appendChild(img);

        const name = document.createElement("div");
        name.className = "tc-card-name";
        name.textContent = card.name || "Unknown";
        inner.appendChild(name);
      } else {
        const fallback = document.createElement("div");
        fallback.className = "tc-card-fallback";
        fallback.textContent = card.name || "Unknown card";
        inner.appendChild(fallback);
      }

      wrapper.appendChild(inner);
      return wrapper;
    }


    function renderDeckArea() {
      if (!deckEl) return;
      deckEl.innerHTML = "";

      if (!lastReveal || lastReveal.length === 0) {
        setChoiceMode(false);
        return;
      }

      const isChoiceMode = lastMode === "choose";
      setChoiceMode(isChoiceMode);

      lastReveal.forEach((item) => {
        // item may be plain card or { kept: bool, ...card }
        const card = item.card || item;
        const kept = item.kept === true || item.kept === "true";
        const node = createCardTile(card, {
          clickable: isChoiceMode,
          kept: kept,
        });
        deckEl.appendChild(node);
      });
    }

    function renderHand() {
      if (!handEl || !state || !Array.isArray(state.players)) return;
      handEl.innerHTML = "";

      const idx = state.turn_idx ?? 0;
      const current = state.players[idx];
      if (!current || !Array.isArray(current.gains)) {
        return;
      }

      current.gains.forEach((card) => {
        const node = createCardTile(card);
        handEl.appendChild(node);
      });
    }

    function renderLog() {
      if (!logBox || !state || !Array.isArray(state.log)) return;

      const lines = state.log;
      logBox.innerHTML = "";

      lines.forEach((line, idx) => {
        const div = document.createElement("div");
        div.className = "log-line";
        div.textContent = line;
        logBox.appendChild(div);
      });

      if (!logExpanded) {
        logBox.scrollTop = logBox.scrollHeight;
      }
    }

    function renderAll() {
      renderPlayers();
      renderTurnLabel();
      updateRollButtonLabel();
      renderDeckArea();
      renderHand();
      renderLog();
    }

    async function loadInitialState() {
      try {
        const url = `/treasure/${encodeURIComponent(sid)}/state`;
        const data = await fetchJSON(url);
        state = data;
        // Initial “pending_choices” support: if any, show them as choice
        if (state && Array.isArray(state.pending_choices) && state.pending_choices.length) {
          lastReveal = state.pending_choices.map((c) => ({ card: c }));
          lastMode = "choose";
        }
        renderAll();
      } catch (err) {
        console.error("Failed to load session state", err);
      }
    }

    async function doRoll() {
      setBusy(true);
      try {
        const url = `/treasure/${encodeURIComponent(sid)}/roll`;
        const body = new URLSearchParams();
        // player_id omitted => server uses current player
        const data = await fetchJSON(url, {
          method: "POST",
          body,
        });

        state = data.state || null;
        lastMode = data.mode || null;
        lastReceived = data.received || null;

        if (data.mode === "choose") {
          // data.choices: array of Card
          lastReveal = (data.choices || []).map((c) => ({ card: c }));
        } else if (Array.isArray(data.revealed)) {
          // each item is { kept: bool, ...card }
          lastReveal = data.revealed.map((r) => {
            const { kept, ...card } = r;
            return { kept: !!kept, card };
          });
        } else {
          lastReveal = [];
        }

        renderAll();
      } catch (err) {
        console.error("roll failed", err);
        alert("Roll failed. Please try again.");
      } finally {
        setBusy(false);
      }
    }

    async function doChoose(cardId) {
      if (!cardId) return;
      setBusy(true);
      try {
        const url = `/treasure/${encodeURIComponent(sid)}/choose`;
        const body = new URLSearchParams();
        body.set("card_id", cardId);
        const data = await fetchJSON(url, {
          method: "POST",
          body,
        });

        state = data.state || null;
        lastMode = "auto";
        lastReceived = data.received || null;

        if (Array.isArray(data.revealed)) {
          lastReveal = data.revealed.map((c) => ({ card: c }));
        } else {
          lastReveal = [];
        }

        setChoiceMode(false);
        renderAll();
      } catch (err) {
        console.error("choose failed", err);
        alert("Choice failed. Please try again.");
      } finally {
        setBusy(false);
      }
    }

    async function doPass() {
      setBusy(true);
      try {
        const url = `/treasure/${encodeURIComponent(sid)}/pass`;
        const data = await fetchJSON(url, {
          method: "POST",
        });
        state = data.state || null;
        lastReveal = [];
        lastMode = null;
        renderAll();
      } catch (err) {
        console.error("pass failed", err);
        alert("Pass failed. Please try again.");
      } finally {
        setBusy(false);
      }
    }

    async function doEnd() {
      if (!window.confirm("End this game for everyone in this session?")) {
        return;
      }
      setBusy(true);
      try {
        const url = `/treasure/${encodeURIComponent(sid)}/end`;
        const data = await fetchJSON(url, {
          method: "POST",
        });
        state = data.state || null;
        lastReveal = [];
        lastMode = null;
        renderAll();
      } catch (err) {
        console.error("end failed", err);
        alert("Could not end the game. Please try again.");
      } finally {
        setBusy(false);
      }
    }

    function bindEvents() {
      // Copy session code
      if (sidCopyBtn && sidCodeEl) {
        sidCopyBtn.addEventListener("click", async () => {
          const text = sidCodeEl.textContent || "";
          try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              await navigator.clipboard.writeText(text.trim());
            } else {
              // Fallback
              const tmp = document.createElement("textarea");
              tmp.value = text.trim();
              document.body.appendChild(tmp);
              tmp.select();
              document.execCommand("copy");
              document.body.removeChild(tmp);
            }
            alert("Session code copied.");
          } catch (err) {
            console.error(err);
            alert("Unable to copy; please copy manually.");
          }
        });
      }

      // Roll / pass / end buttons
      if (rollBtn) {
        rollBtn.addEventListener("click", () => {
          if (choiceActive) {
            alert("You must choose a card for the previous roll first.");
            return;
          }
          void doRoll();
        });
      }

      if (passBtn) {
        passBtn.addEventListener("click", () => {
          void doPass();
        });
      }

      if (endBtn) {
        endBtn.addEventListener("click", () => {
          void doEnd();
        });
      }

      // Choice click handler (event delegation on deck)
      if (deckEl) {
        deckEl.addEventListener("click", (ev) => {
          if (!choiceActive) return;
          const target = ev.target;
          if (!target) return;
          const cardNode = target.closest("[data-card-id]");
          if (!cardNode) return;
          const cardId = cardNode.dataset.cardId;
          if (!cardId) return;
          void doChoose(cardId);
        });
      }

      // Log toggle
      if (logToggle && logBox) {
        logToggle.addEventListener("click", () => {
          logExpanded = !logExpanded;
          if (logExpanded) {
            logBox.classList.add("log__box--full");
            logToggle.textContent = "Collapse";
          } else {
            logBox.classList.remove("log__box--full");
            logToggle.textContent = "Show all";
            logBox.scrollTop = logBox.scrollHeight;
          }
        });
      }
    }

    bindEvents();
    void loadInitialState();
  }

  /* ------------------------------------------------------------------ */
  /*  ENTRYPOINT                                                        */
  /* ------------------------------------------------------------------ */

  document.addEventListener("DOMContentLoaded", () => {
    const precacheRoot = document.getElementById("tc-precache");
    if (precacheRoot) {
      initPrecache(precacheRoot);
    }

    const sessionRoot = document.getElementById("tc-root");
    if (sessionRoot) {
      initSession(sessionRoot);
    }
  });
})();
