import geopandas as gpd

from .common import make_grid
from .config import GRID_CELL_M, GRID_GPKG


def build_grid(yerevan_utm, cell_size_m: int = GRID_CELL_M, out_path=GRID_GPKG) -> gpd.GeoDataFrame:
    grid = make_grid(yerevan_utm.total_bounds, cell_size_m, crs=yerevan_utm.crs)
    grid = gpd.overlay(grid, yerevan_utm[["geometry"]], how="intersection")
    grid["area_km2"] = grid.geometry.area / 1_000_000.0
    grid["cx"] = grid.geometry.centroid.x
    grid["cy"] = grid.geometry.centroid.y
    grid.to_file(out_path, layer="grid", driver="GPKG")
    return grid
