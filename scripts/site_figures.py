"""Site figures in the house style of hurricane.johnazer.com (paper #EDEDE7, ink #22201C, accent #7D5F33, model #8C4A32).
From docs/site/site_numbers.json (controls numbers recomputed with the held-out block and aerial tip excluded) and
docs/wind/wind.json (also excluding them). Writes site/figures/*.png at 2x."""
import json, os
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
os.makedirs("site/figures", exist_ok=True)
PAPER, INK, BODY, MUTED, RULE, HAIR, ACC, MOD, WET = "#EDEDE7", "#22201C", "#4A463E", "#6E6859", "#B6B2A5", "#D6D2C6", "#7D5F33", "#8C4A32", "#2F5F73"
plt.rcParams.update({"font.family": ["Georgia", "DejaVu Serif"], "font.size": 10.5, "axes.facecolor": PAPER, "figure.facecolor": PAPER, "savefig.facecolor": PAPER,
                     "axes.edgecolor": RULE, "axes.labelcolor": BODY, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": HAIR, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False})
def save(fig, name): fig.savefig(f"site/figures/{name}", dpi=200, bbox_inches="tight"); plt.close(fig)
# 1. storm vs no-storm (NISAR HV, track 76 single 12-day pairs)
N = json.load(open("docs/site/site_numbers.json"))   # held-out block and aerial tip excluded (site_numbers.py)
sv = N["storm_vs_control_HV"]
g = lambda dom, res: (sv[f"storm | {dom} | {res} m"], sv[f"nostorm_2026 | {dom} | {res} m"], sv[f"nostorm_2025 | {dom} | {res} m"])
groups = [("All forest, 100 m",) + g("all forest", 100), ("Upland forest, 100 m",) + g("strict upland", 100), ("All forest, 30 m",) + g("all forest", 30)]
fig, ax = plt.subplots(figsize=(7.2, 3.4)); w = 0.26
for k, (lab, a, c, b) in enumerate(groups):
    for j, (v, col, nm) in enumerate(((a, MOD, "Storm pair, 5 to 17 Oct 2026"), (c, MUTED, "No storm, 11 to 23 Sep 2026"), (b, RULE, "No storm, 22 Oct to 3 Nov 2025"))):
        ax.bar(k + (j - 1) * w, v - 0.5, w * 0.92, bottom=0.5, color=col, label=nm if k == 0 else None)
        ax.text(k + (j - 1) * w, v + 0.008, f"{v:.2f}", ha="center", fontsize=8.5, color=BODY)
ax.set_xticks(range(len(groups)), [g[0] for g in groups]); ax.set_ylim(0.45, 0.88); ax.axhline(0.5, color=INK, lw=0.8)
ax.set_ylabel("AUC, damage vs intact"); ax.legend(fontsize=8.5, loc="upper right"); ax.grid(axis="x", visible=False)
save(fig, "storm_vs_control.png")
# 2. persistence
PN = N["persistence_30m"]
def recmap(d):
    return {"NISAR HV t76 2026-10-17 (pre 10-05)": [d["NISAR HV post 10-17"]], "NISAR HV t76 2026-10-29 (pre 10-05)": [d["NISAR HV post 10-29"]],
            "NISAR HH t76 2026-10-17 (pre 10-05)": [d["NISAR HH post 10-17"]], "NISAR HH t76 2026-10-29 (pre 10-05)": [d["NISAR HH post 10-29"]],
            "S1 VH o92 2026-10-27": [d["S1 VH o92 post 10-27"]], "S1 VH o92 2026-11-08": [d["S1 VH o92 post 11-08"]],
            "NISAR HV no-storm B (2025)": [d["NISAR HV no-storm 2025"]], "NISAR HV no-storm C (2026 pre)": [d["NISAR HV no-storm 2026"]]}
U = {"upland | 30 m": recmap(PN["upland"]), "woody_wetland | 30 m": recmap(PN["woody_wetland"])}
day = lambda s: (np.datetime64("2026-" + s) - np.datetime64("2026-10-01")).astype(int)
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
for a, dom, title in zip(axs, ("upland | 30 m", "woody_wetland | 30 m"), ("Upland forest", "Woody wetland")):
    rec = U[dom]
    a.plot([day("10-17"), day("10-29")], [rec["NISAR HV t76 2026-10-17 (pre 10-05)"][0], rec["NISAR HV t76 2026-10-29 (pre 10-05)"][0]], "-o", color=MOD, lw=1.8, ms=4, label="NISAR HV")
    a.plot([day("10-17"), day("10-29")], [rec["NISAR HH t76 2026-10-17 (pre 10-05)"][0], rec["NISAR HH t76 2026-10-29 (pre 10-05)"][0]], "--o", color=MOD, lw=1.2, ms=3.5, label="NISAR HH")
    a.plot([day("10-27"), day("11-08")], [rec["S1 VH o92 2026-10-27"][0], rec["S1 VH o92 2026-11-08"][0]], "-s", color=WET, lw=1.6, ms=3.5, label="Sentinel-1 VH, orbit 92")
    lo = min(rec["NISAR HV no-storm B (2025)"][0], rec["NISAR HV no-storm C (2026 pre)"][0]); hi = max(rec["NISAR HV no-storm B (2025)"][0], rec["NISAR HV no-storm C (2026 pre)"][0])
    a.axhspan(lo - 0.02, hi + 0.02, color=HAIR, lw=0); a.text(day("11-08"), hi + 0.035, "NISAR HV, no-storm pairs", fontsize=8, color=MUTED, ha="right")
    a.axhline(0, color=INK, lw=0.7); a.set_title(title, fontsize=11, color=INK, loc="left")
    a.set_xticks([day(x) for x in ("10-17", "10-29", "11-08")], ["17 Oct", "29 Oct", "8 Nov"], fontsize=8.5)
axs[0].set_ylabel("damage minus intact (dB)")
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=3, fontsize=8.5, bbox_to_anchor=(0.5, -0.06))
fig.text(0.5, -0.11, "Sentinel-1 points are 27 October and 8 November.", ha="center", fontsize=8, color=MUTED)
save(fig, "persistence.png")
# 3. wind: damaged share vs distance from track
W = json.load(open("docs/wind/wind.json")); WB2 = json.load(open("docs/wind/wind_both.json"))   # both sides of the track
fig, ax = plt.subplots(figsize=(7.4, 3.6))
for dn, col, ls, lab in (("wetland", WET, "-", "Woody wetland"), ("upland", ACC, "-", "Upland forest"), ("all", INK, "--", "All forest")):
    r = WB2["bins_signed_distance_5km"][dn]; ax.plot([(q["from_km"] + q["to_km"]) / 2 for q in r], [q["damaged_share"] * 100 for q in r], ls, color=col, lw=1.7 if ls == "-" else 1.1, label=lab)
ax.axvline(0, color=INK, lw=0.9); ax.text(-2, 46, "west of track", ha="right", fontsize=8.5, color=MUTED); ax.text(2, 46, "east of track", ha="left", fontsize=8.5, color=MUTED)
a2 = ax.twinx(); a2.grid(False); a2.spines["right"].set_visible(True)
for s in W["stations"]:
    if s.get("gust_kt") is None: continue
    sparse = s.get("n_obs_22Z_to_06Z") is not None and s["n_obs_22Z_to_06Z"] < 10
    a2.plot(s["signed_distance_km"], s["gust_kt"], "^", ms=6.5, mfc="none" if sparse else MOD, mec=MOD)
for s in W["stations"]:
    if s["short"] in ("Jay", "Oriole Beach", "Whiting Field South", "Eglin AFB", "Destin"):
        off = (4, -12) if s["short"] == "Whiting Field South" else (4, 4)
        a2.annotate(s["short"].replace("Whiting Field South", "Whiting Field"), (s["signed_distance_km"], s["gust_kt"]), xytext=off, textcoords="offset points", fontsize=8, color=MOD)
a2.set_ylim(0, 120); a2.set_ylabel("peak gust (kt), triangles", color=MOD); a2.tick_params(colors=MOD)
ax.set_xlabel("distance from the best track (km), negative = west, positive = east"); ax.set_ylabel("forest in damage mask (%)")
ax.set_ylim(0, 50); ax.legend(fontsize=8.5, loc="upper right"); ax.set_xlim(-108, 76)
save(fig, "wind_distance.png")
# ---- narrow versions for phones (served below 620 px by <picture>), same data, larger relative type
plt.rcParams.update({"font.size": 10})
fig, ax = plt.subplots(figsize=(3.9, 4.4)); w = 0.27
short = ["All forest\n100 m", "Upland\n100 m", "All forest\n30 m"]
for k, (lab, a, c, b) in enumerate(groups):
    for j, (v, col, nm) in enumerate(((a, MOD, "Storm, 5 to 17 Oct 2026"), (c, MUTED, "No storm, Sep 2026"), (b, RULE, "No storm, Oct to Nov 2025"))):
        ax.bar(k + (j - 1) * w, v - 0.5, w * 0.92, bottom=0.5, color=col, label=nm if k == 0 else None)
        ax.text(k + (j - 1) * w, v + 0.008, f"{v:.2f}", ha="center", fontsize=7.5, color=BODY)
ax.set_xticks(range(3), short); ax.set_ylim(0.45, 0.88); ax.axhline(0.5, color=INK, lw=0.8); ax.grid(axis="x", visible=False)
ax.set_ylabel("AUC, damage vs intact"); ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
save(fig, "storm_vs_control_narrow.png")
fig, axs = plt.subplots(2, 1, figsize=(3.9, 6.2), sharex=True)
for a, dom, title in zip(axs, ("upland | 30 m", "woody_wetland | 30 m"), ("Upland forest", "Woody wetland")):
    rec = U[dom]
    a.plot([day("10-17"), day("10-29")], [rec["NISAR HV t76 2026-10-17 (pre 10-05)"][0], rec["NISAR HV t76 2026-10-29 (pre 10-05)"][0]], "-o", color=MOD, lw=1.8, ms=4, label="NISAR HV")
    a.plot([day("10-17"), day("10-29")], [rec["NISAR HH t76 2026-10-17 (pre 10-05)"][0], rec["NISAR HH t76 2026-10-29 (pre 10-05)"][0]], "--o", color=MOD, lw=1.2, ms=3.5, label="NISAR HH")
    a.plot([day("10-27"), day("11-08")], [rec["S1 VH o92 2026-10-27"][0], rec["S1 VH o92 2026-11-08"][0]], "-s", color=WET, lw=1.6, ms=3.5, label="Sentinel-1 VH, orbit 92")
    lo = min(rec["NISAR HV no-storm B (2025)"][0], rec["NISAR HV no-storm C (2026 pre)"][0]); hi = max(rec["NISAR HV no-storm B (2025)"][0], rec["NISAR HV no-storm C (2026 pre)"][0])
    a.axhspan(lo - 0.02, hi + 0.02, color=HAIR, lw=0); a.text(day("11-08"), hi + 0.04, "NISAR HV, no storm", fontsize=8, color=MUTED, ha="right")
    a.axhline(0, color=INK, lw=0.7); a.set_title(title, fontsize=10.5, color=INK, loc="left"); a.set_ylim(-0.08, 1.1)
    a.set_ylabel("damage − intact (dB)")
axs[1].set_xticks([day(x) for x in ("10-17", "10-29", "11-08")], ["17 Oct", "29 Oct", "8 Nov"])
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=1, fontsize=8.5, bbox_to_anchor=(0.5, -0.1))
save(fig, "persistence_narrow.png")
fig, ax = plt.subplots(figsize=(3.9, 4.0))
for dn, col, ls, lab in (("wetland", WET, "-", "Woody wetland"), ("upland", ACC, "-", "Upland forest"), ("all", INK, "--", "All forest")):
    r = WB2["bins_signed_distance_5km"][dn]; ax.plot([(q["from_km"] + q["to_km"]) / 2 for q in r], [q["damaged_share"] * 100 for q in r], ls, color=col, lw=1.7 if ls == "-" else 1.1, label=lab)
ax.axvline(0, color=INK, lw=0.9)
a2 = ax.twinx(); a2.grid(False); a2.spines["right"].set_visible(True)
for s in W["stations"]:
    if s.get("gust_kt") is None: continue
    sparse = s.get("n_obs_22Z_to_06Z") is not None and s["n_obs_22Z_to_06Z"] < 10
    a2.plot(s["signed_distance_km"], s["gust_kt"], "^", ms=5.5, mfc="none" if sparse else MOD, mec=MOD)
for s in W["stations"]:
    if s["short"] == "Jay": a2.annotate("Jay", (s["signed_distance_km"], s["gust_kt"]), xytext=(-30, 6), textcoords="offset points", fontsize=8, color=MOD, arrowprops=dict(arrowstyle="-", color=MOD, lw=0.6))
a2.set_ylim(0, 120); a2.set_ylabel("peak gust (kt)", color=MOD); a2.tick_params(colors=MOD)
ax.set_xlabel("km from track (negative = west)"); ax.set_ylabel("forest in damage mask (%)"); ax.set_ylim(0, 50); ax.set_xlim(-108, 76)
ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
save(fig, "wind_distance_narrow.png")
from PIL import Image
for f in sorted(os.listdir("site/figures")): print(f, os.path.getsize(f"site/figures/{f}"), Image.open(f"site/figures/{f}").size)
