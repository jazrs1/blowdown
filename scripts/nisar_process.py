"""Extract NISAR GCOV HH/HV (frequencyA) for each box, smooth, dB, post-pre, and resample onto the EE grid.

Usage: python -I scripts/nisar_process.py data/nisar
Reads only the box windows from the HDF5 (never the full grid) and reports peak RAM.
"""
import json, os, sys, time
import h5py, numpy as np, psutil
from pyproj import CRS, Transformer
from scipy.ndimage import uniform_filter

NDIR = sys.argv[1]
LOG = json.load(open(os.path.join(NDIR, "download_log.json")))
GRID = "/science/LSAR/GCOV/grids/frequencyA"
EXT = {"AL": (-87.35, 30.95, -86.85, 31.45), "FL": (-87.25, 30.55, -86.95, 30.80)}
PAD = 0.01  # degrees of margin so smoothing has context at the box edge


def describe(f):
    """Print the frequencyA group so the structure is checked, not assumed."""
    g = f[GRID]
    for k, v in g.items():
        if isinstance(v, h5py.Dataset):
            print(f"   {k}: shape={v.shape} dtype={v.dtype} attrs={ {a: v.attrs[a] for a in list(v.attrs)[:6]} }")
    return g


def epsg_of(g):
    p = g["projection"]
    for key in ("epsg_code", "epsg"):
        if key in p.attrs:
            return int(np.asarray(p.attrs[key]).ravel()[0])
    return int(np.asarray(p[()]).ravel()[0])


def window(g, box, epsg):
    """Row/col slices covering the lon/lat box (edges densified) in the product's projected grid."""
    x0, y0, x1, y1 = box[0] - PAD, box[1] - PAD, box[2] + PAD, box[3] + PAD
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    s = np.linspace(0, 1, 50)
    lons = np.r_[x0 + s * (x1 - x0), np.full(50, x1), x1 - s * (x1 - x0), np.full(50, x0)]
    lats = np.r_[np.full(50, y0), y0 + s * (y1 - y0), np.full(50, y1), y1 - s * (y1 - y0)]
    X, Y = t.transform(lons, lats)
    xc, yc = g["xCoordinates"][()], g["yCoordinates"][()]
    ci = np.flatnonzero((xc >= X.min()) & (xc <= X.max()))
    ri = np.flatnonzero((yc >= Y.min()) & (yc <= Y.max()))
    return slice(ri[0], ri[-1] + 1), slice(ci[0], ci[-1] + 1), xc, yc


def read_box(path, box):
    with h5py.File(path, "r") as f:
        g = f[GRID]
        epsg = epsg_of(g)
        rs, cs, xc, yc = window(g, box, epsg)
        m = g["mask"][rs, cs]
        bad = (m == 0) | (m == 255)  # spec: 0 = partially focused/invalid, 255 = outside acquisition
        out = {p: np.where(bad, np.nan, g[p][rs, cs]).astype("float32") for p in ("HHHH", "HVHV")}
        out["invalid_frac"] = float(bad.mean())
        return out, xc[cs], yc[rs], epsg


def to_db_smoothed(lin, size=5):
    lin = np.where(np.isfinite(lin) & (lin > 0), lin, np.nan)
    valid = np.isfinite(lin).astype("float32")
    num = uniform_filter(np.nan_to_num(lin), size)
    den = uniform_filter(valid, size)
    sm = np.where(den > 0.5, num / np.maximum(den, 1e-6), np.nan)  # NaN-aware boxcar in linear power
    return 10 * np.log10(sm)


def resample_to_ee(diff, xc, yc, epsg, box, res):
    """Mean-aggregate the projected-grid difference into the EE lon/lat grid cells."""
    x0, y0, x1, y1 = box
    w, h = round((x1 - x0) / res), round((y1 - y0) / res)
    XX, YY = np.meshgrid(xc, yc)
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(XX, YY)
    col = np.floor((lon - x0) / res).astype(int); row = np.floor((y1 - lat) / res).astype(int)
    ok = (col >= 0) & (col < w) & (row >= 0) & (row < h) & np.isfinite(diff)
    s = np.zeros(h * w); n = np.zeros(h * w)
    np.add.at(s, row[ok] * w + col[ok], diff[ok]); np.add.at(n, row[ok] * w + col[ok], 1)
    return np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(h, w).astype("float32")


t0 = time.time()
paths = {k: os.path.join(NDIR, LOG[k]["file"]) for k in ("pre", "post")}
for k, p in paths.items():
    with h5py.File(p, "r") as f:
        print(k, os.path.basename(p)); describe(f)
summary = {}
for name, box in EXT.items():
    pre, xpre, ypre, e1 = read_box(paths["pre"], box)
    post, xpost, ypost, e2 = read_box(paths["post"], box)
    assert e1 == e2, f"EPSG differs between cycles: {e1} vs {e2}"
    dx1, dx2 = np.diff(xpre).mean(), np.diff(xpost).mean()
    assert abs(dx1 - dx2) < 1e-6, f"posting differs: {dx1} vs {dx2}"
    # align by coordinate values, not array position
    xs = np.intersect1d(np.round(xpre, 3), np.round(xpost, 3)); ys = np.intersect1d(np.round(ypre, 3), np.round(ypost, 3))
    def sub(a, xc, yc):
        ci = np.isin(np.round(xc, 3), xs); ri = np.isin(np.round(yc, 3), ys)
        return a[np.ix_(ri, ci)]
    ee = np.load(f"data/ee_{name}.npz"); res = float(ee["res"])
    xg = xpre[np.isin(np.round(xpre, 3), xs)]; yg = ypre[np.isin(np.round(ypre, 3), ys)]
    out = {}
    for pol, key in (("HHHH", "dHH"), ("HVHV", "dHV")):
        d = to_db_smoothed(sub(post[pol], xpost, ypost)) - to_db_smoothed(sub(pre[pol], xpre, ypre))
        out[key] = resample_to_ee(d, xg, yg, e1, box, res)
        out[key + "_native_median"] = float(np.nanmedian(d))
    np.savez_compressed(f"data/nisar_{name}.npz", dHH=out["dHH"], dHV=out["dHV"], extent=np.array(box), res=res)
    summary[name] = {"epsg": e1, "posting_m": float(abs(dx1)), "native_shape": [len(yg), len(xg)],
                     "invalid_frac_pre": pre["invalid_frac"], "invalid_frac_post": post["invalid_frac"],
                     "median_dHH_dB": out["dHH_native_median"], "median_dHV_dB": out["dHV_native_median"]}
    print(name, summary[name])
proc = psutil.Process()
mi = proc.memory_info()
summary["peak_ram_bytes"] = int(getattr(mi, "peak_wset", 0) or mi.rss)
summary["peak_ram_note"] = "peak working set of this processing process (Windows peak_wset)"
summary["seconds"] = round(time.time() - t0, 1)
json.dump(summary, open("data/nisar_summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
