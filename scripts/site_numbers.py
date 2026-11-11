"""Site sections 4-5 numbers recomputed with the held-out block + 2 km and the aerial tip + 2 km masked out (the
controls.md / pipeline.md numbers were computed over the whole grid, before the block existed). Same definitions as
controls_eval.py / controls_strict.py / controls_upland.py / matched_check.py; only the exclusion mask is added.
Writes docs/site/site_numbers.json and prints masked vs original."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np
from sklearn.metrics import roc_auc_score
import grid as G
RG = np.load("data/regions_30.npz"); ex30 = RG["heldout_excl"] | RG["tip_excl"]; H3, W3 = ex30.shape
ex10 = np.repeat(np.repeat(ex30, 3, 0), 3, 1); ex100 = ex10.reshape(H3 * 3 // 10, 10, W3 * 3 // 10, 10).any((1, 3))
K = np.load("data/controls_coarse.npz"); E = np.load("data/controls_ee_30.npz")
def auc(s, y, m):
    m = m & np.isfinite(s); return round(float(roc_auc_score(y[m], s[m])), 3)
out = {"storm_vs_control_HV": {}, "persistence_30m": {}, "nisar_t76_vs_s1_oct_100m": {}}
for res, ex in ((30, ex30), (100, ex100)):
    yd = K[f"dmg_{res}"] >= 0.5; lab = (yd | ((K[f"itc_{res}"] >= 0.9) & ~yd)) & ~ex
    up = K[f"upl_{res}"] >= 0.9; ydu = (K[f"dmg_u_{res}"] >= 0.5) & up; labu = (ydu | ((K[f"itc_u_{res}"] >= 0.9) & ~ydu)) & up & ~ex
    for n, key in (("storm", "A storm 10-05->10-17"), ("nostorm_2026", "C no storm 2026-09-11->09-23"), ("nostorm_2025", "B no storm 2025-10-22->11-03")):
        d = K[f"{key}|HV|{res}"]
        out["storm_vs_control_HV"][f"{n} | all forest | {res} m"] = auc(d, yd, lab)
        out["storm_vs_control_HV"][f"{n} | strict upland | {res} m"] = auc(d, ydu, labu)
# persistence (30 m): upland = looser upland labels as controls_upland; wetland = all labels & woody wetland
forest = K["ft_30"] > 0
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"): return 10 * np.log10(x)
def s1(o, pre, post):
    with np.errstate(invalid="ignore"):
        d = db(np.nanmean(np.stack([E[f"VH_{o}_2026-{x}"] for x in post]), 0)) - db(np.nanmean(np.stack([E[f"VH_{o}_2026-{x}"] for x in pre]), 0))
    return d - np.nanmedian(d[forest & ~ex30 & np.isfinite(d)])
for dom in ("upland", "woody_wetland"):
    if dom == "upland": yd = K["dmg_u_30"] >= 0.5; lab = (yd | ((K["itc_u_30"] >= 0.9) & ~yd)) & ~ex30
    else: yd = K["dmg_30"] >= 0.5; lab = (yd | ((K["itc_30"] >= 0.9) & ~yd)) & ~ex30 & (K["ft_30"] == 4)
    def con(d): m = lab & np.isfinite(d); return round(float(d[m & yd].mean() - d[m & ~yd].mean()), 2)
    rec = {}
    for p in ("HV", "HH"):
        rec[f"NISAR {p} post 10-17"] = con(K[f"A storm 10-05->10-17|{p}|30"]); rec[f"NISAR {p} post 10-29"] = con(K[f"persist 10-05->10-29|{p}|30"])
        rec[f"NISAR {p} no-storm 2025"] = con(K[f"B no storm 2025-10-22->11-03|{p}|30"]); rec[f"NISAR {p} no-storm 2026"] = con(K[f"C no storm 2026-09-11->09-23|{p}|30"])
    rec["S1 VH o92 post 10-27"] = con(s1(92, ["09-21", "10-03"], ["10-27"])); rec["S1 VH o92 post 11-08"] = con(s1(92, ["09-21", "10-03"], ["11-08"]))
    out["persistence_30m"][dom] = rec
# NISAR track 76 HV stack vs S1 VH Oct-only, 100 m (matched_check definition)
c = np.load("data/coarse_100.npz"); P = np.load("data/s1_perdate_100.npz"); f100 = c["ft"] > 0
def d100(o, pre, post):
    with np.errstate(invalid="ignore"):
        d = db(np.nanmean(np.stack([P[f"VH_{o}_2026-{x}"] for x in post]), 0)) - db(np.nanmean(np.stack([P[f"VH_{o}_2026-{x}"] for x in pre]), 0))
    return d - np.nanmedian(d[f100 & np.isfinite(d)])
with np.errstate(invalid="ignore"): s1oct = np.nanmean(np.stack([d100(19, ["09-28"], ["10-22"]), d100(92, ["09-21", "10-03"], ["10-27"])]), 0)
yd = c["dmg"] >= 0.5; lab = (yd | ((c["itc"] >= 0.9) & ~yd)) & ~ex100
a = c["nisar_076:HV"]; both = lab & np.isfinite(a) & np.isfinite(s1oct)
out["nisar_t76_vs_s1_oct_100m"] = {"nisar_t76_HV": auc(a, yd, both), "s1_VH_oct": auc(s1oct, yd, both), "n_blocks": int(both.sum())}
out["note"] = "held-out block + 2 km and aerial tip + 2 km excluded; otherwise identical to the controls/pipeline definitions"
json.dump(out, open("docs/site/site_numbers.json", "w"), indent=1); print(json.dumps(out, indent=1))
