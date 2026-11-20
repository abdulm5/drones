# Vercel deployment

Import `abdulm5/drones` into Vercel, using the repository root. `vercel.json` configures the Vite build, Python 3.13 API function, API routing, and a 300-second function limit. The globe assets and fonts are served as static files.

## Required configuration

Set `AGRIFORGE_SIGNING_KEY` in Vercel to a private random value of at least 32 bytes. Generate it locally with `openssl rand -hex 32`. Keep the same value across instances. Do not prefix it with `VITE_`.

Git deployments fetch the small fixture archive automatically from the [fixtures-v1 release](https://github.com/abdulm5/drones/releases/tag/fixtures-v1). `scripts/deployment-fixtures.json` pins its URL and SHA-256. Only the eleven required small files are included; the 36 MB county raster is excluded. The build verifies the checksum and file allowlist before packaging the API. No fixture environment variables are required for this repository.

For a custom dataset archive, run `npm run fixtures:pack`, upload the ZIP to an HTTPS host, and set both `AGRIFORGE_DATA_URL` and `AGRIFORGE_DATA_SHA256` to override the pinned release.

Alternatively, deploy from this local checkout using the Vercel CLI. `.vercelignore` permits the minimal local fixtures while excluding the large raster, generated state, secrets, and development dependencies. The signing key is still required. Data is never committed to Git.

## Serverless behavior

Observation, mission, and approval packets carry signed, expiring state. Requests can reach different instances without losing the mission. The browser cannot edit a packet to approve a product; the application endpoint checks the current policy catalog again. These one-hour demo sessions are not account authentication or durable history. No Redis service is required.

Measurement images travel with the observation response, and aerial tiles use a signed imagery identifier. Runtime state writes to `/tmp/agriforge/runtime` on Vercel. Process-local caches are only optimizations.

Live Sentinel-2 and POWER requests remain the default. `AGRIFORGE_OFFLINE=1` is optional for a labeled fixture rehearsal. The advisor is a deterministic template; it does not call Grok or Grok Bot.

Python runtime dependencies have Linux wheels; their expanded contents total approximately 264 MiB, below Vercel's 500 MB Python bundle limit. Local production builds and cold-start workflow checks pass. An actual Vercel deployment still requires the project environment above; no hosted deployment has been performed here.

References: [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [function limits](https://vercel.com/docs/functions/limitations).
