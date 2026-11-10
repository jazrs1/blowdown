"""Step 3: per relative orbit, mean linear VV/VH of the pre and post dates (S1_GRD_FLOAT, IW, ascending), pulled onto the
common 10 m UTM grid in tiles and written to data/s1/<orbit>_<year>.h5. No spatial smoothing (same as NISAR stacks).
Usage: s1_stack.py 2026|2025 [test]"""
import json, os, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, ee
import grid as G
from ee_common import STUDY
YEAR = sys.argv[1]; TEST = len(sys.argv) > 2
DATES = {"2026": {19: (["2026-09-28"], ["2026-10-22", "2026-11-03"]),
                  92: (["2026-09-21", "2026-10-03"], ["2026-10-27", "2026-11-08"])},
         "2025": {19: (["2025-09-26"], ["2025-10-20", "2025-11-01"]),
                  92: (["2025-09-19", "2025-10-01"], ["2025-10-25", "2025-11-06"])}}[YEAR]
TILE = 1536
os.makedirs("data/s1", exist_ok=True)

def mean_img(orbit, days):
    cols = [ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(STUDY)
            .filter(ee.Filter.eq("relativeOrbitNumber_start", orbit)).filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
            .filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")).select(["VV", "VH"]).mosaic()
            for d in days]
    return ee.ImageCollection(cols).mean()   # per-pixel mean over dates where present (linear power)

for orbit, (pre, post) in DATES.items():
    img = (mean_img(orbit, pre).rename(["VV_pre", "VH_pre"]).addBands(mean_img(orbit, post).rename(["VV_post", "VH_post"]))
           .unmask(-9999).toFloat())
    path = f"data/s1/{orbit}_{YEAR}{'_test' if TEST else ''}.h5"
    t0 = time.time()
    with h5py.File(path, "a") as o:
        names = ["VV_pre", "VH_pre", "VV_post", "VH_post"]
        for n in names:
            if n not in o: o.create_dataset(n, (G.H, G.W), "float32", chunks=(512, 512), compression="lzf", shuffle=True, fillvalue=np.nan)
        done = set(json.loads(o.attrs.get("tiles_done", "[]")))
        o.attrs.update({"orbit": orbit, "pre": json.dumps(pre), "post": json.dumps(post)})
        tiles = [(r, c) for r in range(0, G.H, TILE) for c in range(0, G.W, TILE)]
        if TEST: tiles = [(6 * TILE, 3 * TILE)]
        for (r, c) in tiles:
            if f"{r}_{c}" in done: continue
            th, tw = min(TILE, G.H - r), min(TILE, G.W - c)
            req = {"expression": img, "fileFormat": "NUMPY_NDARRAY",
                   "grid": {"dimensions": {"width": tw, "height": th}, "crsCode": f"EPSG:{G.EPSG}",
                            "affineTransform": {"scaleX": G.RES, "shearX": 0, "translateX": G.X0 + c * G.RES,
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
    print(orbit, YEAR, "tiles", len(done), "s", round(time.time() - t0, 1), flush=True)
