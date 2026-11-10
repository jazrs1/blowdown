"""Six NOAA aerial chips (~150 m) over NLCD forest inside the aerial footprint, FL box:
3 at moderate S2 NDVI drop (-0.5..-0.15; stronger drops were flood water), 3 random forest pixels (seeded)."""
import os, sys, json, urllib.request; sys.path.insert(0, "scripts")
import numpy as np, ee
from shapely.geometry import shape, Point
from ee_common import FL
d = np.load("data/ee_FL.npz"); x0, y0, x1, y1 = d["extent"]; res = float(d["res"])
fp = shape(json.load(open("data/noaa_footprint_FL.geojson")))
h, w = d["dNDVI"].shape
yy, xx = np.mgrid[0:h, 0:w]; lon = x0 + (xx + .5) * res; lat = y1 - (yy + .5) * res
cand = (d["forest"] == 1) & np.isfinite(d["dNDVI"])
idx = np.flatnonzero(cand)
inside = np.array([fp.contains(Point(lon.flat[i], lat.flat[i])) for i in idx]); idx = idx[inside]
dn = d["dNDVI"].flat[idx]
mod = idx[(dn < -0.15) & (dn > -0.5)]  # moderate drop; strongest drops are flood water
order = mod[np.argsort(d["dNDVI"].flat[mod])]
col = ee.ImageCollection("projects/sat-io/open-datasets/NOAA-EMERGENCY-RESPONSE/HURRICANE_ISAIAS_2026")
import matplotlib.image as mpimg
chosen, meta = [], []
def far(i): return all(abs(lon.flat[i]-lon.flat[j]) + abs(lat.flat[i]-lat.flat[j]) > 0.01 for j in chosen)
def try_chip(kind, i, k):
    lo, la = float(lon.flat[i]), float(lat.flat[i])
    g = ee.Geometry.Point([lo, la]).buffer(75).bounds()
    tiles = col.filterBounds(g)
    url = tiles.mosaic().select(["red", "green", "blue"]).getThumbURL(
        {"region": g, "dimensions": 600, "min": 0, "max": 255, "format": "png"})
    fn = f"docs/gate/thumbs/aerial_{k}_{kind}.png"
    urllib.request.urlretrieve(url, fn)
    im = mpimg.imread(fn)
    if im.shape[-1] == 4 and (im[..., 3] > 0).mean() < 0.9:   # chip falls in an aerial gap; skip it
        os.remove(fn); return False
    m = {"file": fn, "kind": kind, "lon": round(lo, 5), "lat": round(la, 5),
         "dNDVI": round(float(d["dNDVI"].flat[i]), 3), "dVH_S1": round(float(d["dVH"].flat[i]), 2),
         "acquired": tiles.aggregate_array("acquired").distinct().getInfo()}
    meta.append(m); chosen.append(i); print(m); return True
rng = np.random.default_rng(7)
for kind, seq, n in [("ndvi_drop", order, 3), ("random_forest", rng.permutation(idx), 6)]:
    for i in seq:
        if len(meta) == n: break
        if far(i): try_chip(kind, i, len(meta) + 1)
json.dump(meta, open("docs/gate/thumbs/thumbs.json", "w"), indent=1)
