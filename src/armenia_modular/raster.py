from pathlib import Path

from .common import clip_raster_to_polygon, download_file, reproject_raster
from .config import WORLDPOP_CLIP_UTM_TIF, WORLDPOP_CLIP_WGS84_TIF, WORLDPOP_RAW_TIF, WORLDPOP_URL


def build_worldpop_raster(
    yerevan_ll,
    raw_tif=WORLDPOP_RAW_TIF,
    clip_tif=WORLDPOP_CLIP_WGS84_TIF,
    clip_utm_tif=WORLDPOP_CLIP_UTM_TIF,
    worldpop_url: str = WORLDPOP_URL,
) -> tuple[Path, Path, Path]:
    """
    Download, clip, and reproject the WorldPop raster.
    Returns (raw_tif, clip_tif, clip_utm_tif).
    """
    raw_tif = download_file(worldpop_url, raw_tif)
    clip_tif = clip_raster_to_polygon(raw_tif, yerevan_ll, clip_tif)
    clip_utm_tif = reproject_raster(clip_tif, clip_utm_tif, dst_crs="EPSG:32638")
    return Path(raw_tif), Path(clip_tif), Path(clip_utm_tif)
