"""Screenshots of the local site preview (http://localhost:8766/) through the Chrome DevTools Protocol, with a normal viewport
so viewport-relative sizes (the 72vh map) render as on a real screen, then captured beyond the viewport.
  docs/site/desktop_1280.png      full page, 1280 x 900 viewport
  docs/site/phone_390.png         full page, 390 x 844 viewport (mobile emulation)
  docs/site/desktop_top_1200.png  top 1,200 px of the desktop page
  docs/site/desktop_map.png       the map section (heading to caption), desktop, default view
  docs/site/phone_map.png         the map section on the phone
Also checks, in a fresh profile (empty cache), that every overlay image loads: network status and size for each data/ request,
and naturalWidth of each overlay after switching it on (desktop and phone). Writes docs/site/overlay_check.json.
Usage: site_screens.py [phone]  (Chrome must be installed; the preview server must be running). Headless Chrome draws the
WebGL basemap only on the first page load of a session, so the phone captures are taken in a second run: `site_screens.py phone`.
phone_map.png is stitched from viewport captures: a WebGL canvas far below the viewport captures blank."""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websocket
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"; URL = "http://localhost:8766/"; PORT = 9333
prof = tempfile.mkdtemp(prefix="cdp_")
proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}", "--no-first-run", "--hide-scrollbars", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try: tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read()); break
        except Exception: time.sleep(0.2)
    ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
    ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True); mid = [0]
    def cmd(method, **params):
        mid[0] += 1; ws.send(json.dumps({"id": mid[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]: return m.get("result", {})
    def ev(expr):
        return cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True).get("result", {}).get("value")
    def shoot(path, clip=None):
        r = cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True, **({"clip": {**clip, "scale": 1}} if clip else {}))
        open(path, "wb").write(base64.b64decode(r["data"])); print(path, clip, flush=True)
    def shoot_stitched(path, top, height, w, vh):
        # Viewport-only captures, scrolled down the section and stitched: a WebGL canvas outside the viewport captures blank.
        from PIL import Image
        import io
        out = Image.new("RGB", (w, int(height))); y = 0
        while y < height:
            ev(f"window.scrollTo(0, {top + y}); new Promise(r => setTimeout(r, 2500))")
            sy = ev("scrollY"); r = cmd("Page.captureScreenshot", format="png")
            im = Image.open(io.BytesIO(base64.b64decode(r["data"]))); off = int(round(top + y - sy))
            part = im.crop((0, off, w, min(vh, off + int(height - y)))); out.paste(part, (0, int(y))); y += part.height
            if part.height <= 0: break
        out.save(path); print(path, "stitched", top, height, flush=True)
    def load(w, h, mobile):
        cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=mobile)
        cmd("Page.navigate", url=URL); time.sleep(4)
        ev("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager'); new Promise(r => setTimeout(r, 2500))")
        return ev("({h: document.documentElement.scrollHeight, w: document.documentElement.scrollWidth})")
    cmd("Page.enable"); cmd("Runtime.enable"); cmd("Network.enable"); cmd("Network.setCacheDisabled", cacheDisabled=True)
    net = {}; ofm = []; errors = []; cmd("Log.enable")
    _recv = ws.recv
    def recv_hook():
        m = _recv(); j = json.loads(m)
        if j.get("method") == "Network.responseReceived":
            r = j["params"]["response"]
            if "/data/" in r["url"]: net[j["params"]["requestId"]] = {"url": r["url"].split("/data/")[-1], "status": r["status"], "mime": r.get("mimeType")}
        elif j.get("method") == "Network.loadingFinished" and j["params"]["requestId"] in net:
            net[j["params"]["requestId"]]["bytes"] = int(j["params"]["encodedDataLength"])
        elif j.get("method") == "Network.loadingFailed" and j["params"]["requestId"] in net:
            net[j["params"]["requestId"]]["failed"] = j["params"].get("errorText")
        if j.get("method") == "Network.responseReceived" and "openfreemap.org" in j["params"]["response"]["url"]:
            ofm.append(j["params"]["response"]["status"])
        if j.get("method") == "Runtime.exceptionThrown": errors.append("exception: " + str(j["params"]["exceptionDetails"].get("text")) + " " + str(j["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:200])
        if j.get("method") == "Runtime.consoleAPICalled" and j["params"]["type"] == "error": errors.append("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in j["params"]["args"])[:200])
        if j.get("method") == "Log.entryAdded" and j["params"]["entry"]["level"] == "error": errors.append("log: " + j["params"]["entry"]["text"][:200] + " " + j["params"]["entry"].get("url", ""))
        return m
    ws.recv = recv_hook
    CHECK = """(async () => { const out = {};
      const names = {nisar: 'nisar_hv', s1: 's1_vh', ndvi: 's2_ndvi', damage: 'damage', beforeafter: 's2_'};
      for (const k of ['damage','nisar','s1','ndvi']) { const c = document.querySelector(`input[data-layer="${k}"]`); if (!c.checked) c.click(); }
      await new Promise(r => setTimeout(r, 2500));
      document.querySelectorAll('#map img.leaflet-image-layer').forEach(i => out[i.getAttribute("src").split("?")[0]] = i.complete ? i.naturalWidth : -1);
      const ba = document.querySelector('input[data-layer="beforeafter"]'); ba.click(); await new Promise(r => setTimeout(r, 2500));
      document.querySelectorAll('#map img.leaflet-image-layer').forEach(i => out[i.getAttribute("src").split("?")[0]] = i.complete ? i.naturalWidth : -1);
      out.status = document.getElementById('map-status').textContent; out.jump_height = Math.round(document.querySelector('.jump').getBoundingClientRect().height);
      out.attr_h = Math.round(document.querySelector('.leaflet-control-attribution').getBoundingClientRect().height); out.basemap_canvas = !!document.querySelector('#map canvas');
      out.default_checked = null; return out; })()"""
    if len(sys.argv) > 1 and sys.argv[1] == "phone":
        p = load(390, 844, True); print("phone page", p, flush=True)
        shoot("docs/site/phone_390.png", {"x": 0, "y": 0, "width": 390, "height": p["h"]})
        bp = ev("(() => { const s = document.getElementById('map-section').getBoundingClientRect(); return {top: s.top + scrollY, h: s.height}; })()")
        shoot_stitched("docs/site/phone_map.png", max(0, bp["top"] - 10), bp["h"] + 20, 390, 844)
        pc = ev(CHECK); json.dump({"phone_all_overlays": pc, "console_errors": errors, "openfreemap_responses": {str(k): ofm.count(k) for k in set(ofm)}}, open("docs/site/overlay_check_phone.json", "w"), indent=1)
        print(json.dumps({"phone": pc, "errors": errors, "ofm": {str(k): ofm.count(k) for k in set(ofm)}}, indent=1)); ws.close(); sys.exit(0)
    d = load(1280, 900, False); print("desktop page", d, flush=True)
    default_on = ev("[...document.querySelectorAll('.map-controls input[data-layer]')].filter(c => c.checked).map(c => c.dataset.layer)")
    default_imgs = ev("[...document.querySelectorAll('#map img.leaflet-image-layer')].map(i => [i.getAttribute('src').split('?')[0], i.naturalWidth])")
    align = ev("""(() => { const m = window.__blowdownMap; const img = document.querySelector('#map img.leaflet-image-layer'); const r = img.getBoundingClientRect(), mr = document.getElementById('map').getBoundingClientRect();
      const L_ = window.L; let ov = null; m.eachLayer(l => { if (l instanceof L_.ImageOverlay) ov = l; }); const bb = ov.getBounds();
      const nw = m.latLngToContainerPoint(bb.getNorthWest()), se = m.latLngToContainerPoint(bb.getSouthEast());
      return {img_vs_bounds_px: [Math.round((r.left - mr.left - nw.x) * 10) / 10, Math.round((r.top - mr.top - nw.y) * 10) / 10, Math.round((r.right - mr.left - se.x) * 10) / 10, Math.round((r.bottom - mr.top - se.y) * 10) / 10],
              basemap_canvas: !!document.querySelector('#map canvas.maplibregl-canvas, #map .leaflet-gl-layer canvas, #map canvas'), attribution: document.querySelector('.leaflet-control-attribution').textContent}; })()""")
    shoot("docs/site/desktop_1280.png", {"x": 0, "y": 0, "width": 1280, "height": d["h"]})
    shoot("docs/site/desktop_top_1200.png", {"x": 0, "y": 0, "width": 1280, "height": 1200})
    b = ev("(() => { const s = document.getElementById('map-section').getBoundingClientRect(); return {top: s.top + scrollY, h: s.height}; })()")
    shoot("docs/site/desktop_map.png", {"x": 0, "y": max(0, b["top"] - 20), "width": 1280, "height": b["h"] + 40})
    desk_check = ev(CHECK)
    p = load(390, 844, True); print("phone page", p, flush=True)
    shoot("docs/site/phone_390.png", {"x": 0, "y": 0, "width": 390, "height": p["h"]})
    bp = ev("(() => { const s = document.getElementById('map-section').getBoundingClientRect(); return {top: s.top + scrollY, h: s.height}; })()")
    shoot_stitched("docs/site/phone_map.png", max(0, bp["top"] - 10), bp["h"] + 20, 390, 844)
    phone_check = ev(CHECK)
    # zoomed landfall view for a visual alignment check (track vs coastline), desktop
    cmd("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
    cmd("Page.navigate", url=URL + "?view=30.43,-86.58,10"); time.sleep(12)
    bz = ev("(() => { const s = document.getElementById('map').getBoundingClientRect(); return {top: s.top + scrollY, h: s.height}; })()")
    shoot(os.environ.get("TEMP", ".") + "/blowdown_landfall_check.png", {"x": 0, "y": bz["top"], "width": 1280, "height": bz["h"]})
    attr_phone_lines = phone_check.get("attr_h") if isinstance(phone_check, dict) else None
    res = {"basemap_alignment": align, "openfreemap_responses": {str(k): ofm.count(k) for k in set(ofm)}, "console_errors": errors, "default_layers_on": default_on, "default_overlays_loaded": default_imgs, "desktop_all_overlays": desk_check, "phone_all_overlays": phone_check,
           "network_data_requests": sorted(net.values(), key=lambda q: q["url"])}
    json.dump(res, open("docs/site/overlay_check.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "network_data_requests"}, indent=1))
    for q in sorted({(q["url"], q["status"], q.get("bytes"), q.get("failed")) for q in net.values()}): print(q)
    ws.close()
finally:
    proc.terminate()
