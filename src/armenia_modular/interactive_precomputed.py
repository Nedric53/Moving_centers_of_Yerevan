from .config import G_LAT, G_LON, INTERACTIVE_DIR, SPEED_M_PER_MIN


def write_yerevan_precomputed_html(
    master,
    logit_model,
    features,
    means,
    stds,
    mu0x,
    mu0y,
    out_dir=INTERACTIVE_DIR,
    g_lon: float = G_LON,
    g_lat: float = G_LAT,
    speed_m_per_min: float = SPEED_M_PER_MIN,
):
    """
    Direct modular wrapper around notebook cell 16.
    Returns the written HTML path.
    """
    # yerevan_business_polygon_precompute.py
    #
    # Output:
    #   data/yerevan_interactive/yerevan_business_polygon_precomputed.html
    #
    # Assumes you already have:
    # - master GeoDataFrame with columns: cx, cy, dist_to_g_m, herit_density_500m, pop_density_per_km2, log_rent, rent_missing
    # - logit_model (statsmodels), features list, means, stds, mu0x, mu0y
    # - G_LON, G_LAT, SPEED_M_PER_MIN
    #
    # Notes:
    # - sliders snap to precomputed grid (T_STEP, A_STEP).
    # - no grid, no tiles. Only polygon + μ and g markers.
    #
    # Key change vs your version:
    # - payload is JSON-minified, gzip-compressed, base64-embedded
    # - HTML inflates it in-browser with pako (gzip)
    # This keeps polygon count and geometry unchanged, but shrinks HTML a lot.

    import os
    import json
    import gzip
    import base64
    import numpy as np
    import geopandas as gpd
    from shapely.geometry import Point, LineString, mapping
    from shapely.ops import unary_union, transform
    from shapely.prepared import prep
    from pyproj import Transformer
    from tqdm import tqdm

    OUT_DIR = str(out_dir)
    os.makedirs(OUT_DIR, exist_ok=True)

    # -----------------------------
    # Input arrays
    # -----------------------------
    cx = master["cx"].to_numpy().astype(float)  # UTM meters
    cy = master["cy"].to_numpy().astype(float)

    dist_g = master["dist_to_g_m"].to_numpy().astype(float)
    herit = master["herit_density_500m"].fillna(0).to_numpy().astype(float)
    pop = master["pop_density_per_km2"].fillna(0).to_numpy().astype(float)
    log_rent = master["log_rent"].fillna(master["log_rent"].median()).to_numpy().astype(float)
    rent_missing = master["rent_missing"].fillna(1).to_numpy().astype(float)

    params = logit_model.params.to_dict()
    coef = {
        "const": float(params.get("const", 0.0)),
        "tau_min": float(params.get("tau_min", 0.0)),
        "dist_to_g_m": float(params.get("dist_to_g_m", 0.0)),
        "herit_density_500m": float(params.get("herit_density_500m", 0.0)),
        "pop_density_per_km2": float(params.get("pop_density_per_km2", 0.0)),
        "log_rent": float(params.get("log_rent", 0.0)),
        "rent_missing": float(params.get("rent_missing", 0.0)),
    }
    mean = {k: float(means[k]) for k in features}
    std = {k: float(stds[k]) for k in features}

    speed_m_per_min = float(speed_m_per_min)

    # g in lon/lat and UTM
    g_lon, g_lat = float(g_lon), float(g_lat)
    g_utm = gpd.GeoSeries([Point(g_lon, g_lat)], crs="EPSG:4326").to_crs("EPSG:32638").iloc[0]
    g_utm_x, g_utm_y = float(g_utm.x), float(g_utm.y)

    mu0x = float(mu0x)
    mu0y = float(mu0y)

    # -----------------------------
    # Business polygon settings
    # -----------------------------
    BUS_TARGET_MASS = 0.55
    BUS_MAX_POINTS = 1300
    BUS_MIN_POINTS = 80

    BUS_BUFFER_KM = 0.35
    BUS_CLOSE_KM = 0.25
    BUS_CORRIDOR_KM = 0.20
    BUS_MIN_COMP_MASS = 0.10

    BUS_SIMPLIFY_TOL_DEG = 0.00025  # simplify after projecting to EPSG:4326

    # -----------------------------
    # Precompute grid (snap-to)
    # -----------------------------
    T_MIN, T_MAX, T_STEP = 0.10, 2.00, 0.05
    A_MIN, A_MAX, A_STEP = 0.10, 2.00, 0.05

    t_vals = np.round(np.arange(T_MIN, T_MAX + 1e-9, T_STEP), 2)
    a_vals = np.round(np.arange(A_MIN, A_MAX + 1e-9, A_STEP), 2)

    # -----------------------------
    # Helpers
    # -----------------------------
    def sigmoid(x: np.ndarray) -> np.ndarray:
        x = np.clip(x, -35, 35)
        return 1.0 / (1.0 + np.exp(-x))

    def z(x: np.ndarray, m: float, s: float) -> np.ndarray:
        if not np.isfinite(s) or s == 0:
            return np.zeros_like(x, dtype=float)
        out = (x - m) / s
        out[~np.isfinite(out)] = 0.0
        return out

    def solve_mu_and_shares(t_factor: float, a_factor: float, iters: int = 20, tol_m: float = 30.0):
        mux, muy = mu0x, mu0y
        shares = np.zeros_like(cx, dtype=float)

        for _ in range(iters):
            dx = cx - mux
            dy = cy - muy
            d = np.sqrt(dx * dx + dy * dy)
            tau = t_factor * (d / speed_m_per_min)

            z_tau = z(tau, mean["tau_min"], std["tau_min"])
            z_dg = z(dist_g, mean["dist_to_g_m"], std["dist_to_g_m"]) * a_factor
            z_herit = z(herit, mean["herit_density_500m"], std["herit_density_500m"]) * a_factor
            z_pop = z(pop, mean["pop_density_per_km2"], std["pop_density_per_km2"])
            z_lr = z(log_rent, mean["log_rent"], std["log_rent"])
            z_rm = z(rent_missing, mean["rent_missing"], std["rent_missing"])

            lin = (
                coef["const"]
                + coef["tau_min"] * z_tau
                + coef["dist_to_g_m"] * z_dg
                + coef["herit_density_500m"] * z_herit
                + coef["pop_density_per_km2"] * z_pop
                + coef["log_rent"] * z_lr
                + coef["rent_missing"] * z_rm
            )
            shares = sigmoid(lin)

            sumw = shares.sum()
            if sumw <= 0:
                break

            mux_new = float((shares * cx).sum() / sumw)
            muy_new = float((shares * cy).sum() / sumw)
            shift = float(np.hypot(mux_new - mux, muy_new - muy))

            mux, muy = mux_new, muy_new
            if shift < tol_m:
                break

        return mux, muy, shares

    def _explode_polys(geom):
        if geom is None or geom.is_empty:
            return []
        gt = geom.geom_type
        if gt == "Polygon":
            return [geom]
        if gt == "MultiPolygon":
            return list(geom.geoms)
        if gt == "GeometryCollection":
            out = []
            for g in geom.geoms:
                out.extend(_explode_polys(g))
            return out
        return []

    # Project UTM (EPSG:32638) -> lonlat (EPSG:4326)
    to_ll = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True).transform

    def business_polygon_from_shares_one(shares: np.ndarray):
        n = shares.size
        s_clean = np.where(np.isfinite(shares) & (shares > 0), shares, 0.0)
        total_mass = float(s_clean.sum())
        if total_mass <= 0:
            return None, 0.0, 0

        idx = np.argsort(-s_clean)  # desc
        target_mass = BUS_TARGET_MASS * total_mass

        selected = []
        cum = 0.0
        max_points = min(BUS_MAX_POINTS, n)

        for i in idx[:max_points]:
            si = float(s_clean[i])
            if si <= 0:
                continue
            selected.append(int(i))
            cum += si
            if len(selected) >= BUS_MIN_POINTS and cum >= target_mass:
                break

        if len(selected) < 10:
            return None, 0.0, len(selected)

        # Buffers in UTM meters
        r_m = BUS_BUFFER_KM * 1000.0
        close_m = BUS_CLOSE_KM * 1000.0
        corridor_m = BUS_CORRIDOR_KM * 1000.0

        pts = [Point(float(cx[i]), float(cy[i])) for i in selected]
        buffered = [p.buffer(r_m, resolution=16) for p in pts]
        merged = unary_union(buffered)
        if merged is None or merged.is_empty:
            return None, 0.0, len(selected)

        # Closing to merge near blobs
        try:
            merged = merged.buffer(close_m, resolution=16).buffer(-close_m, resolution=16)
        except Exception:
            pass

        parts = _explode_polys(merged)

        if len(parts) > 1:
            comp_mass = [0.0] * len(parts)
            prepped = [prep(p) for p in parts]
            for i in selected:
                p = Point(float(cx[i]), float(cy[i]))
                si = float(s_clean[i])
                for ci, pr in enumerate(prepped):
                    if pr.contains(p) or pr.covers(p):
                        comp_mass[ci] += si
                        break

            min_comp = BUS_MIN_COMP_MASS * float(cum)
            kept = [(parts[i], comp_mass[i]) for i in range(len(parts)) if comp_mass[i] >= min_comp]
            if not kept:
                kept = [(parts[0], comp_mass[0])]

            peak_i = int(selected[0])
            peak_pt = Point(float(cx[peak_i]), float(cy[peak_i]))

            anchor_geom = None
            for pg, _m in kept:
                pr = prep(pg)
                if pr.contains(peak_pt) or pr.covers(peak_pt):
                    anchor_geom = pg
                    break
            if anchor_geom is None:
                kept.sort(key=lambda x: x[1], reverse=True)
                anchor_geom = kept[0][0]

            out = anchor_geom
            out_cent = out.centroid

            for pg, _m in kept:
                if pg.equals(anchor_geom):
                    continue
                line = LineString([out_cent.coords[0], pg.centroid.coords[0]])
                corridor = line.buffer(corridor_m, resolution=8)
                out = unary_union([out, corridor, pg])
                out_cent = out.centroid

            try:
                out = out.buffer(close_m, resolution=16).buffer(-close_m, resolution=16)
            except Exception:
                pass

            merged = out

        # Fix invalids
        try:
            merged = merged.buffer(0)
        except Exception:
            pass

        # Area in km2 (UTM meters)
        area_km2 = float(merged.area) / 1e6 if merged and not merged.is_empty else 0.0

        # Project to lon/lat and simplify in degrees
        merged_ll = transform(to_ll, merged)
        if BUS_SIMPLIFY_TOL_DEG and BUS_SIMPLIFY_TOL_DEG > 0:
            try:
                merged_ll = merged_ll.simplify(BUS_SIMPLIFY_TOL_DEG, preserve_topology=True)
            except Exception:
                pass

        geom_json = mapping(merged_ll) if merged_ll and not merged_ll.is_empty else None
        return geom_json, area_km2, len(selected)

    def utm_point_to_ll(x: float, y: float):
        lon, lat = to_ll(x, y)
        return float(lon), float(lat)

    # -----------------------------
    # Precompute table
    # -----------------------------
    precomp = {}
    total = len(t_vals) * len(a_vals)

    for t in tqdm(t_vals, total=len(t_vals), desc="t grid"):
        for a in a_vals:
            mux, muy, shares = solve_mu_and_shares(float(t), float(a))
            geom_json, area_km2, used_pts = business_polygon_from_shares_one(shares)

            mu_lon, mu_lat = utm_point_to_ll(mux, muy)
            sep_m = float(np.hypot(mux - g_utm_x, muy - g_utm_y))

            key = f"{t:.2f}_{a:.2f}"
            precomp[key] = {
                # Keep only what the page uses. This does not affect polygon geometry.
                "mu": {"lon": mu_lon, "lat": mu_lat},
                "sep_m": sep_m,
                "area_km2": float(area_km2),
                "poly_geom": geom_json,  # GeoJSON geometry (Polygon or MultiPolygon), holes preserved
            }

    payload = {
        "t_grid": {"min": T_MIN, "max": T_MAX, "step": T_STEP},
        "a_grid": {"min": A_MIN, "max": A_MAX, "step": A_STEP},
        "g": {"lon": g_lon, "lat": g_lat},
        "precomp": precomp,
    }

    # -----------------------------
    # HTML
    # -----------------------------
    html_template = r"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Yerevan business polygon (precomputed)</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
      <style>
        body { margin:0; font-family: Arial, sans-serif; }
        #map { height: 86vh; width: 100%; }
        #controls {
          height: 14vh; padding: 10px 14px; box-sizing: border-box;
          display: grid; grid-template-columns: 1fr; gap: 8px;
          border-top: 1px solid #ddd;
          background: #fff;
        }
        .row { display:flex; gap:12px; align-items:center; }
        .label { width: 340px; }
        .value { font-weight: 600; width: 70px; }
        .info { margin-left: 8px; }
        input[type="range"] { width: 460px; }
        .leaflet-container { background: #fff; }
      </style>
    </head>
    <body>
      <div id="map"></div>
      <div id="controls">
        <div class="row">
          <div class="label">Transport factor (snap grid)</div>
          <div class="value" id="tVal"></div>
          <input id="tSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          <div class="info" id="tSnap"></div>
        </div>

        <div class="row">
          <div class="label">Historic amenity strength (snap grid)</div>
          <div class="value" id="aVal"></div>
          <input id="aSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          <div class="info" id="aSnap"></div>
        </div>

        <div class="row">
          <div class="label">μ, separation, business area</div>
          <div class="info" id="muInfo"></div>
        </div>
      </div>

      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js"></script>

      <script>
        // Payload is gzip-compressed and base64-embedded to keep this HTML small.
        const PAYLOAD_GZ_B64 = "__PAYLOAD_GZ_B64__";

        function loadPayload() {
          const bin = Uint8Array.from(atob(PAYLOAD_GZ_B64), c => c.charCodeAt(0));
          const jsonStr = pako.ungzip(bin, { to: "string" });
          return JSON.parse(jsonStr);
        }

        const data = loadPayload();
        const g = data.g;
        const precomp = data.precomp;
        const tg = data.t_grid;
        const ag = data.a_grid;

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

        // map (no tiles)
        const map = L.map("map", { zoomControl: true, attributionControl: false }).setView([g.lat, g.lon], 12);

        const gMarker = L.circleMarker([g.lat, g.lon], {
          radius: 6, weight: 2, color: "#000", fillColor: "#000", fillOpacity: 1
        }).addTo(map).bindPopup("g (historic center)");

        let muMarker = L.circleMarker([g.lat, g.lon], {
          radius: 7, weight: 2, color: "#000", fillColor: "#fff", fillOpacity: 1
        }).addTo(map).bindPopup("μ (business center)");

        let bizLayer = null;
        let didFit = false;

        function setPolygon(entry) {
          const mu = entry.mu;
          muMarker.setLatLng([mu.lat, mu.lon]);

          if (bizLayer) { map.removeLayer(bizLayer); bizLayer = null; }

          if (entry.poly_geom) {
            const feat = { "type": "Feature", "properties": {}, "geometry": entry.poly_geom };
            bizLayer = L.geoJSON(feat, {
              style: () => ({ color:"#000", weight:2, opacity:0.95, fillColor:"#000", fillOpacity:0.12 })
            }).addTo(map);

            if (!didFit) {
              try { map.fitBounds(bizLayer.getBounds(), { padding: [20, 20] }); } catch (e) {}
              didFit = true;
            }
          }

          document.getElementById("muInfo").textContent =
            `μ: (${mu.lon.toFixed(5)}, ${mu.lat.toFixed(5)}) | |μ-g|: ${entry.sep_m.toFixed(0)} m | area: ${entry.area_km2.toFixed(2)} km²`;
        }

        function update() {
          const tRaw = parseFloat(document.getElementById("tSlider").value);
          const aRaw = parseFloat(document.getElementById("aSlider").value);

          document.getElementById("tVal").textContent = tRaw.toFixed(2);
          document.getElementById("aVal").textContent = aRaw.toFixed(2);

          const tS = snap(tRaw, tg);
          const aS = snap(aRaw, ag);

          document.getElementById("tSnap").textContent = `snap: ${tS.toFixed(2)}`;
          document.getElementById("aSnap").textContent = `snap: ${aS.toFixed(2)}`;

          const key = keyFor(tS, aS);
          const entry = precomp[key];
          if (entry) setPolygon(entry);
        }

        let pending = null;
        function scheduleUpdate() {
          if (pending) clearTimeout(pending);
          pending = setTimeout(update, 30);
        }

        document.getElementById("tSlider").addEventListener("input", scheduleUpdate);
        document.getElementById("aSlider").addEventListener("input", scheduleUpdate);

        update();
      </script>
    </body>
    </html>
    """

    # -----------------------------
    # Build embedded payload (minify JSON, gzip, base64)
    # -----------------------------
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_gz = gzip.compress(payload_json, compresslevel=9)
    payload_b64 = base64.b64encode(payload_gz).decode("ascii")

    html_filled = html_template.replace("__PAYLOAD_GZ_B64__", payload_b64)

    html_path = os.path.join(OUT_DIR, "yerevan_business_polygon_precomputed.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_filled)

    return html_path
