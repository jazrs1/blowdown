"""Models step 4d: validation diagnostics (validation tiles inside the training region only; nothing from the held-out
block or the tip is read). Frozen models from data/models/v1/ are re-run on the validation tiles and scored on
  design   : the design labels (edge, clearcut and salvage cells removed) - reproduces train_gbm / train_unet numbers
  all      : every damage cell vs every intact cell in validation tiles (regions_30.npz; no edge / flag removal), which
             is closer to how John's sample is drawn
  band     : 'all' restricted to cells inside the band (pipeline extent mask)
  outband  : 'all' restricted to cells outside the band
  band_mask_vs_rest : inside the band, Sentinel-2 damage cells vs ALL other forest cells (closest to John's sample: half
             in the mask, half outside it); scored on cells where every arm has a finite score (one common set).
             This is agreement with the Sentinel-2 mask, not with ground truth.
Smoothed threshold arms (7x7 mean of the diff layers) are added to separate the gain from smoothing from the gain from learning.
Writes docs/models/train_diag.json."""
import json, sys, time; sys.path.insert(0, "scripts")
import h5py, numpy as np, lightgbm as lgb, torch, torch.nn as nn
from sklearn.metrics import roc_auc_score
t0 = time.time()
f = h5py.File("data/models/features_train.h5", "r"); S = np.load("data/models/split.npz"); RG = np.load("data/regions_30.npz")
lab = f["label"][()]; val = S["val"]; H, W = lab.shape
up, wt, band = RG["upland"], RG["wetland"], RG["band"]
D, I = RG["damage"] & val, RG["intact"] & val
FO = RG["forest"]
cells = val & (D | I | (lab >= 0) | (FO & band)); idx = np.flatnonzero(cells.ravel())
y_all = D.ravel()[idx]; lab_d = lab.ravel()[idx]; bd = band.ravel()[idx]
SETS = {"design": lab_d >= 0, "all": (D | I).ravel()[idx], "band": (D | I).ravel()[idx] & bd, "outband": (D | I).ravel()[idx] & ~bd,
        "band_mask_vs_rest": FO.ravel()[idx] & bd}
Y = {"design": lab_d == 1, "all": y_all, "band": y_all, "outband": y_all, "band_mask_vs_rest": y_all}
COMMON = None
DOM = {"all": np.ones(len(idx), bool), "upland": up.ravel()[idx], "wetland": wt.ravel()[idx]}
col = lambda n: f[n][()].ravel()[idx]
SC = {}
def score_all(s):
    out = {}
    for sn, m in SETS.items():
        for dn, dm in DOM.items():
            mm = m & dm & np.isfinite(s)
            if sn == "band_mask_vs_rest" and COMMON is not None: mm = m & dm & COMMON
            y = Y[sn][mm]
            out[f"{sn}|{dn}"] = None if y.sum() < 30 or (~y).sum() < 30 else {"auc": round(float(roc_auc_score(y, s[mm])), 4), "n_damage": int(y.sum()), "n_intact": int((~y).sum())}
    return out
res = {}
with np.errstate(invalid="ignore"):
    simple = {"A": np.nanmean(np.stack([col("t76_HV_diff"), col("t55_HV_diff")]), 0), "A76": col("t76_HV_diff"),
              "B": np.nanmean(np.stack([col("o19_VH_diff"), col("o92_VH_diff")]), 0),
              "A smoothed 7x7": np.nanmean(np.stack([col("t76_HV_diff_m7"), col("t55_HV_diff_m7")]), 0), "A76 smoothed 7x7": col("t76_HV_diff_m7"),
              "B smoothed 7x7": np.nanmean(np.stack([col("o19_VH_diff_m7"), col("o92_VH_diff_m7")]), 0)}
for k, s in simple.items(): SC[k] = s
G = json.load(open("docs/models/train_gbm.json"))["gbm"]
for arm, g in G.items():
    feats = g["features"]; X = np.stack([col(n) for n in feats], 1).astype("float32")
    pr = np.mean([lgb.Booster(model_file=f"data/models/v1/gbm_{arm}_seed{sd}.txt").predict(X) for sd in range(5)], 0)
    SC[f"GBM {arm}"] = pr; print("GBM", arm, round(time.time() - t0), flush=True)
    del X
# ---- U-Net
class Block(nn.Sequential):
    def __init__(s, i, o): super().__init__(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True), nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))
class UNet(nn.Module):
    def __init__(s, cin):
        super().__init__(); s.e1, s.e2, s.e3 = Block(cin, 32), Block(32, 64), Block(64, 128); s.pool = nn.MaxPool2d(2)
        s.u2, s.d2 = nn.ConvTranspose2d(128, 64, 2, 2), Block(128, 64); s.u1, s.d1 = nn.ConvTranspose2d(64, 32, 2, 2), Block(64, 32); s.out = nn.Conv2d(32, 1, 1)
    def forward(s, x):
        a = s.e1(x); b = s.e2(s.pool(a)); c = s.e3(s.pool(b))
        y = s.d2(torch.cat([s.u2(c), b], 1)); y = s.d1(torch.cat([s.u1(y), a], 1)); return s.out(y)[:, 0]
T, M = 320, 32
vtiles = [((t // 100) * T, (t % 100) * T) for t in np.unique(S["tile_id"][val])]
for arm in ("C", "D", "E"):
    try: nm = json.load(open(f"data/models/v1/unet_norm_{arm}.json"))
    except FileNotFoundError: continue
    chans = []
    for n in nm["channels"]:
        if n.endswith("_valid"):
            g = n[:-6]; ps = ["HH", "HV"] if g.startswith("t") else ["VV", "VH"]
            v = np.ones((H, W), bool)
            for p in ps:
                for k in ("pre", "post", "diff"): v &= np.isfinite(f[f"{g}_{p}_{k}"][()])
            chans.append(v.astype("float16"))
        elif n.startswith("nlcd_"): chans.append((f["nlcd"][()] == int(n[-1])).astype("float16"))
        else:
            mu, sd = nm["norm"][n]; chans.append(np.nan_to_num((f[n][()] - mu) / sd, nan=0.0).astype("float16"))
    X = np.stack(chans); prs = []
    for sd_ in range(5):
        net = UNet(X.shape[0]).cuda(); net.load_state_dict(torch.load(f"data/models/v1/unet_{arm}_seed{sd_}.pt")); net.eval()
        out = np.full((H, W), np.nan, "float32")
        with torch.no_grad():
            for r0, c0 in vtiles:
                r1, c1 = min(r0 + T, H), min(c0 + T, W); a0, b0 = max(0, r0 - M), max(0, c0 - M); a1, b1 = min(H, r1 + M), min(W, c1 + M)
                x = X[:, a0:a1, b0:b1]; ph, pw = (-x.shape[1]) % 4, (-x.shape[2]) % 4
                x = np.pad(x, ((0, 0), (0, ph), (0, pw))); pr = torch.sigmoid(net(torch.from_numpy(x.astype("float32"))[None].cuda()))[0].cpu().numpy()[: a1 - a0, : b1 - b0]
                out[r0:r1, c0:c1] = pr[r0 - a0: r1 - a0, c0 - b0: c1 - b0]
        prs.append(out.ravel()[idx])
    SC[f"U-Net {arm}"] = np.mean(prs, 0); print("U-Net", arm, round(time.time() - t0), flush=True)
    del X; torch.cuda.empty_cache()
COMMON = np.all([np.isfinite(v) for v in SC.values()], 0)
for k, v in SC.items():
    res[k] = score_all(v); print(k, {q: (res[k][q] or {}).get("auc") for q in ("design|all", "all|all", "outband|all", "band|all", "band_mask_vs_rest|upland", "band_mask_vs_rest|wetland")}, flush=True)
res["n_common_band_cells"] = {dn: int((SETS["band_mask_vs_rest"] & DOM[dn] & COMMON).sum()) for dn in DOM}
res["seconds"] = round(time.time() - t0)
json.dump(res, open("docs/models/train_diag.json", "w"), indent=1)
