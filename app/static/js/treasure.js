/* Treasure Cruise session UI
   - No auto-advance; turn advances only on "Pass turn"
   - Player chips with sliding highlight
   - Choice mode on roll=6 (top 3, click to choose)
   - Shows kept card (1–5) in reveal, highlighted
   - Chosen-card flash overlay
   - End Game lock
*/
(function () {
  const { $, $$, toast, haptic, escapeHtml } = window.EDH;

  const root      = $("#tc-root");
  const sid       = root?.dataset.sid;

  const btnRoll   = $("#tc-roll");
  const btnPass   = $("#tc-pass");
  const btnEnd    = $("#tc-end");
  const playersBar= $("#tc-players");
  const turnLabel = $("#tc-turnlabel");
  const deckHost  = $("#tc-deck");
  const handHost  = $("#tc-hand");
  const logBox    = $("#tc-logbox");
  const logToggle = $("#tc-log-toggle");

  let state = null;
  let inflight = false;
  let choicePending = false;
  let lastReveal = [];
  let playerSlider = null;

  // --- Banner ---
  const banner = document.createElement("div");
  banner.id = "tc-banner";
  banner.className = "tc-banner";
  banner.hidden = true;
  root.insertBefore(banner, root.firstChild);
  const showBanner = (msg) => { banner.textContent = msg; banner.hidden = false; };
  const hideBanner = () => { banner.hidden = true; };

  // --- Chosen-card flash overlay ---
  const flashHost = document.createElement("div");
  flashHost.id = "tc-flash";
  flashHost.setAttribute("aria-hidden", "true");
  document.body.appendChild(flashHost);

  function flashChosen(card) {
    if (!card || !card.img) return;
    flashHost.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "card";
    const img = new Image();
    img.src = card.img;
    img.alt = card.name || "Chosen card";
    wrap.appendChild(img);
    flashHost.appendChild(wrap);

    // restart animation
    flashHost.classList.remove("show");
    void flashHost.offsetWidth; // reflow
    flashHost.classList.add("show");

    // auto-hide after animation
    setTimeout(() => {
      flashHost.classList.remove("show");
      flashHost.innerHTML = "";
    }, 1200);
  }

  const isClosed = () => !!state?.closed_at;

  const setBusy = (busy) => {
    inflight = busy;
    if (btnRoll) {
      if (busy) {
        btnRoll.textContent = "…";
      } else {
        btnRoll.textContent = `Pay ${costNow()} • Roll d6`;
      }
    }
    updateControls();
  };

  const lockAll = () => {
    if (btnRoll) btnRoll.disabled = true;
    if (btnPass) btnPass.disabled = true;
    if (btnEnd)  btnEnd.disabled  = true;
  };

  const currentPlayer = () => state?.players?.[state.turn_idx];
  const costNow = () => 1 + ((currentPlayer()?.digs_this_game) || 0);

  const updateControls = () => {
    if (isClosed()) { lockAll(); return; }
    const alreadyDug = !!currentPlayer()?.dug_this_turn;
    const lock = inflight || choicePending;
    if (btnRoll) btnRoll.disabled = lock || alreadyDug;
    if (btnPass) btnPass.disabled = lock;   // disabled only during pending choice/inflight
    if (btnEnd)  btnEnd.disabled  = !!inflight;
  };

  // --- Player slider (animated highlight) ---
  const ensureSlider = () => {
    if (!playerSlider) {
      playerSlider = document.createElement("div");
      playerSlider.id = "tc-player-slider";
      playersBar.appendChild(playerSlider);
    }
  };
  const moveSlider = () => {
    ensureSlider();
    const active = playersBar.querySelector(".pill--on");
    if (!active) { playerSlider.style.opacity = "0"; return; }
    const left = active.offsetLeft;
    const top = active.offsetTop;
    const w = active.offsetWidth;
    const h = active.offsetHeight;
    playerSlider.style.opacity = "1";
    playerSlider.style.left = `${left}px`;
    playerSlider.style.top = `${top}px`;
    playerSlider.style.width = `${w}px`;
    playerSlider.style.height = `${h}px`;
  };
  window.addEventListener("resize", () => { moveSlider(); });

  const updateTurnUI = () => {
    if (!state) return;
    const p = currentPlayer();
    if (turnLabel) turnLabel.textContent = `Turn ${state.turn_num} • ${p.name}`;

    // Render chips: names only; active has .pill--on
    playersBar.innerHTML = "";
    (state.players || []).forEach((pl, i) => {
      const el = document.createElement("div");
      el.className = `pill ${i === state.turn_idx ? "pill--on" : ""}`;
      el.textContent = pl.name;
      playersBar.appendChild(el);
    });
    ensureSlider();
    moveSlider();

    if (btnRoll) btnRoll.textContent = `Pay ${costNow()} • Roll d6`;
  };

  const cardEl = (c, extraClass = "") => {
    const a = document.createElement("a");
    a.href = c.scry || "#";
    a.target = "_blank";
    a.className = `tc-card${extraClass ? " " + extraClass : ""}`;
    a.setAttribute("aria-label", c.name);

    const img = new Image();
    img.loading = "lazy";
    img.src = c.img;
    img.alt = c.name;

    a.appendChild(img);
    a.title = c.name;
    return a;
  };

  const renderDeck = (override) => {
    const src = (override && override.length)
      ? override
      : (state?.pending_choices?.length ? state.pending_choices : (state?.pile?.revealed || []));
    deckHost.innerHTML = "";
    if (!src.length) return;
    src.forEach(c => deckHost.appendChild(cardEl(c, c.kept ? "kept" : "")));
  };

  const renderHand = () => {
    handHost.innerHTML = "";
    const p = currentPlayer();
    (p?.gains || []).forEach(c => handHost.appendChild(cardEl(c)));
  };

  let showAllLog = false;
  const renderLog = () => {
    const lines = state?.log || [];
    const subset = showAllLog ? lines : lines.slice(-5);
    logBox.innerHTML = subset.map(x => escapeHtml(x)).join("<br>");
    logToggle.textContent = showAllLog ? "Show recent" : "Show all";
    logToggle.setAttribute("aria-expanded", showAllLog ? "true" : "false");
    logBox.scrollTop = logBox.scrollHeight;
  };

  const enableChoice = (choices) => {
    deckHost.classList.add("tc-choice");
    root.classList.add("is-choice");
    const cards = Array.from(deckHost.querySelectorAll(".tc-card"));
    cards.forEach((a, i) => {
      a.classList.add("clickable");
      a.title = `${choices[i]?.name || "Choose this card"}`;
      a.setAttribute("role", "button");
      a.tabIndex = 0;
      const act = () => choose(choices[i].id);
      a.addEventListener("click", (ev) => { ev.preventDefault(); act(); }, { once: true });
      a.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); act(); }
      });
    });
  };
  const disableChoice = () => {
    deckHost.classList.remove("tc-choice");
    root.classList.remove("is-choice");
    for (const a of deckHost.querySelectorAll(".tc-card.clickable")) {
      a.classList.remove("clickable");
      a.removeAttribute("role");
      a.removeAttribute("tabindex");
    }
  };

  async function fetchState() {
    const r = await fetch(`/treasure/${sid}/state`);
    if (!r.ok) throw new Error("Failed to load session");
    return r.json();
  }

  async function refreshState() {
    state = await fetchState();
    updateTurnUI();

    if (isClosed()) {
      choicePending = false;
      disableChoice();
      lockAll();
      showBanner("⛔ Game ended. This session is read-only.");
      renderDeck();
      renderHand();
      renderLog();
      return;
    }

    if (state?.pending_choices?.length) {
      lastReveal = state.pending_choices;
      renderDeck(lastReveal);
      enableChoice(lastReveal);
      choicePending = true;
      showBanner("🎲 Rolled 6 — choose 1 from the 3 shown cards.");
    } else {
      choicePending = false;
      renderDeck();
      if (currentPlayer()?.dug_this_turn) {
        showBanner("Roll complete — press “Pass turn” when you’re done.");
      } else {
        hideBanner();
      }
      disableChoice();
    }

    renderHand();
    renderLog();
    updateControls();
  }

  // --- Actions ---
  async function roll() {
    if (inflight || choicePending || isClosed()) return;
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
        lastReveal = (res.choices || []);
        renderDeck(lastReveal);
        enableChoice(lastReveal);
        choicePending = true;
        showBanner("🎲 Rolled 6 — choose 1 from the 3 shown cards.");
      } else {
        // 1–5: show kept + others; do not advance
        renderHand();
        lastReveal = (res.revealed || []);
        renderDeck(lastReveal);
        renderLog();
        showBanner("Roll complete — press “Pass turn” when you’re done.");
        disableChoice();
        choicePending = false;

        // flash the kept card
        if (res.received) flashChosen(res.received);
      }

      updateControls();
    } catch (e) {
      console.error(e);
      toast(e?.message || "Roll failed.");
    } finally {
      setBusy(false);
      updateControls();
    }
  }

  async function choose(cardId) {
    if (inflight || isClosed()) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("player_id", state.players[state.turn_idx].id);
      fd.append("card_id", cardId);
      const r = await fetch(`/treasure/${sid}/choose`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();

      state = res.state;
      lastReveal = [];
      choicePending = false;

      updateTurnUI();
      renderDeck();
      renderHand();
      renderLog();

      showBanner("Choice made — press “Pass turn” when you’re done.");
      disableChoice();
      updateControls();

      // flash the chosen card
      if (res.received) flashChosen(res.received);

      haptic("success");
      toast(`Chosen.`);
    } catch (e) {
      console.error(e);
      toast("Choose failed.");
    } finally {
      setBusy(false);
      updateControls();
    }
  }

  async function passTurn() {
    if (inflight || choicePending || isClosed()) return;
    setBusy(true);
    try {
      const r = await fetch(`/treasure/${sid}/pass`, { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();
      state = res.state;
      lastReveal = [];
      hideBanner();
      disableChoice();
      choicePending = false;
      updateTurnUI();
      moveSlider();       // animate to the new active player
      renderDeck();
      renderHand();
      renderLog();
      updateControls();
      toast(`Turn passed.`);
    } catch (e) {
      console.error(e);
      toast("Pass failed.");
    } finally {
      setBusy(false);
      updateControls();
    }
  }

  async function endGame() {
    if (inflight || isClosed()) return;
    if (!confirm("End game for this session? No further actions will be allowed.")) return;
    setBusy(true);
    try {
      const r = await fetch(`/treasure/${sid}/end`, { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();
      state = res.state;
      choicePending = false;
      disableChoice();
      lockAll();
      showBanner("⛔ Game ended. This session is read-only.");
      renderDeck();
      renderHand();
      renderLog();
      haptic("success");
      toast("Game ended.");
    } catch (e) {
      console.error(e);
      toast("End game failed.");
    } finally {
      setBusy(false);
      updateControls();
    }
  }

  // --- Wire up & init ---
  if (btnRoll) btnRoll.addEventListener("click", roll);
  if (btnPass) btnPass.addEventListener("click", passTurn);
  if (btnEnd)  btnEnd.addEventListener("click", endGame);
  if (logToggle) logToggle.addEventListener("click", () => { showAllLog = !showAllLog; renderLog(); });

  async function init() {
    const sidBtn = $("#tc-sid-copy");
    const sidTxt = $("#tc-sid");
    if (sidBtn && sidTxt) {
      sidBtn.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(sidTxt.textContent.trim()); toast("Copied!"); }
        catch { toast("Copy failed."); }
      });
    }
    await refreshState();
  }

  init();
})();
