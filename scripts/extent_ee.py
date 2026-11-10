"""Step 1 EE side: S2 dNDVI 2026, 2025 and anomaly (median composites), NLCD class, on the 0.0008 deg grid over the study box."""
import sys; sys.path.insert(0, "scripts")
import numpy as np, ee
from ee_common import STUDY, STUDY_EXT, pull_grid, s2_ndvi_composite, nlcd2025
RES = 0.0008
x0, y0, x1, y1 = STUDY_EXT
w, h = round((x1 - x0) / RES), round((y1 - y0) / RES)
def d(year):
    pre = s2_ndvi_composite(f"{year}-09-01", f"{year}-10-09", STUDY).select("ndvi")
    post = s2_ndvi_composite(f"{year}-10-11", f"{year}-11-10", STUDY).select("ndvi")
    return post.subtract(pre)
img = (d(2026).rename("dNDVI26").addBands(d(2025).rename("dNDVI25"))
       .addBands(nlcd2025().reduceResolution(ee.Reducer.mode(), maxPixels=100).rename("cls")))
out = pull_grid(img, "EPSG:4326", x0, y1, RES, w, h, tile=625)
out["anom"] = out["dNDVI26"] - out["dNDVI25"]
np.savez_compressed("data/extent_ee.npz", extent=np.array(STUDY_EXT), res=RES, **out)
print({k: (v.shape, float(np.mean(np.isfinite(v)))) for k, v in out.items()})
