"""List the NISAR GCOV granules for the pipeline stacks; print sizes, _PR_ choice, and study-box coverage."""
import json, sys
import asf_search as asf
from shapely.geometry import shape, box
STUDY = box(-87.60, 30.40, -86.60, 31.80)
WANT = {("076", "A", "017"): ["2026-09-23", "2026-10-05", "2026-10-17", "2026-10-29"],
        ("055", "D", "073"): ["2026-09-22", "2026-10-04", "2026-10-16", "2026-10-28"]}
res = asf.search(dataset="NISAR", processingLevel="GCOV", intersectsWith="POINT(-87.1 31.2)",
                 start="2026-09-20T00:00:00Z", end="2026-11-01T00:00:00Z")
rows = []
for (trk, d, frm), dates in WANT.items():
    for day in dates:
        hits = [r for r in res if f"_{trk}_{d}_{frm}_" in r.properties["sceneName"]
                and r.properties["startTime"].startswith(day)]
        pr = [r for r in hits if "_PR_" in r.properties["sceneName"]]
        pick = (pr or hits or [None])[0]
        if pick is None:
            print(trk, d, frm, day, "NOT FOUND"); rows.append({"track": trk, "date": day, "found": False}); continue
        n = pick.properties["sceneName"]; g = shape(pick.geometry)
        size = pick.properties["bytes"][n + ".h5"]["bytes"]
        cov = g.intersection(STUDY).area / STUDY.area
        print(trk, d, frm, day, n, f"{size/1e9:.2f} GB", f"study-box coverage {cov:.3f}", f"({len(hits)} listed)")
        rows.append({"track": trk, "dir": d, "frame": frm, "date": day, "found": True, "name": n, "bytes": size,
                     "url": pick.properties["url"], "coverage": cov, "n_listed": len(hits)})
json.dump(rows, open("data/stack_granules.json", "w"), indent=1)
