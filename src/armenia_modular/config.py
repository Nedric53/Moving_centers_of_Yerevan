from pathlib import Path

# Project paths
ROOT_DIR = Path.cwd()
DATA_DIR = ROOT_DIR / "data" / "yerevan_full_pipeline"
INTERACTIVE_DIR = ROOT_DIR / "data" / "yerevan_interactive"
COMPARE_DIR = ROOT_DIR / "data" / "compare_business_areas"
ASSETS_DIR = ROOT_DIR / "assets"

DATA_DIR.mkdir(parents=True, exist_ok=True)
INTERACTIVE_DIR.mkdir(parents=True, exist_ok=True)
COMPARE_DIR.mkdir(parents=True, exist_ok=True)

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
KAGGLE_SALE_CSV = ROOT_DIR / "data" / "kaggle_real_estate" / "apartments_for_sale(with_lat_long).csv"

# Historic center g (Republic Square)
G_LON = 44.5126
G_LAT = 40.1775

# Standard outputs
BOUNDARY_GPKG = DATA_DIR / "yerevan_boundary.gpkg"
WORLDPOP_RAW_TIF = DATA_DIR / "worldpop_ARM_2020.tif"
WORLDPOP_CLIP_WGS84_TIF = DATA_DIR / "worldpop_yerevan_clipped_wgs84.tif"
WORLDPOP_CLIP_UTM_TIF = DATA_DIR / "worldpop_yerevan_clipped_utm38n.tif"
GRID_GPKG = DATA_DIR / f"yerevan_grid_{GRID_CELL_M}m.gpkg"
POP_GPKG = DATA_DIR / "grid_population.gpkg"
BIZ_POINTS_GPKG = DATA_DIR / "business_points.gpkg"
BIZ_GRID_GPKG = DATA_DIR / "grid_business.gpkg"
RENT_POINTS_GPKG = DATA_DIR / "rent_points_kaggle_sale.gpkg"
RENT_GRID_GPKG = DATA_DIR / "grid_rent.gpkg"
AMEN_POINTS_GPKG = DATA_DIR / "heritage_points.gpkg"
AMEN_GRID_GPKG = DATA_DIR / "grid_amenity.gpkg"
MASTER_GPKG = DATA_DIR / "master_grid.gpkg"
MASTER_CSV = DATA_DIR / "master.csv"
