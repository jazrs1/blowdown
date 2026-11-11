"""GOES-19 (GOES-East) ABI band 9 (6.9 um, mid-level water vapour) CONUS Cloud and Moisture Imagery (ABI-L2-CMIPC), hourly
from 22Z 9 Oct to 06Z 10 Oct 2026, public noaa-goes19 bucket on AWS. Brightness temperature crops around the storm with the
best-track centre at that time, the damage band outline and the held-out areas (grey). A dry slot shows as warm (high BT).
Sector test: mean BT in the 40-120 km ring around the centre, by quadrant (NE, SE, SW, NW).
Writes data/goes/*.nc, docs/wind/goes_wv.json, docs/wind/fig_goes_wv.png."""
import json, os, re, sys, urllib.request; sys.path.insert(0, "scripts")
import xml.etree.ElementTree as ET
import h5py, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Proj, Geod
os.makedirs("data/goes", exist_ok=True); B = "https://noaa-goes19.s3.amazonaws.com"; gd = Geod(ellps="WGS84")
TIMES = [("2026-10-09", 22), ("2026-10-09", 23), ("2026-10-10", 0), ("2026-10-10", 1), ("2026-10-10", 2), ("2026-10-10", 3), ("2026-10-10", 4), ("2026-10-10", 5), ("2026-10-10", 6)]
files = []
for day, hh in TIMES:
    doy = (np.datetime64(day) - np.datetime64(day[:4] + "-01-01")).astype(int) + 1
    url = f"{B}/?list-type=2&prefix=ABI-L2-CMIPC/{day[:4]}/{doy:03d}/{hh:02d}/OR_ABI-L2-CMIPC-M6C09"
    x = ET.fromstring(urllib.request.urlopen(url, timeout=60).read()); ns = {"s": x.tag.split("}")[0][1:]}
    keys = sorted(c.find("s:Key", ns).text for c in x.findall("s:Contents", ns))
    k = keys[0]; dst = "data/goes/" + k.split("/")[-1]
    if not os.path.exists(dst): urllib.request.urlretrieve(f"{B}/{k}", dst)
    m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})", k); files.append((dst, int(m.group(3)) + int(m.group(4)) / 60 + (24 if day == "2026-10-10" else 0) - 24))
fx = []
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]; t = (np.datetime64(f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:8]}T{p[2][8:]}") - np.datetime64("2026-10-10T00")) / np.timedelta64(1, "h")
    if not fx or fx[-1][0] != t: fx.append((float(t), float(p[6][:-1]) / 10, -float(p[7][:-1]) / 10))
th, fla, flo = np.array([f[0] for f in fx]), np.array([f[1] for f in fx]), np.array([f[2] for f in fx])
B_ = np.load("data/extent_band.npy"); e = np.load("data/extent_ee.npz"); bx0, by0, bx1, by1 = e["extent"]; rb = float(e["res"])
blo = bx0 + (np.arange(B_.shape[1]) + 0.5) * rb; bla = by1 - (np.arange(B_.shape[0]) + 0.5) * rb
held = json.load(open("site/data/heldout.geojson"))
from heldout_mask import band_outline_ll
_blo, _bla, _Bs, _ = band_outline_ll()
out = {"files": [], "sector_mean_BT_K_40_120km": {}}
fig, axs = plt.subplots(3, 3, figsize=(13, 12.5), constrained_layout=True)
for ax, (fp, hr) in zip(axs.ravel(), files):
    with h5py.File(fp, "r") as h:
        v = h["CMI"]; cmi = v[()].astype("float32"); sf, ao = float(v.attrs.get("scale_factor", [1])[0]), float(v.attrs.get("add_offset", [0])[0]); fv = v.attrs.get("_FillValue", [None])[0]
        if fv is not None: cmi[v[()] == fv] = np.nan
        cmi = cmi * sf + ao if v.dtype.kind in "iu" else cmi
        x = h["x"][()] * float(h["x"].attrs["scale_factor"][0]) + float(h["x"].attrs["add_offset"][0]); y = h["y"][()] * float(h["y"].attrs["scale_factor"][0]) + float(h["y"].attrs["add_offset"][0])
        pa = h["goes_imager_projection"].attrs; H = float(pa["perspective_point_height"][0])
        pr = Proj(proj="geos", h=H, lon_0=float(pa["longitude_of_projection_origin"][0]), sweep=pa["sweep_angle_axis"].decode() if isinstance(pa["sweep_angle_axis"], bytes) else str(pa["sweep_angle_axis"]),
                  a=float(pa["semi_major_axis"][0]), b=float(pa["semi_minor_axis"][0]))
    X, Y = np.meshgrid(x * H, y * H); LON, LAT = pr(X, Y, inverse=True); LON[np.abs(LON) > 1e10] = np.nan
    box = (LON > -90.5) & (LON < -83.5) & (LAT > 28) & (LAT < 34)
    rr, cc = np.nonzero(box); sl = (slice(rr.min(), rr.max() + 1), slice(cc.min(), cc.max() + 1))
    lo_, la_, bt = LON[sl], LAT[sl], cmi[sl]
    cla, clo = float(np.interp(hr, th, fla)), float(np.interp(hr, th, flo))
    az, _, dist = gd.inv(np.full(lo_.shape, clo), np.full(la_.shape, cla), np.nan_to_num(lo_, nan=clo), np.nan_to_num(la_, nan=cla))
    ring = (dist > 40e3) & (dist < 120e3) & np.isfinite(bt); azm = (az + 360) % 360
    sec = {q: round(float(np.nanmean(bt[ring & m])), 1) for q, m in (("NE", azm < 90), ("SE", (azm >= 90) & (azm < 180)), ("SW", (azm >= 180) & (azm < 270)), ("NW", azm >= 270))}
    out["sector_mean_BT_K_40_120km"][f"{hr:+.2f} h"] = sec; out["files"].append(os.path.basename(fp))
    im = ax.pcolormesh(lo_, la_, bt, cmap="gist_yarg_r" if False else "Greys", vmin=215, vmax=265, shading="auto")
    ax.contour(_blo, _bla, _Bs, levels=[0.3], colors="#8C4A32", linewidths=1.2)
    for f_ in held["features"]:
        c = np.array(f_["geometry"]["coordinates"][0]); ax.fill(c[:, 0], c[:, 1], color="#9e9e9e", ec="#555", lw=0.6)
    sel = (th >= -24) & (th <= 18); ax.plot(flo[sel], fla[sel], "-", c="C3", lw=1); ax.plot(clo, cla, "o", c="C3", ms=6, mec="w")
    ax.set_xlim(-90, -84); ax.set_ylim(28.5, 33.5); ax.set_aspect(1 / np.cos(np.radians(31)))
    ax.set_title(f"{int(round(hr)) % 24:02d}Z  ring BT NE {sec['NE']:.0f} SE {sec['SE']:.0f} SW {sec['SW']:.0f} NW {sec['NW']:.0f} K", fontsize=8.5)
fig.colorbar(im, ax=axs, shrink=0.5, label="band 9 brightness temperature (K); light = cold/moist, dark = warm/dry")
fig.suptitle("GOES-19 band 9 water vapour, hourly; red line/dot = best track and centre; brown = damage band outline; grey = held out", fontsize=10)
fig.savefig("docs/wind/fig_goes_wv.png", dpi=75)
json.dump(out, open("docs/wind/goes_wv.json", "w"), indent=1); print(json.dumps(out, indent=1))
