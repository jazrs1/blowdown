"""Download NEXRAD Level II volumes for KMOB and KEVX, 2026-10-09 22:00 to 2026-10-10 06:00 UTC, from the public
unidata-nexrad-level2 bucket on AWS (anonymous HTTPS). Skips *_MDM metadata files. Writes data/nexrad/<SITE>/ and
data/nexrad/manifest.json (key, bytes)."""
import json, os, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
B = "https://unidata-nexrad-level2.s3.amazonaws.com"
out = {}
for site in ("KMOB", "KEVX"):
    os.makedirs(f"data/nexrad/{site}", exist_ok=True); keys = []
    for day in ("2026/10/09", "2026/10/10"):
        token = None
        while True:
            url = f"{B}/?list-type=2&prefix={day}/{site}/" + (f"&continuation-token={urllib.parse.quote(token)}" if token else "")
            x = ET.fromstring(urllib.request.urlopen(url, timeout=60).read()); ns = {"s": x.tag.split("}")[0][1:]}
            for c in x.findall("s:Contents", ns):
                k = c.find("s:Key", ns).text; sz = int(c.find("s:Size", ns).text)
                m = re.search(r"(\d{8})_(\d{6})_V06$", k)
                if not m: continue
                t = m.group(1) + m.group(2)
                if "20261009220000" <= t <= "20261010060000": keys.append((k, sz))
            if x.find("s:IsTruncated", ns).text == "true": token = x.find("s:NextContinuationToken", ns).text
            else: break
    for k, sz in keys:
        dst = f"data/nexrad/{site}/" + k.split("/")[-1]
        if not (os.path.exists(dst) and os.path.getsize(dst) == sz): urllib.request.urlretrieve(f"{B}/{k}", dst)
    out[site] = [{"key": k, "bytes": sz} for k, sz in keys]; print(site, len(keys), "files", round(sum(s for _, s in keys) / 1e6), "MB", flush=True)
json.dump(out, open("data/nexrad/manifest.json", "w"), indent=1)
