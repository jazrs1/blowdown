"""Build the site's basemap style: OpenFreeMap 'Positron' (https://tiles.openfreemap.org/styles/positron), muted, hosted with
the site as site/data/basemap_style.json (OpenFreeMap: custom styles must be self-hosted; tiles, fonts and sprites still come
from tiles.openfreemap.org).
Changes: park, landuse and landcover layers removed (OSM land use is mapped far more densely in Florida than in Alabama and drew a
shade change along the state line at 31.0 N); background, water, roads, labels and boundaries muted; the state/county boundary
layer (admin levels 3-6) shown from zoom 6 instead of 8; the unused Natural Earth raster source dropped.
Usage: basemap_style.py  (fetches the current Positron style)."""
import json, datetime, urllib.request
SRC = "https://tiles.openfreemap.org/styles/positron"
st = json.loads(urllib.request.urlopen(urllib.request.Request(SRC, headers={"User-Agent": "blowdown-site-build/1.0"}), timeout=60).read())
DROP = {"park", "landuse", "landcover"}
st["layers"] = [l for l in st["layers"] if l.get("source-layer") not in DROP]
for l in st["layers"]:
    p = l.setdefault("paint", {})
    if l["type"] == "background": p["background-color"] = "#f4f4f1"
    if l["id"] == "water": p["fill-color"] = "#d8dfe1"
    if l.get("source-layer") == "transportation" and l["type"] == "line": p["line-opacity"] = 0.55
    if l.get("source-layer") == "boundary":
        p["line-color"] = "#a3a39c"
        if l["id"] == "boundary_3": l["minzoom"] = 6
    if l["type"] == "symbol": p["text-color"] = "#77776f"; p["text-halo-color"] = "#f4f4f1"; p["text-halo-width"] = 1.2
st["sources"].pop("ne2_shaded", None)
st["metadata"] = {**st.get("metadata", {}), "blowdown:source": SRC, "blowdown:built": datetime.date.today().isoformat(),
                  "blowdown:changes": "park/landuse/landcover removed; colors muted; boundary_3 from z6; ne2_shaded source dropped"}
json.dump(st, open("site/data/basemap_style.json", "w"), separators=(",", ":"))
print(len(st["layers"]), "layers;", [l["id"] for l in st["layers"] if l.get("source-layer") in ("boundary", "water")])
