# build_compare_business_areas_html.py
#
# Builds ONE HTML that:
# 1) loads ALL city business-area polygons from POLY_DIR/*.geojson (fixed polygons)
# 2) embeds the Yerevan precomputed payload as gzip+base64 extracted from:
#    data/yerevan_interactive/yerevan_business_polygon_precomputed.html
# 3) renders both on a comparable METERS scale, centered at historic center (0,0)
#
# Inputs expected:
# - data/city_centers/city_centers_business_polygon.csv
# - data/city_centers/business_area_polygons_geojson/*.geojson
# - data/yerevan_interactive/yerevan_business_polygon_precomputed.html
#
# Output:
# - data/compare_business_areas/compare_business_areas.html

import os
import re
import json
import math
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import affinity

CITY_CSV = "data/city_centers/city_centers_business_polygon.csv"
POLY_DIR = "data/city_centers/business_area_polygons_geojson"
YEREVAN_PRECOMP_HTML = "data/yerevan_interactive/yerevan_business_polygon_precomputed.html"

OUT_DIR = "data/compare_business_areas"
OUT_HTML = os.path.join(OUT_DIR, "compare_business_areas.html")
os.makedirs(OUT_DIR, exist_ok=True)


def extract_payload_b64_from_yerevan_html(html_text: str) -> str:
    """
    Extracts:
      const PAYLOAD_GZ_B64 = "....";
    Returns the base64 string.
    """
    m = re.search(r'PAYLOAD_GZ_B64\s*=\s*"([^"]+)"\s*;', html_text)
    if not m:
        m = re.search(r"PAYLOAD_GZ_B64\s*=\s*'([^']+)'\s*;", html_text)
    if not m:
        raise RuntimeError("Could not find PAYLOAD_GZ_B64 in Yerevan HTML")
    return m.group(1)


def geom_to_meters_geojson_like(geom):
    if geom is None or geom.is_empty:
        return None

    if geom.geom_type == "Polygon":
        rings = []
        rings.append([[float(x), float(y)] for x, y in geom.exterior.coords])
        for interior in geom.interiors:
            rings.append([[float(x), float(y)] for x, y in interior.coords])
        return {"type": "Polygon", "coordinates": rings}

    if geom.geom_type == "MultiPolygon":
        polys = []
        for p in geom.geoms:
            rings = []
            rings.append([[float(x), float(y)] for x, y in p.exterior.coords])
            for interior in p.interiors:
                rings.append([[float(x), float(y)] for x, y in interior.coords])
            polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys}

    return None


def load_csv_metadata(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["city"] = df["city"].astype(str).str.strip()
    return df


def safe_float(x):
    try:
        v = float(x)
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def choose_utm_crs_for_polygon(poly_ll_gdf: gpd.GeoDataFrame, fallback_lonlat=None) -> str:
    try:
        crs = poly_ll_gdf.estimate_utm_crs()
        if crs is not None:
            return crs.to_string()
    except Exception:
        pass

    if fallback_lonlat:
        lon, lat = fallback_lonlat
        zone = int((lon + 180.0) // 6) + 1
        epsg = (32600 + zone) if (lat >= 0) else (32700 + zone)
        return f"EPSG:{epsg}"

    return "EPSG:3857"


def load_city_polygons_payload(csv_path: str, poly_dir: str):
    df = load_csv_metadata(csv_path)
    meta = {r["city"]: r for _, r in df.iterrows()}

    files = sorted(glob.glob(os.path.join(poly_dir, "*.geojson")))
    if not files:
        raise RuntimeError(f"No geojson polygons found in {poly_dir}")

    cities = {}
    max_abs = 0.0
    skipped = []

    for fp in files:
        try:
            gdf = gpd.read_file(fp)
        except Exception as e:
            skipped.append((os.path.basename(fp), f"read_error:{type(e).__name__}"))
            continue

        if gdf.empty or gdf.geometry.isna().all():
            skipped.append((os.path.basename(fp), "empty_geometry"))
            continue

        city = None
        for col in ["city", "name"]:
            if col in gdf.columns:
                v = str(gdf[col].iloc[0]).strip()
                if v and v.lower() != "nan":
                    city = v
                    break
        if not city:
            city = os.path.splitext(os.path.basename(fp))[0]

        # Yerevan is dynamic in this app
        if city.strip().lower() == "yerevan, armenia":
            continue

        geom_ll = gdf.geometry.iloc[0]
        if geom_ll is None or geom_ll.is_empty:
            skipped.append((city, "empty_geom"))
            continue

        row = meta.get(city, None)

        historic_lon = safe_float(row.get("historic_lon")) if row is not None else None
        historic_lat = safe_float(row.get("historic_lat")) if row is not None else None
        utm_crs = str(row.get("utm_crs")).strip() if row is not None else ""

        if historic_lon is None or historic_lat is None:
            skipped.append((city, "missing_historic_lonlat"))
            continue

        poly_ll_gdf = gpd.GeoDataFrame({"city": [city]}, geometry=[geom_ll], crs=gdf.crs or "EPSG:4326")
        poly_ll_gdf = poly_ll_gdf.to_crs("EPSG:4326")

        if (not utm_crs) or utm_crs.lower() == "nan":
            utm_crs = choose_utm_crs_for_polygon(poly_ll_gdf, fallback_lonlat=(historic_lon, historic_lat))

        try:
            geom_utm = poly_ll_gdf.to_crs(utm_crs).geometry.iloc[0]
            g_utm = gpd.GeoSeries([Point(historic_lon, historic_lat)], crs="EPSG:4326").to_crs(utm_crs).iloc[0]
        except Exception as e:
            skipped.append((city, f"project_error:{type(e).__name__}"))
            continue

        gx, gy = float(g_utm.x), float(g_utm.y)
        shifted = affinity.translate(geom_utm, xoff=-gx, yoff=-gy)

        gj = geom_to_meters_geojson_like(shifted)
        if gj is None:
            skipped.append((city, "unsupported_geom_type"))
            continue

        area_km2 = None
        if row is not None:
            area_km2 = safe_float(row.get("business_area_km2"))
        if area_km2 is None:
            area_km2 = float(shifted.area) / 1e6

        def update_max_abs(obj):
            nonlocal max_abs
            if obj["type"] == "Polygon":
                for ring in obj["coordinates"]:
                    for x, y in ring:
                        max_abs = max(max_abs, abs(float(x)), abs(float(y)))
            else:
                for poly in obj["coordinates"]:
                    for ring in poly:
                        for x, y in ring:
                            max_abs = max(max_abs, abs(float(x)), abs(float(y)))

        update_max_abs(gj)

        cities[city] = {
            "geom_m": gj,
            "area_km2": float(area_km2),
        }

    extent_m = float(max_abs) * 1.10 if max_abs > 0 else 5000.0

    print(f"Polygons found in folder: {len(files)}")
    print(f"Loaded cities: {len(cities)}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for nm, reason in skipped[:80]:
            print("  -", nm, "=>", reason)

    return {"extent_m": extent_m, "cities": cities}


HTML_TEMPLATE = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Commercial areas comparison</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root { --border:#e6e6e6; --text:#111; --muted:#666; --bg:#fff; --accent:#56d3e5; }
    body { margin:0; font-family: Arial, sans-serif; background:var(--bg); color:var(--text); }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 28px 22px 18px; }
    .desc { max-width: 980px; color: var(--muted); line-height: 1.35; font-size: 18px; margin-bottom: 22px; }

    .card {
      border-top: 1px solid var(--border);
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 0;
      min-height: 560px;
    }

    .left { padding: 20px 18px; border-right: 1px solid var(--border); }
    .sectionTitle { font-weight: 700; margin: 14px 0 10px; }
    .label { color: var(--text); margin-bottom: 8px; font-size: 14px; }
    .help { color: var(--muted); font-size: 12px; margin-top: 6px; }

    select{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      font-size: 14px;
      outline: none;
      background: #fff;
    }

    .sliderBlock { margin-top: 20px; }
    .sliderName { font-weight: 700; margin: 18px 0 10px; }
    .sliderRow { display:flex; align-items:center; gap: 10px; }

    .sliderEnds{
      display:flex;
      justify-content:space-between;
      margin-top:6px;
      font-size:12px;
      color:var(--muted);
    }

    input[type="range"]{
      -webkit-appearance:none;
      appearance:none;
      width:100%;
      height:4px;
      border-radius:999px;
      background:var(--accent);
      outline:none;
    }

    input[type="range"]::-webkit-slider-runnable-track{
      height:4px;
      border-radius:999px;
      background:var(--accent);
    }

    /* Circle thumb (WebKit) */
    input[type="range"]::-webkit-slider-thumb{
      -webkit-appearance:none;
      appearance:none;
      width:14px;
      height:14px;
      border:none;
      border-radius:50%;
      background:var(--accent);
      margin-top:-5px; /* centers the circle on a 4px track */
      cursor:pointer;
    }

    input[type="range"]::-moz-range-track{
      height:4px;
      border:none;
      border-radius:999px;
      background:var(--accent);
    }

    /* Circle thumb (Firefox) */
    input[type="range"]::-moz-range-thumb{
      width:14px;
      height:14px;
      border:none;
      border-radius:50%;
      background:var(--accent);
      cursor:pointer;
    }

    .right { position: relative; padding: 0; display:flex; flex-direction: column; }
    .plotWrap { position: relative; flex: 1 1 auto; min-height: 520px; background: #fff; }

    .plotLabel {
      position:absolute; color: #9a9a9a; font-size: 14px;
      user-select:none; pointer-events:none;
    }
    .plotLabel.top { top: 10px; left: 50%; transform: translateX(-50%); }
    .plotLabel.bottom { bottom: 10px; left: 50%; transform: translateX(-50%); }
    .plotLabel.left { left: 10px; top: 50%; transform: translateY(-50%); }
    .plotLabel.right { right: 10px; top: 50%; transform: translateY(-50%); }

    svg { width: 100%; height: 100%; display:block; }

    .legendRow {
      display:flex; align-items:center; gap:14px; flex-wrap:wrap;
      padding: 12px 18px 6px;
    }
    .legendItem { display:flex; align-items:center; gap:8px; color: var(--muted); font-size: 13px; }
    .swatch { width: 14px; height: 10px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.15); }

    .kpi {
      margin-top: 14px; padding-top: 14px;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .kpi b { color: var(--text); }
  </style>
</head>

<body>
  <div class="wrap">
    <div class="desc">
      Comparison of commercial zones of various cities with the commercial activity zone of Yerevan
    </div>

    <div class="card">
      <div class="left">
        <div class="label">Select the city you want to compare Yerevan with</div>
        <select id="citySelect"></select>

        <div class="sectionTitle" style="margin-top:18px;">Set up parameters for Yerevan</div>

        <div class="sliderBlock">
          <div class="sliderName">Transport factor</div>
          <div class="sliderRow">
            <input id="tSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          </div>
          <div class="sliderEnds"><span>smaller</span><span>faster</span></div>

          <div class="sliderName" style="margin-top:18px;">Historic amenity strength</div>
          <div class="sliderRow">
            <input id="aSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          </div>
          <div class="sliderEnds"><span>weaker</span><span>stronger</span></div>

          <div class="kpi">
            <div><b>Yerevan:</b> <span id="yKpi">...</span></div>
            <div><b>Comparison city:</b> <span id="cKpi">...</span></div>
          </div>
        </div>
      </div>

      <div class="right">
        <div class="legendRow">
          <div class="legendItem"><span class="swatch" style="background: rgba(0, 155, 190, 0.18);"></span>Yerevan commercial area</div>
          <div class="legendItem"><span class="swatch" style="background: rgba(240, 145, 110, 0.18);"></span><span id="legendCityName">...</span> commercial area</div>
          <div class="legendItem"><span class="swatch" style="background: rgba(220, 60, 60, 0.95); border:none;"></span>historical centers of the cities</div>
        </div>

        <div class="plotWrap">
          <div class="plotLabel top">up</div>
          <div class="plotLabel bottom">down</div>
          <div class="plotLabel left">left</div>
          <div class="plotLabel right">right</div>

          <svg id="plot" preserveAspectRatio="xMidYMid meet">
            <line id="xAxis" x1="0" y1="0" x2="0" y2="0" stroke="#d7d7d7" stroke-width="1"></line>
            <line id="yAxis" x1="0" y1="0" x2="0" y2="0" stroke="#d7d7d7" stroke-width="1"></line>

            <path id="cityPoly" d="" fill="rgba(240, 145, 110, 0.18)" stroke="rgba(240, 145, 110, 0.95)" stroke-width="2" fill-rule="evenodd"></path>
            <path id="yerPoly" d="" fill="rgba(0, 155, 190, 0.18)" stroke="rgba(0, 155, 190, 0.95)" stroke-width="2" fill-rule="evenodd"></path>

            <circle id="originDot" r="6" cx="0" cy="0" fill="rgba(220, 60, 60, 0.95)"></circle>
          </svg>
        </div>
      </div>
    </div>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.0/proj4.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js"></script>

  <script>
    const cityPayload = __CITY_PAYLOAD__;

    // embedded Yerevan gzip+base64
    const YEREVAN_PAYLOAD_GZ_B64 = "__YEREVAN_PAYLOAD_GZ_B64__";

    function loadYerevanPayload() {
      const bin = Uint8Array.from(atob(YEREVAN_PAYLOAD_GZ_B64), c => c.charCodeAt(0));
      const jsonStr = pako.ungzip(bin, { to: "string" });
      return JSON.parse(jsonStr);
    }

    const yerevanData = loadYerevanPayload();

    proj4.defs("EPSG:32638", "+proj=utm +zone=38 +datum=WGS84 +units=m +no_defs");

    const cityNames = Object.keys(cityPayload.cities).sort();

    const citySelect = document.getElementById("citySelect");
    for (const nm of cityNames) {
      const opt = document.createElement("option");
      opt.value = nm;
      opt.textContent = nm;
      citySelect.appendChild(opt);
    }

    const defaultCity = cityNames.includes("Tokyo, Japan") ? "Tokyo, Japan" : (cityNames[0] || "");
    citySelect.value = defaultCity;

    const tSlider = document.getElementById("tSlider");
    const aSlider = document.getElementById("aSlider");
    const yKpiEl = document.getElementById("yKpi");
    const cKpiEl = document.getElementById("cKpi");
    const legendCityName = document.getElementById("legendCityName");

    const svg = document.getElementById("plot");
    const xAxis = document.getElementById("xAxis");
    const yAxis = document.getElementById("yAxis");

    const cityPolyEl = document.getElementById("cityPoly");
    const yerPolyEl = document.getElementById("yerPoly");
    const originDot = document.getElementById("originDot");

    const R = Math.max(500.0, cityPayload.extent_m);

    function svgSize() {
      const r = svg.getBoundingClientRect();
      return { w: Math.max(10, r.width), h: Math.max(10, r.height) };
    }

    function worldToSvg(x, y, w, h) {
      const s = Math.min(w, h) / (2.0 * R);
      const cx = w * 0.5;
      const cy = h * 0.5;
      return { x: cx + x * s, y: cy - y * s, s };
    }

    function ringToPathMeters(ring, w, h) {
      if (!ring || ring.length < 3) return "";
      let d = "";
      for (let i = 0; i < ring.length; i++) {
        const p = ring[i];
        const xy = worldToSvg(p[0], p[1], w, h);
        d += (i === 0 ? "M " : " L ") + xy.x.toFixed(2) + " " + xy.y.toFixed(2);
      }
      d += " Z";
      return d;
    }

    function geomMetersToPath(geom, w, h) {
      if (!geom) return "";
      let d = "";
      if (geom.type === "Polygon") {
        for (const ring of geom.coordinates) d += " " + ringToPathMeters(ring, w, h);
        return d.trim();
      }
      if (geom.type === "MultiPolygon") {
        for (const poly of geom.coordinates) {
          for (const ring of poly) d += " " + ringToPathMeters(ring, w, h);
        }
        return d.trim();
      }
      return "";
    }

    function updateAxes(w, h) {
      const o = worldToSvg(0, 0, w, h);
      xAxis.setAttribute("x1", 0);
      xAxis.setAttribute("y1", o.y);
      xAxis.setAttribute("x2", w);
      xAxis.setAttribute("y2", o.y);

      yAxis.setAttribute("x1", o.x);
      yAxis.setAttribute("y1", 0);
      yAxis.setAttribute("x2", o.x);
      yAxis.setAttribute("y2", h);

      originDot.setAttribute("cx", o.x);
      originDot.setAttribute("cy", o.y);
    }

    // Yerevan precomputed
    const tg = yerevanData.t_grid;
    const ag = yerevanData.a_grid;
    const g = yerevanData.g;
    const precomp = yerevanData.precomp;

    // compute gX,gY in EPSG:32638 in browser
    const gXY = proj4("EPSG:4326", "EPSG:32638", [g.lon, g.lat]);
    const gX = gXY[0];
    const gY = gXY[1];

    tSlider.min = tg.min; tSlider.max = tg.max; tSlider.step = 0.01;
    aSlider.min = ag.min; aSlider.max = ag.max; aSlider.step = 0.01;

    function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

    function snap(val, grid) {
      const v = clamp(val, grid.min, grid.max);
      const k = Math.round((v - grid.min) / grid.step);
      const snapped = grid.min + k * grid.step;
      return Number(snapped.toFixed(2));
    }

    function keyFor(t, a) {
      return `${t.toFixed(2)}_${a.toFixed(2)}`;
    }

    function lonLatToYerevanRelMeters(lon, lat) {
      const xy = proj4("EPSG:4326", "EPSG:32638", [lon, lat]);
      return [xy[0] - gX, xy[1] - gY];
    }

    function llGeomToRelMetersGeom(geom) {
      if (!geom) return null;

      if (geom.type === "Polygon") {
        const rings = geom.coordinates.map(ring =>
          ring.map(p => lonLatToYerevanRelMeters(p[0], p[1]))
        );
        return { type: "Polygon", coordinates: rings };
      }

      if (geom.type === "MultiPolygon") {
        const polys = geom.coordinates.map(poly =>
          poly.map(ring => ring.map(p => lonLatToYerevanRelMeters(p[0], p[1])))
        );
        return { type: "MultiPolygon", coordinates: polys };
      }

      return null;
    }

    let pending = null;
    function scheduleUpdate() {
      if (pending) clearTimeout(pending);
      pending = setTimeout(update, 80);
    }

    citySelect.addEventListener("change", scheduleUpdate);
    tSlider.addEventListener("input", scheduleUpdate);
    aSlider.addEventListener("input", scheduleUpdate);
    window.addEventListener("resize", scheduleUpdate);

    function update() {
      const cityName = citySelect.value;
      legendCityName.textContent = cityName;

      const { w, h } = svgSize();
      updateAxes(w, h);

      const cityObj = cityPayload.cities[cityName];
      const cityGeom = cityObj ? cityObj.geom_m : null;
      cityPolyEl.setAttribute("d", geomMetersToPath(cityGeom, w, h));

      const tRaw = parseFloat(tSlider.value);
      const aRaw = parseFloat(aSlider.value);

      const tS = snap(tRaw, tg);
      const aS = snap(aRaw, ag);

      const entry = precomp[keyFor(tS, aS)];

      let yerGeomRel = null;
      if (entry && entry.poly_geom) {
        yerGeomRel = llGeomToRelMetersGeom(entry.poly_geom);
      }

      yerPolyEl.setAttribute("d", geomMetersToPath(yerGeomRel, w, h));

      if (entry) {
        yKpiEl.innerHTML =
          entry.area_km2.toFixed(2) +
          ' km<sup>2</sup> | distance from commercial center to historical center: ' +
          entry.sep_m.toFixed(0) +
          ' m';
      } else {
        yKpiEl.textContent = "no data";
      }

      if (cityObj) {
        cKpiEl.innerHTML = cityObj.area_km2.toFixed(2) + ' km<sup>2</sup>';
      } else {
        cKpiEl.textContent = "...";
      }
    }

    update();
  </script>
</body>
</html>
"""


def main():
    if not os.path.exists(CITY_CSV):
        raise SystemExit(f"Missing: {CITY_CSV}")
    if not os.path.exists(YEREVAN_PRECOMP_HTML):
        raise SystemExit(f"Missing: {YEREVAN_PRECOMP_HTML}")

    city_payload = load_city_polygons_payload(CITY_CSV, POLY_DIR)
    city_payload_js = json.dumps(city_payload, ensure_ascii=False)

    with open(YEREVAN_PRECOMP_HTML, "r", encoding="utf-8") as f:
        ytxt = f.read()
    y_b64 = extract_payload_b64_from_yerevan_html(ytxt)

    html = HTML_TEMPLATE.replace("__CITY_PAYLOAD__", city_payload_js)
    html = html.replace("__YEREVAN_PAYLOAD_GZ_B64__", y_b64)

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("Saved:", OUT_HTML)


if __name__ == "__main__":
    main()