# Implementation and contracts

## Observations

`POST /fuse {"refresh": false}` validates the known fixture, concurrently requests Earth Search, POWER and NAIP metadata, and returns `snapshot_id`, ordered `fields`, feed modes, scene time, imagery metadata, and fixture-check results. The first call performs real requests by default. Cache lifetime is five minutes; `refresh: true` forces requests. `AGRIFORGE_OFFLINE=1` explicitly disables live queries and always marks fixtures.

Each field contains its clipped DWR geometry, representative point, rank, and evidence packet. The packet carries sources/dates, CDL class, SCL counts, clear fraction, NDVI/NDMI distributions, anomaly gap, POWER values with nulls, whole-box SSURGO context, alternatives, missing evidence, and an action. Rank is mean positive same-class gap × clear fraction. Class comparators with fewer than ten clear pixels produce no anomaly. Fields with fewer than twenty clear pixels, clear fraction below 60%, or imagery older than thirty days defer.

`GET /ndvi.png?snapshot_id=...&field_id=...` returns a geographic PNG transparent outside the chosen field and masked pixels. Red/NIR are 10 m; SWIR and SCL are natively 20 m and explicitly aligned onto the red grid. CDL is natively 30 m. Resampling NDMI does not create finer spatial information. Crop labels are annual classes, not confirmed current crops.

POWER context is the fourteen days strictly before scene acquisition, with fill values replaced by null, counts of available days, and partial sums labeled. SSURGO is center-point context only. Organic matter is not nitrate. NAIP/World Imagery is an aerial picture, never the anomaly layer.

## Planning and simulation

`POST /simulate` takes `snapshot_id`, `field_id`, `low_battery`, `cloud`, `stale`, and `exclusion`. It resolves geometry/quality from the server snapshot and rejects stale snapshot IDs. The browser cannot submit arbitrary field geometry.

Planning uses EPSG:32610 meters. For a multipart field, inspection uses its largest connected component. A 2 m interior margin keeps lanes/turns inside. An authored northwest wedge is subtracted with a 2 m margin when enabled. Horizontal lanes are spaced 30 m apart. A polygon-vertex visibility graph joins lanes without cutting across concavities or exclusions. An authored 16 m transit corridor joins the depot to the field entry; an 8 m pad footprint completes the mission geofence.

Dynamics: 8 m/s, 40 m AGL, 1% battery per 80 m, no wind or turn costs. Normal launch is 100%. Low-battery launch is sized for the direct depot round trip plus about 200 m of inspection, capped at 95%. Before every inspection step, the planner computes a feasible route back through the field to entry and depot. It returns early before projected landing falls below 25% plus 0.2% numerical margin. Long normal missions can also return early.

The independent checker examines complete traveled segments against the geofence and exclusion and verifies minimum battery. It catches paths whose endpoints are inside but whose connecting segment crosses a forbidden area. Violating plans return HTTP 422. Deferred missions have no trace. Scenario flags never replace actual scene dates, NDVI, or SCL counts.

The response begins with `simulated: true` and supplies trace, phases, distance, elapsed simulated time, battery, simulated sample count, rejected segments, geofence, exclusion, final status, and checker results. Samples are simulated locations, not newly measured crop evidence. AF-2 remains cold. `data/runtime/AF-1.json` is a single state file, not a flight log.

## Advisory and gates

`GET /missions/{id}/findings` returns the observation packet plus path result and filed time. `GET /missions/{id}/advice` runs a deterministic template on that packet only. Rates are null. Missing nitrate, irrigation-water nitrate, prior applications, growth stage, and an approved crop product remain explicit.

`POST /gate` takes `mission_id`, `human_go` (default false), `product_name`, and optional `state_override: "15"`. Actual field state remains 06. Product, state and crop must exactly match a verified catalog row. Absent/unknown and prohibited rows veto; prohibition wins conflicting entries. Restricted requires human GO and displays its restrictions. The labeled Hawaiʻi comparison does not persist or overwrite the real-field gate.

`POST /apply {"mission_id": "..."}` rechecks the stored real-field gate and requires a completed inspection. A successful response is SIMULATED APPLICATION, reuses the verified track, and supplies no rate. The real catalog has no allowed row, so the shipped demo stays locked. Only tests use synthetic approvals to exercise the successful branch.

Direct endpoints and `/api/*` aliases work. Vite proxies the API during development. On Vercel, the CDN serves Vite/Cesium assets and one Python function handles API requests. Signed snapshot, mission, and approval packets let requests survive cold starts and reach different instances. The UI uses POST `/findings` and `/advice` with its signed mission packet, and sends the signed approval to `/apply`; legacy in-memory routes remain available locally. NDVI images are embedded in the fusion response. Aerial tiles accept a signed image identifier. Caches are optional optimizations; no shared database is required. Hosted state writes to `/tmp`. See [Vercel setup](vercel.md). This prototype has no account authentication or durable shared history.
