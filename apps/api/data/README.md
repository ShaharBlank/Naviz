# Metropolitan OSM feature bundle

`metro-osm-features.sqlite3` is an immutable SQLite/RTree index used for
request-time shade and traffic-signal enrichment. It contains 137,049 building
footprints and 3,991 traffic-signal nodes inside Naviz's metropolitan coverage
box (`34.69,31.94,34.93,32.20`).

- Source: Geofabrik Israel and Palestine OpenStreetMap extract, 2026-08-16
- Source SHA-256: `FF07BDA6E385105FD0126704D0D940A5F8A531DFEBC16AC22437FADFF40862C5`
- Bundle SHA-256: `2470A06286C576FAD135EDA0D0F052AFE0197827ADDC6A9FE608DB0B390F94ED`
- License: Open Database License (ODbL) 1.0
- Attribution: © OpenStreetMap contributors

Rebuild it with `scripts/build_osm_feature_bundle.py` and a newly pinned PBF.
PyOsmium is a build-only dependency and is not installed in the API image.
