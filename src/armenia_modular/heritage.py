import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

from .common import ensure_crs
from .config import AMEN_GRID_GPKG, AMEN_POINTS_GPKG, BUFFER_HERIT_M, G_LAT, G_LON


TAGS_HERIT = {
    "historic": True,
    "heritage": True,
    "tourism": ["museum", "attraction"],
    "memorial": True,
}


def build_heritage_grid(
    yerevan_ll: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    out_points=AMEN_POINTS_GPKG,
    out_grid=AMEN_GRID_GPKG,
    buffer_herit_m: float = BUFFER_HERIT_M,
    g_lon: float = G_LON,
    g_lat: float = G_LAT,
    tags: dict | None = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    tags = tags or TAGS_HERIT
    herit_raw = ox.features_from_polygon(yerevan_ll.geometry.iloc[0], tags)
    herit_raw = herit_raw[herit_raw.geometry.notnull()].copy()
    herit = ensure_crs(herit_raw, 32638)

    gt = herit.geometry.geom_type
    hp = herit[gt == "Point"].copy()
    hpoly = herit[gt.isin(["Polygon", "MultiPolygon"])].copy()
    if len(hpoly) > 0:
        hpoly["geometry"] = hpoly.geometry.representative_point()

    herit_pts = gpd.GeoDataFrame(pd.concat([hp, hpoly], ignore_index=True), crs="EPSG:32638")

    g_utm = gpd.GeoSeries([Point(g_lon, g_lat)], crs="EPSG:4326").to_crs("EPSG:32638").iloc[0]

    amen = grid.copy()
    amen_cent = gpd.GeoDataFrame(amen[["cell_id"]].copy(), geometry=amen.geometry.centroid, crs="EPSG:32638")
    amen["dist_to_g_m"] = amen.geometry.centroid.distance(g_utm)

    nearest = gpd.sjoin_nearest(
        amen_cent,
        herit_pts[["geometry"]],
        how="left",
        distance_col="dist_to_nearest_herit_m",
    )
    amen = amen.merge(nearest[["cell_id", "dist_to_nearest_herit_m"]], on="cell_id", how="left")

    buff = amen_cent.copy()
    buff["geometry"] = buff.geometry.buffer(buffer_herit_m)
    join_cnt = gpd.sjoin(herit_pts[["geometry"]], buff[["cell_id", "geometry"]], predicate="within", how="left")
    cnt = join_cnt.groupby("cell_id").size().rename("herit_cnt_500m").reset_index()
    amen = amen.merge(cnt, on="cell_id", how="left")
    amen["herit_cnt_500m"] = amen["herit_cnt_500m"].fillna(0).astype(int)

    buffer_area_km2 = (np.pi * (buffer_herit_m ** 2)) / 1_000_000.0
    amen["herit_density_500m"] = amen["herit_cnt_500m"] / buffer_area_km2

    herit_pts.to_file(out_points, layer="herit_points", driver="GPKG")
    amen.to_file(out_grid, layer="grid_amen", driver="GPKG")
    return herit_pts, amen
