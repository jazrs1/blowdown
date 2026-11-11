# Deploying blowdown.johnazer.com

The site is static: `index.html`, `map.js`, `figures/`, `data/`. There is no build step and no `vercel.json`, the same as `site/` in `jazrs1/hurricane-intensity`, which has no Vercel config in the repo.

It loads Leaflet 1.9.4 from unpkg (pinned with integrity hashes), Google Fonts, and OpenStreetMap tiles at runtime. Everything else is in this folder, about 6.5 MB.

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

- **Held-out areas:** the grey blocks and blank pixels are deliberate. Keep them until the scoring pass is done, then re-export the layers with `scripts/site_layers.py` once the rule is lifted.
- **Basemap:** OpenStreetMap's tile servers allow light use with attribution (their tile usage policy). If traffic grows, switch to a keyed provider.
- **Results table:** it says "Scored after held-out labeling" until the single scoring pass.
