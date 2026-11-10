"""List S1 GRD scenes per requested date for rel. orbits 19 and 92 (ascending): platform, mode, pols, study-box coverage.
Also list what exists in the same weeks of 2025 (control)."""
import sys, json; sys.path.insert(0, "scripts")
import ee
from ee_common import STUDY
DATES = {"pre": ["2026-09-21", "2026-09-28", "2026-10-03"], "post": ["2026-10-22", "2026-10-27", "2026-11-03", "2026-11-08"]}
def info(orbit, a, b):
    col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(STUDY).filter(ee.Filter.eq("relativeOrbitNumber_start", orbit))
           .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING")).filterDate(a, b))
    feats = col.map(lambda i: ee.Feature(None, {"id": i.get("system:index"), "plat": i.get("platform_number"),
        "mode": i.get("instrumentMode"), "pol": i.get("transmitterReceiverPolarisation"),
        "day": i.date().format("YYYY-MM-dd")})).getInfo()["features"]
    cov = col.filter(ee.Filter.eq("instrumentMode", "IW")).geometry().dissolve(1000).intersection(STUDY, 1000).area(1000).divide(STUDY.area(1000)).getInfo() if feats else 0
    return [f["properties"] for f in feats], cov
out = {}
for orbit in (19, 92):
    for phase, days in DATES.items():
        for d in days:
            e = ee.Date(d); f, cov = info(orbit, e.advance(-1, "day"), e.advance(1, "day"))
            modes = sorted({(x["plat"], x["mode"], x["day"]) for x in f})
            print(orbit, phase, d, "n", len(f), modes, "IW study cov %.3f" % cov)
            out[f"{orbit}_{d}"] = {"scenes": f, "iw_cov": cov}
    for phase, (a, b) in {"pre2025": ("2025-09-17", "2025-10-08"), "post2025": ("2025-10-19", "2025-11-12")}.items():
        f, cov = info(orbit, a, b)
        print(orbit, phase, sorted({(x["plat"], x["mode"], x["day"]) for x in f}), "IW cov %.3f" % cov)
        out[f"{orbit}_{phase}"] = {"scenes": f, "iw_cov": cov}
json.dump(out, open("data/s1_stack_check.json", "w"), indent=1)
