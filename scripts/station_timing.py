"""Wind timing at gust stations against the storm centre's passage.
- ASOS/AWOS (IEM archive, METARs and specials): Whiting Field South (NDZ), Pensacola (PNS), Eglin (VPS), Destin (DTS):
  sustained speed (sknt), direction (drct), gust, and peak-wind remark (gust, direction, time), 2026-10-09 18Z to 10-10 08Z.
- FAWN Jay (station 110): 15-minute mean wind speed and direction (public file; no gusts). Its clock is inferred from the
  timing of solar noon in the solar-radiation record.
- Texas Tech StickNet (Oriole Beach 0217A): no public time series found (reported, not plotted).
Centre passage: time of closest approach of the best track (b-deck fixes, linear in time and position) to each station.
NHC: landfall 01:30Z (Discussion 14); last advisory 09Z called it post-tropical; b-deck type HU at 00Z, LO at 06Z.
Writes data/wind/sources/iem_timing.csv, docs/wind/station_timing.json, docs/wind/fig_station_timing.png."""
import csv, json, sys, urllib.request; sys.path.insert(0, "scripts")
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pyproj import Geod
gd = Geod(ellps="WGS84")
URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + "&".join(f"station={s}" for s in ("NDZ", "PNS", "VPS", "DTS")) +
       "&data=sknt&data=drct&data=gust&data=peak_wind_gust&data=peak_wind_drct&data=peak_wind_time&year1=2026&month1=10&day1=9&hour1=18&year2=2026&month2=10&day2=10&hour2=8"
       "&tz=Etc/UTC&format=onlycomma&latlon=yes&missing=M&trace=T&direct=no&report_type=3&report_type=4")
open("data/wind/sources/iem_timing.url", "w").write(URL)
raw = urllib.request.urlopen(URL, timeout=120).read().decode(); open("data/wind/sources/iem_timing.csv", "w").write(raw)
rows = list(csv.DictReader(raw.splitlines()))
fx = []
for line in open("data/wind/bal092026.dat"):
    p = [s.strip() for s in line.split(",")]; t = np.datetime64(f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:8]}T{p[2][8:]}")
    la = float(p[6][:-1]) / 10; lo = -float(p[7][:-1]) / 10
    if not fx or fx[-1][0] != t: fx.append((t, la, lo, int(p[8]), p[10]))
T0 = np.datetime64("2026-10-10T00:00"); th = np.array([(f[0] - T0) / np.timedelta64(1, "h") for f in fx]); fla = np.array([f[1] for f in fx]); flo = np.array([f[2] for f in fx])
tt = np.arange(-6, 8.01, 1 / 12); cla = np.interp(tt, th, fla); clo = np.interp(tt, th, flo)
def passage(lat, lon):
    _, _, d = gd.inv(np.full_like(clo, lon), np.full_like(cla, lat), clo, cla); k = int(np.argmin(d)); return float(tt[k]), float(d[k] / 1000)
def hrs(s): t = np.datetime64(s.replace(" ", "T")); return float((t - T0) / np.timedelta64(1, "h"))
def num(x):
    try: return float(x)
    except ValueError: return np.nan
out = {"stations": {}, "notes": {}}
st = {}
for r in rows:
    s = r["station"]; st.setdefault(s, {"lat": float(r["lat"]), "lon": float(r["lon"]), "t": [], "sknt": [], "drct": [], "gust": [], "pk": []})
    d = st[s]; d["t"].append(hrs(r["valid"])); d["sknt"].append(num(r["sknt"])); d["drct"].append(num(r["drct"])); d["gust"].append(num(r["gust"]))
    if r["peak_wind_gust"] not in ("M", ""):
        pt = r["peak_wind_time"]; d["pk"].append((hrs(pt) if pt not in ("M", "") else hrs(r["valid"]), num(r["peak_wind_gust"]), num(r["peak_wind_drct"])))
# FAWN Jay: infer clock from solar noon
F = [x for x in csv.DictReader(open("data/wind/sources/fawn_jay_110_2026.csv")) if x["Date Time"][:10] in ("2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11")]
sol = {}
for x in F:
    try: sol.setdefault(x["Date Time"][:10], []).append((int(x["Date Time"][11:13]) + int(x["Date Time"][14:16]) / 60, float(x["Solar Radiation (w/m2)"])))
    except ValueError: pass
noons = []
for d, v in sol.items():
    v = np.array(v); w = np.clip(v[:, 1], 0, None)
    if w.sum() > 0: noons.append(float((v[:, 0] * w).sum() / w.sum()))
solar_noon_utc = 12 + 87.14 / 15 - 0.25            # ~17:34 UTC (equation of time ~ +14 min in October)
fawn_offset = round(float(np.median(noons)) - solar_noon_utc)     # local = UTC + offset
out["notes"]["fawn_clock"] = {"weighted_solar_noon_local_h": round(float(np.median(noons)), 2), "expected_solar_noon_utc_h": round(solar_noon_utc, 2), "inferred_utc_offset_h": fawn_offset}
jt, js, jd = [], [], []
for x in F:
    if x["Date Time"][:10] not in ("2026-10-09", "2026-10-10"): continue
    t = hrs(x["Date Time"]) - fawn_offset; s = num(x["Wind Speed (mph)"]) * 0.868976; dd = num(x["Wind Direction (deg)"])
    if -6 <= t <= 8: jt.append(t); js.append(s); jd.append(dd)
st["Jay (FAWN)"] = {"lat": 30.77516, "lon": -87.14015, "t": jt, "sknt": js, "drct": jd, "gust": [np.nan] * len(jt), "pk": []}
NAMES = {"NDZ": "Whiting Field South (KNDZ)", "PNS": "Pensacola (KPNS)", "VPS": "Eglin AFB (KVPS)", "DTS": "Destin (KDTS)", "Jay (FAWN)": "Jay, FAWN 15-min mean"}
order = ["Jay (FAWN)", "NDZ", "PNS", "VPS", "DTS"]
fig, axs = plt.subplots(len(order), 1, figsize=(9, 2.4 * len(order)), sharex=True, constrained_layout=True)
for ax, s in zip(axs, order):
    d = st[s]; t = np.array(d["t"]); tp, dist = passage(d["lat"], d["lon"])
    g = np.array(d["gust"]); sk = np.array(d["sknt"]); dr = np.array(d["drct"])
    allg = [(t[i], g[i], dr[i]) for i in range(len(t)) if np.isfinite(g[i])] + [(a, b, c) for a, b, c in d["pk"]]
    best = max(allg, key=lambda q: q[1]) if allg else None
    rec = {"name": NAMES[s], "centre_closest_approach_h_from_00Z": round(tp, 2), "closest_distance_km": round(dist, 1),
           "n_reports_22Z_06Z": int(((t >= -2) & (t <= 6)).sum())}
    if best: rec.update({"peak_gust_kt": best[1], "peak_gust_h_from_00Z": round(best[0], 2), "peak_gust_dir_deg": None if not np.isfinite(best[2]) else best[2],
                         "peak_after_centre_h": round(best[0] - tp, 2)})
    km = int(np.nanargmax(sk)) if np.isfinite(sk).any() else None
    if km is not None: rec.update({"max_sustained_kt": round(float(sk[km]), 1), "max_sustained_h": round(float(t[km]), 2), "max_sustained_dir": None if not np.isfinite(dr[km]) else float(dr[km]), "max_sustained_after_centre_h": round(float(t[km]) - tp, 2)})
    out["stations"][s] = rec
    ax.plot(t, sk, "-", c="#22201C", lw=1.2, label="sustained / mean (kt)")
    ax.plot(t, g, "^", c="#8C4A32", ms=4, label="gust (kt)")
    for a, b, c in d["pk"]: ax.plot(a, b, "*", c="#8C4A32", ms=9)
    a2 = ax.twinx(); a2.plot(t, dr, ".", c="#2F5F73", ms=3); a2.set_ylim(0, 360); a2.set_yticks([0, 90, 180, 270, 360], ["N", "E", "S", "W", "N"]); a2.tick_params(labelsize=7, colors="#2F5F73")
    ax.axvline(tp, c="k", lw=1); ax.text(tp + 0.05, 5, "centre closest", fontsize=7)
    ax.axvline(1.5, c="0.5", ls=":", lw=1); ax.axvspan(0, 6, color="#D6D2C6", alpha=0.4, lw=0)
    ax.set_ylim(0, 110); ax.set_title(f"{NAMES[s]} (closest centre approach {dist:.0f} km)", fontsize=9, loc="left"); ax.set_ylabel("kt")
axs[0].legend(fontsize=7, loc="upper left"); axs[-1].set_xlabel("hours from 00Z 10 Oct 2026 (CDT = UTC-5). Dotted: NHC landfall 01:30Z. Shaded: hurricane (00Z) to low (06Z) in the best track")
fig.suptitle("Wind speed (black), gusts (triangles, stars = peak-wind remarks) and direction (blue dots, right axis)", fontsize=10)
fig.savefig("docs/wind/fig_station_timing.png", dpi=85)
out["notes"]["sticknet"] = "No public Texas Tech StickNet time series found for Oriole Beach 0217A (not plotted)."
json.dump(out, open("docs/wind/station_timing.json", "w"), indent=1); print(json.dumps(out, indent=1))
