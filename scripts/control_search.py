"""List NISAR GCOV granules for the no-storm controls (track 76 frame 17 only; track 55 has no 2025 data before 11-26):
2025-10-22 -> 2025-11-03 (same season as the 2026 posts, a year earlier) and 2026-09-11 -> 2026-09-23 (both pre-storm;
09-23 is already extracted in data/stack). Writes data/control_granules.json in the stack_granules.json format."""
import json
import asf_search as asf
from shapely.geometry import shape, box
STUDY = box(-87.60, 30.40, -86.60, 31.80)
DATES = ["2025-10-22", "2025-11-03", "2026-09-11"]
res = asf.search(dataset="NISAR", processingLevel="GCOV", intersectsWith="POINT(-87.1 31.2)",
                 start="2025-10-01T00:00:00Z", end="2026-09-20T00:00:00Z")
rows = []
for day in DATES:
    hits = [r for r in res if "_076_A_017_" in r.properties["sceneName"] and r.properties["startTime"].startswith(day)]
    pr = [r for r in hits if "_PR_" in r.properties["sceneName"]]
    pick = (pr or hits or [None])[0]
    if pick is None:
        print("076", day, "NOT FOUND", [r.properties["sceneName"] for r in res if "_076_" in r.properties["sceneName"]][:5])
        rows.append({"track": "076", "date": day, "found": False}); continue
    n = pick.properties["sceneName"]; size = pick.properties["bytes"][n + ".h5"]["bytes"]
    cov = shape(pick.geometry).intersection(STUDY).area / STUDY.area
    print("076", day, n, f"{size/1e9:.2f} GB", f"coverage {cov:.3f}", f"({len(hits)} listed: {[h.properties['sceneName'][-30:] for h in hits]})")
    rows.append({"track": "076", "dir": "A", "frame": "017", "date": day, "found": True, "name": n, "bytes": size,
                 "url": pick.properties["url"], "coverage": cov, "n_listed": len(hits)})
json.dump(rows, open("data/control_granules.json", "w"), indent=1)
