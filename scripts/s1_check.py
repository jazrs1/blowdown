"""List Sentinel-1 GRD scenes on relative orbit 19 ascending near the chosen dates."""
import sys; sys.path.insert(0, "scripts")
import ee
from ee_common import BOXES
for day in ["2026-09-28", "2026-10-10", "2026-10-22"]:
    d = ee.Date(day)
    for name, g in BOXES.items():
        col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(g)
               .filterDate(d.advance(-1, "day"), d.advance(1, "day")))
        info = col.map(lambda i: ee.Feature(None, {
            "id": i.get("system:index"), "plat": i.get("platform_number"),
            "orbit": i.get("relativeOrbitNumber_start"), "pass": i.get("orbitProperties_pass"),
            "pol": i.get("transmitterReceiverPolarisation"), "mode": i.get("instrumentMode"),
            "covers": i.geometry().contains(g, 100)})).getInfo()["features"]
        print(day, name, len(info))
        for f in info: print("   ", f["properties"])
# what platforms exist at all since mid-2026
recent = ee.ImageCollection("COPERNICUS/S1_GRD").filterDate("2026-06-01", "2026-11-10").filterBounds(BOXES["AL"])
print("platforms over AL since Jun 2026:", recent.aggregate_histogram("platform_number").getInfo())
print("orbits over AL since Jun 2026:", recent.aggregate_histogram("relativeOrbitNumber_start").getInfo())
