# Naviz

Naviz is an open, Hebrew-first navigation beta for Tel Aviv-Yafo. This monorepo
contains an executable product vertical slice for shaded walking, personal
bicycle/scooter + scheduled transit, and low-traffic-signal road alternatives.

## What is implemented

- FastAPI/Pydantic 2 API with RFC 9457 errors, request IDs, Polyline6 routes,
  search/reverse search, rerouting, data status, GBFS normalization, and optional
  authenticated favorites/preferences/history.
- Compact CSR street graph, side-context and crossing legality, time-dependent
  five-minute shade profiles, bounded shade detours, low-signal caps, maneuvers,
  HMM/Viterbi-style map matching, and compact Range-RAPTOR transit.
- Conservative personal-vehicle transit rules: a full-size bicycle is never
  silently boarded when permission is unknown. Shared vehicles are treated as
  separate access/egress rentals.
- Typed Valhalla and OpenTripPlanner adapters behind normalized engine ports.
- Expo SDK 56/React Native 0.85 development-build app with MapLibre,
  Hebrew/English, RTL/LTR, local recents/favorites, route cards, voice/haptics,
  background/foreground location, off-route hysteresis, rerouting, on-device
  SQLite search fallback, and unexpired-route offline continuation.
- Immutable checksummed bundle contract, OpenAPI-generated TypeScript types,
  Alembic migrations, Docker/Render configs, CI, dependency audit, and SBOM job.

The checked-in `demo-2026-08-02` graph and search index are deterministic UI and
contract fixtures. They are deliberately labelled **not for real navigation**.
Real OSM/GTFS/building/canopy/crossing/PMTiles artifacts and the field corpus are
deployment inputs, not fabricated by this repository.

## Repository

- `apps/api` — modular Python API, compact engines, and external-engine adapters.
- `apps/mobile` — Expo Router application using MapLibre Native.
- `packages/data_pipeline` — immutable manifest/checksum validation tooling.
- `packages/contracts` — checked-in OpenAPI source for generated mobile types.
- `artifacts/demo` — tiny validated fixture proving the artifact contract.
- `infra` — non-root Render container.
- `docs` — decisions, deployment, privacy, data licensing, and launch gates.

## Run locally

Python 3.12 and Node 22 are the supported toolchains.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\apps\api[dev,data,postgres]" -e ".\packages\data_pipeline"
.\.venv\Scripts\python -m uvicorn naviz_api.main:app --reload
```

The API is at `http://localhost:8000/docs`. In another terminal:

```powershell
cd apps\mobile
npm ci
$env:EXPO_PUBLIC_API_URL="http://YOUR-LAN-IP:8000"
npx expo start --dev-client
```

MapLibre and background navigation require an Expo development build; Expo Go is
not a valid production test path. Run `eas init` once, then
`npm run android:apk` for the internal Android APK configuration. iOS device
builds require Apple signing.

The containerized local stack includes PostGIS:

```powershell
docker compose up --build
```

## Quality gates

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy apps\api\src packages\data_pipeline\naviz_data
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m naviz_data.cli validate artifacts\demo
.\.venv\Scripts\python scripts\export_openapi.py --check

cd apps\mobile
npm run contract:generate
npm run typecheck
npm run lint
npm test -- --runInBand
npx expo-doctor@latest
npx expo export --platform android --output-dir dist\android-bundle
```

See [deployment](docs/deployment.md), [implementation status](docs/status.md),
and [acceptance gates](docs/acceptance.md) before treating a build as a public beta.
