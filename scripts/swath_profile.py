"""Longitude profiles (mean over forest, per column) of NISAR dHV/dHH, S1 dVH and S2 dNDVI per box,
plus in/out-of-NDVI-drop contrasts for HH. A N-S swath shows up as a matching bump in the profiles."""
import json
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
out = {}
fig, axs = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
for ax, name in zip(axs, ("AL", "FL")):
    ee = np.load(f"data/ee_{name}.npz"); ni = np.load(f"data/nisar_{name}.npz"); e = ee["extent"]
    forest = ee["forest"] == 1; dn = ee["dNDVI"]
    ok = forest & (dn > -0.5)  # exclude water
    lon = e[0] + (np.arange(dn.shape[1]) + .5) * float(ee["res"])
    def prof(a):
        a = np.where(ok & np.isfinite(a), a, np.nan); return np.nanmean(a, axis=0)
    P = {"NISAR dHV": prof(ni["dHV"]), "NISAR dHH": prof(ni["dHH"]), "S1 dVH": prof(ee["dVH"]), "S2 dNDVI": prof(dn)}
    r = {k: float(np.corrcoef(*[np.nan_to_num(x - np.nanmean(x)) for x in (v, P["S2 dNDVI"])])[0, 1]) for k, v in P.items() if k != "S2 dNDVI"}
    drop = forest & (dn < -0.10) & (dn > -0.5); keep = forest & (dn >= -0.02)
    out[name] = {"profile_r_vs_dNDVI": r,
                 "NISAR_dHH_in_drop": float(np.nanmean(ni["dHH"][drop])), "NISAR_dHH_no_drop": float(np.nanmean(ni["dHH"][keep])),
                 "NISAR_dHV_in_drop": float(np.nanmean(ni["dHV"][drop])), "NISAR_dHV_no_drop": float(np.nanmean(ni["dHV"][keep]))}
    for k, v in P.items():
        z = (v - np.nanmean(v)) / np.nanstd(v)
        ax.plot(lon, -z if k == "S2 dNDVI" else z, label=k + (" (sign flipped)" if k == "S2 dNDVI" else ""), lw=1.2)
    ax.set_title(f"{name}: column-mean over forest (standardised); up = more damage-like for NDVI")
    ax.set_xlabel("lon"); ax.legend(fontsize=8); ax.axhline(0, c="k", lw=.5)
fig.savefig("docs/gate/fig_profiles.png", dpi=90)
json.dump(out, open("docs/gate/profiles.json", "w"), indent=1); print(json.dumps(out, indent=1))
