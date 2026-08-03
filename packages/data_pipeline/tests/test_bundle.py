from pathlib import Path

from naviz_data.bundle import build_manifest, validate_bundle


def test_manifest_detects_tampering(tmp_path: Path) -> None:
    logical = {}
    for name in ("street_graph", "places", "transit", "shade_profiles"):
        filename = f"{name}.bin"
        (tmp_path / filename).write_bytes(name.encode())
        logical[name] = (filename, "application/octet-stream")
    manifest = build_manifest(
        tmp_path,
        bundle_id="test",
        coverage="test coverage",
        logical_files=logical,
        source_versions={"osm": "test"},
        attribution=["© OpenStreetMap contributors"],
    )
    assert validate_bundle(tmp_path, manifest).valid
    (tmp_path / "street_graph.bin").write_bytes(b"changed")
    result = validate_bundle(tmp_path, manifest)
    assert not result.valid
    assert any("mismatch" in error.lower() for error in result.errors)
