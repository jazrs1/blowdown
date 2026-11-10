"""Controls step 3/4 inputs from Earth Engine on the evaluation extent at 30 m (same origin as data/coarse_30.npz):
- hnd: MERIT Hydro v1.0.1 height above nearest drainage (m), nearest-neighbour from ~90 m
- VH_{orbit}_{date}: per-date S1 VH linear power, 2026, orbits 19 and 92 (reduceResolution mean of 10 m linear power,
  power <= 0 masked), same selection as s1_perdate.py
- S2 SCL-masked medians split at 10-29: ndvi_p1/nbr_p1 = 2026-10-11..10-29, ndvi_p2/nbr_p2 = 2026-10-30..11-10,
  n_p2 = number of clear S2 observations in the second window
Writes data/controls_ee_30.npz."""
import sys, time; sys.path.insert(0, "scripts")
import numpy as np, ee
import grid as G
from ee_common import STUDY, pull_grid, s2_ndvi_composite
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
CRS = f"EPSG:{G.EPSG}"; W3, H3 = WB // 3, HB // 3
DATES = {19: ["2026-09-28", "2026-10-22", "2026-11-03"], 92: ["2026-09-21", "2026-10-03", "2026-10-27", "2026-11-08"]}
t0 = time.time(); out = {}
hnd = ee.Image("MERIT/Hydro/v1_0_1").select("hnd").rename("hnd")
out.update(pull_grid(hnd, CRS, G.X0, G.Y1, 30, W3, H3)); print("hnd", round(float(np.isfinite(out["hnd"]).mean()), 3), round(time.time() - t0), flush=True)
for orbit, days in DATES.items():
    for d in days:
        img = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(STUDY)
               .filter(ee.Filter.eq("relativeOrbitNumber_start", orbit)).filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
               .filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")).select("VH").mosaic())
        img = img.setDefaultProjection(CRS, None, 10).updateMask(img.gt(0)).reduceResolution(ee.Reducer.mean(), False, 64).rename(f"VH_{orbit}_{d}")
        a = pull_grid(img, CRS, G.X0, G.Y1, 30, W3, H3); out.update(a)
        print(orbit, d, "valid", round(float(np.isfinite(list(a.values())[0]).mean()), 3), round(time.time() - t0), flush=True)
p1 = s2_ndvi_composite("2026-10-11", "2026-10-30", STUDY).rename(["ndvi_p1", "nbr_p1"])
p2 = s2_ndvi_composite("2026-10-30", "2026-11-11", STUDY).rename(["ndvi_p2", "nbr_p2"])
def clear(i):
    s = i.select("SCL")
    return s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11)).rename("n_p2")
n2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(STUDY).filterDate("2026-10-30", "2026-11-11").map(clear).sum()
s2 = p1.addBands(p2).addBands(n2.toFloat()).setDefaultProjection(CRS, None, 10).reduceResolution(ee.Reducer.mean(), False, 64)
out.update(pull_grid(s2, CRS, G.X0, G.Y1, 30, W3, H3)); print("s2", round(float(np.isfinite(out["ndvi_p2"]).mean()), 3), round(time.time() - t0), flush=True)
out["seconds"] = np.array(time.time() - t0)
np.savez_compressed("data/controls_ee_30.npz", **out)
