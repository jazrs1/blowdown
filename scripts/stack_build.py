"""Step 2: for each NISAR granule (one at a time): check disk, download (resumable), extract masked HH/HV onto the
common 10 m grid as a compact HDF5, delete the raw file (except the two gate scenes, which are extracted in place)."""
import json, netrc, os, shutil, sys, time
import h5py, numpy as np, psutil
import asf_search as asf
sys.path.insert(0, "scripts")
import grid as G
GR = "/science/LSAR/GCOV/grids/frequencyA"
RAW = "data/nisar"; OUT = "data/stack"; os.makedirs(OUT, exist_ok=True)
MIN_FREE = 15e9
GRAN = sys.argv[1] if len(sys.argv) > 1 else "data/stack_granules.json"  # data/control_granules.json for the no-storm controls
gran = [g for g in json.load(open(GRAN)) if g["found"]]
gate = set(json.load(open("data/nisar/download_log.json"))[k]["file"] for k in ("pre", "post"))
gran.sort(key=lambda g: (g["name"] + ".h5") not in gate)  # gate scenes first: extraction errors surface before downloads
logp = os.path.join(OUT, "stack_log.json")
log = json.load(open(logp)) if os.path.exists(logp) else {}
u, _, pw = netrc.netrc(os.path.expanduser("~/.netrc")).authenticators("urs.earthdata.nasa.gov")
sess = asf.ASFSession().auth_with_creds(u, pw)
free = lambda: shutil.disk_usage("C:/").free
min_free = free()
print(f"free disk at start: {free()/1e9:.1f} GB", flush=True)

def download(url, dest, size):
    part = dest + ".part"; have = os.path.getsize(part) if os.path.exists(part) else 0
    if free() - (size - have) - 2e9 < MIN_FREE:
        raise SystemExit(f"STOP: downloading {os.path.basename(dest)} would take free disk below 15 GB ({free()/1e9:.1f} GB free)")
    t0 = time.time()
    hdr = {"Range": f"bytes={have}-"} if have else {}
    with sess.get(url, stream=True, timeout=120, headers=hdr) as r:
        r.raise_for_status()
        with open(part, "ab" if have else "wb") as f:
            for ch in r.iter_content(8 << 20): f.write(ch)
    assert os.path.getsize(part) == size, f"size mismatch {os.path.getsize(part)} vs {size}"
    os.replace(part, dest); return time.time() - t0

def extract(src, dst):
    t0 = time.time()
    with h5py.File(src, "r") as f, h5py.File(dst + ".tmp", "w") as o:
        g = f[GR]; epsg = int(g["projection"].attrs["epsg_code"])
        assert epsg == G.EPSG, f"EPSG {epsg} != {G.EPSG}"
        xs, ys = g["xCoordinates"][()], g["yCoordinates"][()]
        dx, dy = float(g["xCoordinateSpacing"][()]), float(g["yCoordinateSpacing"][()])
        assert abs(dx - 10) < 1e-6 and abs(dy + 10) < 1e-6, (dx, dy)
        offx = (xs[0] - G.XC[0]) / 10; offy = (G.YC[0] - ys[0]) / 10
        lattice_shift_m = float(max(abs(offx - round(offx)), abs(offy - round(offy))) * 10)
        cx, ry = int(round(offx)), int(round(offy))       # scene col 0 -> grid col cx ; scene row 0 -> grid row ry
        gc0, gc1 = max(0, cx), min(G.W, cx + len(xs)); gr0, gr1 = max(0, ry), min(G.H, ry + len(ys))
        ds = {p: o.create_dataset(p, (G.H, G.W), "float32", chunks=(512, 512), compression="lzf", shuffle=True,
                                  fillvalue=np.nan) for p in ("HH", "HV")}
        nvalid = 0
        for r in range(gr0, gr1, 1024):
            re_ = min(r + 1024, gr1); sr0, sr1 = r - ry, re_ - ry; sc0, sc1 = gc0 - cx, gc1 - cx
            m = g["mask"][sr0:sr1, sc0:sc1]; bad = (m == 0) | (m == 255)
            nvalid += int((~bad).sum())
            for p, src_p in (("HH", "HHHH"), ("HV", "HVHV")):
                v = g[src_p][sr0:sr1, sc0:sc1].astype("float32"); v[bad] = np.nan
                ds[p][r:re_, gc0:gc1] = v
        ident = f["science/LSAR/identification"]
        o.attrs.update({"source": os.path.basename(src), "lattice_shift_m": lattice_shift_m,
                        "valid_frac_of_grid": nvalid / (G.H * G.W),
                        "processingType": ident["processingType"][()], "specVersion": ident["productSpecificationVersion"][()]})
    os.replace(dst + ".tmp", dst)
    return time.time() - t0, lattice_shift_m, nvalid / (G.H * G.W)

for g in gran:
    key = f"{g['track']}_{g['date']}"
    dst = os.path.join(OUT, key + ".h5")
    if key in log and log[key].get("done"): print("skip (done)", key, flush=True); continue
    fname = g["name"] + ".h5"; raw = os.path.join(RAW, fname)
    rec = {"granule": g["name"], "bytes": g["bytes"], "free_before_GB": round(free() / 1e9, 1)}
    if fname in gate:
        rec["download_s"] = 0.0; rec["note"] = "gate scene already on disk; extracted in place, raw kept"
    else:
        print(f"downloading {key} ({g['bytes']/1e9:.2f} GB), free {free()/1e9:.1f} GB", flush=True)
        rec["download_s"] = round(download(g["url"], raw, g["bytes"]), 1)
    min_free = min(min_free, free())
    es, shift, vf = extract(raw, dst)
    rec.update({"extract_s": round(es, 1), "lattice_shift_m": shift, "valid_frac_of_grid": round(vf, 3),
                "compact_bytes": os.path.getsize(dst)})
    if fname not in gate:
        os.remove(raw); rec["raw_deleted"] = True
    rec["free_after_GB"] = round(free() / 1e9, 1); rec["done"] = True
    mi = psutil.Process().memory_info(); rec["peak_ram_GB_so_far"] = round(mi.peak_wset / 1e9, 2)
    log[key] = rec; json.dump(log, open(logp, "w"), indent=1)
    print(key, rec, flush=True)
log["_min_free_GB"] = round(min_free / 1e9, 1); json.dump(log, open(logp, "w"), indent=1)
print("all done", flush=True)
