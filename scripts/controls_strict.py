"""Strict-upland rescore: the upland labels in controls_eval.py let a damage block be up to half non-upland. Here a block
must also be >= 90% upland forest (upl_{res} >= 0.9) to count, for both classes. Pairs A/B/C (HV, HH: AUC, contrast dB) and
the upland main table (NISAR HV stack vs S1 VH Oct-only), with 10 km block bootstrap on the differences.
Also: orbit 19 raw forest-median VH shift (before recentring) of each post date vs 09-28, to see whether 11-03 brightened as a whole.
Writes docs/pipeline/controls_strict.json."""
import json
import numpy as np
from scipy.stats import rankdata
K = np.load("data/controls_coarse.npz"); E = np.load("data/controls_ee_30.npz"); P100 = np.load("data/s1_perdate_100.npz")
def auc(s, y):
    ok = np.isfinite(s); s, y = s[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan
    rk = rankdata(s); return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)
def mean(*a):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(a), 0)
rng = np.random.default_rng(13); out = {"pairs": {}, "main_table": {}, "boot": {}}
def boot(a, b, yd, lab, res, n):
    m = lab & np.isfinite(a) & np.isfinite(b); t = 10000 // res
    tid = (np.arange(a.shape[0])[:, None] // t) * 1000 + (np.arange(a.shape[1])[None, :] // t)
    av, bv, yv, tv = a[m], b[m], yd[m], tid[m]; o = np.argsort(tv); av, bv, yv, tv = av[o], bv[o], yv[o], tv[o]
    tiles, st = np.unique(tv, return_index=True); en = np.r_[st[1:], len(tv)]; bs = []
    for _ in range(n):
        pk = rng.integers(0, len(tiles), len(tiles)); ix = np.concatenate([np.arange(st[q], en[q]) for q in pk])
        bs.append(auc(av[ix], yv[ix]) - auc(bv[ix], yv[ix]))
    lo, hi = np.nanpercentile(bs, [2.5, 97.5]); a1, b1 = auc(av, yv), auc(bv, yv)
    return {"auc_first": round(a1, 3), "auc_second": round(b1, 3), "diff": round(a1 - b1, 3), "ci95_block": [round(float(lo), 3), round(float(hi), 3)], "n_damage": int(yv.sum()), "n": int(m.sum())}
for res in (30, 100):
    up = K[f"upl_{res}"] >= 0.9; yd = (K[f"dmg_u_{res}"] >= 0.5) & up; lab = (yd | ((K[f"itc_u_{res}"] >= 0.9) & ~yd)) & up
    for n in ("A storm 10-05->10-17", "B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23", "persist 10-05->10-29"):
        for p in ("HV", "HH"):
            d = K[f"{n}|{p}|{res}"]; m = lab & np.isfinite(d)
            out["pairs"][f"{n} | {p} | {res} m"] = {"auc": round(auc(d[m], yd[m]), 3), "contrast_dB": round(float(d[m & yd].mean() - d[m & ~yd].mean()), 2),
                                                    "n_damage": int((m & yd).sum()), "n_intact": int((m & ~yd).sum())}
    for p in ("HV", "HH"):
        for cn in ("B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23"):
            out["boot"][f"A minus {cn[0]} | {p} | {res} m"] = boot(K[f"A storm 10-05->10-17|{p}|{res}"], K[f"{cn}|{p}|{res}"], yd, lab, res, 300 if res == 100 else 150)
    c = np.load(f"data/coarse_{res}.npz"); forest = K[f"ft_{res}"] > 0
    src = (lambda d: E[f"VH_{d}"]) if res == 30 else (lambda d: P100[f"VH_{d}"])
    def s1(o, pre, post):
        d = db(mean(*[src(f"{o}_2026-{x}") for x in post])) - db(mean(*[src(f"{o}_2026-{x}") for x in pre])); return d - np.nanmedian(d[forest & np.isfinite(d)])
    s1oct = mean(s1(19, ["09-28"], ["10-22"]), s1(92, ["09-21", "10-03"], ["10-27"]))
    for an, a in (("NISAR HV stack, both tracks", c["A: NISAR HV (both tracks)"]), ("NISAR HV stack, track 76", c["nisar_076:HV"])):
        out["main_table"][f"{an} vs S1 VH Oct-only | {res} m"] = boot(a, s1oct, yd, lab, res, 300 if res == 100 else 150)
    if res == 30:   # orbit 19 raw forest-median shift, blocks valid on all three dates
        ok = forest & np.isfinite(E["VH_19_2026-09-28"]) & np.isfinite(E["VH_19_2026-10-22"]) & np.isfinite(E["VH_19_2026-11-03"])
        out["orbit19_raw_forest_median_shift_dB"] = {d: round(float(np.median(db(E[f"VH_19_2026-{d}"][ok]) - db(E["VH_19_2026-09-28"][ok]))), 3) for d in ("10-22", "11-03")}
        ok92 = forest & np.all([np.isfinite(E[f"VH_92_2026-{d}"]) for d in ("09-21", "10-03", "10-27", "11-08")], 0)
        out["orbit92_raw_forest_median_shift_dB_vs_0921"] = {d: round(float(np.median(db(E[f"VH_92_2026-{d}"][ok92]) - db(E["VH_92_2026-09-21"][ok92]))), 3) for d in ("10-03", "10-27", "11-08")}
print(json.dumps(out, indent=1))
json.dump(out, open("docs/pipeline/controls_strict.json", "w"), indent=1)
