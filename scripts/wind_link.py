"""Site step 1: wind link. Sentinel-2 damage mask (not model output) against the NHC best track.
Track: data/wind/bal092026.dat (NHC ATCF b-deck, operational best track, retrieved from ftp.nhc.noaa.gov/atcf/btk/).
For every 30 m forest cell of the prediction grid (regions_30.npz), excluding the held-out block + 2 km buffer and the
aerial tip + 2 km buffer (both masked grey, "Held out until scoring"):
  signed perpendicular distance to the track polyline (b-deck fixes joined by straight lines in UTM 16N; positive = right
  of the direction of motion), and along-track distance from landfall (NWS: near Destin, 20:30 CDT 9 Oct = 01:30Z 10 Oct,
  placed on the track by linear interpolation in time between the 00Z and 06Z fixes).
Damaged share = damage cells / forest cells (30 m damage cell = >= 50% of 10 m pixels in the mask), in 5 km bins of signed
distance, for upland and wetland (regions_30 definitions) and all forest; bins with < 500 forest cells are dropped.
Gust stations: data/wind/stations.json (values and sources). Writes docs/wind/wind.json, docs/wind/fig_damage_vs_distance.png,
docs/wind/fig_wind_map.png."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle
from pyproj import Transformer
import grid as G
RG = np.load("data/regions_30.npz"); forest, dmg, up, wt = RG["forest"], RG["damage"], RG["upland"], RG["wetland"]
excl = RG["heldout_excl"] | RG["tip_excl"]; H3, W3 = forest.shape; R = 30.0
to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{G.EPSG}", always_xy=True); to_ll = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True)
# ---- track
fix = {}
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]
    t = p[2]; la = float(p[6][:-1]) / 10 * (1 if p[6][-1] == "N" else -1); lo = float(p[7][:-1]) / 10 * (-1 if p[7][-1] == "W" else 1)
    fix[t] = {"time": t, "lat": la, "lon": lo, "vmax_kt": int(p[8]), "mslp_mb": int(p[9]) if p[9].strip() not in ("", "0") else None, "type": p[10]}
fixes = [fix[k] for k in sorted(fix)]
radii = {}
for line in open("data/wind/bal092026.dat"):
    p = [x.strip() for x in line.split(",")]
    if p[11] in ("34", "50", "64") and p[2] in ("2026100918", "2026101000", "2026101006"):
        radii.setdefault(p[2], {"rmw_nm": int(p[19]) if p[19] else None})[p[11] + "kt_NE_SE_SW_NW_nm"] = [int(p[13]), int(p[14]), int(p[15]), int(p[16])]
tx, ty = to_utm.transform([f["lon"] for f in fixes], [f["lat"] for f in fixes]); tx, ty = np.array(tx), np.array(ty)
hrs = np.array([(np.datetime64(f"{f['time'][:4]}-{f['time'][4:6]}-{f['time'][6:8]}T{f['time'][8:]}") - np.datetime64("2026-10-10T00")) / np.timedelta64(1, "h") for f in fixes], float)
# landfall point: where the best track crosses 30.40N (the Gulf coast at ~86.58W, Okaloosa Island / Fort Walton Beach),
# between the 00Z and 06Z fixes; NWS gives landfall near Destin about 01:30Z. Time-interpolation would put it ~12 km inland.
LAT_COAST = 30.40
k0 = max(i for i in range(len(fixes) - 1) if fixes[i]["lat"] <= LAT_COAST < fixes[i + 1]["lat"])
fr = (LAT_COAST - fixes[k0]["lat"]) / (fixes[k0 + 1]["lat"] - fixes[k0]["lat"]); lf_h = hrs[k0] + fr * (hrs[k0 + 1] - hrs[k0])
lfx, lfy = tx[k0] + fr * (tx[k0 + 1] - tx[k0]), ty[k0] + fr * (ty[k0 + 1] - ty[k0])
# cumulative along-track distance, zero at landfall
seg_len = np.hypot(np.diff(tx), np.diff(ty)); cum = np.r_[0, np.cumsum(seg_len)]
cum_lf = np.interp(lf_h, hrs, cum); along_fix = cum - cum_lf
# ---- cell distances (only segments near the grid matter; use fixes from 09 Oct 12Z to 11 Oct 00Z)
use = (hrs >= -12) & (hrs <= 24); ix = np.nonzero(use)[0]
xc = G.X0 + (np.arange(W3) + 0.5) * R; yc = G.Y1 - (np.arange(H3) + 0.5) * R
X, Y = np.meshgrid(xc, yc)
best = np.full(X.shape, np.inf); sgn = np.zeros(X.shape); along = np.zeros(X.shape)
for i in ix[:-1]:
    ax_, ay_, bx_, by_ = tx[i], ty[i], tx[i + 1], ty[i + 1]; dx, dy = bx_ - ax_, by_ - ay_; L2 = dx * dx + dy * dy
    t = np.clip(((X - ax_) * dx + (Y - ay_) * dy) / L2, 0, 1); px, py = ax_ + t * dx, ay_ + t * dy
    d = np.hypot(X - px, Y - py); cross = dx * (Y - ay_) - dy * (X - ax_)       # > 0: left of motion
    m = d < best; best[m] = d[m]; sgn[m] = np.where(cross[m] > 0, -1.0, 1.0)[...]; along[m] = (along_fix[i] + t[m] * np.sqrt(L2))
sd_km = best * sgn / 1000; along_km = along / 1000
ok = forest & ~excl
out = {"track_source": "NHC ATCF b-deck bal092026.dat, https://ftp.nhc.noaa.gov/atcf/btk/bal092026.dat",
       "retrieved_utc": open("data/wind/bal092026.retrieved").read().strip(), "fixes": fixes,
       "landfall": {"method": "point where the best track crosses 30.40N (coast); NWS Mobile: landfall near Destin ~8:30 PM CDT 9 Oct (01:30Z)", "track_time_at_crossing_h_after_00Z": round(float(lf_h), 2),
                    "lon_lat_on_track": [round(v, 4) for v in to_ll.transform(lfx, lfy)]},
       "wind_radii_bdeck": radii,
       "grid_signed_distance_km_range": [round(float(sd_km[ok].min()), 1), round(float(sd_km[ok].max()), 1)],
       "forest_cells_right_of_track": int((ok & (sd_km > 0)).sum()), "forest_cells_left_of_track": int((ok & (sd_km < 0)).sum())}
edges = np.arange(np.floor(sd_km[ok].min() / 5) * 5, np.ceil(sd_km[ok].max() / 5) * 5 + 5, 5)
bins = {}
for dn, dm in (("all", ok), ("upland", ok & up), ("wetland", ok & wt)):
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = dm & (sd_km >= a) & (sd_km < b); n = int(m.sum())
        if n < 500: continue
        rows.append({"from_km": float(a), "to_km": float(b), "side": "right" if a >= 0 else "left", "forest_cells": n, "damaged_share": round(float(dmg[m].mean()), 4)})
    bins[dn] = rows
out["bins_signed_distance_5km"] = bins
aedges = np.arange(np.floor(along_km[ok].min() / 10) * 10, np.ceil(along_km[ok].max() / 10) * 10 + 10, 10); arows = []
for a, b in zip(aedges[:-1], aedges[1:]):
    m = ok & (along_km >= a) & (along_km < b); n = int(m.sum())
    if n >= 500: arows.append({"from_km": float(a), "to_km": float(b), "forest_cells": n, "damaged_share": round(float(dmg[m].mean()), 4),
                              "damaged_share_upland": round(float(dmg[m & up].mean()), 4) if (m & up).sum() >= 500 else None,
                              "damaged_share_wetland": round(float(dmg[m & wt].mean()), 4) if (m & wt).sum() >= 500 else None})
out["bins_along_track_from_landfall_10km"] = arows
# where is the damage? centroid of damage cells in signed distance
dd = sd_km[ok & dmg]; out["damage_signed_distance_km_quantiles"] = {q: round(float(np.quantile(dd, q / 100)), 1) for q in (10, 25, 50, 75, 90)}
fd = sd_km[ok]; out["forest_signed_distance_km_quantiles"] = {q: round(float(np.quantile(fd, q / 100)), 1) for q in (10, 25, 50, 75, 90)}
ST = json.load(open("data/wind/stations.json"))
for s in ST["stations"]:
    if s.get("lat") is not None:
        sx, sy = to_utm.transform(s["lon"], s["lat"]); i = int(np.clip((G.Y1 - sy) // R, 0, H3 - 1)); j = int(np.clip((sx - G.X0) // R, 0, W3 - 1))
        inside = 0 <= (G.Y1 - sy) / R < H3 and 0 <= (sx - G.X0) / R < W3
        # signed distance for the station via the same segments
        dmin, sg = np.inf, 0
        for k in ix[:-1]:
            ax_, ay_, bx_, by_ = tx[k], ty[k], tx[k + 1], ty[k + 1]; dx, dy = bx_ - ax_, by_ - ay_; L2 = dx * dx + dy * dy
            t = np.clip(((sx - ax_) * dx + (sy - ay_) * dy) / L2, 0, 1); d = np.hypot(sx - ax_ - t * dx, sy - ay_ - t * dy)
            if d < dmin: dmin, sg = d, (-1 if dx * (sy - ay_) - dy * (sx - ax_) > 0 else 1)
        s["signed_distance_km"] = round(dmin * sg / 1000, 1); s["inside_study_grid"] = bool(inside)
out["stations"] = ST["stations"]
json.dump(out, open("docs/wind/wind.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("fixes", "bins_signed_distance_5km", "stations")}, indent=1))
for dn, rows in bins.items(): print(dn, [(r["from_km"], r["damaged_share"]) for r in rows])
for s in ST["stations"]: print(s["name"], s.get("gust_kt"), s.get("signed_distance_km"))
# ---- figure: damaged share vs signed distance
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
for dn, c in (("upland", "#7D5F33"), ("wetland", "#2f6f8f"), ("all", "#22201C")):
    r = bins[dn]; xm = [(q["from_km"] + q["to_km"]) / 2 for q in r]
    ax[0].plot(xm, [q["damaged_share"] * 100 for q in r], "-o", ms=3, c=c, lw=1.6 if dn != "all" else 1, ls="-" if dn != "all" else "--", label=dn.replace("_", " ") + " forest")
ax[0].axvline(0, c="k", lw=0.8)
a2 = ax[0].twinx()
for s in ST["stations"]:
    if s.get("signed_distance_km") is None or not s.get("gust_kt"): continue
    sparse = s.get("n_obs_22Z_to_06Z") is not None and s["n_obs_22Z_to_06Z"] < 10
    a2.plot(s["signed_distance_km"], s["gust_kt"], "^", ms=7, mfc="none" if sparse else "#2f6f8f", mec="#2f6f8f")
    a2.annotate(s["short"], (s["signed_distance_km"], s["gust_kt"]), xytext=(4, 3), textcoords="offset points", fontsize=7, color="#1d4f66")
a2.set_ylabel("station peak gust (kt); hollow = < 10 reports 22Z-06Z", color="#1d4f66", fontsize=8); a2.set_ylim(0, 120)
ax[0].set_xlabel("distance from best track (km); negative = left (west) of motion"); ax[0].set_ylabel("forest cells in Sentinel-2 damage mask (%)")
ax[0].set_title("Damaged share of forest by distance from the track (5 km bins);\nno study-grid forest lies right of the track", fontsize=10); ax[0].legend(fontsize=8)
xm = [(q["from_km"] + q["to_km"]) / 2 for q in arows]
for key, c, lab in (("damaged_share_upland", "#7D5F33", "upland"), ("damaged_share_wetland", "#2f6f8f", "wetland"), ("damaged_share", "#22201C", "all")):
    ax[1].plot(xm, [np.nan if q[key] is None else q[key] * 100 for q in arows], "-o", ms=3, c=c, ls="-" if lab != "all" else "--", label=lab)
ax[1].axvline(0, c="k", lw=0.8); ax[1].set_xlabel("distance along the track from landfall (km; negative = offshore, before landfall)")
ax[1].set_title("Damaged share by along-track position (10 km bins)", fontsize=10); ax[1].legend(fontsize=8)
fig.suptitle("Hurricane Isaias: Sentinel-2 damage mask vs NHC best track (held-out block and aerial tip excluded)", fontsize=11)
fig.savefig("docs/wind/fig_damage_vs_distance.png", dpi=90); plt.close(fig)
# ---- map
fig, ax = plt.subplots(figsize=(7.5, 10))
ext = [G.X0 / 1e3, (G.X0 + W3 * R) / 1e3, (G.Y1 - H3 * R) / 1e3, G.Y1 / 1e3]
img = np.ones((H3, W3, 3)); img[forest] = (0.84, 0.84, 0.80); img[forest & dmg] = (0.70, 0.18, 0.12); img[excl] = (0.62, 0.62, 0.62)
ax.imshow(img[::3, ::3], extent=ext, interpolation="nearest")
for nm in ("heldout_excl", "tip_excl"):
    rr, cc = np.nonzero(RG[nm]); x0, x1 = G.X0 + cc.min() * R, G.X0 + (cc.max() + 1) * R; y1, y0 = G.Y1 - rr.min() * R, G.Y1 - (rr.max() + 1) * R
    ax.add_patch(Rectangle((x0 / 1e3, y0 / 1e3), (x1 - x0) / 1e3, (y1 - y0) / 1e3, fill=False, ec="#555", lw=1))
    ax.text((x0 + x1) / 2e3, (y0 + y1) / 2e3, "Held out\nuntil scoring", ha="center", va="center", fontsize=9, color="#222")
sel = (hrs >= -24) & (hrs <= 18)
ax.plot(tx[sel] / 1e3, ty[sel] / 1e3, "-", c="#22201C", lw=2)
for k in np.nonzero(sel)[0]:
    ax.plot(tx[k] / 1e3, ty[k] / 1e3, "o", c="#22201C", ms=4)
    ax.annotate(f"{fixes[k]['time'][6:8]}/{fixes[k]['time'][8:]}Z {fixes[k]['vmax_kt']} kt", (tx[k] / 1e3, ty[k] / 1e3), xytext=(6, 0), textcoords="offset points", fontsize=7)
ax.plot(lfx / 1e3, lfy / 1e3, "*", c="#22201C", ms=12); ax.annotate("landfall (track meets coast)", (lfx / 1e3, lfy / 1e3), xytext=(6, -10), textcoords="offset points", fontsize=8)
for s in ST["stations"]:
    if s.get("lat") is None: continue
    sx, sy = to_utm.transform(s["lon"], s["lat"])
    ax.plot(sx / 1e3, sy / 1e3, "^" if s.get("gust_kt") and s["gust_kt"] >= 90 else "v", c="#2f6f8f", ms=7, mec="white")
    ax.annotate(f"{s['short']} {s['gust_kt']:.0f} kt" + (" (approx. location)" if s.get("location_approximate") else ""), (sx / 1e3, sy / 1e3), xytext=(5, 3), textcoords="offset points", fontsize=7.5, color="#1d4f66", path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
ax.set_xlim(ext[0] - 5, ext[1] + 45); ax.set_ylim(ext[2] - 25, ext[3]); ax.set_xlabel("UTM 16N easting (km)"); ax.set_ylabel("northing (km)")
ax.set_title("Isaias best track, peak gusts (kt) and Sentinel-2 damage mask (red)\nstudy grid only; grey = held out until scoring", fontsize=10)
fig.savefig("docs/wind/fig_wind_map.png", dpi=90, bbox_inches="tight"); plt.close(fig)
