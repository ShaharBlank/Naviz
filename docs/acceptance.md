# Public-beta acceptance gates

The bundled graph and schedules are deliberately labelled as demo data. They are
not acceptable for field navigation. A regional artifact can be promoted only
after all automated and field gates pass.

## Automated gates

- All Python unit, property, API, adapter-contract, and bundle-validation tests pass.
- All mobile state-machine, navigation-progress, component, RTL/LTR, and E2E tests pass.
- Ruff, mypy strict mode, ESLint, and TypeScript strict mode are clean.
- Every golden route is connected, respects direction/turn/vehicle/crossing constraints,
  is reproducible for the pinned bundle, and stays inside explicit detour caps.
- Bundle checksums, schema, source timestamps, attribution, and data-quality counts pass.
- Warm p95 is below three seconds for street/shade and five seconds for multimodal at
  one-user load; warm reroute p95 is below three seconds.

## Field gates

- 30 shaded walks across dates and times: at least 85% shade/sun classification
  accuracy for high-confidence samples.
- 20 multimodal journeys: no prohibited or unknown carry-on rule is silently used.
- 30 road journeys: advertised signal reduction is correct and never exceeds 10%
  time or 15% distance overhead.
- At least 95% of field navigations finish without manual route recovery.
- One-hour navigation consumes less than 12% battery on each reference device.
- VoiceOver, TalkBack, Dynamic Type, reduced motion, Hebrew RTL, and English LTR have
  no critical defects.

Field observations use random test identifiers and never retain participant identity.

