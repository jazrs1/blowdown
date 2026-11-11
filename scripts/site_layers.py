"""Site step 2: web map layers on a Web Mercator (EPSG:3857) grid covering the study grid, 75 m Mercator pixels (~64 m on
the ground at 31N), so Leaflet image overlays are exact. Nothing is drawn inside the held-out block + 2 km or the aerial
tip + 2 km: those pixels are transparent (data layers) or grey (true colour), and the page draws grey polygons labelled
"Held out until scoring" on top. No model is run anywhere.
Layers (forest cells only for the difference layers, as in the analysis):
  nisar_hv.png   NISAR HV post - pre (dB, re-centred), mean of track 76 and track 55 (features_train.h5), +-2 dB
  s1_vh.png      Sentinel-1 VH post - pre (dB, re-centred, October-only posts), mean of orbits 19 and 92, +-2 dB
  s2_ndvi.png    Sentinel-2 NDVI post - pre (s2_stack.h5, 30 m mean), +-0.25
  damage.png     Sentinel-2 damage mask (30 m damage cells)
  s2_before.jpg / s2_after.jpg  Sentinel-2 SR true colour, SCL-masked medians 2026-09-01..10-08 and 10-11..11-09 (Earth Engine,
                 computed directly on the 3857 grid), fixed stretch 0-0.16 reflectance
GeoJSON: track.geojson (NHC b-deck), stations.geojson (data/wind/stations.json), heldout.geojson (exclusion polygons),
study.geojson (study grid outline). Writes site/data/ and site/data/layers.json."""
import json, os, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
from PIL import Image
from pyproj import Transformer
import matplotlib; matplotlib.use("Agg"); from matplotlib import cm, colors
import grid as G
OUT = "site/data"; os.makedirs(OUT, exist_ok=True)
RG = np.load("data/regions_30.npz"); forest, dmg = RG["forest"], RG["damage"]; excl = RG["heldout_excl"] | RG["tip_excl"]
H3, W3 = forest.shape; R = 30.0
u2l = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True); l2u = Transformer.from_crs("EPSG:4326", f"EPSG:{G.EPSG}", always_xy=True)
l2m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True); m2l = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
ux = [G.X0, G.X0 + W3 * R]; uy = [G.Y1 - H3 * R, G.Y1]
clon, clat = u2l.transform([ux[0], ux[1], ux[0], ux[1]], [uy[0], uy[0], uy[1], uy[1]])
mx0, my0 = l2m.transform(min(clon), min(clat)); mx1, my1 = l2m.transform(max(clon), max(clat))
PX = 75.0; mw, mh = int(np.ceil((mx1 - mx0) / PX)), int(np.ceil((my1 - my0) / PX)); mx1, my1 = mx0 + mw * PX, my0 + mh * PX
MX, MY = np.meshgrid(mx0 + (np.arange(mw) + 0.5) * PX, my1 - (np.arange(mh) + 0.5) * PX)
LON, LAT = m2l.transform(MX, MY); UX, UY = l2u.transform(LON, LAT)
ci = np.floor((UX - G.X0) / R).astype(int); ri = np.floor((G.Y1 - UY) / R).astype(int)
inside = (ci >= 0) & (ci < W3) & (ri >= 0) & (ri < H3); ci, ri = np.clip(ci, 0, W3 - 1), np.clip(ri, 0, H3 - 1)
samp = lambda a: a[ri, ci]
ex_t = inside & samp(excl); fo_t = inside & samp(forest) & ~ex_t
wlon, slat = m2l.transform(mx0, my0); elon, nlat = m2l.transform(mx1, my1)
bounds = [[slat, wlon], [nlat, elon]]
print("grid", mw, mh, "bounds", bounds, flush=True)
def save_png(rgba, name):
    im = Image.fromarray(rgba, "RGBA").quantize(colors=64, method=Image.Quantize.FASTOCTREE); im.save(f"{OUT}/{name}", optimize=True)
    return os.path.getsize(f"{OUT}/{name}")
def diverging(v, lim, cmap):
    rgba = (cmap(colors.Normalize(-lim, lim, clip=True)(np.nan_to_num(v))) * 255).astype("uint8")
    rgba[..., 3] = np.where(fo_t & np.isfinite(v), 255, 0); return rgba
meta = {"bounds": bounds, "pixel_m_mercator": PX, "size": [mw, mh], "layers": {}}
f = h5py.File("data/models/features_train.h5", "r")
with np.errstate(invalid="ignore"):
    hv = np.nanmean(np.stack([f["t76_HV_diff"][()], f["t55_HV_diff"][()]]), 0); vh = np.nanmean(np.stack([f["o19_VH_diff"][()], f["o92_VH_diff"][()]]), 0)
RdBu = matplotlib.colormaps["RdBu_r"]; BrBG = matplotlib.colormaps["BrBG"]
for name, arr, lim, cmap, label, unit in (("nisar_hv.png", hv, 2.0, RdBu, "NISAR HV difference", "dB"), ("s1_vh.png", vh, 2.0, RdBu, "Sentinel-1 VH difference", "dB")):
    v = np.where(inside, samp(arr), np.nan); v[ex_t] = np.nan
    meta["layers"][name] = {"label": label, "unit": unit, "range": [-lim, lim], "cmap": "RdBu_r", "bytes": save_png(diverging(v, lim, cmap), name)}
del hv, vh
S = h5py.File("data/s2_stack.h5", "r"); nd = np.zeros((H3, W3), "float32")
for r in range(0, H3 * 3, 600):
    re_ = min(r + 600, H3 * 3)
    with np.errstate(invalid="ignore"):
        d = S["ndvi_post"][r:re_, :W3 * 3] - S["ndvi_pre"][r:re_, :W3 * 3]
        nd[r // 3:re_ // 3] = np.nanmean(d.reshape(-1, 3, W3, 3), (1, 3))
nd[excl] = np.nan
v = np.where(inside, samp(nd), np.nan)
rgba = (BrBG(colors.Normalize(-0.25, 0.25, clip=True)(np.nan_to_num(v))) * 255).astype("uint8"); rgba[..., 3] = np.where(fo_t & np.isfinite(v), 255, 0)
meta["layers"]["s2_ndvi.png"] = {"label": "Sentinel-2 NDVI difference", "unit": "NDVI", "range": [-0.25, 0.25], "cmap": "BrBG", "bytes": save_png(rgba, "s2_ndvi.png")}
dm = fo_t & samp(dmg); rgba = np.zeros((mh, mw, 4), "uint8"); rgba[dm] = (140, 46, 30, 235)
meta["layers"]["damage.png"] = {"label": "Sentinel-2 damage mask", "bytes": save_png(rgba, "damage.png")}
# ---- true colour from Earth Engine on the same 3857 grid
cache = "data/site_s2rgb_3857.npz"
if not os.path.exists(cache):
    import ee
    from ee_common import pull_grid
    def comp(a, b):
        def m(i):
            s = i.select("SCL"); ok = s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11))
            return i.select(["B4", "B3", "B2"]).updateMask(ok)
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(ee.Geometry.Rectangle([wlon, slat, elon, nlat])).filterDate(a, b).map(m).median()
    img = comp("2026-09-01", "2026-10-09").rename(["r0", "g0", "b0"]).addBands(comp("2026-10-11", "2026-11-10").rename(["r1", "g1", "b1"]))
    a = pull_grid(img, "EPSG:3857", float(mx0), float(my1), PX, mw, mh, tile=512)
    np.savez_compressed(cache, **{k: v.astype("float32") for k, v in a.items()}); print("ee pulled", flush=True)
T = np.load(cache)
for tag, nm in (("0", "s2_before.jpg"), ("1", "s2_after.jpg")):
    rgb = np.stack([T[f"r{tag}"], T[f"g{tag}"], T[f"b{tag}"]], -1) / 10000.0
    nod = ~np.isfinite(rgb).all(-1)                       # masked by SCL (water, cloud) or no data
    rgb = (np.clip(np.nan_to_num(rgb) / 0.16, 0, 1) ** 0.85 * 255).astype("uint8"); rgb[nod] = (205, 212, 214); rgb[ex_t] = (158, 158, 158)
    Image.fromarray(rgb).save(f"{OUT}/{nm}", quality=78, optimize=True, progressive=True)
    meta["layers"][nm] = {"label": "Sentinel-2 true colour " + ("before" if tag == "0" else "after"), "bytes": os.path.getsize(f"{OUT}/{nm}")}
# ---- vectors
W = json.load(open("docs/wind/wind.json")); ST = json.load(open("data/wind/stations.json"))
fx = W["fixes"]; feats = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[q["lon"], q["lat"]] for q in fx]}, "properties": {"kind": "track"}}]
for q in fx:
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [q["lon"], q["lat"]]},
                  "properties": {"kind": "fix", "time": q["time"], "vmax_kt": q["vmax_kt"], "mslp_mb": q["mslp_mb"], "type": q["type"]}})
lf = W["landfall"]["lon_lat_on_track"]
feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": lf}, "properties": {"kind": "landfall", "note": "where the best track meets the coast; NWS Mobile: landfall near Destin about 8:30 PM CDT 9 Oct"}})
json.dump({"type": "FeatureCollection", "features": feats}, open(f"{OUT}/track.geojson", "w"))
sf = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
       "properties": {"name": s["name"], "gust_kt": s["gust_kt"], "network": s["network"], "approx": bool(s.get("location_approximate")),
                      "sparse": (s.get("n_obs_22Z_to_06Z") is not None and s["n_obs_22Z_to_06Z"] < 10),
                      "source": "NWS Mobile post-tropical cyclone report" if s["short"] in ("Jay", "Oriole Beach") else "Iowa Environmental Mesonet ASOS archive"}} for s in ST["stations"]]
json.dump({"type": "FeatureCollection", "features": sf}, open(f"{OUT}/stations.geojson", "w"))
hf = []
for nm in ("heldout_excl", "tip_excl"):
    rr, cc = np.nonzero(RG[nm]); x0, x1 = G.X0 + cc.min() * R, G.X0 + (cc.max() + 1) * R; y1, y0 = G.Y1 - rr.min() * R, G.Y1 - (rr.max() + 1) * R
    xs = np.r_[np.linspace(x0, x1, 20), np.full(20, x1), np.linspace(x1, x0, 20), np.full(20, x0)]; ys = np.r_[np.full(20, y0), np.linspace(y0, y1, 20), np.full(20, y1), np.linspace(y1, y0, 20)]
    lo, la = u2l.transform(xs, ys); hf.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[round(a, 5), round(b, 5)] for a, b in zip(lo, la)]]},
                                               "properties": {"label": "Held out until scoring", "which": "held-out block + 2 km" if nm == "heldout_excl" else "aerial tip + 2 km"}})
json.dump({"type": "FeatureCollection", "features": hf}, open(f"{OUT}/heldout.geojson", "w"))
xs = np.r_[np.linspace(ux[0], ux[1], 30), np.full(30, ux[1]), np.linspace(ux[1], ux[0], 30), np.full(30, ux[0])]; ys = np.r_[np.full(30, uy[0]), np.linspace(uy[0], uy[1], 30), np.full(30, uy[1]), np.linspace(uy[1], uy[0], 30)]
lo, la = u2l.transform(xs, ys)
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[round(a, 5), round(b, 5)] for a, b in zip(lo, la)]]}, "properties": {}}]}, open(f"{OUT}/study.geojson", "w"))
json.dump(meta, open(f"{OUT}/layers.json", "w"), indent=1)
print(json.dumps(meta, indent=1))
