"""Amendment 1, v2 LightGBM arms C (NISAR), D (S1), E (both). Same as train_gbm.py except:
labels = data/models/labels_v2.npz; tuning, early stopping and thresholds use the in-band validation cut (validation-tile
forest cells inside the band, v2 labels). Reads features_train.h5, split.npz, labels_v2.npz and the band mask of
regions_30.npz (validation tiles only). Writes data/models/v2/gbm_<arm>_seed<k>.txt, data/models/v2/thresholds_gbm.json,
docs/models/train_gbm_v2.json."""
import json, os, time
import h5py, numpy as np, lightgbm as lgb
from sklearn.metrics import roc_auc_score
t0 = time.time(); OUT = "data/models/v2"
f = h5py.File("data/models/features_train.h5", "r"); S = np.load("data/models/split.npz")
lab = np.load("data/models/labels_v2.npz")["label"]; band = np.load("data/regions_30.npz")["band"]
val, ta = S["val"], S["trainarea"]
NIS = [f"{g}_{p}_{k}" for g in ("t76", "t55") for p in ("HH", "HV") for k in ("pre", "post", "diff")]
S1 = [f"{g}_{p}_{k}" for g in ("o19", "o92") for p in ("VV", "VH") for k in ("pre", "post", "diff")]
ARMS = {"C": NIS, "D": S1, "E": NIS + S1}
vidx = np.flatnonzero((val & band & (lab >= 0)).ravel()); yv = lab.ravel()[vidx] == 1
tri_d = np.flatnonzero((ta & (lab == 1)).ravel()); tri_i = np.flatnonzero((ta & (lab == 0)).ravel())
print("in-band val cells", len(vidx), "damage", int(yv.sum()), "| train label1", len(tri_d), "label0", len(tri_i), flush=True)
def col(name, idx): return f[name][()].ravel()[idx]
def best_f1(score, y):
    ok = np.isfinite(score); s, yy = score[ok], y[ok]; qs = np.unique(np.quantile(s, np.linspace(0.01, 0.995, 300)))
    f1 = [(2 * (yy & (s > q)).sum() / max((s > q).sum() + yy.sum(), 1)) for q in qs]; k = int(np.argmax(f1)); return float(qs[k]), float(f1[k])
GRID = [{"num_leaves": nl, "min_data_in_leaf": md} for nl in (31, 127) for md in (100, 1000)]
BASE = {"objective": "binary", "learning_rate": 0.05, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "metric": "auc", "verbose": -1, "num_threads": 16}
res = {"n_inband_val": len(vidx), "n_inband_val_damage": int(yv.sum()), "gbm": {}}
for arm, base in ARMS.items():
    feats = base + [f"{n}_m3" for n in base] + [f"{n}_m7" for n in base] + ["hand", "nlcd"]
    Xv = np.stack([col(n, vidx) for n in feats], 1).astype("float32")
    def trainset(seed):
        r = np.random.default_rng(seed); ii = r.choice(tri_i, min(len(tri_i), 4 * len(tri_d)), replace=False); idx = np.sort(np.r_[tri_d, ii])
        return np.stack([col(n, idx) for n in feats], 1).astype("float32"), (lab.ravel()[idx] == 1).astype("int8")
    tune = []; X0, y0 = trainset(0)
    for g in GRID:
        p = {**BASE, **g, "seed": 0, "bagging_seed": 0, "feature_fraction_seed": 0}
        dtr = lgb.Dataset(X0, y0, feature_name=feats, categorical_feature=["nlcd"], free_raw_data=False); dva = lgb.Dataset(Xv, yv.astype("int8"), reference=dtr)
        b = lgb.train(p, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        tune.append({**g, "best_iter": b.best_iteration, "inband_val_auc": round(b.best_score["valid_0"]["auc"], 4)}); print(arm, tune[-1], round(time.time() - t0), flush=True)
    bestg = max(tune, key=lambda t: t["inband_val_auc"]); bp = {k: bestg[k] for k in ("num_leaves", "min_data_in_leaf")}
    probs, seeds, imp = [], [], np.zeros(len(feats))
    for sd in range(5):
        X, y = (X0, y0) if sd == 0 else trainset(sd)
        p = {**BASE, **bp, "seed": sd, "bagging_seed": sd, "feature_fraction_seed": sd}
        dtr = lgb.Dataset(X, y, feature_name=feats, categorical_feature=["nlcd"]); dva = lgb.Dataset(Xv, yv.astype("int8"), reference=dtr)
        b = lgb.train(p, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        b.save_model(f"{OUT}/gbm_{arm}_seed{sd}.txt", num_iteration=b.best_iteration)
        pr = b.predict(Xv, num_iteration=b.best_iteration); probs.append(pr); imp += b.feature_importance("gain", iteration=b.best_iteration)
        seeds.append({"seed": sd, "best_iter": b.best_iteration, "inband_val_auc": round(float(roc_auc_score(yv, pr)), 4)}); print(arm, "seed", sd, seeds[-1], round(time.time() - t0), flush=True)
        if sd > 0: del X
    ens = np.mean(probs, 0); th, f1 = best_f1(ens, yv); imp = imp / imp.sum(); order = np.argsort(-imp)
    res["gbm"][arm] = {"features": feats, "tuning": tune, "chosen": bp, "seeds": seeds, "ensemble_inband_val_auc": round(float(roc_auc_score(yv, ens)), 4),
                       "ensemble_threshold": round(th, 5), "ensemble_inband_val_f1": round(f1, 4),
                       "importance_gain_share": {feats[i]: round(float(imp[i]), 4) for i in order}}
    print(arm, "ensemble", res["gbm"][arm]["ensemble_inband_val_auc"], round(f1, 4), flush=True)
    del Xv, X0
json.dump({k: v["ensemble_threshold"] for k, v in res["gbm"].items()}, open(f"{OUT}/thresholds_gbm.json", "w"), indent=1)
res["seconds"] = round(time.time() - t0); json.dump(res, open("docs/models/train_gbm_v2.json", "w"), indent=1)
