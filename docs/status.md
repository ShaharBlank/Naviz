# Implementation status

## Nationwide beta slice

The mobile application and local API run the complete journey: search, plan, compare,
preview, navigate, match location to route progress, reroute, and arrive. The
prepared nationwide profile uses live search and street routing, scheduled public
transport, an immutable national building/traffic-signal bundle, and provider-
scoped shared mobility with operator deep links. It never returns the deterministic
CI fixture.

The public Render service still reports API `0.2.0`, data bundle
`metro-live-2026-08-16`, and metropolitan coverage. Nationwide API `0.3.0` is
ready locally but is not deployed until the checksummed Israel OSM bundle is
published at the pinned GitHub release URL and the new container is published.

The Android 0.5.0 universal preview APK was built for ARM64, ARMv7, x86, and
x86_64 and cryptographically verified. Its x86_64 variant was exercised on an
Android 16 Pixel emulator for permissions, fresh GPS acquisition, Hebrew RTL and
English LTR, hosted search/routing, route comparison, walking and driving 3D
guidance, direction-aware person/vehicle markers, synthetic GPS progress, and
repeated live 2D/3D switching. Strict TypeScript, ESLint, Jest, Ruff, mypy,
pytest, contract generation, and Expo dependency checks are release gates.

The release audit has no critical npm findings. It still reports upstream
high-severity advisories through Expo/Metro's local build tooling. npm's offered
remediation is an incompatible downgrade from Expo SDK 57 and React Native 0.86;
the production Hermes bundle does not expose those local build-server paths. CI
reports the findings, blocks critical findings, and Dependabot checks weekly for
a compatible upstream fix.

Shade exposure is evaluated from route geometry, solar position, and OpenStreetMap
building footprints. The 3D view requests clipped ground-shadow polygons for the
selected time and keeps high-confidence height geometry distinct. Low-signal routes use mapped signal nodes
and advertise an alternative only inside the 10% ETA and 15% distance caps.
Transit rules reject unknown full-size-bicycle permission and explicitly present
fold-and-carry behavior for folding vehicles.

## Continued hardening

- Add further provider-approved GBFS feeds as each operator's license and
  deep-link flow is confirmed. Dott is enabled under CC-BY-4.0; no synthetic
  shared vehicles are shown.
- Package regional PMTiles for opt-in offline map coverage without bloating the APK.
- Complete physical-device shade, multimodal, traffic-signal, accessibility, and
  battery field corpora defined in `docs/acceptance.md`.
- Move community endpoints to dedicated Valhalla, MOTIS/OTP, Photon,
  and tile services before usage grows beyond the single-user free-host profile.
- Enable authenticated SIRI only after legitimate Ministry credentials are
  available; until then transit departure times are explicitly scheduled.
