from pathlib import Path
from IPython.display import IFrame, HTML, display

def write_interactive_html(out_path="thesis_dashboard_fit_one_screen.html"):
    html = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Interactive thesis figures (3-up + compact controls)</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>

  <style>
    :root{
      --pad: 12px;
      --gap: 10px;
      --line: rgba(0,0,0,0.12);
      --muted: rgba(0,0,0,0.62);

      /* Golden mean: cap plot heights so they do not stretch */
      --plotH: clamp(220px, 34vh, 320px);
      --plotHSmall: clamp(200px, 30vh, 280px);
    }

    html, body { height: 100%; }
    body {
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      margin: var(--pad);
      background: #fff;
      color: #111;
    }

    h2 { margin: 0 0 8px 0; font-size: 18px; }

    .grid3 {
      display: grid;
      grid-template-columns: repeat(3, minmax(240px, 1fr));
      gap: var(--gap);
      align-items: start;
      margin-bottom: var(--gap);
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px;
      background: #fff;
    }

    .plotTitle { font-weight: 750; margin: 0 0 4px 0; font-size: 13px; }
    .small { color: var(--muted); font-size: 11px; line-height: 1.25; margin: 0 0 6px 0; }
    .pill { display:inline-block; padding: 1px 7px; border: 1px solid var(--line); border-radius: 999px; font-size: 11px; margin-left: 6px; }

    /* Key change: explicit heights, not flex-fill */
    .plot { height: var(--plotH); }
    .plotSmall { height: var(--plotHSmall); }

    .controls {
      display: grid;
      grid-template-columns: 1fr 260px;
      gap: 12px;
      align-items: start;
    }

    .sliderRow {
      display: grid;
      grid-template-columns: 24px 1fr 72px;
      gap: 10px;
      align-items: center;
      margin: 6px 0;
    }
    .sliderRow .lbl { font-size: 12px; font-weight: 650; }
    .sliderRow .val { font-size: 12px; text-align: right; color: #222; }
    input[type="range"] { width: 100%; }

    .kvs { font-size: 12px; line-height: 1.25; }
    .kvs b { font-weight: 650; }
    hr { border: 0; border-top: 1px solid rgba(0,0,0,0.08); margin: 8px 0; }

    @media (max-width: 1050px) {
      .grid3 { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
      :root{
        --plotH: clamp(240px, 38vh, 360px);
        --plotHSmall: clamp(220px, 34vh, 320px);
      }
    }
  </style>
</head>

<body>
  <h2>Interactive figures: 3 plots in a row, compact sliders below</h2>

  <div class="grid3">
    <div class="card">
      <div class="plotTitle">City layout <span class="pill">instant response</span></div>
      <div class="small">
        Thick segment is the business area. The x marker is the historic center (g). The circle is the economic center (μ).
      </div>
      <div id="plot_layout" class="plot plotSmall"></div>
    </div>

    <div class="card">
      <div class="plotTitle">Figure 1 style: sweep historic center location</div>
      <div class="small">
        We sweep g from 0 to 1.0 (x axis). Dashed line is the current g from the slider.
        Green X markers show current q and p at that g.
      </div>
      <div id="plot_fig1" class="plot"></div>
    </div>

    <div class="card">
      <div class="plotTitle">Figure 2-3 style: sweep transport cost</div>
      <div class="small">
        We sweep t from 0.0 to 1.5 (y axis). Dashed vertical line marks g. Dots show the current t.
      </div>
      <div id="plot_fig2" class="plot"></div>
    </div>
  </div>

  <div class="card">
    <div class="controls">
      <div>
        <div class="plotTitle">Common parameters</div>
        <div class="small">These sliders update all three plots.</div>

        <div class="sliderRow">
          <div class="lbl">N</div>
          <input id="N" type="range" min="0.20" max="1.90" step="0.05" value="1.40"/>
          <div class="val" id="N_val"></div>
        </div>

        <div class="sliderRow">
          <div class="lbl">e</div>
          <input id="e" type="range" min="0.01" max="1.00" step="0.01" value="0.10"/>
          <div class="val" id="e_val"></div>
        </div>

        <div class="sliderRow">
          <div class="lbl">g</div>
          <input id="g" type="range" min="0.00" max="1.00" step="0.01" value="0.25"/>
          <div class="val" id="g_val"></div>
        </div>

        <div class="sliderRow">
          <div class="lbl">t</div>
          <input id="t" type="range" min="0.00" max="1.50" step="0.01" value="0.25"/>
          <div class="val" id="t_val"></div>
        </div>

        <div class="small" style="margin-top:6px;">
          Tip: Increasing t makes distance more painful, so the business area often shifts to reduce travel.
        </div>
      </div>

      <div>
        <div class="plotTitle">Current interpretation</div>
        <div class="kvs">
          <div style="margin-top:4px;"><b>Business area</b></div>
          <div>Left edge: <span id="q_out"></span></div>
          <div>Right edge: <span id="p_out"></span></div>

          <div style="margin-top:6px;"><b>Historic center</b>: <span id="g_out"></span></div>
          <div><b>Economic center</b>: <span id="mu_out"></span></div>

          <hr/>

          <div><b>Situation label</b></div>
          <div id="case_out" class="small" style="margin:0;"></div>
        </div>
      </div>
    </div>
  </div>

<script>
  const EPS = 1e-9;

  function clip(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }
  function fmt(x) {
    if (!isFinite(x)) return "nan";
    const ax = Math.abs(x);
    if (ax >= 10) return x.toFixed(3);
    return x.toFixed(4);
  }

  function elH(id, fallback){
    const el = document.getElementById(id);
    const h = el ? el.clientHeight : 0;
    return (h && h > 50) ? h : fallback;
  }

  function solveBounds(N, t, e, g) {
    if (!(N > 0 && N < 2)) return { ok:false, reason:"N must be between 0 and 2." };
    if (!(e > 0)) return { ok:false, reason:"e must be positive." };
    if (!(t >= 0)) return { ok:false, reason:"t must be zero or positive." };

    const M = 2 - N;
    const theta = t / e;

    function inCity(q, p) {
      return (q < p) && (q >= -1 - 1e-6) && (p <= 1 + 1e-6);
    }

    let muB = NaN, pB = NaN, qB = NaN;
    if (theta > EPS) {
      muB = -M * N / (4 * theta);
      pB = muB + M / 2;
      qB = muB - M / 2;
    }

    let muC = NaN, pC = NaN, qC = NaN;
    if (theta > EPS) {
      muC =  M * N / (4 * theta);
      pC = muC + M / 2;
      qC = muC - M / 2;
    }

    let muA = NaN, pA = NaN, qA = NaN;
    const denom = (N - 2 * theta);
    if (Math.abs(denom) > EPS) {
      muA = N * g / denom;
      pA = muA + M / 2;
      qA = muA - M / 2;
    }

    function scoreCase(kind, q, p, mu) {
      if (!isFinite(q) || !isFinite(p) || !isFinite(mu)) return null;
      let score = 0.0;

      if (!inCity(q, p)) {
        score += 10.0 * (Math.max(0.0, (-1 - q)) + Math.max(0.0, (p - 1)));
      }
      if (kind === "A") {
        score += Math.max(0.0, q - g) + Math.max(0.0, g - p);
      } else if (kind === "B") {
        score += Math.max(0.0, p - g);
      } else if (kind === "C") {
        score += Math.max(0.0, g - q);
      }
      return score;
    }

    const candidates = [];
    const sA = scoreCase("A", qA, pA, muA);
    if (sA !== null) candidates.push([sA, "Historic center sits inside the business area.", qA, pA, muA]);
    const sB = scoreCase("B", qB, pB, muB);
    if (sB !== null) candidates.push([sB, "Historic center is to the right of the business area.", qB, pB, muB]);
    const sC = scoreCase("C", qC, pC, muC);
    if (sC !== null) candidates.push([sC, "Historic center is to the left of the business area.", qC, pC, muC]);

    if (candidates.length === 0) return { ok:false, reason:"No valid configuration found for these values." };

    candidates.sort((a,b) => a[0] - b[0]);
    const best = candidates[0];

    return {
      ok: true,
      N, M, t, e, g, theta,
      caseText: best[1],
      q: best[2],
      p: best[3],
      mu: best[4]
    };
  }

  const state = { N: 1.40, e: 0.10, g: 0.25, t: 0.25 };

  function readSlider(id) {
    return parseFloat(document.getElementById(id).value);
  }

  function syncLabelsFromState() {
    document.getElementById("N_val").textContent = fmt(state.N);
    document.getElementById("e_val").textContent = fmt(state.e);
    document.getElementById("g_val").textContent = fmt(state.g);
    document.getElementById("t_val").textContent = fmt(state.t);
  }

  function updateText(sol) {
    if (!sol.ok) {
      document.getElementById("q_out").textContent = "nan";
      document.getElementById("p_out").textContent = "nan";
      document.getElementById("g_out").textContent = "nan";
      document.getElementById("mu_out").textContent = "nan";
      document.getElementById("case_out").textContent = sol.reason;
      return;
    }
    document.getElementById("q_out").textContent = fmt(sol.q);
    document.getElementById("p_out").textContent = fmt(sol.p);
    document.getElementById("g_out").textContent = fmt(sol.g);
    document.getElementById("mu_out").textContent = fmt(sol.mu);
    document.getElementById("case_out").textContent = sol.caseText;
  }

  function drawLayout(sol) {
    let q = NaN, p = NaN, mu = NaN, g = NaN;
    if (sol.ok) { q = sol.q; p = sol.p; mu = sol.mu; g = sol.g; }

    const qd = clip(q, -1, 1);
    const pd = clip(p, -1, 1);

    const data = [
      { x: [-1, 1], y: [0, 0], mode: "lines", line: { width: 6 }, name: "city" },
      { x: sol.ok ? [qd, pd] : [], y: sol.ok ? [0, 0] : [], mode: "lines",
        line: { width: 18 }, opacity: 0.25, name: "business area" },
      { x: sol.ok ? [g] : [], y: sol.ok ? [0] : [], mode: "markers+text",
        marker: { size: 12, symbol: "x" }, text: ["g"], textposition: "top center", name: "historic center" },
      { x: sol.ok ? [mu] : [], y: sol.ok ? [0] : [], mode: "markers+text",
        marker: { size: 10, symbol: "circle" }, text: ["μ"], textposition: "top center", name: "economic center" },
      { x: sol.ok ? [q, p] : [], y: sol.ok ? [0, 0] : [], mode: "markers+text",
        marker: { size: 14, symbol: "line-ns-open" }, text: ["q", "p"], textposition: "bottom center", name: "edges" }
    ];

    const layout = {
      font: { size: 11 },
      margin: { l: 34, r: 10, t: 4, b: 26 },
      xaxis: { range: [-1.05, 1.05], title: "location on the city line" },
      yaxis: { range: [-0.8, 0.8], visible: false },
      showlegend: false,
      height: elH("plot_layout", 260)
    };

    Plotly.react("plot_layout", data, layout, {displayModeBar: false, responsive: false});
  }

  function drawFig1() {
    const N = state.N, e = state.e, t = state.t;
    const gmax = 1.0;
    const n = 320;

    const gs = [];
    const qs = [];
    const ps = [];

    for (let i=0; i<n; i++) {
      const g = gmax * (i/(n-1));
      const sol = solveBounds(N, t, e, g);
      gs.push(g);
      qs.push(sol.ok ? sol.q : NaN);
      ps.push(sol.ok ? sol.p : NaN);
    }

    const gCur = state.g;
    const solCur = solveBounds(N, t, e, gCur);
    const qCur = solCur.ok ? solCur.q : NaN;
    const pCur = solCur.ok ? solCur.p : NaN;

    const yLo = -1.05, yHi = 1.05;

    const data = [
      { x: gs, y: gs, mode: "lines", name: "g (reference)" },
      { x: gs, y: ps, mode: "lines", name: "right edge p(g)" },
      { x: gs, y: qs, mode: "lines", name: "left edge q(g)" },

      { x: gs, y: qs, mode: "lines", line: { width: 0 }, showlegend: false },
      { x: gs, y: ps, mode: "lines", fill: "tonexty", opacity: 0.2, name: "business area" },

      { x: [gCur, gCur], y: [yLo, yHi], mode: "lines",
        line: { dash: "dash", width: 2 }, name: "current g" },

      { x: solCur.ok ? [gCur, gCur] : [], y: solCur.ok ? [qCur, pCur] : [],
        mode: "markers",
        marker: { symbol: "x", size: 11, color: "green", line: { width: 2, color: "green" } },
        name: "current q,p" }
    ];

    const layout = {
      font: { size: 11 },
      margin: { l: 52, r: 10, t: 26, b: 38 },
      xaxis: { range: [0, gmax], title: "g (historic center location)" },
      yaxis: { range: [yLo, yHi], title: "location on the city line" },
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: 1.01,
        xanchor: "left",
        x: 0,
        font: { size: 10 }
      },
      height: elH("plot_fig1", 300)
    };

    Plotly.react("plot_fig1", data, layout, {displayModeBar: false, responsive: false});
  }

  function drawFig2() {
    const N = state.N, e = state.e, g = state.g;
    const tmin = 0.0;
    const tmax = 1.5;

    const n = 280;
    const ts = [];
    const qs = [];
    const ps = [];

    for (let i=0; i<n; i++) {
      const t = tmin + (tmax - tmin) * (i/(n-1));
      const sol = solveBounds(N, t, e, g);
      ts.push(t);
      qs.push(sol.ok ? sol.q : NaN);
      ps.push(sol.ok ? sol.p : NaN);
    }

    const solNow = solveBounds(N, state.t, e, g);
    const qNow = solNow.ok ? solNow.q : NaN;
    const pNow = solNow.ok ? solNow.p : NaN;

    const data = [
      { x: qs, y: ts, mode: "lines", name: "left edge q(t)" },
      { x: ps, y: ts, mode: "lines", name: "right edge p(t)" },

      { x: qs, y: ts, mode: "lines", line: { width: 0 }, showlegend: false },
      { x: ps, y: ts, mode: "lines", fill: "tonextx", opacity: 0.2, name: "business area" },

      { x: [g, g], y: [tmin, tmax], mode: "lines", line: { dash: "dash" }, name: "g (fixed)" },

      { x: [qNow, pNow], y: [state.t, state.t], mode: "markers", marker: { size: 8 }, name: "current t points" }
    ];

    const layout = {
      font: { size: 11 },
      margin: { l: 52, r: 10, t: 26, b: 38 },
      xaxis: { range: [-1.05, 1.05], title: "location on the city line" },
      yaxis: { range: [tmin, tmax], title: "t (transport cost)" },
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: 1.01,
        xanchor: "left",
        x: 0,
        font: { size: 10 }
      },
      height: elH("plot_fig2", 300)
    };

    Plotly.react("plot_fig2", data, layout, {displayModeBar: false, responsive: false});
  }

  function updateAll() {
    const sol = solveBounds(state.N, state.t, state.e, state.g);
    updateText(sol);
    drawLayout(sol);
    drawFig1();
    drawFig2();
  }

  function wireUp() {
    syncLabelsFromState();
    updateAll();

    ["N","e","g","t"].forEach((id) => {
      const el = document.getElementById(id);
      el.addEventListener("input", () => {
        state[id] = readSlider(id);
        syncLabelsFromState();
        updateAll();
      });
    });

    let rT = 0;
    window.addEventListener("resize", () => {
      clearTimeout(rT);
      rT = setTimeout(() => updateAll(), 120);
    });
  }

  wireUp();
</script>

</body>
</html>
"""
    out_path = Path(out_path)
    out_path.write_text(html, encoding="utf-8")
    return out_path

path = write_interactive_html("./data/yerevan_interactive/thesis_sectioned_dashboard.html")

try:
    display(IFrame(src=str(path), width=1400, height=860))
except Exception:
    display(HTML(path.read_text(encoding="utf-8")))

print(f"Wrote: {path.resolve()}")
