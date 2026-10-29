from __future__ import annotations

import argparse
import json

from .config import Settings
from .meta_api import MetaModelClient
from .providers import ProviderError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one bounded synthetic paid Spark Responses API smoke test."
    )
    parser.add_argument(
        "--confirm-paid-synthetic-call",
        action="store_true",
        help="Required acknowledgement that this sends one paid synthetic inference.",
    )
    args = parser.parse_args()
    if not args.confirm_paid_synthetic_call:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "CONFIRMATION_REQUIRED",
                        "message": (
                            "Re-run with --confirm-paid-synthetic-call to send one bounded "
                            "synthetic inference."
                        ),
                        "retryable": False,
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise SystemExit(2)
    settings = Settings.from_env()
    if settings.meta_api_key is None:
        error = ProviderError(
            "NOT_CONFIGURED",
            "Meta Model API is not configured on this server.",
            retryable=False,
        )
    else:
        try:
            result = MetaModelClient(settings.meta_api_key).run_spark_smoke()
        except ProviderError as caught:
            error = caught
        else:
            print(json.dumps({"ok": True, **result.model_dump()}, indent=2, sort_keys=True))
            return
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
    raise SystemExit(3 if error.retryable else 2)


if __name__ == "__main__":
    main()
