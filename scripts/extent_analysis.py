"""Step 1: band extent per 0.05 deg latitude strip, band outline, overlap with NOAA aerial footprint, map figure."""
import json
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter, label
from shapely.geometry import shape
e = np.load("data/extent_ee.npz"); n = np.load("data/extent_nisar.npz"); a = np.load("data/extent_noaa.npz")
x0, y0, x1, y1 = e["extent"]; RES = float(e["res"]); h, w = e["anom"].shape
lon = x0 + (np.arange(w) + .5) * RES; lat = y1 - (np.arange(h) + .5) * RES
cls = e["cls"]; forest = np.isin(cls, [41, 42, 43, 90]); everg = cls == 42
anom = e["anom"]; good = forest & np.isfinite(anom) & (e["dNDVI26"] > -0.5)  # drop open water / flood extremes
hv = n["dHV"] - np.nanmedian(n["dHV"][forest]); hh = n["dHH"] - np.nanmedian(n["dHH"][forest])

def sm(arr, m, k):
    v = np.where(m & np.isfinite(arr), arr, 0.); c = (m & np.isfinite(arr)).astype(float)
    cc = uniform_filter(c, k); return np.where(cc > 0.2, uniform_filter(v, k) / np.maximum(cc, 1e-6), np.nan)

S = sm(anom, good, 7)                      # ~560 m smoothed forest anomaly
T = -0.06                                  # band threshold (gate band core is ~-0.10..-0.15, background ~0 +/- 0.03)
lab, _ = label(np.nan_to_num(S, nan=0) < T)
seed = lab[int((y1 - 31.2) / RES), int((-87.12 - x0) / RES)]
band = (lab == seed) & (seed > 0)

strips = []
for s0 in np.round(np.arange(30.40, 31.79, 0.05), 2):
    r = (lat >= s0) & (lat < s0 + 0.05)
    m = good[r]
    prof = np.nanmean(np.where(m, -anom[r], np.nan), 0); prof = uniform_filter(np.nan_to_num(prof, nan=np.nanmedian(prof)), 9)
    med = np.median(prof); mad = 1.4826 * np.median(np.abs(prof - med))
    pk = int(np.argmax(prof))
    b = band[r]; bw = b.any(0)
    hv_in = np.nanmean(hv[r][b & good[r]]) if (b & good[r]).sum() > 50 else np.nan
    hv_out = np.nanmean(hv[r][~b & good[r]]) if (~b & good[r]).sum() > 50 else np.nan
    nis_cov = float(np.mean(np.isfinite(n["dHV"][r])))
    strips.append({"lat": f"{s0:.2f}-{s0+0.05:.2f}", "peak_lon": round(float(lon[pk]), 3),
                   "peak_contrast": round(float(prof[pk] - med), 3), "peak_z": round(float((prof[pk] - med) / max(mad, 1e-6)), 1),
                   "band_cols_km": round(float(bw.sum() * RES * 111.32 * np.cos(np.radians(s0))), 1),
                   "band_lon_range": [round(float(lon[bw].min()), 3), round(float(lon[bw].max()), 3)] if bw.any() else None,
                   "nisar_cov": round(nis_cov, 2),
                   "nisar_dHV_in_minus_out": None if np.isnan(hv_in) or np.isnan(hv_out) else round(float(hv_in - hv_out), 2)})
for s in strips: print(s)
cellkm2 = (RES * 111.32 * np.cos(np.radians(lat)) * RES * 110.6)[:, None] * np.ones((1, w))
res = {"threshold": T, "band_km2": float(cellkm2[band].sum()),
       "band_forest_km2": float(a["forest_km2"][band].sum()),
       "band_lat_range": [float(lat[band.any(1)].min()), float(lat[band.any(1)].max())],
       "band_in_noaa_km2": float(a["noaa_km2"][band].sum()),
       "forest_in_band_and_noaa_km2": float(a["forest_noaa_km2"][band].sum()),
       "noaa_footprint_in_study_km2": float(np.nansum(a["noaa_km2"])),
       "forest_in_noaa_study_km2": float(np.nansum(a["forest_noaa_km2"])),
       "band_woody_wetland_frac": float(np.mean(cls[band & forest] == 90)), "study_woody_wetland_frac": float(np.mean(cls[forest] == 90)),
       "band_evergreen_frac": float(np.mean(cls[band & forest] == 42)), "study_evergreen_frac": float(np.mean(cls[forest] == 42)),
       "nisar_band_cov": float(np.mean(np.isfinite(n["dHV"][band]))),
       "nisar_dHV_band_minus_forest": float(np.nanmean(hv[band & good]) - np.nanmean(hv[~band & good])),
       "nisar_dHH_band_minus_forest": float(np.nanmean(hh[band & good]) - np.nanmean(hh[~band & good])),
       "strips": strips}
json.dump(res, open("docs/pipeline/extent.json", "w"), indent=1)
np.save("data/extent_band.npy", band)
print(json.dumps({k: v for k, v in res.items() if k != "strips"}, indent=1))

# figure
fp = shape(json.load(open("data/noaa_footprint_study.geojson")))
ext = [x0, x1, y0, y1]; asp = 1 / np.cos(np.radians(31.1))
fig, ax = plt.subplots(1, 2, figsize=(15, 10.5), constrained_layout=True)
for axx, arr, v, cm, t in [(ax[0], S, .15, "RdBu", "Sentinel-2 NDVI anomaly (2026 − 2025), forest, ~560 m smoothing"),
                           (ax[1], sm(hv, forest & np.isfinite(hv), 7), 1.5, "RdBu_r", "NISAR HV 10-05→10-17 (dB, forest median removed), forest, smoothed")]:
    im = axx.imshow(arr, extent=ext, cmap=cm, vmin=-v, vmax=v); fig.colorbar(im, ax=axx, shrink=.6)
    axx.contour(lon, lat, band.astype(float), [0.5], colors="k", linewidths=1.0)
    for g in getattr(fp, "geoms", [fp]):
        xs, ys = g.exterior.xy; axx.plot(xs, ys, color="purple", lw=1.4)
    for bx in [(-87.35, 30.95, -86.85, 31.45), (-87.25, 30.55, -86.95, 30.80)]:
        axx.plot([bx[0], bx[2], bx[2], bx[0], bx[0]], [bx[1], bx[1], bx[3], bx[3], bx[1]], "g--", lw=1)
    axx.plot(-87.15, 30.95, "k*", ms=12); axx.text(-87.13, 30.95, "Jay", fontsize=10)
    axx.plot(-87.07, 31.10, "k^", ms=7); axx.text(-87.05, 31.10, "Brewton", fontsize=9)
    axx.axhline(31.0, color="gray", lw=.6, ls=":"); axx.text(-87.59, 31.005, "AL / FL ≈ 31.0", fontsize=8, color="gray")
    axx.set_title(t, fontsize=10); axx.set_aspect(asp); axx.set_xlim(x0, x1); axx.set_ylim(y0, y1)
ax[0].plot([], [], "k-", label=f"band outline (smoothed anomaly < {T})"); ax[0].plot([], [], color="purple", label="NOAA aerial footprint")
ax[0].plot([], [], "g--", label="gate boxes"); ax[0].legend(loc="lower right", fontsize=8)
ax[1].text(-87.55, 31.72, "no frame-17 coverage north of ~31.49", fontsize=8)
fig.savefig("docs/pipeline/fig_extent.png", dpi=85)
