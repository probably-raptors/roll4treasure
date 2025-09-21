/* Mr. House • front-end
   - Robust rendering (0 shows as 0, not —)
   - Builds result cards on first render if missing
   - Sticky summary always updates from latest result
*/
(function () {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---- DOM ----
  const form = $('#simForm');
  const btnRun = $('#runBtn');
  const note = $('#runNote');

  // Sticky summary spans that are already in the HTML
  const sIters    = $('#s-iters');
  const sRobots   = $('#s-robots');
  const sTreas    = $('#s-treas');
  const sCounters = $('#s-counters');
  const sMana     = $('#s-mana');

  const copySummaryBtn = $('#copySummaryBtn');

  // Where we’ll mount the result cards
  const container = $('.container.page');

  // ---- helpers ----
  const fmt = (n) => (n === null || n === undefined ? '—' : String(n));
  const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v));

  // Build the result cards once if they don’t exist
  let cardsHost = null;
  let histCtx = null;
  function ensureResultCards() {
    if (cardsHost) return;
    cardsHost = document.createElement('div');
    cardsHost.className = 'stack-12';
    cardsHost.id = 'house-results';

    cardsHost.innerHTML = `
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
        <div class="k">Puzzlebox Counters</div>
        <div class="v" id="pb_cnt">—</div>
      </div>

      <div class="card">
        <div class="k">Puzzlebox Mana</div>
        <div class="v" id="pb_mana">—</div>
      </div>

      <div class="card">
        <div class="k">Roll Histogram (d20)</div>
        <canvas id="hist" height="120" style="width:100%; display:block;"></canvas>
      </div>
    `;
    container.appendChild(cardsHost);

    const canvas = $('#hist', cardsHost);
    histCtx = canvas.getContext('2d');
  }

  function drawHistogram(hist) {
    if (!histCtx) return;
    const canvas = histCtx.canvas;
    const W = canvas.width = canvas.clientWidth;
    const H = canvas.height;

    histCtx.clearRect(0, 0, W, H);

    // Build array 1..20
    const data = Array.from({ length: 20 }, (_, i) => hist?.[String(i + 1)] || 0);
    const max = Math.max(1, ...data);
    const pad = 8;
    const barW = (W - pad * 2) / 20 - 4;

    data.forEach((v, i) => {
      const x = pad + i * ((W - pad * 2) / 20) + 2;
      const h = (v / max) * (H - 10);
      const y = H - h - 2;
      histCtx.fillStyle = 'rgba(255,255,255,0.8)';
      histCtx.fillRect(x, y, barW, h);
    });
  }

  function updateSticky(res) {
    if (!res) return;
    sIters.textContent    = `${fmt(res.iterations)}`;
    sRobots.textContent   = `R:${fmt(res.robots?.total)}`;
    sTreas.textContent    = `T:${fmt(res.treasures?.total)}`;
    sCounters.textContent = `PB Cntrs:${fmt(res.puzzlebox?.counters)}`;
    sMana.textContent     = `Mana:${fmt(res.puzzlebox?.mana)}`;
  }

  function renderResults(res) {
    ensureResultCards();

    $('#it_val').textContent = fmt(res.iterations);

    $('#r_total').textContent = fmt(res.robots?.total);
    $('#r_ut').textContent    = fmt(res.robots?.untapped);
    $('#r_tp').textContent    = fmt(res.robots?.tapped);

    $('#t_total').textContent = fmt(res.treasures?.total);
    $('#t_ut').textContent    = fmt(res.treasures?.untapped);
    $('#t_tp').textContent    = fmt(res.treasures?.tapped);

    $('#pb_cnt').textContent  = fmt(res.puzzlebox?.counters);
    $('#pb_mana').textContent = fmt(res.puzzlebox?.mana);

    drawHistogram(res.roll_histogram || {});
    updateSticky(res);
  }

  // Copy summary
  if (copySummaryBtn) {
    copySummaryBtn.addEventListener('click', async () => {
      const summary = [
        sIters.textContent,
        sRobots.textContent,
        sTreas.textContent,
        sCounters.textContent,
        sMana.textContent
      ].join(' • ');
      try {
        await navigator.clipboard.writeText(summary);
        note.textContent = 'Copied.';
        setTimeout(() => (note.textContent = ''), 1200);
      } catch {
        note.textContent = 'Copy failed.';
        setTimeout(() => (note.textContent = ''), 1500);
      }
    });
  }

  // Intercept submit -> call JSON API
  async function runSim(e) {
    e.preventDefault();

    const params = new URLSearchParams();
    params.set('untapped', String(num($('#untapped_other_init').value) ?? 0));
    params.set('stop_at_100', $('#stop_ge_100').checked ? 'true' : 'false');

    const st = num($('#stop_treasures_ge').value);
    const sr = num($('#stop_robots_ge').value);
    const sm = num($('#stop_mana_ge').value);
    if (st !== null) params.set('stop_treasures_ge', String(st));
    if (sr !== null) params.set('stop_robots_ge', String(sr));
    if (sm !== null) params.set('stop_mana_ge', String(sm));

    const seed = num($('#seed').value);
    if (seed !== null) params.set('seed', String(seed));

    // UX
    btnRun.disabled = true;
    btnRun.textContent = 'Running…';
    note.textContent = '';

    try {
      const r = await fetch(`/gamble/simulate?${params.toString()}`);
      if (!r.ok) throw new Error(await r.text());
      const res = await r.json();
      renderResults(res);
    } catch (err) {
      console.error(err);
      note.textContent = 'Failed to run.';
    } finally {
      btnRun.disabled = false;
      btnRun.textContent = 'Run Simulation';
    }
  }

  // Initial placeholder (so sticky isn’t blank before first run)
  updateSticky({
    iterations: null,
    robots:    { total: null, untapped: null, tapped: null },
    treasures: { total: null, untapped: null, tapped: null },
    puzzlebox: { counters: null, mana: null }
  });

  // If server rendered a prior result, render it
  const bootData = $('#result')?.dataset?.json;
  if (bootData) {
    try { renderResults(JSON.parse(bootData)); } catch {}
  }

  form.addEventListener('submit', runSim);
})();
