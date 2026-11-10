"""Models step 2 input: per-date S1 VV linear power at 30 m for the October-only dates (same selection and grid as
controls_ee.py, which already holds VH). Writes data/s1_vv_30.npz."""
import sys, time; sys.path.insert(0, "scripts")
import numpy as np, ee
import grid as G
from ee_common import STUDY, pull_grid
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300; CRS = f"EPSG:{G.EPSG}"
DATES = {19: ["2026-09-28", "2026-10-22"], 92: ["2026-09-21", "2026-10-03", "2026-10-27"]}
t0 = time.time(); out = {}
for orbit, days in DATES.items():
    for d in days:
        img = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(STUDY)
               .filter(ee.Filter.eq("relativeOrbitNumber_start", orbit)).filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
               .filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")).select("VV").mosaic())
        img = img.setDefaultProjection(CRS, None, 10).updateMask(img.gt(0)).reduceResolution(ee.Reducer.mean(), False, 64).rename(f"VV_{orbit}_{d}")
        a = pull_grid(img, CRS, G.X0, G.Y1, 30, WB // 3, HB // 3); out.update(a)
        print(orbit, d, "valid", round(float(np.isfinite(list(a.values())[0]).mean()), 3), round(time.time() - t0), flush=True)
np.savez_compressed("data/s1_vv_30.npz", **out)
