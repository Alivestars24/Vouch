from __future__ import annotations

import json
import struct

import httpx
import pytest

from vouch_backend.meta_sam import segment_image
from vouch_backend.providers import ProviderError

KEY = "test-provider-credential-123456"
PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 100, 100)


def stream(output: str, *, complete: bool = True) -> httpx.Response:
    events = [{"type": "response.output_text.delta", "delta": output}]
    if complete:
        events.append(
            {"type": "response.completed", "response": {"model": "sam-3.1", "status": "completed"}}
        )
    data = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    return httpx.Response(200, text=data, headers={"content-type": "text/event-stream"})


def test_sam_stream_validates_box_and_terminal_event() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["stream"] is True
        return stream("<0f>0<|box;x1=1;y1=2;x2=50;y2=70;w=100;h=100|>")

    result = segment_image(KEY, PNG, concept="glasses", transport=httpx.MockTransport(handler))
    assert len(result) == 1
    assert result[0].x2 == 50


def test_zero_matches_is_valid_only_with_completed_stream() -> None:
    result = segment_image(
        KEY, PNG, concept="glasses", transport=httpx.MockTransport(lambda _: stream(""))
    )
    assert result == ()
    with pytest.raises(ProviderError):
        segment_image(
            KEY,
            PNG,
            concept="glasses",
            transport=httpx.MockTransport(lambda _: stream("", complete=False)),
        )


def test_out_of_bounds_box_fails_closed() -> None:
    data = "<0f>0<|box;x1=1;y1=2;x2=101;y2=70;w=100;h=100|>"
    with pytest.raises(ProviderError) as error:
        segment_image(
            KEY, PNG, concept="glasses", transport=httpx.MockTransport(lambda _: stream(data))
        )
    assert error.value.code == "INVALID_PROVIDER_OUTPUT"
