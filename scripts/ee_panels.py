"""Pull S1 VV/VH dB differences, S2 NDVI difference and NLCD forest onto a common EPSG:4326 grid per box."""
import sys, json; sys.path.insert(0, "scripts")
import numpy as np, ee
from ee_common import BOXES
EXT = {"AL": (-87.35, 30.95, -86.85, 31.45), "FL": (-87.25, 30.55, -86.95, 30.80)}
RES = 0.0008  # degrees (~77 m E-W, ~89 m N-S)
S2SEL = json.load(open("data/s2_selection.json"))

def s1(day):
    d = ee.Date(day)
    col = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filter(ee.Filter.eq("relativeOrbitNumber_start", 19))
           .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING")).filter(ee.Filter.eq("instrumentMode", "IW"))
           .filterDate(d.advance(-1, "day"), d.advance(1, "day")).select(["VV", "VH"]))
    lin = col.mosaic().focalMean(30, "circle", "meters")      # light speckle smoothing in linear power
    return lin.log10().multiply(10)

def s2_ndvi(day, g):
    col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(g).filterDate(day, ee.Date(day).advance(1, "day"))
    m = col.mosaic(); scl = m.select("SCL")
    ok = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(0))
    return m.normalizedDifference(["B8", "B4"]).updateMask(ok)

nlcd = ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER") \
    .filter(ee.Filter.stringContains("system:index", "2025")).first().select("b1")
forest = nlcd.eq(41).Or(nlcd.eq(42)).Or(nlcd.eq(43)).Or(nlcd.eq(90)).rename("forest")

for name, g in BOXES.items():
    x0, y0, x1, y1 = EXT[name]
    w, h = round((x1 - x0) / RES), round((y1 - y0) / RES)
    dS1 = s1("2026-10-22").subtract(s1("2026-09-28")).rename(["dVV", "dVH"])
    dN = s2_ndvi(S2SEL[f"{name}_post"]["date"], g).subtract(s2_ndvi(S2SEL[f"{name}_pre"]["date"], g)).rename("dNDVI")
    img = dS1.addBands(dN).addBands(forest.reduceResolution(ee.Reducer.mode(), maxPixels=100).toFloat()).unmask(-9999).toFloat()
    arr = ee.data.computePixels({
        "expression": img, "fileFormat": "NUMPY_NDARRAY",
        "grid": {"dimensions": {"width": w, "height": h}, "crsCode": "EPSG:4326",
                 "affineTransform": {"scaleX": RES, "shearX": 0, "translateX": x0,
                                     "shearY": 0, "scaleY": -RES, "translateY": y1}}})
    out = {k: np.where(arr[k] == -9999, np.nan, arr[k]).astype("float32") for k in arr.dtype.names}
    np.savez_compressed(f"data/ee_{name}.npz", extent=np.array(EXT[name]), res=RES, **out)
    print(name, (h, w), {k: (float(np.nanmedian(v)), float(np.mean(np.isfinite(v)))) for k, v in out.items()})
