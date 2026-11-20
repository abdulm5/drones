# Five Points datasets

Pulled on 19 November 2026 for the AGRIFORGE demo. Files are in `data/five_points/` and are gitignored.

The demo area is the UC West Side Research and Extension Center at Five Points, Fresno County. Bounding box: `-120.116, 36.336, -120.100, 36.348`. Center: `36.341988, -120.108177`.

The technical track asks for live public Earth data. These files are a real extract so the build can proceed offline. The demo should still search Element84 Earth Search and NASA POWER at runtime and show the acquisition time from that search. A saved clip alone does not meet the track.

## What is on disk

| File | What it is | Size |
| --- | --- | --- |
| `cdl_2025_fresno_06019.tif` | USDA NASS 2025 Cropland Data Layer, Fresno County, 30 m, public domain | 36 MB |
| `cdl_2025_fresno_06019.csv` | County class acreage for that raster | 2 KB |
| `cdl_2025_five_points_clip.tif` | Same CDL, cut to the demo box | 3 KB |
| `sentinel2_20261111_clip/` | Sentinel-2B L2A window, sensed 2026-11-11, bands blue, green, red, nir, nir08, swir16, scl | 172 KB |
| `sentinel2_item_20261111.json` | STAC item for `S2B_T10SGF_20261111T184941_L2A` | 20 KB |
| `dwr_fields_2024.geojson` | 45 provisional 2024 DWR field polygons that intersect the box | 68 KB |
| `nasa_power_20261001_20261118.json` | NASA POWER daily weather at the center, 1 Oct–18 Nov 2026 | 12 KB |
| `ssurgo_point.json` | SSURGO horizons at the center: Cerini clay loam | 4 KB |
| `clip_summary.json` | Pixel counts, NDVI, and CDL class counts for the clip | 8 KB |

## What the clip actually shows

The 11 November 2026 scene is clear over this box. Scene classification is only vegetation and bare soil. NDVI on clear pixels has mean 0.30, 10th percentile 0.10, and 90th percentile 0.55. Reflectance is `DN * 0.0001 - 0.1`, from the GeoTIFF scale and offset.

The CDL clip is mostly pistachios, garlic, winter wheat, fallow, cotton, and grapes. That is an annual classification, not a live observation and not a fertilizer diagnosis.

Soil at the center is Cerini clay loam, 85% component. Surface horizon: 32% sand, 40% silt, 28% clay, 0.8% organic matter, pH 7.7. Organic matter is not nitrate. There is no public soil-nitrate test in this folder, so a treatment rate should not be proposed from these files.

NASA POWER at this point is about a half-degree cell. Precipitation on 11 November 2026 is 0 mm. 17–18 November are fill values (`-999`) and are not measurements. This weather cannot explain a within-field anomaly.

## Do not post-train tonight

Tinker can run a small LoRA fine-tune, including an official toy example of about eight chats. AGRIFORGE has no held-out agronomic labels. A fine-tune would memorize a heuristic the team can already run. Use a checked planner. Revisit Tinker only after the live satellite demo works, auth and billing already work, and a held-out set is scored for action agreement and constraint violations.

## Sources

- Sentinel-2: Element84 Earth Search collection `sentinel-2-c1-l2a`, tile `10SGF`. Full bands are about 230–290 MB, so only the window is stored.
- Cropland: `https://nassgeodata.gmu.edu/webservice/nass_data_cache/byfips/CDL_2025_06019.tif`
- Fields: California DWR 2024 provisional crop mapping, public use, queried from the statewide map service. These are land-use polygons, not farm-tract boundaries.
- Weather: NASA POWER Daily API v2.10.4, no key.
- Soil: USDA NRCS Soil Data Access.
