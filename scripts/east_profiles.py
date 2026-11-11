"""Mean change over forest by signed distance from the best track, both sides, for three independent layers, to see
whether the west-east asymmetry depends on the Sentinel-2 mask threshold:
  Sentinel-2 dNDVI (composites; west s2_stack.h5, east s2_stack_east.h5; 30 m means), NISAR HV track 76 single pair
  10-05 -> 10-17 (both boxes, data/east/nisar_pair_30m_both.npz), Sentinel-1 VH orbit 19 (09-28 -> 10-22; west features_train,
  east east_30m; same re-centring constant on both sides).
Forest cells only; held-out block + 2 km and aerial tip + 2 km excluded. 5 km bins; all forest and upland.
Writes docs/wind/east_profiles.json and docs/wind/fig_east_profiles.png."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Transformer
import grid as G
R = 30.0; l2u = Transformer.from_crs("EPSG:4326", f"EPSG:{G.EPSG}", always_xy=True)
RG = np.load("data/regions_30.npz"); E = np.load("data/east/east_30m.npz"); NP = np.load("data/east/nisar_pair_30m_both.npz")
ex = RG["heldout_excl"] | RG["tip_excl"]; XE0 = G.X0 + G.W * 10
def dndvi(path, H, W):
    S = h5py.File(path, "r"); out = np.zeros((H // 3, W // 3), "float32")
    for r in range(0, H, 600):
        re_ = min(r + 600, H)
        with np.errstate(invalid="ignore"): out[r // 3:re_ // 3] = np.nanmean((S["ndvi_post"][r:re_, :W] - S["ndvi_pre"][r:re_, :W]).reshape(-1, 3, W // 3, 3), (1, 3))
    return out
F = h5py.File("data/models/features_train.h5", "r")
L = {"west": {"x0": G.X0, "forest": RG["forest"] & ~ex, "upland": RG["upland"], "dNDVI": dndvi("data/s2_stack.h5", 15300, 9600),
              "NISAR HV t76 pair": NP["west_t76_HV_pair_diff"], "S1 VH orbit 19": F["o19_VH_diff"][()]},
     "east": {"x0": XE0, "forest": E["forest"], "upland": E["upland"], "dNDVI": dndvi("data/east/s2_stack_east.h5", 15300, 7770),
              "NISAR HV t76 pair": NP["east_t76_HV_pair_diff"], "S1 VH orbit 19": None}}
# east S1 orbit 19 only: east_30m 's1_vh_oct' is nanmean(o19, o92) and o92 does not cover the east box -> it is orbit 19
L["east"]["S1 VH orbit 19"] = np.where(E["s1_o19_valid"], E["s1_vh_oct"], np.nan)
fix = []
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]
    t = (np.datetime64(f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:8]}T{p[2][8:]}") - np.datetime64("2026-10-10T00")) / np.timedelta64(1, "h")
    if not fix or fix[-1][0] != t: fix.append((float(t), float(p[6][:-1]) / 10, -float(p[7][:-1]) / 10))
hrs = np.array([q[0] for q in fix]); tx, ty = l2u.transform([q[2] for q in fix], [q[1] for q in fix]); tx, ty = np.array(tx), np.array(ty); ix = np.nonzero((hrs >= -12) & (hrs <= 24))[0]
def signed(X, Y):
    best = np.full(X.shape, np.inf); sg = np.zeros(X.shape)
    for i in ix[:-1]:
        ax_, ay_, dx, dy = tx[i], ty[i], tx[i + 1] - tx[i], ty[i + 1] - ty[i]; L2 = dx * dx + dy * dy
        t = np.clip(((X - ax_) * dx + (Y - ay_) * dy) / L2, 0, 1); d = np.hypot(X - ax_ - t * dx, Y - ay_ - t * dy)
        m = d < best; best[m] = d[m]; sg[m] = np.where((dx * (Y - ay_) - dy * (X - ax_))[m] > 0, -1.0, 1.0)
    return best * sg / 1000
for b in L.values():
    h, w = b["forest"].shape; X, Y = np.meshgrid(b["x0"] + (np.arange(w) + 0.5) * R, G.Y1 - (np.arange(h) + 0.5) * R); b["sd"] = signed(X, Y)
edges = np.arange(-110, 80, 5); out = {}
for lay in ("dNDVI", "NISAR HV t76 pair", "S1 VH orbit 19"):
    for dom in ("all", "upland"):
        rows = []
        for a, c in zip(edges[:-1], edges[1:]):
            vals = []
            for b in L.values():
                arr = b[lay]; hh, ww = b["forest"].shape; arr = arr[:hh, :ww]
                m = b["forest"] & (b["sd"] >= a) & (b["sd"] < c) & np.isfinite(arr)
                if dom == "upland": m &= b["upland"]
                vals.append(arr[m])
            v = np.concatenate(vals)
            if v.size >= 500: rows.append({"from_km": int(a), "mean": round(float(v.mean()), 4), "n": int(v.size)})
        out[f"{lay} | {dom}"] = rows
json.dump(out, open("docs/wind/east_profiles.json", "w"), indent=1)
fig, axs = plt.subplots(1, 3, figsize=(16, 4.4), constrained_layout=True)
for ax, (lay, unit, sg) in zip(axs, (("dNDVI", "NDVI change (negative = loss)", 1), ("NISAR HV t76 pair", "HV change (dB, re-centered)", 1), ("S1 VH orbit 19", "VH change (dB, re-centered)", 1))):
    for dom, ls in (("all", "-"), ("upland", "--")):
        r = out[f"{lay} | {dom}"]; ax.plot([q["from_km"] + 2.5 for q in r], [q["mean"] for q in r], ls, c="k" if dom == "all" else "#7D5F33", label=f"{dom} forest")
    ax.axvline(0, c="0.4", lw=0.8); ax.axhline(0, c="0.7", lw=0.6); ax.set_title(lay + " (mean over forest, 5 km bins)", fontsize=10); ax.set_xlabel("km from track (negative = west)"); ax.set_ylabel(unit)
axs[0].legend(fontsize=8)
fig.suptitle("Change by distance from the best track, both sides, three independent layers (held-out block and aerial tip excluded)", fontsize=11)
fig.savefig("docs/wind/fig_east_profiles.png", dpi=85)
for k, v in out.items(): print(k, [(q["from_km"], q["mean"]) for q in v if q["from_km"] in (-65, -55, -35, -15, 5, 25, 45, 65)])
