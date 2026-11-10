"""NOAA aerial footprint over the study box (dissolved) and per-cell forest area inside it on the 0.0008 deg grid."""
import sys, json; sys.path.insert(0, "scripts")
import numpy as np, ee
from ee_common import STUDY, STUDY_EXT, pull_grid, nlcd2025
RES = 0.0008; x0, y0, x1, y1 = STUDY_EXT; w, h = round((x1 - x0) / RES), round((y1 - y0) / RES)
col = ee.ImageCollection("projects/sat-io/open-datasets/NOAA-EMERGENCY-RESPONSE/HURRICANE_ISAIAS_2026").filterBounds(STUDY)
n = col.size().getInfo()
fp = col.geometry().dissolve(20).intersection(STUDY, 20)
fpinfo = fp.getInfo(); json.dump(fpinfo, open("data/noaa_footprint_study.geojson", "w"))
fp_km2 = fp.area(20).divide(1e6).getInfo()
c = nlcd2025(); forest = c.eq(41).Or(c.eq(42)).Or(c.eq(43)).Or(c.eq(90))
inside = ee.Image(0).paint(ee.FeatureCollection([ee.Feature(fp)]), 1)
# per-cell fractions (mean of 30 m indicators), times analytic cell area; reduceResolution(sum) returned single pixels
img = (forest.multiply(inside).rename("forest_noaa").addBands(forest.rename("forest")).addBands(inside.rename("noaa"))
       .toFloat().reproject(c.projection()).reduceResolution(ee.Reducer.mean(), maxPixels=200))
frac = pull_grid(img, "EPSG:4326", x0, y1, RES, w, h, tile=625)
lat = y1 - (np.arange(h) + .5) * RES
cell = (RES * 111.32 * np.cos(np.radians(lat)) * RES * 110.6)[:, None]  # km2
out = {k + "_km2": (v * cell).astype("float32") for k, v in frac.items()}
np.savez_compressed("data/extent_noaa.npz", **out)
print(json.dumps({"tiles_in_study": n, "footprint_km2": fp_km2,
                  "grid_noaa_km2": float(np.nansum(out["noaa_km2"])), "grid_forest_noaa_km2": float(np.nansum(out["forest_noaa_km2"]))}, indent=1))
