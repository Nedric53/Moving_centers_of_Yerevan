from __future__ import annotations

import shutil
import sys
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armenia_modular.compare_business_areas import main as build_compare_html
from armenia_modular.config import (
    CITY_CENTERS_MAP_ASSET_NAME,
    DOCS_DIR,
    HERO_IMAGE_ASSET_NAME,
    MASTER_GPKG,
    PROJECT_PDF_ASSET_NAME,
    PROJECT_POSTER_ASSET_NAME,
    SITE_BUILD_DIR,
    SITE_SOURCE_ASSETS_DIR,
)
from armenia_modular.dashboard_embed import write_dashboard_html
from armenia_modular.interactive_fast import write_yerevan_single_polygon_html
from armenia_modular.interactive_precomputed import write_yerevan_precomputed_html
from armenia_modular.model import fit_business_model
from armenia_modular.site_builder import write_full_scrolly_site


def rebuild_release_site() -> dict[str, str]:
    master = gpd.read_file(MASTER_GPKG, layer="master")
    model_bundle = fit_business_model(master)

    interactive_path = write_yerevan_single_polygon_html(
        master=model_bundle["master"],
        logit_model=model_bundle["logit_model"],
        features=model_bundle["features"],
        means=model_bundle["means"],
        stds=model_bundle["stds"],
        mu0x=model_bundle["mu0x"],
        mu0y=model_bundle["mu0y"],
    )

    precomputed_path = write_yerevan_precomputed_html(
        master=model_bundle["master"],
        logit_model=model_bundle["logit_model"],
        features=model_bundle["features"],
        means=model_bundle["means"],
        stds=model_bundle["stds"],
        mu0x=model_bundle["mu0x"],
        mu0y=model_bundle["mu0y"],
    )

    dashboard_path = write_dashboard_html()
    compare_path = build_compare_html()
    interactive_html = Path(interactive_path).read_text(encoding="utf-8")

    write_full_scrolly_site(
        out_dir=str(SITE_BUILD_DIR),
        interactive_html=interactive_html,
        compare_html_src_path=str(compare_path),
        dashboard_filename=Path(dashboard_path).name,
        hero_image_src_path=str(SITE_SOURCE_ASSETS_DIR / HERO_IMAGE_ASSET_NAME),
        poster_svg_src_path=str(SITE_SOURCE_ASSETS_DIR / PROJECT_POSTER_ASSET_NAME),
        pdf_src_path=str(SITE_SOURCE_ASSETS_DIR / PROJECT_PDF_ASSET_NAME),
        context_image_src_path=str(SITE_SOURCE_ASSETS_DIR / CITY_CENTERS_MAP_ASSET_NAME),
    )

    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    shutil.copytree(SITE_BUILD_DIR, DOCS_DIR)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "interactive": str(interactive_path),
        "precomputed": str(precomputed_path),
        "dashboard": str(dashboard_path),
        "comparison": str(compare_path),
        "docs_index": str(DOCS_DIR / "index.html"),
    }


if __name__ == "__main__":
    result = rebuild_release_site()
    for key, value in result.items():
        print(f"{key}: {value}")
