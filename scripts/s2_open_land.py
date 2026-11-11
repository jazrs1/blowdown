"""Why does the Sentinel-2 'before' composite look drier and browner than 'after' outside the damage band? Mean NDVI change
(after minus before) by NLCD 2025 class on the 10 m grid (every 3rd pixel each way), 2026 windows (pre 09-01..10-08, post
10-11..11-09) against the same windows in 2025 (dndvi25), from data/s2_stack.h5. Held-out block + 2 km and aerial tip + 2 km
excluded (site/data/heldout.geojson); water (MNDWI > 0) excluded. Forest is split into outside / inside the Sentinel-2 damage
mask (data/reference.h5). Writes docs/site/s2_open_land.json."""
import json, sys
import numpy as np, h5py
from pyproj import Transformer
from shapely.ops import transform  # noqa
from shapely import contains_xy
sys.path.insert(0, "scripts"); import grid as G
from heldout_mask import held_polys
S = 3
s2 = h5py.File("data/s2_stack.h5", "r"); ref = h5py.File("data/reference.h5", "r")
pre = s2["ndvi_pre"][::S, ::S]; post = s2["ndvi_post"][::S, ::S]; d25 = s2["dndvi25"][::S, ::S]; cls = s2["cls"][::S, ::S]; water = s2["water"][::S, ::S]
dmg = ref["damage"][::S, ::S].astype(bool)
X, Y = np.meshgrid(G.XC[::S], G.YC[::S])
tr = Transformer.from_crs(4326, G.EPSG, always_xy=True).transform
held = np.zeros(X.shape, bool)
for g in held_polys(): held |= contains_xy(transform(tr, g), X, Y)
d26 = post - pre
ok = np.isfinite(d26) & np.isfinite(d25) & ~held & ~(water > 0)
def stats(m):
    m = m & ok; n = int(m.sum())
    return {"n_pixels_30m": n, "km2": round(n * (S * G.RES) ** 2 / 1e6, 1), "mean_dndvi_2026": round(float(d26[m].mean()), 4), "mean_dndvi_2025": round(float(d25[m].mean()), 4),
            "median_dndvi_2026": round(float(np.median(d26[m])), 4), "share_greener_2026": round(float((d26[m] > 0).mean()), 3), "mean_ndvi_pre_2026": round(float(pre[m].mean()), 3)}
forest = np.isin(cls, (41, 42, 43, 90))
out = {"pasture_hay_81": stats(cls == 81), "cropland_82": stats(cls == 82), "open_land_81_82": stats(np.isin(cls, (81, 82))),
       "forest_outside_damage_mask": stats(forest & ~dmg), "upland_forest_41_43_outside_mask": stats(np.isin(cls, (41, 42, 43)) & ~dmg),
       "woody_wetland_90_outside_mask": stats((cls == 90) & ~dmg), "forest_inside_damage_mask": stats(forest & dmg),
       "notes": "NDVI change = after minus before median composite; 2025 = same calendar windows (no storm). Held-out block and aerial tip excluded."}
json.dump(out, open("docs/site/s2_open_land.json", "w"), indent=1); print(json.dumps(out, indent=1))
# ---- true-colour brightness of the two site composites (data/site_s2rgb_3857.npz, the cache behind s2_before/after.jpg),
# by NLCD class, sampled from the 10 m grid at each 75 m Mercator pixel centre. Held-out block and tip excluded as above.
src = open("scripts/site_layers.py").read(); i = src.index("import grid as G"); j = src.index("samp = lambda")
ns = {}; exec("import json, os, sys\nimport numpy as np, h5py\nfrom pyproj import Transformer\n" + src[i:j].replace('OUT = "site/data"; os.makedirs(OUT, exist_ok=True)', ""), ns)
UX, UY, inside, excl_ = ns["UX"], ns["UY"], ns["inside"], ns["excl"]
ci10 = np.clip(np.floor((UX - G.X0) / G.RES).astype(int), 0, G.W - 1); ri10 = np.clip(np.floor((G.Y1 - UY) / G.RES).astype(int), 0, G.H - 1)
cls10 = s2["cls"][...][ri10, ci10]; dmg10 = ref["damage"][...][ri10, ci10].astype(bool)
ex = inside & excl_[ns["ri"], ns["ci"]]
T = np.load("data/site_s2rgb_3857.npz"); rgb = {t: np.stack([T[f"r{t}"], T[f"g{t}"], T[f"b{t}"]], -1) / 10000.0 for t in "01"}
okc = inside & ~ex & np.isfinite(rgb["0"]).all(-1) & np.isfinite(rgb["1"]).all(-1)
tc = {}
for nm, m in (("open_land_81_82", np.isin(cls10, (81, 82))), ("forest_outside_damage_mask", np.isin(cls10, (41, 42, 43, 90)) & ~dmg10)):
    m = m & okc
    tc[nm] = {t_: {"mean_red": round(float(rgb[t][m, 0].mean()), 4), "mean_green": round(float(rgb[t][m, 1].mean()), 4), "mean_blue": round(float(rgb[t][m, 2].mean()), 4),
                   "red_over_green": round(float(rgb[t][m, 0].mean() / rgb[t][m, 1].mean()), 3)} for t, t_ in (("0", "before"), ("1", "after"))}
out["true_colour_reflectance"] = tc
json.dump(out, open("docs/site/s2_open_land.json", "w"), indent=1); print(json.dumps(tc, indent=1))
