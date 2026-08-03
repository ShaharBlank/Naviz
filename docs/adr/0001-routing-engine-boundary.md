# ADR 0001: Stable product API over replaceable routing engines

Status: accepted

FastAPI owns Naviz's public route contract. The free hosted profile uses compact,
immutable Tel Aviv graph arrays and bounded Range-RAPTOR. Production adapters use
Valhalla and OpenTripPlanner but normalize results into identical route, leg,
maneuver, metric, warning, and data-quality types.

The mobile app never calls an engine directly. There is no public `/area/load` and
no request can replace process-global data. This permits a later infrastructure
upgrade without a mobile API migration.

