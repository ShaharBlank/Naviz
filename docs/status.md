# Implementation status

## Nationwide beta slice

The mobile application and local API run the complete journey: search, plan, compare,
preview, navigate, match location to route progress, reroute, and arrive. The
prepared nationwide profile uses live search and street routing, scheduled public
transport, an immutable national building/traffic-signal bundle, and provider-
scoped shared mobility with operator deep links. It never returns the deterministic
CI fixture.

The public Render service reports API `0.3.0`, data bundle
`israel-live-2026-08-16`, and nationwide Israel coverage. The checksummed OSM
feature bundle is published as the `data-israel-2026-08-16` GitHub release and
is verified before the container starts. Hebrew Photon queries use OSM's default
localized names because Photon does not accept `lang=he`; English explicitly
uses `lang=en`.

The Android 0.5.1 universal preview APK was built for ARM64, ARMv7, x86, and
x86_64 and cryptographically verified. Its x86_64 variant was exercised on an
Android 16 Pixel emulator for installation, startup, fresh GPS acquisition, and
hosted nationwide search. Intercity route testing exposed and fixed a quadratic
traffic-signal enrichment path: national-bundle feature lookup for the regression
case now completes in 0.221 seconds after filtering to the real route corridor.
Strict TypeScript, ESLint, Jest, Ruff, mypy, pytest, contract generation, and
Expo dependency checks are release gates.

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
