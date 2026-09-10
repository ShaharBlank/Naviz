# Israel OSM feature bundle

`israel-osm-features.sqlite3` is an immutable SQLite/RTree index used for
request-time shade, 3D shadow-scene, and traffic-signal enrichment. It contains
1,001,363 building footprints and 10,545 traffic-signal nodes inside the service
box (`34.15,29.35,35.95,33.40`).

- Source: Geofabrik Israel and Palestine OpenStreetMap extract, 2026-08-16
- Bundle SHA-256: `DBFB0E2732A1BAE468EB79908C5D250166F663BF104FFA4319519746ACF01B20`
- Release archive SHA-256: `FB663559621B53D372EFC99EBCF6B23F80123DAF10E7F0EEB9432F96D8FB0BD5`
- License: Open Database License (ODbL) 1.0
- Attribution: © OpenStreetMap contributors

Rebuild it with `scripts/build_osm_feature_bundle.py` and a newly pinned PBF.
PyOsmium is a build-only dependency and is not installed in the API image.
