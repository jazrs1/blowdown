"""Models step 4a: spatial validation split inside the training region (design.md section 5).
Tiles 320 x 320 cells from the grid origin; eligible if >= 500 labelled training cells; 20% of eligible tiles drawn as
validation with numpy default_rng(s), s = 0, 1, ...; accept the first s with >= 5000 validation damage cells in upland,
>= 5000 in wetland and >= 15% of all labelled damage cells. Training cells within 4 cells of a validation tile are guard
(not used for training). Reads only data/models/features_train.h5. Writes data/models/split.npz, docs/models/split.json."""
import json
import h5py, numpy as np
from scipy.ndimage import maximum_filter
f = h5py.File("data/models/features_train.h5", "r")
lab = f["label"][()]; up = f["upland"][()]; wt = f["wetland"][()]; H, W = lab.shape; T = 320
ti = (np.arange(H)[:, None] // T) * 100 + (np.arange(W)[None, :] // T)
labd = lab >= 0; tiles = np.unique(ti)
cnt = {t: int(labd[ti == t].sum()) for t in tiles}; elig = np.array([t for t in tiles if cnt[t] >= 500])
D = lab == 1; ntot = int(D.sum())
for s in range(1000):
    rng = np.random.default_rng(s); val_t = rng.choice(elig, int(round(0.2 * len(elig))), replace=False)
    val = np.isin(ti, val_t); du, dw = int((D & val & up).sum()), int((D & val & wt).sum()); share = (D & val).sum() / ntot
    if du >= 5000 and dw >= 5000 and share >= 0.15: break
guard = (maximum_filter(val.astype(np.uint8), 9) > 0) & ~val
trainarea = ~val & ~guard & f["train"][()]
np.savez_compressed("data/models/split.npz", val=val, guard=guard, trainarea=trainarea, tile_id=ti)
out = {"seed_used": s, "n_tiles": int(len(tiles)), "n_eligible": int(len(elig)), "n_val_tiles": int(len(val_t)), "val_tiles": [int(t) for t in sorted(val_t)],
       "val_damage_upland": du, "val_damage_wetland": dw, "val_share_of_damage": round(float(share), 3),
       "train_damage": int((D & trainarea).sum()), "train_intact": int(((lab == 0) & trainarea).sum()),
       "val_damage": int((D & val).sum()), "val_intact": int(((lab == 0) & val).sum()),
       "guard_labelled_dropped": int((labd & guard).sum())}
json.dump(out, open("docs/models/split.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "val_tiles"}, indent=1))
