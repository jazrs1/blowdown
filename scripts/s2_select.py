"""Rank Sentinel-2 SR dates by cloud fraction inside each box (SCL 3,8,9,10 or no data)."""
import sys, json; sys.path.insert(0, "scripts")
import ee
from ee_common import BOXES
WINDOWS = {"pre": ("2026-09-15", "2026-10-09"), "post": ("2026-10-11", "2026-11-10")}
out = {}
for name, g in BOXES.items():
    for win, (a, b) in WINDOWS.items():
        col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(g).filterDate(a, b)
        dates = col.aggregate_array("system:time_start").map(
            lambda t: ee.Date(t).format("YYYY-MM-dd")).distinct().getInfo()
        rows = []
        for d in dates:
            day = col.filterDate(d, ee.Date(d).advance(1, "day"))
            scl = day.select("SCL").mosaic()
            bad = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10)).unmask(1)  # no data counts as bad
            frac = bad.reduceRegion(ee.Reducer.mean(), g, 60, maxPixels=1e9).getInfo()
            v = list(frac.values())[0]
            tile_cc = day.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
            rows.append((d, round(100 * v, 1), [round(x, 1) for x in tile_cc]))
        rows.sort(key=lambda r: r[1])
        print(name, win, "candidates:", len(rows))
        for r in rows[:5]: print("   ", r)
        out[f"{name}_{win}"] = {"date": rows[0][0], "inbox_cloud_pct": rows[0][1], "tile_cloud_pct": rows[0][2]}
json.dump(out, open("data/s2_selection.json", "w"), indent=1)
print(json.dumps(out, indent=1))
