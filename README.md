# AgriForce

The public homepage currently plays the supplied demo recording. Run `npm start` for the video page. The original console is retained at `/console.html`; `npm run console:dev` starts its local Python service while the hosted API repair continues. Vercel currently serves a static build and does not require Python, fixture downloads, or signing-key configuration for video playback.

AGRIFORGE prototype, themed with the supplied AgriForce brand kit: evergreen/frost, Geist typography, and the sprout mark. [Vercel deployment setup](docs/vercel.md).

A mission-control console for UC West Side Research and Extension Center, Five Points, California. Real satellite observations guide **simulated** drone inspections. GrokBot reads that satellite evidence and the state product restrictions, then advises the operator. A human and the policy gate both have to agree before any simulated application.

## Inspiration

A vegetation anomaly tells an operator where to look, not what to spray. AGRIFORGE makes evidence, missing ground measurements, mission constraints, and approval decisions visible in one workflow.

## What it does

1. Queries Element84 Earth Search and NASA POWER on load. Range-reads the Five Points Sentinel-2 window; never downloads the full 110 km tile. Each failed feed independently falls back to its local extract and displays FIXTURE.
2. Applies reflectance scale/offset, retains SCL classes 4 and 5, and computes NDVI and NDMI. Ranks each DWR polygon by its same-field/same-CDL-class, leave-one-out 20th-percentile anomaly gap times clear fraction.
3. Dives from a Cesium night-side globe onto aerial imagery and a selected-field measurement grid. Labels the aerial picture separately from Sentinel-2. Searches latest NAIP metadata; visibly falls back to World Imagery if tiles fail.
4. Plans 30 m inspection lanes with concave-field connectors, an authored exclusion wedge, and an explicit depot transit corridor. Simulates AF-1 with a 25% reserve including return; AF-2 stays cold. Cloud/stale scenarios defer; low battery changes execution; exclusion changes the route.
5. Files a downloadable findings packet from the Sentinel-2 window, the crop class, the soil point, and the weather cell. GrokBot reads that satellite observation, names what the image shows, and says which ground measurements are still missing. It does not propose a fertilizer rate.
6. GrokBot also reads the state restriction for the proposed product. California rules and the simulated other-state comparison stay attached to the advisory. Human GO and an independent policy GO are both required before simulated application. Unknown and prohibited products veto a human GO. The API rechecks the restriction when application is requested.

## How we built it

Vite, React, CesiumJS, locally bundled Geist fonts, and Lucide icons power the interface. FastAPI, rasterio/GDAL, NumPy, pystac-client, Shapely, and pyproj handle observations and geometry. The browser performs no reflectance math. The raster pipeline measures the Sentinel-2 image. GrokBot reviews that measurement together with the state restriction and writes the operator advisory. Raster rules still lock the mission action, and the policy catalog can still veto. There is no Tinker fine-tune. No Cesium Ion token is needed. The xAI key stays in `XAI_API_KEY` on the server.

See [architecture and API contracts](docs/architecture.md) and [dataset provenance](docs/datasets.md).

## Challenges

The supplied clips lost scale metadata, so reflectance is read from the accompanying STAC assets and checked against the known scene before processing another scene. Band resolutions and the CDL projection require explicit reprojection. The off-field depot needs a labeled transit geofence rather than silently treating off-field travel as compliant. NAIP search can succeed while rendering fails, so imagery fallback is separate from observation-feed status.

Earth Search Collection 1 uses `grid:code = MGRS-10SGF` for its MGRS predicate, rather than the brief's unavailable `s2:mgrs_tile` property.

## Accomplishments

The known clip reproduces mean NDVI 0.2973 (expected approximately 0.30). All 44 usable clipped DWR polygons pass four battery/exclusion combinations: 176 simulations with zero segment-geofence, exclusion, or reserve violations. The highest field completes normally and returns early under low battery. Adversarial tests also cross a concave boundary/exclusion and verify that the independent checker detects the violations.

## What we learned

The highest-ranked actual fixture polygon is **Alfalfa**, outside the brief's five policy-seed crops. Its product eligibility stays unknown. Use **Cotton / DWR-316415** for the verified California/Hawaiʻi prohibition comparison. Unverified crop/product rows are intentionally omitted. The shipped catalog contains no allowed product, so application stays locked; tests exercise the successful branch with test-only rows.

## What's next

Collect actual ground measurements; verify current crop-specific product labels and restrictions; integrate measured drone observations; calibrate vehicle energy; evaluate prioritization on held-out fields. These geometry and energy checks are simulation checks, not formal flight certification or authorization to fly or apply products.

## How Grok Bot helped

GrokBot is the consultant on the console, marked Powered by GrokBot.

It looks at the satellite observation for the field the operator opened. That is the Sentinel-2 scene over Five Points: when the image was taken, the NDVI and NDMI measured from the bands, the cloud and soil mask, and how the weak pixels sit inside that same field and crop. It treats those numbers as an observation of the image, not a diagnosis.

The same review puts that satellite note next to the state restriction. GrokBot’s advice is the hold: look, or request a soil test, and do not treat the image as a prescription. The policy gate then reads the crop and the product the operator picked. California can prohibit it, and the simulated other-state rule can prohibit it for a different reason. A missing or prohibited product stays locked even when the satellite view looks uneven.

GrokBot names the missing evidence, including nitrate, prior applications, and growth stage. It does not invent a spray rate. Measuring the image and enforcing the statute stay in the local pipeline. GrokBot is the reader that turns the satellite observation into the advisory the operator checks against those state rules.

## How to run it

Requires Node.js 22.12+ and Python 3.13. From the repository:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci
npm start
```

Open **http://127.0.0.1:5173/**. `npm start` launches FastAPI on 8000 and Vite on 5173; Ctrl-C stops both. Alternatively, use `npm run api` and `npm run dev` in separate terminals.

The supplied local fixtures must exist at `data/five_points/`, or set `AGRIFORGE_DATA` to their directory. See [expected filenames](docs/datasets.md). They are intentionally excluded from Git. A clone without them displays a setup error rather than fabricated measurements. Ignored runtime state is written to `data/runtime/AF-1.json`; its first line begins with `{"simulated": true`.

Live requests are the default. Each failed feed displays FIXTURE and a provenance reason. Results are reused for five minutes; refresh bypasses that cache. Explicit offline rehearsal:

```sh
AGRIFORGE_OFFLINE=1 npm start
```

To serve a production build entirely through Python:

```sh
npm run build
npm run api
```

Open **http://127.0.0.1:8000/**. Fonts and Cesium assets are bundled; public basemaps still need network access.

### Demo loop

1. Wait for the feed lamps and scene time. Select the highest field to dive onto its evidence.
2. Press **DISPATCH**. Telemetry plays at 32× by default. AF-1 returns and files findings with zero geofence violations.
3. Review `request_soil_measurement`, missing nitrate evidence, and the JSON export. Press **GO / accept record**. No approved product means **UNKNOWN / NO-GO**; application stays locked.
4. Open **Mission**, arm **Low battery**, and dispatch again. AF-1 returns early with reserve. Cloud/stale instead defer; exclusion changes the grid and shows rejected segments.
5. Select **Cotton / DWR-316415**, complete an inspection, choose **Lorsban Advanced**, and enable **State override**. Both California and Hawaiʻi prohibit this product, with different cited authorities/reasons. The field stays in California. Other crop/product combinations stay unknown when no exact verified row exists.

### Verification

```sh
npm test
npm run build
```

Raster tests run with the supplied fixtures; synthetic spectral, missing-data, routing, checker, and policy/API tests run without them. Synthetic allowed/restricted rows exist only in tests.

### Official policy sources

- [California DPR cancellation notice](https://www.cdpr.ca.gov/wp-content/uploads/2024/10/general_notice_append_o.pdf), pages 1–2: use deadline and listed product.
- [EPA historical Lorsban Advanced label](https://www3.epa.gov/pesticides/chem_search/ppls/062719-00591-20100812.pdf): identity, chlorpyrifos, and historical cotton use; not current authorization.
- [Hawaiʻi Department of Agriculture and Biosecurity](https://dab.hawaii.gov/pi/pest/): statewide chlorpyrifos use/sale prohibition from January 1, 2023.
