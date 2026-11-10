"""Step 2/3 combine: per NISAR track and per S1 orbit-year, mean linear power of pre and post scenes ->
10 m dB pre, post, raw difference, forest-median-recentred difference, and scene counts. Processed in row blocks.
Output: data/layers.h5 (group per arm). Requires data/s2_stack.h5 for the forest mask (cls)."""
import json, os, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy import ndimage
import grid as G
FOREST = (41, 42, 43, 90)
NIS = {"nisar_076": (["076_2026-09-23", "076_2026-10-05"], ["076_2026-10-17", "076_2026-10-29"]),
       "nisar_055": (["055_2026-09-22", "055_2026-10-04"], ["055_2026-10-16", "055_2026-10-28"]),
       # sensitivity: drop the P05036 (spec 1.6.0) post scenes, which sit 0.6 dB HV / 1.0 dB HH below the rest
       "nisar_076_p23": (["076_2026-09-23", "076_2026-10-05"], ["076_2026-10-17"]),
       "nisar_055_p23": (["055_2026-09-22", "055_2026-10-04"], ["055_2026-10-16"])}
S1 = {f"s1_{o}_{y}": (f"data/s1/{o}_{y}.h5",) for o in (19, 92) for y in (2026, 2025)}
BLK = 1024
cls_ds = h5py.File("data/s2_stack.h5", "r")["cls"]
out = h5py.File("data/layers.h5", "a")
def mk(g, n, dt="float32"):
    if n in g: del g[n]
    return g.create_dataset(n, (G.H, G.W), dt, chunks=(512, 512), compression="lzf", shuffle=True,
                            fillvalue=np.nan if dt == "float32" else 0)
def db(x): 
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)

def run(arm, pols, read_pre, read_post):
    t0 = time.time(); g = out.require_group(arm)
    ds = {f"{p}_{k}": mk(g, f"{p}_{k}") for p in pols for k in ("pre", "post", "diff", "diffc")}
    cnt = {k: mk(g, f"n_{k}", "uint8") for k in ("pre", "post")}
    samples = {p: [] for p in pols}; rng = np.random.default_rng(0)
    for r in range(0, G.H, BLK):
        re_ = min(r + BLK, G.H); forest = np.isin(cls_ds[r:re_], FOREST)
        for k, reader in (("pre", read_pre), ("post", read_post)):
            for p in pols:
                stack = reader(p, r, re_)
                with np.errstate(invalid="ignore"): m = np.nanmean(stack, 0) if stack.shape[0] > 1 else stack[0]
                ds[f"{p}_{k}"][r:re_] = db(m).astype("float32")
            cnt[k][r:re_] = np.isfinite(stack).sum(0).astype("uint8")
        for p in pols:
            d = ds[f"{p}_post"][r:re_] - ds[f"{p}_pre"][r:re_]; ds[f"{p}_diff"][r:re_] = d
            v = d[forest & np.isfinite(d)]
            if v.size: samples[p].append(rng.choice(v, min(v.size, 20000), replace=False))
    for p in pols:
        med = float(np.median(np.concatenate(samples[p]))); g[f"{p}_diffc"].attrs["forest_median_removed_dB"] = med
        for r in range(0, G.H, BLK): ds[f"{p}_diffc"][r:r + BLK] = ds[f"{p}_diff"][r:r + BLK] - med
        print(arm, p, "forest median diff removed: %.3f dB" % med, flush=True)
    g.attrs["seconds"] = time.time() - t0

which = sys.argv[1:] or list(NIS) + list(S1)
for arm in which:
    if arm in NIS:
        pre, post = NIS[arm]; fs = {k: h5py.File(f"data/stack/{k}.h5", "r") for k in pre + post}
        rd = lambda keys: (lambda p, r, re_: np.stack([fs[k][p][r:re_] for k in keys]))
        run(arm, ("HH", "HV"), rd(pre), rd(post))
        out[arm].attrs.update({"pre": json.dumps(pre), "post": json.dumps(post)})
    elif os.path.exists(S1[arm][0]):
        f = h5py.File(S1[arm][0], "r")
        def s1read(k):   # power <= 0 is no-data (swath-edge zeros in S1D GRD_FLOAT); trim 200 m off swath edges
            def rd(p, r, re_):
                a = f[f"{p}_{k}"][r:re_]; ok = np.isfinite(a) & (a > 0)
                ok = ndimage.binary_erosion(ok, np.ones((3, 3)), iterations=20, border_value=1)
                return np.where(ok, a, np.nan)[None]
            return rd
        run(arm, ("VV", "VH"), s1read("pre"), s1read("post"))
        out[arm].attrs.update({"pre": f.attrs["pre"], "post": f.attrs["post"]})
    else:
        print("missing", arm)
out.close()
