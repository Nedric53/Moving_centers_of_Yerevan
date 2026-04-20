# Armenia moving centers

## Canonical structure

- `run_armenia_modular.ipynb`: main notebook that builds the pipeline outputs and the site.
- `src/armenia_modular/config.py`: project-root-based paths and constants.
- `src/armenia_modular/pipeline.py`: end-to-end data pipeline.
- `src/armenia_modular/interactive_fast.py`: interactive Yerevan polygon module.
- `src/armenia_modular/interactive_precomputed.py`: precomputed Yerevan polygon module.
- `src/armenia_modular/compare_business_areas.py`: comparison page generator.
- `src/armenia_modular/dashboard_embed.py`: theoretical dashboard generator.
- `src/armenia_modular/site_builder.py`: landing page and site assembly.
- `src/armenia_modular/publish_github_pages.py`: optional publish step to copy the built site into `docs/`.

## Data layout

- `data/inputs/real_estate`: raw external input tables.
- `data/reference/city_business_areas`: reference metadata and polygons for city comparison.
- `data/build/pipeline`: heavy intermediate pipeline outputs.
  - `vectors`: GeoPackage layers and vector outputs.
  - `tables`: CSV tables.
  - `rasters`: TIFF rasters.
- `data/build/site`: generated site files and standalone HTML modules.
- `docs`: optional publish copy for GitHub Pages.
- `site_source_assets`: source images and static assets that are copied into the built site when needed.

## Main generated files

- `data/build/site/index.html`: landing page.
- `data/build/site/yerevan_interactive_model.html`: main interactive Yerevan module.
- `data/build/site/yerevan_precomputed_model.html`: precomputed comparison-ready Yerevan model.
- `data/build/site/theoretical_model_dashboard.html`: theoretical dashboard.
- `data/build/site/city_business_area_comparison.html`: city comparison page.

## Typical flow

Run `run_armenia_modular.ipynb` from the project root. The notebook should generate the data pipeline outputs in `data/build/pipeline` and all site HTML files in `data/build/site`. If needed, publish that built site into `docs/` separately.

## GitHub publish

The project now includes a one-command publisher:

- `tools/rebuild_release_site.py`: rebuilds the generated site and refreshes `docs/`.
- `tools/publish_project_to_github.ps1`: rebuilds the release site, commits the whole project, and can push to GitHub.

First upload with a clean remote reset:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\publish_project_to_github.ps1 `
  -FreshStart `
  -GitName "Your Name" `
  -GitEmail "you@example.com"
```

Regular updates afterwards:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\publish_project_to_github.ps1 `
  -GitName "Your Name" `
  -GitEmail "you@example.com"
```

If `git` is not in `PATH`, pass its full path:

```powershell
-GitExe "C:\Program Files\Git\cmd\git.exe"
```

After the first successful push, enable GitHub Pages in repository settings:

- Branch: `main`
- Folder: `/docs`
