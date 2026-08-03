from __future__ import annotations

import argparse
import json
from pathlib import Path

from naviz_api.main import app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[1] / "packages" / "contracts" / "openapi.json",
    )
    args = parser.parse_args()
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"OpenAPI contract is stale; run: python {Path(__file__).name}")
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

