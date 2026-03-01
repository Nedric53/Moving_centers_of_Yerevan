from .common import ensure_crs
from .config import DATA_DIR, G_LAT, G_LON


def export_heritage_points_and_map(yerevan_ll, data_dir=DATA_DIR, g_lon: float = G_LON, g_lat: float = G_LAT):
    """
    Direct modular wrapper around notebook cell 10.
    Returns whatever the original cell returns (an IFrame in notebook contexts).
    """
    DATA_DIR = str(data_dir)
    G_LON = float(g_lon)
    G_LAT = float(g_lat)
    import os, json
    import pandas as pd
    import geopandas as gpd
    import osmnx as ox
    import folium
    from folium.plugins import MarkerCluster
    from shapely.geometry import Point
    from IPython.display import IFrame

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _jsonify_weird_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Convert list/dict/set/tuple columns to JSON strings so CSV/GPKG writing is safe."""
        out = df.copy()
        for c in out.columns:
            if c == "geometry":
                continue
            if out[c].apply(lambda x: isinstance(x, (list, dict, set, tuple))).any():
                out[c] = out[c].apply(
                    lambda x: json.dumps(x, ensure_ascii=False)
                    if isinstance(x, (list, dict, set, tuple))
                    else x
                )
        return out

    def _safe_str(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return ""
        return str(x)

    # ------------------------------------------------------------
    # 1) OSM tags: heritage + monuments (and related)
    # ------------------------------------------------------------
    # Your original tags
    TAGS_HERIT_BASE = {
        "historic": True,
        "heritage": True,
        "tourism": ["museum", "attraction"],
        "memorial": True
    }

    # Added: monuments and common monument-like tagging patterns
    TAGS_MONUMENTS_1 = {"historic": ["monument", "memorial"]}
    TAGS_MONUMENTS_2 = {"tourism": ["artwork", "gallery", "attraction"]}
    TAGS_MONUMENTS_3 = {"memorial": ["statue", "bust", "stone", "plaque", "sculpture", "war_memorial"]}
    # Some mappers also use these keys directly
    TAGS_MONUMENTS_4 = {"artwork_type": True}

    tag_queries = [TAGS_HERIT_BASE, TAGS_MONUMENTS_1, TAGS_MONUMENTS_2, TAGS_MONUMENTS_3, TAGS_MONUMENTS_4]

    # Make sure yerevan_ll polygon is in EPSG:4326 for OSMnx querying
    poly_ll = yerevan_ll.to_crs("EPSG:4326").geometry.iloc[0]

    frames = []
    for tags in tag_queries:
        try:
            g = ox.features_from_polygon(poly_ll, tags)
            if g is not None and len(g) > 0:
                frames.append(g)
        except Exception as e:
            print("OSMnx query failed for tags:", tags, "| error:", repr(e))

    if len(frames) == 0:
        raise RuntimeError("No OSM features were returned. Check polygon, internet, or Overpass availability.")

    # Combine and deduplicate by index (OSMnx typically uses a multiindex like (element_type, osmid))
    herit_raw = pd.concat(frames)
    herit_raw = herit_raw[~herit_raw.index.duplicated(keep="first")].copy()
    herit_raw = herit_raw[herit_raw.geometry.notnull()].copy()

    # Project to UTM (your pipeline uses EPSG:32638)
    herit = ensure_crs(herit_raw, 32638)

    # ------------------------------------------------------------
    # 2) Convert to datapoints (keep original geometry as WKT too)
    # ------------------------------------------------------------
    herit = herit.copy()
    herit["orig_geom_type"] = herit.geometry.geom_type
    herit["orig_geom_wkt"] = herit.geometry.to_wkt()

    # Convert non-point geometries to representative points
    points = herit[herit["orig_geom_type"] == "Point"].copy()
    non_points = herit[herit["orig_geom_type"] != "Point"].copy()

    if len(non_points) > 0:
        non_points = non_points.copy()
        non_points["geometry"] = non_points.geometry.representative_point()

    herit_pts = gpd.GeoDataFrame(
        pd.concat([points, non_points], ignore_index=True),
        crs="EPSG:32638",
        geometry="geometry"
    )

    # Add a stable local id (useful for joins, popups, etc.)
    herit_pts["feature_id"] = range(1, len(herit_pts) + 1)

    # g point in UTM for distance calc (you already had this)
    g_utm = gpd.GeoSeries([Point(G_LON, G_LAT)], crs="EPSG:4326").to_crs("EPSG:32638").iloc[0]
    herit_pts["dist_to_g_m"] = herit_pts.geometry.distance(g_utm)

    # ------------------------------------------------------------
    # 3) Save to GPKG and CSV with all attributes
    # ------------------------------------------------------------
    AMEN_POINTS_GPKG = os.path.join(DATA_DIR, "heritage_points_with_monuments.gpkg")
    AMEN_POINTS_CSV  = os.path.join(DATA_DIR, "heritage_points_with_monuments.csv")

    # GPKG export (convert odd columns to JSON strings first)
    herit_pts_export = _jsonify_weird_columns(herit_pts)
    herit_pts_export.to_file(AMEN_POINTS_GPKG, layer="herit_points", driver="GPKG")

    # CSV export: use EPSG:4326 + lon/lat + geometry_wkt
    herit_ll = herit_pts_export.to_crs("EPSG:4326").copy()
    herit_ll["lon"] = herit_ll.geometry.x
    herit_ll["lat"] = herit_ll.geometry.y
    herit_ll["geometry_wkt"] = herit_ll.geometry.to_wkt()

    csv_df = pd.DataFrame(herit_ll.drop(columns=["geometry"]))
    csv_df = _jsonify_weird_columns(csv_df)
    csv_df.to_csv(AMEN_POINTS_CSV, index=False, encoding="utf-8")

    print("Saved points (GPKG):", AMEN_POINTS_GPKG, "n:", len(herit_pts_export))
    print("Saved points (CSV): ", AMEN_POINTS_CSV)

    # ------------------------------------------------------------
    # 4) Folium map with clickable annotations (popups)
    # ------------------------------------------------------------
    MAP_HTML = os.path.join(DATA_DIR, "heritage_points_map.html")

    m = folium.Map(location=[G_LAT, G_LON], zoom_start=14, tiles="CartoDB positron")
    folium.Marker(
        location=[G_LAT, G_LON],
        tooltip="Republic Square (g)",
        popup="Republic Square (g)",
        icon=folium.Icon(icon="info-sign")
    ).add_to(m)

    cluster = MarkerCluster(name="Heritage + monuments").add_to(m)

    # Choose which fields you want to show in popup
    popup_fields = [
        "feature_id",
        "name",
        "historic",
        "heritage",
        "tourism",
        "memorial",
        "artwork_type",
        "wikipedia",
        "wikidata",
        "start_date",
        "addr:street",
        "addr:housenumber",
        "dist_to_g_m",
        "orig_geom_type"
    ]

    herit_ll_iter = herit_ll.copy()
    for _, r in herit_ll_iter.iterrows():
        title = _safe_str(r.get("name")) or _safe_str(r.get("historic")) or "Heritage place"

        rows_html = []
        for f in popup_fields:
            if f in r and _safe_str(r[f]) != "":
                val = r[f]
                if f == "dist_to_g_m":
                    try:
                        val = f"{float(val):.0f}"
                    except Exception:
                        val = _safe_str(val)
                rows_html.append(f"<tr><td><b>{f}</b></td><td>{_safe_str(val)}</td></tr>")

        popup_html = f"""
        <div style="max-width: 360px;">
          <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">{title}</div>
          <table style="width: 100%; font-size: 12px;">{''.join(rows_html)}</table>
        </div>
        """

        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=5,
            fill=True,
            popup=folium.Popup(popup_html, max_width=380),
            tooltip=title
        ).add_to(cluster)

    folium.LayerControl().add_to(m)
    m.save(MAP_HTML)

    print("Saved map HTML:", MAP_HTML)
    IFrame(MAP_HTML, width=1100, height=700)

