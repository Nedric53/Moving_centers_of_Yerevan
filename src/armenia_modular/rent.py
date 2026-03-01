import geopandas as gpd
import numpy as np
import pandas as pd

from .common import ensure_crs, parse_area
from .config import FILTER_CURRENCY, GROSS_YIELD_ANNUAL, KAGGLE_SALE_CSV, RENT_GRID_GPKG, RENT_POINTS_GPKG


REQUIRED_COLUMNS = ["Latitude", "Longitude", "price", "currency", "floor_area"]


def build_rent_grid(
    yerevan_ll: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    csv_path=KAGGLE_SALE_CSV,
    out_points=RENT_POINTS_GPKG,
    out_grid=RENT_GRID_GPKG,
    filter_currency: str = FILTER_CURRENCY,
    gross_yield_annual: float = GROSS_YIELD_ANNUAL,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    df = pd.read_csv(csv_path)

    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            raise RuntimeError(f"Missing column {c} in Kaggle CSV. Columns: {list(df.columns)}")

    work = df.dropna(subset=["Latitude", "Longitude", "price"]).copy()
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    work = work.dropna(subset=["price"])

    work["currency"] = work["currency"].astype(str).str.upper().str.strip()
    work = work[work["currency"] == filter_currency].copy()

    work["area_m2"] = work["floor_area"].apply(parse_area)
    work.loc[(work["area_m2"] < 10) | (work["area_m2"] > 500), "area_m2"] = np.nan
    work["price_per_m2"] = work["price"] / work["area_m2"]
    work.loc[(work["price_per_m2"] <= 0) | (work["price_per_m2"] > 20000), "price_per_m2"] = np.nan

    work["implied_rent_per_m2_month"] = (work["price_per_m2"] * gross_yield_annual) / 12.0

    rent_pts = gpd.GeoDataFrame(
        work,
        geometry=gpd.points_from_xy(work["Longitude"], work["Latitude"]),
        crs="EPSG:4326",
    )
    rent_pts = rent_pts[rent_pts.within(yerevan_ll.geometry.iloc[0])].copy()
    rent_pts = ensure_crs(rent_pts, 32638)

    j = gpd.sjoin(
        rent_pts[["implied_rent_per_m2_month", "geometry"]],
        grid[["cell_id", "geometry"]],
        predicate="within",
        how="left",
    )

    agg = j.groupby("cell_id").agg(
        rent_listings=("geometry", "size"),
        implied_rent_per_m2_month=("implied_rent_per_m2_month", "median"),
    ).reset_index()

    grid_rent = grid.copy()
    grid_rent = grid_rent.merge(agg, on="cell_id", how="left")
    grid_rent["rent_listings"] = grid_rent["rent_listings"].fillna(0).astype(int)

    rent_pts.to_file(out_points, layer="rent_points", driver="GPKG")
    grid_rent.to_file(out_grid, layer="grid_rent", driver="GPKG")
    return rent_pts, grid_rent
