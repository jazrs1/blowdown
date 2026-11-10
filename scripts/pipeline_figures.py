"""Step 5/6 figures and tables from evaluate.py outputs.
fig_threshold_maps.png  30 m Youden-threshold maps for arm A (NISAR HV) and arm B (S1 VH) against the provisional reference
fig_auc_resolution.png  AUC vs resolution per arm; per forest type for the headline arms
fig_layers_100m.png     100 m recentred differences (NISAR HV per track, S1 VH 2026 and 2025) and the reference damage fraction
auc_table.md            markdown tables (AUC, dB separation +- sd) used in pipeline.md"""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import grid as G
A, B = "A: NISAR HV (both tracks)", "B: S1 VH (both orbits)"
J = json.load(open("docs/pipeline/auc.json")); rows = J["rows"]
HB, WB = (G.H // 300) * 300, (G.W // 300) * 300
ext = [G.X0 / 1e3, (G.X0 + WB * 10) / 1e3, (G.Y1 - HB * 10) / 1e3, G.Y1 / 1e3]

# ---- threshold maps (30 m)
t = np.load("data/threshold_maps_30.npz"); ft = t["ft"] > 0; ref = t["dmg"] >= 0.5
cmap = ListedColormap(["white", "#d9d9d9", "#f4a582", "#2166ac", "#b2182b", "black"])
def cat(det, valid):
    c = np.zeros(det.shape, "uint8"); c[ft] = 1
    c[ft & det & ~ref] = 2; c[ft & ~det & ref] = 3; c[ft & det & ref] = 4; c[~valid] = 5; return c
refc = np.zeros(ref.shape, "uint8"); refc[ft] = 1; refc[ft & ref] = 4
fig, ax = plt.subplots(1, 3, figsize=(17, 9), constrained_layout=True)
th = J["thresholds_30m"]
for a, (title, img) in zip(ax, [("Provisional optical reference (30 m block >= 50% damage)", refc),
                                (f"Arm A: NISAR HV diff > {th[A]['threshold_dB']:+.2f} dB\nTPR {th[A]['tpr']:.2f}, FPR {th[A]['fpr']:.2f}", cat(t["A"], t["validA"])),
                                (f"Arm B: S1 VH diff > {th[B]['threshold_dB']:+.2f} dB\nTPR {th[B]['tpr']:.2f}, FPR {th[B]['fpr']:.2f}", cat(t["B"], t["validB"]))]):
    a.imshow(img, cmap=cmap, vmin=0, vmax=5, extent=ext, interpolation="nearest"); a.set_title(title, fontsize=10)
    a.set_xlabel("UTM 16N easting (km)"); a.set_ylabel("northing (km)")
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(cmap.colors[1:], ["forest, not flagged", "flagged, not in reference",
           "reference damage, missed", "flagged and in reference", "no radar data"])], loc="lower center", ncol=5, fontsize=9)
fig.suptitle("Threshold maps at 30 m (forest only; Youden-optimal threshold on labelled 30 m blocks)")
fig.savefig("docs/pipeline/fig_threshold_maps.png", dpi=80); plt.close(fig)

# ---- AUC vs resolution
get = lambda arm, ftype, res: next((r["auc"] for r in rows if r["arm"] == arm and r["forest_type"] == ftype and r["res_m"] == res), None)
arms = sorted({r["arm"] for r in rows}, key=lambda s: (not s.startswith("A"), not s.startswith("B:"), s))
fig, ax = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
for arm in arms:
    y = [get(arm, "all", r) for r in (10, 30, 100)]
    st = "-" if arm.startswith(("A", "B")) else ":"; lw = 2.5 if arm.startswith(("A", "B")) else 1.2
    ax[0].plot([10, 30, 100], [np.nan if v is None else v for v in y], st, marker="o", lw=lw, label=arm)
ax[0].set_xscale("log"); ax[0].set_xticks([10, 30, 100], ["10", "30", "100"]); ax[0].axhline(0.5, c="k", lw=.5)
ax[0].set_xlabel("resolution (m)"); ax[0].set_ylabel("ROC AUC (damage vs intact)"); ax[0].set_title("All forest"); ax[0].legend(fontsize=7)
for arm, c in ((A, "C0"), (B, "C1")):
    for ftype, st in (("evergreen", "-"), ("deciduous", "--"), ("woody_wetland", ":")):
        y = [get(arm, ftype, r) for r in (10, 30, 100)]
        ax[1].plot([10, 30, 100], [np.nan if v is None else v for v in y], st, c=c, marker="o", label=f"{arm.split(':')[0]} {ftype}")
ax[1].set_xscale("log"); ax[1].set_xticks([10, 30, 100], ["10", "30", "100"]); ax[1].axhline(0.5, c="k", lw=.5)
ax[1].set_xlabel("resolution (m)"); ax[1].set_title("By forest type: A = NISAR HV, B = S1 VH"); ax[1].legend(fontsize=7)
fig.savefig("docs/pipeline/fig_auc_resolution.png", dpi=85); plt.close(fig)

# ---- 100 m layers
c = np.load("data/coarse_100.npz"); e100 = ext
pan = [("NISAR HV, track 76 asc", c["nisar_076:HV"], 2), ("NISAR HV, track 55 desc", c["nisar_055:HV"], 2),
       ("S1 VH 2026, orbits 19+92", c[B], 2), ("S1 VH 2025 control, same weeks", c["B 2025 control: S1 VH (both orbits)"], 2),
       ("Reference damage fraction", c["dmg"], None)]
fig, ax = plt.subplots(1, 5, figsize=(24, 9), constrained_layout=True)
for a, (tt, img, v) in zip(ax, pan):
    img = np.where(c["ft"] > 0, img, np.nan)
    im = a.imshow(img, extent=e100, cmap="RdBu_r" if v else "Reds", vmin=-v if v else 0, vmax=v if v else 1, interpolation="nearest")
    a.set_title(tt + ("\npost - pre, forest median removed (dB)" if v else "\n(10 m damage pixels per 100 m block)"), fontsize=10)
    fig.colorbar(im, ax=a, shrink=0.6); a.set_xlabel("easting (km)")
ax[0].set_ylabel("northing (km)")
fig.suptitle("100 m forest-only layers (red = backscatter increase / damage)")
fig.savefig("docs/pipeline/fig_layers_100m.png", dpi=70); plt.close(fig)

# ---- tables
L = ["| Arm | Res (m) | AUC | Damage dB (mean ± sd) | Intact dB (mean ± sd) | Δ dB | n damage / intact |", "|---|---|---|---|---|---|---|"]
for arm in arms:
    for res in (10, 30, 100):
        r = next(x for x in rows if x["arm"] == arm and x["res_m"] == res and x["forest_type"] == "all")
        L.append(f"| {arm} | {res} | {r['auc']} | {r['damage_mean_dB']} ± {r['damage_sd_dB']} | {r['intact_mean_dB']} ± {r['intact_sd_dB']} | {r['delta_dB']} | {r['n_damage']:,} / {r['n_intact']:,} |")
L += ["", "| Arm | Res (m) | Evergreen AUC (Δ dB) | Deciduous AUC (Δ dB) | Woody wetland AUC (Δ dB) |", "|---|---|---|---|---|"]
for arm in arms:
    for res in (10, 30, 100):
        cells = []
        for ftype in ("evergreen", "deciduous", "woody_wetland"):
            r = next(x for x in rows if x["arm"] == arm and x["res_m"] == res and x["forest_type"] == ftype)
            cells.append(f"{r['auc']} ({r['delta_dB']}) n={r['n_damage']:,}")
        L.append(f"| {arm} | {res} | " + " | ".join(cells) + " |")
L += ["", "| Res (m) | n (both valid) | n damage | AUC A (NISAR HV) | AUC B (S1 VH) | A − B | 95% bootstrap CI |", "|---|---|---|---|---|---|---|"]
for p in J["paired_A_vs_B"]:
    L.append(f"| {p['res_m']} | {p['n']:,} | {p['n_damage']:,} | {p['auc_A_NISAR_HV']} | {p['auc_B_S1_VH']} | {p['diff']:+.3f} | {p['ci95'][0]:+.3f} to {p['ci95'][1]:+.3f} |")
open("docs/pipeline/auc_table.md", "w", encoding="utf8").write("\n".join(L) + "\n")
print("\n".join(L))
