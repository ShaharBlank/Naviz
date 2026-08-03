from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bundle import read_manifest, validate_bundle
from .gtfs import validate_gtfs


def main() -> int:
    parser = argparse.ArgumentParser(prog="naviz-data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate an immutable regional bundle")
    validate.add_argument("bundle_directory", type=Path)
    validate.add_argument("--manifest", type=Path)
    gtfs = subparsers.add_parser("validate-gtfs", help="Validate GTFS references and coordinates")
    gtfs.add_argument("archive", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        manifest_path = args.manifest or args.bundle_directory / "manifest.json"
        bundle_result = validate_bundle(args.bundle_directory, read_manifest(manifest_path))
        print(
            json.dumps(
                {
                    "valid": bundle_result.valid,
                    "errors": bundle_result.errors,
                    "warnings": bundle_result.warnings,
                },
                indent=2,
            )
        )
        return 0 if bundle_result.valid else 1
    if args.command == "validate-gtfs":
        gtfs_result = validate_gtfs(args.archive)
        print(
            json.dumps(
                {
                    "valid": gtfs_result.valid,
                    "errors": gtfs_result.errors,
                    "warnings": gtfs_result.warnings,
                    "counts": gtfs_result.counts,
                },
                indent=2,
            )
        )
        return 0 if gtfs_result.valid else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
