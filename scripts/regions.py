"""Models step 1: held-out block, aerial-tip block and training region on the 30 m prediction grid
(evaluation extent of data/coarse_30.npz: origin grid.X0, grid.Y1, 30 m, (HB/3) x (WB/3) cells).

30 m cell classes (from data/controls_coarse.npz, fractions of 10 m pixels):
  forest = majority forest type > 0; damage = damage fraction >= 0.5; intact = intact fraction >= 0.9;
  upland = upland-forest fraction >= 0.5 (NLCD evergreen/deciduous and MERIT HAND > 5 m); wetland = woody-wetland majority.
Band = data/extent_band.npy (pipeline step 1, lat/lon grid), sampled at each 30 m cell centre.

Aerial tip: band cells inside the NOAA aerial footprint; tip block = their bounding rectangle widened by 1 km east and west,
  intersected with the footprint. Tip exclusion = that rectangle + 2 km.
Held-out rule (design.md): slide a 20 km northing window along the band in 1 km steps. Block = bounding rectangle (easting)
  of the band cells in the window, widened by 1 km east and west, over the 20 km of northing. Candidate if
  (a) block + 2 km buffer does not touch the tip exclusion, (b) the window lies inside the band's northing range, and
  (c) it holds >= 100 cells each of damaged upland, intact upland, damaged wetland and non-damaged wetland forest
  (so the labeling sample can be drawn). Pick the candidate whose upland share of damage (10 m damage pixels in upland
  forest / all 10 m damage pixels in the block) is closest to the band-wide 0.324 (controls.md); ties -> southernmost.
Training region = analysis extent minus (held-out block + 2 km) minus (tip rectangle + 2 km).
Writes data/regions_30.npz, docs/models/regions.json, docs/models/fig_regions.png (band outline and blocks only)."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import shape
from shapely import contains_xy
import grid as G
K = np.load("data/controls_coarse.npz")
ft, dmg, itc, upl, dmgu = K["ft_30"], K["dmg_30"], K["itc_30"], K["upl_30"], K["dmg_u_30"]
H3, W3 = ft.shape; R = 30.0
forest = ft > 0; D = forest & (dmg >= 0.5); I = forest & (itc >= 0.9) & ~D; U = forest & (upl >= 0.5); Wt = ft == 4
xc = G.X0 + (np.arange(W3) + 0.5) * R; yc = G.Y1 - (np.arange(H3) + 0.5) * R
tr = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True)
XX, YY = np.meshgrid(xc, yc); lon, lat = tr.transform(XX, YY)
e = np.load("data/extent_ee.npz"); bx0, by0, bx1, by1 = e["extent"]; bres = float(e["res"]); B = np.load("data/extent_band.npy")
bi = np.clip(((by1 - lat) / bres).astype(int), 0, B.shape[0] - 1); bj = np.clip(((lon - bx0) / bres).astype(int), 0, B.shape[1] - 1)
inb = (lat >= by0) & (lat <= by1) & (lon >= bx0) & (lon <= bx1)
band = B[bi, bj] & inb
fp = shape(json.load(open("data/noaa_footprint_study.geojson"))) if True else None
fp = fp if fp.geom_type in ("Polygon", "MultiPolygon") else fp.geoms[0]
infp = contains_xy(fp, lon, lat)
# ---- tip
tipb = band & infp; tr_, tc_ = np.nonzero(tipb)
km = lambda x: int(round(x * 1000 / R))
t_r0, t_r1, t_c0, t_c1 = tr_.min(), tr_.max() + 1, max(0, tc_.min() - km(1)), min(W3, tc_.max() + 1 + km(1))
tip = np.zeros_like(band); tip[t_r0:t_r1, t_c0:t_c1] = True; tip &= infp
tip_ex = np.zeros_like(band); tip_ex[max(0, t_r0 - km(2)):t_r1 + km(2), max(0, t_c0 - km(2)):t_c1 + km(2)] = True
# ---- candidate windows
brows = np.nonzero(band.any(1))[0]; r_top, r_bot = brows.min(), brows.max() + 1
WIN = km(20); STEP = km(1); cands = []
SHARE = 0.324
for r0 in range(r_top, r_bot - WIN + 1, STEP):
    r1 = r0 + WIN; cols = np.nonzero(band[r0:r1].any(0))[0]
    if cols.size == 0: continue
    c0, c1 = max(0, cols.min() - km(1)), min(W3, cols.max() + 1 + km(1))
    ex = np.zeros_like(band); ex[max(0, r0 - km(2)):r1 + km(2), max(0, c0 - km(2)):c1 + km(2)] = True
    touches_tip = bool((ex & tip_ex).any())
    s = (slice(r0, r1), slice(c0, c1))
    n = {"dmg_upland": int((D[s] & U[s]).sum()), "intact_upland": int((I[s] & U[s]).sum()),
         "dmg_wetland": int((D[s] & Wt[s]).sum()), "nondmg_wetland": int((forest[s] & ~D[s] & Wt[s]).sum())}
    tot = float(np.nansum(np.where(forest[s], dmg[s], 0))); share = float(np.nansum(np.where(forest[s], dmgu[s], 0)) / tot) if tot > 0 else np.nan
    ok = (not touches_tip) and min(n.values()) >= 100
    cands.append({"r0": int(r0), "r1": int(r1), "c0": int(c0), "c1": int(c1), "upland_share": round(share, 4), "touches_tip": touches_tip,
                  "eligible": ok, **n, "northing_m": [float(G.Y1 - r1 * R), float(G.Y1 - r0 * R)], "easting_m": [float(G.X0 + c0 * R), float(G.X0 + c1 * R)]})
el = [c for c in cands if c["eligible"]]
best = sorted(el, key=lambda c: (abs(c["upland_share"] - SHARE), -c["r0"]))[0]
r0, r1, c0, c1 = best["r0"], best["r1"], best["c0"], best["c1"]
held = np.zeros_like(band); held[r0:r1, c0:c1] = True
held_ex = np.zeros_like(band); held_ex[max(0, r0 - km(2)):r1 + km(2), max(0, c0 - km(2)):c1 + km(2)] = True
train = ~held_ex & ~tip_ex
np.savez_compressed("data/regions_30.npz", heldout=held, heldout_excl=held_ex, tip=tip, tip_excl=tip_ex, train=train, band=band,
                    forest=forest, damage=D, intact=I, upland=U, wetland=Wt)
def ll(r_a, r_b, c_a, c_b):
    xs = [G.X0 + c_a * R, G.X0 + c_b * R]; ys = [G.Y1 - r_b * R, G.Y1 - r_a * R]
    lo, la = tr.transform([xs[0], xs[1], xs[0], xs[1]], [ys[0], ys[0], ys[1], ys[1]])
    return {"easting_m": xs, "northing_m": ys, "lon": [round(min(lo), 4), round(max(lo), 4)], "lat": [round(min(la), 4), round(max(la), 4)]}
out = {"grid": {"crs": f"EPSG:{G.EPSG}", "res_m": R, "origin_x": G.X0, "origin_y": G.Y1, "shape": [H3, W3]},
       "band_wide_upland_share_target": SHARE,
       "heldout": {**ll(r0, r1, c0, c1), "rows": [r0, r1], "cols": [c0, c1], "upland_share_of_damage": best["upland_share"],
                   "forest_km2": round(float(forest[held].sum()) * 9e-4, 1), "damage_km2": round(float(np.nansum(np.where(forest & held, dmg, 0))) * 9e-4, 1),
                   **{k: best[k] for k in ("dmg_upland", "intact_upland", "dmg_wetland", "nondmg_wetland")}},
       "heldout_exclusion_with_2km_buffer": ll(max(0, r0 - km(2)), r1 + km(2), max(0, c0 - km(2)), c1 + km(2)),
       "tip": {**ll(t_r0, t_r1, t_c0, t_c1), "rows": [int(t_r0), int(t_r1)], "cols": [int(t_c0), int(t_c1)], "note": "rectangle intersected with the NOAA footprint",
               "forest_km2": round(float((forest & tip).sum()) * 9e-4, 1), "damage_km2": round(float(np.nansum(np.where(forest & tip, dmg, 0))) * 9e-4, 1),
               "dmg_upland": int((D & U & tip).sum()), "intact_upland": int((I & U & tip).sum()), "dmg_wetland": int((D & Wt & tip).sum()),
               "nondmg_wetland": int((forest & ~D & Wt & tip).sum())},
       "tip_exclusion_with_2km_buffer": ll(max(0, t_r0 - km(2)), t_r1 + km(2), max(0, t_c0 - km(2)), t_c1 + km(2)),
       "train": {"forest_km2": round(float((forest & train).sum()) * 9e-4, 1), "damage_cells": int((D & train).sum()), "intact_cells": int((I & train).sum())},
       "n_candidates": len(cands), "n_eligible": len(el), "candidates": cands}
json.dump(out, open("docs/models/regions.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "candidates"}, indent=1))
fig, ax = plt.subplots(figsize=(6, 9))
ext = [G.X0 / 1e3, (G.X0 + W3 * R) / 1e3, (G.Y1 - H3 * R) / 1e3, G.Y1 / 1e3]
img = np.zeros((H3, W3, 3)) + 1; img[forest] = (0.85, 0.85, 0.85); img[band & forest] = (0.6, 0.6, 0.6)
img[train & ~forest] = img[train & ~forest]; img[held_ex & ~held] = (1, 0.85, 0.6); img[held] = np.where(img[held] < 1, img[held] * (1, 0.5, 0.5), (1, 0.7, 0.7))
img[tip_ex & ~tip] = (0.7, 0.85, 1); img[tip] = (0.3, 0.5, 1)
ax.imshow(img[::4, ::4], extent=ext, interpolation="nearest"); ax.set_xlabel("easting (km)"); ax.set_ylabel("northing (km)")
ax.set_title("Regions: grey = forest (darker = band), red = held-out block,\norange = its 2 km buffer, blue = aerial tip + buffer; rest = training", fontsize=9)
fig.savefig("docs/models/fig_regions.png", dpi=90, bbox_inches="tight")
