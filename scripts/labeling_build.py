"""Models step 3: labeling set for John.
Sampling frame (design.md): forest cells of the block where every arm can predict (at least one NISAR track and at least one
S1 orbit valid in the 30 m difference layers). Strata: upland / wetland (regions_30.npz) x inside / outside the Sentinel-2
damage mask (30 m damage cell = >= 50% damage pixels). Held-out: 100 per stratum (400). Tip: 150 = upland 37 in + 38 out,
wetland 38 in + 37 out. Sampling seed 2026; a stratum with too few cells gives all it has (recorded).
Ids are random 8-hex strings from a separate generator; the order shown is a random permutation. The key (id -> region,
stratum, row, col, lon, lat) goes to data/models/labeling_key.csv only; its sha256 goes to docs/models/labeling_key.sha256.
Images: Sentinel-2 SR harmonized true colour (B4, B3, B2), SCL-masked medians, before 2026-09-01..10-08 and after
2026-10-11..11-09 (the reference windows), 1 km around the cell centre at 10 m, shown 3x enlarged; joint 2-98% stretch per cell;
the 30 m cell is outlined. Tip cells add the NOAA aerial mosaic (same collection as the gate) at 2 m over the same 1 km.
Stages (cached): sample -> s2 pull per region (data/models/s2rgb_<region>.npz) -> aerial chips -> render -> page -> zip."""
import csv, hashlib, io, json, os, sys, time, zipfile; sys.path.insert(0, "scripts")
import h5py, numpy as np, ee
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
import grid as G
from ee_common import pull_grid
t0 = time.time(); R = 30.0
RG = np.load("data/regions_30.npz"); H3, W3 = RG["forest"].shape
tr = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True)
OUT = "labeling"; IMG = f"{OUT}/img"; os.makedirs(IMG, exist_ok=True)
KEY = "data/models/labeling_key.csv"
PLAN = {"heldout": {("upland", 1): 100, ("upland", 0): 100, ("wetland", 1): 100, ("wetland", 0): 100},
        "tip": {("upland", 1): 37, ("upland", 0): 38, ("wetland", 1): 38, ("wetland", 0): 37}}
# ---- 1. sample
if not os.path.exists(KEY):
    rng = np.random.default_rng(2026); ids_rng = np.random.default_rng(int.from_bytes(os.urandom(8), "little"))
    rows, notes = [], {}
    for reg, plan in PLAN.items():
        f = h5py.File(f"data/models/features_{reg}.h5", "r"); r0, c0 = f.attrs["row0"], f.attrs["col0"]
        blk = f["block"][()]; fo = f["forest"][()]
        nis = np.isfinite(f["t76_HV_diff"][()]) | np.isfinite(f["t55_HV_diff"][()]); s1 = np.isfinite(f["o19_VH_diff"][()]) | np.isfinite(f["o92_VH_diff"][()])
        hh, ww = blk.shape; dmg = RG["damage"][r0:r0 + hh, c0:c0 + ww]
        frame = blk & fo & nis & s1
        for (dom, ind), n in plan.items():
            m = frame & f[dom][()] & (dmg if ind else ~dmg); idx = np.flatnonzero(m)
            pick = rng.choice(idx, min(n, idx.size), replace=False); notes[f"{reg} {dom} {'in' if ind else 'out'}"] = {"wanted": n, "frame_cells": int(idx.size), "drawn": int(pick.size)}
            for i in pick:
                rr, cc = np.unravel_index(i, blk.shape); R_, C_ = int(rr + r0), int(cc + c0)
                x, y = G.X0 + (C_ + 0.5) * R, G.Y1 - (R_ + 0.5) * R; lo, la = tr.transform(x, y)
                rows.append({"region": reg, "domain": dom, "in_s2_mask": ind, "row": R_, "col": C_, "x": x, "y": y, "lon": round(lo, 6), "lat": round(la, 6)})
    ids = set()
    while len(ids) < len(rows): ids.add(ids_rng.bytes(4).hex())
    ids = list(ids); order = ids_rng.permutation(len(rows))
    for k, row in enumerate(rows): row["id"] = ids[k]; row["show_order"] = int(np.nonzero(order == k)[0][0])
    with open(KEY, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    json.dump(notes, open("docs/models/labeling_sample.json", "w"), indent=1); print(json.dumps(notes, indent=1), flush=True)
rows = list(csv.DictReader(open(KEY)))
for r_ in rows:
    for k in ("row", "col", "show_order"): r_[k] = int(r_[k])
    for k in ("x", "y", "lon", "lat"): r_[k] = float(r_[k])
open("docs/models/labeling_key.sha256", "w").write(hashlib.sha256(open(KEY, "rb").read()).hexdigest() + "  data/models/labeling_key.csv\n")
# ---- 2. S2 true colour per region at 10 m (bbox of the sampled cells + 600 m)
def s2rgb(a, b):
    def m(i):
        s = i.select("SCL"); ok = s.neq(0).And(s.neq(1)).And(s.neq(3)).And(s.neq(6)).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(11))
        return i.select(["B4", "B3", "B2"]).updateMask(ok)
    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(ee.Geometry.Rectangle([-87.6, 30.4, -86.6, 31.8])).filterDate(a, b).map(m).median()
S2 = {}
for reg in PLAN:
    p = f"data/models/s2rgb_{reg}.npz"; rs = [r_ for r_ in rows if r_["region"] == reg]
    x0 = min(r_["x"] for r_ in rs) - 600; x1 = max(r_["x"] for r_ in rs) + 600; y0 = min(r_["y"] for r_ in rs) - 600; y1 = max(r_["y"] for r_ in rs) + 600
    x0 = G.X0 + np.floor((x0 - G.X0) / 10) * 10; y1 = G.Y1 - np.floor((G.Y1 - y1) / 10) * 10
    w, h = int(np.ceil((x1 - x0) / 10)), int(np.ceil((y1 - y0) / 10))
    if not os.path.exists(p):
        img = s2rgb("2026-09-01", "2026-10-09").rename(["r0", "g0", "b0"]).addBands(s2rgb("2026-10-11", "2026-11-10").rename(["r1", "g1", "b1"]))
        a = pull_grid(img, f"EPSG:{G.EPSG}", float(x0), float(y1), 10, w, h, tile=512)
        np.savez_compressed(p, x0=x0, y1=y1, **{k: v.astype("float32") for k, v in a.items()}); print("s2", reg, w, h, round(time.time() - t0), flush=True)
    S2[reg] = np.load(p)
# ---- 3. aerial chips (tip): NOAA mosaic RGB at 2 m over the 1 km window
COL = ee.ImageCollection("projects/sat-io/open-datasets/NOAA-EMERGENCY-RESPONSE/HURRICANE_ISAIAS_2026")
os.makedirs("data/models/aerial", exist_ok=True)
for r_ in rows:
    if r_["region"] != "tip": continue
    p = f"data/models/aerial/{r_['id']}.npy"
    if os.path.exists(p): continue
    req = {"expression": COL.mosaic().select(["red", "green", "blue"]).unmask(0).toByte(), "fileFormat": "NUMPY_NDARRAY",
           "grid": {"dimensions": {"width": 500, "height": 500}, "crsCode": f"EPSG:{G.EPSG}",
                    "affineTransform": {"scaleX": 2, "shearX": 0, "translateX": r_["x"] - 500, "shearY": 0, "scaleY": -2, "translateY": r_["y"] + 500}}}
    for k in range(4):
        try: a = ee.data.computePixels(req); break
        except Exception as e:
            if k == 3: raise
            time.sleep(5 * (k + 1))
    np.save(p, np.stack([a["red"], a["green"], a["blue"]], -1).astype("uint8"))
print("aerial done", round(time.time() - t0), flush=True)
# ---- 4. render
try: FONT = ImageFont.truetype("arial.ttf", 15)
except Exception: FONT = ImageFont.load_default()
PX = 300
def panel(rgb, title, box):
    im = Image.fromarray(rgb).resize((PX, PX), Image.BILINEAR); c = Image.new("RGB", (PX, PX + 24), "white"); c.paste(im, (0, 24))
    d = ImageDraw.Draw(c); d.text((4, 3), title, fill="black", font=FONT)
    if box: d.rectangle([box[0], box[1] + 24, box[2], box[3] + 24], outline=(255, 0, 255), width=2)
    return c
for r_ in rows:
    p = f"{IMG}/{r_['id']}.jpg"
    if os.path.exists(p): continue
    s = S2[r_["region"]]; ci = int(np.floor((r_["x"] - float(s["x0"])) / 10)); ri = int(np.floor((float(s["y1"]) - r_["y"]) / 10))
    win = lambda b: s[b][ri - 50:ri + 50, ci - 50:ci + 50]
    pre = np.stack([win(b) for b in ("r0", "g0", "b0")], -1); post = np.stack([win(b) for b in ("r1", "g1", "b1")], -1)
    both = np.concatenate([pre, post]); lo, hi = np.nanpercentile(both, 2), np.nanpercentile(both, 98)
    st = lambda a: (np.clip((np.nan_to_num(a, nan=lo) - lo) / max(hi - lo, 1e-6), 0, 1) ** 0.8 * 255).astype("uint8")
    # the cell centre lies at the centre of S2 pixel (ri, ci) = window pixel 50 -> display 151.5 px; cell = 3 S2 px = 9 display px
    box = (147, 147, 156, 156)
    pans = [panel(st(pre), "Before (Sep-early Oct 2026)", box), panel(st(post), "After (mid Oct-early Nov 2026)", box)]
    if r_["region"] == "tip":
        a = np.load(f"data/models/aerial/{r_['id']}.npy")
        if (a.sum(-1) > 0).mean() > 0.2: pans.append(panel(a, "NOAA aerial (after)", (145.5, 145.5, 154.5, 154.5)))   # centred window, 30 m = 9 px
        else:
            c = Image.new("RGB", (PX, PX + 24), (230, 230, 230)); ImageDraw.Draw(c).text((10, 150), "No aerial image here", fill="black", font=FONT); pans.append(c)
    out = Image.new("RGB", (sum(q.width for q in pans) + 8 * (len(pans) - 1), PX + 24), "white"); x = 0
    for q in pans: out.paste(q, (x, 0)); x += q.width + 8
    out.save(p, quality=88)
print("rendered", round(time.time() - t0), flush=True)
# ---- 5. page
cells = [{"id": r_["id"], "img": f"img/{r_['id']}.jpg"} for r_ in sorted(rows, key=lambda q: q["show_order"])]
html = open("scripts/labeling_template.html", encoding="utf8").read().replace("/*CELLS*/[]", json.dumps(cells))
open(f"{OUT}/index.html", "w", encoding="utf8").write(html)
with zipfile.ZipFile("labeling.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(OUT):
        for fn in files: z.write(os.path.join(root, fn), os.path.relpath(os.path.join(root, fn), "."))
print("zip", round(os.path.getsize("labeling.zip") / 1e6, 1), "MB", round(time.time() - t0), flush=True)
