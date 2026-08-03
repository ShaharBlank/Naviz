from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
REQUIRED_LOGICAL_FILES = frozenset({"street_graph", "places", "transit", "shade_profiles"})


class BundleFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logical_name: str
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str


class BundleManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    bundle_id: str
    coverage: str
    generated_at: datetime
    source_versions: dict[str, str]
    files: list[BundleFile]
    attribution: list[str]


@dataclass(frozen=True, slots=True)
class BundleValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def build_manifest(
    bundle_directory: Path,
    *,
    bundle_id: str,
    coverage: str,
    logical_files: dict[str, tuple[str, str]],
    source_versions: dict[str, str],
    attribution: Iterable[str],
) -> BundleManifest:
    files: list[BundleFile] = []
    for logical_name, (relative_path, media_type) in sorted(logical_files.items()):
        resolved = _safe_resolve(bundle_directory, relative_path)
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        files.append(
            BundleFile(
                logical_name=logical_name,
                path=relative_path.replace("\\", "/"),
                sha256=sha256_file(resolved),
                size_bytes=resolved.stat().st_size,
                media_type=media_type,
            )
        )
    return BundleManifest(
        schema_version=SCHEMA_VERSION,
        bundle_id=bundle_id,
        coverage=coverage,
        generated_at=datetime.now(UTC),
        source_versions=source_versions,
        files=files,
        attribution=sorted(set(attribution)),
    )


def validate_bundle(bundle_directory: Path, manifest: BundleManifest) -> BundleValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.schema_version != SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema version {manifest.schema_version}; expected {SCHEMA_VERSION}"
        )
    logical_names = {item.logical_name for item in manifest.files}
    missing = REQUIRED_LOGICAL_FILES - logical_names
    if missing:
        errors.append(f"Missing required logical files: {', '.join(sorted(missing))}")
    if not manifest.attribution:
        errors.append("At least one attribution statement is required")
    if not manifest.source_versions:
        errors.append("Source versions are required")
    for item in manifest.files:
        try:
            resolved = _safe_resolve(bundle_directory, item.path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not resolved.is_file():
            errors.append(f"Missing bundle file: {item.path}")
            continue
        if resolved.stat().st_size != item.size_bytes:
            errors.append(f"Size mismatch: {item.path}")
        if sha256_file(resolved) != item.sha256:
            errors.append(f"Checksum mismatch: {item.path}")
        if item.size_bytes == 0:
            warnings.append(f"Empty bundle file: {item.path}")
    return BundleValidation(not errors, tuple(errors), tuple(warnings))


def write_manifest(path: Path, manifest: BundleManifest) -> None:
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_manifest(path: Path) -> BundleManifest:
    return BundleManifest.model_validate_json(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_resolve(root: Path, relative_path: str) -> Path:
    resolved_root = root.resolve()
    resolved = (root / relative_path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"Bundle path escapes its root: {relative_path}")
    return resolved
