from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from .osm_features import validate_osm_feature_bundle


@dataclass(frozen=True, slots=True)
class PinnedFeatureArtifact:
    bundle_id: str
    url: str
    archive_sha256: str
    archive_member: str
    database_sha256: str

    @classmethod
    def from_json(cls, path: Path) -> PinnedFeatureArtifact:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported feature artifact manifest schema")
        artifact = cls(
            bundle_id=str(payload["bundle_id"]),
            url=str(payload["url"]),
            archive_sha256=_sha(payload["archive_sha256"], "archive_sha256"),
            archive_member=str(payload["archive_member"]),
            database_sha256=_sha(payload["database_sha256"], "database_sha256"),
        )
        if not artifact.url.startswith("https://"):
            raise ValueError("Feature artifact URL must use HTTPS")
        if Path(artifact.archive_member).name != artifact.archive_member:
            raise ValueError("archive_member must be a root-level filename")
        return artifact


def materialize_feature_artifact(
    manifest_path: Path,
    output_path: Path,
    *,
    open_url: Callable[[str], BinaryIO] | None = None,
) -> PinnedFeatureArtifact:
    """Download, verify, extract, and validate one immutable feature database."""

    artifact = PinnedFeatureArtifact.from_json(manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    opener = open_url or _open_url
    with tempfile.TemporaryDirectory(dir=output_path.parent) as raw_temp:
        temp = Path(raw_temp)
        archive_path = temp / "artifact.zip"
        database_path = temp / artifact.archive_member
        digest = hashlib.sha256()
        with opener(artifact.url) as source, archive_path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                destination.write(chunk)
        if digest.hexdigest() != artifact.archive_sha256:
            raise ValueError("Feature artifact archive checksum mismatch")
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1 or members[0].filename != artifact.archive_member:
                raise ValueError("Feature artifact archive has unexpected members")
            with archive.open(members[0]) as source, database_path.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        if _file_sha256(database_path) != artifact.database_sha256:
            raise ValueError("Feature database checksum mismatch")
        validation = validate_osm_feature_bundle(database_path)
        if not validation.valid:
            raise ValueError("Invalid feature database: " + "; ".join(validation.errors))
        database_path.replace(output_path)
    return artifact


def _open_url(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "Naviz-data-builder/1"})
    return cast(BinaryIO, urllib.request.urlopen(request, timeout=120))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha(value: object, name: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return normalized


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python -m naviz_data.artifact_fetch MANIFEST OUTPUT", file=sys.stderr)
        return 2
    artifact = materialize_feature_artifact(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps({"bundle_id": artifact.bundle_id, "output": sys.argv[2]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
