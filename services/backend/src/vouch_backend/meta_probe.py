from __future__ import annotations

import json

from .config import Settings
from .meta_api import probe_meta_capabilities
from .providers import ProviderError


def main() -> None:
    try:
        result = probe_meta_capabilities(Settings.from_env())
    except ProviderError as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": error.code,
                        "message": error.safe_message,
                        "retryable": error.retryable,
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise SystemExit(3 if error.retryable else 2) from None
    print(json.dumps({"ok": True, **result.model_dump()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
