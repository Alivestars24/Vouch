"""Bounded SAM image transport; not connected to campaign execution."""

from __future__ import annotations

import base64
import json
import re
import struct
from dataclasses import dataclass

import httpx

from .meta_api import META_API_BASE_URL, MetaModelClient
from .providers import ProviderError

MAX_IMAGE_BYTES = 4_000_000
MAX_STREAM_BYTES = 4_000_000
BOX_PATTERN = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>")


@dataclass(frozen=True, slots=True)
class ImageBox:
    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int


def segment_image(
    api_key: str,
    png: bytes,
    *,
    concept: str,
    transport: httpx.BaseTransport | None = None,
) -> tuple[ImageBox, ...]:
    """Locate one concept in a PNG. Callers must establish consent, budget and scope."""
    MetaModelClient(api_key)
    if (
        not 24 <= len(png) <= MAX_IMAGE_BYTES
        or png[:8] != b"\x89PNG\r\n\x1a\n"
        or png[12:16] != b"IHDR"
    ):
        raise ValueError("A bounded PNG is required.")
    width, height = struct.unpack(">II", png[16:24])
    if not 1 <= width <= 1920 or not 1 <= height <= 1920:
        raise ValueError("PNG dimensions exceed supported bounds.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z -]{0,79}", concept):
        raise ValueError("Concept must be a short noun phrase.")
    body = {
        "model": "sam-3.1",
        "store": False,
        "stream": True,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept},
                    {
                        "type": "input_image",
                        "image_url": "data:image/png;base64,"
                        + base64.b64encode(png).decode("ascii"),
                    },
                ],
            }
        ],
    }
    try:
        with (
            httpx.Client(
                timeout=90, follow_redirects=False, trust_env=False, transport=transport
            ) as client,
            client.stream(
                "POST",
                f"{META_API_BASE_URL}/responses",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "text/event-stream"},
                json=body,
            ) as response,
        ):
            MetaModelClient._raise_for_inference_status(response.status_code)
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raise ValueError("invalid stream content type")
            chunks: list[str] = []
            count = 0
            completed = False
            for line in response.iter_lines():
                count += len(line.encode("utf-8"))
                if count > MAX_STREAM_BYTES:
                    raise ValueError("stream exceeds limit")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if not isinstance(event, dict):
                    raise ValueError("invalid event")
                event_type = event.get("type")
                if event_type in {"error", "response.failed", "response.incomplete"}:
                    raise ValueError("provider stream failed")
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if not isinstance(delta, str):
                        raise ValueError("invalid delta")
                    chunks.append(delta)
                if event_type == "response.completed":
                    result = event.get("response")
                    if not isinstance(result, dict) or result.get("model") != "sam-3.1":
                        raise ValueError("unexpected model")
                    if result.get("status") != "completed":
                        raise ValueError("incomplete response")
                    completed = True
            if not completed:
                raise ValueError("missing terminal completion")
            output = "".join(chunks)
            if output and not output.startswith("<0f>"):
                raise ValueError("unexpected image frame")
            matches = list(BOX_PATTERN.finditer(output))
            if len(matches) > 100 or len(matches) != output.count("<|box;"):
                raise ValueError("malformed boxes")
            boxes = []
            for match in matches:
                x1, y1, x2, y2, w, h = map(int, match.groups())
                if (w, h) != (width, height) or not (0 <= x1 <= x2 < w and 0 <= y1 <= y2 < h):
                    raise ValueError("box is outside source image")
                boxes.append(ImageBox(x1, y1, x2, y2, w, h))
            return tuple(boxes)
    except httpx.ConnectError:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Meta could not be reached.", retryable=True
        ) from None
    except httpx.HTTPError:
        raise ProviderError(
            "OUTCOME_UNKNOWN", "Meta request outcome is unknown.", retryable=False
        ) from None
    except (TypeError, ValueError):
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "SAM response failed validation.", retryable=False
        ) from None
