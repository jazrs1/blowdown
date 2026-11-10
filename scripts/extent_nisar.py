"""Step 1 NISAR side: HH/HV post-pre over the study box from the two gate scenes, aggregated (linear mean) to 80 m
UTM blocks while reading in row chunks, then binned onto the 0.0008 deg grid."""
import json, sys
import h5py, numpy as np, psutil
from pyproj import Transformer
sys.path.insert(0, "scripts")
GRID = "/science/LSAR/GCOV/grids/frequencyA"
LOG = json.load(open("data/nisar/download_log.json"))
P = {k: "data/nisar/" + LOG[k]["file"] for k in ("pre", "post")}
STUDY = (-87.60, 30.40, -86.60, 31.80); RES = 0.0008; B = 8  # 8 x 10 m = 80 m blocks

def window(g, box, pad=0.01):
    t = Transformer.from_crs(4326, int(g["projection"].attrs["epsg_code"]), always_xy=True)
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    s = np.linspace(0, 1, 100)
    X, Y = t.transform(np.r_[x0 + s*(x1-x0), np.full(100, x1), x1 - s*(x1-x0), np.full(100, x0)],
                       np.r_[np.full(100, y0), y0 + s*(y1-y0), np.full(100, y1), y1 - s*(y1-y0)])
    xc, yc = g["xCoordinates"][()], g["yCoordinates"][()]
    ci = np.flatnonzero((xc >= X.min()) & (xc <= X.max())); ri = np.flatnonzero((yc >= Y.min()) & (yc <= Y.max()))
    return ri[0], ri[-1] + 1, ci[0], ci[-1] + 1, xc, yc

def blockmean(a):
    h, w = (a.shape[0] // B) * B, (a.shape[1] // B) * B
    a = a[:h, :w].reshape(h // B, B, w // B, B)
    n = np.isfinite(a).sum((1, 3)); s = np.nansum(a, (1, 3))
    return np.where(n >= B * B // 2, s / np.maximum(n, 1), np.nan)

agg = {}
for tag, path in P.items():
    with h5py.File(path, "r") as f:
        g = f[GRID]; r0, r1, c0, c1, xc, yc = window(g, STUDY); epsg = int(g["projection"].attrs["epsg_code"])
        c1 = c0 + ((c1 - c0) // B) * B
        rows = {p: [] for p in ("HHHH", "HVHV")}
        for rs in range(r0, r1 - B + 1, 1024):
            re_ = min(rs + 1024, r0 + ((r1 - r0) // B) * B)
            m = g["mask"][rs:re_, c0:c1]; bad = (m == 0) | (m == 255)
            for p in rows:
                v = g[p][rs:re_, c0:c1].astype("float32"); v[bad] = np.nan; rows[p].append(blockmean(v))
        agg[tag] = {p: np.vstack(v) for p, v in rows.items()}
        nb_r, nb_c = agg[tag]["HHHH"].shape
        bx = xc[c0:c1].reshape(-1, B).mean(1); by = yc[r0:r0 + nb_r * B].reshape(-1, B).mean(1)
        agg[tag]["xy"] = (bx, by, epsg)
assert agg["pre"]["xy"][2] == agg["post"]["xy"][2] and np.allclose(agg["pre"]["xy"][0], agg["post"]["xy"][0])
bx, by, epsg = agg["pre"]["xy"]
XX, YY = np.meshgrid(bx, by); lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(XX, YY)
x0, y0, x1, y1 = STUDY; w, h = round((x1 - x0) / RES), round((y1 - y0) / RES)
col = np.floor((lon - x0) / RES).astype(int); row = np.floor((y1 - lat) / RES).astype(int)
out = {}
for p, k in (("HHHH", "dHH"), ("HVHV", "dHV")):
    d = 10 * np.log10(agg["post"][p]) - 10 * np.log10(agg["pre"][p])
    ok = (col >= 0) & (col < w) & (row >= 0) & (row < h) & np.isfinite(d)
    s = np.zeros(h * w); n = np.zeros(h * w)
    np.add.at(s, row[ok] * w + col[ok], d[ok]); np.add.at(n, row[ok] * w + col[ok], 1)
    out[k] = np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(h, w).astype("float32")
np.savez_compressed("data/extent_nisar.npz", extent=np.array(STUDY), res=RES, **out)
mi = psutil.Process().memory_info()
print({k: float(np.mean(np.isfinite(v))) for k, v in out.items()}, "peak RAM GB", round(mi.peak_wset / 1e9, 2))
