"""Wind link with both sides of the track: west box (study grid, regions_30.npz, held-out block + 2 km and aerial tip + 2 km
excluded) plus east box (data/east/east_30m.npz, same mask rules). Sentinel-2 damage mask only (no model output).
Damaged share of forest in 5 km bins of signed perpendicular distance from the NHC best track (negative = left/west of motion),
upland and wetland separately; along-track bins from the coast crossing. Damage share by county (TIGER 2018 counties via Earth
Engine) for Covington, Crenshaw (AL), Okaloosa, Walton, Santa Rosa, Escambia (FL) and Escambia (AL), within the mapped boxes.
Writes docs/wind/wind_both.json, docs/wind/fig_wind_both.png, docs/wind/fig_wind_map_both.png."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib, ee
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from pyproj import Transformer
from shapely.geometry import shape
from shapely import contains_xy
import grid as G
import ee_common  # noqa: F401  (initialises Earth Engine, project blowdown)
R = 30.0; l2u = Transformer.from_crs("EPSG:4326", f"EPSG:{G.EPSG}", always_xy=True); u2l = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True)
RG = np.load("data/regions_30.npz"); E = np.load("data/east/east_30m.npz")
XE0 = G.X0 + G.W * 10
boxes = {"west": dict(x0=G.X0, f=RG["forest"] & ~(RG["heldout_excl"] | RG["tip_excl"]), d=RG["damage"], u=RG["upland"], w=RG["wetland"]),
         "east": dict(x0=XE0, f=E["forest"], d=E["damage"], u=E["upland"], w=E["wetland"])}
fix = []
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]
    t = (np.datetime64(f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:8]}T{p[2][8:]}") - np.datetime64("2026-10-10T00")) / np.timedelta64(1, "h")
    if not fix or fix[-1][0] != t: fix.append((float(t), float(p[6][:-1]) / 10, -float(p[7][:-1]) / 10, int(p[8])))
hrs = np.array([q[0] for q in fix]); tx, ty = l2u.transform([q[2] for q in fix], [q[1] for q in fix]); tx, ty = np.array(tx), np.array(ty)
k0 = max(i for i in range(len(fix) - 1) if fix[i][1] <= 30.40 < fix[i + 1][1]); fr = (30.40 - fix[k0][1]) / (fix[k0 + 1][1] - fix[k0][1])
cum = np.r_[0, np.cumsum(np.hypot(np.diff(tx), np.diff(ty)))]; cum_lf = cum[k0] + fr * (cum[k0 + 1] - cum[k0])
ix = np.nonzero((hrs >= -12) & (hrs <= 24))[0]
def signed(X, Y):
    best = np.full(X.shape, np.inf); sg = np.zeros(X.shape); al = np.zeros(X.shape)
    for i in ix[:-1]:
        ax_, ay_, dx, dy = tx[i], ty[i], tx[i + 1] - tx[i], ty[i + 1] - ty[i]; L2 = dx * dx + dy * dy
        t = np.clip(((X - ax_) * dx + (Y - ay_) * dy) / L2, 0, 1); d = np.hypot(X - ax_ - t * dx, Y - ay_ - t * dy)
        m = d < best; best[m] = d[m]; sg[m] = np.where((dx * (Y - ay_) - dy * (X - ax_))[m] > 0, -1.0, 1.0); al[m] = cum[i] - cum_lf + t[m] * np.sqrt(L2)
    return best * sg / 1000, al / 1000
SD, AL = {}, {}
for nm, b in boxes.items():
    h, w = b["f"].shape; X, Y = np.meshgrid(b["x0"] + (np.arange(w) + 0.5) * R, G.Y1 - (np.arange(h) + 0.5) * R); SD[nm], AL[nm] = signed(X, Y)
edges = np.arange(-110, 80, 5); out = {"bins_signed_distance_5km": {}, "bins_along_track_10km": {}}
for dom in ("all", "upland", "wetland"):
    rows = []
    for a, c in zip(edges[:-1], edges[1:]):
        nf = nd = 0
        for nm, b in boxes.items():
            m = b["f"] & (SD[nm] >= a) & (SD[nm] < c)
            if dom != "all": m &= b[dom[0]]
            nf += int(m.sum()); nd += int((m & b["d"]).sum())
        if nf >= 500: rows.append({"from_km": int(a), "to_km": int(c), "side": "right" if a >= 0 else "left", "forest_cells": nf, "damaged_share": round(nd / nf, 4)})
    out["bins_signed_distance_5km"][dom] = rows
for side, sel in (("left", lambda s: s < 0), ("right", lambda s: s >= 0)):
    rows = []
    for a in range(-20, 180, 10):
        nf = nd = 0
        for nm, b in boxes.items():
            m = b["f"] & sel(SD[nm]) & (AL[nm] >= a) & (AL[nm] < a + 10); nf += int(m.sum()); nd += int((m & b["d"]).sum())
        if nf >= 500: rows.append({"from_km": a, "to_km": a + 10, "forest_cells": nf, "damaged_share": round(nd / nf, 4)})
    out["bins_along_track_10km"][side] = rows
def summ(sel):
    nf = nd = 0
    for nm, b in boxes.items():
        m = b["f"] & sel(SD[nm]); nf += int(m.sum()); nd += int((m & b["d"]).sum())
    return {"forest_km2": round(nf * 9e-4, 1), "damage_km2": round(nd * 9e-4, 1), "damaged_share": round(nd / max(nf, 1), 4)}
out["side_summary"] = {"left_0_110km": summ(lambda s: s < 0), "right_0_75km": summ(lambda s: s >= 0),
                       "left_40_80km": summ(lambda s: (s <= -40) & (s > -80)), "right_0_40km": summ(lambda s: (s >= 0) & (s < 40)), "left_0_40km": summ(lambda s: (s < 0) & (s > -40))}
# counties
fc = ee.FeatureCollection("TIGER/2018/Counties").filter(ee.Filter.Or(
    ee.Filter.And(ee.Filter.eq("STATEFP", "01"), ee.Filter.inList("NAME", ["Covington", "Crenshaw", "Escambia"])),
    ee.Filter.And(ee.Filter.eq("STATEFP", "12"), ee.Filter.inList("NAME", ["Okaloosa", "Walton", "Santa Rosa", "Escambia"])))).getInfo()
out["counties"] = {}
for f_ in fc["features"]:
    nm = f_["properties"]["NAME"] + (" AL" if f_["properties"]["STATEFP"] == "01" else " FL"); g = shape(f_["geometry"]); nf = nd = 0; nfm = 0
    for bn, b in boxes.items():
        h, w = b["f"].shape; X, Y = np.meshgrid(b["x0"] + (np.arange(0, w, 2) + 0.5) * R, G.Y1 - (np.arange(0, h, 2) + 0.5) * R); lo, la = u2l.transform(X, Y)
        inside = contains_xy(g, lo, la); ff = b["f"][::2, ::2]; nf += int((inside & ff).sum()); nd += int((inside & ff & b["d"][::2, ::2]).sum())
    out["counties"][nm] = {"mapped_forest_km2": round(nf * 4 * 9e-4, 1), "damage_km2": round(nd * 4 * 9e-4, 1), "damaged_share": round(nd / max(nf, 1), 4) if nf else None}
json.dump(out, open("docs/wind/wind_both.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("side_summary", "counties")}, indent=1))
for dom in ("upland", "wetland"): print(dom, [(r["from_km"], round(r["damaged_share"] * 100, 1)) for r in out["bins_signed_distance_5km"][dom]])
# ---- figures
W = json.load(open("docs/wind/wind.json"))
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.8), constrained_layout=True)
for dn, c, ls in (("upland", "#7D5F33", "-"), ("wetland", "#2F5F73", "-"), ("all", "#22201C", "--")):
    r = out["bins_signed_distance_5km"][dn]; ax[0].plot([(q["from_km"] + q["to_km"]) / 2 for q in r], [q["damaged_share"] * 100 for q in r], ls, c=c, lw=1.7 if ls == "-" else 1, label=dn + " forest")
ax[0].axvline(0, c="k", lw=0.9); ax[0].text(1, 40, "right of track", fontsize=8); ax[0].text(-2, 40, "left of track", fontsize=8, ha="right")
a2 = ax[0].twinx()
for s in W["stations"]:
    if s.get("gust_kt") is None: continue
    sparse = s.get("n_obs_22Z_to_06Z") is not None and s["n_obs_22Z_to_06Z"] < 10
    a2.plot(s["signed_distance_km"], s["gust_kt"], "^", ms=6, mfc="none" if sparse else "#8C4A32", mec="#8C4A32")
a2.set_ylim(0, 120); a2.set_ylabel("station peak gust (kt)", color="#8C4A32")
ax[0].set_xlabel("distance from best track (km), negative = left (west)"); ax[0].set_ylabel("forest in Sentinel-2 damage mask (%)"); ax[0].legend(fontsize=8, loc="upper right")
ax[0].set_title("Damaged share of forest by distance from the track, both sides (5 km bins)", fontsize=10)
for side, c in (("left", "#8C4A32"), ("right", "#2F5F73")):
    r = out["bins_along_track_10km"][side]; ax[1].plot([(q["from_km"] + q["to_km"]) / 2 for q in r], [q["damaged_share"] * 100 for q in r], "-o", ms=3, c=c, label=f"{side} of track")
ax[1].axvline(0, c="k", lw=0.8); ax[1].set_xlabel("distance along the track from the coast crossing (km)"); ax[1].legend(fontsize=8); ax[1].set_title("Damaged share by along-track position, each side (10 km bins)", fontsize=10)
fig.suptitle("Hurricane Isaias: Sentinel-2 damage mask, west and east of the NHC best track (held-out block and aerial tip excluded)", fontsize=11)
fig.savefig("docs/wind/fig_wind_both.png", dpi=90); plt.close(fig)
fig, ax = plt.subplots(figsize=(10, 10))
for nm, b in boxes.items():
    h, w = b["f"].shape; img = np.ones((h, w, 3)); img[b["f"]] = (0.84, 0.84, 0.80); img[b["f"] & b["d"]] = (0.70, 0.18, 0.12)
    if nm == "west": img[RG["heldout_excl"] | RG["tip_excl"]] = (0.62, 0.62, 0.62)
    ax.imshow(img[::3, ::3], extent=[b["x0"] / 1e3, (b["x0"] + w * R) / 1e3, (G.Y1 - h * R) / 1e3, G.Y1 / 1e3], interpolation="nearest")
for nm in ("heldout_excl", "tip_excl"):
    rr, cc = np.nonzero(RG[nm]); cx = (G.X0 + (cc.min() + cc.max()) / 2 * R) / 1e3; cy = (G.Y1 - (rr.min() + rr.max()) / 2 * R) / 1e3
    ax.text(cx, cy, "Held out\nuntil scoring", ha="center", va="center", fontsize=8)
for f_ in fc["features"]:
    g = shape(f_["geometry"]); gs = getattr(g, "geoms", [g])
    for q in gs:
        ring = q.exterior if hasattr(q, "exterior") else q
        if not hasattr(ring, "xy"): continue
        xs, ys = l2u.transform(*ring.xy); ax.plot(np.array(xs) / 1e3, np.array(ys) / 1e3, c="#555", lw=0.6)
    c_ = g.representative_point(); x_, y_ = l2u.transform(c_.x, c_.y)
    ax.text(x_ / 1e3, y_ / 1e3, f_["properties"]["NAME"], fontsize=8, color="#333", ha="center", path_effects=[pe.withStroke(linewidth=2, foreground="white")])
sel = (hrs >= -24) & (hrs <= 18); ax.plot(tx[sel] / 1e3, ty[sel] / 1e3, "-", c="k", lw=2)
for s in W["stations"]:
    if s.get("lat") is None: continue
    x_, y_ = l2u.transform(s["lon"], s["lat"]); ax.plot(x_ / 1e3, y_ / 1e3, "^", c="#2F5F73", ms=6, mec="w")
    ax.annotate(f"{s['short']} {s['gust_kt']:.0f}", (x_ / 1e3, y_ / 1e3), xytext=(4, 3), textcoords="offset points", fontsize=7, color="#1d4f66", path_effects=[pe.withStroke(linewidth=2, foreground="white")])
ax.set_xlim(G.X0 / 1e3 - 2, (XE0 + 7770 * 10) / 1e3 + 2); ax.set_ylim((G.Y1 - 15300 * 10) / 1e3 - 25, G.Y1 / 1e3); ax.set_xlabel("UTM 16N easting (km)"); ax.set_ylabel("northing (km)")
ax.set_title("Sentinel-2 damage mask (red), west and east boxes, best track, counties and peak gusts (kt)", fontsize=10)
fig.savefig("docs/wind/fig_wind_map_both.png", dpi=85, bbox_inches="tight"); plt.close(fig)
