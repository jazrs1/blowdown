"""Is the AL NDVI/NISAR band storm damage or autumn phenology?
1) NLCD class on the shared grid -> profiles/contrasts for evergreen (42) vs deciduous+woody wetland (41, 90).
2) Same seasonal windows in 2025 (cloud-masked median composites) -> dNDVI_2025; anomaly = dNDVI_2026 - dNDVI_2025.
"""
import sys, json; sys.path.insert(0, "scripts")
import numpy as np, ee, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from ee_common import BOXES
EXT = {"AL": (-87.35, 30.95, -86.85, 31.45), "FL": (-87.25, 30.55, -86.95, 30.80)}
RES = 0.0008
nlcd = ee.ImageCollection("projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER") \
    .filter(ee.Filter.stringContains("system:index", "2025")).first().select("b1")

def ndvi_med(a, b, g):
    def m(i):
        s = i.select("SCL"); ok = s.neq(3).And(s.neq(8)).And(s.neq(9)).And(s.neq(10)).And(s.neq(0))
        return i.normalizedDifference(["B8", "B4"]).updateMask(ok)
    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(g).filterDate(a, b).map(m).median()

def pull(img, name):
    x0, y0, x1, y1 = EXT[name]; w, h = round((x1 - x0) / RES), round((y1 - y0) / RES)
    arr = ee.data.computePixels({"expression": img.unmask(-9999).toFloat(), "fileFormat": "NUMPY_NDARRAY",
        "grid": {"dimensions": {"width": w, "height": h}, "crsCode": "EPSG:4326",
                 "affineTransform": {"scaleX": RES, "shearX": 0, "translateX": x0, "shearY": 0, "scaleY": -RES, "translateY": y1}}})
    return {k: np.where(arr[k] == -9999, np.nan, arr[k]) for k in arr.dtype.names}

def r_prof(a, b, m):
    pa = np.nanmean(np.where(m & np.isfinite(a), a, np.nan), 0); pb = np.nanmean(np.where(m & np.isfinite(b), b, np.nan), 0)
    ok = np.isfinite(pa) & np.isfinite(pb)
    return float(np.corrcoef(pa[ok], pb[ok])[0, 1]), pa, pb

out = {}
fig, axs = plt.subplots(2, 2, figsize=(14, 8), constrained_layout=True)
for row, (name, g) in enumerate(BOXES.items()):
    d25 = ndvi_med("2025-10-11", "2025-11-10", g).subtract(ndvi_med("2025-09-15", "2025-10-09", g)).rename("dNDVI25")
    cls = nlcd.reduceResolution(ee.Reducer.mode(), maxPixels=100).toFloat().rename("cls")
    p = pull(d25.addBands(cls), name)
    ee_ = np.load(f"data/ee_{name}.npz"); ni = np.load(f"data/nisar_{name}.npz")
    dn, hv, vh = ee_["dNDVI"], ni["dHV"], ee_["dVH"]; c = p["cls"]
    anom = dn - p["dNDVI25"]
    lon = EXT[name][0] + (np.arange(dn.shape[1]) + .5) * RES
    notwater = dn > -0.5
    strata = {"evergreen_42": (c == 42) & notwater, "decid_wetland_41_90": ((c == 41) | (c == 90)) & notwater,
              "all_forest": np.isin(c, [41, 42, 43, 90]) & notwater}
    res = {"pixels": {k: int(v.sum()) for k, v in strata.items()}}
    for k, m in strata.items():
        drop = m & (dn < -0.10); keep = m & (dn >= -0.02)
        res[k] = {"r_prof_HV_vs_dNDVI": r_prof(hv, dn, m)[0], "r_prof_VH_vs_dNDVI": r_prof(vh, dn, m)[0],
                  "r_prof_HV_vs_anomaly": r_prof(hv, anom, m)[0],
                  "dHV_drop_minus_nodrop": float(np.nanmean(hv[drop]) - np.nanmean(hv[keep])),
                  "mean_dNDVI_2026": float(np.nanmean(dn[m])), "mean_dNDVI_2025": float(np.nanmean(p["dNDVI25"][m]))}
    out[name] = res; print(name, json.dumps(res, indent=1))
    z = lambda v: (v - np.nanmean(v)) / np.nanstd(v)
    for col, k in enumerate(["evergreen_42", "decid_wetland_41_90"]):
        m = strata[k]; ax = axs[row, col]
        _, phv, pdn = r_prof(hv, dn, m); _, _, p25 = r_prof(hv, p["dNDVI25"], m); _, _, pan = r_prof(hv, anom, m)
        ax.plot(lon, z(phv), label="NISAR dHV"); ax.plot(lon, -z(pdn), label="−dNDVI 2026")
        ax.plot(lon, -z(p25), label="−dNDVI 2025 (same weeks)", alpha=.7); ax.plot(lon, -z(pan), label="−(2026 − 2025) anomaly", alpha=.7)
        ax.set_title(f"{name} {k}: column means, standardised"); ax.axhline(0, c="k", lw=.5); ax.legend(fontsize=7); ax.set_xlabel("lon")
    np.savez_compressed(f"data/pheno_{name}.npz", dNDVI25=p["dNDVI25"], cls=c)
fig.savefig("docs/gate/fig_phenology.png", dpi=85)
json.dump(out, open("docs/gate/phenology.json", "w"), indent=1)
