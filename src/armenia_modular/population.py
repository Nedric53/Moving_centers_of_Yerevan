import geopandas as gpd
import numpy as np
import rasterio
from rasterstats import zonal_stats

from .config import POP_GPKG


def build_population_grid(grid: gpd.GeoDataFrame, clip_utm_tif, out_path=POP_GPKG) -> gpd.GeoDataFrame:
    with rasterio.open(clip_utm_tif) as src:
        nodata = src.nodata

    zs = zonal_stats(grid, clip_utm_tif, stats=["sum"], nodata=nodata, all_touched=False)
    grid_pop = grid.copy()
    grid_pop["pop_sum"] = [z["sum"] if z["sum"] is not None else 0.0 for z in zs]
    grid_pop["pop_density_per_km2"] = grid_pop["pop_sum"] / grid_pop["area_km2"].replace(0, np.nan)
    grid_pop.to_file(out_path, layer="grid_pop", driver="GPKG")
    return grid_pop
