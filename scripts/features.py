"""Models step 2: 30 m feature stack on the prediction grid (data/regions_30.npz), one file per region.
Radar (dB): pre, post, diff for
  NISAR track 76 (pre 09-23,10-05; post 10-17,10-29) and track 55 (pre 09-22,10-04; post 10-16,10-28), HH and HV;
  S1 orbit 19 (pre 09-28; post 10-22) and orbit 92 (pre 09-21,10-03; post 10-27), VV and VH (October-only posts).
  Scenes are block-averaged to 30 m in linear power (>= 5 of 9 valid 10 m pixels), averaged across the stack in linear power,
  then converted to dB. diff = post - pre, re-centred on its median over all forest cells of the grid (as pipeline/controls).
Other: hand (MERIT HAND, m), nlcd (forest type at 30 m: 1 evergreen, 2 deciduous, 3 mixed, 4 woody wetland, by majority).
Neighbourhood means (3x3, 7x7, NaN-aware) of every radar layer are computed on the full grid before cropping.
Training labels (train file only): 1 = damage cell, 0 = intact cell, -1 = not used. Removed: cells with any 10 m pixel in the
  reference clearcut/salvage flag; cells flagged clearing-like after 10-29 (controls.md: S2 NDVI 10-30..11-10 < 0.35 and
  drop > 0.15 vs 10-11..10-29); edge cells: a damage cell with any non-damage forest cell in its 3x3 window, an intact
  cell with any damage cell in its 3x3 window (5x5 kept only 22% of damage cells; 3x3 keeps 43%).
Files (data/models/):
  features_train.h5   full grid; every layer NaN (labels -1) inside the held-out and tip exclusions (block + 2 km)
  features_heldout.h5 held-out block + 1 km context margin (margin lies in the 2 km buffer); mask 'block' marks the block
  features_tip.h5     tip rectangle + 1 km margin; mask 'block' = tip cells (rectangle within NOAA footprint)
  Region files carry forest / upland / wetland masks and no damage labels.
Writes docs/models/feature_coverage.json (share of forest cells with valid data, per region and sensor; validity only)."""
import json, os, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy.ndimage import uniform_filter, maximum_filter, minimum_filter
import grid as G
t0 = time.time(); os.makedirs("data/models", exist_ok=True)
RG = np.load("data/regions_30.npz"); forest, upland, wetland = RG["forest"], RG["upland"], RG["wetland"]
H3, W3 = forest.shape; HB, WB = H3 * 3, W3 * 3
E = np.load("data/controls_ee_30.npz"); V = np.load("data/s1_vv_30.npz"); K = np.load("data/controls_coarse.npz")
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return (10 * np.log10(x)).astype("float32")
def lmean(xs):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(xs), 0) if len(xs) > 1 else xs[0]
def b3(a):
    v = a.reshape(a.shape[0] // 3, 3, a.shape[1] // 3, 3); n = np.isfinite(v).sum((1, 3))
    return np.where(n >= 5, np.nansum(v, (1, 3)) / np.maximum(n, 1), np.nan).astype("float32")
F = {}
NIS = {"t76": (["076_2026-09-23", "076_2026-10-05"], ["076_2026-10-17", "076_2026-10-29"]),
       "t55": (["055_2026-09-22", "055_2026-10-04"], ["055_2026-10-16", "055_2026-10-28"])}
for tk, (pre, post) in NIS.items():
    fs = {k: h5py.File(f"data/stack/{k}.h5", "r") for k in pre + post}
    P = {(k, p): np.zeros((H3, W3), "float32") for k in fs for p in ("HH", "HV")}
    for r in range(0, HB, 600):
        re_ = min(r + 600, HB)
        for (k, p), arr in P.items(): arr[r // 3:re_ // 3] = b3(fs[k][p][r:re_, :WB])
    for p in ("HH", "HV"):
        F[f"{tk}_{p}_pre"] = db(lmean([P[(k, p)] for k in pre])); F[f"{tk}_{p}_post"] = db(lmean([P[(k, p)] for k in post]))
    print(tk, "done", round(time.time() - t0), flush=True)
S1 = {"o19": (["19_2026-09-28"], ["19_2026-10-22"]), "o92": (["92_2026-09-21", "92_2026-10-03"], ["92_2026-10-27"])}
for ob, (pre, post) in S1.items():
    for p, src in (("VV", V), ("VH", E)):
        F[f"{ob}_{p}_pre"] = db(lmean([src[f"{p}_{k}"] for k in pre])); F[f"{ob}_{p}_post"] = db(lmean([src[f"{p}_{k}"] for k in post]))
RADAR = []
for g in ("t76_HH", "t76_HV", "t55_HH", "t55_HV", "o19_VV", "o19_VH", "o92_VV", "o92_VH"):
    d = F[f"{g}_post"] - F[f"{g}_pre"]; med = float(np.nanmedian(d[forest & np.isfinite(d)])); F[f"{g}_diff"] = (d - med).astype("float32")
    RADAR += [f"{g}_pre", f"{g}_post", f"{g}_diff"]; print(g, "forest median diff removed", round(med, 3), flush=True)
F["hand"] = E["hnd"].astype("float32"); F["nlcd"] = np.where(forest, K["ft_30"], 0).astype("float32")
def nmean(a, k):
    ok = np.isfinite(a); s = uniform_filter(np.where(ok, a, 0).astype("float64"), k, mode="constant"); n = uniform_filter(ok.astype("float64"), k, mode="constant")
    return np.where(n > 0, s / np.maximum(n, 1e-9), np.nan).astype("float32")
for name in RADAR:
    F[f"{name}_m3"] = nmean(F[name], 3); F[f"{name}_m7"] = nmean(F[name], 7)
print("neighbourhood means done", round(time.time() - t0), flush=True)
# ---- training labels
Rr = h5py.File("data/reference.h5", "r"); cc = np.zeros((H3, W3), bool)
for r in range(0, HB, 600):
    re_ = min(r + 600, HB); c10 = Rr["clearcut"][r:re_, :WB] > 0; cc[r // 3:re_ // 3] = c10.reshape(-1, 3, W3, 3).any((1, 3))
with np.errstate(invalid="ignore"): sal = (E["ndvi_p2"] < 0.35) & (E["ndvi_p2"] - E["ndvi_p1"] < -0.15) & (E["n_p2"] > 0)
D, I = RG["damage"], RG["intact"]
nondmg_forest = forest & ~D
edge_d = D & (maximum_filter(nondmg_forest.astype(np.uint8), 3) > 0)
edge_i = I & (maximum_filter(D.astype(np.uint8), 3) > 0)
lab = np.full((H3, W3), -1, "int8"); lab[I] = 0; lab[D] = 1
drop = cc | sal | edge_d | edge_i; lab[drop] = -1
train = RG["train"]; lab[~train] = -1
lstats = {"damage_cells_before": int((D & train).sum()), "intact_cells_before": int((I & train).sum()),
          "removed_clearcut_flag": int(((D | I) & train & cc).sum()), "removed_salvage_after_1029": int(((D | I) & train & sal & ~cc).sum()),
          "removed_edge": int(((edge_d | edge_i) & train & ~cc & ~sal).sum()),
          "damage_cells_used": int((lab == 1).sum()), "intact_cells_used": int((lab == 0).sum())}
print(lstats, flush=True)
# ---- coverage (validity only)
cov = {}
regions = {"train": train & forest, "heldout": RG["heldout"] & forest, "tip": RG["tip"] & forest}
for rn, m in regions.items():
    v = {s: np.isfinite(F[f"{s}_diff"]) for s in ("t76_HV", "t55_HV", "o19_VH", "o92_VH")}
    nis = v["t76_HV"] | v["t55_HV"]; s1 = v["o19_VH"] | v["o92_VH"]
    cov[rn] = {**{k: round(float(x[m].mean()), 3) for k, x in v.items()}, "any_nisar": round(float(nis[m].mean()), 3), "any_s1": round(float(s1[m].mean()), 3),
               "any_nisar_and_any_s1": round(float((nis & s1)[m].mean()), 3), "forest_cells": int(m.sum()),
               **({"upland_cells_scorable": int((nis & s1 & m & upland).sum()), "wetland_cells_scorable": int((nis & s1 & m & wetland).sum())} if rn != "train" else {})}
json.dump({"coverage": cov, "labels": lstats, "radar_layers": RADAR, "seconds": round(time.time() - t0)}, open("docs/models/feature_coverage.json", "w"), indent=1)
print(json.dumps(cov, indent=1), flush=True)
# ---- write
NAMES = list(F)
def write(path, rs, cs, block, extra):
    with h5py.File(path, "w") as o:
        for n in NAMES: o.create_dataset(n, data=F[n][rs, cs], compression="lzf", shuffle=True)
        for n, a in extra.items(): o.create_dataset(n, data=a[rs, cs], compression="lzf")
        o.create_dataset("block", data=block[rs, cs], compression="lzf")
        o.attrs.update({"row0": rs.start or 0, "col0": cs.start or 0, "res_m": 30.0, "origin_x": G.X0, "origin_y": G.Y1, "crs": f"EPSG:{G.EPSG}"})
masks = {"forest": forest, "upland": upland, "wetland": wetland}
# train file: blank everything inside the exclusions
Ftrain = {n: np.where(train, F[n], np.nan).astype("float32") for n in NAMES}
with h5py.File("data/models/features_train.h5", "w") as o:
    for n in NAMES: o.create_dataset(n, data=Ftrain[n], compression="lzf", shuffle=True)
    for n, a in masks.items(): o.create_dataset(n, data=a & train, compression="lzf")
    o.create_dataset("label", data=lab, compression="lzf"); o.create_dataset("train", data=train, compression="lzf")
    o.attrs.update({"row0": 0, "col0": 0, "res_m": 30.0, "origin_x": G.X0, "origin_y": G.Y1, "crs": f"EPSG:{G.EPSG}"})
del Ftrain
M = 33   # 1 km margin
for nm, blk in (("heldout", RG["heldout"]), ("tip", RG["tip"])):
    rr, cc_ = np.nonzero(blk if nm == "heldout" else RG["tip"])
    rs = slice(max(0, rr.min() - M), min(H3, rr.max() + 1 + M)); cs = slice(max(0, cc_.min() - M), min(W3, cc_.max() + 1 + M))
    write(f"data/models/features_{nm}.h5", rs, cs, blk, masks)
print("written", round(time.time() - t0), flush=True)
