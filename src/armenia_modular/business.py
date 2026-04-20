import osmnx as ox
import geopandas as gpd
import numpy as np
import pandas as pd

from .common import ensure_crs
from .config import BIZ_GRID_GPKG, BIZ_POINTS_GPKG


BUSINESS_TAGS = {
    "shop": True,
    "office": True,
    "craft": True,
    "industrial": True,
    "amenity": ["restaurant", "cafe", "bar", "fast_food", "bank", "pharmacy", "hospital", "clinic"],
    "building": ["commercial", "industrial", "retail", "office"],
}


def build_business_grid(
    yerevan_ll: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    out_points=BIZ_POINTS_GPKG,
    out_grid=BIZ_GRID_GPKG,
    business_tags: dict | None = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    ox.settings.use_cache = True
    ox.settings.log_console = True
    ox.settings.timeout = 180

    tags = business_tags or BUSINESS_TAGS
    poly_ll = yerevan_ll.geometry.iloc[0]
    biz_raw = ox.features_from_polygon(poly_ll, tags)
    biz_raw = biz_raw[biz_raw.geometry.notnull()].copy()

    biz = ensure_crs(biz_raw, 32638)
    gt = biz.geometry.geom_type
    pts = biz[gt == "Point"].copy()
    polys = biz[gt.isin(["Polygon", "MultiPolygon"])].copy()
    if len(polys) > 0:
        polys["geometry"] = polys.geometry.representative_point()

    biz_pts = gpd.GeoDataFrame(pd.concat([pts, polys], ignore_index=True), crs="EPSG:32638")

    join = gpd.sjoin(biz_pts[["geometry"]], grid[["cell_id", "geometry"]], predicate="within", how="left")
    counts = join.groupby("cell_id").size().rename("biz_count").reset_index()

    grid_biz = grid.copy()
    grid_biz = grid_biz.merge(counts, on="cell_id", how="left")
    grid_biz["biz_count"] = grid_biz["biz_count"].fillna(0).astype(int)
    grid_biz["biz_density_per_km2"] = grid_biz["biz_count"] / grid_biz["area_km2"].replace(0, np.nan)

    safe_cols = [c for c in ["name", "shop", "office", "craft", "industrial", "amenity", "building"] if c in biz_pts.columns]
    biz_pts_out = biz_pts[safe_cols + ["geometry"]].copy()

    biz_pts_out.to_file(out_points, layer="biz_points", driver="GPKG")
    grid_biz.to_file(out_grid, layer="grid_biz", driver="GPKG")
    return biz_pts_out, grid_biz
