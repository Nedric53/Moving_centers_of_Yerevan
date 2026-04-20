from pathlib import Path

# Project paths
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent

DATA_ROOT_DIR = ROOT_DIR / "data"
INPUTS_DIR = DATA_ROOT_DIR / "inputs"
REFERENCE_DIR = DATA_ROOT_DIR / "reference"
BUILD_DIR = DATA_ROOT_DIR / "build"
SITE_SOURCE_ASSETS_DIR = ROOT_DIR / "site_source_assets"

REAL_ESTATE_INPUT_DIR = INPUTS_DIR / "real_estate"
CITY_BUSINESS_AREAS_DIR = REFERENCE_DIR / "city_business_areas"
CITY_BUSINESS_AREA_POLYGONS_DIR = CITY_BUSINESS_AREAS_DIR / "polygons"

PIPELINE_BUILD_DIR = BUILD_DIR / "pipeline"
SITE_BUILD_DIR = BUILD_DIR / "site"

PIPELINE_VECTOR_DIR = PIPELINE_BUILD_DIR / "vectors"
PIPELINE_TABLES_DIR = PIPELINE_BUILD_DIR / "tables"
PIPELINE_RASTERS_DIR = PIPELINE_BUILD_DIR / "rasters"

# Backward-compatible aliases used across modules
DATA_DIR = PIPELINE_BUILD_DIR
INTERACTIVE_DIR = SITE_BUILD_DIR
COMPARE_DIR = SITE_BUILD_DIR
ASSETS_DIR = SITE_SOURCE_ASSETS_DIR
DOCS_DIR = ROOT_DIR / "docs"

# Canonical generated filenames
LANDING_HTML_NAME = "index.html"
INTERACTIVE_MODEL_HTML_NAME = "yerevan_interactive_model.html"
PRECOMPUTED_MODEL_HTML_NAME = "yerevan_precomputed_model.html"
THEORETICAL_DASHBOARD_HTML_NAME = "theoretical_model_dashboard.html"
CITY_COMPARISON_HTML_NAME = "city_business_area_comparison.html"

# Canonical source asset filenames
HERO_IMAGE_ASSET_NAME = "hero_cover.png"
PROJECT_POSTER_ASSET_NAME = "project_poster.svg"
PROJECT_PDF_ASSET_NAME = "project_brief.pdf"
CITY_CENTERS_MAP_ASSET_NAME = "city_centers_map.png"
HISTORICAL_ICON_ASSET_NAME = "historical_center_icon.png"
BUSINESS_AREA_ICON_ASSET_NAME = "business_area_icon.png"
ADMINISTRATIVE_CENTER_ICON_ASSET_NAME = "administrative_center_icon.png"

INPUTS_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
BUILD_DIR.mkdir(parents=True, exist_ok=True)
SITE_SOURCE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
REAL_ESTATE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
CITY_BUSINESS_AREAS_DIR.mkdir(parents=True, exist_ok=True)
CITY_BUSINESS_AREA_POLYGONS_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_BUILD_DIR.mkdir(parents=True, exist_ok=True)
SITE_BUILD_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_VECTOR_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_TABLES_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_RASTERS_DIR.mkdir(parents=True, exist_ok=True)

# Grid settings
GRID_CELL_M = 500
BUFFER_HERIT_M = 500

# Transport
AVG_SPEED_KMH = 20.0
SPEED_M_PER_MIN = AVG_SPEED_KMH * 1000.0 / 60.0

# Rent conversion
GROSS_YIELD_ANNUAL = 0.06
FILTER_CURRENCY = "USD"

# Inputs
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Individual_countries/ARM/"
    "Armenia_100m_Population/ARM_ppp_v2c_2020.tif"
)
KAGGLE_SALE_CSV = REAL_ESTATE_INPUT_DIR / "apartments_for_sale_with_lat_long.csv"

# Historic center g (Republic Square)
G_LON = 44.5126
G_LAT = 40.1775

# Standard outputs
BOUNDARY_GPKG = PIPELINE_VECTOR_DIR / "yerevan_boundary.gpkg"
WORLDPOP_RAW_TIF = PIPELINE_RASTERS_DIR / "worldpop_ARM_2020.tif"
WORLDPOP_CLIP_WGS84_TIF = PIPELINE_RASTERS_DIR / "worldpop_yerevan_clipped_wgs84.tif"
WORLDPOP_CLIP_UTM_TIF = PIPELINE_RASTERS_DIR / "worldpop_yerevan_clipped_utm38n.tif"
GRID_GPKG = PIPELINE_VECTOR_DIR / f"yerevan_grid_{GRID_CELL_M}m.gpkg"
POP_GPKG = PIPELINE_VECTOR_DIR / "grid_population.gpkg"
BIZ_POINTS_GPKG = PIPELINE_VECTOR_DIR / "business_points.gpkg"
BIZ_GRID_GPKG = PIPELINE_VECTOR_DIR / "grid_business.gpkg"
RENT_POINTS_GPKG = PIPELINE_VECTOR_DIR / "rent_points_kaggle_sale.gpkg"
RENT_GRID_GPKG = PIPELINE_VECTOR_DIR / "grid_rent.gpkg"
AMEN_POINTS_GPKG = PIPELINE_VECTOR_DIR / "heritage_points.gpkg"
AMEN_GRID_GPKG = PIPELINE_VECTOR_DIR / "grid_amenity.gpkg"
MASTER_GPKG = PIPELINE_VECTOR_DIR / "master_grid.gpkg"
MASTER_CSV = PIPELINE_TABLES_DIR / "master.csv"
