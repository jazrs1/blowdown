"""Amendment 1, v2 U-Net arms C, D, E: identical to train_unet.py except labels = data/models/labels_v2.npz and
selection (lr, checkpoint epoch, threshold) on the in-band validation cut (validation-tile forest cells inside the band).
Outputs go to data/models/v2/ and docs/models/train_unet_v2.json. Original v1 docstring follows.
Models step 4c: U-Net arms C (NISAR), D (S1), E (both) per design.md section 6.
Inputs per arm: per-pixel radar layers (standardised with training-area statistics, NaN -> 0), one validity channel per
geometry, standardised HAND, NLCD one-hot (4). 64x64 patches on a stride-32 lattice wholly inside the training area
(training tiles minus guard, inside the region training mask) with >= 1 labelled cell. BCE (pos_weight 4) on labelled cells,
AdamW (wd 1e-4), batch 32, 30 epochs, flips + 90-degree rotations. lr in {1e-3, 3e-4} picked on seed 0 by best validation
AUC; checkpoint = best-validation-AUC epoch; seeds 0-4. Validation tiles predicted whole with a 32-cell context margin.
Reads only data/models/features_train.h5 and data/models/split.npz. Writes data/models/v2/unet_<arm>_seed<k>.pt,
data/models/v2/unet_norm_<arm>.json, data/models/v2/thresholds_unet.json, docs/models/train_unet_v2.json."""
import json, os, sys, time
import h5py, numpy as np, torch, torch.nn as nn
from sklearn.metrics import roc_auc_score
t0 = time.time(); dev = "cuda"
f = h5py.File("data/models/features_train.h5", "r"); S = np.load("data/models/split.npz")
lab = np.load("data/models/labels_v2.npz")["label"]; up = f["upland"][()]; wt = f["wetland"][()]; H, W = lab.shape
val, ta, region = S["val"], S["trainarea"], f["train"][()]
GEOM = {"t76": ["HH", "HV"], "t55": ["HH", "HV"], "o19": ["VV", "VH"], "o92": ["VV", "VH"]}
ARMS = {"C": ["t76", "t55"], "D": ["o19", "o92"], "E": ["t76", "t55", "o19", "o92"]}
def build(arm):
    chans, names, norm = [], [], {}
    for g in ARMS[arm]:
        valid = None
        for p in GEOM[g]:
            for k in ("pre", "post", "diff"):
                n = f"{g}_{p}_{k}"; a = f[n][()]; m = ta & np.isfinite(a); mu, sd = float(a[m].mean()), float(a[m].std())
                norm[n] = [mu, sd]; chans.append(np.nan_to_num((a - mu) / sd, nan=0.0).astype("float16")); names.append(n)
                valid = np.isfinite(a) if valid is None else valid & np.isfinite(a)
        chans.append(valid.astype("float16")); names.append(f"{g}_valid")
    a = f["hand"][()]; m = ta & np.isfinite(a); mu, sd = float(a[m].mean()), float(a[m].std()); norm["hand"] = [mu, sd]
    chans.append(np.nan_to_num((a - mu) / sd, nan=0.0).astype("float16")); names.append("hand")
    nl = f["nlcd"][()]
    for c in (1, 2, 3, 4): chans.append((nl == c).astype("float16")); names.append(f"nlcd_{c}")
    return np.stack(chans), names, norm
class Block(nn.Sequential):
    def __init__(s, i, o): super().__init__(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True), nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))
class UNet(nn.Module):
    def __init__(s, cin):
        super().__init__(); s.e1, s.e2, s.e3 = Block(cin, 32), Block(32, 64), Block(64, 128); s.pool = nn.MaxPool2d(2)
        s.u2, s.d2 = nn.ConvTranspose2d(128, 64, 2, 2), Block(128, 64); s.u1, s.d1 = nn.ConvTranspose2d(64, 32, 2, 2), Block(64, 32); s.out = nn.Conv2d(32, 1, 1)
    def forward(s, x):
        a = s.e1(x); b = s.e2(s.pool(a)); c = s.e3(s.pool(b))
        y = s.d2(torch.cat([s.u2(c), b], 1)); y = s.d1(torch.cat([s.u1(y), a], 1)); return s.out(y)[:, 0]
P, ST, M = 64, 32, 32
ok_area = ta & region
lat = [(r, c) for r in range(0, H - P + 1, ST) for c in range(0, W - P + 1, ST)]
patches = [(r, c) for r, c in lat if ok_area[r:r + P, c:c + P].all() and (lab[r:r + P, c:c + P] >= 0).any()]
vt = np.unique(S["tile_id"][val]); T = 320
vtiles = [((t // 100) * T, (t % 100) * T) for t in vt]
vlab_cells = val & (lab >= 0) & np.load("data/regions_30.npz")["band"]   # in-band validation cut
print("patches", len(patches), "val tiles", len(vtiles), flush=True)
def predict_tiles(net, X):
    net.eval(); out = np.full((H, W), np.nan, "float32")
    with torch.no_grad():
        for r0, c0 in vtiles:
            r1, c1 = min(r0 + T, H), min(c0 + T, W); a0, b0 = max(0, r0 - M), max(0, c0 - M); a1, b1 = min(H, r1 + M), min(W, c1 + M)
            x = X[:, a0:a1, b0:b1]; ph, pw = (-x.shape[1]) % 4, (-x.shape[2]) % 4
            x = np.pad(x, ((0, 0), (0, ph), (0, pw))); xt = torch.from_numpy(x.astype("float32"))[None].to(dev)
            pr = torch.sigmoid(net(xt))[0].cpu().numpy()[: a1 - a0, : b1 - b0]
            out[r0:r1, c0:c1] = pr[r0 - a0: r1 - a0, c0 - b0: c1 - b0]
    return out
def run(X, lr, seed, epochs=30):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    net = UNet(X.shape[0]).to(dev); opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(4.0, device=dev), reduction="none")
    best, best_state, hist = -1, None, []
    for ep in range(epochs):
        net.train(); order = rng.permutation(len(patches)); tl = 0
        for b in range(0, len(order), 32):
            pk = [patches[i] for i in order[b:b + 32]]
            x = np.stack([X[:, r:r + P, c:c + P] for r, c in pk]).astype("float32"); y = np.stack([lab[r:r + P, c:c + P] for r, c in pk]).astype("float32")
            k = rng.integers(0, 4); x, y = np.rot90(x, k, (2, 3)), np.rot90(y, k, (1, 2))
            if rng.random() < 0.5: x, y = x[:, :, :, ::-1], y[:, :, ::-1]
            xt = torch.from_numpy(np.ascontiguousarray(x)).to(dev); yt = torch.from_numpy(np.ascontiguousarray(y)).to(dev)
            m = (yt >= 0).float(); lo = net(xt); l = (lossf(lo, yt.clamp(min=0)) * m).sum() / m.sum().clamp(min=1)
            opt.zero_grad(); l.backward(); opt.step(); tl += float(l)
        pv = predict_tiles(net, X); s = pv[vlab_cells]; y = lab[vlab_cells] == 1; ok = np.isfinite(s)
        a = roc_auc_score(y[ok], s[ok]); hist.append({"epoch": ep, "train_loss": round(tl / max(1, len(order) // 32), 4), "val_auc": round(float(a), 4)})
        if a > best: best, best_state, best_ep = a, {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}, ep
    net.load_state_dict(best_state); return net, best, best_ep, hist
def best_f1(score, y):
    ok = np.isfinite(score); s, yy = score[ok], y[ok]; qs = np.unique(np.quantile(s, np.linspace(0.01, 0.995, 300)))
    f1 = [(2 * (yy & (s > q)).sum() / max((s > q).sum() + yy.sum(), 1)) for q in qs]; k = int(np.argmax(f1)); return float(qs[k]), float(f1[k])
yv = lab[vlab_cells] == 1; upv, wtv = up[vlab_cells], wt[vlab_cells]
def metrics(score, thr):
    out = {}
    for dn, m in (("all", np.ones_like(yv)), ("upland", upv), ("wetland", wtv)):
        s, y = score[m], yv[m]; ok = np.isfinite(s); s, y = s[ok], y[ok]; p = s > thr; tp = (p & y).sum()
        out[dn] = {"auc": round(float(roc_auc_score(y, s)), 4), "f1": round(float(2 * tp / max(p.sum() + y.sum(), 1)), 4),
                   "precision": round(float(tp / max(p.sum(), 1)), 4), "recall": round(float(tp / max(y.sum(), 1)), 4), "n_damage": int(y.sum()), "n_intact": int((~y).sum())}
    return out
res = {"n_patches": len(patches), "n_val_tiles": len(vtiles)}; thr_out = {}
arms = sys.argv[1:] or list(ARMS)
if os.path.exists("docs/models/train_unet_v2.json"): res.update(json.load(open("docs/models/train_unet_v2.json")))
for arm in arms:
    X, names, norm = build(arm); json.dump({"channels": names, "norm": norm}, open(f"data/models/v2/unet_norm_{arm}.json", "w"), indent=1)
    print(arm, "channels", len(names), round(time.time() - t0), flush=True)
    tune = {}
    for lr in (1e-3, 3e-4):
        net, b, ep, hist = run(X, lr, 0); tune[lr] = (net, b, ep, hist); print(arm, "lr", lr, "best val auc", round(b, 4), "epoch", ep, round(time.time() - t0), flush=True)
    lr = max(tune, key=lambda k: tune[k][1]); seeds, probs = [], []
    for sd in range(5):
        net, b, ep, hist = tune[lr] if sd == 0 else run(X, lr, sd)
        fn = f"data/models/v2/unet_{arm}_seed{sd}.pt"; torch.save(net.state_dict(), fn)
        pv = predict_tiles(net, X)[vlab_cells]; probs.append(pv); th, _ = best_f1(pv, yv)
        seeds.append({"seed": sd, "best_epoch": ep, "val": metrics(pv, th), "history": hist}); print(arm, "seed", sd, seeds[-1]["val"]["all"], round(time.time() - t0), flush=True)
    ens = np.mean(probs, 0); th, _ = best_f1(ens, yv); thr_out[arm] = th
    res[arm] = {"lr_tuning": {str(k): {"best_val_auc": round(v[1], 4), "best_epoch": v[2]} for k, v in tune.items()}, "chosen_lr": lr, "seeds": seeds,
                "ensemble_threshold": round(th, 5), "ensemble_val": metrics(ens, th),
                "seed_spread_auc_all": [round(min(s_["val"]["all"]["auc"] for s_ in seeds), 4), round(max(s_["val"]["all"]["auc"] for s_ in seeds), 4)]}
    print(arm, "ensemble", res[arm]["ensemble_val"], flush=True)
    del X; torch.cuda.empty_cache()
    json.dump(res, open("docs/models/train_unet_v2.json", "w"), indent=1)
tp = "data/models/v2/thresholds_unet.json"; old = json.load(open(tp)) if os.path.exists(tp) else {}
old.update(thr_out); json.dump(old, open(tp, "w"), indent=1)
res["seconds_last_run"] = round(time.time() - t0); json.dump(res, open("docs/models/train_unet_v2.json", "w"), indent=1)
