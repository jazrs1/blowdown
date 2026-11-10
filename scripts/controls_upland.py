"""Controls step 3 (upland main table) and step 4 (persistence, salvage).
Step 3: NISAR stack (A both tracks; track 76) vs S1 VH with October-only posts (o19 09-28->10-22, o92 mean(09-21,10-03)->10-27),
  at 30 m (per-date S1 from data/controls_ee_30.npz) and 100 m (data/s1_perdate_100.npz), all forest and upland only,
  with 10 km block bootstrap of AUC(NISAR) - AUC(S1).
Step 4: contrast = mean recentred dB difference in damage blocks minus intact blocks, per post date, for upland blocks and
  for woody-wetland blocks. S1 VH per orbit: each post date vs that orbit's pre-storm average. NISAR track 76 HV/HH:
  10-05->10-17 and 10-05->10-29; no-storm pairs B and C as reference levels.
Salvage: S2 medians 10-11..10-29 (p1) vs 10-30..11-10 (p2) at 30 m: clearing-like = ndvi_p2 < 0.35 and ndvi_p2 - ndvi_p1 < -0.15.
Writes docs/pipeline/controls_upland.json and docs/pipeline/fig_persistence.png."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import rankdata
E = np.load("data/controls_ee_30.npz"); K = np.load("data/controls_coarse.npz"); P100 = np.load("data/s1_perdate_100.npz")
def auc(s, y):
    ok = np.isfinite(s); s, y = s[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan
    rk = rankdata(s); return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)
def mean(*a):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(a), 0)
def labels(res, dom):
    d, i = (f"dmg_{res}", f"itc_{res}") if dom == "all" else (f"dmg_u_{res}", f"itc_u_{res}")
    yd = K[d] >= 0.5; return yd, yd | ((K[i] >= 0.9) & ~yd)
rng = np.random.default_rng(11); out = {"main_table": {}, "persistence": {}, "salvage": {}}
def s1(res, o, pre, post):
    src = (lambda d: E[f"VH_{o}_2026-{d}"]) if res == 30 else (lambda d: P100[f"VH_{o}_2026-{d}"])
    forest = K[f"ft_{res}"] > 0; d = db(mean(*[src(x) for x in post])) - db(mean(*[src(x) for x in pre]))
    return d - np.nanmedian(d[forest & np.isfinite(d)])
for res in (30, 100):
    c = np.load(f"data/coarse_{res}.npz")
    assert c["ft"].shape == K[f"ft_{res}"].shape and (c["ft"] == K[f"ft_{res}"]).mean() > 0.999, "grid mismatch"
    s1oct = mean(s1(res, 19, ["09-28"], ["10-22"]), s1(res, 92, ["09-21", "10-03"], ["10-27"]))
    tid = (np.arange(s1oct.shape[0])[:, None] // (10000 // res)) * 1000 + (np.arange(s1oct.shape[1])[None, :] // (10000 // res))
    for dom in ("all", "upland"):
        yd, lab = labels(res, dom)
        for an, a in (("NISAR HV stack, both tracks", c["A: NISAR HV (both tracks)"]), ("NISAR HV stack, track 76", c["nisar_076:HV"])):
            m = lab & np.isfinite(a) & np.isfinite(s1oct); av, bv, yv, tv = a[m], s1oct[m], yd[m], tid[m]
            o = np.argsort(tv); av, bv, yv, tv = av[o], bv[o], yv[o], tv[o]
            tiles, st = np.unique(tv, return_index=True); en = np.r_[st[1:], len(tv)]; bs = []
            for _ in range(300 if res == 100 else 150):
                pk = rng.integers(0, len(tiles), len(tiles)); ix = np.concatenate([np.arange(st[q], en[q]) for q in pk])
                bs.append(auc(av[ix], yv[ix]) - auc(bv[ix], yv[ix]))
            lo, hi = np.nanpercentile(bs, [2.5, 97.5]); a1, b1 = auc(av, yv), auc(bv, yv)
            k = f"{an} vs S1 VH Oct-only | {res} m | {dom}"
            out["main_table"][k] = {"auc_nisar": round(a1, 3), "auc_s1_oct": round(b1, 3), "diff": round(a1 - b1, 3),
                                    "ci95_block": [round(float(lo), 3), round(float(hi), 3)], "n": int(m.sum()), "n_damage": int(yv.sum())}
            print(k, out["main_table"][k], flush=True)
# ---- persistence
POSTS = {19: (["09-28"], ["10-22", "11-03"]), 92: (["09-21", "10-03"], ["10-27", "11-08"])}
def contrast(d, yd, lab, extra):
    m = lab & extra & np.isfinite(d)
    return round(float(np.nanmean(d[m & yd]) - np.nanmean(d[m & ~yd])), 2), int((m & yd).sum()), int((m & ~yd).sum())
for res in (30, 100):
    for dom in ("upland", "woody_wetland"):
        yd, lab = labels(res, "upland" if dom == "upland" else "all")
        extra = np.ones_like(yd) if dom == "upland" else (K[f"ft_{res}"] == 4)
        rec = {}
        for o, (pre, posts) in POSTS.items():
            for pd in posts: rec[f"S1 VH o{o} 2026-{pd}"] = contrast(s1(res, o, pre, [pd]), yd, lab, extra)
        for p in ("HV", "HH"):
            for n, lbl in (("A storm 10-05->10-17", "NISAR {p} t76 2026-10-17 (pre 10-05)"), ("persist 10-05->10-29", "NISAR {p} t76 2026-10-29 (pre 10-05)"),
                           ("B no storm 2025-10-22->11-03", "NISAR {p} no-storm B (2025)"), ("C no storm 2026-09-11->09-23", "NISAR {p} no-storm C (2026 pre)")):
                rec[lbl.format(p=p)] = contrast(K[f"{n}|{p}|{res}"], yd, lab, extra)
        out["persistence"][f"{dom} | {res} m"] = rec; print(dom, res, json.dumps(rec), flush=True)
# ---- figure (30 m)
fig, ax = plt.subplots(1, 2, figsize=(13, 5), sharey=True, constrained_layout=True)
day = lambda s: (np.datetime64("2026-" + s) - np.datetime64("2026-10-01")).astype(int)
for a, dom in zip(ax, ("upland", "woody_wetland")):
    rec = out["persistence"][f"{dom} | 30 m"]
    for o, col in ((19, "C1"), (92, "C3")):
        xs = POSTS[o][1]; a.plot([day(x) for x in xs], [rec[f"S1 VH o{o} 2026-{x}"][0] for x in xs], "o-", c=col, label=f"S1 VH orbit {o}")
    for p, col in (("HV", "C0"), ("HH", "C2")):
        a.plot([day("10-17"), day("10-29")], [rec[f"NISAR {p} t76 2026-10-17 (pre 10-05)"][0], rec[f"NISAR {p} t76 2026-10-29 (pre 10-05)"][0]], "s-", c=col, label=f"NISAR {p} track 76")
        for lbl, ls in (("B (2025)", ":"), ("C (2026 pre)", "--")):
            a.axhline(rec[f"NISAR {p} no-storm {lbl}"][0], c=col, ls=ls, lw=0.8)
    a.axhline(0, c="k", lw=0.5); a.set_xticks([day(x) for x in ("10-17", "10-22", "10-27", "10-29", "11-03", "11-08")], ["10-17", "10-22", "10-27", "10-29", "11-03", "11-08"], fontsize=8)
    a.set_title(f"{dom.replace('_', ' ')} (30 m blocks)"); a.set_xlabel("post date, 2026")
ax[0].set_ylabel("damage minus intact, recentred dB difference"); ax[1].legend(fontsize=8)
fig.suptitle("Does the signal persist? (thin lines: NISAR no-storm 12-day pairs, dotted = 2025, dashed = 2026 pre-storm)")
fig.savefig("docs/pipeline/fig_persistence.png", dpi=85); plt.close(fig)
# ---- salvage after 10-29
n2 = E["n_p2"]; p1, p2 = E["ndvi_p1"], E["ndvi_p2"]
with np.errstate(invalid="ignore"): sal = (p2 < 0.35) & (p2 - p1 < -0.15) & (n2 > 0)
dmg30, itc30, ft30 = K["dmg_30"], K["itc_30"], K["ft_30"] > 0
obs = np.isfinite(p1) & np.isfinite(p2) & (n2 > 0)
for nm, m in (("damage blocks (>=50% damage)", dmg30 >= 0.5), ("any-damage blocks (>0% damage)", dmg30 > 0), ("intact blocks (>=90% intact)", itc30 >= 0.9)):
    out["salvage"][nm] = {"blocks": int(m.sum()), "observed_both_windows": round(float((m & obs).sum() / max(m.sum(), 1)), 3),
                          "clearing_like_km2": round(float((m & sal).sum()) * 9e-4, 2), "share_of_observed": round(float((m & sal).sum() / max((m & obs).sum(), 1)), 4)}
out["salvage"]["mean_clear_obs_10-30_to_11-10_forest"] = round(float(np.nanmean(n2[ft30])), 2)
print(json.dumps(out["salvage"], indent=1))
# ---- 100 m pairs A/B/C against labels built without the 2025 optical term (definition as matched_check.py)
import h5py, grid as G
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
S = h5py.File("data/s2_stack.h5", "r"); R = h5py.File("data/reference.h5", "r")
fd = np.zeros((HB // 10, WB // 10), "float32"); fi = np.zeros_like(fd)
for r in range(0, HB, 600):
    s = slice(r, min(r + 600, HB)); fo = np.isin(S["cls"][s, :WB], (41, 42, 43, 90))
    with np.errstate(invalid="ignore"):
        dn = S["ndvi_post"][s, :WB] - S["ndvi_pre"][s, :WB]; dnbr = S["nbr_post"][s, :WB] - S["nbr_pre"][s, :WB]
        water = (S["water"][s, :WB] == 1) | (S["ndvi_post"][s, :WB] < 0.1)
    base = fo & ~water & (R["clearcut"][s, :WB] == 0) & np.isfinite(dnbr) & np.isfinite(dn)
    dm = base & (dnbr < -0.10) & (dn < -0.06); it = base & (dnbr > -0.03) & (dn > -0.02); nh = dm.shape[0] // 10
    fd[r // 10:r // 10 + nh] = dm.reshape(nh, 10, WB // 10, 10).mean((1, 3)); fi[r // 10:r // 10 + nh] = it.reshape(nh, 10, WB // 10, 10).mean((1, 3))
d2 = fd >= 0.5; lab2 = d2 | ((fi >= 0.9) & ~d2); out["labels_without_2025_100m"] = {}
for n in ("A storm 10-05->10-17", "B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23"):
    for p in ("HV", "HH"):
        dd = K[f"{n}|{p}|100"]; yd, lab = labels(100, "all")
        out["labels_without_2025_100m"][f"{n} | {p}"] = {"with_2025": round(auc(dd[lab], yd[lab]), 3), "without_2025": round(auc(dd[lab2], d2[lab2]), 3)}
print(json.dumps(out["labels_without_2025_100m"], indent=1))
json.dump(out, open("docs/pipeline/controls_upland.json", "w"), indent=1)
