# Deploying blowdown.johnazer.com

The site is static: `index.html`, `map.js`, `figures/`, `data/`. There is no build step and no `vercel.json`, the same as `site/` in `jazrs1/hurricane-intensity`, which has no Vercel config in the repo.

It loads Leaflet 1.9.4 from unpkg and MapLibre GL 5.24.0 plus maplibre-gl-leaflet 0.1.4 from jsDelivr (all pinned with integrity hashes), Google Fonts, and OpenFreeMap tiles at runtime. Everything else is in this folder, about 6.5 MB.

**Nothing has been deployed.** These are the steps.

## How hurricane.johnazer.com appears to be set up (inferred, not verified)

- **DNS:** `hurricane.johnazer.com` is a CNAME to a project-specific Vercel target (`ee9c8ee7aacbb905.vercel-dns-017.com`). `johnazer.com` uses GoDaddy nameservers (`ns73/ns74.domaincontrol.com`). Both were looked up on 2026-11-10.
- **Vercel project:** the repo has no Vercel config, so the project presumably sets **Root Directory = `site`**, Framework Preset = **Other**, with no build command and no output directory override. I can't see the Vercel dashboard, so check this in the hurricane project's Settings → Build and Deployment.

## Option A: Git-connected project (matches the hurricane site, if that is how it is set up)

This needs the blowdown repository on GitHub. It isn't on GitHub yet, and creating it is your call.

1. Push the repository, including the `site/` folder, to GitHub.
2. In Vercel: **Add New → Project → Import** the repository.
3. Set:
   - Framework Preset: **Other**
   - Root Directory: **`site`**
   - Build Command: empty (override to nothing)
   - Output Directory: empty (defaults to the root directory)
   - Install Command: empty
4. Deploy. Vercel gives a `*.vercel.app` preview URL. Open it and check the map loads (the layers come from `data/`).

## Option B: deploy from this machine with the Vercel CLI (no GitHub needed)

1. `npm i -g vercel`
2. `cd site`
3. `vercel` (first run: log in, choose the team, create a new project, accept "Other" with no build settings)
4. Check the preview URL.
5. `vercel --prod`

## Custom domain: blowdown.johnazer.com

1. Vercel → the blowdown project → **Settings → Domains → Add** `blowdown.johnazer.com`.
2. Vercel shows the DNS record to create. For a subdomain on external DNS it is a **CNAME**. Use the exact target Vercel displays: it may be a project-specific value like the hurricane one (`…vercel-dns-017.com`) or `cname.vercel-dns.com`.
3. At GoDaddy (DNS for johnazer.com) → **DNS → Add record**:
   - Type: `CNAME`
   - Name: `blowdown`
   - Value: the target Vercel showed
   - TTL: default (1 hour is fine)
4. Back in Vercel, wait for the domain to show **Valid Configuration**. Vercel issues the HTTPS certificate automatically, usually within minutes. DNS can take up to the TTL to propagate.
5. Check `https://blowdown.johnazer.com` and the header and footer links to `https://hurricane.johnazer.com`.
6. Optional, for the suite: add a link back from hurricane.johnazer.com's header or footer to blowdown.johnazer.com. That's a change to the other repo and wasn't made here.

## Before going public

- **Held-out areas:** the gray blocks and blank pixels are deliberate. Keep them until the scoring pass is done, then re-export the layers with `scripts/site_layers.py` once the rule is lifted.
- **Basemap: OpenFreeMap "Positron", vector, no API key.**
  - **Source:** the style is a muted copy of `https://tiles.openfreemap.org/styles/positron`, built by `scripts/basemap_style.py` and hosted with the site as `data/basemap_style.json`. OpenFreeMap's quick-start page says custom styles must be self-hosted.
  - **What was changed:** park, land-use and land-cover layers removed (they drew a shade change at the Alabama–Florida line); colors muted; state and county lines shown from zoom 6.
  - **Runtime loads:** tiles, fonts and icons still come from `tiles.openfreemap.org`. The style is drawn by MapLibre GL 5.24.0 through `@maplibre/maplibre-gl-leaflet` 0.1.4, both pinned on jsDelivr with integrity hashes. MapLibre 6 ships only as ES modules, which the Leaflet plugin can't use, so it stays on 5.24.0.
  - **Terms** (OpenFreeMap terms of use, read 2026-11-11):
    - free, no API key, no stated view limits for normal map use;
    - provided "as-is", with no promise of availability, and it may be discontinued without notice;
    - bulk/offline downloads are capped at 3,000 tiles or 50 MB per download, at most 4 parallel requests, with a unique User-Agent;
    - governed by Hungarian law.
  - **Attribution:** the map shows "OpenFreeMap © OpenMapTiles © OpenStreetMap contributors". OpenStreetMap's license (ODbL) and the OpenMapTiles schema require credit; OpenFreeMap's own credit is a courtesy.
  - **Fallback if the public OpenFreeMap instance goes away:** self-host a Protomaps extract of the study region. This hasn't been tested.
    1. Install the `pmtiles` CLI and cut an extract from a Protomaps daily planet build:
       `pmtiles extract https://build.protomaps.com/<YYYYMMDD>.pmtiles site/data/basemap.pmtiles --bbox=-88.6,29.6,-85.4,32.7 --maxzoom=13`
       (check the size; keep it within what Vercel serves comfortably).
    2. Load MapLibre's `pmtiles` protocol plugin and point a style's vector source at `pmtiles://data/basemap.pmtiles`. A Protomaps "light" or "grayscale" basemap style, with its land-use layers removed the same way, fits the site.
    3. Change the attribution to "Protomaps © OpenStreetMap contributors".
- **Results table:** it says "Scored after held-out labeling" until the single scoring pass.
