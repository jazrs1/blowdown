# Wind and damage: Hurricane Isaias (AL092026)

Branch `site`. The damage here is the **Sentinel-2 damage mask** (pipeline step 4), not model output.

The held-out block (lat 31.14–31.32, plus a 2 km buffer) and the aerial tip (plus a 2 km buffer) are left out of every number and figure. They show as grey, "Held out until scoring".

Script: [wind_link.py](../../scripts/wind_link.py). Numbers: [wind.json](wind.json). Station values and sources: [stations.json](stations.json). Downloaded sources are in `data/wind/sources/` (not in git).

## Track

NHC operational best track, ATCF b-deck `bal092026.dat`:
- Downloaded from `https://ftp.nhc.noaa.gov/atcf/btk/bal092026.dat` on 2026-11-10 (46 records, sha256 `1aa33d53…`).
- Peak 105 kt, 959 mb (9 Oct 12Z–18Z). 95 kt at 30.2°N 86.6°W at 10 Oct 00Z, then 45 kt at 31.4°N 86.5°W at 06Z (system type LO) and extratropical by 12Z.
- **Landfall:** NWS Mobile puts it near Destin around 8:30 PM CDT on 9 Oct (01:30Z), as a Category 2 with 105 mph winds. I placed it where the best track crosses the coast at 30.40°N, 86.58°W (about 01:00Z on the track's timing). Interpolating by time alone would put the 01:30Z position about 12 km inland, at 30.50°N. Along-track distances start from the coast crossing.
- **Analysed wind field (b-deck wind radii):**
  - At 00Z on 10 Oct: radius of maximum wind 15 nm (28 km). 64 kt winds reach 30 / 30 / 25 / 20 nm in the NE / SE / SW / NW quadrants, so hurricane-force winds extend about 37–46 km on the west side and about 56 km on the east side. 50 kt winds reach 60 / 70 / 50 / 70 nm.
  - At 18Z on 9 Oct the 64 kt radii were the same, with radius of maximum wind 20 nm.
  - By 06Z on 10 Oct, 34 kt radii only (radius of maximum wind 100 nm).

**The track runs north along the eastern edge of the study grid.** Every forest cell in the grid lies 0.6–104.5 km left (west) of the track, and none lies right of it.

## Peak gusts (kt) and their sources

Mapped stations:

| Station | Gust (kt) | Distance from track | Source of the value |
|---|---|---|---|
| Jay, FL (UF FAWN 110) | **102.2** | 56 km left | NWS Mobile Post Tropical Cyclone Report, Highest 10 Land Gusts (updated 10/23/2026). The NWS Mobile county impact narrative (Santa Rosa) gives "102 kts ... at a UF FAWN station in Jay". |
| Oriole Beach, FL (Texas Tech StickNet 0217A) | **101.3** | 48 km left (approx.) | Same NWS report. The impact narrative (Escambia, FL) gives "gusts measured 101 kts". |
| Whiting Field South (KNDZ, AWOS) | 99.0 | 44 km left | IEM ASOS archive, peak-wind remark at 01:56Z 10 Oct. Matches the NWS report's 99.0. |
| Pensacola Regional (KPNS) | 80 | 58 km left | IEM ASOS archive, 23:53Z 9 Oct |
| Eglin AFB (KVPS) | 71 | at the track (5 km right) | IEM ASOS archive (61 reports 22Z–06Z) |
| Destin–Fort Walton Beach (KDTS) | 66 | 11 km right | IEM ASOS archive (25 reports) |
| Pensacola NAS (KNPA) | 55 | 70 km left | IEM; only 4 reports 22Z–06Z |
| Hurlburt Field (KHRT) | 47 | 10 km left | IEM; only 2 reports 22Z–06Z |
| Duke Field (KEGI) | 39 | at the track (4 km right) | IEM; only 2 reports 22Z–06Z |
| Crestview (KCEW) | 38 | at the track (3 km right) | IEM (20 reports) |
| Evergreen, AL (KGZH) | 38 | 51 km left | IEM; only 5 reports 22Z–06Z |

Listed by NWS Mobile but not mapped, because no published coordinates were found:
- Navarre StickNet 91.5
- Ferry Pass StickNet 90.8
- Allentown StickNet 88.1
- UWF Pace Library (WeatherSTEM) 86.9
- Pensacola Beach (WeatherSTEM) 86.0
- Navarre Beach Marine Science Station (WeatherSTEM) 86.0
- Gulf Breeze (WxFlow) 82.6

**What was checked against station data:**
- **Jay's 102.2 kt** could not be checked against FAWN's public data: the public 15-minute file has no gust column. Its peak 15-minute mean wind on 9–10 Oct is 72.59 mph = 63.1 kt at 20:15, matching the NWS sustained value for Jay FAWN (63.1 kt).
- **Oriole Beach's 101.3 kt** has no independent check: StickNet data and coordinates weren't found. Its map position is the approximate location of the Oriole Beach community.
- **Whiting Field South's 99 kt** is confirmed in the IEM archive.
- **Stations with very few reports in the storm window** (fewer than 10 between 22Z and 06Z) probably had outages, so their peaks are unreliable. They're drawn hollow in the figure.
- NWS notes that point observations likely didn't sample the event's peak values, and that anemometer heights are under 20 m.

## Damaged share of forest by distance from the track

![damage vs distance](fig_damage_vs_distance.png)

Damage is concentrated in a band 45–75 km left of the track. The median damaged cell is 59.5 km left, with 10–90% between 70 and 45 km.

| Signed distance (km) | All forest | Upland | Wetland |
|---|---|---|---|
| −80 to −75 | 1.0% | 1.3% | 0.7% |
| −75 to −70 | 7.6% | 2.2% | 18.3% |
| −70 to −65 | 22.1% | 12.4% | 32.8% |
| −65 to −60 | **30.0%** | **22.4%** | 37.9% |
| −60 to −55 | 26.2% | 17.8% | **44.9%** |
| −55 to −50 | 22.9% | 17.6% | 36.3% |
| −50 to −45 | 13.6% | 12.7% | 13.5% |
| −45 to −40 | 6.1% | 6.1% | 8.6% |
| −40 to 0 | 0.4–1.3% | 0.2–0.8% | 0.1–4.5% |
| −105 to −80 | 0.7–1.0% | 0.6–1.3% | 0.5–1.2% |

The right side has no forest in the grid, so no bins exist there.

Along the track, the damaged share is highest 20–70 km north of landfall: 10–13% of all forest, and wetland 17–25%. It drops to under 1% at 80–90 km, with a smaller rise around 120–130 km.

## Map

![wind map](fig_wind_map.png)

## Does the damage sit where the strongest winds were expected?

No, not where you'd expect for a northward-moving hurricane. The strongest winds are usually on the right of the track near landfall, which here means east of the track around Destin and Fort Walton Beach. Inside this study grid, the damage mask instead sits 45–75 km left (west) of the track, from about 20 to 70 km north of landfall.

The gust reports point the same way. The three highest land gusts (Jay 102 kt, Oriole Beach 101 kt, Whiting Field 99 kt) are all 44–56 km left of the track. The stations close to the track on the right side that kept reporting through the storm peaked lower (Eglin 71 kt, Destin 66 kt).

Two things limit this conclusion:
- The study grid was drawn around the damage band and ends at the track, so the right side was never mapped with the Sentinel-2 mask. Damage east of the track can't be ruled out from this analysis.
- **NHC's own analysed wind field doesn't explain it either.** At 00Z its hurricane-force radius is slightly larger on the right (30 nm east, 20–25 nm west). The damage band, 45–75 km west, lies at and just beyond the western edge of the analysed 64 kt winds (37–46 km) and well inside the 50 kt radius (93–130 km). So the damage is consistent with the analysed field reaching that far west, but the field doesn't put the strongest winds on the left.
- I haven't established why the strongest observed gusts and the damage fell on the left. Possible reasons, not tested: a wind field more asymmetric than the radii capture as the storm weakened and lost tropical character within six hours of landfall; error in the operational track (0.1° fixes, about 10 km); and sparse station coverage on the right, where several stations had outages. Stations within about 5 km of the track are called "at the track" because of that rounding.

## Not verified

- Jay's 102.2 kt gust against raw FAWN data (no gust in the public file).
- The coordinates and data of the StickNet stations, including Oriole Beach.
- Whether ASOS stations with few storm-window reports failed or just reported less often.
- Damage right of the track: outside the study grid, so not mapped.
- The operational best track may be revised in NHC's final report; it was used as downloaded.
