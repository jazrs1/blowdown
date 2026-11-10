"""Per-box side-by-side figure (NISAR HV diff | S1 VH diff | S2 NDVI diff) on one extent, plus agreement stats."""
import json, os
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

stats = {}
for name, title in (("AL", "Alabama box (Brewton)"), ("FL", "Florida box (Milton/Pace)")):
    ee = np.load(f"data/ee_{name}.npz"); e = ee["extent"]; ext = [e[0], e[2], e[1], e[3]]
    nis = np.load(f"data/nisar_{name}.npz") if os.path.exists(f"data/nisar_{name}.npz") else None
    forest = ee["forest"] == 1
    dn = ee["dNDVI"]
    drop = forest & (dn < -0.10) & (dn > -0.5)    # canopy loss; < -0.5 is mostly flood water
    keep = forest & (dn >= -0.02)                 # forest with no NDVI drop
    panels = [("NISAR HV  post−pre (dB)", nis["dHV"] if nis is not None else None, 3, "RdBu_r"),
              ("Sentinel-1 VH  post−pre (dB)", ee["dVH"], 3, "RdBu_r"),
              ("Sentinel-2 NDVI  post−pre", dn, 0.3, "RdBu")]
    fig, ax = plt.subplots(1, 3, figsize=(18, 6.4), constrained_layout=True)
    s = {"forest_px": int(forest.sum()), "drop_px": int(drop.sum()), "nodrop_px": int(keep.sum())}
    for a, (t, arr, v, cm) in zip(ax, panels):
        if arr is None:
            a.text(0.5, 0.5, "NISAR not yet processed", ha="center", va="center", transform=a.transAxes)
            a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
        else:
            if "dB" in t:  # remove scene-wide offset (calibration/moisture) so the relative pattern is readable
                med = float(np.nanmedian(arr[forest])); arr = arr - med
                t = t + "\n" + f"(forest median {med:+.2f} dB removed)"
            im = a.imshow(arr, extent=ext, cmap=cm, vmin=-v, vmax=v, interpolation="nearest")
            fig.colorbar(im, ax=a, shrink=0.75)
            # stats use offset-removed values; the in-vs-out contrast and r are unaffected
            key = t.split()[0] + ("_" + t.split()[1] if t.startswith("Sentinel") else "")
            ok = np.isfinite(arr) & np.isfinite(dn) & forest & (dn > -0.5)
            s[key] = {"mean_in_ndvi_drop": float(np.nanmean(arr[drop])), "mean_in_no_drop": float(np.nanmean(arr[keep])),
                      "pearson_r_vs_dNDVI_forest": float(np.corrcoef(arr[ok], dn[ok])[0, 1])}
        a.set_title(t); a.set_xlabel("lon"); a.set_ylabel("lat"); a.set_aspect(1 / np.cos(np.radians((e[1] + e[3]) / 2)))
    fig.suptitle(f"{title}: Hurricane Isaias, NISAR 10-05→10-17, S1D 09-28→10-22, S2 09-17→10-20")
    fig.savefig(f"docs/gate/fig_{name}.png", dpi=90); plt.close(fig)
    stats[name] = s
json.dump(stats, open("docs/gate/stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1))
