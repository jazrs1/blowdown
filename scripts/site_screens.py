"""Screenshots of the local site preview (http://localhost:8766/) through the Chrome DevTools Protocol, with a normal viewport
so viewport-relative sizes (the 72vh map) render as on a real screen, then captured beyond the viewport.
  docs/site/desktop_1280.png      full page, 1280 x 900 viewport
  docs/site/phone_390.png         full page, 390 x 844 viewport (mobile emulation)
  docs/site/desktop_top_1200.png  top 1,200 px of the desktop page
  docs/site/desktop_map.png       the map section (heading to caption), desktop
Usage: site_screens.py  (Chrome must be installed; the preview server must be running)."""
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
    def load(w, h, mobile):
        cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=mobile)
        cmd("Page.navigate", url=URL); time.sleep(4)
        ev("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager'); new Promise(r => setTimeout(r, 2500))")
        return ev("({h: document.documentElement.scrollHeight, w: document.documentElement.scrollWidth})")
    cmd("Page.enable"); cmd("Runtime.enable")
    d = load(1280, 900, False); print("desktop page", d, flush=True)
    shoot("docs/site/desktop_1280.png", {"x": 0, "y": 0, "width": 1280, "height": d["h"]})
    shoot("docs/site/desktop_top_1200.png", {"x": 0, "y": 0, "width": 1280, "height": 1200})
    b = ev("(() => { const s = document.getElementById('map-section').getBoundingClientRect(); return {top: s.top + scrollY, h: s.height}; })()")
    shoot("docs/site/desktop_map.png", {"x": 0, "y": max(0, b["top"] - 20), "width": 1280, "height": b["h"] + 40})
    p = load(390, 844, True); print("phone page", p, flush=True)
    shoot("docs/site/phone_390.png", {"x": 0, "y": 0, "width": 390, "height": p["h"]})
    ws.close()
finally:
    proc.terminate()
