"""Download the pre/post NISAR GCOV PR granules one at a time, logging size and time."""
import json, netrc, os, sys, time
import asf_search as asf

BASE = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/"
NAMES = {
    "pre":  "NISAR_L2_PR_GCOV_032_076_A_017_4005_DHDH_A_20261005T110224_20261005T110258_P05023_N_F_J_001",
    "post": "NISAR_L2_PR_GCOV_033_076_A_017_4005_DHDH_A_20261017T110224_20261017T110259_P05023_N_F_J_001",
}
out_dir = sys.argv[1]
user, _, pw = netrc.netrc(os.path.expanduser("~/.netrc")).authenticators("urs.earthdata.nasa.gov")
sess = asf.ASFSession().auth_with_creds(user, pw)
log = {}
for tag, name in NAMES.items():
    url = f"{BASE}{name}/{name}.h5"
    dest = os.path.join(out_dir, name + ".h5")
    t0 = time.time()
    with sess.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done, last = 0, 0
        with open(dest + ".part", "wb") as f:
            for chunk in r.iter_content(8 << 20):
                f.write(chunk); done += len(chunk)
                if done - last > 500 << 20:
                    last = done
                    print(f"{tag}: {done/1e9:.2f}/{total/1e9:.2f} GB  {time.time()-t0:.0f}s", flush=True)
    os.replace(dest + ".part", dest)
    dt = time.time() - t0
    log[tag] = {"file": name + ".h5", "bytes": os.path.getsize(dest), "seconds": round(dt, 1)}
    print(f"{tag} done: {log[tag]}", flush=True)
json.dump(log, open(os.path.join(out_dir, "download_log.json"), "w"), indent=1)
