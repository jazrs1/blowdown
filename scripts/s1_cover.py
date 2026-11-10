"""Fraction of each box covered by orbit-19 ascending S1 scenes (and neighbouring slices) per date."""
import sys; sys.path.insert(0, "scripts")
import ee
from ee_common import BOXES
for day in ["2026-09-28", "2026-10-22"]:
    d = ee.Date(day)
    for name, g in BOXES.items():
        col = (ee.ImageCollection("COPERNICUS/S1_GRD").filter(ee.Filter.eq("relativeOrbitNumber_start", 19))
               .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
               .filterDate(d.advance(-1, "day"), d.advance(1, "day")))
        ids = col.aggregate_array("system:index").getInfo()
        union = col.geometry().dissolve(100)
        frac = union.intersection(g, 100).area(100).divide(g.area(100)).getInfo()
        # valid-data coverage of VH mosaic
        vh = col.select("VH").mosaic().mask().reduceRegion(ee.Reducer.mean(), g, 100).get("VH").getInfo()
        print(day, name, "scenes:", ids, "footprint frac: %.3f" % frac, "valid VH frac: %.3f" % vh)
