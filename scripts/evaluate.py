"""Step 5: how well each radar difference separates the provisional damage mask from intact forest.
- 10 m: stratified random sample of damage / intact pixels (same pixels for every arm).
- 30 m, 100 m: block means in LINEAR power of the 10 m pre/post layers, then dB difference, recentred on the forest
  median at that resolution. Block is 'damage' if >= 50% of its 10 m pixels are damage, 'intact' if >= 90% are intact.
- AUC = Mann-Whitney (rank) statistic with score = recentred difference (higher = more damage-like).
- Combined arms: A = mean of NISAR HV over both tracks, B = mean of S1 VH over both orbits (2026); B_2025 control.
- Paired A vs B comparison on pixels valid in both, with bootstrap CI of the AUC difference.
Writes docs/pipeline/auc.json, data/coarse_30.npz, data/coarse_100.npz, data/threshold_maps_30.npz (figures/tables: pipeline_figures.py)."""
import json, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, psutil
from scipy.stats import rankdata
import grid as G
t0 = time.time()
L = h5py.File("data/layers.h5", "r"); R = h5py.File("data/reference.h5", "r")
ARMS = [(g, p) for g in ("nisar_076", "nisar_055", "nisar_076_p23", "nisar_055_p23", "nisar_076_pre0923", "nisar_076_pre1005") for p in ("HH", "HV")] + \
       [(f"s1_{o}_{y}", p) for y in (2026, 2025) for o in (19, 92) for p in ("VV", "VH")]
ARMS = [(g, p) for g, p in ARMS if g in L]
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300      # analysis extent divisible by 30 and 100 px
BLK = 600
FT = {1: "evergreen", 2: "deciduous", 3: "mixed", 4: "woody_wetland"}

# ---- sampling rates at 10 m from reference counts
nd = ni = 0
for r in range(0, HB, BLK):
    nd += int(R["damage"][r:min(r + BLK, HB), :WB].sum()); ni += int(R["intact"][r:min(r + BLK, HB), :WB].sum())
pd, pi = min(1, 1.5e6 / max(nd, 1)), min(1, 1.5e6 / max(ni, 1))
rng = np.random.default_rng(42)
S = {"cls": [], "ft": [], **{f"{g}:{p}": [] for g, p in ARMS}}
coarse = {k: {"dmg": [], "itc": [], "ft": [], **{f"{g}:{p}": [] for g, p in ARMS}} for k in (3, 10)}

def bmean(a, k):
    h, w = a.shape; v = a.reshape(h // k, k, w // k, k)
    n = np.isfinite(v).sum((1, 3)); s = np.nansum(v, (1, 3))
    return np.where(n >= k * k / 2, s / np.maximum(n, 1), np.nan)

for r in range(0, HB, BLK):
    s = slice(r, min(r + BLK, HB))
    dmg = R["damage"][s, :WB].astype(bool); itc = R["intact"][s, :WB].astype(bool); ft = R["ftype"][s, :WB]
    u = rng.random(dmg.shape); pick = (dmg & (u < pd)) | (itc & (u < pi))
    S["cls"].append(dmg[pick].astype("int8")); S["ft"].append(ft[pick])
    for k, c in coarse.items():
        c["dmg"].append(bmean(dmg.astype("float32"), k)); c["itc"].append(bmean(itc.astype("float32"), k))
        cnt = np.stack([bmean((ft == t).astype("float32"), k) for t in (1, 2, 3, 4)])
        c["ft"].append(np.where(cnt.max(0) > 0, cnt.argmax(0) + 1, 0).astype("uint8"))
    for g, p in ARMS:
        S[f"{g}:{p}"].append(L[g][f"{p}_diffc"][s, :WB][pick])
        pre = 10 ** (L[g][f"{p}_pre"][s, :WB] / 10); post = 10 ** (L[g][f"{p}_post"][s, :WB] / 10)
        for k, c in coarse.items():
            with np.errstate(divide="ignore", invalid="ignore"):
                c[f"{g}:{p}"].append((10 * np.log10(bmean(post, k)) - 10 * np.log10(bmean(pre, k))).astype("float32"))
S = {k: np.concatenate(v) for k, v in S.items()}
for k, c in coarse.items():
    for n in list(c): c[n] = np.vstack(c[n])
    forest_blk = (c["ft"] > 0)
    for g, p in ARMS:          # recentre on forest median at this resolution
        a = c[f"{g}:{p}"]; c[f"{g}:{p}"] = a - np.nanmedian(a[forest_blk & np.isfinite(a)])

def combine(d, keys):
    st = np.stack([d[k] for k in keys if k in d])
    with np.errstate(invalid="ignore"): return np.nanmean(st, 0)
COMB = {"A: NISAR HV (both tracks)": ["nisar_076:HV", "nisar_055:HV"], "A: NISAR HH (both tracks)": ["nisar_076:HH", "nisar_055:HH"],
        "B: S1 VH (both orbits)": ["s1_19_2026:VH", "s1_92_2026:VH"], "B: S1 VV (both orbits)": ["s1_19_2026:VV", "s1_92_2026:VV"],
        "B 2025 control: S1 VH (both orbits)": ["s1_19_2025:VH", "s1_92_2025:VH"],
        "A sensitivity: NISAR HV, P05023 scenes only": ["nisar_076_p23:HV", "nisar_055_p23:HV"]}
for name, keys in COMB.items():
    S[name] = combine(S, keys)
    for c in coarse.values(): c[name] = combine(c, keys)
for k, c in coarse.items(): np.savez_compressed(f"data/coarse_{k*10}.npz", **c)

def auc(score, y):
    ok = np.isfinite(score); s, y = score[ok], y[ok]; n1 = int(y.sum()); n0 = len(y) - n1
    if n1 < 30 or n0 < 30: return np.nan, n1, n0
    rk = rankdata(s); return float((rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), n1, n0

rows = []
def evaluate(label, res, score, y, ft):
    for tname, tm in [("all", np.ones_like(y, bool))] + [(FT[t], ft == t) for t in (1, 2, 4)]:
        sc, yy = score[tm], y[tm]; a, n1, n0 = auc(sc, yy)
        ok = np.isfinite(sc)
        d, i = sc[ok & (yy == 1)], sc[ok & (yy == 0)]
        rows.append({"arm": label, "res_m": res, "forest_type": tname, "auc": None if np.isnan(a) else round(a, 3),
                     "n_damage": n1, "n_intact": n0,
                     "damage_mean_dB": round(float(d.mean()), 2) if d.size else None, "damage_sd_dB": round(float(d.std()), 2) if d.size else None,
                     "intact_mean_dB": round(float(i.mean()), 2) if i.size else None, "intact_sd_dB": round(float(i.std()), 2) if i.size else None,
                     "delta_dB": round(float(d.mean() - i.mean()), 2) if d.size and i.size else None})

labels = [f"{g}:{p}" for g, p in ARMS] + list(COMB)
y10, ft10 = S["cls"], S["ft"]
for lab in labels: evaluate(lab, 10, S[lab], y10, ft10)
for k, c in coarse.items():
    lab_d = c["dmg"] >= 0.5; lab_i = (c["itc"] >= 0.9) & ~lab_d
    m = lab_d | lab_i; y = lab_d[m].astype("int8"); ftc = c["ft"][m]
    for lab in labels: evaluate(lab, k * 10, c[lab][m], y, ftc)

# ---- paired A vs B (HV vs VH, both-valid pixels), bootstrap CI on AUC difference
paired = []
for res in (10, 30, 100):
    if res == 10: a, b, y = S["A: NISAR HV (both tracks)"], S["B: S1 VH (both orbits)"], y10
    else:
        c = coarse[res // 10]; lab_d = c["dmg"] >= 0.5; m = lab_d | ((c["itc"] >= 0.9) & ~lab_d)
        a, b, y = c["A: NISAR HV (both tracks)"][m], c["B: S1 VH (both orbits)"][m], lab_d[m].astype("int8")
    ok = np.isfinite(a) & np.isfinite(b); a, b, y = a[ok], b[ok], y[ok]
    aa, ab = auc(a, y)[0], auc(b, y)[0]
    bs = []; br = np.random.default_rng(1); n = len(y); m = min(n, 200000)
    for _ in range(200):
        ix = br.integers(0, n, m); bs.append(auc(a[ix], y[ix])[0] - auc(b[ix], y[ix])[0])
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    paired.append({"res_m": res, "n": int(n), "n_damage": int(y.sum()), "auc_A_NISAR_HV": round(aa, 3), "auc_B_S1_VH": round(ab, 3),
                   "diff": round(aa - ab, 3), "ci95": [round(float(lo), 3), round(float(hi), 3)]})
    print("paired", paired[-1], flush=True)

# ---- threshold maps at 30 m (Youden-optimal threshold on the 30 m labelled blocks)
c = coarse[3]; lab_d = c["dmg"] >= 0.5; m = lab_d | ((c["itc"] >= 0.9) & ~lab_d)
thr = {}
for name in ("A: NISAR HV (both tracks)", "B: S1 VH (both orbits)"):
    s, y = c[name][m], lab_d[m]; ok = np.isfinite(s); s, y = s[ok], y[ok]
    qs = np.quantile(s, np.linspace(0.05, 0.95, 91))
    J = [((s[y] > q).mean() - (s[~y] > q).mean()) for q in qs]; q = float(qs[int(np.argmax(J))])
    thr[name] = {"threshold_dB": round(q, 2), "tpr": round(float((s[y] > q).mean()), 3), "fpr": round(float((s[~y] > q).mean()), 3)}
np.savez_compressed("data/threshold_maps_30.npz", A=(c["A: NISAR HV (both tracks)"] > thr["A: NISAR HV (both tracks)"]["threshold_dB"]) & (c["ft"] > 0),
                    B=(c["B: S1 VH (both orbits)"] > thr["B: S1 VH (both orbits)"]["threshold_dB"]) & (c["ft"] > 0),
                    validA=np.isfinite(c["A: NISAR HV (both tracks)"]), validB=np.isfinite(c["B: S1 VH (both orbits)"]),
                    dmg=c["dmg"], ft=c["ft"])
mi = psutil.Process().memory_info()
out = {"rows": rows, "paired_A_vs_B": paired, "thresholds_30m": thr, "sample_rates": {"damage": pd, "intact": pi},
       "n_damage_10m": nd, "n_intact_10m": ni, "seconds": round(time.time() - t0, 1), "peak_ram_GB": round(mi.peak_wset / 1e9, 2)}
json.dump(out, open("docs/pipeline/auc.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
