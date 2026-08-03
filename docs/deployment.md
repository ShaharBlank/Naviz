# Deployment

## Render beta API

1. Create a Render Blueprint from `render.yaml`.
2. Set `NAVIZ_ALLOWED_ORIGINS` to exact web/development-client origins.
3. Optionally set a Neon pooled URL in `NAVIZ_DATABASE_URL` and the OIDC issuer in
   `NAVIZ_AUTH_ISSUER`. The adapter converts ordinary PostgreSQL URLs to asyncpg.
4. Configure lawful feeds as comma-separated
   `provider|discovery_url|operator_deep_link` entries in `NAVIZ_GBFS_FEEDS`.
5. Pin `NAVIZ_DATA_BUNDLE` to the validated artifact ID used by the image.

The free profile has one worker, cold starts, low concurrency, and no SLA. The
mobile app displays “Starting routing engine” after 2.5 seconds and never invents
a progress percentage.

## Database

The zero-ops beta creates missing tables idempotently. Controlled environments
should run from `apps/api`:

```powershell
alembic upgrade head
```

Only account-scoped favorites, preferences, and opt-in expiring history are in
PostgreSQL. GPS fixes and anonymous origin/destination coordinates are not.

## Mobile

Set `EXPO_PUBLIC_API_URL`, run `eas init`, and create a development build before
testing MapLibre/background navigation. `eas build --platform android --profile
preview` produces an internal APK. The iOS development profile requires a valid
signing team; simulator/personal-team and Android remain the zero-cost paths.

The repository does not contain signing keys, EAS project IDs, provider secrets,
or a fake live-data URL.
