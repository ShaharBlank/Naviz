# Naviz API

The FastAPI service owns the public contract and selects either the regional live
profile or the deterministic test profile. Valhalla, MOTIS/Transitous, Photon,
Overpass, compact Range-RAPTOR, and future OTP deployments normalize into the
same domain types.

No endpoint mutates or replaces the active regional graph. Data bundles are
immutable and selected at process start.
