# NISAR no-storm controls, upland scoring and persistence

Branch `pipeline`; extends [pipeline.md](pipeline.md). Same study area, 10 m grid, NISAR invalid-pixel mask (mask 0/255), forest-median re-centring, Sentinel-2 provisional damage mask and labels (block damage ≥ 50%, intact ≥ 90%) as pipeline.md.

Scripts:
- [control_search.py](../../scripts/control_search.py)
- [stack_build.py](../../scripts/stack_build.py), now called with `data/control_granules.json`
- [controls_ee.py](../../scripts/controls_ee.py)
- [controls_eval.py](../../scripts/controls_eval.py)
- [controls_upland.py](../../scripts/controls_upland.py)
- [controls_strict.py](../../scripts/controls_strict.py)
- [controls_tables.py](../../scripts/controls_tables.py), which generates the tables below as [controls_tables.md](controls_tables.md)

Numbers: [controls_eval.json](controls_eval.json), [controls_strict.json](controls_strict.json), [controls_upland.json](controls_upland.json).

## Summary

**How much is the storm.** The storm 12-day pair (10-05 → 10-17) scores HV AUC 0.828 at 100 m.
- **Control C** (2026-09-11 → 09-23) uses the same processor as the storm pair and scores 0.543. That puts about 87% of the storm pair's AUC above 0.5 on the storm (CI on the difference: +0.21 to +0.36).
- **Control B** (2025, older processor) scores 0.566, which gives about 80%.
- In dB, damage minus intact is +0.76 dB for the storm pair against +0.06 / +0.07 dB for the controls.

**Upland forest.** The HV signal holds there at lower strength. On blocks that are at least 90% upland forest (evergreen or deciduous, HAND > 5 m):
- 100 m: AUC 0.744 (+0.49 dB) against 0.514 (C) and 0.566 (B).
- 30 m: 0.616 against 0.503 / 0.527.
- Every CI on the difference excludes zero.

HH shows no detectable storm signal on upland forest at 10-17: 0.496 at 100 m, against C 0.478, with a CI that spans zero.

**Structural or wet.**

*Upland, HV:* the contrast stays put from 10-17 to 10-29, with a slight drop: +0.52 → +0.47 dB at 30 m, +0.49 → +0.41 at 100 m. That points to structural damage rather than a wetness pulse.

*Upland, HH:* a contrast of +0.26 to +0.37 dB appears only by 10-29. The 10-29 scene comes from a newer processor (P05036), and "steady" rests on only these two dates. So the upland reading is suggestive, not proven.

*Woody wetland:* the NISAR contrasts grow from 10-17 to 10-29 instead of fading (HV +0.68 → +0.76, HH +0.83 → +1.01), and HH is strongest. That pattern fits longer inundation as well as structural damage, and these data can't separate the two.

*Sentinel-1* doesn't follow the expected wetness pattern either:
- Orbit 92 fades more on upland (+0.43 → +0.26) than in woody wetland (+0.96 → +0.85).
- Orbit 19's 11-03 contrast flips sign in both domains. That whole scene is 1.19 dB brighter over forest than 09-28, which points to something about that acquisition rather than a gradual fade.

## Step 1: control scenes (track 76, frame 17, ascending, `_PR_`)

| Date | Processor | Spec | Role | Download | Valid share of grid | Forest median HV / HH (dB)* |
|---|---|---|---|---|---|---|
| 2025-10-22 | **X05009** ⚠ | **1.4.0** ⚠ | Control B pre | 6.17 GB, 14.7 min | 0.877 | −11.57 / −5.13 |
| 2025-11-03 | **X05009** ⚠ | **1.4.0** ⚠ | Control B post | 6.18 GB, 14.7 min | 0.888 | −12.09 / −5.55 |
| 2026-09-11 | P05023 | 1.5.0 | Control C pre | 6.01 GB, 14.0 min | 0.855 | −9.44 / −4.00 |
| 2026-09-23 | P05023 | 1.5.0 | Control C post (already extracted) | n/a | n/a | −9.61 / −4.15 |
| 2026-10-05 | P05023 | 1.5.0 | Storm A pre | n/a | n/a | −8.82 / −3.48 |
| 2026-10-17 | P05023 | 1.5.0 | Storm A post | n/a | n/a | −9.78 / −4.24 |
| 2026-10-29 | P05036 ⚠ | 1.6.0 | Persistence post | n/a | n/a | −10.41 / −5.28 |

\*Forest median on 977,967 100 m forest blocks valid in all seven scenes.

**Processor flag.** Both 2025 scenes come from an older processor (X05009, spec 1.4.0) than the storm scenes (P05023, 1.5.0).
- They're about 2 dB lower than the 2026 scenes in forest-median HV but only about 1 dB lower in HH, so the offset isn't a single gain.
- Re-centring removes uniform offsets only.
- That is why control C, on the same processor as the storm pair, is the primary control.

All three new scenes landed on the grid with no lattice shift and normal valid coverage. They were extracted to about 0.79 GB HH/HV files each, and the raw files were deleted.

## Step 2: storm vs no-storm 12-day pairs

- A = 2026-10-05 → 10-17 (storm)
- C = 2026-09-11 → 09-23 (no storm, same processor)
- B = 2025-10-22 → 11-03 (no storm, previous year)

Each cell gives the AUC, with the dB difference in brackets: the recentred damage-block mean minus the intact-block mean. The 10 m scores use the same stratified pixel sample as evaluate.py. Rebuilding the four-scene headline with this code reproduces `auc.json` exactly (track 76 HV: 0.582 / 0.686 / 0.851).

| Pol | Res (m) | Forest type | A storm | C 2026 pre | B 2025 | A − C | A − B | n damage |
|---|---|---|---|---|---|---|---|---|
| HV | 10 | all | 0.568 (+0.70) | 0.502 (+0.01) | 0.511 (+0.08) | +0.066 | +0.057 | 1,409,947 |
| HV | 10 | evergreen | 0.551 (+0.52) | 0.495 (−0.05) | 0.513 (+0.09) | +0.056 | +0.038 | 652,306 |
| HV | 10 | deciduous | 0.542 (+0.47) | 0.490 (−0.09) | 0.496 (+0.01) | +0.052 | +0.046 | 1,188 |
| HV | 10 | woody wetland | 0.562 (+0.63) | 0.504 (+0.03) | 0.507 (+0.05) | +0.058 | +0.055 | 692,006 |
| HV | 30 | all | 0.656 (+0.73) | 0.514 (+0.05) | 0.527 (+0.08) | +0.142 | +0.129 | 753,395 |
| HV | 30 | evergreen | 0.615 (+0.53) | 0.495 (−0.03) | 0.532 (+0.09) | +0.120 | +0.083 | 343,623 |
| HV | 30 | deciduous | 0.647 (+0.66) | 0.483 (−0.09) | 0.519 (+0.07) | +0.164 | +0.128 | 572 |
| HV | 30 | woody wetland | 0.650 (+0.68) | 0.523 (+0.09) | 0.510 (+0.03) | +0.127 | +0.140 | 375,233 |
| HV | 100 | all | **0.828 (+0.76)** | 0.543 (+0.06) | 0.566 (+0.07) | **+0.285** | **+0.262** | 60,378 |
| HV | 100 | evergreen | 0.760 (+0.55) | 0.497 (−0.03) | 0.583 (+0.09) | +0.263 | +0.177 | 26,884 |
| HV | 100 | woody wetland | 0.839 (+0.71) | 0.568 (+0.10) | 0.506 (+0.01) | +0.271 | +0.333 | 31,084 |
| HH | 10 | all | 0.551 (+0.53) | 0.499 (−0.01) | 0.521 (+0.13) | +0.052 | +0.030 | 1,409,947 |
| HH | 10 | evergreen | 0.516 (+0.16) | 0.490 (−0.10) | 0.526 (+0.16) | +0.026 | −0.010 | 652,306 |
| HH | 10 | deciduous | 0.551 (+0.51) | 0.513 (+0.11) | 0.492 (−0.03) | +0.038 | +0.059 | 1,188 |
| HH | 10 | woody wetland | 0.570 (+0.74) | 0.507 (+0.06) | 0.508 (+0.05) | +0.063 | +0.062 | 692,006 |
| HH | 30 | all | 0.604 (+0.53) | 0.504 (+0.01) | 0.553 (+0.14) | +0.100 | +0.051 | 753,395 |
| HH | 30 | evergreen | 0.522 (+0.11) | 0.478 (−0.11) | 0.565 (+0.16) | +0.044 | −0.043 | 343,623 |
| HH | 30 | deciduous | 0.642 (+0.66) | 0.516 (+0.04) | 0.530 (+0.11) | +0.126 | +0.112 | 572 |
| HH | 30 | woody wetland | 0.661 (+0.83) | 0.530 (+0.11) | 0.512 (+0.03) | +0.131 | +0.149 | 375,233 |
| HH | 100 | all | 0.680 (+0.53) | 0.522 (+0.01) | 0.620 (+0.13) | +0.158 | +0.060 | 60,378 |
| HH | 100 | evergreen | 0.529 (+0.07) | 0.461 (−0.12) | 0.651 (+0.16) | +0.068 | −0.122 | 26,884 |
| HH | 100 | woody wetland | 0.792 (+0.86) | 0.586 (+0.13) | 0.506 (+0.00) | +0.206 | +0.286 | 31,084 |

Deciduous at 100 m has 23 damage blocks, too few to score.

**Block bootstrap of A minus control, all forest** (10 km tiles; 150 draws at 30 m, 300 at 100 m; blocks valid in both pairs)

| Comparison | Pol | Res | AUC A | AUC control | A − control | 95% CI |
|---|---|---|---|---|---|---|
| A − C | HV | 30 m | 0.656 | 0.514 | +0.142 | +0.116 to +0.180 |
| A − B | HV | 30 m | 0.656 | 0.527 | +0.129 | +0.107 to +0.147 |
| A − C | HH | 30 m | 0.604 | 0.504 | +0.099 | +0.064 to +0.139 |
| A − B | HH | 30 m | 0.604 | 0.552 | +0.052 | +0.016 to +0.084 |
| A − C | HV | 100 m | 0.828 | 0.543 | +0.285 | +0.205 to +0.362 |
| A − B | HV | 100 m | 0.828 | 0.564 | +0.264 | +0.205 to +0.320 |
| A − C | HH | 100 m | 0.680 | 0.521 | +0.158 | +0.092 to +0.227 |
| A − B | HH | 100 m | 0.680 | 0.616 | +0.064 | −0.016 to +0.140 |

**Checks**
- **Labels without the 2025 optical term** (100 m, definition as matched_check.py): A HV 0.828 → 0.854, B HV 0.566 → 0.585, B HH 0.620 → 0.633, C about unchanged. So the floor is not an artefact of the label using 2025 data. B's HH score of 0.62 to 0.65 remains unexplained.
- **Other 12-day pairs, HV, all forest:**
  - Pre-pre 09-23 → 10-05: AUC 0.454 at 100 m. Damage areas got relatively darker while 10-05 is 0.8 dB brighter overall, so pair A, with 10-05 as its pre scene, may be slightly inflated.
  - The earlier sensitivity run gave 0.835 and 0.836 for the stack with either pre scene alone, so the conclusion doesn't change.
  - Post-post 10-17 → 10-29: 0.544.

## Step 3: upland forest only

Upland means NLCD evergreen or deciduous with MERIT Hydro HAND above 5 m. HAND was pulled at 30 m (nearest neighbour from about 90 m) and repeated to 10 m.
- Upland forest: 4,517 km² of 9,512 km² of forest (47%).
- **Damage mask in upland: 245.5 km² of 756.8 km² (32%).** The other 68% is woody wetland, mixed forest, or low-HAND pine.

Scoring:
- 10 m scores use only upland pixels.
- 30 m and 100 m scores use **strict upland blocks**: at least 90% upland forest, and labelled from the upland pixels with the usual 50% / 90% rules.
- A looser version, which allowed up to half of a damage block to be non-upland, gave slightly higher HV AUCs (0.765 at 100 m) and is kept in controls_eval.json.

**Step 2 pairs on strict upland forest: AUC (Δ dB)**

| Pol | Res | A storm | C 2026 pre | B 2025 | A − C (95% CI) | A − B (95% CI) | 10-05 → 10-29 | n damage / intact (A) |
|---|---|---|---|---|---|---|---|---|
| HV | 10 m | 0.552 (+0.53) | 0.500 (−0.01) | 0.511 (+0.08) | +0.052 | +0.041 | 0.547 (+0.47) | 454,414 / 655,464 |
| HV | 30 m | 0.616 (+0.52) | 0.503 (+0.01) | 0.527 (+0.07) | +0.113 (+0.058 to +0.150) | +0.090 (+0.068 to +0.115) | 0.611 (+0.47) | 196,675 / 1,403,209 |
| HV | 100 m | **0.744 (+0.49)** | 0.514 (+0.01) | 0.566 (+0.07) | **+0.229** (+0.113 to +0.314) | **+0.180** (+0.115 to +0.237) | 0.721 (+0.41) | 9,222 / 79,069 |
| HH | 10 m | 0.519 (+0.19) | 0.494 (−0.06) | 0.524 (+0.14) | +0.025 | −0.005 | 0.542 (+0.44) | 454,414 / 655,464 |
| HH | 30 m | 0.521 (+0.10) | 0.487 (−0.07) | 0.560 (+0.15) | +0.035 (−0.011 to +0.075) | −0.037 (−0.077 to −0.003) | 0.575 (+0.37) | 196,675 / 1,403,209 |
| HH | 100 m | 0.496 (−0.02) | 0.478 (−0.08) | 0.640 (+0.14) | +0.018 (−0.077 to +0.108) | −0.140 (−0.230 to −0.041) | 0.600 (+0.26) | 9,222 / 79,069 |

By construction, upland is almost all evergreen. Upland deciduous has 398 damage blocks at 30 m (looser labels): HV A 0.667 / C 0.510 / B 0.497, HH A 0.677 / C 0.509 / B 0.514. Indicative only.

**Main pipeline table: NISAR HV stack vs S1 VH stack with October-only posts.**
- The S1 posts are orbit 19 10-22 and orbit 92 10-27.
- S1 at 30 m comes from new per-date pulls; at 100 m from `s1_perdate_100.npz`.
- The all-forest 100 m rows reproduce matched_check.json (0.795 and 0.809).

| NISAR arm | Res | Domain | AUC NISAR | AUC S1 Oct | NISAR − S1 | 95% CI (block) | n damage |
|---|---|---|---|---|---|---|---|
| Both tracks | 30 m | all forest | 0.647 | 0.640 | +0.007 | −0.009 to +0.022 | 794,499 |
| Track 76 | 30 m | all forest | 0.686 | 0.648 | +0.038 | +0.025 to +0.051 | 759,635 |
| Both tracks | 100 m | all forest | 0.786 | 0.795 | −0.009 | −0.032 to +0.009 | 62,818 |
| Track 76 | 100 m | all forest | 0.851 | 0.809 | +0.042 | +0.021 to +0.060 | 60,809 |
| Both tracks | 30 m | **strict upland** | 0.562 | 0.589 | −0.027 | −0.048 to −0.010 | 208,572 |
| Track 76 | 30 m | **strict upland** | 0.634 | 0.602 | +0.032 | +0.013 to +0.050 | 198,240 |
| Both tracks | 100 m | **strict upland** | 0.618 | 0.694 | **−0.076** | −0.123 to −0.037 | 9,780 |
| Track 76 | 100 m | **strict upland** | 0.747 | 0.720 | +0.027 | −0.010 to +0.057 | 9,289 |

On upland forest:
- Track 76 still edges date-matched S1: +0.03, significant at 30 m but not at 100 m.
- The two-track NISAR average loses to S1, because track 55 is weak in pine (pipeline.md).

## Step 4: does the signal persist?

Contrast here means the recentred dB difference averaged over damage blocks minus the average over intact blocks, at 30 m.
- S1 VH: each post date against that orbit's pre-storm average. For orbit 19 that's 09-28; for orbit 92 it's the mean of 09-21 and 10-03.
- NISAR: post date against 10-05.

The plot and this table use the looser upland labels. The strict-upland NISAR values are in the step 3 table: HV +0.52 → +0.47 dB at 30 m and +0.49 → +0.41 at 100 m. At 100 m the looser-label values are within 0.06 dB of the 30 m ones.

![persistence](fig_persistence.png)

| Series | Upland | Woody wetland |
|---|---|---|
| NISAR HV, post 10-17 | +0.54 | +0.68 |
| NISAR HV, post 10-29 (P05036) | +0.49 | +0.76 |
| NISAR HH, post 10-17 | +0.13 | +0.83 |
| NISAR HH, post 10-29 (P05036) | +0.40 | +1.01 |
| S1 VH orbit 19, post 10-22 | +0.53 | +0.82 |
| S1 VH orbit 19, post 11-03 | −0.53 | −0.07 |
| S1 VH orbit 92, post 10-27 | +0.43 | +0.96 |
| S1 VH orbit 92, post 11-08 | +0.26 | +0.85 |
| NISAR HV no-storm C (2026 pre) / B (2025) | +0.01 / +0.08 | +0.09 / +0.03 |
| NISAR HH no-storm C (2026 pre) / B (2025) | −0.07 / +0.15 | +0.11 / +0.03 |

As AUC, the NISAR HV storm signal on all forest is about as strong at 10-29 as at 10-17: 10-05 → 10-29 scores 0.823 at 100 m, against 0.828.

**Whole-scene S1 level, before re-centring** (forest median against the first pre date):
- Orbit 19: 10-22 −0.09 dB, **11-03 +1.19 dB**.
- Orbit 92: 10-03 +0.20, 10-27 −0.73, 11-08 −0.49 dB (against 09-21).

The orbit 19 11-03 scene is much brighter across the whole forest. After re-centring that makes damage look relatively dark. A scene-wide change like that (rain or wet canopy at acquisition is a likely cause, but unverified) is not the gradual wetness fade the test was looking for.

**Salvage after 10-29.** I compared Sentinel-2 SCL-masked medians for 10-11..10-29 and 10-30..11-10 at 30 m. Clearing-like means NDVI after 10-29 below 0.35 and a drop of more than 0.15.
- Damage blocks: 2.46 km² clearing-like, 0.34% of damage blocks.
- Intact blocks: 0.04 km².
- Forest pixels had 3.6 clear Sentinel-2 looks on average after 10-29.

Some salvage-like clearing has started inside the damage mask, but too little to move any number here.

## Disk and time

| Item | Size / time |
|---|---|
| 3 NISAR granules downloaded, one at a time | 18.4 GB, 43 min; raw files deleted |
| Compact control files in data/stack | 2.36 GB (data/stack now 8.4 GB) |
| Earth Engine pull (HAND, 7 S1 dates, S2 composites at 30 m) | 39 min (S2 alone 28 min) |
| controls_eval.py | 13 min |
| controls_upland.py, controls_strict.py | not timed (a few minutes each) |
| Free disk | 645.0 GB at start, 641.6 GB after the downloads, about 639 GB now; never near the 15 GB floor |

Not touched:
- `data/layers.h5`
- NISAR frames 18 and 72 (not downloaded)
- the remote (nothing pushed)

## Not verified

- **2025 calibration.** The 2025 control scenes are X05009 / spec 1.4.0, about 2 dB darker in HV and 1 dB in HH than 2026. Non-uniform processor differences were not checked. Control B's HH upland AUC of 0.64 to 0.65, with no storm, is not explained.
- **The 10-29 scene is P05036.** It sits about 0.6 dB (HV) and 1 dB (HH) lower overall in pipeline.md's check. The HH contrast that appears by 10-29, on upland and in wetland, could partly be processing rather than ground change. Persistence rests on two NISAR dates.
- **Orbit 19's 11-03 scene** is 1.19 dB brighter overall. Its cause (rain, wet canopy, or processing) wasn't checked against weather data.
- **Inundation vs structure in woody wetland** can't be separated with these data. No water-level or flood-extent data were used.
- **Upland mask quality.** MERIT HAND is about 90 m and predates 2026. The 5 m threshold is the spec's, not tuned.
- **The damage reference is still Sentinel-2 based** and provisional. There's no aerial or field truth inside the band.
- **Salvage counts** are 30 m Sentinel-2 composites over about 12 days. Clearing smaller than 30 m, or under cloud in every look, would be missed.
