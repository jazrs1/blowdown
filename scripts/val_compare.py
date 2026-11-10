"""Amendment 1, step 3: v1 vs v2 on validation tiles (inside the training region only).
Labels for every cut: v2 labels (forest cell in the Sentinel-2 damage mask = 1, any other forest cell = 0, flagged cells
excluded), so v1 and v2 are scored on identical cells. Cuts: full (all validation forest cells), in-band (inside the band),
outside-band; domains upland / wetland (and all). Scores: arms A, A76, B (thresholds), v1 and v2 GBM and U-Net arms C, D, E
(5-seed mean probability). Block bootstrap: 3.2 km blocks (106 x 106 cells, 9 per validation tile), 1000 resamples,
percentile 95% intervals, for each AUC and for the paired v2 - v1 difference. AUC is computed from per-block histograms on
2000 quantile bins of each score (ties within a bin count half), which matches the exact AUC to about 1e-4.
Reliability (in-band cut): 10 equal-width probability bins, observed share of damage-mask cells, Brier score, ECE.
Writes docs/models/val_compare.json and docs/models/fig_reliability_inband.png."""
import json, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, lightgbm as lgb, torch, torch.nn as nn, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score
t0 = time.time()
f = h5py.File("data/models/features_train.h5", "r"); S = np.load("data/models/split.npz"); RG = np.load("data/regions_30.npz")
lab = np.load("data/models/labels_v2.npz")["label"]; val = S["val"]; H, W = lab.shape
cells = val & (lab >= 0); idx = np.flatnonzero(cells.ravel()); y = lab.ravel()[idx] == 1
bd = RG["band"].ravel()[idx]; DOM = {"all": np.ones(len(idx), bool), "upland": RG["upland"].ravel()[idx], "wetland": RG["wetland"].ravel()[idx]}
CUT = {"full": np.ones(len(idx), bool), "in-band": bd, "outside-band": ~bd}
rr, cc = np.unravel_index(idx, (H, W)); blk = (rr // 106) * 1000 + (cc // 106); ub, binv = np.unique(blk, return_inverse=True)
col = lambda n: f[n][()].ravel()[idx]
import os
CACHE = "data/models/val_scores.npz"
SC = dict(np.load(CACHE)) if os.path.exists(CACHE) else {}
if not SC:
  with np.errstate(invalid="ignore"):
    SC["A"] = np.nanmean(np.stack([col("t76_HV_diff"), col("t55_HV_diff")]), 0); SC["A76"] = col("t76_HV_diff")
    SC["B"] = np.nanmean(np.stack([col("o19_VH_diff"), col("o92_VH_diff")]), 0)
for ver, gj in ([] if "v2 U-Net E" in SC else [("v1", "docs/models/train_gbm.json"), ("v2", "docs/models/train_gbm_v2.json")]):
    G = json.load(open(gj))["gbm"]
    for arm, g in G.items():
        X = np.stack([col(n) for n in g["features"]], 1).astype("float32")
        SC[f"{ver} GBM {arm}"] = np.mean([lgb.Booster(model_file=f"data/models/{ver}/gbm_{arm}_seed{sd}.txt").predict(X) for sd in range(5)], 0)
        del X; print(ver, "GBM", arm, round(time.time() - t0), flush=True)
class Block(nn.Sequential):
    def __init__(s, i, o): super().__init__(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True), nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))
class UNet(nn.Module):
    def __init__(s, cin):
        super().__init__(); s.e1, s.e2, s.e3 = Block(cin, 32), Block(32, 64), Block(64, 128); s.pool = nn.MaxPool2d(2)
        s.u2, s.d2 = nn.ConvTranspose2d(128, 64, 2, 2), Block(128, 64); s.u1, s.d1 = nn.ConvTranspose2d(64, 32, 2, 2), Block(64, 32); s.out = nn.Conv2d(32, 1, 1)
    def forward(s, x):
        a = s.e1(x); b = s.e2(s.pool(a)); c = s.e3(s.pool(b))
        y_ = s.d2(torch.cat([s.u2(c), b], 1)); y_ = s.d1(torch.cat([s.u1(y_), a], 1)); return s.out(y_)[:, 0]
T, M = 320, 32; vtiles = [((t // 100) * T, (t % 100) * T) for t in np.unique(S["tile_id"][val])]
for ver in ([] if "v2 U-Net E" in SC else ["v1", "v2"]):
    for arm in ("C", "D", "E"):
        nm = json.load(open(f"data/models/{ver}/unet_norm_{arm}.json")); chans = []
        for n in nm["channels"]:
            if n.endswith("_valid"):
                g = n[:-6]; v = np.ones((H, W), bool)
                for p in (["HH", "HV"] if g.startswith("t") else ["VV", "VH"]):
                    for k in ("pre", "post", "diff"): v &= np.isfinite(f[f"{g}_{p}_{k}"][()])
                chans.append(v.astype("float16"))
            elif n.startswith("nlcd_"): chans.append((f["nlcd"][()] == int(n[-1])).astype("float16"))
            else: mu, sd = nm["norm"][n]; chans.append(np.nan_to_num((f[n][()] - mu) / sd, nan=0.0).astype("float16"))
        X = np.stack(chans); prs = []
        for sd_ in range(5):
            net = UNet(X.shape[0]).cuda(); net.load_state_dict(torch.load(f"data/models/{ver}/unet_{arm}_seed{sd_}.pt")); net.eval(); out = np.full((H, W), np.nan, "float32")
            with torch.no_grad():
                for r0, c0 in vtiles:
                    r1, c1 = min(r0 + T, H), min(c0 + T, W); a0, b0 = max(0, r0 - M), max(0, c0 - M); a1, b1 = min(H, r1 + M), min(W, c1 + M)
                    x = X[:, a0:a1, b0:b1]; ph, pw = (-x.shape[1]) % 4, (-x.shape[2]) % 4
                    x = np.pad(x, ((0, 0), (0, ph), (0, pw))); pr = torch.sigmoid(net(torch.from_numpy(x.astype("float32"))[None].cuda()))[0].cpu().numpy()[: a1 - a0, : b1 - b0]
                    out[r0:r1, c0:c1] = pr[r0 - a0: r1 - a0, c0 - b0: c1 - b0]
            prs.append(out.ravel()[idx])
        SC[f"{ver} U-Net {arm}"] = np.mean(prs, 0); del X; torch.cuda.empty_cache(); print(ver, "U-Net", arm, round(time.time() - t0), flush=True)
if not os.path.exists(CACHE): np.savez_compressed(CACHE, **SC)
COMMON = np.all([np.isfinite(v) for v in SC.values()], 0)
print("cells", len(idx), "common", int(COMMON.sum()), flush=True)
# ---- histogram AUC + block bootstrap
NB = 2000; rng = np.random.default_rng(42); NBOOT = 1000
def hists(s, m):
    edges = np.unique(np.quantile(s[m], np.linspace(0, 1, NB + 1))); b = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, len(edges) - 2)
    nb = len(edges) - 1; hp = np.zeros((len(ub), nb)); hn = np.zeros((len(ub), nb))
    np.add.at(hp, (binv[m & y], b[m & y]), 1); np.add.at(hn, (binv[m & ~y], b[m & ~y]), 1); return hp, hn
def auc_h(hp, hn):
    if hp.ndim == 2: hp, hn = hp.sum(0), hn.sum(0)
    P, N = hp.sum(), hn.sum(); cn = np.cumsum(hn) - hn
    return float(((hp * cn).sum() + 0.5 * (hp * hn).sum()) / (P * N)) if P > 0 and N > 0 else np.nan
draws = [np.bincount(rng.integers(0, len(ub), len(ub)), minlength=len(ub)) for _ in range(NBOOT)]
res = {"n_cells": int(len(idx)), "n_common": int(COMMON.sum()), "n_blocks": int(len(ub)), "cuts": {}}
for cn, cm in CUT.items():
    for dn, dm in DOM.items():
        m = cm & dm & COMMON; key = f"{cn} | {dn}"; ent = {"n_damage": int((m & y).sum()), "n_other": int((m & ~y).sum()), "auc": {}, "v2_minus_v1": {}}
        if ent["n_damage"] < 30 or ent["n_other"] < 30: res["cuts"][key] = ent; continue
        H_ = {k: hists(v, m) for k, v in SC.items()}; boot = {k: np.array([auc_h(w[:, None] * hp, w[:, None] * hn) for w in draws]) for k, (hp, hn) in H_.items()}
        for k in SC:
            ent["auc"][k] = {"auc": round(float(roc_auc_score(y[m], SC[k][m])), 4), "ci95": [round(float(np.nanpercentile(boot[k], 2.5)), 4), round(float(np.nanpercentile(boot[k], 97.5)), 4)]}
        for mt in ("GBM", "U-Net"):
            for arm in "CDE":
                d = boot[f"v2 {mt} {arm}"] - boot[f"v1 {mt} {arm}"]
                ent["v2_minus_v1"][f"{mt} {arm}"] = {"diff": round(ent["auc"][f"v2 {mt} {arm}"]["auc"] - ent["auc"][f"v1 {mt} {arm}"]["auc"], 4),
                                                    "ci95": [round(float(np.nanpercentile(d, 2.5)), 4), round(float(np.nanpercentile(d, 97.5)), 4)]}
        res["cuts"][key] = ent; print(key, {k: v["auc"] for k, v in ent["auc"].items()}, round(time.time() - t0), flush=True)
# ---- reliability, in-band cut
m = CUT["in-band"] & COMMON; res["reliability_inband"] = {"prevalence": round(float(y[m].mean()), 4)}
fig, ax = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
edges = np.linspace(0, 1, 11)
for a, mt in zip(ax, ("GBM", "U-Net")):
    a.plot([0, 1], [0, 1], c="k", lw=0.6)
    for arm, colr in zip("CDE", ("C0", "C1", "C2")):
        for ver, ls in (("v2", "-"), ("v1", ":")):
            p = SC[f"{ver} {mt} {arm}"][m]; yy = y[m]; b = np.clip(np.digitize(p, edges) - 1, 0, 9)
            cnt = np.bincount(b, minlength=10); obs = np.bincount(b, weights=yy, minlength=10) / np.maximum(cnt, 1); mp = np.bincount(b, weights=p, minlength=10) / np.maximum(cnt, 1)
            ece = float((cnt * np.abs(obs - mp)).sum() / cnt.sum()); brier = float(np.mean((p - yy) ** 2))
            res["reliability_inband"][f"{ver} {mt} {arm}"] = {"brier": round(brier, 4), "ece": round(ece, 4), "bins": [{"p_lo": round(edges[i], 1), "n": int(cnt[i]), "mean_pred": round(float(mp[i]), 3), "observed": round(float(obs[i]), 3)} for i in range(10) if cnt[i]]}
            ok = cnt >= 50; a.plot(mp[ok], obs[ok], ls, c=colr, marker="o" if ver == "v2" else None, label=f"{ver} {arm} (ECE {ece:.2f})")
    a.set_title(f"{mt}: in-band validation cut (prevalence {res['reliability_inband']['prevalence']:.2f})"); a.set_xlabel("mean predicted probability (bin)"); a.set_ylabel("observed share in Sentinel-2 damage mask")
    a.legend(fontsize=8); a.set_xlim(0, 1); a.set_ylim(0, 1)
fig.suptitle("Reliability on the in-band validation cut (solid = v2, dotted = v1; bins with >= 50 cells)")
fig.savefig("docs/models/fig_reliability_inband.png", dpi=85)
res["seconds"] = round(time.time() - t0); json.dump(res, open("docs/models/val_compare.json", "w"), indent=1)
