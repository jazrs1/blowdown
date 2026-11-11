# Sentinel-2 before/after on the site map: why the two images differ outside the damage band

Checked 2026-11-11 on `main`. Numbers come from `scripts/s2_open_land.py` and are saved in `docs/site/s2_open_land.json`. The held-out block (plus 2 km) and the aerial tip (plus 2 km) are excluded, and so is water.

## 1. Slider orientation: correct

- **Code** (`site/map.js`, `updateSplit`): the after image is clipped to the right of the split line, and the before image to the left. The page label reads "before (left) and after (right)", with "Sep to early Oct" and "mid Oct to early Nov" at the two ends.
- **Pixel test** (headless Chrome, fresh profile, `?compare`): at each slider position, the strips on either side of the line were compared with frames showing only the before image and only the after image.
  - **Desktop, 1280 px:** at 50 and 65 the left matched before and the right matched after.
  - **Phone, 390 px:** the same held at all five positions (15, 35, 50, 65, 85).
  - **Excluded samples:** desktop strips that fell outside the imagery tie, because both frames show only basemap there. That covers both sides at 15 and 85, and the left side at 35.
- **Served files:** `s2_before.jpg` matches the before composite in the Earth Engine cache. The mean absolute difference is 6.7 grey levels, against 14.7 for the after composite. `s2_after.jpg` matches the after composite (6.6 against 15.3).

## 2. Display stretch: identical, no fix needed

Both images come from the same code path in `scripts/site_layers.py`:
- bands B4, B3, B2, divided by 10000;
- clipped to 0–0.16 reflectance;
- gamma 0.85;
- the same masking (Sentinel-2 SCL cloud, shadow and water classes).

The composite dates are 1 Sep to 8 Oct 2026 and 11 Oct to 9 Nov 2026 (`filterDate` end dates are exclusive).

## 3. What actually changes

The site does **not** show a drier, browner before image. Outside the band, the before image (left) is the greener and paler one. The after image (right) is darker, and many open fields turn tan or pink.

**Mean NDVI change, after minus before:**

| Area | Area (km²) | 2026 | Same weeks 2025 |
|---|---|---|---|
| Pasture/hay (NLCD 81) | 744 | −0.013 | −0.028 |
| Cropland (NLCD 82) | 854 | −0.180 | −0.191 |
| Forest outside the damage mask | 8,393 | −0.000 | +0.002 |
| Forest inside the damage mask | 566 | −0.147 | −0.007 |

**True-colour reflectance** (the cache behind the site images):

| Area | Red/green, before | Red/green, after |
|---|---|---|
| Open land (81 and 82) | 0.86 | 1.09 |
| Forest outside the mask | 0.66 | 0.76 |

Forest outside the mask is also brighter in every band before (green 0.043 against 0.035, blue 0.027 against 0.020).

**Reading:**
- The browning of open land is the autumn harvest. Cropland NDVI falls by about the same amount in 2025 as in 2026.
- Forest outside the band barely changes.
- There is no post-storm greening of open land.
- The paler, bluer before composite fits the higher September sun and some haze. That is an inference: it wasn't tested.

## US Drought Monitor, study counties

Percent of each county area in each category or worse. 29 Sep is the last map before landfall; 27 Oct is about two weeks after.

| County | 29 Sep 2026 | 27 Oct 2026 |
|---|---|---|
| Baldwin AL | D0 100, D1 30 | D0 29, D1 23 |
| Escambia AL | D1 98, D2 60 | D0 83, D1 20 |
| Monroe AL | D1 100, D2 46, D3 5 | D1 99, D2 1 |
| Conecuh AL | D2 100 | D0 100, D1 8 |
| Covington AL | D1 90, D2 48 | D0 62 |
| Butler AL | D2 75, D3 6 | D0 100, D1 18 |
| Escambia FL | D0 83, D1 21, D2 2 | D0 7 |
| Santa Rosa FL | D0 74, D1 9 | none |
| Okaloosa FL | D0 100 | none |

Sources:
- USDM county statistics API, `GetDroughtSeverityStatisticsByAreaPercent` with `statisticsType=1`: https://usdmdataservices.unl.edu/api/CountyStatistics/GetDroughtSeverityStatisticsByAreaPercent?aoi=01053&startdate=9/29/2026&enddate=10/27/2026&statisticsType=1 (change `aoi` to the county FIPS code: 01003, 01053, 01099, 01035, 01039, 01013, 12033, 12113, 12091).
- State maps:
  - https://droughtmonitor.unl.edu/data/png/20260929/20260929_AL_trd.png
  - https://droughtmonitor.unl.edu/data/png/20261027/20261027_AL_trd.png
  - https://droughtmonitor.unl.edu/data/png/20260929/20260929_FL_trd.png
  - https://droughtmonitor.unl.edu/data/png/20261027/20261027_FL_trd.png

**Conclusion:** severe drought (D2, with some D3) before the storm, easing to D0–D1 after it, is real. It doesn't show up as greening in the Sentinel-2 composites, though: open-land NDVI fell, as it did in 2025. The site's sentence says what the images actually show, the harvest, and doesn't attribute anything to drought.
