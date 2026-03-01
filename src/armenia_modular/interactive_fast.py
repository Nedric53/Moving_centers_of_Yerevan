from .config import ASSETS_DIR, G_LAT, G_LON, INTERACTIVE_DIR, SPEED_M_PER_MIN


def write_yerevan_single_polygon_html(
    master,
    logit_model,
    features,
    means,
    stds,
    mu0x,
    mu0y,
    out_dir=INTERACTIVE_DIR,
    assets_src=ASSETS_DIR,
    g_lon: float = G_LON,
    g_lat: float = G_LAT,
    speed_m_per_min: float = SPEED_M_PER_MIN,
):
    """
    Direct modular wrapper around notebook cell 15.
    Returns the written HTML path.
    """
    # yerevan_sliders_with_single_business_polygon.py
    #
    # Interactive Leaflet HTML with:
    # - Only "hot" cells are filled (share > 0.1)
    # - Cell borders are drawn only for hot cells (thin, transparent)
    # - Hot fill + borders are moderately transparent (tuned below)
    # - City administrative border is thinner
    # - Historical center uses custom icon (22x22) with correct anchoring (no drifting on zoom)
    # - Business center (μ) is a filled circle
    # - Business polygon border is #f0805a fully opaque
    # - Legend aligned, includes icons
    #
    # Output:
    #   data/yerevan_interactive/yerevan_sliders_single_business_polygon.html
    #
    # Assumes you already have in memory:
    #   master GeoDataFrame with columns:
    #     cell_id, geometry, cx, cy, dist_to_g_m, herit_density_500m,
    #     pop_density_per_km2, log_rent, rent_missing
    #   logit_model (statsmodels), features list, means, stds, mu0x, mu0y
    #   G_LON, G_LAT, SPEED_M_PER_MIN

    import os, json, base64, shutil
    import numpy as np
    import geopandas as gpd
    from shapely.geometry import Point, MultiPoint, LineString
    from shapely.ops import unary_union
    from pyproj import Transformer

    OUT_DIR = str(out_dir)
    os.makedirs(OUT_DIR, exist_ok=True)

    # Copy icons into output so HTML can load them via relative paths
    ASSETS_SRC = str(assets_src)
    ASSETS_DST = os.path.join(OUT_DIR, "assets")
    if os.path.isdir(ASSETS_SRC):
        os.makedirs(ASSETS_DST, exist_ok=True)
        for fn in ["icon_historical.png", "icon_business.png"]:
            src = os.path.join(ASSETS_SRC, fn)
            dst = os.path.join(ASSETS_DST, fn)
            if os.path.isfile(src):
                shutil.copy2(src, dst)

    def _ensure_crs(gdf: gpd.GeoDataFrame, default_epsg: str = "EPSG:32638") -> gpd.GeoDataFrame:
        if gdf.crs is None:
            gdf = gdf.copy()
            gdf.set_crs(default_epsg, inplace=True)
        return gdf

    # -----------------------------
    # GeoJSON grid (lightweight)
    # -----------------------------
    geo = master[["cell_id", "geometry"]].copy().reset_index(drop=True)
    geo["gid"] = np.arange(len(geo)).astype(int)

    geo = _ensure_crs(geo, "EPSG:32638")
    geo_ll = geo[["gid", "geometry"]].to_crs("EPSG:4326")
    geo_ll["geometry"] = geo_ll["geometry"].simplify(0.00005, preserve_topology=True)
    geojson_obj = json.loads(geo_ll.to_json())

    # -----------------------------
    # City boundary (approx) from grid union
    # -----------------------------
    def compute_city_boundary_feature(master_gdf: gpd.GeoDataFrame, simplify_tol_deg: float = 0.00030):
        mg = master_gdf[["geometry"]].copy()
        mg = _ensure_crs(mg, "EPSG:32638").to_crs("EPSG:32638")
        try:
            u = unary_union(list(mg.geometry))
        except Exception:
            u = mg.unary_union

        if u.is_empty:
            return None

        u_ll = gpd.GeoSeries([u], crs="EPSG:32638").to_crs("EPSG:4326").iloc[0]
        if simplify_tol_deg and simplify_tol_deg > 0:
            u_ll = u_ll.simplify(float(simplify_tol_deg), preserve_topology=True)

        return {"type": "Feature", "properties": {}, "geometry": u_ll.__geo_interface__}

    city_boundary_feature = compute_city_boundary_feature(master)

    # -----------------------------
    # Arrays for precompute
    # -----------------------------
    cx = master["cx"].to_numpy().astype(float)
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

    m = {k: float(means[k]) for k in features}
    s = {k: float(stds[k]) for k in features}

    # g point lon/lat and UTM (for separation)
    g_lon, g_lat = float(g_lon), float(g_lat)
    g_utm = gpd.GeoSeries([Point(g_lon, g_lat)], crs="EPSG:4326").to_crs("EPSG:32638").iloc[0]
    g_utm_x, g_utm_y = float(g_utm.x), float(g_utm.y)

    # -----------------------------
    # Business polygon settings
    # -----------------------------
    BUS_TARGET_MASS = 0.55
    BUS_MAX_POINTS = 500
    BUS_MIN_POINTS = 80

    BUS_BUFFER_KM = 0.35
    BUS_CLOSE_KM = 0.25
    BUS_CORRIDOR_KM = 0.20
    BUS_MIN_COMP_MASS = 0.10
    BUS_SIMPLIFY_TOL = 0.00025

    payload = {
        "geojson": geojson_obj,
        "cx": cx.tolist(),
        "cy": cy.tolist(),
        "dist_g": dist_g.tolist(),
        "herit": herit.tolist(),
        "pop": pop.tolist(),
        "log_rent": log_rent.tolist(),
        "rent_missing": rent_missing.tolist(),
        "coef": coef,
        "mean": m,
        "std": s,
        "mu0": {"x": float(mu0x), "y": float(mu0y)},
        "g": {"lon": float(g_lon), "lat": float(g_lat), "x": float(g_utm_x), "y": float(g_utm_y)},
        "speed_m_per_min": float(speed_m_per_min),
        "biz": {
            "target_mass": float(BUS_TARGET_MASS),
            "max_points": int(BUS_MAX_POINTS),
            "min_points": int(BUS_MIN_POINTS),
            "buffer_km": float(BUS_BUFFER_KM),
            "close_km": float(BUS_CLOSE_KM),
            "corridor_km": float(BUS_CORRIDOR_KM),
            "min_component_mass": float(BUS_MIN_COMP_MASS),
            "simplify_tol": float(BUS_SIMPLIFY_TOL),
        },
        "city_boundary": city_boundary_feature,
    }

    TRANSPORT_STOPS = [0.50, 0.75, 1.00, 1.25, 1.50]
    AMENITY_STOPS   = [0.50, 0.75, 1.00, 1.25, 1.50]

    # -----------------------------
    # Vectorized fixed-point solver
    # -----------------------------
    def solve_numpy(
        tFactor: float,
        aFactor: float,
        cx: np.ndarray,
        cy: np.ndarray,
        dist_g: np.ndarray,
        herit: np.ndarray,
        pop: np.ndarray,
        log_rent: np.ndarray,
        rent_missing: np.ndarray,
        coef: dict,
        mean: dict,
        std: dict,
        mu0x: float,
        mu0y: float,
        speed_m_per_min: float,
        max_iter: int = 20,
        shift_tol_m: float = 30.0,
    ):
        def _safe_std(x: float) -> float:
            x = float(x)
            return x if x != 0.0 else 1.0

        mux = float(mu0x)
        muy = float(mu0y)

        eps = 1e-9
        tFactor = float(tFactor)
        aFactor = float(aFactor)

        s_tau = _safe_std(std["tau_min"])
        s_dg  = _safe_std(std["dist_to_g_m"])
        s_h   = _safe_std(std["herit_density_500m"])
        s_p   = _safe_std(std["pop_density_per_km2"])
        s_lr  = _safe_std(std["log_rent"])
        s_rm  = _safe_std(std["rent_missing"])

        z_dg0 = (dist_g - mean["dist_to_g_m"]) / s_dg
        z_h0  = (herit  - mean["herit_density_500m"]) / s_h
        z_p0  = (pop    - mean["pop_density_per_km2"]) / s_p
        z_lr0 = (log_rent - mean["log_rent"]) / s_lr
        z_rm0 = (rent_missing - mean["rent_missing"]) / s_rm

        b0   = float(coef["const"])
        bTau = float(coef["tau_min"])
        bDg  = float(coef["dist_to_g_m"])
        bH   = float(coef["herit_density_500m"])
        bP   = float(coef["pop_density_per_km2"])
        bLR  = float(coef["log_rent"])
        bRM  = float(coef["rent_missing"])

        lin = np.empty_like(cx, dtype=float)

        for _ in range(int(max_iter)):
            dx = cx - mux
            dy = cy - muy
            d = np.hypot(dx, dy)

            tau = (d / float(speed_m_per_min)) / max(tFactor, eps)
            z_tau = (tau - mean["tau_min"]) / s_tau

            lin[:] = (
                b0
                + bTau * z_tau
                + bDg  * (z_dg0 * aFactor)
                + bH   * (z_h0  * aFactor)
                + bP   * z_p0
                + bLR  * z_lr0
                + bRM  * z_rm0
            )

            np.clip(lin, -35.0, 35.0, out=lin)
            shares = 1.0 / (1.0 + np.exp(-lin))

            sumw = float(shares.sum())
            if sumw <= 0 or not np.isfinite(sumw):
                return mux, muy, np.zeros_like(cx, dtype=float)

            mux_new = float((shares * cx).sum() / sumw)
            muy_new = float((shares * cy).sum() / sumw)

            shift = float(np.hypot(mux_new - mux, muy_new - muy))
            mux, muy = mux_new, muy_new

            if shift < float(shift_tol_m):
                break

        return mux, muy, shares

    # -----------------------------
    # Business polygon from shares
    # -----------------------------
    def business_polygon_from_shares_python(
        shares: np.ndarray,
        cx: np.ndarray,
        cy: np.ndarray,
        biz_cfg: dict,
    ):
        s_arr = np.where(np.isfinite(shares), shares, 0.0)
        total_mass = float(s_arr.sum())
        if total_mass <= 0:
            return None, 0.0, 0

        idx = np.argsort(-s_arr)

        target_mass = float(biz_cfg["target_mass"]) * total_mass
        max_points = min(int(biz_cfg["max_points"]), int(len(s_arr)))
        min_points = int(biz_cfg["min_points"])

        selected = []
        cum = 0.0
        for k in range(len(s_arr)):
            if len(selected) >= max_points:
                break
            i = int(idx[k])
            if s_arr[i] <= 0:
                continue
            selected.append(i)
            cum += float(s_arr[i])
            if len(selected) >= min_points and cum >= target_mass:
                break

        used_points = len(selected)
        if used_points < 10:
            return None, 0.0, used_points

        r_m = float(biz_cfg["buffer_km"]) * 1000.0
        close_m = float(biz_cfg["close_km"]) * 1000.0
        corridor_m = float(biz_cfg["corridor_km"]) * 1000.0

        pts = [Point(float(cx[i]), float(cy[i])) for i in selected]
        peak_i = selected[0]
        peak_pt = Point(float(cx[peak_i]), float(cy[peak_i]))

        merged = MultiPoint(pts).buffer(r_m)

        if close_m > 0:
            merged = merged.buffer(close_m).buffer(-close_m)

        if merged.is_empty:
            return None, 0.0, used_points

        if merged.geom_type == "Polygon":
            parts = [merged]
        elif merged.geom_type == "MultiPolygon":
            parts = list(merged.geoms)
        else:
            return None, 0.0, used_points

        if len(parts) > 1:
            comp_mass = []
            for p in parts:
                m0 = 0.0
                for i in selected:
                    if p.contains(Point(float(cx[i]), float(cy[i]))):
                        m0 += float(s_arr[i])
                comp_mass.append(m0)

            selected_mass = float(sum(comp_mass))
            min_comp = float(biz_cfg["min_component_mass"]) * selected_mass

            kept = [(parts[i], comp_mass[i]) for i in range(len(parts)) if comp_mass[i] >= min_comp]
            if not kept:
                kept = [(parts[0], comp_mass[0])]

            anchor_poly = None
            for p, _m in kept:
                if p.contains(peak_pt):
                    anchor_poly = p
                    break
            if anchor_poly is None:
                kept.sort(key=lambda x: x[1], reverse=True)
                anchor_poly = kept[0][0]

            out = anchor_poly
            for p, _m in kept:
                if p.equals(anchor_poly):
                    continue
                ca = out.centroid
                cb = p.centroid
                corridor = LineString([ca, cb]).buffer(corridor_m)
                out = unary_union([out, corridor, p])

            if close_m > 0:
                out = out.buffer(close_m).buffer(-close_m)

            merged = out

        area_km2 = float(merged.area) / 1e6
        geom_ll = gpd.GeoSeries([merged], crs="EPSG:32638").to_crs("EPSG:4326").iloc[0]

        simp = float(biz_cfg.get("simplify_tol", 0.0))
        if simp > 0:
            geom_ll = geom_ll.simplify(simp, preserve_topology=True)

        return geom_ll, area_km2, used_points

    # -----------------------------
    # Shares packing to base64 u8
    # -----------------------------
    def _shares_to_u8_b64(shares: np.ndarray) -> str:
        x = np.asarray(shares, dtype=float)
        x = np.where(np.isfinite(x), x, 0.0)
        x = np.clip(x, 0.0, 1.0)
        u8 = np.rint(x * 255.0).astype(np.uint8)
        return base64.b64encode(u8.tobytes()).decode("ascii")

    def precompute_biz(payload: dict) -> dict:
        cx_np = np.asarray(payload["cx"], dtype=float)
        cy_np = np.asarray(payload["cy"], dtype=float)
        dist_g_np = np.asarray(payload["dist_g"], dtype=float)
        herit_np = np.asarray(payload["herit"], dtype=float)
        pop_np = np.asarray(payload["pop"], dtype=float)
        log_rent_np = np.asarray(payload["log_rent"], dtype=float)
        rent_missing_np = np.asarray(payload["rent_missing"], dtype=float)

        coef0 = payload["coef"]
        mean0 = payload["mean"]
        std0 = payload["std"]

        mu0x0 = float(payload["mu0"]["x"])
        mu0y0 = float(payload["mu0"]["y"])
        speed0 = float(payload["speed_m_per_min"])
        biz_cfg0 = payload["biz"]

        gx = float(payload["g"]["x"])
        gy = float(payload["g"]["y"])

        to_ll = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True)

        out = {}
        for t in TRANSPORT_STOPS:
            for a in AMENITY_STOPS:
                mux, muy, shares = solve_numpy(
                    tFactor=float(t),
                    aFactor=float(a),
                    cx=cx_np,
                    cy=cy_np,
                    dist_g=dist_g_np,
                    herit=herit_np,
                    pop=pop_np,
                    log_rent=log_rent_np,
                    rent_missing=rent_missing_np,
                    coef=coef0,
                    mean=mean0,
                    std=std0,
                    mu0x=mu0x0,
                    mu0y=mu0y0,
                    speed_m_per_min=speed0,
                )

                sep_m = float(np.hypot(mux - gx, muy - gy))
                lon, lat = to_ll.transform(float(mux), float(muy))

                geom_ll, area_km2, used_pts = business_polygon_from_shares_python(
                    shares=shares, cx=cx_np, cy=cy_np, biz_cfg=biz_cfg0
                )

                key = f"{t:.2f}|{a:.2f}"
                rec = {
                    "mu": {"x": float(mux), "y": float(muy), "lon": float(lon), "lat": float(lat)},
                    "sep_m": float(sep_m),
                    "shares_u8_b64": _shares_to_u8_b64(shares),
                    "shares_scale": 255,
                    "area_km2": 0.0,
                    "used_points": int(used_pts),
                    "feature": None,
                }
                if geom_ll is not None:
                    rec["feature"] = {"type": "Feature", "properties": {}, "geometry": geom_ll.__geo_interface__}
                    rec["area_km2"] = float(area_km2) if np.isfinite(area_km2) else 0.0

                out[key] = rec

        return out

    def payload_for_browser(payload: dict) -> dict:
        return {
            "geojson": payload["geojson"],
            "g": payload["g"],  # historical center
            "mu0": payload["mu0"],
            "cell_size_m": payload.get("cell_size_m", None),
            "precomputed_biz": payload["precomputed_biz"],
            "city_boundary": payload.get("city_boundary", None),
            "assets": {
                "historical_icon": "assets/icon_historical.png",
                "business_area_icon": "assets/icon_business.png",
            },
        }

    # -----------------------------
    # HTML builder
    # -----------------------------
    def build_fast_yerevan_html(payload_browser: dict) -> str:
        payload_json = json.dumps(payload_browser, ensure_ascii=False, separators=(",", ":"))

        return f"""<!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Yerevan sliders with single business polygon (fast)</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
      <style>
        body {{ margin:0; font-family: Arial, sans-serif; }}
        #map {{ height: 86vh; width: 100%; }}
        #controls {{
          height: 14vh; padding: 10px 14px; box-sizing: border-box;
          display: grid; grid-template-columns: 1fr; gap: 8px;
          border-top: 1px solid #ddd;
        }}
        .row {{ display:flex; gap:12px; align-items:center; }}
        .label {{ width: 340px; }}
        .value {{ font-weight: 600; width: 70px; }}
        .info {{ margin-left: 8px; }}
        input[type="range"] {{ width: 460px; }}

        .legend {{
          background: rgba(255,255,255,0.94);
          padding: 10px 12px;
          border-radius: 12px;
          box-shadow: 0 10px 26px rgba(0,0,0,0.10);
          color: #111;
          font-size: 12px;
          font-family: Inter, Arial, sans-serif;
          max-width: 560px;
        }}
        .legendGrid {{
          display: grid;
          grid-template-columns: auto auto auto;
          grid-template-rows: auto auto;
          column-gap: 18px;
          row-gap: 10px;
          align-items: center;
        }}
        .lItem {{
          display: flex;
          align-items: center;
          gap: 8px;
          line-height: 1.2;
          white-space: nowrap;
        }}
        .swatchHot {{
          width: 12px;
          height: 12px;
          border-radius: 0;
          border: 1px solid rgba(0,0,0,0.35);
          background: rgba(240,128,90,0.55);
          flex: 0 0 auto;
        }}
        .swatchGrid {{
          width: 12px;
          height: 12px;
          border-radius: 0;
          border: 1px solid rgba(0,0,0,0.35);
          background: rgba(255,255,255,0.90);
          flex: 0 0 auto;
        }}
        .dotMu {{
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: 2px solid #111;
          background: #f0805a;
          flex: 0 0 auto;
        }}
        .lIcon {{
          width: 22px;
          height: 22px;
          object-fit: contain;
          display: block;
          flex: 0 0 auto;
        }}
      </style>
    </head>
    <body>
      <div id="map"></div>
      <div id="controls">
        <div class="row">
          <div class="label">Transport factor (0.1..2.0)</div>
          <div class="value" id="tVal"></div>
          <input id="tSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          <div class="info">Higher = faster</div>
        </div>

        <div class="row">
          <div class="label">Historic amenity strength (0.1..2.0)</div>
          <div class="value" id="aVal"></div>
          <input id="aSlider" type="range" min="0.10" max="2.00" step="0.01" value="1.00">
          <div class="info">Higher = stronger</div>
        </div>

        <div class="row">
          <div class="label">μ, separation, business area</div>
          <div class="info" id="muInfo"></div>
        </div>
      </div>

      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

      <script>
        const data = {payload_json};

        const COLOR_HOT = "#f0805a";
        const COLOR_LINE = "#4f4f4f";
        const COLOR_CITY = "#3f3f3f";

        // Threshold: share > 0.1
        const THRESH_SHARE = 0.5;
        const THRESH_B = Math.ceil(THRESH_SHARE * 255.0);

        // Thin borders for hot cells only
        const HOT_LINE_WEIGHT = 0.25;

        function b64ToU8(b64) {{
          const bin = atob(b64);
          const len = bin.length;
          const out = new Uint8Array(len);
          for (let i = 0; i < len; i++) out[i] = bin.charCodeAt(i);
          return out;
        }}

        const _sharesCache = new Map();
        function getSharesU8(key) {{
          const hit = _sharesCache.get(key);
          if (hit) {{
            hit.t = performance.now();
            return hit.u8;
          }}
          const rec = data.precomputed_biz && data.precomputed_biz[key];
          if (!rec || !rec.shares_u8_b64) return null;

          const u8 = b64ToU8(rec.shares_u8_b64);
          _sharesCache.set(key, {{ u8, t: performance.now() }});

          if (_sharesCache.size > 4) {{
            let oldestK = null;
            let oldestT = Infinity;
            for (const [k, v] of _sharesCache.entries()) {{
              if (v.t < oldestT) {{ oldestT = v.t; oldestK = k; }}
            }}
            if (oldestK !== null) _sharesCache.delete(oldestK);
          }}
          return u8;
        }}

        // Opacity LUTs for hot cells
        const FILL_OPACITY_LUT = new Array(256);
        const STROKE_OPACITY_LUT = new Array(256);
        for (let b = 0; b < 256; b++) {{
          if (b <= THRESH_B) {{
            FILL_OPACITY_LUT[b] = 0.0;
            STROKE_OPACITY_LUT[b] = 0.0;
          }} else {{
            const s = b / 255.0;
            const t = Math.min(1.0, Math.max(0.0, (s - THRESH_SHARE) / (1.0 - THRESH_SHARE)));

            const fillOp = 0.10 + 0.34 * Math.pow(t, 0.85);
            const strokeOp = 0.18 + 0.40 * Math.pow(t, 0.60);

            FILL_OPACITY_LUT[b] = Math.min(0.48, Math.max(0.0, fillOp));
            STROKE_OPACITY_LUT[b] = Math.min(0.62, Math.max(0.0, strokeOp));
          }}
        }}

        const g = data.g;

        const map = L.map("map", {{ preferCanvas: true }}).setView([g.lat, g.lon], 11);

        L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
          maxZoom: 19,
          subdomains: "abcd",
          attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
        }}).addTo(map);

        setTimeout(() => map.invalidateSize(), 0);

        const histIconUrl = (data.assets && data.assets.historical_icon)
          ? data.assets.historical_icon
          : "assets/icon_historical.png";

        const HIST_W = 22;
        const HIST_H = 22;

        const histIcon = L.icon({{
          iconUrl: histIconUrl,
          iconSize: [HIST_W, HIST_H],
          iconAnchor: [HIST_W / 2, HIST_H / 2],
          popupAnchor: [0, -HIST_H / 2]
        }});

        L.marker([g.lat, g.lon], {{ icon: histIcon }})
          .addTo(map)
          .bindPopup("Historical center");

        // Business center (μ)
        let muMarker = L.circleMarker([g.lat, g.lon], {{
          radius: 7,
          weight: 2,
          color: "#111",
          fillColor: COLOR_HOT,
          fillOpacity: 1.0
        }}).addTo(map).bindPopup("Business center (μ)");

        const baseStyle = () => {{
          return {{
            fillColor: COLOR_HOT,
            fillOpacity: 0.0,
            color: COLOR_LINE,
            opacity: 0.0,
            weight: 0.0
          }};
        }};

        const gridLayer = L.geoJSON(data.geojson, {{
          style: baseStyle,
          interactive: false,
          renderer: L.canvas({{ padding: 0.5 }})
        }}).addTo(map);

        const nCells = (data.geojson && data.geojson.features) ? data.geojson.features.length : 0;
        const layersByGid = new Array(nCells);
        gridLayer.eachLayer((layer) => {{
          const gid = layer && layer.feature && layer.feature.properties ? layer.feature.properties.gid : null;
          if (Number.isFinite(gid) && gid >= 0 && gid < nCells) layersByGid[gid] = layer;
        }});

        // City boundary overlay
        if (data.city_boundary && data.city_boundary.geometry) {{
          L.geoJSON(data.city_boundary, {{
            interactive: false,
            style: () => ({{
              color: COLOR_CITY,
              weight: 1.6,
              opacity: 0.70,
              fillOpacity: 0.0
            }})
          }}).addTo(map);
        }}

        // Horizontal 2 x 3 legend
        const legend = L.control({{ position: "topleft" }});
        legend.onAdd = function() {{
          const div = L.DomUtil.create("div", "legend");

          const cellSize = data.cell_size_m;
          const cellTxt = (cellSize && isFinite(cellSize))
            ? `Grid cell: about ${{Math.round(cellSize)}} m on a side.`
            : "Grid cell: one model cell.";

          const histIconUrl2 = (data.assets && data.assets.historical_icon)
            ? data.assets.historical_icon
            : "assets/icon_historical.png";

          const bizAreaIconUrl = (data.assets && data.assets.business_area_icon)
            ? data.assets.business_area_icon
            : "assets/icon_business.png";

          const adminIconUrl = (data.assets && data.assets.administrative_icon)
            ? data.assets.administrative_icon
            : "assets/icon_administrative.png";

          div.innerHTML = `
            <div class="legendGrid">
              <div class="lItem" style="grid-column:1;grid-row:1;">
                <span class="swatchHot"></span>
                <span>Hot cells (share &gt; 0.1)</span>
              </div>

              <div class="lItem" style="grid-column:1;grid-row:2;">
                <span class="swatchGrid"></span>
                <span>${{cellTxt}}</span>
              </div>

              <div class="lItem" style="grid-column:2;grid-row:1;">
                <img class="lIcon" src="${{histIconUrl2}}" alt="">
                <span>Historical center</span>
              </div>

              <div class="lItem" style="grid-column:2;grid-row:2;">
                <span class="dotMu"></span>
                <span>Business center (μ)</span>
              </div>

              <div class="lItem" style="grid-column:3;grid-row:1;">
                <img class="lIcon" src="${{bizAreaIconUrl}}" alt="">
                <span>Business area (polygon)</span>
              </div>

              <div class="lItem" style="grid-column:3;grid-row:2;">
                <img class="lIcon" src="${{adminIconUrl}}" alt="">
                <span>Administrative borders</span>
              </div>
            </div>
          `;

          L.DomEvent.disableClickPropagation(div);
          L.DomEvent.disableScrollPropagation(div);
          return div;
        }};
        legend.addTo(map);

        // Business polygon
        const bizLayer = L.geoJSON(null, {{
          interactive: false,
          style: () => ({{
            color: COLOR_HOT,
            weight: 2.5,
            opacity: 1.0,
            fillColor: COLOR_HOT,
            fillOpacity: 0.10
          }})
        }}).addTo(map);

        function keyTA(tVal, aVal) {{
          return `${{tVal.toFixed(2)}}|${{aVal.toFixed(2)}}`;
        }}

        let _paintToken = 0;
        function repaintGrid(u8) {{
          const token = ++_paintToken;
          let i = 0;
          const n = layersByGid.length;

          function pump() {{
            if (token !== _paintToken) return;

            const tEnd = performance.now() + 10;
            while (i < n && performance.now() < tEnd) {{
              const layer = layersByGid[i];
              if (layer) {{
                const b = u8[i] || 0;
                if (b <= THRESH_B) {{
                  layer.setStyle({{
                    fillOpacity: 0.0,
                    opacity: 0.0,
                    weight: 0.0
                  }});
                }} else {{
                  layer.setStyle({{
                    fillColor: COLOR_HOT,
                    fillOpacity: FILL_OPACITY_LUT[b],
                    color: COLOR_LINE,
                    opacity: STROKE_OPACITY_LUT[b],
                    weight: HOT_LINE_WEIGHT
                  }});
                }}
              }}
              i++;
            }}
            if (i < n) requestAnimationFrame(pump);
          }}

          requestAnimationFrame(pump);
        }}

        let _lastKey = null;

        function applyState(key) {{
          const rec = data.precomputed_biz && data.precomputed_biz[key];
          if (!rec) return;

          const mu = rec.mu;
          if (mu && isFinite(mu.lat) && isFinite(mu.lon)) {{
            muMarker.setLatLng([mu.lat, mu.lon]);
          }}

          bizLayer.clearLayers();
          if (rec.feature) bizLayer.addData(rec.feature);

          const u8 = getSharesU8(key);
          if (u8) repaintGrid(u8);

          const areaKm2 = (rec.area_km2 && isFinite(rec.area_km2)) ? rec.area_km2 : 0.0;
          const sep = (rec.sep_m && isFinite(rec.sep_m)) ? rec.sep_m : 0.0;

          const muInfoEl = document.getElementById("muInfo");
          if (muInfoEl) {{
            muInfoEl.textContent =
              `μ: (${{(mu && mu.lon) ? mu.lon.toFixed(5) : "?"}}, ${{(mu && mu.lat) ? mu.lat.toFixed(5) : "?"}}) | |μ-g|: ${{sep.toFixed(0)}} m | business area: ${{areaKm2.toFixed(2)}} km²`;
          }}
        }}

        let _raf = 0;
        function update() {{
          const tVal = parseFloat(document.getElementById("tSlider").value);
          const aVal = parseFloat(document.getElementById("aSlider").value);

          const tEl = document.getElementById("tVal");
          const aEl = document.getElementById("aVal");
          if (tEl) tEl.textContent = tVal.toFixed(2);
          if (aEl) aEl.textContent = aVal.toFixed(2);

          const key = keyTA(tVal, aVal);
          if (key === _lastKey) return;
          _lastKey = key;

          applyState(key);
        }}

        function scheduleUpdate() {{
          if (_raf) cancelAnimationFrame(_raf);
          _raf = requestAnimationFrame(() => {{
            _raf = 0;
            update();
          }});
        }}

        document.getElementById("tSlider").addEventListener("input", scheduleUpdate);
        document.getElementById("aSlider").addEventListener("input", scheduleUpdate);

        update();
      </script>
    </body>
    </html>
    """

    # -----------------------------
    # Approx cell size for legend
    # -----------------------------
    try:
        master0 = _ensure_crs(master, "EPSG:32638")
        cell0 = master0["geometry"].iloc[0]
        minx, miny, maxx, maxy = cell0.bounds
        payload["cell_size_m"] = float(max(maxx - minx, maxy - miny))
    except Exception:
        payload["cell_size_m"] = None

    # -----------------------------
    # Precompute, build, write
    # -----------------------------
    payload["precomputed_biz"] = precompute_biz(payload)
    payload_js = payload_for_browser(payload)

    html_filled = build_fast_yerevan_html(payload_js)
    html_path = os.path.join(OUT_DIR, "yerevan_sliders_single_business_polygon.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_filled)

    return html_path
