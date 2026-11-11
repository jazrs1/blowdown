"""Artifact check, part 4: the band's east edge runs near the MGRS column boundary at easting 500,000 m (87.0 W) in the
south. Two tests, forest cells at 30 m, held-out block + 2 km and aerial tip + 2 km excluded:
1) Step across x = 500,000 m: mean dNDVI (composite and single-date) in 0-2 km strips west and east of the line, by 0.05 deg
   latitude strip, flagged by whether the band touches the line in that strip. A tile-processing artifact would show a step
   at the line also where the band is absent.
2) Independent sensors: half-maximum east/west edges of the NISAR HV (two-track stack) and Sentinel-1 VH (October-only)
   difference profiles, against the Sentinel-2 composite edges, per strip (radar has no MGRS tiles).
Edges = westmost / eastmost longitude where each smoothed profile, scaled to its own 5th-percentile-to-max range, reaches 0.5.
Writes docs/wind/artifact_edges.json."""
import json, sys; sys.path.insert(0, "scripts")
import h5py, numpy as np
from pyproj import Transformer
from scipy.ndimage import uniform_filter1d
import grid as G
RG = np.load("data/regions_30.npz"); forest, band = RG["forest"], RG["band"]; ex = RG["heldout_excl"] | RG["tip_excl"]; H3, W3 = forest.shape; R = 30.0
S = h5py.File("data/s2_stack.h5", "r"); cn = np.zeros((H3, W3), "float32")
for r in range(0, H3 * 3, 600):
    re_ = min(r + 600, H3 * 3)
    with np.errstate(invalid="ignore"): cn[r // 3:re_ // 3] = np.nanmean((S["ndvi_post"][r:re_, :W3 * 3] - S["ndvi_pre"][r:re_, :W3 * 3]).reshape(-1, 3, W3, 3), (1, 3))
SN = np.load("data/artifact/single_ndvi_30m.npz"); sn = SN["ndvi_post"] - SN["ndvi_pre"]
F = h5py.File("data/models/features_train.h5", "r")
with np.errstate(invalid="ignore"):
    hv = np.nanmean(np.stack([F["t76_HV_diff_m7"][()], F["t55_HV_diff_m7"][()]]), 0); vh = np.nanmean(np.stack([F["o19_VH_diff_m7"][()], F["o92_VH_diff_m7"][()]]), 0)
xc = G.X0 + (np.arange(W3) + 0.5) * R; yc = G.Y1 - (np.arange(H3) + 0.5) * R
u2l = Transformer.from_crs(f"EPSG:{G.EPSG}", "EPSG:4326", always_xy=True); LON, LAT = u2l.transform(*np.meshgrid(xc, yc))
ok = forest & ~ex
out = {"step_at_x500km": [], "radar_vs_s2_edges": []}
jw = (xc >= 498000) & (xc < 500000); je = (xc >= 500000) & (xc < 502000)
for a0 in np.round(np.arange(30.45, 31.75, 0.05), 2):
    rows = (LAT[:, 1600] >= a0) & (LAT[:, 1600] < a0 + 0.05)
    if rows.sum() == 0: continue
    m = ok[rows]; touch = bool(band[rows][:, jw | je].any())
    rec = {"lat": f"{a0:.2f}", "band_touches_line": touch}
    for nm, arr in (("composite", cn), ("single", sn)):
        v = arr[rows]; w_ = np.nanmean(np.where(m[:, jw], v[:, jw], np.nan)); e_ = np.nanmean(np.where(m[:, je], v[:, je], np.nan))
        rec[f"{nm}_east_minus_west"] = None if not (np.isfinite(w_) and np.isfinite(e_)) else round(float(e_ - w_), 4)
    out["step_at_x500km"].append(rec)
for k in ("composite", "single"):
    t = [r[f"{k}_east_minus_west"] for r in out["step_at_x500km"] if r["band_touches_line"] is False and r[f"{k}_east_minus_west"] is not None]
    b = [r[f"{k}_east_minus_west"] for r in out["step_at_x500km"] if r["band_touches_line"] is True and r[f"{k}_east_minus_west"] is not None]
    out[f"step_summary_{k}"] = {"strips_without_band": len(t), "median_step_without_band": round(float(np.median(t)), 4) if t else None, "max_abs_step_without_band": round(float(np.max(np.abs(t))), 4) if t else None,
                                "strips_with_band": len(b), "median_step_with_band": round(float(np.median(b)), 4) if b else None}
def halfmax(prof, bins):
    """Westmost and eastmost longitude where the smoothed profile, scaled 5th percentile -> max to 0 -> 1, is >= 0.5.
    (Robust to profiles with several sub-peaks, unlike a single-peak half-maximum.)"""
    sm = uniform_filter1d(np.nan_to_num(prof, nan=np.nanmedian(prof)), 3); lo, hi = np.nanpercentile(sm, 5), np.nanmax(sm); z = (sm - lo) / max(hi - lo, 1e-9)
    on = np.nonzero(z >= 0.5)[0]; pk = int(np.argmax(sm))
    return bins[on.min()] + 0.005, bins[on.max()] + 0.005, bins[pk] + 0.005, float(hi - lo)
bins = np.arange(-87.60, -86.59, 0.01)
EXT = json.load(open("docs/pipeline/extent.json"))
for s in EXT["strips"]:
    if not s["band_lon_range"]: continue
    a0 = float(s["lat"].split("-")[0]); m = (LAT >= a0) & (LAT < a0 + 0.05) & ok; idx = np.digitize(LON, bins); rec = {"lat": s["lat"]}
    for nm, arr, sg in (("s2_composite", cn, -1), ("nisar_hv", hv, 1), ("s1_vh", vh, 1)):
        v = np.where(m & np.isfinite(arr), sg * arr, np.nan)
        pr = np.array([np.nanmean(v[(idx == k) & m]) if ((idx == k) & m & np.isfinite(arr)).sum() > 200 else np.nan for k in range(1, len(bins))])
        if np.isfinite(pr).sum() < 20: rec[nm] = None; continue
        w, e, p, amp = halfmax(pr, bins[:-1]); rec[nm] = {"west": round(float(w), 3), "east": round(float(e), 3), "peak": round(float(p), 3), "amp": round(amp, 3)}
    out["radar_vs_s2_edges"].append(rec)
out["radar_vs_s2_edges_note"] = "per-strip extents from a single threshold are unstable for the noisier radar profiles (sub-peaks outside the band); use profile_alignment"
# profile alignment: correlation at zero shift and the east-west shift (km) that maximises correlation, per strip
def norm(pr):
    sm = uniform_filter1d(np.nan_to_num(pr, nan=np.nanmedian(pr)), 3); return (sm - sm.mean()) / max(sm.std(), 1e-9)
out["profile_alignment"] = []
for s in EXT["strips"]:
    if not s["band_lon_range"]: continue
    a0 = float(s["lat"].split("-")[0]); m = (LAT >= a0) & (LAT < a0 + 0.05) & ok; idx = np.digitize(LON, bins); P = {}
    for nm, arr, sg in (("s2", cn, -1), ("nisar_hv", hv, 1), ("s1_vh", vh, 1)):
        v = np.where(m & np.isfinite(arr), sg * arr, np.nan)
        P[nm] = norm(np.array([np.nanmean(v[(idx == k) & m]) if ((idx == k) & m & np.isfinite(arr)).sum() > 200 else np.nan for k in range(1, len(bins))]))
    rec = {"lat": s["lat"]}
    for nm in ("nisar_hv", "s1_vh"):
        best = max(range(-25, 26), key=lambda L: np.corrcoef(P["s2"][max(0, L):len(P["s2"]) + min(0, L)], P[nm][max(0, -L):len(P[nm]) - max(0, L)])[0, 1])
        rec[nm] = {"r_zero_shift": round(float(np.corrcoef(P["s2"], P[nm])[0, 1]), 2), "best_shift_km": round(best * 0.01 * 96, 1)}
    out["profile_alignment"].append(rec)
for nm in ("nisar_hv", "s1_vh"):
    r0 = [q[nm]["r_zero_shift"] for q in out["profile_alignment"]]; sh = [q[nm]["best_shift_km"] for q in out["profile_alignment"]]
    shs = [q[nm]["best_shift_km"] for q in out["profile_alignment"] if 30.65 <= float(q["lat"].split("-")[0]) < 30.95]
    out[f"alignment_summary_{nm}"] = {"median_r_zero_shift": round(float(np.median(r0)), 2), "median_abs_best_shift_km": round(float(np.median(np.abs(sh))), 1),
                                      "median_abs_best_shift_km_30.65_30.95N": round(float(np.median(np.abs(shs))), 1), "strips": len(r0)}
json.dump(out, open("docs/wind/artifact_edges.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k.startswith(("step_summary", "edge_offset", "alignment"))}, indent=1))
for q in out["profile_alignment"]: print(q)
for r in out["step_at_x500km"]: print(r)
for r in out["radar_vs_s2_edges"]: print(r["lat"], {k: (v["west"], v["east"]) if v else None for k, v in r.items() if k != "lat"})
