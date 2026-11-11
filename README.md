# blowdown

Can satellite radar map forest blown down by a hurricane? This project compares NASA–ISRO NISAR L-band radar (GCOV) with
Sentinel-1 C-band radar over the forest Hurricane Isaias knocked down in October 2026 in Alabama and the Florida Panhandle (lon −87.60 to −86.60,
lat 30.40 to 31.80). A Sentinel-2 optical damage mask is the provisional reference, and the final scoring uses hand
labels on a held-out block.

- **Site:** [blowdown.johnazer.com](https://blowdown.johnazer.com): the write-up and an interactive map of the damage
  mask and radar layers. The source is in [`site/`](site/), and deployment notes are in [`site/DEPLOY.md`](site/DEPLOY.md).
- **Companion project:** [hurricane.johnazer.com](https://hurricane.johnazer.com).

## Held-out block: sealed until hand labeling is done

The held-out block (lat 31.14–31.32 plus a 2 km buffer) and the NOAA aerial-imagery tip are used only for the final
score. Until hand labeling is done and the single scoring pass has run:

- No model, threshold or statistic is fit or tuned there.
- Every analysis, figure and map leaves them masked. The site shows them as gray blocks.

The labeling key (which cell is which) is not in this repository. Only its sha256 hash is, in
`docs/models/labeling_key.sha256`. Neither are the hand labels or the frozen models. The models' hashes are in
`docs/models/frozen_manifest*.json`, so the models can be checked against them before scoring.

## Reports

- [docs/gate/gate.md](docs/gate/gate.md): first look, NISAR vs Sentinel-1 on two boxes
- [docs/pipeline/pipeline.md](docs/pipeline/pipeline.md) and [docs/pipeline/controls.md](docs/pipeline/controls.md): full-area comparison and no-storm controls
- [docs/models/](docs/models/): model design (pre-registered), training and validation
- [docs/wind/](docs/wind/): damage against the storm track, the stations, NEXRAD and an artifact check

Branches: `gate`, `pipeline`, `models` and `site` hold each stage as it was finished. `main` is the full project and the site.

## Rebuilding the derived data

Nothing under `data/` is in git: the raw downloads, stacks and intermediate grids run to tens of GB. Everything in
`docs/` and `site/data/` can be regenerated from the scripts in `scripts/`, except the items listed under "Cannot be
regenerated" below. Each script's docstring states its inputs and outputs.

Setup:

- Python environment in `.venv/`.
- Earth Engine access with a Cloud project. The scripts use project `blowdown`; change it in `scripts/ee_common.py`.
- A NASA Earthdata login in `~/.netrc` for `urs.earthdata.nasa.gov`, with the ASF data-access app authorized. It is
  read at run time and never stored in the repository.

Rough order (run from the repository root, e.g. `.venv/Scripts/python.exe scripts/stack_build.py`). It is drawn from
the scripts' docstrings, not from a fresh end-to-end run:

1. **Radar and optical stacks:** `stack_search.py`, `stack_build.py` (NISAR, downloads many GB), `s1_stack.py`,
   `s2_stack.py`, `stack_combine.py`, then `reference.py` (optical damage reference).
2. **Pipeline comparison:** `evaluate.py`, `sensitivity.py`, `matched_check.py`, `controls_*.py`, `pipeline_figures.py`.
3. **Models:** `regions.py`, `controls_ee.py`, `s1_vv_30.py`, `features.py`, `labels_v2.py`, `train_split.py`,
   `train_gbm*.py`, `train_unet*.py`, `train_diag.py`, `val_compare.py`.
4. **Wind and artifact checks:** `s2_stack_east.py`, `reference_east.py`, `east_layers.py`, `wind_link*.py`,
   `east_profiles.py`, `station_timing.py`, `nexrad_fetch.py`, `nexrad_maxvel.py`, `nexrad_fig.py`, `goes_wv.py`,
   `artifact_*.py`.
5. **Site:** `site_numbers.py`, `site_figures.py`, `site_layers.py` (map overlays in `site/data/`),
   `basemap_style.py` (basemap style), `site_screens.py` (screenshots, with the preview server running).

`data/layers.h5`, the 10 m pre/post/difference layers (about 36 GB), was deleted to free disk. Rebuild it with
`scripts/stack_combine.py`. Only `scripts/evaluate.py` reads it.

### Cannot be regenerated

These are kept locally, outside git, until the held-out scoring pass is done:

- `data/models/v1/` and `data/models/v2/`: the frozen models and thresholds.
- `data/models/labeling_key.csv`. The labeling ids are random, so re-running `scripts/labeling_build.py` without the
  key would draw a new sample that no longer matches the labeling images.

## Labeling

`labeling/` is the offline labeling page (open `labeling/index.html` in a browser, no server needed). It shows only
random cell ids and images, nothing about where a cell is or whether it falls inside the damage mask.
