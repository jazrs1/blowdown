# Model training (validation only)

Branch `models`. Design frozen in [design.md](design.md) (commit `fe4e253`) before any training.

Arms A–E were trained and tuned only on the training region, using the spatial validation split in [split.json](split.json). Models and thresholds are frozen and hashed in [frozen_manifest.json](frozen_manifest.json).

**Nothing inside the held-out block or the aerial tip was opened, scored or plotted by any training step.** Training reads only `features_train.h5`, where both exclusions (block + 2 km) are blank.

Scripts:
- [train_split.py](../../scripts/train_split.py)
- [train_gbm.py](../../scripts/train_gbm.py)
- [train_unet.py](../../scripts/train_unet.py)
- [train_diag.py](../../scripts/train_diag.py)

Numbers: [train_gbm.json](train_gbm.json), [train_unet.json](train_unet.json), [train_diag.json](train_diag.json).

## Read this first: the validation numbers are optimistic

The learned models reach validation AUC 0.97–0.9996. Don't expect that on John's labels. The diagnostic below re-scores the frozen models on the same validation tiles with different label sets, and shows why:
- In the validation tiles, **almost every intact cell lies outside the storm band.** Inside the band there are 220 intact cells against 44,882 damage cells.
- So the design labels mostly ask "storm band or rest of the forest?", and the models answer that very well.
- The design labels also leave out the hard cells near the mask edge.

| Score, validation tiles | Design labels (edge / flag cells removed) | All damage vs all intact cells | Inside the band only |
|---|---|---|---|
| A: NISAR HV threshold | 0.709 | 0.678 | 0.672 |
| A76: track 76 HV threshold | 0.738 | 0.717 | 0.633 |
| B: S1 VH threshold | 0.681 | 0.649 | 0.648 |
| A smoothed 7×7 (not an arm) | 0.859 | 0.819 | 0.779 |
| A76 smoothed 7×7 (not an arm) | 0.916 | 0.895 | 0.712 |
| B smoothed 7×7 (not an arm) | 0.873 | 0.844 | 0.799 |
| GBM C (NISAR) | 0.980 | 0.928 | 0.684 |
| GBM D (S1) | 0.973 | 0.890 | 0.778 |
| GBM E (both) | 0.995 | 0.948 | 0.804 |
| U-Net C (NISAR) | 0.997 | 0.985 | 0.728 |
| U-Net D (S1) | 0.999 | 0.991 | 0.804 |
| U-Net E (both) | 1.000 | 0.995 | 0.810 |

The "inside the band" column rests on only 220 intact cells, so it's noisy. Its signal is still clear:
- **Inside the band, the learned models are about level with a 7×7-smoothed S1 VH threshold** (0.78–0.81).
- The NISAR-only models are weaker there than the S1-only models (0.68–0.73 vs 0.78–0.80).
- Most of the models' edge over the plain thresholds comes from **spatial smoothing**. 70–82% of LightGBM gain is on the 7×7 means, and the smoothed thresholds alone reach 0.86–0.92 on the design labels.

John's held-out sample is drawn inside a block that holds the band, half from outside the Sentinel-2 mask. It's closer to the band-only case than to the design labels.

## Validation results per arm (design labels)

Validation = 30 spatial tiles (9.6 km), 50,704 damage cells and 670,329 intact cells. 12,101 of the damage cells are in upland and 32,732 in wetland.

Each cell shows AUC / F1 for the damaged class. F1 is at the frozen threshold, which was itself chosen on these validation cells, so **F1 here is in-sample and optimistic**. The validation prevalence is about 7%, unlike John's roughly 50/50 sample, so these F1 values don't carry over.

Model arms use the 5-seed mean probability.

| Arm | All forest | Upland | Wetland | Seed range (AUC, all) |
|---|---|---|---|---|
| A: NISAR HV threshold (mean of tracks) | 0.709 / 0.270 | 0.546 / 0.098 | 0.747 / 0.465 | n/a |
| A76: track 76 HV threshold | 0.738 / 0.307 | 0.630 / 0.156 | 0.732 / 0.444 | n/a |
| B: S1 VH threshold (October posts) | 0.681 / 0.243 | 0.540 / 0.077 | 0.741 / 0.443 | n/a |
| C GBM (NISAR) | 0.980 / 0.847 | 0.940 / 0.615 | 0.994 / 0.935 | 0.9793–0.9799 |
| D GBM (S1) | 0.973 / 0.830 | 0.939 / 0.617 | 0.989 / 0.930 | 0.9725–0.9727 |
| E GBM (both) | 0.995 / 0.922 | 0.983 / 0.798 | 0.999 / 0.970 | 0.9944–0.9948 |
| C U-Net (NISAR) | 0.997 / 0.947 | 0.990 / 0.852 | 0.999 / 0.981 | 0.9956–0.9961 |
| D U-Net (S1) | 0.999 / 0.964 | 0.996 / 0.905 | 1.000 / 0.989 | 0.9978–0.9982 |
| E U-Net (both) | 1.000 / 0.975 | 0.999 / 0.934 | 1.000 / 0.991 | 0.9988–0.9994 |

Upland is the harder domain for every arm, and the plain thresholds are near chance there (0.54–0.63).

**Frozen thresholds:**
- A: +0.757 dB
- A76: +1.045 dB
- B: +1.633 dB
- GBM: C 0.826, D 0.814, E 0.847
- U-Net: C 0.856, D 0.570, E 0.598

**Tuning choices** (seed 0, validation AUC):
- GBM C: 127 leaves, min leaf 100. Best iterations across seeds 772–1,660.
- GBM D: 31 leaves, min leaf 1,000. 1,968–2,635 iterations.
- GBM E: 127 leaves, min leaf 1,000. 1,001–1,631 iterations.
- The tuning grids differed by less than 0.002 AUC.
- U-Net learning rate: C 1e-3, D and E 3e-4. The two rates differed by less than 0.0005.
- U-Net best epochs: 18–29 of 30, so longer training might help a little. It wasn't tried, because the design fixed 30 epochs.
- U-Net training used 10,013 patches.

## Feature importance (LightGBM, share of total gain, mean of 5 seeds)

| Arm | Top features | By scale | Context (HAND + NLCD) |
|---|---|---|---|
| C (NISAR) | track 76 HV diff 7×7 0.369, track 76 HV diff 3×3 0.098, track 55 HV diff 7×7 0.070, track 55 HV pre 7×7 0.044, track 76 HH diff 7×7 0.041 | per-pixel 0.045, 3×3 0.214, 7×7 0.704 | 0.037 |
| D (S1) | orbit 19 VH diff 7×7 0.291, orbit 19 VH post 7×7 0.131, orbit 92 VH diff 7×7 0.119, orbit 92 VH post 3×3 0.100, orbit 92 VH post 7×7 0.049 | per-pixel 0.026, 3×3 0.211, 7×7 0.738 | 0.025 |
| E (both) | track 76 HV diff 7×7 0.311, orbit 19 VH diff 7×7 0.127, track 55 HV post 7×7 0.056, orbit 19 VH post 7×7 0.056, track 55 HV diff 7×7 0.055 | per-pixel 0.028, 3×3 0.144, 7×7 0.820 | 0.008 |

Grouped over scales:
- **C:** track 76 HV diff carries 0.47 of the gain. Track 55 HV diff 0.09, track 76 HH diff 0.06, track 55 HV pre/post 0.11.
- **D:** orbit 19 VH diff 0.30, orbit 19 VH post 0.16, orbit 92 VH post 0.15, orbit 92 VH diff 0.13. VV is minor.
- **E:** track 76 HV diff 0.33, then orbit 19 VH diff 0.13. In the combined model, NISAR track 76 HV is the single strongest input.

The post-only levels (VH post, HV post) are fairly important. They can carry land-cover and geometry information as well as change.

## Time and disk

| Item | Time | Disk |
|---|---|---|
| Deleted `data/layers.h5` (rebuild command in README) | n/a | −36.1 GB |
| Installed scikit-learn 1.9.1, LightGBM 4.7.0, PyTorch 2.11 (CUDA 12.8) in .venv | a few minutes | several GB in .venv (not measured) |
| S1 VV per-date pull at 30 m (Earth Engine) | 8 min | small |
| Regions + 30 m features (three files) | about 1.5 min per run, 3 runs | 3.3 GB (`data/models/features_*.h5`) |
| Labeling set: sample, S2 and aerial pulls, rendering, page, zip | 7 min | 30 MB folder + 30 MB zip |
| LightGBM (A, A76, B thresholds; C, D, E tuning + 5 seeds) | 30 min | GBM models 247 MB |
| U-Net (C, D, E; 2 learning rates + 5 seeds; RTX 5070) | 55 min | 1 MB |
| Validation diagnostic | 3 min | n/a |

Free disk is about 660 GB (615 GiB). `data/` dropped from 62 GB to 32 GB.

## Deviations and additions after the design commit

- **Added:** the validation diagnostic (`train_diag.py`). It changes nothing that was frozen.
- **Implementation details not in the design:**
  - F1 thresholds are searched over the 50th–99.5th percentiles of the validation score.
  - A U-Net validity channel is 1 where all six layers of that geometry are finite.
- **No other deviations.** The split rule accepted seed 0 at the first draw.

## Not verified

- **Held-out performance is unknown and likely much lower than validation** (see the diagnostic). It will be measured once, after John's labels.
- **Spatial independence of validation.** Validation tiles border training tiles behind only a 120 m guard band, and the band runs through both. Validation is not independent of training at the band scale.
- **F1 at the frozen threshold** is in-sample on validation.
- **The labeling page from `file://`.** It was tested over `http://localhost`: labelling, reload persistence, going back, and the CSV export all work. The built-in browser can't open `file://` pages with storage. Chrome, Edge and Firefox normally keep localStorage for `file://` pages; Safari can be stricter. The page warns if saving fails.
- **Labeling imagery.** I checked a few rendered images by eye, not all 550. Some may show cloud, haze or flooding in the composites. John's Unsure button covers those. 2 of the 150 tip cells fall in aerial gaps and say so.
- **README rebuild command** for `data/layers.h5` was checked against the script's inputs, not re-run.
- **The training labels are Sentinel-2-derived** and provisional, and John labels from the same composites.
