/* Mr. House — UI
   - /house/api/simulate JSON endpoint
   - Clickable chips for +2/+5/+10/Set 0
   - Untapped input optional
   - Histogram with axes and labels
   - Log: nicely formatted, collapsed by default (shows only last line)
*/
(function () {
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
  const resultsMount = $('#resultsMount');

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

  // ---- helpers ----
  const fmt = (n) => (n === null || n === undefined ? '—' : String(n));
  const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v));
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // Build result UI once
  let resultsHost = null;
  let histCtx = null;
  let logBox = null;
  let logTail = null;
  let toggleLogBtn = null;

  function ensureResultsUI() {
    if (resultsHost) return;

    const mount = resultsMount || pageContainer;
    if (!mount) return;

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
    mount.appendChild(resultsHost);

    histCtx = $('#hist', resultsHost)?.getContext('2d');
    logBox  = $('#logBox', resultsHost);
    logTail = $('#logTail', resultsHost);
    toggleLogBtn = $('#toggleLogBtn', resultsHost);

    // Clear log button
    $('#clearLogBtn', resultsHost).addEventListener('click', () => {
      logBox.innerHTML = '';
      logTail.innerHTML = '<div class="log-empty">No log.</div>';
    });

    // Toggle expand/collapse
    toggleLogBtn.addEventListener('click', () => {
      const expanded = logBox.style.display !== 'none';
      if (expanded) {
        logBox.style.display = 'none';
        toggleLogBtn.textContent = 'Show';
        toggleLogBtn.setAttribute('aria-expanded', 'false');
      } else {
        logBox.style.display = 'block';
        toggleLogBtn.textContent = 'Hide';
        toggleLogBtn.setAttribute('aria-expanded', 'true');
        logBox.scrollTop = logBox.scrollHeight;
      }
    });
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
    const note = e.note ? `— ${esc(e.note)}` : '';

    return `
      <div class="log-line">
        <span class="log-idx">#${esc(e.iter)}</span>
        <span class="log-sep">•</span>
        <span class="log-roll"><span class="log-label">roll</span> ${esc(e.roll)}</span>
        ${deltas.length ? `<span class="log-sep">•</span><span class="log-delta">${esc(deltas.join(', '))}</span>` : ''}
        ${taps ? `<span class="log-sep">•</span><span class="log-tapped">${taps}</span>` : ''}
        ${note ? `<span class="log-note"> ${note}</span>` : ''}
      </div>
    `;
  }

  function renderLog(logArr) {
    ensureResultsUI();
    if (!logBox || !logTail || !toggleLogBtn) return;

    logBox.style.display = 'none';
    toggleLogBtn.textContent = 'Show';
    toggleLogBtn.setAttribute('aria-expanded', 'false');

    if (!logArr || !logArr.length) {
      logTail.innerHTML = '<div class="log-empty">No steps (stopped immediately).</div>';
      logBox.innerHTML = '';
      return;
    }
    const last = logArr[logArr.length - 1];
    logTail.innerHTML = `
      <div class="log-line log-line--tail">
        ${formatLogLine(last)}
      </div>
    `;

    logBox.innerHTML = logArr.map(formatLogLine).join('');
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

    // If Delney is checked and no stop conditions are set, auto-enable stop-at-100.
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

  // Initialize sticky summary
  updateSticky({
    iterations: null,
    robots:    { total: null, untapped: null, tapped: null },
    treasures: { total: null, untapped: null, tapped: null },
    puzzlebox: { counters: null, mana: null }
  });

  // Boot with server-rendered result if present
  const bootData = $('#result')?.dataset?.json;
  if (bootData) {
    try { renderResults(JSON.parse(bootData)); } catch {}
  }

  if (form) form.addEventListener('submit', runSim);
})();
