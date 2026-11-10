"""NOAA aerial footprint, NLCD-2025 forest area inside it within the FL box."""
import sys, json; sys.path.insert(0, "scripts")
import ee
from ee_common import FL
c = ee.ImageCollection("projects/sat-io/open-datasets/NOAA-EMERGENCY-RESPONSE/HURRICANE_ISAIAS_2026")
bounds_all = c.geometry().bounds(1000).getInfo()["coordinates"][0]
xs = [p[0] for p in bounds_all]; ys = [p[1] for p in bounds_all]
cfl = c.filterBounds(FL)
fp = cfl.geometry().dissolve(10).intersection(FL, 10)
fp_km2 = fp.area(10).divide(1e6).getInfo()
nlcd = ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER") \
    .filter(ee.Filter.stringContains("system:index", "2025")).first().select("b1")
forest = nlcd.eq(41).Or(nlcd.eq(42)).Or(nlcd.eq(43)).Or(nlcd.eq(90))
def km2(geom):
    return ee.Number(ee.Image.pixelArea().updateMask(forest).reduceRegion(
        ee.Reducer.sum(), geom, 30, maxPixels=1e10).get("area")).divide(1e6).getInfo()
res = {
    "collection_images": c.size().getInfo(), "images_in_FL_box": cfl.size().getInfo(),
    "bounds_all_lonlat": [min(xs), min(ys), max(xs), max(ys)],
    "dates": c.aggregate_array("system:time_start").map(lambda t: ee.Date(t).format("YYYY-MM-dd")).distinct().getInfo(),
    "FL_box_km2": FL.area(10).divide(1e6).getInfo(),
    "footprint_in_FL_box_km2": fp_km2,
    "forest_in_FL_box_km2": km2(FL),
    "forest_in_footprint_in_FL_box_km2": km2(fp),
    "nlcd": "Annual NLCD 2025 (Annual_NLCD_LndCov_2025_CU_C1V2), classes 41,42,43,90",
}
print(json.dumps(res, indent=1)); json.dump(res, open("data/noaa_forest.json", "w"), indent=1)
json.dump(fp.getInfo(), open("data/noaa_footprint_FL.geojson", "w"))
