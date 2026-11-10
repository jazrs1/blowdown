"""Sensitivity: per-date S1 VH (2026, orbits 19 and 92) at 100 m (EE reduceResolution mean of linear power) on the
evaluation 100 m grid (same origin as data/coarse_100.npz). Writes data/s1_perdate_100.npz (one array per date)."""
import sys; sys.path.insert(0, "scripts")
import numpy as np, ee
import grid as G
from ee_common import STUDY, pull_grid
DATES = {19: ["2026-09-28", "2026-10-22", "2026-11-03"], 92: ["2026-09-21", "2026-10-03", "2026-10-27", "2026-11-08"]}
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
out = {}
for orbit, days in DATES.items():
    for d in days:
        img = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(STUDY)
               .filter(ee.Filter.eq("relativeOrbitNumber_start", orbit)).filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
               .filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")).select("VH").mosaic())
        img = img.setDefaultProjection(f"EPSG:{G.EPSG}", None, 10).updateMask(img.gt(0)).reduceResolution(ee.Reducer.mean(), False, 256).rename(f"VH_{orbit}_{d}")
        a = pull_grid(img, f"EPSG:{G.EPSG}", G.X0, G.Y1, 100, WB // 10, HB // 10)
        out.update(a); v = list(a.values())[0]; print(orbit, d, "valid", round(float(np.isfinite(v).mean()), 3), flush=True)
np.savez_compressed("data/s1_perdate_100.npz", **out)
