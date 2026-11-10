"""List NISAR GCOV granules over the Alabama point for the pre/post dates."""
import asf_search as asf

res = asf.search(dataset="NISAR", processingLevel="GCOV",
                 intersectsWith="POINT(-87.1 31.2)",
                 start="2026-10-01T00:00:00Z", end="2026-10-20T00:00:00Z")
print(f"{len(res)} results")
for r in res:
    p = r.properties
    print(p.get("sceneName") or p.get("fileID"), "| track", p.get("pathNumber"),
          "| frame", p.get("frameNumber"), "|", p.get("flightDirection"),
          "| start", p.get("startTime"), "| bytes", p.get("bytes"),
          "| url", p.get("url"))
    extra = r.umm.get("RelatedUrls", []) if hasattr(r, "umm") and r.umm else []
    for u in extra:
        if u.get("Type", "").startswith("GET DATA"):
            print("    data:", u.get("URL"))
