"""Sensitivity checks on the step-5 comparison (all on the 30 m / 100 m labelled blocks from evaluate.py):
1) Spatial block bootstrap (10 km tiles) of AUC differences: combined A vs B, and best geometry vs best geometry.
2) Per-date S1 VH at 100 m (data/s1_perdate_100.npz): AUC of each single pre->post pair.
3) Near-total canopy loss (post NDVI < 0.35 and dNDVI < -0.30, the clearcut-like signature) inside the damage class:
   km2, and AUCs at 100 m with damage blocks containing >= 5% near-total pixels removed.
Writes docs/pipeline/sensitivity.json."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy.stats import rankdata
import grid as G
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
A, B = "A: NISAR HV (both tracks)", "B: S1 VH (both orbits)"
PAIRS = {"combined: A NISAR HV vs B S1 VH": (A, B), "best geometry: NISAR t76 HV vs S1 o92 VH": ("nisar_076:HV", "s1_92_2026:VH"),
         "weak geometry: NISAR t55 HV vs S1 o19 VH": ("nisar_055:HV", "s1_19_2026:VH"),
         "control-adjusted check: S1 o92 VH 2026 vs 2025": ("s1_92_2026:VH", "s1_92_2025:VH")}
def auc(s, y):
    ok = np.isfinite(s); s, y = s[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan
    rk = rankdata(s); return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
out = {"block_bootstrap": {}, "per_date_s1_100m": {}, "near_total": {}}
rng = np.random.default_rng(3)
for res in (30, 100):
    c = np.load(f"data/coarse_{res}.npz"); dmg = c["dmg"] >= 0.5; lab = dmg | ((c["itc"] >= 0.9) & ~dmg)
    t = 10000 // res; th, tw = dmg.shape[0] // t, dmg.shape[1] // t          # 10 km tiles
    tid = (np.arange(dmg.shape[0])[:, None] // t).clip(0, th - 1) * tw + (np.arange(dmg.shape[1])[None, :] // t).clip(0, tw - 1)
    for name, (ka, kb) in PAIRS.items():
        a, b = c[ka], c[kb]; m = lab & np.isfinite(a) & np.isfinite(b)
        av, bv, yv, tv = a[m], b[m], dmg[m], tid[m]
        order = np.argsort(tv); av, bv, yv, tv = av[order], bv[order], yv[order], tv[order]
        tiles, start = np.unique(tv, return_index=True); ends = np.r_[start[1:], len(tv)]
        point = auc(av, yv) - auc(bv, yv); bs = []
        for _ in range(300 if res == 100 else 100):
            pick = rng.integers(0, len(tiles), len(tiles)); ix = np.concatenate([np.arange(start[p], ends[p]) for p in pick])
            bs.append(auc(av[ix], yv[ix]) - auc(bv[ix], yv[ix]))
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
        out["block_bootstrap"][f"{name} @ {res} m"] = {"auc_first": round(auc(av, yv), 3), "auc_second": round(auc(bv, yv), 3),
            "diff": round(point, 3), "ci95_block": [round(float(lo), 3), round(float(hi), 3)], "n_blocks": int(m.sum()),
            "n_tiles_with_data": int(len(tiles)), "n_tiles_with_damage": int(len(np.unique(tv[yv])))}
        print(name, res, out["block_bootstrap"][f"{name} @ {res} m"], flush=True)

# ---- per-date S1 at 100 m
c = np.load("data/coarse_100.npz"); dmg = c["dmg"] >= 0.5; lab = dmg | ((c["itc"] >= 0.9) & ~dmg); forest = c["ft"] > 0
P = np.load("data/s1_perdate_100.npz")
def score(pre, post):
    with np.errstate(divide="ignore", invalid="ignore"): d = 10 * np.log10(post) - 10 * np.log10(pre)
    d = d - np.nanmedian(d[forest & np.isfinite(d)]); m = lab & np.isfinite(d)
    ev = m & (c["ft"] == 1)
    return {"auc_all": round(auc(d[m], dmg[m]), 3), "auc_evergreen": round(auc(d[ev], dmg[ev]), 3),
            "delta_dB": round(float(np.nanmean(d[m & dmg]) - np.nanmean(d[m & ~dmg])), 2)}
for o, pres, posts in ((19, ["2026-09-28"], ["2026-10-22", "2026-11-03"]), (92, ["2026-09-21", "2026-10-03"], ["2026-10-27", "2026-11-08"])):
    for a in pres:
        for b in posts:
            out["per_date_s1_100m"][f"orbit {o}: {a} -> {b}"] = score(P[f"VH_{o}_{a}"], P[f"VH_{o}_{b}"])
    for a, b in ((pres[0], pres[-1]), (posts[0], posts[-1])):
        if a != b: out["per_date_s1_100m"][f"orbit {o}: {a} -> {b} (same side, no storm between)"] = score(P[f"VH_{o}_{a}"], P[f"VH_{o}_{b}"])
for k, v in out["per_date_s1_100m"].items(): print(k, v)

# ---- near-total loss inside damage
S = h5py.File("data/s2_stack.h5", "r"); R = h5py.File("data/reference.h5", "r")
nt100 = np.zeros((HB // 10, WB // 10), "float32"); n_in_dmg = 0
for r in range(0, HB, 600):
    s = slice(r, min(r + 600, HB)); npre, npost = S["ndvi_pre"][s, :WB], S["ndvi_post"][s, :WB]
    with np.errstate(invalid="ignore"): nt = (npost < 0.35) & (npost - npre < -0.30)
    d = R["damage"][s, :WB].astype(bool); n_in_dmg += int((nt & d).sum())
    nh = nt.shape[0] // 10; nt100[r // 10:r // 10 + nh] = nt.reshape(nh, 10, WB // 10, 10).mean((1, 3))
keep = lab & ~(dmg & (nt100 >= 0.05))
res = {"near_total_km2_inside_damage": round(n_in_dmg * 1e-4, 1),
       "damage_blocks_100m": int((lab & dmg).sum()), "damage_blocks_removed": int((lab & dmg & (nt100 >= 0.05)).sum())}
for k in (A, B, "nisar_076:HV", "nisar_055:HV", "s1_92_2026:VH", "s1_19_2026:VH", "B 2025 control: S1 VH (both orbits)"):
    res[k] = {"auc_all_blocks": round(auc(c[k][lab], dmg[lab]), 3), "auc_without_near_total": round(auc(c[k][keep], dmg[keep]), 3)}
out["near_total"] = res; print(json.dumps(res, indent=1))
json.dump(out, open("docs/pipeline/sensitivity.json", "w"), indent=1)
