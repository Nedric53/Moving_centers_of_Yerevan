from .boundary import build_boundary
from .business import build_business_grid
from .grid import build_grid
from .heritage import build_heritage_grid
from .master import build_master_grid
from .model import fit_business_model
from .population import build_population_grid
from .raster import build_worldpop_raster
from .rent import build_rent_grid


def run_pipeline(*, save_master_csv: bool = True) -> dict:
    """
    Runs the notebook pipeline end to end and returns all important objects.
    """
    yerevan_ll, yerevan_utm = build_boundary()
    _, _, clip_utm_tif = build_worldpop_raster(yerevan_ll)

    grid = build_grid(yerevan_utm)
    grid_pop = build_population_grid(grid, clip_utm_tif)
    biz_points, grid_biz = build_business_grid(yerevan_ll, grid)
    rent_points, grid_rent = build_rent_grid(yerevan_ll, grid)
    heritage_points, grid_amen = build_heritage_grid(yerevan_ll, grid)

    master = build_master_grid(
        grid=grid,
        grid_pop=grid_pop,
        grid_biz=grid_biz,
        grid_rent=grid_rent,
        grid_amen=grid_amen,
        save_csv=save_master_csv,
    )

    model_bundle = fit_business_model(master)

    return {
        "yerevan_ll": yerevan_ll,
        "yerevan_utm": yerevan_utm,
        "grid": grid,
        "grid_pop": grid_pop,
        "biz_points": biz_points,
        "grid_biz": grid_biz,
        "rent_points": rent_points,
        "grid_rent": grid_rent,
        "heritage_points": heritage_points,
        "grid_amen": grid_amen,
        "master": model_bundle["master"],
        "logit_model": model_bundle["logit_model"],
        "features": model_bundle["features"],
        "means": model_bundle["means"],
        "stds": model_bundle["stds"],
        "mu0x": model_bundle["mu0x"],
        "mu0y": model_bundle["mu0y"],
    }
