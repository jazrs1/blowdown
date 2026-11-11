"""Figure and band statistics for the NEXRAD maximum-|V| maps (nexrad_maxvel.py).
Band test: for each radar, mean of the maximum |V| inside the damage band (pipeline extent mask, held-out exclusions removed)
vs. outside the band at the same range from the radar (annulus matched to the band's range distribution, land and sea),
which keeps beam height comparable. Held-out block + 2 km and aerial tip + 2 km are grayed and excluded.
Writes docs/wind/nexrad.json (adds band_test) and docs/wind/fig_nexrad_maxvel.png."""
import json, sys; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Geod
gd = Geod(ellps="WGS84"); J = json.load(open("docs/wind/nexrad.json"))
from scipy.ndimage import uniform_filter
B = np.load("data/extent_band.npy"); Bs = uniform_filter(B.astype(float), 15); e = np.load("data/extent_ee.npz"); bx0, by0, bx1, by1 = e["extent"]; rb = float(e["res"])
blo = bx0 + (np.arange(B.shape[1]) + 0.5) * rb; bla = by1 - (np.arange(B.shape[0]) + 0.5) * rb
from heldout_mask import band_outline_ll
_blo, _bla, _Bs, _ = band_outline_ll()
held = json.load(open("site/data/heldout.geojson")); from shapely.geometry import shape; from shapely import contains_xy
HP = [shape(f["geometry"]) for f in held["features"]]
fx = []
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]
    if not fx or fx[-1][0] != p[2]: fx.append((p[2], float(p[6][:-1]) / 10, -float(p[7][:-1]) / 10))
fig, axs = plt.subplots(2, 2, figsize=(13, 12), constrained_layout=True)
for col, site in enumerate(("KMOB", "KEVX")):
    d = np.load(f"data/nexrad/maxvel_{site}.npz"); v, tm, lo, la = d["vmax"], d["tmax_h"], d["lon"], d["lat"]
    LO, LA = np.meshgrid(lo + 0.00525, la + 0.0045)
    hmask = np.zeros(v.shape, bool)
    for g in HP: hmask |= contains_xy(g, LO, LA)
    v = np.where(hmask, np.nan, v); tm = np.where(hmask, np.nan, tm)
    bi = np.clip(((by1 - LA) / rb).astype(int), 0, B.shape[0] - 1); bj = np.clip(((LO - bx0) / rb).astype(int), 0, B.shape[1] - 1)
    inb = B[bi, bj] & (LA >= by0) & (LA <= by1) & (LO >= bx0) & (LO <= bx1)
    s_lat, s_lon, _ = J[site]["site"]; _, _, rng = gd.inv(np.full(LO.shape, s_lon), np.full(LA.shape, s_lat), LO, LA); rng /= 1000
    rb_in = rng[inb & np.isfinite(v)]; lo_r, hi_r = np.percentile(rb_in, [5, 95])
    ann = (~inb) & (rng >= lo_r) & (rng <= hi_r) & np.isfinite(v) & (LA > 30.2) & (LA < 31.9) & (LO > -88.0) & (LO < -86.0)
    J[site]["band_test"] = {"band_range_km_5_95": [round(float(lo_r), 1), round(float(hi_r), 1)], "mean_max_absV_in_band_ms": round(float(np.nanmean(v[inb])), 1),
                            "mean_max_absV_same_range_outside_band_ms": round(float(np.nanmean(v[ann])), 1), "p90_in_band": round(float(np.nanpercentile(v[inb & np.isfinite(v)], 90)), 1),
                            "p90_outside_same_range": round(float(np.nanpercentile(v[ann], 90)), 1), "cells_in_band": int((inb & np.isfinite(v)).sum()), "cells_outside": int(ann.sum()),
                            "median_time_of_max_in_band_h_from_00Z": round(float(np.nanmedian(tm[inb])), 2)}
    for row, (arr, cmap, vmin, vmax, lab) in enumerate(((v, "magma_r", 20, 60, "2nd-highest |radial velocity| (m/s), lowest sweep"), (tm, "twilight_shifted", -2, 6, "time of the highest accepted value (h from 00Z)"))):
        ax = axs[row, col]; im = ax.pcolormesh(lo, la, arr, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        ax.contour(_blo, _bla, _Bs, levels=[0.3], colors="#2F5F73", linewidths=1.3)
        for g in HP:
            c = np.array(g.exterior.coords); ax.fill(c[:, 0], c[:, 1], color="#9e9e9e", ec="#555", lw=0.6)
        ax.plot([q[2] for q in fx], [q[1] for q in fx], "-", c="k", lw=1.4)
        ax.plot(s_lon, s_lat, "s", c="k", ms=7)
        for rr in (50, 100, 150):
            az = np.linspace(0, 360, 181); lo_c, la_c, _ = gd.fwd(np.full(181, s_lon), np.full(181, s_lat), az, np.full(181, rr * 1000)); ax.plot(lo_c, la_c, ":", c="0.4", lw=0.6)
        ax.set_xlim(-88.4, -85.5); ax.set_ylim(29.8, 32.3); ax.set_aspect(1 / np.cos(np.radians(31)))
        fig.colorbar(im, ax=ax, shrink=0.7, label=lab)
        hb = J[site]["beam_height_over_band"]["band_center_31.0N_87.15W"]
        ax.set_title(f"{site}: {lab}\nbeam center over the band ~{hb['beam_center_height_m_asl']/1000:.1f} km ({hb['range_km']:.0f} km range); blue = band outline; gray = held out", fontsize=9)
fig.suptitle("NEXRAD Level II lowest velocity sweep, 22Z 9 Oct to 06Z 10 Oct 2026: dealiased radial velocity (wind component along the beam, at beam height; not surface wind)", fontsize=10)
fig.savefig("docs/wind/fig_nexrad_maxvel.png", dpi=75)
json.dump(J, open("docs/wind/nexrad.json", "w"), indent=1); print(json.dumps({s: J[s]["band_test"] for s in ("KMOB", "KEVX")}, indent=1))
