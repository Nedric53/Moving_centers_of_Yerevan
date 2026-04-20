import geopandas as gpd

from .common import ensure_crs, get_yerevan_boundary
from .config import BOUNDARY_GPKG


def build_boundary(boundary_path=BOUNDARY_GPKG) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Returns:
        yerevan_ll: boundary in EPSG:4326
        yerevan_utm: boundary in EPSG:32638
    """
    yerevan_ll = get_yerevan_boundary()
    yerevan_utm = ensure_crs(yerevan_ll, 32638)
    yerevan_utm.to_file(boundary_path, layer="boundary", driver="GPKG")
    return yerevan_ll, yerevan_utm
