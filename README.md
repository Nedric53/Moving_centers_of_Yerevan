# Armenia moving centers package package


## Main files

- `src/armenia_modular/config.py`: constants and paths
- `src/armenia_modular/common.py`: shared helpers
- `src/armenia_modular/pipeline.py`: end-to-end pipeline
- `src/armenia_modular/interactive_fast.py`: wrapper for notebook cell 15
- `src/armenia_modular/interactive_precomputed.py`: wrapper for notebook cell 16
- `src/armenia_modular/compare_business_areas.py`: compare page
- `src/armenia_modular/site_builder.py`: scrolly site builder
- `src/armenia_modular/github_upload.py`: GitHub upload helpers
- `notebooks/run_armenia_modular.ipynb`: single runner notebook

## Typical use

```python
from src.armenia_modular.pipeline import run_pipeline

bundle = run_pipeline()
master = bundle["master"]
```

Then call the HTML wrappers using objects from `bundle`.
