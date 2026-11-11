"""East box layers at 30 m (east grid: x from 538,430 m, 2,590 columns; y from grid.Y1, 5,100 rows; EPSG:32616).
- Classes from data/east/reference_east.h5, same rules as regions.py: forest share >= 0.5, damage share >= 0.5,
  wetland share >= 0.5, upland = evergreen/deciduous with MERIT HAND > 5 m (HAND pulled at 30 m, as controls_ee.py).
- Sentinel-1 VH, October-only posts (orbit 19: 09-28 -> 10-22; orbit 92: mean(09-21, 10-03) -> 10-27), 30 m mean of 10 m
  linear power, dB difference, minus the SAME forest-median constants as the west box (features.py) so the two boxes join.
- NISAR HV and HH, track 76 frame 17, single pair 10-05 -> 10-17 (the only raw granules still on disk: the gate scenes),
  extracted from the raw GCOV files (mask 0/255 invalid) for BOTH boxes, 30 m mean of linear power, dB difference minus the
  west-box forest median of the same pair. Track 55 frame 73 raw files were deleted after extraction; its coverage of the
  east box is reported from the ASF footprint only.
Writes data/east/east_30m.npz, data/east/nisar_pair_30m_both.npz, docs/wind/east_layers.json."""
import json, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, ee
import grid as G
from ee_common import pull_grid
t0 = time.time(); R = 30.0
XE0 = G.X0 + G.W * 10; HE, WE = 15300, 7770; H3, W3 = HE // 3, WE // 3; CRS = f"EPSG:{G.EPSG}"
f = h5py.File("data/east/reference_east.h5", "r")
def share(name, fn):
    out = np.zeros((H3, W3), "float32")
    for r in range(0, HE, 600):
        a = fn(f[name][r:r + 600]); out[r // 3:(r + a.shape[0]) // 3] = a.reshape(-1, 3, W3, 3).mean((1, 3))
    return out
ff = share("ftype", lambda a: a > 0); fw = share("ftype", lambda a: a == 4); fd = share("damage", lambda a: a > 0); fi = share("intact", lambda a: a > 0)
fcc = share("clearcut", lambda a: a > 0)
hnd = pull_grid(ee.Image("MERIT/Hydro/v1_0_1").select("hnd"), CRS, XE0, G.Y1, 30, W3, H3)["hnd"]; print("hand", round(time.time() - t0), flush=True)
fu = np.zeros((H3, W3), "float32")
for r in range(0, HE, 600):
    a = f["ftype"][r:r + 600]; h = np.repeat(np.repeat(hnd[r // 3:(r + a.shape[0]) // 3] > 5, 3, 0), 3, 1)
    fu[r // 3:(r + a.shape[0]) // 3] = (np.isin(a, (1, 2)) & h).reshape(-1, 3, W3, 3).mean((1, 3))
forest = ff >= 0.5
cls = {"forest": forest, "damage": forest & (fd >= 0.5), "intact": forest & (fi >= 0.9) & ~(fd >= 0.5), "wetland": forest & (fw >= 0.5), "upland": forest & (fu >= 0.5),
       "damage_share": fd, "clearcut_share": fcc, "hand": hnd}
# ---- Sentinel-1 VH (east)
DATES = {19: ["2026-09-28", "2026-10-22"], 92: ["2026-09-21", "2026-10-03", "2026-10-27"]}; vh = {}
for o, ds in DATES.items():
    for d in ds:
        img = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(ee.Geometry.Rectangle([-86.62, 30.38, -85.78, 31.82]))
               .filter(ee.Filter.eq("relativeOrbitNumber_start", o)).filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
               .filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")).select("VH").mosaic())
        img = img.setDefaultProjection(CRS, None, 10).updateMask(img.gt(0)).reduceResolution(ee.Reducer.mean(), False, 64).rename("v")
        vh[(o, d)] = pull_grid(img, CRS, XE0, G.Y1, 30, W3, H3)["v"]; print("s1", o, d, round(float(np.isfinite(vh[(o, d)]).mean()), 3), round(time.time() - t0), flush=True)
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)
def lmean(xs):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(xs), 0) if len(xs) > 1 else xs[0]
WEST_MED = {19: -0.086, 92: -0.899}          # features.py: o19_VH / o92_VH forest median diff removed (west box)
d19 = db(vh[(19, "2026-10-22")]) - db(vh[(19, "2026-09-28")]) - WEST_MED[19]
d92 = db(vh[(92, "2026-10-27")]) - db(lmean([vh[(92, "2026-09-21")], vh[(92, "2026-10-03")]])) - WEST_MED[92]
with np.errstate(invalid="ignore"): cls["s1_vh_oct"] = np.nanmean(np.stack([d19, d92]), 0).astype("float32")
cls["s1_o19_valid"] = np.isfinite(d19); cls["s1_o92_valid"] = np.isfinite(d92)
np.savez_compressed("data/east/east_30m.npz", **cls)
# ---- NISAR track 76 pair from the raw gate granules, both boxes
GR = "/science/LSAR/GCOV/grids/frequencyA"
RAW = {"2026-10-05": "data/nisar/NISAR_L2_PR_GCOV_032_076_A_017_4005_DHDH_A_20261005T110224_20261005T110258_P05023_N_F_J_001.h5",
       "2026-10-17": "data/nisar/NISAR_L2_PR_GCOV_033_076_A_017_4005_DHDH_A_20261017T110224_20261017T110259_P05023_N_F_J_001.h5"}
def extract(path, pol_src, x_origin, ncols10, nrows10):
    """Block-mean (30 m, >= 5 of 9 valid) of one GCOV polarisation onto a 10 m lattice starting at (x_origin, grid.Y1)."""
    out = np.full((nrows10 // 3, ncols10 // 3), np.nan, "float32")
    with h5py.File(path, "r") as h:
        g = h[GR]; xs, ys = g["xCoordinates"][()], g["yCoordinates"][()]
        cx = int(round((xs[0] - (x_origin + 5)) / 10)); ry = int(round(((G.Y1 - 5) - ys[0]) / 10))
        gc0, gc1 = max(0, cx), min(ncols10, cx + len(xs))
        if gc1 <= gc0: return out
        for r in range(0, nrows10, 900):
            re_ = min(r + 900, nrows10); lo, hi = max(r - ry, 0), min(re_ - ry, len(ys))
            if hi <= lo: continue
            a_ = np.full((re_ - r, ncols10), np.nan, "float32")
            m = g["mask"][lo:hi, gc0 - cx:gc1 - cx]; v = g[pol_src][lo:hi, gc0 - cx:gc1 - cx].astype("float32"); v[(m == 0) | (m == 255)] = np.nan
            a_[lo + ry - r:hi + ry - r, gc0:gc1] = v
            vv = a_.reshape(-1, 3, ncols10 // 3, 3); n = np.isfinite(vv).sum((1, 3))
            out[r // 3:re_ // 3] = np.where(n >= 5, np.nansum(vv, (1, 3)) / np.maximum(n, 1), np.nan)
    return out
BOX = {"west": (G.X0, (G.W // 300) * 300), "east": (XE0, WE)}
pw = {(d, pol, bx): extract(p_, src, x0, nc, HE) for d, p_ in RAW.items() for pol, src in (("HV", "HVHV"), ("HH", "HHHH")) for bx, (x0, nc) in BOX.items()}
print("nisar extracted", round(time.time() - t0), flush=True)
west_forest = np.load("data/regions_30.npz")["forest"]
nis = {}
for pol in ("HV", "HH"):
    dw = db(pw[("2026-10-17", pol, "west")]) - db(pw[("2026-10-05", pol, "west")]); de = db(pw[("2026-10-17", pol, "east")]) - db(pw[("2026-10-05", pol, "east")])
    med = float(np.nanmedian(dw[west_forest & np.isfinite(dw)]))
    nis[f"west_t76_{pol}_pair_diff"] = (dw - med).astype("float32"); nis[f"east_t76_{pol}_pair_diff"] = (de - med).astype("float32"); nis[f"median_removed_{pol}"] = med
np.savez_compressed("data/east/nisar_pair_30m_both.npz", **nis)
# coverage report
inv = json.load(open("data/artifact/inventory.json"))
from shapely.geometry import shape, box
EB = box(-86.60, 30.40, -85.80, 31.80)
fr = {}
for t in ("076", "055"):
    fp = [shape(x["footprint"]) for x in inv["nisar"] if x["track"] == t]; u = fp[0]
    for q in fp[1:]: u = u.union(q)
    fr[t] = round(u.intersection(EB).area / EB.area, 3)
eastnis = nis["east_t76_HV_pair_diff"]
rep = {"east_forest_km2": round(float(forest.sum()) * 9e-4, 1), "east_damage_km2_cells": round(float(cls["damage"].sum()) * 9e-4, 1),
       "east_upland_forest_km2": round(float(cls["upland"].sum()) * 9e-4, 1), "east_wetland_forest_km2": round(float(cls["wetland"].sum()) * 9e-4, 1),
       "s1_valid_share_of_east_forest": {"o19": round(float(cls["s1_o19_valid"][forest].mean()), 3), "o92": round(float(cls["s1_o92_valid"][forest].mean()), 3)},
       "nisar_t76_pair_valid_share_of_east_forest": round(float(np.isfinite(eastnis)[forest].mean()), 3),
       "nisar_frame_footprint_share_of_east_box": fr, "nisar_median_removed_dB": {k: nis[f"median_removed_{k}"] for k in ("HV", "HH")}, "seconds": round(time.time() - t0)}
json.dump(rep, open("docs/wind/east_layers.json", "w"), indent=1); print(json.dumps(rep, indent=1))
