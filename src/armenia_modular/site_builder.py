import os
import html as _html
import urllib.parse
from string import Template
from pathlib import Path
import shutil


# =========================
# Small helpers
# =========================
def _escape(s: str) -> str:
    return _html.escape(str(s), quote=True)


def svg_placeholder_data_uri(label: str, w: int = 1600, h: int = 1000) -> str:
    safe = _html.escape(label)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f2f2f2"/>
      <stop offset="1" stop-color="#dcdcdc"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" rx="48" fill="url(#g)"/>
  <rect x="48" y="48" width="{w-96}" height="{h-96}" rx="36" fill="none" stroke="#bdbdbd" stroke-width="4"/>
  <text x="50%" y="52%" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="54" fill="#333">{safe}</text>
  <text x="50%" y="59%" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="24" fill="#666">
    Replace with assets/ image
  </text>
</svg>"""
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg)


def _clone_step(base: dict, **overrides) -> dict:
    out = dict(base)
    out.update(overrides)
    return out


# =========================
# Config
# =========================
# Idle scroll "slow-down" around first and last scenario
IDLE_LEAD_STEPS = 3          # number of invisible spacer steps before the first real scenario card
IDLE_TAIL_STEPS = 2          # number of invisible spacer steps after the last real scenario card
IDLE_LEAD_PAD_VH = 22        # vertical padding per idle step (vh)
IDLE_TAIL_PAD_VH = 22        # vertical padding per idle step (vh)
OUT_DIR = "data/yerevan_interactive"


def add_idle_spacer_steps(
    scenario_steps: list[dict],
    lead_count: int = 1,
    tail_count: int = 1,
    lead_pad_vh: int = 22,
    tail_pad_vh: int = 22,
) -> list[dict]:
    """
    Adds invisible "idle" scroll steps that keep the same scenario values, so the sticky viz
    stays pinned longer and the minibar/progress bar has time to be seen on the first and last scenario.
    """
    if not scenario_steps:
        return scenario_steps

    first = scenario_steps[0]
    last = scenario_steps[-1]

    out: list[dict] = []

    # Lead idle steps (use first scenario values, keep same progress/title)
    for _ in range(max(0, int(lead_count))):
        out.append(
            _clone_step(
                first,
                idle=True,
                pad_vh=int(lead_pad_vh),
                heading="",
                body="",
                hint="",
            )
        )

    out.extend(scenario_steps)

    # Tail idle steps (use last scenario values, keep same progress/title)
    for _ in range(max(0, int(tail_count))):
        out.append(
            _clone_step(
                last,
                idle=True,
                pad_vh=int(tail_pad_vh),
                heading="",
                body="",
                hint="",
            )
        )

    return out


def assign_progress_percent(scenario_steps: list[dict]) -> list[dict]:
    """
    Assign a stable progress percent per scenario (0..100), then idle steps can copy it.
    """
    if not scenario_steps:
        return scenario_steps

    n = len(scenario_steps)
    if n == 1:
        return [_clone_step(scenario_steps[0], prog=100.0)]

    out: list[dict] = []
    for i, st in enumerate(scenario_steps):
        pct = (i / (n - 1)) * 100.0
        out.append(_clone_step(st, prog=float(pct)))
    return out


# =========================
# Compare section: embed + autosize (landing) and height reporter (compare page)
# =========================
def patch_landing_add_compare_embed_css(landing_html: str) -> str:
    css = r"""

/* ---- injected: compare section full width + iframe embed ---- */
#compare{
  scroll-margin-top: calc(var(--navH) + 16px) !important;
}

#compare .container{
  max-width: none !important;
  width: 100% !important;
  box-sizing: border-box !important;
  padding-left: var(--modelPad, 12px) !important;
  padding-right: var(--modelPad, 12px) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

/* Borderless embed wrapper */
#compare .embedCard{
  background: transparent !important;   /* or #fff if you prefer */
  border: 0 !important;
  box-shadow: none !important;
  border-radius: var(--radius2) !important;
  overflow: hidden !important;
}

#compare .embedCard iframe{
  width: 100%;
  height: 700px;        /* initial, JS will override */
  border: 0;
  display: block;
  overflow: hidden;
}
/* ---- end injected block ---- */
"""
    style_close = landing_html.rfind("</style>")
    if style_close == -1:
        raise ValueError("Could not find </style> to inject compare embed CSS.")
    return landing_html[:style_close] + css + "\n" + landing_html[style_close:]


def patch_landing_insert_compare_before_explain(
    landing_html: str,
    compare_href: str = "compare_business_areas.html",
    title: str = "Business areas comparison",
    sub: str = "Compare Yerevan’s dynamic business area with other cities on a common meters scale.",
) -> str:
    """
    Inserts the compare section immediately before the Explanation section.
    No button.
    """
    block = f"""
  <section class="section" id="compare">
    <div class="container">
      <div class="sectionTitle">
        <h2>{_escape(title)}</h2>
        <p>{_escape(sub)}</p>
      </div>

      <div class="embedCard">
        <iframe id="compareFrame" src="{_escape(compare_href)}" title="{_escape(title)}" loading="eager" scrolling="no"></iframe>
      </div>
    </div>
  </section>
"""
    anchor = '<section class="section" id="explain">'
    if anchor not in landing_html:
        raise ValueError("Could not find the Explanation section anchor.")
    return landing_html.replace(anchor, block + "\n" + anchor, 1)


def patch_landing_add_compare_autosize_js(landing_html: str) -> str:
    """
    Autosize compare iframe:
    - Primary: accept postMessage({type:"compareHeight", height:<px>}) from compare page
    - Also sends postMessage({type:"requestHeight"}) to request updates
    - Same-origin fallback reads .wrap height (not document scrollHeight) to avoid growth loops
    """
    if "compareIframeAutosize" in landing_html:
        return landing_html

    injected = r"""
    // ---- injected: compare iframe autosize (stable, no growth loop) ----
    (function compareIframeAutosize() {
      const compareFrame = document.getElementById("compareFrame");
      if (!compareFrame) return;

      const _COMPARE_PAD = 24; // small safety pad, avoid runaway growth
      let _lastSet = 0;

      function setCompareHeight(px) {
        if (!compareFrame) return;
        if (typeof px !== "number" || !isFinite(px) || px <= 0) return;

        const next = Math.ceil(px + _COMPARE_PAD);

        // Prevent tiny oscillations
        if (_lastSet && Math.abs(next - _lastSet) <= 2) return;

        _lastSet = next;
        compareFrame.style.height = next + "px";
      }

      // Receive height from compare page
      window.addEventListener("message", (event) => {
        const d = event && event.data;
        if (!d || typeof d !== "object") return;
        if (d.type === "compareHeight" && typeof d.height === "number") {
          setCompareHeight(d.height);
        }
      });

      function requestCompareHeight() {
        try {
          if (compareFrame && compareFrame.contentWindow) {
            compareFrame.contentWindow.postMessage({ type: "requestHeight" }, "*");
          }
        } catch (e) {}
      }

      // Same-origin fallback: measure .wrap (content), not documentElement.scrollHeight
      function _compareDoc() {
        try {
          return compareFrame.contentDocument || (compareFrame.contentWindow && compareFrame.contentWindow.document) || null;
        } catch (e) {
          return null;
        }
      }

      function _computeContentHeightSameOrigin(doc) {
        try {
          const wrap = doc && doc.querySelector && doc.querySelector(".wrap");
          if (wrap) {
            const h = Math.max(wrap.scrollHeight || 0, wrap.offsetHeight || 0);
            return (h && isFinite(h)) ? Math.ceil(h) : 0;
          }
        } catch (e) {}
        return 0;
      }

      function resizeCompareFrameSameOrigin() {
        const doc = _compareDoc();
        if (!doc) return;
        const h = _computeContentHeightSameOrigin(doc);
        if (h) setCompareHeight(h);
      }

      compareFrame.setAttribute("scrolling", "no");
      compareFrame.style.overflow = "hidden";

      compareFrame.addEventListener("load", () => {
        requestCompareHeight();
        setTimeout(requestCompareHeight, 120);
        setTimeout(requestCompareHeight, 350);
        setTimeout(requestCompareHeight, 900);

        resizeCompareFrameSameOrigin();
        setTimeout(resizeCompareFrameSameOrigin, 120);
        setTimeout(resizeCompareFrameSameOrigin, 900);
      });

      window.addEventListener("resize", () => {
        requestCompareHeight();
        resizeCompareFrameSameOrigin();
        setTimeout(() => {
          requestCompareHeight();
          resizeCompareFrameSameOrigin();
        }, 250);
      });
    })();
    // ---- end injected block ----
"""

    needle = "\n    // Init\n"
    if needle in landing_html:
        return landing_html.replace(needle, "\n" + injected + needle, 1)

    idx = landing_html.rfind("</script>")
    if idx == -1:
        raise ValueError("Could not find </script> to inject compare autosize JS.")
    return landing_html[:idx] + "\n" + injected + "\n" + landing_html[idx:]


def patch_compare_add_height_postmessage(compare_html: str) -> str:
    """
    Injects postMessage height reporter into compare_business_areas.html.
    IMPORTANT: avoids infinite-growth loop by measuring .wrap height (content height),
    not documentElement.scrollHeight (which tracks iframe viewport).
    """
    if "compareHeightReporter" in compare_html:
        return compare_html

    injected = r"""
  <script id="compareHeightReporter">
  (function() {
    function _contentHeight() {
      try {
        var wrap = document.querySelector(".wrap");
        if (wrap) {
          var h = Math.max(wrap.scrollHeight || 0, wrap.offsetHeight || 0);
          if (h && isFinite(h)) return Math.ceil(h);
        }

        // Fallback only if .wrap not found
        var b = document.body;
        if (b) {
          var hb = Math.max(b.scrollHeight || 0, b.offsetHeight || 0);
          if (hb && isFinite(hb)) return Math.ceil(hb);
        }
      } catch (e) {}
      return 0;
    }

    function _postHeight() {
      try {
        var h = _contentHeight();
        if (!h || !isFinite(h) || h < 50) return;
        if (window.parent) {
          window.parent.postMessage({ type: "compareHeight", height: h }, "*");
        }
      } catch (e) {}
    }

    function _burst() {
      _postHeight();
      setTimeout(_postHeight, 60);
      setTimeout(_postHeight, 180);
      setTimeout(_postHeight, 420);
      setTimeout(_postHeight, 900);
    }

    window.addEventListener("message", function(event) {
      var d = event && event.data;
      if (!d || typeof d !== "object") return;
      if (d.type === "requestHeight") _burst();
    });

    window.addEventListener("load", _burst);
    window.addEventListener("resize", function() {
      _postHeight();
      setTimeout(_postHeight, 120);
    });

    if ("ResizeObserver" in window) {
      try {
        var ro = new ResizeObserver(function() { _postHeight(); });
        var wrap = document.querySelector(".wrap");
        if (wrap) ro.observe(wrap);
      } catch (e) {}
    }

    // Wrap update() so height is re-sent after redraws
    try {
      if (typeof update === "function" && !update.__heightWrapped) {
        var _u = update;
        var wrapped = function() {
          var r = _u.apply(this, arguments);
          _burst();
          return r;
        };
        wrapped.__heightWrapped = true;
        update = wrapped;
      }
    } catch (e) {}

    _burst();
  })();
  </script>
"""

    idx = compare_html.rfind("</body>")
    if idx == -1:
        idx = compare_html.rfind("</html>")
    if idx == -1:
        raise ValueError("Could not find </body> or </html> to inject height reporter.")
    return compare_html[:idx] + injected + "\n" + compare_html[idx:]


# =========================
# Patch: landing CSS layout tweaks for model section
# =========================
def patch_landing_for_model_focus_zoom(landing_html: str) -> str:
    css_inject = r"""

/* ---- injected: make model section full width + compact steps + no minibar overlap ---- */

:root{
  --navH: 68px;     /* JS overwrites */
  --miniBarH: 0px;  /* becomes >0 only while pinned */
  --modelPad: 12px; /* side padding for model section */
  --gapTop: 10px;
  --stepsW: 360px;  /* compact annotation width */
}

/* Top menu always visible */
.nav{
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  z-index: 300 !important;
}

/* Page starts below fixed nav */
body{
  padding-top: var(--navH) !important;
}

/* Keep anchor jumps from hiding under nav */
#gallery1, #model, #gallery2, #explain{
  scroll-margin-top: calc(var(--navH) + 16px) !important;
}

/* Make only the model section nearly full width with small margins */
#model .container{
  max-width: none !important;
  width: 100% !important;
  box-sizing: border-box !important;
  padding-left: var(--modelPad, 12px) !important;
  padding-right: var(--modelPad, 12px) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

/* The header inside model should also align with new width */
#model .modelHeader{
  padding-left: 0 !important;
  padding-right: 0 !important;
}

/* Force the model grid to: compact left, huge right */
#model .modelGrid{
  display: grid !important;
  grid-template-columns: var(--stepsW) 1fr !important;
  gap: 18px !important;
  align-items: start !important;
}

/* Ensure the right column can expand fully */
#model .stickyViz{
  min-width: 0 !important;
}

/* Compact the steps column */
#model .stepsCol{
  width: var(--stepsW) !important;
  max-width: var(--stepsW) !important;
  padding-right: 0 !important;
  opacity: 0.98 !important;
}

/* Make step cards compact */
#model .stepCard{
  max-width: var(--stepsW) !important;
  padding: 12px 12px 10px 12px !important;
  border-radius: 20px !important;
}
#model .stepKicker{
  font-size: 10px !important;
}
#model .stepCard h3{
  font-size: 16px !important;
  margin-bottom: 6px !important;
}
#model .stepBody{
  font-size: 13px !important;
  line-height: 1.45 !important;
}
#model .chip{
  font-size: 11px !important;
  padding: 5px 9px !important;
}

/* Sticky map: always stick below nav, plus minibar when pinned */
#model .stickyViz{
  position: sticky !important;
  top: calc(var(--navH) + var(--miniBarH) + var(--gapTop)) !important;
  height: calc(100vh - var(--navH) - var(--miniBarH) - (2 * var(--gapTop))) !important;
  transition: none !important;
}

/* Hide minibar by default */
#model .modelMiniBar{
  display: none !important;
}

/* Show minibar only while pinned, below nav */
body.modelPinned{
  --miniBarH: 56px;
}

body.modelPinned #model .modelMiniBar{
  display: flex !important;
  position: fixed !important;
  top: var(--navH) !important;
  left: 0 !important;
  right: 0 !important;
  z-index: 250 !important;
  background: rgba(250,250,250,.94) !important;
  backdrop-filter: blur(10px) !important;
  border-bottom: 1px solid rgba(15,15,16,.12) !important;
  padding: 8px 18px 12px 18px !important;
}

/* Extra safety: when pinned, keep stickyViz pushed down */
body.modelPinned #model .stickyViz{
  top: calc(var(--navH) + var(--miniBarH) + var(--gapTop)) !important;
  height: calc(100vh - var(--navH) - var(--miniBarH) - (2 * var(--gapTop))) !important;
}

/* Smaller overall section paddings can help the map feel bigger */
#model.modelWrap, .modelWrap{
  padding-left: 0 !important;
  padding-right: 0 !important;
}

/* Mobile */
@media (max-width: 980px){
  :root{
    --stepsW: 100%;
    --modelPad: 12px;
  }

  #model .modelGrid{
    grid-template-columns: 1fr !important;
  }

  #model .stickyViz{
    position: relative !important;
    top: 0 !important;
    height: 70vh !important;
  }

  body.modelPinned{
    --miniBarH: 54px;
  }
}

/* ---- end injected block ---- */
"""

    style_close = landing_html.rfind("</style>")
    if style_close == -1:
        raise ValueError("Could not find </style> to inject CSS.")
    return landing_html[:style_close] + css_inject + "\n" + landing_html[style_close:]


# =========================
# Patch: center map zoom in viz
# =========================
def patch_center_map_button_zoom(viz_html: str, center_zoom: float = 15.0) -> str:
    import re

    def sub_first(pattern: str, html: str) -> tuple[str, int]:
        rx = re.compile(pattern, re.DOTALL)

        def _repl(m: re.Match) -> str:
            return m.group(1) + str(center_zoom) + m.group(3)

        return rx.subn(_repl, html, count=1)

    # 1) Patch the Center button handler, if it exists
    viz_html, n = sub_first(
        r"(map\.setView\(\s*\[\s*g\.lat\s*,\s*g\.lon\s*\]\s*,\s*)(\d+(?:\.\d+)?)(\s*,)",
        viz_html
    )
    if n:
        return viz_html

    # 2) Otherwise patch the Leaflet init setView (L.map(...).setView(...))
    viz_html, _ = sub_first(
        r"(\.setView\(\s*\[\s*g\.lat\s*,\s*g\.lon\s*\]\s*,\s*)(\d+(?:\.\d+)?)(\s*\))",
        viz_html
    )
    return viz_html


# =========================
# Patch 1: scrolly control hooks for iframe (viz)
# =========================
def patch_interactive_for_scrolly(interactive_html: str) -> str:
    injection = r"""
    // ---- scrollytelling control hooks (injected) ----
    function _dispatchInput(el) {
      try {
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } catch (e) {}
    }

    function setSliders(tVal, aVal) {
      const tSlider = document.getElementById("tSlider");
      const aSlider = document.getElementById("aSlider");
      if (!tSlider || !aSlider) return;

      if (typeof tVal === "number" && isFinite(tVal)) tSlider.value = String(tVal);
      if (typeof aVal === "number" && isFinite(aVal)) aSlider.value = String(aVal);

      _dispatchInput(tSlider);
      _dispatchInput(aSlider);

      try {
        if (typeof update === "function") update();
      } catch (e) {}
    }

    function setMapView(lat, lon, zoom) {
      if (typeof lat === "number" && typeof lon === "number" && typeof zoom === "number") {
        try {
          map.setView([lat, lon], zoom, { animate: true });
        } catch (e) {}
      }
    }

    let _invT = 0;
    function invalidateMapSize() {
      try {
        clearTimeout(_invT);
        _invT = setTimeout(() => map.invalidateSize(), 0);
      } catch (e) {}
    }

    function postReady() {
      try {
        window.parent && window.parent.postMessage({ type: "vizReady" }, "*");
      } catch (e) {}
    }

    window.addEventListener("message", (event) => {
      const msg = event.data;
      if (!msg || typeof msg !== "object") return;

      if (msg.type === "setSliders") setSliders(msg.t, msg.a);
      if (msg.type === "setView") setMapView(msg.lat, msg.lon, msg.zoom);
      if (msg.type === "invalidateSize") invalidateMapSize();

      if (msg.type === "ping") postReady();
    });

    postReady();
    // ---- end injected block ----
    """

    anchor = "    // Initial draw"
    if anchor in interactive_html:
        return interactive_html.replace(anchor, injection + "\n" + anchor, 1)

    idx = interactive_html.rfind("</script>")
    if idx == -1:
        raise ValueError("Could not find </script> to inject scrolly hooks.")
    return interactive_html[:idx] + injection + "\n" + interactive_html[idx:]


# =========================
# Patch 2: iframe UI layout (shrink side panels so the map is bigger)
# =========================
def patch_interactive_ui_left_right_vertical_sliders(html_str: str) -> str:
    import re

    # -------------------------
    # 1) Replace the body layout
    # -------------------------
    old_body_pattern = re.compile(
        r'<div id="map"></div>\s*<div id="controls">.*?</div>\s*',
        re.DOTALL
    )

    new_body = r"""
  <div id="app">
    <div id="topRow">

      <div class="panel" id="leftPanel">
        <div class="panelKicker">Transport</div>

        <div class="panelSliderWrap">
          <div class="sliderStack" id="tStack">
            <div class="vTicks" id="tTicks" aria-hidden="true"></div>
            <div class="thumbLabel" id="tVal"></div>
            <input id="tSlider" class="vSlider pretty" type="range"
                   min="0" max="2.00" step="0.01" value="1.00"
                   aria-label="Transport slider">
          </div>
        </div>
      </div>

      <div class="mapPanel" id="mapPanel">
        <div id="map"></div>
      </div>

      <div class="panel" id="rightPanel">
        <div class="panelKicker">Amenities</div>

        <div class="panelSliderWrap">
          <div class="sliderStack" id="aStack">
            <div class="vTicks" id="aTicks" aria-hidden="true"></div>
            <div class="thumbLabel" id="aVal"></div>
            <input id="aSlider" class="vSlider pretty" type="range"
                   min="0" max="2.00" step="0.01" value="1.00"
                   aria-label="Amenities slider">
          </div>
        </div>
      </div>

    </div>

    <div id="bottomBar">
      <div class="barMapArea">
        <button id="centerBtn" class="barBtn" type="button">Center map</button>
        <div class="barValue" id="muInfo"></div>
      </div>
    </div>
  </div>
"""
    if not old_body_pattern.search(html_str):
        raise ValueError("Could not find the expected map+controls block to replace.")
    html_str = old_body_pattern.sub(new_body, html_str, count=1)

    # -------------------------
    # 2) Replace <style> block
    # -------------------------
    style_pattern = re.compile(r"<style>.*?</style>", re.DOTALL)

    new_style = r"""
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

    html, body { height: 100%; }
    body { margin: 0; font-family: Inter, Arial, sans-serif; overflow: hidden; background: #fff; }

    #app { height: 100%; display: flex; flex-direction: column; }

    #topRow {
      flex: 1;
      min-height: 0;
      display: grid;
      grid-template-columns: clamp(110px, 7.5vw, 150px) 1fr clamp(110px, 7.5vw, 150px);
      gap: 10px;
      padding: 10px;
      box-sizing: border-box;
    }

    .panel {
      position: relative;
      z-index: 5;
      height: 100%;
      border: 1px solid rgba(0,0,0,0.12);
      border-radius: 16px;
      background: #fff;
      box-shadow: 0 8px 20px rgba(0,0,0,0.09);
      padding: 10px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: 0;
    }

    .panelKicker {
      font-size: 10px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      opacity: 0.70;
      font-weight: 800;
    }

    .panelSliderWrap{
      flex: 1;
      min-height: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .sliderStack{
      position: relative;
      height: 100%;
      min-height: 0;
      display: flex;
      align-items: stretch;
      gap: 8px;
      padding: 4px 0;
      box-sizing: border-box;
    }

    .vTicks{
      position: relative;
      width: 14px;
      height: 100%;
      opacity: 0.9;
    }

    .tickDot{
      position: absolute;
      left: 50%;
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: rgba(0,0,0,0.16);
      transform: translate(-50%, -50%);
      transition: transform 120ms ease, background 120ms ease, box-shadow 120ms ease;
    }

    .tickDot.isActive{
      background: rgba(124,58,237,0.95);
      transform: translate(-50%, -50%) scale(1.18);
      box-shadow: 0 0 0 3px rgba(124,58,237,0.14);
    }

    .vSlider{
      writing-mode: bt-lr;
      width: 22px;
      height: 100%;
      padding: 0;
      margin: 0;
      background: transparent;
    }

    .vSlider.pretty{
      -webkit-appearance: slider-vertical;
      appearance: slider-vertical;
    }

    .vSlider.pretty::-webkit-slider-runnable-track{
      width: 12px;
      background: rgba(0,0,0,0.10);
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.10);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.55);
    }

    .vSlider.pretty::-webkit-slider-thumb{
      -webkit-appearance: none;
      width: 20px;
      height: 20px;
      border-radius: 999px;
      background: rgba(0,124,204,0.98);
      border: 2px solid #fff;
      box-shadow: 0 6px 14px rgba(0,0,0,0.16);
      margin-top: -4px;
    }

    .vSlider.pretty::-moz-range-track{
      width: 12px;
      background: rgba(0,0,0,0.10);
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.10);
    }

    .vSlider.pretty::-moz-range-thumb{
      width: 20px;
      height: 20px;
      border-radius: 999px;
      background: rgba(0,124,204,0.98);
      border: 2px solid #fff;
      box-shadow: 0 6px 14px rgba(0,0,0,0.16);
    }

    /* This matches your old look: a word pill that follows slider value */
    .thumbLabel{
      z-index: 5000;
      position: absolute;
      left: calc(100% + 8px);
      top: 50%;
      transform: translateY(-50%);
      font-size: 12px;
      font-weight: 900;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.12);
      background: rgba(250,250,250,0.96);
      white-space: nowrap;
      pointer-events: none;
      box-shadow: 0 6px 14px rgba(0,0,0,0.10);
    }

    #rightPanel .thumbLabel{
      left: auto;
      right: calc(100% + 8px);
    }

    .mapPanel {
      position: relative;
      z-index: 1;
      border: 1px solid rgba(0,0,0,0.12);
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 10px 26px rgba(0,0,0,0.10);
      background: #f3f3f3;
      min-height: 0;
    }

    #map { width: 100%; height: 100%; }

    .leaflet-control-attribution { display: none !important; }
    .leaflet-top, .leaflet-bottom { z-index: 1000; }

    /* Legend: horizontal 3 columns x 2 rows */
    .legend{
      background: rgba(255,255,255,0.94);
      padding: 10px 12px;
      border-radius: 12px;
      box-shadow: 0 1px 10px rgba(0,0,0,0.12);
      color: #111;
      font-size: 12px;
      font-family: Inter, Arial, sans-serif;

      width: 520px;
      max-width: 520px;
    }

    .legend .title{
      font-weight: 800;
      margin-bottom: 8px;
    }

    .legendGrid{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      grid-auto-rows: min-content;
      column-gap: 16px;
      row-gap: 10px;
      align-items: start;
    }

    .legendItem{
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .legendText{
      white-space: normal;
      line-height: 1.15;
    }

    .legend .swatch{
      width: 12px;
      height: 12px;
      border-radius: 0px;
      border: 1px solid rgba(0,0,0,0.25);
      flex: 0 0 auto;
    }

    .legend img.icon{
      width: 22px;
      height: 22px;
      object-fit: contain;
      flex: 0 0 auto;
      display: block;
    }

    .legend .dot{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: 2px solid #111;
      background: #f0805a;
      flex: 0 0 auto;
    }

    /* Bottom bar: only map area column, with left button and right text */
    #bottomBar{
      border-top: 1px solid rgba(0,0,0,0.12);
      padding: 10px 12px;
      background: #fff;
      box-sizing: border-box;

      display: grid;
      grid-template-columns: clamp(110px, 7.5vw, 150px) 1fr clamp(110px, 7.5vw, 150px);
      gap: 10px;
      align-items: center;
    }

    .barMapArea{
      grid-column: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-width: 0;
    }

    .barBtn{
      height: 30px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.18);
      background: rgba(255,255,255,0.92);
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
      font-family: Inter, Arial, sans-serif;
      flex: 0 0 auto;
    }

    .barValue{
      font-size: 13px;
      font-weight: 800;
      white-space: nowrap;
      font-family: Inter, Arial, sans-serif;
      opacity: 0.92;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
      text-align: right;
    }

    @media (max-width: 700px) {
      .legend{
        width: auto;
        max-width: 92vw;
      }
      .legendGrid{
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 560px) {
      #topRow {
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(240px, 1fr) auto;
      }
      .mapPanel { min-height: 45vh; }
      .vSlider { height: 160px; }
      .vTicks { height: 160px; }
      #rightPanel .thumbLabel{ right: calc(100% + 8px); }
      .thumbLabel{ left: calc(100% + 8px); }

      #bottomBar{ grid-template-columns: 1fr; }
      .barMapArea{ grid-column: 1; }
    }
  </style>
"""
    if not style_pattern.search(html_str):
        raise ValueError("Could not find a <style> block to replace.")
    html_str = style_pattern.sub(new_style, html_str, count=1)

    # -------------------------
    # 3) Force zoom control to top-right
    # -------------------------
    if "zoomControl: false" not in html_str:
        html_str = re.sub(
            r'L\.map\(\s*"map"\s*,\s*\{\s*preferCanvas\s*:\s*true\s*\}\s*\)',
            'L.map("map", { preferCanvas: true, zoomControl: false })',
            html_str,
            count=1
        )

    if "L.control.zoom({ position: \"topright\" })" not in html_str:
        html_str = re.sub(
            r'(const\s+map\s*=\s*L\.map\("map"[^;]*;\s*)',
            r'\1\n\n    L.control.zoom({ position: "topright" }).addTo(map);\n',
            html_str,
            count=1
        )

    # -------------------------
    # 4) Legend: replace any existing legend control with new one
    # -------------------------
    legend_repl = r"""
    // Legend (top-left)
    const legend = L.control({ position: "topleft" });
    legend.onAdd = function() {
      const div = L.DomUtil.create("div", "legend");

      const cellSize = data.cell_size_m;
      const cellTxt = (cellSize && isFinite(cellSize))
        ? `Grid cell: about ${Math.round(cellSize)} m on a side.`
        : "Grid cell: one grid cell.";

      div.innerHTML = `

        <div class="legendGrid">
          <div class="legendItem">
            <div class="swatch" style="background:#f0805a;"></div>
            <div class="legendText">Hot cells (share &gt; 0.1)</div>
          </div>

          <div class="legendItem">
            <img class="icon" src="assets/icon_historical.png" alt="Historical center">
            <div class="legendText">Historical center</div>
          </div>

          <div class="legendItem">
            <img class="icon" src="assets/icon_business.png" alt="Business area">
            <div class="legendText">Business area (polygon)</div>
          </div>

          <div class="legendItem">
            <div class="swatch" style="background:#ffffff;"></div>
            <div class="legendText">${cellTxt}</div>
          </div>

          <div class="legendItem">
            <div class="dot"></div>
            <div class="legendText">Business center (μ)</div>
          </div>

          <div class="legendItem">
            <img class="icon" src="assets/icon_administrative.png" alt="Administrative border">
            <div class="legendText">Administrative border</div>
          </div>
        </div>
      `;

      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      return div;
    };
    legend.addTo(map);
"""
    legend_block_pattern = re.compile(
        r"const\s+legend\s*=\s*L\.control\([\s\S]*?\)\s*;\s*"
        r"legend\.onAdd\s*=\s*function\(\)\s*\{[\s\S]*?\}\s*;\s*"
        r"legend\.addTo\(map\)\s*;\s*",
        re.DOTALL
    )
    if legend_block_pattern.search(html_str):
        html_str = legend_block_pattern.sub(legend_repl, html_str, count=1)
    else:
        html_str = re.sub(
            r'(const\s+map\s*=\s*L\.map\("map"[^;]*;\s*)',
            r'\1' + "\n" + legend_repl + "\n",
            html_str,
            count=1
        )

    # -------------------------
    # 5) Ensure bottom text format (override any existing μ text format)
    # -------------------------
    # Replace the muInfo line inside applyState/applyResult if present
    # (matches both muInfoEl.textContent = `...`; and muInfoEl.textContent = '...';)
    html_str = re.sub(
        r"muInfoEl\.textContent\s*=\s*`[^`]*`;\s*",
        "muInfoEl.textContent = `Distance from Historic to Business Center: ${sep.toFixed(0)}m; Business area: ${areaKm2.toFixed(0)} km²`;\n",
        html_str,
        count=1,
        flags=re.DOTALL
    )

    # If that didn’t match (different block), try a broader replacement for any template using μ:
    html_str = re.sub(
        r"muInfoEl\.textContent\s*=\s*`[^`]*μ[^`]*`;\s*",
        "muInfoEl.textContent = `Distance from Historic to Business Center: ${sep.toFixed(0)}m; Business area: ${areaKm2.toFixed(0)} km²`;\n",
        html_str,
        count=1,
        flags=re.DOTALL
    )

    # -------------------------
    # 6) Restore the old “word label” slider behavior (Baseline, Faster, ...)
    #    and prevent numeric 1.00 labels
    # -------------------------
    # Remove any existing "tEl.textContent = tVal.toFixed(2)" / "aEl..." assignments
    html_str = re.sub(
        r"if\s*\(\s*tEl\s*\)\s*tEl\.textContent\s*=\s*tVal\.toFixed\(\s*2\s*\)\s*;\s*",
        "",
        html_str
    )
    html_str = re.sub(
        r"if\s*\(\s*aEl\s*\)\s*aEl\.textContent\s*=\s*aVal\.toFixed\(\s*2\s*\)\s*;\s*",
        "",
        html_str
    )

    injected_words = r"""
    // ---- injected: restore word labels on vertical sliders ----
    const TRANSPORT_STOPS = [0.50, 0.75, 1.00, 1.25, 1.50];
    const TRANSPORT_WORDS = ["Very slow", "Slower", "Baseline", "Faster", "Very fast"];

    const AMENITY_STOPS = [0.50, 0.75, 1.00, 1.25, 1.50];
    const AMENITY_WORDS = ["Very weak", "Weaker", "Baseline", "Stronger", "Very strong"];

    function _nearestStop(v, stops){
      let bestI = 0, bestD = Infinity;
      for (let i = 0; i < stops.length; i++){
        const d = Math.abs(v - stops[i]);
        if (d < bestD){ bestD = d; bestI = i; }
      }
      return { val: stops[bestI], idx: bestI };
    }

    function _clamp(x, lo, hi){ return Math.max(lo, Math.min(hi, x)); }

    function _valueToTopPct(v, vmin, vmax){
      const p = (_clamp(v, vmin, vmax) - vmin) / (vmax - vmin);
      return (100 * (1 - p));
    }

    function _positionLabel(labelEl, v, vmin, vmax){
      if (!labelEl) return;
      labelEl.style.top = _valueToTopPct(v, vmin, vmax).toFixed(2) + "%";
    }

    function _setActiveDot(dots, idx){
      for (let i = 0; i < dots.length; i++){
        dots[i].classList.toggle("isActive", i === idx);
      }
    }

    function _buildTicks(elId, stops, vmin, vmax){
      const el = document.getElementById(elId);
      if (!el) return [];
      el.innerHTML = "";
      const dots = [];
      for (let i = 0; i < stops.length; i++){
        const d = document.createElement("div");
        d.className = "tickDot";
        d.style.top = _valueToTopPct(stops[i], vmin, vmax).toFixed(2) + "%";
        el.appendChild(d);
        dots.push(d);
      }
      return dots;
    }

    const _tDots = _buildTicks("tTicks", TRANSPORT_STOPS, 0.0, 2.0);
    const _aDots = _buildTicks("aTicks", AMENITY_STOPS, 0.0, 2.0);

    function _updateWordLabels(){
      const tSlider = document.getElementById("tSlider");
      const aSlider = document.getElementById("aSlider");
      const tLabel  = document.getElementById("tVal");
      const aLabel  = document.getElementById("aVal");
      if (!tSlider || !aSlider) return;

      const tV = parseFloat(tSlider.value);
      const aV = parseFloat(aSlider.value);

      const tN = _nearestStop(tV, TRANSPORT_STOPS);
      const aN = _nearestStop(aV, AMENITY_STOPS);

      if (tLabel) tLabel.textContent = TRANSPORT_WORDS[tN.idx];
      if (aLabel) aLabel.textContent = AMENITY_WORDS[aN.idx];

      _positionLabel(tLabel, tV, 0.0, 2.0);
      _positionLabel(aLabel, aV, 0.0, 2.0);

      _setActiveDot(_tDots, tN.idx);
      _setActiveDot(_aDots, aN.idx);
    }

    // Wrap update() so labels stay correct after redraws
    if (typeof update === "function" && !update.__wordLabelWrapped){
      const _origUpdate = update;
      update = function(){
        const r = _origUpdate.apply(this, arguments);
        _updateWordLabels();
        return r;
      };
      update.__wordLabelWrapped = true;
    }

    const _ts = document.getElementById("tSlider");
    const _as = document.getElementById("aSlider");
    if (_ts) _ts.addEventListener("input", _updateWordLabels);
    if (_as) _as.addEventListener("input", _updateWordLabels);
    setTimeout(_updateWordLabels, 0);
    // ---- end injected block ----
"""

    # Inject after listeners or near the end of the main script
    inserted = False
    for needle in [
        'document.getElementById("aSlider").addEventListener("input", scheduleUpdate);',
        'document.getElementById("tSlider").addEventListener("input", scheduleUpdate);',
        "update();"
    ]:
        if needle in html_str:
            html_str = html_str.replace(needle, needle + "\n" + injected_words, 1)
            inserted = True
            break

    if not inserted:
        idx = html_str.rfind("</script>")
        if idx == -1:
            raise ValueError("Could not find </script> to inject word-label logic.")
        html_str = html_str[:idx] + "\n" + injected_words + "\n" + html_str[idx:]

    return html_str




# =========================
# Landing (index.html) generator helpers
# =========================
def build_steps_html(steps: list[dict]) -> str:
    out = []
    for st in steps:
        title = _escape(st.get("title", ""))
        heading = _escape(st.get("heading", st.get("title", "Step")))
        body = _escape(st.get("body", ""))
        hint = _escape(st.get("hint", ""))

        t = float(st.get("t", 1.0))
        a = float(st.get("a", 1.0))

        view_lat = st.get("view_lat", "")
        view_lon = st.get("view_lon", "")
        view_zoom = st.get("view_zoom", "")

        prog = st.get("prog", "")
        idle = bool(st.get("idle", False))
        pad_vh = st.get("pad_vh", None)

        hint_html = f"<p class='stepHint'>{hint}</p>" if hint else ""

        step_classes = "step" + (" stepIdle" if idle else "")
        style_attr = ""
        if pad_vh is not None:
            try:
                pv = float(pad_vh)
                style_attr = f' style="--stepPad:{pv:.1f}vh;"'
            except Exception:
                style_attr = ""

        prog_attr = ""
        try:
            prog_f = float(prog)
            if prog_f == prog_f:
                prog_attr = f' data-prog="{prog_f:.2f}"'
        except Exception:
            prog_attr = ""

        if idle:
            card_html = """<div class="stepCard stepCardIdle" aria-hidden="true"></div>"""
        else:
            card_html = f"""
              <div class="stepCard">
                <div class="stepKicker">Scenario</div>
                <h3>{heading}</h3>
                <p class="stepBody">{body}</p>
                {hint_html}
                <div class="chipRow">
                  <span class="chip">Transport: {t:.2f}</span>
                  <span class="chip">Amenity: {a:.2f}</span>
                </div>
              </div>
            """

        out.append(
            f"""
            <section class="{step_classes}"{style_attr}
              data-title="{title}"
              data-t="{t:.2f}"
              data-a="{a:.2f}"
              data-view-lat="{view_lat}"
              data-view-lon="{view_lon}"
              data-view-zoom="{view_zoom}"{prog_attr}>
              {card_html}
            </section>
            """
        )
    return "\n".join(out)


def build_gallery_html(items, cols=3):
    cards = []
    for it in items:
        src = _escape(it["src"])
        cap = _escape(it.get("caption", ""))
        cap_html = f"<figcaption>{cap}</figcaption>" if cap else ""
        cards.append(
            f"""
            <figure class="imgCard">
              <img src="{src}" alt="{cap}" loading="lazy"/>
              {cap_html}
            </figure>
            """
        )
    return f"""<div class="imgGrid cols{int(cols)}">{''.join(cards)}</div>"""


def build_explain_blocks(blocks):
    out = []
    for b in blocks:
        h = _escape(b.get("heading", ""))
        p = _escape(b.get("body", ""))
        out.append(
            f"""
            <div class="textCard">
              <h3>{h}</h3>
              <p>{p}</p>
            </div>
            """
        )
    return "\n".join(out)


# =========================
# Dashboard page generator (fixed: removed unused height_px)
# =========================
def build_dashboard_page_html(
    page_title: str,
    iframe_src: str,
    iframe_title: str = "Theoretical modelling dashboard",
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_escape(page_title)}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root{{
      --bg: #fafafa;
      --panel: #ffffff;
      --text: #0f0f10;
      --muted: rgba(15,15,16,.68);
      --line: rgba(15,15,16,.12);
      --radius2: 24px;
      --padX: 22px;
      --navH: 68px; /* set by JS */
    }}

    html, body {{ height: 100%; }}
    body{{
      margin:0;
      font-family: Inter, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
    }}
    a{{ color: inherit; text-decoration: none; }}

    .nav{{
      position: sticky;
      top: 0;
      z-index: 50;
      background: rgba(250,250,250,.86);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--line);
    }}

    /* full width */
    .container{{
      width: 100%;
      box-sizing: border-box;
      padding: 0 var(--padX);
    }}

    .navInner{{
      display:flex;
      align-items:center;
      justify-content:space-between;
      padding: 14px 0;
      gap: 16px;
    }}
    .brand{{ font-weight: 700; letter-spacing: -0.02em; }}

    .btn{{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      height: 40px;
      padding: 0 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.86);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
    }}

    /* main fills remaining viewport height */
    main{{
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 18px 0 22px 0;
      min-height: 0;
    }}

    .meta{{
      flex: 0 0 auto;
      margin: 0 0 12px 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}

    .card{{
      flex: 1 1 auto;
      min-height: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius2);
      overflow: hidden;
    }}

    iframe{{
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
      background: #fff;
    }}
  </style>
</head>

<body>
  <div class="nav" id="navEl">
    <div class="container">
      <div class="navInner">
        <div class="brand">{_escape(page_title)}</div>
        <a class="btn" href="index.html#explain">Back</a>
      </div>
    </div>
  </div>

  <main class="container">
    <div class="meta" id="metaEl">{_escape(iframe_title)}</div>
    <div class="card" id="cardEl">
      <iframe id="dashFrame" src="{_escape(iframe_src)}" title="{_escape(iframe_title)}" loading="eager"></iframe>
    </div>
  </main>

  <script>
    (function() {{
      const nav = document.getElementById("navEl");
      const meta = document.getElementById("metaEl");
      const card = document.getElementById("cardEl");

      function sync() {{
        const navH = nav ? (nav.getBoundingClientRect().height || 68) : 68;
        document.documentElement.style.setProperty("--navH", Math.round(navH) + "px");

        /* Ensure the card is always visible and not taller than the viewport */
        const vh = window.innerHeight || 800;
        const metaH = meta ? (meta.getBoundingClientRect().height || 0) : 0;

        /* main has padding top/bottom (18 + 22) = 40 */
        const pad = 40;
        const target = Math.max(520, Math.floor(vh - navH - metaH - pad));
        if (card) card.style.height = target + "px";
      }}

      window.addEventListener("resize", sync);
      setTimeout(sync, 0);
      setTimeout(sync, 250);
    }})();
  </script>
</body>
</html>
"""


# =========================
# Landing (index.html) generator
# =========================
def build_landing_html(config: dict) -> str:
    body_class_attr = ' class="modelLayoutFocus"'

    t = Template(r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>${PAGE_TITLE}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

  <style>
    :root{
      /* from your Style.svg palette */
      --accent: #F0805B;
      --text: #303030;
      --bg: #ffffff;

      --panel: #ffffff;
      --muted: rgba(48,48,48,.70);
      --line: rgba(48,48,48,.14);
      --shadow: 0 14px 40px rgba(0,0,0,.08);
      --radius2: 24px;
      --max: 1160px;
    }

    html{ scroll-behavior: smooth; }
    body{
      margin:0;
      font-family: Inter, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    a{ color: inherit; text-decoration: none; }
    .container{ max-width: var(--max); margin: 0 auto; padding: 0 22px; }

    .nav{
      position: sticky;
      top: 0;
      z-index: 50;
      background: rgba(255,255,255,.86);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--line);
    }
    .navInner{
      display:flex;
      align-items:center;
      justify-content:space-between;
      padding: 14px 0;
      gap: 16px;
    }
    .brand{ font-weight: 700; letter-spacing: -0.02em; }
    .navLinks{ display:flex; gap: 14px; flex-wrap: wrap; justify-content: flex-end; }
    .navLinks a{
      font-size: 13px;
      color: var(--muted);
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid transparent;
    }
    .navLinks a:hover{
      color: var(--text);
      border-color: var(--line);
      background: rgba(255,255,255,.7);
    }

    /* HERO, overlap like your reference (pic 2) */
    .hero{
      position: relative;
      padding: 84px 0 54px 0;
      overflow: hidden;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .hero .container{
      position: relative;
    }

    .heroGrid{
      position: relative;
      min-height: 460px;
    }

    .heroText{
      position: relative;
      z-index: 2;
      max-width: 920px;   /* wider so title becomes 2 lines */
      padding-right: 20px;
    }

    h1{
      font-size: clamp(44px, 5.2vw, 76px);
      line-height: 1.02;
      letter-spacing: -0.04em;
      margin: 0 0 18px 0;
      font-weight: 900;
      color: var(--accent);
      max-width: 22ch;  /* helps keep it near 2 lines */
    }

    .sub{
      font-size: 20px;
      color: var(--text);
      line-height: 1.55;
      max-width: 60ch;
      margin: 0 0 26px 0;
      opacity: 0.92;
    }

    .ctaRow{ display:flex; gap: 12px; flex-wrap: wrap; align-items:center; }

    .btn{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      height: 44px;
      padding: 0 18px;
      border-radius: 999px;
      border: 1px solid var(--accent);
      background: transparent;
      font-weight: 800;
      font-size: 14px;
      color: var(--accent);
      box-sizing: border-box;
    }

    .btnPrimary{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }

    /* Hero artwork behind text */
    .heroArt{
      position: absolute;
      top: 50%;
      right: -140px;              /* negative gives the overlap feel */
      transform: translateY(-50%);
      z-index: 1;
      width: min(1120px, 78vw);
      display: flex;
      align-items: center;
      justify-content: flex-end;
      pointer-events: none;
    }

    .heroArt img{
      width: 100%;
      height: auto;
      display:block;
      opacity: 0.98;

      /* fade on the left like your reference */
      -webkit-mask-image: linear-gradient(to right,
        transparent 0%,
        rgba(0,0,0,.20) 16%,
        rgba(0,0,0,1) 40%,
        rgba(0,0,0,1) 100%);
      mask-image: linear-gradient(to right,
        transparent 0%,
        rgba(0,0,0,.20) 16%,
        rgba(0,0,0,1) 40%,
        rgba(0,0,0,1) 100%);
    }

    /* Sections (keep your original look) */
    .section{ padding: 46px 0; }
    .sectionTitle{
      display:flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 18px;
    }
    .sectionTitle h2{ margin:0; font-size: 22px; letter-spacing: -0.02em; }
    .sectionTitle p{ margin:0; color: var(--muted); font-size: 13px; max-width: 58ch; line-height: 1.5; }

    .imgGrid{ display:grid; gap: 14px; }
    .imgGrid.cols3{ grid-template-columns: repeat(3, 1fr); }
    .imgGrid.cols2{ grid-template-columns: repeat(2, 1fr); }
    .imgCard{
      margin: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius2);
      overflow:hidden;
      box-shadow: 0 1px 0 rgba(0,0,0,.04);
    }
    .imgCard img{ width: 100%; height: 280px; object-fit: cover; display:block; }
    .imgCard figcaption{ padding: 12px 14px; font-size: 13px; color: var(--muted); line-height: 1.4; }

    .modelWrap{
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .modelHeader{ padding: 46px 0 14px 0; }
    .modelGrid{
      display:grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 18px;
      padding-bottom: 48px;
    }
    .stepsCol{ padding-right: 10px; }

    .stickyViz{
      position: sticky;
      top: 74px;
      height: calc(100vh - 96px);
      border: 1px solid var(--line);
      border-radius: var(--radius2);
      overflow:hidden;
      background: #f3f3f3;
      box-shadow: var(--shadow);
    }
    .stickyViz iframe{ width: 100%; height: 100%; border: 0; display:block; background: #fff; }

    .modelMiniBar{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap: 14px;
      padding: 10px 0 16px 0;
      color: var(--muted);
      font-size: 13px;
    }
    .progress{
      height: 6px;
      flex: 1;
      background: rgba(0,0,0,.08);
      border-radius: 999px;
      overflow:hidden;
    }
    .progress > div{ height: 100%; width: 0%; background: #111; }

    .step{ padding: var(--stepPad, 24vh) 0; }
    .step:first-child:not(.stepIdle){ padding-top: 14vh; }
    .step:last-child:not(.stepIdle){ padding-bottom: 14vh; }

    .stepCard{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: var(--radius2);
      padding: 16px 16px 14px 16px;
      box-shadow: 0 1px 0 rgba(0,0,0,.04);
      transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
    }
    .step.is-active .stepCard{
      border-color: rgba(0,0,0,.55);
      box-shadow: 0 18px 46px rgba(0,0,0,.10);
      transform: translateY(-1px);
    }
    .stepKicker{ font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
    .stepCard h3{ margin: 0 0 8px 0; font-size: 18px; letter-spacing: -0.02em; }
    .stepBody{ margin: 0 0 10px 0; color: rgba(0,0,0,.72); font-size: 14px; line-height: 1.55; }
    .stepHint{ margin: 0 0 10px 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .chipRow{ display:flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
    .chip{ display:inline-flex; padding: 6px 10px; border-radius: 999px; border: 1px solid var(--line); background: rgba(250,250,250,.9); font-size: 12px; color: rgba(0,0,0,.72); }

    .stepIdle .stepCard{
      opacity: 0;
      pointer-events: none;
      border-color: transparent;
      box-shadow: none;
      transform: none;
    }
    .stepIdle.is-active .stepCard{
      border-color: transparent;
      box-shadow: none;
      transform: none;
    }

    .explainGrid{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
    .textCard{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius2);
      padding: 18px 18px 16px 18px;
      box-shadow: 0 1px 0 rgba(0,0,0,.04);
    }
    .textCard h3{ margin: 0 0 8px 0; font-size: 16px; }
    .textCard p{ margin:0; color: rgba(0,0,0,.72); font-size: 14px; line-height: 1.6; }

    footer{ border-top: 1px solid var(--line); padding: 26px 0 40px 0; color: var(--muted); font-size: 13px; line-height: 1.5; }

    @media (max-width: 980px){
      .hero{ padding: 62px 0 40px 0; }
      .heroGrid{ min-height: 0; }
      .heroText{ max-width: none; }
      h1{ font-size: clamp(38px, 8vw, 58px); max-width: none; }

      .heroArt{
        position: relative;
        top: auto;
        right: auto;
        transform: none;
        width: auto;
        margin-top: 18px;
        justify-content: center;
      }
      .heroArt img{
        width: min(920px, 96vw);
        -webkit-mask-image: none;
        mask-image: none;
      }

      .modelGrid{ grid-template-columns: 1fr; }
      .stickyViz{ position: relative; top: 0; height: 70vh; }
      .imgGrid.cols3{ grid-template-columns: 1fr; }
      .imgGrid.cols2{ grid-template-columns: 1fr; }
      .explainGrid{ grid-template-columns: 1fr; }
      .step{ padding: var(--stepPad, 16vh) 0; }
    }
  </style>
</head>

<body id="top""" + body_class_attr + r""">
  <div class="nav">
    <div class="container">
      <div class="navInner">
        <div class="brand">${BRAND}</div>
        <div class="navLinks">
          <a href="#gallery1">Gallery</a>
          <a href="#model">Model</a>
          <a href="#gallery2">More</a>
          <a href="#explain">Explanation</a>
        </div>
      </div>
    </div>
  </div>

  <header class="hero">
    <div class="container">
      <div class="heroGrid">
        <div class="heroText">
          <h1>${HERO_TITLE}</h1>
          <p class="sub">${HERO_SUB}</p>
          <div class="ctaRow">
            <a class="btn btnPrimary" href="#model">${CTA_PRIMARY}</a>
            <a class="btn" href="#explain">${CTA_SECONDARY}</a>
          </div>
        </div>

        <div class="heroArt" aria-hidden="true">
          <img src="${HERO_IMAGE}" alt="" loading="eager">
        </div>
      </div>
    </div>
  </header>

  <section class="section" id="gallery1">
    <div class="container">
      <div class="sectionTitle">
        <h2>${G1_TITLE}</h2>
        <p>${G1_SUB}</p>
      </div>
      ${GALLERY1_HTML}
    </div>
  </section>

  <section class="modelWrap" id="model">
    <div class="container">
      <div class="modelHeader">
        <div class="sectionTitle">
          <h2>${MODEL_TITLE}</h2>
          <p>${MODEL_SUB}</p>
        </div>

        <div class="modelMiniBar">
          <div id="stepName">Baseline</div>
          <div class="progress"><div id="progBar"></div></div>
        </div>
      </div>

      <div class="modelGrid">
        <div class="stepsCol">
          ${STEPS_HTML}
        </div>

        <div class="stickyViz">
          <iframe id="viz" src="${VIZ_FILENAME}" title="Interactive model" loading="lazy"></iframe>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="gallery2">
    <div class="container">
      <div class="sectionTitle">
        <h2>${G2_TITLE}</h2>
        <p>${G2_SUB}</p>
      </div>
      ${GALLERY2_HTML}
    </div>
  </section>

  <section class="section" id="explain">
    <div class="container">
      <div class="sectionTitle">
        <h2>${EXPLAIN_TITLE}</h2>
        <p>${EXPLAIN_SUB}</p>
      </div>
      <div class="explainGrid">
        ${EXPLAIN_BLOCKS}
      </div>
      ${EXTRA_EXPLAIN_HTML}
    </div>
  </section>

  <footer>
    <div class="container">
      ${FOOTER_TEXT}
    </div>
  </footer>

  <script src="https://unpkg.com/scrollama"></script>
  <script>
    const iframe = document.getElementById("viz");
    const steps = Array.from(document.querySelectorAll(".step"));
    const stepName = document.getElementById("stepName");
    const progBar = document.getElementById("progBar");
    const stickyVizEl = document.querySelector("#model .stickyViz");
    const navEl = document.querySelector(".nav");

    const pending = { sliders: null, view: null, invalidate: false };

    function _postToViz(msg) {
      if (!iframe || !iframe.contentWindow) return;
      iframe.contentWindow.postMessage(msg, "*");
    }

    function _remember(msg) {
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "setSliders") pending.sliders = msg;
      if (msg.type === "setView") pending.view = msg;
      if (msg.type === "invalidateSize") pending.invalidate = true;
    }

    function replayPending() {
      if (!iframe || !iframe.contentWindow) return;
      _postToViz({ type: "ping" });
      if (pending.sliders) _postToViz(pending.sliders);
      if (pending.view) _postToViz(pending.view);
      if (pending.invalidate) _postToViz({ type: "invalidateSize" });
    }

    function sendToViz(msg) {
      _remember(msg);
      if (!iframe || !iframe.contentWindow) return;
      _postToViz(msg);
    }

    if (iframe) {
      iframe.addEventListener("load", () => {
        replayPending();
        sendToViz({ type: "invalidateSize" });
      });
    }

    function syncNavHeightVar() {
      if (!navEl) return;
      const h = navEl.getBoundingClientRect().height || 68;
      document.documentElement.style.setProperty("--navH", Math.round(h) + "px");
    }

    window.addEventListener("resize", () => {
      syncNavHeightVar();
      schedulePinnedCheck();
    });

    setTimeout(syncNavHeightVar, 0);

    let lastIdx = -1;
    function activateStep(el, idx) {
      if (!el) return;
      if (idx === lastIdx) return;
      lastIdx = idx;

      steps.forEach(s => s.classList.remove("is-active"));
      el.classList.add("is-active");

      const title = el.dataset.title || ("Step " + String(idx + 1));
      if (stepName) stepName.textContent = title;

      if (el.classList.contains("stepIdle")) {
        const pctIdle = parseFloat(el.dataset.prog);
        if (progBar && isFinite(pctIdle)) {
          progBar.style.width = String(pctIdle.toFixed(1)) + "%";
        }
        return;
      }

      const t = parseFloat(el.dataset.t);
      const a = parseFloat(el.dataset.a);

      const lat = parseFloat(el.dataset.viewLat);
      const lon = parseFloat(el.dataset.viewLon);
      const zoom = parseFloat(el.dataset.viewZoom);

      if (isFinite(t) && isFinite(a)) sendToViz({ type: "setSliders", t: t, a: a });
      if (isFinite(lat) && isFinite(lon) && isFinite(zoom)) sendToViz({ type: "setView", lat: lat, lon: lon, zoom: zoom });

      const pct = parseFloat(el.dataset.prog);
      if (progBar) {
        if (isFinite(pct)) {
          progBar.style.width = String(pct.toFixed(1)) + "%";
        } else {
          const fallback = steps.length <= 1 ? 100 : (idx / (steps.length - 1)) * 100;
          progBar.style.width = String(fallback.toFixed(1)) + "%";
        }
      }
    }

    let pinnedOn = false;

    function setPinned(on) {
      const next = !!on;
      if (pinnedOn === next) return;
      pinnedOn = next;
      document.body.classList.toggle("modelPinned", pinnedOn);

      setTimeout(() => {
        sendToViz({ type: "invalidateSize" });
        replayPending();
      }, 140);
    }

    function computePinned() {
      if (!stickyVizEl) { setPinned(false); return; }

      const cs = getComputedStyle(stickyVizEl);
      const pos = cs.position;
      if (pos !== "sticky" && pos !== "-webkit-sticky") { setPinned(false); return; }

      const r = stickyVizEl.getBoundingClientRect();
      const topPx = parseFloat(cs.top) || 0;
      const vh = window.innerHeight || 800;

      const delta = Math.abs(r.top - topPx);
      const pinned = pinnedOn ? (delta <= 26) : (delta <= 2);
      const visible = r.bottom > (topPx + 140) && r.top < (vh - 140);

      setPinned(pinned && visible);
    }

    let pinRAF = 0;
    function schedulePinnedCheck() {
      cancelAnimationFrame(pinRAF);
      pinRAF = requestAnimationFrame(computePinned);
    }

    window.addEventListener("scroll", schedulePinnedCheck, { passive: true });

    if (stickyVizEl && "ResizeObserver" in window) {
      const ro = new ResizeObserver(() => {
        setTimeout(() => sendToViz({ type: "invalidateSize" }), 140);
      });
      ro.observe(stickyVizEl);
    }

    const scroller = scrollama();
    scroller
      .setup({ step: ".step", offset: 0.62 })
      .onStepEnter((resp) => {
        schedulePinnedCheck();
        activateStep(resp.element, resp.index);
      })
      .onStepExit((resp) => {
        if (resp.direction === "up" && resp.index > 0) {
          const prev = resp.index - 1;
          activateStep(steps[prev], prev);
        }
        schedulePinnedCheck();
      });

    window.addEventListener("message", (event) => {
      if (event.data && event.data.type === "vizReady") {
        replayPending();
        sendToViz({ type: "invalidateSize" });
      }
    });

    syncNavHeightVar();
    schedulePinnedCheck();
    setTimeout(() => {
      if (steps.length) activateStep(steps[0], 0);
      replayPending();
      sendToViz({ type: "invalidateSize" });
      schedulePinnedCheck();
    }, 700);
  </script>

</body>
</html>
""")
    return t.substitute(config)


# =========================
# One function to write full site
# =========================
def write_full_scrolly_site(
    out_dir: str,
    interactive_html: str,
    viz_filename: str = "yerevan_continuous_two_sliders.html",
    landing_filename: str = "index.html",
    title: str = "Yerevan scrolly",
    extra_html_files: dict[str, str] | None = None,
    embed_extra_filename: str | None = None,
    compare_html_src_path: str | None = None,
    compare_filename: str = "compare_business_areas.html",
    hero_image_src_path: str | None = None,
    hero_image_dst_name: str = "Mask group.png",  # exact asset filename you want
):
    os.makedirs(out_dir, exist_ok=True)

    # 1) Patch the interactive (viz)
    viz_html = interactive_html
    viz_html = patch_interactive_ui_left_right_vertical_sliders(viz_html)
    viz_html = patch_center_map_button_zoom(viz_html, center_zoom=12.0)
    viz_html = patch_interactive_for_scrolly(viz_html)

    viz_path = os.path.join(out_dir, viz_filename)
    with open(viz_path, "w", encoding="utf-8") as f:
        f.write(viz_html)

    # 2) Extra HTML files
    if extra_html_files:
        for fname, html_text in extra_html_files.items():
            Path(os.path.join(out_dir, fname)).write_text(html_text, encoding="utf-8")

    # 3) Hero image: always from assets/Mask group.png if present
    assets_dir = os.path.join("assets")
    os.makedirs(assets_dir, exist_ok=True)
    desired_rel = (hero_image_dst_name).replace(os.sep, "/")
    desired_abs = os.path.abspath(os.path.join("assets", hero_image_dst_name))
    print(desired_abs)
    # If user provides a source image, ensure it's in out_dir/assets with the right name
    if hero_image_src_path:
        if not os.path.exists(hero_image_src_path):
            raise FileNotFoundError(f"Missing hero image: {hero_image_src_path}")

        src_abs = os.path.abspath(hero_image_src_path)

        # Avoid SameFileError
        same = False
        try:
            if os.path.exists(desired_abs) and os.path.samefile(src_abs, desired_abs):
                same = True
        except Exception:
            same = (src_abs == desired_abs)

        if not same:
            shutil.copyfile(src_abs, desired_abs)

    # Choose hero image path for HTML
    hero_image_rel = desired_abs
    
    # 4) Gallery placeholders
    g1 = [
        {"src": svg_placeholder_data_uri("Context image 1"), "caption": "Replace with assets/ images"},
        {"src": svg_placeholder_data_uri("Context image 2"), "caption": "Replace with assets/ images"},
        {"src": svg_placeholder_data_uri("Context image 3"), "caption": "Replace with assets/ images"},
    ]
    g2 = [
        {"src": svg_placeholder_data_uri("More image 1"), "caption": "Replace with assets/ images"},
        {"src": svg_placeholder_data_uri("More image 2"), "caption": "Replace with assets/ images"},
    ]

    # 5) Steps
    scenario_steps = [
        dict(
            title="Baseline",
            heading="Baseline assumptions",
            body="Reference case for transport and amenity strength.",
            hint="Scroll to switch scenarios. The model updates immediately.",
            t=1.00,
            a=1.00
        ),
        dict(
            title="Faster transport",
            heading="Faster transport",
            body="Higher transport speed multiplier lowers time costs.",
            t=1.50,
            a=1.00
        ),
        dict(
            title="Slower transport",
            heading="Slower transport",
            body="Lower transport speed multiplier raises time costs.",
            t=0.50,
            a=1.00
        ),
        dict(
            title="Historic pull",
            heading="Historic amenities matter more",
            body="Higher amenity multiplier strengthens amenity-related effects.",
            t=1.00,
            a=1.50
        ),
        dict(
            title="Weaker amenities",
            heading="Historic amenities matter less",
            body="Lower amenity multiplier weakens amenity-related effects.",
            t=1.00,
            a=0.50
        ),
    ]

    scenario_steps = assign_progress_percent(scenario_steps)
    steps_all = add_idle_spacer_steps(
        scenario_steps,
        lead_count=IDLE_LEAD_STEPS,
        tail_count=IDLE_TAIL_STEPS,
        lead_pad_vh=IDLE_LEAD_PAD_VH,
        tail_pad_vh=IDLE_TAIL_PAD_VH,
    )

    # 6) Explain blocks
    explain_blocks = [
        dict(
            heading="Idle scroll",
            body="Extra invisible spacer steps before the first and after the last scenario keep the model pinned long enough for the minibar and progress to be visible."
        ),
        dict(
            heading="Width",
            body="The model section uses near-full viewport width with small margins."
        ),
        dict(
            heading="Cards",
            body="Scenario cards are fixed-width and compact so the map is large."
        ),
        dict(
            heading="Menu + bar",
            body="The top menu is fixed; the progress bar appears only when the map is pinned and sits below the menu."
        ),
    ]

    dashboard_page = "dashboard.html"
    dashboard_button_html = ""
    if embed_extra_filename:
        dashboard_button_html = f"""
        <div style="display:flex; flex-direction:column; gap:12px; margin-top: 12px;">
          <a class="btn btnPrimary" href="{_escape(dashboard_page)}">Open theoretical dashboard</a>
        </div>
        """

    # 7) Landing config (hero image is real asset now)
    config = {
        "PAGE_TITLE": title,
        "BRAND": title,
        "HERO_TITLE": "Moving centers<br>of Yerevan",
        "HERO_SUB": "How and why the business centers of cities are moving away from historical centers",
        "CTA_PRIMARY": "Read story",
        "CTA_SECONDARY": "Learn model",
        "HERO_IMAGE": hero_image_rel,
        "HERO_IMAGE_CAPTION": "",

        "G1_TITLE": "Context",
        "G1_SUB": "Supporting visuals before the model.",
        "GALLERY1_HTML": build_gallery_html(g1, cols=3),

        "MODEL_TITLE": "Interactive model",
        "MODEL_SUB": "Scroll-driven scenarios with a sticky frame.",
        "STEPS_HTML": build_steps_html(steps_all),
        "VIZ_FILENAME": viz_filename,

        "G2_TITLE": "More visuals",
        "G2_SUB": "More figures or screenshots after the model.",
        "GALLERY2_HTML": build_gallery_html(g2, cols=2),

        "EXPLAIN_TITLE": "Explanation",
        "EXPLAIN_SUB": "Short blocks explaining what is happening.",
        "EXPLAIN_BLOCKS": build_explain_blocks(explain_blocks),
        "EXTRA_EXPLAIN_HTML": "",

        "FOOTER_TEXT": f"""
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div>Static bundle. Serve the folder as a website to share it.</div>
            {dashboard_button_html}
          </div>
        """,
    }

    # 8) Compare page copy + patch (optional)
    if compare_html_src_path:
        if not os.path.exists(compare_html_src_path):
            raise FileNotFoundError(f"Missing compare HTML: {compare_html_src_path}")

        dst = os.path.join(out_dir, compare_filename)
        shutil.copyfile(compare_html_src_path, dst)

        txt = Path(dst).read_text(encoding="utf-8")
        txt = patch_compare_add_height_postmessage(txt)
        Path(dst).write_text(txt, encoding="utf-8")

    # 9) Build landing + your existing model patch
    landing_html = build_landing_html(config)
    landing_html = patch_landing_for_model_focus_zoom(landing_html)

    if compare_html_src_path:
        landing_html = patch_landing_add_compare_embed_css(landing_html)
        landing_html = patch_landing_insert_compare_before_explain(
            landing_html,
            compare_href=compare_filename,
            title="Заголовок блока",
            sub="Сравнение бизнес-ареалов городов. Фигуры приведены к одной шкале и центрированы по историческому центру (0,0).",
        )
        landing_html = patch_landing_add_compare_autosize_js(landing_html)

    landing_path = os.path.join(out_dir, landing_filename)
    with open(landing_path, "w", encoding="utf-8") as f:
        f.write(landing_html)

    # 10) Dashboard page (optional)
    if embed_extra_filename:
        dash_html = build_dashboard_page_html(
            page_title=f"{title} | Dashboard",
            iframe_src=embed_extra_filename,
            iframe_title="Theoretical modelling dashboard",
        )
        Path(os.path.join(out_dir, dashboard_page)).write_text(dash_html, encoding="utf-8")

    return viz_path, landing_path
