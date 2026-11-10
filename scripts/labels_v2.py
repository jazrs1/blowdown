"""Amendment 1: v2 training labels on the training region only. Every forest cell (forest share >= 0.5) inside the training
region: 1 = Sentinel-2 damage cell (damage share >= 0.5), 0 = any other forest cell; -1 = not forest, outside the training
region, or flagged (any 10 m clearcut/salvage-flag pixel, or clearing after 10-29 as in features.py). No edge dropping.
Writes data/models/labels_v2.npz and docs/models/labels_v2.json."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
RG = np.load("data/regions_30.npz"); E = np.load("data/controls_ee_30.npz")
f = h5py.File("data/models/features_train.h5", "r"); train = f["train"][()]; forest = RG["forest"] & train
H3, W3 = forest.shape; HB, WB = H3 * 3, W3 * 3
Rr = h5py.File("data/reference.h5", "r"); cc = np.zeros((H3, W3), bool)
for r in range(0, HB, 600):
    re_ = min(r + 600, HB); cc[r // 3:re_ // 3] = (Rr["clearcut"][r:re_, :WB] > 0).reshape(-1, 3, W3, 3).any((1, 3))
with np.errstate(invalid="ignore"): sal = (E["ndvi_p2"] < 0.35) & (E["ndvi_p2"] - E["ndvi_p1"] < -0.15) & (E["n_p2"] > 0)
lab = np.full((H3, W3), -1, "int8"); lab[forest] = 0; lab[forest & RG["damage"]] = 1; lab[(cc | sal) & forest] = -1
v1 = f["label"][()]
out = {"label1": int((lab == 1).sum()), "label0": int((lab == 0).sum()), "flag_excluded": int(((cc | sal) & forest).sum()),
       "v1_label1": int((v1 == 1).sum()), "v1_label0": int((v1 == 0).sum()),
       "v2_label0_that_v1_left_unlabelled": int(((lab == 0) & (v1 < 0)).sum()), "v2_label1_that_v1_left_unlabelled": int(((lab == 1) & (v1 < 0)).sum())}
np.savez_compressed("data/models/labels_v2.npz", label=lab); json.dump(out, open("docs/models/labels_v2.json", "w"), indent=1); print(out)
