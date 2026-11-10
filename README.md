# blowdown

Hurricane blowdown detection with NISAR L-band GCOV vs Sentinel-1 C-band, Alabama/Florida study area
(lon −87.60 to −86.60, lat 30.40 to 31.80).

Reports:
- [docs/gate/gate.md](docs/gate/gate.md)
- [docs/pipeline/pipeline.md](docs/pipeline/pipeline.md)
- [docs/pipeline/controls.md](docs/pipeline/controls.md)
- [docs/models/](docs/models/)

Scripts are in `scripts/`. Data (not in git) is in `data/`. Python environment: `.venv/`. Earth Engine project: `blowdown`.

## Regenerating derived data

`data/layers.h5` (10 m pre/post/difference layers per NISAR track and S1 orbit-year, about 36 GB) was deleted on the
`models` branch to free disk. It is derived from `data/stack/*.h5`, `data/s1/*.h5` and `data/s2_stack.h5`, which are kept.
Rebuild it with one command from the repository root:

```
.venv/Scripts/python.exe scripts/stack_combine.py
```

Only `scripts/evaluate.py` (pipeline step 5) reads it. The model work on the `models` branch builds its 30 m features
directly from `data/stack`, `data/s1` and Earth Engine and does not need it.

## Do not delete `data/models/`

`data/models/frozen/` (the frozen models and thresholds, hashed in `docs/models/frozen_manifest.json`) and
`data/models/labeling_key.csv` (which cell id is which; only its sha256 is in git) are not in git and cannot be
regenerated: the labeling ids are random, so re-running `scripts/labeling_build.py` without the key would silently draw a
new sample that no longer matches `labeling.zip`. Keep them until the held-out scoring pass is done.

Labeling: copy `labeling.zip` anywhere, unzip it, and open `labeling/index.html` in a browser (no server needed).
