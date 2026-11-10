"""Controls steps 2-3 (NISAR track 76 frame 17, 12-day pairs vs no-storm 12-day pairs).
Scoring as evaluate.py: 10 m = stratified sample of damage/intact pixels (same pixels for every pair), dB post-pre
recentred on the forest median; 30 m / 100 m = block mean of linear power, dB difference, recentred on the forest-block
median; labels: block damage if >= 50% damage pixels, intact if >= 90% intact. AUC = Mann-Whitney, higher = damage.
Upland domain: NLCD evergreen or deciduous (reference ftype 1/2) and MERIT HAND > 5 m (data/controls_ee_30.npz, 30 m
nearest-neighbour, repeated to 10 m). Upland blocks use the fractions of damage&upland / intact&upland pixels with the same
50% / 90% thresholds, so an upland block is mostly upland forest.
Pairs: A storm 10-05->10-17; B no storm 2025-10-22->2025-11-03; C no storm 2026-09-11->09-23; plus the 4-scene headline
(rebuild check against auc.json), 09-23->10-05 (pre-pre), 10-17->10-29 (post-post) and 10-05->10-29 (persistence).
Block bootstrap (10 km tiles, 300 draws) on AUC(A) - AUC(B), AUC(A) - AUC(C) at 30 / 100 m, all and upland.
Writes docs/pipeline/controls_eval.json and data/controls_coarse.npz (recentred differences + labels, for controls_upland.py)."""
import json, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np
from scipy.stats import rankdata
import grid as G
t0 = time.time()
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300; BLK = 600
PAIRS = {"A storm 10-05->10-17": (["2026-10-05"], ["2026-10-17"]),
         "B no storm 2025-10-22->11-03": (["2025-10-22"], ["2025-11-03"]),
         "C no storm 2026-09-11->09-23": (["2026-09-11"], ["2026-09-23"]),
         "headline 09-23,10-05->10-17,10-29": (["2026-09-23", "2026-10-05"], ["2026-10-17", "2026-10-29"]),
         "pre-pre 09-23->10-05": (["2026-09-23"], ["2026-10-05"]),
         "post-post 10-17->10-29": (["2026-10-17"], ["2026-10-29"]),
         "persist 10-05->10-29": (["2026-10-05"], ["2026-10-29"])}
POLS = ("HV", "HH"); KEYS = [(n, p) for n in PAIRS for p in POLS]
DATES = sorted({d for a, b in PAIRS.values() for d in a + b})
F = {d: h5py.File(f"data/stack/076_{d}.h5", "r") for d in DATES}
R = h5py.File("data/reference.h5", "r")
E = np.load("data/controls_ee_30.npz"); hnd30 = E["hnd"]
FT = {1: "evergreen", 2: "deciduous", 4: "woody_wetland"}

def bmean(a, k):
    h, w = a.shape; v = a.reshape(h // k, k, w // k, k)
    n = np.isfinite(v).sum((1, 3)); s = np.nansum(v, (1, 3))
    return np.where(n >= k * k / 2, s / np.maximum(n, 1), np.nan)
def dbd(pre, post):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(post) - 10 * np.log10(pre)
def mean_(xs):
    with np.errstate(invalid="ignore"): return np.nanmean(np.stack(xs), 0) if len(xs) > 1 else xs[0]

# pass 1: sampling rates (same rule as evaluate.py)
nd = ni = 0
for r in range(0, HB, BLK):
    nd += int(R["damage"][r:min(r + BLK, HB), :WB].sum()); ni += int(R["intact"][r:min(r + BLK, HB), :WB].sum())
pd, pi = min(1, 1.5e6 / max(nd, 1)), min(1, 1.5e6 / max(ni, 1))
rng = np.random.default_rng(42)
S = {"cls": [], "ft": [], "upl": [], **{k: [] for k in KEYS}}; FM = {k: [] for k in KEYS}
C = {k: {"dmg": [], "itc": [], "dmg_u": [], "itc_u": [], "ft": [], "upl": [], **{(d, p): [] for d in DATES for p in POLS}} for k in (3, 10)}
n_dmg = n_dmg_upl = n_for = n_for_upl = 0
for r in range(0, HB, BLK):
    s = slice(r, min(r + BLK, HB)); h = s.stop - s.start
    dmg = R["damage"][s, :WB].astype(bool); itc = R["intact"][s, :WB].astype(bool); ft = R["ftype"][s, :WB]
    upl = np.isin(ft, (1, 2)) & np.repeat(np.repeat(hnd30[r // 3:r // 3 + h // 3] > 5, 3, 0), 3, 1)
    n_dmg += int(dmg.sum()); n_dmg_upl += int((dmg & upl).sum()); n_for += int((ft > 0).sum()); n_for_upl += int(upl.sum())
    u = rng.random(dmg.shape); pick = (dmg & (u < pd)) | (itc & (u < pi)); fpick = (ft > 0) & (u > 0.98)
    S["cls"].append(dmg[pick]); S["ft"].append(ft[pick]); S["upl"].append(upl[pick])
    pw = {(d, p): F[d][p][s, :WB] for d in DATES for p in POLS}
    for (n, p) in KEYS:
        pre, post = PAIRS[n]
        dd = dbd(mean_([pw[(d, p)] for d in pre]), mean_([pw[(d, p)] for d in post]))
        S[(n, p)].append(dd[pick].astype("float32")); FM[(n, p)].append(dd[fpick])
    for k, c in C.items():
        for nm, a in (("dmg", dmg), ("itc", itc), ("dmg_u", dmg & upl), ("itc_u", itc & upl), ("upl", upl)): c[nm].append(bmean(a.astype("float32"), k))
        cnt = np.stack([bmean((ft == t).astype("float32"), k) for t in (1, 2, 3, 4)])
        c["ft"].append(np.where(cnt.max(0) > 0, cnt.argmax(0) + 1, 0).astype("uint8"))
        for key, v in pw.items(): c[key].append(bmean(v, k).astype("float32"))
    if r % 3000 == 0: print("rows", r, round(time.time() - t0), flush=True)
S = {k: np.concatenate(v) for k, v in S.items()}
for k in KEYS:
    f = np.concatenate(FM[k]); S[k] = S[k] - np.nanmedian(f[np.isfinite(f)])
D = {}
for k, c in C.items():
    for nm in list(c): c[nm] = np.vstack(c[nm])
    forest = c["ft"] > 0
    for (n, p) in KEYS:
        pre, post = PAIRS[n]
        dd = dbd(mean_([c[(d, p)] for d in pre]), mean_([c[(d, p)] for d in post]))
        D[(k, n, p)] = dd - np.nanmedian(dd[forest & np.isfinite(dd)])

def auc(sc, y):
    ok = np.isfinite(sc); sc, y = sc[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan, n1, n0
    rk = rankdata(sc); return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), n1, n0
rows = []
def ev(n, p, res, dom, sc, y, ft):
    for tn, tm in [("all", np.ones_like(y))] + [(FT[t], ft == t) for t in FT]:
        a, n1, n0 = auc(sc[tm], y[tm]); ok = np.isfinite(sc) & tm
        dmean = np.nanmean(sc[ok & y]) if n1 else np.nan; imean = np.nanmean(sc[ok & ~y]) if n0 else np.nan
        rows.append({"pair": n, "pol": p, "res_m": res, "domain": dom, "forest_type": tn, "auc": None if np.isnan(a) else round(a, 3),
                     "delta_dB": None if np.isnan(dmean - imean) else round(float(dmean - imean), 2), "n_damage": n1, "n_intact": n0})
for (n, p) in KEYS:
    ev(n, p, 10, "all", S[(n, p)], S["cls"], S["ft"])
    u = S["upl"]; ev(n, p, 10, "upland", S[(n, p)][u], S["cls"][u], S["ft"][u])
    for k, c in C.items():
        for dom, dl, il in (("all", "dmg", "itc"), ("upland", "dmg_u", "itc_u")):
            yd = c[dl] >= 0.5; m = yd | ((c[il] >= 0.9) & ~yd)
            ev(n, p, k * 10, dom, D[(k, n, p)][m], yd[m], c["ft"][m])

# block bootstrap: A minus B, A minus C
boot = {}; br = np.random.default_rng(7)
for k, c in C.items():
    tsz = 1000 // k; tid = (np.arange(c["ft"].shape[0])[:, None] // tsz) * 1000 + (np.arange(c["ft"].shape[1])[None, :] // tsz)
    for dom, dl, il in (("all", "dmg", "itc"), ("upland", "dmg_u", "itc_u")):
        yd = c[dl] >= 0.5; lab = yd | ((c[il] >= 0.9) & ~yd)
        for p in POLS:
            a = D[(k, "A storm 10-05->10-17", p)]
            for cn in ("B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23"):
                b = D[(k, cn, p)]; m = lab & np.isfinite(a) & np.isfinite(b)
                av, bv, yv, tv = a[m], b[m], yd[m], tid[m]; o = np.argsort(tv); av, bv, yv, tv = av[o], bv[o], yv[o], tv[o]
                tiles, st = np.unique(tv, return_index=True); en = np.r_[st[1:], len(tv)]; bs = []
                for _ in range(300 if k == 10 else 150):
                    pk = br.integers(0, len(tiles), len(tiles)); ix = np.concatenate([np.arange(st[q], en[q]) for q in pk])
                    bs.append(auc(av[ix], yv[ix])[0] - auc(bv[ix], yv[ix])[0])
                lo, hi = np.nanpercentile(bs, [2.5, 97.5]); a1, b1 = auc(av, yv)[0], auc(bv, yv)[0]
                key = f"A minus {cn[0]} | {p} | {k*10} m | {dom}"
                boot[key] = {"auc_A": round(a1, 3), "auc_control": round(b1, 3), "diff": round(a1 - b1, 3),
                             "ci95_block": [round(float(lo), 3), round(float(hi), 3)], "n": int(m.sum()), "n_damage": int(yv.sum())}
                print(key, boot[key], flush=True)

# scene calibration: forest median dB per scene on 100 m forest blocks valid in every scene
c = C[10]; allok = (c["ft"] > 0) & np.all([np.isfinite(c[(d, p)]) for d in DATES for p in POLS], 0)
calib = {p: {d: round(float(np.median(10 * np.log10(c[(d, p)][allok]))), 3) for d in DATES} for p in POLS}; calib["n_blocks"] = int(allok.sum())
J = json.load(open("docs/pipeline/auc.json"))
ref = {r_["res_m"]: r_["auc"] for r_ in J["rows"] if r_["arm"] == "nisar_076:HV" and r_["forest_type"] == "all"}
mine = {r_["res_m"]: r_["auc"] for r_ in rows if r_["pair"].startswith("headline") and r_["pol"] == "HV" and r_["domain"] == "all" and r_["forest_type"] == "all"}
out = {"scenes": {d: {"source": F[d].attrs["source"], "spec": F[d].attrs["specVersion"].decode() if isinstance(F[d].attrs["specVersion"], bytes) else str(F[d].attrs["specVersion"])} for d in DATES},
       "upland_share": {"damage_km2": round(n_dmg * 1e-4, 1), "damage_in_upland_km2": round(n_dmg_upl * 1e-4, 1), "share_of_damage": round(n_dmg_upl / n_dmg, 3),
                        "forest_km2": round(n_for * 1e-4, 1), "upland_forest_km2": round(n_for_upl * 1e-4, 1), "share_of_forest": round(n_for_upl / n_for, 3),
                        "note": "analysis extent (HB x WB), reference forest classes"},
       "headline_rebuild_check": {"auc_json_nisar_076_HV": ref, "rebuilt": mine},
       "forest_median_dB_100m_common_blocks": calib, "rows": rows, "bootstrap": boot, "seconds": round(time.time() - t0)}
print(json.dumps({k: out[k] for k in ("scenes", "upland_share", "headline_rebuild_check", "forest_median_dB_100m_common_blocks")}, indent=1))
json.dump(out, open("docs/pipeline/controls_eval.json", "w"), indent=1)
sv = {}
for k, c in C.items():
    for nm in ("dmg", "itc", "dmg_u", "itc_u", "ft", "upl"): sv[f"{nm}_{k*10}"] = c[nm]
    for (n, p) in KEYS: sv[f"{n}|{p}|{k*10}"] = D[(k, n, p)]
np.savez_compressed("data/controls_coarse.npz", **sv)
