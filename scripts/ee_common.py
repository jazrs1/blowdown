import ee
ee.Initialize(project="blowdown")
AL = ee.Geometry.Rectangle([-87.35, 30.95, -86.85, 31.45])
FL = ee.Geometry.Rectangle([-87.25, 30.55, -86.95, 30.80])
BOXES = {"AL": AL, "FL": FL}

STUDY = ee.Geometry.Rectangle([-87.60, 30.40, -86.60, 31.80])
STUDY_EXT = (-87.60, 30.40, -86.60, 31.80)


def pull_grid(img, crs, x0, y1, res, w, h, tile=768, retries=4):
    """computePixels in tiles onto a north-up grid (crs units); returns dict of float32 arrays, NaN for no data."""
    import time
    import numpy as np
    img = img.unmask(-9999).toFloat()
    names = img.bandNames().getInfo()
    out = {n: np.full((h, w), np.nan, "float32") for n in names}
    for r0 in range(0, h, tile):
        for c0 in range(0, w, tile):
            th, tw = min(tile, h - r0), min(tile, w - c0)
            req = {"expression": img, "fileFormat": "NUMPY_NDARRAY",
                   "grid": {"dimensions": {"width": tw, "height": th}, "crsCode": crs,
                            "affineTransform": {"scaleX": res, "shearX": 0, "translateX": x0 + c0 * res,
                                                "shearY": 0, "scaleY": -res, "translateY": y1 - r0 * res}}}
            for k in range(retries):
                try:
                    a = ee.data.computePixels(req); break
                except Exception as e:
                    if k == retries - 1: raise
                    time.sleep(5 * (k + 1))
            for n in names:
                v = a[n].astype("float32"); v[v == -9999] = np.nan
                out[n][r0:r0 + th, c0:c0 + tw] = v
    return out


def s2_ndvi_composite(a, b, geom):
    """Cloud/shadow/water-masked median NDVI and NBR over a date window."""
    def m(i):
        s = i.select("SCL")
        ok = s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11))
        return i.normalizedDifference(["B8", "B4"]).rename("ndvi").addBands(
            i.normalizedDifference(["B8", "B12"]).rename("nbr")).updateMask(ok)
    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geom).filterDate(a, b).map(m).median()


def nlcd2025():
    return ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER") \
        .filter(ee.Filter.stringContains("system:index", "2025")).first().select("b1")
