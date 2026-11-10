"""Step 4: provisional optical damage reference on the 10 m grid (NOT final truth).
damage  = forest & ~water & ~clearcut & dNBR < T_NBR_D & NDVI anomaly (2026 change - 2025 change) < T_AN_D
intact  = forest & ~water & ~clearcut & dNBR > T_NBR_I & NDVI anomaly > T_AN_I
clearcut/salvage flag (excluded from both):
  a) loss before the storm: pre NDVI < 0.45 in NLCD forest (already open), or early-Aug/Sep NDVI - pre NDVI > 0.15
  b) near-total loss (post NDVI < 0.35 and dNDVI < -0.30) in 8-connected patches >= 0.5 ha whose bounding-box fill >= 0.6
Writes data/reference.h5 and docs/pipeline/reference.json."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy import ndimage
import grid as G
T_NBR_D, T_AN_D, T_NBR_I, T_AN_I = -0.10, -0.06, -0.03, -0.02
f = h5py.File("data/s2_stack.h5", "r"); BLK = 1024
near = np.zeros((G.H, G.W), bool); preloss = np.zeros((G.H, G.W), bool)
for r in range(0, G.H, BLK):
    s = slice(r, min(r + BLK, G.H)); forest = np.isin(f["cls"][s], (41, 42, 43, 90))
    npre, npost, nearly = f["ndvi_pre"][s], f["ndvi_post"][s], f["ndvi_early"][s]
    with np.errstate(invalid="ignore"):
        near[s] = forest & (npost < 0.35) & (npost - npre < -0.30)
        preloss[s] = forest & ((npre < 0.45) | (nearly - npre > 0.15))
lab, n = ndimage.label(near, structure=np.ones((3, 3)))
sizes = np.bincount(lab.ravel()); objs = ndimage.find_objects(lab)
fill = np.zeros(n + 1)
for i, sl in enumerate(objs, 1):
    if sl is not None: fill[i] = sizes[i] / ((sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start))
rect_ok = (sizes >= 50) & (fill >= 0.6); rect_ok[0] = False
rect = rect_ok[lab]; del lab
stats = {"thresholds": {"dNBR_damage": T_NBR_D, "anom_damage": T_AN_D, "dNBR_intact": T_NBR_I, "anom_intact": T_AN_I},
         "near_total_patches": int(n), "rectangular_patches": int(rect_ok.sum())}
o = h5py.File("data/reference.h5", "w")
mk = lambda name: o.create_dataset(name, (G.H, G.W), "uint8", chunks=(512, 512), compression="lzf")
D, I, C, FT = mk("damage"), mk("intact"), mk("clearcut"), mk("ftype")   # ftype: 1 evergreen(42) 2 deciduous(41) 3 mixed(43) 4 woody wetland(90)
cnt = {k: 0 for k in ("forest", "damage", "intact", "clearcut", "preloss", "rect", "water_in_forest")}
by_type = {t: {"forest": 0, "damage": 0, "intact": 0} for t in (1, 2, 3, 4)}
for r in range(0, G.H, BLK):
    s = slice(r, min(r + BLK, G.H)); cls = f["cls"][s]; forest = np.isin(cls, (41, 42, 43, 90))
    with np.errstate(invalid="ignore"):
        dn = f["ndvi_post"][s] - f["ndvi_pre"][s]; dnbr = f["nbr_post"][s] - f["nbr_pre"][s]; an = dn - f["dndvi25"][s]
        water = (f["water"][s] == 1) | (f["ndvi_post"][s] < 0.1)
    cc = (preloss[s] | rect[s]) & forest
    base = forest & ~water & ~cc & np.isfinite(dnbr) & np.isfinite(an)
    dmg = base & (dnbr < T_NBR_D) & (an < T_AN_D); itc = base & (dnbr > T_NBR_I) & (an > T_AN_I)
    ft = np.select([cls == 42, cls == 41, cls == 43, cls == 90], [1, 2, 3, 4], 0).astype("uint8")
    D[s], I[s], C[s], FT[s] = dmg, itc, cc, ft
    for k, v in (("forest", forest), ("damage", dmg), ("intact", itc), ("clearcut", cc), ("preloss", preloss[s] & forest),
                 ("rect", rect[s] & forest), ("water_in_forest", water & forest)):
        cnt[k] += int(v.sum())
    for t in by_type:
        m = ft == t; by_type[t]["forest"] += int(m.sum()); by_type[t]["damage"] += int((m & dmg).sum()); by_type[t]["intact"] += int((m & itc).sum())
km2 = lambda px: round(px * 100 / 1e6, 1)
stats["km2"] = {k: km2(v) for k, v in cnt.items()}
stats["km2_by_type"] = {{1: "evergreen", 2: "deciduous", 3: "mixed", 4: "woody_wetland"}[t]: {k: km2(v) for k, v in d.items()} for t, d in by_type.items()}
band = np.load("data/extent_band.npy")  # 0.0008 deg grid; fraction of damage inside step-1 band computed in evaluate.py
json.dump(stats, open("docs/pipeline/reference.json", "w"), indent=1); print(json.dumps(stats, indent=1))
