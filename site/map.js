(function () {
  "use strict";
  var el = document.getElementById("map");
  var statusEl = document.getElementById("map-status");
  function status(msg) { statusEl.textContent = msg; statusEl.style.display = msg ? "block" : "none"; }
  if (!window.L) { status("The map library did not load. The figures below do not depend on it."); return; }

  var map = L.map(el, { zoomControl: true, scrollWheelZoom: false, attributionControl: true, minZoom: 7, maxZoom: 13, zoomSnap: 0.25, zoomDelta: 0.5 });
  // Basemap: OpenFreeMap "Positron" vector style (no API key), drawn through maplibre-gl-leaflet under the overlays.
  // The hosted style (data/basemap_style.json) drops park, land-use and land-cover fills, which drew a shade change along the
  // Florida-Alabama line, and keeps roads, labels, water and boundaries, muted.
  var OFM_ATTR = '<a href="https://openfreemap.org">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  if (window.L.maplibreGL) {
    // Muted copy of OpenFreeMap's Positron style, hosted with the site (built by scripts/basemap_style.py).
    fetch("data/basemap_style.json?v=2026-11-11").then(function (r) { if (!r.ok) throw new Error("style " + r.status); return r.json(); })
      .then(function (st) { L.maplibreGL({ style: st, attributionControl: { customAttribution: OFM_ATTR }, interactive: false }).addTo(map); })
      .catch(function (e) { status("The basemap did not load (" + e.message + "); the data layers below still work."); });
  } else {
    status("The basemap library did not load; the data layers still work.");
  }

  map.on("focus", function () { map.scrollWheelZoom.enable(); });
  map.on("blur", function () { map.scrollWheelZoom.disable(); });

  map.createPane("imagery"); map.getPane("imagery").style.zIndex = 380;
  map.createPane("change"); map.getPane("change").style.zIndex = 400;
  map.createPane("held"); map.getPane("held").style.zIndex = 450;

  window.__blowdownMap = map;   // exposed for automated alignment checks only
  var layers = {};
  // Before/after divider: a line with "Before" / "After" labels and a grip, draggable on the map (pointer events; the
  // slider below stays the keyboard control and moves with it).
  var splitLine = L.DomUtil.create("div", "split-line", el);
  splitLine.innerHTML = '<span class="split-tag split-before">Before</span><span class="split-tag split-after">After</span><span class="split-grip" aria-hidden="true"></span>';
  splitLine.setAttribute("title", "Drag to compare before and after");
  L.DomEvent.disableClickPropagation(splitLine); L.DomEvent.disableScrollPropagation(splitLine);

  function getJSON(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(url); return r.json(); }); }

  Promise.all([getJSON("data/layers.json"), getJSON("data/track.geojson"), getJSON("data/stations.geojson"),
               getJSON("data/heldout.geojson"), getJSON("data/study.geojson")]).then(function (res) {
    var meta = res[0], track = res[1], stations = res[2], held = res[3], study = res[4];
    var b = L.latLngBounds(meta.bounds);
    map.fitBounds(b, { padding: [4, 4] });
    var vq = /[?&]view=([-0-9.]+),([-0-9.]+),([0-9.]+)/.exec(location.search);   // ?view=lat,lon,zoom (used for alignment checks)
    if (vq) map.setView([+vq[1], +vq[2]], +vq[3], { animate: false });
    map.setMaxBounds(b.pad(0.6));

    // A failed overlay shows a transparent pixel (no broken-image icon) and a message under the map instead of failing silently.
    var DATA_VERSION = "2026-11-11";   // bump when site/data images are regenerated, so browsers don't show stale cached copies
    var BLANK = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
    function img(name, pane, opacity) {
      var o = L.imageOverlay("data/" + name + "?v=" + DATA_VERSION, b, { pane: pane, opacity: opacity, interactive: false, className: "ov-" + name.split(".")[0], errorOverlayUrl: BLANK });
      o.on("error", function () { status("A map layer (" + name + ") did not load. Reloading the page usually fixes this."); });
      return o;
    }
    layers.nisar = img("nisar_hv.png", "change", 0.9);
    layers.s1 = img("s1_vh.png", "change", 0.9);
    layers.ndvi = img("s2_ndvi.png", "change", 0.9);
    layers.damage = img("damage.png", "change", 0.9);
    layers.before = img("s2_before.jpg", "imagery", 1);
    layers.after = img("s2_after.jpg", "imagery", 1);

    L.geoJSON(study, { style: { color: "#6E6859", weight: 1, dashArray: "3 3", fill: false }, interactive: false }).addTo(map);

    L.geoJSON(held, {
      pane: "held",
      style: { color: "#555", weight: 1, fillColor: "#9e9e9e", fillOpacity: 0.92 },
      onEachFeature: function (f, l) {
        l.bindTooltip(f.properties.label, { permanent: true, direction: "top", offset: [0, -4], className: "held-label" });
        l.bindPopup("<b>Held out until scoring</b><br>" + f.properties.which + ". Nothing here has been used to build or tune any model; it is blank on every layer until the single scoring pass.");
      }
    }).addTo(map);

    var fixes = track.features.filter(function (f) { return f.properties.kind === "fix"; });
    function fmtTime(t) { return t.slice(6, 8) + " Oct " + t.slice(8, 10) + "Z"; }
    layers.track = L.layerGroup([
      L.geoJSON(track.features.filter(function (f) { return f.properties.kind === "track"; }), { style: { color: "#22201C", weight: 2.5 } }),
      L.geoJSON(fixes, {
        pointToLayer: function (f, ll) { return L.circleMarker(ll, { radius: 3.5, color: "#22201C", weight: 1, fillColor: "#EDEDE7", fillOpacity: 1 }); },
        onEachFeature: function (f, l) { l.bindTooltip(fmtTime(f.properties.time) + ", " + f.properties.vmax_kt + " kt"); }
      }),
      L.geoJSON(track.features.filter(function (f) { return f.properties.kind === "landfall"; }), {
        pointToLayer: function (f, ll) { return L.circleMarker(ll, { radius: 6, color: "#22201C", weight: 2, fillColor: "#22201C", fillOpacity: 1 }); },
        onEachFeature: function (f, l) { l.bindTooltip("Landfall, " + f.properties.note); }
      })
    ]);

    layers.stations = L.geoJSON(stations, {
      pointToLayer: function (f, ll) {
        var g = f.properties.gust_kt, r = 4 + Math.max(0, (g - 30)) / 10;
        return L.circleMarker(ll, { radius: r, color: "#8C4A32", weight: 1.5, fillColor: "#8C4A32", fillOpacity: f.properties.sparse ? 0 : 0.85 });
      },
      onEachFeature: function (f, l) {
        var p = f.properties;
        l.bindPopup("<b>" + p.name + "</b><br>Peak gust " + p.gust_kt.toFixed(1) + " kt<br><span style='font-size:13px'>" + p.source +
          (p.approx ? ". Location approximate." : "") + (p.sparse ? ". Few reports during the storm; the station may have failed." : "") + "</span>");
        l.bindTooltip(p.name.split(" (")[0] + " " + Math.round(p.gust_kt) + " kt");
      }
    });

    function sync() {
      document.querySelectorAll(".map-controls input[data-layer]").forEach(function (cb) { set(cb.dataset.layer, cb.checked); });
    }
    function set(key, on) {
      if (key === "beforeafter") {
        if (on) ["nisar", "s1", "ndvi", "damage"].forEach(function (k) {
          var c = document.querySelector('.map-controls input[data-layer="' + k + '"]'); if (c.checked) { c.checked = false; set(k, false); }
        });
        [layers.before, layers.after].forEach(function (l) { if (on) l.addTo(map); else map.removeLayer(l); });
        document.getElementById("slider-row").classList.toggle("on", on);
        splitLine.style.display = on ? "block" : "none";
        updateSplit();
        return;
      }
      var l = layers[key]; if (!l) return;
      if (on) l.addTo(map); else map.removeLayer(l);
    }
    document.querySelectorAll(".map-controls input[data-layer]").forEach(function (cb) {
      cb.addEventListener("change", function () { set(cb.dataset.layer, cb.checked); });
    });

    var split = document.getElementById("split");
    function span() {   // the slider's 0-100 runs across the imagery as it sits on screen, clipped to the map
      var w = map.getSize().x, nw = map.latLngToContainerPoint(b.getNorthWest()), se = map.latLngToContainerPoint(b.getSouthEast());
      var lo = Math.max(0, nw.x), hi = Math.min(w, se.x); return hi - lo > 20 ? [lo, hi] : [0, w];
    }
    function updateSplit() {
      if (!map.hasLayer(layers.after)) return;
      var w = map.getSize().x, sp = span(), x = Math.round(sp[0] + (sp[1] - sp[0]) * split.value / 100);
      splitLine.style.left = x + "px";
      splitLine.classList.toggle("near-left", x < 128); splitLine.classList.toggle("near-right", w - x < 72);   // keep labels inside the map and clear of the zoom buttons
      var a = layers.after.getElement(), bimg = layers.before.getElement();
      if (!a || !bimg) return;
      var nw = map.latLngToContainerPoint(b.getNorthWest());
      var cut = Math.max(0, x - nw.x);
      a.style.clipPath = "inset(0 0 0 " + cut + "px)";
      bimg.style.clipPath = "inset(0 calc(100% - " + cut + "px) 0 0)";
    }
    split.addEventListener("input", updateSplit);
    var dragging = false;
    function dragTo(clientX) {
      var r = el.getBoundingClientRect(), sp = span(), v = Math.max(0, Math.min(100, (clientX - r.left - sp[0]) / (sp[1] - sp[0]) * 100));
      split.value = v; updateSplit();
    }
    splitLine.addEventListener("pointerdown", function (e) {
      dragging = true; splitLine.classList.add("dragging"); map.dragging.disable();
      try { splitLine.setPointerCapture(e.pointerId); } catch (err) {}
      dragTo(e.clientX); e.preventDefault();
    });
    splitLine.addEventListener("pointermove", function (e) { if (dragging) { dragTo(e.clientX); e.preventDefault(); } });
    function endDrag() { if (!dragging) return; dragging = false; splitLine.classList.remove("dragging"); map.dragging.enable(); }
    splitLine.addEventListener("pointerup", endDrag); splitLine.addEventListener("pointercancel", endDrag); splitLine.addEventListener("lostpointercapture", endDrag);
    map.on("move zoomend resize viewreset", updateSplit);
    map.on("zoomanim", function () { splitLine.style.opacity = 0; });
    map.on("zoomend", function () { splitLine.style.opacity = 1; });
    if (/[?&]compare\b/.test(location.search)) { var bc = document.querySelector('.map-controls input[data-layer="beforeafter"]'); bc.checked = true; }
    sync();
    status("");
  }).catch(function (e) { status("Map data failed to load (" + e.message + ")."); });
})();
