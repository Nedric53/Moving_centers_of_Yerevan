import os
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import Point, box, mapping


def ensure_crs(gdf: gpd.GeoDataFrame, epsg: int = 32638) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise RuntimeError("GeoDataFrame CRS missing.")
    return gdf.to_crs(epsg=epsg)


def download_file(url: str, out_path: str | os.PathLike) -> Path:
    import requests

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    r = requests.get(url, stream=True, timeout=180)
    r.raise_for_status()
    with out_path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    return out_path


def get_yerevan_boundary() -> gpd.GeoDataFrame:
    ox.settings.use_cache = True
    ox.settings.log_console = True
    ox.settings.timeout = 180

    gdf = ox.geocode_to_gdf("Yerevan, Armenia")
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    if gdf.empty:
        raise RuntimeError("Could not fetch Yerevan polygon from OSM.")

    try:
        geom = gdf.geometry.union_all()
    except Exception:
        geom = gdf.geometry.unary_union

    return gpd.GeoDataFrame({"name": ["Yerevan"]}, geometry=[geom], crs=gdf.crs)


def clip_raster_to_polygon(in_tif: str | os.PathLike, poly_gdf: gpd.GeoDataFrame, out_tif: str | os.PathLike) -> Path:
    in_tif = Path(in_tif)
    out_tif = Path(out_tif)
    out_tif.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(in_tif) as src:
        poly = poly_gdf.to_crs(src.crs)
        geom = poly.geometry.iloc[0]
        geoms = [mapping(geom)]
        out_img, out_transform = mask(src, geoms, crop=True, filled=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_img.shape[1],
            "width": out_img.shape[2],
            "transform": out_transform,
        })
        with rasterio.open(out_tif, "w", **out_meta) as dst:
            dst.write(out_img)
    return out_tif


def reproject_raster(in_tif: str | os.PathLike, out_tif: str | os.PathLike, dst_crs: str = "EPSG:32638") -> Path:
    in_tif = Path(in_tif)
    out_tif = Path(out_tif)
    out_tif.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(in_tif) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({"crs": dst_crs, "transform": transform, "width": width, "height": height})
        with rasterio.open(out_tif, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest,
                )
    return out_tif


def make_grid(bounds, cell_size_m: float, crs) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bounds
    xs = np.arange(minx, maxx + cell_size_m, cell_size_m)
    ys = np.arange(miny, maxy + cell_size_m, cell_size_m)
    cells = []
    for x in xs[:-1]:
        for y in ys[:-1]:
            cells.append(box(x, y, x + cell_size_m, y + cell_size_m))
    grid = gpd.GeoDataFrame({"geometry": cells}, crs=crs)
    grid["cell_id"] = np.arange(len(grid)).astype(int)
    return grid


def parse_area(x) -> float:
    if pd.isna(x):
        return np.nan
    s = str(x).replace(",", ".")
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else np.nan


def utm_xy_to_lonlat(x: float, y: float) -> tuple[float, float]:
    pt = gpd.GeoSeries([Point(x, y)], crs="EPSG:32638").to_crs("EPSG:4326").iloc[0]
    return float(pt.x), float(pt.y)
