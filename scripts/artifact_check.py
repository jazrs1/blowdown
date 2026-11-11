"""Artifact check, part 3: do the band's edges line up with acquisition geometry, and does the band survive a single-date
Sentinel-2 difference? Held-out block + 2 km and aerial tip + 2 km are masked everywhere (grey in the figure).
Band edges: west and east band longitude in each 0.05 deg strip (docs/pipeline/extent.json). For each edge point:
  distance (km) to the nearest Sentinel-2 relative-orbit swath edge, MGRS tile edge, Sentinel-1 swath edge and NISAR frame edge
  (boundaries clipped to the study box), and the jump in the composites' median acquisition day and clear-observation count
  between 2 km outside and 2 km inside the edge (200 m composite statistics).
Single-date check: dNDVI and dNBR from the chosen single pre and post scenes vs the composites, on forest at 30 m:
  E-W profiles per strip, edge positions (half-maximum of the smoothed -dNDVI profile), and the share of forest meeting a
  common change proxy (dNBR < -0.10 and dNDVI < -0.06, no 2025 term) by distance from the track.
Writes docs/wind/artifact_check.json and docs/wind/fig_artifact_check.png."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pyproj import Transformer
from shapely.geometry import shape, box, LineString, Point
from shapely.ops import unary_union, transform as stransform
from scipy.ndimage import uniform_filter1d
import grid as G
RG = np.load("data/regions_30.npz"); forest, dmg, band30 = RG["forest"], RG["damage"], RG["band"]; ex = RG["heldout_excl"] | RG["tip_excl"]
H3, W3 = forest.shape; R = 30.0
inv = json.load(open("data/artifact/inventory.json")); ST = np.load("data/artifact/composite_stats_200m.npz"); EXT = json.load(open("docs/pipeline/extent.json"))
SD = json.load(open("data/artifact/single_dates.json")); SN = np.load("data/artifact/single_ndvi_30m.npz")
ll2u = Transformer.from_crs("EPSG:4326", f"EPSG:{G.EPSG}", always_xy=True).transform; u2ll = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True)
STUDY = box(-87.60, 30.40, -86.60, 31.80)
toU = lambda g: stransform(ll2u, g)
def edges(geoms):
    u = unary_union([shape(g).buffer(0) for g in geoms]).intersection(STUDY.buffer(0.3))
    return toU(u.boundary.intersection(STUDY))
lines = {}
for orb in sorted({x["rel_orbit"] for w in ("pre", "post") for x in inv["s2"][w]}):
    lines[f"S2 orbit {orb} swath edge"] = edges([x["footprint"] for w in ("pre", "post") for x in inv["s2"][w] if x["rel_orbit"] == orb])
tiles = sorted({x["tile"] for w in ("pre", "post") for x in inv["s2"][w]})
tile_geoms = {t: unary_union([shape(x["footprint"]).buffer(0) for w in ("pre", "post") for x in inv["s2"][w] if x["tile"] == t]).convex_hull for t in tiles}
lines["S2 MGRS tile edge"] = toU(unary_union([g.boundary for g in tile_geoms.values()]).intersection(STUDY))
for o in (19, 92): lines[f"S1 orbit {o} swath edge"] = edges([x["footprint"] for x in inv["s1"] if x["orbit"] == o])
for t in ("076", "055"): lines[f"NISAR track {t} frame edge"] = edges([x["footprint"] for x in inv["nisar"] if x["track"] == t])
# band edge points
pts = []
for s in EXT["strips"]:
    if not s["band_lon_range"]: continue
    la = float(s["lat"].split("-")[0]) + 0.025
    for side, lo in (("west", s["band_lon_range"][0]), ("east", s["band_lon_range"][1])): pts.append({"lat": la, "lon": lo, "side": side})
res = {"band_edge_points": []}
x200 = G.X0 + (np.arange(ST["pre_n"].shape[1]) + 0.5) * 200; y200 = G.Y1 - (np.arange(ST["pre_n"].shape[0]) + 0.5) * 200
def stat_at(name, x, y):
    j = int(np.clip((x - G.X0) // 200, 0, len(x200) - 1)); i = int(np.clip((G.Y1 - y) // 200, 0, len(y200) - 1)); return float(ST[name][i, j])
for p in pts:
    x, y = ll2u(p["lon"], p["lat"]); P = Point(x, y); d = {k: round(P.distance(g) / 1000, 1) if not g.is_empty else None for k, g in lines.items()}
    sgn = -1 if p["side"] == "west" else 1           # outside is west of the west edge, east of the east edge
    xo, xi = x + sgn * 2000, x - sgn * 2000
    jump = {f"{w}_{q}": round(stat_at(f"{w}_{q}", xi, y) - stat_at(f"{w}_{q}", xo, y), 1) for w in ("pre", "post") for q in ("doy_median", "n")}
    in_heldout = bool(ex[int(np.clip((G.Y1 - y) // R, 0, H3 - 1)), int(np.clip((x - G.X0) // R, 0, W3 - 1))])
    res["band_edge_points"].append({**p, "distance_km": d, "inside_minus_outside": jump, "in_heldout_exclusion": in_heldout})
ok = [q for q in res["band_edge_points"] if not q["in_heldout_exclusion"]]
res["summary"] = {}
for k in lines:
    v = [q["distance_km"][k] for q in ok if q["distance_km"][k] is not None]
    res["summary"][k] = {"edge_points": len(v), "within_1km": int(sum(x <= 1 for x in v)), "within_3km": int(sum(x <= 3 for x in v)), "median_km": round(float(np.median(v)), 1) if v else None}
for q_ in ("pre_doy_median", "post_doy_median", "pre_n", "post_n"):
    v = np.array([q["inside_minus_outside"][q_] for q in ok]); res["summary"][f"jump {q_} (inside - outside, 2 km)"] = {"median": round(float(np.median(v)), 2), "abs_ge_2": int((np.abs(v) >= 2).sum()), "n": len(v)}
# ---- composite vs single-date at 30 m
S = h5py.File("data/s2_stack.h5", "r"); cn = np.zeros((H3, W3), "float32"); cb = np.zeros_like(cn)
for r in range(0, H3 * 3, 600):
    re_ = min(r + 600, H3 * 3)
    with np.errstate(invalid="ignore"):
        cn[r // 3:re_ // 3] = np.nanmean((S["ndvi_post"][r:re_, :W3 * 3] - S["ndvi_pre"][r:re_, :W3 * 3]).reshape(-1, 3, W3, 3), (1, 3))
        cb[r // 3:re_ // 3] = np.nanmean((S["nbr_post"][r:re_, :W3 * 3] - S["nbr_pre"][r:re_, :W3 * 3]).reshape(-1, 3, W3, 3), (1, 3))
sn = SN["ndvi_post"] - SN["ndvi_pre"]; sb = SN["nbr_post"] - SN["nbr_pre"]
valid = forest & ~ex & np.isfinite(cn) & np.isfinite(sn)
res["single_dates"] = SD["chosen"]
res["single_vs_composite"] = {"forest_cells_valid_both": int(valid.sum()), "share_valid_of_forest": round(float(valid.sum() / (forest & ~ex).sum()), 3),
                              "pearson_r_dNDVI": round(float(np.corrcoef(cn[valid], sn[valid])[0, 1]), 3),
                              "mean_dNDVI_single_in_damage_mask": round(float(sn[valid & dmg].mean()), 3), "mean_dNDVI_single_outside": round(float(sn[valid & ~dmg].mean()), 3),
                              "mean_dNDVI_composite_in_damage_mask": round(float(cn[valid & dmg].mean()), 3), "mean_dNDVI_composite_outside": round(float(cn[valid & ~dmg].mean()), 3)}
pc = (cb < -0.10) & (cn < -0.06); ps = (sb < -0.10) & (sn < -0.06)
res["single_vs_composite"]["proxy_agreement"] = {"proxy_share_composite": round(float(pc[valid].mean()), 4), "proxy_share_single": round(float(ps[valid].mean()), 4),
                                                 "single_proxy_share_in_damage_mask": round(float(ps[valid & dmg].mean()), 3), "single_proxy_share_outside_mask": round(float(ps[valid & ~dmg].mean()), 3)}
# E-W profiles per strip and half-max edges
xc = G.X0 + (np.arange(W3) + 0.5) * R; yc = G.Y1 - (np.arange(H3) + 0.5) * R
LON, LAT = u2ll.transform(*np.meshgrid(xc, yc))
prof = []
for s in EXT["strips"]:
    if not s["band_lon_range"]: continue
    a0 = float(s["lat"].split("-")[0]); m = (LAT >= a0) & (LAT < a0 + 0.05)
    bins = np.arange(-87.60, -86.59, 0.01); rec = {"lat": s["lat"]}
    for nm, arr in (("composite", cn), ("single", sn)):
        v = np.where(m & valid, -arr, np.nan); idx = np.digitize(LON, bins)
        pr = np.array([np.nanmean(v[(idx == k) & m]) if ((idx == k) & m & valid).sum() > 200 else np.nan for k in range(1, len(bins))])
        sm = uniform_filter1d(np.nan_to_num(pr, nan=np.nanmedian(pr)), 5); base = np.nanmedian(sm); pk = int(np.argmax(sm)); half = base + (sm[pk] - base) / 2
        w = pk
        while w > 0 and sm[w] > half: w -= 1
        e = pk
        while e < len(sm) - 1 and sm[e] > half: e += 1
        rec[nm] = {"peak_lon": round(float(bins[pk] + 0.005), 3), "west_halfmax_lon": round(float(bins[w] + 0.005), 3), "east_halfmax_lon": round(float(bins[e] + 0.005), 3), "peak_minus_base": round(float(sm[pk] - base), 3)}
        rec[nm + "_profile"] = [None if not np.isfinite(q) else round(float(q), 4) for q in pr]
    prof.append(rec)
res["profiles"] = [{k: v for k, v in r.items() if not k.endswith("_profile")} for r in prof]
dw = [abs(r["single"]["west_halfmax_lon"] - r["composite"]["west_halfmax_lon"]) * 96 for r in prof]; de = [abs(r["single"]["east_halfmax_lon"] - r["composite"]["east_halfmax_lon"]) * 96 for r in prof]
res["edge_shift_single_vs_composite_km"] = {"west_median": round(float(np.median(dw)), 1), "east_median": round(float(np.median(de)), 1), "strips": len(prof)}
json.dump(res, open("docs/wind/artifact_check.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("band_edge_points", "profiles")}, indent=1)); print(json.dumps(res["profiles"][:4], indent=0))
# ---- figure
fig = plt.figure(figsize=(16, 11), constrained_layout=True); gs = fig.add_gridspec(2, 4, height_ratios=[1.35, 1])
ext = [G.X0 / 1e3, (G.X0 + W3 * R) / 1e3, (G.Y1 - H3 * R) / 1e3, G.Y1 / 1e3]
def base_img():
    img = np.ones((H3, W3, 3)); img[forest] = (0.86, 0.86, 0.82); img[forest & dmg] = (0.68, 0.17, 0.11); img[ex] = (0.62, 0.62, 0.62); return img[::3, ::3]
from heldout_mask import band_outline_ll
_blo, _bla, _Bs, _ = band_outline_ll()
_BX, _BY = ll2u(*np.meshgrid(_blo, _bla))
def band_outline(ax):
    ax.contour(_BX / 1e3, _BY / 1e3, _Bs, levels=[0.3], colors="k", linewidths=1.0)
# 200 m held-out mask for the composite-statistics panels
_x2 = G.X0 + (np.arange(ST["pre_n"].shape[1]) + 0.5) * 200; _y2 = G.Y1 - (np.arange(ST["pre_n"].shape[0]) + 0.5) * 200
_ii = np.clip(((G.Y1 - _y2) // R).astype(int), 0, H3 - 1); _jj = np.clip(((_x2 - G.X0) // R).astype(int), 0, W3 - 1); EX200 = ex[np.ix_(_ii, _jj)]
ax = fig.add_subplot(gs[0, 0:2]); ax.imshow(base_img(), extent=ext, interpolation="nearest"); band_outline(ax)
sty = {"S2 orbit 40 swath edge": ("C0", "-", 1.6), "S2 orbit 83 swath edge": ("C1", "-", 1.6), "S2 MGRS tile edge": ("0.35", ":", 1.0),
       "S1 orbit 19 swath edge": ("C2", "--", 1.4), "S1 orbit 92 swath edge": ("C4", "--", 1.4), "NISAR track 076 frame edge": ("k", "-.", 1.4), "NISAR track 055 frame edge": ("0.45", "-.", 1.4)}
for k, g in lines.items():
    c, ls, lw = sty.get(k, ("m", "-", 1)); first = True
    for seg in (getattr(g, "geoms", None) or [g]):
        if seg.is_empty or not hasattr(seg, "xy"): continue
        xs, ys = seg.xy; ax.plot(np.array(xs) / 1e3, np.array(ys) / 1e3, ls, c=c, lw=lw, label=k if first else None); first = False
for q in ok: ax.plot(*[v / 1e3 for v in ll2u(q["lon"], q["lat"])], "o", ms=3, c="yellow", mec="k", mew=0.4)
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.legend(fontsize=7, loc="lower left", framealpha=0.9)
ax.set_title("Acquisition geometry over the damage mask (red)" + chr(10) + "black = band outline, yellow = edge points, grey = held out", fontsize=9)
for k, (nm, ttl) in enumerate((("pre_doy_median", "pre composite: median acquisition day of year"), ("post_doy_median", "post composite: median acquisition day of year"))):
    a = fig.add_subplot(gs[0, 2 + k]); v = ST[nm].copy().astype(float); v[EX200] = np.nan
    im = a.imshow(v, extent=ext, cmap="viridis", interpolation="nearest"); a.imshow(np.where(EX200, 1.0, np.nan), extent=ext, cmap=ListedColormap(["#9e9e9e"]), interpolation="nearest"); band_outline(a); fig.colorbar(im, ax=a, shrink=0.6); a.set_title(ttl, fontsize=9)
cmapd = matplotlib.colormaps["BrBG"]
for k, (arr, ttl) in enumerate(((cn, "composite dNDVI" + chr(10) + "(1 Sep-8 Oct vs 11 Oct-9 Nov medians)"), (sn, "single-date dNDVI" + chr(10) + f"({SD['chosen']['pre']['date']} vs {SD['chosen']['post']['date']}, orbit {SD['chosen']['rel_orbit']})"))):
    a = fig.add_subplot(gs[1, k]); v = np.where(forest & ~ex, arr, np.nan); im = a.imshow(v[::3, ::3], extent=ext, cmap=cmapd, vmin=-0.25, vmax=0.25, interpolation="nearest")
    gr = np.where(ex, 1.0, np.nan); a.imshow(gr[::3, ::3], extent=ext, cmap=ListedColormap(["#9e9e9e"]), interpolation="nearest"); band_outline(a); a.set_title(ttl, fontsize=9)
fig.colorbar(im, ax=a, shrink=0.6)
a = fig.add_subplot(gs[1, 2:4]); bins = np.arange(-87.60, -86.59, 0.01)
Fh = h5py.File("data/models/features_train.h5", "r")
with np.errstate(invalid="ignore"):
    hvp = np.nanmean(np.stack([Fh["t76_HV_diff_m7"][()], Fh["t55_HV_diff_m7"][()]]), 0); vhp = np.nanmean(np.stack([Fh["o19_VH_diff_m7"][()], Fh["o92_VH_diff_m7"][()]]), 0)
idx = np.digitize(LON, bins)
def prof_of(arr, m, sg):
    v = np.where(m & np.isfinite(arr), sg * arr, np.nan)
    pr = np.array([np.nanmean(v[(idx == k) & m]) if ((idx == k) & m & np.isfinite(arr)).sum() > 200 else np.nan for k in range(1, len(bins))])
    pr = uniform_filter1d(np.nan_to_num(pr, nan=np.nanmedian(pr)), 3); lo_, hi_ = np.nanpercentile(pr, 5), np.nanmax(pr); return (pr - lo_) / max(hi_ - lo_, 1e-6)
for i, a0 in enumerate((30.65, 30.70, 30.80, 30.90, 31.05, 31.45)):
    m = (LAT >= a0) & (LAT < a0 + 0.05) & valid; off = i * 1.3; xb = bins[:-1] + 0.005
    for arr, sg, c, ls, lab in ((cn, -1, "C0", "-", "S2 composite -dNDVI"), (sn, -1, "C3", "--", "S2 single-date -dNDVI"), (hvp, 1, "k", "-", "NISAR HV diff (7x7)"), (vhp, 1, "C2", ":", "S1 VH diff (7x7)")):
        a.plot(xb, prof_of(arr, m, sg) + off, ls, c=c, lw=1.1, label=lab if i == 0 else None)
    a.text(-87.59, off + 0.75, f"{a0:.2f}-{a0 + 0.05:.2f} N", fontsize=7)
a.axvline(-87.0, c="0.4", ls="-.", lw=1); a.text(-86.995, -0.25, "87.0 W = MGRS column edge", fontsize=7)
a.set_xlabel("longitude"); a.set_yticks([]); a.legend(fontsize=7, loc="upper right", ncol=2)
a.set_title("East-west profiles over forest, each scaled to its own range (offset by strip)", fontsize=9)
fig.savefig("docs/wind/fig_artifact_check.png", dpi=80)
