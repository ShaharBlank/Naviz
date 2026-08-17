# Implementation status

## Regional MVP

The mobile application and API run the complete journey: search, plan, compare,
preview, navigate, match location to route progress, reroute, and arrive. The
hosted profile uses real metropolitan search and street data, scheduled public
transport, live corridor building and traffic-signal context, and Dott's live
Tel Aviv shared-scooter availability with operator deep links. It never returns
the deterministic CI fixture.

The Android development build has been exercised on an Android 16 Pixel emulator
for permissions, fresh GPS acquisition, Hebrew RTL and English LTR, keyboard and
search behavior, shaded walking, scheduled transit, driving, foreground and
background navigation, three-fix off-route hysteresis, rerouting, progress, and
arrival. Strict TypeScript, ESLint, Jest, Ruff, mypy, pytest, contract generation,
and Expo dependency checks are release gates.

The release audit has no critical npm findings. It still reports upstream
high-severity advisories in Expo/Metro's local image parser and an iOS project
generation dependency; neither package is included in the Android runtime
bundle, and npm currently offers no SDK-56-compatible patched resolution. CI
reports those findings, blocks critical findings, and Dependabot checks weekly
for a compatible upstream fix.

Shade exposure is evaluated from the real route geometry, current solar position,
and OpenStreetMap building footprints. Low-signal routes use mapped signal nodes
and advertise an alternative only inside the 10% ETA and 15% distance caps.
Transit rules reject unknown full-size-bicycle permission and explicitly present
fold-and-carry behavior for folding vehicles.

## Continued hardening

- Add further provider-approved GBFS feeds as each operator's license and
  deep-link flow is confirmed. Dott is enabled under CC-BY-4.0; no synthetic
  shared vehicles are shown.
- Package metropolitan PMTiles for broader offline map coverage.
- Complete physical-device shade, multimodal, traffic-signal, accessibility, and
  battery field corpora defined in `docs/acceptance.md`.
- Move community endpoints to dedicated Valhalla, MOTIS/OTP, Photon, Overpass,
  and tile services before usage grows beyond the single-user free-host profile.
- Enable authenticated SIRI only after legitimate Ministry credentials are
  available; until then transit departure times are explicitly scheduled.
