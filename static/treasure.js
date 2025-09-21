/* Treasure Cruise session UI
   - Shows card images (Top of Deck + Active Player's Cards)
   - Auto-advance turn after roll/choose, explicit "Pass turn"
   - Sticky bottom CTA, loading locks, compact log with toggle
*/
(function () {
  const { $, $$, toast, haptic, escapeHtml } = window.EDH;

  const root = $("#tc-root");
  const sid = root?.dataset.sid;

  const btnRoll   = $("#tc-roll");
  const btnPass   = $("#tc-pass");
  const choicesHost = document.createElement("div"); // (kept for future inline choices if you want)

  const logBox      = $("#tc-logbox");
  const logToggle   = $("#tc-log-toggle");
  const playersBar  = $("#tc-players");
  const turnLabel   = $("#tc-turnlabel");

  const deckHost = $("#tc-deck");
  const handHost = $("#tc-hand");

  // Copy session code support
  const sidCopyBtn = $("#tc-sid-copy");
  const sidLabel   = $("#tc-sid");
  if (sidCopyBtn && sidLabel) {
    sidCopyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(sidLabel.textContent.trim());
        toast("Session code copied.");
      } catch {
        toast("Could not copy.");
      }
    });
  }

  let state = null;
  let showAllLog = false;
  let inflight = false;
  let lastReveal = []; // holds most-recent reveal so we can show it in “Top of Deck”

  const setBusy = (busy) => {
    inflight = busy;
    if (btnRoll) btnRoll.disabled = !!busy;
    if (btnPass) btnPass.disabled = !!busy;
    if (btnRoll) {
      if (busy) {
        btnRoll.dataset.label = btnRoll.textContent;
        btnRoll.textContent = "…";
      } else if (btnRoll.dataset.label) {
        btnRoll.textContent = btnRoll.dataset.label;
      }
    }
  };

  const currentPlayer = () => state?.players?.[state.turn_idx];
  const costNow = () => 1 + ((currentPlayer()?.digs_this_game) || 0);

  const updateTurnUI = () => {
    if (!state) return;
    const p = currentPlayer();
    turnLabel.textContent = `Turn ${state.turn_num} • ${p.name}`;
    playersBar.innerHTML = "";
    state.players.forEach((pl, idx) => {
      const chip = document.createElement("div");
      chip.className = "chip" + (idx === state.turn_idx ? " chip--active" : "");
      chip.textContent = pl.name;
      chip.title = `Digs: ${pl.digs_this_game}`;
      playersBar.appendChild(chip);
    });
    if (btnRoll) btnRoll.textContent = `Pay ${costNow()} • Roll d6`;
  };

  const cardEl = (c) => {
    const a = document.createElement("a");
    a.className = "tc-card";
    a.href = c.scry || `https://scryfall.com/search?q=${encodeURIComponent(c.name)}`;
    a.target = "_blank";
    a.rel = "noopener";
    const img = document.createElement("img");
    img.alt = c.name;
    img.loading = "lazy";
    img.src = c.img || "https://cards.scryfall.io/art_crop/front/0/0/00000000-0000-0000-0000-000000000000.jpg"; // harmless fallback
    a.appendChild(img);
    a.title = c.name;
    return a;
  };

  const renderDeck = (override) => {
    // Prefer explicit reveal (from last roll response). Otherwise, current state’s revealed.
    const src = override && override.length ? override : (state?.pile?.revealed || []);
    deckHost.innerHTML = "";
    if (!src.length) return;
    src.forEach(c => deckHost.appendChild(cardEl(c)));
  };

  const renderHand = () => {
    handHost.innerHTML = "";
    const p = currentPlayer();
    const gains = p?.gains || [];
    gains.forEach(c => handHost.appendChild(cardEl(c)));
  };

  const renderLog = () => {
    const lines = state?.log || [];
    const subset = showAllLog ? lines : lines.slice(-5);
    logBox.innerHTML = subset.map(x => escapeHtml(x)).join("<br>");
    logToggle.textContent = showAllLog ? "Show recent" : "Show all";
    logToggle.setAttribute("aria-expanded", showAllLog ? "true" : "false");
    logBox.scrollTop = logBox.scrollHeight;
  };

  async function fetchState() {
    const r = await fetch(`/treasure/${sid}/state`);
    if (!r.ok) throw new Error("Failed to load session");
    return r.json();
  }

  async function refreshState({ announceNext = false } = {}) {
    state = await fetchState();
    updateTurnUI();
    renderDeck(lastReveal.length ? lastReveal : undefined);
    renderHand();
    renderLog();
    if (announceNext) {
      const p = currentPlayer();
      if (p) toast(`Next: ${p.name}`);
    }
  }

  async function init() {
    try {
      await refreshState();
    } catch (e) {
      console.error(e);
      toast("Could not load session.");
    }
  }

  // -------- actions --------
  async function roll() {
    if (inflight) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("player_id", state.players[state.turn_idx].id);
      const r = await fetch(`/treasure/${sid}/roll`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();

      state = res.state;
      updateTurnUI();

      if (res.mode === "choose") {
        // show the 3 revealed options at the top-of-deck area
        lastReveal = (res.choices || []);
        renderDeck(lastReveal);
        haptic("success");
        toast("Strike gold! Choose 1 (on the table).");
        // choices are handled server-side via /choose; no on-page buttons needed here
        setBusy(false);
        if (btnRoll) btnRoll.disabled = true; // must resolve choice
      } else {
        // auto: show the revealed then refresh state (advances turn)
        lastReveal = (res.revealed || []);
        renderDeck(lastReveal);
        const name = res.received?.name || "card";
        haptic("success");
        toast(`Received ${name}.`);
        await refreshState({ announceNext: true });
        setBusy(false);
      }
      renderLog();
      renderHand();
    } catch (e) {
      console.error(e);
      toast("Roll failed. Try again.");
      setBusy(false);
    }
  }

  async function passTurn() {
    if (inflight) return;
    setBusy(true);
    try {
      const r = await fetch(`/treasure/${sid}/pass`, { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();
      state = res.state;
      lastReveal = []; // clear top-of-deck preview when passing
      await refreshState({ announceNext: true });
      haptic("light");
    } catch (e) {
      console.error(e);
      toast("Pass failed.");
    } finally {
      setBusy(false);
    }
  }

  // Wire up
  if (btnRoll) btnRoll.addEventListener("click", roll);
  if (btnPass) btnPass.addEventListener("click", passTurn);
  if (logToggle) logToggle.addEventListener("click", () => { showAllLog = !showAllLog; renderLog(); });

  init();
})();
