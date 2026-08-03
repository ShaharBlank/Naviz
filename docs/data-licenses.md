# Data and license boundary

- OpenStreetMap-derived artifacts must retain © OpenStreetMap contributors and
  ODbL attribution. No public OSM tile server is used for bulk/offline tiles.
- OpenFreeMap is the online beta style/tile provider and MapLibre is the renderer;
  the map UI must keep visible OSM/provider attribution in release builds.
- Israel GTFS is downloaded by a separately reviewed build workflow and records
  its source timestamp and terms in the manifest.
- SIRI is disabled until legitimate Ministry credentials and terms are supplied.
- Each GBFS adapter records provider, discovery URL, deep link, license metadata,
  observation time, and freshness. Availability never implies booking rights.
- Municipal building/tree/crossing inputs are accepted only when redistribution
  and derived-artifact terms are recorded in the bundle manifest.

The demo artifact contains no upstream geographic or transit dataset. Its
manifest is checksum-validated in CI and contains explicit fixture attribution.

ShadoWalk (`3fd6c37`) and Umbra (`f1bfb419`) were reviewed as user-provided
reference prototypes. Their side-continuity, no-waiting-cycle, solar-time, shade
fallback, and navigation-HUD concepts were reimplemented against Naviz's ports;
their stateful `/area/load`, request-time shadow polygons, nearest-segment
navigation, and client autocomplete were not carried forward.
