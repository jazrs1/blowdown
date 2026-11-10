import sys; sys.path.insert(0, "scripts")
import ee
from ee_common import FL
aid = "projects/sat-io/open-datasets/NOAA-EMERGENCY-RESPONSE/HURRICANE_ISAIAS_2026"
try:
    a = ee.data.getAsset(aid); print("type:", a.get("type"), "| props:", {k: a[k] for k in a if k not in ("bands",)})
except Exception as e:
    print("getAsset error:", e)
    parent = aid.rsplit("/", 1)[0]
    try:
        kids = ee.data.listAssets({"parent": parent}).get("assets", [])
        print("siblings matching ISAIAS/2026:", [k["name"] for k in kids if "ISAIAS" in k["name"].upper() or "2026" in k["name"]])
    except Exception as e2: print("listAssets error:", e2)
nl = ee.data.listAssets({"parent": "projects/sat-io/open-datasets"}) if False else None
for cand in ["USGS/NLCD_RELEASES/2021_REL/NLCD", "projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER", "USGS/NLCD_RELEASES/2019_REL/NLCD"]:
    try:
        c = ee.ImageCollection(cand); print(cand, "n=", c.size().getInfo(), "latest:", c.aggregate_max("system:time_start").getInfo() and ee.Date(c.aggregate_max("system:time_start")).format("YYYY").getInfo())
    except Exception as e: print(cand, "error:", str(e)[:150])
