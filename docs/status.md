# Implementation status

## Executable now

The repository runs end to end against a pinned deterministic Tel Aviv fixture:
search → plan → compare → preview → navigate → map match → reroute → arrive. Every
public v1 endpoint exists, except account history is read-only from the mobile
surface; repository support already enforces opt-in and 30-day expiry.

The differentiating algorithms are implemented as compact beta engines. Shade
uses continuous exposure and arrival-time interpolation; crossing/side context
cannot change without a mapped permitted crossing. Low-signal alternatives are
only advertised inside the 10% ETA and 15% distance caps. Range-RAPTOR carries a
vehicle-state dimension and rejects unknown personal-bike boarding rules.

The compact API is deployed at <https://naviz-api.onrender.com> from the public
`ghcr.io/shaharblank/naviz-api` container. Expo build `d1adae85` produced a
signed Android 0.1.0 preview APK with that API URL embedded. The APK release
metadata and SHA-256 checksum are in `artifacts/release/README.md`.

## Requires real data or external operations

- Regional OSM extraction, turn expansion, landmark preprocessing, and the 250
  golden OD/time corpus.
- Official nightly Israel GTFS ingestion and cited, effective-dated operator
  bicycle/scooter policies.
- Licensed municipal building height/tree-canopy data, generated directional
  horizon profiles, and the field-labelled shade corpus.
- Lawful provider-specific GBFS discovery URLs and license approval.
- Generated Tel Aviv PMTiles and device-side corridor packaging.
- Neon project/issuer values and physical-device field, accessibility, security,
  and battery audits.
- Dedicated Valhalla/OTP services for the scale profile.

Until those inputs pass `docs/acceptance.md`, the UI continues to display the
demo warning and the data-status endpoint reports fixture coverage.
