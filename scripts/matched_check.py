"""Two checks on the headline (100 m blocks, 10 km block bootstrap):
1) Date-matched S1: NISAR's posts end 10-29, the specified S1 posts run to 11-08. Build S1 VH with October posts only
   (orbit 19: 09-28 -> 10-22; orbit 92: mean(09-21, 10-03) -> 10-27) from data/s1_perdate_100.npz and compare with arm A.
   The same per-date file with all specified dates is scored too, to show it reproduces arm B.
2) Labels without the 2025 term: damage = dNBR < -0.10 & dNDVI26 < -0.06, intact = dNBR > -0.03 & dNDVI26 > -0.02
   (same forest/water/clearcut exclusions), to see whether the 2025 control's AUC comes from the label using 2025 data.
Writes docs/pipeline/matched_check.json."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy.stats import rankdata
import grid as G
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
def auc(s, y):
    ok = np.isfinite(s); s, y = s[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan
    rk = rankdata(s); return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
c = np.load("data/coarse_100.npz"); P = np.load("data/s1_perdate_100.npz"); forest = c["ft"] > 0
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)
def diffc(pre, post):
    d = db(post) - db(pre); return d - np.nanmedian(d[forest & np.isfinite(d)])
def mean(*a):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(a), 0)
v = lambda o, d: P[f"VH_{o}_2026-{d}"]
S1 = {"S1 VH Oct-only posts (o19 10-22, o92 10-27)": mean(diffc(v(19, "09-28"), v(19, "10-22")),
                                                         diffc(mean(v(92, "09-21"), v(92, "10-03")), v(92, "10-27"))),
      "S1 VH specified dates (rebuilt from per-date 100 m)": mean(diffc(v(19, "09-28"), mean(v(19, "10-22"), v(19, "11-03"))),
                                                               diffc(mean(v(92, "09-21"), v(92, "10-03")), mean(v(92, "10-27"), v(92, "11-08")))),
      "S1 VH orbit 92 only, Oct post 10-27": diffc(mean(v(92, "09-21"), v(92, "10-03")), v(92, "10-27"))}
A = {"A: NISAR HV (both tracks)": c["A: NISAR HV (both tracks)"], "NISAR HV track 76": c["nisar_076:HV"]}
rng = np.random.default_rng(5)
def compare(a, b, dmg, lab):
    m = lab & np.isfinite(a) & np.isfinite(b); t = 100
    tid = (np.arange(dmg.shape[0])[:, None] // t) * 1000 + (np.arange(dmg.shape[1])[None, :] // t)
    av, bv, yv, tv = a[m], b[m], dmg[m], tid[m]; o = np.argsort(tv); av, bv, yv, tv = av[o], bv[o], yv[o], tv[o]
    tiles, st = np.unique(tv, return_index=True); en = np.r_[st[1:], len(tv)]; bs = []
    for _ in range(300):
        pk = rng.integers(0, len(tiles), len(tiles)); ix = np.concatenate([np.arange(st[p], en[p]) for p in pk])
        bs.append(auc(av[ix], yv[ix]) - auc(bv[ix], yv[ix]))
    lo, hi = np.nanpercentile(bs, [2.5, 97.5]); a1, b1 = auc(av, yv), auc(bv, yv)
    return {"auc_A": round(a1, 3), "auc_B": round(b1, 3), "diff": round(a1 - b1, 3), "ci95_block": [round(float(lo), 3), round(float(hi), 3)], "n": int(m.sum())}
out = {"date_matched": {}, "labels_without_2025": {}}
dmg = c["dmg"] >= 0.5; lab = dmg | ((c["itc"] >= 0.9) & ~dmg)
for ka, a in A.items():
    for kb, b in S1.items():
        out["date_matched"][f"{ka} vs {kb}"] = r = compare(a, b, dmg, lab); print(ka, "|", kb, r, flush=True)

# ---- labels without the 2025 term, at 100 m
S = h5py.File("data/s2_stack.h5", "r"); R = h5py.File("data/reference.h5", "r")
fd = np.zeros((HB // 10, WB // 10), "float32"); fi = np.zeros_like(fd); d25 = {"damage": [], "intact": []}
for r in range(0, HB, 600):
    s = slice(r, min(r + 600, HB)); cls = S["cls"][s, :WB]; fo = np.isin(cls, (41, 42, 43, 90))
    with np.errstate(invalid="ignore"):
        dn = S["ndvi_post"][s, :WB] - S["ndvi_pre"][s, :WB]; dnbr = S["nbr_post"][s, :WB] - S["nbr_pre"][s, :WB]
        water = (S["water"][s, :WB] == 1) | (S["ndvi_post"][s, :WB] < 0.1)
    base = fo & ~water & (R["clearcut"][s, :WB] == 0) & np.isfinite(dnbr) & np.isfinite(dn)
    dm = base & (dnbr < -0.10) & (dn < -0.06); it = base & (dnbr > -0.03) & (dn > -0.02)
    nh = dm.shape[0] // 10
    fd[r // 10:r // 10 + nh] = dm.reshape(nh, 10, WB // 10, 10).mean((1, 3)); fi[r // 10:r // 10 + nh] = it.reshape(nh, 10, WB // 10, 10).mean((1, 3))
    d25v = S["dndvi25"][s, :WB]; rd, ri = R["damage"][s, :WB] == 1, R["intact"][s, :WB] == 1
    d25["damage"].append(d25v[rd][::20]); d25["intact"].append(d25v[ri][::20])
d2 = fd >= 0.5; lab2 = d2 | ((fi >= 0.9) & ~d2)
res = {"damage_blocks": int((lab2 & d2).sum()), "intact_blocks": int((lab2 & ~d2).sum()),
       "mean_dNDVI2025_in_reference_damage": round(float(np.nanmean(np.concatenate(d25["damage"]))), 4),
       "mean_dNDVI2025_in_reference_intact": round(float(np.nanmean(np.concatenate(d25["intact"]))), 4)}
for k in ("A: NISAR HV (both tracks)", "B: S1 VH (both orbits)", "B 2025 control: S1 VH (both orbits)", "nisar_076:HV", "s1_92_2026:VH"):
    res[k] = {"auc_labels_with_2025": round(auc(c[k][lab], dmg[lab]), 3), "auc_labels_without_2025": round(auc(c[k][lab2], d2[lab2]), 3)}
for t, nm in ((1, "evergreen"), (4, "woody_wetland")):
    m2 = lab2 & (c["ft"] == t)
    res[f"control AUC, {nm}, labels without 2025"] = round(auc(c["B 2025 control: S1 VH (both orbits)"][m2], d2[m2]), 3)
res["A minus B, labels without 2025"] = compare(c["A: NISAR HV (both tracks)"], c["B: S1 VH (both orbits)"], d2, lab2)
out["labels_without_2025"] = res; print(json.dumps(res, indent=1))
json.dump(out, open("docs/pipeline/matched_check.json", "w"), indent=1)
