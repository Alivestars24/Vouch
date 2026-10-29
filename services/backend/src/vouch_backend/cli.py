from __future__ import annotations

import os

import uvicorn


def api() -> None:
    uvicorn.run(
        "vouch_backend.api:app",
        host="127.0.0.1",
        port=int(os.getenv("VOUCH_API_PORT", "8010")),
        reload=False,
        access_log=True,
    )


if __name__ == "__main__":
    api()
