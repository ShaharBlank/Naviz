# ADR 0002: Anonymous-first location privacy

Status: accepted

Routing requests are stateless. Anonymous coordinates and GPS traces are not stored.
The app retains only the active route and last background fix in device secure storage;
both are removed when navigation ends. Account route history is disabled by default,
opt-in, and expires after 30 days.

Application logs exclude exact coordinates, route polylines, access tokens, and search
text. Future probe traffic requires a separate, explicit consent flow and aggregation
design review.

