# Naviz API

The FastAPI service owns the public contract and selects one of three engine
profiles: `compact` (the free-hosted implementation), `valhalla`, or `otp`.
Engine adapters normalize into the same domain types.

No endpoint mutates or replaces the active regional graph. Data bundles are
immutable and selected at process start.

