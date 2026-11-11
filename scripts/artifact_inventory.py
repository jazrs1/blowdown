"""Artifact check, part 1: what went into the composites, and where.
- Sentinel-2 SR harmonized scenes in the pre (2026-09-01..10-08) and post (2026-10-11..11-09) composite windows over the
  study area: footprint, date, MGRS tile, relative orbit (SENSING_ORBIT_NUMBER), cloudy-pixel percentage.
- Sentinel-1 GRD scenes used (orbits 19 and 92, ascending, IW, the pipeline dates): footprint, date, product id.
- NISAR GCOV frames (track 76 frame 17, track 55 frame 73): footprints from ASF.
- Per-pixel composite statistics on a 200 m version of the study grid: number of clear S2 observations, mean acquisition
  day and the min/max relative orbit among clear observations, for each window (same SCL clear mask as the composites).
Writes data/artifact/inventory.json and data/artifact/composite_stats_200m.npz."""
import json, os, sys, time; sys.path.insert(0, "scripts")
import numpy as np, ee
import grid as G
from ee_common import STUDY, pull_grid
os.makedirs("data/artifact", exist_ok=True); t0 = time.time()
WIN = {"pre": ("2026-09-01", "2026-10-09"), "post": ("2026-10-11", "2026-11-10")}
out = {"s2": {}, "s1": [], "nisar": []}
def clear(i):
    s = i.select("SCL"); return s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11))
for w, (a, b) in WIN.items():
    col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(STUDY).filterDate(a, b)
    fc = col.map(lambda i: ee.Feature(i.geometry(), {"id": i.get("system:index"), "date": i.date().format("YYYY-MM-dd"), "tile": i.get("MGRS_TILE"),
                                                      "rel_orbit": i.get("SENSING_ORBIT_NUMBER"), "cloud_pct": i.get("CLOUDY_PIXEL_PERCENTAGE")}))
    info = fc.getInfo()
    out["s2"][w] = [{**f["properties"], "footprint": f["geometry"]} for f in info["features"]]
    print("s2", w, len(out["s2"][w]), round(time.time() - t0), flush=True)
DATES = {19: ["2026-09-28", "2026-10-22", "2026-11-03"], 92: ["2026-09-21", "2026-10-03", "2026-10-27", "2026-11-08"]}
for o, ds in DATES.items():
    for d in ds:
        col = (ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(STUDY).filter(ee.Filter.eq("relativeOrbitNumber_start", o))
               .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING")).filter(ee.Filter.eq("instrumentMode", "IW")).filterDate(d, ee.Date(d).advance(1, "day")))
        info = col.map(lambda i: ee.Feature(i.geometry(), {"id": i.get("system:index"), "date": i.date().format("YYYY-MM-dd HH:mm")})).getInfo()
        out["s1"] += [{"orbit": o, **f["properties"], "footprint": f["geometry"]} for f in info["features"]]
print("s1", len(out["s1"]), round(time.time() - t0), flush=True)
import asf_search as asf
names = [g["name"] for g in json.load(open("data/stack_granules.json")) if g.get("found")]
for r in asf.granule_search(names):
    n = r.properties["sceneName"]
    if n in names: out["nisar"].append({"name": n, "track": n.split("_")[5], "frame": n.split("_")[7], "date": r.properties["startTime"][:10], "footprint": r.geometry})
print("nisar", len(out["nisar"]), round(time.time() - t0), flush=True)
json.dump(out, open("data/artifact/inventory.json", "w"))
# per-pixel composite statistics, 200 m
R = 200; W2, H2 = int(np.ceil(G.W * 10 / R)), int(np.ceil(G.H * 10 / R)); stats = {}
for w, (a, b) in WIN.items():
    col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(STUDY).filterDate(a, b)
    def per(i):
        c = clear(i); doy = ee.Image.constant(i.date().getRelative("day", "year")).toFloat(); orb = ee.Image.constant(ee.Number(i.get("SENSING_ORBIT_NUMBER"))).toFloat()
        return doy.rename("doy").addBands(orb.rename("orb")).updateMask(c)
    pc = col.map(per)
    img = (pc.select("doy").count().rename(f"{w}_n").toFloat().addBands(pc.select("doy").mean().rename(f"{w}_doy_mean"))
           .addBands(pc.select("doy").reduce(ee.Reducer.median()).rename(f"{w}_doy_median"))
           .addBands(pc.select("orb").min().rename(f"{w}_orb_min")).addBands(pc.select("orb").max().rename(f"{w}_orb_max")))
    img = img.setDefaultProjection(f"EPSG:{G.EPSG}", None, 20)
    stats.update(pull_grid(img, f"EPSG:{G.EPSG}", G.X0, G.Y1, R, W2, H2))
    print("stats", w, round(time.time() - t0), flush=True)
np.savez_compressed("data/artifact/composite_stats_200m.npz", res=R, **stats)
print("done", round(time.time() - t0))
