"""Per-scene calibration check: forest-median HH/HV (dB) of each NISAR scene over pixels valid in all four scenes of
its track, and pairwise same-side differences (pre-pre, post-post). P05036 (10-28/10-29) vs P05023 should show up
as a step in post-post if calibration changed. Writes docs/pipeline/scene_check.json."""
import json, re, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
TR = {"076": ["2026-09-23", "2026-10-05", "2026-10-17", "2026-10-29"], "055": ["2026-09-22", "2026-10-04", "2026-10-16", "2026-10-28"]}
cls = h5py.File("data/s2_stack.h5", "r")["cls"]; rng = np.random.default_rng(0); out = {}
for tr, dates in TR.items():
    fs = [h5py.File(f"data/stack/{tr}_{d}.h5", "r") for d in dates]; vals = {p: [[] for _ in dates] for p in ("HH", "HV")}
    for r in range(0, cls.shape[0], 1024):
        forest = np.isin(cls[r:r + 1024], (41, 42, 43, 90))
        st = {p: np.stack([f[p][r:r + 1024] for f in fs]) for p in ("HH", "HV")}
        ok = forest & np.isfinite(st["HH"]).all(0) & np.isfinite(st["HV"]).all(0)
        idx = np.flatnonzero(ok.ravel())
        if idx.size == 0: continue
        idx = rng.choice(idx, min(idx.size, 5000), replace=False)
        for p in vals:
            for i in range(4): vals[p][i].append(st[p][i].reshape(-1)[idx])
    res = {"versions": [re.search(r"_(P\d{5})_", f.attrs["source"]).group(1) + " spec " + f.attrs["specVersion"].decode() for f in fs]}
    for p in vals:
        db = [10 * np.log10(np.concatenate(v)) for v in vals[p]]
        res[p] = {"forest_median_dB": {d: round(float(np.median(x)), 3) for d, x in zip(dates, db)},
                  "pre_pre_median_diff_dB": round(float(np.median(db[1] - db[0])), 3),
                  "post_post_median_diff_dB": round(float(np.median(db[3] - db[2])), 3)}
    out[tr] = res; print(tr, json.dumps(res, indent=1))
json.dump(out, open("docs/pipeline/scene_check.json", "w"), indent=1)
