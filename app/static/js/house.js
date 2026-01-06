/* Mr. House — UI
   - /house/api/simulate JSON endpoint
   - Clickable chips for +2/+5/+10/Set 0
   - Untapped input optional
   - Histogram with axes and labels
   - Log: intelligent collapse/expand (remembers user preference)
   - Reset button clears UI + resets form to defaults
*/
(function () {
  'use strict';

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---- DOM references ----
  const form    = $('#simForm');
  const runBtn  = $('#runBtn');
  const runNote = $('#runNote');

  const sIters    = $('#s-iters');
  const sRobots   = $('#s-robots');
  const sTreas    = $('#s-treas');
  const sCounters = $('#s-counters');
  const sMana     = $('#s-mana');
  const delneyChk = $('#delney');
  const copySummaryBtn = $('#copySummaryBtn');

  const pageContainer = $('.container.page');
  const resultsMount  = $('#resultsMount');
  const logMount      = $('#logMount');

  const resetBtn = $('#resetBtn');

  // ---- helpers ----
  const fmt = (n) => (n === null || n === undefined ? '—' : String(n));
  const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v));
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // ---- log expand/collapse state (remember user preference) ----
  const LOG_PREF_KEY = 'house_log_expanded';

  function getSavedLogPref() {
    try {
      const v = localStorage.getItem(LOG_PREF_KEY);
      if (v === null) return null;
      return v === 'true';
    } catch {
      return null;
    }
  }

  function saveLogPref(expanded) {
    try {
      localStorage.setItem(LOG_PREF_KEY, expanded ? 'true' : 'false');
    } catch {
      // ignore (privacy mode / disabled storage)
    }
  }

  // Untapped field + chips
  const untapped = $('#untapped_other_init');
  if (untapped) {
    untapped.removeAttribute('required'); // treat as optional

    $$('.chip').forEach(ch => {
      const plus = ch.getAttribute('data-plus');
      const set  = ch.getAttribute('data-set');
      if (plus != null) {
        ch.addEventListener('click', () => {
          const cur = Number(untapped.value || '0');
          untapped.value = String(Math.max(0, cur + Number(plus)));
          untapped.dispatchEvent(new Event('input'));
        });
      }
      if (set != null) {
        ch.addEventListener('click', () => {
          untapped.value = String(Number(set));
          untapped.dispatchEvent(new Event('input'));
        });
      }
    });
  }

  // Build result UI once
  let resultsHost = null;
  let logHost = null;

  let histCtx = null;
  let logBox = null;
  let logTail = null;
  let toggleLogBtn = null;

  function ensureResultsUI() {
    if (resultsHost && logHost) return;

    // Fallbacks so you don’t break if someone forgets to add mounts
    const resultsParent = resultsMount || pageContainer;
    const logParent     = logMount || pageContainer;
    if (!resultsParent || !logParent) return;

    // ---- Stats + histogram host ----
    if (!resultsHost) {
      resultsHost = document.createElement('div');
      resultsHost.className = 'stack-12';
      resultsHost.id = 'house-results';

      resultsHost.innerHTML = `
        <div class="card">
          <div class="k">Iterations</div>
          <div class="v" id="it_val">—</div>
        </div>

        <div class="card">
          <div class="k">Robots</div>
          <div class="v" id="r_total">—</div>
          <div class="k" style="margin-top:8px;">Untapped / Tapped</div>
          <div class="v"><span id="r_ut">—</span> / <span id="r_tp">—</span></div>
        </div>

        <div class="card">
          <div class="k">Treasures</div>
          <div class="v" id="t_total">—</div>
          <div class="k" style="margin-top:8px;">Untapped / Tapped</div>
          <div class="v"><span id="t_ut">—</span> / <span id="t_tp">—</span></div>
        </div>

        <div class="card">
          <div class="k">Puzzlebox State</div>
          <div class="v" id="pb_state">—</div>
        </div>

        <div class="card">
          <div class="k">Puzzlebox Counters</div>
          <div class="v" id="pb_cnt">—</div>
        </div>

        <div class="card">
          <div class="k">Puzzlebox Mana</div>
          <div class="v" id="pb_mana">—</div>
        </div>

        <div class="card">
          <div class="k">Roll Histogram (d20)</div>
          <canvas id="hist" height="140" style="width:100%; display:block;"></canvas>
        </div>
      `;

      resultsParent.appendChild(resultsHost);
      const histEl = $('#hist', resultsHost);
      histCtx = histEl ? histEl.getContext('2d') : null;
    }

    // ---- Log-only host (3rd column) ----
    if (!logHost) {
      logHost = document.createElement('div');
      logHost.className = 'stack-12';
      logHost.id = 'house-log';

      logHost.innerHTML = `
        <div class="card">
          <div class="row" style="justify-content:space-between; align-items:center;">
            <div class="k">Log</div>
            <div class="row" style="gap:8px;">
              <button class="btn btn--small" id="toggleLogBtn" type="button" aria-expanded="false">Show</button>
              <button class="btn btn--small" id="clearLogBtn" type="button">Clear</button>
            </div>
          </div>
          <div id="logTail" class="house-log house-log--tail"></div>
          <div id="logBox" class="house-log" style="display:none;"></div>
        </div>
      `;

      logParent.appendChild(logHost);

      logBox  = $('#logBox', logHost);
      logTail = $('#logTail', logHost);
      toggleLogBtn = $('#toggleLogBtn', logHost);

      const clearBtn = $('#clearLogBtn', logHost);
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          if (logBox) logBox.innerHTML = '';
          if (logTail) logTail.innerHTML = '<div class="log-empty">No log.</div>';
        });
      }

      if (toggleLogBtn && logBox) {
        toggleLogBtn.addEventListener('click', () => {
          const expanded = logBox.style.display !== 'none';
          if (expanded) {
            logBox.style.display = 'none';
            toggleLogBtn.textContent = 'Show';
            toggleLogBtn.setAttribute('aria-expanded', 'false');
            saveLogPref(false);
          } else {
            logBox.style.display = 'block';
            toggleLogBtn.textContent = 'Hide';
            toggleLogBtn.setAttribute('aria-expanded', 'true');
            logBox.scrollTop = logBox.scrollHeight;
            saveLogPref(true);
          }
        });
      }
    }
  }

  function clearHistogram() {
    if (!histCtx) return;
    const c = histCtx.canvas;
    histCtx.clearRect(0, 0, c.width, c.height);
  }

  function drawHistogram(hist) {
    if (!histCtx) return;
    const canvas = histCtx.canvas;
    const W = canvas.width = canvas.clientWidth;
    const H = canvas.height;

    const margin = { left: 28, right: 10, top: 8, bottom: 22 };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    const data = Array.from({ length: 20 }, (_, i) => hist?.[String(i + 1)] || 0);
    const max = Math.max(1, ...data);

    histCtx.clearRect(0, 0, W, H);
    histCtx.strokeStyle = 'rgba(255,255,255,0.35)';
    histCtx.lineWidth = 1;

    histCtx.beginPath();
    histCtx.moveTo(margin.left, margin.top);
    histCtx.lineTo(margin.left, margin.top + innerH);
    histCtx.lineTo(margin.left + innerW, margin.top + innerH);
    histCtx.stroke();

    histCtx.fillStyle = 'rgba(255,255,255,0.7)';
    histCtx.font = '11px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
    histCtx.textAlign = 'right';
    histCtx.textBaseline = 'middle';

    const y0 = margin.top + innerH;
    const yMax = margin.top;
    histCtx.fillText('0', margin.left - 6, y0);
    histCtx.fillText(String(max), margin.left - 6, yMax);

    const step = innerW / 20;
    const barW = Math.max(2, step * 0.7);

    data.forEach((v, i) => {
      const x = margin.left + i * step + (step - barW) / 2;
      const h = (v / max) * innerH;
      const y = y0 - h;
      histCtx.fillStyle = 'rgba(255,255,255,0.8)';
      histCtx.fillRect(x, y, barW, h);
    });

    histCtx.fillStyle = 'rgba(255,255,255,0.7)';
    histCtx.textAlign = 'center';
    histCtx.textBaseline = 'alphabetic';
    for (let i = 0; i < 20; i++) {
      const x = margin.left + i * step + step / 2;
      histCtx.fillText(String(i + 1), x, H - 4);
    }
  }

  function updateSticky(res) {
    if (sIters)    sIters.textContent    = `Iter:${fmt(res.iterations)}`;
    if (sRobots)   sRobots.textContent   = `R:${fmt(res.robots?.total)}`;
    if (sTreas)    sTreas.textContent    = `T:${fmt(res.treasures?.total)}`;
    if (sCounters) sCounters.textContent = `PB Cntrs:${fmt(res.puzzlebox?.counters)}`;
    if (sMana)     sMana.textContent     = `Mana:${fmt(res.puzzlebox?.mana)}`;
  }

  function formatLogLine(e) {
    const deltas = [];
    if (e.created?.robots)    deltas.push(`+${e.created.robots} Robot${e.created.robots > 1 ? 's' : ''}`);
    if (e.created?.treasures) deltas.push(`+${e.created.treasures} Treasure${e.created.treasures > 1 ? 's' : ''}`);

    const taps = (e.tapped_for_clock && e.tapped_for_clock.length)
      ? `tapped: ${e.tapped_for_clock.map(esc).join(', ')}`
      : '';

    const noteStr = (typeof e.note === 'string') ? e.note : '';
    const isStopNote = noteStr && noteStr.toLowerCase().includes('reached');
    const note = noteStr
      ? `<span class="log-note ${isStopNote ? 'log-note--stop' : ''}">— ${esc(noteStr)}</span>`
      : '';

    return `
      <div class="log-line">
        <span class="log-idx">#${esc(e.iter)}</span>
        <span class="log-sep">•</span>
        <span class="log-roll"><span class="log-label">roll</span> ${esc(e.roll)}</span>
        ${deltas.length ? `<span class="log-sep">•</span><span class="log-delta">${esc(deltas.join(', '))}</span>` : ''}
        ${taps ? `<span class="log-sep">•</span><span class="log-tapped">${taps}</span>` : ''}
        ${note ? `<span class="log-sep">•</span>${note}` : ''}
      </div>
    `;
  }

  function setLogExpanded(expanded) {
    ensureResultsUI();
    if (!logBox || !toggleLogBtn) return;

    if (expanded) {
      logBox.style.display = 'block';
      toggleLogBtn.textContent = 'Hide';
      toggleLogBtn.setAttribute('aria-expanded', 'true');
      logBox.scrollTop = logBox.scrollHeight;
    } else {
      logBox.style.display = 'none';
      toggleLogBtn.textContent = 'Show';
      toggleLogBtn.setAttribute('aria-expanded', 'false');
    }
  }

  function renderLog(logArr) {
    ensureResultsUI();
    if (!logBox || !logTail || !toggleLogBtn) return;

    const hasLog = Array.isArray(logArr) && logArr.length > 0;

    const saved = getSavedLogPref();
    const autoExpand = hasLog && logArr.length <= 12;
    const shouldExpand = (saved !== null) ? saved : autoExpand;

    if (!hasLog) {
      logTail.innerHTML = '<div class="log-empty">No steps (stopped immediately).</div>';
      logBox.innerHTML = '';
      setLogExpanded(false);
      return;
    }

    const last = logArr[logArr.length - 1];
    logTail.innerHTML = `
      <div class="log-line log-line--tail">
        ${formatLogLine(last)}
      </div>
    `;

    logBox.innerHTML = logArr.map(formatLogLine).join('');
    setLogExpanded(shouldExpand);
  }

  function renderResults(res) {
    ensureResultsUI();

    const it = $('#it_val');
    if (it) it.textContent = fmt(res.iterations);

    const rTotal = $('#r_total');
    const rUt = $('#r_ut');
    const rTp = $('#r_tp');
    if (rTotal) rTotal.textContent = fmt(res.robots?.total);
    if (rUt)    rUt.textContent    = fmt(res.robots?.untapped);
    if (rTp)    rTp.textContent    = fmt(res.robots?.tapped);

    const tTotal = $('#t_total');
    const tUt = $('#t_ut');
    const tTp = $('#t_tp');
    if (tTotal) tTotal.textContent = fmt(res.treasures?.total);
    if (tUt)    tUt.textContent    = fmt(res.treasures?.untapped);
    if (tTp)    tTp.textContent    = fmt(res.treasures?.tapped);

    const pbCnt = $('#pb_cnt');
    const pbMana = $('#pb_mana');
    if (pbCnt)  pbCnt.textContent  = fmt(res.puzzlebox?.counters);
    if (pbMana) pbMana.textContent = fmt(res.puzzlebox?.mana);

    const pbState = $('#pb_state');
    const ready = res.puzzlebox?.ready;
    if (pbState) {
      pbState.textContent =
        ready === true ? 'Untapped (Ready)' :
        ready === false ? 'Tapped' :
        '—';
    }

    drawHistogram(res.roll_histogram || {});
    updateSticky(res);
    renderLog(res.log || []);
  }

  function clearResultsUI() {
    ensureResultsUI();

    const setText = (sel, val) => {
      const el = $(sel);
      if (el) el.textContent = val;
    };

    setText('#it_val', '—');
    setText('#r_total', '—'); setText('#r_ut', '—'); setText('#r_tp', '—');
    setText('#t_total', '—'); setText('#t_ut', '—'); setText('#t_tp', '—');
    setText('#pb_state', '—');
    setText('#pb_cnt', '—');
    setText('#pb_mana', '—');

    clearHistogram();
    renderLog([]);

    updateSticky({
      iterations: null,
      robots:    { total: null },
      treasures: { total: null },
      puzzlebox: { counters: null, mana: null }
    });

    if (runNote) runNote.textContent = '';
  }

  if (resetBtn && form) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      clearResultsUI();
    });
  }

  if (copySummaryBtn) {
    copySummaryBtn.addEventListener('click', async () => {
      const summary = [
        sIters?.textContent || '',
        sRobots?.textContent || '',
        sTreas?.textContent || '',
        sCounters?.textContent || '',
        sMana?.textContent || ''
      ].filter(Boolean).join(' • ');

      try {
        await navigator.clipboard.writeText(summary);
        if (runNote) runNote.textContent = 'Copied.';
        setTimeout(() => { if (runNote) runNote.textContent = ''; }, 1200);
      } catch {
        if (runNote) runNote.textContent = 'Copy failed.';
        setTimeout(() => { if (runNote) runNote.textContent = ''; }, 1500);
      }
    });
  }

  async function runSim(e) {
    e.preventDefault();
    if (!runBtn) return;

    if (delneyChk && delneyChk.checked) {
      const stopAt100 = $('#stop_ge_100');
      const st = num($('#stop_treasures_ge')?.value);
      const sr = num($('#stop_robots_ge')?.value);
      const sm = num($('#stop_mana_ge')?.value);
      const hasAnyStop = !!(stopAt100?.checked || st !== null || sr !== null || sm !== null);
      if (!hasAnyStop && stopAt100) stopAt100.checked = true;
    }

    const params = new URLSearchParams();
    params.set('untapped', String(num($('#untapped_other_init')?.value) ?? 0));

    if (delneyChk && delneyChk.checked) {
      params.set('delney', 'true');
    }

    params.set('stop_at_100', $('#stop_ge_100')?.checked ? 'true' : 'false');

    const st = num($('#stop_treasures_ge')?.value);
    const sr = num($('#stop_robots_ge')?.value);
    const sm = num($('#stop_mana_ge')?.value);
    if (st !== null) params.set('stop_treasures_ge', String(st));
    if (sr !== null) params.set('stop_robots_ge', String(sr));
    if (sm !== null) params.set('stop_mana_ge', String(sm));

    const seed = num($('#seed')?.value);
    if (seed !== null) params.set('seed', String(seed));

    runBtn.disabled = true;
    runBtn.textContent = 'Running…';
    if (runNote) runNote.textContent = '';

    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 6000);

    try {
      const r = await fetch(`/house/api/simulate?${params.toString()}`, { signal: ctrl.signal });
      const text = await r.text();
      if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
      const res = JSON.parse(text);
      renderResults(res);
    } catch (err) {
      console.error(err);
      if (runNote) {
        runNote.textContent = (err && err.name === 'AbortError')
          ? 'Timed out. Try a stop condition.'
          : 'Failed to run. Check console.';
      }
    } finally {
      clearTimeout(t);
      runBtn.disabled = false;
      runBtn.textContent = 'Run Simulation';
    }
  }

  updateSticky({
    iterations: null,
    robots:    { total: null, untapped: null, tapped: null },
    treasures: { total: null, untapped: null, tapped: null },
    puzzlebox: { counters: null, mana: null }
  });

  const bootData = $('#result')?.dataset?.json;
  if (bootData) {
    try { renderResults(JSON.parse(bootData)); } catch {}
  }

  if (form) form.addEventListener('submit', runSim);
})();
