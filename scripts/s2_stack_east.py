"""East box (lon -86.60..-85.80): same S2 composites as s2_stack.py on an east 10 m grid that continues the study grid's lattice
(x from grid.X0 + grid.W*10 = 538,430 m to 616,130 m, 7,770 columns; y from grid.Y1, 15,300 rows), EPSG:32616.
Original docstring: Step 4 inputs: S2 cloud-free median composites on the common 10 m grid.
Bands: ndvi_pre, ndvi_post, nbr_pre, nbr_post (2026 09-01..10-08 / 10-11..11-09), ndvi_early (2026-08-01..09-10),
dndvi25 (same windows 2025), cls (NLCD 2025), water (MNDWI>0 in post composite).  Usage: s2_stack.py [test]"""
import json, os, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, ee
import grid as G
XE0 = G.X0 + G.W * 10; WE, HE = 7770, 15300
from ee_common import s2_ndvi_composite, nlcd2025
EAST = ee.Geometry.Rectangle([-86.62, 30.38, -85.78, 31.82])
TEST = len(sys.argv) > 1; TILE = 1024
pre = s2_ndvi_composite("2026-09-01", "2026-10-09", EAST); post = s2_ndvi_composite("2026-10-11", "2026-11-10", EAST)
early = s2_ndvi_composite("2026-08-01", "2026-09-11", EAST).select("ndvi")
d25 = s2_ndvi_composite("2025-10-11", "2025-11-10", EAST).select("ndvi").subtract(s2_ndvi_composite("2025-09-01", "2025-10-09", EAST).select("ndvi"))
def mndwi(i): return i.normalizedDifference(["B3", "B11"])
postcol = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(EAST).filterDate("2026-10-11", "2026-11-10") \
    .map(lambda i: mndwi(i).updateMask(i.select("SCL").neq(8).And(i.select("SCL").neq(9)).And(i.select("SCL").neq(3)))).median()
img = (pre.select(["ndvi", "nbr"], ["ndvi_pre", "nbr_pre"]).addBands(post.select(["ndvi", "nbr"], ["ndvi_post", "nbr_post"]))
       .addBands(early.rename("ndvi_early")).addBands(d25.rename("dndvi25")).addBands(nlcd2025().rename("cls").toFloat())
       .addBands(postcol.gt(0).rename("water").toFloat()).unmask(-9999).toFloat())
names = ["ndvi_pre", "ndvi_post", "nbr_pre", "nbr_post", "ndvi_early", "dndvi25", "cls", "water"]
path = "data/east/s2_stack_east" + ("_test" if TEST else "") + ".h5"; t0 = time.time()
with h5py.File(path, "a") as o:
    for n in names:
        if n not in o: o.create_dataset(n, (HE, WE), "float32", chunks=(512, 512), compression="lzf", shuffle=True, fillvalue=np.nan)
    done = set(json.loads(o.attrs.get("tiles_done", "[]")))
    tiles = [(r, c) for r in range(0, HE, TILE) for c in range(0, WE, TILE)]
    if TEST: tiles = [(9 * TILE, 4 * TILE)]
    for r, c in tiles:
        if f"{r}_{c}" in done: continue
        th, tw = min(TILE, HE - r), min(TILE, WE - c)
        req = {"expression": img, "fileFormat": "NUMPY_NDARRAY",
               "grid": {"dimensions": {"width": tw, "height": th}, "crsCode": f"EPSG:{G.EPSG}",
                        "affineTransform": {"scaleX": G.RES, "shearX": 0, "translateX": XE0 + c * G.RES,
                                            "shearY": 0, "scaleY": -G.RES, "translateY": G.Y1 - r * G.RES}}}
        for k in range(5):
            try: a = ee.data.computePixels(req); break
            except Exception as e:
                if k == 4: raise
                print("retry", r, c, str(e)[:120], flush=True); time.sleep(10 * (k + 1))
        for n in names:
            v = a[n].astype("float32"); v[v == -9999] = np.nan; o[n][r:r + th, c:c + tw] = v
        done.add(f"{r}_{c}"); o.attrs["tiles_done"] = json.dumps(sorted(done))
    o.attrs["seconds"] = o.attrs.get("seconds", 0) + time.time() - t0
print("s2 tiles", len(done), "s", round(time.time() - t0, 1))
