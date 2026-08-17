# Data and license boundary

- OpenStreetMap-derived artifacts must retain © OpenStreetMap contributors and
  ODbL attribution. No public OSM tile server is used for bulk/offline tiles.
- OpenFreeMap is the online style/tile provider and MapLibre is the renderer;
  the map UI must keep visible OSM/provider attribution in release builds.
- Israel GTFS is downloaded by a separately reviewed build workflow and records
  its source timestamp and terms in the manifest.
- SIRI is disabled until legitimate Ministry credentials and terms are supplied.
- Each GBFS adapter records provider, discovery URL, deep link, license metadata,
  observation time, and freshness. Availability never implies booking rights.
- Dott Tel Aviv live vehicle availability is read from the operator's official
  GBFS 2.3 discovery feed and attributed under CC-BY-4.0. Naviz shows discovery
  data only and hands booking/unlocking to Dott's operator app.
- Municipal building/tree/crossing inputs are accepted only when redistribution
  and derived-artifact terms are recorded in the bundle manifest.

Transit routes in the hosted regional profile are calculated by Transitous/MOTIS.
The mobile route card links visibly to the Transitous source list, and the API
sends an identifying contact User-Agent. Transitous may log route coordinates and
request metadata for up to two days under its published privacy policy.

The test artifact contains no upstream geographic or transit dataset. Its
manifest is checksum-validated in CI and contains explicit fixture attribution.

ShadoWalk (`3fd6c37`) and Umbra (`f1bfb419`) were reviewed as user-provided
reference prototypes. Their side-continuity, no-waiting-cycle, solar-time, shade
fallback, and navigation-HUD concepts were reimplemented against Naviz's ports;
their stateful `/area/load`, request-time shadow polygons, nearest-segment
navigation, and client autocomplete were not carried forward.
