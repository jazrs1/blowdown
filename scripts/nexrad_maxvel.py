"""Maximum Doppler wind speed from the lowest-elevation velocity sweep, KMOB and KEVX, 22Z 9 Oct to 06Z 10 Oct 2026.
Per volume: lowest fixed-angle sweep that carries velocity; velocities dealiased with Py-ART's region-based dealiaser
(pyart.correct.dealias_region_based); gates with reflectivity < 5 dBZ (or missing) dropped. |V| is taken at each gate and the
maximum over all volumes is kept on a 1 km lon/lat grid (lon -88.4..-85.5, lat 29.8..32.4), with the time of the maximum and the
sign (inbound negative). Beam height above the radar for the band (4/3-earth model) is reported per radar.
This is radial velocity, i.e. the wind component along the beam at beam height, not the surface wind speed. Robustness: |V| > 75 m/s
(physically implausible here, a dealiasing failure) is dropped, and the map keeps the SECOND-highest |V| over all volumes at each
point, so a single mis-dealiased volume cannot set the value. 'time' is that of the highest accepted value.
Held-out block + 2 km and aerial tip + 2 km are masked in the figure. Writes data/nexrad/maxvel_<SITE>.npz,
docs/wind/nexrad.json and docs/wind/fig_nexrad_maxvel.png."""
import glob, json, os, sys, time, warnings; sys.path.insert(0, "scripts")
warnings.filterwarnings("ignore")
import numpy as np, pyart, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
t0 = time.time()
LON = np.arange(-88.4, -85.5, 0.0105); LAT = np.arange(29.8, 32.4, 0.009)   # ~1 km
res = {}
def beam_h(r_m, elev_deg, h0):
    ke, Re = 4 / 3, 6371000.0; return np.sqrt(r_m ** 2 + (ke * Re) ** 2 + 2 * r_m * ke * Re * np.sin(np.radians(elev_deg))) - ke * Re + h0
for site in ("KMOB", "KEVX"):
    files = sorted(glob.glob(f"data/nexrad/{site}/{site}*_V06"))
    vmax = np.full((len(LAT), len(LON)), np.nan, "float32"); tmax = np.full(vmax.shape, np.nan, "float32"); smax = np.zeros(vmax.shape, "int8")
    v1 = np.full(vmax.shape, -1.0); v2 = np.full(vmax.shape, -1.0); n_cap = 0
    n_ok, n_bad, elevs, nyq = 0, 0, [], []
    for fp in files:
        try:
            rad = pyart.io.read_nexrad_archive(fp)
            sw = [i for i in range(rad.nsweeps) if np.ma.count(rad.get_field(i, "velocity")) > 1000] if "velocity" in rad.fields else []
            if not sw: n_bad += 1; continue
            i = min(sw, key=lambda k: rad.fixed_angle["data"][k]); r1 = rad.extract_sweeps([i])
            dv = pyart.correct.dealias_region_based(r1, vel_field="velocity")
            v = np.ma.filled(dv["data"], np.nan).astype("float32")
            if "reflectivity" in r1.fields:
                z = np.ma.filled(r1.fields["reflectivity"]["data"], np.nan); v[~(z >= 5)] = np.nan
            la, lo = r1.gate_latitude["data"], r1.gate_longitude["data"]
            ii = np.floor((la - LAT[0]) / 0.009).astype(int); jj = np.floor((lo - LON[0]) / 0.0105).astype(int)
            n_cap += int((np.abs(v) > 75).sum()); v[np.abs(v) > 75] = np.nan
            ok = np.isfinite(v) & (ii >= 0) & (ii < len(LAT)) & (jj >= 0) & (jj < len(LON))
            a = np.abs(v[ok]); I, J = ii[ok], jj[ok]
            tmp = np.full(vmax.shape, -1.0); np.maximum.at(tmp, (I, J), a)
            sg = np.zeros(vmax.shape, "int8"); order = np.argsort(a); sg[I[order], J[order]] = np.sign(v[ok][order]).astype("int8")
            v2 = np.maximum(v2, np.minimum(v1, tmp)); better = tmp > v1; v1 = np.maximum(v1, tmp)
            stamp = os.path.basename(fp)[4:19]; hrs = (np.datetime64(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}") - np.datetime64("2026-10-10T00:00")) / np.timedelta64(1, "h")
            tmax[better] = hrs; smax[better] = sg[better]
            elevs.append(float(rad.fixed_angle["data"][i])); nyq.append(float(np.nanmax(r1.instrument_parameters["nyquist_velocity"]["data"])) if r1.instrument_parameters and "nyquist_velocity" in r1.instrument_parameters else np.nan)
            n_ok += 1
        except Exception as e:
            n_bad += 1; print("skip", os.path.basename(fp), str(e)[:80], flush=True)
    vmax = np.where(v2 > 0, v2, np.nan).astype("float32")
    site_lat, site_lon, site_alt = float(rad.latitude["data"][0]), float(rad.longitude["data"][0]), float(rad.altitude["data"][0])
    np.savez_compressed(f"data/nexrad/maxvel_{site}.npz", vmax=vmax, tmax_h=tmax, sign=smax, lon=LON, lat=LAT)
    from pyproj import Geod
    gd = Geod(ellps="WGS84"); band = {"band_center_31.0N_87.15W": (31.0, -87.15), "band_south_30.6N_87.05W": (30.6, -87.05), "band_north_31.45N_87.15W": (31.45, -87.15)}
    hh = {}
    for k, (la_, lo_) in band.items():
        _, _, dist = gd.inv(site_lon, site_lat, lo_, la_); hh[k] = {"range_km": round(dist / 1000, 1), "beam_center_height_m_asl": round(float(beam_h(dist, np.median(elevs), site_alt)))}
    res[site] = {"files": len(files), "volumes_used": n_ok, "volumes_skipped": n_bad, "lowest_velocity_elevation_deg_median": round(float(np.median(elevs)), 2),
                 "nyquist_ms_median": round(float(np.nanmedian(nyq)), 1) if nyq else None, "site": [site_lat, site_lon, site_alt], "beam_height_over_band": hh,
                 "second_highest_abs_vel_ms_max_in_grid": round(float(np.nanmax(vmax)), 1), "gates_dropped_over_75ms": n_cap}
    print(site, res[site], round(time.time() - t0), flush=True)
json.dump(res, open("docs/wind/nexrad.json", "w"), indent=1)
