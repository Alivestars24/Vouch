from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .api import app
from .config import BACKEND_ROOT

DESTINATION = BACKEND_ROOT / "openapi.json"


def render_schema() -> str:
    # OpenAPI rendering reads route metadata; it does not run application lifespan or requests.
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate or verify the local FastAPI OpenAPI schema."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if the committed schema is stale."
    )
    arguments = parser.parse_args(argv)
    rendered = render_schema()
    if arguments.check:
        if not DESTINATION.is_file():
            print(
                f"OpenAPI schema is missing: {DESTINATION}. Run npm.cmd run openapi.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if DESTINATION.read_text(encoding="utf-8") != rendered:
            print(
                f"OpenAPI schema is stale: {DESTINATION}. Run npm.cmd run openapi.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print("OpenAPI schema is current.")
        return
    DESTINATION.write_text(rendered, encoding="utf-8")
    print(DESTINATION)


if __name__ == "__main__":
    main()
