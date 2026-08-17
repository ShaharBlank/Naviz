# Deployment

## Current metropolitan deployment

- API: <https://naviz-api.onrender.com>
- API health: <https://naviz-api.onrender.com/health>
- API data status: <https://naviz-api.onrender.com/v1/data/status>
- Public container: `ghcr.io/shaharblank/naviz-api`
- Source repository: <https://github.com/ShaharBlank/Naviz> (Apache-2.0)
- Expo project: <https://expo.dev/accounts/shaharblank/projects/naviz>
- Android build:
  <https://expo.dev/accounts/shaharblank/projects/naviz/builds/be90e304-e999-463c-9f53-b6364c519c2c>

The Android `preview` profile embeds `https://naviz-api.onrender.com` as
`EXPO_PUBLIC_API_URL`. The public EAS artifact is temporary; the verified local
copy and its checksum are documented in `artifacts/release/README.md`.

## Render API

1. Create a Render Blueprint from `render.yaml`.
2. Set `NAVIZ_ALLOWED_ORIGINS` to exact web/development-client origins.
3. Optionally set a Neon pooled URL in `NAVIZ_DATABASE_URL` and the OIDC issuer in
   `NAVIZ_AUTH_ISSUER`. The adapter converts ordinary PostgreSQL URLs to asyncpg.
4. Configure lawful feeds as comma-separated
   `provider|discovery_url|operator_deep_link` entries in `NAVIZ_GBFS_FEEDS`.
5. Keep `NAVIZ_LIVE_PROVIDERS=true` and pin `NAVIZ_DATA_BUNDLE` to the deployed
   regional integration version. Production startup fails if a required provider
   URL is absent, so it cannot silently fall back to test fixtures.
6. Set `NAVIZ_FEATURE_BUNDLE_PATH=/app/apps/api/data/metro-osm-features.sqlite3`.
   The bundled SQLite/RTree extract owns shade and traffic-signal lookup during
   requests; Overpass remains an offline refresh/fallback source only.

The free profile has one worker, cold starts, low concurrency, and no SLA. The
mobile app displays “Starting routing engine” after 2.5 seconds and never invents
a progress percentage.

## Database

The zero-ops deployment creates missing tables idempotently. Controlled environments
should run from `apps/api`:

```powershell
alembic upgrade head
```

Only account-scoped favorites, preferences, and opt-in expiring history are in
PostgreSQL. GPS fixes and anonymous origin/destination coordinates are not.

## Mobile

Set `EXPO_PUBLIC_API_URL`, run `eas init`, and create a development build before
testing MapLibre/background navigation. Expo SDK 57 is the pinned mobile runtime.
`eas build --platform android --profile preview` produces an internal APK. The
iOS development profile requires a valid signing team; simulator/personal-team
and Android remain the zero-cost paths.

The repository contains the public EAS project ID needed for reproducible builds,
but does not contain signing keys, provider secrets, or a fake live-data URL.

## Regional provider contract

The hosted profile uses Photon for regional search, Valhalla for street routes,
the pinned Geofabrik/OSM feature bundle for shade and signals, and
Transitous/MOTIS for scheduled transit. External calls include a named contact
User-Agent, are cached, remain within the metropolitan coverage boundary, and
produce explicit service errors instead of returning fixture routes when a
provider is unavailable. Transitous deployment also requires a publicly licensed
source repository and visible source attribution in the mobile route card.
