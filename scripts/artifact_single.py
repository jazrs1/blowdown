"""Artifact check, part 2: Sentinel-2 difference from single-date scenes.
For every (date, relative orbit) in the pre and post windows, mosaic that day's tiles from that orbit and measure, over the
band box (lon -87.40..-86.80, lat 30.45..31.60): coverage (share of the box with data) and clear share (SCL clear, same mask
as the composites). Pick the orbit and the pre/post dates that maximise min(clear_pre, clear_post) among dates with coverage
>= 0.99 and clear >= 0.9. Pull NDVI and NBR for those two dates at 30 m (mean of 10 m) on the 30 m prediction grid.
Writes data/artifact/single_dates.json and data/artifact/single_ndvi_30m.npz."""
import json, sys, time; sys.path.insert(0, "scripts")
import numpy as np, ee
import grid as G
from ee_common import STUDY, pull_grid
t0 = time.time(); BOX = ee.Geometry.Rectangle([-87.40, 30.45, -86.80, 31.60])
WIN = {"pre": ("2026-09-01", "2026-10-09"), "post": ("2026-10-11", "2026-11-10")}
inv = json.load(open("data/artifact/inventory.json"))
def clear(i):
    s = i.select("SCL"); return s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11))
def day_mosaic(d, orb):
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(BOX).filterDate(d, ee.Date(d).advance(1, "day"))
            .filter(ee.Filter.eq("SENSING_ORBIT_NUMBER", orb)).mosaic())
rows = []
for w in WIN:
    for d, orb in sorted({(x["date"], x["rel_orbit"]) for x in inv["s2"][w]}):
        m = day_mosaic(d, orb); has = m.select("B4").mask().gt(0); c = clear(m).And(has)
        r = ee.Image.cat(has.rename("cov"), c.rename("clr")).reduceRegion(ee.Reducer.mean(), BOX, 200, maxPixels=1e9).getInfo()
        rows.append({"window": w, "date": d, "rel_orbit": orb, "coverage": round(r["cov"] or 0, 3), "clear": round(r["clr"] or 0, 3)})
        print(rows[-1], round(time.time() - t0), flush=True)
best = None
for orb in sorted({r["rel_orbit"] for r in rows}):
    pre = [r for r in rows if r["window"] == "pre" and r["rel_orbit"] == orb and r["coverage"] >= 0.99]
    post = [r for r in rows if r["window"] == "post" and r["rel_orbit"] == orb and r["coverage"] >= 0.99]
    if not pre or not post: continue
    a = max(pre, key=lambda r: r["clear"]); b = max(post, key=lambda r: r["clear"]); sc = min(a["clear"], b["clear"])
    if best is None or sc > best[0]: best = (sc, orb, a, b)
sc, orb, a, b = best
out = {"candidates": rows, "chosen": {"rel_orbit": orb, "pre": a, "post": b, "min_clear": sc}}
json.dump(out, open("data/artifact/single_dates.json", "w"), indent=1); print("chosen", out["chosen"], flush=True)
img = None
for tag, r in (("pre", a), ("post", b)):
    m = day_mosaic(r["date"], orb); ok = clear(m)
    nd = m.normalizedDifference(["B8", "B4"]).rename(f"ndvi_{tag}").updateMask(ok); nb = m.normalizedDifference(["B8", "B12"]).rename(f"nbr_{tag}").updateMask(ok)
    x = nd.addBands(nb); img = x if img is None else img.addBands(x)
img = img.setDefaultProjection(f"EPSG:{G.EPSG}", None, 10).reduceResolution(ee.Reducer.mean(), False, 64)
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
a_ = pull_grid(img, f"EPSG:{G.EPSG}", G.X0, G.Y1, 30, WB // 3, HB // 3)
np.savez_compressed("data/artifact/single_ndvi_30m.npz", **a_); print("done", round(time.time() - t0))
