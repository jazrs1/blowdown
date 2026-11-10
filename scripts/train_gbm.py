"""Models step 4b: threshold arms A, A76, B and LightGBM arms C (NISAR), D (S1), E (both) per design.md section 6.
Reads only data/models/features_train.h5 and data/models/split.npz. Validation numbers only.
Writes data/models/frozen/gbm_<arm>_seed<k>.txt, data/models/frozen/thresholds_simple.json, docs/models/train_gbm.json."""
import json, os, time
import h5py, numpy as np, lightgbm as lgb
from sklearn.metrics import roc_auc_score
t0 = time.time(); os.makedirs("data/models/frozen", exist_ok=True)
f = h5py.File("data/models/features_train.h5", "r"); S = np.load("data/models/split.npz")
lab = f["label"][()]; up = f["upland"][()]; wt = f["wetland"][()]
val, ta = S["val"], S["trainarea"]
NIS = [f"{g}_{p}_{k}" for g in ("t76", "t55") for p in ("HH", "HV") for k in ("pre", "post", "diff")]
S1 = [f"{g}_{p}_{k}" for g in ("o19", "o92") for p in ("VV", "VH") for k in ("pre", "post", "diff")]
ARMS = {"C": NIS, "D": S1, "E": NIS + S1}
vidx = np.flatnonzero((val & (lab >= 0)).ravel()); yv = lab.ravel()[vidx] == 1
upv, wtv = up.ravel()[vidx], wt.ravel()[vidx]
tri_d = np.flatnonzero((ta & (lab == 1)).ravel()); tri_i = np.flatnonzero((ta & (lab == 0)).ravel())
def col(name, idx): return f[name][()].ravel()[idx]
def best_f1(score, y):
    ok = np.isfinite(score); s, yy = score[ok], y[ok]; qs = np.unique(np.quantile(s, np.linspace(0.5, 0.995, 200)))
    f1 = [(2 * (yy & (s > q)).sum() / max((s > q).sum() + yy.sum(), 1)) for q in qs]; k = int(np.argmax(f1)); return float(qs[k]), float(f1[k])
def metrics(score, thr):
    out = {}
    for dn, m in (("all", np.ones_like(yv)), ("upland", upv), ("wetland", wtv)):
        s, y = score[m], yv[m]; ok = np.isfinite(s); s, y = s[ok], y[ok]; p = s > thr
        tp = (p & y).sum(); f1 = 2 * tp / max(p.sum() + y.sum(), 1)
        out[dn] = {"auc": round(float(roc_auc_score(y, s)), 4), "f1": round(float(f1), 4), "precision": round(float(tp / max(p.sum(), 1)), 4),
                   "recall": round(float(tp / max(y.sum(), 1)), 4), "n_damage": int(y.sum()), "n_intact": int((~y).sum()), "n_nan_dropped": int((~ok).sum()) if dn == "all" else None}
    return out
res = {"simple": {}, "gbm": {}}
# ---- threshold arms
with np.errstate(invalid="ignore"):
    simple = {"A": np.nanmean(np.stack([col("t76_HV_diff", vidx), col("t55_HV_diff", vidx)]), 0), "A76": col("t76_HV_diff", vidx),
              "B": np.nanmean(np.stack([col("o19_VH_diff", vidx), col("o92_VH_diff", vidx)]), 0)}
thr_simple = {}
for k, s in simple.items():
    thr, f1 = best_f1(s, yv); thr_simple[k] = thr; res["simple"][k] = {"threshold_dB": round(thr, 3), "val": metrics(s, thr)}
    print(k, res["simple"][k], flush=True)
json.dump({"A": {"score": "nanmean(t76_HV_diff, t55_HV_diff)", "threshold_dB": thr_simple["A"]}, "A76": {"score": "t76_HV_diff", "threshold_dB": thr_simple["A76"]},
           "B": {"score": "nanmean(o19_VH_diff, o92_VH_diff)", "threshold_dB": thr_simple["B"]}}, open("data/models/frozen/thresholds_simple.json", "w"), indent=1)
# ---- GBM
rng_v = np.random.default_rng(0); es_sel = np.sort(rng_v.choice(len(vidx), min(len(vidx), 1_000_000), replace=False))
GRID = [{"num_leaves": nl, "min_data_in_leaf": md} for nl in (31, 127) for md in (100, 1000)]
BASE = {"objective": "binary", "learning_rate": 0.05, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "metric": "auc", "verbose": -1, "num_threads": 16}
for arm, base in ARMS.items():
    feats = base + [f"{n}_m3" for n in base] + [f"{n}_m7" for n in base] + ["hand", "nlcd"]
    Xv = np.stack([col(n, vidx) for n in feats], 1).astype("float32")
    def trainset(seed):
        r = np.random.default_rng(seed); ii = r.choice(tri_i, min(len(tri_i), 4 * len(tri_d)), replace=False); idx = np.sort(np.r_[tri_d, ii])
        return np.stack([col(n, idx) for n in feats], 1).astype("float32"), (lab.ravel()[idx] == 1).astype("int8")
    tune = []; X0, y0 = trainset(0)
    for g in GRID:
        p = {**BASE, **g, "seed": 0, "bagging_seed": 0, "feature_fraction_seed": 0}
        dtr = lgb.Dataset(X0, y0, feature_name=feats, categorical_feature=["nlcd"], free_raw_data=False)
        dva = lgb.Dataset(Xv[es_sel], yv[es_sel].astype("int8"), reference=dtr)
        b = lgb.train(p, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        tune.append({**g, "best_iter": b.best_iteration, "val_auc_es_subset": round(b.best_score["valid_0"]["auc"], 4)}); print(arm, tune[-1], round(time.time() - t0), flush=True)
    bestg = max(tune, key=lambda t: t["val_auc_es_subset"]); bp = {k: bestg[k] for k in ("num_leaves", "min_data_in_leaf")}
    probs, seeds, imp = [], [], np.zeros(len(feats))
    for sd in range(5):
        X, y = (X0, y0) if sd == 0 else trainset(sd)
        p = {**BASE, **bp, "seed": sd, "bagging_seed": sd, "feature_fraction_seed": sd}
        dtr = lgb.Dataset(X, y, feature_name=feats, categorical_feature=["nlcd"]); dva = lgb.Dataset(Xv[es_sel], yv[es_sel].astype("int8"), reference=dtr)
        b = lgb.train(p, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        fn = f"data/models/frozen/gbm_{arm}_seed{sd}.txt"; b.save_model(fn, num_iteration=b.best_iteration)
        pr = b.predict(Xv, num_iteration=b.best_iteration); probs.append(pr); imp += b.feature_importance("gain", iteration=b.best_iteration)
        th, _ = best_f1(pr, yv); seeds.append({"seed": sd, "best_iter": b.best_iteration, "val": metrics(pr, th)}); print(arm, "seed", sd, seeds[-1]["val"]["all"], round(time.time() - t0), flush=True)
    ens = np.mean(probs, 0); th, _ = best_f1(ens, yv)
    imp = imp / imp.sum(); order = np.argsort(-imp)
    res["gbm"][arm] = {"features": feats, "tuning": tune, "chosen": bp, "seeds": seeds, "ensemble_threshold": round(th, 5), "ensemble_val": metrics(ens, th),
                       "seed_spread_auc_all": [round(float(np.min([s_["val"]["all"]["auc"] for s_ in seeds])), 4), round(float(np.max([s_["val"]["all"]["auc"] for s_ in seeds])), 4)],
                       "importance_gain_share": {feats[i]: round(float(imp[i]), 4) for i in order}}
    print(arm, "ensemble", res["gbm"][arm]["ensemble_val"], flush=True)
    del Xv, X0
json.dump({k: v["ensemble_threshold"] for k, v in res["gbm"].items()}, open("data/models/frozen/thresholds_gbm.json", "w"), indent=1)
res["seconds"] = round(time.time() - t0)
json.dump(res, open("docs/models/train_gbm.json", "w"), indent=1)
