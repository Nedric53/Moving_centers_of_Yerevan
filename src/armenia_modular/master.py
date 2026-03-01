import geopandas as gpd
import numpy as np
import pandas as pd

from .config import MASTER_CSV, MASTER_GPKG


def build_master_grid(
    grid: gpd.GeoDataFrame,
    grid_pop: gpd.GeoDataFrame,
    grid_biz: gpd.GeoDataFrame,
    grid_rent: gpd.GeoDataFrame,
    grid_amen: gpd.GeoDataFrame,
    out_gpkg=MASTER_GPKG,
    out_csv=MASTER_CSV,
    business_threshold: float = 2.0,
    save_csv: bool = True,
) -> gpd.GeoDataFrame:
    master = grid.copy()

    master = master.merge(grid_pop[["cell_id", "pop_sum", "pop_density_per_km2"]], on="cell_id", how="left")
    master = master.merge(grid_biz[["cell_id", "biz_count", "biz_density_per_km2"]], on="cell_id", how="left")
    master = master.merge(
        grid_rent[["cell_id", "rent_listings", "implied_rent_per_m2_month"]],
        on="cell_id",
        how="left",
    )
    master = master.merge(
        grid_amen[["cell_id", "dist_to_g_m", "dist_to_nearest_herit_m", "herit_cnt_500m", "herit_density_500m"]],
        on="cell_id",
        how="left",
    )

    master["cx"] = master.geometry.centroid.x
    master["cy"] = master.geometry.centroid.y

    master["R_implied"] = pd.to_numeric(master["implied_rent_per_m2_month"], errors="coerce")
    master["rent_missing"] = (~np.isfinite(master["R_implied"]) | (master["R_implied"] <= 0)).astype(int)

    valid_r = master.loc[master["rent_missing"] == 0, "R_implied"]
    r_med = float(np.nanmedian(valid_r)) if len(valid_r) else 0.0
    master.loc[master["rent_missing"] == 1, "R_implied"] = r_med
    master["log_rent"] = np.log1p(master["R_implied"])

    master["M_obs"] = master["biz_density_per_km2"].fillna(0)
    master["y_business"] = (master["M_obs"] >= float(business_threshold)).astype(int)

    master.to_file(out_gpkg, layer="master", driver="GPKG")
    if save_csv:
        pd.DataFrame(master.drop(columns="geometry")).to_csv(out_csv, index=False)

    return master
